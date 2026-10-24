"""SDK31 signal-mask probe admission; synthetic parsers do not execute signal-mask transitions."""
import re
from object_pressure_evidence import decode_frames, failure_line as general_failure, admit_sdk as admit_common_sdk
from entry_stack_evidence import decode_stacks, COUNTERS

MARKER = b'OK_MUSL_SIGNAL_MASKS raw=pass copies=pass clone=pass fork=pass exec=pass nonleader_exec=pass failed_exec=pass'
EXEC_MARKERS = (b'OK_MUSL_SIGNAL_EXEC caller=leader mask=pass',
                b'OK_MUSL_SIGNAL_EXEC caller=nonleader mask=pass')
IMAGE = re.compile(rb'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=[1-9][0-9]* physical_first=0x[0-9a-f]{16} physical_last=0x[0-9a-f]{16} owner=retained')


def validate_command(span, command, success):
    if span.count(b'oksh> ') != 1:
        raise ValueError('dedicated command must contain exactly one final shell prompt')
    output, _, _ = span.rpartition(b'oksh> ')
    first = True
    for raw in output.splitlines(keepends=True):
        if not raw.endswith(b'\n'):
            raise ValueError('incomplete command output line')
        line = raw[:-1].removesuffix(b'\r')
        if not line:
            continue
        if first and line == command:
            first = False
            continue
        first = False
        if (line == success or (success == MARKER and line in EXEC_MARKERS) or line.startswith(b'OK_NATIVE_FRAMES ') or
                line.startswith(b'OK_ENTRY_STACKS ') or IMAGE.fullmatch(line)):
            continue
        raise ValueError('unexpected output or command inside dedicated command span')


def failure_line(serial):
    if b'SIGNAL_MASK_FAIL' in serial:
        return 'signal-mask assertion failed: ' + serial[serial.index(b'SIGNAL_MASK_FAIL'):].split(b'\n', 1)[0].decode(errors='replace')
    return general_failure(serial)


def validate_probe(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch):
    boundaries = (baseline_begin, probe_begin, probe_mid, probe_end, native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end == native_begin < len(serial):
        raise ValueError('invalid dedicated command boundaries')
    if any(not serial[:value].endswith(b'oksh> ') for value in boundaries):
        raise ValueError('command boundary does not end at a complete shell prompt')
    if error := failure_line(serial):
        raise ValueError(error)
    tail = serial.rsplit(b'oksh> ', 1)
    if len(tail) != 2 or (tail[1] and not re.fullmatch(rb'qemu-system-[a-zA-Z0-9_-]+: terminating on signal 15 from pid [0-9]+ \((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?\)\r?\n', tail[1])):
        raise ValueError('unexpected bytes after the final shell prompt')
    boot = serial[:baseline_begin]
    baseline = serial[baseline_begin:probe_begin]
    first, second = serial[probe_begin:probe_mid], serial[probe_mid:probe_end]
    native = serial[native_begin:]
    for span in (baseline, native):
        validate_command(span, b'hello | cat', b'hello from ObfuscationOS userland')
    for span in (first, second):
        validate_command(span, b'native-signal-masks', MARKER)
    for prefix, expected in ((b'OK_SYSTEM_GUI boot=', b'OK_SYSTEM_GUI boot=complete'),
                             (b'OK_STORAGE ', b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none')):
        lines = [line for line in boot.splitlines(keepends=True) if prefix in line]
        if len(lines) != 1 or lines[0] not in (expected + b'\n', expected + b'\r\n'):
            raise ValueError('missing unique complete distribution boot evidence')
    for span in (baseline, native):
        lines = [line for line in span.splitlines(keepends=True) if b'hello from ObfuscationOS userland' in line]
        if len(lines) != 1 or lines[0] not in (b'hello from ObfuscationOS userland\n', b'hello from ObfuscationOS userland\r\n'):
            raise ValueError('missing unique complete dedicated native pipeline')
    for span in (first, second):
        lines = [line for line in span.splitlines(keepends=True) if b'OK_MUSL_SIGNAL_MASKS' in line]
        if len(lines) != 1 or lines[0] not in (MARKER+b'\n', MARKER+b'\r\n'):
            raise ValueError('missing unique complete probe success within each command')
    for span in (first, second):
        events = [line for line in span.splitlines(keepends=True) if b'OK_MUSL_SIGNAL_EXEC' in line]
        if len(events) != 2 or any(line not in (expected + b'\n', expected + b'\r\n') for line, expected in zip(events, EXEC_MARKERS)):
            raise ValueError('missing unique ordered leader/nonleader exec evidence')
        if span.rfind(EXEC_MARKERS[-1]) >= span.find(MARKER):
            raise ValueError('exec observer evidence must precede final probe success')
    if any(token in span for span in (boot, baseline, serial[probe_end:])
           for token in (b'OK_MUSL_SIGNAL_MASKS', b'OK_MUSL_SIGNAL_EXEC')):
        raise ValueError('probe success outside execution boundaries')
    rows = decode_frames(serial, arch)
    base = decode_frames(baseline, arch)[-1]
    if base['allocations'] <= decode_frames(boot, arch)[-1]['allocations']:
        raise ValueError('baseline pipeline has no independent allocation evidence')
    endings = [decode_frames(span, arch)[-1] for span in (first, second, native)]
    for index, span in enumerate((baseline, first, second, native)):
        success = b'OK_MUSL_SIGNAL_MASKS' if index in (1, 2) else b'hello from ObfuscationOS userland'
        if span.rfind(b'OK_NATIVE_FRAMES') <= span.rfind(success):
            raise ValueError('missing frame retirement after dedicated command output')
    if b'OK_NATIVE_FRAMES' in serial[probe_end:native_begin]:
        raise ValueError('frame activity outside dedicated command boundaries')
    if any(rows[0][key] for key in ('used', 'allocations', 'releases')):
        raise ValueError('missing empty boot baseline')
    for row in [base, *endings]:
        if row['objects'] or row['user'] != base['user']:
            raise ValueError('probe did not retire object/user allocations')
    previous = base
    for row in endings:
        if row['allocations'] <= previous['allocations'] or row['releases'] <= previous['releases']:
            raise ValueError('missing allocation and retirement in dedicated command')
        previous = row
    return dict(runs=2, raw='passed', copies='passed', clone='passed', fork='passed',
                exec='passed', nonleader_exec='passed', failed_exec='passed', minimum_leases_per_run=6,
                baseline=base, final=endings[-1], records=len(rows), accounting_version=2)


def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    manifest = admit_common_sdk(sdk, expected, arch, mode, compiler, compiler_hash)
    if manifest.get("abi_version") != 31 or manifest.get("compiler", {}).get("family") != "gcc":
        raise ValueError("signal-mask probe requires SDK31 GCC ABI")
    return manifest


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch):
    result = validate_probe(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch)
    rows = decode_stacks(serial)
    if any(rows[0].values()):
        raise ValueError('missing empty entry-stack boot baseline')
    boot = decode_stacks(serial[:baseline_begin])
    spans = (serial[baseline_begin:probe_begin], serial[probe_begin:probe_mid],
             serial[probe_mid:probe_end], serial[native_begin:])
    if b'OK_ENTRY_STACKS' in serial[probe_end:native_begin]:
        raise ValueError('entry-stack activity outside dedicated command boundaries')
    endings = [decode_stacks(span)[-1] for span in spans]
    for index, span in enumerate(spans):
        success = b'OK_MUSL_SIGNAL_MASKS' if index in (1, 2) else b'hello from ObfuscationOS userland'
        if span.rfind(b'OK_ENTRY_STACKS') <= span.rfind(success):
            raise ValueError('missing entry-stack retirement after dedicated command output')
    baseline = endings[0]
    if baseline['leased'] == 0 or any(row['leased'] != baseline['leased'] for row in endings):
        raise ValueError('dedicated command did not return to live shell lease baseline')
    previous = boot[-1]
    commands = []
    for index, row in enumerate(endings):
        delta = {key: row[key] - previous[key] for key in COUNTERS}
        # Probe, inheritance peer/fork child, two exec children and exec peer.
        minimum = result['minimum_leases_per_run'] if index in (1, 2) else 1
        if (delta['reservations'] < minimum or delta['releases'] < minimum or
                delta['activations'] <= 0 or delta['syscalls'] <= 0):
            raise ValueError('dedicated command lacks fresh owned entries, syscalls or lease reuse')
        commands.append(delta)
        previous = row
    result['entry_stacks'] = dict(version=1, scope='actual-user', cpu=0, smp=False,
        guards='mapped-canaries', capacity=128, usable_bytes=65536, backing_bytes=9437184,
        boot=rows[0], baseline=baseline, first=endings[1], second=endings[2], final=endings[3],
        commands=commands, minimum_probe_reservations=result['minimum_leases_per_run'], records=len(rows))
    return result
