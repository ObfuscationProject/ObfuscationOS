"""Synthetic all-ten complete command controls; no emulator is invoked."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/tools')]
from signal_wait_fixtures import ARCHES,native_fixture
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
from test_native_pipe_vector import INIT
import native_signal_wait_evidence as evidence

def transcript(arch):
 _,_,command,leases=evidence.probe_spec(arch,'signal-waits');body=command+b'\n'+IMAGE+native_fixture(arch)
 def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
 parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',
  b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
 if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
 return parts

def validate(parts,arch):
 bounds=[sum(map(len,parts[:i])) for i in range(1,5)];return evidence.validate_execution(b''.join(parts),*bounds,bounds[-1],arch)
class NativeSignalWait(unittest.TestCase):
 def test_all_ten_complete_command_wrappers(self):
  for arch in ARCHES:
   with self.subTest(arch=arch):
    r=validate(transcript(arch),arch);self.assertEqual(r['runs'],2)
    self.assertEqual(r['image_publications_per_run'],23 if arch in ('arm32','ppc') else 15 if arch in ('i386','mips') else 13)
    self.assertEqual(r['observations'][0]['native_waits']['libc_retries'],6)
 def test_all_ten_native_contract_mutations(self):
  for arch in ARCHES:
   raw=native_fixture(arch)
   for before,after in ((b'original1=0',b'original1=1'),(b'published=1 staged=0 consumed=1',b'published=0 staged=0 consumed=1'),(b'cause=exec',b'cause=thread'),(b'kind=suspend syscall=',b'kind=timed syscall='),(b'result=-4 published=0 staged=1',b'result=0 published=0 staged=1')):
    self.assertIn(before,raw)
    with self.subTest(arch=arch,before=before),self.assertRaises(ValueError):evidence.validate_cases(raw.replace(before,after,1),arch)
 def test_full_wrapper_missing_duplicate_records(self):
  for arch in ('x86_64','rv32','mips','ppc'):
   parts=transcript(arch)
   for prefix in (b'OK_NATIVE_SIGNAL_WAIT_ARM ',b'OK_NATIVE_SIGNAL_WAIT_COMPLETE ',b'OK_NATIVE_SIGNAL_WAIT_COMMIT ',b'OK_NATIVE_SIGNAL_WAIT_RETIRE ',b'OK_NATIVE_IMAGE ',b'SIGNAL_WAIT_CASE_BEGIN ',b'SIGNAL_WAIT_PASS ',b'OK_NATIVE_FRAMES ',b'OK_ENTRY_STACKS '):
    line=next(x for x in parts[2].splitlines(keepends=True) if x.startswith(prefix))
    for replacement in (b'',line+line):
     changed=parts.copy();changed[2]=changed[2].replace(line,replacement,1)
     with self.subTest(arch=arch,prefix=prefix,duplicate=bool(replacement)),self.assertRaises(ValueError):validate(changed,arch)
 def test_admission_and_commit_cannot_follow_observer(self):
  lines=native_fixture('x86_64').splitlines()
  for prefix,before in ((b'OK_NATIVE_SIGNAL_WAIT_ARM ',b'SIGNAL_WAIT_AWAIT '),(b'OK_NATIVE_SIGNAL_WAIT_COMMIT ',b'SIGNAL_WAIT_HANDLE ')):
   changed=lines.copy();i=next(i for i,l in enumerate(changed) if l.startswith(prefix));line=changed.pop(i);j=next(j for j,l in enumerate(changed[i:],i) if l.startswith(before));changed.insert(j+1,line)
   with self.assertRaises(ValueError):evidence.validate_cases(b'\n'.join(changed)+b'\n','x86_64')
 def test_outside_command_and_wrong_image_domains(self):
  parts=transcript('x86_64');line=next(x for x in parts[2].splitlines(keepends=True) if x.startswith(b'OK_NATIVE_SIGNAL_WAIT_ARM '))
  for i in (0,1,4):
   changed=parts.copy();changed[i]=line+changed[i]
   with self.assertRaises(ValueError):validate(changed,'x86_64')
  changed=parts.copy();changed[2]=changed[2].replace(b'source=firmware',b'source=linker',1)
  with self.assertRaises(ValueError):validate(changed,'x86_64')
 def test_qualifier_all_ten_layout(self):
  import qualify_native_signal_wait as q
  for arch in ARCHES:
   source,name,command=q.probe_layout(arch,'signal-waits');self.assertEqual(source,'native_signal_wait');self.assertEqual(command,'/bin/'+name);self.assertLessEqual(len(name),31)
 def test_unknown_and_malformed_native_record(self):
  raw=native_fixture('x86_64')
  for after in (b'OK_NATIVE_SIGNAL_WAIT_UNKNOWN ',b'OK_NATIVE_SIGNAL_WAIT_ARM garbage '):
   with self.assertRaises(ValueError):evidence.validate_cases(raw.replace(b'OK_NATIVE_SIGNAL_WAIT_ARM ',after,1),'x86_64')
if __name__=='__main__':unittest.main()
