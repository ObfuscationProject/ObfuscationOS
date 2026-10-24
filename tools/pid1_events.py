"""Validate complete native PID 1 serial observations, not just a pass string."""
from __future__ import annotations

import re

EVENT = re.compile(rb"PID1_EVENT kind=([a-z-]+) pid=(0|[1-9][0-9]*) value=(0|[1-9][0-9]*)")
CRASH = re.compile(rb"PID1_SERVICE_CRASH attempt=([12]) pid=([1-9][0-9]*)")
ORPHAN = re.compile(rb"PID1_ORPHAN_PASS pid=([1-9][0-9]*) ppid=1")
STOP = re.compile(rb"PID1_SERVICE_STOP attempt=3 pid=([1-9][0-9]*)")
PASS = b"PID1_NATIVE_PASS pid=1 restarts=2 other=1 shutdown=clean"


def validate(serial: bytes) -> dict:
    if not isinstance(serial, bytes) or not serial:
        raise ValueError("empty native PID 1 serial evidence")
    normalized = serial.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise ValueError("bare carriage return in PID 1 serial evidence")
    lines = normalized.split(b"\n")
    if lines[-1] and b"PID1_" in lines[-1]:
        raise ValueError("incomplete native PID 1 record")
    records = [line for line in lines if b"PID1_" in line]
    if len(records) != 15:
        raise ValueError("native PID 1 record count mismatch")

    def event(index: int, kind: bytes, pid: int | None, value: int | None) -> tuple[int, int]:
        match = EVENT.fullmatch(records[index])
        if not match or match[1] != kind:
            raise ValueError(f"PID 1 event {index} is missing, malformed or reordered")
        observed_pid, observed_value = int(match[2]), int(match[3])
        if (pid is not None and observed_pid != pid or
                value is not None and observed_value != value):
            raise ValueError(f"PID 1 event {index} has incorrect ownership or status")
        return observed_pid, observed_value

    event(0, b"init", 1, 0)
    first, _ = event(1, b"launch", None, 1)
    second, _ = event(4, b"launch", None, 2)
    third, _ = event(7, b"launch", None, 3)
    if len({first, second, third}) != 3 or min(first, second, third) <= 1:
        raise ValueError("foreground service PID lineage is invalid")
    for index, attempt, pid in ((2, 1, first), (5, 2, second)):
        match = CRASH.fullmatch(records[index])
        if not match or int(match[1]) != attempt or int(match[2]) != pid:
            raise ValueError("crash marker does not match launched service")
    event(3, b"reap-service", first, 42 << 8)
    event(6, b"reap-service", second, 42 << 8)
    orphan = ORPHAN.fullmatch(records[8])
    if not orphan:
        raise ValueError("native adopted-orphan observation is missing")
    orphan_pid = int(orphan[1])
    if orphan_pid in (1, first, second, third):
        raise ValueError("adopted orphan aliases a service")
    event(9, b"reap-other", orphan_pid, 17 << 8)
    event(10, b"shutdown", third, 0)
    stopped = STOP.fullmatch(records[11])
    if not stopped or int(stopped[1]) != third:
        raise ValueError("foreground stop marker has wrong process identity")
    event(12, b"reap-service", third, 0)
    event(13, b"stopped", 1, 0)
    if records[14] != PASS:
        raise ValueError("native PID 1 completion record is missing or malformed")
    return {"service_pids": [first, second, third], "orphan_pid": orphan_pid,
            "restarts": 2, "other_reaped": 1, "forced_stops": 0,
            "scope": "observed native guest init/service/orphan/restart/shutdown sequence"}
