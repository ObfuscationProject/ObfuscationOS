"""Synthetic journal controls only; these tests never execute child policy."""
from pathlib import Path
import re
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import native_child_exit_guest as guest

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')


def wire(arch, code, pid, uid, status):
    # Independently assembled fixed words; no call into the parser codec.
    endian = 'big' if arch in ('mips', 'mips64', 'ppc') else 'little'
    wide = arch in ('x86_64', 'aarch64', 'rv64', 'loongarch64', 'mips64')
    words = [18 if arch.startswith('mips') else 17, code, 0] if arch.startswith('mips') else [17, 0, code]
    if wide: words += [0]
    words += [pid, uid, status]
    return (b''.join(value.to_bytes(4, endian) for value in words) + bytes(128))[:128]


def fixture(arch='x86_64'):
    lines = []
    chld = 18 if arch.startswith('mips') else 17
    usr1 = 16 if arch.startswith('mips') else 10
    for case in range(18):
        pid = 100 + case * 3; child = pid + 1; second = pid + 2; seq = 0
        lines += [f'CHILD_EXIT_BEGIN arch={arch} case={case} parent=5',
                  f'CHILD_EXIT_CASE arch={arch} case={case} pid={pid} uid=1000']
        def e(op, a, b, c):
            nonlocal seq
            lines.append(f'CHILD_EXIT_EVENT arch={arch} case={case} seq={seq} op={op} a={a} b={b} c={c}')
            seq += 1
        def info(who, status, code=1, via='wait'):
            nonlocal seq
            lines.append(f'CHILD_EXIT_INFO arch={arch} case={case} seq={seq} via={via} signal={chld} code={code} child={who} uid=1000 status={status} bytes=128 hex={wire(arch,code,who,1000,status).hex()}')
            seq += 1
        def child_run(slot, who, status, wait=True):
            e('SPAWN', slot, who, status); e('RELEASE', slot, who, 0)
            if wait: e('WAIT', slot, who, status)
        if case < 12:
            kind, mask, no_wait = case // 4, case // 2 % 2, case % 2
            h = int(kind == 2 and mask == 0)
            e('CONFIG', kind, no_wait, mask); child_run(0, child, 9472, False)
            if mask == 1 and kind != 1:
                e('PENDING', 1, 1, 0); info(child, 37); e('PENDING', 0, 1, 0)
            elif kind == 2: info(child, 37, via='handler')
            e('ECHILD' if kind == 1 or no_wait else 'WAIT', 0, child, 0 if kind == 1 or no_wait else 9472)
            e('PENDING', 0, mask, h); e('ABSENT', 11, mask, h)
        else:
            h = 0; e('CONFIG', 2, 0, 1)
            if case == 12:
                child_run(0, child, 15, False); info(child, 15, 2); e('WAIT', 0, child, 15)
            elif case == 13:
                child_run(0, child, 10496); e('PENDING', 1, 1, 0)
                child_run(1, second, 10752); e('PENDING', 1, 1, 0); info(child, 41)
            elif case == 14:
                e('SEND_USER', pid, chld, 0); e('PENDING', 1, 1, 0)
                child_run(0, child, 11008); e('PENDING', 1, 1, 0); info(pid, 0, 0)
            elif case == 15:
                child_run(0, child, 11264, False); e('PENDING', 1, 1, 0); e('CONFIG', 1, 0, 1)
                e('PENDING', 0, 1, 0); e('WAIT', 0, child, 11264); e('ABSENT', 11, 1, 0)
                e('CONFIG', 2, 0, 1); child_run(1, second, 11520, False); e('PENDING', 1, 1, 0)
                e('CONFIG', 2, 1, 1); e('PENDING', 1, 1, 0); e('WAIT', 1, second, 11520); info(second, 45)
            elif case == 16:
                child_run(0, child, 11776, False); e('PENDING', 1, 1, 0); e('SPAWN', 1, second, 0)
                e('INHERIT', second, 1, 0); e('INHERIT_ACTION', 2, 0, 1); e('WAIT', 1, second, 0)
                e('WAIT', 0, child, 11776); e('PENDING', 1, 1, 0); info(child, 46)
            else:
                child_run(0, child, 12032, False); e('PENDING', 1, 1, 0); e('EXEC_FAILED', 2, 2, 1)
                e('EXEC_CHECK', pid, 0, 1); e('IGNORE_CHECK', usr1, 1, 0)
                e('PENDING', 1, 1, 0); info(child, 47); e('WAIT', 0, child, 12032)
            e('PENDING', 0, 1, 0); e('ABSENT', 11, 1, 0)
        lines += [f'CHILD_EXIT_DONE arch={arch} case={case} pid={pid} events={seq} handlers={h}',
                  f'CHILD_EXIT_REAP arch={arch} case={case} parent=5 child={pid} status=0']
    lines.append(f'CHILD_EXIT_PASS {arch} cases=18 policy=12 killed=1 coalesced=1 user_first=1 no_retro=2 fork=1 exec=1 bytes=128')
    return ('\n'.join(lines) + '\n').encode()


class ChildExitJournal(unittest.TestCase):
    def test_complete_all_profiles_and_crlf(self):
        for arch in ARCHES:
            for crlf in (False, True):
                source = fixture(arch)
                if crlf: source = source.replace(b'\n', b'\r\n')
                with self.subTest(arch=arch, crlf=crlf):
                    result = guest.guest_events(source, arch)
                    self.assertEqual(result['count'], 18)
                    self.assertFalse(result['native_execution'])
                    self.assertEqual(sum(len(c['children']) for c in result['cases']), 21)
                    self.assertEqual(sum(c['handlers'] for c in result['cases']), 2)
                    self.assertEqual(guest.probe_spec(arch)[3], 40)

    def test_no_deleted_duplicated_or_reordered_marker(self):
        original = fixture().splitlines(keepends=True)
        for index, line in enumerate(original):
            for mutation in (b'', line + line, b'prefix ' + line):
                with self.subTest(index=index, mutation=mutation[:20]), self.assertRaises(ValueError):
                    guest.guest_events(b''.join(original[:index]) + mutation + b''.join(original[index+1:]), 'x86_64')
            if index:
                changed = original.copy(); changed[index-1], changed[index] = changed[index], changed[index-1]
                with self.subTest(index=index, reorder=True), self.assertRaises(ValueError):
                    guest.guest_events(b''.join(changed), 'x86_64')

    def test_ownership_and_operations_cannot_be_forged(self):
        for arch in ARCHES:
            lines = fixture(arch).splitlines(keepends=True)
            for index, line in enumerate(lines):
                if not line.startswith((b'CHILD_EXIT_EVENT ', b'CHILD_EXIT_REAP ', b'CHILD_EXIT_CASE ', b'CHILD_EXIT_DONE ')):
                    continue
                for field in (b'a', b'b', b'c', b'pid', b'child', b'parent', b'events', b'handlers'):
                    pattern = rb'\b' + field + rb'=(-?[0-9]+)'
                    match = re.search(pattern, line)
                    if not match: continue
                    value = int(match[1]); changed = re.sub(pattern, field + b'=' + str(value + 1).encode(), line)
                    # SPAWN is the sole child-identity capture; later exact references reject it.
                    with self.subTest(arch=arch, index=index, field=field), self.assertRaises(ValueError):
                        guest.guest_events(b''.join(lines[:index]) + changed + b''.join(lines[index+1:]), arch)

    def test_full_wire_padding_clock_and_first_payload(self):
        for arch in ARCHES:
            lines = fixture(arch).splitlines(keepends=True)
            for index, line in enumerate(lines):
                if not line.startswith(b'CHILD_EXIT_INFO '): continue
                original = re.search(rb'hex=([0-9a-f]{256})', line)[1]
                for offset in (0, 4, 8, 12, 16, 20, 24, 28, 32, 48, 64, 127):
                    raw = bytearray.fromhex(original.decode()); raw[offset] ^= 1
                    changed = line.replace(original, raw.hex().encode())
                    with self.subTest(arch=arch, index=index, offset=offset), self.assertRaises(ValueError):
                        guest.guest_events(b''.join(lines[:index]) + changed + b''.join(lines[index+1:]), arch)
                for field in (b'child', b'uid', b'code', b'status', b'signal'):
                    changed = re.sub(rb'\b' + field + rb'=[0-9]+', field + b'=9999', line)
                    with self.subTest(arch=arch, index=index, field=field), self.assertRaises(ValueError):
                        guest.guest_events(b''.join(lines[:index]) + changed + b''.join(lines[index+1:]), arch)

    def test_strict_namespace_and_aggregate(self):
        source = fixture()
        bad = (source[:-1], b'CHILD_EXIT_FAIL line=1\n' + source,
               source + b'CHILD_EXIT_EVENT invalid\n', source.replace(b'case=17', b'case=18'),
               source.replace(b'arch=x86_64', b'arch=rv64', 1), source.replace(b'bytes=128', b'bytes=64', 1),
               source.replace(b'hex=', b'HEX=', 1), source.replace(b'CHILD_EXIT_PASS', b'CHILD_EXIT_PASS_BAD'))
        for changed in bad:
            with self.subTest(source=changed[-100:]), self.assertRaises(ValueError): guest.guest_events(changed, 'x86_64')
        self.assertEqual(guest.guest_events(b'OK_NATIVE_CHILD_EXIT invalid\n'+source, 'x86_64')['count'], 18)
        # Kernel namespace validation deliberately belongs to the root collector.
        with self.assertRaises(ValueError): guest.probe_spec('unsupported')
        with self.assertRaises(ValueError): guest.probe_spec('x86_64', 'wrong-kind')


if __name__ == '__main__': unittest.main()
