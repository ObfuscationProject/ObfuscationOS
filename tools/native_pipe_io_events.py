"""Compose scalar/vector pipe ownership without hiding publication adjacency."""
import native_pipe_signal_evidence as read
import native_pipe_write_events as write
import native_pipe_vector_events as vector

PATTERNS = read.PATTERNS + vector.PATTERNS


def _read_view(span):
    # Preserve a nonempty intervening line. Deleting a write could incorrectly
    # join a read arm/origin or an interrupted read/signal publication pair.
    return b''.join(b'validated scalar pipe write\n' if line.startswith(write.PREFIX)
                    else line for line in span.splitlines(keepends=True))


def native_events(span, arch):
    # Both forms allocate from the same per-direction pool. Validate the
    # original stream once so overlapping live counts and adjacency stay exact.
    return vector.native_events(span, arch, allow_signal=False)


def validate_read_cases(span, arch):
    write.native_events(span, arch, allow_signal=False)
    return read.validate_cases(_read_view(span), arch)
