"""Independent combined scalar/vector ledger controls; synthetic records only."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/tools'))
import native_pipe_vector_events as e
from test_native_pipe_vector import events,ARCHES,transcript,validate
from test_native_pipe_write import events as scalar_write
from test_native_pipe_signal import events as scalar_read
from test_native_signal_delivery_x86_64 import IMAGE

def records(arch,direction=0):
 key=f'direction={direction} variant=0 form=0 restart=0 case=0 '.encode();lines=events(arch).splitlines();start=next(i for i,l in enumerate(lines) if l.startswith(b'PIPE_VECTOR_CASE_BEGIN ') and key in l);end=next(i for i in range(start,len(lines)) if lines[i].startswith(b'PIPE_VECTOR_PARENT_PASS ') and key in lines[i]);return [l for l in lines[start:end] if l.startswith(b'OK_NATIVE_PIPE_')]
def stream(rows):return b'\n'.join(rows)+b'\n'

class VectorLedgerTests(unittest.TestCase):
 def test_vector_positive_allten(self):
  for arch in ARCHES:
   for direction in (0,1):
    with self.subTest(arch=arch,direction=direction):
     rows=records(arch,direction);parsed=e.native_events(stream(rows),arch,allow_signal=True);self.assertEqual(len(parsed),7)
     with self.assertRaises(ValueError):e.native_events(stream(rows),arch)
 def test_each_bound_vector_field(self):
  for arch in ARCHES:
   for direction in (0,1):
    rows=records(arch,direction)
    for index,row in enumerate(rows):
     for field in re.finditer(rb'(?<![a-z_])([a-z][a-z0-9_]*)=(-?[0-9]+)',row):
      key=field[1]
      # A globally valid descriptor slot or ticket requires consistency across records;
      # mutate one occurrence only so ownership checks must reject it.
      old=int(field[2]);value=old+1 if key not in (b'result',b'live',b'pinned') else old+2
      if key==b'origin':value=0
      if key==b'signal':value=99
      if key==b'syscall':value=9999
      if key==b'pc':value=1
      changed=rows.copy();changed[index]=row[:field.start(2)]+str(value).encode()+row[field.end(2):]
      with self.subTest(arch=arch,direction=direction,index=index,key=key),self.assertRaises(ValueError):e.native_events(stream(changed),arch,allow_signal=True)
    for index,row in enumerate(rows):
     changed=rows.copy();changed[index]=row.replace(b'vectors=1:0,',b'vectors=2:0,',1)
     with self.subTest(arch=arch,direction=direction,index=index,field='zero-span-base'),self.assertRaises(ValueError):e.native_events(stream(changed),arch,allow_signal=True)
 def test_scalar_and_vector_share_live_count(self):
  for arch in ARCHES:
   for direction in (0,1):
    vector=records(arch,direction);initial=vector[0];base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000;ptr=base+0x9000;number=(e.WRITE if direction else e.READ)[arch];field='input' if direction else 'output';prefix=b'OK_NATIVE_PIPE_WRITE_' if direction else b'OK_NATIVE_PIPE_READ_';origin=b'OK_NATIVE_PIPE_WRITE_ORIGIN' if direction else b'OK_NATIVE_PIPE_ORIGIN';identity=f'pid=51 tid=52 wait=1 request=1 {field}={ptr} fd=8 description=9 pipe=2 bytes=1'.encode()
    scalar=[prefix+b'WAIT '+identity+b' stage=arm live=1',origin+f' pid=51 tid=52 request=1 wait=1 origin=1 pc={base+0x6000} syscall={number} fd=8 {field}={ptr} bytes=1'.encode()]
    vector=[r.replace(b' live=1',b' live=2').replace(b' live=0',b' live=1') for r in vector]
    combined=scalar+vector+[prefix+b'COMPLETE '+identity+b' result=1 outcome=ready pinned=0 live=0']
    with self.subTest(arch=arch,direction=direction):self.assertEqual(len(e.native_events(stream(combined),arch,allow_signal=True)),10)
    wrong=combined.copy();wrong[2]=initial
    with self.assertRaises(ValueError):e.native_events(stream(wrong),arch,allow_signal=True)
 def test_publication_adjacency_cannot_be_hidden(self):
  for arch in ARCHES:
   read=records(arch,0);write=records(arch,1)
   for index in (1,3):
    corrupt=read[:index]+write+read[index:]
    with self.subTest(arch=arch,index=index),self.assertRaises(ValueError):e.native_events(stream(corrupt),arch,allow_signal=True)
   for index in (1,3):
    corrupt=read[:index]+[b'innocent guest text']+read[index:]
    with self.assertRaises(ValueError):e.native_events(stream(corrupt),arch,allow_signal=True)
 def test_unrelated_image_preserves_live_owner(self):
  for arch in ARCHES:
   for direction in (0,1):
    rows=records(arch,direction)
    # An unattributed IMAGE may belong to another process. Keep the exact active
    # owner, retained vectors and captured origin through this publication.
    changed=rows[:2]+[IMAGE.strip()]+rows[2:]
    with self.subTest(arch=arch,direction=direction):self.assertEqual(len(e.native_events(stream(changed),arch,allow_signal=True)),7)
    malformed=rows[:2]+[b'OK_NATIVE_IMAGE malformed=1']+rows[2:]
    with self.assertRaises(ValueError):e.native_events(stream(malformed),arch,allow_signal=True)
    lost_origin=rows[:1]+[IMAGE.strip()]+rows[1:]
    with self.assertRaises(ValueError):e.native_events(stream(lost_origin),arch,allow_signal=True)
 def test_owner_tickets_and_origins_span_directions(self):
  for arch in ARCHES:
   reads=records(arch,0);writes=records(arch,1)
   owner={k:int(v) for k,v in re.findall(rb'(pid|tid)=([0-9]+)',reads[0])}
   def rewrite(rows,tickets,origins):
    changed=[]
    for row in rows:
     for key,value in owner.items():row=re.sub(rb'(?<![a-z_])'+key+rb'=[0-9]+',key+b'='+str(value).encode(),row)
     for key,increment in ((b'wait',tickets),(b'request',tickets),(b'origin',origins)):
      row=re.sub(rb'(?<![a-z_])'+key+rb'=([0-9]+)',lambda m:key+b'='+str(int(m[1])+increment).encode(),row)
     changed.append(row)
    return changed
   good=rewrite(writes,2,2)
   with self.subTest(arch=arch):self.assertEqual(len(e.native_events(stream(reads+good),arch,allow_signal=True)),14)
   for corrupt in (reads+rewrite(writes,0,2),reads+rewrite(writes,2,0),reads[:2]+good+reads[2:]):
    with self.assertRaises(ValueError):e.native_events(stream(corrupt),arch,allow_signal=True)
 def test_dedicated_scope_and_resources(self):
  for arch in ARCHES:
   original=transcript(arch)
   for target in (0,1,4):
    changed=original.copy();changed[target]=changed[target][:-len(b'oksh> ')]+stream(records(arch))+b'oksh> '
    with self.subTest(arch=arch,target=target),self.assertRaises(ValueError):validate(changed,arch)
   for old,new in ((b'objects=1',b'objects=2'),(b'PIPE_VECTOR_PASS',b'PIPE_VECTOR_PASX')):
    changed=original.copy();changed[2]=changed[2].replace(old,new)
    with self.assertRaises(ValueError):validate(changed,arch)
   changed=original.copy();changed[2]=changed[2].replace(b'OK_NATIVE_IMAGE',b'BAD_NATIVE_IMAGE',1)
   with self.assertRaises(ValueError):validate(changed,arch)

if __name__=='__main__':unittest.main()
