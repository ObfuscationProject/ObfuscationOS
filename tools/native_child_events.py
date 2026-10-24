"""Owned child-wait diagnostic ledger; diagnostics alone do not prove execution."""
import re

PREFIX = b'OK_NATIVE_CHILD_'
OWNER = rb'pid=([0-9]+) tid=([0-9]+) request=([0-9]+) wait=([0-9]+)'
WAIT = re.compile(PREFIX + rb'WAIT ' + OWNER + rb' selector=([0-9]+) output=([0-9]+) format=(status|siginfo) outcome=(arm|rearm|complete|interrupted|cancelled) result=(-?[0-9]+) live=([0-9]+)')
SIGNAL = re.compile(PREFIX + rb'SIGNAL ' + OWNER + rb' origin=([0-9]+) signal=([0-9]+) outcome=(restart|eintr) pc=([0-9]+) selector=([0-9]+) output=([0-9]+) live=([0-9]+)')
PATTERNS = (WAIT, SIGNAL)


def parsed(pattern, line):
    if not pattern.fullmatch(line):
        raise ValueError('malformed child-wait record')
    row = {'tag': line.split()[0].decode(), 'line': line}
    for field in line.split()[1:]:
        name, value = field.decode().split('=', 1)
        row[name] = value if name in ('format', 'outcome') else int(value)
    return row


def scan(span, allow_signal=False, baseline=None, boot=False, signal_numbers=(10,16), pc_bounds=(0x40000000,0x80000000)):
    active, events, pending = dict(baseline or {}), [], None
    seen = {owner + (row['request'],) for owner, row in active.items()}
    for line in span.splitlines():
        if line.startswith(b'OK_NATIVE_IMAGE '):
            # Image replacement can reset a thread's scheduler ticket sequence.
            seen.clear()
        if PREFIX not in line:
            if line and pending is not None:
                raise ValueError('child retirement lacks immediate signal publication')
            continue
        banner = b'oksh: commands run as user processes; use | to connect two programs'
        if boot and line.startswith(banner + PREFIX):
            line = line[len(banner):]
        pattern = next((p for p in PATTERNS if p.fullmatch(line)), None)
        if pattern is None:
            raise ValueError('malformed native child diagnostic')
        row = parsed(pattern, line)
        owner = row['pid'], row['tid']
        if (any(not 0 < v <= 0xffffffff for v in owner) or
                not 0 < row['request'] <= 0xffffffffffffffff or
                not row['request'] <= row['wait'] <= 0xffffffffffffffff or
                not 0 < row['selector'] <= 0xffffffff or
                not 0 <= row['output'] <= 0xffffffffffffffff):
            raise ValueError('invalid child wait identity or copied request')
        if pending is not None and pattern is not SIGNAL:
            raise ValueError('missing child signal publication')
        if pattern is SIGNAL:
            if not allow_signal or pending is None:
                raise ValueError('unowned child signal publication')
            if (any(row[k] != pending[k] for k in ('pid', 'tid', 'request', 'wait', 'selector', 'output', 'live')) or
                    not 0 < row['origin'] <= 0xffffffffffffffff or row['signal'] not in signal_numbers or
                    not pc_bounds[0] <= row['pc'] < pc_bounds[1] or
                    pending['result'] != (0 if row['outcome'] == 'restart' else -4)):
                raise ValueError('child signal differs from exact retired continuation')
            row['terminal'] = pending
            pending = None
        elif row['outcome'] == 'arm':
            identity = owner + (row['request'],)
            if owner in active or identity in seen or row['request'] != row['wait'] or row['result'] != -11:
                raise ValueError('duplicate or invalid child wait admission')
            if row['format'] == 'siginfo' and row['output'] == 0:
                raise ValueError('null copied child siginfo output')
            seen.add(identity)
            active[owner] = row
        else:
            prior = active.get(owner)
            if prior is None or any(row[k] != prior[k] for k in ('request', 'selector', 'output', 'format')):
                raise ValueError('child wait lost its copied request')
            if row['outcome'] == 'rearm':
                if row['wait'] <= prior['wait'] or row['result'] != -11:
                    raise ValueError('child rearm did not advance the owned ticket')
                row['previous'] = prior
                active[owner] = row
            else:
                if row['wait'] != prior['wait']:
                    raise ValueError('child retirement changed owned ticket')
                value, outcome = row['result'], row['outcome']
                if (outcome == 'cancelled' and value != -125 or
                        outcome == 'interrupted' and value not in (0, -4) or
                        outcome == 'complete' and not (0 < value <= 0xffffffff or value in (-3, -10, -14))):
                    raise ValueError('child retirement result differs from cause')
                if outcome == 'complete' and value > 0 and row['selector'] not in (value, 0xffffffff):
                    raise ValueError('child wait reaped a different selected child')
                row['arm'] = prior
                del active[owner]
                if outcome == 'interrupted':
                    pending = row
        if row['live'] != len(active):
            raise ValueError('child wait live count differs from owned ledger')
        events.append(row)
    if pending is not None:
        raise ValueError('unpublished child signal at command boundary')
    return events, active


def native_events(span, allow_signal=False, baseline=None, signal_numbers=(10,16), pc_bounds=(0x40000000,0x80000000)):
    events, active = scan(span, allow_signal=allow_signal, baseline=baseline, signal_numbers=signal_numbers, pc_bounds=pc_bounds)
    # An inherited owner must stay live throughout this command. Final equality
    # alone would admit retirement/recreation across an image ticket reset.
    if any((row['pid'], row['tid']) in (baseline or {}) for row in events):
        raise ValueError('child wait command touched an inherited owner')
    if active != (baseline or {}):
        raise ValueError('child wait command changed its inherited baseline')
    return events


def normalize_transcript(serial, boundaries):
    """Split only observed complete banners interrupted by a valid WAIT record.

    Offsets belong to the original immutable serial bytes. Return recalculated
    offsets for the normalized view; do not change or fabricate accounting.
    """
    if (len(boundaries) != 5 or any(type(x) is not int for x in boundaries) or
            not 0 < boundaries[0] < boundaries[1] < boundaries[2] <
            boundaries[3] == boundaries[4] < len(serial)):
        raise ValueError('invalid original child command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('child command boundary is not a complete prompt')
    ends = [0, *boundaries[:4], len(serial)]
    parts = []
    banners = (b'hello from ObfuscationOS userland',
               b'oksh: commands run as user processes; use | to connect two programs')
    for first, last in zip(ends, ends[1:]):
        lines = []
        for raw in serial[first:last].splitlines(keepends=True):
            for banner in banners:
                if raw.startswith(banner + PREFIX):
                    tail = raw[len(banner):]
                    if not tail.endswith(b'\n') or not WAIT.fullmatch(tail.removesuffix(b'\n').removesuffix(b'\r')):
                        raise ValueError('malformed child diagnostic after known user banner')
                    raw = banner + b'\n' + tail
                    break
            lines.append(raw)
        parts.append(b''.join(lines))
    offsets = tuple(sum(map(len, parts[:i])) for i in range(1, 5))
    return b''.join(parts), (*offsets, offsets[-1])


def boot_baseline(boot, required=False):
    """Admit the sole init-to-shell wait, or the older no-child-record profile."""
    events, active = scan(boot)
    if not events and not required:
        return {}
    if len(active) != 1:
        raise ValueError('expected one owned init-to-shell wait at boot')
    row = next(iter(active.values()))
    if (row['pid'] != row['tid'] or row['selector'] in (0, 0xffffffff, row['pid']) or
            row['format'] != 'status' or row['outcome'] != 'arm'):
        raise ValueError('invalid persistent init child wait')
    return active
