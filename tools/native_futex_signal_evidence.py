"""Private native FUTEX_WAIT caught-signal and context-controlled restart evidence."""
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
from native_futex_events import (WORD32, NUMBERS, ARM, RETIRE, SIGNAL, PATTERNS as NATIVE_PATTERNS,
    PREFIX as KERNEL_PREFIX, parse as parsed, native_events, instruction, final_snapshots)

GETPID=dict(zip(NUMBERS,(39,20,172,20,172,172,172,4020,5038,20)))
def form_count(arch):
    if arch not in NUMBERS:raise ValueError('unsupported native futex signal architecture')
    return 2 if arch in ('arm32','ppc') else 1

def probe_spec(arch,kind):
    forms=form_count(arch);abis=len(NUMBERS[arch]);multiple=forms*abis
    if kind!='futex-signals':raise ValueError('unsupported native futex signal profile')
    command='/bin/native-futex-signal-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
    marker=f'FUTEX_SIGNAL_PASS arch={arch} forms={forms} abis={abis} domains=2 rounds=2 cases={76*multiple} initial_waits={68*multiple} parent=1'
    return marker.encode(),b'FUTEX_SIGNAL_PASS',command.encode(),1+78*multiple

KEY=rb'arch=([a-z0-9_]+) form=([01]) abi=([01]) domain=([01]) round=([01]) case=([0-9]|1[0-8])'
OWNER=rb' pid=([0-9]+) tid=([0-9]+)'
ARGS=rb' number=([0-9]+) address=([0-9]+) operation=([0-9]+) value=([0-9]+) timeout=([0-9]+)'
BEGIN=re.compile(rb'FUTEX_SIGNAL_CASE_BEGIN '+KEY+OWNER+rb' number=([0-9]+) address=([0-9]+) alternate=([0-9]+) operation=([0-9]+) value=([0-9]+) timeout=([0-9]+) format=(time32|time64) timed=([01]) duration=([0-9]+) site=([0-9]+) resume=([0-9]+) wait=([01])')
ATTEMPT=re.compile(rb'FUTEX_SIGNAL_ATTEMPT '+KEY+OWNER+ARGS)
SEND=re.compile(rb'FUTEX_SIGNAL_SEND '+KEY+OWNER+rb' ordinal=([12]) signal=([0-9]+)')
WAKE=re.compile(rb'FUTEX_SIGNAL_WAKE '+KEY+rb' address=([0-9]+) operation=([0-9]+) expected=([01])')
MUTATE=re.compile(rb'FUTEX_SIGNAL_MUTATE_TIMEOUT '+KEY)
UNMASK=re.compile(rb'FUTEX_SIGNAL_UNMASK '+KEY)
RETURN=re.compile(rb'FUTEX_SIGNAL_RETURN '+KEY+rb' result=(-?[0-9]+) error=([0-9]+) elapsed=([0-9]+)')
END=re.compile(rb'FUTEX_SIGNAL_CASE_PASS '+KEY)
HANDLER=re.compile(rb'FUTEX_SIGNAL_(HANDLE|HANDLER_RETURN|NESTED) '+KEY+OWNER+rb' ordinal=([12]) pc=([0-9]+) inspected=([01])(?:'+ARGS+rb')?(?: cr=([0-9]+) diagnostic_result=([0-9]+) orig_r3=([0-9]+)| cpsr=([0-9]+))?')
GUEST_PREFIX=b'FUTEX_SIGNAL_'
PATTERNS=(BEGIN,ATTEMPT,SEND,WAKE,MUTATE,UNMASK,RETURN,END,HANDLER)+NATIVE_PATTERNS

def failure_line(serial):
    prefix=b'FUTEX_SIGNAL_FAIL'
    if prefix in serial:
        return 'futex signal assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)

def incomplete_failure_line(serial):
    prefix=b'FUTEX_SIGNAL_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def validate_cases(span,arch):
    events=native_events(span,arch)
    event_lines={row['line']:row for row in events}
    if len(event_lines)!=len(events):raise ValueError('duplicate native futex diagnostic')
    targets={(row['pid'],row['tid']) for line in span.splitlines() if BEGIN.fullmatch(line) for row in (parsed(BEGIN,line),)}
    selected={row['line'] for row in events if (row['pid'],row['tid']) in targets}
    incidental=[row for row in events if row['line'] not in selected]
    if any(row['tag']=='OK_NATIVE_FUTEX_SIGNAL' for row in incidental):
        raise ValueError('unowned incidental futex signal interruption')
    lines=[line for line in span.splitlines() if line in selected or
        (GUEST_PREFIX in line and KERNEL_PREFIX not in line and not line.startswith(b'FUTEX_SIGNAL_PASS'))]
    cursor=0;maximum=(1 << (32 if arch in WORD32 else 64))-1
    forms=form_count(arch);abis=len(NUMBERS[arch]);owners={};tids=set()
    counts=dict(cases=0,forms=forms,abis=abis,domains=2,rounds=2,initial_waits=0,fresh_restart_waits=0,
        eintr=0,restart_publications=0,ready_retirements=0,timeout_retirements=0,immediate=0,
        outer_handlers=0,nested_handlers=0,main_sends=0,wake_calls=0,
        incidental_arms=sum(row['tag']=='OK_NATIVE_FUTEX_ARM' for row in incidental))
    def take(pattern):
        nonlocal cursor
        if cursor>=len(lines):raise ValueError('truncated futex signal case')
        row=parsed(pattern,lines[cursor]);cursor+=1
        return event_lines.get(row['line'],row)
    for domain in range(2):
      for abi in range(abis):
       for form in range(forms):
        for round_id in range(2):
         for case in range(19):
            def guest(pattern):
                row=take(pattern)
                if tuple(row[k] for k in ('arch','form','abi','domain','round','case'))!=(arch,form,abi,domain,round_id,case):
                    raise ValueError('futex signal event changed active case')
                return row
            begin=guest(BEGIN);pid,tid=begin['pid'],begin['tid']
            timed=case in (2,3,10,12,17);duration=0 if case==17 else 160000000 if case in (10,12) else 500000000
            width=2 if arch in ('i386','x86_64') or (arch=='arm32' and form==1) else 4
            wide=arch not in WORD32 or NUMBERS[arch][abi] in (422,4422)
            if (not 0<pid<=0xffffffff or not 0<tid<=0xffffffff or pid==tid or tid in tids or
                    begin['number']!=NUMBERS[arch][abi] or begin['operation']!=128*domain or begin['value']!=0x12345678+int(case==18) or
                    begin['format']!=('time64' if wide else 'time32') or begin['timed']!=int(timed) or begin['duration']!=duration or begin['wait']!=int(case<17) or
                    bool(begin['timeout'])!=timed or not 0<=begin['timeout']<=maximum-(15 if wide else 7) or
                    not 0<begin['address']<=maximum-128 or begin['address']%4 or begin['alternate']!=begin['address']+64 or
                    not instruction(arch,begin['site'],form==1) or not instruction(arch,begin['resume'],form==1) or begin['resume']-begin['site']!=width):
                raise ValueError('invalid futex case identity, ABI, arguments or instruction labels')
            tids.add(tid);group=(domain,abi,form)
            if group in owners and owners[group]!=pid:raise ValueError('futex domain/ABI/form changed child process')
            owners[group]=pid
            attempt=guest(ATTEMPT)
            if any(attempt[k]!=begin[k] for k in ('pid','tid','number','address','operation','value','timeout')):
                raise ValueError('futex attempt changed original request')
            current=None;previous_origin=0;previous_wait=0
            def fresh(initial=False):
                nonlocal current,previous_origin,previous_wait
                arm=take(ARM);changed=case==8 and not initial
                expected=dict(pid=pid,tid=tid,pc=begin['resume'],syscall=begin['number'],address=begin['alternate'] if changed else begin['address'],
                    operation=begin['operation'],expected=0x87654321 if changed else begin['value'],timeout=begin['timeout'],format=begin['format'])
                if any(arm[k]!=value for k,value in expected.items()) or arm['origin']<=previous_origin or arm['wait']<=previous_wait:
                    raise ValueError('missing exact fresh owned futex arm')
                current=arm;previous_origin=arm['origin'];previous_wait=arm['wait']
                counts['initial_waits' if initial else 'fresh_restart_waits']+=1
            def terminal(reason):
                row=take(RETIRE)
                if current is None or row['arm'] is not current or row['reason']!=reason:
                    raise ValueError('futex terminal changed current owned wait')
                if reason in ('ready','timeout'):counts[reason+'_retirements']+=1
                return row
            def handler(ordinal,signal_event=None):
                h=guest(HANDLER);inspected=case<=9 or case==16
                base={'tag','line','arch','form','abi','domain','round','case','pid','tid','ordinal','pc','inspected'}
                fields={'number','address','operation','value','timeout'} if inspected else set()
                extra=({'cr','diagnostic_result','orig_r3'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set()) if inspected else set()
                if (h['tag']!='FUTEX_SIGNAL_HANDLE' or (h['pid'],h['tid'],h['ordinal'],h['inspected'])!=(pid,tid,ordinal,int(inspected)) or
                        not instruction(arch,h['pc']) or set(h)!=base|fields|extra or any(not 0<=h[k]<=maximum for k in fields|extra)):
                    raise ValueError('invalid futex signal handler target/context shape')
                if inspected:
                    restart=case not in (0,2,3)
                    number=begin['number'] if restart or arch not in ('x86_64','i386','mips','mips64') else 4 if arch.startswith('mips') else maximum-3
                    address=begin['address'] if restart or arch in ('x86_64','i386','mips','mips64') else 4 if arch=='ppc' else maximum-3
                    timeout=1 if not restart and arch.startswith('mips') else begin['timeout']
                    expected=dict(pc=begin['site' if restart else 'resume'],number=number,address=address,operation=begin['operation'],value=begin['value'],timeout=timeout)
                    if signal_event is None or h['pc']!=signal_event['pc'] or any(h[k]!=v for k,v in expected.items()):
                        raise ValueError('handler differs from captured original futex context/result')
                    if arch=='arm32' and (h['cpsr']&0x0700ffdf!=0x10 or bool(h['cpsr']&0x20)!=(form==1)):
                        raise ValueError('futex handler lost legal ARM user instruction state')
                    if arch=='ppc' and (not h['cr']&0x10000000 or h['orig_r3']!=begin['address'] or
                            h['diagnostic_result']!=(0 if restart else maximum-3)):
                        raise ValueError('futex handler lost PPC restart diagnostics')
                counts['outer_handlers']+=1
                if case==16:
                    nested=guest(HANDLER)
                    if (nested['tag']!='FUTEX_SIGNAL_NESTED' or set(nested)!=base or
                            (nested['pid'],nested['tid'],nested['ordinal'],nested['inspected'])!=(pid,tid,1,0) or not instruction(arch,nested['pc'])):
                        raise ValueError('invalid nested futex signal target/context')
                    counts['nested_handlers']+=1
                end=guest(HANDLER);expected={k:v for k,v in h.items() if k not in ('tag','line')}
                if case==5:
                    expected['pc']=begin['resume'];expected['number' if arch in ('x86_64','i386','mips','mips64') else 'address']=77
                    if arch.startswith('mips'):expected['timeout']=0
                    if arch=='ppc':expected.update(cr=h['cr']&~0x10000000,diagnostic_result=0x123,orig_r3=0x234)
                if case==6:expected['number']=GETPID[arch]
                if case==7:expected['value']=0x87654321
                if case==8:expected.update(address=begin['alternate'],value=0x87654321)
                if end['tag']!='FUTEX_SIGNAL_HANDLER_RETURN' or {k:v for k,v in end.items() if k not in ('tag','line')}!=expected:
                    raise ValueError('futex handler edits differ from exact user request')
            def send(ordinal,delivered=True):
                row=guest(SEND)
                if (row['pid'],row['tid'],row['ordinal'],row['signal'])!=(pid,tid,ordinal,16 if arch.startswith('mips') else 10):
                    raise ValueError('futex signal changed owner/ordinal/number')
                counts['main_sends']+=1
                if delivered:
                    event=None
                    if case<=9 or case==16:
                        retired=terminal('interrupted');event=take(SIGNAL);outcome='eintr' if case in (0,2,3) else 'restart'
                        if event['terminal'] is not retired or event['outcome']!=outcome:
                            raise ValueError('caught futex signal changed interruption outcome')
                        counts['eintr' if outcome=='eintr' else 'restart_publications']+=1
                    handler(ordinal,event)
            def wake(address,expected):
                row=guest(WAKE)
                if (row['address'],row['operation'],row['expected'])!=(address,128*domain+1,expected):
                    raise ValueError('futex wake address/domain/count differs from active case')
                counts['wake_calls']+=1
                if expected:terminal('ready')
            def result():
                row=guest(RETURN)
                # Raw guest results use target Linux errno numbers; kernel RETIRE
                # diagnostics retain the internal canonical timeout result -110.
                expected=-4 if case in (0,2,3) else -11 if case in (4,7,18) else 77 if case==5 else pid if case==6 else -(145 if arch in ('mips','mips64') else 110) if case in (10,12,17) else 0
                if (row['result'],row['error'])!=(expected,111) or not 0<=row['elapsed']<5000000000:
                    raise ValueError('futex raw result/errno/elapsed differs from case contract')
                if case in (2,3) and row['elapsed']>=duration or case in (10,12) and not duration<=row['elapsed']<duration+1000000000:
                    raise ValueError('futex timing differs from original copied relative timeout')
            if case<17:
                fresh(initial=True)
                if case<=9 or case==16:
                    send(1)
                    if case==9:fresh();send(2)
                    if case in (1,8,9,16):
                        fresh()
                        if case==8:wake(begin['address'],0)
                        wake(begin['alternate'] if case==8 else begin['address'],1)
                    result()
                elif case==10:guest(MUTATE);terminal('timeout');result()
                elif case==12:terminal('timeout');result();send(1)
                else:
                    if case in (14,15):send(1,False)
                    wake(begin['address'],1);result()
                    if case==13:send(1)
                    if case==14:guest(UNMASK);handler(1)
            else:result();counts['immediate']+=1
            wake(begin['address'],0);wake(begin['alternate'],0);guest(END);counts['cases']+=1
    if cursor!=len(lines) or len(set(owners.values()))!=2*abis*forms:
        raise ValueError('unexpected futex case event or reused domain/ABI/form child')
    if span.rfind(probe_spec(arch,'futex-signals')[0])<span.rfind(b'FUTEX_SIGNAL_CASE_PASS'):
        raise ValueError('futex aggregate precedes exact case completion')
    return counts

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='futex-signals'):
    serial, boundaries = normalize_transcript(serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = boundaries
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated futex signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('futex signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final futex signal prompt')
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
        if (len(images)!=1 or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered futex-signals/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong futex signal image source')
        pipe_events(span,arch)
        child_events(span,arch, baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+PIPE_PATTERNS+CHILD_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_events(boot,arch)
    native_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('futex signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate futex signal frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty futex signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('futex signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('futex signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] != int(bool(child_baseline)) or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('futex signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('futex signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-futex-signals',
                observations=observations,owned_futex_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,untimed_futex_restart=True,timed_futex_restart=False,shared_backing_keys=False,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
