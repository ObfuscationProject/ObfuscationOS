"""Exact scalar/vector pipe ownership composition; a ledger is not execution evidence."""
import re
from native_futex_events import WORD32,instruction
from native_signal_delivery_x86_64_evidence import IMAGE
from native_pipe_signal_evidence import READ
from native_pipe_write_events import WRITE
ARCHES=tuple(READ)
READV=dict(zip(ARCHES,(19,145,65,145,65,65,65,4145,5018,145)))
WRITEV=dict(zip(ARCHES,(20,146,66,146,66,66,66,4146,5019,146)))
N=rb'([0-9]+)'
V=rb' iovcnt='+N+rb' vectors=([0-9]+:[0-9]+(?:,[0-9]+:[0-9]+){0,15})'
PATTERNS=[];SCHEMAS=[]
for direction in (0,1):
 for vector in (False,True):
  prefix=b'OK_NATIVE_PIPE_'+(b'WRITEV_' if direction else b'READV_') if vector else b'OK_NATIVE_PIPE_'+(b'WRITE_' if direction else b'READ_')
  field=b'array' if vector else b'input' if direction else b'output'
  identity=rb'pid='+N+rb' tid='+N+rb' wait='+N+rb' request='+N+b' '+field+b'='+N+rb' fd='+N+rb' description='+N+rb' pipe='+N+rb' bytes='+N+(V if vector else b'')
  pub=rb'pid='+N+rb' tid='+N+rb' request='+N+rb' wait='+N+rb' origin='+N
  args=rb' pc='+N+rb' syscall='+N+rb' fd='+N+b' '+field+b'='+N+rb' bytes='+N+(V if vector else b'')
  origins=prefix if vector or direction else b'OK_NATIVE_PIPE_'
  for tag,expression in [('WAIT',prefix+b'WAIT '+identity+rb' stage=(arm|rearm) live='+N),('COMPLETE',prefix+b'COMPLETE '+identity+rb' result=(-?[0-9]+) outcome=(ready|eof|efault|cancelled|error|interrupted) pinned=([01]) live='+N),('ORIGIN',origins+b'ORIGIN '+pub+args),('SIGNAL',origins+b'SIGNAL '+pub+rb' signal='+N+rb' outcome=(eintr|restart)'+args+rb' pinned=([01]) live='+N)]:
   p=re.compile(expression);PATTERNS.append(p);SCHEMAS.append((p,direction,vector,tag,field.decode()))
from native_pipe_large_events import schemas as large_schemas,terminal as large_terminal
SCHEMAS=[(*row,False) for row in SCHEMAS]+large_schemas(re,N,V)
PATTERNS=tuple(row[0] for row in SCHEMAS)
PREFIX=b'OK_NATIVE_PIPE_'

def native_events(span,arch,allow_signal=False):
 if arch not in READV:raise ValueError('unsupported pipe vector architecture')
 word=32 if arch in WORD32 else 64;maximum=(1<<word)-1;low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000)
 active=({},{});waits={};origins={};events=[];previous=None;pending=None
 for position,line in enumerate(span.splitlines()):
  if not line:continue
  if pending is not None and not line.startswith(pending['signal_prefix']):raise ValueError('pipe interrupted retirement lacks adjacent signal publication')
  if line.startswith(b'OK_NATIVE_IMAGE '):
   if not IMAGE.fullmatch(line) or pending is not None:raise ValueError('malformed image or interrupted publication across exec')
   # IMAGE has no owner identity. An unrelated process may exec while a parent
   # remains blocked; preserve every live owner's request and generation history.
   live_owners=set(active[0])|set(active[1])
   waits={owner:value for owner,value in waits.items() if owner in live_owners}
   origins={owner:value for owner,value in origins.items() if owner in live_owners}
  if PREFIX not in line:previous=None;continue
  schema=next((s for s in SCHEMAS if s[0].fullmatch(line)),None)
  if schema is None:raise ValueError('malformed or unknown pipe diagnostic')
  _,direction,vector,tag,field,large=schema
  row=dict(tag=line.split()[0].decode(),line=line,position=position,direction=direction,vector=vector,event=tag)
  if large:row['large']=True
  for item in line.split()[1:]:
   k,v=item.decode().split('=',1);row[k]=tuple(tuple(map(int,p.split(':'))) for p in v.split(',')) if k=='vectors' else v if k in ('stage','outcome') else int(v)
  owner=(row['pid'],row['tid']);buffer=row[field];count=row['bytes'];limit=(1<<(word-1))-1 if large else 4097 if direction else 4096
  if (not all(0<n<=0xffffffff for n in owner) or not 0<row['request']<=row['wait']<=0xffffffffffffffff or not low<=buffer<high or not 0<count<=limit or not 0<=row['fd']<32):raise ValueError('invalid pipe request identity/range')
  if large and (not 4096<count<=limit or not 0<=row['committed']<=count or tag=='WAIT' and row['committed']>=count):raise ValueError('invalid large pipe committed range')
  shape=()
  if vector:
   shape=row['vectors'];total=sum(n for p,n in shape)
   if (not 1<=row['iovcnt']<=16 or len(shape)!=row['iovcnt'] or row['iovcnt']*2*(word//8)>high-buffer or not 0<total<=(1<<(word-1))-1 or count!=min(total,limit)):raise ValueError('invalid copied vector count/sum/staged bytes')
   for base,length in shape:
    if not 0<=base<=maximum or not 0<=length<=maximum or length and (not low<=base<high or length>high-base):raise ValueError('invalid copied vector payload span')
  elif count>high-buffer:raise ValueError('invalid scalar pipe payload span')
  identity=(large,vector,row['pid'],row['tid'],row['request'],buffer,row['fd'],count,shape)
  state=active[direction].get(owner)
  if tag in ('WAIT','COMPLETE'):
   if not 0<=row['description']<256 or not 0<=row['pipe']<16:raise ValueError('invalid pipe/open-description object')
   retained=identity+(row['description'],row['pipe'])
   if tag=='WAIT':
    if row['wait']<=waits.get(owner,0):raise ValueError('stale pipe wait ticket')
    if row['stage']=='arm':
     if owner in active[0] or owner in active[1] or row['wait']!=row['request']:raise ValueError('duplicate pipe wait or non-fresh initial request')
     state=dict(identity=identity,retained=retained,wait=row['wait'],origin=None,arm=row,committed=row.get('committed',0));active[direction][owner]=state
    else:
     if state is None or state['retained']!=retained:raise ValueError('pipe rearm changed copied vectors or retained description')
     if large and not 0<=row['committed']-state['committed']<=4096:raise ValueError('large pipe rearm regressed or skipped a bounded fragment')
     state['wait']=row['wait'];state['committed']=row.get('committed',0)
    if large and row['stage']=='arm' and row['committed']>4096:raise ValueError('large pipe admission exceeds one fragment')
    waits[owner]=row['wait']
   else:
    if state is None or state['retained']!=retained or state['wait']!=row['wait'] or row['pinned']:raise ValueError('pipe completion lost exact request/pin')
    value,outcome=row['result'],row['outcome']
    if large:large_terminal(row,state['committed'])
    if (not -(1<<63)<=value<(1<<63) or not large and (outcome=='ready' and (not 0<value<=min(count,4096) or direction and count<=4096 and value!=count) or outcome=='eof' and (direction or value!=0) or outcome=='efault' and value!=-14 or outcome=='cancelled' and value!=-125 or outcome=='error' and (value>=0 or value in (-4,-14,-125)) or outcome=='interrupted' and value not in (-4,0))):raise ValueError('pipe terminal cause/result/atomicity mismatch')
    row['arm']=state['arm'];row['origin_record']=state['origin'];del active[direction][owner]
    if outcome=='interrupted':
     if state['origin'] is None:raise ValueError('pipe interruption lacks typed origin')
     row['signal_prefix']=(b'OK_NATIVE_PIPE_WRITEV_LARGE_' if vector else b'OK_NATIVE_PIPE_WRITE_LARGE_')+b'SIGNAL ' if large else (b'OK_NATIVE_PIPE_WRITEV_' if direction else b'OK_NATIVE_PIPE_READV_')+b'SIGNAL ' if vector else (b'OK_NATIVE_PIPE_WRITE_SIGNAL ' if direction else b'OK_NATIVE_PIPE_SIGNAL ');pending=row
   if row['live']!=len(active[direction]):raise ValueError('combined scalar/vector pipe live count differs')
  elif tag=='ORIGIN':
   op=(WRITEV if direction else READV)[arch] if vector else (WRITE if direction else READ)[arch]
   if (state is None or state['identity']!=identity or state['origin'] is not None or previous is not state['arm'] or row['wait']!=row['request'] or row['syscall']!=op or not origins.get(owner,0)<row['origin']<=0xffffffffffffffff or not low<=row['pc']<high or not instruction(arch,row['pc'])):raise ValueError('pipe origin does not bind immediately preceding copied request')
   if large and row['committed']!=state['committed']:raise ValueError('large pipe origin changed admission cursor')
   state['origin']=row;origins[owner]=row['origin']
  else:
   if not allow_signal or pending is None or previous is not pending:raise ValueError('unpermitted or orphan pipe signal')
   origin=pending['origin_record'];widths=(2,) if arch in ('x86_64','i386') else (2,4) if arch=='arm32' else (4,)
   if (direction!=pending['direction'] or vector!=pending['vector'] or any(row[k]!=pending[k] for k in ('pid','tid','request','wait','fd',field,'bytes','pinned','live')) or vector and row['vectors']!=pending['vectors'] or any(row[k]!=origin[k] for k in ('origin','syscall')) or row['signal'] not in ((16,17) if arch.startswith('mips') else (10,12)) or not low<=row['pc']<high or not instruction(arch,row['pc']) or pending['result']!=(row.get('committed',0) if row['outcome']=='partial' else -4 if row['outcome']=='eintr' else 0) or row['outcome'] in ('eintr','partial') and row['pc']!=origin['pc'] or row['outcome']=='restart' and origin['pc']-row['pc'] not in widths):raise ValueError('pipe signal changed retired vectors or saved continuation')
   if bool(pending.get('large'))!=large or large and (row['committed']!=pending['committed'] or (row['outcome']=='partial')!=(row['committed']>0)):raise ValueError('large pipe signal replayed or lost committed prefix')
   row['terminal']=pending;row['origin_record']=origin;pending=None
  events.append(row);previous=row
 if active[0] or active[1] or pending is not None:raise ValueError('pipe request/publication escaped boundary')
 return events
