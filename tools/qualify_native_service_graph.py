#!/usr/bin/env python3
"""Build an isolated SDK-only consumer and execute the ordinary native PID 1 graph.

This bounded QEMU lane tests native service instructions and syscalls. It does not
qualify system shutdown, orphan adoption, physical hardware or all M7 services.
An explicit --native-adoption lane additionally checks PID 1 adoption/reap of
live and completed native descendants.
The --shell-acceptance option adds the native pipeline/redirection suite.
The --native-control option explicitly enables the bounded PID 1 control socket.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from qemu_distro import command_for
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import source_files
from qualify_oksh_guest import MARKER as OKSH_MARKER
from build_musl_probe import admit_musl_build, verify_compile_dependencies
from native_quiesce_evidence import validate_quiesce

OKSH_LISTS_MARKER = (b'OKSH_LISTS sequential=pass short-circuit=pass left-associative=pass '
    b'pipeline=pass parent-builtin=pass exit=pass syntax=pass repeat=pass')
NATIVE_CONTROL_MARKER = (b'NATIVE_CONTROL_PASS status=public root_restart=accepted '
    b'dependency_replacement=pass unknown=unchanged')
CONTROL_CREDENTIALS_MARKER = b'NATIVE_CONTROL_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 saved=1000'
CONTROL_DENIED_MARKER = b'NATIVE_CONTROL_DENIED uid=nonroot status=public mutation=unchanged'
CONTROL_TRANSPORT_MARKER = b'NATIVE_CONTROL_TRANSPORT malformed=pass partial=pass deadline=pass disconnected=pass'

CONFIGURATION = ("OK_SERVICE_MANIFEST 1\n"
    "service termination oneshot /bin/native-termination-probe -\n"
    "service setup oneshot /bin/native-service-child termination\n"
    "service provider notify /bin/native-service-child setup\n"
    "service dependent notify /bin/native-service-child provider\n"
    "service missing simple /bin/intentionally-missing -\n"
    "service console simple /bin/oksh -\n")
EVENT = re.compile(rb"NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event=([a-z-]+) "
    rb"service=([A-Za-z0-9_-]+) pid=([0-9]+) generation=([0-9]+) time_ms=([0-9]+) "
    rb"next_ms=([0-9]+) errno=([0-9]+) status=([0-9]+)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def validate_shell_lists(serial: bytes) -> None:
    """Require the distinct new fixture record before its final shell record."""
    lines = serial.replace(b'\r\n', b'\n').splitlines()
    found = [index for index, line in enumerate(lines) if b'OKSH_LISTS' in line]
    final = [index for index, line in enumerate(lines) if line == OKSH_MARKER]
    need(len(found) == 1 and lines[found[0]] == OKSH_LISTS_MARKER,
         'missing, malformed or duplicate shell list acceptance record')
    need(len(final) == 1 and found[0] < final[0], 'shell list record must precede final shell acceptance')


CREDENTIALS_MARKER = (b'NATIVE_CREDENTIALS_PASS native=1 reversible=pass high_ids=pass pair=pass '
    b'permanent=pass fork_exec=pass failed_exec=pass file_permissions=pass failure_atomic=pass')
NATIVE_DROP_MARKER = b'NATIVE_CONTROL_NATIVE_CREDENTIALS permanent=pass regain=denied'


def validate_credentials(serial: bytes) -> dict:
    """Require native instructions plus PID-bound configured service identity."""
    lines = serial.replace(b'\r\n', b'\n').splitlines()
    for failure in (b'NATIVE_CREDENTIALS_FAIL', b'NATIVE_CONTROL_FAIL', b'NATIVE_SERVICE_FAIL',
                    b'NATIVE_ADOPTION_FAIL', b'NATIVE_TERMINATION_FAIL', b'event=fatal-hold',
                    b'OK_TEST_FAIL', b'OK_NATIVE_FAIL', b'Kernel panic'):
        need(failure not in serial, 'native credentials lane failure: ' + failure.decode())
    final = [i for i, line in enumerate(lines) if b'NATIVE_CREDENTIALS_PASS' in line]
    need(len(final) == 1 and lines[final[0]] == CREDENTIALS_MARKER,
         'missing unique native credentials completion')
    exec_indices = []
    for expected in (b'NATIVE_CREDENTIALS_EXEC kind=permanent inherited=pass regain=denied',
                     b'NATIVE_CREDENTIALS_EXEC kind=saved reset=pass regain=denied'):
        found = [i for i, line in enumerate(lines) if expected.split(b' reset=')[0].split(b' inherited=')[0] in line]
        need(len(found) == 1 and lines[found[0]] == expected and found[0] < final[0],
             'missing ordered native credential exec completion')
        exec_indices.append(found[0])
    need(exec_indices[0] < exec_indices[1], 'native credential exec order differs')
    need(sum(b'NATIVE_CREDENTIALS_EXEC' in line for line in lines) == 2,
         'unknown native credential exec record')
    identity = [line for line in lines if b'NATIVE_SERVICE_IDENTITY' in line]
    need(len(identity) == 1, 'missing unique configured service identity')
    match = re.fullmatch(rb'NATIVE_SERVICE_IDENTITY service=identity pid=([0-9]+) '
                         rb'uid=1000 gid=1000 saved=1000 regain=denied', identity[0])
    need(match is not None and int(match[1]) > 1, 'malformed configured service identity')
    pid = int(match[1])
    events = [(i, EVENT.fullmatch(line[line.find(b'NATIVE_PID1 '):]))
              for i, line in enumerate(lines) if b'NATIVE_PID1 ' in line]
    for _, event in events:
        if event and event[2] == b'identity':
            need(int(event[3]) == pid and event[4] == b'1' and
                 event[1] in (b'launch', b'oneshot-ready', b'reap') and
                 event[7] == b'0' and event[8] == b'0', 'contradictory configured identity event')
    launches = [i for i, event in events if event and event[1] == b'launch' and
                event[2] == b'identity' and int(event[3]) == pid and event[4] == b'1' and
                event[7] == b'0' and event[8] == b'0']
    completions = [i for i, event in events if event and event[1] == b'oneshot-ready' and
                   event[2] == b'identity' and int(event[3]) == pid and event[4] == b'1' and
                   event[7] == b'0' and event[8] == b'0']
    reaps = [i for i, event in events if event and event[1] == b'reap' and
             event[2] == b'identity' and int(event[3]) == pid and event[4] == b'1']
    need(len(launches) == len(reaps) == len(completions) == 1 and
         max(launches[0], lines.index(identity[0])) < reaps[0] < completions[0] < final[0],
         'configured identity is not bound to successful PID1 launch/reap')
    native_drop = [i for i, line in enumerate(lines) if b'NATIVE_CONTROL_NATIVE_CREDENTIALS' in line]
    need(len(native_drop) == 1 and lines[native_drop[0]] == NATIVE_DROP_MARKER and
         completions[0] < native_drop[0] < exec_indices[0],
         'missing unique native control credential drop')
    return dict(native=True, linux_bridge=False, service_identity_pid=pid,
                reversible=True, high_ids=True, pair=True, permanent=True,
                fork_exec=True, failed_exec=True, file_permissions=True, failure_atomic=True)


def validate_control(serial: bytes) -> dict:
    """Bind the actual request's generation identities to PID 1 retirement/readiness."""
    serial = serial.replace(b'\r\n', b'\n')
    lines = serial.splitlines()
    final = [i for i, line in enumerate(lines) if b'NATIVE_CONTROL_PASS' in line]
    need(len(final) == 1 and lines[final[0]] == NATIVE_CONTROL_MARKER,
         'missing, malformed or duplicate native control completion')
    need(b'NATIVE_CONTROL_FAIL' not in serial, 'native control probe failed')
    need(b'event=control-disabled' not in serial and b'event=control-unavailable' not in serial,
         'native control transport unavailable')

    def exact(marker):
        prefix = marker.split(b' ', 1)[0]
        found = [i for i, line in enumerate(lines) if prefix in line]
        need(len(found) == 1 and lines[found[0]] == marker, 'missing, malformed or duplicate ' + prefix.decode())
        return found[0]

    credentials = exact(CONTROL_CREDENTIALS_MARKER)
    denied = exact(CONTROL_DENIED_MARKER)
    transport = exact(CONTROL_TRANSPORT_MARKER)
    need(credentials < denied < transport < final[0], 'control credentials/denial/transport order differs')
    deadline_rows = [(i, re.fullmatch(rb'NATIVE_CONTROL_DEADLINE elapsed_ms=([0-9]+) '
                     rb'activity_ms=([0-9]+) bound_ms=1200', line))
                     for i, line in enumerate(lines) if b'NATIVE_CONTROL_DEADLINE' in line]
    need(len(deadline_rows) == 1 and deadline_rows[0][1] is not None,
         'missing, malformed or duplicate fixed control deadline')
    deadline_index, deadline_row = deadline_rows[0]
    elapsed, activity = map(int, deadline_row.groups())
    need(denied < deadline_index < transport and 900 <= elapsed <= 1200 and 600 <= activity < 900,
         'control deadline did not reject activity-based extension')
    generation = re.compile(rb'NATIVE_CONTROL_GENERATION service=(provider|dependent) '
        rb'old_pid=([1-9][0-9]*) new_pid=([1-9][0-9]*) old_generation=2 new_generation=3')
    changes = {}
    for index, line in enumerate(lines):
        if b'NATIVE_CONTROL_GENERATION' not in line:
            continue
        match = generation.fullmatch(line)
        need(match is not None, 'malformed native control generation record')
        service, old_pid, new_pid = match.groups()
        service = service.decode()
        need(service not in changes and index < final[0], 'duplicate or late control generation')
        changes[service] = dict(old_pid=int(old_pid), new_pid=int(new_pid), record=index)
    need(set(changes) == {'provider', 'dependent'}, 'missing native control generation identities')
    need(len({pid for row in changes.values() for pid in (row['old_pid'], row['new_pid'])}) == 4,
         'native control reused a live child identity')

    def one(event, service, pid, epoch):
        found = []
        for index, line in enumerate(lines):
            at = line.find(b'NATIVE_PID1 ')
            match = EVENT.fullmatch(line[at:]) if at >= 0 else None
            if (match and match.group(1).decode() == event and match.group(2).decode() == service and
                int(match.group(3)) == pid and int(match.group(4)) == epoch):
                found.append((index, match))
        need(len(found) == 1, f'missing or duplicate control {service}/{epoch}/{event}')
        need(int(found[0][1].group(7)) == 0, 'control supervisor event has an error')
        return found[0]

    enabled, _ = one('control-enabled', 'none', 1, 0)
    accepted = f'OK_INIT_CONTROL 1 ACCEPTED service=provider pid={changes["provider"]["old_pid"]} generation=2'.encode()
    accepted_rows = [i for i, line in enumerate(lines) if b'OK_INIT_CONTROL 1 ACCEPTED' in line]
    need(len(accepted_rows) == 1 and lines[accepted_rows[0]] == accepted and
         transport < accepted_rows[0] < min(row['record'] for row in changes.values()),
         'control acceptance does not identify the requested old generation')
    order = {}
    for service, change in changes.items():
        old, new = change['old_pid'], change['new_pid']
        old_ready, _ = one('notify-ready', service, old, 2)
        term, _ = one('term', service, old, 2)
        reaped, raw = one('reap', service, old, 2)
        launched, _ = one('launch', service, new, 3)
        ready, _ = one('notify-ready', service, new, 3)
        need(int(raw.group(8)) == 128, 'controlled child did not retire by signal')
        need(enabled < old_ready < term < reaped < launched < ready < final[0],
             'control retirement/replacement causal order failed')
        marker = f'NATIVE_SERVICE_CHILD service={service} generation=3 pid={new} event=start'.encode()
        starts = [i for i, line in enumerate(lines) if line == marker]
        need(len(starts) == 1 and reaped < starts[0] < ready,
             'control replacement child differs from supervised generation')
        inherited = f'NATIVE_CONTROL_FDS service={service} generation=3 pid={new} inherited=0'.encode()
        fd_rows = [i for i, line in enumerate(lines)
                   if b'NATIVE_CONTROL_FDS' in line and f'service={service} generation=3 '.encode() in line]
        need(len(fd_rows) == 1 and lines[fd_rows[0]] == inherited and reaped < fd_rows[0] < ready,
             'replacement retained an unexpected control descriptor')
        order[service] = dict(term=term, reap=reaped, launch=launched, ready=ready)
    need(order['dependent']['term'] < order['dependent']['reap'] < order['provider']['term'] and
         order['provider']['ready'] < order['dependent']['launch'],
         'controlled restart violated dependency stop/start ordering')
    return dict(generations={name: {key: value for key, value in row.items() if key != 'record'}
                             for name, row in changes.items()}, status_public=True,
                restart_accepted=True, dependency_replacement=True,
                denied_uid=1000, fixed_deadline_ms=1200, observed_eof_ms=elapsed,
                activity_ms=activity, replacement_fds_closed=True)


def validate_serial(serial: bytes) -> dict:
    need(b"event=fatal-hold" not in serial, "native supervisor entered diagnostic hold")
    rows = []
    for line in serial.replace(b"\r", b"").splitlines():
        at = line.find(b"NATIVE_PID1 ")
        if at < 0:
            continue
        match = EVENT.fullmatch(line[at:])
        need(match is not None, "incomplete or wrong-profile native PID 1 event")
        event, service = (value.decode() for value in match.groups()[:2])
        pid, generation, now, next_ms, error, status = map(int, match.groups()[2:])
        rows.append(dict(event=event, service=service, pid=pid, generation=generation,
                         time_ms=now, next_ms=next_ms, errno=error, status=status))

    def one(event, service, generation):
        found = [(index, row) for index, row in enumerate(rows)
                 if row['event'] == event and row['service'] == service and row['generation'] == generation]
        need(len(found) == 1, f"missing or duplicate {service}/{generation}/{event}")
        return found[0]

    termination, _ = one('oneshot-ready', 'termination', 1)
    setup, _ = one('oneshot-ready', 'setup', 1)
    need(termination < setup, 'setup ran before native termination probe completed')
    up1, provider1 = one('launch', 'provider', 1)
    ready1, _ = one('notify-ready', 'provider', 1)
    down1, dependent1 = one('launch', 'dependent', 1)
    down_ready1, _ = one('notify-ready', 'dependent', 1)
    crash, crashed = one('reap', 'provider', 1)
    term, terminated = one('term', 'dependent', 1)
    retired, reaped = one('reap', 'dependent', 1)
    up2, provider2 = one('launch', 'provider', 2)
    ready2, _ = one('notify-ready', 'provider', 2)
    down2, dependent2 = one('launch', 'dependent', 2)
    down_ready2, _ = one('notify-ready', 'dependent', 2)
    need(setup < up1 < ready1 < down1 < down_ready1 < crash < term < retired,
         'startup/dependency retirement causal order failed')
    need(crash < up2 < ready2 < down2 < down_ready2 and retired < down2,
         'replacement launched before dependency readiness or predecessor retirement')
    need(crashed['pid'] == provider1['pid'] and crashed['status'] == 42 and
         terminated['pid'] == reaped['pid'] == dependent1['pid'] and reaped['status'] == 128,
         'crash or signal retirement does not identify its actual child')
    need(provider1['pid'] != provider2['pid'] and dependent1['pid'] != dependent2['pid'],
         'replacement reused a live child identity')
    for service, children in (('provider', (provider1, provider2)), ('dependent', (dependent1, dependent2))):
        for child in children:
            marker = (f"NATIVE_SERVICE_CHILD service={service} generation={child['generation']} "
                      f"pid={child['pid']} event=start").encode()
            need(serial.count(marker) == 1, 'native child identity differs from the supervised PID/generation')
    need(any(row['event'] == 'exec-failed' and row['service'] == 'missing' and row['errno'] == 2 for row in rows),
         'missing executable did not report ENOENT independently')
    need(any(row['event'] == 'simple-ready' and row['service'] == 'console' for row in rows),
         'independent console never became ready')
    need(b'NATIVE_SERVICE_GRAPH stable=2 dependency_restart=pass' in serial and
         b'NATIVE_SERVICE_PROVIDER crash=42' in serial and b'NATIVE_SERVICE_SETUP complete=1' in serial and
         b'NATIVE_TERMINATION_PASS term_wait=15 kill_wait=9 self_kill=9' in serial,
         'actual native child workflow markers missing')
    termination_rows = re.findall(rb'^NATIVE_TERMINATION signal=(15|9) child=([1-9][0-9]*) '
        rb'wait_signal=(15|9) retired=pass\r?$', serial, re.MULTILINE)
    need(len(termination_rows) == 2 and [row[0] for row in termination_rows] == [b'15', b'9'] and
         all(row[0] == row[2] for row in termination_rows) and termination_rows[0][1] != termination_rows[1][1],
         'native TERM/KILL wait status and retired-child probes missing or contradictory')
    return dict(events=len(rows), provider_pids=[provider1['pid'], provider2['pid']],
        dependent_pids=[dependent1['pid'], dependent2['pid']], oneshot=True,
        notify=True, dependency_retirement=True, restart=True, independent_exec_failure=True,
        native_termination_wait_signals=[15, 9], native_self_kill=True)


ADOPTION_PARENT = re.compile(rb'^NATIVE_ADOPTION_PARENT pid=([1-9][0-9]*) live=([1-9][0-9]*) '
                             rb'zombie=([1-9][0-9]*)\r?$', re.MULTILINE)
ADOPTION_CHILD = re.compile(rb'^NATIVE_ADOPTION_CHILD pid=([1-9][0-9]*) old_parent=([1-9][0-9]*) '
                            rb'new_parent=1 exit=23\r?$', re.MULTILINE)


def adoption_complete(serial: bytes) -> bool:
    parents = list(ADOPTION_PARENT.finditer(serial))
    if not parents or not ADOPTION_CHILD.search(serial):
        return False
    _, live, zombie = parents[0].groups()
    return all(re.search(rb'event=other-child service=none pid=' + pid + rb' generation=0 ', serial)
               for pid in (live, zombie))


def validate_adoption(serial: bytes) -> dict:
    need(b'NATIVE_ADOPTION_FAIL' not in serial, 'native descendant failed to observe adoption')
    for line in serial.replace(b'\r', b'').splitlines():
        if b'NATIVE_ADOPTION_' in line:
            need(ADOPTION_PARENT.fullmatch(line) or ADOPTION_CHILD.fullmatch(line),
                 'malformed native adoption identity')
    parents, children = list(ADOPTION_PARENT.finditer(serial)), list(ADOPTION_CHILD.finditer(serial))
    need(len(parents) == len(children) == 1, 'missing or duplicate native adoption identities')
    parent, live, zombie = map(int, parents[0].groups())
    observed_child, observed_parent = map(int, children[0].groups())
    need(len({1, parent, live, zombie}) == 4 and (observed_child, observed_parent) == (live, parent),
         'native adoption child/parent identities differ')
    rows, offsets = [], []
    cursor = 0
    for raw in serial.splitlines(keepends=True):
        offset = cursor
        cursor += len(raw)
        line = raw.rstrip(b'\r\n')
        at = line.find(b'NATIVE_PID1 ')
        if at < 0:
            continue
        match = EVENT.fullmatch(line[at:])
        need(match is not None, 'malformed adoption supervisor event')
        rows.append(match)
        offsets.append(offset + at)
    starts = [row for row in rows if row.group(1) == b'launch' and row.group(2) == b'adoption']
    ready = [row for row in rows if row.group(1) == b'oneshot-ready' and row.group(2) == b'adoption']
    reaped = [row for row in rows if row.group(1) == b'reap' and row.group(2) == b'adoption']
    need(len(starts) == len(ready) == len(reaped) == 1 and all(int(row.group(3)) == parent and
         row.group(4) == b'1' and row.group(7) == row.group(8) == b'0'
         for row in starts + ready + reaped), 'adoption parent differs from its supervised generation')
    parent_exit = rows.index(reaped[0])
    need(rows.index(starts[0]) < parent_exit < rows.index(ready[0]), 'adoption parent lifecycle order differs')
    parent_marker, child_marker = parents[0].start(), children[0].start()
    need(offsets[rows.index(starts[0])] < parent_marker < offsets[parent_exit] and
         parent_marker < child_marker, 'adoption identity precedes its owner or follows its reap')
    exits = {}
    for index, row in enumerate(rows):
        if row.group(1) == b'other-child' and int(row.group(3)) in (live, zombie):
            pid = int(row.group(3))
            need(index > parent_exit and pid not in exits and row.group(2) == b'none' and row.group(4) == b'0' and
                 row.group(7) == b'0', 'duplicate or inconsistent adopted-child reap')
            if pid == live:
                need(child_marker < offsets[index], 'live identity follows its own reap')
            exits[pid] = int(row.group(8))
    # Other-child events preserve the raw wait status, unlike service reap events.
    need(exits == {live: 23 << 8, zombie: 31 << 8}, 'PID 1 did not reap both adopted native descendants')
    return dict(parent=parent, live_child=live, completed_child=zombie, observed_parent=1,
                live_wait_exit=23, completed_wait_exit=31,
                raw_wait_status={str(pid): value for pid, value in exits.items()}, pid1_reaped=True)


def run(args):
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1',
         'use PYTHONDONTWRITEBYTECODE=1 python3 -B')
    out = args.output.resolve()
    need(not out.exists() and not ROOT.is_relative_to(out) and not out.is_relative_to(ROOT),
         'output must be a fresh directory outside OS source')
    sdk_input = args.kernel_sdk.resolve()
    need(sha(sdk_input / 'manifest.json') == args.sdk_manifest_sha256, 'wrong SDK manifest input')
    compiler = args.compiler.resolve()
    manifest = validate_sdk(sdk_input, args.arch, args.mode, compiler)
    out.mkdir(parents=True)
    record = dict(schema=1, status='preparing', architecture=args.arch, mode=args.mode,
        sdk_abi=manifest['abi_version'], sdk_manifest_sha256=args.sdk_manifest_sha256,
        sdk_only=True, kernel_source_compiled=False, guest_executed=False,
        physical=False, smp=False, synchronized_guest_shutdown=False,
        orphan_adoption=False, shell_acceptance=False, shell_lists=False, native_control=False, native_credentials=False,
        native_quiesce=False,
        full_M7=False, commands=[],
        layer='native-user-instructions-and-syscalls-qemu', runner_sha256=sha(Path(__file__)))
    serial = bytearray()
    process = None

    def save():
        (out / 'serial.log').write_bytes(serial)
        temporary = out / 'result.json.tmp'
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        temporary.replace(out / 'result.json')

    def call(label, argv, cwd):
        argv = list(map(str, argv))
        row = dict(label=label, argv=argv)
        record['commands'].append(row)
        save()
        with (out / (label + '.log')).open('xb') as stream:
            result = subprocess.run(argv, cwd=cwd, env=environment, stdout=stream, stderr=subprocess.STDOUT)
        row.update(returncode=result.returncode, log_sha256=sha(out / (label + '.log')))
        save()
        need(result.returncode == 0, label + ' failed; retained log identifies the original failure')

    environment = dict(os.environ, XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(out / 'xmake-global'),
                       XMAKE_TMPDIR=str(out / 'xmake-temp'),
                       PYTHONDONTWRITEBYTECODE='1')
    for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        environment.pop(key, None)
    save()
    try:
        consumer = out / 'ObfuscationOS'
        files = source_files(ROOT)
        files['config/services.conf'] = sha(ROOT / 'config/services.conf')
        record['original_source_files'] = files
        for name, expected in files.items():
            destination = consumer / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
            need(sha(destination) == expected, 'source changed during snapshot: ' + name)
        sdk = out / 'sdk'
        for name, expected in {**manifest['files'], 'manifest.json': args.sdk_manifest_sha256}.items():
            destination = sdk / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sdk_input / name, destination)
            need(sha(destination) == expected, 'SDK changed during snapshot: ' + name)
        validate_sdk(sdk, args.arch, args.mode, compiler)
        # Explicit test-only target and config stay in the retained consumer.
        with (consumer / 'xmake.lua').open('a') as stream:
            stream.write('\nincludes("tests/native/native_service_graph_fixture.lua")\n')
            if args.native_control:
                stream.write('includes("tests/native/native_control_fixture.lua")\n')
            if args.native_credentials:
                stream.write('includes("tests/native/native_credentials_fixture.lua")\n')
            if args.native_quiesce:
                stream.write('includes("tests/native/native_quiesce_fixture.lua")\n')
        configuration = CONFIGURATION
        if args.native_adoption:
            configuration = configuration.replace('service termination oneshot /bin/native-termination-probe -\n',
                'service adoption oneshot /bin/native-init-adoption-probe -\n'
                'service termination oneshot /bin/native-termination-probe adoption\n')
        if args.native_credentials:
            configuration = 'OK_SERVICE_MANIFEST 2\n' + ''.join(
                line + ' 0 0\n' for line in configuration.splitlines()[1:])
            configuration += 'service identity oneshot /bin/native-credentials-probe setup 1000 1000\n'
        (consumer / 'config/services.conf').write_text(configuration)
        record['fixture_configuration_sha256'] = sha(consumer / 'config/services.conf')
        record['consumer_xmake_sha256'] = sha(consumer / 'xmake.lua')
        configuration_options = ['--native_init_control=y'] if args.native_control else []
        call('configure', [args.xmake, 'f', '-y', '-a', args.arch, '-m', args.mode,
            '--kernel_sdk=' + str(sdk), '--systoolchain_dir=' + str(compiler.parent.parent),
            *configuration_options], consumer)
        targets = ['apps', 'native-service-graph-child', 'native-termination-probe']
        if args.native_adoption:
            targets.append('native-init-adoption-probe')
        if args.shell_acceptance:
            targets.append('oksh-native-acceptance')
        if args.native_control:
            targets.append('native-init-control-probe')
        if args.native_credentials:
            targets.extend(('native-credentials-probe', 'native-control-drop'))
        if args.native_quiesce:
            targets.append('native-quiesce-probe')
        targets.append('distro_image')
        for target in targets:
            call('build-' + target, [args.xmake, '-y', '-b', target], consumer)
        if args.native_control and not args.native_credentials:
            original_musl = args.control_musl_build.resolve()
            need(sha(original_musl / 'manifest.json') == args.control_musl_manifest_sha256,
                 'wrong explicit control helper musl manifest')
            musl_manifest = admit_musl_build(original_musl, args.arch)
            need(musl_manifest['compiler']['triple'] == manifest['triple'] and
                 musl_manifest['compiler']['version'] == manifest['compiler']['version'],
                 'control helper musl compiler differs from SDK')
            musl = out / 'control-musl'
            musl_inputs = {name: digest for name, digest in musl_manifest['files'].items()
                           if name.startswith('sysroot/')}
            musl_inputs['manifest.json'] = args.control_musl_manifest_sha256
            for name, expected in musl_inputs.items():
                destination = musl / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original_musl / name, destination)
                need(sha(destination) == expected, 'control musl input changed: ' + name)
            admit_musl_build(musl, args.arch)
            helper = out / 'control-helper'
            call('control-helper-build', [sys.executable, '-B', consumer / 'tools/build_musl_probe.py',
                 '--arch', args.arch, '--musl-build', musl, '--toolchain', compiler.parent.parent,
                 '--source', consumer / 'tests/musl/native_control_drop.c',
                 '--linker-script', consumer / 'tests/musl/bootstrap.ld',
                 '--capture-compile-dependencies', '--out', helper], consumer)
            helper_manifest = json.loads((helper / 'manifest.json').read_text())
            need(helper_manifest['status'] == 'built-not-executed' and not helper_manifest['executed'] and
                 helper_manifest['source_manifest_sha256'] == args.control_musl_manifest_sha256 and
                 helper_manifest['probe_sha256'] == sha(consumer / 'tests/musl/native_control_drop.c') and
                 helper_manifest['elf_sha256'] == sha(helper / 'bootstrap.elf'),
                 'control helper does not match pinned build')
            verify_compile_dependencies(helper_manifest['compile_dependencies'])
            record['control_helper'] = dict(personality='linux-static-musl',
                source_manifest_sha256=args.control_musl_manifest_sha256,
                manifest_sha256=sha(helper / 'manifest.json'), elf_sha256=helper_manifest['elf_sha256'],
                source_mode=musl_manifest['mode'])
        build = consumer / 'build' / args.arch / args.mode
        root = out / 'rootfs'
        call('stage', [sys.executable, '-B', consumer / 'tools/stage_rootfs.py',
            '--apps-dir', build / 'apps', '--out', root, '--arch', args.arch], consumer)
        shutil.copy2(build / 'fixtures/native-service-child.elf', root / 'bin/native-service-child')
        (root / 'bin/native-service-child').chmod(0o755)
        shutil.copy2(build / 'fixtures/native-termination-probe.elf', root / 'bin/native-termination-probe')
        (root / 'bin/native-termination-probe').chmod(0o755)
        if args.native_adoption:
            shutil.copy2(build / 'fixtures/native-init-adoption-probe.elf', root / 'bin/native-init-adoption-probe')
            (root / 'bin/native-init-adoption-probe').chmod(0o755)
        if args.shell_acceptance:
            shutil.copy2(build / 'fixtures/oksh-acceptance.elf', root / 'bin/oksh-acceptance')
            (root / 'bin/oksh-acceptance').chmod(0o755)
            record['shell_fixture_sha256'] = sha(root / 'bin/oksh-acceptance')
        if args.native_control:
            shutil.copy2(build / 'fixtures/native-init-control-probe.elf', root / 'bin/native-init-control-probe')
            (root / 'bin/native-init-control-probe').chmod(0o755)
            record['control_fixture_sha256'] = sha(root / 'bin/native-init-control-probe')
            record['control_cli_sha256'] = sha(root / 'bin/service-ctl')
            if args.native_credentials:
                shutil.copy2(build / 'fixtures/native-control-drop.elf', root / 'bin/native-control-drop')
                record['control_helper'] = dict(personality='native',
                    elf_sha256=sha(root / 'bin/native-control-drop'),
                    source_sha256=sha(consumer / 'tests/native/native_control_drop.c'))
            else:
                shutil.copy2(helper / 'bootstrap.elf', root / 'bin/native-control-drop')
            (root / 'bin/native-control-drop').chmod(0o755)
        if args.native_credentials:
            shutil.copy2(build / 'fixtures/native-credentials-probe.elf', root / 'bin/native-credentials-probe')
            (root / 'bin/native-credentials-probe').chmod(0o755)
            record['credentials_fixture_sha256'] = sha(root / 'bin/native-credentials-probe')
        if args.native_quiesce:
            shutil.copy2(build / 'fixtures/native-quiesce-probe.elf', root / 'bin/native-quiesce-probe')
            (root / 'bin/native-quiesce-probe').chmod(0o755)
            record['quiesce_fixture_sha256'] = sha(root / 'bin/native-quiesce-probe')
        disk = out / 'rootfs.ext4.img'
        call('rootfs', [sys.executable, '-B', consumer / 'tools/mkext4.py', '--root', root,
                       '--out', disk, '--size', '32M'], consumer)
        image = build / 'distro' / ('kernel.bin' if args.arch in ('i386', 'x86_64') else 'kernel.elf')
        record.update(image_sha256=sha(image), initial_disk_sha256=sha(disk),
                      init_sha256=sha(root / 'init'), child_sha256=sha(root / 'bin/native-service-child'),
                      qemu_sha256=sha(args.qemu.resolve()), compiler_sha256=sha(compiler),
                      xmake_sha256=sha(args.xmake.resolve()), status='running-guest')
        command = command_for(args.qemu.resolve(), args.arch, image, disk, 'none', native_profile=True)
        record['qemu_argv'] = command
        save()
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=environment)
        record['guest_executed'] = True

        def receive(predicate):
            deadline = time.monotonic() + args.timeout
            while not predicate():
                need(time.monotonic() < deadline, 'timeout waiting for native graph/console')
                ready, _, _ = select.select([process.stdout], [], [], .1)
                if not ready:
                    need(process.poll() is None, 'QEMU exited before acceptance')
                    continue
                chunk = os.read(process.stdout.fileno(), 16384)
                need(chunk, 'QEMU output ended')
                serial.extend(chunk)
                need(len(serial) < 4 * 1024 * 1024, 'serial capacity exceeded')
                for marker in (b'OK_TEST_FAIL', b'Kernel panic', b'event=fatal-hold', b'acceptance=FAIL',
                               b'NATIVE_TERMINATION_FAIL', b'NATIVE_ADOPTION_FAIL', b'OKSH_NATIVE_FAIL',
                               b'NATIVE_CONTROL_FAIL', b'NATIVE_CREDENTIALS_FAIL', b'NATIVE_QUIESCE_FAIL'):
                    need(marker not in serial, 'guest failure: ' + marker.decode())
                save()

        receive(lambda: b'NATIVE_SERVICE_GRAPH stable=2 dependency_restart=pass' in serial and
            re.search(rb'event=notify-ready service=dependent pid=[0-9]+ generation=2 ', serial) and b'oksh> ' in serial)
        record['execution'] = validate_serial(bytes(serial))
        if args.native_adoption:
            receive(lambda: adoption_complete(bytes(serial)))
            record['adoption'] = validate_adoption(bytes(serial))
            record['orphan_adoption'] = True
        if args.native_credentials:
            receive(lambda: re.search(rb'event=oneshot-ready service=identity pid=[0-9]+ generation=1 ', serial))
        if args.native_control:
            start = len(serial)
            process.stdin.write(b'native-init-control-probe\n'); process.stdin.flush()
            receive(lambda: NATIVE_CONTROL_MARKER in serial[start:] and
                serial.rfind(b'oksh> ') > serial.find(NATIVE_CONTROL_MARKER, start))
            record['control'] = validate_control(bytes(serial))
            record['native_control'] = True
        if args.native_credentials:
            start = len(serial)
            process.stdin.write(b'native-credentials-probe\n'); process.stdin.flush()
            receive(lambda: CREDENTIALS_MARKER in serial[start:] and
                serial.rfind(b'oksh> ') > serial.find(CREDENTIALS_MARKER, start))
            record['credentials'] = validate_credentials(bytes(serial))
            record['native_credentials'] = True
        start = len(serial)
        process.stdin.write(b'hello\n'); process.stdin.flush()
        receive(lambda: b'hello from ObfuscationOS userland' in serial[start:] and b'oksh> ' in serial[start:])
        if args.shell_acceptance:
            start = len(serial)
            process.stdin.write(b'oksh-acceptance\n'); process.stdin.flush()
            receive(lambda: OKSH_MARKER in serial[start:] and
                serial.rfind(b'oksh> ') > serial.find(OKSH_MARKER, start))
            span = bytes(serial[start:]).replace(b'\r\n', b'\n')
            need(len(re.findall(rb'^' + re.escape(OKSH_MARKER) + rb'$', span, re.MULTILINE)) == 1,
                 'missing or duplicate complete shell acceptance record')
            if args.shell_lists:
                validate_shell_lists(span)
                record['shell_lists'] = True
            start = len(serial)
            process.stdin.write(b'echo OKSH_AFTER_ACCEPTANCE | cat | cat\n'); process.stdin.flush()
            receive(lambda: b'\nOKSH_AFTER_ACCEPTANCE\n' in
                bytes(serial[start:]).replace(b'\r\n', b'\n') and b'oksh> ' in serial[start:])
            record['shell_acceptance'] = True
        start = len(serial)
        process.stdin.write(b'sync\n'); process.stdin.flush()
        receive(lambda: b'oksh> ' in serial[start:])
        record['console_command_executed'] = True
        if args.native_quiesce:
            start = len(serial)
            process.stdin.write(b'native-quiesce-probe\n'); process.stdin.flush()
            receive(lambda: re.search(rb'event=quiesced service=none pid=1 generation=0 ', serial[start:]))
            # Keep observing the actor after completion; a delayed launch or
            # failure must not be hidden by immediate host retirement.
            observation_until = time.monotonic() + 1
            receive(lambda: time.monotonic() >= observation_until)
            record['quiesce'] = validate_quiesce(bytes(serial))
            record['native_quiesce'] = True
        record.update(status='passed-bounded-native-service-graph', serial_sha256=hashlib.sha256(serial).hexdigest())
    except Exception as error:
        record.update(status='failed', error=str(error))
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=3)
            process.stdin.close(); process.stdout.close()
            record['qemu_returncode'] = process.returncode
            record['host_retired_guest'] = True
        save()
    print('NATIVE_SERVICE_GRAPH_PASS', args.arch, args.mode, out / 'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--xmake', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--native-adoption', action='store_true')
    parser.add_argument('--shell-acceptance', action='store_true')
    parser.add_argument('--shell-lists', action='store_true')
    parser.add_argument('--native-control', action='store_true')
    parser.add_argument('--native-credentials', action='store_true')
    parser.add_argument('--native-quiesce', action='store_true')
    parser.add_argument('--control-musl-build', type=Path)
    parser.add_argument('--control-musl-manifest-sha256')
    args = parser.parse_args()
    if args.shell_lists and not args.shell_acceptance:
        parser.error('--shell-lists requires --shell-acceptance')
    if args.native_credentials and not args.native_control:
        parser.error('--native-credentials requires --native-control')
    if args.native_quiesce and not (args.native_control and args.native_credentials):
        parser.error('--native-quiesce requires --native-control and --native-credentials')
    if args.native_credentials and (args.control_musl_build or args.control_musl_manifest_sha256):
        parser.error('--native-credentials uses the native helper; do not supply musl inputs')
    if args.native_control and not args.native_credentials and not (args.control_musl_build and args.control_musl_manifest_sha256):
        parser.error('--native-control requires an explicit pinned control musl build')
    if not args.native_control and (args.control_musl_build or args.control_musl_manifest_sha256):
        parser.error('control musl inputs require --native-control')
    run(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
