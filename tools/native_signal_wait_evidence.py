"""Strict all-ten SDK synchronous signal wait execution collector; host/model/static evidence stays separate."""
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
from signal_wait_guest_protocol import validate_cases as guest_cases,parse as guest_rows,PATTERNS as GUEST_PATTERNS,GUEST_PREFIX
from signal_wait_native_protocol import validate_owned_waits
from signal_wait_guest_protocol import combinations, expected_calls, signals
from native_signal_wait_events import native_events as wait_events, PATTERNS as WAIT_PATTERNS
PATTERNS=GUEST_PATTERNS+KERNEL_PATTERNS+WAIT_PATTERNS

def image_count(arch):
 return 1+sum((f==0 and c==28) or (f==1 and c in (13,14)) for f,a,t,form,restart,c in combinations(arch))
def minimum_leases(arch):
 count=1
 for f,a,t,form,restart,c in combinations(arch):
  count+=1
  count+=0 if (f and c<5) or (not f and c<13) or (not f and c in (21,22,23)) else 2 if (f and c==14) or (not f and c in (16,28,30)) else 1
  count+=1 if (f and c==12) or (not f and c in (5,30)) else 3 if not f and c==21 else 0
 return count

def probe_spec(arch,kind):
 if arch not in READV or kind!='signal-waits':raise ValueError('unsupported synchronous signal wait profile')
 command='/bin/native-signal-wait-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
 if len(command.rsplit('/',1)[1])>31:raise ValueError('signal-wait executable exceeds component capacity')
 return f'SIGNAL_WAIT_PASS arch={arch} cases={len(list(combinations(arch)))} excluded=0 semantic_cases=49'.encode(),b'SIGNAL_WAIT_PASS',command.encode(),minimum_leases(arch)

def failure_line(serial):
 if b'SIGNAL_WAIT_FAIL' in serial:return 'synchronous signal wait assertion: '+serial[serial.index(b'SIGNAL_WAIT_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
 return general_failure(serial)
def incomplete_failure_line(serial):return b'SIGNAL_WAIT_FAIL' in serial and b'\n' not in serial[serial.index(b'SIGNAL_WAIT_FAIL'):]
def validate_cases(span,arch):
 result=guest_cases(span,arch)
 result['native_waits']=validate_owned_waits(span,arch,guest_rows(span,arch),wait_events(span,arch))
 return result

def _validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='signal-waits'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated synchronous signal wait command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('synchronous signal wait boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final synchronous signal wait prompt')
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
        if (len(images)!=image_count(arch) or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered synchronous signal wait/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong synchronous signal wait image source')
        pipe_events(span,arch,allow_signal=False)
        futex_events(span,arch,allow_signal=False)
        poll_events(span,arch,allow_signal=False)
        children = child_events(span,arch,baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+FUTEX_PATTERNS+POLL_PATTERNS+CHILD_PATTERNS))
        validate_command(span,command,marker,extra + tuple(e['line'] for e in children))
    for outside in (boot,baseline,native):
        if wait_events(outside,arch):raise ValueError('signal wait ownership outside dedicated commands')
    pipe_events(boot,arch,allow_signal=False)
    if any(r['vector'] for span in (boot,baseline,native) for r in pipe_events(span,arch,allow_signal=False)):
        raise ValueError('vector publication outside dedicated guest commands')
    futex_events(boot,arch,allow_signal=False)
    poll_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and b'OK_NATIVE_' not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('synchronous signal wait completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate synchronous signal wait frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty synchronous signal wait boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('synchronous signal wait commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('synchronous signal wait accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('synchronous signal wait command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('synchronous signal wait command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=image_count(arch),scope='actual-user-private-signal-waits',
                observations=observations,raw_timed_wait=True,libc_timed_wait=True,
                raw_suspend=True,libc_suspend=True,copied_masks=True,copied_deadlines=True,
                realtime_pressure_fallback=True,full_siginfo_bytes=True,
                fork_empty=True,exec_retirement=True,group_retirement=True,
                raw_eintr=True,libc_eintr_retry=True,suspend_handler_masks=True,
                ignored_generation_real_blocked=True,ignored_suspend_drain=True,
                physical=False,smp=False,production=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))


def validate_execution(serial,baseline_begin,probe_begin,probe_mid,probe_end,native_begin,arch,kind='signal-waits'):
    normalized,bounds=normalize_transcript(serial,(baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    return _validate_execution(normalized,*bounds,arch,kind)
