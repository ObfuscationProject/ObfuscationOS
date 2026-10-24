"""Actual pinned musl/Linux transcript and explicitly synthetic ABI schedules.

Transcoding observed actor schedules is parser input, never hardware evidence.
Private 32-slot payload cases are independently authored below. The generator
imports no production collector plans or field dictionaries.
"""
from pathlib import Path
from functools import lru_cache
import base64,hashlib,zlib
ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
TIMED=dict(zip(ARCHES,(128,177,137,177,421,137,137,4197,5126,176)))
SUSPEND=dict(zip(ARCHES,(130,179,133,179,133,133,133,4199,5128,178)))
@lru_cache(None)
def linux_fixture():
 lines=(Path(__file__).resolve().parents[1]/'fixtures/signal_wait_linux_x86_64.b85').read_text().splitlines();raw=zlib.decompress(base64.b85decode(''.join(lines[2:])))
 assert hashlib.sha256(raw).hexdigest()==lines[1].split(': ',1)[1];return raw

def decode(line):
 words=line.decode().split();tag=words[0].removeprefix('SIGNAL_WAIT_');row={}
 for field in words[1:]:
  k,v=field.split('=',1);row[k]=v if k in ('arch','tag','reason') else int(v)
 return tag,row

def encode(tag,row):return ('SIGNAL_WAIT_'+tag+' '+' '.join(f'{k}={v}' for k,v in row.items())).encode()
def info_hash(arch,signal,code,sender,uid):
 data=bytearray(128);order='big' if arch in ('mips','mips64','ppc') else 'little';offset=12 if arch in ('i386','arm32','rv32','mips','ppc') else 16
 for at,value in ((0,signal),(4 if arch.startswith('mips') else 8,code),(offset,sender),(offset+4,uid)):data[at:at+4]=(value&0xffffffff).to_bytes(4,order)
 value=5381
 for byte in data:value=((value*33)^byte)&0xffffffff
 return value

def matrix(arch):
 forms=(0,1) if arch in ('arm32','ppc') else (0,);times=(1,) if arch=='rv32' else (0,1) if arch in ('i386','arm32','mips','ppc') else (0,)
 for restart in (0,1):
  for time in times:
   for form in forms:
    for case in range(32):yield 0,0,time,form,restart,case
  for case in range(4,32):yield 0,1,2,0,restart,case
  for form in forms:
   for case in range(17):yield 1,0,3,form,restart,case
  for case in range(2,17):yield 1,1,3,0,restart,case

def private_capacity(part,case,arch):
 """Use only the fixture's bootstrap identity; author new queue operations."""
 key={k:part[0][1][k] for k in ('arch','family','api','time','form','restart','case')};key['case']=case
 child=next(r for t,r in part if t=='CHILD');pid=child['pid'];uid=child['uid'];site=child['site'];resume=child['resume'];api=key['api'];size=child['size'];base=site+0x10000
 lines=[]
 for tag,row in part:
  if tag=='SEND':break
  lines.append((tag,dict(row,case=case)))
 pending_ordinal=1;ordinal=0;send_ordinal=0
 def emit(kind,**fields):lines.append((kind,dict(key,**fields)))
 def send(number):
  nonlocal send_ordinal
  emit('SEND',actor=9,ordinal=send_ordinal,pid=pid,tid=pid,process=1,target=pid,signal=number,uid=uid);emit('SENT',actor=9,ordinal=send_ordinal);send_ordinal+=1
 def pending(value):
  nonlocal pending_ordinal
  emit('PENDING',actor=9,ordinal=pending_ordinal,bits=value,mask=31);pending_ordinal+=1
 def receive(wanted,result,source):
  nonlocal ordinal
  code=0;sender=source if result>0 else 0;user=uid if sender else 0
  canonical=(1<<34 if wanted&4 else 0)|(1<<35 if wanted&8 else 0)
  word0=((canonical&0xffffffff)<<32)|(canonical>>32) if arch in ('mips','ppc') else canonical
  syscall=4421 if arch=='mips' and key['time']==1 else 421 if key['time']==1 else TIMED[arch]
  emit('BEGIN',actor=9,ordinal=ordinal,pid=pid,tid=pid,syscall=syscall,set=base,info=base+256,timeout=base+512,size=size,wanted=wanted,word0=word0,word1=0,mask=31,expected=result,library=0,site=site,resume=resume)
  emit('RETURN',actor=9,ordinal=ordinal,value=(-1 if api and result<0 else result),errno=(-result if api and result<0 else 222),mask=31)
  if result>0:emit('INFO',actor=9,ordinal=ordinal,signal=result,code=code,sender=sender,uid=user,bytes=128,checksum=info_hash(arch,result,code,sender,user))
  emit('EVENT',actor=9,tag='INFO_GUARDS',value=ordinal,extra=16);emit('EVENT',actor=9,tag='WAIT_CHECKED',value=ordinal,extra=result);ordinal+=1
 for _ in range(32):send(35)
 send(36);pending(12)
 if case==22:receive(8,36,0)
 else:receive(4,35,pid);send(36);receive(8,36,pid)
 for _ in range(32 if case==22 else 31):receive(4,35,pid)
 receive(12,-11,0);pending(0)
 emit('CASE_PASS',pid=pid,handlers0=0,handlers1=0,handlers9=0);emit('PARENT_PASS',child=pid,exit=0,signal=0)
 return lines

@lru_cache(None)
def events(arch):
 templates={};current=[]
 for line in linux_fixture().splitlines():
  tag,row=decode(line)
  if tag=='CASE_BEGIN':current=[(tag,row)]
  elif tag=='PARENT_PASS':current.append((tag,row));templates[(row['family'],row['api'],row['restart'],row['case'])]=current;current=[]
  elif current:current.append((tag,row))
 forms=2 if arch in ('arm32','ppc') else 1;word32=arch in ('i386','arm32','rv32','mips','ppc');base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000
 output=[encode('START',dict(arch=arch,pid=1,pointer_bits=32 if word32 else 64,raw_forms=forms,raw_time_begin=1 if arch=='rv32' else 0,raw_time_end=2 if word32 else 1))]
 cases=list(matrix(arch))
 for number,(family,api,time,form,restart,case) in enumerate(cases):
  sourcecase=4 if not family and case in (22,23) else case;original=templates[(family,api,restart,sourcecase)];part=[];pid=10+number*10;oldchild=next(r for t,r in original if t=='CHILD')['pid'];oldpid=original[0][1]['parent'];pointermap={};pidmap={oldchild:pid,oldpid:1}
  threadids={r['tid']:pid+r['actor']+1 for t,r in original if t=='THREAD'};pidmap.update(threadids)
  def remap_pid(value):
   if not value:return 0
   if value not in pidmap:pidmap[value]=pid+3+len([v for v in pidmap.values() if pid+3<=v<pid+10])
   return pidmap[value]
  def pointer(value):
   if value in (0,1):return value
   if value not in pointermap:pointermap[value]=base+0x10000+len(pointermap)*4096
   return pointermap[value]
  def signal(value):return {10:16,12:17,19:23,28:20}.get(value,value) if arch.startswith('mips') else value
  for tag,old in original:
   row=old.copy()
   if tag=='LINUX_WAIT':continue
   # Keep the first shared raw call and model continuous waiting by its loser.
   if not family and case==16 and not api:
    retrying={r['actor'] for t,r in original if t=='EVENT' and r['tag']=='RAW_SHARED_RETRY'}
    if row.get('actor') in retrying:
     if tag=='BEGIN' and row['ordinal']>0:continue
     if tag=='RETURN' and row['value']==-4:continue
     if tag=='EVENT' and row['tag']=='RAW_SHARED_RETRY':continue
     if tag=='EVENT' and row['tag'] in ('INFO_GUARDS','WAIT_CHECKED') and row['value']==0:continue
     if 'ordinal' in row and tag in ('RETURN','INFO'):row['ordinal']=0
     if tag=='EVENT' and row['tag'] in ('INFO_GUARDS','WAIT_CHECKED'):row['value']=0
   if not family and case==2 and word32:
    if tag in ('BEGIN','RETURN') and row['ordinal']==3:continue
    if tag=='EVENT' and row['tag'] in ('INFO_GUARDS','WAIT_CHECKED') and row['value']==3:continue
    if tag=='PENDING' and row['ordinal']==5:continue
    if tag in ('BEGIN','RETURN','INFO') and row['ordinal']==4:row['ordinal']=3
    if tag=='EVENT' and row['tag'] in ('INFO_GUARDS','WAIT_CHECKED') and row['value']==4:row['value']=3
    if tag=='PENDING' and row['ordinal']==6:row['ordinal']=5
   row.update(arch=arch,family=family,api=api,time=time,form=form,restart=restart,case=sourcecase)
   for k in ('pid','tid','sender','parent','child'):
    if k in row:row[k]=remap_pid(row[k])
   if tag=='SEND':row['target']=remap_pid(row['target'])
   for k in ('signal',):
    if k in row:row[k]=signal(row[k])
   if tag in ('BEGIN','RETURN'):
    k='expected' if tag=='BEGIN' else 'value'
    if row[k]>0:row[k]=signal(row[k])
   if tag=='EVENT':
    ev=row['tag']
    if ev in ('THREAD_EXIT','SENDER_EXIT','CHILD_REAP','EXEC_COMMIT','FORK_EMPTY','FORK_REAP','HANDLER_REAP','HANDLER_EXIT'):row['value']=remap_pid(row['value'])
    if ev=='JOIN':row['extra']=remap_pid(row['extra'])
    if ev in ('HANDLER_RETURN',):row['value']=signal(row['value'])
    if ev in ('WAIT_CHECKED','WINNER') and row['extra']>0:row['extra']=signal(row['extra'])
    if ev in ('MAP','PROTECT','UNPROTECT','MUTATE_SET'):row['value']=pointer(row['value'])
    if ev=='HUGE_TIMEOUT':row['value']=4 if word32 else 8;row['extra']=time
   for k in ('site','resume','pc','set','info','timeout'):
    if k in row:row[k]=pointer(row[k])
   if tag in ('CHILD','BEGIN'):
    row['site']=base+0x400;row['resume']=row['site']+(2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4)
   if tag in ('CHILD','BEGIN'):row['size']=16 if arch.startswith('mips') else 8
   if tag=='BEGIN':
    if sourcecase==0 and row['ordinal']==0:row['size']-=1
    row['syscall']=SUSPEND[arch] if old['syscall']==130 else (4421 if arch=='mips' else 421) if time==1 or api and case==31 and word32 else TIMED[arch]
    if old['word0']:
     raw=sum(1<<(signal(n)-1) for n in range(1,65) if old['word0']&(1<<(n-1)))
     row['word0']=((raw&0xffffffff)<<32)|(raw>>32) if arch in ('mips','ppc') else raw
   if tag=='HANDLE':
    row['pc']=base+0x400+(2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4) if not api else base+0x800
    row['abi']=1 if arch.startswith('mips') else 0x10000000 if arch=='ppc' else 32 if arch=='arm32' and form else 0
   if tag=='INFO':row['checksum']=info_hash(arch,row['signal'],row['code'],row['sender'],row['uid'])
   part.append((tag,row))
  if not family and case in (22,23):part=private_capacity(part,case,arch)
  output.extend(encode(t,r) for t,r in part)
 output.append(encode('PASS',dict(arch=arch,cases=len(cases),excluded=0,semantic_cases=49)))
 return b'\n'.join(output)+b'\n'

@lru_cache(None)
def native_fixture(arch):
 """Author legal ownership transitions around synthetic actor schedules."""
 raw=events(arch);decoded=[decode(line) for line in raw.splitlines()];out=[];active={};epochs={};case_rows=[];context=None
 def kernel(tag,fields):out.append(('OK_NATIVE_SIGNAL_WAIT_'+tag+' '+' '.join(f'{k}={v}' for k,v in fields.items())).encode())
 def identity(record):return {k:record[k] for k in ('pid','tid','epoch','wait','kind')}
 def arm(call):
  who=call['actor'];epochs[who]=epochs.get(who,0)+1
  sigs=(16,17,35,36,20) if arch.startswith('mips') else (10,12,35,36,28)
  def mask(bits):return sum(1<<(n-1) for i,n in enumerate(sigs) if bits&(1<<i))
  wanted=mask(call['wanted']);original=mask(call['mask']);temporary=wanted if call['family'] else original&~wanted
  record=dict(pid=call['pid'],tid=call['tid'],epoch=epochs[who],wait=epochs[who],kind='suspend' if call['family'] else 'timed',syscall=call['syscall'],pc=call['resume'] if not call['api'] else call['site']+0x800,set=call['set'],info=call['info'],timeout=call['timeout'],sigsetsize=call['size'],wanted0=wanted,wanted1=0,original0=original,original1=0,deadline=9000000000 if call['timeout'] else 0,active0=temporary,active1=0)
  active[who]=(record,call);kernel('ARM',dict(record,live=len(active)))
 def complete(who,signal=0,code=0,sender=0,uid=0,outcome='received'):
  record,call=active[who];suspend=record['kind']=='suspend';result=signal if outcome=='received' else -11 if outcome=='timeout' else -4
  if not suspend:del active[who]
  kernel('COMPLETE',dict(identity(record),outcome=outcome,signal=signal,code=code,sender_pid=sender,sender_uid=uid,info=record['info'],result=result,published=int(not suspend),staged=int(suspend),consumed=int(outcome=='received'),live=len(active),deadline=record['deadline'],now=record['deadline'] if outcome=='timeout' else 1000000000))
  if suspend:
   kernel('COMMIT',dict(identity(record),signal=signal,published=1,result=-4,live_before=len(active)));del active[who]
 def retire(cause):
  before=len(active)
  for who,(record,call) in list(active.items()):
   kernel('RETIRE',dict(identity(record),cause=cause,published=0,staged=0,live_before=before if cause=='exec' else len(active)));del active[who]
 from test_native_signal_delivery_x86_64 import IMAGE
 for index,(tag,row) in enumerate(decoded):
  if tag=='CASE_BEGIN':
   assert not active;epochs={};context=row;case_rows=[]
   for t,r in decoded[index:]:
    case_rows.append((t,r))
    if t=='PARENT_PASS':break
  f=row.get('family');c=row.get('case');a=row.get('api');who=row.get('actor');ev=row.get('tag')
  if tag=='RETURN' and who in active:
   assert row['value'] in (-11,-1);complete(who,outcome='timeout')
  out.append(encode(tag,row))
  if tag=='BEGIN':
   deferred=(f and c>=2 and not(c==4 and row['ordinal']==1)) or (not f and c>=13 and c not in (21,22,23))
   if deferred:
    arm(row)
    if f and c in (2,3,4):
     send=next(r for t,r in reversed(case_rows[:next(i for i,(t,r) in enumerate(case_rows) if t=='BEGIN')]) if t=='SEND' and r['signal']==(16 if arch.startswith('mips') else 10))
     complete(who,send['signal'],0 if send['process'] else -6,send['pid'],send['uid'],'eintr')
  elif tag=='SEND':
   signal=row['signal'];usr1,usr2,win=(16,17,20) if arch.startswith('mips') else (10,12,28)
   if signal==9:retire('group');continue
   if not active:continue
   if f:
    if signal==win or signal==usr1 and c in (7,8,10):continue
    complete(0,signal,0 if row['process'] else -6,row['pid'],row['uid'],'eintr')
   else:
    if c==18 and signal==win:
     if row['target']!=row['pid']:continue
     call=active[0][1];complete(0,signal,0,row['pid'],row['uid'],'eintr')
     if a:arm(call)
    elif c==17 and signal==usr2:complete(0,signal,-6,row['pid'],row['uid'],'eintr')
    elif c==26 and row['target']==row['pid']:continue
    else:
     if c==16:
      winner=next(r['value'] for t,r in case_rows if t=='EVENT' and r['tag']=='WINNER');selected=winner if signal==usr1 else 1-winner
     else:selected=next((actor for actor,(record,call) in active.items() if record['tid']==row['target']),0)
     complete(selected,signal,0 if row['process'] else -6,row['pid'],row['uid'])
  elif tag=='EVENT' and ev=='HANDLER_RETURN' and not f and c==17 and a:
   call=next(r for t,r in case_rows if t=='BEGIN' and r['actor']==0);arm(call)
  elif tag=='EVENT' and ev=='EXEC_COMMIT':
   retire('exec');out.append(IMAGE.rstrip(b'\n'))
 assert not active
 return b'\n'.join(out)+b'\n'
