"""Bounded SDK31 owned-entry evidence; source/SDK/ELF identity is checked externally.

These records describe service-boundary accounting and actual privileged capture.
They are neither a per-thread event trace nor protection against forged user output.
"""
import re

from native_threads_evidence import validate_execution as validate_threads


FIELDS = ('leased', 'active', 'quarantine', 'peak', 'reservations', 'releases',
          'activations', 'syscalls', 'timers', 'faults', 'rejected')
COUNTERS = ('reservations', 'releases', 'activations', 'syscalls', 'timers', 'faults', 'rejected')
CAPTURES = ('syscalls', 'timers', 'faults')
NUMBER = rb'(0|[1-9][0-9]{0,19})'
PREFIX = (b'OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 '
          b'usable_bytes=65536 backing_bytes=9437184')
RECORD = re.compile(PREFIX + b''.join(b' ' + key.encode() + b'=' + NUMBER for key in FIELDS) +
                    rb' guards=mapped-canaries smp=0\r?\n')


def decode_stacks(serial):
    """Admit complete, fresh, monotonically accounted service snapshots."""
    rows = []
    for line in serial.splitlines(keepends=True):
        if b'OK_ENTRY_STACKS' not in line:
            continue
        match = RECORD.fullmatch(line)
        if not match:
            raise ValueError('incomplete, malformed or wrong-contract entry-stack record')
        row = dict(zip(FIELDS, map(int, match.groups())))
        captures = sum(row[key] for key in CAPTURES)
        if (any(value > 0xffffffffffffffff for value in row.values()) or
                row['active'] or row['quarantine'] or
                not 0 <= row['leased'] <= row['peak'] <= 128 or
                row['peak'] > row['reservations'] or
                bool(row['peak']) != bool(row['reservations']) or
                (row['activations'] and not row['reservations']) or
                row['reservations'] - row['releases'] != row['leased'] or
                captures + row['rejected'] > row['activations']):
            raise ValueError('invalid owned-entry accounting or capture totals')
        if rows:
            previous = rows[-1]
            delta = {key: row[key] - previous[key] for key in COUNTERS}
            if (any(value < 0 for value in delta.values()) or
                    row['peak'] < previous['peak'] or
                    row['peak'] > max(previous['peak'], previous['leased'] + delta['reservations']) or
                    sum(delta[key] for key in CAPTURES) + delta['rejected'] > delta['activations']):
                raise ValueError('entry-stack counters moved backward or lack fresh supporting activity')
            if not any(delta.values()):
                raise ValueError('duplicate or stale entry-stack record')
        rows.append(row)
    if not rows:
        raise ValueError('missing owned-entry records')
    return rows


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch):
    result = validate_threads(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch)
    rows = decode_stacks(serial)
    if any(rows[0].values()):
        raise ValueError('missing empty entry-stack boot baseline')
    boot = decode_stacks(serial[:baseline_begin])
    spans = (serial[baseline_begin:probe_begin], serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end], serial[native_begin:])
    if b'OK_ENTRY_STACKS' in serial[probe_end:native_begin]:
        raise ValueError('entry-stack activity outside dedicated command boundaries')
    endings = [decode_stacks(span)[-1] for span in spans]
    for index, span in enumerate(spans):
        success = b'OK_MUSL_THREADS' if index in (1, 2) else b'hello from ObfuscationOS userland'
        if span.rfind(b'OK_ENTRY_STACKS') <= span.rfind(success):
            raise ValueError('missing entry-stack retirement after dedicated command output')
    baseline = endings[0]
    if baseline['leased'] == 0 or any(row['leased'] != baseline['leased'] for row in endings):
        raise ValueError('dedicated command did not return to live shell lease baseline')
    previous = boot[-1]
    commands = []
    for index, row in enumerate(endings):
        delta = {key: row[key] - previous[key] for key in COUNTERS}
        minimum = result['rounds_per_run'] if index in (1, 2) else 1
        if (delta['reservations'] < minimum or delta['releases'] < minimum or
                delta['activations'] <= 0 or delta['syscalls'] <= 0):
            raise ValueError('dedicated command lacks fresh owned entries, syscalls or lease reuse')
        commands.append(delta)
        previous = row
    result['entry_stacks'] = dict(version=1, scope='actual-user', cpu=0, smp=False,
        guards='mapped-canaries', capacity=128, usable_bytes=65536, backing_bytes=9437184,
        boot=rows[0], baseline=baseline, first=endings[1], second=endings[2], final=endings[3],
        commands=commands, minimum_probe_reservations=result['rounds_per_run'], records=len(rows))
    return result
