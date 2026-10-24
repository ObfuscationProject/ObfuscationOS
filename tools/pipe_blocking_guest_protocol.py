"""Exact multi-wait blocking-write guest contract, including byte stream evidence."""
import re
from functools import lru_cache
from native_pipe_vector_events import native_events,ARCHES,WORD32,instruction,WRITEV
from native_pipe_write_events import WRITE
from native_signal_delivery_x86_64_evidence import IMAGE
GUEST_PREFIX=b'PIPE_BLOCKING_'
KEY=rb'arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) vector=([01]) variant=([01]) form=([01]) restart=([01]) case=([0-9]+)'
N=rb'[0-9]+';I=rb'-?[0-9]+'
TAGS=('ATTEMPT','RETURN','ERRNO','RETRY','WORKER_PASS','AWAIT','EMPTY','BUFFER','SEND','CLOSE','THREAD_EXIT','HANDLER_RETURN','PROTECT_SUFFIX','RESTORE_SUFFIX','MUTATE_METADATA','PROTECT_PREFIX','RESTORE_PREFIX','MUTATE_PAYLOAD','REPLACE_FD','NONBLOCK_REPLACEMENT','NONBLOCK_SHARED','IGNORED','ATOMIC_PENDING','REPLACEMENT_BYTE','EXIT_GROUP','EXEC_FAILED','EXEC_COMMIT','EXEC_REPLACED','EXEC_BYTE','EXEC_CHECKED')
PATTERNS=(re.compile(rb'PIPE_BLOCKING_CASE_BEGIN '+KEY+rb' pid='+N+rb' uid='+N+rb' streams=[12] count='+N+rb' site='+N+rb' resume='+N+rb' syscall='+N+rb' capacity=4096'),
 re.compile(rb'PIPE_BLOCKING_WRITER '+KEY+rb' stream=[01] tid='+N+rb' fd='+I+rb' readfd='+I+rb' saved='+I+rb' replacement='+I+rb' replacementread='+I+rb' input='+N+rb' payload0='+N+rb' payload1='+N+rb' payload2='+N+rb' payload3='+N+rb' argcount='+N),
 re.compile(rb'PIPE_BLOCKING_('+'|'.join(TAGS).encode()+rb') '+KEY+rb' actor=(0|1|9) stream=[012] ordinal='+N+rb' value='+I),
 re.compile(rb'PIPE_BLOCKING_HANDLE '+KEY+rb' actor=0 stream=0 pid='+N+rb' tid='+N+rb' signal='+N+rb' code='+I+rb' sender='+N+rb' uid='+N+rb' again=[01] pc='+N+rb' result='+I+rb' number='+N+rb' a0='+N+rb' a1='+N+rb' a2='+N+rb' a3='+N+rb' abi='+N),
 re.compile(rb'PIPE_BLOCKING_READ_BEGIN '+KEY+rb' actor=9 stream=[01] ordinal='+N+rb' fill=[01] offset='+N+rb' bytes='+N),
 re.compile(rb'PIPE_BLOCKING_BYTES '+KEY+rb' actor=9 stream=[01] ordinal='+N+rb' fill=[01] offset='+N+rb' bytes='+N+rb' checksum='+N),
 re.compile(rb'PIPE_BLOCKING_CASE_PASS '+KEY),
 re.compile(rb'PIPE_BLOCKING_PARENT_PASS '+KEY+rb' pid='+N+rb' signal='+N),
 re.compile(rb'PIPE_BLOCKING_LINUX_WAIT '+KEY+rb' actor=9 stream=[01] phase='+N+rb' pid='+N+rb' tid='+N+rb' syscall='+N+rb' committed='+N),
 re.compile(rb'PIPE_BLOCKING_LINUX_SKIP '+KEY+rb' reason=native-final-suffix-capacity-not-linux-page-layout'),
 re.compile(rb'PIPE_BLOCKING_(?:LINUX_REFERENCE_)?PASS arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) variants=2 groups='+N+rb' cases='+N+rb' parent=1'))
KEYS=('vector','variant','form','restart','case')
def key(row):return tuple(row[k] for k in KEYS)
def combinations(arch):
 for vector in range(2):
  for variant in range(2):
   for form in range(2 if not variant and arch in ('arm32','ppc') else 1):
    for restart in range(2):
     for case in range(26):yield(vector,variant,form,restart,case)
def parse(raw,arch):
 rows=[]
 for pos,line in enumerate(raw.splitlines()):
  if GUEST_PREFIX not in line:continue
  if not any(p.fullmatch(line) for p in PATTERNS):raise ValueError('malformed or unknown blocking-write guest record')
  r=dict(tag=line.split()[0].decode().removeprefix('PIPE_BLOCKING_'),position=pos,line=line)
  for item in line.split()[1:]:
   n,v=item.decode().split('=');r[n]=v if n in ('arch','reason') else int(v)
  if r['arch']!=arch:raise ValueError('blocking-write guest architecture differs')
  rows.append(r)
 return rows

@lru_cache(maxsize=2048)
def checksum(offset,count,stream,case,fill=False):
 result=5381
 for i in range(offset,offset+count):
  value=241 if fill else (i*17+(i//4096)*53+31+stream*97)&255
  if not fill and case==11 and i>=4096:value^=0x5a
  result=((result*33)^value)&0xffffffff
 return result

def main_plan(b,writers,arch,linux):
 c=b['case'];count=b['count'];usr=16 if arch.startswith('mips') else 10;plan=[];offset=[0,0];ordinal=[0,0]
 def ev(tag,stream=0,order=0,value=0):plan.append(dict(tag=tag,actor=9,stream=stream,ordinal=order,value=value))
 def await_(stream,cursor,phase):
  if linux:plan.append(dict(tag='LINUX_WAIT',actor=9,stream=stream,phase=phase,pid=b['pid'],tid=writers[stream]['tid'],syscall=b['syscall'],committed=cursor))
  ev('AWAIT',stream,phase,cursor)
 def read(stream,n,fill=False):
  r=dict(actor=9,stream=stream,ordinal=ordinal[stream],fill=int(fill),offset=offset[stream],bytes=n);plan.append(dict(tag='READ_BEGIN',**r));plan.append(dict(tag='BYTES',**r,checksum=checksum(offset[stream],n,stream,c,fill)));ordinal[stream]+=1
  if not fill:offset[stream]+=n
 def finish(stream):
  while offset[stream]<count:
   read(stream,min(4096,count-offset[stream]))
   if offset[stream]+4096<count:await_(stream,offset[stream]+4096,10+offset[stream]//4096)
 full=c in (1,3,7,12,14,15,21,23)
 if c<22 or c==25:await_(0,0 if full else 4096,0)
 if c==25:await_(1,4096,0);read(0,4096);await_(0,8192,1);read(1,4096);await_(1,8192,1);finish(0);finish(1)
 elif c==2:read(0,4096);await_(0,8192,1);read(0,1);read(0,4096)
 elif c==3:ev('SEND',value=usr);await_(0,0,1);read(0,4096,True);await_(0,4096,2);finish(0)
 elif c in (4,5,6,7,17,18,19,20):
  if c in (5,6,18,19,20):read(0,4096);await_(0,8192,1)
  if c in (6,7):ev('CLOSE',value=writers[0]['readfd'])
  elif c==18:ev('BUFFER',value=65536);ev('EXIT_GROUP',value=8192);return plan
  elif c==19:
   ev('BUFFER',value=65536);ev('EXEC_FAILED',value=2);ev('EXEC_COMMIT',value=b['pid']);ev('EXEC_REPLACED',value=b['pid']);read(0,4096);ev('EMPTY',value=writers[0]['readfd']);ev('EXEC_BYTE',value=69);ev('EMPTY',value=writers[0]['readfd']);ev('EXEC_CHECKED',value=b['pid']);return plan
  else:ev('SEND',value=usr)
  if c==20:return plan
 elif c==8:ev('PROTECT_SUFFIX',value=4096);read(0,4096);ev('RESTORE_SUFFIX',value=4096)
 elif c==9:ev('MUTATE_METADATA',value=1);finish(0)
 elif c==10:ev('PROTECT_PREFIX',value=4096);finish(0);ev('RESTORE_PREFIX',value=4096)
 elif c==11:ev('MUTATE_PAYLOAD',value=4096);finish(0)
 elif c in (12,15):
  ev('REPLACE_FD',value=writers[0]['replacement'])
  if c==15:ev('NONBLOCK_REPLACEMENT',value=writers[0]['fd'])
  read(0,4096,True);await_(0,4096,1);finish(0)
 elif c in (13,14):ev('NONBLOCK_SHARED',value=writers[0]['saved']);read(0,4096,c==14)
 elif c==16:ev('SEND',value=usr);ev('IGNORED',value=1);finish(0)
 elif c==21:read(0,1,True);await_(0,0,1);ev('ATOMIC_PENDING',value=1);read(0,4095,True);read(0,4096)
 elif c in (0,1):
  if full:read(0,4096,True);await_(0,4096,1)
  finish(0)
 if c in (4,5,13,14,17,22):read(0,4096)
 if c==23:read(0,4096,True)
 for stream,w in enumerate(writers):
  ev('BUFFER',stream,value=65536)
  if c not in (6,7,24):ev('EMPTY',stream,value=w['readfd'])
  if c in (12,15):ev('EMPTY',2,value=w['replacementread']);ev('REPLACEMENT_BYTE',stream,value=82)
 return plan

def validate_cases(raw,arch,linux=False,native=None):
 if arch not in ARCHES or linux and arch!='x86_64':raise ValueError('unsupported blocking-write profile/reference')
 rows=parse(raw,arch);expected=list(combinations(arch));groups=len(expected)//26;finish='LINUX_REFERENCE_PASS' if linux else 'PASS';count=len(expected)-(groups if linux else 0)
 if (not rows or rows[-1]['tag']!=finish or any(r['tag'] in ('PASS','LINUX_REFERENCE_PASS') for r in rows[:-1]) or rows[-1]['groups']!=groups or rows[-1]['cases']!=count):raise ValueError('blocking-write final scope/cardinality differs')
 native=[] if linux else native_events(raw,arch,allow_signal=True) if native is None else native
 image_rows=[(i,line) for i,line in enumerate(raw.splitlines()) if IMAGE.fullmatch(line)]
 if linux and any(line.startswith(b'OK_NATIVE_') for line in raw.splitlines()):raise ValueError('native diagnostics in Linux blocking-write reference')
 result=dict(cases=count,groups=groups,streams=0,handlers=0,exec_replacements=0,signal_terminations=0,payload_bytes=0,fill_bytes=0,buffer_proofs=0,owned_requests=0,owned_rearms=0,Linux_wait_samples=0,explicit_operations=0);word=32 if arch in WORD32 else 64;maximum=(1<<word)-1;low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000);at=0;seen=set();assigned=set()
 for k in expected:
  v,variant,form,restart,c=k
  if linux and c==2:
   if rows[at]['tag']!='LINUX_SKIP' or key(rows[at])!=k:raise ValueError('missing explicit Linux suffix-geometry exclusion')
   at+=1;continue
  if rows[at]['tag']!='CASE_BEGIN' or key(rows[at])!=k:raise ValueError('blocking-write case matrix differs')
  end=next((i for i in range(at+1,len(rows)) if rows[i]['tag']=='PARENT_PASS'),None)
  if end is None:raise ValueError('missing blocking-write parent status')
  part=rows[at:end+1];at=end+1;b=part[0];wanted_count=12289 if c==1 else 8193 if c==2 else 4096 if c==21 else 0 if c==24 else 12288;streams=2 if c==25 else 1;op=(WRITEV if v else WRITE)[arch];usr=16 if arch.startswith('mips') else 10
  if any(key(r)!=k for r in part) or b['pid'] in seen or not 0<b['pid']<=0xffffffff or not 0<=b['uid']<=0xffffffff or b['count']!=wanted_count or b['streams']!=streams or b['syscall']!=op or b['resume']-b['site']!=(2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4):raise ValueError('blocking-write case identity/size differs')
  seen.add(b['pid']);writers=part[1:1+streams]
  if [r['tag'] for r in writers]!=['WRITER']*streams or [r['stream'] for r in writers]!=list(range(streams)):raise ValueError('blocking-write writer roles differ')
  descriptors=[];tids={b['pid']}
  for i,w in enumerate(writers):
   if not 0<w['tid']<=0xffffffff or w['tid'] in tids:raise ValueError('blocking-write thread role aliases')
   tids.add(w['tid']);fds=[w[n] for n in ('fd','readfd','saved','replacement','replacementread')]
   if any(not -1<=n<=(0x7fffffff if linux else 31) for n in fds) or w['fd']<0 or (w['readfd']==-1)!=(c==24) or (w['saved']>=0)!=(c in (12,13,14,15)) or (w['replacement']>=0)!=(c in (12,15)) or (w['replacementread']>=0)!=(c in (12,15)):raise ValueError('blocking-write descriptor roles/ranges differ')
   descriptors.extend(n for n in fds if n>=0)
   if any(w[f'payload{j}']!=w['payload0']+j*(8192 if v else 4096) for j in range(4)) or w['input']!=w['payload0']+(36864 if v else 0) or w['argcount']!=(5 if v else wanted_count):raise ValueError('blocking-write admitted payload/array differs')
   if not linux and (any(not low<=w[n]<high for n in ('input','payload0','payload1','payload2','payload3')) or w['payload0']<low+4096 or w['payload0']+61440>high or not low<=b['site']<b['resume']<high or not instruction(arch,b['site'])):raise ValueError('blocking-write native address bounds differ')
  if len(descriptors)!=len(set(descriptors)):raise ValueError('blocking-write descriptor roles alias')
  result['streams']+=streams;main=[r for r in part if r.get('actor')==9];plan=main_plan(b,writers,arch,linux)
  if len(main)!=len(plan) or any(r['tag']!=want['tag'] or any(r.get(n)!=value for n,value in want.items()) for r,want in zip(main,plan)):raise ValueError('blocking-write reader/progress/lifecycle order or byte proof differs')
  for r in main:
   if r['tag']=='BYTES':result['fill_bytes' if r['fill'] else 'payload_bytes']+=r['bytes']
   elif r['tag']=='BUFFER':result['buffer_proofs']+=1
   elif r['tag']=='LINUX_WAIT':result['Linux_wait_samples']+=1
  passes=[r for r in part if r['tag']=='CASE_PASS'];normal=c not in (18,19,20)
  accounted=[b]+writers+main+[r for r in part if r.get('actor') in (0,1)]+passes+[part[-1]]
  if len(accounted)!=len(part) or {r['position'] for r in accounted}!={r['position'] for r in part}:raise ValueError('blocking-write unassigned or duplicate structural record')
  if len(passes)!=int(normal) or passes and passes[0] is not part[-2] or (part[-1]['pid'],part[-1]['signal'])!=(b['pid'],usr if c==20 else 0):raise ValueError('blocking-write case/parent completion differs')
  handlers=[r for r in part if r['tag']=='HANDLE'];caught=c in (3,4,5,6,7,17)
  if len(handlers)!=int(caught):raise ValueError('blocking-write caught handler cardinality differs')
  h=handlers[0] if handlers else None;again=c==3 and restart;prefix=4096 if c in (4,17) else 8192 if c in (5,6) else -32 if c==7 else -4
  if h:
   w=writers[0];signal=13 if c in (6,7) else usr
   if (h['pid']!=b['pid'] or h['tid']!=w['tid'] or h['signal']!=signal or h['code']!=(0 if signal==13 else -6) or h['sender']!=b['pid'] or h['uid']!=b['uid'] or h['again']!=again or h['result']!=(0 if again else prefix) or h['a1']!=w['input'] or h['a2']!=w['argcount'] or again and (h['number']!=op or h['a0']!=w['fd']) or again and not variant and h['a3']!=0x1357 or not variant and h['pc']!=(b['site'] if again else b['resume'])):raise ValueError('blocking-write handler completed/restart frame differs')
   if not linux and (not low<=h['pc']<high or not instruction(arch,h['pc'])):raise ValueError('blocking-write handler PC outside native user code')
   if not again and arch.startswith('mips') and h['abi']!=int(prefix<0) or not again and arch=='ppc' and bool(h['abi']&0x10000000)!=(prefix<0) or arch=='arm32' and not variant and bool(h['abi']&0x20)!=bool(form):raise ValueError('blocking-write handler ABI status differs')
   result['handlers']+=1
  for stream,w in enumerate(writers):
   worker=[r for r in part if r.get('actor')==stream];want=[('ATTEMPT',0,op)]
   if stream==0 and caught:
    want += [('HANDLE',None,None),('THREAD_EXIT' if c==17 else 'HANDLER_RETURN',0,4096 if c==17 else 13 if c in (6,7) else usr)]
   expected_result=4096 if c in (4,8,14,22) else 8192 if c in (5,6,13) else (-1 if variant else -32) if c==7 else (-1 if variant else -11) if c==23 else wanted_count
   if c not in (17,18,19,20):
    if c==3 and not restart:want += [('RETURN',0,-1 if variant else -4),('ERRNO',0,4 if variant else 111),('RETRY',1,op)]
    ordinal=1 if c==3 and not restart else 0;error=32 if c==7 else 11 if c==23 else 0;want += [('RETURN',ordinal,expected_result),('ERRNO',ordinal,error if variant and expected_result==-1 else 111),('WORKER_PASS',0,expected_result)]
   if len(worker)!=len(want) or any(r['tag']!=tag or ordinal is not None and (r.get('ordinal'),r.get('value'))!=(ordinal,value) or r.get('stream')!=stream for r,(tag,ordinal,value) in zip(worker,want)):raise ValueError('blocking-write worker syscall/handler/return order differs')
   if worker[0]['position']<=writers[-1]['position']:raise ValueError('blocking-write attempt preceded published roles')
   result['explicit_operations']+=1+int(c==3 and not restart)
  native_case=[r for r in native if b['position']<r['position']<part[-1]['position']];assigned.update(r['position'] for r in native_case)
  if not linux:
   if any(r['pid']!=b['pid'] or r['tid'] not in {w['tid'] for w in writers} or r['direction']!=1 for r in native_case):raise ValueError('foreign pipe owner inside blocking-write case')
   for stream,w in enumerate(writers):
    owned=[r for r in native_case if r['tid']==w['tid']];arms=[r for r in owned if r['event']=='WAIT' and r['stage']=='arm'];terms=[r for r in owned if r['event']=='COMPLETE'];origins=[r for r in owned if r['event']=='ORIGIN'];signals=[r for r in owned if r['event']=='SIGNAL'];needed=0 if c in (22,23,24) else 2 if c==3 else 1
    if len(arms)!=needed or len(terms)!=needed or len(origins)!=needed or len(signals)!=int(c in (3,4,5,17)):raise ValueError('blocking-write owned request/origin/terminal cardinality differs')
    shape=((1,0),)+tuple((w[f'payload{j}'],max(0,min(4096,wanted_count-j*4096))) for j in range(4))
    for r in owned:
     if (r['vector']!=bool(v) or bool(r.get('large'))!=(wanted_count>4096) or r['fd']!=w['fd'] or r['array' if v else 'input']!=w['input'] or r['bytes']!=wanted_count or v and r['vectors']!=shape or r['event'] in ('ORIGIN','SIGNAL') and r['syscall']!=op):raise ValueError('blocking-write retained original request/description snapshot differs')
     cursor=r.get('committed',0)
     if r['event'] in ('WAIT','COMPLETE'):
      if not r.get('large'):cursor=max(0,r['result']) if r['event']=='COMPLETE' else 0
      reads=sum(x['bytes'] for x in main if x['tag']=='READ_BEGIN' and x['stream']==stream and x['position']<r['position']);initial=0 if c in (1,3,7,12,14,15,21,23) else 4096
      if cursor>initial+reads:raise ValueError('blocking-write publication preceded reader capacity')
    attempt=next(r for r in part if r['tag']=='ATTEMPT' and r['stream']==stream)
    if arms and arms[0]['position']<=attempt['position']:raise ValueError('blocking-write request preceded syscall attempt')
    for a,o in zip(arms,origins):
     if a['request']!=o['request'] or not a['position']<o['position'] or not variant and o['pc']!=b['resume']:raise ValueError('blocking-write origin changed exact continuation')
    for awaited in (r for r in main if r['tag']=='AWAIT' and r['stream']==stream):
     previous=[r for r in owned if r['position']<awaited['position']];latest=next((r for r in reversed(previous) if r['event'] in ('WAIT','COMPLETE')),None)
     if latest is None or latest['event']!='WAIT' or latest.get('committed',0)!=awaited['value']:raise ValueError('blocking-write AWAIT lacks current owned committed cursor')
    terminal_specs=[]
    if needed:
     if c==3:terminal_specs=[('interrupted',0 if restart else -4,0),('ready',wanted_count,wanted_count)]
     elif c in (4,5,17):terminal_specs=[('interrupted',4096 if c!=5 else 8192,4096 if c!=5 else 8192)]
     elif c in (6,7):terminal_specs=[('error',8192 if c==6 else -32,8192 if c==6 else 0)]
     elif c==8:terminal_specs=[('efault',4096,4096)]
     elif c in (18,19,20):terminal_specs=[('cancelled',-125,8192)]
     else:terminal_specs=[('ready',expected_result,expected_result if wanted_count>4096 else 0)]
    for terminal,(cause,value,cursor) in zip(terms,terminal_specs):
     if (terminal['outcome'],terminal['result'],terminal.get('committed',0))!=(cause,value,cursor):raise ValueError('blocking-write terminal cause/prefix differs')
    returns=[r for r in part if r['tag']=='RETURN' and r['stream']==stream]
    if terms and returns and terms[-1]['position']>=returns[-1]['position']:raise ValueError('blocking-write returned before retiring owner')
    if h:
     if terms[0]['position']>=h['position'] or h['pc']!=(signals[0]['pc'] if signals else origins[0]['pc']):raise ValueError('blocking-write handler preceded terminal or moved completed PC')
     trigger=next(r for r in main if r['tag'] in ('SEND','CLOSE'))
     if trigger['position']>=terms[0]['position']:raise ValueError('blocking-write signal/reader-loss terminal preceded trigger')
    if c==3:
     resumed=next(r for r in part if r['tag']==('HANDLER_RETURN' if restart else 'RETRY'))
     if not terms[0]['position']<h['position']<resumed['position']<arms[1]['position']<terms[1]['position']:raise ValueError('blocking-write restart lacks fresh owned request')
    if c==8:
     protected=next(r for r in main if r['tag']=='PROTECT_SUFFIX');restored=next(r for r in main if r['tag']=='RESTORE_SUFFIX')
     read_begin=next(r for r in main if r['tag']=='READ_BEGIN')
     if not protected['position']<read_begin['position']<terms[0]['position']<restored['position']:raise ValueError('blocking-write fault terminal outside protected suffix interval')
    if c in (18,19,20):
     trigger=next(r for r in main if r['tag'] in ('EXIT_GROUP','EXEC_COMMIT','SEND'))
     if trigger['position']>=terms[0]['position']:raise ValueError('blocking-write lifecycle terminal preceded trigger')
    for proof in (r for r in main if r['tag']=='BYTES' and r['stream']==stream and not r['fill']):
     before=[r for r in owned if r['event'] in ('WAIT','COMPLETE') and r['position']<proof['position']];bound=max((r.get('committed',r['result'] if r['event']=='COMPLETE' and r['result']>0 else 0) for r in before),default=4096 if c==22 else 0)
     if proof['offset']+proof['bytes']>bound:raise ValueError('blocking-write byte proof exceeded published prefix')
    if c not in (18,19,20):
     worker_done=next(r for r in part if r['tag']==('THREAD_EXIT' if c==17 else 'WORKER_PASS') and r['stream']==stream)
     buffer=next(r for r in main if r['tag']=='BUFFER' and r['stream']==stream)
     if buffer['position']<=worker_done['position']:raise ValueError('blocking-write buffer proof preceded worker retirement')
    result['owned_requests']+=needed;result['owned_rearms']+=sum(r['event']=='WAIT' and r['stage']=='rearm' for r in owned)
   images=[(i,line) for i,line in image_rows if b['position']<i<part[-1]['position']]
   if len(images)!=int(c==19):raise ValueError('blocking-write lifecycle image count differs')
   if images:
    terminal=next(r for r in native_case if r['event']=='COMPLETE');replaced=next(r for r in main if r['tag']=='EXEC_REPLACED')
    if not terminal['position']<images[0][0]<replaced['position']:raise ValueError('blocking-write replacement image preceded wait retirement')
   if c==25 and max((r.get('live',0) for r in native_case),default=0)!=2:raise ValueError('blocking-write dual streams never simultaneously owned')
  result['exec_replacements']+=c==19;result['signal_terminations']+=c==20
 if at!=len(rows)-1 or len(assigned)!=len(native):raise ValueError('blocking-write records escaped dedicated case scope')
 result.update(scope='host-Linux-complete-blocking-write-reference' if linux else 'actual-native-private-complete-blocking-write',native_OS_execution=not linux,full_blocking_large_write=True,automatic_sigpipe=True,production=False,physical=False,smp=False)
 return result
