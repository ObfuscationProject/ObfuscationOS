"""Actual scalar pipe continuation evidence, separate from hosted/model tests."""
import re
from kernel_sdk import ARCH_TRIPLES
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command


def probe_spec(arch, kind):
    if arch not in ARCH_TRIPLES or kind != 'pipe-read-continuation':
        raise ValueError('unsupported pipe read profile')
    command = '/bin/native-pipe-read-' + ('la64' if arch == 'loongarch64' else arch.replace('_', '-'))
    marker = f'PIPE_READ_PASS arch={arch} forms=2 rounds=4 cases=64 waits=48 efault=8 parent=1'
    return marker.encode(), b'PIPE_READ_PASS', command.encode(), 75


KEY = rb'arch=([a-z0-9_]+) form=([01]) round=([0-3]) case=([0-7])'
OWNER = rb' pid=([0-9]+) tid=([0-9]+)'
ARGS = rb' fd=([0-9]+) buffer=([0-9]+) count=([0-9]+)'
BEGIN = re.compile(rb'PIPE_READ_CASE_BEGIN ' + KEY + OWNER + ARGS + rb' wait=([01])')
ATTEMPT = re.compile(rb'PIPE_READ_ATTEMPT ' + KEY + OWNER + ARGS)
MUTATE = re.compile(rb'PIPE_READ_MUTATE ' + KEY + OWNER)
EXIT = re.compile(rb'PIPE_READ_EXIT_GROUP ' + KEY + OWNER)
REPLACEMENT = re.compile(rb'PIPE_READ_REPLACEMENT_READY ' + KEY)
ORIGINAL = re.compile(rb'PIPE_READ_ORIGINAL_READY ' + KEY)
END = re.compile(rb'PIPE_READ_CASE_PASS ' + KEY)
IDENTITY = rb'pid=([0-9]+) tid=([0-9]+) wait=([0-9]+) request=([0-9]+) output=([0-9]+) fd=([0-9]+) description=([0-9]+) pipe=([0-9]+) bytes=([0-9]+)'
WAIT = re.compile(rb'OK_NATIVE_PIPE_READ_WAIT ' + IDENTITY + rb' stage=(arm|rearm) live=([0-9]+)')
COMPLETE = re.compile(rb'OK_NATIVE_PIPE_READ_COMPLETE ' + IDENTITY + rb' result=(-?[0-9]+) outcome=(ready|eof|efault|cancelled|error) pinned=([01]) live=([0-9]+)')
KERNEL_PREFIX = b'OK_NATIVE_PIPE_READ'
GUEST_PREFIX = b'PIPE_READ_'


def native_events(span, arch):
    """Account every published object, including incidental native pipelines."""
    if arch not in ARCH_TRIPLES:
        raise ValueError('unsupported pipe read architecture')
    maximum = 0xffffffff if arch in ('i386', 'arm32', 'rv32', 'mips', 'ppc') else 0xffffffffffffffff
    active, generations, events = {}, {}, []
    for line in span.splitlines():
        if KERNEL_PREFIX not in line:
            continue
        match = WAIT.fullmatch(line)
        terminal = False
        if match is None:
            match = COMPLETE.fullmatch(line)
            terminal = True
        if match is None:
            raise ValueError('malformed native pipe continuation record')
        values = match.groups()
        pid, tid, wait, request, output, fd, description, pipe, count = map(int, values[:9])
        if (not 0 < pid <= 0xffffffff or not 0 < tid <= 0xffffffff or
                not 0 < wait <= 0xffffffffffffffff or not 0 < request <= wait or
                not 0 < output <= maximum or not 0 < count <= maximum or
                count - 1 > maximum - output or not 0 <= fd <= 0x7fffffff or
                not 0 <= description < 0xffff or not 0 <= pipe < 0xffff):
            raise ValueError('invalid native pipe continuation identity')
        identity = (pid, tid, request, output, fd, description, pipe, count)
        owner = (pid, tid)
        live = int(values[-1])
        event = dict(pid=pid, tid=tid, wait=wait, request=request, output=output,
                     fd=fd, description=description, pipe=pipe, count=count, live=live,
                     terminal=terminal, line=line)
        if not terminal:
            stage = values[9].decode()
            event['stage'] = stage
            if wait <= generations.get(owner, 0):
                raise ValueError('stale native pipe wait generation')
            if stage == 'arm':
                if owner in active or request != wait:
                    raise ValueError('duplicate or invalid native pipe arm')
            elif owner not in active or active[owner][0] != identity:
                raise ValueError('rearm changed original pipe request')
            active[owner] = (identity, wait)
            generations[owner] = wait
        else:
            result, outcome, pinned = int(values[9]), values[10].decode(), int(values[11])
            if active.get(owner) != (identity, wait) or pinned:
                raise ValueError('completion lost original pipe identity or pin')
            if (not -(1 << 63) <= result < (1 << 63) or
                    (outcome == 'ready' and not 0 < result <= count) or
                    (outcome == 'eof' and result != 0) or
                    (outcome == 'efault' and result != -14) or
                    (outcome == 'cancelled' and result != -125) or
                    (outcome == 'error' and (result >= 0 or result in (-14, -125)))):
                raise ValueError('pipe result does not match terminal outcome')
            del active[owner]
            event.update(result=result, outcome=outcome)
        if live != len(active):
            raise ValueError('native pipe object count did not track publication/retirement')
        events.append(event)
    if active:
        raise ValueError('native pipe continuation remained live at command boundary')
    return events


def validate_cases(span, arch):
    records = native_events(span, arch)
    by_line = {row['line']: row for row in records}
    if len(by_line) != len(records):
        raise ValueError('duplicate native pipe diagnostic')
    lines = [line for line in span.splitlines() if KERNEL_PREFIX in line or
             (GUEST_PREFIX in line and not line.startswith(b'PIPE_READ_PASS'))]
    cursor, waits, rearmed, faults, cancellations = 0, 0, 0, 0, 0
    seen_threads, form_owners = set(), {}
    def take(pattern):
        nonlocal cursor
        if cursor >= len(lines) or not (match := pattern.fullmatch(lines[cursor])):
            raise ValueError('missing, malformed or reordered pipe case event')
        cursor += 1
        return match.groups()
    def key(values, form, round_id, case):
        if values[:4] != (arch.encode(), str(form).encode(), str(round_id).encode(), str(case).encode()):
            raise ValueError('pipe event differs from active case')
    for form in range(2):
        for round_id in range(4):
            for case in range(8):
                values = take(BEGIN)
                key(values, form, round_id, case)
                pid, tid, fd, output, count, blocking = map(int, values[4:])
                expected_count = 8 if case == 2 else 0 if case == 5 else 1
                if (not 0 < pid <= 0xffffffff or not 0 < tid <= 0xffffffff or tid == pid or
                        tid in seen_threads or count != expected_count or
                        blocking != int(case < 5 or case == 7) or output <= 0 or fd < 0):
                    raise ValueError('invalid pipe case owner or arguments')
                seen_threads.add(tid)
                if case != 7:
                    if form in form_owners and form_owners[form] != pid:
                        raise ValueError('pipe form changed process')
                    form_owners[form] = pid
                elif pid == form_owners.get(form):
                    raise ValueError('lifecycle pipe case did not use a separate child')
                attempted = take(ATTEMPT)
                if attempted != values[:-1]:
                    raise ValueError('pipe attempt changed captured case arguments')
                if blocking:
                    initial = lines[cursor] if cursor < len(lines) else b''
                    take(WAIT)
                    arm = by_line.get(initial)
                    if (not arm or arm['stage'] != 'arm' or
                            (arm['pid'], arm['tid'], arm['fd'], arm['output'], arm['count']) != (pid, tid, fd, output, count)):
                        raise ValueError('pipe case lacks matching owned arm before mutation')
                    waits += 1
                    def rearm():
                        nonlocal cursor, rearmed
                        while cursor < len(lines) and WAIT.fullmatch(lines[cursor]):
                            event = by_line[lines[cursor]]
                            if event['stage'] != 'rearm' or (event['pid'], event['tid'], event['request']) != (pid, tid, arm['request']):
                                raise ValueError('unrelated pipe rearm inside case')
                            cursor += 1
                            rearmed += 1
                    rearm()
                    mutation = take(EXIT if case == 7 else MUTATE)
                    key(mutation, form, round_id, case)
                    if tuple(map(int, mutation[4:])) != (pid, tid):
                        raise ValueError('pipe mutation targeted another thread')
                    if case != 7:
                        rearm(); key(take(REPLACEMENT), form, round_id, case)
                        rearm(); key(take(ORIGINAL), form, round_id, case)
                    rearm()
                    complete = lines[cursor] if cursor < len(lines) else b''
                    take(COMPLETE)
                    terminal = by_line.get(complete)
                    expected = ('cancelled', -125) if case == 7 else ('efault', -14) if case == 4 else ('eof', 0) if case == 3 else ('ready', 3 if case == 2 else 1)
                    if (not terminal or (terminal['pid'], terminal['tid'], terminal['request']) != (pid, tid, arm['request']) or
                            (terminal['outcome'], terminal['result']) != expected):
                        raise ValueError('pipe case did not complete its original request')
                    faults += case == 4
                    cancellations += case == 7
                key(take(END), form, round_id, case)
    if cursor != len(lines) or len(set(form_owners.values())) != 2:
        raise ValueError('unexpected pipe case event or duplicate form process')
    if span.rfind(probe_spec(arch, 'pipe-read-continuation')[0]) < span.rfind(b'PIPE_READ_CASE_PASS'):
        raise ValueError('pipe aggregate precedes all case completions')
    return dict(cases=64, forms=2, rounds=4, waits=waits, rearms=rearmed,
                efault=faults, cancellations=cancellations)


def incomplete_failure_line(serial):
    prefix = b'PIPE_READ_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]


def failure_line(serial):
    prefix = b'PIPE_READ_FAIL'
    if prefix in serial:
        return 'pipe read assertion failed: ' + serial[serial.index(prefix):].split(b'\n', 1)[0].decode(errors='replace')
    return general_failure(serial)


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='pipe-read-continuation'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated pipe read command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('pipe read boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final pipe read prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        if any(IMAGE.fullmatch(line) for line in span.splitlines()):
            raise ValueError('unexpected Linux image in native pipeline')
        incidental = native_events(span, arch)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=1 or lines.count(marker)!=1 or
            images[0]!=(1 if lines[0]==command else 0) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered pipe-read-continuation/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong pipe read image source')
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in (BEGIN, ATTEMPT, MUTATE, EXIT, REPLACEMENT, ORIGINAL, END, WAIT, COMPLETE)))
        validate_command(span,command,marker,extra)
    native_events(boot, arch)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('pipe read completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty pipe read boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('pipe read commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('pipe read accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('pipe read command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('pipe read command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-scalar-pipe-continuation',
                observations=observations,owned_description_continuation=True,blocked_wait_interruption=False,
                process_directed_kill=False,pipe_restart=False,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
