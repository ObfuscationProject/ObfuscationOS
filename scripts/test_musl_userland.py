#!/usr/bin/env python3
"""Package explicit audited probes on a scratch root and execute them in QEMU."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from musl_source import VERSION, inspect_elf
from kernel_sdk import ARCH_TRIPLES
from realtime_evidence import fixture_seconds, validate_realtime
from mkdir_evidence import GROUP_ID, check_metadata, creation_slots, qualify_disk


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def failure_line(serial):
    for line in serial.splitlines(keepends=True):
        if line.endswith(b"\n") and any(marker in line for marker in
                (b"OK_TEST_FAIL ", b"POSIX_CHECK failed:", b"MUSL_CHECK failed:")):
            return line.decode(errors="replace").strip()
    return None


def directory_inode_evidence(serial):
    import re
    lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_DIRECTORY_INODE ")]
    pattern = rb"OK_MUSL_DIRECTORY_INODE name=musl-positional inode=([1-9][0-9]*)\r?\n"
    if len(lines) != 2 or any(not re.fullmatch(pattern, line) for line in lines):
        raise RuntimeError("directory inode evidence requires two complete records")
    values = [int(re.fullmatch(pattern, line)[1]) for line in lines]
    if values[0] != values[1] or values[0] > 0xffffffffffffffff:
        raise RuntimeError("directory inode changed across stable repeated runs")
    return values[0]


def umask_file_evidence(serial):
    import re
    lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_UMASK_FILES ")]
    pattern = rb"OK_MUSL_UMASK_FILES slot=([01]) parent=0644 restricted=0600 child=0660 exec=0640\r?\n"
    matched = [re.fullmatch(pattern, line) for line in lines]
    if len(matched) != 2 or not all(matched) or {int(m[1]) for m in matched} != {0, 1}:
        raise RuntimeError("umask evidence requires two distinct complete creation slots")
    return [int(m[1]) for m in matched]


def validate_file_private(serial, architecture):
    if architecture not in ARCH_TRIPLES:
        raise ValueError("unknown private file mapping architecture")
    mmap2_arches = {"i386", "arm32", "rv32", "mips", "ppc"}
    syscall_name = b"mmap2" if architecture in mmap2_arches else b"mmap"
    marker = (b"OK_MUSL_FILE_PRIVATE scope=hardware offset=pass short_length=pass "
              b"tail_zero=pass errno=pass close=pass unlink=pass private_write=pass fork=pass syscall=" + syscall_name)
    native = (b"OK_MUSL_NATIVE scope=hardware libc=musl-1.2.5 "
              b"startup=pass tls=pass errno=pass clock=pass")
    starts = []
    records = []
    for index, line in enumerate(serial.splitlines(keepends=True)):
        if line.rstrip(b"\r\n") == native and line.endswith(b"\n"):
            starts.append(index)
        if b"OK_MUSL_FILE_PRIVATE" in line:
            if not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker:
                raise RuntimeError("malformed or wrapped musl private file mapping record")
            records.append(index)
    if len(starts) != 2 or len(records) != 2 or not (starts[0] < records[0] < starts[1] < records[1]):
        raise RuntimeError("musl private file mapping requires two complete exact guest records")


def validate_shared_futex_rejection(serial):
    marker = b"OK_MUSL_SHARED_FUTEX scope=hardware wait=unsupported wake=unsupported cleanup=pass"
    lines = [line for line in serial.splitlines(keepends=True)
             if line.startswith(b"OK_MUSL_SHARED_FUTEX ")]
    if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
        raise RuntimeError("shared anonymous futex rejection requires two exact guest records")


def validate_execution(serial, require_files=False, require_heap=False, require_process=False, require_paths=False, require_fds=False, require_seek=False, require_pipes=False, require_sleep=False, require_poll=False, require_open=False, require_positional=False, require_select=False, require_directory=False, require_umask=False):
    require_directory = require_directory or require_umask
    if require_umask:
        marker = b"OK_MUSL_UMASK scalar=pass creation=pass existing=pass fork=pass exec=pass isolation=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_UMASK ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl umask evidence requires two complete runs")
        umask_file_evidence(serial)
    require_select = require_select or require_directory
    if require_directory:
        marker = b"OK_MUSL_DIRECTORY opendir=pass readdir=pass cookies=pass shared=pass inode=pass copies=pass bounded=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_DIRECTORY ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl directory evidence requires two complete runs")
        directory_inode_evidence(serial)
    require_positional = require_positional or require_select
    require_open = require_open or require_positional
    if require_positional:
        marker = b"OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_POSITIONAL ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl positional evidence requires two complete runs")
    if require_select:
        marker = b"OK_MUSL_SELECT select=pass pselect=pass layouts=pass timeout=pass wake=pass sets=pass errors=pass mask=unsupported"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_SELECT ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl select evidence requires two complete runs")
    require_poll = require_poll or require_open
    if require_open:
        marker = b"OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_OPEN ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl open evidence requires two complete runs")
    require_sleep = require_sleep or require_poll
    if require_poll:
        marker = b"OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_POLL ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl poll evidence requires two complete runs")
    require_pipes = require_pipes or require_sleep
    require_seek = require_seek or require_sleep
    if require_sleep:
        marker = b"OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_SLEEP ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl sleep evidence requires two complete runs")
    require_fds = require_fds or require_seek or require_pipes
    if require_seek:
        marker = b"OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_SEEK ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl seek evidence requires two complete runs")
    if require_pipes:
        marker = b"OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_PIPES ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl pipe evidence requires two complete runs")
    require_paths = require_paths or require_fds
    if require_fds:
        marker = b"OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_FDS ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl descriptor evidence requires two complete runs")
    require_process = require_process or require_paths
    if require_paths:
        marker = b"OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_PATHS ")]
        if len(lines) != 2 or any(not line.endswith(b"\n") or line.rstrip(b"\r\n") != marker for line in lines):
            raise RuntimeError("musl pathname evidence requires two complete runs")
    require_files = require_files or require_process
    require_heap = require_heap or require_process
    probe = b"OK_MUSL_NATIVE scope=hardware libc=musl-1.2.5 startup=pass tls=pass errno=pass clock=pass"
    parent = b"OK_MUSL_PARENT scope=hardware native=pass exec=pass wait=pass exit=pass repeat=pass"
    if serial.count(probe) != 2 or parent not in serial:
        raise RuntimeError("missing musl execution or native-parent wait/exit evidence")
    files = b"OK_MUSL_FILES scope=hardware openat=pass flags=pass append=pass vector_io=pass symlink=pass limits=pass sync=pass"
    if require_files and serial.count(files) != 2:
        raise RuntimeError("missing musl file and sync execution evidence")
    heap = b"OK_MUSL_HEAP malloc=pass calloc=pass realloc=pass alignment=pass reuse=pass"
    heap_vm = b"OK_MUSL_HEAP_VM brk=pass fixed=pass pressure=pass reclaim=pass"
    if require_heap and (serial.count(heap) != 2 or serial.count(heap_vm) != 2):
        raise RuntimeError("missing musl heap and VM execution evidence")
    if require_process:
        for marker in (
            b"OK_MUSL_PROCESS identity=pass fork=pass isolation=pass exec=pass wait=pass shared_fd=pass",
            b"OK_MUSL_PROCESS_CAPACITY bounded=pass reap=pass retry=pass",
        ):
            if serial.count(marker) != 2:
                raise RuntimeError("missing musl process/heap execution evidence")
        limits = [line.strip() for line in serial.splitlines() if line.startswith(b"OK_MUSL_PROCESS_LIMIT ")]
        if len(limits) != 2:
            raise RuntimeError("missing musl process resource-limit evidence")
        for line in limits:
            match = re.fullmatch(rb"OK_MUSL_PROCESS_LIMIT errno=(EAGAIN|ENOMEM) children=([0-9]+)", line)
            if not match or not 0 < int(match[2]) < 64:
                raise RuntimeError("invalid musl process resource-limit evidence")


def validate_runtime_frames(serial, architecture):
    # Kernel SDK 75: every profile discovers its boot memory and the native page
    # pool shares the kernel frame allocator (OK_BOOT_MEMORY, OK_NATIVE_FRAMES v3).
    lines = [line.strip() for line in serial.splitlines()]
    boots = [line for line in lines if line.startswith(b"OK_BOOT_MEMORY ")]
    if len(boots) != 1:
        raise RuntimeError("missing unique kernel boot memory provenance")
    boot = re.fullmatch(rb"OK_BOOT_MEMORY version=1 protocol=([a-z0-9-]+) source=(e820|fdt|board) status=pass "
                        rb"image_begin=(0x[0-9a-f]+) image_end=(0x[0-9a-f]+) direct_offset=(0x[0-9a-f]+) "
                        rb"managed_pages=([0-9]+) managed_ranges=([0-9]+) excluded=([0-9]+)", boots[0])
    if not boot:
        raise RuntimeError("boot memory was not discovered from the loader")
    first, last = int(boot[3],16), int(boot[4],16)
    managed_pages, managed_ranges = int(boot[6]), int(boot[7])
    if first >= last or not managed_pages:
        raise RuntimeError("invalid complete linker reservation or empty managed RAM")
    ranges = []
    for line in lines:
        if line.startswith(b"OK_BOOT_MEMORY_RANGE "):
            match = re.fullmatch(rb"OK_BOOT_MEMORY_RANGE base=(0x[0-9a-f]+) size=(0x[0-9a-f]+)",line)
            if not match:
                raise RuntimeError("invalid managed frame provenance")
            base, size = int(match[1],16), int(match[2],16)
            if not size or (base | size) & 4095 or (base < last and first < base + size) or base == 0:
                raise RuntimeError("managed frames overlap linked image or page zero, or are unaligned")
            if any(base < b+s and b < base+size for b,s in ranges):
                raise RuntimeError("managed frame ranges overlap")
            ranges.append((base,size))
    if len(ranges) != managed_ranges or sum(size for _,size in ranges) != managed_pages*4096:
        raise RuntimeError("managed ranges differ from the boot memory summary")
    if architecture == "arm32":
        entries = [line for line in lines if line.startswith(b"OK_ARM32_ENTRY")]
        sources = [line for line in lines if line.startswith(b"OK_BOOT_MEMORY_SOURCE")]
        if len(entries) != 1 or len(sources) != 1:
            raise RuntimeError("missing unique ARM loader state or FDT source")
        entry = re.fullmatch(rb"OK_ARM32_ENTRY cpsr=(0x[0-9a-f]+) sctlr=(0x[0-9a-f]+) mpidr=(0x[0-9a-f]+) status=pass",entries[0])
        storage = re.fullmatch(rb"OK_BOOT_MEMORY_SOURCE base=(0x[0-9a-f]+) size=(0x[0-9a-f]+) decoded=(0x[0-9a-f]+)",sources[0])
        if not entry or not storage or not lines.index(entries[0]) < lines.index(boots[0]) < lines.index(sources[0]):
            raise RuntimeError("invalid ARM loader identity or source order")
        cpsr,sctlr,mpidr = map(lambda word:int(word,16),entry.groups())
        address,length = int(storage[1],16), int(storage[2],16)
        if cpsr & 0x23f != 0x13 or sctlr & 0x02000005 or mpidr & 0xffffff:
            raise RuntimeError("ARM physical-access entry state was not qualified")
        if address & 7 or not 40 <= length <= 2*1024*1024 or not 0x40000000 <= address < address+length <= 0x60000000:
            raise RuntimeError("ARM FDT storage exceeds entry access window")
        if first != 0x40010000 or last > 0x50000000 or address < last and first < address+length:
            raise RuntimeError("ARM complete image overlaps firmware or exceeds runtime aperture")
        for base,size in ranges:
            if not 0x40010000 <= base < base+size <= 0x50000000 or base < address+length and address < base+size:
                raise RuntimeError("ARM frames overlap FDT/boot prefix or exceed supervisor RAM")
    statistics = []
    ownership = []
    reserve = limit = total = None
    for line in lines:
        if line.startswith(b"OK_NATIVE_FRAMES "):
            match = re.fullmatch(rb"OK_NATIVE_FRAMES version=3 source=firmware used=([0-9]+) total=([0-9]+) allocations=([0-9]+) releases=([0-9]+) pinned=([0-9]+) user=([0-9]+) objects=([0-9]+) free=([0-9]+) pending=([0-9]+) reserve=([0-9]+) user_limit=([0-9]+)(?: object_quarantine=0)?",line)
            if not match:
                raise RuntimeError("native allocation source or accounting version mismatch")
            used,current_total,allocated,released,pinned,user,objects,free,pending,current_reserve,user_limit = map(int,match.groups())
            # The allocator is shared: other kernel owners hold the remaining frames.
            if (pinned or pending or allocated-released != used or user+objects != used or
                    used+free > current_total or current_total > managed_pages or
                    not 0 < current_reserve < current_total or user_limit + current_reserve > current_total or
                    user > user_limit or objects > current_reserve):
                raise RuntimeError("native frame ownership, purpose or retirement accounting mismatch")
            if reserve is not None and (reserve, limit, total) != (current_reserve, user_limit, current_total):
                raise RuntimeError("native object reserve or user quota changed during execution")
            reserve, limit, total = current_reserve, user_limit, current_total
            if statistics and (allocated < statistics[-1][1] or released < statistics[-1][2]):
                raise RuntimeError("native frame counters moved backward")
            statistics.append((used,allocated,released))
            ownership.append((user,objects,free))
    if len(statistics) < 3 or statistics[0] != (0,0,0) or statistics[-1][2] == 0:
        raise RuntimeError("missing native allocation/reclamation evidence")
    images = []
    for line in lines:
        if line.startswith(b"OK_NATIVE_IMAGE "):
            match = re.fullmatch(rb"OK_NATIVE_IMAGE personality=linux source=firmware pages=([0-9]+) physical_first=(0x[0-9a-f]+) physical_last=(0x[0-9a-f]+) owner=retained",line)
            if not match or not 0 < int(match[1]) <= 1024:
                raise RuntimeError("Linux image lacks retained frame ownership")
            low,high = int(match[2],16),int(match[3],16)
            if low > high or (low|high)&4095:
                raise RuntimeError("invalid Linux physical image bounds")
            offset = int(boot[5],16)
            if any(not any(base <= address - offset and address - offset + 4096 <= base+size for base,size in ranges)
                   for address in (low,high)):
                raise RuntimeError("Linux image physical pages lie outside qualified ranges")
            images.append(int(match[1]))
    if len(images) < 4:
        raise RuntimeError("missing repeated Linux exec ownership evidence")
    return {"accounting_version":3,"source":"firmware","boot_protocol":boot[1].decode(),"total":total,
            "managed_pages":managed_pages,"linux_images":len(images),"object_reserve":reserve,"user_limit":limit,
            "remaining_user":ownership[-1][0],"remaining_objects":ownership[-1][1],"free":ownership[-1][2],
            "pending":0,"allocations":statistics[-1][1],"releases":statistics[-1][2],
            "remaining":statistics[-1][0],"pinned":0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=ARCH_TRIPLES, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--rootfs-tree", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True, help="Explicit audited probe build directory")
    parser.add_argument("--runner", type=Path, required=True, help="Native musl-test-runner ELF")
    # Non-ext4 boot uses the embedded archive, not a disk-mounted namespace.
    # Appending a probe to simplefs cannot make it executable in that image.
    parser.add_argument("--fs", choices=("ext4",), default="ext4")
    parser.add_argument("--out", type=Path, required=True, help="New evidence and scratch-image directory")
    parser.add_argument("--timeout", type=float, default=100)
    parser.add_argument("--require-files", action="store_true", help="Require openat/vector/flags/limits/sync guest checks")
    parser.add_argument("--require-file-private", action="store_true", help="Require two exact nonzero-offset private file mapping guest records")
    parser.add_argument("--require-shared-futex", action="store_true", help="Require two Linux-personality MAP_SHARED anonymous futex rejection records")
    parser.add_argument("--require-heap", action="store_true", help="Require mapped brk, fixed mappings and musl heap/pressure checks")
    parser.add_argument("--require-process", action="store_true", help="Require musl identity/fork/exec/wait/limits plus heap and file checks")
    parser.add_argument("--require-runtime-frames", action="store_true", help="Require process/heap execution and qualified runtime frame provenance")
    parser.add_argument("--require-paths", action="store_true", help="Require musl cwd/readlink and buffer checks in addition to process/file/heap gates")
    parser.add_argument("--require-fds", action="store_true", help="Require descriptor duplication, flags, exec and pressure plus all previous musl gates")
    parser.add_argument("--require-seek", action="store_true", help="Require seek ABI, shared offset, errors and bounded capacity plus preceding musl gates")
    parser.add_argument("--require-pipes", action="store_true", help="Require pipe/pipe2, EOF/nonblocking/reference/fork/exec/rollback checks and all preceding gates")
    parser.add_argument("--require-sleep", action="store_true", help="Require elapsed sleep/deadline/resolution/error/peer checks and preceding musl gates")
    parser.add_argument("--require-poll", action="store_true", help="Require poll/ppoll readiness, elapsed waits, raw timeout updates and preceding musl gates")
    parser.add_argument("--require-select", action="store_true", help="Require public select/pselect, raw layouts and cumulative musl gates")
    parser.add_argument("--require-open", action="store_true", help="Require public open/creat, raw legacy entries and cumulative musl gates")
    parser.add_argument("--require-positional", action="store_true", help="Require public pread/pwrite, shared offsets, copy faults and cumulative musl gates")
    parser.add_argument("--require-directory", action="store_true", help="Require bounded directory streams, inode/cookie/copy checks and all preceding gates")
    parser.add_argument("--require-umask", action="store_true", help="Require creation-mask, fork/exec and fresh offline mode checks plus earlier gates")
    parser.add_argument("--require-realtime", action="store_true", help="Require native and musl realtime/error checks in parent, fork and exec plus earlier gates")
    parser.add_argument("--rtc-base", help="Explicit UTC YYYY-MM-DDTHH:MM:SS source fixture for realtime qualification")
    parser.add_argument("--require-mkdir", action="store_true", help="Require directory creation and offline ownership/inheritance plus all earlier gates")
    args = parser.parse_args()
    args.require_realtime = args.require_realtime or args.require_mkdir
    if args.require_realtime:
        args.rtc_base = args.rtc_base or "2024-02-29T12:34:56"
        fixture_seconds(args.rtc_base)
        args.require_umask = True
    elif args.rtc_base:
        parser.error("--rtc-base requires --require-realtime")
    args.require_directory = args.require_directory or args.require_umask
    args.require_select = args.require_select or args.require_directory
    args.require_positional = args.require_positional or args.require_select
    args.require_open = args.require_open or args.require_positional
    args.require_poll = args.require_poll or args.require_open
    args.require_sleep = args.require_sleep or args.require_poll
    args.require_pipes = args.require_pipes or args.require_sleep
    args.require_seek = args.require_seek or args.require_sleep
    args.require_fds = args.require_fds or args.require_seek or args.require_pipes
    args.require_paths = args.require_paths or args.require_fds
    args.require_process = args.require_process or args.require_paths or args.require_runtime_frames
    if args.require_process:
        args.require_files = True
        args.require_heap = True
    args.require_files = args.require_files or args.require_file_private
    manifest = json.loads((args.probe / "manifest.json").read_text())
    executable = args.probe / "bootstrap.elf"
    if (manifest.get("architecture") != args.arch or manifest.get("musl") != VERSION or
            manifest.get("status") != "built-not-executed" or
            manifest.get("elf_sha256") != digest(executable)):
        raise ValueError("probe manifest, source version or executable hash mismatch")
    inspect_elf(executable, args.arch)
    inspect_elf(args.runner, args.arch)
    if executable.read_bytes()[7] != 3 or args.runner.read_bytes()[7] != 0:
        raise ValueError("Linux probe and native runner require explicit distinct ELF personalities")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / "root"
    shutil.copytree(args.rootfs_tree, root, symlinks=True)
    for source, name in ((executable, "musl-bootstrap"), (args.runner, "musl-test-runner")):
        destination = root / "bin" / name
        shutil.copy2(source, destination)
        destination.chmod(0o755)
    if args.require_files:
        link = root / "home/musl-link"
        if link.exists() or link.is_symlink():
            raise ValueError("scratch root already contains musl-link")
        link.symlink_to("musl-file")
    # Cumulative probes execute their mkdir checks even when only an earlier
    # evidence gate was requested. Prepare the private fixture independently.
    (root / "home/musl-mkdir-sgid").mkdir()
    disk = output / ("rootfs." + args.fs + ".img")
    command = [sys.executable, str(TOOLS / "mkext4.py")]
    with (output / "package.log").open("w") as log:
        subprocess.run(command + ["--root", str(root), "--out", str(disk)], check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    commands = output / "mkdir-fixture.commands"
    commands.write_text("set_inode_field /home/musl-mkdir-sgid mode 042777\n"
                        "set_inode_field /home/musl-mkdir-sgid uid 0\n"
                        f"set_inode_field /home/musl-mkdir-sgid gid {GROUP_ID}\n")
    with (output / "mkdir-fixture.log").open("w") as log:
        subprocess.run(["debugfs", "-w", "-f", str(commands), str(disk)], check=True, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run(["e2fsck", "-fn", str(disk)], check=True, stdout=log, stderr=subprocess.STDOUT)
    initial = subprocess.run(["debugfs", "-R", "stat /home/musl-mkdir-sgid", str(disk)], text=True, capture_output=True, check=True)
    (output / "mkdir-fixture.stat.log").write_text(initial.stdout + initial.stderr)
    check_metadata(initial.stdout, ("directory", 0o2777, 0, GROUP_ID, 2))
    record = {"scope": "qemu-native-execution", "architecture": args.arch, "filesystem": args.fs,
              "musl": VERSION, "status": "running", "inputs": {
                  str(path.resolve()): digest(path) for path in
                  (args.kernel, executable, args.runner, args.probe / "manifest.json", disk, Path(__file__))}}
    # Ordinary build paths are replaced by later matrix configurations. Boot the
    # retained bytes so failed guests remain reproducible from this directory.
    kernel_input = output / "kernel-input.bin"
    shutil.copyfile(args.kernel, kernel_input)
    if digest(kernel_input) != record["inputs"][str(args.kernel.resolve())]:
        raise RuntimeError("kernel changed while preserving guest input")
    shutil.copyfile(args.probe / "manifest.json", output / "probe-manifest.json")
    # The guest mutates disk. Preserve its fully prepared input separately so
    # later audits can verify both ends without reconstructing host fixtures.
    initial_disk = output / ("rootfs-input." + args.fs + ".img")
    shutil.copyfile(disk, initial_disk)
    initial_digest = record["inputs"][str(disk.resolve())]
    if digest(initial_disk) != initial_digest or digest(disk) != initial_digest:
        raise RuntimeError("disk changed while preserving guest input")
    record["initial_disk"] = {"path": initial_disk.name, "sha256": initial_digest,
                              "scope": "prepared pre-guest bytes; guest uses a separate mutable image"}
    serial = bytearray()
    command = command_for(args.qemu.resolve(), args.arch, kernel_input, disk, "none",
                          native_profile=args.arch == "ppc")
    if args.require_realtime:
        command += ["-rtc", "base=" + args.rtc_base + ",clock=vm,driftfix=none"]
        record["inputs"][str(TOOLS / "realtime_evidence.py")] = digest(TOOLS / "realtime_evidence.py")
    record["inputs"][str(TOOLS / "mkdir_evidence.py")] = digest(TOOLS / "mkdir_evidence.py")
    record["command"] = list(map(str, command))
    record["qemu_binary_sha256"] = digest(args.qemu.resolve())
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdin is not None and process.stdout is not None

    def receive(predicate):
        deadline = time.monotonic() + args.timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise RuntimeError("timeout waiting for musl execution")
            readable, _, _ = select.select([process.stdout], [], [], .1)
            if not readable:
                continue
            chunk = os.read(process.stdout.fileno(), 8192)
            if not chunk:
                raise RuntimeError("QEMU exited before acceptance")
            serial.extend(chunk)
            if failure := failure_line(serial):
                raise RuntimeError("guest acceptance failed: " + failure)

    try:
        receive(lambda: b"OK_SYSTEM_GUI boot=complete" in serial and b"oksh> " in serial)
        if args.fs == "ext4" and b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("probe root was not mounted from ext4")
        start = len(serial)
        process.stdin.write(b"musl-test-runner\n")
        process.stdin.flush()
        receive(lambda: b"oksh> " in serial[start:])
        validate_execution(serial[start:], args.require_files, args.require_heap, args.require_process, args.require_paths, args.require_fds, args.require_seek, args.require_pipes, args.require_sleep, args.require_poll, args.require_open, args.require_positional, args.require_select, args.require_directory, args.require_umask)
        if args.require_file_private:
            validate_file_private(serial[start:], args.arch)
        if args.require_shared_futex:
            validate_shared_futex_rejection(serial[start:])
        if args.require_realtime:
            record["realtime"] = validate_realtime(serial[start:], args.arch, args.rtc_base)
            record["realtime_checks"] = "pass"
        if args.require_mkdir:
            record["mkdir_slots"] = creation_slots(serial[start:])
        # Native syscall dispatch must still work after repeated Linux exits.
        start = len(serial)
        process.stdin.write(b"hello | cat\n")
        process.stdin.flush()
        receive(lambda: b"oksh> " in serial[start:])
        if b"hello from ObfuscationOS userland" not in serial[start:]:
            raise RuntimeError("native personality regression after musl execution")
        if args.require_runtime_frames:
            record["runtime_frames"] = validate_runtime_frames(serial, args.arch)
        record["status"] = "awaiting-offline" if args.require_files else "pass"
        record["pipe_checks"] = "pass" if args.require_pipes else "not-requested"
        record["pipe_signal_scope"] = "EPIPE errno only; SIGPIPE delivery not implemented" if args.require_pipes else "not-requested"
        record["heap_checks"] = "pass" if args.require_heap else "not-requested"
        record["file_checks"] = "pass" if args.require_files else "not-requested"
        record["file_private_checks"] = "pass" if args.require_file_private else "not-requested"
        record["shared_futex_checks"] = "pass" if args.require_shared_futex else "not-requested"
    except Exception as error:
        record["status"] = "fail"
        record["failure"] = str(error)
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        (output / "serial.log").write_bytes(serial)
        record["serial_sha256"] = digest(output / "serial.log")
        record["initial_disk"]["unchanged_after_guest"] = digest(initial_disk) == initial_digest
        if not record["initial_disk"]["unchanged_after_guest"]:
            record["status"] = "fail"
            record["failure"] = "preserved initial disk changed during guest execution"
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    if not record["initial_disk"]["unchanged_after_guest"]:
        raise RuntimeError(record["failure"])
    if args.require_files:
        # These are clean synchronization checks, not crash recovery.
        try:
            with (output / "fsck.log").open("w") as log:
                check = subprocess.run(["e2fsck", "-fn", str(disk)], stdout=log, stderr=subprocess.STDOUT)
            offline = output / "musl-file.bin"
            with (output / "debugfs.log").open("w") as log:
                subprocess.run(["debugfs", "-R", "dump /home/musl-file musl-file.bin", str(disk)],
                               cwd=output, check=True, stdout=log, stderr=subprocess.STDOUT)
            record["offline"] = {"fsck_exit_code": check.returncode, "expected_file": "abcdef",
                                 "disk_sha256": digest(disk), "log_sha256": digest(output / "fsck.log")}
            if check.returncode or not offline.is_file() or offline.read_bytes() != b"abcdef":
                raise RuntimeError("offline filesystem or musl file bytes disagree")
            if args.require_process:
                process_bytes = output / "musl-process.bin"
                with (output / "debugfs-process.log").open("w") as log:
                    subprocess.run(["debugfs", "-R", "dump /home/musl-process musl-process.bin", str(disk)],
                                   cwd=output, check=True, stdout=log, stderr=subprocess.STDOUT)
                if not process_bytes.is_file() or process_bytes.read_bytes() != b"parentchild!":
                    raise RuntimeError("offline shared file offset bytes disagree")
                record["offline"]["process_file"] = "parentchild!"
                record["process_checks"] = "pass"
            if args.require_positional:
                positional_bytes = output / "musl-positional.bin"
                with (output / "debugfs-positional.log").open("w") as log:
                    subprocess.run(["debugfs", "-R", "dump /home/musl-positional musl-positional.bin", str(disk)],
                                   cwd=output, check=True, stdout=log, stderr=subprocess.STDOUT)
                if not positional_bytes.is_file() or positional_bytes.read_bytes() != b"aXYZef!":
                    raise RuntimeError("offline positional file bytes disagree")
                record["offline"]["positional_file"] = "aXYZef!"
                record["positional_checks"] = "pass"
            if args.require_open:
                open_bytes = output / "musl-open.bin"
                with (output / "debugfs-open.log").open("w") as log:
                    subprocess.run(["debugfs", "-R", "dump /home/musl-open musl-open.bin", str(disk)],
                                   cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
                if open_bytes.read_bytes() != b"created!":
                    raise RuntimeError("musl open/creat persisted bytes differ")
                record["offline"]["open_file"] = "created!"
                record["open_checks"] = "pass"
                record["open_scope"] = "public musl open/creat and raw legacy entries where present; no complete flags, TTY or cancellation claim"
            if args.require_mkdir:
                record["mkdir_nodes"] = qualify_disk(disk, output)
                record["mkdir_checks"] = "pass"
                record["mkdir_scope"] = "bounded nonjournalled directory creation, initial ownership and setgid inheritance; no ACL, crash atomicity or SMP claim"
            if args.require_umask:
                import re
                modes = {"parent": 0o644, "restricted": 0o600, "child": 0o660, "exec": 0o640}
                receipts = {}
                for slot in umask_file_evidence(serial):
                    for role, mode in modes.items():
                        name = f"musl-mask-{slot}-{role}"
                        result = subprocess.run(["debugfs", "-R", "stat /home/" + name, str(disk)], text=True, capture_output=True, check=True)
                        (output / (name + ".stat.log")).write_text(result.stdout + result.stderr)
                        match = re.search(r"^Inode:\s+(\d+)\s+Type:\s+regular\s+Mode:\s+([0-7]+)\s", result.stdout, re.MULTILINE)
                        content = subprocess.run(["debugfs", "-R", "cat /home/" + name, str(disk)], capture_output=True, check=True).stdout
                        (output / (name + ".bin")).write_bytes(content)
                        if not match or int(match[2], 8) != mode or content != role.encode():
                            raise RuntimeError("offline umask type, permission or contents disagree: " + name)
                        receipts[name] = {"inode": int(match[1]), "mode": mode, "data_sha256": digest(output / (name + ".bin")),
                                          "stat_log_sha256": digest(output / (name + ".stat.log"))}
                if len({r["inode"] for r in receipts.values()}) != 8:
                    raise RuntimeError("umask creation slots do not contain eight distinct inodes")
                record["umask_checks"] = "pass"
                record["umask_files"] = receipts
                record["umask_scope"] = "bounded process mask, ordinary fork isolation and exec preservation; no ACL/CLONE_FS/SMP claim"
            if args.require_directory:
                import re
                inode = directory_inode_evidence(serial)
                result = subprocess.run(["debugfs", "-R", "stat /home/musl-positional", str(disk)], text=True, capture_output=True, check=True)
                (output / "debugfs-directory-inode.log").write_text(result.stdout + result.stderr)
                match = re.search(r"^Inode:\s+(\d+)\s", result.stdout, re.MULTILINE)
                if not match or int(match[1]) != inode:
                    raise RuntimeError("native directory inode differs from offline ext4 inode")
                record["directory_checks"] = "pass"
                record["directory_inode"] = inode
                record["directory_scope"] = "bounded RAM/ext4 inode providers and logical cookies; no mutation races, fdopendir/stat, SMP or physical hardware claim"
            if args.require_select:
                record["select_checks"] = "pass"
                record["select_scope"] = "bounded 32-FD sets and boot-CPU deadlines; null signal masks only; no sockets, signals or SMP"
            if args.require_poll:
                record["poll_checks"] = "pass"
                record["poll_scope"] = "bounded boot-CPU readiness and deadlines; non-null masks unsupported; no signals, SMP or sockets"
            if args.require_sleep:
                record["sleep_checks"] = "pass"
                record["sleep_scope"] = "monotonic deadlines; no signals, cancellation or absolute realtime"
            if args.require_seek:
                seek_bytes = output / "musl-seek.bin"
                with (output / "debugfs-seek.log").open("w") as log:
                    subprocess.run(["debugfs", "-R", "dump /home/musl-seek musl-seek.bin", str(disk)],
                                   cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
                if seek_bytes.read_bytes() != b"abcdef!":
                    raise RuntimeError("musl seek persisted bytes differ")
                record["offline"]["seek_file"] = "abcdef!"
                record["seek_checks"] = "pass"
            if args.require_fds:
                descriptor_bytes = output / "musl-fds.bin"
                with (output / "debugfs-fds.log").open("w") as log:
                    subprocess.run(["debugfs", "-R", "dump /home/musl-fds musl-fds.bin", str(disk)],
                                   cwd=output, check=True, stdout=log, stderr=subprocess.STDOUT)
                if not descriptor_bytes.is_file() or descriptor_bytes.read_bytes() != b"abcdef!x":
                    raise RuntimeError("offline duplicated/exec-inherited descriptor bytes disagree")
                record["offline"]["descriptor_file"] = "abcdef!x"
                record["descriptor_checks"] = "pass"
            record["status"] = "pass"
        except Exception as error:
            record["status"] = "fail"
            record["failure"] = str(error)
            raise
        finally:
            (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"PASS scope=qemu-native-execution arch={args.arch} fs={args.fs} musl=startup-tls-errno-clock native=exec-wait-exit-repeat")


if __name__ == "__main__":
    main()
