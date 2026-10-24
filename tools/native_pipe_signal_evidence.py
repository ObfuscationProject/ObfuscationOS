"""Private native pipe signal evidence. Synthetic parser tests are not execution."""
import re
from native_child_events import normalize_transcript, PATTERNS as CHILD_WAIT_PATTERNS, WAIT as CHILD_WAIT
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
from kernel_sdk import ARCH_TRIPLES
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command
from native_pipe_read_evidence import WAIT, IDENTITY
from native_futex_events import native_events as futex_events, PATTERNS as FUTEX_PATTERNS, instruction, final_snapshots

READ = dict(zip(('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc'), (0,3,63,3,63,63,63,4003,5000,3)))
GETPID = dict(zip(READ, (39,20,172,20,172,172,172,4020,5038,20)))
WORD32 = ('i386','arm32','rv32','mips','ppc')
def form_count(arch):
    if arch not in ARCH_TRIPLES:
        raise ValueError('unsupported native pipe signal architecture')
    return 2 if arch in ('arm32','ppc') else 1

def probe_spec(arch, kind):
    forms = form_count(arch)
    if kind != 'pipe-signals':
        raise ValueError('unsupported pipe signal profile')
    command = '/bin/native-pipe-signal-' + ('la64' if arch == 'loongarch64' else arch.replace('_', '-'))
    marker = f'PIPE_SIGNAL_PASS arch={arch} forms={forms} rounds=3 cases={forms*36} initial_waits={forms*33} signals={forms*39} parent=1'
    return marker.encode(), b'PIPE_SIGNAL_PASS', command.encode(), 1+37*forms

KEY = rb'arch=([a-z0-9_]+) form=([01]) round=([0-2]) case=([0-9]|1[01])'
OWNER = rb' pid=([0-9]+) tid=([0-9]+)'
ARGS = rb' fd=([0-9]+) buffer=([0-9]+) count=([0-9]+)'
BEGIN = re.compile(rb'PIPE_SIGNAL_CASE_BEGIN ' + KEY + OWNER + ARGS + rb' site=([0-9]+) resume=([0-9]+) replacement=([0-9]+) alternate=([0-9]+) libc=([01]) wait=([01])')
ATTEMPT = re.compile(rb'PIPE_SIGNAL_ATTEMPT ' + KEY + OWNER + ARGS)
SEND = re.compile(rb'PIPE_SIGNAL_SEND ' + KEY + OWNER + rb' ordinal=([12]) signal=([0-9]+)')
REPLACE = re.compile(rb'PIPE_SIGNAL_REPLACE ' + KEY)
ORIGINAL = re.compile(rb'PIPE_SIGNAL_ORIGINAL_READY ' + KEY)
RETURN = re.compile(rb'PIPE_SIGNAL_RETURN ' + KEY + rb' result=(-?[0-9]+) error=([0-9]+)')
END = re.compile(rb'PIPE_SIGNAL_CASE_PASS ' + KEY)
HANDLER = re.compile(rb'PIPE_SIGNAL_(HANDLE|HANDLER_RETURN|NESTED) ' + KEY + OWNER + rb' ordinal=([12]) pc=([0-9]+) inspected=([01])(?: number=([0-9]+) fd=([0-9]+) buffer=([0-9]+) count=([0-9]+))?(?: cr=([0-9]+) diagnostic_result=([0-9]+) orig_r3=([0-9]+)| cpsr=([0-9]+)| a3=([0-9]+))?')
COMPLETE = re.compile(rb'OK_NATIVE_PIPE_READ_COMPLETE ' + IDENTITY + rb' result=(-?[0-9]+) outcome=(ready|eof|efault|cancelled|error|interrupted) pinned=([01]) live=([0-9]+)')
ORIGIN = re.compile(rb'OK_NATIVE_PIPE_ORIGIN pid=([0-9]+) tid=([0-9]+) request=([0-9]+) wait=([0-9]+) origin=([0-9]+) pc=([0-9]+) syscall=([0-9]+) fd=([0-9]+) output=([0-9]+) bytes=([0-9]+)')
INTERRUPT = re.compile(rb'OK_NATIVE_PIPE_SIGNAL pid=([0-9]+) tid=([0-9]+) request=([0-9]+) wait=([0-9]+) origin=([0-9]+) signal=([0-9]+) outcome=(eintr|restart) pc=([0-9]+) syscall=([0-9]+) fd=([0-9]+) output=([0-9]+) bytes=([0-9]+) pinned=([01]) live=([0-9]+)')
KERNEL_PREFIX = b'OK_NATIVE_PIPE_'
GUEST_PREFIX = b'PIPE_SIGNAL_'
PATTERNS = (BEGIN,ATTEMPT,SEND,REPLACE,ORIGINAL,RETURN,END,HANDLER,WAIT,COMPLETE,ORIGIN,INTERRUPT)

def failure_line(serial):
    prefix = b'PIPE_SIGNAL_FAIL'
    if prefix in serial:
        return 'pipe signal assertion failed: ' + serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)

def incomplete_failure_line(serial):
    prefix = b'PIPE_SIGNAL_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def parsed(pattern, line):
    if not pattern.fullmatch(line):
        raise ValueError('malformed pipe signal event')
    result = {'tag': line.split()[0].decode(), 'line': line}
    for item in line.split()[1:]:
        name, value = item.decode().split('=', 1)
        result[name] = value if name in ('arch', 'stage', 'outcome') else int(value)
    return result


def native_events(span, arch):
    """Account actual transcript objects and origins, including native pipelines."""
    form_count(arch)
    maximum = (1 << (32 if arch in WORD32 else 64)) - 1
    active, waits, origins, events = {}, {}, {}, []
    pending = None
    previous = b''
    identity_keys = ('pid','tid','request','output','fd','description','pipe','bytes')
    for line in span.splitlines():
        if KERNEL_PREFIX not in line:
            if line:
                previous = line
            continue
        pattern = next((p for p in (WAIT, COMPLETE, ORIGIN, INTERRUPT) if p.fullmatch(line)), None)
        if pattern is None:
            raise ValueError('malformed native pipe signal diagnostic')
        row = parsed(pattern, line)
        owner = (row['pid'], row['tid'])
        if (not all(0 < value <= 0xffffffff for value in owner) or
                not 0 < row['request'] <= row['wait'] <= 0xffffffffffffffff or
                not 0 < row['output'] <= maximum or not 0 < row['bytes'] <= maximum or
                row['bytes']-1 > maximum-row['output'] or not 0 <= row['fd'] <= 0x7fffffff):
            raise ValueError('invalid native pipe signal identity')
        if pending is not None and pattern is not INTERRUPT:
            raise ValueError('interrupted retirement lacks immediate signal publication')
        if pattern in (WAIT, COMPLETE):
            if not 0 <= row['description'] < 0xffff or not 0 <= row['pipe'] < 0xffff:
                raise ValueError('invalid pipe description or object identity')
            identity = tuple(row[key] for key in identity_keys)
            if pattern is WAIT:
                if row['wait'] <= waits.get(owner, 0):
                    raise ValueError('stale pipe wait generation')
                if row['stage'] == 'arm':
                    if owner in active or row['request'] != row['wait']:
                        raise ValueError('duplicate or invalid pipe initial arm')
                    active[owner] = dict(identity=identity, wait=row['wait'], origin=None)
                else:
                    if owner not in active or active[owner]['identity'] != identity:
                        raise ValueError('readiness rearm changed retained pipe request')
                    active[owner]['wait'] = row['wait']
                waits[owner] = row['wait']
            else:
                state = active.get(owner)
                if state is None or state['identity'] != identity or state['wait'] != row['wait'] or row['pinned']:
                    raise ValueError('terminal lost retained pipe identity, wait or pin')
                result, outcome = row['result'], row['outcome']
                if (not -(1 << 63) <= result < (1 << 63) or
                        (outcome == 'ready' and not 0 < result <= row['bytes']) or
                        (outcome == 'eof' and result != 0) or
                        (outcome == 'efault' and result != -14) or
                        (outcome == 'cancelled' and result != -125) or
                        (outcome == 'error' and (result >= 0 or result in (-14, -125))) or
                        (outcome == 'interrupted' and result not in (-4, 0))):
                    raise ValueError('terminal result differs from pipe outcome')
                row['origin_record'] = state['origin']
                if outcome == 'interrupted':
                    if state['origin'] is None:
                        raise ValueError('interrupted pipe has no captured origin')
                    pending = row
                del active[owner]
            if row['live'] != len(active):
                raise ValueError('pipe live count differs from actual publication/retirement ledger')
        elif pattern is ORIGIN:
            state = active.get(owner)
            arm = parsed(WAIT, previous) if WAIT.fullmatch(previous) else None
            if (state is None or state['origin'] is not None or arm is None or arm['stage'] != 'arm' or
                    any(row[key] != arm[key] for key in ('pid','tid','request','wait','fd','output','bytes')) or
                    row['request'] != row['wait'] or not origins.get(owner, 0) < row['origin'] <= 0xffffffffffffffff or
                    row['syscall'] != READ[arch] or not instruction(arch,row['pc'])):
                raise ValueError('origin does not bind the immediately preceding fresh Linux arm')
            state['origin'] = row
            origins[owner] = row['origin']
        else:
            if pending is None or previous != pending['line']:
                raise ValueError('signal publication did not immediately follow interrupted retirement')
            origin = pending['origin_record']
            if (any(row[key] != pending[key] for key in ('pid','tid','request','wait','fd','output','bytes','live','pinned')) or
                    any(row[key] != origin[key] for key in ('origin','syscall')) or
                    row['signal'] != (16 if arch.startswith('mips') else 10) or
                    not instruction(arch,row['pc']) or
                    pending['result'] != (-4 if row['outcome'] == 'eintr' else 0)):
                raise ValueError('signal publication changed interrupted owner/origin/request/outcome')
            widths = (2,) if arch in ('x86_64','i386') else (2,4) if arch == 'arm32' else (4,)
            if (row['outcome'] == 'eintr' and row['pc'] != origin['pc']) or (
                    row['outcome'] == 'restart' and origin['pc']-row['pc'] not in widths):
                raise ValueError('published signal PC differs from captured origin')
            row['origin_record'] = origin
            row['terminal'] = pending
            pending = None
        events.append(row)
        previous = line
    if active or pending is not None:
        raise ValueError('live continuation or incomplete signal retirement at command boundary')
    return events


def validate_cases(span, arch):
    events = native_events(span, arch)
    event_lines = {row['line']: row for row in events}
    if len(event_lines) != len(events):
        raise ValueError('duplicate native pipe signal diagnostic')
    lines = [line for line in span.splitlines() if KERNEL_PREFIX in line or
             (GUEST_PREFIX in line and not line.startswith(b'PIPE_SIGNAL_PASS'))]
    cursor = 0
    maximum = (1 << (32 if arch in WORD32 else 64)) - 1
    forms = form_count(arch)
    form_owners, tids = {}, set()
    counts = dict(cases=0,forms=forms,rounds=3,initial_waits=0,fresh_restart_waits=0,
                  rearms=0,eintr=0,restart_publications=0,outer_handlers=0,nested_handlers=0)

    def take(pattern):
        nonlocal cursor
        if cursor >= len(lines):
            raise ValueError('truncated pipe signal case')
        row = parsed(pattern, lines[cursor])
        cursor += 1
        return event_lines.get(row['line'], row)

    def keyed(row, form, round_id, case):
        if (row['arch'],row['form'],row['round'],row['case']) != (arch,form,round_id,case):
            raise ValueError('pipe signal event changed active case')
        return row

    for form in range(forms):
        for round_id in range(3):
            for case in range(12):
                def guest(pattern):
                    return keyed(take(pattern), form, round_id, case)
                begin = guest(BEGIN)
                pid, tid, fd, output, count = (begin[key] for key in ('pid','tid','fd','buffer','count'))
                raw_width = 2 if arch in ('x86_64','i386') or (arch=='arm32' and form==1) else 4
                if (not 0 < pid <= 0xffffffff or not 0 < tid <= 0xffffffff or tid==pid or tid in tids or
                        not 0 <= fd <= 0x7fffffff or not 0 <= begin['replacement'] <= 0x7fffffff or begin['replacement']==fd or
                        count != (8 if case==7 else 1) or not 0 < output <= maximum-4096 or
                        begin['alternate'] != output+64 or begin['libc'] != int(case>=10) or begin['wait'] != int(case!=7) or
                        not instruction(arch,begin['site'],form==1) or not instruction(arch,begin['resume'],form==1) or begin['resume']-begin['site'] != raw_width):
                    raise ValueError('invalid pipe signal case ownership/arguments/instruction labels')
                tids.add(tid)
                if form in form_owners and form_owners[form] != pid:
                    raise ValueError('pipe signal form changed child process')
                form_owners[form] = pid
                attempted = guest(ATTEMPT)
                if any(attempted[key] != begin[key] for key in ('pid','tid','fd','buffer','count')):
                    raise ValueError('pipe signal attempt changed case inputs')
                current = None
                previous_origin = 0

                def fresh(initial=False):
                    nonlocal current, previous_origin
                    arm = take(WAIT)
                    if (arm['stage'] != 'arm' or
                            (arm['pid'],arm['tid'],arm['fd'],arm['output'],arm['bytes']) != (pid,tid,fd,output,count)):
                        raise ValueError('missing exact fresh owned pipe arm')
                    origin = take(ORIGIN)
                    if origin['origin'] <= previous_origin or (case<10 and origin['pc'] != begin['resume']):
                        raise ValueError('fresh restarted entry lacks a new exact captured origin')
                    if current is not None and any(arm[key] != current[key] for key in ('description','pipe')):
                        raise ValueError('unchanged numeric fd restarted on another pipe description')
                    previous_origin = origin['origin']
                    current = arm
                    counts['initial_waits' if initial else 'fresh_restart_waits'] += 1

                def rearms():
                    nonlocal cursor
                    while cursor < len(lines) and WAIT.fullmatch(lines[cursor]):
                        row = take(WAIT)
                        if current is None or row['stage'] != 'rearm' or any(row[key] != current[key] for key in ('pid','tid','request')):
                            raise ValueError('unexpected new wait instead of same-request readiness rearm')
                        counts['rearms'] += 1

                def handler(ordinal, signal_event=None):
                    handled = guest(HANDLER)
                    if (handled['tag'] != 'PIPE_SIGNAL_HANDLE' or
                            (handled['pid'],handled['tid'],handled['ordinal'],handled['inspected']) != (pid,tid,ordinal,int(case!=7)) or
                            not instruction(arch,handled['pc'])):
                        raise ValueError('handler entered for wrong target or sequence')
                    if case!=7:
                        fields = {'number','fd','buffer','count'}
                        extra = {'cr','diagnostic_result','orig_r3'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else {'a3'} if arch.startswith('mips') else set()
                        actual = set(handled)-{'tag','line','arch','form','round','case','pid','tid','ordinal','pc','inspected'}
                        if actual != fields|extra or any(not 0 <= handled[key] <= maximum for key in fields|extra):
                            raise ValueError('handler context has missing/extra/overflow target fields')
                        if (handled['buffer'],handled['count'],handled['pc']) != (output,count,signal_event['pc']):
                            raise ValueError('handler context differs from published pipe frame')
                        restart = case not in (0,10)
                        expected_number = READ[arch] if restart or arch not in ('x86_64','i386','mips','mips64') else 4 if arch.startswith('mips') else maximum-3
                        expected_fd = fd if restart or arch in ('x86_64','i386','mips','mips64') else 4 if arch=='ppc' else maximum-3
                        if handled['number']!=expected_number or handled['fd']!=expected_fd:
                            raise ValueError('handler lost original syscall inputs or EINTR result encoding')
                        if arch=='arm32':
                            width = 2 if handled['cpsr']&0x20 else 4
                            if handled['cpsr']&0x010001df != 0x10 or not instruction(arch,handled['pc'],width==2) or (case<10 and width!=raw_width):
                                raise ValueError('handler lost captured ARM instruction mode')
                        else:
                            width = 2 if arch in ('x86_64','i386') else 4
                        origin_pc = signal_event['origin_record']['pc']
                        if handled['pc'] != origin_pc-(width if restart else 0):
                            raise ValueError('handler PC has incorrect target instruction adjustment')
                        if arch.startswith('mips') and ((restart and case<10 and handled['a3']!=0x1357) or (not restart and handled['a3']!=1)):
                            raise ValueError('handler lost original MIPS a3 or EINTR flag')
                        if arch=='ppc' and (not handled['cr']&0x10000000 or handled['diagnostic_result']!=(0 if restart else maximum-3) or handled['orig_r3']!=fd):
                            raise ValueError('handler lost Linux PPC saved restart/EINTR diagnostics')
                    elif set(handled)-{'tag','line','arch','form','round','case','pid','tid','ordinal','pc','inspected'}:
                        raise ValueError('short-progress handler must not claim pipe restart context')
                    counts['outer_handlers'] += 1
                    if case==9:
                        nested = guest(HANDLER)
                        if (nested['tag'] != 'PIPE_SIGNAL_NESTED' or
                                (nested['pid'],nested['tid'],nested['ordinal'],nested['inspected']) != (pid,tid,1,0) or
                                not instruction(arch,nested['pc']) or
                                set(nested)-{'tag','line','arch','form','round','case','pid','tid','ordinal','pc','inspected'}):
                            raise ValueError('nested handler changed target or claimed restart authority')
                        counts['nested_handlers'] += 1
                    returned = guest(HANDLER)
                    expected = {key:value for key,value in handled.items() if key not in ('tag','line')}
                    if case==2:
                        expected['pc']=begin['resume']
                        expected['number' if arch in ('x86_64','i386','mips','mips64') else 'fd']=77
                        if arch.startswith('mips'):expected['a3']=0
                        if arch=='ppc':expected.update(cr=handled['cr']&~0x10000000,diagnostic_result=0x123,orig_r3=0x234)
                    if case==3:expected['number']=GETPID[arch]
                    if case==4:expected.update(fd=begin['replacement'],buffer=begin['alternate'],count=2)
                    if returned['tag']!='PIPE_SIGNAL_HANDLER_RETURN' or {key:value for key,value in returned.items() if key not in ('tag','line')}!=expected:
                        raise ValueError('handler-edited context differs from exact expected user request')

                def sent(ordinal):
                    rearms()
                    sent_row = guest(SEND)
                    if (sent_row['pid'],sent_row['tid'],sent_row['ordinal'],sent_row['signal']) != (pid,tid,ordinal,16 if arch.startswith('mips') else 10):
                        raise ValueError('directed signal changed owner/ordinal/number')
                    if case==7:
                        handler(ordinal)
                        return
                    rearms()
                    terminal = take(COMPLETE)
                    interrupted = take(INTERRUPT)
                    outcome = 'eintr' if case in (0,10) else 'restart'
                    if (terminal['outcome']!='interrupted' or current is None or
                            any(terminal[key]!=current[key] for key in ('pid','tid','request')) or interrupted['outcome']!=outcome):
                        raise ValueError('caught signal failed to retire its exact owned read')
                    counts['eintr' if outcome=='eintr' else 'restart_publications'] += 1
                    handler(ordinal, interrupted)

                def returned():
                    row = guest(RETURN)
                    expected = pid if case==3 else -1 if case==10 else -4 if case==0 else 77 if case==2 else 2 if case==4 else 3 if case==7 else 1
                    if (row['result'],row['error']) != (expected,4 if case==10 else 111):
                        raise ValueError('pipe return differs from guest data/context contract')

                if case==7:
                    returned(); sent(1)
                else:
                    fresh(initial=True); rearms()
                    if case==6:
                        guest(REPLACE); rearms()
                    else:
                        sent(1)
                    if case==8:
                        fresh(); sent(2)
                    if case in (1,8,9,11):
                        fresh(); rearms()
                    if case in (1,6,8,9,11):
                        guest(ORIGINAL); rearms()
                        complete = take(COMPLETE)
                        if (complete['outcome'],complete['result']) != ('ready',1) or any(complete[key]!=current[key] for key in ('pid','tid','request')):
                            raise ValueError('final readiness completed another read')
                    returned()
                guest(END)
                counts['cases'] += 1
    if cursor!=len(lines) or len(set(form_owners.values()))!=forms:
        raise ValueError('unexpected pipe signal event or reused form child')
    if span.rfind(probe_spec(arch,'pipe-signals')[0]) < span.rfind(b'PIPE_SIGNAL_CASE_PASS'):
        raise ValueError('pipe signal aggregate precedes case completion')
    return counts

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='pipe-signals'):
    import native_pipe_io_events as pipe_io
    serial, boundaries = normalize_transcript(serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = boundaries
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated pipe signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('pipe signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final pipe signal prompt')
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
        incidental = pipe_io.native_events(span, arch) + futex_events(span, arch, allow_signal=False) + child_events(span,arch, baseline=child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland', tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    observations=[]
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=1 or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered pipe-signals/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong pipe signal image source')
        futex_events(span,arch,allow_signal=False)
        child_events(span,arch, baseline=child_baseline)
        observations.append(pipe_io.validate_read_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in pipe_io.PATTERNS+FUTEX_PATTERNS+CHILD_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_io.native_events(boot, arch)
    futex_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('pipe signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate pipe signal frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty pipe signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('pipe signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('pipe signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] != int(bool(child_baseline)) or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('pipe signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('pipe signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-pipe-signals',
                observations=observations,owned_description_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,pipe_restart=True,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
