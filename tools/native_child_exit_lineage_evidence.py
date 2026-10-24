"""SDK-only child lineage, leader cause and actual wait-window qualification."""
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
from native_child_exit_events import native_events as exit_events, wait_ledger_view, explicit_reap_batches
from native_child_exit_join import validate_native_pipeline, join_native_waits
from native_child_exit_lineage_guest import (probe_spec, guest_events, validate_joins,
    failure_line as guest_failure, incomplete_failure_line)


def failure_line(serial):
    return guest_failure(serial) or general_failure(serial)


def incidental(span, arch, baseline, child_wait=False):
    lifecycle = exit_events(span, arch)
    waits = child_events(wait_ledger_view(span, lifecycle), baseline=baseline)
    signals = signal_wait_events(span, arch, allow_child=child_wait)
    return (pipe_events(span, arch) + futex_events(span, arch, allow_signal=False) +
            poll_events(span, arch, allow_signal=False) + waits + signals + lifecycle)


def serializable(value):
    if isinstance(value, list): return [serializable(v) for v in value]
    if isinstance(value, dict): return {k: serializable(v) for k,v in value.items() if k not in ('line','lines')}
    return value


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin,
                       arch, kind='child-exit-lineage'):
    marker, prefix, command, leases = probe_spec(arch, kind)
    serial, bounds = normalize_transcript(serial, (baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = bounds
    if error := failure_line(serial): raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail) != 2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final child-lineage prompt')
    boot = serial[:baseline_begin]
    spans = (serial[baseline_begin:probe_begin],serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end],serial[native_begin:])
    boot_exits = exit_events(boot, arch)
    child_baseline = boot_baseline(wait_ledger_view(boot, boot_exits), required=True)
    native_parent = next(iter(child_baseline.values()))['selector']
    for start, expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
            (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        if [line for line in boot.splitlines() if start in line] != [expected]:
            raise ValueError('missing unique child-lineage distribution boot')
    pipe_events(boot, arch)
    futex_events(boot, arch, allow_signal=False)
    poll_events(boot, arch, allow_signal=False)
    if signal_wait_events(boot, arch): raise ValueError('signal wait outside lineage probe')
    observations = []
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    for index, span in enumerate(spans):
        events = incidental(span, arch, child_baseline, child_wait=index in (1,2))
        lines = [line for line in span.splitlines() if line]
        images = [i for i,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if index in (0,3):
            if images or any(b'CHILD_LINEAGE_' in line for line in lines) or signal_wait_events(span, arch):
                raise ValueError('lineage image or wait outside dedicated probe')
            if lines.count(b'hello from ObfuscationOS userland') != 1:
                raise ValueError('missing unique lineage native pipeline')
            validate_native_pipeline(span, arch, native_parent, require_two_pairs=False)
            validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland',tuple(e['line'] for e in events))
            continue
        if len(images) != 1 or lines.count(marker) != 1 or not images[0] < lines.index(marker):
            raise ValueError('lineage probe lacks unique image and completion')
        if IMAGE.fullmatch(lines[images[0]])[1] != source:
            raise ValueError('wrong lineage image memory source')
        if any(line != command and not WAIT.fullmatch(line) for line in lines[:images[0]]):
            raise ValueError('unexpected output before lineage image admission')
        guest = guest_events(span,arch)
        lifecycle = exit_events(span,arch)
        exits = [r for r in lifecycle if r['tag']=='OK_NATIVE_CHILD_EXIT']
        if explicit_reap_batches(lifecycle) or len(lifecycle) != 15:
            raise ValueError('lineage campaign has extra completion or automatic reap')
        signals = signal_wait_events(span,arch,allow_child=True)
        polls = poll_events(span,arch,allow_signal=False)
        joined = validate_joins(span,guest,exits,signals,polls)
        # Only case5 performs a blocking signal wait. The full parser admits
        # unrelated extra rows, so bind its complete set to this exact workload.
        if len(signals) != 2 or any(r['pid'] != guest['cases'][5]['pid'] for r in signals):
            raise ValueError('unobserved signal-wait owner in lineage campaign')
        # pipe and pthread operations have separate ledgers; only case6 ppolls.
        if len(polls) != 2 or any(r['pid'] != guest['cases'][6]['pid'] for r in polls):
            raise ValueError('unobserved poll owner in lineage campaign')
        main = guest['cases'][0]['parent']
        main_rows = [r for r in exits if r['child']==main]
        if len(main_rows) != 1: raise ValueError('missing unique lineage main completion')
        final = main_rows[0]
        wanted = dict(parent=native_parent,parent_tid=0,parent_epoch=0,uid=guest['cases'][0]['uid'],
                      code=1,status=0,wait_code=1,wait_status=0,published=1,notify=0,queued=0,coalesced=0,autoreap=0)
        if any(final[k] != v for k,v in wanted.items()) or not span.splitlines().index(marker) < final['position']:
            raise ValueError('lineage main lost native shell ownership or completion ordering')
        if set(joined['assigned_exit_positions']) | {final['position']} != {r['position'] for r in exits}:
            raise ValueError('unobserved lineage process completion')
        waits = join_native_waits(span,lifecycle)
        if len(waits) != 2: raise ValueError('lineage campaign lacks exact shell wait pair')
        arm, complete = waits
        if (any(r[k] != v for r in waits for k,v in dict(pid=native_parent,tid=native_parent,selector=main,format='status').items()) or
                arm['outcome'] != 'arm' or arm['result'] != -11 or arm['live'] != 2 or
                complete['outcome'] != 'complete' or complete['result'] != main or complete['live'] != 1 or
                not 0 < arm['request'] == arm['wait'] == complete['request'] == complete['wait'] or
                not 0 < arm['output'] == complete['output'] or
                not arm['position'] < guest['cases'][0]['begin']['position'] < final['position'] < complete['position']):
            raise ValueError('lineage shell wait differs from exact main lifetime')
        validate_command(span,command,marker,tuple(e['line'] for e in events)+tuple(guest['lines']))
        observations.append(dict(guest_cases=serializable(guest['cases']),**joined,main_pid=main,
                                 main_parent=native_parent,process_completions=15))
    if any(b'CHILD_LINEAGE_' in line for line in boot.splitlines()):
        raise ValueError('lineage marker outside dedicated commands')
    exit_events(serial,arch)
    frames, stacks = decode_frames(serial,arch), decode_stacks(serial)
    if any(left==right for left,right in zip(frames,frames[1:])):
        raise ValueError('duplicate child-lineage frame snapshot')
    if any(frames[0][k] for k in ('used','allocations','releases')) or any(stacks[0].values()):
        raise ValueError('missing empty child-lineage boot accounting')
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base,live = frame_ends[0],stack_ends[0]['leased']
    if not live or any(r['leased']!=live for r in stack_ends):
        raise ValueError('lineage command did not return to live shell stack baseline')
    previous_frame,previous_stack = decode_frames(boot,arch)[-1],decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        if any(span.rfind(p)<=span.rfind(success) for p in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS')):
            raise ValueError('lineage resource retirement precedes user completion')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or
                frame['allocations']<=previous_frame['allocations'] or frame['releases']<=previous_frame['releases']):
            raise ValueError('lineage pages and persistent owner did not retire exactly')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if (delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or
                delta['activations']<=0 or delta['faults'] or delta['rejected']):
            raise ValueError('lineage command lacks fresh owned entries or has rejected/faulting capture')
        commands.append(delta)
        previous_frame,previous_stack=frame,stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-child-exit-lineage',
                observations=observations,parent_thread_lineage=True,leader_first_group_cause=True,
                synchronous_wait_real_blocked=True,ppoll_temporary_mask=True,
                native_pipeline_immediate_ready_allowed=True,all_native_waits_traced=False,
                production=False,physical=False,smp=False,cpu_time_accounting=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frames),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stacks)))
