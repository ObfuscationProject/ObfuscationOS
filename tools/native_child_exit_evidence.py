"""SDK-only18-case child-exit integration, preserving exact resource accounting."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command
from native_pipe_io_events import native_events as pipe_events
from native_futex_events import native_events as futex_events, final_snapshots
from native_poll_events import native_events as poll_events
from native_child_events import native_events as child_events, boot_baseline, normalize_transcript, WAIT
from native_child_exit_guest import probe_spec, guest_events, failure_line as guest_failure, incomplete_failure_line
from native_child_exit_events import native_events as exit_events, wait_ledger_view, explicit_reap_batches
from native_child_exit_join import validate_join, validate_native_pipeline


def failure_line(serial):
    return guest_failure(serial) or general_failure(serial)


def incidental(span, arch, baseline):
    lifecycle = exit_events(span, arch)
    waits = child_events(wait_ledger_view(span, lifecycle), baseline=baseline)
    return (pipe_events(span, arch) + futex_events(span, arch, allow_signal=False) +
            poll_events(span, arch, allow_signal=False) + waits + lifecycle)


def _serializable(value):
    if isinstance(value, list): return [_serializable(v) for v in value]
    if isinstance(value, dict): return {k: _serializable(v) for k, v in value.items() if k not in ('line', 'lines')}
    return value


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin,
                       arch, kind='child-exit-policy'):
    marker, prefix, command, leases = probe_spec(arch, kind)
    serial, bounds = normalize_transcript(serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = bounds
    if error := failure_line(serial): raise ValueError(error)
    tail = serial.rsplit(b'oksh> ', 1)
    if len(tail) != 2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n', tail[1])):
        raise ValueError('unexpected bytes after final child-exit prompt')
    boot = serial[:baseline_begin]
    spans = (serial[baseline_begin:probe_begin], serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end], serial[native_begin:])
    boot_exits = exit_events(boot, arch)
    child_baseline = boot_baseline(wait_ledger_view(boot, boot_exits), required=True)
    native_parent = next(iter(child_baseline.values()))['selector']
    for start, expected in ((b'OK_SYSTEM_GUI boot=', b'OK_SYSTEM_GUI boot=complete'),
                            (b'OK_STORAGE ', b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines() if start in line]
        if rows != [expected]: raise ValueError('missing unique complete child-exit distribution boot')
    pipe_events(boot, arch)
    futex_events(boot, arch, allow_signal=False)
    poll_events(boot, arch, allow_signal=False)
    observations = []
    source = b'linker' if arch in ('loongarch64', 'mips', 'mips64') else b'firmware'
    for index, span in enumerate(spans):
        events = incidental(span, arch, child_baseline)
        lines = [line for line in span.splitlines() if line]
        images = [i for i, line in enumerate(lines) if IMAGE.fullmatch(line)]
        if index in (0, 3):
            if images or any(b'CHILD_EXIT_' in line for line in lines):
                raise ValueError('Linux image or child-exit guest marker in native pipeline')
            if lines.count(b'hello from ObfuscationOS userland') != 1:
                raise ValueError('missing unique native pipeline success')
            validate_native_pipeline(span, arch, native_parent)
            validate_command(span, b'hello | cat', b'hello from ObfuscationOS userland', tuple(e['line'] for e in events))
            continue
        if len(images) != 2 or lines.count(marker) != 1 or not images[0] < lines.index(marker):
            raise ValueError('child-exit probe lacks exact initial and replacement images')
        if any(IMAGE.fullmatch(lines[i])[1] != source for i in images):
            raise ValueError('wrong child-exit image memory source')
        if any(line != command and not WAIT.fullmatch(line) for line in lines[:images[0]]):
            raise ValueError('unexpected output before child-exit image admission')
        guest = guest_events(span, arch)
        case17 = guest['cases'][17]
        fail = next(row['line'] for row in case17['events'] if row.get('op') == 'EXEC_FAILED')
        check = next(row['line'] for row in case17['events'] if row.get('op') == 'EXEC_CHECK')
        if not lines.index(fail) < images[1] < lines.index(check):
            raise ValueError('child-exit replacement observations lack intervening ELF admission')
        joined = validate_join(span, arch, marker, native_parent)
        validate_command(span, command, marker, tuple(e['line'] for e in events) + tuple(guest['lines']))
        observations.append(dict(guest_cases=_serializable(guest['cases']), **joined))
    if any(b'CHILD_EXIT_' in line for line in boot.splitlines()):
        raise ValueError('child-exit guest marker outside dedicated commands')
    # Cross-command PID duplication is not hidden by a per-span ledger reset.
    exit_events(serial, arch)
    frames, stacks = decode_frames(serial, arch), decode_stacks(serial)
    if any(left == right for left, right in zip(frames, frames[1:])):
        raise ValueError('duplicate child-exit frame accounting snapshot')
    if any(frames[0][k] for k in ('used', 'allocations', 'releases')) or any(stacks[0].values()):
        raise ValueError('missing empty child-exit boot accounting')
    frame_ends = [decode_frames(span, arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0]
    live = stack_ends[0]['leased']
    if not live or any(row['leased'] != live for row in stack_ends):
        raise ValueError('child-exit command did not return to live shell stack baseline')
    previous_frame, previous_stack = decode_frames(boot, arch)[-1], decode_stacks(boot)[-1]
    commands = []
    for index, span in enumerate(spans):
        final_snapshots(span)
        success = prefix if index in (1, 2) else b'hello from ObfuscationOS userland'
        if any(span.rfind(p) <= span.rfind(success) for p in (b'OK_NATIVE_FRAMES', b'OK_ENTRY_STACKS')):
            raise ValueError('child-exit resource retirement precedes user completion')
        frame, stack = frame_ends[index], stack_ends[index]
        if (frame['objects'] != base['objects'] or base['objects'] != 1 or frame['user'] != base['user'] or
                frame['allocations'] <= previous_frame['allocations'] or frame['releases'] <= previous_frame['releases']):
            raise ValueError('child-exit pages and persistent owner did not retire exactly')
        delta = {key: stack[key] - previous_stack[key] for key in COUNTERS}
        minimum = leases if index in (1, 2) else 1
        if delta['reservations'] < minimum or delta['releases'] < minimum or delta['syscalls'] <= 0 or delta['activations'] <= 0 or delta['faults'] or delta['rejected']:
            raise ValueError('child-exit execution lacks fresh entries or contains a captured fault')
        commands.append(delta)
        previous_frame, previous_stack = frame, stack
    return dict(runs=2, kind=kind, architecture=arch, sdk_abi=31, minimum_leases_per_run=leases,
                image_publications_per_run=2, scope='actual-user-private-child-exit-policy',
                observations=observations, automatic_child_notification=True, deferred_autoreap=True,
                continuous_inherited_wait_owner=True, parent_thread_lineage=False,
                leader_first_group_cause=False, cpu_time_accounting=False,
                production=False, physical=False, smp=False,
                child_baseline={str(k): {n: v for n, v in r.items() if n != 'line'} for k, r in child_baseline.items()},
                baseline=base, final=frame_ends[-1], records=len(frames),
                entry_stacks=dict(baseline=stack_ends[0], first=stack_ends[1], second=stack_ends[2],
                                  final=stack_ends[3], commands=commands, records=len(stacks)))
