"""Strict all-ten scalar pipe write guest collector; synthetic traces are not execution."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure,decode_frames
from entry_stack_evidence import decode_stacks,COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE,validate_command
from native_pipe_signal_evidence import native_events as read_events,PATTERNS as READ_PATTERNS
from native_futex_events import native_events as futex_events,final_snapshots,instruction,WORD32,PATTERNS as FUTEX_PATTERNS
from native_poll_events import native_events as poll_events,PATTERNS as POLL_PATTERNS
from native_child_events import normalize_transcript, WAIT as CHILD_WAIT, PATTERNS as CHILD_WAIT_PATTERNS
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
from native_pipe_write_events import WRITE,PREFIX as WRITE_PREFIX
from native_pipe_vector_events import native_events as shared_pipe_events,SCHEMAS
WRITE_PATTERNS=tuple(p for p,d,v,*_ in SCHEMAS if d and not v)

def write_events(span,arch,allow_signal=False):
 return [r for r in shared_pipe_events(span,arch,allow_signal=allow_signal) if r['direction'] and not r['vector']]
from native_pipe_io_events import _read_view
KEY=rb'arch=([a-z0-9_]+) variant=([01]) form=([01]) restart=([01]) case=([0-9]|1[0-9]|2[0-4])'
BEGIN=re.compile(rb'PIPE_WRITE_CASE_BEGIN '+KEY+rb' pid=([0-9]+) tid=([0-9]+) fd=([0-9]+) readfd=(-?[0-9]+) replacement=(-?[0-9]+) replacementread=(-?[0-9]+) nestedfd=(-?[0-9]+) nestedread=(-?[0-9]+) input=([0-9]+) nestedinput=([0-9]+) count=([0-9]+) site=([0-9]+) resume=([0-9]+) syscall=([0-9]+) uid=([0-9]+) capacity=4096')
ATTEMPT=re.compile(rb'PIPE_WRITE_ATTEMPT '+KEY+rb' actor=0 pid=([0-9]+) tid=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+) a4=([0-9]+) a5=([0-9]+)')
EVENT=re.compile(rb'PIPE_WRITE_(RETURN|ERRNO|RETRY|RETRY_RETURN|NEST_SEND|NEST_ATTEMPT|NEST_EINTR|NEST_RETRY|NEST_RETURN|MUTATE_INPUT|PROTECT_READ|REPLACE_FD|PROTECT_NONE|RESTORE_INPUT|CHANGE_ACTION|EXIT_GROUP|CLOSE_READER|SEND|PAYLOAD_BEGIN|DRAIN_BEGIN|DRAIN_END|ATOMIC_PENDING|PENDING|UNMASK|EMPTY|EXEC_FAILED|EXEC_COMMIT|EXEC_REPLACED|EXEC_CHECKED) '+KEY+rb' actor=([09]) ordinal=([012]) value=(-?[0-9]+)')
HANDLER=re.compile(rb'PIPE_WRITE_(HANDLE|HANDLER_RETURN|NESTED|THREAD_EXIT|HANDLER_EXEC) '+KEY+rb' actor=0 pid=([0-9]+) tid=([0-9]+) depth=([12]) inspected=([01]) pc=([0-9]+)(?: number=([0-9]+) result=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+)(?: cr=([0-9]+) diagnostic_result=([0-9]+) orig_r3=([0-9]+)| cpsr=([0-9]+))?)?')
PAYLOAD=re.compile(rb'PIPE_WRITE_PAYLOAD '+KEY+rb' actor=9 pipe=([012]) bytes=([0-9]+) value=([0-9]+)')
END=re.compile(rb'PIPE_WRITE_CASE_PASS '+KEY)
PARENT=re.compile(rb'PIPE_WRITE_PARENT_PASS '+KEY+rb' pid=([0-9]+) signal=([0-9]+)')
GUEST_PREFIX=b'PIPE_WRITE_';PATTERNS=(BEGIN,ATTEMPT,EVENT,HANDLER,PAYLOAD,END,PARENT)+WRITE_PATTERNS

def pipe_events(span,arch):
 # The inherited read ledger predates WRITE diagnostics and owns a broader prefix.
 # Validate every write before separating that exact namespace for the read ledger.
 write_events(span,arch,allow_signal=True)
 retained=_read_view(span)
 return read_events(retained,arch)

def parse(pattern,line,position):
 if not pattern.fullmatch(line):raise ValueError('malformed scalar write guest event')
 r={'tag':line.split()[0].decode(),'line':line,'position':position}
 for field in line.split()[1:]:
  key,value=field.decode().split('=',1);r[key]=value if key=='arch' else int(value)
 return r

def probe_spec(arch,kind):
 if arch not in WRITE or kind!='pipe-write-signals':raise ValueError('unsupported scalar pipe write profile')
 groups=6 if arch in ('arm32','ppc') else 4
 command='/bin/native-pipe-write-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
 if len(command.rsplit('/',1)[1])>31:raise ValueError('scalar write executable exceeds component capacity')
 return f'PIPE_WRITE_PASS arch={arch} variants=2 groups={groups} cases={25*groups} parent=1'.encode(),b'PIPE_WRITE_PASS',command.encode(),1+50*groups

def failure_line(serial):
 if b'PIPE_WRITE_FAIL' in serial:return 'scalar write guest assertion: '+serial[serial.index(b'PIPE_WRITE_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
 return general_failure(serial)
def incomplete_failure_line(serial):return b'PIPE_WRITE_FAIL' in serial and b'\n' not in serial[serial.index(b'PIPE_WRITE_FAIL'):]

def validate_cases(span,arch):
 native=write_events(span,arch,allow_signal=True);byline={r['line']:r for r in native}
 if len(byline)!=len(native):raise ValueError('duplicate scalar write diagnostic')
 lines=span.splitlines();begins=[i for i,l in enumerate(lines) if BEGIN.fullmatch(l)];parents=[i for i,l in enumerate(lines) if PARENT.fullmatch(l)]
 keys=[(v,f,r,c) for v in range(2) for f in range(1 if v else 2 if arch in ('arm32','ppc') else 1) for r in range(2) for c in range(25)]
 if len(begins)!=len(keys) or len(parents)!=len(keys):raise ValueError('missing scalar write case/parent')
 maximum=(1<<(32 if arch in WORD32 else 64))-1;low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000);mips=arch.startswith('mips');usr1,usr2=(16,17) if mips else (10,12)
 owners=set();claimed=set();guest_claimed=set();counts=dict(cases=0,groups=len(keys)//25,initial_waits=0,fresh_waits=0,rearms=0,interruptions=0,restarts=0,eintr=0,payload_records=0,payload_bytes=0,exec_replacements=0)
 for index,((variant,form,restart,case),first,last) in enumerate(zip(keys,begins,parents)):
  if first>=last or index and first<=parents[index-1]:raise ValueError('overlapping scalar write cases')
  rows=[]
  for i in range(first,last+1):
   line=lines[i]
   if GUEST_PREFIX in line and WRITE_PREFIX not in line:
    pattern=next((p for p in PATTERNS[:7] if p.fullmatch(line)),None)
    if pattern is None:raise ValueError('unknown scalar write guest record')
    r=parse(pattern,line,i)
    if tuple(r[k] for k in ('arch','variant','form','restart','case'))!=(arch,variant,form,restart,case):raise ValueError('scalar write marker changed active case')
    rows.append(r);guest_claimed.add(i)
  def tagged(tag):return [r for r in rows if r['tag']=='PIPE_WRITE_'+tag]
  def one(tag):
   found=tagged(tag)
   if len(found)!=1:raise ValueError('scalar write event missing/duplicate: '+tag)
   return found[0]
  def action(tag,value,actor=9,ordinal=0):
   r=one(tag)
   if (r['actor'],r['ordinal'],r['value'])!=(actor,ordinal,value):raise ValueError('scalar write action payload differs: '+tag)
   return r
  def ordered(*records):
   positions=[r['position'] if 'position' in r else position[r['line']] for r in records]
   if positions!=sorted(set(positions)):raise ValueError('scalar write causal order differs')
  begin=one('CASE_BEGIN');pid,tid=begin['pid'],begin['tid'];fd,input,count=begin['fd'],begin['input'],begin['count'];width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
  expected_count=1 if case==0 else 4096 if case in (1,12) else 4097 if case in (13,14) else 32
  if (pid in owners or not 0<pid<=0xffffffff or not 0<tid<=0xffffffff or tid==pid or not 3<=fd<32 or count!=expected_count or begin['syscall']!=WRITE[arch] or not 0<=begin['uid']<=0xffffffff or
      not low<=input<=high-count or not low<=begin['site']<high or begin['resume']-begin['site']!=width or not instruction(arch,begin['site'],bool(form)) or not instruction(arch,begin['resume'],bool(form))):raise ValueError('invalid scalar write case identity/ABI')
  owners.add(pid)
  if any(not -1<=begin[n]<32 for n in ('readfd','replacement','replacementread','nestedfd','nestedread')):raise ValueError('scalar write descriptor exceeds native SDK31 table')
  if (case==11 and begin['readfd']!=-1 or case!=11 and (begin['readfd']<3 or begin['readfd']==fd) or
      case in (5,6) and (begin['replacement']<3 or begin['replacementread']<3 or len({fd,begin['readfd'],begin['replacement'],begin['replacementread']})!=4) or case not in (5,6) and (begin['replacement'],begin['replacementread'])!=(-1,-1) or
      case==17 and (begin['nestedfd']<3 or begin['nestedread']<3 or len({fd,begin['readfd'],begin['nestedfd'],begin['nestedread']})!=4 or begin['nestedinput']!=input+4096) or
      case!=17 and (begin['nestedfd'],begin['nestedread'],begin['nestedinput'])!=(-1,-1,0)):raise ValueError('scalar write pipe/fd topology differs')
  if (one('PARENT_PASS')['pid'],one('PARENT_PASS')['signal'])!=(pid,usr1 if case==20 else 0):raise ValueError('scalar write scenario parent status differs')
  caught=case in (0,1,6,14,15,16,17,18,19,23);again=bool(1-restart if case==15 else restart);pending=8<=case<=11;immediate=case in (9,10,11,13);edited=case==18 and not variant and again;has_return=case not in (19,20,21,22,23);retry=case==3 or caught and case not in (19,23) and (not again or edited);normal_pass=case not in (20,21,22,23)
  drains=2 if case in (12,17) else 0 if case in (9,11,13,20,21,22,23,24) else 1
  payloads=2 if case in (14,17) else 0 if case in (10,11,19,20,21,24) else 1
  empties=2 if case in (5,6,17,22,23) else 0 if case in (11,20,21,24) else 1
  expected={'CASE_BEGIN':1,'ATTEMPT':1,'PARENT_PASS':1,'CASE_PASS':int(normal_pass),'RETURN':int(has_return),'ERRNO':int(has_return),'RETRY':int(retry),'RETRY_RETURN':int(retry),'HANDLE':int(caught or pending),'HANDLER_RETURN':int(caught and case not in (19,23) or pending),'NESTED':int(case in (16,17)),'THREAD_EXIT':int(case==19),'HANDLER_EXEC':int(case==23),'NEST_SEND':int(case==16),'NEST_ATTEMPT':int(case==17),'NEST_EINTR':int(case==17),'NEST_RETRY':int(case==17),'NEST_RETURN':int(case==17),'SEND':int(caught or pending or case in (7,20))+int(case==17),'MUTATE_INPUT':int(case==2),'PROTECT_READ':int(case==4),'REPLACE_FD':int(case in (5,6)),'PROTECT_NONE':int(case==3),'RESTORE_INPUT':int(case==3),'CHANGE_ACTION':int(case==15),'EXIT_GROUP':int(case==21),'CLOSE_READER':int(case==24),'PAYLOAD_BEGIN':int(case==14),'DRAIN_BEGIN':drains,'DRAIN_END':drains,'ATOMIC_PENDING':int(case==12),'PENDING':int(pending),'UNMASK':int(pending),'PAYLOAD':payloads,'EMPTY':empties,'EXEC_FAILED':int(case in (22,23)),'EXEC_COMMIT':int(case in (22,23)),'EXEC_REPLACED':int(case in (22,23)),'EXEC_CHECKED':int(case in (22,23))}
  if any(len(tagged(tag))!=n for tag,n in expected.items()) or any(r['tag'].removeprefix('PIPE_WRITE_') not in expected for r in rows):raise ValueError('scalar write case event cardinality differs')
  att=one('ATTEMPT')
  if (att['pid'],att['tid'])!=(pid,tid) or [att['a'+str(j)] for j in range(6)]!=[fd,input,count,0x1357,0,0]:raise ValueError('scalar write attempted arguments differ')
  ordered(begin,att,one('PARENT_PASS'))
  position={l:i for i,l in enumerate(lines[first:last+1],first)};stream=[byline[l] for l in lines[first:last+1] if l in byline];claimed.update(r['line'] for r in stream)
  if any((r['pid'],r['tid'])!=(pid,tid) for r in stream):raise ValueError('scalar write diagnostic belongs to unannounced writer')
  arms=[r for r in stream if r['tag'].endswith('_WAIT') and r['stage']=='arm'];rearms=[r for r in stream if r['tag'].endswith('_WAIT') and r['stage']=='rearm'];terminals=[r for r in stream if r['tag'].endswith('_COMPLETE')];origins=[r for r in stream if r['tag'].endswith('_ORIGIN')];signals=[r for r in stream if r['tag'].endswith('_SIGNAL')]
  expected_arms=0 if immediate else 4 if case==17 else 2 if caught and case not in (6,19,23) else 1
  if len(arms)!=expected_arms or len(origins)!=len(arms) or len(terminals)!=len(arms) or len(rearms)!=int(case in (5,6,12,14)) or len(signals)!=int(caught)+int(case==17):raise ValueError('scalar write owned request topology differs')
  if any(bool(r.get('large'))!=(case==14) for r in stream):raise ValueError('scalar write scenario has wrong LARGE namespace')
  if case==14:
   if any(r['committed'] for r in arms+origins+signals) or [r['committed'] for r in rearms]!=[4096] or [r['committed'] for r in terminals]!=[0,4097]:raise ValueError('scalar large write cursor differs')
   action('PAYLOAD_BEGIN',4096);ordered(rearms[0],terminals[-1]);ordered(tagged('DRAIN_END')[0],one('PAYLOAD_BEGIN'),terminals[-1]);ordered(tagged('DRAIN_BEGIN')[0],rearms[0])
   ordered(one('PAYLOAD_BEGIN'),tagged('PAYLOAD')[0],tagged('PAYLOAD')[1]);ordered(rearms[0],tagged('PAYLOAD')[0])
  if arms:ordered(att,arms[0]);counts['initial_waits']+=1;counts['fresh_waits']+=len(arms)-1
  counts['rearms']+=len(rearms)
  for j,arm in enumerate(arms):
   nested=case==17 and j in (1,2);wanted=(begin['nestedfd'],begin['nestedinput'],8) if nested else (fd,input,count)
   if (arm['fd'],arm['input'],arm['bytes'])!=wanted:raise ValueError('scalar write copied request changed role/arguments')
   origin=next(r for r in origins if r['request']==arm['request'])
   if (not variant or nested) and origin['pc']!=begin['resume']:raise ValueError('scalar write raw origin differs from exact return label')
   prior=arms[1] if nested else arms[0]
   if (arm['description'],arm['pipe'])!=(prior['description'],prior['pipe']):raise ValueError('scalar write fresh request selected wrong open description')
   if nested and (arm['description']==arms[0]['description'] or arm['pipe']==arms[0]['pipe']):raise ValueError('nested scalar write reused outer pipe identity')
   terminal=next(r for r in terminals if r['request']==arm['request']);is_signal=arm is arms[0] and caught or case==17 and j==1
   outcome='interrupted' if is_signal else 'cancelled' if case in (20,21,22) else 'efault' if case==3 else 'error' if case==24 else 'ready'
   result=(0 if again and j==0 else -4) if is_signal else -125 if outcome=='cancelled' else -14 if outcome=='efault' else -32 if outcome=='error' else 8 if nested else (count if case==14 else min(count,4096))
   if (terminal['outcome'],terminal['result'])!=(outcome,result):raise ValueError('scalar write owned completion differs from case')
  sends=tagged('SEND')
  for j,r in enumerate(sends):
   if (r['actor'],r['ordinal'],r['value'])!=(9,0,usr2 if j else usr1):raise ValueError('scalar write directed send differs')
  for j,sig in enumerate(signals):
   nested=j==1;redo=again and not nested
   if (sig['signal'],sig['outcome'])!=(usr2 if nested else usr1,'restart' if redo else 'eintr'):raise ValueError('scalar write signal selection/disposition differs')
   if not variant or nested:
    if sig['pc']!=(begin['site'] if redo else begin['resume']):raise ValueError('scalar write raw trap PC differs')
   ordered(sends[j],sig);counts['interruptions']+=1;counts['restarts' if redo else 'eintr']+=1
  if pending:ordered(sends[0],att);action('PENDING',1,0);action('UNMASK',0,0);ordered(one('RETURN'),one('ERRNO'),one('PENDING'),one('UNMASK'),one('HANDLE'),one('HANDLER_RETURN'))
  elif sends and arms:ordered(arms[0],sends[0])
  for tag,value in [('MUTATE_INPUT',90),('PROTECT_READ',0),('PROTECT_NONE',0),('RESTORE_INPUT',0),('REPLACE_FD',begin['replacement']),('CHANGE_ACTION',1-restart),('EXIT_GROUP',0),('CLOSE_READER',begin['readfd']),('ATOMIC_PENDING',1)]:
   if tagged(tag):action(tag,value)
  starts,ends=tagged('DRAIN_BEGIN'),tagged('DRAIN_END');drain_pairs=[(0,14096),(0,4096)] if case==17 else [(0,1),(1,4095)] if case==12 else [(0,4096)] if drains else []
  for b,e,(ordinal,value) in zip(starts,ends,drain_pairs):
   if (b['actor'],b['ordinal'],b['value'],e['actor'],e['ordinal'],e['value'])!=(9,ordinal,value,9,ordinal,value):raise ValueError('scalar write drain length/pipe changed')
   ordered(b,e)
  for terminal in terminals:
   if terminal['outcome'] in ('ready','efault'):
    nested=terminal['input']==begin['nestedinput'];drain=starts[0] if nested or case!=17 else starts[1]
    if case==12:drain=starts[1]
    ordered(drain,terminal)
  if case==12:ordered(arms[0],starts[0],rearms[0],one('ATOMIC_PENDING'),starts[1],terminals[0])
  if case in (5,6):ordered(arms[0],one('REPLACE_FD'),rearms[0],one('SEND') if case==6 else starts[0],terminals[0])
  if case in (2,3,4,5):ordered(arms[0],one({2:'MUTATE_INPUT',3:'PROTECT_NONE',4:'PROTECT_READ',5:'REPLACE_FD'}[case]),starts[0])
  if case in (6,15):ordered(arms[0],one('REPLACE_FD' if case==6 else 'CHANGE_ACTION'),sends[0])
  if case==7:ordered(sends[0],starts[0])
  if case in (20,21,22,24):ordered(arms[0],one({20:'SEND',21:'EXIT_GROUP',22:'EXEC_COMMIT',24:'CLOSE_READER'}[case]),terminals[0])
  if has_return:
   value=77 if edited else (-1 if variant else -4) if caught and not again else (-1 if variant else -14) if case==3 else (-1 if variant else -11) if case==10 else (-1 if variant else -32) if case in (11,24) else (count if case==14 else min(count,4096))
   action('RETURN',value,0);action('ERRNO',(14 if case==3 else 11 if case==10 else 32 if case in (11,24) else 4) if variant and value==-1 else 111,0);ordered(att,one('RETURN'),one('ERRNO'))
   if terminals and not (caught and (not again or edited)):ordered(terminals[-1],one('RETURN'))
  if retry:action('RETRY',fd,0,1);action('RETRY_RETURN',(count if case==14 else min(count,4096)),0,1);ordered(one('ERRNO'),one('RETRY'),one('RETRY_RETURN'))
  if retry and case not in (3,6):ordered(terminals[-1],one('RETRY_RETURN'))
  if case==3:ordered(terminals[0],one('RETURN'),one('RESTORE_INPUT'),one('RETRY'))
  if caught:
   finish=one('THREAD_EXIT' if case==19 else 'HANDLER_EXEC' if case==23 else 'HANDLER_RETURN');ordered(signals[0],one('HANDLE'),finish)
   if has_return:ordered(finish,one('RETURN'))
   if case not in (6,19,23):
    fresh=arms[-1];ordered(one('RETRY') if retry else finish,fresh,starts[-1])
   if case==16:action('NEST_SEND',usr2,0);ordered(one('HANDLE'),one('NEST_SEND'),one('NESTED'),finish)
   if case==17:
    action('NEST_ATTEMPT',begin['nestedfd'],0);action('NEST_EINTR',-4,0);action('NEST_RETRY',begin['nestedfd'],0,1);action('NEST_RETURN',8,0,1)
    ordered(one('HANDLE'),one('NEST_ATTEMPT'),arms[1],sends[1],signals[1],one('NESTED'),one('NEST_EINTR'),one('NEST_RETRY'),arms[2],starts[0],terminals[2],one('NEST_RETURN'),finish)
  for h in [r for r in rows if HANDLER.fullmatch(r['line'])]:
   nested=h['tag']=='PIPE_WRITE_NESTED';inspected=caught and not(nested and case==16);edit=h['tag']=='PIPE_WRITE_HANDLER_RETURN' and edited
   if (h['pid'],h['tid'],h['depth'],h['inspected'])!=(pid,tid,2 if nested else 1,int(inspected)) or not low<=h['pc']<high or not instruction(arch,h['pc']):raise ValueError('scalar write handler ownership/depth/PC differs')
   base={'tag','line','position','arch','variant','form','restart','case','actor','pid','tid','depth','inspected','pc'};extra={'number','result','a0','a1','a2','a3'}|({'cr','diagnostic_result','orig_r3'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set())
   if set(h)!=base|(extra if inspected else set()):raise ValueError('scalar write handler context fields differ')
   if not inspected:continue
   sig=signals[1 if nested else 0];redo=again and not nested;argfd=begin['nestedfd'] if nested else fd;arginput=begin['nestedinput'] if nested else input;argcount=8 if nested else count
   result=77 if edit else (WRITE[arch] if arch in ('x86_64','i386') or mips else argfd) if redo else 4 if mips or arch=='ppc' else maximum-3
   number=77 if edit and (arch in ('x86_64','i386') or mips) else WRITE[arch] if redo or arch not in ('x86_64','i386') and not mips else result
   arg0=result if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not redo or edit) else argfd
   if (h['pc'],h['number'],h['result'],h['a0'],h['a1'],h['a2'])!=(begin['resume'] if edit else sig['pc'],number,result,arg0,arginput,argcount):raise ValueError('scalar write saved result/syscall/arguments differ')
   arg3=0 if mips and edit else 1 if mips and not redo else 0x1357 if not variant or nested else None
   if not 0<=h['a3']<=maximum or arg3 is not None and h['a3']!=arg3:raise ValueError('scalar write fourth argument/error flag differs')
   if arch=='ppc' and (not 0<=h['cr']<=maximum or bool(h['cr']&0x10000000)==edit or h['diagnostic_result']!=(0x123 if edit else 0 if redo else maximum-3) or h['orig_r3']!=(0x234 if edit else argfd)):raise ValueError('scalar write PPC saved diagnostics differ')
   if arch=='arm32' and (not 0<=h['cpsr']<=maximum or h['cpsr']&0x0700ffdf!=0x10 or not instruction(arch,h['pc'],bool(h['cpsr']&0x20)) or (not variant or nested) and bool(h['cpsr']&0x20)!=bool(form)):raise ValueError('scalar write ARM saved instruction mode differs')
   if arch=='arm32' and redo and not edit and sig['origin_record']['pc']-h['pc']!=(2 if h['cpsr']&0x20 else 4):raise ValueError('scalar write ARM origin and saved instruction width differ')
   if h['tag']=='PIPE_WRITE_HANDLER_RETURN' and not edit:
    original=one('HANDLE')
    if any(h[k]!=original[k] for k in extra|{'pc'}):raise ValueError('scalar write unedited handler changed context')
  expected_payload=[(0,4096,65),(0,1,65)] if case==14 else [(0,1,80)] if case in (22,23) else ([(2 if case==6 else 0,(count if case==14 else min(count,4096)),90 if case==2 else 65)] if payloads else [])+([(1,8,66)] if case==17 else [])
  if [(r['pipe'],r['bytes'],r['value']) for r in tagged('PAYLOAD')]!=expected_payload:raise ValueError('scalar write reader observed wrong pipe/bytes/payload')
  counts['payload_records']+=payloads;counts['payload_bytes']+=sum(r['bytes'] for r in tagged('PAYLOAD'))
  for p in tagged('PAYLOAD'):
   if has_return and not(case==14 and p is tagged('PAYLOAD')[0]):ordered(one('RETRY_RETURN') if retry else one('ERRNO'),p)
   if starts and case not in (22,23):ordered(ends[-1],p)
  if normal_pass:
   worker_end=one('HANDLER_RETURN') if pending else one('RETRY_RETURN') if retry else one('ERRNO') if has_return else one('THREAD_EXIT')
   for proof in (tagged('PAYLOAD')[1:] if case==14 else tagged('PAYLOAD'))+tagged('EMPTY'):ordered(worker_end,proof)
   if case in (6,10,19):ordered(worker_end,starts[0])
  expected_empty=[(0,begin['readfd'])]*2 if case in (22,23) else ([(0,begin['readfd'])] if empties else [])+([(1,begin['nestedread'])] if case==17 else [])+([(2,begin['replacementread'])] if case in (5,6) else [])
  for e,(ordinal,readfd) in zip(tagged('EMPTY'),expected_empty):
   if e['actor']!=9 or e['ordinal']!=ordinal or e['value']<3 or e['value']!=readfd:raise ValueError('scalar write empty-pipe check changed ownership')
   if case not in (22,23):
    previous_payload=[p for p in tagged('PAYLOAD') if p['pipe']==ordinal]
    if previous_payload:ordered(previous_payload[-1],e)
    elif ends:ordered(ends[-1],e)
  if normal_pass:
   if one('CASE_PASS')['position']!=max(r['position'] for r in rows if r['tag']!='PIPE_WRITE_PARENT_PASS'):raise ValueError('scalar write case pass precedes completed checks')
  images=[dict(position=i) for i in range(first,last+1) if IMAGE.fullmatch(lines[i])]
  if len(images)!=int(case in (22,23)):raise ValueError('scalar write missing/extra replacement image')
  if case in (22,23):
   executor=0 if case==23 else 9;action('EXEC_FAILED',2,executor);action('EXEC_COMMIT',pid,executor);action('EXEC_REPLACED',pid);action('EXEC_CHECKED',pid)
   if case==22:ordered(origins[0],one('EXEC_FAILED'),one('EXEC_COMMIT'),terminals[0],images[0])
   if case==23:ordered(one('HANDLER_EXEC'),one('EXEC_FAILED'))
   ordered(one('EXEC_FAILED'),one('EXEC_COMMIT'),images[0],one('EXEC_REPLACED'),tagged('EMPTY')[0],one('PAYLOAD'),tagged('EMPTY')[1],one('EXEC_CHECKED'),one('PARENT_PASS'));counts['exec_replacements']+=1
  counts['cases']+=1
 aggregate=probe_spec(arch,'pipe-write-signals')[0]
 if lines.count(aggregate)!=1 or lines.index(aggregate)<=parents[-1]:raise ValueError('scalar write aggregate misplaced')
 if any(GUEST_PREFIX in l and WRITE_PREFIX not in l and i not in guest_claimed and l!=aggregate for i,l in enumerate(lines)):raise ValueError('scalar write guest marker outside case')
 if len(claimed)!=len(native):raise ValueError('unclaimed scalar write operation')
 return counts

def _validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='pipe-write-signals'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated scalar pipe write command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('scalar pipe write boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final scalar pipe write prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    child_baseline = boot_baseline(boot,arch,required=True)
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        if any(IMAGE.fullmatch(line) for line in span.splitlines()):
            raise ValueError('unexpected Linux image in native pipeline')
        incidental = pipe_events(span,arch) + futex_events(span,arch,allow_signal=False) + poll_events(span,arch,allow_signal=False) + child_events(span,arch,baseline=child_baseline) + write_events(span,arch,allow_signal=False)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=(13 if arch in ('arm32','ppc') else 9) or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered scalar-write/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong scalar pipe write image source')
        pipe_events(span,arch)
        futex_events(span,arch,allow_signal=False)
        poll_events(span,arch,allow_signal=False)
        child_events(span,arch,baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+READ_PATTERNS+FUTEX_PATTERNS+POLL_PATTERNS+CHILD_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    write_events(boot,arch,allow_signal=False)
    pipe_events(boot,arch)
    futex_events(boot,arch,allow_signal=False)
    poll_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and WRITE_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('scalar pipe write completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate scalar pipe write frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty scalar pipe write boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('scalar pipe write commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('scalar pipe write accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('scalar pipe write command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('scalar pipe write command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=13 if arch in ('arm32','ppc') else 9,scope='actual-user-private-scalar-pipe-write-signals',
                observations=observations,owned_scalar_write_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_restart=True,temporary_masks=False,full_exec_replacement=True,
                writev=False,automatic_sigpipe=False,full_blocking_large_write=True,production=False,physical=False,smp=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))


def validate_execution(serial,baseline_begin,probe_begin,probe_mid,probe_end,native_begin,arch,kind='pipe-write-signals'):
    normalized,bounds=normalize_transcript(serial,(baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    return _validate_execution(normalized,*bounds,arch,kind)
