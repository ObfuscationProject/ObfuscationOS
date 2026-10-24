"""Bounded transcript admission for first-chmod software transport cuts.

Synthetic calls are parser/model evidence only. The outer runner binds sources,
SDK, guest ELF, QEMU and disk snapshots. CRC values are collected, not a disk
oracle, and a completed Virtio call is not evidence of physical power loss.
"""
from __future__ import annotations

import re


ARCHES = ("x86_64", "i386", "mips")
MAX_SERIAL_BYTES = 256 * 1024
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1
NUMBER = rb"(0|[1-9][0-9]{0,19})"
FIXTURE = b"JDMODE_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1 uid=1000 clock=in-range"
STORAGE = b"JDMODE_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive clock=administrator-software"
CREDENTIALS = b"JDMODE_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1 personality=linux"
USER = b"JDMODE_USER_BEGIN uid=1000 sdk=31 scope=actual-musl-syscalls"
OPERATION = b"JDMODE_OP_BEGIN ordinal=1 name=chmod"
HARDWARE = b"OK_NATIVE scope=hardware init=loaded"
IO = re.compile(rb"JDMODE_IO ordinal=" + NUMBER + rb" kind=(write|flush) sector=" + NUMBER +
                rb" bytes=" + NUMBER + rb" crc32c=" + NUMBER + rb" status=" + NUMBER)
INODE = re.compile(rb"JDMODE_INODE io=" + NUMBER + rb" inode=" + NUMBER + rb" mode=" + NUMBER +
                   rb" uid=" + NUMBER + rb" gid=" + NUMBER + rb" ctime_sec=" + NUMBER +
                   rb" ctime_nsec=" + NUMBER + rb" version=" + NUMBER)
CUT = re.compile(rb"JDMODE_CUT ordinal=" + NUMBER + rb" writes=" + NUMBER + rb" flushes=" + NUMBER)
IMAGE = re.compile(rb"OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=" + NUMBER +
                   rb" physical_first=(0x[0-9a-f]{16}) physical_last=(0x[0-9a-f]{16}) owner=retained")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _uint(mapping, key, maximum=UINT64_MAX):
    value = mapping.get(key)
    _require(type(value) is int and 0 <= value <= maximum, "invalid fixture fact: " + key)
    return value


def _layout(facts):
    _require(type(facts) is dict, "fixture facts must be a dictionary")
    _require(facts.get("block_size") == 1024 and facts.get("feature_masks") == [4, 0x42, 0x400]
             and type(facts.get("journal_start")) is int and facts["journal_start"] == 0,
             "fixture facts must describe the admitted clean 1 KiB profile")
    origin = _uint(facts, "origin")
    blocks = _uint(facts, "filesystem_blocks")
    sectors = _uint(facts, "sectors")
    journal = _uint(facts, "journal_first")
    journal_blocks = _uint(facts, "journal_blocks")
    _require(blocks > 1 and sectors == blocks * 2 and origin + sectors <= UINT64_MAX,
             "invalid guarded volume geometry")
    _require(journal > 1 and journal_blocks >= 6 and journal + journal_blocks <= blocks,
             "invalid first-transaction journal extent")
    nodes = facts.get("nodes")
    _require(type(nodes) is dict and type(nodes.get("child")) is dict, "missing child facts")
    child = nodes["child"]
    block = _uint(child, "block")
    _require(1 < block < blocks and not journal <= block < journal + journal_blocks,
             "child home block overlaps journal or lies outside volume")
    _require(_uint(child, "inode", UINT32_MAX) == 14 and _uint(child, "mode", 0xffff) == 0o40755
             and _uint(child, "uid", UINT32_MAX) == 1000 and _uint(child, "gid", UINT32_MAX) == 1000,
             "wrong initial UID1000 child metadata")
    _require(_uint(child, "version") < UINT64_MAX, "child version cannot advance")
    # Each item is the block written, or None for a completed FLUSH. This is
    # the first publication/checkpoint transaction, including all nine FLUSHes.
    sequence = (None, journal + 1, journal + 2, journal + 3, journal + 5,
                None, journal + 4, None, 1, None, journal, None, None,
                1, block, None, journal, None, 1, None)
    return origin, child, sequence


def validate_cut(serial: bytes, cut: int, arch: str, facts: dict) -> dict:
    """Reject anything except the exact first-chmod prefix and one cut marker.

    Accept LF or CRLF with every record newline-complete. After the cut, only
    one optional architecture-matching QEMU signal-15 termination line is legal.
    The returned I/O CRCs require a separate disk oracle before acceptance.
    """
    _require(type(cut) is int and 1 <= cut <= 20, "cut ordinal must be in 1..20")
    _require(type(arch) is str and arch in ARCHES, "unsupported cut architecture")
    _require(type(serial) is bytes and 0 < len(serial) <= MAX_SERIAL_BYTES,
             "serial must be nonempty bounded bytes")
    origin, child, sequence = _layout(facts)
    normalized = serial.replace(b"\r\n", b"\n")
    _require(normalized.endswith(b"\n") and b"\r" not in normalized,
             "partial record or bare carriage return")
    lines = normalized[:-1].split(b"\n")
    _require(len(lines) <= 4096 and all(len(line) <= 4096 for line in lines), "serial line limit")
    _require(all(all(32 <= byte <= 126 for byte in line) for line in lines),
             "nonprintable serial byte")
    _require(not any(token in normalized for token in
                     (b"FAIL", b"panic", b"PANIC", b"boot=failed", b"boot=degraded",
                      b"LINUX_CHMOD_SNAPSHOT")), "failure or completed-user evidence in cut transcript")

    rows = []
    images = []
    hardware = []
    constants = {FIXTURE: "fixture", STORAGE: "storage", CREDENTIALS: "credentials",
                 USER: "user", OPERATION: "operation"}
    for position, line in enumerate(lines):
        if b"JDMODE" in line:
            kind = constants.get(line)
            values = None
            if kind is None:
                for kind, pattern in (("io", IO), ("inode", INODE), ("cut", CUT)):
                    if match := pattern.fullmatch(line):
                        values = match.groups()
                        break
                else:
                    raise ValueError("unknown, malformed or forbidden JDMODE record")
            rows.append((kind, position, values))
        if b"OK_NATIVE_IMAGE" in line:
            match = IMAGE.fullmatch(line)
            _require(match is not None, "malformed or non-Linux native image record")
            source, pages, first, last = match.groups()
            pages, first, last = int(pages), int(first, 16), int(last, 16)
            _require(source == (b"linker" if arch == "mips" else b"firmware")
                     and 0 < pages <= 1024 and 0 < first <= last <= UINT64_MAX
                     and first % 4096 == last % 4096 == 0, "native image profile/domain")
            images.append((position, dict(source=source.decode(), pages=pages,
                                           physical_first=first, physical_last=last)))
        if b"init=" in line and b"OK_NATIVE" in line:
            _require(line == HARDWARE, "malformed hardware init record")
            hardware.append(position)
        if b"qemu-system-" in line:
            _require(position == len(lines) - 1, "early QEMU termination or diagnostic")

    _require(len(rows) >= 7 and [item[0] for item in rows[:5]] ==
             ["fixture", "storage", "credentials", "user", "operation"],
             "fixture/storage/credentials/user/first-chmod order")
    _require(len(images) == len(hardware) == 1, "missing or duplicate image/hardware entry")
    _require(rows[1][1] < images[0][0] < hardware[0] < rows[2][1],
             "native image and hardware init must precede credentials after storage")
    _require(rows[0][1] == 0, "fixture begin must be the first serial line")

    cursor = 5
    previous = rows[4][1]
    transport = []
    inode = None
    for ordinal, block in enumerate(sequence[:cut], 1):
        _require(cursor < len(rows) and rows[cursor][0] == "io", "missing ordered completed I/O")
        _, position, values = rows[cursor]
        _require(position == previous + 1, "nonadjacent first-transaction I/O")
        actual, kind, sector, length, crc, status = values
        actual, sector, length, crc, status = map(int, (actual, sector, length, crc, status))
        expected_kind = b"flush" if block is None else b"write"
        _require(actual == ordinal and kind == expected_kind and status == 0,
                 "wrong I/O ordinal/kind or unsuccessful transport completion")
        _require((sector, length) == ((0, 0) if block is None else (origin + block * 2, 1024))
                 and 0 <= crc <= UINT32_MAX and (block is not None or crc == 0),
                 "wrong first-transaction sector/length or CRC domain")
        transport.append(dict(ordinal=actual, kind=kind.decode(), sector=sector,
                              bytes=length, crc32c=crc, status=status))
        cursor += 1
        previous = position
        if ordinal == 15:
            _require(cursor < len(rows) and rows[cursor][0] == "inode", "missing child home inode")
            _, position, values = rows[cursor]
            _require(position == previous + 1, "nonadjacent home inode")
            inode = dict(zip(("io", "inode", "mode", "uid", "gid", "ctime_sec", "ctime_nsec", "version"),
                             map(int, values)))
            _require((inode["io"], inode["inode"], inode["mode"], inode["uid"], inode["gid"], inode["version"]) ==
                     (15, child["inode"], 0o42750, child["uid"], child["gid"], child["version"] + 1),
                     "wrong first-chmod child inode identity/mode/version")
            _require(1700000000 <= inode["ctime_sec"] < 1700003600 and
                     0 <= inode["ctime_nsec"] < 1000000000, "inode ctime outside admitted clock window")
            cursor += 1
            previous = position

    _require(cursor + 1 == len(rows) and rows[cursor][0] == "cut", "missing unique final cut marker")
    _, position, values = rows[cursor]
    writes = sum(item["kind"] == "write" for item in transport)
    flushes = cut - writes
    _require(position == previous + 1 and tuple(map(int, values)) == (cut, writes, flushes),
             "cut marker must immediately follow selected completed call with exact counts")
    tail = lines[position + 1:]
    termination = None
    if tail:
        pattern = re.compile(rb"qemu-system-" + arch.encode() +
                             rb": terminating on signal 15 from pid ([1-9][0-9]{0,19}) "
                             rb"\(((?:/?[A-Za-z0-9_.-]+/)*python3(?:\.[0-9]+)?)\)")
        match = pattern.fullmatch(tail[0])
        _require(len(tail) == 1 and match is not None and int(match[1]) <= UINT64_MAX,
                 "unexpected output after cut marker")
        termination = dict(signal=15, pid=int(match[1]), process=match[2].decode())

    return dict(schema=1, scope="parsed-software-transport-cut", architecture=arch,
                uid=1000, clock="in-range", cut=cut, completed_io=cut, writes=writes,
                flushes=flushes, operation=dict(ordinal=1, name="chmod", completed=False),
                io=transport, inode=inode, native_image=images[0][1],
                hardware_init=True, qemu_termination=termination,
                disk_oracle_checked=False, native_execution_verified=False,
                physical_power_loss=False, volatile_cache_loss_modeled=False)
