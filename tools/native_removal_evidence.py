"""Validate complete, ordered Linux removal guest records, including post-pass failures."""
import re
from object_pressure_evidence import failure_line as general_failure

IMAGE = re.compile(rb'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=[1-9][0-9]* physical_first=0x[0-9a-f]{16} physical_last=0x[0-9a-f]{16} owner=retained\r?\n')

CASES = ('flags', 'paths', 'retained', 'recreated', 'directories',
         'libc_unlink', 'libc_rmdir', 'absolute')
RECORDS = (b'REMOVAL_BEGIN cases=8', *(f'REMOVAL_CASE index={i} name={name} pass=1'.encode()
           for i, name in enumerate(CASES)), b'REMOVAL_PASS cases=8')


def failure_line(serial):
    if error := general_failure(serial):
        return error
    for line in serial.splitlines():
        if b'REMOVAL_FAIL' in line:
            return line.decode(errors='replace')
    return None


def validate(serial, boundaries, arch='x86_64'):
    if not isinstance(serial, bytes) or len(boundaries) != 3:
        raise ValueError('invalid removal execution inputs')
    if error := failure_line(serial):
        raise ValueError(error)
    if (any(type(value) is not int for value in boundaries) or
            not 0 < boundaries[0] < boundaries[1] < boundaries[2] <= len(serial)):
        raise ValueError('invalid removal command boundaries')
    for value in boundaries:
        if not serial[:value].endswith(b'oksh> '):
            raise ValueError('removal commands require complete prompts')
    boot = serial[:boundaries[0]]
    if b'OK_SYSTEM_GUI boot=complete\n' not in boot.replace(b'\r\n', b'\n'):
        raise ValueError('missing completed distribution boot')
    storage = b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none'
    if [line for line in boot.replace(b'\r\n', b'\n').splitlines() if b'OK_STORAGE ' in line] != [storage]:
        raise ValueError('missing unique ext4 subset boot')
    if b'REMOVAL_' in boot or b'REMOVAL_' in serial[boundaries[2]:]:
        raise ValueError('unexpected removal records outside commands')
    for start, end in zip(boundaries, boundaries[1:]):
        span = serial[start:end]
        images = [line for line in span.splitlines(keepends=True) if b'OK_NATIVE_IMAGE' in line]
        source = b'linker' if arch in ('loongarch64', 'mips', 'mips64') else b'firmware'
        if len(images) != 1 or not (match := IMAGE.fullmatch(images[0])) or match[1] != source:
            raise ValueError('missing unique complete Linux image ownership record')
        rows = []
        for line in span.splitlines(keepends=True):
            if b'REMOVAL_' not in line:
                continue
            if not line.endswith(b'\n'):
                raise ValueError('incomplete removal record')
            rows.append(line.removesuffix(b'\n').removesuffix(b'\r'))
        if tuple(rows) != RECORDS:
            raise ValueError('missing, extra, reordered or malformed removal record')
    if b'OK_NATIVE_IMAGE' in serial[boundaries[2]:]:
        raise ValueError('unexpected Linux image after removal commands')
    return dict(runs=2, cases_per_run=8, assertions='static-musl user instructions and Linux syscall personality',
                physical=False, smp=False, shutdown=False)
