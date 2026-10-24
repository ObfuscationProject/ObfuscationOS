"""Generic scalar write ledger ownership fixtures, separate from target execution."""
from pathlib import Path
import re,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import native_pipe_write_events as e

def trace(arch,signal=False,restart=False,rearm=False,large=False):
 base=0x10000000 if arch in ('arm32','aarch64') else 0x40000000;pc=base+0x2001 if arch in ('i386','x86_64') else base+0x2000;width=2 if arch in ('i386','x86_64') else 4;count=4097 if large else 4096
 identity=f'pid=2 tid=3 wait=7 request=7 input={base+0x100040} fd=4 description=5 pipe=1 bytes={count}'
 lines=[f'OK_NATIVE_PIPE_WRITE_WAIT {identity} stage=arm live=1',f'OK_NATIVE_PIPE_WRITE_ORIGIN pid=2 tid=3 request=7 wait=7 origin=9 pc={pc+width} syscall={e.WRITE[arch]} fd=4 input={base+0x100040} bytes={count}']
 if rearm:identity=identity.replace('wait=7','wait=8');lines.append(f'OK_NATIVE_PIPE_WRITE_WAIT {identity} stage=rearm live=1')
 lines.append(f'OK_NATIVE_PIPE_WRITE_COMPLETE {identity} result={0 if restart else -4 if signal else 4096} outcome={"interrupted" if signal else "ready"} pinned=0 live=0')
 if signal:lines.append(f'OK_NATIVE_PIPE_WRITE_SIGNAL pid=2 tid=3 request=7 wait={8 if rearm else 7} origin=9 signal={17 if arch.startswith("mips") else 12} outcome={"restart" if restart else "eintr"} pc={pc if restart else pc+width} syscall={e.WRITE[arch]} fd=4 input={base+0x100040} bytes={count} pinned=0 live=0')
 return ('\n'.join(lines)+'\n').encode()

class ScalarWriteLedger(unittest.TestCase):
 def test_complete_interrupted_restart_rearm_all_profiles(self):
  for arch in e.WRITE:
   for signal,restart in ((False,False),(True,False),(True,True)):
    for rearm in (False,True):
     for large in (False,True):
      with self.subTest(arch=arch,signal=signal,restart=restart,rearm=rearm,large=large):
       rows=e.native_events(trace(arch,signal,restart,rearm,large),arch,allow_signal=signal);self.assertEqual(rows[-1]['live'],0)
 def test_caught_publication_requires_explicit_authority(self):
  for arch in e.WRITE:
   with self.assertRaises(ValueError):e.native_events(trace(arch,True),arch)
 def test_identity_and_lifetime_corruption(self):
  for arch in e.WRITE:
   original=trace(arch,True,True,True);lines=original.splitlines(keepends=True)
   for i,line in enumerate(lines):
    for field in (b'pid',b'tid',b'wait',b'request',b'input',b'fd',b'bytes',b'live'):
     if field+b'=' not in line:continue
     pattern=rb'(?<![a-z_])'+field+rb'=[0-9]+';value=b'999' if re.search(pattern,line)[0].endswith(b'=0') else b'0';changed=re.sub(pattern,field+b'='+value,line);bad=lines.copy();bad[i]=changed
     with self.subTest(arch=arch,index=i,field=field),self.assertRaises(ValueError):e.native_events(b''.join(bad),arch,allow_signal=True)
    for replacement in (b'',line+line,b'garbage '+line):
     bad=lines.copy();bad[i]=replacement
     with self.subTest(arch=arch,index=i),self.assertRaises(ValueError):e.native_events(b''.join(bad),arch,allow_signal=True)
 def test_atomicity_pin_and_pc_regions(self):
  for arch in e.WRITE:
   original=trace(arch)
   for before,after in ((b'result=4096',b'result=1'),(b'pinned=0',b'pinned=1'),(b'bytes=4096',b'bytes=4098'),(b'stage=arm',b'stage=rearm')):
    with self.subTest(arch=arch,before=before),self.assertRaises(ValueError):e.native_events(original.replace(before,after),arch)
   original=trace(arch,True,True)
   for pc in (0,0x10000000 if arch not in ('arm32','aarch64') else 0x40000000,0x80000000,2**64):
    bad=re.sub(rb'pc=[0-9]+',f'pc={pc}'.encode(),original)
    with self.subTest(arch=arch,pc=pc),self.assertRaises(ValueError):e.native_events(bad,arch,allow_signal=True)
 def test_image_reset_and_pending_publication(self):
  image=b'OK_NATIVE_IMAGE personality=linux source=firmware pages=1 physical_first=0x0000000000000001 physical_last=0x0000000000000001 owner=retained\n'
  original=trace('x86_64')
  self.assertEqual(len(e.native_events(original+image+original,'x86_64')),6)
  with self.assertRaises(ValueError):e.native_events(original+original,'x86_64')
  interrupted=trace('x86_64',True).splitlines(keepends=True)
  with self.assertRaises(ValueError):e.native_events(b''.join(interrupted[:-1])+b'PIPE_WRITE_HANDLE arbitrary\n'+interrupted[-1],'x86_64',allow_signal=True)
  with self.assertRaises(ValueError):e.native_events(interrupted[0]+image+b''.join(interrupted[1:]),'x86_64',allow_signal=True)

if __name__=='__main__':unittest.main()
