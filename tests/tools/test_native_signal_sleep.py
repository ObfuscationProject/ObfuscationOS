"""Synthetic sleep collector controls; none of these execute a guest."""
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'tests/tools'))
import native_signal_sleep_evidence as evidence
from test_native_signal_delivery_x86_64 import frames, stacks, IMAGE

ARCHES = ('i386','x86_64','arm32','aarch64','rv32','rv64','loongarch64','mips','mips64','ppc')


def events(arch):
    # Independent fixture enumeration: libc forms omit raw copyout-fault cases;
    # nanosleep omits absolute cases; raw clock forms exercise all sixteen.
    formats = [(0,'time64'),(1,'time64'),(2,'time64'),(3,'time64')]
    if arch in ('i386','arm32','mips','ppc'):
        formats = [(0,'time32'),(1,'time32'),(2,'time32'),(3,'time32'),(4,'time64')]
    elif arch == 'rv32':
        formats = [(0,'time64'),(1,'time64'),(4,'time64')]
    output = []
    for form, fmt in formats:
        cases = {0:(0,1,2,3,4,5,6,7,8,15),
                 1:(0,1,2,3,4,5,6,7,8,11,12,13,14,15),
                 2:(0,1,2,3,4,5,6,7,8,9,10,15)}.get(form, tuple(range(16)))
        pid = 200+form
        generation = 0
        for case in cases:
            result = 'eintr' if case in (0,1,2,3,4,11,12) else ('efault' if case in (9,10) else 'success')
            kind = 'absolute' if case in (11,12,13,14) else 'relative'
            count = 2 if case == 14 else int(result != 'success')
            output.append(f'SLEEP_SIGNAL_CASE_BEGIN arch={arch} form={form} case={case} pid={pid} tid={pid} expected={result} format={fmt} kind={kind} interrupts={count}\n')
            for index in range(count):
                generation += 1
                diagnostic = 'efault' if result == 'efault' else 'eintr'
                output.append(f'OK_NATIVE_SLEEP_INTERRUPT pid={pid} tid={pid} wait={generation} kind={kind} format={fmt} result={diagnostic} deadline=100000 now={1000+index}\n')
            output.append(f'SLEEP_SIGNAL_CASE_PASS arch={arch} form={form} case={case}\n')
    return ''.join(output).encode()


def fixture(arch):
    wide = arch not in ('i386','arm32','mips','ppc')
    forms, cases, interrupts, faults, leases = (4,52,32,4,47) if wide else (5,68,43,6,61)
    if arch == 'rv32':
        forms, cases, interrupts, faults, leases = 3,40,25,2,36
    command = ('/bin/native-signal-sleep-'+('la64' if arch == 'loongarch64' else arch.replace('_','-'))).encode()
    marker = f'SLEEP_SIGNAL_PASS arch={arch} forms={forms} cases={cases} interrupts={interrupts} efault={faults} guards=1 parent=1'.encode()
    output = command+b'\n'+IMAGE+events(arch)+marker+b'\n'
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+frames(0,0)+stacks(0,0,0,peak=0)+frames(40,0)+stacks(7,5,100)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(100,60)+stacks(10,8,200)+b'oksh> ',
        output+frames(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
        output+frames(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ',
    ]
    if arch in ('loongarch64','mips','mips64'):
        parts = [p.replace(b'source=firmware',b'source=linker') for p in parts]
    return parts


def validate(parts, arch):
    ends = [sum(map(len, parts[:i])) for i in range(1,5)]
    return evidence.validate_execution(b''.join(parts),*ends,ends[-1],arch)


class SleepEvidence(unittest.TestCase):
    def test_all_profiles(self):
        for arch in ARCHES:
            for newline in (b'\n',b'\r\n'):
                with self.subTest(arch=arch,newline=newline):
                    r = validate([p.replace(b'\n',newline) for p in fixture(arch)],arch)
                    expected = (68,5,43,6) if arch in ('i386','arm32','mips','ppc') else (52,4,32,4)
                    if arch == 'rv32': expected = (40,3,25,2)
                    self.assertEqual(tuple(r['observations'][0][k] for k in ('cases','forms','interruptions','efault')),expected)
                    self.assertEqual(r['observations'][0],r['observations'][1])
                    self.assertTrue(r['blocked_wait_interruption'])
                    self.assertFalse(r['pipe_restart'])

    def test_diagnostic_and_case_mutations(self):
        for arch in ARCHES:
            good = fixture(arch)
            for index in (2,3):
                original = good[index]
                lines = original.splitlines(keepends=True)
                di = next(i for i,l in enumerate(lines) if l.startswith(b'OK_NATIVE_SLEEP_INTERRUPT'))
                first = lines[di]
                image = IMAGE.replace(b'firmware',b'linker') if arch in ('loongarch64','mips','mips64') else IMAGE
                mutations = {
                    'missing-interrupt': original.replace(first,b'',1),
                    'duplicate-interrupt': original.replace(first,first+first,1),
                    'wrong-owner': original.replace(first,first.replace(b'pid=200',b'pid=201'),1),
                    'wrong-thread': original.replace(first,first.replace(b'tid=200',b'tid=201'),1),
                    'stale-ticket': original.replace(b'wait=2 ',b'wait=1 ',1),
                    'zero-ticket': original.replace(b'wait=1 ',b'wait=0 ',1),
                    'overflow-ticket': original.replace(b'wait=1 ',b'wait=18446744073709551616 ',1),
                    'expired': original.replace(b'deadline=100000 ',b'deadline=1000 ',1),
                    'negative-time': original.replace(b'now=1000',b'now=-1',1),
                    'overflow-deadline': original.replace(b'deadline=100000',b'deadline=18446744073709551616',1),
                    'shifted-absolute-deadline': original.replace(b'deadline=100000 now=1001',b'deadline=100001 now=1001',1),
                    'nonadvancing-time': original.replace(b'now=1001',b'now=1000',1),
                    'diagnostic-before-case': original.replace(first,b'',1).replace(image,image+first,1),
                    'wrong-result': original.replace(b'result=eintr',b'result=efault',1),
                    'wrong-kind': original.replace(first,first.replace(b'kind=relative',b'kind=absolute'),1),
                    'wrong-format': original.replace(first,first.replace(b'format=time32',b'format=bad').replace(b'format=time64',b'format=bad'),1),
                    'bad-line': original.replace(first,b'junk '+first,1),
                    'wrong-case-order': original.replace(b'case=0 ',b'case=1 ',1),
                    'missing-case-completion': original.replace(f'SLEEP_SIGNAL_CASE_PASS arch={arch} form=0 case=0\n'.encode(),b'',1),
                    'early-aggregate': original.replace(image,image+evidence.probe_spec(arch,'sleep-signals')[0]+b'\n',1),
                    'wrong-final-count': original.replace(b'guards=1 parent=1',b'guards=0 parent=1'),
                    'child-failure': original.replace(b'oksh> ',b'SLEEP_SIGNAL_FAIL code=100\noksh> '),
                    'contained-fault': original.replace(b'oksh> ',b'OK_NATIVE scope=hardware fault=contained\noksh> '),
                    'missing-image': original.replace(IMAGE.replace(b'firmware',b'linker') if arch in ('loongarch64','mips','mips64') else IMAGE,b''),
                    'unexpected-output': original.replace(b'oksh> ',b'junk\noksh> '),
                }
                for label, changed in mutations.items():
                    with self.subTest(arch=arch,index=index,label=label):
                        self.assertTrue(original != changed, 'control must change bytes')
                        parts=good.copy();parts[index]=changed
                        with self.assertRaises(ValueError):validate(parts,arch)
            for index in (0,1,4):
                parts=good.copy();parts[index]=b'OK_NATIVE_SLEEP_INTERRUPT invalid\n'+parts[index]
                with self.subTest(arch=arch,outside=index),self.assertRaises(ValueError):validate(parts,arch)

    def test_native_pipelines_reject_linux_images(self):
        for arch in ARCHES:
            for index in (1,4):
                for newline in (b'\n',b'\r\n'):
                    with self.subTest(arch=arch,index=index,newline=newline):
                        parts = fixture(arch)
                        extra = IMAGE.replace(b'firmware',b'linker') if arch in ('loongarch64','mips','mips64') else IMAGE
                        parts[index] = parts[index].replace(b'hello from ObfuscationOS userland\n',
                            b'hello from ObfuscationOS userland\n'+extra)
                        with self.assertRaisesRegex(ValueError,'unexpected Linux image'):
                            validate([p.replace(b'\n',newline) for p in parts],arch)

    def test_runner_freeze_admission_roundtrip(self):
        from object_pressure_evidence import admit_sources, sha
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp)/'source.json'
            run = subprocess.run([sys.executable,'-B',str(ROOT/'tools/qualify_native_signal_sleep.py'),
                                  'freeze','--output',str(inventory)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(run.stdout.strip(),sha(inventory))
            self.assertIn('tools/native_signal_sleep_evidence.py',admit_sources(ROOT,inventory,sha(inventory))['files'])

    def test_failure_draining(self):
        for suffix in (b'',b' code=',b' code=100\r'):
            self.assertTrue(evidence.incomplete_failure_line(b'SLEEP_SIGNAL_FAIL'+suffix))
        self.assertFalse(evidence.incomplete_failure_line(b'SLEEP_SIGNAL_FAIL code=100\n'))
        self.assertIn('code=100',evidence.failure_line(b'SLEEP_SIGNAL_FAIL code=100\n'))


if __name__ == '__main__':
    unittest.main()
