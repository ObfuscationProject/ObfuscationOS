"""Complete retirement evidence for disposable PID 1 guests, not guest shutdown."""
from entry_stack_evidence import decode_stacks
from object_pressure_evidence import decode_frames, failure_line


def inspect_terminal(serial: bytes, marker: bytes, architecture: str, *, complete: bool = False) -> dict | None:
    """Wait for complete post-marker frame and entry-stack retirement records.

    A partial UART line never satisfies readiness. Final admission parses every
    retained record and rejects incomplete or contradictory accounting.
    """
    if not isinstance(serial, bytes) or not isinstance(marker, bytes) or not marker or b'\n' in marker or b'\r' in marker:
        raise ValueError('invalid terminal evidence input')
    if failure_line(serial):
        raise ValueError('failure in terminal evidence')
    payload = serial if complete else serial[:serial.rfind(b'\n') + 1]
    positions = []
    offset = 0
    for line in payload.splitlines(keepends=True):
        if line in (marker + b'\n', marker + b'\r\n'):
            positions.append(offset + len(line))
        offset += len(line)
    if len(positions) > 1:
        raise ValueError('duplicate terminal success marker')
    if not positions:
        if complete:
            raise ValueError('missing complete terminal success marker')
        return None
    tail = payload[positions[0]:]
    if b'OK_NATIVE_FRAMES' not in tail or b'OK_ENTRY_STACKS' not in tail:
        if complete:
            raise ValueError('missing post-marker native retirement')
        return None
    frames = decode_frames(payload, architecture, require_quarantine=True)
    stacks = decode_stacks(payload)
    if (any(frames[-1][field] for field in ('used', 'user', 'objects', 'pinned', 'pending', 'object_quarantine')) or
            any(stacks[-1][field] for field in ('leased', 'active', 'quarantine')) or
            tail.rfind(b'OK_ENTRY_STACKS') <= tail.rfind(b'OK_NATIVE_FRAMES')):
        if complete:
            raise ValueError('native ownership remains after terminal success')
        return None
    return dict(scope='retired-disposable-native-workload', guest_shutdown=False,
                marker_end=positions[0], frames=frames[-1], entry_stacks=stacks[-1])
