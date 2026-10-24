"""SDK-only natural fork exhaustion, child policy and exact reclaim qualification."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command
from native_pipe_io_events import native_events as pipe_events
from native_futex_events import native_events as futex_events, final_snapshots
from native_poll_events import native_events as poll_events
from native_signal_wait_events import native_events as signal_wait_events
from native_child_events import native_events as child_events, boot_baseline, normalize_transcript, WAIT
from native_child_exit_events import native_events as exit_events, wait_ledger_view
from native_child_exit_join import validate_native_pipeline, join_native_waits
from native_child_exit_pressure_guest import (probe_spec, guest_events,
    failure_line as guest_failure, incomplete_failure_line)
from native_child_exit_pressure_join import validate_joins


def failure_line(serial):
    return guest_failure(serial) or general_failure(serial)


def incidental(span, arch, baseline, child_wait=False):
    lifecycle = exit_events(span, arch)
    waits = child_events(wait_ledger_view(span, lifecycle), baseline=baseline)
    signals = signal_wait_events(span, arch, allow_child=child_wait)
    return (pipe_events(span, arch) + futex_events(span, arch, allow_signal=False) +
            poll_events(span, arch, allow_signal=False) + waits + signals + lifecycle)


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin,
                       arch, kind='child-exit-pressure'):
    marker, prefix, command, _ = probe_spec(arch, kind)
    serial, bounds = normalize_transcript(serial, (baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = bounds
    if error := failure_line(serial): raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail) != 2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final child-pressure prompt')
    boot = serial[:baseline_begin]
    spans = (serial[baseline_begin:probe_begin],serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end],serial[native_begin:])
    boot_exits = exit_events(boot, arch)
    child_baseline = boot_baseline(wait_ledger_view(boot, boot_exits), required=True)
    native_parent = next(iter(child_baseline.values()))['selector']
    for start, expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
            (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        if [line for line in boot.splitlines() if start in line] != [expected]:
            raise ValueError('missing unique child-pressure distribution boot')
    pipe_events(boot, arch)
    futex_events(boot, arch, allow_signal=False)
    poll_events(boot, arch, allow_signal=False)
    if signal_wait_events(boot, arch): raise ValueError('signal wait outside pressure probe')
    observations = []
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    for index, span in enumerate(spans):
        events = incidental(span, arch, child_baseline, child_wait=False)
        lines = [line for line in span.splitlines() if line]
        images = [i for i,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if index in (0,3):
            if images or any(b'CHILD_PRESSURE_' in line for line in lines) or signal_wait_events(span, arch):
                raise ValueError('pressure image or wait outside dedicated probe')
            if lines.count(b'hello from ObfuscationOS userland') != 1:
                raise ValueError('missing unique pressure native pipeline')
            validate_native_pipeline(span, arch, native_parent, require_two_pairs=False)
            validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland',tuple(e['line'] for e in events))
            continue
        if len(images) != 1 or lines.count(marker) != 1 or not images[0] < lines.index(marker):
            raise ValueError('pressure probe lacks unique image and completion')
        if IMAGE.fullmatch(lines[images[0]])[1] != source:
            raise ValueError('wrong pressure image memory source')
        if any(line != command and not WAIT.fullmatch(line) for line in lines[:images[0]]):
            raise ValueError('unexpected output before pressure image admission')
        guest = guest_events(span,arch)
        lifecycle = exit_events(span,arch)
        exits = [r for r in lifecycle if r['tag']=='OK_NATIVE_CHILD_EXIT']
        signals = signal_wait_events(span,arch)
        polls = poll_events(span,arch,allow_signal=False)
        futexes = futex_events(span,arch,allow_signal=False)
        if signals or polls or futexes:
            raise ValueError('pressure guest unexpectedly entered signal/poll/futex wait')
        reads = pipe_events(span,arch)
        joined = validate_joins(guest,lifecycle,reads,native_parent)
        main = guest['pid']
        final = next(row for row in exits if row['child']==main)
        waits = join_native_waits(span,lifecycle)
        if len(waits) != 2: raise ValueError('pressure campaign lacks exact shell wait pair')
        arm, complete = waits
        if (any(r[k] != v for r in waits for k,v in dict(pid=native_parent,tid=native_parent,selector=main,format='status').items()) or
                arm['outcome'] != 'arm' or arm['result'] != -11 or arm['live'] != 2 or
                complete['outcome'] != 'complete' or complete['result'] != main or complete['live'] != 1 or
                not 0 < arm['request'] == arm['wait'] == complete['request'] == complete['wait'] or
                not 0 < arm['output'] == complete['output'] or
                not arm['position'] < guest['begin']['position'] < final['position'] < complete['position']):
            raise ValueError('pressure shell wait differs from exact main lifetime')
        validate_command(span,command,marker,tuple(e['line'] for e in events)+tuple(guest['lines']))
        observations.append(joined)
    if any(b'CHILD_PRESSURE_' in line for line in boot.splitlines()):
        raise ValueError('pressure marker outside dedicated commands')
    exit_events(serial,arch)
    frames, stacks = decode_frames(serial,arch), decode_stacks(serial)
    if any(left==right for left,right in zip(frames,frames[1:])):
        raise ValueError('duplicate child-pressure frame snapshot')
    if any(frames[0][k] for k in ('used','allocations','releases')) or any(stacks[0].values()):
        raise ValueError('missing empty child-pressure boot accounting')
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base,live = frame_ends[0],stack_ends[0]['leased']
    if not live or any(r['leased']!=live for r in stack_ends):
        raise ValueError('pressure command did not return to live shell stack baseline')
    previous_frame,previous_stack = decode_frames(boot,arch)[-1],decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        if any(span.rfind(p)<=span.rfind(success) for p in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS')):
            raise ValueError('pressure resource retirement precedes user completion')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or
                frame['allocations']<=previous_frame['allocations'] or frame['releases']<=previous_frame['releases']):
            raise ValueError('pressure pages and persistent owner did not retire exactly')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=observations[index-1]['minimum_entry_leases'] if index in (1,2) else 1
        if (delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or
                delta['activations']<=0 or delta['faults'] or delta['rejected']):
            raise ValueError('pressure command lacks fresh owned entries or has rejected/faulting capture')
        commands.append(delta)
        previous_frame,previous_stack=frame,stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=[row['minimum_entry_leases'] for row in observations],
                image_publications_per_run=1,scope='actual-user-private-child-exit-pressure',
                observations=observations,natural_fork_exhaustion=True,failed_forks_per_run=9,
                actual_blocked_pressure_reads=True,complete_automatic_reap_accounting=True,
                global_process_exhaustion=False,vm_exhaustion=False,stack_exhaustion=False,
                native_pipeline_immediate_ready_allowed=True,all_native_waits_traced=False,
                production=False,physical=False,smp=False,cpu_time_accounting=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frames),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stacks)))
