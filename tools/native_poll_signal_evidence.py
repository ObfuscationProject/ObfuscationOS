"""Private copied poll/select signal qualification; all raw and libc ABI lanes."""
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
from native_poll_events import native_events,parse as parsed,ARM,RETIRE,SIGNAL,PATTERNS as NATIVE_PATTERNS,PREFIX as KERNEL_PREFIX

KEY=rb'arch=([a-z0-9_]+) variant=([0-9]|10) form=([01]) case=([0-9]|1[0-8])'
OWNER=rb' pid=([0-9]+) tid=([0-9]+)'
BEGIN=re.compile(rb'POLL_SIGNAL_CASE_BEGIN '+KEY+OWNER+rb' syscall=([0-9]+) kind=(poll|select) libc=([01]) timed=([01]) duration=([0-9]+) site=([0-9]+) resume=([0-9]+) count=([12]) fd=([0-9]+) output=([0-9]+) timeout=([0-9]+) width=(32|64) packed=([01])')
ATTEMPT=re.compile(rb'POLL_SIGNAL_ATTEMPT '+KEY+OWNER+rb' a0=([0-9]+) a1=([0-9]+) a2=([0-9]+) a3=([0-9]+) a4=([0-9]+) a5=([0-9]+)')
SEND=re.compile(rb'POLL_SIGNAL_SEND '+KEY+OWNER+rb' signal=([0-9]+)')
READY=re.compile(rb'POLL_SIGNAL_READY '+KEY+rb' source=(original|replacement)')
MUTATE_INPUT=re.compile(rb'POLL_SIGNAL_MUTATE_INPUT '+KEY)
MUTATE_TIMEOUT=re.compile(rb'POLL_SIGNAL_MUTATE_TIMEOUT '+KEY)
REUSE=re.compile(rb'POLL_SIGNAL_REUSE '+KEY+rb' fd=([0-9]+) replacement=([0-9]+)')
PROTECT=re.compile(rb'POLL_SIGNAL_PROTECT '+KEY+rb' target=(output|timeout)')
UNMASK=re.compile(rb'POLL_SIGNAL_UNMASK '+KEY)
RETURN=re.compile(rb'POLL_SIGNAL_RETURN '+KEY+rb' result=(-?[0-9]+) error=([0-9]+) elapsed=([0-9]+) revents=([0-9]+) mask=([0-9]+) remaining=(-?[0-9]+)')
END=re.compile(rb'POLL_SIGNAL_CASE_PASS '+KEY)
EXIT=re.compile(rb'POLL_SIGNAL_EXIT '+KEY+rb' pid=([0-9]+)')
EXIT_PASS=re.compile(rb'POLL_SIGNAL_EXIT_PASS '+KEY+rb' pid=([0-9]+) signal=([0-9]+)')
HANDLER=re.compile(rb'POLL_SIGNAL_(HANDLE|HANDLER_RETURN|NESTED) '+KEY+OWNER+rb' pc=([0-9]+) inspected=([01])(?: result=([0-9]+))?(?: a3=([0-9]+)| cr=([0-9]+) diagnostic_result=([0-9]+)| cpsr=([0-9]+))?')
GUEST_PREFIX=b'POLL_SIGNAL_'
PATTERNS=(BEGIN,ATTEMPT,SEND,READY,MUTATE_INPUT,MUTATE_TIMEOUT,REUSE,PROTECT,UNMASK,RETURN,END,EXIT,EXIT_PASS,HANDLER)+NATIVE_PATTERNS

def probe_spec(arch,kind):
    if arch not in LANES or kind!='poll-signals':raise ValueError('unsupported native poll signal profile')
    lanes=LANES[arch];forms=2 if arch in ('arm32','ppc') else 1;groups=sum(1 if lane[4] else forms for lane in lanes)
    command='/bin/native-poll-signal-'+('la64' if arch=='loongarch64' else arch.replace('_','-'))
    marker=f'POLL_SIGNAL_PASS arch={arch} variants={len(lanes)} groups={groups} cases={19*groups} waits={17*groups} parent=1'
    return marker.encode(),b'POLL_SIGNAL_PASS',command.encode(),1+22*groups
def failure_line(serial):
    prefix=b'POLL_SIGNAL_FAIL'
    if prefix in serial:return 'poll signal assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)
def incomplete_failure_line(serial):
    prefix=b'POLL_SIGNAL_FAIL';return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def validate_cases(span,arch):
    events=native_events(span,arch);event_lines={row['line']:row for row in events}
    if len(event_lines)!=len(events):raise ValueError('duplicate poll object diagnostic')
    targets={(row['pid'],row['tid']) for line in span.splitlines() if BEGIN.fullmatch(line) for row in (parsed(BEGIN,line),)}
    selected={row['line'] for row in events if (row['pid'],row['tid']) in targets}
    incidental=[row for row in events if row['line'] not in selected]
    if any(row['tag']=='OK_NATIVE_POLL_SIGNAL' for row in incidental):raise ValueError('incidental wait claims poll signal delivery')
    lines=[line for line in span.splitlines() if line in selected or
        GUEST_PREFIX in line and KERNEL_PREFIX not in line and not line.startswith(b'POLL_SIGNAL_PASS')]
    cursor=0;maximum=(1<<(32 if arch in WORD32 else 64))-1;forms=2 if arch in ('arm32','ppc') else 1
    owners={};tids=set();counts=dict(cases=0,variants=len(LANES[arch]),groups=0,initial_waits=0,eintr=0,efault=0,
        ready_retirements=0,timeout_retirements=0,cancelled_retirements=0,outer_handlers=0,nested_handlers=0,main_sends=0,
        fatal_children=0,exit_children=0,immediate=0,incidental_arms=sum(row['tag']=='OK_NATIVE_POLL_ARM' for row in incidental))
    def take(pattern):
        nonlocal cursor
        if cursor>=len(lines):raise ValueError('truncated poll signal case')
        row=parsed(pattern,lines[cursor]);cursor+=1;return event_lines.get(row['line'],row)
    for variant,lane in enumerate(LANES[arch]):
      number,interface,wide,packed,libc=lane;kind='select' if interface>=2 else 'poll'
      for form in range(1 if libc else forms):
        counts['groups']+=1
        for case in range(19):
            def guest(pattern):
                row=take(pattern)
                if tuple(row[k] for k in ('arch','variant','form','case'))!=(arch,variant,form,case):raise ValueError('poll event changed active case')
                return row
            begin=guest(BEGIN);pid,tid=begin['pid'],begin['tid'];timed=case in (2,3,7,8,9,11,14,15)
            caught=case<=5 or case in (7,8,14);duration=0 if case==15 else 160000000 if case in (9,11) else 500000000
            width=2 if arch in ('i386','x86_64') or arch=='arm32' and form and not libc else 4
            if (not 0<pid<=0xffffffff or not 0<tid<=0xffffffff or pid==tid or tid in tids or
                    (begin['syscall'],begin['kind'],begin['libc'],begin['timed'],begin['duration'],begin['count'],begin['width'],begin['packed'])!=(number,kind,libc,int(timed),duration,1 if kind=='select' else 2,64 if wide else 32,packed) or
                    not 0<=begin['fd']<32 or not 0<begin['output']<=maximum-128 or begin['output']%8 or
                    bool(begin['timeout'])!=timed or not 0<=begin['timeout']<=maximum-32 or begin['timeout']%8 or
                    not instruction(arch,begin['site'],form==1 and not libc) or not instruction(arch,begin['resume'],form==1 and not libc) or begin['resume']-begin['site']!=width):
                raise ValueError('invalid poll case owner, ABI, input or instruction labels')
            tids.add(tid);group=(variant,form,0 if case<17 else case)
            if group in owners and owners[group]!=pid:raise ValueError('poll variant/form changed owned child')
            owners[group]=pid;attempt=guest(ATTEMPT)
            args=[attempt['a'+str(i)] for i in range(6)]
            if (attempt['pid'],attempt['tid'])!=(pid,tid) or any(not 0<=v<=maximum for v in args):raise ValueError('poll attempt changed owner or word width')
            expected=[0]*6
            if kind=='poll':expected=[begin['output'],2,duration//1000000 if timed else maximum,0,0,0] if interface==0 else [begin['output'],2,begin['timeout'],0,16 if arch.startswith('mips') else 8,0]
            elif packed:
                if not 0<args[0]<=maximum-5*(4 if arch in WORD32 else 8) or args[0]%(4 if arch in WORD32 else 8):raise ValueError('invalid packed select argument block')
                expected=[args[0],0,0,0,0,0]
            else:expected=[begin['fd']+1,begin['output'],0,0,begin['timeout'],0]
            if args!=expected:raise ValueError('poll attempt changed original argument vector')
            current=None
            def terminal(reason,result):
                row=take(RETIRE)
                if current is None or row['arm'] is not current or (row['reason'],row['result'])!=(reason,result):raise ValueError('poll terminal lost current owned completion')
                if reason!='interrupted':counts[reason+'_retirements']+=1
                return row
            def handler(signal_event=None):
                row=guest(HANDLER);base={'tag','line','arch','variant','form','case','pid','tid','pc','inspected'}
                extra=({'a3'} if arch.startswith('mips') else {'cr','diagnostic_result'} if arch=='ppc' else {'cpsr'} if arch=='arm32' else set()) if caught else set()
                if (row['tag']!='POLL_SIGNAL_HANDLE' or (row['pid'],row['tid'],row['inspected'])!=(pid,tid,int(caught)) or
                        set(row)!=base|({'result'} if caught else set())|extra or not instruction(arch,row['pc'])):raise ValueError('invalid poll handler context/owner')
                if caught:
                    code=14 if case==7 and kind=='poll' else 4
                    value=code if arch.startswith('mips') or arch=='ppc' else maximum+1-code
                    if signal_event is None or row['pc']!=current['pc'] or row['result']!=value:raise ValueError('poll handler saved result/continuation disagrees with retirement')
                    if arch.startswith('mips') and row['a3']!=1:raise ValueError('poll MIPS a3 lost error result flag')
                    if arch=='ppc' and (not 0<=row['cr']<=maximum or not row['cr']&0x10000000 or row['diagnostic_result']!=maximum+1-code):raise ValueError('poll PPC saved completion diagnostics disagree')
                    if arch=='arm32' and (not 0<=row['cpsr']<=maximum or row['cpsr']&0x0700ffdf!=0x10 or not instruction(arch,row['pc'],bool(row['cpsr']&0x20)) or not libc and bool(row['cpsr']&0x20)!=bool(form)):raise ValueError('poll handler lost legal ARM user instruction state')
                counts['outer_handlers']+=1
                if case==14:
                    nested=guest(HANDLER)
                    if nested['tag']!='POLL_SIGNAL_NESTED' or set(nested)!=base or (nested['pid'],nested['tid'],nested['inspected'])!=(pid,tid,0) or not instruction(arch,nested['pc']):raise ValueError('poll nested handler changed owner/context')
                    counts['nested_handlers']+=1
                returned=guest(HANDLER)
                if returned['tag']!='POLL_SIGNAL_HANDLER_RETURN' or {k:v for k,v in returned.items() if k not in ('tag','line')}!={k:v for k,v in row.items() if k not in ('tag','line')}:raise ValueError('poll saved context unexpectedly changed')
            def send(delivered=True):
                row=guest(SEND)
                if (row['pid'],row['tid'],row['signal'])!=(pid,tid,16 if arch.startswith('mips') else 10):raise ValueError('poll signal changed directed recipient')
                counts['main_sends']+=1
                if delivered:
                    event=None
                    if caught:
                        fault=case==7 and kind=='poll';retired=terminal('interrupted',-14 if fault else -4);event=take(SIGNAL)
                        if event['terminal'] is not retired or event['result']!=('efault' if fault else 'eintr'):raise ValueError('poll signal label contradicts actual completion')
                        counts['efault' if fault else 'eintr']+=1
                    handler(event)
            def ready(replacement=False):
                row=guest(READY)
                if row['source']!=('replacement' if replacement else 'original'):raise ValueError('poll readiness used wrong description source')
                if not replacement:terminal('ready',1)
            def returned():
                row=guest(RETURN);result=-(14 if case==7 and kind=='poll' else 4) if caught else 0 if case in (9,11,15) else 1
                mask=0 if kind=='poll' or case==4 or result==0 else 1<<begin['fd']
                revents=0 if kind=='select' else 0x3333 if case==7 else 1 if result==1 else 0
                if (row['result'],row['error'],row['mask'],row['revents'])!=(-1 if libc and result<0 else result,-result if libc and result<0 else 111,mask,revents) or not 0<=row['elapsed']<5000000000:raise ValueError('poll raw/libc result, errno or copied output differs from case')
                if timed and caught and row['elapsed']>=duration or case in (9,11) and not duration<=row['elapsed']<duration+1000000000:raise ValueError('poll completion rebased or lost original deadline')
                left=row['remaining']
                if interface==0:
                    if left!=-1:raise ValueError('scalar poll falsely claims timeout-memory output')
                elif libc or not timed or case==8:
                    if left!=(2000000000 if case==9 else duration):raise ValueError('poll timeout memory unexpectedly changed')
                elif not 0<=left<=duration or case in (9,11,15) and left!=0 or interface==2 and left%1000:raise ValueError('poll copied timeout writeback is invalid')
            if case<15 or case>=17:
                current=take(ARM)
                if (current['pid'],current['tid'],current['syscall'],current['kind'],current['count'])!=(pid,tid,number,kind,begin['count']) or bool(current['deadline'])!=timed or not libc and current['pc']!=begin['resume']:raise ValueError('missing exact owned poll arm before guest action')
                counts['initial_waits']+=1
                if case==4:guest(MUTATE_INPUT)
                if case in (5,6):
                    row=guest(REUSE)
                    if row['fd']!=begin['fd'] or not 0<=row['replacement']<32 or row['replacement']==row['fd']:raise ValueError('poll fd reuse changed original descriptor identity')
                    if case==5:ready(True)
                if case==7:
                    if guest(PROTECT)['target']!='output':raise ValueError('poll protected wrong output mapping')
                if case==8 and not libc and interface!=0:
                    if guest(PROTECT)['target']!='timeout':raise ValueError('poll protected wrong timeout mapping')
                if caught:send();returned()
                elif case==9:guest(MUTATE_TIMEOUT);terminal('timeout',0);returned()
                elif case==11:terminal('timeout',0);returned();send()
                elif case in (17,18):
                    if case==17:send(False)
                    elif guest(EXIT)['pid']!=pid:raise ValueError('poll exit changed owner')
                    terminal('cancelled',-4);row=guest(EXIT_PASS)
                    if (row['pid'],row['signal'])!=(pid,(16 if arch.startswith('mips') else 10) if case==17 else 0):raise ValueError('poll parent lost fatal/exit child status')
                    counts['fatal_children' if case==17 else 'exit_children']+=1
                else:
                    if case in (12,13):send(False)
                    ready();returned()
                    if case==10:send()
                    if case==12:guest(UNMASK);handler()
            else:returned();counts['immediate']+=1
            if case<17:guest(END)
            counts['cases']+=1
    if cursor!=len(lines) or len(set(owners.values()))!=3*counts['groups']:raise ValueError('unexpected poll evidence or reused child identity')
    if span.rfind(probe_spec(arch,'poll-signals')[0])<span.rfind(b'POLL_SIGNAL_EXIT_PASS'):raise ValueError('poll aggregate precedes case completion')
    return counts

# Explicit syscall lanes from admitted musl headers; no runtime SDK glob selection.
LANES = {
    'aarch64': [(73, 1, 1, 0, 0), (72, 3, 1, 0, 0), (73, 0, 1, 0, 1), (73, 1, 1, 0, 1), (72, 2, 1, 0, 1), (72, 3, 1, 0, 1)],
    'arm32': [(168, 0, 0, 0, 0), (336, 1, 0, 0, 0), (414, 1, 1, 0, 0), (142, 2, 0, 0, 0), (335, 3, 0, 0, 0), (413, 3, 1, 0, 0), (168, 0, 0, 0, 1), (336, 1, 0, 0, 1), (142, 2, 0, 0, 1), (335, 3, 0, 0, 1)],
    'i386': [(168, 0, 0, 0, 0), (309, 1, 0, 0, 0), (414, 1, 1, 0, 0), (82, 2, 0, 1, 0), (142, 2, 0, 0, 0), (308, 3, 0, 0, 0), (413, 3, 1, 0, 0), (168, 0, 0, 0, 1), (309, 1, 0, 0, 1), (142, 2, 0, 0, 1), (308, 3, 0, 0, 1)],
    'loongarch64': [(73, 1, 1, 0, 0), (72, 3, 1, 0, 0), (73, 0, 1, 0, 1), (73, 1, 1, 0, 1), (72, 2, 1, 0, 1), (72, 3, 1, 0, 1)],
    'mips': [(4188, 0, 0, 0, 0), (4302, 1, 0, 0, 0), (4414, 1, 1, 0, 0), (4142, 2, 0, 0, 0), (4301, 3, 0, 0, 0), (4413, 3, 1, 0, 0), (4188, 0, 0, 0, 1), (4302, 1, 0, 0, 1), (4142, 2, 0, 0, 1), (4301, 3, 0, 0, 1)],
    'mips64': [(5007, 0, 1, 0, 0), (5261, 1, 1, 0, 0), (5022, 2, 1, 0, 0), (5260, 3, 1, 0, 0), (5007, 0, 1, 0, 1), (5261, 1, 1, 0, 1), (5022, 2, 1, 0, 1), (5260, 3, 1, 0, 1)],
    'ppc': [(167, 0, 0, 0, 0), (281, 1, 0, 0, 0), (414, 1, 1, 0, 0), (82, 2, 0, 1, 0), (142, 2, 0, 0, 0), (280, 3, 0, 0, 0), (413, 3, 1, 0, 0), (167, 0, 0, 0, 1), (281, 1, 0, 0, 1), (142, 2, 0, 0, 1), (280, 3, 0, 0, 1)],
    'rv32': [(414, 1, 1, 0, 0), (413, 3, 1, 0, 0), (414, 0, 0, 0, 1), (414, 1, 0, 0, 1), (413, 2, 0, 0, 1), (413, 3, 0, 0, 1)],
    'rv64': [(73, 1, 1, 0, 0), (72, 3, 1, 0, 0), (73, 0, 1, 0, 1), (73, 1, 1, 0, 1), (72, 2, 1, 0, 1), (72, 3, 1, 0, 1)],
    'x86_64': [(7, 0, 1, 0, 0), (271, 1, 1, 0, 0), (23, 2, 1, 0, 0), (270, 3, 1, 0, 0), (7, 0, 1, 0, 1), (271, 1, 1, 0, 1), (23, 2, 1, 0, 1), (270, 3, 1, 0, 1)],
}

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='poll-signals'):
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
            raise ValueError('missing unique ordered poll-signals/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong poll signal image source')
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
                image_publications_per_run=1,scope='actual-user-private-poll-signals',
                observations=observations,owned_poll_continuation=True,blocked_wait_interruption=True,
                process_directed_kill=False,caught_poll_restart=False,temporary_masks=False,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
