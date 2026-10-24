"""Complete-line observations for the bounded x86_64 dynamic-startup guest."""
from __future__ import annotations

MARKER = (b'OK_SHARED_MUSL_STARTUP interpreter=pass main_entry=pass loader_identity=pass '
          b'relocation=pass auxv=pass tls_errno=pass entropy=pass')
RUNNER = b'OK_DYNAMIC_RUNNER child_exit=0 normal=1'
MISSING_RUNNER = b'OK_DYNAMIC_RUNNER child_exit=127 normal=1'
MISSING_ERROR = b'OK_DYNAMIC_ROLLBACK errno=2 continued=1'
NO_ENTROPY_ERROR = b'OK_DYNAMIC_NO_ENTROPY errno=11 continued=1'
NO_ENTROPY_RUNNER = b'OK_DYNAMIC_RUNNER child_exit=124 normal=1'
STATIC_MARKER = b'OK_STATIC_ENTROPY auxv=pass getrandom=pass'
STATIC_RUNNER = b'OK_STATIC_ENTROPY_RUNNER child_exit=0 normal=1'
STATIC_NO_ENTROPY = b'OK_STATIC_ENTROPY_ROLLBACK errno=11 continued=1'
STATIC_NO_ENTROPY_RUNNER = b'OK_STATIC_ENTROPY_RUNNER child_exit=124 normal=1'
FAILURES = (b'OK_TEST_FAIL', b'POSIX_CHECK failed:', b'MUSL_CHECK failed:',
            b'acceptance=FAIL', b'boot=failed', b'boot=degraded',
            b'kernel-probe-failed', b'DYNAMIC_OPEN ', b'shell_pipeline=FAIL')


def lines_of(serial: bytes, *, prompt: bool) -> list[bytes]:
    if not isinstance(serial, bytes) or not serial:
        raise ValueError('empty dynamic guest transcript')
    if any(token in serial for token in FAILURES):
        raise ValueError('dynamic guest or kernel failure')
    normalized = serial.replace(b'\r\n', b'\n')
    if b'\r' in normalized:
        raise ValueError('bare carriage return in dynamic guest transcript')
    try:
        normalized.decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('non-ASCII dynamic guest transcript') from error
    lines = normalized.split(b'\n')
    ending = lines.pop()
    if ending != (b'oksh> ' if prompt else b''):
        raise ValueError('dynamic guest transcript lacks the completed command boundary')
    return lines


def validate_run(serial: bytes, *, missing_loader: bool = False, no_entropy: bool = False) -> dict:
    lines = lines_of(serial, prompt=True)
    if missing_loader and no_entropy:
        raise ValueError('negative controls are mutually exclusive')
    wanted = ([MISSING_ERROR, MISSING_RUNNER] if missing_loader else
              [NO_ENTROPY_ERROR, NO_ENTROPY_RUNNER] if no_entropy else [MARKER, RUNNER])
    records = [line for line in lines if b'OK_SHARED_MUSL' in line or b'OK_DYNAMIC_' in line]
    if records != wanted:
        raise ValueError('dynamic guest records are missing, wrapped, duplicated or reordered')
    if any(b'exec failed' in line or b'not found' in line or b'dynamic-startup execve:' in line for line in lines):
        raise ValueError('unexpected dynamic exec failure')
    return dict(startup_executed=not (missing_loader or no_entropy), child_reaped=True,
                resumed_native_child_after_failed_exec=missing_loader or no_entropy)


def validate_static_run(serial: bytes, *, no_entropy: bool = False) -> dict:
    lines = lines_of(serial, prompt=True)
    wanted = ([STATIC_NO_ENTROPY, STATIC_NO_ENTROPY_RUNNER] if no_entropy else
              [STATIC_MARKER, STATIC_RUNNER])
    records = [line for line in lines if b'OK_STATIC_ENTROPY' in line]
    if records != wanted or any(b'exec failed' in line for line in lines):
        raise ValueError('static entropy guest records are missing, duplicated or reordered')
    return dict(executed=not no_entropy, child_reaped=True, rollback=no_entropy)


def validate_pipeline(serial: bytes) -> None:
    lines = lines_of(serial, prompt=True)
    # Kernel child-wait diagnostics can begin immediately after the native
    # program's bytes on this serialized console, before its trailing newline.
    if serial.count(b'hello from ObfuscationOS userland') != 1:
        raise ValueError('post-dynamic native pipeline did not execute exactly once')
    if any(b'OK_SHARED_MUSL' in line or b'OK_DYNAMIC_' in line for line in lines):
        raise ValueError('dynamic guest records outside the requested command')


def validate_complete(serial: bytes, runs: list[tuple[int, int]], pipeline: tuple[int, int], *,
                      missing_loader: bool, no_entropy: bool = False) -> dict:
    lines_of(serial, prompt=True)
    if len(runs) != 2:
        raise ValueError('dynamic campaign requires two distinct commands')
    previous = 0
    for index, (start, end) in enumerate([*runs, pipeline]):
        if (type(start) is not int or type(end) is not int or
                not 0 < start < end <= len(serial) or start < previous or
                (index > 0 and start != previous) or
                not serial[:start].endswith(b'oksh> ') or not serial[:end].endswith(b'oksh> ')):
            raise ValueError('invalid dynamic guest command boundaries')
        previous = end
    if pipeline[1] != len(serial):
        raise ValueError('unreviewed records follow the pipeline boundary')
    for start, end in runs:
        validate_run(serial[start:end], missing_loader=missing_loader, no_entropy=no_entropy)
    validate_pipeline(serial[pipeline[0]:pipeline[1]])
    before = serial[:runs[0][0]]
    if b'OK_SHARED_MUSL' in before or b'OK_DYNAMIC_' in before:
        raise ValueError('dynamic acceptance records precede the requested command')
    return dict(commands=2, native_pipeline=True, missing_loader=missing_loader, no_entropy=no_entropy,
                command_boundaries=[list(row) for row in runs], pipeline_boundary=list(pipeline))
