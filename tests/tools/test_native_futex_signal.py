"""Synthetic transcript admissibility tests; these do not execute a native kernel."""
from pathlib import Path
import re
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_futex_signal_evidence as evidence
import native_futex_events as ledger
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
NUMBERS=dict(zip(ARCHES,((202,),(240,422),(98,),(240,422),(422,),(98,),(98,),(4238,4422),(5194,),(221,422))))
GETPID=dict(zip(ARCHES,(39,20,172,20,172,172,172,4020,5038,20)))

def events(arch):
    lines=[];forms=2 if arch in ('arm32','ppc') else 1
    maximum=(1 << (32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1
    for domain in range(2):
     for abi,number in enumerate(NUMBERS[arch]):
      for form in range(forms):
       pid=200+domain*4+abi*2+form
       for round_id in range(2):
        for case in range(19):
            tid=pid*100+round_id*19+case+1
            key=f'arch={arch} form={form} abi={abi} domain={domain} round={round_id} case={case}'
            owner=f'pid={pid} tid={tid}';address=268443648;alternate=address+64;op=128*domain;value=0x12345678+int(case==18)
            timed=case in (2,3,10,12,17);timeout=268447744 if timed else 0;deadline=1000000000 if timed else 0
            duration=0 if case==17 else 160000000 if case in (10,12) else 500000000
            width=2 if arch in ('x86_64','i386') or (arch=='arm32' and form==1) else 4
            site=1073750016+form*64;resume=site+width
            format='time64' if maximum>0xffffffff or number in (422,4422) else 'time32'
            lines.append(f'FUTEX_SIGNAL_CASE_BEGIN {key} {owner} number={number} address={address} alternate={alternate} operation={op} value={value} timeout={timeout} format={format} timed={int(timed)} duration={duration} site={site} resume={resume} wait={int(case<17)}')
            lines.append(f'FUTEX_SIGNAL_ATTEMPT {key} {owner} number={number} address={address} operation={op} value={value} timeout={timeout}')
            generation=0;active_address=address;active_value=value
            def inputs(pc):return f'pc={pc} syscall={number} address={active_address} operation={op} expected={active_value} timeout={timeout} deadline={deadline}'
            def identity():return f'{owner} wait={generation} origin={10*generation}'
            def arm():
                nonlocal generation,active_address,active_value
                generation+=1
                if case==8 and generation>1:active_address=alternate;active_value=0x87654321
                lines.append(f'OK_NATIVE_FUTEX_ARM {identity()} {inputs(resume)} format={format} live=1')
            def retire(reason):
                result=-110 if reason=='timeout' else -4 if reason=='interrupted' and case in (0,2,3) else 0
                lines.append(f'OK_NATIVE_FUTEX_RETIRE {identity()} reason={reason} result={result} live=0')
            def context(edited=False):
                inspected=case<=9 or case==16
                if not inspected:return 'pc=1073780000 inspected=0'
                restart=case not in (0,2,3);pc=site if restart else resume
                nr=number if restart or arch not in ('x86_64','i386','mips','mips64') else 4 if arch.startswith('mips') else maximum-3
                addr=address if restart or arch in ('x86_64','i386','mips','mips64') else 4 if arch=='ppc' else maximum-3
                argtime=1 if not restart and arch.startswith('mips') else timeout;expected=value
                cr=0x1a000001;diagnostic=0 if restart else maximum-3;orig=address
                if edited and case==5:
                    pc=resume
                    if arch in ('x86_64','i386','mips','mips64'):nr=77
                    else:addr=77
                    if arch.startswith('mips'):argtime=0
                    cr&=~0x10000000;diagnostic=0x123;orig=0x234
                if edited and case==6:nr=GETPID[arch]
                if edited and case in (7,8):expected=0x87654321
                if edited and case==8:addr=alternate
                result=f'pc={pc} inspected=1 number={nr} address={addr} operation={op} value={expected} timeout={argtime}'
                if arch=='ppc':result+=f' cr={cr} diagnostic_result={diagnostic} orig_r3={orig}'
                if arch=='arm32':result+=f' cpsr={0x10+(0x20 if form else 0)}'
                return result
            def handler(ordinal):
                lines.append(f'FUTEX_SIGNAL_HANDLE {key} {owner} ordinal={ordinal} '+context())
                if case==16:lines.append(f'FUTEX_SIGNAL_NESTED {key} {owner} ordinal=1 pc=1073780000 inspected=0')
                lines.append(f'FUTEX_SIGNAL_HANDLER_RETURN {key} {owner} ordinal={ordinal} '+context(True))
            def signal(ordinal,delivered=True):
                signo=16 if arch.startswith('mips') else 10
                lines.append(f'FUTEX_SIGNAL_SEND {key} {owner} ordinal={ordinal} signal={signo}')
                if delivered:
                    if case<=9 or case==16:
                        retire('interrupted');outcome='eintr' if case in (0,2,3) else 'restart'
                        lines.append(f'OK_NATIVE_FUTEX_SIGNAL {identity()} signal={signo} outcome={outcome} {inputs(resume if outcome=="eintr" else site)} live=0')
                    handler(ordinal)
            def wake(addr,expected):
                lines.append(f'FUTEX_SIGNAL_WAKE {key} address={addr} operation={op+1} expected={expected}')
                if expected:retire('ready')
            def result():
                value=-4 if case in (0,2,3) else -11 if case in (4,7,18) else 77 if case==5 else pid if case==6 else -(145 if arch in ('mips','mips64') else 110) if case in (10,12,17) else 0
                elapsed=170000000 if case in (10,12) else 100000000
                lines.append(f'FUTEX_SIGNAL_RETURN {key} result={value} error=111 elapsed={elapsed}')
            if case<17:
                arm()
                if case<=9 or case==16:
                    signal(1)
                    if case==9:arm();signal(2)
                    if case in (1,8,9,16):
                        arm()
                        if case==8:wake(address,0)
                        wake(alternate if case==8 else address,1)
                    result()
                elif case==10:lines.append(f'FUTEX_SIGNAL_MUTATE_TIMEOUT {key}');retire('timeout');result()
                elif case==12:retire('timeout');result();signal(1)
                else:
                    if case in (14,15):signal(1,False)
                    wake(address,1);result()
                    if case==13:signal(1)
                    if case==14:lines.append(f'FUTEX_SIGNAL_UNMASK {key}');handler(1)
            else:result()
            wake(address,0);wake(alternate,0);lines.append(f'FUTEX_SIGNAL_CASE_PASS {key}')
    return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
    marker,_,command,leases=evidence.probe_spec(arch,'futex-signals')
    output=command+b'\n'+IMAGE+events(arch)+marker+b'\n'
    parts=[
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+frames(0,0)+stacks(0,0,0,peak=0)+frames(40,0)+stacks(7,5,100)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(100,60)+stacks(10,8,200)+b'oksh> ',
        output+frames(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
        output+frames(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ',
    ]
    if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
    return parts

def validate(parts,arch):
    ends=[sum(map(len,parts[:i])) for i in range(1,5)]
    return evidence.validate_execution(b''.join(parts),*ends,ends[-1],arch)

class FutexSignalEvidence(unittest.TestCase):
    def test_timeout_guest_errno_uses_target_abi_and_retirement_stays_canonical(self):
        target_errors=dict(x86_64=110,i386=110,aarch64=110,arm32=110,rv32=110,
            rv64=110,loongarch64=110,mips=145,mips64=145,ppc=110)
        for arch,error in target_errors.items():
            original=fixture(arch)
            self.assertEqual(validate(original,arch)['runs'],2)
            wrong=110 if error==145 else 145
            for index in (2,3):
                span=original[index];lines=span.splitlines(keepends=True)
                timeout_results=[line for line in lines if line.startswith(b'FUTEX_SIGNAL_RETURN ') and
                    re.search(rb' case=(10|12|17) ',line)]
                self.assertEqual(len(timeout_results),12*len(NUMBERS[arch])*(2 if arch in ('arm32','ppc') else 1))
                self.assertTrue(all(f' result=-{error} error=111 '.encode() in line for line in timeout_results))
                for abi in range(len(NUMBERS[arch])):
                    for case in (10,12,17):
                        key=f'form=0 abi={abi} domain=0 round=0 case={case} '.encode()
                        line=next(line for line in timeout_results if key in line)
                        changed=line.replace(f' result=-{error} '.encode(),f' result=-{wrong} '.encode())
                        self.assertNotEqual(line,changed)
                        parts=original.copy();parts[index]=span.replace(line,changed,1)
                        with self.subTest(arch=arch,index=index,abi=abi,case=case),self.assertRaises(ValueError):validate(parts,arch)
                terminal=next(line for line in lines if line.startswith(b'OK_NATIVE_FUTEX_RETIRE ') and b' reason=timeout ' in line)
                self.assertIn(b' result=-110 ',terminal)
                parts=original.copy();parts[index]=span.replace(terminal,terminal.replace(b' result=-110 ',b' result=-145 '),1)
                with self.subTest(arch=arch,index=index,canonical=True),self.assertRaises(ValueError):validate(parts,arch)

    def test_duplicate_boot_frame_snapshot(self):
        for arch in ARCHES:
            parts=fixture(arch)
            frame=next(row for row in parts[0].splitlines(keepends=True) if row.startswith(b'OK_NATIVE_FRAMES '))
            parts[0]=parts[0].replace(frame,frame+frame,1)
            with self.subTest(arch=arch),self.assertRaises(ValueError):validate(parts,arch)

    def test_ppc_eintr_preserves_diagnostic_result_and_original_r3(self):
        original=fixture('ppc')
        for case in (0,2,3):
            key=f'form=0 abi=0 domain=0 round=0 case={case} '.encode()
            for field in (b'diagnostic_result',b'orig_r3'):
                lines=original[2].splitlines(keepends=True);changed=0
                for index,line in enumerate(lines):
                    if line.startswith((b'FUTEX_SIGNAL_HANDLE ',b'FUTEX_SIGNAL_HANDLER_RETURN ')) and key in line:
                        lines[index]=re.sub(field+rb'=([0-9]+)',field+b'=999',line);changed+=1
                self.assertEqual(changed,2)
                parts=original.copy();parts[2]=b''.join(lines)
                with self.subTest(case=case,field=field),self.assertRaises(ValueError):validate(parts,'ppc')

    def test_all_profiles_and_line_endings(self):
        for arch in ARCHES:
            for newline in (b'\n',b'\r\n'):
                with self.subTest(arch=arch,newline=newline):
                    result=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch)
                    multiple=(2 if arch in ('arm32','ppc') else 1)*len(NUMBERS[arch])
                    for row in result['observations']:
                        for key,value in dict(cases=76,initial_waits=68,fresh_restart_waits=20,eintr=12,restart_publications=36,
                                ready_retirements=32,timeout_retirements=8,immediate=8,outer_handlers=60,nested_handlers=4,main_sends=64,wake_calls=188).items():
                            self.assertEqual(row[key],value*multiple,key)
                    self.assertFalse(result['timed_futex_restart']);self.assertFalse(result['physical'])

    def test_missing_duplicate_malformed_and_reordered_events(self):
        for arch in ARCHES:
            original=fixture(arch)
            for index in (2,3):
                span=original[index];lines=span.splitlines(keepends=True)
                tags=(b'FUTEX_SIGNAL_CASE_BEGIN',b'FUTEX_SIGNAL_ATTEMPT',b'OK_NATIVE_FUTEX_ARM',b'FUTEX_SIGNAL_SEND',b'OK_NATIVE_FUTEX_RETIRE',b'OK_NATIVE_FUTEX_SIGNAL',b'FUTEX_SIGNAL_HANDLE',b'FUTEX_SIGNAL_HANDLER_RETURN',b'FUTEX_SIGNAL_RETURN',b'FUTEX_SIGNAL_WAKE',b'FUTEX_SIGNAL_CASE_PASS',b'FUTEX_SIGNAL_MUTATE_TIMEOUT',b'FUTEX_SIGNAL_UNMASK',b'FUTEX_SIGNAL_NESTED')
                selected={tag:next(line for line in lines if line.startswith(tag+b' ')) for tag in tags}
                for tag,line in selected.items():
                    for name,replacement in (('missing',b''),('duplicate',line+line),('malformed',b'junk '+line)):
                        bad=original.copy();bad[index]=span.replace(line,replacement,1)
                        with self.subTest(arch=arch,index=index,tag=tag,name=name),self.assertRaises(ValueError):validate(bad,arch)
                arm=selected[b'OK_NATIVE_FUTEX_ARM'];send=selected[b'FUTEX_SIGNAL_SEND'];retire=selected[b'OK_NATIVE_FUTEX_RETIRE'];signal=selected[b'OK_NATIVE_FUTEX_SIGNAL']
                for name,changed in [('late-arm',span.replace(arm,b'',1).replace(send,send+arm,1)),('early-signal',span.replace(retire+signal,signal+retire,1))]:
                    bad=original.copy();bad[index]=changed
                    with self.subTest(arch=arch,index=index,name=name),self.assertRaises(ValueError):validate(bad,arch)

    def test_owned_native_request_and_retirement_fields(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for tag in (b'OK_NATIVE_FUTEX_ARM',b'OK_NATIVE_FUTEX_RETIRE',b'OK_NATIVE_FUTEX_SIGNAL'):
                line=next(line for line in lines if line.startswith(tag+b' '))
                for field in line.split()[1:]:
                    key,value=field.split(b'=')
                    if key==b'format':replacement=b'time32' if value==b'time64' else b'time64'
                    elif key==b'reason':replacement=b'ready'
                    elif key==b'outcome':replacement=b'restart'
                    else:replacement=str(int(value)+1).encode()
                    bad=original.copy();bad[2]=span.replace(line,line.replace(field,key+b'='+replacement),1)
                    with self.subTest(arch=arch,tag=tag,field=field),self.assertRaises(ValueError):validate(bad,arch)

    def test_edits_timeout_outcomes_and_fresh_generations(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for case in (2,3,4,5,6,7,8,9,10,12,14,15,16,17,18):
                scope=f'abi=0 domain=0 round=0 case={case} '.encode()
                row=next(l for l in lines if l.startswith(b'FUTEX_SIGNAL_RETURN ') and scope in l)
                for field in (b'result',b'error',b'elapsed'):
                    value=re.search(field+rb'=(-?[0-9]+)',row)[1]
                    replacement=b'2000000000' if field==b'elapsed' else b'999'
                    if field==b'elapsed' and case not in (2,3,10,12):replacement=b'5000000000'
                    bad=original.copy();bad[2]=span.replace(row,row.replace(field+b'='+value,field+b'='+replacement),1)
                    with self.subTest(arch=arch,case=case,field=field),self.assertRaises(ValueError):validate(bad,arch)
            for row in [l for l in lines if l.startswith(b'FUTEX_SIGNAL_HANDLER_RETURN ') and b'abi=0 domain=0 round=0 ' in l][:12]:
                for field in (b'pc',b'number',b'address',b'operation',b'value',b'timeout'):
                    value=re.search(field+rb'=([0-9]+)',row)
                    if value is None:continue
                    bad=original.copy();bad[2]=span.replace(row,row.replace(field+b'='+value[1],field+b'=999'),1)
                    with self.subTest(arch=arch,field=field,row=row),self.assertRaises(ValueError):validate(bad,arch)
            restarted=next(l for l in lines if l.startswith(b'OK_NATIVE_FUTEX_ARM ') and b'wait=2 ' in l)
            for field,value in ((b'wait=2',b'wait=1'),(b'origin=20',b'origin=10')):
                bad=original.copy();bad[2]=span.replace(restarted,restarted.replace(field,value),1)
                with self.subTest(arch=arch,restart=field),self.assertRaises(ValueError):validate(bad,arch)

    def test_incidental_waits_and_pipe_diagnostics_are_accounted(self):
        arm=b'OK_NATIVE_FUTEX_ARM pid=50 tid=50 wait=1 origin=10 pc=1073750018 syscall=202 address=268443648 operation=128 expected=2 timeout=0 deadline=0 format=time64 live=1\n'
        retire=b'OK_NATIVE_FUTEX_RETIRE pid=50 tid=50 wait=1 origin=10 reason=ready result=0 live=0\n'
        original=fixture('x86_64')
        for index in (0,1,2,3,4):
            parts=original.copy();position=parts[index].index(b'OK_NATIVE_FRAMES') if index not in (2,3) else parts[index].index(b'FUTEX_SIGNAL_CASE_BEGIN')
            parts[index]=parts[index][:position]+arm+retire+parts[index][position:]
            self.assertEqual(validate(parts,'x86_64')['runs'],2)
            for bad in (arm,retire,arm+retire+retire,arm+retire.replace(b'origin=10',b'origin=11'),arm+retire.replace(b'live=0',b'live=1')):
                changed=parts.copy();changed[index]=parts[index].replace(arm+retire,bad,1)
                with self.subTest(index=index,bad=bad),self.assertRaises(ValueError):validate(changed,'x86_64')
        pipe=b'OK_NATIVE_PIPE_READ_WAIT pid=50 tid=50 wait=1 request=1 output=1073750016 fd=3 description=1 pipe=2 bytes=64 stage=arm live=1\n'
        complete=pipe.replace(b'_WAIT ',b'_COMPLETE ').replace(b'stage=arm live=1',b'result=4 outcome=ready pinned=0 live=0')
        parts=original.copy();parts[1]=parts[1].replace(b'hello from',pipe+complete+b'hello from',1)
        self.assertEqual(validate(parts,'x86_64')['runs'],2)
        parts[1]=parts[1].replace(complete,b'',1)
        with self.assertRaises(ValueError):validate(parts,'x86_64')

    def test_state_alignment_snapshots_failures_and_wrong_images(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2]
            frame=next(l for l in span.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_FRAMES'))
            stack=next(l for l in span.splitlines(keepends=True) if l.startswith(b'OK_ENTRY_STACKS'))
            image=next(l for l in span.splitlines(keepends=True) if evidence.IMAGE.fullmatch(l.strip()))
            changes=[span.replace(frame,frame+frame),span.replace(frame+stack,frame+stack+frame+stack),span.replace(b'faults=0',b'faults=1'),span.replace(b'FUTEX_SIGNAL_PASS',b'FUTEX_SIGNAL_FAIL'),span.replace(b'FUTEX_SIGNAL_CASE_BEGIN',b'FUTEX_SIGNAL_LINUX_WAIT',1),span.replace(image,image+image)]
            if arch=='arm32':changes += [span.replace(b'cpsr=16',b'cpsr=19'),span.replace(b'cpsr=48',b'cpsr=51'),span.replace(b'cpsr=16',b'cpsr=16777232')]
            if arch not in ('x86_64','i386'):
                def shifted(m):return m[1]+str(int(m[2])+1).encode()
                changes.append(re.sub(rb'((?:site|resume|pc)=)([0-9]+)',shifted,span))
            for changed in changes:
                parts=original.copy();parts[2]=changed
                self.assertNotEqual(changed,span)
                with self.subTest(arch=arch),self.assertRaises(ValueError):validate(parts,arch)

    def test_pipe_successor_accounts_futex_and_closes_prior_admissibility_gaps(self):
        from test_native_pipe_signal import fixture as pipe_fixture,validate as pipe_validate
        arm=b'OK_NATIVE_FUTEX_ARM pid=50 tid=50 wait=1 origin=10 pc=1073750018 syscall=202 address=268443648 operation=128 expected=2 timeout=0 deadline=0 format=time64 live=1\n'
        retire=b'OK_NATIVE_FUTEX_RETIRE pid=50 tid=50 wait=1 origin=10 reason=ready result=0 live=0\n'
        original=pipe_fixture('x86_64')
        for index in (0,1,2,3,4):
            parts=original.copy();parts[index]=parts[index].replace(b'OK_NATIVE_FRAMES',arm+retire+b'OK_NATIVE_FRAMES',1)
            self.assertEqual(pipe_validate(parts,'x86_64')['runs'],2)
            for bad in (arm,retire,arm+retire+retire,arm+retire.replace(b'origin=10',b'origin=11')):
                changed=parts.copy();changed[index]=parts[index].replace(arm+retire,bad,1)
                with self.subTest(index=index),self.assertRaises(ValueError):pipe_validate(changed,'x86_64')
        for arch in ('arm32','mips64','x86_64'):
            parts=pipe_fixture(arch);span=parts[2]
            if arch=='arm32':changed=span.replace(b'cpsr=16',b'cpsr=19')
            elif arch=='mips64':changed=re.sub(rb'((?:site|resume|pc)=)([0-9]+)',lambda m:m[1]+str(int(m[2])+1).encode(),span)
            else:
                row=next(l for l in span.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_FRAMES'))
                changed=span.replace(row,row+row,1)
            self.assertNotEqual(span,changed);parts[2]=changed
            with self.subTest(arch=arch),self.assertRaises(ValueError):pipe_validate(parts,arch)

    def test_runner_layout_and_help(self):
        import qualify_native_futex_signal as runner
        for arch in ARCHES:
            source,binary,command=runner.probe_layout(arch,'futex-signals')
            self.assertEqual(source,'native_futex_signal');self.assertEqual('/bin/'+binary,command)
        done=subprocess.run([sys.executable,'-B',str(ROOT/'tools/qualify_native_futex_signal.py'),'--help'],capture_output=True)
        self.assertEqual(done.returncode,0)

if __name__=='__main__':unittest.main()
