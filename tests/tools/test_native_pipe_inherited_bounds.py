"""Coherent full-wrapper descriptor mutations, including operations without waits."""
from pathlib import Path
import re,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/tools')]
import test_native_pipe_write as scalar
import test_native_pipe_vector as vector
from native_pipe_vector_events import ARCHES


def change_role(raw,prefix,case,field,value,direction=None):
 lines=raw.splitlines(keepends=True)
 first=next(i for i,line in enumerate(lines) if line.startswith(prefix+b'CASE_BEGIN ') and f' case={case} '.encode() in line and (direction is None or f' direction={direction} '.encode() in line))
 last=next(i for i in range(first,len(lines)) if lines[i].startswith(prefix+b'PARENT_PASS '))
 begin=dict(token.split(b'=',1) for token in lines[first].split()[1:]);old=int(begin[field.encode()]);assert old>=3 and old!=value
 names=rb'(fd|readfd|writefd|replacement|replacementread|nestedfd|nestedread)'
 for i in range(first,last+1):
  line=lines[i]
  if i==first:line=re.sub(rb'\b'+names+rb'='+str(old).encode()+rb'(?=\s|$)',lambda m:m[1]+b'='+str(value).encode(),line)
  else:
   line=re.sub(rb'\b(fd|a0|orig_r3)='+str(old).encode()+rb'(?=\s|$)',lambda m:m[1]+b'='+str(value).encode(),line)
   if any(line.startswith(prefix+tag+b' ') for tag in (b'EMPTY',b'CLOSE_READER',b'CLOSE_PEER',b'REPLACE_FD',b'NEST_ATTEMPT',b'NEST_RETRY')):
    line=re.sub(rb'\bvalue='+str(old).encode()+rb'(?=\s|$)',b'value='+str(value).encode(),line)
  lines[i]=line
 changed=b''.join(lines);assert changed!=raw;return changed


class InheritedDescriptorBoundsTests(unittest.TestCase):
 def check_role(self,kind,arch,case,field,direction=None):
  module=scalar if kind=='write' else vector;make=module.fixture if kind=='write' else module.transcript;prefix=b'PIPE_WRITE_' if kind=='write' else b'PIPE_VECTOR_'
  for value in (31,32,2147483647):
   parts=make(arch);parts[2]=change_role(parts[2],prefix,case,field,value,direction)
   with self.subTest(kind=kind,arch=arch,case=case,field=field,direction=direction,value=value):
    if value==31:self.assertEqual(module.validate(parts,arch)['runs'],2)
    else:
     with self.assertRaises(ValueError):module.validate(parts,arch)
 def test_scalar_immediate_fd(self):
  for arch in ARCHES:
   for case in (9,10,11,13):self.check_role('write',arch,case,'fd')
 def test_scalar_reader_replacement_nested_roles(self):
  for arch in ARCHES:
   for case,field in ((9,'readfd'),(10,'readfd'),(13,'readfd'),(5,'replacement'),(5,'replacementread'),(17,'nestedfd'),(17,'nestedread')):self.check_role('write',arch,case,field)
 def test_vector_immediate_fd(self):
  for arch in ARCHES:
   for direction in (0,1):
    for case in (9,10,11,13,25,26,27,28,29,30,31):self.check_role('vector',arch,case,'fd',direction)
 def test_vector_reader_writer_replacement_nested_roles(self):
  for arch in ARCHES:
   for direction in (0,1):
    for case,field in ((13,'readfd'),(13,'writefd'),(5,'replacement'),(5,'replacementread'),(17,'nestedfd'),(17,'nestedread')):self.check_role('vector',arch,case,field,direction)

if __name__=='__main__':unittest.main()
