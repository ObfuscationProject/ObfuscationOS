"""Child owner and incidental diagnostic controls for inherited signal collectors."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_native_signal_delivery_x86_64 as frame
import test_native_directed_signals as directed
from test_native_child_events import wait
from test_native_child_exit_events import completion
ARCHES=('x86_64','i386','aarch64','arm32','rv64','rv32','loongarch64','mips','mips64','ppc')
def fixture(kind,arch):
 parts=frame.fixture('pthread',arch=arch) if kind=='frame' else directed.fixture(arch)
 parts=[part.replace(b'user=40 objects=0',b'user=39 objects=1') for part in parts]
 parts[0]=parts[0].removesuffix(b'oksh> ')+wait()+b'oksh> '
 for i in range(1,5):
  command,body=parts[i].split(b'\n',1)
  parts[i]=(command+b'\n'+wait(pid=2,tid=2,request=10+i,selector=8,live=2)+body.removesuffix(b'oksh> ')+completion(child=8,parent=2,parent_tid=0,parent_epoch=0,uid=0,status=0,wait_status=0,published=0,notify=0,queued=0)+b'\n'+wait(pid=2,tid=2,request=10+i,selector=8,outcome='complete',result=8,live=1)+b'oksh> ')
 return parts
def validate(kind,parts,arch):
 return frame.validate(parts,'pthread',arch) if kind=='frame' else directed.validate(parts,arch)
class ChildRecords(unittest.TestCase):
 def test_all_profiles_exact_owned_waits(self):
  for kind in ('frame','directed'):
   for arch in ARCHES:
    for crlf in (False,True):
     parts=fixture(kind,arch)
     if crlf:parts=[p.replace(b'\n',b'\r\n') for p in parts]
     with self.subTest(kind=kind,arch=arch,crlf=crlf):
      r=validate(kind,parts,arch);self.assertEqual(r['runs'],2);self.assertEqual(r['final']['objects'],1)
 def test_owned_pair_cannot_be_deleted_duplicated_or_changed(self):
  for kind in ('frame','directed'):
   for arch in ARCHES:
    parts=fixture(kind,arch)
    for index in range(1,5):
     arm=wait(pid=2,tid=2,request=10+index,selector=8,live=2)
     complete=wait(pid=2,tid=2,request=10+index,selector=8,outcome='complete',result=8,live=1)
     mutations=[(arm,b''),(complete,b''),(arm,arm*2),(complete,complete*2),
                (arm,b'prefix '+arm),(arm,arm.replace(b'live=2',b'live=1')),
                (arm,arm.replace(b'selector=8',b'selector=9')),
                (complete,complete.replace(b'result=8',b'result=9')),
                (complete,complete.replace(b'tid=2',b'tid=3')),
                (complete,complete.replace(b'wait='+str(10+index).encode(),b'wait=99'))]
     for old,new in mutations:
      changed=parts.copy();changed[index]=changed[index].replace(old,new,1)
      with self.subTest(kind=kind,arch=arch,index=index,old=old,new=new),self.assertRaises(ValueError):validate(kind,changed,arch)
 def test_inherited_owner_cannot_retire_and_reappear_across_image(self):
  for kind in ('frame','directed'):
   for arch in ARCHES:
    for index in (2,3):
     parts=fixture(kind,arch)
     arm=wait(pid=2,tid=2,request=10+index,selector=8,live=2)
     lines=parts[index].replace(arm,b'',1).splitlines(keepends=True)
     first=next(i for i,line in enumerate(lines) if line.startswith(b'OK_NATIVE_IMAGE '))
     lines.insert(first,wait(outcome='complete',result=2,live=0))
     lines.insert(first+2,wait()+arm)
     parts[index]=b''.join(lines)
     with self.subTest(kind=kind,arch=arch,index=index),self.assertRaises(ValueError):validate(kind,parts,arch)
 def test_retained_init_owner_and_object_page_are_required_together(self):
  for kind in ('frame','directed'):
   parts=fixture(kind,'x86_64')
   for changed in ([parts[0].replace(wait(),b'')]+parts[1:],parts[:1]+[p.replace(b'objects=1',b'objects=0') for p in parts[1:]]):
    with self.subTest(kind=kind),self.assertRaises(ValueError):validate(kind,changed,'x86_64')
 def test_diagnostics_require_grammar_and_matching_retirement(self):
  for kind in ('frame','directed'):
   parts=fixture(kind,'x86_64')
   for index in range(1,5):
    for line in (b'OK_NATIVE_CHILD_WAIT invalid\n',b'OK_NATIVE_PIPE_READ_WAIT invalid\n',b'OK_NATIVE_FUTEX_WAIT invalid\n',b'OK_NATIVE_POLL_WAIT invalid\n'):
     changed=parts.copy();changed[index]=changed[index].replace(b'oksh> ',line+b'oksh> ')
     with self.subTest(kind=kind,index=index,line=line),self.assertRaises(ValueError):validate(kind,changed,'x86_64')
 def test_only_exact_banner_join_is_normalized(self):
  for kind in ('frame','directed'):
   parts=fixture(kind,'x86_64');arm=wait(pid=2,tid=2,request=11,selector=8,live=2)
   changed=parts.copy();changed[1]=changed[1].replace(arm,b'').replace(b'hello from ObfuscationOS userland\n',b'hello from ObfuscationOS userland'+arm)
   self.assertEqual(validate(kind,changed,'x86_64')['runs'],2)
   changed[1]=changed[1].replace(b'userlandOK_NATIVE_CHILD_WAIT',b'userlandOK_NATIVE_CHILD_WAIT invalid')
   with self.assertRaises(ValueError):validate(kind,changed,'x86_64')
if __name__=='__main__':unittest.main()
