"""Exact user marker journal for child-exit policy; parsing is not execution.

The integration collector separately validates SDK/IMAGE provenance, kernel
EXIT/REAP/WAIT lifetimes, command boundaries and resource accounting.
"""
import re

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv32', 'rv64',
          'loongarch64', 'mips', 'mips64', 'ppc')
WIDE = ('x86_64', 'aarch64', 'rv64', 'loongarch64', 'mips64')
BIG = ('mips', 'mips64', 'ppc')
MARKER = b'CHILD_EXIT_PASS {arch} cases=18 policy=12 killed=1 coalesced=1 user_first=1 no_retro=2 fork=1 exec=1 bytes=128'
PREFIX = b'CHILD_EXIT_'
KEY = rb' arch=([a-z0-9_]+) case=([0-9]+)'
BEGIN = re.compile(rb'CHILD_EXIT_BEGIN' + KEY + rb' parent=([0-9]+)')
CASE = re.compile(rb'CHILD_EXIT_CASE' + KEY + rb' pid=([0-9]+) uid=([0-9]+)')
EVENT = re.compile(rb'CHILD_EXIT_EVENT' + KEY + rb' seq=([0-9]+) op=([A-Z_]+) a=(-?[0-9]+) b=(-?[0-9]+) c=(-?[0-9]+)')
INFO = re.compile(rb'CHILD_EXIT_INFO' + KEY + rb' seq=([0-9]+) via=(wait|handler) signal=([0-9]+) code=(-?[0-9]+) child=([0-9]+) uid=([0-9]+) status=([0-9]+) bytes=128 hex=([0-9a-f]{256})')
DONE = re.compile(rb'CHILD_EXIT_DONE' + KEY + rb' pid=([0-9]+) events=([0-9]+) handlers=([0-9]+)')
REAP = re.compile(rb'CHILD_EXIT_REAP' + KEY + rb' parent=([0-9]+) child=([0-9]+) status=0')
PATTERNS = (BEGIN, CASE, EVENT, INFO, DONE, REAP)


def probe_spec(arch, kind='child-exit-policy'):
    if arch not in ARCHES or kind != 'child-exit-policy':
        raise ValueError('unsupported child-exit policy profile')
    suffix = 'la64' if arch == 'loongarch64' else arch.replace('_', '-')
    # One main + 18 scenario processes + 21 children/inspector.
    # Successful leader exec keeps its existing canonical entry-stack lease.
    return MARKER.replace(b'{arch}', arch.encode()), b'CHILD_EXIT_PASS', ('/bin/native-child-exit-' + suffix).encode(), 40


def failure_line(serial):
    if b'CHILD_EXIT_FAIL' in serial:
        return 'child-exit guest assertion failed: ' + serial[serial.index(b'CHILD_EXIT_FAIL'):].split(b'\n', 1)[0].decode(errors='replace')
    return None


def incomplete_failure_line(serial):
    return b'CHILD_EXIT_FAIL' in serial and b'\n' not in serial[serial.index(b'CHILD_EXIT_FAIL'):]


def expected_info(arch, code, child, uid, status):
    """Independent target wire offsets, including MIPS header order and padding."""
    if arch not in ARCHES or code not in (0, 1, 2):
        raise ValueError('invalid expected child-exit payload profile/code')
    if not 0 < child <= 0xffffffff or not 0 <= uid <= 0xffffffff or not 0 <= status <= 255:
        raise ValueError('invalid expected child-exit payload values')
    if code == 0 and status != 0:
        raise ValueError('user signal cannot carry child status')
    data = bytearray(128)
    endian = 'big' if arch in BIG else 'little'
    offset = 16 if arch in WIDE else 12
    for at, value in ((0, 18 if arch.startswith('mips') else 17),
                      (4 if arch.startswith('mips') else 8, code),
                      (offset, child), (offset + 4, uid), (offset + 8, status)):
        data[at:at + 4] = value.to_bytes(4, endian)
    return bytes(data)


def scenario(case):
    """Exact observable script. Symbols are captured only by owned SPAWN rows."""
    config = lambda kind=2, no_wait=0, blocked=1: ('CONFIG', kind, no_wait, blocked)
    spawn = lambda slot, status: ('SPAWN', slot, '$child' + str(slot), status)
    release = lambda slot: ('RELEASE', slot, '$child' + str(slot), 0)
    wait = lambda slot, status: ('WAIT', slot, '$child' + str(slot), status)
    pending = lambda value, mask=1, handlers=0: ('PENDING', value, mask, handlers)
    absent = lambda mask=1, handlers=0: ('ABSENT', 11, mask, handlers)
    info = lambda child, status, via='wait', code=1: ('INFO', via, code, child, status)
    if 0 <= case < 12:
        kind, mask, no_wait = case // 4, case // 2 % 2, case % 2
        handlers = int(kind == 2 and not mask)
        rows = [config(kind, no_wait, mask), spawn(0, 37 << 8), release(0)]
        if mask and kind != 1:
            rows += [pending(1), info('$child0', 37), pending(0)]
        elif kind == 2:
            rows += [info('$child0', 37, 'handler')]
        rows += [('ECHILD', 0, '$child0', 0) if kind == 1 or no_wait else wait(0, 37 << 8),
                 pending(0, mask, handlers), absent(mask, handlers)]
        return rows
    if case == 12:
        return [config(), spawn(0, 15), release(0), info('$child0', 15, code=2), wait(0, 15), pending(0), absent()]
    if case == 13:
        return [config(), spawn(0, 41 << 8), release(0), wait(0, 41 << 8), pending(1),
                spawn(1, 42 << 8), release(1), wait(1, 42 << 8), pending(1), info('$child0', 41), pending(0), absent()]
    if case == 14:
        return [config(), ('SEND_USER', '$owner', '$chld', 0), pending(1), spawn(0, 43 << 8),
                release(0), wait(0, 43 << 8), pending(1), info('$owner', 0, code=0), pending(0), absent()]
    if case == 15:
        return [config(), spawn(0, 44 << 8), release(0), pending(1), config(1), pending(0), wait(0, 44 << 8), absent(),
                config(), spawn(1, 45 << 8), release(1), pending(1), config(2, 1), pending(1), wait(1, 45 << 8),
                info('$child1', 45), pending(0), absent()]
    if case == 16:
        return [config(), spawn(0, 46 << 8), release(0), pending(1), spawn(1, 0),
                ('INHERIT', '$child1', 1, 0), ('INHERIT_ACTION', 2, 0, 1), wait(1, 0), wait(0, 46 << 8),
                pending(1), info('$child0', 46), pending(0), absent()]
    if case == 17:
        return [config(), spawn(0, 47 << 8), release(0), pending(1), ('EXEC_FAILED', 2, 2, 1),
                ('EXEC_CHECK', '$owner', 0, 1), ('IGNORE_CHECK', '$usr1', 1, 0), pending(1),
                info('$child0', 47), wait(0, 47 << 8), pending(0), absent()]
    raise ValueError('invalid child-exit scenario')


def guest_events(span, arch):
    """Validate one complete 18-case probe command and return owned observations.

    Other namespaces are retained in the original span for the integration
    collector. Any malformed, prefixed or incomplete CHILD_EXIT line is fatal.
    """
    marker, _, _, _ = probe_spec(arch)
    if error := failure_line(span):
        raise ValueError(error)
    lines = []
    for raw in span.splitlines(keepends=True):
        if PREFIX not in raw:
            continue
        if not raw.endswith(b'\n'):
            raise ValueError('incomplete child-exit guest marker')
        line = raw[:-1].removesuffix(b'\r')
        if line == marker:
            lines.append(('PASS', line)); continue
        pattern = next((p for p in PATTERNS if p.fullmatch(line)), None)
        if pattern is None:
            raise ValueError('malformed child-exit guest marker')
        fields = dict(field.decode().split('=', 1) for field in line.split()[1:])
        for key in fields.keys() - {'arch', 'op', 'via', 'hex'}:
            fields[key] = int(fields[key])
        if fields['arch'] != arch:
            raise ValueError('child-exit guest architecture mismatch')
        fields['line'] = line
        lines.append((pattern, fields))
    index = 0
    def take(pattern, case):
        nonlocal index
        if index >= len(lines) or lines[index][0] is not pattern:
            raise ValueError('missing or reordered child-exit marker')
        row = lines[index][1]; index += 1
        if row['case'] != case:
            raise ValueError('missing, duplicate or reordered child-exit case')
        return row
    master = None; cases = []; exact = []
    for case in range(18):
        begin = take(BEGIN, case); owner = take(CASE, case)
        if not (0 < begin['parent'] <= 0xffffffff and 0 < owner['pid'] <= 0xffffffff and
                owner['pid'] != begin['parent'] and 0 <= owner['uid'] <= 0xffffffff):
            raise ValueError('invalid child-exit process identity')
        if master is None: master = begin['parent']
        if begin['parent'] != master:
            raise ValueError('child-exit scenario changed controller')
        env = {'$owner': owner['pid'], '$chld': 18 if arch.startswith('mips') else 17,
               '$usr1': 16 if arch.startswith('mips') else 10}
        observed = []; script = scenario(case)
        for seq, step in enumerate(script):
            row = take(INFO if step[0] == 'INFO' else EVENT, case)
            if row['seq'] != seq:
                raise ValueError('missing, duplicate or reordered child-exit operation')
            if step[0] == 'SPAWN':
                child = row['b']
                if not 0 < child <= 0xffffffff or child in (master, owner['pid']) or child in [v for k, v in env.items() if k.startswith('$child')]:
                    raise ValueError('invalid or duplicate observed child owner')
                env[step[2]] = child
            resolve = lambda value: env[value] if isinstance(value, str) and value.startswith('$') else value
            if step[0] == 'INFO':
                _, via, code, child, status = step; child = resolve(child)
                if (row['via'], row['signal'], row['code'], row['child'], row['uid'], row['status']) != (
                        via, env['$chld'], code, child, owner['uid'], status):
                    raise ValueError('child-exit siginfo differs from expected first owned payload')
                if bytes.fromhex(row['hex']) != expected_info(arch, code, child, owner['uid'], status):
                    raise ValueError('child-exit full target siginfo bytes differ')
            elif (row['op'], row['a'], row['b'], row['c']) != tuple(resolve(value) for value in step):
                raise ValueError('child-exit operation differs from exact scenario policy')
            observed.append(row)
        done = take(DONE, case); reaped = take(REAP, case)
        handlers = int(case in (8, 9))
        if (done['pid'], done['events'], done['handlers']) != (owner['pid'], len(script), handlers):
            raise ValueError('child-exit scenario completion disagrees with observed operations')
        if (reaped['parent'], reaped['child']) != (master, owner['pid']):
            raise ValueError('child-exit controller reaped a different scenario process')
        cases.append(dict(case=case, parent=master, pid=owner['pid'], uid=owner['uid'],
                          children={k.removeprefix('$'): v for k, v in env.items() if k.startswith('$child')},
                          events=observed, handlers=handlers))
        exact += [begin['line'], owner['line'], *(r['line'] for r in observed), done['line'], reaped['line']]
    if index + 1 != len(lines) or lines[index] != ('PASS', marker):
        raise ValueError('missing, duplicate or misplaced aggregate child-exit success')
    return dict(cases=cases, count=18, policy_cases=12, target_info_bytes=128,
                architecture=arch, lines=exact + [marker], native_execution=False)
