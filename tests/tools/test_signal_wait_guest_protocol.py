"""Actual-reference and synthetic actor controls, not kernel execution."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/tools')]
from signal_wait_fixtures import ARCHES,linux_fixture,events,decode,encode
import signal_wait_guest_protocol as evidence

def change(raw,tag,family,case,**fields):
 lines=raw.splitlines()
 for i,line in enumerate(lines):
  t,r=decode(line)
  if t==tag and r.get('family')==family and r.get('case')==case and r.get('api')==0 and r.get('form')==0 and r.get('restart')==0:
   r.update(fields);lines[i]=encode(t,r);return b'\n'.join(lines)+b'\n'
 raise AssertionError((tag,family,case))
class SignalWaitGuestProtocol(unittest.TestCase):
 def test_actual_static_musl_linux_reference(self):
  r=evidence.validate_cases(linux_fixture(),'x86_64',linux=True)
  self.assertEqual((r['cases'],r['excluded'],r['handlers'],r['sends'],r['exec_images']),(176,8,60,254,12))
 def test_all_ten_exact_matrices(self):
  for arch in ARCHES:
   with self.subTest(arch=arch):
    r=evidence.validate_cases(events(arch),arch)
    self.assertEqual(r['cases'],410 if arch in ('arm32','ppc') else 248 if arch in ('i386','mips') else 184)
    self.assertEqual((r['excluded'],r['semantic_cases']),(0,49))
 def test_reject_reference_exclusions_in_native_mode(self):
  with self.assertRaises(ValueError):evidence.validate_cases(linux_fixture(),'x86_64')
 def test_exact_architecture_and_time_abi(self):
  for arch in ARCHES:
   for fields in (dict(syscall=137 if arch=='rv32' else 0),dict(size=7),dict(word1=1),dict(word0=1),dict(info=1)):
    with self.subTest(arch=arch,fields=fields),self.assertRaises(ValueError):evidence.validate_cases(change(events(arch),'BEGIN',0,4,**fields),arch)
 def test_all_semantic_cases_have_parent_assertions(self):
  for family,count in ((0,32),(1,17)):
   for case in range(count):
    with self.subTest(family=family,case=case),self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),'PARENT_PASS',family,case,child=0),'x86_64')
 def test_full_siginfo_fields_and_bytes(self):
  for case in (4,5,6,7,8,10,14,15,16,19,21,22,23,24,25,26,27,30,31):
   for fields in (dict(checksum=1),dict(bytes=127),dict(sender=99999),dict(uid=99999)):
    with self.subTest(case=case,fields=fields),self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),'INFO',0,case,**fields),'x86_64')
 def test_handler_masks_pc_result_and_sender(self):
  for tag,family,case,fields in [('RETURN',0,17,dict(mask=31)),('RETURN',0,13,dict(errno=4)),('HANDLE',0,17,dict(saved=31)),('HANDLE',1,5,dict(live=31)),('HANDLE',1,5,dict(saved=24)),('HANDLE',1,5,dict(pc=1)),('HANDLE',1,5,dict(result=0)),('HANDLE',1,5,dict(sender=0)),('SEND',0,25,dict(target=0)),('SEND',0,26,dict(process=0))]:
   with self.subTest(tag=tag,case=case,fields=fields),self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),tag,family,case,**fields),'x86_64')
 def test_pending_and_ignored_dispositions(self):
  for family,case in ((0,7),(0,8),(0,18),(0,22),(0,23),(0,24),(0,25),(0,26),(0,27),(1,4),(1,7),(1,8),(1,9),(1,10)):
   with self.subTest(family=family,case=case),self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),'PENDING',family,case,bits=31),'x86_64')
 def test_exec_state_and_fatal_status(self):
  for family,case in ((0,28),(1,13),(1,14)):
   for fields in (dict(mask=0),dict(tls=0),dict(caught_reset=0),dict(pid=0),dict(pending=1)):
    with self.subTest(family=family,case=case,fields=fields),self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),'REPLACED',family,case,**fields),'x86_64')
  for family,case in ((0,29),(1,15)):
   with self.assertRaises(ValueError):evidence.validate_cases(change(events('x86_64'),'PARENT_PASS',family,case,signal=0),'x86_64')
 def test_missing_duplicate_unknown_every_record_kind(self):
  raw=events('x86_64');unique={line.split()[0]:line for line in raw.splitlines(keepends=True)}
  for prefix,line in unique.items():
   for replacement in (b'',line+line,line.replace(prefix,b'SIGNAL_WAIT_UNKNOWN',1)):
    with self.subTest(prefix=prefix,duplicate=bool(replacement)),self.assertRaises(ValueError):evidence.validate_cases(raw.replace(line,replacement,1),'x86_64')
 def test_crlf_reference_and_synthetic(self):
  for raw,linux in ((linux_fixture(),True),(events('x86_64'),False)):
   self.assertEqual(evidence.validate_cases(raw,'x86_64',linux),evidence.validate_cases(raw.replace(b'\n',b'\r\n'),'x86_64',linux))
if __name__=='__main__':unittest.main()
