"""Strict, offline observations for the native PID 1 adoption guest.

Parsing a serial transcript does not itself establish execution provenance. The
SDK-only runner binds source, compiler, ELF, disk and QEMU inputs separately.
"""
from __future__ import annotations

import re

from entry_stack_evidence import decode_stacks
from kernel_sdk import ARCH_TRIPLES
from object_pressure_evidence import decode_frames, failure_line as general_failure


BEGIN = re.compile(rb"INIT_ADOPTION_BEGIN pid=1 ppid=0")
WAIT = re.compile(rb"INIT_ADOPTION_WAIT child=([1-9][0-9]*) status=([1-9][0-9]*)")
SIGNAL = re.compile(rb"INIT_ADOPTION_SIGNAL case=(live|completed) owner=(init|service) child=([1-9][0-9]*) status=([1-9][0-9]*)")
GRANDCHILD = re.compile(rb"INIT_ADOPTION_GRANDCHILD case=live pid=([1-9][0-9]*) ppid=1")
CASE = re.compile(rb"INIT_ADOPTION_CASE case=(live|completed) service=([1-9][0-9]*) grandchild=([1-9][0-9]*) pass=1")
PASS = b"INIT_ADOPTION_PASS live=1 completed=1 wait_any=1 signal=1 drained=1"
IMAGE = re.compile(rb"OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=([1-9][0-9]*) physical_first=0x[0-9a-f]+ physical_last=0x[0-9a-f]+ owner=retained")
CHILD_WAIT = re.compile(rb"OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=([1-9][0-9]*) wait=([1-9][0-9]*) selector=4294967295 output=([1-9][0-9]*) format=(status|siginfo) outcome=(arm|complete) result=(-?[0-9]+) live=([01])")
PLATFORM_PASS = b"N64_SIGNAL_PLATFORM_PASS before-cxx=1 fp=fr1"
FAILURES = (b"INIT_ADOPTION_FAIL", b"OK_TEST_FAIL", b"POSIX_CHECK failed:",
            b"MUSL_CHECK failed:", b"acceptance=FAIL", b"boot=degraded", b"boot=failed",
            b"N64_SIGNAL_PLATFORM_REJECT", b"N64_PRIVATE_EARLY_")


def lines_of(serial: bytes) -> list[bytes]:
    if not serial or not serial.endswith(b"\n"):
        raise ValueError("empty or incomplete guest transcript")
    lines = [line.removesuffix(b"\r") for line in serial.split(b"\n")[:-1]]
    if any(b"\r" in line for line in lines):
        raise ValueError("embedded carriage return in guest transcript")
    return lines


def singleton(lines: list[bytes], marker: bytes) -> int:
    positions = [i for i, line in enumerate(lines) if line == marker]
    if len(positions) != 1:
        raise ValueError("missing or duplicated marker: " + marker.decode())
    return positions[0]


def validate_execution(serial: bytes, arch: str, mode: str, *, sdk_abi: int | None = None) -> dict:
    if arch not in ARCH_TRIPLES or mode not in ("debug", "release"):
        raise ValueError("unsupported architecture or mode")
    lines = lines_of(serial)
    if any(b"INIT_ADOPTION_" in line and not line.startswith(b"INIT_ADOPTION_") for line in lines):
        raise ValueError("wrapped init adoption record")
    if any(token in line for line in lines for token in FAILURES) or general_failure(serial):
        raise ValueError("guest or kernel failure marker")
    if arch == "mips64":
        if not lines or lines[0] != PLATFORM_PASS or lines.count(PLATFORM_PASS) != 1:
            raise ValueError("MIPS64 platform admission must be the first serial line")
        if any(b"N64_SIGNAL_PLATFORM" in line for line in lines[1:]):
            raise ValueError("unexpected later MIPS64 platform admission")
    elif any(b"N64_SIGNAL_PLATFORM_PASS" in line for line in lines):
        raise ValueError("unexpected MIPS64 platform admission")
    if any(b"OK_NATIVE_IMAGE" in line and not IMAGE.fullmatch(line) for line in lines):
        raise ValueError("malformed Linux image admission")
    if any(b"OK_NATIVE_CHILD_WAIT" in line and not CHILD_WAIT.fullmatch(line) for line in lines):
        raise ValueError("malformed native child-wait diagnostic")
    begin = singleton(lines, b"INIT_ADOPTION_BEGIN pid=1 ppid=0")
    end = singleton(lines, PASS)
    if begin >= end:
        raise ValueError("guest pass precedes entry")
    if singleton(lines, b"OK_SYSTEM_GUI boot=complete") >= begin:
        raise ValueError("kernel GUI boot did not precede guest")
    if singleton(lines, b"OK_NATIVE scope=hardware init=loaded") >= begin:
        raise ValueError("native init load did not precede guest")
    if singleton(lines, b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none") >= begin:
        raise ValueError("Virtio ext4 root was not established before guest")
    images = [(i, match) for i, line in enumerate(lines) if (match := IMAGE.fullmatch(line))]
    if len(images) != 1 or images[0][0] >= begin:
        raise ValueError("missing unique Linux init ELF image admission")
    source = b"linker" if arch in ("loongarch64", "mips", "mips64") else b"firmware"
    if images[0][1][1] != source:
        raise ValueError("wrong physical image source for architecture")
    image_pages = int(images[0][1][2])
    guest = [line for line in lines if line.startswith(b"INIT_ADOPTION_")]
    if len(guest) != 13 or guest[0] != BEGIN.pattern or guest[-1] != PASS:
        raise ValueError("guest event count or terminal marker differs")
    expected_types = (BEGIN, WAIT, SIGNAL, GRANDCHILD, WAIT, SIGNAL, CASE,
                      SIGNAL, WAIT, SIGNAL, WAIT, CASE)
    captures = []
    for line, pattern in zip(guest[:-1], expected_types):
        match = pattern.fullmatch(line)
        if not match:
            raise ValueError("guest event order or syntax differs: " + line.decode(errors="replace"))
        captures.append(match.groups())
    live_service = int(captures[1][0]); live_grandchild = int(captures[3][0])
    completed_grandchild = int(captures[7][2]); completed_service = int(captures[8][0])
    if (len({live_service, live_grandchild, completed_service, completed_grandchild}) != 4 or
            any(pid <= 1 for pid in (live_service, live_grandchild, completed_service, completed_grandchild))):
        raise ValueError("invalid or reused process identities")
    expected = (
        (captures[1], (str(live_service).encode(), b"4352")),
        (captures[2], (b"live", b"init", str(live_service).encode(), b"17")),
        (captures[4], (str(live_grandchild).encode(), b"5888")),
        (captures[5], (b"live", b"init", str(live_grandchild).encode(), b"23")),
        (captures[6], (b"live", str(live_service).encode(), str(live_grandchild).encode())),
        (captures[7], (b"completed", b"service", str(completed_grandchild).encode(), b"31")),
        (captures[8], (str(completed_service).encode(), b"4864")),
        (captures[9], (b"completed", b"init", str(completed_service).encode(), b"19")),
        (captures[10], (str(completed_grandchild).encode(), b"7936")),
        (captures[11], (b"completed", str(completed_service).encode(), str(completed_grandchild).encode())),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise ValueError("PID, status or signal ownership differs from guest protocol")
    waits = [(i, match) for i, line in enumerate(lines) if (match := CHILD_WAIT.fullmatch(line))]
    if mode == "debug":
        expected_format = b"siginfo" if arch == "rv32" else b"status"
        if (any(match[4] != expected_format for _, match in waits) or
                not any(match[5] == b"arm" for _, match in waits) or not any(
                match[5] == b"complete" and int(match[6]) == live_grandchild and i < end
                for i, match in waits)):
            raise ValueError("no native blocked wait-any wakeup for adopted live child")
    elif waits or any(b"OK_NATIVE_CHILD_WAIT" in line for line in lines):
        raise ValueError("Release leaked Debug-only child-wait diagnostics")
    frames = decode_frames(serial, arch, require_quarantine=True)
    stacks = decode_stacks(serial)
    last_frame, last_stack = frames[-1], stacks[-1]
    records_per_page = 341 if arch in ("i386", "arm32", "rv32", "mips", "ppc") else 170
    metadata_pages = (image_pages + records_per_page - 1) // records_per_page
    if (last_frame["user"] != image_pages or last_frame["objects"] != metadata_pages or
            last_frame["used"] != image_pages + metadata_pages or last_stack["leased"] != 1 or
            last_stack["faults"] or last_stack["rejected"]):
        raise ValueError("child resources did not return to the PID 1 baseline")
    if not any(row["used"] == 0 for row in frames[:2]) or stacks[0]["leased"] != 0:
        raise ValueError("missing empty pre-init resource baseline")
    if not (frames[-1]["allocations"] > frames[0]["allocations"] and
            frames[-1]["releases"] > frames[0]["releases"] and
            last_stack["reservations"] >= 5 and last_stack["releases"] >= 4):
        raise ValueError("insufficient child lifetime activity")
    result = dict(architecture=arch, mode=mode, native_execution=False,
                parser_replay_only=True, live_service=live_service,
                live_grandchild=live_grandchild, completed_service=completed_service,
                completed_grandchild=completed_grandchild, wait_any_completion=True,
                wait_any_wakeup_observed=mode == "debug",
                final_user_pages=last_frame["user"], final_entry_leases=last_stack["leased"],
                physical=False, smp=False, service_manager=False)
    if sdk_abi is not None:
        if type(sdk_abi) is not int or sdk_abi < 1:
            raise ValueError("invalid externally admitted SDK ABI")
        result["sdk_abi"] = sdk_abi
    return result
