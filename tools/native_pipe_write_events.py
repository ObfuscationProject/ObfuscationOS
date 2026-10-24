"""Owned scalar pipe write diagnostics; this ledger alone is not execution evidence."""
import re
from native_futex_events import instruction,WORD32
from native_signal_delivery_x86_64_evidence import IMAGE
WRITE=dict(zip(('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc'),(1,4,64,4,64,64,64,4004,5001,4)))
PREFIX=b'OK_NATIVE_PIPE_WRITE_'
IDENTITY=rb'pid=([0-9]+) tid=([0-9]+) wait=([0-9]+) request=([0-9]+) input=([0-9]+) fd=([0-9]+) description=([0-9]+) pipe=([0-9]+) bytes=([0-9]+)'
WAIT=re.compile(PREFIX+rb'WAIT '+IDENTITY+rb' stage=(arm|rearm) live=([0-9]+)')
COMPLETE=re.compile(PREFIX+rb'COMPLETE '+IDENTITY+rb' result=(-?[0-9]+) outcome=(ready|efault|cancelled|error|interrupted) pinned=([01]) live=([0-9]+)')
PUBLICATION=rb'pid=([0-9]+) tid=([0-9]+) request=([0-9]+) wait=([0-9]+) origin=([0-9]+)'
ARGUMENTS=rb' pc=([0-9]+) syscall=([0-9]+) fd=([0-9]+) input=([0-9]+) bytes=([0-9]+)'
ORIGIN=re.compile(PREFIX+rb'ORIGIN '+PUBLICATION+ARGUMENTS)
SIGNAL=re.compile(PREFIX+rb'SIGNAL '+PUBLICATION+rb' signal=([0-9]+) outcome=(eintr|restart)'+ARGUMENTS+rb' pinned=([01]) live=([0-9]+)')
PATTERNS=(WAIT,COMPLETE,ORIGIN,SIGNAL)

def parsed(pattern,line):
 if not pattern.fullmatch(line):raise ValueError('malformed scalar pipe write diagnostic')
 row={'tag':line.split()[0].decode(),'line':line}
 for field in line.split()[1:]:
  key,value=field.decode().split('=',1);row[key]=value if key in ('stage','outcome') else int(value)
 return row

def native_events(span,arch,allow_signal=False):
 if arch not in WRITE:raise ValueError('unsupported scalar pipe write architecture')
 maximum=(1<<(32 if arch in WORD32 else 64))-1
 low,high=(0x10000000,0x40000000) if arch in ('arm32','aarch64') else (0x40000000,0x80000000)
 active={};waits={};origins={};events=[];pending=None;previous=b''
 identity_fields=('pid','tid','request','input','fd','description','pipe','bytes')
 for line in span.splitlines():
  if line.startswith(b'OK_NATIVE_IMAGE '):
   if not IMAGE.fullmatch(line):raise ValueError('malformed image cannot reset scalar write generations')
   if active or pending is not None:raise ValueError('image replacement retained scalar pipe write objects')
   waits.clear();origins.clear()
  if PREFIX not in line:
   if line:
    if pending is not None:raise ValueError('write interruption missing immediate signal publication')
    previous=line
   continue
  pattern=next((p for p in PATTERNS if p.fullmatch(line)),None)
  if pattern is None:raise ValueError('malformed/unexpected scalar pipe write diagnostic')
  row=parsed(pattern,line);owner=row['pid'],row['tid']
  if (not all(0<v<=0xffffffff for v in owner) or not 0<row['request']<=row['wait']<=0xffffffffffffffff or
      not low<=row['input']<high or not 0<row['bytes']<=4097 or row['bytes']>high-row['input'] or not 0<=row['fd']<=0x7fffffff):raise ValueError('invalid copied scalar write identity/input/count')
  if pending is not None and pattern is not SIGNAL:raise ValueError('scalar write interrupted retirement lacks signal')
  if pattern in (WAIT,COMPLETE):
   if not 0<=row['description']<0xffff or not 0<=row['pipe']<0xffff:raise ValueError('invalid scalar write object or description')
   identity=tuple(row[k] for k in identity_fields)
   if pattern is WAIT:
    if row['wait']<=waits.get(owner,0):raise ValueError('scalar write reused a stale exact ticket')
    if row['stage']=='arm':
     if owner in active or row['wait']!=row['request']:raise ValueError('duplicate or invalid scalar write arm')
     active[owner]=dict(identity=identity,wait=row['wait'],origin=None,arm=row)
    else:
     if owner not in active or active[owner]['identity']!=identity:raise ValueError('scalar write rearm changed retained copied request')
     active[owner]['wait']=row['wait']
    waits[owner]=row['wait']
   else:
    state=active.get(owner)
    if state is None or state['identity']!=identity or state['wait']!=row['wait'] or row['pinned']:raise ValueError('scalar write terminal lost ownership or description pin')
    value,outcome=row['result'],row['outcome']
    if (not -(1<<63)<=value<(1<<63) or
        outcome=='ready' and not 0<value<=min(4096,row['bytes']) or
        outcome=='ready' and row['bytes']<=4096 and value!=row['bytes'] or
        outcome=='efault' and value!=-14 or outcome=='cancelled' and value!=-125 or
        outcome=='error' and (value>=0 or value in (-14,-125,-4)) or
        outcome=='interrupted' and value not in (-4,0)):raise ValueError('scalar write result differs from terminal cause/atomicity')
    row['origin_record']=state['origin'];row['arm']=state['arm'];del active[owner]
    if outcome=='interrupted':
     if state['origin'] is None:raise ValueError('scalar write interruption has no bound origin')
     pending=row
   if row['live']!=len(active):raise ValueError('scalar write live count differs from owned ledger')
  elif pattern is ORIGIN:
   state=active.get(owner);arm=parsed(WAIT,previous) if WAIT.fullmatch(previous) else None
   if (state is None or state['origin'] is not None or arm is None or arm['stage']!='arm' or
       any(row[k]!=arm[k] for k in ('pid','tid','request','wait','fd','input','bytes')) or
       row['request']!=row['wait'] or not origins.get(owner,0)<row['origin']<=0xffffffffffffffff or
       row['syscall']!=WRITE[arch] or not low<=row['pc']<high or not instruction(arch,row['pc'])):raise ValueError('scalar write origin does not bind preceding fresh arm')
   state['origin']=row;origins[owner]=row['origin']
  else:
   if not allow_signal or pending is None or previous!=pending['line']:raise ValueError('scalar write signal has no exact interrupted predecessor')
   origin=pending['origin_record'];numbers=(16,17) if arch.startswith('mips') else (10,12)
   if (any(row[k]!=pending[k] for k in ('pid','tid','request','wait','fd','input','bytes','pinned','live')) or
       any(row[k]!=origin[k] for k in ('origin','syscall')) or row['signal'] not in numbers or
       not low<=row['pc']<high or not instruction(arch,row['pc']) or
       pending['result']!=(-4 if row['outcome']=='eintr' else 0)):raise ValueError('scalar write signal changed retired request or origin')
   widths=(2,) if arch in ('x86_64','i386') else (2,4) if arch=='arm32' else (4,)
   if row['outcome']=='eintr' and row['pc']!=origin['pc'] or row['outcome']=='restart' and origin['pc']-row['pc'] not in widths:raise ValueError('scalar write signal has wrong saved instruction continuation')
   row['terminal']=pending;row['origin_record']=origin;pending=None
  events.append(row);previous=line
 if active or pending is not None:raise ValueError('scalar write objects or signal publication escaped command boundary')
 return events
