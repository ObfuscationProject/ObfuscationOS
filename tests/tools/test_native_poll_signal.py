"""Synthetic evidence tests. These fixtures never execute a native kernel."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_poll_signal_evidence as e
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')

def events(arch):
    lines=[];maximum=(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1
    for variant,(number,interface,wide,packed,libc) in enumerate(e.LANES[arch]):
      for form in range(1 if libc else 2 if arch in ('arm32','ppc') else 1):
        for case in range(19):
            key=f'arch={arch} variant={variant} form={form} case={case}'
            pid=200+variant*20+form*3+(case-16 if case>=17 else 0);tid=pid*100+case+1
            owner=f'pid={pid} tid={tid}';kind='select' if interface>=2 else 'poll';count=1 if kind=='select' else 2
            timed=case in (2,3,7,8,9,11,14,15);caught=case<=5 or case in (7,8,14)
            duration=0 if case==15 else 160000000 if case in (9,11) else 500000000
            output=268443648;timeout=268447744 if timed else 0
            width=2 if arch in ('i386','x86_64') or arch=='arm32' and form and not libc else 4
            site=1073750016+form*64;resume=site+width;pc=site+256 if libc else resume
            deadline=1000000000 if timed else 0;current_time=deadline-duration+60000000 if timed else 1000000000
            lines.append(f'POLL_SIGNAL_CASE_BEGIN {key} {owner} syscall={number} kind={kind} libc={libc} timed={int(timed)} duration={duration} site={site} resume={resume} count={count} fd=3 output={output} timeout={timeout} width={64 if wide else 32} packed={packed}')
            if interface==0:args=[output,2,duration//1000000 if timed else maximum,0,0,0]
            elif interface==1:args=[output,2,timeout,0,16 if arch.startswith('mips') else 8,0]
            elif packed:args=[268451840,0,0,0,0,0]
            else:args=[4,output,0,0,timeout,0]
            lines.append(f'POLL_SIGNAL_ATTEMPT {key} {owner} '+' '.join(f'a{i}={v}' for i,v in enumerate(args)))
            def retire(reason,result):lines.append(f'OK_NATIVE_POLL_RETIRE {owner} wait=1 reason={reason} result={result} live=0')
            def handler():
                context=f'pc={pc if caught else 1073780000} inspected={int(caught)}'
                if caught:
                    code=14 if case==7 and kind=='poll' else 4
                    context+=f' result={code if arch.startswith("mips") or arch=="ppc" else maximum+1-code}'
                    if arch.startswith('mips'):context+=' a3=1'
                    if arch=='ppc':context+=f' cr={0x1a000001} diagnostic_result={maximum+1-code}'
                    if arch=='arm32':context+=f' cpsr={48 if form and not libc else 16}'
                lines.append(f'POLL_SIGNAL_HANDLE {key} {owner} {context}')
                if case==14:lines.append(f'POLL_SIGNAL_NESTED {key} {owner} pc=1073780000 inspected=0')
                lines.append(f'POLL_SIGNAL_HANDLER_RETURN {key} {owner} {context}')
            def send(delivered=True):
                signal=16 if arch.startswith('mips') else 10
                lines.append(f'POLL_SIGNAL_SEND {key} {owner} signal={signal}')
                if delivered:
                    if caught:
                        fault=case==7 and kind=='poll';retire('interrupted',-14 if fault else -4)
                        lines.append(f'OK_NATIVE_POLL_SIGNAL {owner} wait=1 signal={signal} kind={kind} result={"efault" if fault else "eintr"} deadline={deadline} now={current_time} live=0')
                    handler()
            def ready(replacement=False):
                lines.append(f'POLL_SIGNAL_READY {key} source={"replacement" if replacement else "original"}')
                if not replacement:retire('ready',1)
            def returned():
                result=-(14 if case==7 and kind=='poll' else 4) if caught else 0 if case in (9,11,15) else 1
                revents=0 if kind=='select' else 0x3333 if case==7 else 1 if result==1 else 0
                mask=0 if kind=='poll' or case==4 or result==0 else 8
                elapsed=170000000 if case in (9,11) else 1000000
                remaining=-1 if interface==0 else (2000000000 if case==9 else duration) if libc or not timed or case==8 else 0 if case in (9,11,15) else duration-60000000
                lines.append(f'POLL_SIGNAL_RETURN {key} result={-1 if libc and result<0 else result} error={-result if libc and result<0 else 111} elapsed={elapsed} revents={revents} mask={mask} remaining={remaining}')
            if case<15 or case>=17:
                lines.append(f'OK_NATIVE_POLL_ARM {owner} wait=1 pc={pc} syscall={number} kind={kind} count={count} deadline={deadline} live=1')
                if case==4:lines.append(f'POLL_SIGNAL_MUTATE_INPUT {key}')
                if case in (5,6):
                    lines.append(f'POLL_SIGNAL_REUSE {key} fd=3 replacement=5')
                    if case==5:ready(True)
                if case==7:lines.append(f'POLL_SIGNAL_PROTECT {key} target=output')
                if case==8 and not libc and interface!=0:lines.append(f'POLL_SIGNAL_PROTECT {key} target=timeout')
                if caught:send();returned()
                elif case==9:lines.append(f'POLL_SIGNAL_MUTATE_TIMEOUT {key}');retire('timeout',0);returned()
                elif case==11:retire('timeout',0);returned();send()
                elif case in (17,18):
                    if case==17:send(False)
                    else:lines.append(f'POLL_SIGNAL_EXIT {key} pid={pid}')
                    retire('cancelled',-4);signal=(16 if arch.startswith('mips') else 10) if case==17 else 0
                    lines.append(f'POLL_SIGNAL_EXIT_PASS {key} pid={pid} signal={signal}')
                else:
                    if case in (12,13):send(False)
                    ready();returned()
                    if case==10:send()
                    if case==12:lines.append(f'POLL_SIGNAL_UNMASK {key}');handler()
            else:returned()
            if case<17:lines.append(f'POLL_SIGNAL_CASE_PASS {key}')
    return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
    marker,_,command,leases=e.probe_spec(arch,'poll-signals');output=command+b'\n'+IMAGE+events(arch)+marker+b'\n'
    parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+frames(0,0)+stacks(0,0,0,peak=0)+frames(40,0)+stacks(7,5,100)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(100,60)+stacks(10,8,200)+b'oksh> ',
        output+frames(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
        output+frames(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
    if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
    return parts
def validate(parts,arch):
    ends=[sum(map(len,parts[:i])) for i in range(1,5)];return e.validate_execution(b''.join(parts),*ends,ends[-1],arch)

class PollSignalEvidence(unittest.TestCase):
    def test_all_profiles_complete_raw_libc_modes_and_cleanup(self):
        expected_groups=dict(x86_64=8,i386=11,aarch64=6,arm32=16,rv32=6,rv64=6,loongarch64=6,mips=10,mips64=8,ppc=18)
        for arch in ARCHES:
            for newline in (b'\n',b'\r\n'):
                result=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch)
                for row in result['observations']:
                    groups=expected_groups[arch]
                    for key,value in dict(groups=groups,cases=groups*19,initial_waits=groups*17,
                        ready_retirements=groups*4,timeout_retirements=groups*2,cancelled_retirements=groups*2,
                        outer_handlers=groups*12,nested_handlers=groups,fatal_children=groups,exit_children=groups,immediate=groups*2).items():
                        self.assertEqual(row[key],value,(arch,key))
                    self.assertEqual(row['eintr']+row['efault'],groups*9)
                self.assertFalse(result['caught_poll_restart']);self.assertFalse(result['temporary_masks'])

    def test_missing_duplicate_malformed_and_late_arms(self):
        for arch in ARCHES:
            original=fixture(arch)
            for index in (2,3):
                span=original[index];lines=span.splitlines(keepends=True)
                tags=(b'POLL_SIGNAL_CASE_BEGIN',b'POLL_SIGNAL_ATTEMPT',b'OK_NATIVE_POLL_ARM',b'OK_NATIVE_POLL_RETIRE',b'OK_NATIVE_POLL_SIGNAL',b'POLL_SIGNAL_SEND',b'POLL_SIGNAL_HANDLE',b'POLL_SIGNAL_HANDLER_RETURN',b'POLL_SIGNAL_NESTED',b'POLL_SIGNAL_REUSE',b'POLL_SIGNAL_MUTATE_INPUT',b'POLL_SIGNAL_MUTATE_TIMEOUT',b'POLL_SIGNAL_PROTECT',b'POLL_SIGNAL_RETURN',b'POLL_SIGNAL_EXIT',b'POLL_SIGNAL_EXIT_PASS',b'POLL_SIGNAL_CASE_PASS')
                selected={tag:next(l for l in lines if l.startswith(tag+b' ')) for tag in tags}
                for tag,line in selected.items():
                    for name,changed in [('missing',b''),('duplicate',line+line),('malformed',b'junk '+line)]:
                        parts=original.copy();parts[index]=span.replace(line,changed,1)
                        with self.subTest(arch=arch,index=index,tag=tag,name=name),self.assertRaises(ValueError):validate(parts,arch)
                arm=selected[b'OK_NATIVE_POLL_ARM'];send=selected[b'POLL_SIGNAL_SEND']
                parts=original.copy();parts[index]=span.replace(arm,b'',1).replace(send,send+arm,1)
                with self.assertRaises(ValueError):validate(parts,arch)

    def test_native_owner_deadline_outcome_and_saved_result_fields(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for tag in (b'OK_NATIVE_POLL_ARM',b'OK_NATIVE_POLL_RETIRE',b'OK_NATIVE_POLL_SIGNAL'):
                line=next(l for l in lines if l.startswith(tag+b' '))
                for field in line.split()[1:]:
                    key,value=field.split(b'=')
                    if key==b'kind':replacement=b'select'
                    elif key==b'reason':replacement=b'ready'
                    elif key==b'result' and value==b'eintr':replacement=b'efault'
                    elif key==b'now':replacement=b'0'
                    else:replacement=str(int(value)+1).encode()
                    parts=original.copy();parts[2]=span.replace(line,line.replace(field,key+b'='+replacement),1)
                    with self.subTest(arch=arch,tag=tag,field=field),self.assertRaises(ValueError):validate(parts,arch)
            retired=next(l for l in lines if l.startswith(b'OK_NATIVE_POLL_RETIRE') and b'result=-4' in l)
            parts=original.copy();parts[2]=span.replace(retired,retired.replace(b'result=-4',b'result=-11'),1)
            with self.subTest(arch=arch,wrong_result=True),self.assertRaises(ValueError):validate(parts,arch)
            for tag in (b'POLL_SIGNAL_HANDLE',b'POLL_SIGNAL_HANDLER_RETURN'):
                line=next(l for l in lines if l.startswith(tag+b' '))
                for key in (b'result',b'pc'):
                    parts=original.copy();parts[2]=span.replace(line,re.sub(key+rb'=[0-9]+',key+b'=999',line),1)
                    with self.subTest(arch=arch,tag=tag,key=key),self.assertRaises(ValueError):validate(parts,arch)

    def test_copied_output_timeout_parent_status_and_context_mode(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2];lines=span.splitlines(keepends=True)
            for case in range(17):
                row=next(l for l in lines if l.startswith(b'POLL_SIGNAL_RETURN ') and f'variant=0 form=0 case={case} '.encode() in l)
                for field in (b'result',b'error',b'revents',b'mask',b'remaining'):
                    parts=original.copy();parts[2]=span.replace(row,re.sub(field+rb'=-?[0-9]+',field+b'=999999999',row),1)
                    with self.subTest(arch=arch,case=case,field=field),self.assertRaises(ValueError):validate(parts,arch)
            exit_row=next(l for l in lines if l.startswith(b'POLL_SIGNAL_EXIT_PASS ') and b'case=17 ' in l)
            parts=original.copy();parts[2]=span.replace(exit_row,re.sub(rb'signal=[0-9]+',b'signal=0',exit_row),1)
            with self.assertRaises(ValueError):validate(parts,arch)
            if arch=='arm32':
                parts=original.copy();parts[2]=span.replace(b'cpsr=16',b'cpsr=19')
                with self.assertRaises(ValueError):validate(parts,arch)
            if arch=='ppc':
                parts=original.copy();parts[2]=re.sub(rb'diagnostic_result=[0-9]+',b'diagnostic_result=0',span)
                with self.assertRaises(ValueError):validate(parts,arch)

    def test_boundary_snapshots_images_and_failure_markers(self):
        for arch in ARCHES:
            original=fixture(arch);span=original[2]
            frame=next(l for l in span.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_FRAMES'))
            image=next(l for l in span.splitlines(keepends=True) if e.IMAGE.fullmatch(l.strip()))
            for changed in (span.replace(frame,frame+frame),span.replace(image,image+image),span.replace(b'POLL_SIGNAL_PASS',b'POLL_SIGNAL_FAIL'),span.replace(b'faults=0',b'faults=1'),span.replace(b'POLL_SIGNAL_CASE_PASS',b'POLL_SIGNAL_LINUX_WAIT',1)):
                parts=original.copy();parts[2]=changed
                with self.subTest(arch=arch),self.assertRaises(ValueError):validate(parts,arch)
            if arch not in ('x86_64','i386'):
                parts=original.copy();parts[2]=re.sub(rb'((?:site|resume|pc)=)([0-9]+)',lambda m:m[1]+str(int(m[2])+1).encode(),span)
                with self.assertRaises(ValueError):validate(parts,arch)

    def test_incidental_futex_pipe_and_poll_events_are_joined(self):
        original=fixture('x86_64')
        events=[
            b'OK_NATIVE_FUTEX_ARM pid=50 tid=50 wait=1 origin=10 pc=1073750018 syscall=202 address=268443648 operation=128 expected=2 timeout=0 deadline=0 format=time64 live=1\nOK_NATIVE_FUTEX_RETIRE pid=50 tid=50 wait=1 origin=10 reason=ready result=0 live=0\n',
            b'OK_NATIVE_PIPE_READ_WAIT pid=50 tid=50 wait=1 request=1 output=1073750016 fd=3 description=1 pipe=2 bytes=64 stage=arm live=1\nOK_NATIVE_PIPE_READ_COMPLETE pid=50 tid=50 wait=1 request=1 output=1073750016 fd=3 description=1 pipe=2 bytes=64 result=4 outcome=ready pinned=0 live=0\n',
            b'OK_NATIVE_POLL_ARM pid=50 tid=50 wait=1 pc=1073750018 syscall=7 kind=poll count=1 deadline=0 live=1\nOK_NATIVE_POLL_RETIRE pid=50 tid=50 wait=1 reason=ready result=1 live=0\n']
        for index in range(5):
            for pair in events:
                parts=original.copy();parts[index]=parts[index].replace(b'OK_NATIVE_FRAMES',pair+b'OK_NATIVE_FRAMES',1)
                self.assertEqual(validate(parts,'x86_64')['runs'],2)
                parts[index]=parts[index].replace(pair,pair.splitlines(keepends=True)[0],1)
                with self.subTest(index=index,pair=pair),self.assertRaises(ValueError):validate(parts,'x86_64')

    def test_runner_profiles(self):
        import qualify_native_poll_signal as runner
        for arch in ARCHES:
            source,binary,command=runner.probe_layout(arch,'poll-signals')
            self.assertEqual(source,'native_poll_signal');self.assertEqual('/bin/'+binary,command)

if __name__=='__main__':unittest.main()
