"""SDK31 sleep signal guest evidence; parsing alone does not execute delivery."""
import json
import re
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import decode_frames, failure_line as general_failure, require_hash, relative_file
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command

LEGACY32 = ('i386', 'arm32', 'mips', 'ppc')

def case_contract(arch):
    if arch not in ARCH_TRIPLES:
        raise ValueError('unsupported sleep-signal architecture')
    forms = (0, 1, 2, 3, 4) if arch in LEGACY32 else ((0, 1, 4) if arch == 'rv32' else (0, 1, 2, 3))
    rows = []
    for form in forms:
        for case in range(16):
            if case in (9, 10) and form < 2:
                continue
            if case in (11, 12, 13, 14) and form in (0, 2):
                continue
            rows.append(dict(form=form, case=case,
                format='time32' if (arch in LEGACY32 and form != 4) else 'time64',
                kind='absolute' if 11 <= case <= 14 else 'relative',
                result='efault' if case in (9, 10) else ('eintr' if case < 5 or case in (11, 12) else 'success'),
                interruptions=2 if case == 14 else (1 if case < 5 or case in (9, 10, 11, 12) else 0)))
    return rows

def probe_spec(arch, kind):
    if arch not in ARCH_TRIPLES or kind != 'sleep-signals':
        raise ValueError('unsupported sleep-signal guest profile')
    count = (5, 68, 43, 6, 61) if arch in LEGACY32 else ((3, 40, 25, 2, 36) if arch == 'rv32' else (4, 52, 32, 4, 47))
    forms, cases, interrupts, faults, leases = count
    marker = f'SLEEP_SIGNAL_PASS arch={arch} forms={forms} cases={cases} interrupts={interrupts} efault={faults} guards=1 parent=1'.encode()
    command = '/bin/native-signal-sleep-' + ('la64' if arch == 'loongarch64' else arch.replace('_','-'))
    return marker, b'SLEEP_SIGNAL_PASS', command.encode(), leases

BEGIN = re.compile(rb'SLEEP_SIGNAL_CASE_BEGIN arch=([a-z0-9_]+) form=([0-9]+) case=([0-9]+) pid=([0-9]+) tid=([0-9]+) expected=(success|eintr|efault) format=(time32|time64) kind=(relative|absolute) interrupts=([0-9]+)')
END = re.compile(rb'SLEEP_SIGNAL_CASE_PASS arch=([a-z0-9_]+) form=([0-9]+) case=([0-9]+)')
INTERRUPT = re.compile(rb'OK_NATIVE_SLEEP_INTERRUPT pid=([0-9]+) tid=([0-9]+) wait=([0-9]+) kind=(relative|absolute) format=(time32|time64) result=(eintr|efault) deadline=([0-9]+) now=([0-9]+)')
EVENT_PREFIXES = (b'SLEEP_SIGNAL_CASE', b'OK_NATIVE_SLEEP_INTERRUPT')

def validate_cases(span, arch):
    """Bind each guest case to exact owned native interruption diagnostics."""
    lines = [line for line in span.splitlines() if any(prefix in line for prefix in EVENT_PREFIXES)]
    cursor = 0
    owners, generations = {}, {}
    interrupted = faults = 0
    def take(pattern):
        nonlocal cursor
        if cursor >= len(lines) or not (match := pattern.fullmatch(lines[cursor])):
            raise ValueError('missing, malformed or reordered sleep case event')
        cursor += 1
        return match.groups()
    rows = case_contract(arch)
    for row in rows:
        a, form, case, pid, tid, result, fmt, kind, number = take(BEGIN)
        pid, tid = int(pid), int(tid)
        if (a.decode() != arch or int(form) != row['form'] or int(case) != row['case'] or
            result.decode() != row['result'] or fmt.decode() != row['format'] or
            kind.decode() != row['kind'] or int(number) != row['interruptions'] or
            not 0 < pid == tid <= 0xffffffff):
            raise ValueError('sleep case differs from admitted guest contract')
        if row['form'] in owners:
            if owners[row['form']] != pid:
                raise ValueError('sleep form changed receiver identity')
        else:
            if pid in owners.values():
                raise ValueError('sleep forms must execute in distinct child processes')
            owners[row['form']] = pid
        deadline = previous_now = None
        for _ in range(row['interruptions']):
            dp, dt, ticket, dk, df, dr, end, now = take(INTERRUPT)
            ticket, end, now = int(ticket), int(end), int(now)
            expected_result = 'efault' if row['result'] == 'efault' else 'eintr'
            if (int(dp) != pid or int(dt) != tid or dk.decode() != row['kind'] or
                df.decode() != row['format'] or dr.decode() != expected_result or
                not generations.get(tid, 0) < ticket <= 0xffffffffffffffff or
                not 0 <= now < end <= 0xffffffffffffffff):
                raise ValueError('sleep interruption lacks exact unexpired owned wait')
            if deadline is not None and (end != deadline or now <= previous_now):
                raise ValueError('repeated absolute sleep shifted deadline or time did not advance')
            deadline, previous_now = end, now
            generations[tid] = ticket
            interrupted += 1
            faults += dr == b'efault'
        ea, ef, ec = take(END)
        if ea.decode() != arch or int(ef) != row['form'] or int(ec) != row['case']:
            raise ValueError('sleep completion differs from active case')
    if cursor != len(lines):
        raise ValueError('unexpected sleep event after final case')
    final = probe_spec(arch, 'sleep-signals')[0]
    if span.rfind(final) < span.rfind(b'SLEEP_SIGNAL_CASE_PASS'):
        raise ValueError('sleep aggregate precedes case completion')
    return dict(cases=len(rows), forms=len(owners), interruptions=interrupted, efault=faults)

def incomplete_failure_line(serial):
    prefix = b'SLEEP_SIGNAL_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def failure_line(serial):
    prefix = b'SLEEP_SIGNAL_FAIL'
    if prefix in serial:
        return 'sleep-signal assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)

def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    if arch not in ARCH_TRIPLES or mode != 'debug':
        raise ValueError('sleep-signal execution requires an explicit Debug profile')
    require_hash(sdk/'manifest.json', expected, 'SDK manifest')
    require_hash(compiler, compiler_hash, 'SDK compiler')
    manifest = json.loads((sdk/'manifest.json').read_text())
    if not isinstance(manifest.get('files'),dict):
        raise ValueError('SDK missing artifact inventory')
    for name in manifest['files']:
        relative_file(sdk,name)
    manifest = validate_sdk(sdk,arch,mode,compiler)
    if manifest['abi_version'] != 31 or manifest['compiler'].get('family') != 'gcc':
        raise ValueError('sleep-signal execution requires SDK31 GCC ABI')
    return manifest

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='sleep-signals'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated sleep signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('sleep signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final sleep signal prompt')
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
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland')
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=1 or lines.count(marker)!=1 or
            images[0]!=(1 if lines[0]==command else 0) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered sleep-signals/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong sleep signal image source')
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if BEGIN.fullmatch(line) or END.fullmatch(line) or INTERRUPT.fullmatch(line))
        validate_command(span,command,marker,extra)
    if any(any(p in span for p in (prefix, *EVENT_PREFIXES)) for span in (boot,baseline,native)):
        raise ValueError('sleep signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty sleep signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('sleep signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('sleep signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('sleep signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('sleep signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-signal-sleep',
                observations=observations,blocked_wait_interruption=True,
                process_directed_kill=False,pipe_restart=False,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
