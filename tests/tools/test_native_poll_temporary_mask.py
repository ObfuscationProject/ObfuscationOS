"""Synthetic strict-parser controls; never native execution or Linux evidence."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_poll_temporary_mask_evidence as e
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')

def events(arch):
    lines=[];maximum=(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1;mips=arch.startswith('mips');usr1,usr2=(16,17) if mips else (10,12)
    for variant,(number,select,wide) in enumerate(e.LANES[arch]):
      for form in range(2 if arch in ('arm32','ppc') else 1):
       for restart in range(2):
        for case in list(range(21))+[24,21,22,23]:
            key=f'arch={arch} variant={variant} form={form} restart={restart} case={case}'
            pid=200+variant*100+form*20+restart*5+(case-20 if case in (21,22,23) else 0);tid=pid*100+case+1
            owner=f'pid={pid} tid={tid}';kind='select' if select else 'poll';width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
            site=1073750016+64*form;resume=site+width;duration=0 if case==6 else 160000000 if case in (5,18) else 500000000
            original=(644 if mips else 132)+(case not in (1,3));temporary=(322 if mips else 66)+(case==14)
            output,timeout,maskptr,pair=268443648,268447744,268451840,268455936
            lines.append(f'POLL_TEMP_CASE_BEGIN {key} {owner} syscall={number} kind={kind} duration={duration} site={site} resume={resume} fd=3 output={output} timeout={timeout} maskptr={maskptr} pair={pair} width={64 if wide else 32} bytes={16 if mips else 8} original={original} temporary={temporary}')
            def send(sig):lines.append(f'POLL_TEMP_SEND {key} {owner} signal={sig}')
            if case==15:send(usr1)
            args=[4,output,0,0,timeout,pair] if select else [output,1,timeout,maskptr,16 if mips else 8,0]
            if case==8 and select:args[0]=31
            if case==9 and not select:args[3]=1
            if case==10 and not select:args[4]-=1
            if case==11:args[4 if select else 2]=1
            if case==11 and not select:args[4]-=1
            if case==12:args[1 if select else 0]=1
            lines.append(f'POLL_TEMP_ATTEMPT {key} {owner} '+' '.join(f'a{i}={v}' for i,v in enumerate(args)))
            wait=0
            def arm():
                nonlocal wait
                wait+=1;lines.append(f'OK_NATIVE_POLL_ARM {owner} wait={wait} pc={resume} syscall={number} kind={kind} count=1 deadline=1000000000 live=1')
            def terminal(reason,result,sig=usr1):
                lines.append(f'OK_NATIVE_POLL_RETIRE {owner} wait={wait} reason={reason} result={result} live=0')
                if reason=='interrupted':lines.append(f'OK_NATIVE_POLL_SIGNAL {owner} wait={wait} signal={sig} kind={kind} result={"efault" if result==-14 else "eintr"} deadline=1000000000 now=700000000 live=0')
            def action(name):lines.append(f'POLL_TEMP_ACTION {key} action={name}')
            def context(tag,depth=1,edited=False):
                code=14 if case==3 and not select and depth==1 else 4
                saved=temporary+1 if depth==2 else original+4 if edited else original
                active=temporary+4 if depth==2 else original+1 if case==3 and not select else temporary+8 if case==20 else temporary+1
                extra=' a3=1' if mips else f' cr=436207617 diagnostic_result={maximum+1-code}' if arch=='ppc' else f' cpsr={48 if form else 16}' if arch=='arm32' else ''
                lines.append(f'POLL_TEMP_{tag} {key} {owner} depth={depth} pc={resume} result={code if mips or arch=="ppc" else maximum+1-code} saved={saved} active={active}{extra}')
            caught=case<=3 or case in (15,16,17,19,20,23,24)
            if case<=5 or case>=13:
                arm()
                if case in (2,3,19):action({2:'mutate-mask',3:'protect-output',19:'protect-mask'}[case])
                if caught:
                    if case!=15:send(usr1)
                    terminal('interrupted',-14 if case==3 and not select else -4);context('HANDLE')
                    if case==16:context('NEST_BEGIN');arm();send(usr2);terminal('interrupted',-4,usr2);context('NESTED',2);context('NEST_RETURN')
                    if case==23:context('HANDLER_EXIT')
                    elif case!=24:context('HANDLER_RETURN',edited=case==17)
                elif case in (21,22):
                    if case==21:send(usr1)
                    else:action('exit-group')
                    terminal('cancelled',-4)
                elif case in (5,18):
                    if case==18:action('mutate-timeout')
                    terminal('timeout',0)
                else:
                    if case in (13,14):send(usr1)
                    action('ready');terminal('ready',1)
            if case in (21,22,23):lines.append(f'POLL_TEMP_EXIT_PASS {key} pid={pid} signal={usr1 if case==21 else 0}')
            else:
                if case!=24:
                    result=-(14 if case==3 and not select else 4) if caught else 0 if case in (5,6,18) else -9 if case==8 and select else -14 if case in (9,11,12) else -22 if case==10 else 1
                    elapsed=170000000 if case in (5,18) else 1000000;remaining=0 if case in (5,6,18) else duration-1000000;restored=original+4 if case==17 else original
                    lines.append(f'POLL_TEMP_RETURN {key} result={result} error=111 restored={restored} elapsed={elapsed} remaining={remaining}')
                    if case==14:lines.append(f'POLL_TEMP_PENDING {key} mask=1')
                lines.append(f'POLL_TEMP_CASE_PASS {key}')
    return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
    marker,_,command,leases=e.probe_spec(arch,'poll-temporary-masks');output=command+b'\n'+IMAGE+events(arch)+marker+b'\n'
    parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+frames(0,0)+stacks(0,0,0,peak=0)+frames(40,0)+stacks(7,5,100)+b'oksh> ',
      b'hello | cat\nhello from ObfuscationOS userland\n'+frames(100,60)+stacks(10,8,200)+b'oksh> ',
      output+frames(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
      output+frames(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
      b'hello | cat\nhello from ObfuscationOS userland\n'+frames(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
    if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
    return parts

def validate(parts,arch):
    ends=[sum(map(len,parts[:i])) for i in range(1,5)];return e.validate_execution(b''.join(parts),*ends,ends[-1],arch)

class TemporaryMasks(unittest.TestCase):
    def test_all_ten_complete_and_both_newlines(self):
        for arch in ARCHES:
            self.assertLessEqual(len(e.probe_spec(arch,'poll-temporary-masks')[2].rsplit(b'/',1)[1]),31)
            for newline in (b'\n',b'\r\n'):
                result=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch)
                self.assertTrue(result['temporary_masks']);self.assertFalse(result['caught_poll_restart'])
                groups=len(e.LANES[arch])*(4 if arch in ('arm32','ppc') else 2)
                for row in result['observations']:
                    for key,value in dict(cases=25*groups,groups=groups,initial_waits=18*groups,nested_waits=groups,outer_handlers=11*groups,nested_handlers=groups,main_sends=15*groups,immediate=7*groups,ready=3*groups,timeout=2*groups,cancelled=2*groups,fatal_children=groups,exit_children=groups,handler_exit_children=groups,thread_exits=groups).items():self.assertEqual(row[key],value,(arch,key))
                    self.assertEqual(row['eintr']+row['efault'],12*groups)

    def test_missing_duplicate_malformed_reordered_records(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for pattern in e.PATTERNS:
                line=next(l for l in lines if pattern.fullmatch(l.rstrip(b'\n')))
                for changed in (b'',line+line,b'junk '+line):
                    parts=original.copy();parts[2]=span.replace(line,changed,1)
                    with self.subTest(arch=arch,tag=line.split()[0]),self.assertRaises(ValueError):validate(parts,arch)
            arm=next(l for l in lines if l.startswith(b'OK_NATIVE_POLL_ARM '));send=next(l for l in lines if l.startswith(b'POLL_TEMP_SEND '))
            parts=original.copy();parts[2]=span.replace(arm,b'',1).replace(send,send+arm,1)
            with self.assertRaises(ValueError):validate(parts,arch)

    def test_every_mask_result_and_owner_field(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for tag,fields in ((b'POLL_TEMP_CASE_BEGIN',(b'original',b'temporary',b'bytes',b'width',b'restart',b'pid',b'tid')),(b'POLL_TEMP_HANDLE',(b'saved',b'active',b'result',b'pc',b'depth')),(b'POLL_TEMP_NESTED',(b'saved',b'active',b'result',b'pc')),(b'POLL_TEMP_HANDLER_RETURN',(b'saved',b'active')),(b'POLL_TEMP_RETURN',(b'restored',b'result',b'error')),(b'POLL_TEMP_PENDING',(b'mask',)),(b'POLL_TEMP_EXIT_PASS',(b'signal',b'pid'))):
                line=next(l for l in lines if l.startswith(tag+b' '))
                for field in fields:
                    parts=original.copy();parts[2]=span.replace(line,re.sub(rb'(?<![a-z_])'+field+rb'=-?[0-9]+',field+b'=999',line),1)
                    with self.subTest(arch=arch,tag=tag,field=field),self.assertRaises(ValueError):validate(parts,arch)
            for tag in (b'POLL_TEMP_NEST_RETURN',b'POLL_TEMP_HANDLER_EXIT'):
                line=next(l for l in lines if l.startswith(tag+b' '));parts=original.copy();parts[2]=span.replace(line,re.sub(rb'saved=[0-9]+',b'saved=0',line),1)
                with self.assertRaises(ValueError):validate(parts,arch)

    def test_native_completion_and_context_flags(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for tag in (b'OK_NATIVE_POLL_ARM',b'OK_NATIVE_POLL_RETIRE',b'OK_NATIVE_POLL_SIGNAL'):
                line=next(l for l in lines if l.startswith(tag+b' '))
                for field in line.split()[1:]:
                    k,v=field.split(b'=');replacement=b'poll' if v==b'select' else b'select' if k==b'kind' else b'ready' if k==b'reason' else b'efault' if v==b'eintr' else b'0' if k==b'now' else str(int(v)+1).encode()
                    parts=original.copy();parts[2]=span.replace(line,line.replace(field,k+b'='+replacement),1)
                    with self.subTest(arch=arch,tag=tag,field=field),self.assertRaises(ValueError):validate(parts,arch)
            h=next(l for l in lines if l.startswith(b'POLL_TEMP_HANDLE '))
            for field in ((b'a3',) if arch.startswith('mips') else (b'cr',b'diagnostic_result') if arch=='ppc' else (b'cpsr',) if arch=='arm32' else ()):
                parts=original.copy();parts[2]=span.replace(h,re.sub(field+rb'=[0-9]+',field+b'=0',h),1)
                with self.assertRaises(ValueError):validate(parts,arch)
            retired=next(l for l in lines if l.startswith(b'OK_NATIVE_POLL_RETIRE ') and b'result=-4' in l);parts=original.copy();parts[2]=span.replace(retired,retired.replace(b'result=-4',b'result=-11'),1)
            with self.assertRaises(ValueError):validate(parts,arch)

    def test_every_case_result_and_edited_sigreturn(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2]
            for case in range(21):
                row=next(l for l in span.splitlines(keepends=True) if l.startswith(b'POLL_TEMP_RETURN ') and f'variant=0 form=0 restart=0 case={case} '.encode() in l)
                for field in (b'result',b'restored'):
                    parts=original.copy();parts[2]=span.replace(row,re.sub(field+rb'=-?[0-9]+',field+b'=999',row),1)
                    with self.subTest(arch=arch,case=case,field=field),self.assertRaises(ValueError):validate(parts,arch)
            parts=original.copy();parts[2]=span.replace(b'remaining=0',b'remaining=1',1)
            with self.assertRaises(ValueError):validate(parts,arch)

    def test_snapshots_aggregate_faults_and_trailing_output(self):
        original=fixture('x86_64')
        for index in (0,2,3,4):
            span=original[index]
            for prefix in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
                line=next(l for l in span.splitlines(keepends=True) if l.startswith(prefix))
                parts=original.copy();parts[index]=span.replace(line,line+line,1)
                with self.assertRaises(ValueError):validate(parts,'x86_64')
        for replacement in (b'POLL_TEMP_PASS arch=x86_64 variants=2 groups=4 cases=99 parent=1',b'POLL_TEMP_FAIL code=213'):
            parts=original.copy();parts[2]=parts[2].replace(e.probe_spec('x86_64','poll-temporary-masks')[0],replacement)
            with self.assertRaises(ValueError):validate(parts,'x86_64')
        parts=original.copy();parts[-1]+=b'junk'
        with self.assertRaises(ValueError):validate(parts,'x86_64')

if __name__=='__main__':unittest.main()
