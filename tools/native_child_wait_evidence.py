"""Strict all-ten private child wait raw/libc execution collector."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure,decode_frames
from entry_stack_evidence import decode_stacks,COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE,validate_command
from native_pipe_io_events import native_events as pipe_events,PATTERNS as PIPE_PATTERNS
from native_futex_events import native_events as futex_events,final_snapshots,instruction,WORD32,PATTERNS as FUTEX_PATTERNS
from native_poll_events import native_events as poll_events,PATTERNS as POLL_PATTERNS
from native_child_events import normalize_transcript, WAIT, SIGNAL, PATTERNS as CHILD_WAIT_PATTERNS
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
NUMBERS={'x86_64':61,'i386':114,'aarch64':260,'arm32':114,'rv32':95,'rv64':260,'loongarch64':260,'mips':4114,'mips64':5059,'ppc':114}
KEY=rb'arch=([a-z0-9_]+) variant=([01]) form=([01]) restart=([01]) case=([0-9]|1[0-9]|2[01])'
BEGIN=re.compile(rb'CHILD_WAIT_CASE_BEGIN '+KEY+rb' pid=([0-9]+) tid0=([0-9]+) tid1=([0-9]+) child0=([0-9]+) child1=([0-9]+) any=([01]) workers=([12]) children=([12]) output0=([0-9]+) output1=([0-9]+) site=([0-9]+) resume=([0-9]+) syscall=([0-9]+) siginfo=([01]) uid=([0-9]+)')
ATTEMPT=re.compile(rb'CHILD_WAIT_ATTEMPT '+KEY+rb' actor=([01]) pid=([0-9]+) tid=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+) a4=([0-9]+) a5=([0-9]+)')
EVENT=re.compile(rb'CHILD_WAIT_(RETURN|RETRY|NEST_ATTEMPT|NEST_EINTR|NEST_REAP|PENDING|UNMASK|SEND|RELEASE|MUTATE_OUTPUT|PROTECT_OUTPUT|EXIT_GROUP|CHANGE_ACTION|MAIN_REAP|EXEC_FAILED|EXEC_COMMIT|EXEC_REPLACED|EXEC_REAP) '+KEY+rb' actor=([019]) ordinal=([01]) value=(-?[0-9]+)')
HANDLER=re.compile(rb'CHILD_WAIT_(HANDLE|NESTED|HANDLER_RETURN|THREAD_EXIT|HANDLER_EXEC) '+KEY+rb' actor=0 pid=([0-9]+) tid=([0-9]+) depth=([12]) inspected=([01]) pc=([0-9]+)(?: number=([0-9]+) result=([0-9]+) a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+)(?: cr=([0-9]+) diagnostic_result=([0-9]+) orig_r3=([0-9]+)| cpsr=([0-9]+))?)?')
OUTPUT=re.compile(rb'CHILD_WAIT_OUTPUT '+KEY+rb' actor=([01]) ordinal=([01]) child=([0-9]+) status=([0-9]+) uid=([0-9]+) bytes=(4|128)')
END=re.compile(rb'CHILD_WAIT_CASE_PASS '+KEY)
PARENT=re.compile(rb'CHILD_WAIT_PARENT_PASS '+KEY+rb' pid=([0-9]+) signal=([0-9]+) descendants=([12])')
SKIP=re.compile(rb'CHILD_WAIT_CASE_SKIP arch=rv32 variant=1 form=0 restart=([01]) case=3 reason=musl-user-status-copy')
GUEST_PREFIX=b'CHILD_WAIT_';KERNEL_PREFIX=b'OK_NATIVE_CHILD_';PATTERNS=(BEGIN,ATTEMPT,EVENT,HANDLER,OUTPUT,END,PARENT,SKIP)+CHILD_PATTERNS

def parse(pattern,line):
 if not pattern.fullmatch(line):raise ValueError('malformed child guest event: '+line[:160].decode(errors='replace'))
 r={'tag':line.split()[0].decode(),'line':line}
 for field in line.split()[1:]:
  key,value=field.decode().split('=',1);r[key]=value if key=='arch' else int(value)
 return r

def probe_spec(arch,kind):
 if arch not in NUMBERS or kind!='child-wait-signals':raise ValueError('unsupported native child wait profile')
 groups=6 if arch in ('arm32','ppc') else 4
 marker=f'CHILD_WAIT_PASS arch={arch} variants=2 groups={groups} cases={22*groups-(2 if arch=="rv32" else 0)} parent=1'
 command='/bin/native-child-wait-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
 if len(command.rsplit('/',1)[1])>31:raise ValueError('child executable component exceeds native name capacity')
 # Per group: 22 scenario leaders, 25 children and 24 waiter threads.
 # RV32 omits two libc output-copy scenarios, each containing three leases.
 return marker.encode(),b'CHILD_WAIT_PASS',command.encode(),1+71*groups-(6 if arch=='rv32' else 0)

def failure_line(serial):
 if b'CHILD_WAIT_FAIL' in serial:return 'child guest assertion: '+serial[serial.index(b'CHILD_WAIT_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
 return general_failure(serial)
def incomplete_failure_line(serial):
 return b'CHILD_WAIT_FAIL' in serial and b'\n' not in serial[serial.index(b'CHILD_WAIT_FAIL'):]

def validate_cases(span,arch,baseline):
 pc_bounds=(0x10000000,0x40000000) if arch in ('aarch64','arm32') else (0x40000000,0x80000000)
 native=child_events(span,arch,allow_signal=True,baseline=baseline,signal_numbers=(16,17) if arch.startswith('mips') else (10,12),pc_bounds=pc_bounds);native=[r for r in native if r['tag'] in ('OK_NATIVE_CHILD_WAIT','OK_NATIVE_CHILD_SIGNAL')];native_lines={r['line']:r for r in native}
 if len(native_lines)!=len(native):raise ValueError('duplicate child diagnostic')
 lines=span.splitlines();begins=[i for i,l in enumerate(lines) if BEGIN.fullmatch(l)];parents=[i for i,l in enumerate(lines) if PARENT.fullmatch(l)]
 groups=6 if arch in ('arm32','ppc') else 4
 if len(begins)!=22*groups-(2 if arch=='rv32' else 0) or len(parents)!=len(begins):raise ValueError('incomplete child case/parent sequence')
 maximum=(1<<(32 if arch in WORD32 else 64))-1;rv=arch=='rv32';mips=arch.startswith('mips');usr1,usr2=(16,17) if mips else (10,12)
 owners=set();children=set();tids=set();selected_native=set();guest_lines=set();images=0;counts=dict(cases=0,groups=groups,handlers=0,nested_handlers=0,interruptions=0,restarts=0,eintr=0,rearms=0,initial_waits=0,fresh_waits=0,thread_exits=0,fatal_groups=0,group_exits=0,exec_replacements=0,reaped_outputs=0)
 casekeys=[(v,f,r,c) for v in range(2) for f in range(1 if v else 2 if arch in ('arm32','ppc') else 1) for r in range(2) for c in range(22) if not (rv and v and c==3)]
 skips=[(i,SKIP.fullmatch(l)) for i,l in enumerate(lines) if SKIP.fullmatch(l)]
 if len(skips)!=(2 if rv else 0):raise ValueError('unexpected/missing child coverage exception')
 for (position,match),restart_value in zip(skips,range(2)):
  prior=casekeys.index((1,0,restart_value,2));following=casekeys.index((1,0,restart_value,4))
  if int(match[1])!=restart_value or not parents[prior]<position<begins[following]:raise ValueError('child coverage exception misplaced')
  guest_lines.add(position)
 counts['skipped_libc_output_faults']=len(skips)
 for index,((variant,form,restart,case),start,end) in enumerate(zip(casekeys,begins,parents)):
  if start>=end or index and start<=parents[index-1]:raise ValueError('overlapping child case boundaries')
  rows=[]
  for i in range(start,end+1):
   l=lines[i]
   if GUEST_PREFIX in l and KERNEL_PREFIX not in l:
    pattern=next((p for p in PATTERNS[:7] if p.fullmatch(l)),None)
    if pattern is None:raise ValueError('unexpected child guest record')
    row=parse(pattern,l);row['position']=i
    if tuple(row[k] for k in ('arch','variant','form','restart','case'))!=(arch,variant,form,restart,case):raise ValueError('child marker changed active case')
    rows.append(row);guest_lines.add(i)
  begin=rows[0];pid=begin['pid'];child=[begin['child0'],begin['child1']];worker=[begin['tid0'],begin['tid1']];output=[begin['output0'],begin['output1']];any_child=case in (1,15,16);nchildren=2 if case in (12,15,16) else 1;nworkers=2 if case in (14,15) else 1;selector=0xffffffff if any_child else child[0]
  width=2 if arch in ('x86_64','i386') or arch=='arm32' and form and not variant else 4
  if (pid in owners or not 0<pid<=0xffffffff or (begin['any'],begin['workers'],begin['children'],begin['syscall'],begin['siginfo'])!=(int(any_child),nworkers,nchildren,NUMBERS[arch],int(rv)) or
      not 0<=begin['uid']<=0xffffffff or not instruction(arch,begin['site'],bool(form)) or not instruction(arch,begin['resume'],bool(form)) or begin['resume']-begin['site']!=width):raise ValueError('invalid child case owner, ABI or trap labels')
  owners.add(pid)
  for j in range(2):
   if j<nchildren:
    if not 0<child[j]<=0xffffffff or child[j] in children or child[j]==pid:raise ValueError('reused/invalid real child identity')
    children.add(child[j])
   elif child[j]!=0:raise ValueError('unexpected second child')
   if j<nworkers:
    if not 0<worker[j]<=0xffffffff or worker[j] in tids or worker[j]==pid or not 0<output[j]<=maximum-512 or output[j]%4:raise ValueError('invalid child waiter owner/output')
    tids.add(worker[j])
   elif worker[j] or output[j]:raise ValueError('unexpected second waiter')
  endrow=rows[-1]
  if endrow['tag']!='CHILD_WAIT_PARENT_PASS' or (endrow['pid'],endrow['signal'],endrow['descendants'])!=(pid,usr1 if case==18 else 0,nchildren):raise ValueError('child scenario exit/descendant drain differs')
  def tagged(tag):return [r for r in rows if r['tag']=='CHILD_WAIT_'+tag]
  def one(tag):
   found=tagged(tag)
   if len(found)!=1:raise ValueError('missing/duplicate child event '+tag)
   return found[0]
  def event(tag,value,ordinal=0,actor=9):
   r=one(tag)
   if (r['value'],r['ordinal'],r['actor'])!=(value,ordinal,actor):raise ValueError('child action payload differs: '+tag)
   return r
  expected_events={'CASE_BEGIN':1,'PARENT_PASS':1,'ATTEMPT':nworkers,'CASE_PASS':int(case<18),'RETURN':0 if case in (17,18,19,20,21) else nworkers,'OUTPUT':0,'RETRY':0,'HANDLE':0,'HANDLER_RETURN':0,'NESTED':0,'SEND':0,'RELEASE':0,'PENDING':0,'UNMASK':0,'MAIN_REAP':0,'MUTATE_OUTPUT':int(case==2),'PROTECT_OUTPUT':int(case==3),'CHANGE_ACTION':int(case==10),'THREAD_EXIT':int(case==17),'EXIT_GROUP':int(case==19),'EXEC_FAILED':int(case in (20,21)),'EXEC_COMMIT':int(case in (20,21)),'EXEC_REPLACED':int(case in (20,21)),'EXEC_REAP':int(case in (20,21)),'HANDLER_EXEC':int(case==21),'NEST_ATTEMPT':int(case==12),'NEST_EINTR':int(case==12),'NEST_REAP':int(case==12)}
  caught=case<=2 or case in (10,11,12,13,17,21);again=bool(1-restart if case==10 else restart);blocked=6<=case<=9;immediate=case in (7,8,9,16)
  expected_events['HANDLE']=int(caught or blocked);expected_events['HANDLER_RETURN']=int(caught and case not in (17,21) or blocked);expected_events['NESTED']=int(case in (11,12));expected_events['SEND']=int(caught or blocked or case in (5,18))+int(case==12)
  expected_events['RELEASE']=0 if case in (18,19,20,21) else nchildren
  expected_events['PENDING']=expected_events['UNMASK']=int(blocked);expected_events['MAIN_REAP']=int(case in (7,8,17));expected_events['RETRY']=int(caught and case not in (17,21) and (not again or case==13 and not variant))+int(case in (3,16))
  expected_events['OUTPUT']=0 if case in (7,8,17,18,19,20,21) else 2 if case in (15,16) else 1
  for tag,count in expected_events.items():
   if len(tagged(tag))!=count:raise ValueError(f'child case {case} requires {count} {tag} records')
  if any(r['tag'].removeprefix('CHILD_WAIT_') not in expected_events for r in rows):raise ValueError('unclaimed child guest event')
  case_native=[native_lines[l] for l in lines[start:end+1] if l in native_lines and native_lines[l]['pid']==pid]
  positions={l:i for i,l in enumerate(lines[start:end+1],start)}
  selected_native.update(r['line'] for r in case_native)
  streams={j:[r for r in case_native if r['tid']==worker[j]] for j in range(nworkers)}
  leader=[r for r in case_native if r['tid']==pid]
  if len(case_native)!=sum(map(len,streams.values()))+len(leader):raise ValueError('child record belongs to unannounced waiter')
  if leader and case not in (7,8,17,20,21):raise ValueError('unexpected leader child wait')
  if any(r['tag']!='OK_NATIVE_CHILD_WAIT' or r['outcome'] not in ('arm','complete') or r['selector']!=child[0] or r['format']!=('siginfo' if rv else 'status') or r['outcome']=='complete' and r['result']!=child[0] for r in leader):raise ValueError('leader reaping changed child/result')
  for j in range(nworkers):
   att=[r for r in tagged('ATTEMPT') if r['actor']==j]
   if len(att)!=1 or (att[0]['pid'],att[0]['tid'])!=(pid,worker[j]):raise ValueError('missing exact child attempt owner')
   selected=pid if case==8 else (-1 if any_child else child[0]);args=[0 if selected==-1 else 1,0 if selected==-1 else selected,output[j],5 if case==7 else 4,0,0] if rv else [maximum if selected==-1 else selected,output[j],int(case==7),0,0,0]
   if [att[0]['a'+str(k)] for k in range(6)]!=args:raise ValueError('child attempted arguments changed')
   stream=streams[j];arms=[r for r in stream if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='arm'];rearms=[r for r in stream if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='rearm'];terminals=[r for r in stream if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome'] in ('complete','interrupted','cancelled')];signals=[r for r in stream if r['tag']=='OK_NATIVE_CHILD_SIGNAL']
   if immediate and stream or not immediate and not arms:raise ValueError('child immediate/blocking admission differs')
   expected_arms=0 if immediate else 4 if case==12 else 2 if caught and case not in (17,21) else 1
   if len(arms)!=expected_arms:raise ValueError('child request topology differs from executed case')
   for ordinal,arm in enumerate(arms):
    nested=case==12 and ordinal in (1,2)
    wanted_selector=child[1] if nested else selector
    if case==1 and ordinal and not again: wanted_selector=child[0]  # Explicit post-EINTR retry selects the child.
    wanted_output=output[j]+192 if nested else output[j]
    if (arm['selector'],arm['format'])!=(wanted_selector,'siginfo' if rv else 'status') or not pc_bounds[0]<=arm['output']<pc_bounds[1] or arm['output']%4 or (nested or not (variant and rv)) and arm['output']!=wanted_output:
     raise ValueError('child fresh request changed selected child, format or output')
   if arms:
    first=arms[0]
    if (first['selector'],first['format'])!=(selector,'siginfo' if rv else 'status') or first['output']!=(first['output'] if variant and rv else output[j]) or not 0<first['output']<=maximum-128 or first['output']%4 or positions[first['line']]<=att[0]['position']:raise ValueError('child initial copied request differs')
    # Every deliberate release/signal/mutation occurs after the corresponding admission.
    actions=[r for r in rows if r['tag'] in ('CHILD_WAIT_RELEASE','CHILD_WAIT_PROTECT_OUTPUT','CHILD_WAIT_MUTATE_OUTPUT','CHILD_WAIT_CHANGE_ACTION','CHILD_WAIT_EXIT_GROUP','CHILD_WAIT_EXEC_FAILED') or r['tag']=='CHILD_WAIT_SEND' and not blocked]
    if actions and positions[first['line']]>=min(r['position'] for r in actions):raise ValueError('child action preceded owned admission')
    if any(positions[r['line']]<=positions[first['line']] for r in arms[1:]) or any(b['request']<=a['request'] for a,b in zip(arms,arms[1:])):raise ValueError('child fresh entry reused a request')
    counts['initial_waits']+=1;counts['fresh_waits']+=len(arms)-1
   if rearms and case!=15:raise ValueError('unexpected child peer rearm')
   counts['rearms']+=len(rearms)
   if len(signals)!=(int(caught and j==0)+int(case==12 and j==0)):raise ValueError('child signal count differs')
   for k,sig in enumerate(signals):
    is_nested=k==1;expected_restart=again and not is_nested;outcome='restart' if expected_restart else 'eintr'
    if sig['signal']!=(usr2 if is_nested else usr1) or sig['outcome']!=outcome:raise ValueError('child disposition/selected signal changed')
    if not instruction(arch,sig['pc'],bool(form) if not variant or is_nested else False):
     if arch!='arm32' or not variant or not instruction(arch,sig['pc'],True):raise ValueError('illegal child saved trap PC')
    if (not variant or is_nested) and sig['pc']!=(begin['site'] if expected_restart else begin['resume']):raise ValueError('child raw PC differs from exact trap label')
    counts['interruptions']+=1;counts['restarts' if expected_restart else 'eintr']+=1
   completes=[r for r in terminals if r['outcome']=='complete'];cancelled=[r for r in terminals if r['outcome']=='cancelled']
   if len(completes)!=(0 if immediate or case in (17,18,19,20,21) else 2 if case==12 else 1):raise ValueError('child completion count differs')
   if bool(cancelled)!=(case in (18,19,20)) or len(cancelled)>1:raise ValueError('child lifecycle cancellation differs')
   allowed={-14,child[0]} if case==3 else {-10,child[0]} if case==14 else set(child) if case==15 else {child[0],child[1]} if case==12 else {child[0]}
   if any(r['result'] not in allowed for r in completes):raise ValueError('child completion claimed wrong child/error')
   if case==3 and (not completes or completes[0]['result']!=-14):raise ValueError('protected child output did not reject before reap')
   if caught and case not in (17,21):
    outer=signals[0];fresh=[r for r in arms if positions[r['line']]>positions[outer['line']] and r['selector']==(child[0] if case==1 and not again else selector) and (variant and rv and not again or r['output']==outer['output'])]
    if not fresh:raise ValueError('child handler return did not enter a fresh owned wait')
   if case==12:
    nested_arms=[r for r in arms if r['selector']==child[1] and r['output']==output[0]+192]
    if len(nested_arms)!=2:raise ValueError('nested child wait lacks interrupted and fresh requests')
  if case==15 and not any(r['outcome']=='rearm' for r in case_native if r['tag']=='OK_NATIVE_CHILD_WAIT'):raise ValueError('two-waiter child race did not exercise owned rearm')
  sends=tagged('SEND')
  if any(r['actor']!=9 or r['ordinal'] or r['value']!=(usr2 if k else usr1) for k,r in enumerate(sends)):raise ValueError('child directed send payload changed')
  releases=tagged('RELEASE')
  if releases and [(r['ordinal'],r['value']) for r in releases]!=[(j,child[j]) for j in ([1,0] if case==12 else range(nchildren))]:raise ValueError('child release order/identity changed')
  if any(r['actor']!=9 for r in releases):raise ValueError('child release actor changed')
  if case==2:event('MUTATE_OUTPUT',0)
  if case==3:event('PROTECT_OUTPUT',0)
  if case==10:event('CHANGE_ACTION',1-restart)
  if case==19:event('EXIT_GROUP',0);counts['group_exits']+=1
  if case==18:counts['fatal_groups']+=1
  if case==17:counts['thread_exits']+=1
  if blocked:
   event('PENDING',1,actor=0);event('UNMASK',0,actor=0)
   if not one('RETURN')['position']<one('PENDING')['position']<one('UNMASK')['position']<one('HANDLE')['position']:raise ValueError('pending child signal delivered before normal completion/unmask')
  if case in (7,8,17):event('MAIN_REAP',child[0])
  if case==12:
   event('NEST_ATTEMPT',child[1],actor=0);event('NEST_EINTR',-4,actor=0);event('NEST_REAP',child[1],actor=0)
  returns=tagged('RETURN')
  if returns and sorted(r['actor'] for r in returns)!=list(range(nworkers)):raise ValueError('child waiter return duplicated or missing')
  for r in returns:
   if r['ordinal'] or r['actor']>=nworkers:raise ValueError('child return actor differs')
   expected=77 if caught and case==13 and not variant and again else (-1 if variant else -4) if caught and not again else (-1 if variant else -14) if case==3 else 0 if case==7 else (-1 if variant else -10) if case==8 else None if case in (14,15) else 0 if rv and not variant else child[0]
   if expected is not None and r['value']!=expected:raise ValueError('child raw/libc return result differs')
  outs=tagged('OUTPUT');counts['reaped_outputs']+=len(outs)
  for r in outs:
   if r['actor']>=nworkers or r['child'] not in child[:nchildren] or (r['status'],r['uid'],r['bytes'])!=((42+child.index(r['child']))<<8,(begin['uid'] or 1001) if rv and not variant else begin['uid'],128 if rv and not variant else 4):raise ValueError('child status/UID/full-record output differs')
  if case in (15,16) and {r['child'] for r in outs}!=set(child):raise ValueError('two-child reaping duplicated/lost a child')
  if case==14:
   winner=outs[0]['actor'];loser=1-winner
   expected_return={winner:0 if rv and not variant else child[0],loser:-1 if variant else -10}
   if any(r['value']!=expected_return[r['actor']] for r in returns):raise ValueError('competing child waiters did not produce one reap and ECHILD')
  # Bind every reported userspace output to its actor, request, selected child and temporal cause.
  for j in range(nworkers):
   actor_outs=[r for r in outs if r['actor']==j];actor_returns=[r for r in returns if r['actor']==j]
   actor_completes=[r for r in streams[j] if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='complete']
   if case==15:
    if len(actor_outs)!=1 or actor_returns[0]['value']!=(0 if rv and not variant else actor_outs[0]['child']) or actor_completes[0]['result']!=actor_outs[0]['child']:raise ValueError('any-child result/output disagrees with owned completion')
   if case==14 and actor_completes[0]['result']!=(child[0] if actor_outs else -10):raise ValueError('competing completion disagrees with reap/ECHILD output')
   for r in actor_outs:
    ordinal=int(case in (3,16) and (case!=16 or r['child']==child[1]) or caught and (not again or case==13 and not variant))
    if r['ordinal']!=ordinal:raise ValueError('child output belongs to wrong explicit retry')
    if case!=15 and r['child']!=(child[1] if case==16 and ordinal else child[0]):raise ValueError('child output changed deterministic selected child')
    if not actor_returns[0]['position']<r['position']:raise ValueError('child output precedes userspace return')
    if ordinal and not one('RETRY')['position']<r['position']:raise ValueError('child output precedes explicit retry')
    if not any(release['value']==r['child'] and release['position']<r['position'] for release in releases):raise ValueError('child output precedes its selected child release')
    if not immediate and case!=3 and not any(c['result']==r['child'] and positions[c['line']]<r['position'] for c in actor_completes):raise ValueError('child output lacks preceding owned successful reap')
   for completion in actor_completes:
    if case==3 and completion['result']==-14:
     if not one('PROTECT_OUTPUT')['position']<positions[completion['line']]<actor_returns[0]['position']:raise ValueError('child output fault is outside protection/return interval')
     continue
    released_child=completion['result'] if completion['result']>0 else child[0]
    release=next((r for r in releases if r['value']==released_child),None)
    if release is None or not release['position']<positions[completion['line']]:raise ValueError('child completion precedes the selected child release')
   if actor_returns and actor_completes and not positions[actor_completes[-1]['line']]<actor_returns[0]['position']:
    if not caught or again and not (case==13 and not variant):raise ValueError('child userspace return precedes owned completion')
  if case<18 and one('CASE_PASS')['position']!=max(r['position'] for r in rows if r['tag']!='CHILD_WAIT_PARENT_PASS'):raise ValueError('child case pass precedes its completed scenario')
  if case in (2,3,10):
   action=one({2:'MUTATE_OUTPUT',3:'PROTECT_OUTPUT',10:'CHANGE_ACTION'}[case]);next_action=one('RELEASE') if case==3 else one('SEND')
   if action['position']>=next_action['position']:raise ValueError('child admission mutation follows its triggering action')
  if case==15:
   rearm_rows=[r for r in case_native if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='rearm']
   first_complete=next(r for r in case_native if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='complete' and r['result']==child[0])
   if len(rearm_rows)!=1 or rearm_rows[0]['tid']==first_complete['tid'] or not positions[first_complete['line']]<positions[rearm_rows[0]['line']]<releases[1]['position']:raise ValueError('peer child wait did not rearm after losing the first reap')
  if blocked and sends[0]['position']>=tagged('ATTEMPT')[0]['position']:raise ValueError('pending child signal was not queued before entry')
  if case==5 and sends[0]['position']>=releases[0]['position']:raise ValueError('ignored child signal follows release')
  if case in (18,19,20):
   action=one({18:'SEND',19:'EXIT_GROUP',20:'EXEC_COMMIT'}[case])
   cancellation=next(r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='cancelled')
   if action['position']>=positions[cancellation['line']]:raise ValueError('child cleanup precedes lifecycle action')
  if caught:
   outer_signal=next(r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_SIGNAL')
   handler=one('HANDLE');exit_tag='THREAD_EXIT' if case==17 else 'HANDLER_EXEC' if case==21 else 'HANDLER_RETURN';handler_end=one(exit_tag)
   if not positions[outer_signal['line']]<handler['position']<handler_end['position']:raise ValueError('child handler entry/return order differs')
   owned_arms=[r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='arm']
   if case not in (17,21):
    fresh_position=positions[owned_arms[-1]['line']]
    if not handler_end['position']<fresh_position:raise ValueError('fresh child wait precedes handler return')
    if tagged('RETRY') and not one('RETRY')['position']<fresh_position:raise ValueError('fresh child wait precedes explicit retry')
   if sends[0]['position']>=positions[outer_signal['line']]:raise ValueError('caught child signal precedes its directed send')
   if case in (11,12) and not handler['position']<one('NESTED')['position']<handler_end['position']:raise ValueError('nested signal escaped its outer handler')
   if case==12:
    nested_signals=[r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_SIGNAL']
    nested_complete=next(r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_WAIT' and r['outcome']=='complete' and r['selector']==child[1])
    if not one('NEST_ATTEMPT')['position']<positions[owned_arms[1]['line']]<positions[nested_signals[1]['line']]:raise ValueError('nested child arm is outside attempt/interruption interval')
    if not one('NEST_EINTR')['position']<positions[owned_arms[2]['line']]<positions[nested_complete['line']]<one('NEST_REAP')['position']:raise ValueError('nested child retry/completion/reap order differs')
    if not handler['position']<one('NEST_ATTEMPT')['position']<positions[nested_signals[1]['line']]<one('NESTED')['position']<one('NEST_EINTR')['position']<one('NEST_REAP')['position']<handler_end['position']:raise ValueError('nested child attempt/interruption/reap order differs')
    if not one('NEST_ATTEMPT')['position']<sends[1]['position']<positions[nested_signals[1]['line']]:raise ValueError('nested child signal precedes send/attempt')
   if returns and not handler_end['position']<returns[0]['position']:raise ValueError('child userspace return precedes handler return')
  retry=tagged('RETRY')
  if retry and (retry[0]['actor'],retry[0]['ordinal'],retry[0]['value'])!=(0,1,child[1] if case==16 else child[0]):raise ValueError('child explicit retry changed selector')
  for h in [r for r in rows if HANDLER.fullmatch(r['line'])]:
   nested=h['tag']=='CHILD_WAIT_NESTED';inspected=caught and not (nested and case==11);edited=h['tag']=='CHILD_WAIT_HANDLER_RETURN' and case==13 and not variant and again
   if (h['pid'],h['tid'],h['depth'],h['inspected'])!=(pid,worker[0],2 if nested else 1,int(inspected)) or not instruction(arch,h['pc'],bool(form) if not variant else False):
    if not (arch=='arm32' and variant and (h['pid'],h['tid'],h['depth'],h['inspected'])==(pid,worker[0],2 if nested else 1,int(inspected)) and instruction(arch,h['pc'],True)):raise ValueError('invalid child handler owner/depth/PC')
   base={'tag','line','position','arch','variant','form','restart','case','actor','pid','tid','depth','inspected','pc'}
   extra={'number','result','a0','a1','a2','a3'}|({'cr','diagnostic_result','orig_r3'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set())
   if set(h)!=base|(extra if inspected else set()):raise ValueError('unexpected child handler context fields')
   if not inspected:continue
   signalrows=[r for r in streams[0] if r['tag']=='OK_NATIVE_CHILD_SIGNAL'];sig=signalrows[1 if nested else 0];again_here=again and not nested;input0=(1 if not any_child or nested else 0) if rv else child[1] if nested else maximum if any_child else child[0];input1=child[1] if nested else 0 if any_child else child[0] if rv else 0
   if not rv:input1=sig['output']
   elif variant and any_child and not nested:input1=maximum  # musl preserves -1 in P_ALL's ignored id field.
   input2=sig['output'] if rv else 0;input3=4 if rv else 0
   value=77 if edited else (NUMBERS[arch] if arch in ('x86_64','i386') or mips else input0) if again_here else 4 if mips or arch=='ppc' else maximum-3
   number=77 if edited and (arch in ('x86_64','i386') or mips) else NUMBERS[arch] if again_here or arch not in ('x86_64','i386') and not mips else value
   a0=value if arch in ('aarch64','arm32','rv32','rv64','loongarch64','ppc') and (not again_here or edited) else input0
   a3=0 if edited and mips else 1 if mips and not again_here else input3
   pc=begin['resume'] if edited else sig['pc']
   if (h['pc'],h['number'],h['result'],h['a0'],h['a1'],h['a2'],h['a3'])!=(pc,number,value,a0,input1,input2,a3):raise ValueError('child saved result, syscall or argument frame differs')
   if arch=='ppc' and (not 0<=h['cr']<=maximum or bool(h['cr']&0x10000000)==edited or h['diagnostic_result']!=(0x123 if edited else 0 if again_here else maximum-3) or h['orig_r3']!=(0x234 if edited else input0)):raise ValueError('child PPC saved ABI diagnostics changed')
   if arch=='arm32' and (not 0<=h['cpsr']<=maximum or h['cpsr']&0x0700ffdf!=0x10 or not instruction(arch,h['pc'],bool(h['cpsr']&0x20)) or (not variant or nested) and bool(h['cpsr']&0x20)!=bool(form)):raise ValueError('child ARM instruction/user mode changed')
   if arch=='arm32' and not nested and h['cpsr']!=one('HANDLE')['cpsr']:raise ValueError('child outer handler changed its unchanged CPSR')
  counts['handlers']+=len(tagged('HANDLE'));counts['nested_handlers']+=len(tagged('NESTED'))
  case_images=[i for i in range(start,end+1) if IMAGE.fullmatch(lines[i])]
  if len(case_images)!=int(case in (20,21)):raise ValueError('child case unexpected/missing image replacement')
  if case in (20,21):
   executor=0 if case==21 else 9;event('EXEC_FAILED',2,actor=executor);event('EXEC_COMMIT',pid,actor=executor);event('EXEC_REPLACED',child[0]);event('EXEC_REAP',child[0]);counts['exec_replacements']+=1
   if not one('EXEC_FAILED')['position']<one('EXEC_COMMIT')['position']<case_images[0]<one('EXEC_REPLACED')['position']<one('EXEC_REAP')['position']<end:raise ValueError('child ELF replacement did not execute/reap in new image')
  images+=len(case_images);counts['cases']+=1
 aggregate=probe_spec(arch,'child-wait-signals')[0]
 if lines.count(aggregate)!=1 or lines.index(aggregate)<=parents[-1]:raise ValueError('child aggregate not after parent checks')
 if any(GUEST_PREFIX in l and KERNEL_PREFIX not in l and i not in guest_lines and l!=aggregate for i,l in enumerate(lines)):raise ValueError('child guest record outside active case')
 if any(r['tag']=='OK_NATIVE_CHILD_SIGNAL' for r in native if r['line'] not in selected_native):raise ValueError('incidental child wait claims caught signal')
 counts['image_replacements']=images;return counts

def _validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='child-wait-signals'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated child wait smoke command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('child wait smoke boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final child wait smoke prompt')
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
        incidental = pipe_events(span,arch) + futex_events(span,arch,allow_signal=False) + poll_events(span,arch,allow_signal=False) + child_events(span,arch,baseline=child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=(13 if arch in ('arm32','ppc') else 9) or lines.count(marker)!=1 or
            any(line!=command and not WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered child-wait-smoke/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong child wait smoke image source')
        pipe_events(span,arch)
        futex_events(span,arch,allow_signal=False)
        poll_events(span,arch,allow_signal=False)
        observations.append(validate_cases(span,arch,child_baseline))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+PIPE_PATTERNS+FUTEX_PATTERNS+POLL_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_events(boot,arch)
    futex_events(boot,arch,allow_signal=False)
    poll_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('child wait smoke completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate child wait smoke frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty child wait smoke boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('child wait smoke commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('child wait smoke accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('child wait smoke command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('child wait smoke command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=13 if arch in ('arm32','ppc') else 9,scope='actual-user-private-child-wait-signals',
                observations=observations,owned_child_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_restart=True,temporary_masks=False,full_exec_replacement=True,
                job_control=False,production=False,physical=False,smp=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))


def validate_execution(serial,baseline_begin,probe_begin,probe_mid,probe_end,native_begin,arch,kind='child-wait-signals'):
    normalized,bounds=normalize_transcript(serial,(baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    return _validate_execution(normalized,*bounds,arch,kind)
