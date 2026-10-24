"""Independent all-ten synthetic scalar-write traces; no guest instructions execute."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_write_evidence as e
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
NUMBERS=(1,4,64,4,64,64,64,4004,5001,4)
INIT=b'OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=1 wait=1 selector=2 output=1073800000 format=status outcome=arm result=-11 live=1\n'

def events(arch):
 lines=[];base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000;maximum=(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1;nr=NUMBERS[ARCHES.index(arch)];usr1,usr2=(16,17) if arch.startswith('mips') else (10,12);sequence=0
 for variant in range(2):
  for form in range(1 if variant else 2 if arch in ('arm32','ppc') else 1):
   for restart in range(2):
    for case in range(25):
     sequence+=1;pid=100+sequence*10;tid=pid+1;fd=4;rd=-1 if case==11 else 3;replacement=6 if case in (5,6) else -1;replacementread=5 if replacement!=-1 else -1;nestedfd=6 if case==17 else -1;nestedread=5 if case==17 else -1;ptr=base+0x10000040;nptr=ptr+4096 if case==17 else 0;count=1 if case==0 else 4096 if case in (1,12) else 4097 if case in (13,14) else 32;size=count if case==14 else min(count,4096);caught=case in (0,1,6,14,15,16,17,18,19,23);again=bool(1-restart if case==15 else restart);pending=8<=case<=11;immediate=case in (9,10,11,13);edited=case==18 and not variant and again
     site=base+0x2001 if arch in ('x86_64','i386') else base+0x2000+form*64;width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4;resume=site+width;libcsite=base+0x5000;libcwidth=2 if arch=='arm32' else width
     key=f'arch={arch} variant={variant} form={form} restart={restart} case={case}';lines.append(f'PIPE_WRITE_CASE_BEGIN {key} pid={pid} tid={tid} fd={fd} readfd={rd} replacement={replacement} replacementread={replacementread} nestedfd={nestedfd} nestedread={nestedread} input={ptr} nestedinput={nptr} count={count} site={site} resume={resume} syscall={nr} uid=1000 capacity=4096')
     def event(tag,value=0,ordinal=0,actor=9):lines.append(f'PIPE_WRITE_{tag} {key} actor={actor} ordinal={ordinal} value={value}')
     generation=0;active=None;prefix='OK_NATIVE_PIPE_WRITE_LARGE_' if case==14 else 'OK_NATIVE_PIPE_WRITE_'
     def arm(nested=False):
      nonlocal active,generation
      assert active is None;generation+=1;active=dict(pid=pid,tid=tid,wait=generation,request=generation,input=nptr if nested else ptr,fd=nestedfd if nested else fd,description=7 if nested else 5,pipe=1 if nested else 0,bytes=8 if nested else count)
      if case==14:active['committed']=0
      lines.append(prefix+'WAIT '+' '.join(f'{k}={v}' for k,v in active.items())+' stage=arm live=1');pc=(site+width) if not variant or nested else libcsite+libcwidth
      lines.append(prefix+f'ORIGIN pid={pid} tid={tid} request={generation} wait={generation} origin={generation+100} pc={pc} syscall={nr} fd={active["fd"]} input={active["input"]} bytes={active["bytes"]}'+(' committed=0' if case==14 else ''))
     def terminal(outcome,result):
      nonlocal active
      r=active;assert r is not None
      if case==14 and outcome=='ready':r['committed']=result
      lines.append(prefix+'COMPLETE '+' '.join(f'{k}={v}' for k,v in r.items())+f' result={result} outcome={outcome} pinned=0 live=0');active=None;return r
     def interrupt(nested=False):
      redo=again and not nested;r=terminal('interrupted',0 if redo else -4);pc=(site if redo else resume) if not variant or nested else libcsite+(0 if redo else libcwidth)
      lines.append(prefix+f'SIGNAL pid={pid} tid={tid} request={r["request"]} wait={r["wait"]} origin={r["request"]+100} signal={usr2 if nested else usr1} outcome={"restart" if redo else "eintr"} pc={pc} syscall={nr} fd={r["fd"]} input={r["input"]} bytes={r["bytes"]}'+(' committed=0' if case==14 else '')+' pinned=0 live=0')
     def rearm():
      nonlocal generation
      generation+=1;active['wait']=generation
      if case==14:active['committed']=4096
      lines.append(prefix+'WAIT '+' '.join(f'{k}={v}' for k,v in active.items())+' stage=rearm live=1')
     def handler(tag,nested=False,edit=False):
      inspected=caught and not(nested and case==16);pc=base+0x6000;suffix=''
      if inspected:
       redo=again and not nested;arg0=nestedfd if nested else fd;arg1=nptr if nested else ptr;arg2=8 if nested else count;arg3=4951 if not variant or nested else 777
       value=77 if edit else (nr if arch in ('x86_64','i386','mips','mips64') else arg0) if redo else 4 if arch in ('mips','mips64','ppc') else maximum-3
       number=77 if edit and arch in ('x86_64','i386','mips','mips64') else nr if redo or arch not in ('x86_64','i386','mips','mips64') else value
       if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not redo or edit):arg0=value
       if arch in ('mips','mips64'):arg3=0 if edit else arg3 if redo else 1
       pc=resume if edit else (site if redo else resume) if not variant or nested else libcsite+(0 if redo else libcwidth)
       suffix=f' number={number} result={value} a0={arg0} a1={arg1} a2={arg2} a3={arg3}'
       if arch=='ppc':suffix+=f' cr={0 if edit else 0x10000000} diagnostic_result={0x123 if edit else 0 if redo else maximum-3} orig_r3={0x234 if edit else nestedfd if nested else fd}'
       if arch=='arm32':suffix+=f' cpsr={48 if form or variant and not nested else 16}'
      lines.append(f'PIPE_WRITE_{tag} {key} actor=0 pid={pid} tid={tid} depth={2 if nested else 1} inspected={int(inspected)} pc={pc}{suffix}')
     def drain(n=4096,ordinal=0,pipe=0):event('DRAIN_BEGIN',10000*pipe+n,ordinal);event('DRAIN_END',10000*pipe+n,ordinal)
     def result(value):event('RETURN',value,actor=0);event('ERRNO',(14 if case==3 else 11 if case==10 else 32 if case in (11,24) else 4) if variant and value==-1 else 111,actor=0)
     def payload(pipe,n,value):lines.append(f'PIPE_WRITE_PAYLOAD {key} actor=9 pipe={pipe} bytes={n} value={value}')
     if pending:event('SEND',usr1)
     lines.append(f'PIPE_WRITE_ATTEMPT {key} actor=0 pid={pid} tid={tid} a0={fd} a1={ptr} a2={count} a3=4951 a4=0 a5=0')
     if not immediate:arm()
     if case in (5,6):event('REPLACE_FD',replacement);rearm()
     if case==2:event('MUTATE_INPUT',90)
     if case==4:event('PROTECT_READ')
     if caught:
      if case==15:event('CHANGE_ACTION',int(again))
      event('SEND',usr1);interrupt();handler('HANDLE')
      if case==16:event('NEST_SEND',usr2,actor=0);handler('NESTED',True)
      if case==17:
       event('NEST_ATTEMPT',nestedfd,actor=0);arm(True);event('SEND',usr2);interrupt(True);handler('NESTED',True);event('NEST_EINTR',-4,actor=0);event('NEST_RETRY',nestedfd,1,0);arm(True);drain(pipe=1);terminal('ready',8);event('NEST_RETURN',8,1,0)
      if case==19:handler('THREAD_EXIT');drain()
      elif case==23:handler('HANDLER_EXEC')
      else:
       handler('HANDLER_RETURN',edit=edited)
       if not again or edited:result(77 if edited else -1 if variant else -4);event('RETRY',fd,1,0)
       if case!=6:
        arm();drain()
        if case==14:rearm();event('PAYLOAD_BEGIN',4096);payload(0,4096,65)
        terminal('ready',size)
       if not again or edited:event('RETRY_RETURN',size,1,0)
       else:result(size)
       if case==6:drain()
     elif case==3:
      event('PROTECT_NONE');drain();terminal('efault',-14);result(-1 if variant else -14);event('RESTORE_INPUT');event('RETRY',fd,1,0);event('RETRY_RETURN',size,1,0)
     elif case in (20,21,22):
      if case==20:event('SEND',usr1)
      if case==21:event('EXIT_GROUP')
      if case!=22:terminal('cancelled',-125)
     elif case==24:event('CLOSE_READER',rd);terminal('error',-32);result(-1 if variant else -32)
     else:
      if not immediate:
       if case==7:event('SEND',usr1)
       if case==12:drain(1);rearm();event('ATOMIC_PENDING',1);drain(4095,1)
       else:drain()
       terminal('ready',size)
      result((-1 if variant else -11) if case==10 else (-1 if variant else -32) if case==11 else size)
      if pending:event('PENDING',1,actor=0);event('UNMASK',actor=0);handler('HANDLE');handler('HANDLER_RETURN')
      if case==10:drain()
     if case in (22,23):
      executor=0 if case==23 else 9;event('EXEC_FAILED',2,actor=executor);event('EXEC_COMMIT',pid,actor=executor)
      if case==22:terminal('cancelled',-125)
      lines.append(IMAGE.decode().strip());event('EXEC_REPLACED',pid);event('EMPTY',rd);payload(0,1,80);event('EMPTY',rd);event('EXEC_CHECKED',pid)
     elif case not in (20,21):
      if case not in (10,11,19,24):payload(2 if case==6 else 0,1 if case==14 else size,90 if case==2 else 65)
      if case==17:payload(1,8,66)
      if rd>=0 and case!=24:event('EMPTY',rd)
      if case==17:event('EMPTY',nestedread,1)
      if case in (5,6):event('EMPTY',replacementread,2)
      lines.append(f'PIPE_WRITE_CASE_PASS {key}')
     lines.append(f'PIPE_WRITE_PARENT_PASS {key} pid={pid} signal={usr1 if case==20 else 0}')
     assert active is None
 return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
 marker,_,command,leases=e.probe_spec(arch,'pipe-write-signals');body=command+b'\n'+IMAGE+events(arch)+marker+b'\n'
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts

def validate(parts,arch):
 ends=[sum(map(len,parts[:i])) for i in range(1,5)];return e.validate_execution(b''.join(parts),*ends,ends[-1],arch)

class ScalarPipeWriteEvidence(unittest.TestCase):
 def test_descriptor_rearm_requires_its_replacement_and_precedes_release_or_signal(self):
  for arch in ARCHES:
   original=fixture(arch)
   for case in (5,6):
    lines=original[2].splitlines(keepends=True);key=f'variant=0 form=0 restart=0 case={case} '.encode()
    start=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_CASE_BEGIN ') and key in l);end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'PIPE_WRITE_PARENT_PASS '))
    ri=next(i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_PIPE_WRITE_WAIT ') and b'stage=rearm ' in lines[i]);record=lines.pop(ri)
    for tag,after in ((b'PIPE_WRITE_REPLACE_FD ',False),(b'PIPE_WRITE_SEND ' if case==6 else b'PIPE_WRITE_DRAIN_BEGIN ',True)):
     modified=lines.copy();target=next(i for i in range(start,end-1) if lines[i].startswith(tag));modified.insert(target+int(after),record);parts=original.copy();parts[2]=b''.join(modified)
     with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(parts,arch)
 def test_all_profiles_context_forms_and_newlines(self):
  for arch in ARCHES:
   for newline in (b'\n',b'\r\n'):
    with self.subTest(arch=arch,newline=newline):
     result=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch);groups=6 if arch in ('arm32','ppc') else 4
     self.assertEqual(result['baseline']['objects'],1)
     for r in result['observations']:self.assertEqual(r['cases'],25*groups);self.assertEqual(r['rearms'],4*groups);self.assertEqual(r['exec_replacements'],2*groups)
 def test_missing_duplicate_malformed(self):
  for arch in ARCHES:
   original=fixture(arch)
   for pattern in e.PATTERNS:
    line=next(l for l in original[2].splitlines(keepends=True) if pattern.fullmatch(l.rstrip(b'\n')))
    for bad in (b'',line+line,b'garbage '+line):
     parts=original.copy();parts[2]=parts[2].replace(line,bad,1)
     with self.subTest(arch=arch,tag=line.split()[0]),self.assertRaises(ValueError):validate(parts,arch)
 def test_copied_request_abi_and_payload(self):
  groups=((b'PIPE_WRITE_CASE_BEGIN',(b'pid',b'tid',b'fd',b'input',b'count',b'site',b'syscall')),(b'PIPE_WRITE_ATTEMPT',tuple(f'a{i}'.encode() for i in range(6))),(b'PIPE_WRITE_HANDLE',(b'pid',b'tid',b'pc',b'number',b'result',b'a0',b'a1',b'a2',b'a3')),(b'PIPE_WRITE_PAYLOAD',(b'pipe',b'bytes',b'value')),(b'PIPE_WRITE_PARENT_PASS',(b'pid',b'signal')))
  for arch in ARCHES:
   original=fixture(arch)
   for prefix,fields in groups:
    line=next(l for l in original[2].splitlines(keepends=True) if l.startswith(prefix+b' '))
    for field in fields:
     bad=re.sub(rb'(?<![a-z0-9_])'+field+rb'=-?[0-9]+',field+b'=999',line);parts=original.copy();parts[2]=parts[2].replace(line,bad,1)
     with self.subTest(arch=arch,prefix=prefix,field=field),self.assertRaises(ValueError):validate(parts,arch)
 def test_owned_write_diagnostics(self):
  for arch in ARCHES:
   original=fixture(arch)
   for prefix in (b'OK_NATIVE_PIPE_WRITE_WAIT',b'OK_NATIVE_PIPE_WRITE_ORIGIN',b'OK_NATIVE_PIPE_WRITE_COMPLETE',b'OK_NATIVE_PIPE_WRITE_SIGNAL'):
    line=next(l for l in original[2].splitlines(keepends=True) if l.startswith(prefix+b' '))
    fields=[f.split(b'=')[0] for f in line.split()[1:] if f.split(b'=')[1].lstrip(b'-').isdigit()]
    for field in fields:
     bad=re.sub(rb'(?<![a-z0-9_])'+field+rb'=-?[0-9]+',field+b'=999',line);parts=original.copy();parts[2]=parts[2].replace(line,bad,1)
     with self.subTest(arch=arch,prefix=prefix,field=field),self.assertRaises(ValueError):validate(parts,arch)
 def test_temporal_and_cross_event_corruptions(self):
  def part(body,case):
   lines=body.splitlines(keepends=True);key=f'variant=0 form=0 restart=0 case={case} '.encode();begin=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_CASE_BEGIN ') and key in l);end=next(i for i,l in enumerate(lines[begin:],begin) if l.startswith(b'PIPE_WRITE_PARENT_PASS ') and key in l);return lines,begin,end
  def at(lines,tag):return next(i for i,l in enumerate(lines) if l.startswith(tag+b' '))
  def move(lines,tag,before):
   line=lines.pop(at(lines,tag));lines.insert(at(lines,before),line);return lines
  controls=[(0,b'PIPE_WRITE_CASE_PASS',b'PIPE_WRITE_ATTEMPT'),(0,b'PIPE_WRITE_HANDLER_RETURN',b'PIPE_WRITE_HANDLE'),(0,b'PIPE_WRITE_HANDLE',b'PIPE_WRITE_SEND'),(2,b'PIPE_WRITE_RETURN',b'PIPE_WRITE_MUTATE_INPUT'),(3,b'PIPE_WRITE_RETRY',b'PIPE_WRITE_PROTECT_NONE'),(6,b'PIPE_WRITE_SEND',b'PIPE_WRITE_REPLACE_FD'),(0,b'PIPE_WRITE_DRAIN_BEGIN',b'PIPE_WRITE_ATTEMPT'),(12,b'PIPE_WRITE_ATOMIC_PENDING',b'PIPE_WRITE_DRAIN_BEGIN'),(17,b'PIPE_WRITE_NEST_RETRY',b'PIPE_WRITE_NEST_EINTR'),(22,b'PIPE_WRITE_EXEC_REPLACED',b'PIPE_WRITE_EXEC_COMMIT'),(0,b'PIPE_WRITE_EMPTY',b'PIPE_WRITE_PAYLOAD')]
  for arch in ARCHES:
   original=fixture(arch)
   for case,tag,before in controls:
    lines,a,b=part(original[2],case);changed=move(lines[a:b+1].copy(),tag,before);pieces=original.copy();pieces[2]=b''.join(lines[:a]+changed+lines[b+1:])
    with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(pieces,arch)
   for case,tag,field,value in ((13,b'PIPE_WRITE_RETURN',b'value',4097),(5,b'PIPE_WRITE_PAYLOAD',b'pipe',2),(17,b'PIPE_WRITE_NEST_RETURN',b'value',9)):
    lines,a,b=part(original[2],case);j=a+at(lines[a:b+1],tag);lines[j]=re.sub(rb'(?<![a-z_])'+field+rb'=-?[0-9]+',field+b'='+str(value).encode(),lines[j]);pieces=original.copy();pieces[2]=b''.join(lines)
    with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(pieces,arch)
 def test_resource_baseline_and_extra_image(self):
  original=fixture('x86_64')
  for i in (0,2,3,4):
   for prefix in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
    line=next(l for l in original[i].splitlines(keepends=True) if l.startswith(prefix));parts=original.copy();parts[i]=parts[i].replace(line,line+line,1)
    with self.assertRaises(ValueError):validate(parts,'x86_64')
  parts=original.copy();parts[0]=parts[0].replace(INIT,b'')
  with self.assertRaises(ValueError):validate(parts,'x86_64')
  parts=original.copy();parts[2]=parts[2].replace(IMAGE,IMAGE+IMAGE,1)
  with self.assertRaises(ValueError):validate(parts,'x86_64')

 def test_ready_completion_precedes_retry_return(self):
  for arch in ARCHES:
   parts=fixture(arch);lines=parts[2].splitlines(keepends=True)
   end=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_PARENT_PASS '))
   target=next(i for i in range(end) if lines[i].startswith(b'OK_NATIVE_PIPE_WRITE_COMPLETE ') and b'outcome=ready ' in lines[i])
   record=lines.pop(target);at=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_RETRY_RETURN '));lines.insert(at+1,record);parts[2]=b''.join(lines)
   with self.subTest(arch=arch),self.assertRaises(ValueError):validate(parts,arch)
 def test_exec_handler_precedes_failed_exec_and_replacement(self):
  for arch in ARCHES:
   original=fixture(arch)
   for tag in (b'PIPE_WRITE_EXEC_FAILED ',b'PIPE_WRITE_EXEC_CHECKED '):
    parts=original.copy();lines=parts[2].splitlines(keepends=True);key=b'variant=0 form=0 restart=0 case=23 '
    group=[l for l in lines if key in l and l.startswith((b'PIPE_WRITE_HANDLE ',b'PIPE_WRITE_HANDLER_EXEC '))]
    self.assertEqual(len(group),2);lines=[l for l in lines if l not in group];at=next(i for i,l in enumerate(lines) if l.startswith(tag) and key in l);lines[at+1:at+1]=group;parts[2]=b''.join(lines)
    with self.subTest(arch=arch,tag=tag),self.assertRaises(ValueError):validate(parts,arch)
 def test_join_proofs_follow_writer_completion(self):
  controls=((6,b'PIPE_WRITE_DRAIN_BEGIN ',b'PIPE_WRITE_HANDLER_RETURN '),(10,b'PIPE_WRITE_DRAIN_BEGIN ',b'PIPE_WRITE_HANDLE '),(19,b'PIPE_WRITE_DRAIN_BEGIN ',b'PIPE_WRITE_THREAD_EXIT '),(8,b'PIPE_WRITE_PAYLOAD ',b'PIPE_WRITE_HANDLE '),(8,b'PIPE_WRITE_EMPTY ',b'PIPE_WRITE_HANDLE '))
  for arch in ARCHES:
   original=fixture(arch)
   for case,tag,before in controls:
    parts=original.copy();lines=parts[2].splitlines(keepends=True);key=f'variant=0 form=0 restart=0 case={case} '.encode()
    at=next(i for i,l in enumerate(lines) if l.startswith(tag) and key in l);record=lines.pop(at);at=next(i for i,l in enumerate(lines) if l.startswith(before) and key in l);lines.insert(at,record);parts[2]=b''.join(lines)
    with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(parts,arch)
 def test_boot_rejects_caught_write_ledger(self):
  for arch in ARCHES:
   parts=fixture(arch);first=events(arch).split(b'PIPE_WRITE_PARENT_PASS ',1)[0]
   injected=b'\n'.join(line for line in first.splitlines() if line.startswith(b'OK_NATIVE_PIPE_WRITE_'))+b'\n'
   e.write_events(injected,arch,allow_signal=True)
   parts[0]=parts[0][:-len(b'oksh> ')]+injected+b'oksh> '
   with self.subTest(arch=arch),self.assertRaises(ValueError):validate(parts,arch)
 def test_ignored_delivery_and_exec_preserve_blocked_request_order(self):
  controls=((7,b'PIPE_WRITE_SEND ',b'PIPE_WRITE_DRAIN_END ',True),(22,b'PIPE_WRITE_EXEC_FAILED ',b'PIPE_WRITE_ATTEMPT ',False),(22,b'OK_NATIVE_PIPE_WRITE_COMPLETE ',b'OK_NATIVE_IMAGE ',True))
  for arch in ARCHES:
   original=fixture(arch)
   for case,tag,target,after in controls:
    parts=original.copy();lines=parts[2].splitlines(keepends=True);key=f'variant=0 form=0 restart=0 case={case} '.encode()
    start=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_CASE_BEGIN ') and key in l);end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'PIPE_WRITE_PARENT_PASS '))
    group=lines[start:end+1];at=next(i for i,l in enumerate(group) if l.startswith(tag));record=group.pop(at);at=next(i for i,l in enumerate(group) if l.startswith(target));group.insert(at+int(after),record);parts[2]=b''.join(lines[:start]+group+lines[end+1:])
    with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(parts,arch)

 def test_large_blocking_progress_and_read_publication(self):
  for arch in ARCHES:
   original=events(arch);lines=original.splitlines(keepends=True);key=b'variant=0 form=0 restart=0 case=14 '
   begin=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_WRITE_CASE_BEGIN ') and key in l);end=next(i for i in range(begin,len(lines)) if lines[i].startswith(b'PIPE_WRITE_PARENT_PASS '))
   def check(data):return e.validate_cases(data+e.probe_spec(arch,'pipe-write-signals')[0]+b'\n',arch)
   controls=[]
   for tag,field,value in ((b'OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'committed',1),(b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'committed',1),(b'PIPE_WRITE_PAYLOAD ',b'bytes',4095)):
    at=next(i for i in range(begin,end) if lines[i].startswith(tag));bad=lines.copy();bad[at]=re.sub(rb'(?<![a-z_])'+field+rb'=[0-9]+',field+b'='+str(value).encode(),bad[at]);controls.append(b''.join(bad))
   # The small namespace must never substitute for a large owned request.
   bad=lines.copy()
   for i in range(begin,end):
    if bad[i].startswith(b'OK_NATIVE_PIPE_WRITE_LARGE_'):bad[i]=re.sub(rb' committed=[0-9]+',b'',bad[i].replace(b'OK_NATIVE_PIPE_WRITE_LARGE_',b'OK_NATIVE_PIPE_WRITE_'))
   controls.append(b''.join(bad))
   at=next(i for i in range(begin,end) if lines[i].startswith(b'PIPE_WRITE_PAYLOAD_BEGIN '));bad=lines.copy();record=bad.pop(at);target=next(i for i in range(begin,end-1) if bad[i].startswith(b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ') and b'outcome=ready ' in bad[i]);bad.insert(target+1,record);controls.append(b''.join(bad))
   for data in controls:
    with self.subTest(arch=arch),self.assertRaises(ValueError):check(data)
   # Read completion and serial proof may be delayed until after syscall return.
   bad=lines.copy();proofs=[l for l in bad[begin:end] if l.startswith(b'PIPE_WRITE_PAYLOAD ')][:1]
   for proof in proofs:bad.remove(proof)
   target=next(i for i in range(begin,len(bad)) if bad[i].startswith(b'PIPE_WRITE_PAYLOAD '));bad[target:target]=proofs
   with self.subTest(arch=arch,race='proof-after-return'):check(b''.join(bad))

if __name__=='__main__':unittest.main()
