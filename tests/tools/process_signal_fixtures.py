"""Retained Linux transcript and independent synthetic all-ten guest schedules.

Transcoding a host observation is only parser test data, never native proof.
Native-only credential/pressure/console scenarios are authored below; they do
not call the production collector's plan builder or import its expectations.
"""
from pathlib import Path
from functools import lru_cache
import base64
import hashlib
import zlib

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')
READ = dict(zip(ARCHES, (0, 3, 63, 3, 63, 63, 63, 4003, 5000, 3)))
KILL = dict(zip(ARCHES, (62, 37, 129, 37, 129, 129, 129, 4037, 5060, 37)))

@lru_cache(None)
def linux_fixture():
 lines = (Path(__file__).resolve().parents[1] / 'fixtures/process_signals_linux_x86_64.b85').read_text().splitlines()
 raw = zlib.decompress(base64.b85decode(''.join(lines[2:])))
 digest = next(line.split(': ', 1)[1] for line in lines if line.startswith('# Uncompressed SHA-256:'))
 if hashlib.sha256(raw).hexdigest() != digest:
  raise AssertionError('retained Linux transcript digest differs')
 return raw

def decode(line):
 parts = line.decode().split()
 row = {name: value if name in ('arch', 'reason', 'tag') else int(value)
        for name, value in (field.split('=', 1) for field in parts[1:])}
 return parts[0].removeprefix('PROCESS_SIGNAL_'), row

def encode(tag, row):
 return ('PROCESS_SIGNAL_' + tag + ' ' + ' '.join(f'{name}={value}' for name, value in row.items())).encode()

def native_only(arch, variant, form, restart, case, pid, site, resume):
 """Serial legal schedules for the six native-only case specifications."""
 key = dict(arch=arch, variant=variant, form=form, restart=restart, case=case)
 u, v, win, maximum = (16, 17, 20, 128) if arch.startswith('mips') else (10, 12, 28, 64)
 lines = []
 calls, queries, seq, masks = [0] * 10, [0] * 10, [0] * 2, [31] * 10
 def emit(kind, **fields):
  lines.append(encode(kind, dict(key, **fields)))
 def event(actor, tag, value, extra):
  emit('EVENT', actor=actor, tag=tag, value=value, extra=extra)
 def mask(actor, bits):
  masks[actor] = bits; emit('MASK', actor=actor, bits=bits)
 def pending(actor, bits):
  emit('PENDING', actor=actor, ordinal=queries[actor], bits=bits, mask=masks[actor]); queries[actor] += 1
 def begin(actor, operation, argument):
  seq[actor] += 1; emit('COMMAND_BEGIN', actor=9, target=actor, seq=seq[actor], operation=operation, argument=argument)
 def command(actor, operation, argument):
  begin(actor, operation, argument)
  if operation == 1: mask(actor, argument)
  elif operation == 2: pending(actor, argument)
  elif operation == 3: event(actor, 'THREAD_EXIT', pid+actor+1, seq[actor])
  if operation != 3: emit('COMMAND_ACK', actor=actor, seq=seq[actor], operation=operation, argument=argument)
  emit('COMMAND_END', actor=9, target=actor, seq=seq[actor], operation=operation, argument=argument)
 def all_pending(bits):
  pending(9, bits); command(0, 2, bits); command(1, 2, bits)
 def kill(actor, signal, error=0, fatal=False):
  caller = pid+3 if actor == 8 else pid
  uid = (1102 if case == 27 else 1101) if actor == 8 else 0
  ordinal = calls[actor]; calls[actor] += 1
  emit('KILL_BEGIN', actor=actor, ordinal=ordinal, pid=caller,
       tid=caller if actor in (8, 9) else pid+actor+1, uid=uid,
       effective=1102 if actor == 8 and case == 27 else 0,
       target=pid, signal=signal, syscall=KILL[arch])
  if not fatal:
   emit('KILL_END', actor=actor, ordinal=ordinal, value=(-1 if variant else -error) if error else 0,
        errno=error if error and variant else 222)
 ordinal = 0
 def handler(signal, sender=pid, uid=0):
  nonlocal ordinal
  emit('HANDLE', actor=9, ordinal=ordinal, pid=pid, tid=pid, signal=signal,
       code=0, sender=sender, uid=uid, mask=31, pc=site+4096,
       inspected=0, again=0, result=0, number=0, a0=0, a1=0, a2=0, a3=0, abi=0)
  ordinal += 1
 emit('CASE_BEGIN', pid=pid, uid=0, usr1=u, usr2=v, rt1=35, rt2=36,
      winch=win, maximum=maximum, kill=KILL[arch], read=READ[arch], site=site, resume=resume)
 emit('THREAD', actor=0, tid=pid+1, mask=31); emit('THREAD', actor=1, tid=pid+2, mask=31)
 all_pending(0)
 if case in (26, 27):
  uid = 1102 if case == 27 else 1101
  emit('CREDENTIALS', actor=8, pid=pid+3, real=uid, effective=1102 if case == 27 else 0, saved=1102 if case == 27 else 0)
  if case == 27:
   kill(8, 0, 1); kill(8, u, 1); kill(8, maximum+1, 22)
  else: kill(8, u)
  event(8, 'SENDER_EXIT', pid+3, uid); emit('CHILD_REAP', actor=9, pid=pid+3, status=17)
  all_pending(int(case == 26))
  if case == 26: handler(u, pid+3, 1101); mask(9, 30)
 elif case in (29, 30, 31):
  for _ in range(32): kill(9, 35)
  if case == 29: kill(9, 35)
  else: kill(9, 36); kill(9, 36)
  all_pending(4 if case == 29 else 12)
  if case == 30: handler(36, 0, 0); mask(9, 23); all_pending(4)
  for _ in range(32): handler(35)
  mask(9, 27)
  if case == 31:
   mask(9, 31); all_pending(8); kill(9, 36); handler(36); mask(9, 23)
 elif case == 32:
  emit('PIPE', actor=9, role=0, readfd=3, writefd=4)
  begin(0, 5, 31); mask(0, 31)
  emit('READ_BEGIN', actor=0, fd=3, input=site+16384, bytes=1, site=site, resume=resume, syscall=READ[arch])
  begin(1, 8, 0)
  emit('LEADER_READ', actor=9, fd=0, console=1, input=site+24576, bytes=1)
  event(1, 'GROUP_AWAIT', 1, 1); kill(1, 9, fatal=True)
  emit('PARENT_PASS', pid=pid, signal=9)
  return lines
 else: raise AssertionError('not a native-only fixture case')
 mask(9, 31); command(0, 1, 31); command(1, 1, 31); all_pending(0)
 for actor in (0, 1, 9): emit('TOTAL', actor=actor, handlers=ordinal if actor == 9 else 0)
 for actor in (0, 1): command(actor, 3, 0); event(9, 'JOIN', actor, pid+actor+1)
 emit('CASE_PASS'); emit('PARENT_PASS', pid=pid, signal=0)
 return lines

@lru_cache(None)
def events(arch):
 """Return guest-only synthetic native test data for one complete command."""
 if arch not in ARCHES: raise ValueError(arch)
 source = {}
 for line in linux_fixture().splitlines():
  tag, row = decode(line)
  if 'case' in row:
   source.setdefault((row['variant'], row['restart'], row['case']), []).append((tag, row))
 out = []
 base = 0x10000000 if arch in ('arm32', 'aarch64') else 0x40000000
 groups = 6 if arch in ('arm32', 'ppc') else 4
 sequence = 0
 for variant in (0, 1):
  for form in range(2 if arch in ('arm32', 'ppc') and not variant else 1):
   for restart in (0, 1):
    for case in range(33):
     pid = 100+10*sequence; sequence += 1
     site = base+8192+form*64
     resume = site+(2 if arch in ('x86_64', 'i386') or arch == 'arm32' and form else 4)
     if case in (26, 27, 29, 30, 31, 32):
      out.extend(native_only(arch, variant, form, restart, case, pid, site, resume)); continue
     part = source[(variant, restart, case)]
     oldpid = part[0][1]['pid']
     identities = {oldpid: pid}
     for tag, row in part:
      if tag == 'THREAD': identities[row['tid']] = pid+row['actor']+1
      elif tag == 'CHILD_REAP': identities[row['pid']] = pid+3
     read_input = base+0x100000
     leader_input = base+0x200000
     signals = {10: 16, 12: 17, 28: 20, 34: 35, 35: 36, 65: 129} if arch.startswith('mips') else {34: 35, 35: 36}
     for tag, original in part:
      row = dict(original)
      row.update(arch=arch, form=form)
      for name in ('pid', 'tid', 'sender', 'parent'):
       if name in row: row[name] = identities.get(row[name], row[name])
      if tag in ('KILL_BEGIN', 'DIRECT'): row['target'] = identities[row['target']]
      if 'signal' in row: row['signal'] = signals.get(row['signal'], row['signal'])
      if 'uid' in row: row['uid'] = 0
      if 'effective' in row: row['effective'] = 0
      if tag == 'CASE_BEGIN':
       row.update(usr1=16 if arch.startswith('mips') else 10, usr2=17 if arch.startswith('mips') else 12,
                  rt1=35, rt2=36, winch=20 if arch.startswith('mips') else 28,
                  maximum=128 if arch.startswith('mips') else 64, kill=KILL[arch], read=READ[arch])
      if 'site' in row: row.update(site=site, resume=resume)
      if tag == 'KILL_BEGIN': row['syscall'] = KILL[arch]
      if tag == 'READ_BEGIN': row.update(syscall=READ[arch], input=read_input)
      if tag == 'LEADER_READ': row['input'] = leader_input
      if tag == 'HANDLE':
       row['pc'] = (site if restart else resume) if case == 23 and not variant else base+0x4000
       if case == 23:
        row.update(number=READ[arch] if restart else 1 << 30, a1=read_input,
                   abi=(1 if not restart else 0) if arch.startswith('mips') else
                       0x10000000 if arch == 'ppc' and not restart else
                       0x10 | (0x20 if form else 0) if arch == 'arm32' else 0)
        if restart: row['a0'] = next(r['fd'] for t, r in part if t == 'READ_BEGIN')
      if tag == 'EVENT':
       if row['tag'] in ('THREAD_EXIT', 'SENDER_EXIT', 'ZOMBIE_EOF', 'LEADER_EXIT', 'EXEC_COMMIT', 'EXEC_REPLACED', 'SURVIVOR_PASS'):
        row['value'] = identities.get(row['value'], row['value'])
       if row['tag'] in ('JOIN', 'READ_AWAIT', 'EXEC_COMMIT', 'EXEC_REPLACED', 'SURVIVOR_PASS'):
        row['extra'] = identities.get(row['extra'], row['extra'])
       if row['tag'] == 'SENDER_EXIT': row['extra'] = 0
      out.append(encode(tag, row))
 out.append(encode('PASS', dict(arch=arch, variants=2, groups=groups, cases=33*groups, parent=1)))
 return b'\n'.join(out)+b'\n'
