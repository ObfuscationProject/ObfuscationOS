"""Strict completed-EPIPE guest contract; synthetic parsing is not execution."""
import re
from native_pipe_vector_events import native_events,WORD32,instruction,ARCHES,WRITEV
from native_pipe_write_events import WRITE
GUEST_PREFIX=b'PIPE_SIGPIPE_'
KEY=rb'arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) vector=([01]) variant=([01]) form=([01]) restart=([01]) resumed=([01]) case=([0-9]+)'
N=rb'[0-9]+';I=rb'-?[0-9]+'
EVENT_TAGS=('QUEUE','PENDING','ATTEMPT','RETURN','ERRNO','EDIT','HANDLER_RETURN','SIBLING','ACTION_CAUGHT','UNMASK','WORKER_PASS','CLOSE','BUFFER','FILL','EMPTY')
PATTERNS=(re.compile(rb'PIPE_SIGPIPE_CASE_BEGIN '+KEY+rb' pid='+N+rb' tid='+N+rb' sibling='+N+rb' uid='+N+rb' fd='+I+rb' readfd='+I+rb' input='+N+rb' bytes='+N+rb' payload0='+N+rb' payload1='+N+rb' site='+N+rb' resume='+N+rb' syscall='+N+rb' capacity=4096'),
 re.compile(rb'PIPE_SIGPIPE_('+'|'.join(EVENT_TAGS).encode()+rb') '+KEY+rb' actor=(0|1|9) ordinal='+N+rb' value='+I),
 re.compile(rb'PIPE_SIGPIPE_HANDLE '+KEY+rb' actor=0 pid='+N+rb' tid='+N+rb' signal='+N+rb' code='+I+rb' sender='+N+rb' uid='+N+rb' inspected=[01] pc='+N+rb' result='+I+rb' a1='+N+rb' a2='+N+rb' abi='+N),
 re.compile(rb'PIPE_SIGPIPE_CASE_PASS '+KEY),
 re.compile(rb'PIPE_SIGPIPE_PARENT_PASS '+KEY+rb' pid='+N+rb' signal='+N),
 re.compile(rb'PIPE_SIGPIPE_LINUX_WAIT '+KEY+rb' pid='+N+rb' tid='+N+rb' syscall='+N),
 re.compile(rb'PIPE_SIGPIPE_(?:LINUX_REFERENCE_)?PASS arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) variants=2 groups='+N+rb' cases='+N+rb' parent=1'))
KEYS=('vector','variant','form','restart','resumed','case')
def key(row):return tuple(row[k] for k in KEYS)
def combinations(arch):
 for v in range(2):
  for variant in range(2):
   for form in range(2 if not variant and arch in ('arm32','ppc') else 1):
    for restart in range(2):
     for resumed in range(2):
      for case in range(14):yield (v,variant,form,restart,resumed,case)
def parse(span,arch):
 rows=[]
 for pos,line in enumerate(span.splitlines()):
  if GUEST_PREFIX not in line:continue
  if not any(p.fullmatch(line) for p in PATTERNS):raise ValueError('malformed or unknown SIGPIPE guest record')
  r=dict(tag=line.split()[0].decode().removeprefix('PIPE_SIGPIPE_'),position=pos,line=line)
  for item in line.split()[1:]:
   k,v=item.decode().split('=');r[k]=v if k=='arch' else int(v)
  if r['arch']!=arch:raise ValueError('SIGPIPE guest architecture differs')
  rows.append(r)
 return rows

def validate_cases(span,arch,linux=False,native=None):
 if arch not in ARCHES or linux and arch!='x86_64':raise ValueError('unsupported SIGPIPE profile/reference')
 rows=parse(span,arch);expected=list(combinations(arch));groups=len(expected)//14
 finish='LINUX_REFERENCE_PASS' if linux else 'PASS'
 if (not rows or rows[-1]['tag']!=finish or any(r['tag'] in ('PASS','LINUX_REFERENCE_PASS') for r in rows[:-1]) or rows[-1]['groups']!=groups or rows[-1]['cases']!=len(expected)):raise ValueError('SIGPIPE final pass namespace/cardinality differs')
 if native is None:native=[] if linux else native_events(span,arch,allow_signal=False)
 if linux and any(line.startswith(b'OK_NATIVE_') for line in span.splitlines()):raise ValueError('native diagnostics in Linux SIGPIPE reference')
 begin=[i for i,r in enumerate(rows) if r['tag']=='CASE_BEGIN'];ends=[i for i,r in enumerate(rows) if r['tag']=='PARENT_PASS']
 if len(begin)!=len(expected) or len(ends)!=len(expected) or [key(rows[i]) for i in begin]!=expected:raise ValueError('SIGPIPE case matrix differs')
 word=32 if arch in WORD32 else 64;maximum=(1<<word)-1;low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000)
 seen=set();owned_positions=set();counts=dict(cases=len(expected),groups=groups,handlers=0,signal_terminations=0,owned_waits=0,observed_Linux_waits=0,buffer_proofs=0,explicit_operations=0)
 prior=-1
 for start,end,k in zip(begin,ends,expected):
  if start!=prior+1 or not start<end:raise ValueError('SIGPIPE cases overlap or contain loose records')
  prior=end;part=rows[start:end+1];b=part[0];v,variant,form,restart,resumed,c=k;blocked=resumed and c<10;deferred=3<=c<=8;fatal=c in (0,4);op=(WRITEV if v else WRITE)[arch]
  if any(key(r)!=k for r in part):raise ValueError('SIGPIPE crossed guest case')
  if (b['pid'] in seen or len({b['pid'],b['tid'],b['sibling']})!=3 or any(not 0<n<=0xffffffff for n in (b['pid'],b['tid'],b['sibling'])) or b['syscall']!=op or b['bytes']!=(3 if v else 0 if c==10 else 13) or b['fd']!=(-1 if c==11 else b['fd']) or c!=11 and b['fd']<0 or b['readfd']!=(-1 if not blocked and c<12 else b['readfd']) or (blocked or c>=12) and b['readfd']<0 or b['readfd']>=0 and b['readfd']==b['fd'] or b['payload1']-b['payload0']!=8192 or not v and b['input']!=b['payload0'] or b['uid']>0xffffffff):raise ValueError('SIGPIPE role/descriptor/payload identity differs')
  if not -1<=b['fd']<=0x7fffffff or not -1<=b['readfd']<=0x7fffffff:raise ValueError('SIGPIPE descriptor outside signed range')
  if not linux and (any(not low<=b[n]<high for n in ('input','payload0','payload1','site','resume')) or not instruction(arch,b['site']) or b['resume']-b['site']!=(2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4)):raise ValueError('SIGPIPE address/trap bounds differ')
  if not linux and any(b[field]>=32 for field in ('fd','readfd')):raise ValueError('SIGPIPE descriptor exceeds native SDK31 table')
  seen.add(b['pid']);expected_rows=[]
  def tag(t):expected_rows.append((t,None,None,None))
  def event(t,actor,ordinal,value):expected_rows.append((t,actor,ordinal,value))
  def handler(signal):
   tag('HANDLE')
   if c==9:event('EDIT',0,0,77)
   event('HANDLER_RETURN',0,0,signal)
  tag('CASE_BEGIN')
  usr=16 if arch.startswith('mips') else 10
  if c in (7,8):event('QUEUE',0,0,13 if c==7 else usr);event('PENDING',0,0,1 if c==7 else 2)
  event('ATTEMPT',0,0,op)
  if blocked:
   if linux:tag('LINUX_WAIT')
   event('CLOSE',9,0,b['readfd'])
  if c in (1,9):handler(13)
  if c!=0:
   code=9 if c==11 else 14 if c==12 else 11 if c==13 else 32;result=77 if c==9 else 0 if c==10 else -1 if variant else -code
   event('RETURN',0,0,result);event('ERRNO',0,0,code if variant and result==-1 else 111)
   if c==6:event('ATTEMPT',0,1,op);event('RETURN',0,1,-1 if variant else -32);event('ERRNO',0,1,32 if variant else 111)
   event('PENDING',0,0,(1+2*(c==8)) if deferred else 0);event('PENDING',1,0,0);event('SIBLING',1,0,b['sibling'])
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
    tag('CASE_PASS')
  tag('PARENT_PASS')
  if len(part)!=len(expected_rows):raise ValueError('SIGPIPE case record cardinality differs')
  for r,(t,a,o,value) in zip(part,expected_rows):
   if r['tag']!=t or a is not None and (r['actor'],r['ordinal'],r['value'])!=(a,o,value):raise ValueError('SIGPIPE exact causal role/order/value differs')
   if t=='HANDLE':
    signal=usr if c==8 and any(x['tag']=='HANDLE' for x in part[:part.index(r)]) else 13;inspected=signal==13 and not deferred
    if (r['pid']!=b['pid'] or r['tid']!=b['tid'] or r['signal']!=signal or r['code']!=(-6 if c==7 or signal==usr else 0) or r['sender']!=b['pid'] or r['uid']!=b['uid'] or r['inspected']!=inspected or r['result']!=(-32 if inspected else 0) or r['a1']!=(b['input'] if inspected else 0) or r['a2']!=(b['bytes'] if inspected else 0) or inspected and not variant and r['pc']!=b['resume'] or not linux and (not low<=r['pc']<high or not instruction(arch,r['pc'])) or inspected and arch.startswith('mips') and r['abi']!=1 or inspected and arch=='ppc' and not r['abi']&0x10000000 or inspected and arch=='arm32' and not variant and bool(r['abi']&0x20)!=bool(form)):raise ValueError('SIGPIPE completed handler payload/context differs')
    counts['handlers']+=1
   if t=='LINUX_WAIT':
    if (r['pid'],r['tid'],r['syscall'])!=(b['pid'],b['tid'],op):raise ValueError('Linux SIGPIPE observed wrong caller syscall')
    counts['observed_Linux_waits']+=1
  if (part[-1]['pid'],part[-1]['signal'])!=(b['pid'],13 if fatal else 0):raise ValueError('SIGPIPE exact parent status differs')
  owned=[r for r in native if b['position']<r['position']<part[-1]['position']]
  owned_positions.update(r['position'] for r in owned)
  if not linux:
   if not blocked and owned:raise ValueError('SIGPIPE immediate operation invented a blocked owner')
   if blocked:
    arm=[r for r in owned if r['event']=='WAIT' and r['stage']=='arm'];origin=[r for r in owned if r['event']=='ORIGIN'];term=[r for r in owned if r['event']=='COMPLETE'];attempt=next(r for r in part if r['tag']=='ATTEMPT');close=next(r for r in part if r['tag']=='CLOSE');after=next(r for r in part if r['tag'] in ('HANDLE','RETURN','PARENT_PASS'))
    if len(arm)!=1 or len(origin)!=1 or len(term)!=1 or any(r['event'] not in ('WAIT','ORIGIN','COMPLETE') for r in owned):raise ValueError('SIGPIPE owned terminal cardinality differs')
    a,o,t=arm[0],origin[0],term[0]
    if (not attempt['position']<a['position']<o['position']<close['position']<t['position']<after['position'] or t['result']!=-32 or t['outcome']!='error' or t['pinned'] or any(r['pid']!=b['pid'] or r['tid']!=b['tid'] or r['direction']!=1 or r['vector']!=bool(v) or r['fd']!=b['fd'] or r['array' if v else 'input']!=b['input'] or r['bytes']!=(32 if v else 13) or v and r['vectors']!=((1,0),(b['payload0'],13),(b['payload1'],19)) for r in owned) or o['syscall']!=op or not variant and o['pc']!=b['resume']):raise ValueError('SIGPIPE owned completed EPIPE order/identity differs')
    inspected=[r for r in part if r['tag']=='HANDLE' and r['inspected']]
    if inspected and inspected[0]['pc']!=o['pc']:raise ValueError('SIGPIPE completed frame moved saved origin PC')
    counts['owned_waits']+=1
  counts['signal_terminations']+=fatal;counts['buffer_proofs']+=not fatal;counts['explicit_operations']+=1+(c==6)
 if not linux and len(owned_positions)!=len(native):raise ValueError('SIGPIPE pipe owner escaped dedicated case')
 if prior!=len(rows)-2:raise ValueError('SIGPIPE loose records before final pass')
 counts.update(scope='host-Linux-automatic-SIGPIPE-reference' if linux else 'actual-native-private-automatic-SIGPIPE',native_OS_execution=not linux,automatic_sigpipe=True,production=False,physical=False,smp=False)
 return counts
