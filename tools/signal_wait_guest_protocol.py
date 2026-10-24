"""Independent actor/case contract for the all-ten synchronous wait guest.

A passing C assertion marker is checked together with its inputs, returned ABI
bytes, role streams and command edges. This module does not claim native wait
ownership; the native ledger and binding module supply that separate evidence.
"""
import re
from collections import Counter, defaultdict

ARCHES=('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc')
WORD32={'i386','arm32','rv32','mips','ppc'}
TIMED=dict(zip(ARCHES,(128,177,137,177,421,137,137,4197,5126,176)))
SUSPEND=dict(zip(ARCHES,(130,179,133,179,133,133,133,4199,5128,178)))
GUEST_PREFIX=b'SIGNAL_WAIT_'
KEYS=('family','api','time','form','restart','case')
KEY=rb'arch=(?:'+b'|'.join(a.encode() for a in ARCHES)+rb') family=[01] api=[01] time=[0123] form=[01] restart=[01] case=[0-9]+'
N,I=rb'[0-9]+',rb'-?[0-9]+'
EVENTS=('INFO_GUARDS','WAIT_CHECKED','RAW_SHARED_RETRY','HANDLER_REAP','HANDLER_EXIT',
 'HANDLER_RETURN','THREAD_EXIT','JOIN','SENDER_EXIT','CHILD_REAP','MAP','PROTECT','UNPROTECT',
 'EXEC_COMMIT','STRADDLE_GUARDS','WINNER','IGNORED_DROP_OBSERVED','IGNORED_INTERRUPT_OBSERVED',
 'MUTATE_SET','MUTATE_TIMEOUT','HUGE_TIMEOUT','FORK_EMPTY','FORK_REAP','IGNORED_DRAIN_OWNED',
 'HANDLER_EXIT_NO_RETURN','SUSPEND_IGNORED_DROP','UNMAP')
FIELDS={
 'CASE_BEGIN':'parent:N',
 'CHILD':'pid:N tid:N uid:N size:N rtmin:N site:N resume:N',
 'MASK':'actor:A bits:N','PENDING':'actor:A ordinal:N bits:N mask:N',
 'ACTION':'actor:A signal:N kind:[012]',
 'THREAD':'actor:R tid:N mask:N',
 'BEGIN':'actor:A ordinal:N pid:N tid:N syscall:N set:N info:N timeout:N size:N wanted:N word0:N word1:N mask:N expected:I library:N site:N resume:N',
 'RETURN':'actor:A ordinal:N value:I errno:N mask:N',
 'INFO':'actor:A ordinal:N signal:N code:I sender:N uid:N bytes:N checksum:N',
 'SEND':'actor:A ordinal:N pid:N tid:N process:[01] target:N signal:N uid:N',
 'SENT':'actor:A ordinal:N',
 'HANDLE':'actor:A ordinal:N pid:N tid:N signal:N code:I sender:N uid:N live:N saved:N pc:N result:I abi:N',
 'HANDLER_FORK':'actor:8 pid:N parent:N mask:N pending:N',
 'COMMAND':'actor:9 target:R seq:N operation:N argument:N',
 'ACK':'actor:R seq:N operation:N argument:N',
 'COMMAND_DONE':'actor:9 target:R seq:N operation:N argument:N',
 'AWAIT':'actor:9 target:R phase:N tid:N',
 'LINUX_WAIT':'actor:9 target:R phase:N tid:N syscall:N set:N info:N timeout:N size:N pc:N',
 'EVENT':'actor:A tag:('+ '|'.join(EVENTS)+') value:I extra:I',
 'CASE_PASS':'pid:N handlers0:N handlers1:N handlers9:N',
 'PARENT_PASS':'child:N exit:I signal:N',
 'REPLACED':'pid:N tid:N mask:N pending:N dirty:N tls:I caught_reset:N ignored_retained:N',
 'EXCLUDED':'reason:private-32-payload-capacity',
}
def _pattern(tag, fields, key=KEY):
 types={'N':N,'I':I,'A':rb'(?:0|1|8|9)','R':rb'[01]'}
 return re.compile(GUEST_PREFIX+tag.encode()+b' '+key+b''.join(b' '+n.encode()+b'='+types.get(k,k.encode()) for n,k in (v.split(':',1) for v in fields.split())))
PATTERNS=tuple(_pattern(t,f) for t,f in FIELDS.items())+(
 _pattern('START','pid:N pointer_bits:N raw_forms:N raw_time_begin:N raw_time_end:N',rb'arch=(?:'+b'|'.join(a.encode() for a in ARCHES)+b')'),
 _pattern('PASS','cases:N excluded:N semantic_cases:N',rb'arch=(?:'+b'|'.join(a.encode() for a in ARCHES)+b')'))

def require(value,message):
 if not value:raise ValueError('signal wait '+message)
def only(rows,label):
 require(len(rows)==1,'requires one '+label);return rows[0]
def key(row):return tuple(row[n] for n in KEYS)
def combinations(arch):
 forms=2 if arch in ('arm32','ppc') else 1
 times=(1,) if arch=='rv32' else (0,1) if arch in ('i386','arm32','mips','ppc') else (0,)
 for restart in (0,1):
  for time in times:
   for form in range(forms):
    for case in range(32):yield (0,0,time,form,restart,case)
  for case in range(4,32):yield (0,1,2,0,restart,case)
  for form in range(forms):
   for case in range(17):yield (1,0,3,form,restart,case)
  for case in range(2,17):yield (1,1,3,0,restart,case)
def parse(raw,arch):
 require(arch in ARCHES,'architecture not supported');out=[]
 for position,line in enumerate(raw.splitlines()):
  if GUEST_PREFIX not in line or b'OK_NATIVE_SIGNAL_WAIT_' in line:continue
  require(any(p.fullmatch(line) for p in PATTERNS),'unknown or malformed guest record')
  fields=line.split();row={'tag':fields[0].decode().removeprefix('SIGNAL_WAIT_'),'line':line,'position':position}
  for field in fields[1:]:
   name,value=field.split(b'=',1);name=name.decode();value=value.decode()
   if name=='tag':name='tag_value'
   row[name]=value if name in ('arch','reason','tag_value') else int(value)
  require(row['arch']==arch,'foreign architecture');out.append(row)
 return out

def signals(arch,rt=35):return (16,17,rt,rt+1,20) if arch in ('mips','mips64') else (10,12,rt,rt+1,28)
def encoded_info(arch,signal,code,pid,uid):
 endian='big' if arch in ('mips','mips64','ppc') else 'little';out=bytearray(128)
 def put(i,value):out[i:i+4]=(value&0xffffffff).to_bytes(4,endian)
 put(0,signal);put(4 if arch.startswith('mips') else 8,code);off=12 if arch in WORD32 else 16;put(off,pid);put(off+4,uid)
 value=5381
 for byte in out:value=((value*33)^byte)&0xffffffff
 return value

def expected_calls(family,case,api,arch,sigs):
 """(actor,wanted,result,code,mask,library); sender checked separately."""
 u,v,r,s,_=sigs;out=[]
 def call(actor,wanted,result,code=0,mask=31,library=0):out.append((actor,wanted,result,code,mask,library))
 def immediate(wanted,result,code=0,library=0):call(9,wanted,result,code,library=library)
 if family:
  if case==0:call(9,24,-22)
  elif case==1:
   for _ in range(3):call(9,24,-14)
  elif case in (2,3,4):
   call(9,26 if case==4 else 24,-4)
   if case==4:call(9,2,v,-6)
  elif case==9:
   for _ in range(2):call(0,8,-4)
  else:call(0,24,-4)
 elif case==0:
  for result in (-22,-14,-14):immediate(1,result)
 elif case==1:immediate(1,-14);immediate(1,u,-6)
 elif case==2:
  for _ in range(3 if arch in WORD32 else 4):immediate(1,-22)
  immediate(1,u,-6)
 elif case==3:immediate(0,-11);immediate(0,-11)
 elif case in (4,7,8):immediate(1,u,-6)
 elif case==5:immediate(1,u,0)
 elif case==6:
  for result,code in ((u,-6),(u,0),(v,-6),(u,0),(u,-6),(v,-6),(u,0),(v,0)):immediate(3,result,code)
  immediate(3,-11)
 elif case==9:
  immediate(1,u,-6);immediate(1,-11)
  if api:immediate(1,u,-6,1);immediate(1,u,-6,2);immediate(1,-11)
 elif case==10:immediate(1,u,-6);immediate(1,-11)
 elif case in (11,12):immediate(1,-14);immediate(1,-11)
 elif case in (13,20):call(0,1,-11)
 elif case in (14,15):call(0,1,u,-6 if case==14 else 0)
 elif case==16:call(0,3,u,0);call(1,3,u,0)
 elif case==17:call(0,1,u if api else -4,-6,29)
 elif case==18:
  for _ in range(2):call(0,1,u if api else -4,-6,15)
 elif case==21:
  for _ in range(3):immediate(4,r,0)
  immediate(4,-11)
 elif case in (22,23):
  if case==22:immediate(8,s,0)
  else:immediate(4,r,0);immediate(8,s,0)
  for _ in range(32 if case==22 else 31):immediate(4,r,0)
  immediate(12,-11)
 elif case in (24,25,26):call(0,1,u,-6 if case==24 else 0)
 elif case==30:call(0,1,u,-6);call(1,2,v,-6)
 else:call(0,1,u,-6)
 return out

def planned_sends(family,case,api,sigs):
 """Per-role sender plans; target is a role or 'group', external senders use 8."""
 u,v,r,s,w=sigs;out=[]
 def send(process,target,signal,actor=9):out.append((actor,process,target,signal))
 if family:
  if case in (2,3,4):
   if case==4:send(0,9,v)
   send(case!=2,9,u)
  elif case in (5,6,11,12,13,16):send(case==6,0,u)
  elif case in (7,8,10):send(case==8,0,u);send(0,0,v)
  elif case==9:
   for _ in range(2):send(1,9,w);send(0,0,u)
  elif case==15:send(1,0,9)
 elif case in (1,2,4,7,8,9,10,11,12):
  send(0,9,u)
  if case==9 and api:send(0,9,u);send(0,9,u)
 elif case==5:send(1,9,u,8)
 elif case==6:
  for process,signal in ((1,u),(0,u),(1,u),(0,v),(0,v),(0,u),(1,v),(1,u)):send(process,9,signal)
 elif case in (14,15,19,24,25,26,27,31):
  if case==26:send(1,9,u)
  if case==27:send(0,0,v)
  send(case in (15,25,26),0,u)
 elif case==16:send(1,9,u);send(1,9,v)
 elif case==17:
  send(0,0,v)
  if api:send(0,0,u)
 elif case==18:
  for _ in range(2):
   send(1,0,w);send(1,9,w)
   if api:send(0,0,u)
 elif case==21:
  for _ in range(3):send(1,9,r,8)
 elif case in (22,23):
  for _ in range(32):send(1,9,r)
  send(1,9,s)
  if case==23:send(1,9,s)
 elif case==29:send(1,0,9)
 elif case==30:send(0,1,v);send(0,0,u)
 return out

def _case(rows,begin,parent,arch,linux):
 f,a,t,form,restart,c=key(begin);part=[r for r in rows if begin['position']<r['position']<parent['position']]
 require(all(key(r)==key(begin) for r in part),'case key changed inside child')
 child=only([r for r in part if r['tag']=='CHILD'],'child identity');pid=child['pid'];uid=child['uid'];rt=child['rtmin'];sigs=signals(arch,rt)
 require(pid==child['tid']==parent['child'] and pid>0 and child['size']==(16 if arch.startswith('mips') else 8),'child PID or set size')
 require(rt==35,'pinned musl realtime minimum');width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
 require(child['resume']==child['site']+width,'trap continuation size')
 fatal=(f and c==15) or (not f and c==29);replaced=(f and c in (13,14)) or (not f and c==28)
 require((parent['exit'],parent['signal'])==((-1,9) if fatal else (0,0)),'exact child exit status')
 threads=[r for r in part if r['tag']=='THREAD'];actors={9:pid};expected_threads=0 if (f and c<5) or (not f and c<13) or (not f and c in (21,22,23)) else 2 if (f and c==14) or (not f and c in (16,28,30)) else 1
 require(len(threads)==expected_threads,'thread cardinality')
 for i,r in enumerate(threads):require(r['actor']==i and r['tid'] not in actors.values() and r['mask']==31,'new thread identity/mask');actors[i]=r['tid']
 passes=[r for r in part if r['tag']=='CASE_PASS'];fresh=[r for r in part if r['tag']=='REPLACED']
 require(len(passes)==int(not fatal and not replaced) and len(fresh)==int(replaced),'normal/exec completion cardinality')
 if fresh:
  q=fresh[0];expected_mask=29 if f and c==13 else 31
  require((q['pid'],q['tid'],q['mask'],q['pending'],q['dirty'],q['tls'],q['caught_reset'],q['ignored_retained'])==(pid,pid,expected_mask,0,0,-1,1,int(f and c==13)),'exec image state')
  commit=only([r for r in part if r['tag']=='EVENT' and r['tag_value']=='EXEC_COMMIT'],'exec commit');require(commit['position']<q['position'] and commit['value']==pid and commit['extra']==expected_mask,'exec commit ordering')
 # All wait attempts have an independent declared plan; raw shared-loser EINTR
 # retries are admitted only with a new ordinal and checked retry marker.
 calls=[r for r in part if r['tag']=='BEGIN'];returns=[r for r in part if r['tag']=='RETURN'];infos=[r for r in part if r['tag']=='INFO'];events=[r for r in part if r['tag']=='EVENT']
 retries=[r for r in events if r['tag_value']=='RAW_SHARED_RETRY'];require(not retries or not f and c==16 and not a and len(retries)<8,'raw retry applicability')
 retry_ids={(r['actor'],r['value']) for r in retries};planned=expected_calls(f,c,a,arch,sigs)
 for who in actors:
  actual=[r for r in calls if r['actor']==who];require([r['ordinal'] for r in actual]==list(range(len(actual))),'attempt ordinal')
  normal=[r for r in actual if (who,r['ordinal']) not in retry_ids];expected=[r for r in planned if r[0]==who]
  require(len(normal)==len(expected),'planned invocation cardinality')
  for r,e in zip(normal,expected):require((r['wanted'],r['expected'],r['mask'],r['library'])==(e[1],e[2],e[4],e[5]),'planned wait input')
 require(all(r['actor'] in actors for r in calls),'unknown caller')
 expected_returns=len(calls)-int(fatal or replaced or f and c==16)
 require(len(returns)==expected_returns,'wait return cardinality')
 seen_returns=set();assigned_infos=set()
 for call in calls:
  who,ordinal=call['actor'],call['ordinal'];effective_family=0 if f and c==4 and ordinal==1 else f
  require((call['pid'],call['tid'],call['site'],call['resume'])==(pid,actors[who],child['site'],child['resume']),'caller identity and trap labels')
  expected_number=SUSPEND[arch] if effective_family else (4421 if arch=='mips' else 421) if t==1 or a and c==31 and arch in WORD32 else TIMED[arch]
  require(call['syscall']==expected_number,'syscall/time ABI')
  require(call['size']==child['size']-(1 if c==0 and ordinal==0 else 0),'sigset byte count')
  low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000)
  def pointer(value):return value>1 if linux else low<=value<high
  null_set=(c==0 and ordinal==1) or (f and c==1 and ordinal==1)
  bad_set=(c==0 and ordinal==0) or (f and c==1 and ordinal==0)
  require(call['set']==0 if null_set else call['set']==1 if bad_set else pointer(call['set']),'set pointer admission shape')
  null_info=effective_family or not f and c==9 and ordinal==0
  bad_info=not f and (c==3 or c==11 and ordinal==0)
  require(call['info']==0 if null_info else call['info']==1 if bad_info else pointer(call['info']),'info pointer result shape')
  timeout_absent=effective_family or call['library'] or (not f and c>=14 and c not in (20,21,22,23,31))
  bad_timeout=not f and c==1 and ordinal==0
  require(call['timeout']==1 if bad_timeout else call['timeout']==0 if timeout_absent else pointer(call['timeout']),'timeout pointer shape')
  copied=not ((f and c in (0,1,11)) or (not f and c in (0,19,20)) or (not f and c==1 and ordinal==0))
  canonical=sum(1<<(n-1) for i,n in enumerate(sigs) if call['wanted']&(1<<i))
  if not f and c==3 and ordinal==1:canonical|=(1<<8)|(1<<((23 if arch.startswith('mips') else 19)-1))
  first=(((canonical&0xffffffff)<<32)|(canonical>>32)) if arch in ('mips','ppc') else canonical
  require((call['word0'],call['word1'])==((first,0) if copied else (0,0)),'copied sigset input bytes')
  result_rows=[r for r in returns if (r['actor'],r['ordinal'])==(who,ordinal)]
  if not result_rows:
   require(who==0 and (fatal or replaced or f and c==16),'unreturned unrelated call');continue
  result=only(result_rows,'call return');seen_returns.add((who,ordinal));require(call['position']<result['position'],'return before call')
  retry=(who,ordinal) in retry_ids;expected=-4 if retry else call['expected'];actual=result['value']
  require(actual==(-1 if a and expected<0 else expected) or not f and c==16 and actual==sigs[1],'returned value')
  require(result['errno']==(-expected if a and expected<0 else 222) and result['mask']==call['mask'],'errno/restored mask')
  checked=only([r for r in events if r['actor']==who and r['tag_value']=='WAIT_CHECKED' and r['value']==ordinal],'checked call');require(result['position']<checked['position'] and checked['extra']==expected,'checked result linkage')
  info=[r for r in infos if (r['actor'],r['ordinal'])==(who,ordinal)]
  needs_info=actual>0 and call['info'] and call['library']!=2
  require(len(info)==int(bool(needs_info)),'full siginfo proof cardinality')
  if info:
   q=info[0];assigned_infos.add((who,ordinal));source=pid;code=-6
   if not effective_family:
    planned_for_actor=[e for e in planned if e[0]==who];n=[r for r in calls if r['actor']==who and (who,r['ordinal']) not in retry_ids].index(call);code=planned_for_actor[n][3]
   if not f and c in (5,21):
    reaped=[r for r in events if r['tag_value']=='CHILD_REAP'];source=reaped[0 if c==5 else ordinal]['value']
   if not f and c==22 and ordinal==0:source=0
   expected_uid=0 if not source else uid
   require((q['signal'],q['code'],q['sender'],q['uid'],q['bytes'],q['checksum'])==(actual,code,source,expected_uid,128,encoded_info(arch,actual,code,source,expected_uid)),'full siginfo fields/checksum')
   require(result['position']<q['position']<checked['position'],'siginfo check ordering')
 require(len(seen_returns)==len(returns) and len(assigned_infos)==len(infos),'orphan result or info')
 # Exact sender plans and return pairs, including each separately reaped sender.
 sends=[r for r in part if r['tag']=='SEND'];sent=[r for r in part if r['tag']=='SENT'];plan=planned_sends(f,c,a,sigs)
 require(len(sends)==len(plan),'signal send cardinality');require(len(sent)==len(sends)-int(fatal),'signal return cardinality')
 for send,e in zip(sends,plan):
  who,process,target,signal=e;require((send['actor'],send['process'],send['target'],send['signal'],send['uid'])==(who,int(process),actors[target],signal,uid),'signal send plan')
  require(send['pid']==send['tid'] and (who==8 or send['pid']==pid),'sender identity')
  if signal!=9:
   end=only([r for r in sent if (r['actor'],r['ordinal'])==(who,send['ordinal'])],'successful send');require(send['position']<end['position'],'send completion edge')
 for who in (9,8):require([r['ordinal'] for r in sends if r['actor']==who]==list(range(sum(r['actor']==who for r in sends))),'sender ordinal')
 # Original, temporary and action masks are distinct and independently asserted.
 actions=[(r['signal'],r['kind']) for r in part if r['tag']=='ACTION'];expected_actions=[(v,2) for v in sigs]
 if not f and c in (7,24,25,26):expected_actions.append((sigs[0],1))
 if not f and c==8:expected_actions.append((sigs[0],0))
 if not f and c==27:expected_actions.append((sigs[1],1))
 if c==(9 if f else 18):expected_actions.extend(((sigs[4],0),(sigs[4],1)))
 if f and c in (7,8,10):expected_actions.append((sigs[0],1))
 if f and c==13:expected_actions.append((sigs[4],1))
 require(actions==expected_actions,'signal disposition sequence')
 masks=[(r['actor'],r['bits']) for r in part if r['tag']=='MASK'];expected_masks=[(9,31)]
 if not f and c in (17,18):expected_masks.extend(((0,29 if c==17 else 15),(0,31)))
 if not f and c==26:expected_masks.extend(((9,30),(9,31)))
 require(masks==expected_masks,'explicit mask transitions')
 handlers=[r for r in part if r['tag']=='HANDLE'];hplan=[]
 if not f and c==17:hplan=[(0,sigs[1],-6,31,29)]
 if f and c not in (0,1,14,15):
  who=9 if c<5 else 0;signal=sigs[1] if c in (7,8,10) else sigs[0];code=0 if c in (3,4,6) else -6;live=31 if c==4 else 13 if c==9 else 30 if signal==sigs[1] else 29
  hplan=[(who,signal,code,live,31)]*(2 if c==9 else 1)
 require(len(handlers)==len(hplan),'handler count')
 for h,e in zip(handlers,hplan):
  who,signal,code,live,saved=e;require((h['actor'],h['signal'],h['code'],h['live'],h['saved'],h['pid'],h['tid'],h['sender'],h['uid'],h['result'])==(who,signal,code,live,saved,pid,actors[who],pid,uid,-4),'handler source or live/saved mask')
  if not a:require(h['pc']==child['resume'],'raw signal continuation')
  if arch.startswith('mips'):require(h['abi']==1,'MIPS error indicator')
  elif arch=='ppc':require(h['abi']&0x10000000,'PPC error SO')
  elif arch=='arm32' and not a:require(bool(h['abi']&32)==bool(form),'ARM execution state')
 if passes:
  q=passes[0];require(q['pid']==pid and [q['handlers'+str(i)] for i in (0,1,9)]==[sum(h['actor']==i for h in handlers) for i in (0,1,9)],'final handler totals')
 # Pending observations include the state before dequeue, destructive faults,
 # ignored drains while owned, and both worker and leader cleanup boundaries.
 pending_plan={who:[] for who in actors};pending_plan[9]=[(0,31)]
 def pend(who,value,mask=31):pending_plan[who].append((value,mask))
 if f:
  if c in (0,1):pend(9,0)
  elif c in (2,3,4):pend(9,3 if c==4 else 1);pend(9,2 if c==4 else 0)
  elif c in (7,8,10):pend(9,0)
  elif c==9:
   for _ in range(2):pend(9,16);pend(9,0);pend(0,0)
 else:
  if c in (0,3,11,12):pend(9,0)
  elif c==1:pend(9,1);pend(9,1)
  elif c==2:
   for _ in range(1+(3 if arch in WORD32 else 4)):pend(9,1)
  elif c in (4,5):pend(9,1);pend(9,0)
  elif c==6:pend(9,1);pend(9,1);pend(9,3)
  elif c in (7,8):pend(9,1)
  elif c in (13,14,15):pend(0,0)
  elif c==16:pend(0,0);pend(1,0)
  elif c==18:
   for _ in range(4):pend(9,0)
  elif c==21:pend(9,4)
  elif c in (22,23):pend(9,12)
  elif c==26:pend(9,0,30)
  elif c==27:pend(0,2);pend(0,0)
 if not fatal and not replaced:
  for who in range(expected_threads):
   if not (f and c==16):pend(who,0)
  pend(9,0)
 for who,values in pending_plan.items():
  stream=[r for r in part if r['tag']=='PENDING' and r['actor']==who]
  require([(r['bits'],r['mask']) for r in stream]==values and [r['ordinal'] for r in stream]==list(range(len(values))),'pending queue observations')
 require(all(r['actor'] in actors for r in part if r['tag']=='PENDING'),'foreign pending observer')
 awaited=[r for r in part if r['tag']=='AWAIT'];await_plan=[]
 if f and c>=5:
  if c==9:await_plan=[(0,0),(0,1),(0,0),(0,1)]
  else:await_plan=[(0,0)]+([(0,1)] if c in (7,8,10) else [])
 elif not f and c>=13 and c not in (21,22,23):
  if c==16:
   winner=only([r for r in events if r['tag_value']=='WINNER'],'shared recipient');require(winner['value'] in (0,1) and winner['extra']==sigs[0],'shared winner identity');await_plan=[(0,0),(1,0),(1-winner['value'],1)]
   first=only([r for r in returns if r['actor']==winner['value'] and r['value']==sigs[0]],'winner return');require(first['position']<winner['position'],'winner proof before announcement')
   require(sum(r['value']==sigs[0] for r in returns)==1 and sum(r['value']==sigs[1] for r in returns)==1,'one receiver per shared occurrence')
  elif c==18:await_plan=([(0,0),(0,1)]+([(0,2)] if a else []))*2
  elif c==30:await_plan=[(0,0),(1,0),(0,1)]
  else:await_plan=[(0,0)]+([(0,1)] if c in (26,27) or c==17 and a else [])
 require([(r['target'],r['phase']) for r in awaited]==await_plan,'exact deferred await plan')
 linux_waits=[r for r in part if r['tag']=='LINUX_WAIT']
 require(len(linux_waits)==(len(awaited) if linux else 0),'reference syscall observations')
 for observed,awaited_row in zip(linux_waits,awaited):
  require((observed['target'],observed['phase'],observed['tid'])==(awaited_row['target'],awaited_row['phase'],awaited_row['tid']) and observed['position']<awaited_row['position'],'reference syscall observation edge')
  invocation=[r for r in calls if r['actor']==observed['target'] and r['position']<observed['position']][-1]
  require(observed['syscall']==invocation['syscall'],'reference blocked syscall number')
  if not a:require(observed['set']==invocation['set'] and observed['pc']==invocation['resume'],'reference raw blocked arguments')
 event_counts=Counter({'WAIT_CHECKED':len(returns),'RAW_SHARED_RETRY':len(retries),'HANDLER_RETURN':len(handlers)-int(f and c in (13,16)),
  'JOIN':0 if fatal or replaced else expected_threads,'THREAD_EXIT':0 if fatal or replaced else expected_threads-int(f and c==16),
  'EXEC_COMMIT':int(bool(replaced))})
 guards=len(returns)
 if not f:
  guards-={3:2,9:1,10:1,11:1,12:1}.get(c,0)
 event_counts['INFO_GUARDS']=guards
 mapped=(f and c in (1,11)) or (not f and c in (0,12,19))
 if mapped:event_counts.update({'MAP':1,'PROTECT':1,'UNPROTECT':1,'UNMAP':1})
 if not f:
  for case,tag,count in ((5,'SENDER_EXIT',1),(5,'CHILD_REAP',1),(12,'STRADDLE_GUARDS',1),(16,'WINNER',1),(18,'IGNORED_DROP_OBSERVED',2),(18,'IGNORED_INTERRUPT_OBSERVED',2),(19,'MUTATE_SET',1),(20,'MUTATE_TIMEOUT',1),(21,'SENDER_EXIT',3),(21,'CHILD_REAP',3),(30,'FORK_EMPTY',1),(30,'FORK_REAP',1),(31,'HUGE_TIMEOUT',1)):
   if c==case:event_counts[tag]=count
 else:
  for case,tag,count in ((7,'SUSPEND_IGNORED_DROP',1),(8,'SUSPEND_IGNORED_DROP',1),(9,'IGNORED_DRAIN_OWNED',2),(10,'SUSPEND_IGNORED_DROP',1),(11,'MUTATE_SET',1),(12,'HANDLER_REAP',1),(16,'HANDLER_EXIT',1),(16,'HANDLER_EXIT_NO_RETURN',1)):
   if c==case:event_counts[tag]=count
 require(Counter(r['tag_value'] for r in events)==+event_counts,'event proof cardinality')
 for event in events:
  if event['tag_value']=='INFO_GUARDS':
   result=only([r for r in returns if (r['actor'],r['ordinal'])==(event['actor'],event['value'])],'guard-associated return');require(event['extra']==16 and result['position']<event['position'],'guard check order/value')
  if event['tag_value']=='JOIN':require(event['actor']==9 and event['value'] in actors and event['extra']==actors[event['value']],'joined worker identity')
 for who in (0,1,9):require([r['ordinal'] for r in handlers if r['actor']==who]==list(range(sum(r['actor']==who for r in handlers))),'handler ordinal')
 forked=[r for r in part if r['tag']=='HANDLER_FORK'];require(len(forked)==int(f and c==12),'handler fork cardinality')
 if forked:require((forked[0]['parent'],forked[0]['mask'],forked[0]['pending'])==(pid,29,0),'handler fork inherits live mask')
 # Every worker operation is causally bracketed. Exec/kill/handler exit may
 # deliberately retire an unfinished command, but no other ACK can disappear.
 commands=[r for r in part if r['tag']=='COMMAND'];acks=[r for r in part if r['tag']=='ACK'];done=[r for r in part if r['tag']=='COMMAND_DONE']
 for who in range(expected_threads):
  expected_commands=[]
  if not f and c in (17,18):expected_commands.append((1,29 if c==17 else 15))
  if not f and c==27:expected_commands.append((2,2))
  if replaced and who==1:expected_commands.append((5,31))
  elif f and c==9:expected_commands.extend(((3,0),(2,0),(3,0),(2,0)))
  else:
   expected_commands.append((3,0))
   if not f and c==18:expected_commands.append((3,0))
   if not f and c in (13,14,15,16,27):expected_commands.append((2,0))
  if not f and c in (17,18):expected_commands.append((1,31))
  if not fatal and not replaced and not (f and c==16):expected_commands.extend(((2,0),(4,0)))
  require([(r['operation'],r['argument']) for r in commands if r['target']==who]==expected_commands,'exact worker command plan')
 assigned_ack=set();assigned_done=set()
 for who in range(expected_threads):
  stream=[r for r in commands if r['target']==who];require([r['seq'] for r in stream]==list(range(1,len(stream)+1)),'command sequence')
  previous=-1
  for command in stream:
   require(command['operation'] in range(1,6) and command['position']>previous,'command ownership')
   ack=[r for r in acks if (r['actor'],r['seq'])==(who,command['seq'])];end=[r for r in done if (r['target'],r['seq'])==(who,command['seq'])]
   abandoned=command['operation']==5 or command['operation']==3 and (fatal or replaced or f and c==16)
   require(len(ack)==int(not abandoned and command['operation']!=4) and len(end)==int(not abandoned),'command terminal cardinality')
   if end:
    q=end[0];assigned_done.add(q['position']);require((q['operation'],q['argument'])==(command['operation'],command['argument']) and q['position']>command['position'],'command terminal identity');previous=q['position']
   if ack:
    q=ack[0];assigned_ack.add(q['position']);require((q['operation'],q['argument'])==(command['operation'],command['argument']) and command['position']<q['position']<end[0]['position'],'worker ACK identity/edge')
   if command['operation'] in (1,2,3):
    tag={1:'MASK',2:'PENDING',3:'BEGIN'}[command['operation']];inside=[r for r in part if r['tag']==tag and r['actor']==who and command['position']<r['position']<(end[0]['position'] if end else parent['position'])]
    require(bool(inside) if tag=='BEGIN' else len(inside)==1,'command lacks actual worker operation')
 require(len(assigned_ack)==len(acks) and len(assigned_done)==len(done),'orphan command terminal')
 for awaited in [r for r in part if r['tag']=='AWAIT']:
  require(awaited['target'] in actors and awaited['tid']==actors[awaited['target']],'await identity')
  prior=[r for r in calls if r['actor']==awaited['target'] and r['position']<awaited['position']];require(bool(prior),'await before invocation')
  require(not any(r['actor']==prior[-1]['actor'] and r['ordinal']==prior[-1]['ordinal'] and r['position']<awaited['position'] for r in returns),'await after return')
 if not linux:require(not any(r['tag']=='LINUX_WAIT' for r in part),'host proof in native command')
 return {'key':key(begin),'pid':pid,'invocations':len(calls),'handlers':len(handlers),'sends':len(sends),'exec':int(bool(fresh)),'fatal':int(fatal)}

def validate_cases(raw,arch,linux=False):
 rows=parse(raw,arch);start=only([r for r in rows if r['tag']=='START'],'command start');end=only([r for r in rows if r['tag']=='PASS'],'command completion')
 require(rows[0] is start and rows[-1] is end,'command record boundaries');forms=2 if arch in ('arm32','ppc') else 1;begin_time=1 if arch=='rv32' else 0;end_time=2 if arch in WORD32-{'rv32'} or arch=='rv32' else 1
 require((start['pointer_bits'],start['raw_forms'],start['raw_time_begin'],start['raw_time_end'])==(32 if arch in WORD32 else 64,forms,begin_time,end_time),'profile matrix header')
 begins=[r for r in rows if r['tag']=='CASE_BEGIN'];parents=[r for r in rows if r['tag']=='PARENT_PASS'];skips=[r for r in rows if r['tag']=='EXCLUDED'];matrix=list(combinations(arch));expected=[k for k in matrix if not linux or k[0] or k[-1] not in (22,23)]
 require([key(r) for r in begins]==expected==[key(r) for r in parents],'exact case matrix');require([key(r) for r in skips]==[k for k in matrix if k not in expected],'explicit reference exclusions')
 require((end['cases'],end['excluded'],end['semantic_cases'])==(len(expected),len(skips),49),'command completion counts')
 result=[];previous=start['position'];assigned={start['position'],end['position'],*(r['position'] for r in skips)}
 for begin,parent in zip(begins,parents):
  require(previous<begin['position']<parent['position']<end['position'] and begin['parent']==start['pid'],'serial parent/child boundary');previous=parent['position'];result.append(_case(rows,begin,parent,arch,linux));assigned.update(r['position'] for r in rows if begin['position']<=r['position']<=parent['position'])
 require(assigned=={r['position'] for r in rows},'record outside owned case')
 return {'cases':len(result),'excluded':len(skips),'semantic_cases':49,'invocations':sum(r['invocations'] for r in result),'handlers':sum(r['handlers'] for r in result),'sends':sum(r['sends'] for r in result),'exec_images':sum(r['exec'] for r in result),'results':result}
