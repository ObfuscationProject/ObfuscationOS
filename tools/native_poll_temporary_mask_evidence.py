"""Strict private raw ppoll/pselect temporary-mask native execution evidence."""
import re
from native_child_events import normalize_transcript, PATTERNS as CHILD_WAIT_PATTERNS, WAIT as CHILD_WAIT
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline
from native_child_exit_events import EXIT as CHILD_EXIT, REAP as CHILD_REAP
CHILD_PATTERNS = CHILD_WAIT_PATTERNS
LIFECYCLE_PATTERNS = (CHILD_EXIT, CHILD_REAP)
from native_signal_sleep_evidence import admit_sdk
from object_pressure_evidence import failure_line as general_failure, decode_frames
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE,validate_command
from native_pipe_io_events import native_events as pipe_events,PATTERNS as PIPE_PATTERNS
from native_futex_events import native_events as futex_events,PATTERNS as FUTEX_PATTERNS,WORD32,instruction,final_snapshots
from native_poll_events import native_events as poll_events,ARM,RETIRE,SIGNAL,PATTERNS as NATIVE_PATTERNS,PREFIX as KERNEL_PREFIX
from native_poll_signal_evidence import LANES as ORIGINAL_LANES
LANES={arch:[(n,i==3,w) for n,i,w,p,l in lanes if not l and i in (1,3)] for arch,lanes in ORIGINAL_LANES.items()}
KEY=rb'arch=([a-z0-9_]+) variant=([0-3]) form=([01]) restart=([01]) case=([0-9]|1[0-9]|2[0-4])'
OWNER=rb' pid=([0-9]+) tid=([0-9]+)'
BEGIN=re.compile(rb'POLL_TEMP_CASE_BEGIN '+KEY+OWNER+rb' syscall=([0-9]+) kind=(poll|select) duration=([0-9]+) site=([0-9]+) resume=([0-9]+) fd=([0-9]+) output=([0-9]+) timeout=([0-9]+) maskptr=([0-9]+) pair=([0-9]+) width=(32|64) bytes=(8|16) original=([0-9]+) temporary=([0-9]+)')
ATTEMPT=re.compile(rb'POLL_TEMP_ATTEMPT '+KEY+OWNER+rb' a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+) a4=([0-9]+) a5=([0-9]+)')
SEND=re.compile(rb'POLL_TEMP_SEND '+KEY+OWNER+rb' signal=([0-9]+)')
ACTION=re.compile(rb'POLL_TEMP_ACTION '+KEY+rb' action=(mutate-mask|protect-output|protect-mask|exit-group|mutate-timeout|ready)')
HANDLER=re.compile(rb'POLL_TEMP_(HANDLE|NESTED|NEST_BEGIN|NEST_RETURN|HANDLER_RETURN|HANDLER_EXIT) '+KEY+OWNER+rb' depth=([12]) pc=([0-9]+) result=([0-9]+) saved=([0-9]+) active=([0-9]+)(?: a3=([0-9]+)| cr=([0-9]+) diagnostic_result=([0-9]+)| cpsr=([0-9]+))?')
RETURN=re.compile(rb'POLL_TEMP_RETURN '+KEY+rb' result=(-?[0-9]+) error=([0-9]+) restored=([0-9]+) elapsed=([0-9]+) remaining=([0-9]+)')
PENDING=re.compile(rb'POLL_TEMP_PENDING '+KEY+rb' mask=([0-9]+)')
END=re.compile(rb'POLL_TEMP_CASE_PASS '+KEY)
EXIT_PASS=re.compile(rb'POLL_TEMP_EXIT_PASS '+KEY+rb' pid=([0-9]+) signal=([0-9]+)')
LINUX_WAIT=re.compile(rb'POLL_TEMP_LINUX_WAIT '+KEY+rb' nested=([01])'+OWNER+rb' syscall=([0-9]+)')
GUEST_PREFIX=b'POLL_TEMP_'
PATTERNS=(BEGIN,ATTEMPT,SEND,ACTION,HANDLER,RETURN,PENDING,END,EXIT_PASS)+NATIVE_PATTERNS

def parsed(pattern,line):
    if not pattern.fullmatch(line):raise ValueError('malformed temporary-mask event: '+line[:160].decode(errors='replace'))
    row={'tag':line.split()[0].decode(),'line':line}
    for field in line.split()[1:]:
        name,value=field.decode().split('=',1)
        row[name]=value if name in ('arch','kind','action') else int(value)
    return row

def native_events(span,arch,allow_signal=True):
    return poll_events(span,arch,allow_signal=allow_signal,signal_numbers=(16,17) if arch.startswith('mips') else (10,12))

def probe_spec(arch,kind):
    if arch not in LANES or kind!='poll-temporary-masks':raise ValueError('unsupported temporary-mask profile')
    forms=2 if arch in ('arm32','ppc') else 1;groups=len(LANES[arch])*forms*2
    marker=f'POLL_TEMP_PASS arch={arch} variants={len(LANES[arch])} groups={groups} cases={25*groups} parent=1'
    command='/bin/native-poll-tmask-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
    return marker.encode(),b'POLL_TEMP_PASS',command.encode(),1+29*groups

def failure_line(serial):
    prefix=b'POLL_TEMP_FAIL'
    if prefix in serial:return 'temporary-mask assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)
def incomplete_failure_line(serial):
    prefix=b'POLL_TEMP_FAIL';return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def validate_cases(span,arch,linux=False):
    if arch not in LANES or linux and arch!='x86_64':raise ValueError('unsupported temporary-mask case architecture')
    if error:=failure_line(span):raise ValueError(error)
    if linux and KERNEL_PREFIX in span:raise ValueError('Linux reference cannot contain native poll diagnostics')
    events=[] if linux else native_events(span,arch);event_lines={r['line']:r for r in events}
    if len(event_lines)!=len(events):raise ValueError('duplicate native poll diagnostic')
    targets={(row['pid'],row['tid']) for line in span.splitlines() if BEGIN.fullmatch(line) for row in (parsed(BEGIN,line),)}
    selected={r['line'] for r in events if (r['pid'],r['tid']) in targets}
    incidental=[r for r in events if r['line'] not in selected]
    if any(r['tag']=='OK_NATIVE_POLL_SIGNAL' for r in incidental):raise ValueError('incidental poll signal publication')
    aggregate=probe_spec(arch,'poll-temporary-masks')[0]
    if linux:aggregate=aggregate.replace(b'POLL_TEMP_PASS',b'POLL_TEMP_LINUX_REFERENCE_PASS')
    if span.splitlines().count(aggregate)!=1:raise ValueError('missing unique exact temporary-mask aggregate')
    lines=[line for line in span.splitlines() if line in selected or GUEST_PREFIX in line and line!=aggregate]
    cursor=0;maximum=(1<<(32 if arch in WORD32 else 64))-1;word_bytes=4 if arch in WORD32 else 8
    forms=2 if arch in ('arm32','ppc') else 1;mips=arch.startswith('mips');usr1,usr2=(16,17) if mips else (10,12)
    owners={};tids=set();counts=dict(cases=0,groups=0,initial_waits=0,nested_waits=0,outer_handlers=0,nested_handlers=0,main_sends=0,immediate=0,eintr=0,efault=0,ready=0,timeout=0,cancelled=0,fatal_children=0,exit_children=0,handler_exit_children=0,thread_exits=0,linux_observed_waits=0)
    def take(pattern):
        nonlocal cursor
        if cursor>=len(lines):raise ValueError('truncated temporary-mask case')
        row=parsed(pattern,lines[cursor]) if pattern not in NATIVE_PATTERNS else event_lines.get(lines[cursor])
        if row is None or not pattern.fullmatch(lines[cursor]):raise ValueError('unexpected temporary-mask/native event order')
        cursor+=1;return row
    for variant,(number,is_select,wide) in enumerate(LANES[arch]):
      for form in range(forms):
       for restart in range(2):
        counts['groups']+=1
        for case in list(range(21))+[24,21,22,23]:
            def guest(pattern):
                row=take(pattern)
                if tuple(row[k] for k in ('arch','variant','form','restart','case'))!=(arch,variant,form,restart,case):raise ValueError('temporary-mask event changed active case')
                return row
            begin=guest(BEGIN);pid,tid=begin['pid'],begin['tid'];kind='select' if is_select else 'poll';duration=0 if case==6 else 160000000 if case in (5,18) else 500000000
            original=132+(512 if mips else 0)+(case not in (1,3));temporary=66+(256 if mips else 0)+(case==14)
            width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
            if (not 0<pid<=0xffffffff or not 0<tid<=0xffffffff or pid==tid or tid in tids or
                (begin['syscall'],begin['kind'],begin['duration'],begin['width'],begin['bytes'],begin['original'],begin['temporary'])!=(number,kind,duration,64 if wide else 32,16 if mips else 8,original,temporary) or
                not 0<=begin['fd']<31 or any(not 0<begin[k]<=maximum-1024 or begin[k]%word_bytes for k in ('output','timeout','maskptr','pair')) or
                not instruction(arch,begin['site'],form==1) or not instruction(arch,begin['resume'],form==1) or begin['resume']-begin['site']!=width):raise ValueError('invalid temporary-mask owner, ABI, pointers or masks')
            tids.add(tid);group=(variant,form,restart,case if case in (21,22,23) else 0)
            if group in owners and owners[group]!=pid:raise ValueError('temporary-mask child changed identity')
            owners[group]=pid
            def send(signal):
                row=guest(SEND)
                if (row['pid'],row['tid'],row['signal'])!=(pid,tid,signal):raise ValueError('temporary-mask signal changed recipient')
                counts['main_sends']+=1
            if case==15:send(usr1)
            attempt=guest(ATTEMPT);args=[attempt['a'+str(i)] for i in range(6)]
            expected=[begin['fd']+1,begin['output'],0,0,begin['timeout'],begin['pair']] if is_select else [begin['output'],1,begin['timeout'],begin['maskptr'],16 if mips else 8,0]
            if case==8 and is_select:expected[0]=31
            if case==9 and not is_select:expected[3]=1
            if case==10 and not is_select:expected[4]-=1
            if case==11:expected[4 if is_select else 2]=1
            if case==11 and not is_select:expected[4]-=1
            if case==12:expected[1 if is_select else 0]=1
            if (attempt['pid'],attempt['tid'])!=(pid,tid) or args!=expected:raise ValueError('temporary-mask attempted argument vector changed')
            current=None
            def arm(nested=False):
                nonlocal current
                if not linux:
                    current=take(ARM)
                    if (current['pid'],current['tid'],current['syscall'],current['kind'],current['count'],current['pc'])!=(pid,tid,number,kind,1,begin['resume']) or not current['deadline']:raise ValueError('temporary-mask wait lacks exact owned arm')
                if linux and (case!=15 or nested):
                    row=guest(LINUX_WAIT)
                    if (row['nested'],row['pid'],row['tid'],row['syscall'])!=(int(nested),pid,tid,number):raise ValueError('Linux observed wait changed target')
                    counts['linux_observed_waits']+=1
                counts['nested_waits' if nested else 'initial_waits']+=1
            def terminal(reason,result,signal=usr1):
                if not linux:
                    row=take(RETIRE)
                    if row['arm'] is not current or (row['reason'],row['result'])!=(reason,result):raise ValueError('temporary-mask retirement changed owner/cause/result')
                    if reason=='interrupted':
                        event=take(SIGNAL)
                        if event['terminal'] is not row or event['signal']!=signal or event['result']!=('efault' if result==-14 else 'eintr'):raise ValueError('temporary-mask signal completion disagrees')
                counts[('efault' if result==-14 else 'eintr') if reason=='interrupted' else reason]+=1
            def action(name):
                if guest(ACTION)['action']!=name:raise ValueError('temporary-mask action differs from case')
            def context(tag,depth=1,edited=False):
                row=guest(HANDLER);fault=case==3 and not is_select and depth==1;code=14 if fault else 4
                expected_saved=(temporary|1) if depth==2 else (original&~4)|8 if edited else original
                expected_active=(temporary&~2)|6 if depth==2 else original|1 if fault else (temporary|8)&~1 if case==20 else temporary|1
                base={'tag','line','arch','variant','form','restart','case','pid','tid','depth','pc','result','saved','active'}
                extra={'a3'} if mips else {'cr','diagnostic_result'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set()
                if set(row)!=base|extra or (row['tag'],row['pid'],row['tid'],row['depth'],row['pc'],row['result'],row['saved'],row['active'])!=(tag,pid,tid,depth,begin['resume'],code if mips or arch=='ppc' else maximum+1-code,expected_saved,expected_active):raise ValueError('temporary-mask saved/active frame, result or owner changed')
                if mips and row['a3']!=1:raise ValueError('temporary-mask MIPS error flag missing')
                if arch=='ppc' and (not 0<=row['cr']<=maximum or not row['cr']&0x10000000 or row['diagnostic_result']!=maximum+1-code):raise ValueError('temporary-mask PPC diagnostics changed')
                if arch=='arm32' and (not 0<=row['cpsr']<=maximum or row['cpsr']&0x0700ffdf!=0x10 or bool(row['cpsr']&0x20)!=bool(form)):raise ValueError('temporary-mask ARM user state changed')
                return row
            caught=case<=3 or case in (15,16,17,19,20,23,24)
            if case<=5 or case>=13:
                arm()
                if case in (2,3,19):action({2:'mutate-mask',3:'protect-output',19:'protect-mask'}[case])
                if caught:
                    if case!=15:send(usr1)
                    terminal('interrupted',-14 if case==3 and not is_select else -4);context('POLL_TEMP_HANDLE');counts['outer_handlers']+=1
                    if case==16:
                        context('POLL_TEMP_NEST_BEGIN');arm(True);send(usr2);terminal('interrupted',-4,usr2);context('POLL_TEMP_NESTED',2);counts['nested_handlers']+=1;context('POLL_TEMP_NEST_RETURN')
                    if case==23:context('POLL_TEMP_HANDLER_EXIT')
                    elif case==24:counts['thread_exits']+=1
                    else:context('POLL_TEMP_HANDLER_RETURN',edited=case==17)
                elif case in (21,22):
                    if case==21:send(usr1)
                    else:action('exit-group')
                    terminal('cancelled',-4)
                elif case in (5,18):
                    if case==18:action('mutate-timeout')
                    terminal('timeout',0)
                else:
                    if case in (13,14):send(usr1)
                    action('ready');terminal('ready',1)
            else:counts['immediate']+=1
            if case in (21,22,23):
                row=guest(EXIT_PASS)
                if (row['pid'],row['signal'])!=(pid,usr1 if case==21 else 0):raise ValueError('temporary-mask parent exit status changed')
                counts[{21:'fatal_children',22:'exit_children',23:'handler_exit_children'}[case]]+=1
            else:
                if case!=24:
                    row=guest(RETURN);result=-(14 if case==3 and not is_select else 4) if caught else 0 if case in (5,6,18) else -9 if case==8 and is_select else -14 if case in (9,11,12) else -22 if case==10 else 1
                    restored=(original&~4)|8 if case==17 else original
                    if (row['result'],row['error'],row['restored'])!=(result,111,restored) or not 0<=row['elapsed']<5000000000 or not 0<=row['remaining']<=duration:raise ValueError('temporary-mask return/restoration/deadline changed')
                    if caught and row['elapsed']>=duration or case in (5,18) and not duration<=row['elapsed']<duration+1000000000 or case in (5,6,18) and row['remaining']!=0:raise ValueError('temporary-mask wait lost its original deadline')
                    if case==14 and guest(PENDING)['mask']!=1:raise ValueError('temporary-mask blocked signal lost pending state')
                guest(END)
            counts['cases']+=1
    if cursor!=len(lines) or len(set(owners.values()))!=4*counts['groups']:raise ValueError('unexpected temporary-mask records/child reuse')
    if span.rfind(aggregate)<span.rfind(b'POLL_TEMP_EXIT_PASS'):raise ValueError('aggregate precedes lifecycle completion')
    counts['incidental_arms']=sum(r['tag']=='OK_NATIVE_POLL_ARM' for r in incidental)
    return counts

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='poll-temporary-masks'):
    serial, boundaries = normalize_transcript(serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    baseline_begin, probe_begin, probe_mid, probe_end, native_begin = boundaries
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated temporary-mask command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('temporary-mask boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final temporary-mask prompt')
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
        incidental = pipe_events(span,arch) + futex_events(span,arch,allow_signal=False) + native_events(span,arch,allow_signal=False) + child_events(span,arch, baseline=child_baseline)
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
            raise ValueError('missing unique ordered poll-temporary-masks/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong temporary-mask image source')
        pipe_events(span,arch)
        futex_events(span,arch,allow_signal=False)
        child_events(span,arch, baseline=child_baseline)
        observations.append(validate_cases(span,arch))
        extra = tuple(line for line in lines if any(p.fullmatch(line) for p in PATTERNS+PIPE_PATTERNS+FUTEX_PATTERNS+CHILD_PATTERNS+LIFECYCLE_PATTERNS))
        validate_command(span,command,marker,extra)
    pipe_events(boot,arch)
    futex_events(boot,arch,allow_signal=False)
    native_events(boot,arch,allow_signal=False)
    if any(GUEST_PREFIX in line and KERNEL_PREFIX not in line for span in (boot,baseline,native) for line in span.splitlines()):
        raise ValueError('temporary-mask completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(before == after for before,after in zip(frame_rows,frame_rows[1:])):
        raise ValueError('duplicate temporary-mask frame-accounting snapshot')
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty temporary-mask boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('temporary-mask commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        final_snapshots(span)
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('temporary-mask accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] != int(bool(child_baseline)) or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('temporary-mask command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('temporary-mask command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=leases,
                image_publications_per_run=1,scope='actual-user-private-poll-temporary-masks',
                observations=observations,owned_poll_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_poll_restart=False,temporary_masks=True,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
