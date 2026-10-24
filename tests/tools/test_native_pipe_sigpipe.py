"""Synthetic SIGPIPE contract controls; no native or hardware execution."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_sigpipe_evidence as e
from native_pipe_vector_events import ARCHES,WRITEV
from native_pipe_write_events import WRITE
from pipe_sigpipe_guest_protocol import combinations
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
from test_native_pipe_vector import INIT

def events(arch):
 lines=[];base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000
 for sequence,k in enumerate(combinations(arch)):
  v,variant,form,restart,resumed,c=k;pid=100+10*sequence;tid=pid+1;sibling=pid+2;blocked=resumed and c<10;deferred=3<=c<=8;fatal=c in (0,4);usr=16 if arch.startswith('mips') else 10;op=(WRITEV if v else WRITE)[arch]
  key=f'arch={arch} vector={v} variant={variant} form={form} restart={restart} resumed={resumed} case={c}'
  payload0=base+0x1000040;payload1=payload0+8192;buf=base+0x1008000 if v else payload0;fd=-1 if c==11 else 4;rd=3 if blocked or c>=12 else -1;count=3 if v else 0 if c==10 else 13;site=base+0x2000+form*64;width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4;resume=site+width
  lines.append(f'PIPE_SIGPIPE_CASE_BEGIN {key} pid={pid} tid={tid} sibling={sibling} uid=1000 fd={fd} readfd={rd} input={buf} bytes={count} payload0={payload0} payload1={payload1} site={site} resume={resume} syscall={op} capacity=4096')
  def event(tag,actor,ordinal,value):lines.append(f'PIPE_SIGPIPE_{tag} {key} actor={actor} ordinal={ordinal} value={value}')
  def handler(signal):
   inspected=signal==13 and not deferred;pc=resume if inspected and not variant else base+0x5000;abi=1 if arch.startswith('mips') else 0x10000000 if arch=='ppc' else 16|(32 if form else 0) if arch=='arm32' else 0
   lines.append(f'PIPE_SIGPIPE_HANDLE {key} actor=0 pid={pid} tid={tid} signal={signal} code={-6 if c==7 or signal==usr else 0} sender={pid} uid=1000 inspected={int(inspected)} pc={pc} result={-32 if inspected else 0} a1={buf if inspected else 0} a2={count if inspected else 0} abi={abi}')
   if c==9:event('EDIT',0,0,77)
   event('HANDLER_RETURN',0,0,signal)
  if c in (7,8):event('QUEUE',0,0,13 if c==7 else usr);event('PENDING',0,0,1 if c==7 else 2)
  event('ATTEMPT',0,0,op)
  if blocked:
   prefix='OK_NATIVE_PIPE_WRITE'+('V' if v else '')+'_';field='array' if v else 'input';shape=f' iovcnt=3 vectors=1:0,{payload0}:13,{payload1}:19' if v else '';identity=f'pid={pid} tid={tid} wait=1 request=1 {field}={buf} fd={fd} description=5 pipe=0 bytes={32 if v else 13}'+shape
   lines.append(prefix+'WAIT '+identity+' stage=arm live=1');lines.append(prefix+f'ORIGIN pid={pid} tid={tid} request=1 wait=1 origin=1 pc={resume if not variant else base+0x5000} syscall={op} fd={fd} {field}={buf} bytes={32 if v else 13}'+shape)
   event('CLOSE',9,0,rd);lines.append(prefix+'COMPLETE '+identity+' result=-32 outcome=error pinned=0 live=0')
  if c in (1,9):handler(13)
  if c!=0:
   code=9 if c==11 else 14 if c==12 else 11 if c==13 else 32;result=77 if c==9 else 0 if c==10 else -1 if variant else -code
   event('RETURN',0,0,result);event('ERRNO',0,0,code if variant and result==-1 else 111)
   if c==6:event('ATTEMPT',0,1,op);event('RETURN',0,1,-1 if variant else -32);event('ERRNO',0,1,32 if variant else 111)
   event('PENDING',0,0,1+2*(c==8) if deferred else 0);event('PENDING',1,0,0);event('SIBLING',1,0,sibling)
   if deferred:
    if c==5:event('ACTION_CAUGHT',0,0,13)
    event('UNMASK',0,0,13)
    if c!=4:
     handler(13);event('PENDING',0,0,2 if c==8 else 0)
     if c==8:event('UNMASK',0,1,usr);handler(usr);event('PENDING',0,0,0)
   if not fatal:
    event('WORKER_PASS',0,0,3 if c==8 else int(c in (1,3,5,6,7,9)));event('BUFFER',9,0,16384)
    if c==13:event('FILL',9,0,4096)
    if c>=12:event('EMPTY',9,0,0)
    lines.append(f'PIPE_SIGPIPE_CASE_PASS {key}')
  lines.append(f'PIPE_SIGPIPE_PARENT_PASS {key} pid={pid} signal={13 if fatal else 0}')
 lines.append(e.probe_spec(arch,'pipe-sigpipe-signals')[0].decode());return ('\n'.join(lines)+'\n').encode()

def transcript(arch):
 _,_,command,leases=e.probe_spec(arch,'pipe-sigpipe-signals');body=command+b'\n'+IMAGE+b'\n'+events(arch)
 if arch in ('loongarch64','mips','mips64'):body=body.replace(b'source=firmware',b'source=linker')
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts
def validate(parts,arch):
 bounds=[];offset=0
 for part in parts[:-1]:offset+=len(part);bounds.append(offset)
 return e.validate_execution(b''.join(parts),*bounds,bounds[-1],arch)

class SigpipeGuestTests(unittest.TestCase):
 def test_allten_and_crlf(self):
  for arch in ARCHES:
   raw=events(arch);r=e.validate_cases(raw,arch);self.assertEqual(r,e.validate_cases(raw.replace(b'\n',b'\r\n'),arch));self.assertEqual(r['cases'],336 if arch in ('arm32','ppc') else 224);self.assertEqual(r['owned_waits'],120 if arch in ('arm32','ppc') else 80)
 def test_full_wrapper(self):
  for arch in ARCHES:
   parts=transcript(arch);r=validate(parts,arch);self.assertEqual(r['runs'],2);self.assertTrue(r['automatic_sigpipe']);self.assertEqual(r['image_publications_per_run'],1)
 def test_record_removal_duplication(self):
  for arch in ARCHES:
   raw=events(arch);lines=raw.splitlines(keepends=True)
   for prefix in (b'PIPE_SIGPIPE_HANDLE ',b'PIPE_SIGPIPE_SIBLING ',b'PIPE_SIGPIPE_BUFFER ',b'PIPE_SIGPIPE_UNMASK ',b'PIPE_SIGPIPE_PARENT_PASS ',b'OK_NATIVE_PIPE_WRITE_COMPLETE '):
    line=next(x for x in lines if x.startswith(prefix))
    for replacement in (b'',line+line):
     with self.assertRaises(ValueError):e.validate_cases(raw.replace(line,replacement,1),arch)
 def test_payload_context_and_ownership_controls(self):
  for arch in ARCHES:
   raw=events(arch);lines=raw.splitlines(keepends=True)
   targets=[(b'PIPE_SIGPIPE_HANDLE ',b'code=0 ',b'code=-6 '),(b'PIPE_SIGPIPE_HANDLE ',b'result=-32 ',b'result=-4 '),(b'PIPE_SIGPIPE_HANDLE ',b'actor=0 ',b'actor=1 '),(b'PIPE_SIGPIPE_PARENT_PASS ',b'signal=13',b'signal=0'),(b'OK_NATIVE_PIPE_WRITE_COMPLETE ',b'pinned=0',b'pinned=1'),(b'OK_NATIVE_PIPE_WRITE_COMPLETE ',b'result=-32',b'result=-4'),(b'PIPE_SIGPIPE_PENDING ',b'value=1',b'value=0')]
   for prefix,before,after in targets:
    line=next(x for x in lines if x.startswith(prefix) and before in x)
    with self.assertRaises(ValueError):e.validate_cases(raw.replace(line,line.replace(before,after,1),1),arch)
   begin=next(i for i,x in enumerate(lines) if b'resumed=1 case=1 ' in x and x.startswith(b'PIPE_SIGPIPE_CASE_BEGIN '));close=next(i for i in range(begin,len(lines)) if lines[i].startswith(b'PIPE_SIGPIPE_CLOSE '));terminal=next(i for i in range(close,len(lines)) if lines[i].startswith(b'OK_NATIVE_PIPE_WRITE_COMPLETE '));changed=lines.copy();row=changed.pop(terminal);changed.insert(close,row)
   with self.assertRaises(ValueError):e.validate_cases(b''.join(changed),arch)
 def test_qualifier_layout(self):
  from qualify_native_pipe_sigpipe import probe_layout
  for arch in ARCHES:self.assertEqual(probe_layout(arch,'pipe-sigpipe-signals')[0],'native_pipe_sigpipe')
if __name__=='__main__':unittest.main()
