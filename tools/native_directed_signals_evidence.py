"""SDK31 directed signal guest evidence; parsing alone does not execute delivery."""
import json
import re
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import decode_frames, failure_line as general_failure, require_hash, relative_file
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command, incidental_events
from native_child_events import normalize_transcript, WAIT as CHILD_WAIT
from native_child_lifecycle_evidence import native_events as child_events, boot_baseline

MARKER = b'DIRECTED_SIGNALS_PASS {arch} cases=9 cross=6 denied=3 handlers=5 masked=1 coalesced=1 sender_snapshot=1 zero=9 zombie=9 reaped=9 target_actions=2 isolation=1'

def probe_spec(arch, kind):
    if arch not in ARCH_TRIPLES or kind != 'directed-signals':
        raise ValueError('unsupported directed-signal guest profile')
    return (MARKER.replace(b'{arch}', arch.encode()), b'DIRECTED_SIGNALS_PASS',
            ('/bin/native-directed-signals-'+('la64' if arch == 'loongarch64' else arch.replace('_','-'))).encode(), 19)

def incomplete_failure_line(serial):
    prefix = b'DIRECTED_SIGNALS_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def failure_line(serial):
    prefix = b'DIRECTED_SIGNALS_FAIL'
    if prefix in serial:
        return 'directed-signal assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)

def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    if arch not in ARCH_TRIPLES or mode != 'debug':
        raise ValueError('directed-signal execution requires an explicit Debug profile')
    require_hash(sdk/'manifest.json', expected, 'SDK manifest')
    require_hash(compiler, compiler_hash, 'SDK compiler')
    manifest = json.loads((sdk/'manifest.json').read_text())
    if not isinstance(manifest.get('files'),dict):
        raise ValueError('SDK missing artifact inventory')
    for name in manifest['files']:
        relative_file(sdk,name)
    manifest = validate_sdk(sdk,arch,mode,compiler)
    if manifest['abi_version'] != 31 or manifest['compiler'].get('family') != 'gcc':
        raise ValueError('directed-signal execution requires SDK31 GCC ABI')
    return manifest

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='directed-signals'):
    serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin) = normalize_transcript(
        serial, (baseline_begin, probe_begin, probe_mid, probe_end, native_begin))
    marker, prefix, command, leases = probe_spec(arch,kind)
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated directed signal command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('directed signal boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final directed signal prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    child_baseline = boot_baseline(boot, arch)
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        incidental = incidental_events(span,arch,child_baseline)
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland',tuple(e['line'] for e in incidental))
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=1 or lines.count(marker)!=1 or
            any(line!=command and not CHILD_WAIT.fullmatch(line) for line in lines[:images[0]]) or not images[0]<lines.index(marker)):
            raise ValueError('missing unique ordered directed-signals/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong directed signal image source')
        incidental = incidental_events(span,arch,child_baseline)
        validate_command(span,command,marker,tuple(e['line'] for e in incidental))
    if any(prefix in span for span in (boot,baseline,native)):
        raise ValueError('directed signal completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty directed signal boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('directed signal commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('directed signal accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] != int(bool(child_baseline)) or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('directed signal command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('directed signal command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=19,
                image_publications_per_run=1,scope='actual-user-private-directed-signals',
                cases=9,cross_process_allowed=6,permission_denied=3,handlers=5,
                masked=1,coalesced=1,sender_snapshot=1,zero=9,zombie=9,reaped=9,
                target_actions=2,process_isolation_canary=1,
                process_directed_kill=False,blocked_wait_interruption=False,
                job_control=False,production=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
