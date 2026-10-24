"""Strict private signal-wait ownership ledger, independent of guest markers.

Epochs are scoped to exposed live owners. The implementation does not expose an
entry-stack slot, so this parser does not invent global PID epoch monotonicity.
Exec retirement is an atomic per-process batch with pre-batch live counts.
"""
import re
from signal_wait_guest_protocol import ARCHES,TIMED,SUSPEND

PREFIX=b'OK_NATIVE_SIGNAL_WAIT_';N=rb'[0-9]+';I=rb'-?[0-9]+'
IDENTITY='pid:N tid:N epoch:N wait:N kind:(timed|suspend)'
INPUTS='syscall:N pc:N set:N info:N timeout:N sigsetsize:N wanted0:N wanted1:N original0:N original1:N deadline:N'
ACTIVE='active0:N active1:N'
FIELDS={
 'ARM':IDENTITY+' '+INPUTS+' '+ACTIVE+' live:N',
 'COMPLETE':IDENTITY+' outcome:(received|efault|timeout|cancelled|eintr) signal:N code:I sender_pid:N sender_uid:N info:N result:I published:[01] staged:[01] consumed:[01] live:N deadline:N now:N',
 'REARM':IDENTITY+' old_wait:N cause:(ready|delivery) '+INPUTS+' '+ACTIVE+' published:0 staged:[01] live:N',
 'COMMIT':IDENTITY+' signal:N published:1 result:-4 live_before:N',
 'RETIRE':IDENTITY+' cause:(thread|group|exec) published:0 staged:[01] live_before:N',
}
def pattern(event,fields):return re.compile(PREFIX+event.encode()+b''.join(b' '+n.encode()+b'='+{'N':N,'I':I}.get(k,k.encode()) for n,k in (f.split(':',1) for f in fields.split())))
PATTERNS=tuple(pattern(e,f) for e,f in FIELDS.items())
def require(value,message):
 if not value:raise ValueError('native signal wait '+message)
def parse(raw):
 rows=[]
 if raw and not raw.endswith(b'\n') and PREFIX in raw.splitlines()[-1]:raise ValueError('native signal wait unterminated final record')
 for position,line in enumerate(raw.splitlines()):
  if PREFIX not in line:continue
  require(any(p.fullmatch(line) for p in PATTERNS),'malformed or unknown record')
  words=line.split();row={'event':words[0].decode().removeprefix('OK_NATIVE_SIGNAL_WAIT_'),'position':position,'line':line}
  for field in words[1:]:
   k,v=field.split(b'=',1);k=k.decode();v=v.decode();row[k]=v if k in ('kind','outcome','cause') else int(v)
  require(all(-2**63<=v<2**64 for k,v in row.items() if type(v) is int and k!='position'),'integer range')
  require(all(row[k]>0 for k in ('pid','tid','epoch','wait')) and row['pid']<=0x3fffffff and row['tid']<=0x3fffffff,'owner identity domain')
  rows.append(row)
 return rows

def native_events(raw,arch,allow_child=False):
 require(arch in ARCHES,'unknown architecture');rows=parse(raw);live={};history={};exec_batch=None
 low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000)
 def pointer(v,size=1,optional=False):return optional and v==0 or low<=v<high and v+size<=high
 def finish_exec():
  nonlocal exec_batch
  if exec_batch:
   require(exec_batch['pending']==set(),'incomplete exec retirement batch');exec_batch=None
 def inputs(row):
  kind=row['kind'];size=16 if arch in ('mips','mips64') else 8
  require(pointer(row['pc']) and pointer(row['set'],size) and row['info']<(1<<(32 if arch in ('i386','arm32','rv32','mips','ppc') else 64)),'input address domain')
  require(row['pc']%4==0 if arch not in ('x86_64','i386','arm32','rv32','rv64') else row['pc']%2==0 if arch in ('arm32','rv32','rv64') else True,'instruction alignment')
  require(row['sigsetsize']==size,'sigset size')
  numbers={SUSPEND[arch]} if kind=='suspend' else {TIMED[arch]}|({4421 if arch=='mips' else 421} if arch in ('i386','arm32','rv32','mips','ppc') else set())
  require(row['syscall'] in numbers,'syscall kind/time ABI')
  timesize=16 if arch not in ('i386','arm32','mips','ppc') or row['syscall'] in (421,4421) else 8
  require(pointer(row['timeout'],timesize,optional=True) and row['deadline']<=0x7fffffffffffffff,'timeout structure/deadline domain')
  forbidden=(1<<8)|(1<<((23 if arch.startswith('mips') else 19)-1))
  require(not any(row[k]&forbidden for k in ('wanted0','original0','active0')),'uncatchable signal mask')
  if size==8:require(not any(row[k] for k in ('wanted1','original1','active1')),'upper mask word')
  for i in range(2):require(row['active'+str(i)]==(row['wanted'+str(i)] if kind=='suspend' else row['original'+str(i)]&~row['wanted'+str(i)]),'active mask derivation')
  if kind=='suspend':require(row['info']==row['timeout']==row['deadline']==0,'suspend has timed output/deadline')
  else:require(bool(row['timeout'])==bool(row['deadline']),'finite deadline ownership')
 for row in rows:
  identity=(row['pid'],row['tid']);event=row['event'];ticket=(identity,row['epoch'],row['wait'])
  is_exec=event=='RETIRE' and row['cause']=='exec'
  if exec_batch and not (is_exec and row['pid']==exec_batch['pid']):finish_exec()
  if event=='ARM':
   inputs(row);require(identity not in live and all(k[1]!=row['tid'] for k in live),'duplicate live owner/TID')
   require(row['wait']>history.get(identity,0),'scheduler ticket did not advance in exposed TCB lifetime');history[identity]=row['wait']
   live[identity]={'origin':row,'current':row,'phase':'waiting','staged':0,'tickets':{row['wait']}}
   require(row['live']==len(live),'ARM live count');row['origin_position']=row['position']
  else:
   require(identity in live,'record has no live owner');owned=live[identity];origin=owned['origin'];current=owned['current'];row['origin_position']=origin['position']
   require(row['epoch']==origin['epoch'] and row['kind']==origin['kind'],'logical owner changed')
   if event=='REARM':
    inputs(row);require(row['old_wait']==current['wait'] and row['wait']>current['wait'] and row['wait'] not in owned['tickets']  ,'stale rearm ticket')
    for field in INPUTS.split():
     k=field.split(':')[0];require(row[k]==origin[k],'copied request changed on rearm')
    require(row['cause']==('delivery' if owned['phase']=='delivery' else 'ready') and row['staged']==owned['staged'],'rearm phase/staged result')
    require(row['live']==len(live),'REARM live count');owned.update(current=row,phase='waiting');owned['tickets'].add(row['wait']);history[identity]=row['wait']
   else:
    require(row['wait']==current['wait'],'stale completion/retirement ticket')
    if event=='COMPLETE':
     require(owned['phase']=='waiting','duplicate staged completion');require(row['info']==origin['info'] and row['deadline']==origin['deadline'],'completion copied inputs')
     outcome=row['outcome'];signal=row['signal'];matched=outcome in ('received','efault');staged=row['kind']=='suspend' and outcome=='eintr'
     require((row['published'],row['staged'],row['consumed'])==(int(not staged),int(staged),int(matched)),'publication/consumption flags')
     require(row['result']==(signal if outcome=='received' else -14 if outcome=='efault' else -11 if outcome=='timeout' else -4),'completion result')
     if outcome in ('timeout','cancelled'):
      require(signal==row['code']==row['sender_pid']==row['sender_uid']==0,'empty completion siginfo')
     else:
      child_code=row['code'] in (1,2)
      require(1<=signal<=(128 if arch.startswith('mips') else 64) and signal not in (9,23 if arch.startswith('mips') else 19) and
              (row['code'] in (0,-6,128) or allow_child and child_code),'signal completion info')
      require(row['sender_pid']<=0x3fffffff and row['sender_uid']<=0xffffffff,'sender identity domain')
      if child_code:
       # Typed child status is opt-in: inherited user-signal campaigns keep
       # their original domains. Exact child ownership/cause is joined by the
       # child-exit campaign against trusted lifecycle and full guest siginfo.
       require(signal==(18 if arch.startswith('mips') else 17) and row['sender_pid']>0,'child signal identity')
      require(row['code']!=128 or row['sender_pid']==row['sender_uid']==0,'kernel signal zero payload')
      index=(signal-1)//64;bit=1<<((signal-1)%64);in_wanted=bool(origin['wanted'+str(index)]&bit)
      require(in_wanted if matched else not (current['active'+str(index)]&bit) and (row['kind']=='suspend' or not in_wanted),'selection or interrupt eligibility')
     if matched:require(row['kind']=='timed' and (outcome!='efault' or row['info']!=0) and (outcome!='received' or pointer(row['info'],128,optional=True)),'suspend receive or output copy result')
     if outcome=='eintr' and row['kind']=='timed' and origin['timeout']:require(row['now']<origin['deadline'],'timed EINTR after elapsed deadline')
     if outcome=='timeout':require(row['kind']=='timed' and origin['timeout'] and row['now']>=origin['deadline'],'unelapsed timeout')
     if staged:owned.update(phase='delivery',staged=1)
     else:del live[identity]
     require(row['live']==len(live),'COMPLETE live count')
    elif event=='COMMIT':
     require(owned['phase']=='delivery' and row['kind']=='suspend' and owned['staged']==1 and row['live_before']==len(live),'handler commit phase/live')
     require(1<=row['signal']<=(128 if arch.startswith('mips') else 64) and row['signal'] not in (9,23 if arch.startswith('mips') else 19) and not (origin['wanted'+str((row['signal']-1)//64)]&(1<<((row['signal']-1)%64))),'committed blocked signal');del live[identity]
    elif event=='RETIRE':
     require(row['staged']==owned['staged'],'retirement staged state')
     if is_exec:
      if not exec_batch:exec_batch={'pid':row['pid'],'live_before':len(live),'pending':{k for k in live if k[0]==row['pid']},'previous_position':row['position']-1}
      require(row['position']==exec_batch['previous_position']+1,'noncontiguous exec batch');exec_batch['previous_position']=row['position']
      require(row['live_before']==exec_batch['live_before'] and identity in exec_batch['pending'],'exec pre-batch count/identity');exec_batch['pending'].remove(identity)
     else:require(row['live_before']==len(live),'retirement live count')
     del live[identity];history.pop(identity,None)
 finish_exec();require(not live,'live ownership at supplied boundary');return rows
