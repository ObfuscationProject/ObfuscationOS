#!/usr/bin/env python3
"""Strict numeric admission of actual native/musl clock-setting serial evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setter_forms(sdk):
    """Use only the explicitly selected exported SDK, including all ten profiles."""
    header = Path(sdk) / 'include/ok/abi/linux_profile_data.hpp'
    source = header.read_text()
    operations = re.search(r'enum class Operation : u8 \{([^}]+)\};', source)
    if operations is None:
        raise ValueError('SDK operation declaration missing')
    names = [name.strip() for name in operations[1].split(',')]
    if names[-1] != 'count' or len(names) != len(set(names)):
        raise ValueError('ambiguous SDK operation declaration')
    names.pop()
    indices = {name: names.index(name) for name in
               ('clock_settime', 'clock_settime32', 'clock_settime64')}
    rows = re.findall(r'\{"([a-z0-9_]+)", (4|8), (?:true|false), [^\n]+\n\s*\{([^}]+)\},', source)
    profiles = {}
    for arch, word_bytes, raw in rows:
        numbers = [item.strip() for item in raw.split(',')]
        if arch in profiles or len(numbers) != len(names):
            raise ValueError('ambiguous SDK profile ' + arch)
        forms = []
        for operation, index in indices.items():
            value = numbers[index]
            if value == 'unavailable_number':
                continue
            if not re.fullmatch(r'[0-9]+U', value):
                raise ValueError('invalid SDK setter number')
            width = 8 if operation == 'clock_settime32' else 16
            forms.append({'operation': operation, 'number': int(value[:-1]), 'bytes': width,
                          'padding': 'none' if width == 8 else 'ignored-high32' if word_bytes == '4' else 'full64'})
        profiles[arch] = forms
    expected = {'i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc'}
    if set(profiles) != expected or sum(map(len, profiles.values())) != 14:
        raise ValueError('SDK does not preserve ten profiles and fourteen setter forms')
    return profiles


def rows(text, marker, fields):
    found = []
    for line in text.splitlines():
        if marker not in line:
            continue
        if not line.startswith(marker + ' '):
            raise ValueError('interleaved or malformed ' + marker)
        values = {}
        for token in line[len(marker) + 1:].split():
            pair = token.split('=', 1)
            if len(pair) != 2 or not pair[1] or pair[0] in values:
                raise ValueError('malformed field in ' + marker)
            values[pair[0]] = pair[1]
        if set(values) != set(fields):
            raise ValueError('unexpected fields in ' + marker)
        found.append(values)
    return found


def integer(value):
    if not re.fullmatch(r'[0-9]+', value):
        raise ValueError('invalid unsigned serial integer ' + value)
    return int(value)


def nanoseconds(value):
    match = re.fullmatch(r'([0-9]+):([0-9]+)', value)
    if match is None or int(match[2]) >= 1_000_000_000:
        raise ValueError('invalid timespec ' + value)
    return int(match[1]) * 1_000_000_000 + int(match[2])


def validate_clock_set(text, sdk, arch, authority, *, require_fixture=False, require_held=False):
    if not text.endswith('\n'):
        raise ValueError('serial evidence has an incomplete final line')
    if authority not in ('root', 'denied'):
        raise ValueError('unknown clock-set authority')
    if require_held and (authority != 'root' or not require_fixture):
        raise ValueError('held-wait evidence requires the actual root fixture')
    failures = ('CLOCK_SET_NATIVE_FAIL', 'CLOCK_SET_MUSL_FAIL', 'CLOCK_SET_FIXTURE_FAIL',
                'CLOCK_SET_NATIVE_EXEC_ERROR') + (('fault=contained',) if require_fixture else ())
    for failure in failures:
        if failure in text:
            raise ValueError('guest failure ' + failure)
    required = (['CLOCK_SET_NATIVE_PASS setter=pass global-musl-child=pass monotonic=pass',
                 'CLOCK_SET_MUSL_PASS setters=pass backwards=pass post2038=pass fork-exec=pass',
                 'CLOCK_SET_MUSL_EXEC_PASS inherited=software-time'] if authority == 'root' else
                ['CLOCK_SET_NATIVE_DENIED_PASS authority=real-process errno=EPERM',
                 'CLOCK_SET_MUSL_DENIED_PASS authority=real-process errno=EPERM'])
    if require_fixture:
        required += ['CLOCK_SET_FIXTURE_BEGIN scope=actual-user-mode sdk-only=1',
                     'CLOCK_SET_FIXTURE_PASS mode=' + ('root' if authority == 'root' else 'deny') +
                     ' exit=0 actual-native-and-musl=1']
    lines = text.splitlines()
    for marker in required:
        if lines.count(marker) != 1:
            raise ValueError('missing or repeated ' + marker)
    profiles = setter_forms(sdk)
    raw = rows(text, 'CLOCK_SET_RAW_PASS', ('number', 'bytes', 'authority', 'copies', 'range', 'padding'))
    actual = []
    for row in raw:
        if row['authority'] != authority or row['copies'] != 'pass' or row['range'] != 'pass':
            raise ValueError('raw setter authority/copy/range failure')
        actual.append((integer(row['number']), integer(row['bytes']), row['padding']))
    expected = [(row['number'], row['bytes'], row['padding']) for row in profiles[arch]]
    if sorted(actual) != sorted(expected):
        raise ValueError('raw setter forms do not match explicit SDK profile')
    result = {'authority': authority, 'architecture': arch,
              'sdk_profile_header_sha256': sha(Path(sdk) / 'include/ok/abi/linux_profile_data.hpp'),
              'all_profile_setter_forms': profiles, 'raw_forms': raw, 'required_markers': required}
    if require_fixture:
        credentials = rows(text, 'CLOCK_SET_FIXTURE_CREDENTIALS',
                           ('pid', 'uid', 'euid', 'gid', 'egid', 'before-user-entry'))
        expected_id = '0' if authority == 'root' else '1000'
        if len(credentials) != 1 or credentials[0]['before-user-entry'] != '1' or any(
                credentials[0][name] != expected_id for name in ('uid', 'euid', 'gid', 'egid')):
            raise ValueError('actual initial process authority evidence missing')
        integer(credentials[0]['pid'])
        result['credentials'] = credentials[0]
    sample_rows = rows(text, 'CLOCK_SET_MUSL_SAMPLE',
                       ('label', 'requested', 'before', 'after', 'read_before', 'wall', 'at'))
    wait_rows = rows(text, 'CLOCK_SET_WAIT_PASS', ('kind', 'parent', 'child', 'before', 'first', 'last', 'after'))
    if authority == 'denied':
        if sample_rows or wait_rows or 'CLOCK_SET_FIXTURE_WAIT_SET' in text:
            raise ValueError('denied run unexpectedly contains successful time mutation evidence')
        return result
    requested = {'time32-date': 1700000001123456789, 'forward': 1700000101456789123,
                 'backward': 1700000002987654321, 'post2038': 2214176523135791113}
    if [row['label'] for row in sample_rows] != list(requested):
        raise ValueError('four ordered clock sample labels missing or repeated')
    samples = []
    for row in sample_rows:
        values = {name: nanoseconds(value) for name, value in row.items() if name != 'label'}
        b, a, c, d = [values[key] for key in ('before', 'after', 'read_before', 'at')]
        wanted = values['requested']
        lower, upper = wanted + c - a, wanted + d - b
        if wanted != requested[row['label']] or not b <= a <= c <= d or c - a < 20_000_000:
            raise ValueError('invalid elapsed sample interval ' + row['label'])
        if not lower <= values['wall'] <= upper:
            raise ValueError('wall clock outside exact elapsed bracket ' + row['label'])
        samples.append({'label': row['label'], **values, 'wall_lower': lower, 'wall_upper': upper})
    if [integer(row['kind']) for row in wait_rows] != list(range(6)):
        raise ValueError('six ordered wait kinds missing or repeated')
    waits = [{name: integer(value) for name, value in row.items()} for row in wait_rows]
    parent = waits[0]['parent']
    if parent == 0 or any(row['parent'] != parent or row['child'] in (0, parent) for row in waits) or len(
            {row['child'] for row in waits}) != 6:
        raise ValueError('wait process identity is inconsistent')
    for row in waits:
        if not row['before'] <= row['first'] <= row['last'] < row['after'] or not (
                150_000_000 <= row['after'] - row['before'] < 3_000_000_000):
            raise ValueError('invalid wait interval kind=' + str(row['kind']))
    if any(previous['after'] >= following['before'] for previous, following in zip(waits, waits[1:])):
        raise ValueError('wait intervals overlap or are out of order')
    native_wait = rows(text, 'CLOCK_SET_NATIVE_WAIT', ('pid', 'status'))
    if len(native_wait) != 1 or integer(native_wait[0]['pid']) != parent or native_wait[0]['status'] != '0':
        raise ValueError('native parent did not observe the exact musl waiter exiting successfully')
    result.update(samples=samples, waits=waits)
    if not require_held:
        return result
    events = []
    for line in lines:
        if 'CLOCK_SET_FIXTURE_WAIT_SET' not in line:
            continue
        fields = ('api', 'pid', 'tid', 'wall_before', 'wall_after', 'monotonic_before',
                  'monotonic_after', 'wait_key', 'deadline', 'held')
        fields += ('wait_generation',) if 'api=sleep ' in line else ('pending-syscall',)
        event = rows(line, 'CLOCK_SET_FIXTURE_WAIT_SET', fields)[0]
        if event['held'] != '1' or event['api'] not in ('sleep', 'poll', 'select'):
            raise ValueError('invalid held waiter event')
        for name in ('pid', 'tid', 'wall_before', 'wall_after', 'monotonic_before', 'monotonic_after', 'wait_key'):
            event[name] = integer(event[name])
        if event['wall_after'] != event['wall_before'] + 1 or event['monotonic_after'] < event['monotonic_before']:
            raise ValueError('held event does not bracket one actual realtime mutation')
        if event['api'] == 'sleep':
            event['deadline'] = integer(event['deadline'])
            event['wait_generation'] = integer(event['wait_generation'])
            if event['deadline'] <= event['monotonic_after']:
                raise ValueError('held sleep deadline already expired')
        elif event['deadline'] != 'private' or event['pending-syscall'] != '1':
            raise ValueError('held poll/select evidence must expose its actual observation scope')
        events.append(event)
    assigned = set()
    for row in waits:
        api = ('sleep', 'sleep', 'poll', 'select', 'poll', 'select')[row['kind']]
        matches = [index for index, event in enumerate(events) if event['pid'] == row['parent'] and
                   event['api'] == api and row['first'] <= event['monotonic_before'] <=
                   event['monotonic_after'] <= row['last']]
        if len(matches) < 2 or assigned.intersection(matches):
            raise ValueError('missing two distinct waiter-held mutations for kind=' + str(row['kind']))
        selected = [events[index] for index in matches]
        if len({event['wall_before'] for event in selected}) != len(selected):
            raise ValueError('repeated held mutation generation')
        if len({event['tid'] for event in selected}) != 1:
            raise ValueError('waiter thread identity changed')
        if api == 'sleep' and len({(event['deadline'], event['wait_generation']) for event in selected}) != 1:
            raise ValueError('sleep deadline or generation changed between clock sets')
        assigned.update(matches)
        row['held_event_indices'] = matches
    if len(assigned) < 12:
        raise ValueError('fewer than twelve correlated held waiter events')
    result.update(held_events=events, correlated_held_event_count=len(assigned),
                  poll_select_deadline_scope='private runtime deadline; actual blocked pending syscall observed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', type=Path, required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--arch', required=True)
    parser.add_argument('--authority', choices=('root', 'denied'), required=True)
    parser.add_argument('--require-fixture', action='store_true')
    parser.add_argument('--require-held', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = validate_clock_set(args.serial.read_text(), args.kernel_sdk, args.arch, args.authority,
                                require_fixture=args.require_fixture, require_held=args.require_held)
    result.update(status='passed', serial_sha256=sha(args.serial), validator_sha256=sha(__file__))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('PASS actual clock-set serial evidence')


if __name__ == '__main__':
    main()
