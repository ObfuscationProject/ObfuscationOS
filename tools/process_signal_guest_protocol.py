"""Strict guest records for positive process-shared signals.

This module checks the independently specified guest protocol. It is not native
execution evidence: native ownership, image and complete-command ledgers belong
to the outer collector. Cross-thread scheduling is constrained by published
command handshakes, not by one preferred recipient or one serialized trace.
"""
import re
from native_pipe_vector_events import ARCHES, WORD32, instruction
from native_pipe_signal_evidence import READ

GUEST_PREFIX = b'PROCESS_SIGNAL_'
KEYS = ('variant', 'form', 'restart', 'case')
KEY = rb'arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) variant=[01] form=[01] restart=[01] case=[0-9]+'
N, I = rb'[0-9]+', rb'-?[0-9]+'
KILL = dict(zip(ARCHES, (62, 37, 129, 37, 129, 129, 129, 4037, 5060, 37)))
SKIPS = {26: 'native-credential-policy', 27: 'native-credential-policy',
         29: 'private-realtime-capacity-policy', 30: 'private-realtime-capacity-policy',
         31: 'private-realtime-capacity-policy', 32: 'native-console-input-contract'}
EVENTS = ('THREAD_EXIT', 'SURVIVOR_PASS', 'JOIN', 'SENDER_EXIT', 'ZOMBIE_EOF',
          'ZOMBIE_GATE', 'LEADER_EXIT', 'EXEC_COMMIT', 'EXEC_REPLACED', 'EXEC_CHECKED',
          'READ_RETRY', 'READ_PASS', 'READ_AWAIT', 'READ_RELEASE', 'GROUP_AWAIT')
FIELDS = {
 'CASE_BEGIN': 'pid:N uid:N usr1:N usr2:N rt1:N rt2:N winch:N maximum:N kill:N read:N site:N resume:N',
 'THREAD': 'actor:R tid:N mask:N',
 'KILL_BEGIN': 'actor:A ordinal:N pid:N tid:N uid:N effective:N target:I signal:I syscall:N',
 'KILL_END': 'actor:A ordinal:N value:I errno:N',
 'DIRECT': 'actor:A pid:N tid:N target:N signal:N',
 'MASK': 'actor:A bits:N', 'PENDING': 'actor:A ordinal:N bits:N mask:N',
 'ACTION': 'actor:A signal:N kind:[012]',
 'HANDLE': 'actor:A ordinal:N pid:N tid:N signal:N code:I sender:N uid:N mask:N pc:N inspected:[01] again:[01] result:I number:N a0:N a1:N a2:N a3:N abi:N',
 'COMMAND_BEGIN': 'actor:9 target:R seq:N operation:N argument:N',
 'COMMAND_END': 'actor:9 target:R seq:N operation:N argument:N',
 'COMMAND_ACK': 'actor:R seq:N operation:N argument:N',
 'EVENT': 'actor:A tag:(' + '|'.join(EVENTS) + ') value:I extra:I',
 'PIPE': 'actor:9 role:R readfd:I writefd:I',
 'READ_BEGIN': 'actor:R fd:I input:N bytes:1 site:N resume:N syscall:N',
 'READ_RETURN': 'actor:R ordinal:N value:I errno:N',
 'LEADER_READ': 'actor:9 fd:I console:[01] input:N bytes:1',
 'CREDENTIALS': 'actor:8 pid:N real:N effective:N saved:N',
 'CHILD_REAP': 'actor:9 pid:N status:N',
 'FORK_EMPTY': 'actor:8 pid:N parent:N mask:N caught:1 pending:0',
 'TOTAL': 'actor:(0|1|9) handlers:N',
 'CASE_PASS': '', 'PARENT_PASS': 'pid:N signal:N',
 'LINUX_SKIP': 'reason:(' + '|'.join(sorted(set(SKIPS.values()))) + ')',
}
def _pattern(tag, fields):
 types = {'N': N, 'I': I, 'R': b'[01]', 'A': b'(0|1|8|9)'}
 suffix = b''.join(b' ' + name.encode() + b'=' + types.get(kind, kind.encode())
                   for name, kind in (field.split(':', 1) for field in fields.split()))
 return re.compile(GUEST_PREFIX + tag.encode() + b' ' + KEY + suffix)
PATTERNS = tuple(_pattern(tag, fields) for tag, fields in FIELDS.items()) + (
 re.compile(GUEST_PREFIX + rb'(?:LINUX_REFERENCE_)?PASS arch=(x86_64|i386|aarch64|arm32|rv32|rv64|loongarch64|mips|mips64|ppc) variants=2 groups=[0-9]+ cases=[0-9]+ parent=1'),)

def key(row):
 return tuple(row[k] for k in KEYS)

def combinations(arch):
 for variant in range(2):
  for form in range(2 if not variant and arch in ('arm32', 'ppc') else 1):
   for restart in range(2):
    for case in range(33):
     yield variant, form, restart, case

def parse(raw, arch):
 rows = []
 for position, line in enumerate(raw.splitlines()):
  if GUEST_PREFIX not in line:
   continue
  if not any(pattern.fullmatch(line) for pattern in PATTERNS):
   raise ValueError('malformed or unknown process-signal guest record')
  row = dict(tag=line.split()[0].decode().removeprefix('PROCESS_SIGNAL_'),
             position=position, line=line)
  for item in line.split()[1:]:
   name, value = item.decode().split('=', 1)
   if name == 'tag':
    row['event'] = value
    row['tag_value'] = value
   else:
    row[name] = value if name in ('arch', 'reason') else int(value)
  if row['arch'] != arch:
   raise ValueError('process-signal guest architecture differs')
  rows.append(row)
 return rows

def _stream(row):
 # THREAD and TOTAL describe another actor but are emitted by the leader.
 if row['tag'] in ('THREAD', 'TOTAL', 'CASE_BEGIN', 'PARENT_PASS'):
  return 9
 if row['tag'] == 'CASE_PASS':
  return 0 if row['case'] == 18 else 9
 return row.get('actor', 9)

class CasePlan:
 """Independent expected actor streams plus explicit happens-before edges."""
 def __init__(self, begin, threads, child, pipes, read, leader, recipient):
  self.b, self.c = begin, begin['case']
  self.pid, self.uid = begin['pid'], begin['uid']
  self.threads, self.child = threads, child
  self.pipes, self.read, self.leader = pipes, read, leader
  self.streams = {actor: [] for actor in (0, 1, 8, 9)}
  self.edges, self.handles = [], []
  self.seq = [0, 0]
  self.calls = {a: 0 for a in self.streams}
  self.queries = {a: 0 for a in self.streams}
  self.masks = {a: 31 for a in self.streams}
  self.live = set()
  self.recipient = recipient
  self.last_send = {}
 def emit(self, tag, stream=9, **fields):
  row = dict(tag=tag, **fields)
  rows = self.streams[stream]
  if rows:
   self.edges.append((rows[-1], row))
  rows.append(row)
  return row
 def event(self, event, value=0, extra=0, actor=9):
  return self.emit('EVENT', actor, actor=actor, event=event, value=value, extra=extra)
 def spawn(self, actor):
  self.live.add(actor)
  return self.emit('THREAD', actor=actor, tid=self.threads[actor], mask=31)
 def mask(self, value, actor=9):
  self.masks[actor] = value
  return self.emit('MASK', actor, actor=actor, bits=value)
 def pending(self, value, actor=9):
  ordinal = self.queries[actor]
  self.queries[actor] += 1
  return self.emit('PENDING', actor, actor=actor, ordinal=ordinal, bits=value, mask=self.masks[actor])
 def kill(self, target, signal, error=0, actor=9, fatal=False):
  ordinal = self.calls[actor]
  self.calls[actor] += 1
  pid = self.child if actor == 8 else self.pid
  uid = (1102 if self.c == 27 else 1101) if actor == 8 and self.c in (26, 27) else self.uid
  effective = 1102 if actor == 8 and self.c == 27 else 0 if actor == 8 and self.c == 26 else self.uid
  begin = self.emit('KILL_BEGIN', actor, actor=actor, ordinal=ordinal, pid=pid,
                    tid=pid if actor in (8, 9) else self.threads[actor], uid=uid,
                    effective=effective, target=target, signal=signal, syscall=self.b['kill'])
  if not fatal:
   self.emit('KILL_END', actor, actor=actor, ordinal=ordinal,
             value=(-1 if self.b['variant'] else -error) if error else 0,
             errno=error if self.b['variant'] and error else 222)
  if not error and signal:
   self.last_send[(signal, 0)] = begin
  return begin
 def direct(self, target, signal):
  row = self.emit('DIRECT', actor=9, pid=self.pid, tid=self.pid, target=target, signal=signal)
  self.last_send[(signal, -6)] = row
  return row
 def action(self, signal, kind):
  return self.emit('ACTION', actor=9, signal=signal, kind=kind)
 def start(self, actor, op, arg=0):
  self.seq[actor] += 1
  begin = self.emit('COMMAND_BEGIN', actor=9, target=actor, seq=self.seq[actor], operation=op, argument=arg)
  return begin
 def complete_command(self, begin, first, last, ack=True):
  actor = begin['target']
  if ack:
   last = self.emit('COMMAND_ACK', actor, actor=actor, seq=begin['seq'], operation=begin['operation'], argument=begin['argument'])
  end = self.emit('COMMAND_END', actor=9, target=actor, seq=begin['seq'], operation=begin['operation'], argument=begin['argument'])
  self.edges.extend(((begin, first), (last, end)))
  return end
 def command(self, actor, op, arg=0):
  begin = self.start(actor, op, arg)
  if op == 1:
   first = last = self.mask(arg, actor)
  elif op == 2:
   first = last = self.pending(arg, actor)
  elif op in (3, 4):
   first = self.kill(self.pid, self.b['usr1'], actor=actor) if op == 4 else None
   last = self.event('THREAD_EXIT', self.threads[actor], begin['seq'], actor)
   first = first or last
  else:
   raise AssertionError('unsupported synchronous command')
  end = self.complete_command(begin, first, last, ack=op not in (3, 4))
  return begin, end
 def join(self, actor):
  self.live.remove(actor)
  return self.event('JOIN', actor, self.threads[actor])
 def pending_all(self, leader, first, second):
  row = self.pending(leader)
  for actor, value in enumerate((first, second)):
   if actor in self.live:
    _, row = self.command(actor, 2, value)
  return row
 def handler(self, actor, signal, code=0, sender=None, uid=None, after=None, before=None):
  source = self.last_send.get((signal, code))
  spec = dict(actor=actor, signal=signal, code=code,
              sender=self.pid if sender is None else sender,
              uid=self.uid if uid is None else uid,
              after=after, before=before, source=source)
  self.handles.append(spec)
  return spec
 def unmask(self, actor, value, signals):
  # A mask syscall may deliver before its MASK marker. The command handshake,
  # or the previous leader statement, provides the true lower bound.
  previous = self.streams[9][-1]
  if actor == 9:
   end = self.mask(value)
  else:
   previous, end = self.command(actor, 1, value)
  for item in signals:
   signal, code, *identity = item
   self.handler(actor, signal, code, *(identity or [None, None]), after=previous, before=end)
  return end
 def sender(self, denied=False, credentials=False):
  first = None
  if credentials:
   value, effective = (1102, 1102) if denied else (1101, 0)
   first = self.emit('CREDENTIALS', 8, actor=8, pid=self.child, real=value, effective=effective, saved=effective)
  if denied:
   self.kill(self.pid, 0, 1, 8)
   self.kill(self.pid, self.b['usr1'], 1, 8)
   self.kill(self.pid, self.b['maximum'] + 1, 22, 8)
  else:
   first = first or self.kill(self.pid, self.b['usr1'], actor=8)
   if credentials:
    self.kill(self.pid, self.b['usr1'], actor=8)
  end = self.event('SENDER_EXIT', self.child, 1102 if denied else 1101 if credentials else self.uid, 8)
  reap = self.emit('CHILD_REAP', actor=9, pid=self.child, status=17)
  self.edges.extend(((self.streams[9][-2], first or self.streams[8][0]), (end, reap)))
  return reap
 def pipe(self, role):
  return self.emit('PIPE', actor=9, role=role, **self.pipes[role])
 def execute(self):
  b, c = self.b, self.c
  u, v, rt, rt2, win = (b[n] for n in ('usr1', 'usr2', 'rt1', 'rt2', 'winch'))
  self.emit('CASE_BEGIN', **{n: b[n] for n in ('pid', 'uid', 'usr1', 'usr2', 'rt1', 'rt2', 'winch', 'maximum', 'kill', 'read', 'site', 'resume')})
  self.spawn(0)
  if c not in (9, 18):
   self.spawn(1)
  self.pending_all(0, 0, 0)
  if c == 0:
   for target, signal, error in ((self.pid, 0, 0), (self.threads[0], 0, 0), (self.pid, -1, 22), (self.threads[0], b['maximum'] + 1, 22)):
    self.kill(target, signal, error)
   self.pending_all(0, 0, 0)
   self.command(0, 3); self.join(0)
   self.kill(self.threads[0], 0, 3); self.kill(self.threads[0], b['maximum'] + 1, 3)
   self.event('ZOMBIE_GATE', self.gate['value'], self.gate['extra'])
   self.event('ZOMBIE_EOF', self.child, 17)
   self.kill(self.child, 0); self.kill(self.child, u); self.kill(self.child, b['maximum'] + 1, 22)
   self.emit('CHILD_REAP', actor=9, pid=self.child, status=17)
   for signal in (0, b['maximum'] + 1, -1): self.kill(self.child, signal, 3)
  elif c in (1, 2):
   self.kill(self.pid, u); self.direct(self.pid, u if c == 1 else v)
   self.pending_all(1 if c == 1 else 3, 1, 1)
   self.unmask(9, 30 if c == 1 else 28, [(u if c == 1 else v, -6), (u, 0)])
  elif c == 3:
   self.kill(self.pid, v); self.kill(self.pid, u); self.pending_all(3, 3, 3)
   self.unmask(9, 28, [(u, 0), (v, 0)])
  elif c == 4:
   self.direct(self.pid, u); self.kill(self.pid, v); self.pending_all(3, 2, 2)
   self.unmask(9, 29, [(v, 0)]); self.pending_all(1, 0, 0); self.unmask(9, 28, [(u, -6)])
  elif c == 5:
   self.kill(self.pid, u); self.pending_all(1, 1, 1); self.unmask(0, 30, [(u, 0)])
  elif c in (6, 7):
   if c == 7: self.command(0, 1, 30)
   self.command(1, 1, 30)
   source = self.kill(self.threads[0] if c == 6 else self.pid, u)
   self.handler(1 if c == 6 else self.recipient, u, after=source)
  elif c == 8:
   self.direct(self.threads[0], v); self.kill(self.pid, u); self.pending_all(1, 3, 1)
   self.unmask(0, 28, [(v, -6), (u, 0)])
  elif c == 9:
   self.direct(self.pid, v); self.kill(self.pid, u); self.spawn(1); self.pending_all(3, 1, 1)
   self.unmask(1, 30, [(u, 0)]); self.pending_all(2, 0, 0); self.unmask(9, 29, [(v, -6)])
  elif c == 10:
   self.command(0, 4); self.join(0); self.pending_all(1, 0, 1); self.unmask(9, 30, [(u, 0)])
  elif c == 11:
   self.sender(); self.kill(self.pid, u); self.pending_all(1, 1, 1)
   self.unmask(9, 30, [(u, 0, self.child, self.uid)])
  elif c == 12:
   self.direct(self.pid, v); source = self.kill(self.pid, u)
   fork = self.emit('FORK_EMPTY', 8, actor=8, pid=self.child, parent=self.pid, mask=31, caught=1, pending=0)
   reap = self.emit('CHILD_REAP', actor=9, pid=self.child, status=17)
   self.edges.extend(((source, fork), (fork, reap)))
   self.pending_all(3, 1, 1); self.unmask(9, 28, [(v, -6), (u, 0)])
  elif c in (13, 14, 15, 16):
   blocked, nonleader = c in (14, 16), c >= 15
   self.action(u, 1)
   if not blocked:
    if nonleader: self.command(0, 1, 30)
    else: self.mask(30)
   self.kill(self.threads[0] if nonleader else self.pid, u)
   self.pending_all(int(blocked), int(blocked), int(blocked)); self.action(u, 2)
   if blocked: self.unmask(1 if nonleader else 0, 30, [(u, 0)])
  elif c == 17:
   self.direct(self.pid, u); self.direct(self.threads[0], u); self.kill(self.pid, u)
   self.pending_all(1, 1, 1); self.action(u, 1); self.pending_all(0, 0, 0); self.action(u, 2)
   self.mask(30); self.command(0, 1, 30)
  elif c == 18:
   begin = self.start(0, 7)
   retired = self.event('LEADER_EXIT', self.pid)
   unblocked = self.mask(30, 0)
   source = self.kill(self.pid, u, actor=0)
   end = self.pending(0, 0)
   self.handler(0, u, after=source, before=end)
   self.event('SURVIVOR_PASS', self.pid, self.threads[0], 0)
   done = self.emit('CASE_PASS', 0)
   self.edges.extend(((begin, unblocked), (retired, unblocked)))
   parent = self.emit('PARENT_PASS', pid=self.pid, signal=0)
   self.edges.append((done, parent)); return self
  elif c == 19:
   for _ in range(3): self.kill(self.pid, rt)
   self.pending_all(4, 4, 4); self.unmask(9, 27, [(rt, 0)] * 3)
  elif c in (20, 21):
   self.direct(self.pid if c == 20 else self.threads[0], v); self.kill(self.pid, u)
   if c == 21: self.direct(self.pid, rt)
   self.action(win, 1); self.pending_all(3 if c == 20 else 5, 1 if c == 20 else 3, 1)
   begin = self.start(0, 6) if c == 21 else self.streams[9][-1]
   commit = self.event('EXEC_COMMIT', self.pid, self.pid if c == 20 else self.threads[0], 9 if c == 20 else 0)
   replaced = self.event('EXEC_REPLACED', self.pid, self.pid)
   self.edges.extend(((begin, commit), (commit, replaced)))
   self.queries[9] = 0
   self.pending(3)
   for signal in (u, v, rt, rt2): self.action(signal, 2)
   self.unmask(9, 28, [(v, -6), (u, 0)])
   self.mask(31); self.pending(0); self.event('EXEC_CHECKED', 2, 31)
   self.emit('PARENT_PASS', pid=self.pid, signal=0); return self
  elif c == 22:
   self.direct(self.threads[0], v); self.kill(self.threads[0], u); self.pending_all(1, 3, 1)
   self.command(0, 3); self.join(0); self.pending_all(1, 0, 1); self.unmask(9, 30, [(u, 0)])
  elif c in (23, 24, 25, 32):
   self.pipe(0); begin = self.start(0, 5, 30 if c == 23 else 31)
   masked = self.mask(begin['argument'], 0)
   attempt = self.emit('READ_BEGIN', 0, actor=0, **self.read)
   self.edges.append((begin, masked))
   if c == 23:
    awaiting = self.event('READ_AWAIT', 0, self.threads[0]); self.edges.append((attempt, awaiting))
    source = self.kill(self.threads[1], u)
    if not b['restart']:
     first_return = self.emit('READ_RETURN', 0, actor=0, ordinal=0, value=-1 if b['variant'] else -4, errno=4 if b['variant'] else 222)
     retry = self.event('READ_RETRY', self.pipes[0]['readfd'], 1, 0)
    awaiting = self.event('READ_AWAIT', 1, self.threads[0])
    release = self.event('READ_RELEASE', self.pipes[0]['writefd'], 81)
    last_return = self.emit('READ_RETURN', 0, actor=0, ordinal=0 if b['restart'] else 1, value=1, errno=222)
    self.edges.append((release, last_return))
    if not b['restart']: self.edges.append((retry, awaiting))
    self.handler(0, u, after=source, before=last_return if b['restart'] else first_return)
    done = self.event('READ_PASS', 81, 3, 0)
    self.complete_command(begin, masked, done)
   else:
    if c != 32: self.pipe(1)
    killer = self.start(1, 8)
    leader = self.emit('LEADER_READ', actor=9, **self.leader)
    ready = self.event('GROUP_AWAIT', 1 if c == 32 else 2, int(c == 32), 1)
    self.edges.extend(((attempt, leader), (killer, ready), (leader, ready)))
    source = self.kill(self.threads[0] if c == 25 else self.pid, 9, actor=1, fatal=True)
    parent = self.emit('PARENT_PASS', pid=self.pid, signal=9)
    self.edges.append((source, parent)); return self
  elif c == 26:
   self.sender(credentials=True); self.pending_all(1, 1, 1)
   self.unmask(9, 30, [(u, 0, self.child, 1101)])
  elif c == 27:
   self.sender(denied=True, credentials=True); self.pending_all(0, 0, 0)
  elif c == 28:
   self.action(win, 0); self.kill(self.threads[0], win); self.pending_all(16, 16, 16)
   self.action(win, 2); self.unmask(0, 15, [(win, 0)])
  elif c in (29, 30, 31):
   for _ in range(32): self.kill(self.pid, rt)
   if c == 29: self.kill(self.pid, rt)
   else: self.kill(self.pid, rt2); self.kill(self.pid, rt2)
   bits = 4 if c == 29 else 12
   self.pending_all(bits, bits, bits)
   if c == 30:
    self.unmask(9, 23, [(rt2, 0, 0, 0)]); self.pending_all(4, 4, 4)
   self.unmask(9, 27, [(rt, 0)] * 32)
   if c == 31:
    self.mask(31); self.pending_all(8, 8, 8); self.kill(self.pid, rt2)
    self.unmask(9, 23, [(rt2, 0)])
  else:
   raise AssertionError('unknown case')
  self.mask(31)
  for actor in sorted(self.live):
   begin, end = self.command(actor, 1, 31)
   for handler in self.handles:
    if handler['actor'] == actor and handler['before'] is None: handler['before'] = end
  self.pending_all(0, 0, 0)
  for actor in (0, 1, 9):
   self.emit('TOTAL', actor=actor, handlers=sum(h['actor'] == actor for h in self.handles))
  for actor in sorted(self.live): self.command(actor, 3); self.join(actor)
  self.emit('CASE_PASS'); self.emit('PARENT_PASS', pid=self.pid, signal=0)
  return self

def _only(part, tag, count=None):
 rows = [row for row in part if row['tag'] == tag]
 if count is not None and len(rows) != count:
  raise ValueError(f'process-signal {tag} cardinality differs')
 return rows

def validate_cases(raw, arch, linux=False, native=None):
 """Validate a complete guest command; ``native`` is reserved for composition.

Native ownership is intentionally not inferred here. Callers must validate the
native wrapper before treating these guest observations as hardware execution.
 """
 if arch not in ARCHES or linux and arch != 'x86_64':
  raise ValueError('unsupported process-signal profile/reference')
 if linux and any(b'OK_NATIVE_' in line for line in raw.splitlines()):
  raise ValueError('native diagnostics in Linux process-signal reference')
 rows = parse(raw, arch)
 matrix = list(combinations(arch))
 groups = len(matrix) // 33
 finish = 'LINUX_REFERENCE_PASS' if linux else 'PASS'
 cases = groups * (27 if linux else 33)
 if (not rows or rows[-1]['tag'] != finish or
     any(row['tag'] in ('PASS', 'LINUX_REFERENCE_PASS') for row in rows[:-1]) or
     rows[-1]['groups'] != groups or rows[-1]['cases'] != cases):
  raise ValueError('process-signal final scope/cardinality differs')
 result = dict(cases=cases, groups=groups, handlers=0, threads=0,
               exec_replacements=0, signal_terminations=0, kill_operations=0,
               directed_operations=0, pending_observations=0, command_handshakes=0,
               explicit_operations=0, credential_children=0, skipped=len(matrix)-cases)
 low, high = (0x10000000, 0x40000000) if arch in ('arm32', 'aarch64') else (0x40000000, 0x80000000)
 maximum_word = (1 << (32 if arch in WORD32 else 64)) - 1
 seen = set()
 at = 0
 for expected_key in matrix:
  variant, form, restart, case = expected_key
  if at >= len(rows) - 1:
   raise ValueError('missing process-signal case')
  if linux and case in SKIPS:
   row = rows[at]
   if row['tag'] != 'LINUX_SKIP' or key(row) != expected_key or row['reason'] != SKIPS[case]:
    raise ValueError('process-signal explicit Linux exclusion differs')
   at += 1
   continue
  if rows[at]['tag'] != 'CASE_BEGIN' or key(rows[at]) != expected_key:
   raise ValueError('process-signal case matrix differs')
  end = next((index for index in range(at + 1, len(rows)) if rows[index]['tag'] == 'PARENT_PASS'), None)
  if end is None:
   raise ValueError('missing process-signal parent status')
  part = rows[at:end + 1]
  at = end + 1
  if any(key(row) != expected_key for row in part):
   raise ValueError('process-signal record escaped case scope')
  b = part[0]
  expected_signals = (16, 17, 20, 128) if arch.startswith('mips') else (10, 12, 28, 64)
  if ((b['usr1'], b['usr2'], b['winch'], b['maximum']) != expected_signals or
      b['rt1'] != (34 if linux else 35) or b['rt2'] != b['rt1'] + 1 or
      b['kill'] != KILL[arch] or b['read'] != READ[arch] or
      not 0 < b['pid'] <= 0xffffffff or b['pid'] in seen or
      not 0 <= b['uid'] <= 0xffffffff or not linux and b['uid'] != 0):
   raise ValueError('process-signal identity/architecture constants differ')
  seen.add(b['pid'])
  width = 2 if arch in ('x86_64', 'i386') or arch == 'arm32' and form else 4
  if not 0 < b['site'] < b['resume'] <= maximum_word or b['resume'] - b['site'] != width:
   raise ValueError('process-signal trap continuation differs')
  if not linux and (not low <= b['site'] < b['resume'] < high or not instruction(arch, b['site'])):
   raise ValueError('process-signal trap outside admitted native code')
  thread_rows = _only(part, 'THREAD', 1 if case == 18 else 2)
  if [row['actor'] for row in thread_rows] != list(range(len(thread_rows))):
   raise ValueError('process-signal thread role order differs')
  threads = {row['actor']: row['tid'] for row in thread_rows}
  identities = {b['pid'], *threads.values()}
  if len(identities) != 1 + len(threads) or any(not 0 < value <= 0xffffffff for value in identities):
   raise ValueError('process-signal task identity aliases or exceeds domain')
  child = None
  reaps = _only(part, 'CHILD_REAP', int(case in (0, 11, 12, 26, 27)))
  if reaps:
   child = reaps[0]['pid']
   if not 0 < child <= 0xffffffff or child in identities:
    raise ValueError('process-signal child identity aliases group')
  pipe_rows = _only(part, 'PIPE', 2 if case in (24, 25) else 1 if case in (23, 32) else 0)
  if [row['role'] for row in pipe_rows] != list(range(len(pipe_rows))):
   raise ValueError('process-signal pipe role order differs')
  pipes = {row['role']: {name: row[name] for name in ('readfd', 'writefd')} for row in pipe_rows}
  fds = [row[name] for row in pipe_rows for name in ('readfd', 'writefd')]
  gate = [r for r in part if r['tag'] == 'EVENT' and r['event'] == 'ZOMBIE_GATE']
  if len(gate) != int(case == 0):
   raise ValueError('process-signal zombie gate declaration differs')
  if gate:
   fds.extend((gate[0]['value'], gate[0]['extra']))
  if len(fds) != len(set(fds)) or any(not 3 <= value <= (0x7fffffff if linux else 31) for value in fds):
   raise ValueError('process-signal descriptor roles alias or exceed domain')
  read_rows = _only(part, 'READ_BEGIN', int(case in (23, 24, 25, 32)))
  read = {name: read_rows[0][name] for name in ('fd', 'input', 'bytes', 'site', 'resume', 'syscall')} if read_rows else None
  if read and (read['fd'] != pipes[0]['readfd'] or read['site'] != b['site'] or
               read['resume'] != b['resume'] or read['syscall'] != b['read']):
   raise ValueError('process-signal read changed declared descriptor/trap')
  leader_rows = _only(part, 'LEADER_READ', int(case in (24, 25, 32)))
  leader = {name: leader_rows[0][name] for name in ('fd', 'console', 'input', 'bytes')} if leader_rows else None
  if leader and (leader['console'] != int(case == 32) or leader['fd'] != (0 if case == 32 else pipes[1]['readfd'])):
   raise ValueError('process-signal leader read role differs')
  for proof in (read, leader):
   if proof and (not 0 < proof['input'] <= maximum_word or not linux and not low + 1 <= proof['input'] < high - 1):
    raise ValueError('process-signal read buffer outside address domain')
  if read and leader and read['input'] == leader['input']:
   raise ValueError('process-signal simultaneous read buffers alias')
  handlers = _only(part, 'HANDLE')
  recipient = handlers[0]['actor'] if case == 7 and len(handlers) == 1 else 0
  if case == 7 and recipient not in (0, 1):
   raise ValueError('process-signal eligible recipient differs')
  plan = CasePlan(b, threads, child, pipes, read, leader, recipient)
  plan.gate = gate[0] if gate else None
  plan.execute()
  matches = {}
  for actor, expected in plan.streams.items():
   actual = [row for row in part if row['tag'] != 'HANDLE' and _stream(row) == actor]
   if len(actual) != len(expected):
    raise ValueError(f'process-signal case {case} actor {actor} record cardinality differs: {len(actual)} != {len(expected)}')
   for row, want in zip(actual, expected):
    if any(row.get(name) != value for name, value in want.items()):
     raise ValueError(f'process-signal case {case} actor {actor} action/order differs: {row} != {want}')
    matches[id(want)] = row
  for first, second in plan.edges:
   if matches[id(first)]['position'] >= matches[id(second)]['position']:
    raise ValueError('process-signal command/lifecycle causal ordering differs')
  if len(handlers) != len(plan.handles):
   raise ValueError('process-signal handler occurrence cardinality differs')
  for actor in (0, 1, 9):
   actual = [row for row in handlers if row['actor'] == actor]
   expected = [row for row in plan.handles if row['actor'] == actor]
   if len(actual) != len(expected):
    raise ValueError('process-signal handler recipient cardinality differs')
   for ordinal, (row, spec) in enumerate(zip(actual, expected)):
    if (row['ordinal'] != ordinal or row['pid'] != b['pid'] or
        row['tid'] != (b['pid'] if actor == 9 else threads[actor]) or
        any(row[name] != spec[name] for name in ('actor', 'signal', 'code', 'sender', 'uid')) or
        row['mask'] != 31 or not 0 < row['pc'] <= maximum_word or
        not linux and (not low <= row['pc'] < high or not instruction(arch, row['pc']))):
     raise ValueError('process-signal handler identity/occurrence/order differs')
    for bound in ('source', 'after', 'before'):
     node = spec[bound]
     if node is not None:
      position = matches[id(node)]['position']
      if (row['position'] >= position if bound == 'before' else row['position'] <= position):
       raise ValueError('process-signal handler outside generation/eligibility interval')
    if case != 23:
     if any(row[name] != 0 for name in ('inspected', 'again', 'result', 'number', 'a0', 'a1', 'a2', 'a3', 'abi')):
      raise ValueError('process-signal ordinary handler claims a read context')
    else:
     if (row['inspected'] != 1 or row['again'] != restart or
         row['result'] != (0 if restart else -4) or row['a1'] != read['input'] or row['a2'] != 1 or
         restart and (row['number'] != READ[arch] or row['a0'] != read['fd']) or
         restart and not variant and row['a3'] != 0x1357 or
         not variant and row['pc'] != (b['site'] if restart else b['resume'])):
      raise ValueError('process-signal interrupted read context differs')
     if (arch.startswith('mips') and not restart and row['abi'] != 1 or
         arch == 'ppc' and not restart and not row['abi'] & 0x10000000 or
         arch == 'arm32' and not variant and bool(row['abi'] & 0x20) != bool(form) or
         any(not 0 <= row[name] <= maximum_word for name in ('number', 'a0', 'a1', 'a2', 'a3', 'abi'))):
      raise ValueError('process-signal read ABI/status domain differs')
  result['handlers'] += len(handlers)
  result['threads'] += len(thread_rows)
  result['exec_replacements'] += case in (20, 21)
  result['signal_terminations'] += case in (24, 25, 32)
  result['kill_operations'] += len(_only(part, 'KILL_BEGIN'))
  result['directed_operations'] += len(_only(part, 'DIRECT'))
  result['pending_observations'] += len(_only(part, 'PENDING'))
  result['command_handshakes'] += len(_only(part, 'COMMAND_END'))
  result['explicit_operations'] += len(read_rows) + len(leader_rows) + int(case == 23 and not restart)
  result['credential_children'] += case in (26, 27)
 if at != len(rows) - 1:
  raise ValueError('process-signal unassigned records after final case')
 result.update(scope='host-Linux-process-signal-guest-reference' if linux else 'native-process-signal-guest-contract',
               guest_protocol_only=True, native_OS_execution=False, production=False, physical=False, smp=False)
 return result
