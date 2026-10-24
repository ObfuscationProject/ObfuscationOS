"""Strict all-ten SDK process-shared signal execution collector; host/model/static evidence stays separate."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure,decode_frames
from entry_stack_evidence import decode_stacks,COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE,validate_command
from native_futex_events import native_events as futex_events,final_snapshots,PATTERNS as FUTEX_PATTERNS
from native_poll_events import native_events as poll_events,PATTERNS as POLL_PATTERNS
from native_child_events import normalize_transcript,WAIT as CHILD_WAIT,PATTERNS as CHILD_PATTERNS
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_pipe_vector_events import native_events as pipe_events,READV,PATTERNS as KERNEL_PATTERNS
from process_signal_guest_protocol import validate_cases as guest_cases,parse as guest_rows,PATTERNS as GUEST_PATTERNS,GUEST_PREFIX
from process_signal_native_protocol import validate_owned_waits
PATTERNS=GUEST_PATTERNS+KERNEL_PATTERNS

def probe_spec(arch,kind):
 if arch not in READV or kind!='process-shared-signals':raise ValueError('unsupported process-shared signal profile')
 groups=6 if arch in ('arm32','ppc') else 4
 command='/bin/native-process-signal-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
 if len(command.rsplit('/',1)[1])>31:raise ValueError('process-shared signal executable exceeds component capacity')
 return f'PROCESS_SIGNAL_PASS arch={arch} variants=2 groups={groups} cases={33*groups} parent=1'.encode(),b'PROCESS_SIGNAL_PASS',command.encode(),1+103*groups

def failure_line(serial):
 if b'PROCESS_SIGNAL_FAIL' in serial:return 'process-shared signal assertion: '+serial[serial.index(b'PROCESS_SIGNAL_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
 return general_failure(serial)
def incomplete_failure_line(serial):return b'PROCESS_SIGNAL_FAIL' in serial and b'\n' not in serial[serial.index(b'PROCESS_SIGNAL_FAIL'):]
def validate_cases(span,arch):
 result=guest_cases(span,arch)
 result['native_waits']=validate_owned_waits(span,arch,guest_rows(span,arch),pipe_events(span,arch,allow_signal=True))
 return result

def _validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='process-shared-signals'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated process-shared signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('process-shared signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final process-shared signal prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    child_baseline = boot_baseline(boot,arch,required=True)
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        if any(IMAGE.fullmatch(line) for line in span.splitlines()):
            raise ValueError('unexpected Linux image in native pipeline')
        incidental = pipe_events(span,arch,allow_signal=False) + futex_events(span,arch,allow_signal=False) + poll_events(span,arch,allow_signal=False) + child_events(span,arch,baseline=child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=(13 if arch in ('arm32','ppc') else 9) or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered process-shared signal/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong process-shared signal image source')
        pipe_events(span,arch,allow_signal=True)
        futex_events(span,arch,allow_signal=False)
        poll_events(span,arch,allow_signal=False)
        children = child_events(span,arch,baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+FUTEX_PATTERNS+POLL_PATTERNS+CHILD_PATTERNS))
        validate_command(span,command,marker,extra + tuple(e['line'] for e in children))
    pipe_events(boot,arch,allow_signal=False)
    if any(r['vector'] for span in (boot,baseline,native) for r in pipe_events(span,arch,allow_signal=False)):
        raise ValueError('vector publication outside dedicated guest commands')
    futex_events(boot,arch,allow_signal=False)
    poll_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and b'OK_NATIVE_' not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('process-shared signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate process-shared signal frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty process-shared signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('process-shared signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('process-shared signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('process-shared signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('process-shared signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=13 if arch in ('arm32','ppc') else 9,scope='actual-user-private-process-shared-signals',
                observations=observations,process_directed_kill=True,positive_pid_tid=True,
                directed_before_shared=True,shared_pending_union=True,real_sender_credentials=True,
                fork_empty=True,exec_preserves_survivor_queues=True,realtime_pressure_fallback=True,
                blocked_wait_interruption=True,caught_restart=True,group_fatal_cancellation=True,
                fatal_console_service=True,temporary_masks=False,job_control=False,
                nonpositive_targets=False,caught_console_delivery=False,production=False,physical=False,smp=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))


def validate_execution(serial,baseline_begin,probe_begin,probe_mid,probe_end,native_begin,arch,kind='process-shared-signals'):
    normalized,bounds=normalize_transcript(serial,(baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    return _validate_execution(normalized,*bounds,arch,kind)
