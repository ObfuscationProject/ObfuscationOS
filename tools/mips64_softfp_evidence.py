"""Admission of actual MIPS64 binary128 and musl stdio guest checks."""
import re
from object_pressure_evidence import decode_frames, failure_line as general_failure

MARKER = b'OK_MUSL_SOFTFP arithmetic=pass rounding=pass exceptions=pass comparisons=pass conversions=pass stdio=pass'
PRINTF = b'SOFTFP_PRINTF int=-17 uint=42 double=1.25 quad=1.500'


def failure_line(serial):
    if b'SOFTFP_FAIL' in serial:
        return 'soft-fp assertion failed: ' + serial[serial.index(b'SOFTFP_FAIL'):].split(b'\n', 1)[0].decode(errors='replace')
    return general_failure(serial)


def validate_execution(serial, baseline_begin, probe_begin, probe_mid, probe_end, native_begin, arch):
    if arch != 'mips64':
        raise ValueError('binary128 qualifier requires MIPS64')
    boundaries = (baseline_begin, probe_begin, probe_mid, probe_end, native_begin)
    if any(type(value) is not int for value in boundaries) or not 0 < baseline_begin < probe_begin < probe_mid < probe_end <= native_begin < len(serial):
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
    if b'OK_SYSTEM_GUI boot=complete' not in boot or b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw' not in boot:
        raise ValueError('missing distribution boot evidence')
    for span in (baseline, native):
        if b'hello from ObfuscationOS userland' not in span:
            raise ValueError('missing dedicated native pipeline')
    for span in (first, second):
        lines = [line for line in span.splitlines(keepends=True) if b'OK_MUSL_SOFTFP' in line]
        if len(lines) != 1 or lines[0] not in (MARKER+b'\n', MARKER+b'\r\n'):
            raise ValueError('missing unique complete probe success within each command')
        printf = [line for line in span.splitlines(keepends=True) if b'SOFTFP_PRINTF' in line]
        if len(printf) != 1 or printf[0] not in (PRINTF+b'\n', PRINTF+b'\r\n') or span.index(PRINTF) >= span.index(MARKER):
            raise ValueError('missing complete real printf output before success')
    if any(b'SOFTFP_PRINTF' in span for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('printf output outside execution boundaries')
    if any(b'OK_MUSL_SOFTFP' in span for span in (boot, baseline, serial[probe_end:])):
        raise ValueError('probe success outside execution boundaries')
    rows = decode_frames(serial, arch)
    base = decode_frames(baseline, arch)[-1]
    if base['allocations'] <= decode_frames(boot, arch)[-1]['allocations']:
        raise ValueError('baseline pipeline has no independent allocation evidence')
    endings = [decode_frames(span, arch)[-1] for span in (first, second, native)]
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
    return dict(runs=2, arithmetic='passed', rounding='passed', exceptions='passed', comparisons='passed', conversions='passed', stdio='passed',
                baseline=base, final=endings[-1], records=len(rows), accounting_version=2)
