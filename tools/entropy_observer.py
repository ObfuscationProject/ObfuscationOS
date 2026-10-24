"""Strict complete-command observations for static entropy and rollback guests."""
from dynamic_startup_observer import lines_of, validate_static_run, validate_pipeline

PROFILES = {'i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc'}

def validate_complete(serial, runs, pipeline, *, architecture, enabled):
    if architecture not in PROFILES or type(enabled) is not bool:
        raise ValueError('unknown entropy execution profile')
    lines_of(serial, prompt=True)
    if len(runs) != 2:
        raise ValueError('two distinct entropy commands required')
    previous = None
    for start, end in [*runs, pipeline]:
        if (type(start) is not int or type(end) is not int or
                not 0 < start < end <= len(serial) or
                (previous is not None and start != previous) or
                not serial[:start].endswith(b'oksh> ') or not serial[:end].endswith(b'oksh> ')):
            raise ValueError('invalid or noncontiguous entropy command boundaries')
        previous = end
    if pipeline[1] != len(serial):
        raise ValueError('unreviewed records follow native pipeline')
    before = serial[:runs[0][0]]
    if b'OK_STATIC_ENTROPY' in before:
        raise ValueError('entropy acceptance precedes requested command')
    transport = b'mmio' if architecture in {'aarch64', 'arm32', 'rv64', 'rv32'} else b'pci'
    expected = (b'OK_ENTROPY source=virtio-rng-' + transport + b' state=ready' if enabled
                else b'OK_ENTROPY source=none state=unavailable')
    source_lines = [line for line in lines_of(before, prompt=True) if b'OK_ENTROPY' in line]
    if source_lines != [expected]:
        raise ValueError('entropy source record differs from explicit device selection')
    for start, end in runs:
        validate_static_run(serial[start:end], no_entropy=not enabled)
        if b'OK_ENTROPY ' in serial[start:end]:
            raise ValueError('source changes during guest command')
    continuation = serial[pipeline[0]:pipeline[1]]
    if b'OK_STATIC_ENTROPY' in continuation or b'OK_ENTROPY ' in continuation:
        raise ValueError('entropy acceptance outside requested command')
    validate_pipeline(continuation)
    return dict(commands=2, executed=enabled, rollback=not enabled, child_reaped=True,
                native_pipeline=True, command_boundaries=[list(pair) for pair in runs],
                pipeline_boundary=list(pipeline), architecture=architecture)
