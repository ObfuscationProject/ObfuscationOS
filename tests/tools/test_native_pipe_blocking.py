"""Synthetic complete-write schedules and rejection controls; not native execution."""
from functools import lru_cache
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_blocking_evidence as e
from native_pipe_vector_events import ARCHES,WRITEV,native_events
from native_pipe_write_events import WRITE
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
from test_native_pipe_vector import INIT

@lru_cache(None)
def digest(offset,count,stream,case,fill):
 value=5381
 for i in range(offset,offset+count):
  byte=241 if fill else (i*17+(i//4096)*53+31+stream*97)&255
  if not fill and case==11 and i>=4096:byte^=90
  value=((value*33)^byte)&0xffffffff
 return value

def cases(arch):
 for v in (0,1):
  for variant in (0,1):
   for form in range(2 if arch in ('arm32','ppc') and not variant else 1):
    for restart in (0,1):
     for case in range(26):yield v,variant,form,restart,case

@lru_cache(None)
def events(arch):
 lines=[];base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000
 for sequence,(v,variant,form,restart,c) in enumerate(cases(arch)):
  pid=100+10*sequence;usr=16 if arch.startswith('mips') else 10;op=(WRITEV if v else WRITE)[arch];count=12289 if c==1 else 8193 if c==2 else 4096 if c==21 else 0 if c==24 else 12288
  key=f'arch={arch} vector={v} variant={variant} form={form} restart={restart} case={c}'
  site=base+0x2000+form*64;resume=site+(2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4);pc=base+0x5000 if variant else resume
  streams=2 if c==25 else 1;writers=[];live=set()
  lines.append(f'PIPE_BLOCKING_CASE_BEGIN {key} pid={pid} uid=1000 streams={streams} count={count} site={site} resume={resume} syscall={op} capacity=4096')
  for stream in range(streams):
   payload=base+0x1001000+stream*0x20000;buf=payload+36864 if v else payload;fd=4+stream*8;rd=-1 if c==24 else fd-1;saved=fd+1 if c in (12,13,14,15) else -1;replacement=fd+3 if c in (12,15) else -1;rr=fd+2 if c in (12,15) else -1
   w=dict(stream=stream,tid=pid+stream+1,fd=fd,readfd=rd,saved=saved,replacement=replacement,replacementread=rr,input=buf,argcount=5 if v else count,offset=0,ordinal=0,cursor=0,wait=0,request=0,origin=0)
   w.update({f'payload{i}':payload+i*(8192 if v else 4096) for i in range(4)});writers.append(w)
   lines.append(f'PIPE_BLOCKING_WRITER {key} '+' '.join(f'{n}={w[n]}' for n in ('stream','tid','fd','readfd','saved','replacement','replacementread','input','payload0','payload1','payload2','payload3','argcount')))
  def guest(tag,stream=0,ordinal=0,value=0,actor=9):lines.append(f'PIPE_BLOCKING_{tag} {key} actor={actor} stream={stream} ordinal={ordinal} value={value}')
  def diagnostic(tag,w,**kwargs):
   prefix='OK_NATIVE_PIPE_WRITE'+('V' if v else '')+('_LARGE_' if count>4096 else '_');field='array' if v else 'input';shape=' iovcnt=5 vectors=1:0,'+','.join(f'{w[f"payload{i}"]}:{max(0,min(4096,count-4096*i))}' for i in range(4)) if v else '';cursor=f' committed={w["cursor"]}' if count>4096 else ''
   if tag in ('WAIT','COMPLETE'):
    text=f'pid={pid} tid={w["tid"]} wait={w["wait"]} request={w["request"]} {field}={w["input"]} fd={w["fd"]} description={5+w["stream"]} pipe={w["stream"]} bytes={count}'+shape+cursor
   else:
    text=f'pid={pid} tid={w["tid"]} request={w["request"]} wait={w["wait"]} origin={w["origin"]}'
    if tag=='SIGNAL':text+=f' signal={usr} outcome={kwargs.pop("outcome")}'
    text+=f' pc={kwargs.pop("pc",pc)} syscall={op} fd={w["fd"]} {field}={w["input"]} bytes={count}'+shape+cursor
   lines.append(prefix+tag+' '+text+''.join(f' {n}={value}' for n,value in kwargs.items()))
  def arm(w,cursor):
   w['wait']+=1;w['request']=w['wait'];w['origin']+=1;w['cursor']=cursor;live.add(w['stream']);diagnostic('WAIT',w,stage='arm',live=len(live));diagnostic('ORIGIN',w)
  def rearm(w,cursor):w.update(wait=w['wait']+1,cursor=cursor);diagnostic('WAIT',w,stage='rearm',live=len(live))
  def complete(w,cursor,result,cause='ready',signal=None):
   w['cursor']=cursor;live.remove(w['stream']);diagnostic('COMPLETE',w,result=result,outcome=cause,pinned=0,live=len(live))
   if signal:diagnostic('SIGNAL',w,outcome=signal,pc=pc-(resume-site) if signal=='restart' else pc,pinned=0,live=len(live))
  def read(w,n,fill=False,publish=True):
   fields=f'actor=9 stream={w["stream"]} ordinal={w["ordinal"]} fill={int(fill)} offset={w["offset"]} bytes={n}'
   lines.append(f'PIPE_BLOCKING_READ_BEGIN {key} '+fields)
   if publish and w['stream'] in live:
    if c==8:complete(w,w['cursor'],w['cursor'],'efault')
    elif c==21:
     if n==1:rearm(w,0)
     else:complete(w,0,4096)
    elif c in (13,14):complete(w,w['cursor']+4096,w['cursor']+4096)
    else:
     cursor=min(count,w['cursor']+n)
     if cursor==count:complete(w,cursor,count)
     else:rearm(w,cursor)
   lines.append(f'PIPE_BLOCKING_BYTES {key} '+fields+f' checksum={digest(w["offset"],n,w["stream"],c,fill)}')
   w['ordinal']+=1
   if not fill:w['offset']+=n
  def await_(w,phase):guest('AWAIT',w['stream'],phase,w['cursor'])
  def finish(w):
   while w['offset']<count:
    read(w,min(4096,count-w['offset']))
    if w['offset']+4096<count:await_(w,10+w['offset']//4096)
  def handle(result,again=False):
   w=writers[0];signal=13 if c in (6,7) else usr;abi=(int(result<0) if arch.startswith('mips') else 0x10000000 if arch=='ppc' and result<0 else 16|(32 if form else 0) if arch=='arm32' else 0)
   lines.append(f'PIPE_BLOCKING_HANDLE {key} actor=0 stream=0 pid={pid} tid={w["tid"]} signal={signal} code={0 if signal==13 else -6} sender={pid} uid=1000 again={int(again)} pc={pc-(resume-site) if again else pc} result={result} number={op} a0={w["fd"]} a1={w["input"]} a2={w["argcount"]} a3=4951 abi={abi}')
   guest('THREAD_EXIT' if c==17 else 'HANDLER_RETURN',value=4096 if c==17 else signal,actor=0)
  full=c in (1,3,7,12,14,15,21,23)
  for w in writers:
   guest('ATTEMPT',w['stream'],value=op,actor=w['stream'])
   if c<22 or c==25:arm(w,0 if full else 4096)
  w=writers[0]
  if c<22 or c==25:await_(w,0)
  if c==25:
   await_(writers[1],0);read(w,4096);await_(w,1);read(writers[1],4096);await_(writers[1],1);finish(w);finish(writers[1])
  elif c==2:read(w,4096);await_(w,1);read(w,1);read(w,4096)
  elif c==3:
   guest('SEND',value=usr);complete(w,0,0 if restart else -4,'interrupted','restart' if restart else 'eintr');handle(0 if restart else -4,bool(restart))
   if not restart:guest('RETURN',value=-1 if variant else -4,actor=0);guest('ERRNO',value=4 if variant else 111,actor=0);guest('RETRY',ordinal=1,value=op,actor=0)
   arm(w,0);await_(w,1);read(w,4096,True);await_(w,2);finish(w)
  elif c in (4,5,6,7,17,18,19,20):
   if c in (5,6,18,19,20):read(w,4096);await_(w,1)
   if c in (6,7):guest('CLOSE',value=w['readfd']);complete(w,w['cursor'],8192 if c==6 else -32,'error');handle(8192 if c==6 else -32)
   elif c==18:guest('BUFFER',value=65536);guest('EXIT_GROUP',value=8192);complete(w,8192,-125,'cancelled')
   elif c==19:
    guest('BUFFER',value=65536);guest('EXEC_FAILED',value=2);guest('EXEC_COMMIT',value=pid);complete(w,8192,-125,'cancelled');lines.append(IMAGE.decode().strip());guest('EXEC_REPLACED',value=pid);read(w,4096);guest('EMPTY',value=w['readfd']);guest('EXEC_BYTE',value=69);guest('EMPTY',value=w['readfd']);guest('EXEC_CHECKED',value=pid)
   elif c==20:guest('SEND',value=usr);complete(w,8192,-125,'cancelled')
   else:guest('SEND',value=usr);complete(w,w['cursor'],w['cursor'],'interrupted','partial');handle(w['cursor'])
  elif c==8:guest('PROTECT_SUFFIX',value=4096);read(w,4096);guest('RESTORE_SUFFIX',value=4096)
  elif c==9:guest('MUTATE_METADATA',value=1);finish(w)
  elif c==10:guest('PROTECT_PREFIX',value=4096);finish(w);guest('RESTORE_PREFIX',value=4096)
  elif c==11:guest('MUTATE_PAYLOAD',value=4096);finish(w)
  elif c in (12,15):
   guest('REPLACE_FD',value=w['replacement'])
   if c==15:guest('NONBLOCK_REPLACEMENT',value=w['fd'])
   read(w,4096,True);await_(w,1);finish(w)
  elif c in (13,14):guest('NONBLOCK_SHARED',value=w['saved']);read(w,4096,c==14)
  elif c==16:guest('SEND',value=usr);guest('IGNORED',value=1);finish(w)
  elif c==21:read(w,1,True);await_(w,1);guest('ATOMIC_PENDING',value=1);read(w,4095,True);read(w,4096)
  elif c in (0,1):
   if full:read(w,4096,True);await_(w,1)
   finish(w)
  if c in (4,5,13,14,17,22):read(w,4096)
  if c==23:read(w,4096,True)
  if c not in (18,19,20):
   for w in writers:
    if c!=17:
     value=4096 if c in (4,8,14,22) else 8192 if c in (5,6,13) else (-1 if variant else -32) if c==7 else (-1 if variant else -11) if c==23 else count;err=32 if c==7 else 11 if c==23 else 0
     guest('RETURN',w['stream'],int(c==3 and not restart),value,w['stream']);guest('ERRNO',w['stream'],int(c==3 and not restart),err if variant and value==-1 else 111,w['stream']);guest('WORKER_PASS',w['stream'],value=value,actor=w['stream'])
    guest('BUFFER',w['stream'],value=65536)
    if c not in (6,7,24):guest('EMPTY',w['stream'],value=w['readfd'])
    if c in (12,15):guest('EMPTY',2,value=w['replacementread']);guest('REPLACEMENT_BYTE',w['stream'],value=82)
   lines.append(f'PIPE_BLOCKING_CASE_PASS {key}')
  lines.append(f'PIPE_BLOCKING_PARENT_PASS {key} pid={pid} signal={usr if c==20 else 0}')
 lines.append(e.probe_spec(arch,'pipe-blocking-writes')[0].decode());return ('\n'.join(lines)+'\n').encode()

def transcript(arch):
 _,_,command,leases=e.probe_spec(arch,'pipe-blocking-writes');body=command+b'\n'+IMAGE+events(arch)
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts

def validate(parts,arch):
 bounds=[];offset=0
 for part in parts[:-1]:offset+=len(part);bounds.append(offset)
 return e.validate_execution(b''.join(parts),*bounds,bounds[-1],arch)

class BlockingGuestTests(unittest.TestCase):
 def test_allten_and_crlf(self):
  for arch in ARCHES:
   raw=events(arch);r=e.validate_cases(raw,arch);self.assertEqual(r,e.validate_cases(raw.replace(b'\n',b'\r\n'),arch));self.assertEqual(r['cases'],312 if arch in ('arm32','ppc') else 208);self.assertEqual(r['groups'],12 if arch in ('arm32','ppc') else 8)
 def test_full_wrapper(self):
  for arch in ARCHES:
   r=validate(transcript(arch),arch);self.assertEqual(r['runs'],2);self.assertTrue(r['full_blocking_large_write']);self.assertEqual(r['image_publications_per_run'],13 if arch in ('arm32','ppc') else 9)
 def test_record_cardinality_controls(self):
  prefixes=('CASE_BEGIN','WRITER','ATTEMPT','HANDLE','HANDLER_RETURN','THREAD_EXIT','READ_BEGIN','BYTES','BUFFER','EMPTY','AWAIT','SEND','CLOSE','RETURN','ERRNO','RETRY','WORKER_PASS','PROTECT_SUFFIX','RESTORE_SUFFIX','MUTATE_METADATA','PROTECT_PREFIX','RESTORE_PREFIX','MUTATE_PAYLOAD','REPLACE_FD','NONBLOCK_REPLACEMENT','NONBLOCK_SHARED','IGNORED','ATOMIC_PENDING','REPLACEMENT_BYTE','EXIT_GROUP','EXEC_FAILED','EXEC_COMMIT','EXEC_REPLACED','EXEC_BYTE','EXEC_CHECKED','CASE_PASS','PARENT_PASS','PASS')
  for arch in ARCHES:
   raw=events(arch);lines=raw.splitlines(keepends=True)
   for tag in prefixes:
    line=next(x for x in lines if x.startswith(('PIPE_BLOCKING_'+tag+' ').encode()))
    for replacement in (b'',line+line):
     with self.subTest(arch=arch,tag=tag,duplicate=bool(replacement)),self.assertRaises(ValueError):e.validate_cases(raw.replace(line,replacement,1),arch)
 def test_large_ledger_and_payload_mutations(self):
  mutations=[('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'fd=4 ',b'fd=32 '),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'description=5 ',b'description=256 '),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'pipe=0 ',b'pipe=16 '),('OK_NATIVE_PIPE_WRITE_LARGE_ORIGIN ',b'committed=4096',b'committed=0'),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'committed=8192',b'committed=4095'),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'committed=8192',b'committed=12287'),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'committed=8192',b'committed=12288'),('OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'result=12288',b'result=8192'),('OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'pinned=0',b'pinned=1'),('OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'description=5',b'description=6'),('OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'description=5',b'description=65535'),('OK_NATIVE_PIPE_WRITE_LARGE_SIGNAL ',b'outcome=partial',b'outcome=restart'),('OK_NATIVE_PIPE_WRITE_LARGE_SIGNAL ',b'committed=4096',b'committed=0'),('OK_NATIVE_PIPE_WRITEV_LARGE_WAIT ',b'1:0,',b'1:1,'),('OK_NATIVE_PIPE_WRITEV_LARGE_WAIT ',b'committed=8192',b'committed=4096'),('PIPE_BLOCKING_BYTES ',b'bytes=4096',b'bytes=4095'),('PIPE_BLOCKING_BYTES ',b'checksum=',b'checksum=9'),('PIPE_BLOCKING_HANDLE ',b'result=4096',b'result=0'),('PIPE_BLOCKING_HANDLE ',b'again=0',b'again=1'),('PIPE_BLOCKING_WRITER ',b'payload1=',b'payload1=9'),('PIPE_BLOCKING_WRITER ',b'saved=-1',b'saved=4'),('PIPE_BLOCKING_PARENT_PASS ',b'signal=0',b'signal=13'),('PIPE_BLOCKING_BUFFER ',b'value=65536',b'value=65535')]
  for arch in ARCHES:
   raw=events(arch);lines=raw.splitlines(keepends=True)
   for prefix,before,after in mutations:
    line=next(x for x in lines if x.startswith(prefix.encode()) and before in x)
    with self.subTest(arch=arch,prefix=prefix,before=before),self.assertRaises(ValueError):e.validate_cases(raw.replace(line,line.replace(before,after,1),1),arch)
 def test_causal_controls(self):
  for arch in ARCHES:
   raw=events(arch);original=raw.splitlines(keepends=True)
   def case_rows(c):
    start=next(i for i,x in enumerate(original) if x.startswith(b'PIPE_BLOCKING_CASE_BEGIN ') and f' case={c} '.encode() in x)
    end=next(i for i in range(start,len(original)) if original[i].startswith(b'PIPE_BLOCKING_PARENT_PASS '));return start,end
   def moved(c,tag,before,pair=False):
    start,end=case_rows(c);lines=original.copy();at=next(i for i in range(start,end) if lines[i].startswith(tag));target=next(i for i in range(start,end) if lines[i].startswith(before));items=lines[at:at+1+int(pair)];del lines[at:at+len(items)];target=lines.index(original[target]);lines[target:target]=items;return b''.join(lines)
   for c,tag,before,pair in [(0,b'OK_NATIVE_PIPE_WRITE_LARGE_WAIT ',b'PIPE_BLOCKING_ATTEMPT ',True),(4,b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'PIPE_BLOCKING_SEND ',True),(8,b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'PIPE_BLOCKING_PROTECT_SUFFIX ',False),(18,b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'PIPE_BLOCKING_EXIT_GROUP ',False),(19,b'OK_NATIVE_IMAGE ',b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',False),(20,b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE ',b'PIPE_BLOCKING_SEND ',False),(0,b'PIPE_BLOCKING_BUFFER ',b'PIPE_BLOCKING_WORKER_PASS ',False)]:
    with self.subTest(arch=arch,case=c,tag=tag),self.assertRaises(ValueError):e.validate_cases(moved(c,tag,before,pair),arch)
   start,end=case_rows(0);lines=original.copy();terminal=next(i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE '));read=next(i for i in range(start,end) if lines[i].startswith(b'PIPE_BLOCKING_READ_BEGIN ') and b'offset=4096' in lines[i]);line=lines.pop(terminal);lines.insert(read,line)
   with self.assertRaises(ValueError):e.validate_cases(b''.join(lines),arch)
   start,end=case_rows(21);lines=original.copy();terminal=next(i for i in range(start,end) if lines[i].startswith(b'OK_NATIVE_PIPE_WRITE_COMPLETE '));read=next(i for i in range(start,end) if lines[i].startswith(b'PIPE_BLOCKING_READ_BEGIN ') and b'bytes=4095' in lines[i]);line=lines.pop(terminal);lines.insert(read,line)
   with self.assertRaises(ValueError):e.validate_cases(b''.join(lines),arch)
   start,end=case_rows(25);line=next(x for x in original[start:end] if x.startswith(b'OK_NATIVE_PIPE_WRITE_LARGE_WAIT ') and b'live=2' in x)
   with self.assertRaises(ValueError):e.validate_cases(raw.replace(line,line.replace(b'live=2',b'live=1'),1),arch)
 def test_immediate_descriptor_bounds_in_full_wrapper(self):
  import re
  for arch in ARCHES:
   for c in (22,23,24):
    for value in (32,65535,0x7fffffff):
     parts=transcript(arch);lines=parts[2].splitlines(keepends=True);start=next(i for i,x in enumerate(lines) if x.startswith(b'PIPE_BLOCKING_CASE_BEGIN ') and f' case={c} '.encode() in x);end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'PIPE_BLOCKING_PARENT_PASS '));index=next(i for i in range(start,end) if lines[i].startswith(b'PIPE_BLOCKING_WRITER '));lines[index]=re.sub(rb' fd=[0-9]+ ',f' fd={value} '.encode(),lines[index]);parts[2]=b''.join(lines)
     with self.subTest(arch=arch,case=c,fd=value),self.assertRaises(ValueError):validate(parts,arch)
 def test_unrelated_image_preserves_live_owner(self):
  for arch in ARCHES:
   records=[x for x in events(arch).splitlines(keepends=True) if x.startswith(b'OK_NATIVE_PIPE_')];first=next(i for i,x in enumerate(records) if x.startswith(b'OK_NATIVE_PIPE_WRITE_LARGE_COMPLETE '));one=records[:first+1];one.insert(2,IMAGE);parsed=native_events(b''.join(one),arch,allow_signal=True);self.assertEqual(parsed[-1]['result'],12288)
   wrong=one.copy();wrong[-1]=wrong[-1].replace(b'description=5',b'description=6')
   with self.assertRaises(ValueError):native_events(b''.join(wrong),arch,allow_signal=True)
 def test_qualifier_layout(self):
  from qualify_native_pipe_blocking import probe_layout
  for arch in ARCHES:self.assertEqual(probe_layout(arch,'pipe-blocking-writes')[0],'native_pipe_blocking')
if __name__=='__main__':unittest.main()
