"""SDK31 saved-ID guest evidence; parsing alone does not execute credentials."""
import json
import re
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import decode_frames, failure_line as general_failure, require_hash, relative_file
from entry_stack_evidence import decode_stacks, COUNTERS
from native_signal_delivery_x86_64_evidence import IMAGE, validate_command

MARKER = b'CREDENTIALS_PASS {arch} reversible=1 permanent_child=1 fork=1 failed_exec=1 saved_exec=1 file_permissions=1 failure_atomic=1 thread_gate=2 high_uid=4'
CHILD = b'CREDENTIALS_EXEC_CHILD_PASS {arch} saved_reset=1 permanent=1'

def probe_spec(arch, kind):
    if arch not in ARCH_TRIPLES or kind != 'credentials':
        raise ValueError('unsupported saved-ID guest profile')
    return (MARKER.replace(b'{arch}', arch.encode()), b'CREDENTIALS_PASS',
            ('/bin/native-credentials-'+arch.replace('_','-')).encode(), 4)

def incomplete_failure_line(serial):
    prefix = b'CREDENTIALS_FAIL'
    return prefix in serial and b'\n' not in serial[serial.index(prefix):]

def failure_line(serial):
    prefix = b'CREDENTIALS_FAIL'
    if prefix in serial:
        return 'saved-ID assertion failed: '+serial[serial.index(prefix):].split(b'\n',1)[0].decode(errors='replace')
    return general_failure(serial)

def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    if arch not in ARCH_TRIPLES or mode != 'debug':
        raise ValueError('saved-ID execution requires an explicit Debug profile')
    require_hash(sdk/'manifest.json', expected, 'SDK manifest')
    require_hash(compiler, compiler_hash, 'SDK compiler')
    manifest = json.loads((sdk/'manifest.json').read_text())
    if not isinstance(manifest.get('files'),dict):
        raise ValueError('SDK missing artifact inventory')
    for name in manifest['files']:
        relative_file(sdk,name)
    manifest = validate_sdk(sdk,arch,mode,compiler)
    if manifest['abi_version'] != 31 or manifest['compiler'].get('family') != 'gcc':
        raise ValueError('saved-ID execution requires SDK31 GCC ABI')
    return manifest

def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch, kind='credentials'):
    marker, prefix, command, leases = probe_spec(arch,kind)
    child = CHILD.replace(b'{arch}',arch.encode())
    boundaries = (baseline_begin,probe_begin,probe_mid,probe_end,native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated credential command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('credential boundaries require complete shell prompts')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ',1)
    if len(tail)!=2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n',tail[1])):
        raise ValueError('unexpected bytes after final credential prompt')
    boot,baseline = serial[:baseline_begin],serial[baseline_begin:probe_begin]
    first,second,native = serial[probe_begin:probe_mid],serial[probe_mid:probe_end],serial[native_begin:]
    for boot_prefix,expected in ((b'OK_SYSTEM_GUI boot=',b'OK_SYSTEM_GUI boot=complete'),
        (b'OK_STORAGE ',b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        rows = [line for line in boot.splitlines(keepends=True) if boot_prefix in line]
        if len(rows)!=1 or rows[0] not in (expected+b'\n',expected+b'\r\n'):
            raise ValueError('missing unique complete distribution boot')
    for span in (baseline,native):
        validate_command(span,b'hello | cat',b'hello from ObfuscationOS userland')
        if span.splitlines().count(b'hello from ObfuscationOS userland')!=1:
            raise ValueError('missing unique native pipeline')
    source = b'linker' if arch in ('loongarch64','mips','mips64') else b'firmware'
    for span in (first,second):
        lines = [line for line in span.splitlines() if line]
        images = [index for index,line in enumerate(lines) if IMAGE.fullmatch(line)]
        if (len(images)!=2 or lines.count(marker)!=1 or lines.count(child)!=1 or
            images[0]!=(1 if lines[0]==command else 0) or
            not images[0]<images[1]<lines.index(child)<lines.index(marker)):
            raise ValueError('missing unique ordered credentials/exec/image completion')
        if any(IMAGE.fullmatch(lines[index])[1]!=source for index in images):
            raise ValueError('wrong credential image source')
        validate_command(span,command,marker,(child,))
    if any(word in span for word in (prefix,b'CREDENTIALS_EXEC_CHILD_PASS') for span in (boot,baseline,native)):
        raise ValueError('credential completion outside dedicated commands')
    frame_rows = decode_frames(serial,arch);stack_rows = decode_stacks(serial)
    if any(frame_rows[0][key] for key in ('used','allocations','releases')) or any(stack_rows[0].values()):
        raise ValueError('missing empty credential boot accounting')
    spans = (baseline,first,second,native)
    frame_ends = [decode_frames(span,arch)[-1] for span in spans]
    stack_ends = [decode_stacks(span)[-1] for span in spans]
    base = frame_ends[0];live = stack_ends[0]['leased']
    if live==0 or any(row['leased']!=live for row in stack_ends):
        raise ValueError('credential commands did not retire to live shell lease baseline')
    previous_frame=decode_frames(boot,arch)[-1];previous_stack=decode_stacks(boot)[-1]
    commands=[]
    for index,span in enumerate(spans):
        success=prefix if index in (1,2) else b'hello from ObfuscationOS userland'
        for prefix_record in (b'OK_NATIVE_FRAMES',b'OK_ENTRY_STACKS'):
            if span.rfind(prefix_record)<=span.rfind(success):
                raise ValueError('credential accounting must follow command success')
        frame,stack=frame_ends[index],stack_ends[index]
        if (frame['objects'] or frame['user']!=base['user'] or frame['allocations']<=previous_frame['allocations'] or
            frame['releases']<=previous_frame['releases']):
            raise ValueError('credential command allocation did not retire')
        delta={key:stack[key]-previous_stack[key] for key in COUNTERS}
        minimum=leases if index in (1,2) else 1
        if delta['reservations']<minimum or delta['releases']<minimum or delta['syscalls']<=0 or delta['activations']<=0 or delta['faults']:
            raise ValueError('credential command lacks fresh owned entries or has a captured fault')
        commands.append(delta);previous_frame=frame;previous_stack=stack
    return dict(runs=2,kind=kind,architecture=arch,sdk_abi=31,minimum_leases_per_run=4,
                image_publications_per_run=2,scope='actual-user-single-live-thread-identity-mutation',
                reversible='passed',permanent_child='passed',fork='passed',failed_exec='passed',saved_exec='passed',
                file_permissions='passed',failure_atomic='passed',thread_gate='passed',high_unsigned_ids=4,
                per_thread_credentials=False,libc_thread_sync=False,physical=False,smp=False,
                baseline=base,final=frame_ends[-1],records=len(frame_rows),
                entry_stacks=dict(baseline=stack_ends[0],first=stack_ends[1],second=stack_ends[2],
                                  final=stack_ends[3],commands=commands,records=len(stack_rows)))
