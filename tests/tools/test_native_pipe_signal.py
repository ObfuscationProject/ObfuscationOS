"""Synthetic parser/runner tests only; no native execution is generated here."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_signal_evidence as evidence
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
READ=dict(zip(ARCHES,(0,3,63,3,63,63,63,4003,5000,3)))
GETPID=dict(zip(ARCHES,(39,20,172,20,172,172,172,4020,5038,20)))

def events(arch):
    lines=[];forms=2 if arch in ('arm32','ppc') else 1
    maximum=(1 << (32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1
    for form in range(forms):
        for round_id in range(3):
            for case in range(12):
                pid=200+form;tid=1000+form*36+round_id*12+case
                key=f'arch={arch} form={form} round={round_id} case={case}'
                owner=f'pid={pid} tid={tid}'
                count=8 if case==7 else 1;fd=3;output=268443648
                width=2 if arch in ('i386','x86_64') or (arch=='arm32' and form==1) else 4
                site=1073750016+form*64;resume=site+width
                actual_width=4 if arch=='arm32' and case>=10 else width
                actual_site=site+256 if case>=10 else site
                actual_resume=actual_site+actual_width
                args=f'fd=3 buffer={output} count={count}'
                lines.append(f'PIPE_SIGNAL_CASE_BEGIN {key} {owner} {args} site={site} resume={resume} replacement=5 alternate={output+64} libc={int(case>=10)} wait={int(case!=7)}')
                lines.append(f'PIPE_SIGNAL_ATTEMPT {key} {owner} {args}')
                generation=0
                def identity():return f'{owner} wait={generation} request={generation} output={output} fd=3 description=1 pipe=2 bytes={count}'
                def arm():
                    nonlocal generation
                    generation+=1
                    lines.append(f'OK_NATIVE_PIPE_READ_WAIT {identity()} stage=arm live=1')
                    lines.append(f'OK_NATIVE_PIPE_ORIGIN {owner} request={generation} wait={generation} origin={10*generation} pc={actual_resume} syscall={READ[arch]} fd=3 output={output} bytes={count}')
                def context(edited=False):
                    restart=case not in (0,10)
                    number=READ[arch] if restart or arch not in ('x86_64','i386','mips','mips64') else 4 if arch.startswith('mips') else maximum-3
                    argfd=3 if restart or arch in ('x86_64','i386','mips','mips64') else 4 if arch=='ppc' else maximum-3
                    pc=actual_site if restart else actual_resume
                    buf=output;size=count;cr=0x1a000001;diagnostic=0 if restart else maximum-3;orig=3;a3=0x1357 if restart else 1
                    if edited and case==2:
                        pc=resume
                        if arch in ('x86_64','i386','mips','mips64'):number=77
                        else:argfd=77
                        a3=0;cr&=~0x10000000;diagnostic=0x123;orig=0x234
                    if edited and case==3:number=GETPID[arch]
                    if edited and case==4:argfd=5;buf=output+64;size=2
                    if case==7:return 'pc=1073780000 inspected=0'
                    result=f'pc={pc} inspected=1 number={number} fd={argfd} buffer={buf} count={size}'
                    if arch=='ppc':result+=f' cr={cr} diagnostic_result={diagnostic} orig_r3={orig}'
                    if arch=='arm32':result+=f' cpsr={0x10+(0x20 if actual_width==2 else 0)}'
                    if arch.startswith('mips'):result+=f' a3={a3}'
                    return result
                def signal(ordinal):
                    signo=16 if arch.startswith('mips') else 10
                    lines.append(f'PIPE_SIGNAL_SEND {key} {owner} ordinal={ordinal} signal={signo}')
                    if case!=7:
                        outcome='eintr' if case in (0,10) else 'restart';result=-4 if outcome=='eintr' else 0
                        lines.append(f'OK_NATIVE_PIPE_READ_COMPLETE {identity()} result={result} outcome=interrupted pinned=0 live=0')
                        pc=actual_resume if outcome=='eintr' else actual_site
                        lines.append(f'OK_NATIVE_PIPE_SIGNAL {owner} request={generation} wait={generation} origin={10*generation} signal={signo} outcome={outcome} pc={pc} syscall={READ[arch]} fd=3 output={output} bytes={count} pinned=0 live=0')
                    lines.append(f'PIPE_SIGNAL_HANDLE {key} {owner} ordinal={ordinal} '+context())
                    if case==9:lines.append(f'PIPE_SIGNAL_NESTED {key} {owner} ordinal=1 pc=1073780000 inspected=0')
                    lines.append(f'PIPE_SIGNAL_HANDLER_RETURN {key} {owner} ordinal={ordinal} '+context(True))
                def result():
                    value=pid if case==3 else -1 if case==10 else -4 if case==0 else 77 if case==2 else 2 if case==4 else 3 if case==7 else 1
                    lines.append(f'PIPE_SIGNAL_RETURN {key} result={value} error={4 if case==10 else 111}')
                if case==7:result();signal(1)
                else:
                    arm()
                    if case==6:lines.append(f'PIPE_SIGNAL_REPLACE {key}')
                    else:signal(1)
                    if case==8:arm();signal(2)
                    if case in (1,8,9,11):arm()
                    if case in (1,6,8,9,11):
                        lines.append(f'PIPE_SIGNAL_ORIGINAL_READY {key}')
                        lines.append(f'OK_NATIVE_PIPE_READ_COMPLETE {identity()} result=1 outcome=ready pinned=0 live=0')
                    result()
                lines.append(f'PIPE_SIGNAL_CASE_PASS {key}')
    return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
    marker,_,command,leases=evidence.probe_spec(arch,'pipe-signals')
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

class PipeSignalEvidence(unittest.TestCase):
    def test_reject_duplicate_frame_snapshots(self):
        for arch in ARCHES:
            original=fixture(arch)
            for index,span in enumerate(original):
                for line in (row for row in span.splitlines(keepends=True) if row.startswith(b'OK_NATIVE_FRAMES ')):
                    bad=original.copy();bad[index]=span.replace(line,line+line,1)
                    with self.subTest(arch=arch,index=index),self.assertRaises(ValueError):validate(bad,arch)

    def test_arm_context_requires_user_mode(self):
        original=fixture('arm32')
        for form in (0,1):
            for case in (0,1,10,11):
                key=f'form={form} round=0 case={case} '.encode()
                for mode in range(32):
                    if mode==0x10:continue
                    lines=original[2].splitlines(keepends=True);changed=0
                    for index,line in enumerate(lines):
                        if line.startswith((b'PIPE_SIGNAL_HANDLE ',b'PIPE_SIGNAL_HANDLER_RETURN ')) and key in line:
                            lines[index]=re.sub(rb'cpsr=([0-9]+)',lambda match:b'cpsr='+str((int(match[1])&~31)|mode).encode(),line);changed+=1
                    self.assertEqual(changed,2);bad=original.copy();bad[2]=b''.join(lines)
                    with self.subTest(form=form,case=case,mode=mode),self.assertRaises(ValueError):validate(bad,'arm32')
        # Condition flags are unrelated to the privilege mode or instruction width.
        good=original.copy();good[2]=re.sub(rb'cpsr=([0-9]+)',lambda match:b'cpsr='+str(int(match[1])|0xf8000000).encode(),good[2])
        self.assertEqual(validate(good,'arm32')['runs'],2)

    def test_absolute_instruction_alignment(self):
        for arch in ARCHES:
            forms=(0,1) if arch=='arm32' else (0,)
            for form in forms:
                original=fixture(arch)
                # Change every matching PC, including the labels, so relative
                # consistency alone cannot detect the deliberately wrong address.
                for delta in (1,2,3):
                    lines=original[2].splitlines(keepends=True);active=False
                    key=f'form={form} round=0 case=1'.encode()
                    for index,line in enumerate(lines):
                        if line.startswith(b'PIPE_SIGNAL_CASE_BEGIN ') and key+b' ' in line:active=True
                        if active:lines[index]=re.sub(rb'\b(pc|site|resume)=([0-9]+)',lambda match:match[1]+b'='+str(int(match[2])+delta).encode(),line)
                        if line.startswith(b'PIPE_SIGNAL_CASE_PASS ') and key+b'\n' in line:active=False
                    changed=original.copy();changed[2]=b''.join(lines)
                    allowed=arch in ('x86_64','i386') or (delta==2 and (arch in ('rv32','rv64') or (arch=='arm32' and form==1)))
                    with self.subTest(arch=arch,form=form,delta=delta):
                        if allowed:self.assertEqual(validate(changed,arch)['runs'],2)
                        else:
                            with self.assertRaises(ValueError):validate(changed,arch)

    def test_all_profiles(self):
        for arch in ARCHES:
            for newline in (b'\n',b'\r\n'):
                with self.subTest(arch=arch,newline=newline):
                    result=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch)
                    forms=2 if arch in ('arm32','ppc') else 1
                    expected=dict(cases=36*forms,forms=forms,rounds=3,initial_waits=33*forms,fresh_restart_waits=15*forms,
                        rearms=0,eintr=6*forms,restart_publications=27*forms,outer_handlers=36*forms,nested_handlers=3*forms)
                    self.assertEqual(result['observations'],[expected]*2)
                    self.assertTrue(result['pipe_restart']);self.assertFalse(result['physical'])

    def test_reject_corrupt_publications_and_case_order(self):
        for arch in ARCHES:
            original=fixture(arch)
            for index in (2,3):
                span=original[index];lines=span.splitlines(keepends=True)
                selected={tag:next(line for line in lines if line.startswith(tag+b' ')) for tag in
                    (b'OK_NATIVE_PIPE_READ_WAIT',b'OK_NATIVE_PIPE_ORIGIN',b'PIPE_SIGNAL_SEND',b'OK_NATIVE_PIPE_READ_COMPLETE',b'OK_NATIVE_PIPE_SIGNAL',b'PIPE_SIGNAL_HANDLE',b'PIPE_SIGNAL_HANDLER_RETURN',b'PIPE_SIGNAL_RETURN',b'PIPE_SIGNAL_CASE_PASS')}
                mutations={}
                for tag,line in selected.items():
                    mutations[(tag,'missing')]=span.replace(line,b'',1)
                    mutations[(tag,'duplicate')]=span.replace(line,line+line,1)
                    mutations[(tag,'malformed')]=span.replace(line,b'junk '+line,1)
                for tag in (b'OK_NATIVE_PIPE_ORIGIN',b'OK_NATIVE_PIPE_SIGNAL'):
                    line=selected[tag]
                    for before,after in ((b'tid=1000',b'tid=1001'),(b'pid=200',b'pid=201'),(b'request=1',b'request=2'),
                      (b'wait=1',b'wait=2'),(b'origin=10',b'origin=0'),(b'fd=3',b'fd=5'),(b'output=268443648',b'output=268443649'),
                      (b'bytes=1',b'bytes=2')):
                        mutations[(tag,before)]=span.replace(line,line.replace(before,after),1)
                terminal=selected[b'OK_NATIVE_PIPE_READ_COMPLETE'];interrupt=selected[b'OK_NATIVE_PIPE_SIGNAL'];origin=selected[b'OK_NATIVE_PIPE_ORIGIN'];send=selected[b'PIPE_SIGNAL_SEND']
                for before,after in ((b'outcome=interrupted',b'outcome=error'),(b'result=-4',b'result=0'),(b'pinned=0',b'pinned=1'),(b'live=0',b'live=1'),(b'description=1',b'description=2'),(b'pipe=2',b'pipe=3')):
                    mutations[('terminal',before)]=span.replace(terminal,terminal.replace(before,after),1)
                mutations['signal-before-retirement']=span.replace(terminal+interrupt,interrupt+terminal,1)
                mutations['late-origin']=span.replace(origin,b'',1).replace(send,send+origin,1)
                mutations['publication-before-send']=span.replace(terminal+interrupt,b'',1).replace(send,terminal+interrupt+send,1)
                mutations['wrong-outcome']=span.replace(interrupt,interrupt.replace(b'outcome=eintr',b'outcome=restart'),1)
                mutations['forged-context']=span.replace(selected[b'PIPE_SIGNAL_HANDLE'],selected[b'PIPE_SIGNAL_HANDLE'].replace(b'buffer=268443648',b'buffer=268443649'),1)
                mutations['wrong-result']=span.replace(selected[b'PIPE_SIGNAL_RETURN'],selected[b'PIPE_SIGNAL_RETURN'].replace(b'result=-4',b'result=0'),1)
                mutations['linux-in-native']=span.replace(send,b'PIPE_SIGNAL_LINUX_WAIT arch=x86_64\n'+send,1)
                for name,changed in mutations.items():
                    with self.subTest(arch=arch,index=index,name=name):
                        self.assertNotEqual(changed,span)
                        parts=original.copy();parts[index]=changed
                        with self.assertRaises(ValueError):validate(parts,arch)

    def test_ppc_eintr_context_rejects_consistent_diagnostic_corruption(self):
        original=fixture('ppc')
        self.assertEqual(validate(original,'ppc')['runs'],2)
        for index in (2,3):
            for form in (0,1):
                for case in (0,10):
                    for field in (b'diagnostic_result',b'orig_r3'):
                        for value in (b'0',b'1',b'4294967295'):
                            lines=original[index].splitlines(keepends=True);edits=0
                            for i,line in enumerate(lines):
                                if line.startswith((b'PIPE_SIGNAL_HANDLE ',b'PIPE_SIGNAL_HANDLER_RETURN ')) and f'form={form} round=0 case={case} '.encode() in line:
                                    lines[i],count=re.subn(field+rb'=[0-9]+',field+b'='+value,line)
                                    self.assertEqual(count,1);self.assertNotEqual(lines[i],line);edits+=1
                            self.assertEqual(edits,2)
                            changed=original.copy();changed[index]=b''.join(lines)
                            with self.subTest(index=index,form=form,case=case,field=field,value=value),self.assertRaises(ValueError):
                                validate(changed,'ppc')

    def test_target_context_edits_and_restart_origins(self):
        for arch in ARCHES:
            parts=fixture(arch);span=parts[2];lines=span.splitlines(keepends=True)
            for case in (1,2,3,4,5,7,8,9,10,11):
                handler=next(line for line in lines if line.startswith(b'PIPE_SIGNAL_HANDLER_RETURN ') and f'round=0 case={case} '.encode() in line)
                mutations=[handler.replace(b'ordinal=1',b'ordinal=2'),handler.replace(b'pc=',b'pc=9')]
                if b' number=' in handler:mutations.append(handler.replace(b' number=',b' number=9'))
                if arch=='ppc' and b' cr=' in handler:mutations.append(handler.replace(b' cr=',b' cr=9'))
                if arch=='arm32' and b' cpsr=' in handler:mutations.append(handler.replace(b' cpsr=',b' cpsr=9'))
                if arch.startswith('mips') and b' a3=' in handler:mutations.append(handler.replace(b' a3=',b' a3=9'))
                for changed in mutations:
                    bad=parts.copy();bad[2]=span.replace(handler,changed,1)
                    with self.subTest(arch=arch,case=case,changed=changed),self.assertRaises(ValueError):validate(bad,arch)
            origin=next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_ORIGIN ') and b'tid=1008 request=2' in line)
            for before,after in ((b'origin=20',b'origin=10'),(b'pc=',b'pc=9')):
                bad=parts.copy();bad[2]=span.replace(origin,origin.replace(before,after),1)
                with self.subTest(arch=arch,origin=before),self.assertRaises(ValueError):validate(bad,arch)

    def test_incidental_pipelines_images_faults_and_accounting(self):
        arm=b'OK_NATIVE_PIPE_READ_WAIT pid=50 tid=50 wait=1 request=1 output=268443648 fd=3 description=1 pipe=2 bytes=64 stage=arm live=1\n'
        for arch in ARCHES:
            address = 268443648 if arch in ('arm32', 'aarch64') else 1073750016
            local_arm = arm.replace(b'output=268443648', b'output=' + str(address).encode())
            complete=local_arm.replace(b'_WAIT ',b'_COMPLETE ').replace(b'stage=arm live=1',b'result=4 outcome=ready pinned=0 live=0')
            original=fixture(arch)
            for index in (1,4):
                good=original.copy();good[index]=good[index].replace(b'hello from ObfuscationOS userland\n',local_arm+complete+b'hello from ObfuscationOS userland\n')
                self.assertEqual(validate(good,arch)['runs'],2)
                for injected in (local_arm,complete,IMAGE,local_arm+complete+complete):
                    bad=original.copy();bad[index]=bad[index].replace(b'hello from ObfuscationOS userland\n',injected+b'hello from ObfuscationOS userland\n')
                    with self.assertRaises(ValueError):validate(bad,arch)
            for index in (2,3):
                for injected in (IMAGE,b'PIPE_SIGNAL_FAIL code=203\n',b'OK_NATIVE scope=hardware fault=contained\n',b'garbage\n'):
                    bad=original.copy();bad[index]=bad[index].replace(b'oksh> ',injected+b'oksh> ')
                    with self.assertRaises(ValueError):validate(bad,arch)
                bad=original.copy();bad[index]=bad[index].replace(b'faults=0',b'faults=1')
                with self.assertRaises(ValueError):validate(bad,arch)

    def test_runner_freeze_and_source_dependencies(self):
        from object_pressure_evidence import admit_sources,sha
        from qualify_native_pipe_signal import probe_layout,dependencies
        for arch in ARCHES:self.assertEqual(probe_layout(arch,'pipe-signals')[0],'native_pipe_signal')
        with tempfile.TemporaryDirectory() as tmp:
            inventory=Path(tmp)/'source.json'
            run=subprocess.run([sys.executable,'-B',str(ROOT/'tools/qualify_native_pipe_signal.py'),'freeze','--output',str(inventory)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout.strip(),sha(inventory))
            source=admit_sources(ROOT,inventory,sha(inventory))['files']
            for path in ('tools/native_pipe_signal_evidence.py','tests/musl/native_pipe_signal.c','tests/musl/pipe_signal_raw.h'):
                self.assertIn(path,source)
            dependency=ROOT/'tests/musl/pipe_signal_raw.h'
            self.assertIn(str(dependency),dependencies([],f'object-pressure: {dependency}\n'.encode(),(ROOT,))['files'])
            with self.assertRaises(ValueError):dependencies([],b'wrong-target: /etc/passwd\n',(ROOT,))
            with self.assertRaises(ValueError):dependencies([],b'object-pressure: /etc/passwd\n',(ROOT,))

    def test_readiness_rearm_preserves_origin_until_interrupt(self):
        for arch in ARCHES:
            parts=fixture(arch);span=parts[2];lines=span.splitlines(keepends=True)
            arm=next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_READ_WAIT '))
            origin=next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_ORIGIN '))
            terminal=next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_READ_COMPLETE '))
            interrupted=next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_SIGNAL '))
            rearm=arm.replace(b'wait=1',b'wait=2').replace(b'stage=arm',b'stage=rearm')
            parts[2]=span.replace(origin,origin+rearm,1).replace(terminal,terminal.replace(b'wait=1',b'wait=2'),1).replace(interrupted,interrupted.replace(b'wait=1',b'wait=2'),1)
            self.assertEqual(validate(parts,arch)['observations'][0]['rearms'],1)
            for changed in (rearm.replace(b'request=1',b'request=2'),rearm+origin,rearm.replace(b'description=1',b'description=2')):
                bad=parts.copy();bad[2]=bad[2].replace(rearm,changed,1)
                with self.subTest(arch=arch,changed=changed),self.assertRaises(ValueError):validate(bad,arch)

    def test_fragmented_failure(self):
        self.assertTrue(evidence.incomplete_failure_line(b'PIPE_SIGNAL_FAIL code='))
        self.assertFalse(evidence.incomplete_failure_line(b'PIPE_SIGNAL_FAIL code=203\n'))
        self.assertIn('code=203',evidence.failure_line(b'PIPE_SIGNAL_FAIL code=203\n'))

if __name__=='__main__':unittest.main()
