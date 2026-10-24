"""Synthetic semantic child-wait traces; no target instruction execution."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_child_wait_evidence as e
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
from test_native_child_exit_events import completion
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
NUMBERS=(61,114,260,114,95,260,260,4114,5059,114)
INIT=b'OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=1 wait=1 selector=2 output=1073800000 format=status outcome=arm result=-11 live=1\n'

def events(arch):
 base=0x10000000 if arch in ('aarch64','arm32') else 0x40000000;lines=[];rv=arch=='rv32';mips=arch.startswith('mips');maximum=(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64))-1;nr=NUMBERS[ARCHES.index(arch)];usr1,usr2=(16,17) if mips else (10,12);live=1;sequence=0
 for variant in range(2):
  for form in range(1 if variant else 2 if arch in ('arm32','ppc') else 1):
   for restart in range(2):
    for case in range(22):
     if rv and variant and case==3:
      lines.append(f'CHILD_WAIT_CASE_SKIP arch=rv32 variant=1 form=0 restart={restart} case=3 reason=musl-user-status-copy');continue
     sequence+=1;pid=100+sequence*10;child=[pid+1,pid+2 if case in (12,15,16) else 0];tids=[pid+3,pid+4 if case in (14,15) else 0];out=[base+0x10000040,base+0x10001040 if tids[1] else 0];nw=2 if tids[1] else 1;nc=2 if child[1] else 1;any_child=case in (1,15,16);selector=0xffffffff if any_child else child[0];again=bool(1-restart if case==10 else restart);caught=case<=2 or case in (10,11,12,13,17,21);blocked=6<=case<=9;site=0x40002001 if arch in ('x86_64','i386') else base+0x2000+form*64;width=2 if arch in ('x86_64','i386') or arch=='arm32' and form and not variant else 4;resume=site+width
     key=f'arch={arch} variant={variant} form={form} restart={restart} case={case}';fmt='siginfo' if rv else 'status';uid=1001 if rv and not variant else 0
     lines.append(f'CHILD_WAIT_CASE_BEGIN {key} pid={pid} tid0={tids[0]} tid1={tids[1]} child0={child[0]} child1={child[1]} any={int(any_child)} workers={nw} children={nc} output0={out[0]} output1={out[1]} site={site} resume={resume} syscall={nr} siginfo={int(rv)} uid=0')
     def event(tag,value=0,ordinal=0,actor=9):lines.append(f'CHILD_WAIT_{tag} {key} actor={actor} ordinal={ordinal} value={value}')
     def release(j):event('RELEASE',child[j],j)
     if case in (9,16):
      for j in range(nc):release(j)
     if blocked:event('SEND',usr1)
     generation={0:0,1:0,9:0};active={};retired={}
     def arm(actor=0,sel=None,output=None):
      nonlocal live
      generation[actor]+=1;q=generation[actor];sel=selector if sel is None else sel;output=(out[actor]+512 if rv and variant else out[actor]) if output is None else output;tid=pid if actor==9 else tids[actor];active[actor]=dict(pid=pid,tid=tid,request=q,wait=q,selector=sel,output=output);live+=1
      lines.append(f'OK_NATIVE_CHILD_WAIT pid={pid} tid={tid} request={q} wait={q} selector={sel} output={output} format={fmt} outcome=arm result=-11 live={live}')
     def terminal(reason,result,actor=0):
      nonlocal live
      if reason=='complete' and result>0:lines.append(completion(child=result,parent=pid,parent_tid=pid,parent_epoch=sequence,uid=uid,status=42+child.index(result),wait_status=42+child.index(result),notify=0,queued=0).decode())
      r=active.pop(actor);live-=1;retired[actor]=r;lines.append('OK_NATIVE_CHILD_WAIT '+' '.join(f'{k}={v}' for k,v in r.items())+f' format={fmt} outcome={reason} result={result} live={live}')
     def rearm(actor):
      generation[actor]+=1;r=active[actor];r['wait']=generation[actor];lines.append('OK_NATIVE_CHILD_WAIT '+' '.join(f'{k}={v}' for k,v in r.items())+f' format={fmt} outcome=rearm result=-11 live={live}')
     def interrupted(nested=False):
      redo=again and not nested;terminal('interrupted',0 if redo else -4);r=retired[0];pc=(site if redo else resume) if not variant or nested else (base+0x5000)+(0 if redo else width);lines.append('OK_NATIVE_CHILD_SIGNAL '+' '.join(f'{k}={v}' for k,v in r.items() if k not in ('selector','output'))+f' origin={r["request"]+100} signal={usr2 if nested else usr1} outcome={"restart" if redo else "eintr"} pc={pc} selector={r["selector"]} output={r["output"]} live={live}')
     def handler(tag,nested=False,edited=False):
      inspected=caught and not(nested and case==11);pc=base+0x6000
      suffix=''
      if inspected:
       redo=again and not nested;ptr=out[0]+192 if nested else out[0]+512 if rv and variant else out[0];arg0=(1 if nested or not any_child else 0) if rv else child[1] if nested else maximum if any_child else child[0];arg1=(child[1] if nested else 0 if any_child else child[0]) if rv else ptr;arg2=ptr if rv else 0;arg3=4 if rv else 0
       if rv and variant and any_child and not nested:arg1=maximum
       result=77 if edited else (nr if arch in ('x86_64','i386') or mips else arg0) if redo else 4 if mips or arch=='ppc' else maximum-3
       number=77 if edited and (arch in ('x86_64','i386') or mips) else nr if redo or arch not in ('x86_64','i386') and not mips else result
       if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not redo or edited):arg0=result
       if mips:arg3=0 if edited else arg3 if redo else 1
       pc=resume if edited else (site if redo else resume) if not variant or nested else (base+0x5000)+(0 if redo else width)
       suffix=f' number={number} result={result} a0={arg0} a1={arg1} a2={arg2} a3={arg3}'
       if arch=='ppc':suffix+=f' cr={0 if edited else 0x10000000} diagnostic_result={0x123 if edited else 0 if redo else maximum-3} orig_r3={0x234 if edited else maximum if any_child and not nested else child[1] if nested else child[0]}'
       if arch=='arm32':suffix+=f' cpsr={48 if form and not variant else 16}'
      lines.append(f'CHILD_WAIT_{tag} {key} actor=0 pid={pid} tid={tids[0]} depth={2 if nested else 1} inspected={int(inspected)} pc={pc}{suffix}')
     def output(j=0,which=0,ordinal=0):lines.append(f'CHILD_WAIT_OUTPUT {key} actor={j} ordinal={ordinal} child={child[which]} status={(42+which)<<8} uid={uid} bytes={128 if rv and not variant else 4}')
     def returned(value,j=0):event('RETURN',value,actor=j)
     for j in range(nw):
      selected=pid if case==8 else selector;a=[0 if selected==0xffffffff else 1,0 if selected==0xffffffff else selected,out[j],5 if case==7 else 4,0,0] if rv else [maximum if selected==0xffffffff else selected,out[j],int(case==7),0,0,0]
      lines.append(f'CHILD_WAIT_ATTEMPT {key} actor={j} pid={pid} tid={tids[j]} '+' '.join(f'a{i}={v}' for i,v in enumerate(a)))
      if case not in (7,8,9,16):arm(j)
     if caught:
      if case==2:event('MUTATE_OUTPUT')
      if case==10:event('CHANGE_ACTION',int(again))
      event('SEND',usr1);interrupted();handler('HANDLE')
      if case==11:handler('NESTED',True)
      if case==12:
       event('NEST_ATTEMPT',child[1],actor=0);arm(sel=child[1],output=out[0]+192);event('SEND',usr2);interrupted(True);handler('NESTED',True);event('NEST_EINTR',-4,actor=0);arm(sel=child[1],output=out[0]+192);release(1);terminal('complete',child[1]);event('NEST_REAP',child[1],actor=0)
      if case==17:handler('THREAD_EXIT');release(0);event('MAIN_REAP',child[0])
      elif case==21:handler('HANDLER_EXEC')
      else:
       edit=case==13 and not variant and again;handler('HANDLER_RETURN',edited=edit)
       if not again or edit:returned(77 if edit else -1 if variant else -4);event('RETRY',child[0],1,0)
       arm(sel=child[0] if case==1 and not again else None);release(0);terminal('complete',child[0]);
       if again and not edit:returned(0 if rv and not variant else child[0])
       output(ordinal=int(not again or edit))
     elif case==3:
      event('PROTECT_OUTPUT');terminal('complete',-14);release(0);returned(-1 if variant else -14);event('RETRY',child[0],1,0);output(ordinal=1)
     elif case in (18,19,20):
      if case==18:event('SEND',usr1)
      if case==19:event('EXIT_GROUP')
      if case!=20:terminal('cancelled',-125)
     elif case in (14,15):
      release(0);terminal('complete',child[0]);returned(0 if rv and not variant else child[0]);output()
      if case==15:rearm(1);release(1);terminal('complete',child[1],1);returned(0 if rv and not variant else child[1],1);output(1,1)
      else:terminal('complete',-10,1);returned(-1 if variant else -10,1)
     else:
      if case not in (7,8,9,16):
       if case==5:event('SEND',usr1)
       release(0);terminal('complete',child[0])
      returned(0 if case==7 else -1 if variant and case==8 else -10 if case==8 else 0 if rv and not variant else child[0])
      if case not in (7,8):output()
      if case==16:event('RETRY',child[1],1,0);output(0,1,1)
      if blocked:event('PENDING',1,actor=0);event('UNMASK',actor=0);handler('HANDLE');handler('HANDLER_RETURN')
      if case in (7,8):release(0);event('MAIN_REAP',child[0])
     if case in (20,21):
      executor=0 if case==21 else 9;event('EXEC_FAILED',2,actor=executor);event('EXEC_COMMIT',pid,actor=executor)
      if case==20:terminal('cancelled',-125)
      lines.append(IMAGE.decode().strip());event('EXEC_REPLACED',child[0]);event('EXEC_REAP',child[0])
     if case<18:lines.append(f'CHILD_WAIT_CASE_PASS {key}')
     lines.append(f'CHILD_WAIT_PARENT_PASS {key} pid={pid} signal={usr1 if case==18 else 0} descendants={nc}')
     assert not active and live==1
 return ('\n'.join(lines)+'\n').encode()

def fixture(arch):
 marker,_,cmd,leases=e.probe_spec(arch,'child-wait-signals');body=cmd+b'\n'+IMAGE+events(arch)+marker+b'\n'
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts

def validate(parts,arch):
 ends=[sum(map(len,parts[:i])) for i in range(1,5)];return e.validate_execution(b''.join(parts),*ends,ends[-1],arch)

class ChildWaitEvidence(unittest.TestCase):
 def test_reentry_preserves_restart_selector_but_explicit_retry_selects_child(self):
  for arch in ARCHES:
   original=fixture(arch)
   for restart in (0,1):
    lines=original[2].splitlines(keepends=True)
    start=next(i for i,l in enumerate(lines) if l.startswith(b'CHILD_WAIT_CASE_BEGIN ') and f'variant=0 form=0 restart={restart} case=1 '.encode() in l)
    end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'CHILD_WAIT_PARENT_PASS '))
    child=re.search(rb'child0=([0-9]+)',lines[start])[1]
    arm=[i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_CHILD_WAIT ') and b'outcome=arm ' in lines[i]][1]
    before=b'selector='+ (child if restart==0 else b'4294967295')
    after=b'selector='+ (b'4294967295' if restart==0 else child)
    for i in range(arm,end):
     if lines[i].startswith(b'OK_NATIVE_CHILD_WAIT '):lines[i]=lines[i].replace(before,after)
    parts=original.copy();parts[2]=b''.join(lines)
    with self.subTest(arch=arch,restart=restart),self.assertRaises(ValueError):validate(parts,arch)
 def test_output_fault_interval_and_successful_reap_release_order(self):
  for arch in ARCHES:
   original=fixture(arch)
   for case in (3,4):
    lines=original[2].splitlines(keepends=True)
    start=next(i for i,l in enumerate(lines) if l.startswith(b'CHILD_WAIT_CASE_BEGIN ') and f'variant=0 form=0 restart=0 case={case} '.encode() in l)
    end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'CHILD_WAIT_PARENT_PASS '))
    complete=next(i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_CHILD_WAIT ') and b'outcome=complete ' in lines[i]);record=lines.pop(complete)
    # Early EFAULT is valid; success must still follow release. EFAULT cannot
    # precede the protection action or follow its userspace error return.
    for tag,after in ((b'CHILD_WAIT_PROTECT_OUTPUT ',False),(b'CHILD_WAIT_RETURN ',True)) if case==3 else ((b'CHILD_WAIT_RELEASE ',False),):
     changed=lines.copy();target=next(i for i in range(start,end-1) if changed[i].startswith(tag));changed.insert(target+int(after),record)
     parts=original.copy();parts[2]=b''.join(changed)
     with self.subTest(arch=arch,case=case,tag=tag),self.assertRaises(ValueError):validate(parts,arch)
    if case==3:
     changed=lines.copy();target=next(i for i in range(start,end-1) if changed[i].startswith(b'CHILD_WAIT_RELEASE '));changed.insert(target+1,record)
     parts=original.copy();parts[2]=b''.join(changed);validate(parts,arch)
 def test_rv32_musl_ignored_id_is_still_exact_saved_state(self):
  original=fixture('rv32');lines=original[2].splitlines(keepends=True)
  for variant,old,new in ((0,b'a1=0 ',b'a1=4294967295 '),(1,b'a1=4294967295 ',b'a1=0 ')):
   changed=lines.copy();count=0
   for i,line in enumerate(changed):
    if line.startswith((b'CHILD_WAIT_HANDLE ',b'CHILD_WAIT_HANDLER_RETURN ')) and f'variant={variant} form=0 restart=0 case=1 '.encode() in line:
     self.assertIn(old,line);changed[i]=line.replace(old,new);count+=1
   self.assertEqual(count,2);parts=original.copy();parts[2]=b''.join(changed)
   with self.assertRaises(ValueError):validate(parts,'rv32')
 def test_exact_scenario_lease_lower_bound(self):
  for arch in ARCHES:
   expected=279 if arch=='rv32' else 427 if arch in ('arm32','ppc') else 285
   self.assertEqual(e.probe_spec(arch,'child-wait-signals')[3],expected)
 def test_arm_nested_raw_mode_and_unchanged_libc_outer_context(self):
  original=fixture('arm32')
  for restart in (0,1):
   for tag,case in ((b'CHILD_WAIT_NESTED ',12),(b'CHILD_WAIT_HANDLE ',0)):
    lines=original[2].splitlines(keepends=True)
    i=next(i for i,l in enumerate(lines) if l.startswith(tag) and f'variant=1 form=0 restart={restart} case={case} '.encode() in l)
    self.assertIn(b'cpsr=16',lines[i]);lines[i]=lines[i].replace(b'cpsr=16',b'cpsr=48')
    parts=original.copy();parts[2]=b''.join(lines)
    with self.subTest(restart=restart,tag=tag),self.assertRaises(ValueError):validate(parts,'arm32')
 def test_fresh_and_nested_waits_cannot_precede_their_userspace_call(self):
  for arch in ARCHES:
   original=fixture(arch)
   for case,ordinal,target_tag,move_tag in ((0,1,b'CHILD_WAIT_HANDLER_RETURN ',b'arm'),(0,1,b'CHILD_WAIT_RETRY ',b'arm'),(12,1,b'CHILD_WAIT_NEST_ATTEMPT ',b'arm'),(12,2,b'CHILD_WAIT_NEST_EINTR ',b'arm'),(12,2,b'OK_NATIVE_CHILD_WAIT ',b'nested-reap')):
    lines=original[2].splitlines(keepends=True)
    start=next(i for i,l in enumerate(lines) if l.startswith(b'CHILD_WAIT_CASE_BEGIN ') and f'variant=0 form=0 restart=0 case={case} '.encode() in l)
    end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'CHILD_WAIT_PARENT_PASS '))
    arms=[i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_CHILD_WAIT ') and b'outcome=arm ' in lines[i]]
    if move_tag==b'arm':
     moved=arms[ordinal];target=next(i for i in range(start,end) if lines[i].startswith(target_tag))
    else:
     moved=next(i for i in range(start,end) if lines[i].startswith(b'CHILD_WAIT_NEST_REAP '));target=arms[ordinal]
    record=lines.pop(moved);lines.insert(target-int(moved<target),record)
    parts=original.copy();parts[2]=b''.join(lines)
    with self.subTest(arch=arch,case=case,ordinal=ordinal,target=target_tag),self.assertRaises(ValueError):validate(parts,arch)
 def test_all_profiles_and_odd_x86_raw_pc(self):
  for arch in ARCHES:
   for newline in (b'\n',b'\r\n'):
    with self.subTest(arch=arch,newline=newline):
     r=validate([p.replace(b'\n',newline) for p in fixture(arch)],arch);groups=6 if arch in ('arm32','ppc') else 4
     for row in r['observations']:
      self.assertEqual(row['cases'],22*groups-(2 if arch=='rv32' else 0));self.assertEqual(row['skipped_libc_output_faults'],2 if arch=='rv32' else 0);self.assertEqual(row['exec_replacements'],2*groups);self.assertEqual(row['rearms'],groups)
     self.assertEqual(r['baseline']['objects'],1)
 def test_missing_duplicate_and_malformed_records(self):
  for arch in ARCHES:
   original=fixture(arch);span=original[2]
   for pattern in e.PATTERNS:
    if pattern is e.SKIP and arch!='rv32':continue
    line=next(l for l in span.splitlines(keepends=True) if pattern.fullmatch(l.rstrip(b'\n')))
    for replacement in (b'',line+line,b'garbage '+line):
     parts=original.copy();parts[2]=span.replace(line,replacement,1)
     with self.subTest(arch=arch,tag=line.split()[0]),self.assertRaises(ValueError):validate(parts,arch)
 def test_masks_abi_and_copied_child_fields(self):
  for arch in ARCHES:
   original=fixture(arch);span=original[2]
   for prefix,fields in ((b'CHILD_WAIT_CASE_BEGIN',(b'pid',b'tid0',b'child0',b'output0',b'syscall')),(b'CHILD_WAIT_ATTEMPT',(b'a0',b'a1',b'a2',b'a3',b'a4',b'a5')),(b'CHILD_WAIT_HANDLE',(b'pc',b'result',b'number',b'a0',b'a1',b'a2',b'a3')),(b'CHILD_WAIT_OUTPUT',(b'child',b'status',b'uid',b'bytes')),(b'CHILD_WAIT_PARENT_PASS',(b'pid',b'signal',b'descendants'))):
    line=next(l for l in span.splitlines(keepends=True) if l.startswith(prefix+b' '))
    for field in fields:
     parts=original.copy();parts[2]=span.replace(line,re.sub(rb'(?<![a-z0-9_])'+field+rb'=[0-9]+',field+b'=999',line),1)
     with self.subTest(arch=arch,prefix=prefix,field=field),self.assertRaises(ValueError):validate(parts,arch)
 def test_owned_retirement_restart_rearm_and_exec(self):
  for arch in ARCHES:
   original=fixture(arch);span=original[2]
   for prefix in (b'OK_NATIVE_CHILD_WAIT',b'OK_NATIVE_CHILD_SIGNAL'):
    line=next(l for l in span.splitlines(keepends=True) if l.startswith(prefix+b' '))
    for field in (b'pid',b'tid',b'request',b'wait',b'selector',b'output',b'live'):
     parts=original.copy();parts[2]=span.replace(line,re.sub(field+rb'=[0-9]+',field+b'=999',line),1)
     with self.subTest(arch=arch,field=field),self.assertRaises(ValueError):validate(parts,arch)
   for tag in (b'CHILD_WAIT_NESTED',b'CHILD_WAIT_THREAD_EXIT',b'CHILD_WAIT_HANDLER_EXEC',b'CHILD_WAIT_EXEC_REPLACED',b'CHILD_WAIT_EXEC_REAP'):
    line=next(l for l in span.splitlines(keepends=True) if l.startswith(tag+b' '));parts=original.copy();parts[2]=span.replace(line,b'',1)
    with self.assertRaises(ValueError):validate(parts,arch)
 def test_resource_and_boot_baseline_are_owned(self):
  original=fixture('x86_64')
  for i in (0,2,3,4):
   for prefix in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
    line=next(l for l in original[i].splitlines(keepends=True) if l.startswith(prefix));parts=original.copy();parts[i]=parts[i].replace(line,line+line,1)
    with self.assertRaises(ValueError):validate(parts,'x86_64')
  parts=original.copy();parts[0]=parts[0].replace(INIT,b'')
  with self.assertRaises(ValueError):validate(parts,'x86_64')
  parts=original.copy();parts[2]=parts[2].replace(b'objects=1',b'objects=2')
  with self.assertRaises(ValueError):validate(parts,'x86_64')

if __name__=='__main__':unittest.main()
