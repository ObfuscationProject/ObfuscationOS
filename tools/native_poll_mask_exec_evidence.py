"""SDK-only temporary-mask lifecycle across complete ELF image replacement."""
import re
from native_child_events import normalize_transcript, PATTERNS as CHILD_WAIT_PATTERNS, WAIT as CHILD_WAIT
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command
from native_pipe_io_events import native_events as pipe_events, PATTERNS as PIPE_PATTERNS
from native_futex_events import native_events, final_snapshots, PATTERNS as FUTEX_PATTERNS
from native_poll_events import native_events as poll_events, parse, ARM, RETIRE, SIGNAL, NUMBERS
GUEST_PREFIX=b'MASK_EXEC_'
KERNEL_PREFIX=b'OK_NATIVE_POLL_'
EVENT=re.compile(rb'MASK_EXEC_(WAIT|SEND|HANDLER|FAILED_PRESERVED|COMMIT|REPLACED) stage=([0-7]) family=([01]) mode=([0-3]) pid=([0-9]+) waiter=([0-9]+) executor=([0-9]+)')
PATTERNS=(EVENT,ARM,RETIRE,SIGNAL)
MASK_NUMBERS={
    'x86_64':((271,),(270,)), 'i386':((309,414),(308,413)),
    'aarch64':((73,),(72,)), 'arm32':((336,414),(335,413)),
    'rv32':((414,),(413,)), 'rv64':((73,),(72,)), 'loongarch64':((73,),(72,)),
    'mips':((4302,4414),(4301,4413)), 'mips64':((5261,),(5260,)),
    'ppc':((281,414),(280,413))}
def probe_spec(arch,kind):
    if arch not in NUMBERS or kind!='poll-mask-exec':raise ValueError('unsupported mask exec profile')
    return b'MASK_EXEC_PASS replacements=8 failed_exec=8',b'MASK_EXEC_PASS',b'/bin/native-poll-mask-exec',9
def failure_line(serial):
    prefix=b'MASK_EXEC_FAIL code='
    if prefix in serial:return serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)
def incomplete_failure_line(serial):
    prefix=b'MASK_EXEC_FAIL code=';return prefix in serial and b'\n' not in serial[serial.index(prefix):]
def validate_cases(span,arch):
    native_events(span,arch,allow_signal=False)
    lines=[line for line in span.splitlines() if IMAGE.fullmatch(line) or KERNEL_PREFIX in line or
           GUEST_PREFIX in line and not line.startswith(b'MASK_EXEC_PASS')]
    if not lines or not IMAGE.fullmatch(lines[0]):raise ValueError('missing initial exec image')
    cursor=1;owner=None
    def take(pattern):
        nonlocal cursor
        if cursor>=len(lines):raise ValueError('truncated exec transition')
        line=lines[cursor];cursor+=1
        if not pattern.fullmatch(line):raise ValueError('unexpected exec transition: '+line.decode(errors='replace'))
        return line
    for stage in range(8):
        first=cursor;family=stage//4;mode=stage%4;caught=mode<2
        def event(tag):
            line=take(EVENT);m=EVENT.fullmatch(line)
            values=tuple(int(x) for x in m.groups()[1:])
            if m[1]!=tag or values[:3]!=(stage,family,mode):raise ValueError('wrong exec stage')
            return values[3:]
        pid,tid,initial_executor=event(b'WAIT')
        if not 0<pid<=0xffffffff or not 0<tid<=0xffffffff:raise ValueError('invalid exec process identity')
        if owner is not None and owner!=pid:raise ValueError('exec changed process identity')
        owner=pid
        if (tid==pid)!=(mode in (0,2)) or initial_executor!=(tid if caught else 0):raise ValueError('wrong leader/nonleader waiter')
        arm=parse(ARM,take(ARM))
        if (arm['pid'],arm['tid'],arm['kind'],arm['count'],arm['live'])!=(pid,tid,'select' if family else 'poll',0,1) or not arm['deadline']:
            raise ValueError('exec waiter not armed under copied timeout')
        if arm['syscall'] not in MASK_NUMBERS[arch][family]:raise ValueError('exec wait does not use a mask-capable syscall')
        if caught:
            if event(b'SEND')!=(pid,tid,tid):raise ValueError('exec signal sender changed target')
            retired=parse(RETIRE,take(RETIRE));signal=parse(SIGNAL,take(SIGNAL))
            if retired['reason']!='interrupted' or retired['result']!=-4 or signal['result']!='eintr':raise ValueError('exec handler lacks EINTR')
            if event(b'HANDLER')!=(pid,tid,tid):raise ValueError('exec from wrong handler thread')
        failed=event(b'FAILED_PRESERVED');commit=event(b'COMMIT')
        if failed!=commit or failed[:2]!=(pid,tid):raise ValueError('failed exec changed caller identity')
        executor=commit[2]
        if (caught and executor!=tid or not caught and (executor<=0 or executor==tid or (executor==pid)!=(mode==3))):
            raise ValueError('wrong committed exec caller')
        if not caught:
            retired=parse(RETIRE,take(RETIRE))
            if retired['reason']!='cancelled' or retired['result']!=-4:raise ValueError('exec failed to cancel sibling wait')
        take(IMAGE)
        if event(b'REPLACED')!=(pid,0,0):raise ValueError('replacement did not reset image state')
        # Ticket generations belong to each exec image; validate each lifetime independently.
        events=poll_events(b'\n'.join(lines[first:cursor])+b'\n',arch)
        if len(events)!=(3 if caught else 2):raise ValueError('unexpected poll lifecycle during exec')
    if cursor!=len(lines):raise ValueError('extra exec transition')
    return dict(cases=8,initial_waits=8,eintr=4,handlers=4,cancelled_waits=4,failed_exec=8,replacements=8,post_exec_restorations=16)

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='poll-mask-exec'):
    serial, boundaries = normalize_transcript(serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = boundaries
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated poll signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('poll signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final poll signal prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    child_baseline = boot_baseline(boot,arch)
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        if any(IMAGE.fullmatch(line) for line in span.splitlines()):
            raise ValueError('unexpected Linux image in native pipeline')
        incidental = pipe_events(span,arch) + native_events(span,arch,allow_signal=False) + child_events(span,arch, baseline=child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=9 or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered poll-masks/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong poll signal image source')
        pipe_events(span,arch)
        child_events(span,arch, baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+PIPE_PATTERNS+FUTEX_PATTERNS+CHILD_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_events(boot,arch)
    native_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('poll signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate poll signal frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty poll signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('poll signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('poll signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] != int(bool(child_baseline)) or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('poll signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('poll signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=9,scope='actual-user-private-mask-exec',
                observations=observations,owned_readiness_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_restart=False,temporary_masks=True,exec_replacement=True,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
