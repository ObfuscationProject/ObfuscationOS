"""Synthetic corruption controls, not executed guest evidence."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from private_futex_evidence import MARKER, validate_execution
from object_pressure_evidence import ARCH_TRIPLES


def frame(allocations, releases, source):
    used = allocations-releases
    return (f'OK_NATIVE_FRAMES version=2 source={source} used={used} total=1024 allocations={allocations} '
            f'releases={releases} pinned=0 user={used} objects=0 free={1024-used} pending=0 reserve=10 user_limit=1014\n').encode()


def spans(source='firmware'):
    return [b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw\nOK_SYSTEM_GUI boot=complete\n'+frame(0,0,source)+b'hello from ObfuscationOS userland\n'+frame(19,0,source)+b'oksh> ',
            b'hello | cat\nhello from ObfuscationOS userland\n'+frame(100,60,source)+b'oksh> ',
            b'private-futex\n'+MARKER+b'\n'+frame(200,160,source)+b'oksh> ',
            b'private-futex\n'+MARKER+b'\n'+frame(300,260,source)+b'oksh> ',
            b'hello | cat\nhello from ObfuscationOS userland\n'+frame(400,360,source)+b'oksh> ']


def validate(parts, arch='x86_64'):
    boundaries = [sum(map(len,parts[:i])) for i in range(1,5)]
    return validate_execution(b''.join(parts), *boundaries, boundaries[-1], arch)


class Evidence(unittest.TestCase):
    def test_ten_sources(self):
        for arch in ARCH_TRIPLES:
            source = 'linker' if arch in ('mips', 'mips64', 'loongarch64') else 'firmware'
            self.assertEqual(validate(spans(source), arch)['runs'], 2)

    def test_missing_partial_duplicate_outside_marker(self):
        for index in range(5):
            variants = [MARKER+b'\n', b'prefix '+MARKER+b'\n', MARKER, MARKER.replace(b'pass',b'fail')+b'\n']
            for mutation in variants:
                parts=spans()
                if index in (2,3):parts[index]=parts[index].replace(MARKER+b'\n',mutation+MARKER+b'\n')
                else:parts[index]=mutation+parts[index]
                with self.subTest(index=index,mutation=mutation), self.assertRaises(ValueError):validate(parts)
        for index in (2,3):
            parts=spans();parts[index]=parts[index].replace(MARKER+b'\n',b'')
            with self.assertRaises(ValueError):validate(parts)

    def test_dedicated_pipeline_and_frames(self):
        for index in (1,4):
            parts=spans();parts[index]=parts[index].replace(b'hello from ObfuscationOS userland',b'missing')
            with self.assertRaises(ValueError):validate(parts)
        for index in (1,2,3,4):
            parts=spans();parts[index]=b''.join(line for line in parts[index].splitlines(keepends=True) if not line.startswith(b'OK_NATIVE_FRAMES'))
            with self.assertRaises(ValueError):validate(parts)

    def test_leaks_and_stale_counters(self):
        parts=spans();parts[2]=parts[2].replace(frame(200,160,'firmware'),frame(200,159,'firmware'))
        with self.assertRaises(ValueError):validate(parts)
        parts=spans();parts[3]=parts[3].replace(frame(300,260,'firmware'),frame(200,160,'firmware'))
        with self.assertRaises(ValueError):validate(parts)
        parts=spans();parts[1]=parts[1].replace(frame(100,60,'firmware'),frame(19,0,'firmware'))
        with self.assertRaises(ValueError):validate(parts)

    def test_qemu_termination_tail(self):
        parts=spans();parts[-1]+=b'qemu-system-x86_64: terminating on signal 15 from pid 5 (python3)\n'
        self.assertEqual(validate(parts)['runs'],2)
        parts=spans();parts[-1]+=b'qemu-system-x86_64: terminating on signal 15 from pid 1147 (/usr/bin/python3)\n'
        self.assertEqual(validate(parts)['runs'],2)
        for tail in (b'partial',b'OK_TEST_FAIL x\n',b'\n'):
            parts=spans();parts[-1]+=tail
            with self.assertRaises(ValueError):validate(parts)

    def test_boundaries_and_failures(self):
        parts=spans();data=b''.join(parts);bounds=[sum(map(len,parts[:i])) for i in range(1,5)];bounds.append(bounds[-1])
        for i in range(5):
            for value in (0,-1,True,1.5,'1',len(data),bounds[i]-1):
                changed=bounds.copy();changed[i]=value
                with self.subTest(i=i,value=value), self.assertRaises(ValueError):validate_execution(data,*changed,'x86_64')
        for marker in (b'FUTEX_FAIL', b'OK_TEST_FAIL', b'boot=degraded'):
            parts=spans();parts[2]=marker+b'\n'+parts[2]
            with self.assertRaises(ValueError):validate(parts)


if __name__ == '__main__':unittest.main()
