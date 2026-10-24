"""Causal serial evidence for the bounded native dependency-supervision fixture."""
from __future__ import annotations
import re

PASS = b'SERVICE_GRAPH_NATIVE_PASS pid=1 setup=1 upstream=2 downstream=2 other=1 shutdown=ordered'
FAILURES = (b'OK_TEST_FAIL', b'acceptance=FAIL', b'boot=degraded', b'boot=failed',
            b'POSIX_CHECK failed:', b'MUSL_CHECK failed:', b'-failed name=', b'-error name=',
            b'SERVICE_EVENT kind=init-invalid', b'SERVICE_EVENT kind=service-lost',
            b'SERVICE_EVENT kind=stop-timeout', b'SERVICE_EVENT kind=orphan-timeout',
            b'SERVICE_EVENT kind=deadline-overflow')
NUMBER = rb'(0|[1-9][0-9]{0,19})'
EVENT = re.compile(rb'SERVICE_EVENT kind=([a-z-]+) name=([a-z-]+) generation=' + NUMBER +
                   rb' pid=' + NUMBER + rb' value=' + NUMBER)
CHILD = re.compile(rb'SERVICE_CHILD kind=([a-z-]+) name=([a-z-]+) generation=' + NUMBER +
                   rb' attempt=' + NUMBER + rb' pid=' + NUMBER + rb' value=' + NUMBER)


def validate(serial: bytes) -> dict:
    if not isinstance(serial, bytes) or not serial:
        raise ValueError('empty service graph serial evidence')
    normalized = serial.replace(b'\r\n', b'\n')
    if b'\r' in normalized: raise ValueError('bare carriage return in serial evidence')
    if any(token in normalized for token in FAILURES):
        raise ValueError('guest or kernel failure in service graph evidence')
    lines = normalized.split(b'\n')
    if lines[-1] and b'SERVICE_' in lines[-1]: raise ValueError('incomplete service graph record')
    events, children, passes = [], [], []
    for position, line in enumerate(lines):
        if b'SERVICE_' not in line: continue
        if line == PASS: passes.append(position); continue
        match = EVENT.fullmatch(line)
        if match:
            kind, name = match[1].decode(), match[2].decode()
            generation, pid, value = map(int, match.groups()[2:])
            if generation > 2**64 - 1 or pid > 2**31 - 1 or value > 2**31 - 1:
                raise ValueError('event integer exceeds its native field')
            events.append((position, kind, name, generation, pid, value)); continue
        match = CHILD.fullmatch(line)
        if match:
            kind, name = match[1].decode(), match[2].decode()
            generation, attempt, pid, value = map(int, match.groups()[2:])
            if max(generation, attempt, pid, value) > 2**31 - 1:
                raise ValueError('child integer exceeds fixture field')
            children.append((position, kind, name, generation, attempt, pid, value)); continue
        raise ValueError('malformed or unexpected service graph record')
    if len(passes) != 1: raise ValueError('missing unique graph completion record')

    expected = {('setup', 1): ('launch', 'exec', 'reap-service', 'ready'),
                ('upstream', 1): ('launch', 'exec', 'notify', 'ready', 'reap-service'),
                ('upstream', 2): ('launch', 'exec', 'notify', 'ready', 'term', 'reap-service'),
                ('downstream', 1): ('launch', 'exec', 'notify', 'ready', 'term', 'reap-service'),
                ('downstream', 2): ('launch', 'exec', 'notify', 'ready', 'term', 'reap-service')}
    pids, positions = {}, {}
    for key, kinds in expected.items():
        rows = [row for row in events if row[2:4] == key]
        # Notify may precede exec; readiness must follow both confirmations.
        observed = tuple(row[1] for row in rows)
        alternate = (tuple('notify' if kind == 'exec' else 'exec' if kind == 'notify' else kind for kind in kinds)
                     if 'notify' in kinds else kinds)
        if observed not in (kinds, alternate): raise ValueError('missing, repeated or reordered service events')
        pid = rows[0][4]
        if pid <= 1 or any(row[4] != pid for row in rows): raise ValueError('service process ownership mismatch')
        pids[key] = pid
        for row in rows:
            _, kind, _, generation, _, value = row
            wanted = {'launch': generation, 'exec': 0, 'notify': 0,
                      'ready': 2 if key[0] == 'setup' else 1,
                      'term': 1 if key == ('downstream', 1) else 2,
                      'reap-service': 42 << 8 if key == ('upstream', 1) else 0}[kind]
            if value != wanted: raise ValueError('service status, mode or retirement reason mismatch')
            positions[key + (kind,)] = row[0]
    if len(set(pids.values())) != 5: raise ValueError('service process generations alias')
    if any(row[2:4] not in expected and row[2] != 'init' for row in events):
        raise ValueError('unknown service token')
    roots = [row for row in events if row[2] == 'init']
    if (len(roots) != 4 or roots[0][1] != 'init' or roots[-1][1] != 'stopped' or
            {row[1] for row in roots[1:3]} != {'reap-other', 'shutdown'}):
        raise ValueError('missing, repeated or reordered init observations')
    roots = [next(row for row in roots if row[1] == kind)
             for kind in ('init', 'reap-other', 'shutdown', 'stopped')]
    if any(row[3] != 0 for row in roots): raise ValueError('init has service generation')
    for row, pid, value in ((roots[0], 1, 3), (roots[2], 1, 0), (roots[3], 1, 1)):
        if row[4:] != (pid, value): raise ValueError('init identity or status mismatch')
    orphan_pid = roots[1][4]
    if orphan_pid <= 1 or orphan_pid in pids.values() or roots[1][5] != 17 << 8:
        raise ValueError('adopted orphan identity or exit status mismatch')
    if roots[0][0] >= min(row[0] for row in events if row[2] != 'init'):
        raise ValueError('service appeared before init')
    for a, b in ((('setup', 1, 'ready'), ('upstream', 1, 'launch')),
                 (('upstream', 1, 'ready'), ('downstream', 1, 'launch')),
                 (('upstream', 1, 'reap-service'), ('downstream', 1, 'term')),
                 (('upstream', 1, 'reap-service'), ('upstream', 2, 'launch')),
                 (('upstream', 2, 'ready'), ('downstream', 2, 'launch')),
                 (('downstream', 1, 'reap-service'), ('downstream', 2, 'launch')),
                 (('downstream', 2, 'reap-service'), ('upstream', 2, 'term'))):
        if positions[a] >= positions[b]: raise ValueError('dependency or reap-before-restart ordering violation')
    if not (roots[2][0] < positions[('downstream', 2, 'term')] and
            positions[('upstream', 2, 'reap-service')] < roots[3][0] < passes[0]):
        raise ValueError('shutdown completion ordering violation')

    child_kinds = {('setup', 1): ('start', 'setup'),
                   ('upstream', 1): ('start', 'notify', 'crash'),
                   ('upstream', 2): ('start', 'notify', 'stop'),
                   ('downstream', 1): ('start', 'notify', 'orphan', 'stop'),
                   ('downstream', 2): ('start', 'notify', 'request-stop', 'stop')}
    for key, kinds in child_kinds.items():
        rows = [row for row in children if row[2:4] == key]
        if tuple(row[1] for row in rows) != kinds: raise ValueError('missing, repeated or reordered child observations')
        for row in rows:
            position, kind, _, _, attempt, pid, value = row
            if position <= roots[0][0]: raise ValueError('child appeared before init')
            wanted_pid = orphan_pid if kind == 'orphan' else pids[key]
            wanted_value = 42 if kind == 'crash' else 1 if kind in ('orphan', 'request-stop') else 0
            if attempt != key[1] or pid != wanted_pid or value != wanted_value:
                raise ValueError('child observation does not match its service generation')
            if position >= positions[key + ('reap-service',)]:
                raise ValueError('child observation follows service reap')
            if kind == 'start' and key[0] != 'setup' and position >= positions[key + ('notify',)]:
                raise ValueError('notify precedes child start observation')
            if kind == 'orphan' and position >= roots[1][0]: raise ValueError('orphan reaped before adoption observation')
            if kind == 'orphan' and position <= positions[key + ('term',)]:
                raise ValueError('fixture orphan appeared before dependency TERM')
            if kind == 'crash' and position >= positions[key + ('reap-service',)]:
                raise ValueError('crash observation follows reap')
            if kind == 'stop' and not positions[key + ('term',)] < position < positions[key + ('reap-service',)]:
                raise ValueError('stop lacks matching TERM/reap interval')
            if kind == 'request-stop' and position >= roots[2][0]: raise ValueError('shutdown precedes child request')
    if len(children) != sum(map(len, child_kinds.values())):
        raise ValueError('unknown child observation')
    if passes[0] <= max(row[0] for row in events + children): raise ValueError('completion precedes observations')
    return dict(service_pids={f'{name}-{generation}': pid for (name, generation), pid in pids.items()},
                orphan_pid=orphan_pid, readiness_modes=['oneshot', 'notify'],
                dependency_retirements=1, restarts=2, other_reaped=1, forced_stops=0,
                shutdown='reverse-dependency', scope='observed native bounded service-graph sequence')
