"""Actual Linux transcript controls and synthetic profile parser regressions.

These tests establish collector strictness, not native execution or isolation.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/tools')]
import process_signal_guest_protocol as evidence
from process_signal_fixtures import ARCHES, decode, encode, events, linux_fixture


def change(raw, tag, case, **fields):
 """Mutate exactly the first matching record in the first raw/no-restart group."""
 lines = raw.splitlines()
 for index, line in enumerate(lines):
  kind, row = decode(line)
  if kind == tag and row.get('case') == case and row.get('variant') == 0 and row.get('form') == 0 and row.get('restart') == 0:
   row.update(fields); lines[index] = encode(kind, row)
   return b'\n'.join(lines)+b'\n'
 raise AssertionError((tag, case))


def locate(lines, wanted, case, **fields):
 for index, line in enumerate(lines):
  kind, row = decode(line)
  if (kind == wanted and row.get('case') == case and row.get('variant') == 0 and
      row.get('form') == 0 and row.get('restart') == 0 and
      all(row.get(name) == value for name, value in fields.items())):
   return index
 raise AssertionError((wanted, case, fields))


def move(raw, tag, case, before, selection=None, destination=None):
 lines = raw.splitlines()
 index = locate(lines, tag, case, **(selection or {}))
 line = lines.pop(index)
 target = locate(lines, before, case, **(destination or {}))
 lines.insert(target, line)
 return b'\n'.join(lines)+b'\n'


class ProcessSignalGuestProtocolTests(unittest.TestCase):
 def reject(self, raw, arch='x86_64', linux=False):
  with self.assertRaises(ValueError):
   evidence.validate_cases(raw, arch, linux=linux)

 def test_actual_host_reference(self):
  result = evidence.validate_cases(linux_fixture(), 'x86_64', linux=True)
  self.assertEqual((result['cases'], result['groups'], result['handlers'], result['skipped']), (108, 4, 128, 24))
  self.assertEqual(result['exec_replacements'], 8)
  self.assertEqual(result['signal_terminations'], 8)
  self.assertFalse(result['native_OS_execution'])

 def test_all_ten_complete_synthetic_guest_profiles(self):
  for arch in ARCHES:
   with self.subTest(arch=arch):
    result = evidence.validate_cases(events(arch), arch)
    groups = 6 if arch in ('arm32', 'ppc') else 4
    self.assertEqual((result['cases'], result['handlers']), (33*groups, 131*groups))
    self.assertEqual((result['exec_replacements'], result['signal_terminations']), (2*groups, 3*groups))
    self.assertEqual(result['skipped'], 0)
    self.assertFalse(result['native_OS_execution'])

 def test_either_eligible_sibling_and_cross_thread_interleavings(self):
  for raw, linux in ((events('x86_64'), False), (linux_fixture(), True)):
   lines = raw.splitlines()
   index = locate(lines, 'HANDLE', 7)
   _, handle = decode(lines[index]); previous = handle['actor']; alternate = 1-previous
   tids = {row['actor']: row['tid'] for tag, row in map(decode, lines)
           if tag == 'THREAD' and row.get('case') == 7 and row.get('variant') == 0 and row.get('restart') == 0}
   handle.update(actor=alternate, tid=tids[alternate]); lines[index] = encode('HANDLE', handle)
   for index, line in enumerate(lines):
    tag, row = decode(line)
    if tag == 'TOTAL' and row['case'] == 7 and row['variant'] == 0 and row['restart'] == 0 and row['actor'] in (0, 1):
     row['handlers'] = int(row['actor'] == alternate); lines[index] = encode(tag, row)
   changed = b'\n'.join(lines)+b'\n'
   evidence.validate_cases(changed, 'x86_64', linux=linux)
   # A recipient can run its handler before the sender prints KILL_END.
   changed = move(changed, 'HANDLE', 7, 'KILL_END')
   evidence.validate_cases(changed, 'x86_64', linux=linux)

 def test_actual_host_transcript_semantic_mutations(self):
  raw = linux_fixture()
  mutations = [
   ('KILL_BEGIN', 0, dict(signal=1)), ('KILL_END', 0, dict(value=-3)),
   ('THREAD', 1, dict(tid=0)), ('THREAD', 1, dict(mask=30)),
   ('DIRECT', 1, dict(signal=12)), ('HANDLE', 1, dict(code=0)),
   ('HANDLE', 2, dict(signal=10)), ('HANDLE', 3, dict(signal=12)),
   ('PENDING', 4, dict(bits=1)), ('MASK', 5, dict(bits=29)),
   ('KILL_BEGIN', 6, dict(target=0)), ('HANDLE', 6, dict(actor=0)),
   ('HANDLE', 7, dict(sender=0)), ('HANDLE', 8, dict(code=0)),
   ('THREAD', 9, dict(actor=1)), ('HANDLE', 10, dict(sender=0)),
   ('HANDLE', 11, dict(uid=0)), ('FORK_EMPTY', 12, dict(parent=0)),
   ('ACTION', 13, dict(kind=0)), ('PENDING', 14, dict(mask=30)),
   ('KILL_END', 15, dict(errno=1)), ('HANDLE', 16, dict(actor=0)),
   ('TOTAL', 17, dict(handlers=1)), ('PARENT_PASS', 18, dict(signal=9)),
   ('HANDLE', 19, dict(ordinal=1)), ('ACTION', 20, dict(kind=0)),
   ('PENDING', 21, dict(bits=4)), ('DIRECT', 22, dict(target=0)),
   ('HANDLE', 23, dict(result=0)), ('PARENT_PASS', 24, dict(signal=0)),
   ('KILL_BEGIN', 25, dict(signal=0)), ('ACTION', 28, dict(kind=1)),
   ('CASE_BEGIN', 0, dict(rt1=35)), ('CASE_BEGIN', 0, dict(kill=63)),
   ('READ_RETURN', 23, dict(errno=4)), ('HANDLE', 23, dict(a2=2)),
   ('HANDLE', 23, dict(mask=30)), ('TOTAL', 1, dict(actor=1)),
  ]
  for tag, case, fields in mutations:
   with self.subTest(tag=tag, case=case, fields=fields):
    self.reject(change(raw, tag, case, **fields), linux=True)

 def test_actual_host_ordering_and_record_accountability(self):
  raw = linux_fixture()
  controls = [
   move(raw, 'COMMAND_END', 0, 'COMMAND_ACK'),
   move(raw, 'COMMAND_ACK', 0, 'PENDING', destination=dict(actor=0)),
   move(raw, 'KILL_END', 0, 'KILL_BEGIN'),
   move(raw, 'CHILD_REAP', 0, 'EVENT', destination=dict(tag='ZOMBIE_EOF')),
   move(raw, 'HANDLE', 1, 'DIRECT'),
   move(raw, 'HANDLE', 5, 'COMMAND_BEGIN', destination=dict(operation=1)),
   move(raw, 'HANDLE', 6, 'KILL_BEGIN'),
   move(raw, 'HANDLE', 7, 'KILL_BEGIN'),
   move(raw, 'FORK_EMPTY', 12, 'KILL_BEGIN'),
   move(raw, 'CHILD_REAP', 12, 'FORK_EMPTY'),
   move(raw, 'EVENT', 18, 'EVENT', selection=dict(tag='SURVIVOR_PASS'), destination=dict(tag='LEADER_EXIT')),
   move(raw, 'EVENT', 21, 'EVENT', selection=dict(tag='EXEC_REPLACED'), destination=dict(tag='EXEC_COMMIT')),
   move(raw, 'HANDLE', 23, 'READ_BEGIN'),
   move(raw, 'READ_RETURN', 23, 'HANDLE'),
   move(raw, 'EVENT', 24, 'LEADER_READ', selection=dict(tag='GROUP_AWAIT')),
  ]
  lines = raw.splitlines()
  for tag, case in (('THREAD', 0), ('HANDLE', 1), ('TOTAL', 2), ('COMMAND_ACK', 5), ('FORK_EMPTY', 12), ('CASE_PASS', 18), ('PARENT_PASS', 23)):
   index = locate(lines, tag, case)
   controls.append(b'\n'.join(lines[:index]+lines[index+1:])+b'\n')
   controls.append(b'\n'.join(lines[:index]+[lines[index]]+lines[index:])+b'\n')
  for number, control in enumerate(controls):
   with self.subTest(control=number): self.reject(control, linux=True)

 def test_every_native_case_pending_view_is_checked(self):
  for case in range(33):
   with self.subTest(case=case):
    self.reject(change(events('x86_64'), 'PENDING', case, bits=31))

 def test_native_credentials_pressure_and_mask_semantics(self):
  raw = events('x86_64')
  controls = [
   ('CREDENTIALS', 26, dict(real=0)), ('CREDENTIALS', 26, dict(effective=1101)),
   ('KILL_BEGIN', 26, dict(uid=0)), ('HANDLE', 26, dict(uid=0)),
   ('HANDLE', 26, dict(sender=0)), ('CREDENTIALS', 27, dict(saved=0)),
   ('KILL_END', 27, dict(value=0)), ('KILL_BEGIN', 27, dict(effective=0)),
   ('HANDLE', 29, dict(code=-6)), ('HANDLE', 29, dict(signal=36)),
   ('HANDLE', 30, dict(sender=1)), ('HANDLE', 30, dict(uid=1)),
   ('HANDLE', 30, dict(signal=35)), ('KILL_BEGIN', 31, dict(signal=36)),
   ('LEADER_READ', 32, dict(console=0)), ('LEADER_READ', 32, dict(fd=3)),
  ]
  for tag, case, fields in controls:
   with self.subTest(tag=tag, case=case, fields=fields): self.reject(change(raw, tag, case, **fields))
  for case, ordinal in ((19, 1), (29, 31), (30, 32), (31, 32)):
   lines = raw.splitlines(); index = locate(lines, 'HANDLE', case, ordinal=ordinal)
   self.reject(b'\n'.join(lines[:index]+lines[index+1:])+b'\n')
  # Reversing the two same-number origins must fail even with repaired ordinals.
  lines = raw.splitlines(); first = locate(lines, 'HANDLE', 1, ordinal=0); second = locate(lines, 'HANDLE', 1, ordinal=1)
  a, b = decode(lines[first])[1], decode(lines[second])[1]
  a['ordinal'], b['ordinal'] = 1, 0
  lines[first], lines[second] = encode('HANDLE', b), encode('HANDLE', a)
  self.reject(b'\n'.join(lines)+b'\n')
  # The final RT2 payload subsumes the fallback; zero sender is no longer valid.
  lines = raw.splitlines(); index = locate(lines, 'HANDLE', 31, ordinal=32)
  row = decode(lines[index])[1]; row.update(sender=0, uid=0); lines[index] = encode('HANDLE', row)
  self.reject(b'\n'.join(lines)+b'\n')

 def test_all_ten_native_descriptor_and_address_domains(self):
  for arch in ARCHES:
   raw = events(arch)
   high = 0x40000000 if arch in ('arm32', 'aarch64') else 0x80000000
   for tag, case, fields in (
    ('PIPE', 23, dict(readfd=32)), ('PIPE', 24, dict(writefd=32)),
    ('PIPE', 25, dict(readfd=4)), ('LEADER_READ', 32, dict(fd=32)),
    ('READ_BEGIN', 23, dict(input=high)), ('LEADER_READ', 24, dict(input=high)),
    ('HANDLE', 1, dict(pc=high)), ('CASE_BEGIN', 0, dict(site=high, resume=high+4)),
    ('EVENT', 0, dict(value=32, extra=33)),
   ):
    with self.subTest(arch=arch, tag=tag, case=case, fields=fields):
     if tag == 'EVENT':
      lines = raw.splitlines(); index = locate(lines, 'EVENT', 0, tag='ZOMBIE_GATE')
      row = decode(lines[index])[1]; row.update(fields); lines[index] = encode(tag, row)
      self.reject(b'\n'.join(lines)+b'\n', arch)
     else: self.reject(change(raw, tag, case, **fields), arch)

 def test_malformed_scope_exclusions_and_foreign_native_records(self):
  host, native = linux_fixture(), events('x86_64')
  for control in (
   native + b'PROCESS_SIGNAL_FAIL code=999\n',
   native.replace(b'variant=0', b'variant=2', 1),
   native.replace(b'case=0', b'case=1', 1),
   native.replace(b' uid=0 ', b' uid=0 uid=0 ', 1),
   native.replace(b'PROCESS_SIGNAL_THREAD', b'PROCESS_SIGNAL_UNRECOGNIZED', 1),
   native.replace(b'groups=4 cases=132', b'groups=4 cases=131'),
   native.replace(b'arch=x86_64', b'arch=i386', 1),
   native.replace(b'PROCESS_SIGNAL_CASE_BEGIN', b'prefix PROCESS_SIGNAL_CASE_BEGIN', 1),
   native.replace(b'PROCESS_SIGNAL_PASS', b'PROCESS_SIGNAL_LINUX_REFERENCE_PASS'),
  ): self.reject(control)
  self.reject(host)
  self.reject(native, linux=True)
  self.reject(host+b'OK_NATIVE_DIAGNOSTIC fake=1\n', linux=True)
  self.reject(host.replace(b'reason=native-credential-policy', b'reason=native-console-input-contract', 1), linux=True)
  self.reject(host.replace(b'PROCESS_SIGNAL_LINUX_SKIP', b'PROCESS_SIGNAL_CASE_PASS', 1), linux=True)


if __name__ == '__main__':
 unittest.main()
