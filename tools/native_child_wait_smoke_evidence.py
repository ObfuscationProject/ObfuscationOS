"""Exploratory x86 native child wait EINTR/restart and exact continuation ledger."""
import re
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure,decode_frames
from entry_stack_evidence import decode_stacks,COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE,validate_command
from native_pipe_io_events import native_events as pipe_events,PATTERNS as PIPE_PATTERNS
from native_futex_events import native_events,final_snapshots,PATTERNS as FUTEX_PATTERNS
from native_child_events import scan as child_scan, parsed, WAIT, SIGNAL, PATTERNS as CHILD_WAIT_PATTERNS, normalize_transcript
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
GUEST_PREFIX=b'CHILD_SMOKE_'
KERNEL_PREFIX=b'OK_NATIVE_CHILD_'
EVENT=re.compile(rb'CHILD_SMOKE_(BEGIN|SEND|HANDLE|EINTR|RELEASE|REAP|CASE_PASS) case=([0-3]) restart=([01]) any=([01]) pid=([0-9]+) child=([0-9]+) selector=([0-9]+) output=([0-9]+) pc=([0-9]+) result=(-?[0-9]+)')
PATTERNS=(EVENT,)+CHILD_PATTERNS
def probe_spec(arch,kind):
    if arch!='x86_64' or kind!='child-wait-smoke':raise ValueError('exploratory x86 child wait only')
    return b'CHILD_SMOKE_PASS cases=4 eintr=2 restart=2',b'CHILD_SMOKE_PASS',b'/bin/child-wait-smoke',9
def failure_line(serial):
    prefix=b'CHILD_SMOKE_FAIL code='
    if prefix in serial:return serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)
def incomplete_failure_line(serial):
    prefix=b'CHILD_SMOKE_FAIL code=';return prefix in serial and b'\n' not in serial[serial.index(prefix):]
def validate_cases(span,arch,baseline=None):
    if arch!='x86_64':raise ValueError('unsupported exploratory child profile')
    events=child_events(span,arch,allow_signal=True,baseline=baseline);events=[r for r in events if r['tag'] in ('OK_NATIVE_CHILD_WAIT','OK_NATIVE_CHILD_SIGNAL')];event_lines={r['line']:r for r in events}
    if len(events)!=len(event_lines):raise ValueError('duplicate child wait diagnostic')
    owners={int(EVENT.fullmatch(l)[5]) for l in span.splitlines() if EVENT.fullmatch(l)}
    if len(owners)!=1:raise ValueError('child smoke changed parent process')
    pid=next(iter(owners));selected={r['line'] for r in events if (r['pid'],r['tid'])==(pid,pid)}
    if any(r['tag']=='OK_NATIVE_CHILD_SIGNAL' for r in events if r['line'] not in selected):raise ValueError('incidental child signal completion')
    lines=[l for l in span.splitlines() if l in selected or GUEST_PREFIX in l and not l.startswith(b'CHILD_SMOKE_PASS')]
    cursor=0;previous=0;children=set()
    def take(pattern):
        nonlocal cursor
        if cursor>=len(lines):raise ValueError('truncated child smoke case')
        line=lines[cursor];cursor+=1
        if not pattern.fullmatch(line):raise ValueError('unexpected child smoke event: '+line.decode(errors='replace'))
        return event_lines[line] if pattern in CHILD_PATTERNS else EVENT.fullmatch(line)
    for case in range(4):
        restart,any_child=case%2,case//2
        begin=take(EVENT);values=tuple(int(x) for x in begin.groups()[1:])
        if begin[1]!=b'BEGIN' or values[:3]!=(case,restart,any_child):raise ValueError('wrong child smoke case')
        owner,child,selector,output,site,value=values[3:]
        if (owner!=pid or child<=0 or child==pid or child in children or
            selector!=(0xffffffff if any_child else child) or not 0x40000000<=output<0x80000000 or output%4 or
            not 0x40000000<=site<0x80000000 or value!=0):raise ValueError('invalid child wait copied inputs')
        children.add(child);resume=site+2
        def event(tag,pc,result):
            m=take(EVENT)
            if m[1]!=tag or tuple(int(x) for x in m.groups()[1:])!=(case,restart,any_child,pid,child,selector,output,pc,result):raise ValueError('child smoke event changed owner/result/continuation')
        arm=take(WAIT)
        if (arm['pid'],arm['tid'],arm['selector'],arm['output'],arm['format'],arm['outcome'],arm['result'])!=(pid,pid,selector,output,'status','arm',-11) or arm['request']<=previous:raise ValueError('missing fresh owned child wait')
        event(b'SEND',site,0);retired=take(WAIT)
        if retired['arm'] is not arm or retired['outcome']!='interrupted' or retired['result']!=(0 if restart else -4):raise ValueError('child wait interrupted wrong object')
        signal=take(SIGNAL)
        if signal['terminal'] is not retired or signal['signal']!=10 or signal['pc']!=(site if restart else resume) or signal['outcome']!=('restart' if restart else 'eintr'):raise ValueError('wrong child wait signal publication')
        event(b'HANDLE',site if restart else resume,61 if restart else -4)
        if not restart:event(b'EINTR',resume,-4)
        fresh=take(WAIT)
        if (fresh['outcome'],fresh['selector'],fresh['output'],fresh['format'])!=('arm',selector,output,'status') or fresh['request']<=arm['request'] or fresh['wait']<=arm['wait']:raise ValueError('child restart reused old request or ticket')
        event(b'RELEASE',site,0);completed=take(WAIT)
        if completed['arm'] is not fresh or completed['outcome']!='complete' or completed['result']!=child:raise ValueError('child wait reaped wrong child')
        event(b'REAP',resume,child);event(b'CASE_PASS',resume,child);previous=fresh['request']
    if cursor!=len(lines):raise ValueError('extra child smoke events')
    return dict(cases=4,initial_waits=4,fresh_waits=4,eintr=2,restart=2,handlers=4,reaped=4)

def _validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='child-wait-smoke'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated child wait smoke command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('child wait smoke boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final child wait smoke prompt')
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
        incidental = pipe_events(span,arch) + native_events(span,arch,allow_signal=False) + child_events(span,arch,baseline=child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=1 or lines.count(marker)!=1 or
            any(line!=command and not WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered child-wait-smoke/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong child wait smoke image source')
        pipe_events(span,arch)
        native_events(span,arch,allow_signal=False)
        observations.append(validate_cases(span,arch,child_baseline))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+PIPE_PATTERNS+FUTEX_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_events(boot,arch)
    native_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('child wait smoke completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate child wait smoke frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty child wait smoke boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('child wait smoke commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('child wait smoke accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects']!=base['objects'] or base['objects']!=1 or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('child wait smoke command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('child wait smoke command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-child-wait-smoke',
                observations=observations,owned_child_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_restart=True,temporary_masks=False,exploratory_x86_only=True,
                job_control=False,production=False,physical=False,smp=False,
                child_baseline={str(k):{n:v for n,v in r.items() if n!='line'} for k,r in child_baseline.items()},
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))


def validate_execution(serial,baseline_begin,probe_begin,probe_mid,probe_end,native_begin,arch,kind='child-wait-smoke'):
    serial,bounds=normalize_transcript(serial,(baseline_begin,probe_begin,probe_mid,probe_end,native_begin))
    return _validate_execution(serial,*bounds,arch,kind)
