"""Guest byte/ABI protocol shared by explicitly separated native and host reference collectors."""
import re
from native_pipe_vector_events import READV,WRITEV,WORD32,instruction
from native_signal_delivery_x86_64_evidence import IMAGE
KEY=rb'arch=([a-z0-9_]+) direction=([01]) variant=([01]) form=([01]) restart=([01]) case=([0-9]|[12][0-9]|3[0-5])'
BEGIN=re.compile(rb'PIPE_VECTOR_CASE_BEGIN '+KEY+rb' pid=([0-9]+) tid=([0-9]+) fd=([0-9]+) readfd=(-?[0-9]+) writefd=(-?[0-9]+) replacement=(-?[0-9]+) replacementread=(-?[0-9]+) nestedfd=(-?[0-9]+) nestedread=(-?[0-9]+) array=([0-9]+) nestedarray=([0-9]+) count=([0-9]+) iovcnt=([0-9]+) site=([0-9]+) resume=([0-9]+) syscall=([0-9]+) uid=([0-9]+) capacity=4096')
ENTRY=re.compile(rb'PIPE_VECTOR_ENTRY '+KEY+rb' role=([012]) index=([0-9]|1[0-5]) base=([0-9]+) length=([0-9]+)')
ATTEMPT=re.compile(rb'PIPE_VECTOR_ATTEMPT '+KEY+rb' actor=0 pid=([0-9]+) tid=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+) a4=([0-9]+) a5=([0-9]+)')
EVENT=re.compile(rb'PIPE_VECTOR_(RETURN|ERRNO|RETRY|RETRY_RETURN|NEST_SEND|NEST_ATTEMPT|NEST_EINTR|NEST_RETRY|NEST_RETURN|MUTATE_VECTOR|MUTATE_LENGTH|MUTATE_INPUT|PROTECT_VECTOR|REPLACE_FD|PROTECT_NONE|FAULT_UNTOUCHED|RESTORE_INPUT|CHANGE_ACTION|EXIT_GROUP|CLOSE_PEER|SEND|PAYLOAD_BEGIN|READY_BEGIN|READY_END|ATOMIC_PENDING|PENDING|UNMASK|EMPTY|EXEC_FAILED|EXEC_COMMIT|EXEC_REPLACED|EXEC_BYTE|EXEC_CHECKED) '+KEY+rb' actor=([09]) ordinal=([012]) value=(-?[0-9]+)')
HANDLER=re.compile(rb'PIPE_VECTOR_(HANDLE|HANDLER_RETURN|NESTED|THREAD_EXIT|HANDLER_EXEC) '+KEY+rb' actor=0 pid=([0-9]+) tid=([0-9]+) depth=([12]) inspected=([01]) pc=([0-9]+)(?: number=([0-9]+) result=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+)(?: cr=([0-9]+) diagnostic_result=([0-9]+) orig_r3=([0-9]+)| cpsr=([0-9]+))?)?')
PAYLOAD=re.compile(rb'PIPE_VECTOR_PAYLOAD '+KEY+rb' actor=9 pipe=([012]) segment=([01]) bytes=([0-9]+) value=([0-9]+)')
BUFFER=re.compile(rb'PIPE_VECTOR_BUFFER '+KEY+rb' actor=9 role=([012]) segment=([01]) base=([0-9]+) bytes=([0-9]+) value=([0-9]+) guards=1')
END=re.compile(rb'PIPE_VECTOR_CASE_PASS '+KEY)
PARENT=re.compile(rb'PIPE_VECTOR_PARENT_PASS '+KEY+rb' pid=([0-9]+) signal=([0-9]+)')
LINUX_WAIT=re.compile(rb'PIPE_VECTOR_LINUX_WAIT '+KEY+rb' actor=0 phase=([023]) pid=([0-9]+) tid=([0-9]+) syscall=([0-9]+)')
LINUX_SKIP=re.compile(rb'PIPE_VECTOR_LINUX_SKIP '+KEY+rb' reason=(native-iov-max-sixteen|native-overflow-before-payload-validation|native-eager-mapping-validation|native-whole-vector-mapping-revalidation)')
PATTERNS=(BEGIN,ENTRY,ATTEMPT,EVENT,HANDLER,PAYLOAD,BUFFER,END,PARENT)
GUEST_PREFIX=b'PIPE_VECTOR_'

def parse(pattern,line,position):
 if not pattern.fullmatch(line):raise ValueError('malformed vector guest marker')
 row=dict(tag=line.split()[0].decode().removeprefix('PIPE_VECTOR_'),line=line,position=position)
 for field in line.split()[1:]:
  k,v=field.decode().split('=',1);row[k]=v if k in ('arch','reason') else int(v)
 return row

def validate_cases(span,arch,native=None,linux=False):
 if arch not in READV or linux and arch!='x86_64':raise ValueError('unsupported vector guest profile/reference')
 if (native is None)!=linux:raise ValueError('native and Linux evidence must be explicitly distinct')
 lines=span.splitlines();keys=[(d,v,f,r,c) for d in range(2) for v in range(2) for f in range(1 if v else 2 if arch in ('arm32','ppc') else 1) for r in range(2) for c in range(36) if not(linux and (c in (27,28,31,35)))]
 begins=[i for i,l in enumerate(lines) if BEGIN.fullmatch(l)];parents=[i for i,l in enumerate(lines) if PARENT.fullmatch(l)]
 if len(begins)!=len(keys) or len(parents)!=len(keys):raise ValueError('vector cases or parent status missing')
 maximum=(1<<(32 if arch in WORD32 else 64))-1;low,high=(0,maximum+1) if linux else (0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000);usr1,usr2=(16,17) if arch.startswith('mips') else (10,12);mips=arch.startswith('mips')
 claimed=set();kernel_claimed=set();owners=set();stats=dict(cases=0,groups=8 if linux else len(keys)//36,initial_waits=0,fresh_waits=0,rearms=0,interruptions=0,restarts=0,eintr=0,payload_records=0,payload_bytes=0,buffer_records=0,exec_replacements=0,observed_Linux_waits=0)
 for index,((direction,variant,form,restart,case),first,last) in enumerate(zip(keys,begins,parents)):
  if first>=last or index and first<=parents[index-1]:raise ValueError('overlapping vector cases')
  rows=[]
  for pos in range(first,last+1):
   line=lines[pos]
   if GUEST_PREFIX in line and b'OK_NATIVE_' not in line:
    pattern=next((p for p in PATTERNS+((LINUX_WAIT,) if linux else ()) if p.fullmatch(line)),None)
    if pattern is None:raise ValueError('unknown/malformed vector guest record')
    r=parse(pattern,line,pos)
    if tuple(r[k] for k in ('arch','direction','variant','form','restart','case'))!=(arch,direction,variant,form,restart,case):raise ValueError('vector event changed active case')
    rows.append(r);claimed.add(pos)
  def tagged(tag):return [r for r in rows if r['tag']==tag]
  def one(tag):
   found=tagged(tag)
   if len(found)!=1:raise ValueError('vector event missing/duplicate: '+tag)
   return found[0]
  def action(tag,value,actor=9,ordinal=0):
   r=one(tag)
   if (r['actor'],r['ordinal'],r['value'])!=(actor,ordinal,value):raise ValueError('vector action identity/value differs: '+tag)
   return r
  def ordered(*records):
   positions=[r['position'] for r in records]
   if positions!=sorted(set(positions)):raise ValueError('vector causal order differs: '+','.join(str(r.get('tag')) for r in records))
  b=one('CASE_BEGIN');pid,tid=b['pid'],b['tid'];fd,array,count=b['fd'],b['array'],b['count'];nvec=b['iovcnt'];op=(WRITEV if direction else READV)[arch];width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
  want_count=4096 if case==12 else 4097 if case in (13,34) else 32;want_nvec=0 if case==25 else 17 if case==27 else 2 if case==28 else maximum if case==29 else 16 if case==32 else 3
  if (pid in owners or not 0<pid<=0xffffffff or not 0<tid<=0xffffffff or tid==pid or not 3<=fd<=(0x7fffffff if linux else 31) or count!=want_count or nvec!=want_nvec or b['syscall']!=op or not 0<=b['uid']<=0xffffffff or not low+57344<=array<=high-8192 or array%4096 or not low<=b['site']<high or b['resume']-b['site']!=width or not instruction(arch,b['site'],bool(form)) or not instruction(arch,b['resume'],bool(form))):raise ValueError('invalid vector begin identity/layout/ABI')
  owners.add(pid);base=array-57344;part=lambda role,seg:base+role*16384+seg*8192+64
  sizes=lambda role:(3,5) if role else (2048,count-2048) if count>32 else (13,19)
  values=lambda role:(81,82) if role==2 else (97,98) if role==1 else (90,91) if case==2 else (65,66)
  entries={role:[r for r in tagged('ENTRY') if r['role']==role] for role in range(3)}
  shapes={}
  for role in range(3):
   total=3 if role==2 and case==17 else 0 if role==2 else 2 if role==0 and case==28 else 16 if case==32 else 3
   expected=[(1,0)]*max(0,total-2)+[(part(role,j),sizes(role)[j]) for j in range(2)] if total else []
   if role==0 and case==26:expected=[(1,0)]*3
   if role==0 and case==28:expected=[(part(0,0),maximum//2),(part(0,1),1)]
   if [(r['index'],r['base'],r['length']) for r in entries[role]]!=[(i,p,n) for i,(p,n) in enumerate(expected)]:raise ValueError('vector announcement changed copied segment layout')
   shapes[role]=tuple(expected)
  if any(not -1<=b[k]<=(0x7fffffff if linux else 31) for k in ('readfd','writefd','replacement','replacementread','nestedfd','nestedread')):raise ValueError('vector descriptor exceeds selected execution table')
  if (direction and b['writefd']!=fd or not direction and case not in (5,6) and b['readfd']!=fd or case==11 and b['readfd' if direction else 'writefd']!=-1 or case!=11 and (b['readfd']<3 or b['writefd']<3 or b['readfd']==b['writefd'])):raise ValueError('vector original pipe topology differs')
  if case in (5,6):
   topology={fd,b['readfd'],b['replacement'],b['replacementread']} if direction else {fd,b['readfd'],b['writefd'],b['replacement']}
   if b['replacement']<3 or b['replacementread']<3 or len(topology)!=4 or not direction and b['replacement']!=b['replacementread']:raise ValueError('vector retained/replacement pipe topology differs')
  elif (b['replacement'],b['replacementread'])!=(-1,-1):raise ValueError('unexpected vector replacement pipe')
  if case==17:
   if b['nestedfd']<3 or b['nestedread']<3 or (len({fd,b['readfd'],b['nestedfd'],b['nestedread']})!=4 if direction else len({fd,b['writefd'],b['nestedfd']})!=3) or b['nestedarray']!=array+4096 or not direction and b['nestedfd']!=b['nestedread']:raise ValueError('invalid nested vector topology')
  elif (b['nestedfd'],b['nestedread'],b['nestedarray'])!=(-1,-1,0):raise ValueError('unexpected nested vector topology')
  parent=one('PARENT_PASS')
  if (parent['pid'],parent['signal'])!=(pid,usr1 if case==20 else 0):raise ValueError('vector parent child/status differs')
  caught=case in (0,6,14,15,16,17,18,19,23);again=bool(1-restart if case==15 else restart);pending=8<=case<=11;immediate=case in (9,10,11,13) or 25<=case<=31;edited=case==18 and not variant and again;has_return=case not in (19,20,21,22,23);retry=case in (3,35) or caught and case not in (19,23) and (not again or edited);normal=case not in (20,21,22,23);success=normal and case not in (10,11,19,24) and not 25<=case<=31
  amount=8 if case==14 else 17 if not direction and case in (9,13) else count if direction and case==34 else min(count,4096)
  ready_cases=(0,1,2,3,4,5,7,8,12,14,15,16,17,18,32,33,34,35)
  post_ready=bool(direction and (case in (6,10,19) or 25<=case<=31))
  ready_pairs=[(0,14096 if direction else 10008),(0,4096 if direction else amount)] if case==17 else [(0,1),(1,4095)] if case==12 and direction else [(0,4096 if direction else amount)] if case in ready_cases or post_ready else []
  payload_specs=[]
  if direction and success:payload_specs.append((2 if case==6 else 0,amount,1 if case==14 else 0))
  if direction and case==17:payload_specs.append((1,8,2))
  if not direction and case==5:payload_specs.append((2,count,0))
  payload_expected=[]
  for pipe,bytes_,role in payload_specs:
   n=min(bytes_,sizes(role)[0]);payload_expected.extend([(pipe,0,n,values(role)[0]),(pipe,1,bytes_-n,values(role)[1])])
  if direction and case==34:payload_expected=[(0,0,2048,65),(0,1,2048,66),(0,1,1,66)]
  empties=[(0,b['readfd'])]*(2 if case in (22,23) else 0 if case in (11,20,21,24) else 1)+([(1,b['nestedread'])] if case==17 else [])+([(2,b['replacementread'])] if case in (5,6) else [])
  expected=dict(CASE_BEGIN=1,ENTRY=sum(map(len,entries.values())),ATTEMPT=1,PARENT_PASS=1,CASE_PASS=int(normal),RETURN=int(has_return),ERRNO=int(has_return),RETRY=int(retry),RETRY_RETURN=int(retry),HANDLE=int(caught or pending),HANDLER_RETURN=int(caught and case not in (19,23) or pending),NESTED=int(case in (16,17)),THREAD_EXIT=int(case==19),HANDLER_EXEC=int(case==23),NEST_SEND=int(case==16),NEST_ATTEMPT=int(case==17),NEST_EINTR=int(case==17),NEST_RETRY=int(case==17),NEST_RETURN=int(case==17),SEND=int(caught or pending or case in (7,20))+int(case==17),MUTATE_VECTOR=int(case in (1,14)),MUTATE_LENGTH=int(case==33),MUTATE_INPUT=int(case==2),PROTECT_VECTOR=int(case==4),REPLACE_FD=int(case in (5,6)),PROTECT_NONE=int(case in (3,35)),FAULT_UNTOUCHED=int(case==35),RESTORE_INPUT=int(case in (3,35)),CHANGE_ACTION=int(case==15),EXIT_GROUP=int(case==21),CLOSE_PEER=int(case==24),PAYLOAD_BEGIN=int(direction and case==34),READY_BEGIN=len(ready_pairs),READY_END=len(ready_pairs),ATOMIC_PENDING=int(case==12 and direction),PENDING=int(pending),UNMASK=int(pending),PAYLOAD=len(payload_expected),BUFFER=6*int(normal),EMPTY=len(empties),EXEC_FAILED=int(case in (22,23)),EXEC_COMMIT=int(case in (22,23)),EXEC_REPLACED=int(case in (22,23)),EXEC_BYTE=int(case in (22,23)),EXEC_CHECKED=int(case in (22,23)))
  if linux:expected['LINUX_WAIT']=0 if immediate else 3 if case==17 else 1
  if any(len(tagged(k))!=n for k,n in expected.items()) or any(r['tag'] not in expected for r in rows):raise ValueError('vector event cardinality differs '+str((direction,variant,form,restart,case))+': '+str({k:(n,len(tagged(k))) for k,n in expected.items() if n!=len(tagged(k))}))
  att=one('ATTEMPT')
  if (att['pid'],att['tid'])!=(pid,tid) or [att['a'+str(i)] for i in range(6)]!=[fd,array,nvec,4951,0,0]:raise ValueError('vector attempted syscall arguments differ')
  ordered(b,att,parent)
  for entry in tagged('ENTRY'):ordered(b,entry,att)
  sends=tagged('SEND')
  for i,r in enumerate(sends):
   if (r['actor'],r['ordinal'],r['value'])!=(9,0,usr2 if i else usr1):raise ValueError('vector signal target differs')
  for tag,value in [('MUTATE_VECTOR',1),('MUTATE_LENGTH',0),('MUTATE_INPUT',90),('PROTECT_VECTOR',0),('PROTECT_NONE',0),('RESTORE_INPUT',0),('REPLACE_FD',b['replacement']),('CHANGE_ACTION',1-restart),('EXIT_GROUP',0),('CLOSE_PEER',b['readfd' if direction else 'writefd']),('ATOMIC_PENDING',1)]:
   if tagged(tag):action(tag,value)
  starts,ends=tagged('READY_BEGIN'),tagged('READY_END')
  for begin,end,(ordinal,value) in zip(starts,ends,ready_pairs):
   if (begin['actor'],begin['ordinal'],begin['value'],end['actor'],end['ordinal'],end['value'])!=(9,ordinal,value,9,ordinal,value):raise ValueError('vector readiness action wrong role/count')
   ordered(begin,end)
  if pending:action('PENDING',1,0);action('UNMASK',0,0);ordered(sends[0],att,one('RETURN'),one('ERRNO'),one('PENDING'),one('UNMASK'),one('HANDLE'),one('HANDLER_RETURN'))
  for c,tag in ((1,'MUTATE_VECTOR'),(2,'MUTATE_INPUT'),(3,'PROTECT_NONE'),(4,'PROTECT_VECTOR'),(5,'REPLACE_FD'),(33,'MUTATE_LENGTH'),(35,'PROTECT_NONE')):
   if case==c:ordered(att,one(tag),starts[0])
  if case in (6,14,15):ordered(att,one({6:'REPLACE_FD',14:'MUTATE_VECTOR',15:'CHANGE_ACTION'}[case]),sends[0])
  if case==7:ordered(sends[0],starts[0])
  if case==12 and direction:ordered(starts[0],one('ATOMIC_PENDING'),starts[1])
  error=14 if case in (3,35,30,31) else 11 if case==10 else 22 if 27<=case<=29 else 32 if direction and case in (11,24) else 4
  result=77 if edited else (-1 if variant else -4) if caught and not again else (-1 if variant else -error) if case in (3,35,10,30,31) or 27<=case<=29 or direction and case in (11,24) else 0 if case in (25,26) or not direction and case in (11,24) else amount
  if has_return:action('RETURN',result,0);action('ERRNO',error if variant and result==-1 else 111,0);ordered(att,one('RETURN'),one('ERRNO'))
  if retry:action('RETRY',fd,0,1);action('RETRY_RETURN',amount,0,1);ordered(one('ERRNO'),one('RETRY'),one('RETRY_RETURN'))
  if case in (3,35):ordered(one('RETURN'),one('RESTORE_INPUT'),one('RETRY'))
  if case==35:action('FAULT_UNTOUCHED',0 if direction else 13);ordered(one('RETURN'),one('FAULT_UNTOUCHED'),one('RESTORE_INPUT'))
  if caught:
   finish=one('THREAD_EXIT' if case==19 else 'HANDLER_EXEC' if case==23 else 'HANDLER_RETURN');ordered(sends[0],one('HANDLE'),finish)
   if has_return:ordered(finish,one('RETURN'))
   if case not in (6,19,23):ordered(one('RETRY') if retry else finish,starts[-1])
   if case==16:action('NEST_SEND',usr2,0);ordered(one('HANDLE'),one('NEST_SEND'),one('NESTED'),finish)
   if case==17:
    action('NEST_ATTEMPT',b['nestedfd'],0);action('NEST_EINTR',-4,0);action('NEST_RETRY',b['nestedfd'],0,1);action('NEST_RETURN',8,0,1);ordered(one('HANDLE'),one('NEST_ATTEMPT'),sends[1],one('NESTED'),one('NEST_EINTR'),one('NEST_RETRY'),starts[0],one('NEST_RETURN'),finish)
  stream=[] if linux else [r for r in native if first<=r['position']<=last and r['vector']]
  kernel_claimed.update(r['position'] for r in stream)
  arms=[r for r in stream if r['event']=='WAIT' and r['stage']=='arm'];rearms=[r for r in stream if r['event']=='WAIT' and r['stage']=='rearm'];terms=[r for r in stream if r['event']=='COMPLETE'];origins=[r for r in stream if r['event']=='ORIGIN'];signals=[r for r in stream if r['event']=='SIGNAL']
  if not linux:
   expected_arms=0 if immediate else 4 if case==17 else 2 if caught and case not in (6,19,23) else 1
   if len(arms)!=expected_arms or len(origins)!=expected_arms or len(terms)!=expected_arms or len(rearms)!=int(case in (5,6) or direction and case in (12,34)) or len(signals)!=int(caught)+int(case==17):raise ValueError('vector owned wait topology differs')
   if any(bool(r.get('large'))!=bool(direction and case==34) for r in stream):raise ValueError('vector scenario has wrong LARGE namespace')
   if direction and case==34:
    if [r['committed'] for r in arms+origins]!=[0,0] or [r['committed'] for r in rearms]!=[4096] or [r['committed'] for r in terms]!=[4097]:raise ValueError('vector large write cursor differs')
    ordered(starts[0],rearms[0],terms[0]);ordered(ends[0],one('PAYLOAD_BEGIN'),terms[0]);ordered(rearms[0],tagged('PAYLOAD')[0])
   if any((r['pid'],r['tid'],r['direction'])!=(pid,tid,direction) for r in stream):raise ValueError('vector diagnostics changed owner/direction')
   if arms:ordered(att,arms[0]);stats['initial_waits']+=1;stats['fresh_waits']+=len(arms)-1
   stats['rearms']+=len(rearms)
   for i,arm in enumerate(arms):
    nested=case==17 and i in (1,2);role=2 if nested else 1 if case==14 and i>0 else 0;wanted=(b['nestedfd'],b['nestedarray'],8,3) if nested else (fd,array,8 if role==1 else min(count,4097 if direction else 4096),nvec)
    if (arm['fd'],arm['array'],arm['bytes'],arm['iovcnt'])!=wanted or arm['vectors']!=shapes[role]:raise ValueError('vector kernel copied wrong original/fresh descriptor snapshot')
    origin=next(r for r in origins if r['request']==arm['request']);prior=arms[1] if nested else arms[0]
    if (not variant or nested) and origin['pc']!=b['resume']:raise ValueError('vector raw origin differs from exact trap return label')
    if (arm['description'],arm['pipe'])!=(prior['description'],prior['pipe']) or nested and (arm['description']==arms[0]['description'] or arm['pipe']==arms[0]['pipe']):raise ValueError('vector operation changed retained pipe description')
    terminal=next(r for r in terms if r['request']==arm['request']);interrupted=i==0 and caught or case==17 and i==1
    outcome='interrupted' if interrupted else 'cancelled' if case in (20,21,22) else 'efault' if case in (3,35) else ('error' if direction else 'eof') if case==24 else 'ready'
    value=(0 if again and i==0 else -4) if interrupted else -125 if outcome=='cancelled' else -14 if outcome=='efault' else -32 if outcome=='error' else 0 if outcome=='eof' else 8 if nested else amount
    if (terminal['outcome'],terminal['result'])!=(outcome,value):raise ValueError('vector owned terminal differs from scenario')
    if outcome in ('ready','efault'):ordered(starts[0] if nested or case!=17 else starts[1],terminal)
   for i,sig in enumerate(signals):
    redo=again and i==0
    if (sig['signal'],sig['outcome'])!=(usr2 if i else usr1,'restart' if redo else 'eintr'):raise ValueError('vector signal disposition differs')
    if (not variant or i) and sig['pc']!=(b['site'] if redo else b['resume']):raise ValueError('vector raw saved trap PC differs')
    ordered(sends[i],sig,one('NESTED') if i else one('HANDLE'));stats['interruptions']+=1;stats['restarts' if redo else 'eintr']+=1
   if arms and sends and not pending:ordered(arms[0],sends[0])
   for tag in ('MUTATE_VECTOR','MUTATE_LENGTH','MUTATE_INPUT','PROTECT_VECTOR','PROTECT_NONE','REPLACE_FD','CHANGE_ACTION','EXIT_GROUP','CLOSE_PEER'):
    if tagged(tag):ordered(arms[0],one(tag))
   if not post_ready:
    for i,start in enumerate(starts):ordered(arms[2] if case==17 and i==0 else arms[-1],start)
   if case==22:ordered(arms[0],one('EXEC_FAILED'))
   if case in (5,6):ordered(one('REPLACE_FD'),rearms[0],sends[0] if case==6 else starts[0],terms[0])
   if case==12 and direction:ordered(starts[0],rearms[0],one('ATOMIC_PENDING'),starts[1],terms[0])
   if case in (20,21,22,24):ordered(one({20:'SEND',21:'EXIT_GROUP',22:'EXEC_COMMIT',24:'CLOSE_PEER'}[case]),terms[0])
   if terms and has_return and not(caught and (not again or edited)):ordered(terms[-1],one('RETURN'))
   if retry and case not in (3,35,6):ordered(terms[-1],one('RETRY_RETURN'))
   if case in (3,35):ordered(terms[0],one('RETURN'))
   if caught and case not in (6,19,23):ordered(one('RETRY') if retry else finish,arms[-1],starts[-1])
   if case==17:ordered(one('NEST_ATTEMPT'),arms[1],sends[1],signals[1]);ordered(one('NEST_RETRY'),arms[2],starts[0],terms[2],one('NEST_RETURN'))
  else:
   waits=tagged('LINUX_WAIT');stats['observed_Linux_waits']+=len(waits)
   for r,phase in zip(waits,[0,2,3] if case==17 else [0]):
    if (r['actor'],r['phase'],r['pid'],r['tid'],r['syscall'])!=(0,phase,pid,tid,op):raise ValueError('Linux observed wait syscall/owner differs')
   if waits:
    ordered(att,waits[0])
    for tag in ('MUTATE_VECTOR','MUTATE_LENGTH','MUTATE_INPUT','PROTECT_VECTOR','PROTECT_NONE','REPLACE_FD','CHANGE_ACTION','EXIT_GROUP','CLOSE_PEER','EXEC_COMMIT'):
     if tagged(tag):ordered(waits[0],one(tag))
    if sends and not pending:ordered(waits[0],sends[0])
    if starts and not post_ready:ordered(waits[0],starts[0])
   if case==17:ordered(one('NEST_ATTEMPT'),waits[1],sends[1],one('NEST_RETRY'),waits[2],starts[0])
  for h in [r for r in rows if HANDLER.fullmatch(r['line'])]:
   nested=h['tag']=='NESTED';inspected=caught and not(nested and case==16);edit=h['tag']=='HANDLER_RETURN' and edited
   if (h['pid'],h['tid'],h['depth'],h['inspected'])!=(pid,tid,2 if nested else 1,int(inspected)) or not low<=h['pc']<high or not instruction(arch,h['pc']):raise ValueError('vector handler identity/depth/PC differs')
   basefields={'tag','line','position','arch','direction','variant','form','restart','case','actor','pid','tid','depth','inspected','pc'};extra={'number','result','a0','a1','a2','a3'}|({'cr','diagnostic_result','orig_r3'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set())
   if set(h)!=basefields|(extra if inspected else set()):raise ValueError('vector handler context field shape differs')
   if not inspected:continue
   redo=again and not nested;argfd=b['nestedfd'] if nested else fd;argarray=b['nestedarray'] if nested else array;argcount=3 if nested else nvec
   value=77 if edit else (op if arch in ('x86_64','i386') or mips else argfd) if redo else 4 if mips or arch=='ppc' else maximum-3
   nr=77 if edit and (arch in ('x86_64','i386') or mips) else op if redo or arch not in ('x86_64','i386') and not mips else value
   a0=value if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not redo or edit) else argfd
   if (h['number'],h['result'],h['a0'],h['a1'],h['a2'])!=(nr,value,a0,argarray,argcount):raise ValueError('vector saved syscall/result/array/iovcnt differs')
   if edit or not variant or nested:
    if h['pc']!=(b['resume'] if edit or not redo else b['site']):raise ValueError('vector raw context PC differs')
   elif not linux and h['pc']!=signals[0]['pc']:raise ValueError('vector libc context and kernel publication PC differ')
   a3=0 if mips and edit else 1 if mips and not redo else 4951 if not variant or nested else None
   if not 0<=h['a3']<=maximum or a3 is not None and h['a3']!=a3:raise ValueError('vector fourth register/error flag differs')
   if arch=='ppc' and (not 0<=h['cr']<=maximum or bool(h['cr']&0x10000000)==edit or h['diagnostic_result']!=(0x123 if edit else 0 if redo else maximum-3) or h['orig_r3']!=(0x234 if edit else argfd)):raise ValueError('vector PPC signal context differs')
   if arch=='arm32' and (not 0<=h['cpsr']<=maximum or h['cpsr']&0x0700ffdf!=0x10 or not instruction(arch,h['pc'],bool(h['cpsr']&0x20)) or (not variant or nested) and bool(h['cpsr']&0x20)!=bool(form)):raise ValueError('vector ARM saved instruction state differs')
   if arch=='arm32' and redo and not edit and not linux and signals[1 if nested else 0]['origin_record']['pc']-h['pc']!=(2 if h['cpsr']&0x20 else 4):raise ValueError('vector ARM saved width/origin differs')
   if h['tag']=='HANDLER_RETURN' and not edit and any(h[k]!=one('HANDLE')[k] for k in extra|{'pc'}):raise ValueError('vector unedited handler changed frame')
  if [(r['pipe'],r['segment'],r['bytes'],r['value']) for r in tagged('PAYLOAD')]!=payload_expected:raise ValueError('vector pipe reader observed wrong segment/order/data')
  if direction and case==34:
   action('PAYLOAD_BEGIN',4096);ordered(ends[0],one('PAYLOAD_BEGIN'),*tagged('PAYLOAD'));ordered(one('ERRNO'),tagged('PAYLOAD')[-1])
  stats['payload_records']+=len(payload_expected);stats['payload_bytes']+=sum(p[2] for p in payload_expected)
  buffers=[]
  for role in range(3):
   consumed=amount if not direction and success and role==(1 if case==14 else 0) else 8 if not direction and case==17 and role==2 else 0
   for seg,n in enumerate(sizes(role)):
    filled=n if direction else min(consumed,n);consumed-=min(consumed,n);buffers.append((role,seg,part(role,seg),filled,values(role)[seg],1))
  if [(r['role'],r['segment'],r['base'],r['bytes'],r['value'],r['guards']) for r in tagged('BUFFER')]!=(buffers if normal else []):raise ValueError('vector scatter/input buffer or guard proof differs')
  stats['buffer_records']+=6*int(normal)
  if [(r['ordinal'],r['value']) for r in tagged('EMPTY')]!=empties or any(r['actor']!=9 for r in tagged('EMPTY')):raise ValueError('vector empty proof ownership differs')
  if normal:
   worker_end=one('HANDLER_RETURN') if pending else one('RETRY_RETURN') if retry else one('ERRNO') if has_return else one('THREAD_EXIT')
   for proof in (tagged('PAYLOAD')[2:] if direction and case==34 else tagged('PAYLOAD'))+tagged('BUFFER')+tagged('EMPTY'):ordered(worker_end,proof,one('CASE_PASS'))
   if post_ready:ordered(worker_end,starts[0])
   if ends:
    for proof in tagged('PAYLOAD')+tagged('BUFFER')+tagged('EMPTY'):ordered(ends[-1],proof)
   if one('CASE_PASS')['position']!=max(r['position'] for r in rows if r['tag']!='PARENT_PASS'):raise ValueError('vector case pass precedes proof')
  images=[dict(position=i,tag='IMAGE') for i in range(first,last+1) if IMAGE.fullmatch(lines[i])]
  if case in (22,23):
   action('EXEC_FAILED',2,0 if case==23 else 9);action('EXEC_COMMIT',pid,0 if case==23 else 9);action('EXEC_REPLACED',pid);action('EXEC_BYTE',80);action('EXEC_CHECKED',pid)
   if case==23:ordered(one('HANDLE'),one('HANDLER_EXEC'),one('EXEC_FAILED'))
   ordered(one('EXEC_FAILED'),one('EXEC_COMMIT'),one('EXEC_REPLACED'),tagged('EMPTY')[0],one('EXEC_BYTE'),tagged('EMPTY')[1],one('EXEC_CHECKED'),parent)
   if not linux:
    if len(images)!=1:raise ValueError('vector exec lacks exact full image replacement')
    ordered(terms[0],images[0],one('EXEC_REPLACED'));ordered(one('EXEC_COMMIT'),images[0])
   stats['exec_replacements']+=1
  elif images:raise ValueError('unexpected vector image replacement')
  stats['cases']+=1
 if not linux and {r['position'] for r in native if r['vector']}!=kernel_claimed:raise ValueError('vector diagnostic escaped announced cases')
 if not linux and any(not r['vector'] and r['event']=='SIGNAL' for r in native):raise ValueError('scalar caught publication is not a vector scenario')
 native_marker=f'PIPE_VECTOR_PASS arch={arch} variants=2 groups={12 if arch in ("arm32","ppc") else 8} cases={432 if arch in ("arm32","ppc") else 288} parent=1'.encode()
 linux_marker=b'PIPE_VECTOR_LINUX_REFERENCE_PASS arch=x86_64 variants=2 groups=8 cases=256 parent=1'
 if sum(l==native_marker for l in lines)>int(not linux) or sum(l==linux_marker for l in lines)>int(linux):raise ValueError('duplicate/out-of-scope vector completion')
 for i,line in enumerate(lines):
  if GUEST_PREFIX in line and b'OK_NATIVE_' not in line and i not in claimed and not(not linux and line==native_marker) and not(linux and (LINUX_SKIP.fullmatch(line) or line==linux_marker)):raise ValueError('vector guest event escaped scenario')
 if linux:
  skips=[parse(LINUX_SKIP,l,i) for i,l in enumerate(lines) if LINUX_SKIP.fullmatch(l)]
  wanted=[('x86_64',d,v,0,r,c,{27:'native-iov-max-sixteen',28:'native-overflow-before-payload-validation',31:'native-eager-mapping-validation',35:'native-whole-vector-mapping-revalidation'}[c]) for d in range(2) for v in range(2) for r in range(2) for c in (27,28,31,35)]
  if [tuple(s[k] for k in ('arch','direction','variant','form','restart','case','reason')) for s in skips]!=wanted:raise ValueError('Linux reference exclusions differ')
  marker=f'PIPE_VECTOR_LINUX_REFERENCE_PASS arch={arch} variants=2 groups=8 cases=256 parent=1'.encode()
  if lines[-1:]!=[marker] or sum(l==marker for l in lines)!=1 or b'OK_NATIVE_' in span:raise ValueError('Linux reference pass/native scope differs')
 return stats
