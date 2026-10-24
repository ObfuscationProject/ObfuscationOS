"""Synthetic all-ten vector ABI/event traces; no guest or hardware instructions execute."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_vector_evidence as e
from native_pipe_vector_events import native_events,READV,WRITEV
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
ARCHES=tuple(READV)
INIT=b'OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=1 wait=1 selector=2 output=1073800000 format=status outcome=arm result=-11 live=1\n'

def events(arch):
 lines=[];base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000;maximum=(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1;usr1,usr2=(16,17) if arch.startswith('mips') else (10,12);sequence=0
 for direction in range(2):
  nr=(WRITEV if direction else READV)[arch];prefix='OK_NATIVE_PIPE_'+('WRITEV_' if direction else 'READV_')
  for variant in range(2):
   for form in range(1 if variant else 2 if arch in ('arm32','ppc') else 1):
    for restart in range(2):
     for case in range(36):
      prefix='OK_NATIVE_PIPE_'+('WRITEV_LARGE_' if direction and case==34 else 'WRITEV_' if direction else 'READV_')
      sequence+=1;pid=100+sequence*10;tid=pid+1;fd=4 if direction else 3;rd=-1 if direction and case==11 else 7 if not direction and case in (5,6) else 3;wr=-1 if not direction and case==11 else 4;replacement=(6 if direction else 5) if case in (5,6) else -1;rr=5 if replacement!=-1 else -1;nf=(6 if direction else 5) if case==17 else -1;nrfd=5 if case==17 else -1;mapping=base+0x10000000;array=mapping+57344;narray=array+4096 if case==17 else 0;count=4096 if case==12 else 4097 if case in (13,34) else 32;nvec=0 if case==25 else 17 if case==27 else 2 if case==28 else maximum if case==29 else 16 if case==32 else 3
      sizes=lambda role:(3,5) if role else (2048,count-2048) if count>32 else (13,19)
      vals=lambda role:(81,82) if role==2 else (97,98) if role==1 else (90,91) if case==2 else (65,66)
      ptr=lambda role,seg:mapping+role*16384+seg*8192+64
      shapes={}
      for role in range(3):
       n=3 if role==2 else 16 if case==32 else 3
       shapes[role]=[(1,0)]*(n-2)+[(ptr(role,j),sizes(role)[j]) for j in range(2)]
      if case==26:shapes[0]=[(1,0)]*3
      if case==28:shapes[0]=[(ptr(0,0),maximum//2),(ptr(0,1),1)]
      caught=case in (0,6,14,15,16,17,18,19,23);again=bool(1-restart if case==15 else restart);pending=8<=case<=11;immediate=case in (9,10,11,13) or 25<=case<=31;edited=case==18 and not variant and again;normal=case not in (20,21,22,23);success=normal and case not in (10,11,19,24) and not 25<=case<=31
      amount=8 if case==14 else 17 if not direction and case in (9,13) else count if direction and case==34 else min(count,4096)
      site=base+0x2001 if arch in ('x86_64','i386') else base+0x2000+form*64;width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4;resume=site+width;libcsite=base+0x5000;libcwidth=2 if arch=='arm32' else width
      key=f'arch={arch} direction={direction} variant={variant} form={form} restart={restart} case={case}'
      lines.append(f'PIPE_VECTOR_CASE_BEGIN {key} pid={pid} tid={tid} fd={fd} readfd={rd} writefd={wr} replacement={replacement} replacementread={rr} nestedfd={nf} nestedread={nrfd} array={array} nestedarray={narray} count={count} iovcnt={nvec} site={site} resume={resume} syscall={nr} uid=1000 capacity=4096')
      for role in range(3 if case==17 else 2):
       for i,(p,n) in enumerate(shapes[role]):lines.append(f'PIPE_VECTOR_ENTRY {key} role={role} index={i} base={p} length={n}')
      def event(tag,value=0,ordinal=0,actor=9):lines.append(f'PIPE_VECTOR_{tag} {key} actor={actor} ordinal={ordinal} value={value}')
      generation=0;active=None
      def arm(nested=False,fresh=False):
       nonlocal active,generation
       assert active is None;generation+=1;role=2 if nested else 1 if case==14 and fresh else 0;shape=shapes[role]
       active=dict(pid=pid,tid=tid,wait=generation,request=generation,array=narray if nested else array,fd=nf if nested else fd,description=7 if nested else 5,pipe=1 if nested else 0,bytes=min(sum(n for p,n in shape),4097 if direction else 4096),iovcnt=len(shape),vectors=','.join(f'{p}:{n}' for p,n in shape))
       if direction and case==34:active['committed']=0
       lines.append(prefix+'WAIT '+' '.join(f'{k}={v}' for k,v in active.items())+' stage=arm live=1');pc=resume if not variant or nested else libcsite+libcwidth
       lines.append(prefix+f'ORIGIN pid={pid} tid={tid} request={generation} wait={generation} origin={generation+100} pc={pc} syscall={nr} fd={active["fd"]} array={active["array"]} bytes={active["bytes"]} iovcnt={active["iovcnt"]} vectors={active["vectors"]}'+(' committed=0' if direction and case==34 else ''))
      def terminal(outcome,value):
       nonlocal active
       r=active;assert r is not None
       if direction and case==34:r['committed']=value
       lines.append(prefix+'COMPLETE '+' '.join(f'{k}={v}' for k,v in r.items())+f' result={value} outcome={outcome} pinned=0 live=0');active=None;return r
      def rearm():
       nonlocal generation
       generation+=1;active['wait']=generation
       if direction and case==34:active['committed']=4096
       lines.append(prefix+'WAIT '+' '.join(f'{k}={v}' for k,v in active.items())+' stage=rearm live=1')
      def interrupt(nested=False):
       redo=again and not nested;r=terminal('interrupted',0 if redo else -4);pc=(site if redo else resume) if not variant or nested else libcsite+(0 if redo else libcwidth)
       lines.append(prefix+f'SIGNAL pid={pid} tid={tid} request={r["request"]} wait={r["wait"]} origin={r["request"]+100} signal={usr2 if nested else usr1} outcome={"restart" if redo else "eintr"} pc={pc} syscall={nr} fd={r["fd"]} array={r["array"]} bytes={r["bytes"]} iovcnt={r["iovcnt"]} vectors={r["vectors"]} pinned=0 live=0')
      def handler(tag,nested=False,edit=False):
       inspected=caught and not(nested and case==16);pc=base+0x6000;suffix=''
       if inspected:
        redo=again and not nested;arg0=nf if nested else fd;arg1=narray if nested else array;arg2=3 if nested else nvec;arg3=4951 if not variant or nested else 777
        val=77 if edit else (nr if arch in ('x86_64','i386','mips','mips64') else arg0) if redo else 4 if arch in ('mips','mips64','ppc') else maximum-3
        number=77 if edit and arch in ('x86_64','i386','mips','mips64') else nr if redo or arch not in ('x86_64','i386','mips','mips64') else val
        if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not redo or edit):arg0=val
        if arch.startswith('mips'):arg3=0 if edit else arg3 if redo else 1
        pc=resume if edit else (site if redo else resume) if not variant or nested else libcsite+(0 if redo else libcwidth)
        suffix=f' number={number} result={val} a0={arg0} a1={arg1} a2={arg2} a3={arg3}'
        if arch=='ppc':suffix+=f' cr={0 if edit else 0x10000000} diagnostic_result={0x123 if edit else 0 if redo else maximum-3} orig_r3={0x234 if edit else nf if nested else fd}'
        if arch=='arm32':suffix+=f' cpsr={48 if form or variant and not nested else 16}'
       lines.append(f'PIPE_VECTOR_{tag} {key} actor=0 pid={pid} tid={tid} depth={2 if nested else 1} inspected={int(inspected)} pc={pc}{suffix}')
      def ready(n=None,ordinal=0,pipe=0):
       n=(4096 if direction else amount) if n is None else n
       if pipe and not direction:n=8
       event('READY_BEGIN',pipe*10000+n,ordinal);event('READY_END',pipe*10000+n,ordinal)
      def result(value):
       error=14 if case in (3,35,30,31) else 11 if case==10 else 22 if 27<=case<=29 else 32 if direction and case in (11,24) else 4
       event('RETURN',value,actor=0);event('ERRNO',error if variant and value==-1 else 111,actor=0)
      if pending:event('SEND',usr1)
      lines.append(f'PIPE_VECTOR_ATTEMPT {key} actor=0 pid={pid} tid={tid} a0={fd} a1={array} a2={nvec} a3=4951 a4=0 a5=0')
      if not immediate:arm()
      if case in (5,6):event('REPLACE_FD',replacement);rearm()
      if case in (1,14):event('MUTATE_VECTOR',1)
      if case==33:event('MUTATE_LENGTH')
      if case==2:event('MUTATE_INPUT',90)
      if case==4:event('PROTECT_VECTOR')
      if caught:
       if case==15:event('CHANGE_ACTION',int(again))
       event('SEND',usr1);interrupt();handler('HANDLE')
       if case==16:event('NEST_SEND',usr2,actor=0);handler('NESTED',True)
       if case==17:
        event('NEST_ATTEMPT',nf,actor=0);arm(True);event('SEND',usr2);interrupt(True);handler('NESTED',True);event('NEST_EINTR',-4,actor=0);event('NEST_RETRY',nf,1,0);arm(True);ready(pipe=1);terminal('ready',8);event('NEST_RETURN',8,1,0)
       if case==19:
        handler('THREAD_EXIT')
        if direction:ready()
       elif case==23:handler('HANDLER_EXEC')
       else:
        handler('HANDLER_RETURN',edit=edited)
        if not again or edited:result(77 if edited else -1 if variant else -4);event('RETRY',fd,1,0)
        if case!=6:arm(fresh=True);ready();terminal('ready',amount)
        if not again or edited:event('RETRY_RETURN',amount,1,0)
        else:result(amount)
        if case==6 and direction:ready()
      elif case in (3,35):
       event('PROTECT_NONE');ready();terminal('efault',-14);result(-1 if variant else -14)
       if case==35:event('FAULT_UNTOUCHED',0 if direction else 13)
       event('RESTORE_INPUT');event('RETRY',fd,1,0);event('RETRY_RETURN',amount,1,0)
      elif case in (20,21,22):
       if case==20:event('SEND',usr1)
       if case==21:event('EXIT_GROUP')
       if case!=22:terminal('cancelled',-125)
      elif case==24:event('CLOSE_PEER',rd if direction else wr);terminal('error' if direction else 'eof',-32 if direction else 0);result((-1 if variant else -32) if direction else 0)
      else:
       if not immediate:
        if case==7:event('SEND',usr1)
        if case==12 and direction:ready(1);rearm();event('ATOMIC_PENDING',1);ready(4095,1)
        else:ready()
        if direction and case==34:
         rearm();event('PAYLOAD_BEGIN',4096)
         for seg in range(2):lines.append(f'PIPE_VECTOR_PAYLOAD {key} actor=9 pipe=0 segment={seg} bytes=2048 value={65+seg}')
        terminal('ready',amount)
       error=11 if case==10 else 32 if direction and case==11 else 22 if 27<=case<=29 else 14
       value=(-1 if variant else -error) if case==10 or direction and case==11 or 27<=case<=31 else 0 if case in (25,26) or not direction and case==11 else amount
       result(value)
       if pending:event('PENDING',1,actor=0);event('UNMASK',actor=0);handler('HANDLE');handler('HANDLER_RETURN')
       if direction and (case==10 or 25<=case<=31):ready()
      if case in (22,23):
       executor=0 if case==23 else 9;event('EXEC_FAILED',2,actor=executor);event('EXEC_COMMIT',pid,actor=executor)
       if case==22:terminal('cancelled',-125)
       lines.append(IMAGE.decode().strip());event('EXEC_REPLACED',pid);event('EMPTY',rd);event('EXEC_BYTE',80);event('EMPTY',rd);event('EXEC_CHECKED',pid)
      elif normal:
       specs=[]
       if direction and case==34:lines.append(f'PIPE_VECTOR_PAYLOAD {key} actor=9 pipe=0 segment=1 bytes=1 value=66')
       elif direction and success:specs.append((2 if case==6 else 0,amount,1 if case==14 else 0))
       if direction and case==17:specs.append((1,8,2))
       if not direction and case==5:specs.append((2,count,0))
       for pipe,total,role in specs:
        for seg,n in enumerate(sizes(role)):
         n=min(n,total);total-=n;lines.append(f'PIPE_VECTOR_PAYLOAD {key} actor=9 pipe={pipe} segment={seg} bytes={n} value={vals(role)[seg]}')
       for role in range(3):
        consumed=amount if not direction and success and role==(1 if case==14 else 0) else 8 if not direction and case==17 and role==2 else 0
        for seg,n in enumerate(sizes(role)):
         filled=n if direction else min(n,consumed);consumed-=min(n,consumed);lines.append(f'PIPE_VECTOR_BUFFER {key} actor=9 role={role} segment={seg} base={ptr(role,seg)} bytes={filled} value={vals(role)[seg]} guards=1')
       if case not in (11,24):event('EMPTY',rd)
       if case==17:event('EMPTY',nrfd,1)
       if case in (5,6):event('EMPTY',rr,2)
       lines.append(f'PIPE_VECTOR_CASE_PASS {key}')
      lines.append(f'PIPE_VECTOR_PARENT_PASS {key} pid={pid} signal={usr1 if case==20 else 0}')
 return ('\n'.join(lines)+'\n').encode()

def transcript(arch):
 marker,_,command,leases=e.probe_spec(arch,'pipe-vector-signals');body=command+b'\n'+IMAGE+events(arch)+marker+b'\n'
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts

def validate(parts,arch):
 ends=[];offset=0
 for p in parts[:-1]:offset+=len(p);ends.append(offset)
 return e.validate_execution(b''.join(parts),ends[0],ends[1],ends[2],ends[3],ends[3],arch)

class VectorGuestTests(unittest.TestCase):
 def test_all_profiles_and_line_endings(self):
  for arch in ARCHES:
   with self.subTest(arch=arch):
    r=e.validate_cases(events(arch),arch);self.assertEqual(r['cases'],432 if arch in ('arm32','ppc') else 288)
    self.assertEqual(e.validate_cases(events(arch).replace(b'\n',b'\r\n'),arch),r)
 def test_missing_duplicate_malformed_and_argument_corruptions(self):
  for arch in ARCHES:
   original=events(arch);lines=original.splitlines(keepends=True)
   indexes=[];seen=set()
   for i,l in enumerate(lines):
    tag=l.split()[0]
    if tag not in seen:seen.add(tag);indexes.append(i)
   for i in indexes:
    for kind,changed in [('missing',b''),('duplicate',lines[i]*2),('malformed',b'bad '+lines[i])]:
     broken=lines.copy();broken[i]=changed
     with self.subTest(arch=arch,tag=lines[i].split()[0],kind=kind),self.assertRaises(ValueError):e.validate_cases(b''.join(broken),arch)
 def test_temporal_and_snapshot_corruptions(self):
  for arch in ARCHES:
   original=events(arch);lines=original.splitlines(keepends=True)
   def indexes(case,tag):
    key=f'direction=0 variant=0 form=0 restart=0 case={case} '.encode();begin=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_VECTOR_CASE_BEGIN ') and key in l);end=next(i for i in range(begin,len(lines)) if lines[i].startswith(b'PIPE_VECTOR_PARENT_PASS ') and key in lines[i]);return [i for i in range(begin,end) if lines[i].startswith(tag+b' ')]
   for case,tag,before in [(0,b'PIPE_VECTOR_RETRY_RETURN',b'OK_NATIVE_PIPE_READV_COMPLETE'),(1,b'PIPE_VECTOR_MUTATE_VECTOR',b'OK_NATIVE_PIPE_READV_WAIT'),(5,b'PIPE_VECTOR_REPLACE_FD',b'OK_NATIVE_PIPE_READV_WAIT'),(14,b'PIPE_VECTOR_MUTATE_VECTOR',b'PIPE_VECTOR_ATTEMPT'),(17,b'PIPE_VECTOR_NEST_RETURN',b'PIPE_VECTOR_NEST_RETRY'),(23,b'PIPE_VECTOR_HANDLER_EXEC',b'PIPE_VECTOR_HANDLE'),(0,b'PIPE_VECTOR_BUFFER',b'PIPE_VECTOR_RETURN')]:
    i=indexes(case,tag)[0];j=indexes(case,before)[0];broken=lines.copy();record=broken.pop(i);broken.insert(j,record)
    with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):e.validate_cases(b''.join(broken),arch)
   for field,replacement in [(rb'iovcnt=3',b'iovcnt=2'),(rb'bytes=32',b'bytes=31'),(rb'vectors=1:0,',b'vectors=2:1,'),(rb'live=1',b'live=2'),(rb'array=[0-9]+',b'array=1')]:
    index=next(i for i,l in enumerate(lines) if l.startswith(b'OK_NATIVE_PIPE_READV_WAIT '));broken=lines.copy();broken[index]=re.sub(field,replacement,broken[index],count=1)
    with self.subTest(arch=arch,field=field),self.assertRaises(ValueError):e.validate_cases(b''.join(broken),arch)
 def test_full_wrapper(self):
  for arch in ARCHES:
   with self.subTest(arch=arch):self.assertEqual(validate(transcript(arch),arch)['runs'],2)

 def test_large_blocking_progress_and_read_publication(self):
  for arch in ARCHES:
   original=events(arch);lines=original.splitlines(keepends=True);key=b'direction=1 variant=0 form=0 restart=0 case=34 '
   begin=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_VECTOR_CASE_BEGIN ') and key in l);end=next(i for i in range(begin,len(lines)) if lines[i].startswith(b'PIPE_VECTOR_PARENT_PASS '))
   def check(data):return e.validate_cases(data,arch)
   controls=[]
   for tag,field,value in ((b'OK_NATIVE_PIPE_WRITEV_LARGE_WAIT ',b'committed',1),(b'OK_NATIVE_PIPE_WRITEV_LARGE_COMPLETE ',b'committed',1),(b'PIPE_VECTOR_PAYLOAD ',b'bytes',4095)):
    at=next(i for i in range(begin,end) if lines[i].startswith(tag));bad=lines.copy();bad[at]=re.sub(rb'(?<![a-z_])'+field+rb'=[0-9]+',field+b'='+str(value).encode(),bad[at]);controls.append(b''.join(bad))
   # The small namespace must never substitute for a large owned request.
   bad=lines.copy()
   for i in range(begin,end):
    if bad[i].startswith(b'OK_NATIVE_PIPE_WRITEV_LARGE_'):bad[i]=re.sub(rb' committed=[0-9]+',b'',bad[i].replace(b'OK_NATIVE_PIPE_WRITEV_LARGE_',b'OK_NATIVE_PIPE_WRITEV_'))
   controls.append(b''.join(bad))
   at=next(i for i in range(begin,end) if lines[i].startswith(b'PIPE_VECTOR_PAYLOAD_BEGIN '));bad=lines.copy();record=bad.pop(at);target=next(i for i in range(begin,end-1) if bad[i].startswith(b'OK_NATIVE_PIPE_WRITEV_LARGE_COMPLETE ') and b'outcome=ready ' in bad[i]);bad.insert(target+1,record);controls.append(b''.join(bad))
   for data in controls:
    with self.subTest(arch=arch),self.assertRaises(ValueError):check(data)
   # Read completion and serial proof may be delayed until after syscall return.
   bad=lines.copy();proofs=[l for l in bad[begin:end] if l.startswith(b'PIPE_VECTOR_PAYLOAD ')][:2]
   for proof in proofs:bad.remove(proof)
   target=next(i for i in range(begin,len(bad)) if bad[i].startswith(b'PIPE_VECTOR_PAYLOAD '));bad[target:target]=proofs
   with self.subTest(arch=arch,race='proof-after-return'):check(b''.join(bad))

if __name__=='__main__':unittest.main()
