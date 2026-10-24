#!/usr/bin/env python3
"""Source-only SDK65 actual-QEMU recipe draft; independent qualification pending.

Adapted from qualified OS/scripts/test_shared_files.py. This separately named
observer consumes prepared artifacts; it never compiles or packages them.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from qemu_distro import command_for

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from write_seal_recipe_inputs import ARCHES, admit_inputs, sha, verify_inputs

PROMPT = b"oksh> "
DETAILS = (b"acceptance=pass version=3 actual_native_alias=1 guest=1 physical_machine=0 english=1 "
           b"distinct_vas=1 canonical_io=1 vectors=1 vector_rollback=1 additive_seals=1 final_seals=1 "
           b"dup=1 fork=1 prot_none=1 offset_alias=1 partial_unmap=1 map_fixed=1 file_replacement=1 "
           b"file_capacity=1 descriptor_capacity=1 page_capacity=1 reclamation=40")
RIGHTS = b"queue_last_owner=pass roundtrip=pass cloexec=pass alias=pass discard=pass"
OLD = (b"OK_NATIVE_SHARED_FILES " + DETAILS, b"OK_NATIVE_SHARED_RIGHTS " + RIGHTS,
       b"OK_MUSL_SHARED_FILES " + DETAILS, b"OK_STATIC_SHARED_RIGHTS " + RIGHTS,
       b"OK_SHARED_FILES_SUITE native=2 static_musl=2 child_exit=0")
SEAL = (b"scope=hardware english=1 producer_exit=pass queue_owner=pass readonly=pass busy_aliases=pass "
        b"combined_rollback=pass idempotent=pass write=refused vectors=refused empty=noop mmap=refused "
        b"mprotect=refused fixed_rollback=pass mixed_rollback=pass store_fault=pass final_close=pass")
FAULT = b"OK_NATIVE scope=hardware fault=contained"
FAILURES = (b"SHARED_FILES_FAIL", b"SHARED_RIGHTS_FAIL", b"SHARED_WRITE_SEAL_FAIL",
            b"SHARED_WRITE_SEAL_SUITE_FAIL", b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_TEST_FAIL",
            b"boot=failed", b"boot=degraded", b"OK_NATIVE scope=hardware enter=failed",
            b"Segmentation fault", b"qemu: fatal", b"qemu-system:")
SHAPES = (rb"OK_NATIVE_SHARED_FILES(?!_LEDGER)", b"OK_NATIVE_SHARED_RIGHTS", b"OK_MUSL_SHARED_FILES",
          b"OK_STATIC_SHARED_RIGHTS", b"OK_SHARED_FILES_SUITE", b"OK_NATIVE_SHARED_WRITE_SEAL",
          b"OK_STATIC_SHARED_WRITE_SEAL", b"OK_SHARED_WRITE_SEAL_STAGE", b"OK_SHARED_WRITE_SEAL_SUITE")
FRAME_FIELDS = {"version", "source", "used", "total", "allocations", "releases", "pinned", "user",
                "objects", "free", "pending", "reserve", "user_limit", "object_quarantine"}
FILE_FIELDS = {"version", "files", "aliases", "retiring_files", "retained_frames", "reserved_cells"}
MAX_SERIAL = 64 * 1024 * 1024


def exact_lines(data: bytes, marker: bytes) -> list:
    return list(re.finditer(rb"(?m)^" + re.escape(marker) + rb"\r?\n", data))


def failure_scan(data: bytes) -> None:
    for marker in FAILURES:
        if marker in data:
            raise ValueError("guest/QEMU failure: " + repr(marker))


def parse_fields(payload: bytes, expected: set[str]) -> dict:
    fields = {}
    for item in payload.decode("ascii").split():
        key, separator, value = item.partition("=")
        if not separator or key in fields or key not in expected:
            raise ValueError("malformed, duplicate or unexpected owner ledger field")
        if key == "source":
            if value not in ("firmware", "linker"):
                raise ValueError("unknown owner page source")
            fields[key] = value
        else:
            if not re.fullmatch(r"[0-9]+", value):
                raise ValueError("invalid owner count")
            fields[key] = int(value)
    if set(fields) != expected:
        raise ValueError("incomplete owner ledger")
    return fields


def owner_evidence(raw: bytes, completion: int, offset: int) -> dict:
    pairs = list(re.finditer(rb"(?m)^OK_NATIVE_FRAMES ([^\r\n]+)\r?\n"
                            rb"OK_NATIVE_SHARED_FILES_LEDGER ([^\r\n]+)\r?\n", raw))
    shaped = list(re.finditer(rb"(?m)^[^\r\n]*(?:OK_NATIVE_FRAMES|OK_NATIVE_SHARED_FILES_LEDGER)"
                             rb"[^\r\n]*(?:\r?\n|$)", raw))
    if not pairs or len(shaped) < 2:
        raise ValueError("missing final paired owner ledgers")
    pair = pairs[-1]
    if (pair.start() < completion or pair.start() != shaped[-2].start() or
            pair.end() != shaped[-1].end()):
        raise ValueError("latest owner ledgers are not the exact pair after suite completion")
    frames, files = parse_fields(pair[1], FRAME_FIELDS), parse_fields(pair[2], FILE_FIELDS)
    if frames["version"] != 2 or files["version"] != 1:
        raise ValueError("owner ledger version mismatch")
    if any(files[name] for name in FILE_FIELDS - {"version"}):
        raise ValueError("shared ownership not reclaimed")
    if any(frames[name] for name in ("pinned", "pending", "object_quarantine")):
        raise ValueError("physical retirement pending")
    if (frames["allocations"] - frames["releases"] != frames["used"] or
            frames["used"] != frames["user"] + frames["objects"] or
            not 0 < frames["total"] <= 1024 or frames["reserve"] > frames["total"] or
            frames["free"] + frames["used"] != frames["total"] or
            frames["reserve"] + frames["user_limit"] != frames["total"] or
            frames["user"] > frames["user_limit"] or frames["objects"] > frames["reserve"]):
        raise ValueError("physical accounting/capacity mismatch")
    return {"frames": frames, "files": files, "raw_pair_extent": [offset + pair.start(), offset + pair.end()]}


def stable_owners(evidence: dict) -> dict:
    return {name: evidence["frames"][name] for name in
            ("source", "used", "total", "user", "objects", "free", "reserve", "user_limit")}


def suite_evidence(raw: bytes, offset: int, profile: str) -> dict:
    failure_scan(raw)
    if PROMPT in raw:
        raise ValueError("command body contains an interior prompt")
    stages = ([(b"shared-files-suite", OLD)] if profile == "paired" else
              [(b"shared-files-native", OLD[:1]), (b"shared-rights-native", OLD[1:2])])
    stages += [(b"shared-write-seal-native", (b"OK_NATIVE_SHARED_WRITE_SEAL " + SEAL,))]
    if profile == "paired":
        stages += [(b"shared-write-seal-static", (b"OK_STATIC_SHARED_WRITE_SEAL " + SEAL,))]
    expected, stage_bounds = [], []
    for name, markers in stages:
        begin = b"OK_SHARED_WRITE_SEAL_STAGE name=" + name + b" state=begin"
        end = b"OK_SHARED_WRITE_SEAL_STAGE name=" + name + b" state=complete child_exit=0"
        expected.extend((begin, *markers, end))
        stage_bounds.append((name, begin, markers[-1], end))
    final = (b"OK_SHARED_WRITE_SEAL_SUITE version=1 legacy_suite=1 native=3 static_musl=3 child_exit=0"
             if profile == "paired" else
             b"OK_SHARED_WRITE_SEAL_SUITE version=1 legacy_suite=0 native=3 static_musl=0 child_exit=0")
    expected.append(final)
    positions = {}
    for marker in expected:
        matches = exact_lines(raw, marker)
        if len(matches) != 1:
            raise ValueError("missing, duplicate or inexact full marker: " + repr(marker))
        positions[marker] = matches[0]
    starts = [positions[marker].start() for marker in expected]
    if starts != sorted(starts):
        raise ValueError("suite markers out of execution order")
    shaped = list(re.finditer(rb"(?m)^[^\r\n]*(?:" + b"|".join(SHAPES) +
                             rb")[^\r\n]*(?:\r?\n|$)", raw))
    if [match.group() for match in shaped] != [positions[marker].group() for marker in expected]:
        raise ValueError("extra, prefixed, malformed or unexpected suite marker")
    faults = exact_lines(raw, FAULT)
    fault_shapes = list(re.finditer(rb"(?m)^[^\r\n]*fault=contained[^\r\n]*(?:\r?\n|$)", raw))
    if [match.span() for match in faults] != [match.span() for match in fault_shapes]:
        raise ValueError("inexact contained-fault record")
    assigned, fault_records = [], []
    for name, begin, success, end in stage_bounds:
        found = [match for match in faults
                 if positions[begin].end() <= match.start() < positions[success].start()]
        count = 2 if name.startswith(b"shared-write-seal-") else 0
        if len(found) != count:
            raise ValueError("wrong store-fault count for " + name.decode())
        assigned.extend(found)
        fault_records.append({"stage": name.decode(), "raw_fault_extents":
                              [[offset + match.start(), offset + match.end()] for match in found]})
    if [match.span() for match in assigned] != [match.span() for match in faults]:
        raise ValueError("unexpected fault outside a seal probe's begin/success interval")
    owners = owner_evidence(raw, positions[final].end(), offset)
    return {"body_extent": [offset, offset + len(raw)],
            "markers": [{"line": marker.decode(), "raw_extent":
                         [offset + positions[marker].start(), offset + positions[marker].end()]}
                        for marker in expected], "fault_evidence": fault_records, "owners": owners}


def process_table() -> dict:
    result = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except FileNotFoundError:
            continue
        result[int(entry.name)] = {"parent": int(fields[1]), "start": int(fields[19])}
    return result


def descendants(table: dict) -> set[int]:
    owned, pending = set(), {os.getpid()}
    while pending:
        children = {pid for pid, value in table.items() if value["parent"] in pending}
        children -= owned
        owned.update(children)
        pending = children
    return owned


def enable_subreaper() -> None:
    if sys.platform != "linux" or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise ValueError("Linux subreaper and pidfd supervision required")
    if descendants(process_table()):
        raise ValueError("observer must start without pre-existing child processes")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot enable descendant adoption")


def retire_tree(process: subprocess.Popen | None) -> dict:
    """Kill/reap every owned descendant, including setsid escapees, before hashes.

    This process is a subreaper and launches exactly one child. pidfds prevent
    PID reuse from redirecting a signal to an unrelated host process.
    """
    retired = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        table = process_table()
        owned = descendants(table)
        for pid in sorted(owned):
            try:
                descriptor = os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            try:
                current = process_table()
                if current.get(pid) != table[pid] or pid not in descendants(current):
                    continue
                signal.pidfd_send_signal(descriptor, signal.SIGSTOP)
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                retired.append({"pid": pid, "start_ticks": table[pid]["start"]})
            except ProcessLookupError:
                pass
            finally:
                os.close(descriptor)
        if process is not None:
            process.poll()  # Let Popen reap its own direct child first.
        no_children = False
        if process is None or process.returncode is not None:
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    no_children = True
                    break
                if not pid:
                    break
                retired.append({"reaped_pid": pid, "wait_status": status})
        if no_children and not descendants(process_table()) and (process is None or process.returncode is not None):
            # No living descendant remains to fork or retain serial/disk FDs.
            return {"complete": True, "mechanism": "linux-subreaper-pidfd", "retired": retired,
                    "qemu_returncode": None if process is None else process.returncode}
        time.sleep(.02)
    raise RuntimeError("owned process tree retirement unproven; serial/disk hashes forbidden")


def read_serial(path: Path) -> bytes:
    if path.stat().st_size > MAX_SERIAL:
        raise ValueError("serial size exceeds recipe bound")
    return path.read_bytes()


def await_prompt(process: subprocess.Popen, path: Path, cursor: int, timeout: float) -> tuple[bytes, int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = read_serial(path)
        failure_scan(raw)
        if process.poll() is not None:
            raise RuntimeError("QEMU exited before observer retirement")
        found = raw.find(PROMPT, cursor)
        if found >= 0:
            if found and raw[found - 1:found] != b"\n":
                raise ValueError("prompt has a prefix or is not at a raw line boundary")
            if raw.find(PROMPT, found + len(PROMPT)) >= 0:
                raise ValueError("unexpected extra prompt")
            return raw, found
        time.sleep(.02)
    raise TimeoutError("guest prompt deadline expired")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=ARCHES, required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--profile", choices=("native", "paired"), required=True)
    parser.add_argument("--expected-abi", type=int, required=True)
    for name in ("qemu", "kernel", "kernel-sdk", "rootfs", "inputs", "serial-log", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValueError("run with PYTHONDONTWRITEBYTECODE=1 python3 -B, without optimization")
    if not 0 < args.timeout <= 1800:
        raise ValueError("timeout must be in (0, 1800]")
    for name in ("qemu", "kernel", "kernel_sdk", "rootfs", "inputs", "serial_log", "out"):
        value = getattr(args, name)
        if not value.is_absolute() or value.resolve() != value:
            raise ValueError("explicit canonical absolute path required: " + name)
    if args.serial_log.parent != args.out or args.serial_log.name in {"result.json", "disk-run.ext4.img"}:
        raise ValueError("serial-log must be a distinct new direct child of out")
    inputs = admit_inputs(args)
    if any(Path(path).is_relative_to(args.out) for path in inputs["tracked_inputs"]):
        raise ValueError("output lane overlaps input artifacts")
    enable_subreaper()
    args.out.mkdir(parents=True, exist_ok=False)
    disk = args.out / "disk-run.ext4.img"
    kernel = args.out / ("kernel-run" + args.kernel.suffix)
    if kernel == args.serial_log:
        raise ValueError("serial/kernel output paths collide")
    record = {"schema": 1, "recipe": "sdk65-write-seal-v1", "status": "running", "abi_version": 65,
              "architecture": args.arch, "mode": args.mode, "profile": args.profile,
              "physical_machine": False, "isolated_desktop": False, "inputs": inputs,
              "runs": [], "retirement": {"complete": False}}
    process, serial_writer, error = None, None, None
    observed_boot, observed_bodies = b"", []
    old_signals = {}
    def interrupted(number, frame):
        raise InterruptedError("observer interrupted by signal " + str(number))
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        old_signals[number] = signal.signal(number, interrupted)
    try:
        shutil.copyfile(args.rootfs, disk)
        shutil.copyfile(args.kernel, kernel)
        if sha(disk) != inputs["files"]["rootfs"]["sha256"] or sha(kernel) != inputs["files"]["kernel"]["sha256"]:
            raise ValueError("private launch copies do not match admitted inputs")
        command = command_for(args.qemu, args.arch, kernel, disk, "none", native_profile=True)
        record["command"] = command
        serial_writer = args.serial_log.open("xb", buffering=0)
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=serial_writer,
                                   stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        raw, first = await_prompt(process, args.serial_log, 0, args.timeout)
        boot = raw[:first]
        if (len(exact_lines(boot, b"OK_SYSTEM_GUI boot=complete")) != 1 or
                len(exact_lines(boot, b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none")) != 1):
            raise ValueError("missing exact complete boot/storage markers")
        for prefix, expected in ((b"OK_SYSTEM_GUI boot=", b"OK_SYSTEM_GUI boot=complete"),
                                 (b"OK_STORAGE ", b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none")):
            shaped = list(re.finditer(rb"(?m)^[^\r\n]*" + re.escape(prefix) + rb"[^\r\n]*(?:\r?\n|$)", boot))
            if len(shaped) != 1 or shaped[0].group() not in (expected + b"\n", expected + b"\r\n"):
                raise ValueError("malformed, additional or prefixed boot/storage marker")
        record["boot_extent"] = [0, first]
        observed_boot = boot
        previous = first
        command_bytes = b"shared-write-seal-suite" + (b" --native" if args.profile == "native" else b"") + b"\n"
        for index in range(2):
            start = previous + len(PROMPT)
            # Do not discard any bytes read beyond the previous prompt.
            if len(read_serial(args.serial_log)) != start:
                raise ValueError("unexpected bytes after idle prompt before command")
            if process.stdin.write(command_bytes) != len(command_bytes):
                raise RuntimeError("short command submission")
            process.stdin.flush()
            raw, following = await_prompt(process, args.serial_log, start, args.timeout)
            evidence = suite_evidence(raw[start:following], start, args.profile)
            observed_bodies.append(raw[start:following])
            evidence.update(index=index + 1, command=command_bytes.decode(),
                            opening_prompt_extent=[previous, start],
                            closing_prompt_extent=[following, following + len(PROMPT)])
            if record["runs"] and stable_owners(evidence["owners"]) != stable_owners(record["runs"][0]["owners"]):
                raise ValueError("repeated complete suite changed stable physical owners")
            record["runs"].append(evidence)
            previous = following
        if process.poll() is not None:
            raise RuntimeError("QEMU died before controlled retirement")
        record["status"] = "awaiting-retirement"
    except BaseException as caught:
        error = repr(caught)
        record.update(status="fail", failure=error)
    finally:
        # A second ordinary signal must not interrupt ownership retirement.
        for number in old_signals:
            signal.signal(number, signal.SIG_IGN)
        try:
            record["retirement"] = retire_tree(process)
            if process is not None and process.stdin is not None:
                process.stdin.close()
            if serial_writer is not None:
                serial_writer.close()
            # No serial/disk final read or hash occurs before complete retirement.
            if args.serial_log.exists():
                raw = read_serial(args.serial_log)
                record["serial_sha256"] = sha(args.serial_log)
                record["serial_size"] = len(raw)
            else:
                raw = b""
            if disk.exists():
                record["final_disk_sha256"] = sha(disk)
            if kernel.exists():
                record["private_kernel_unchanged"] = sha(kernel) == inputs["files"]["kernel"]["sha256"]
            verify_inputs(inputs)
            record["inputs_unchanged"] = True
            if error is None:
                failure_scan(raw)
                if len(record["runs"]) != 2 or raw.count(PROMPT) != 3:
                    raise ValueError("require exactly two complete ordered prompt-bounded suites")
                if record["retirement"]["qemu_returncode"] != -signal.SIGKILL:
                    raise ValueError("QEMU exited independently of controlled process-tree retirement")
                if raw[:record["boot_extent"][1]] != observed_boot:
                    raise ValueError("boot extent changed before final retirement")
                record["boot_sha256"] = hashlib.sha256(observed_boot).hexdigest()
                for prefix in (b"OK_SYSTEM_GUI boot=", b"OK_STORAGE "):
                    if raw.count(prefix) != 1:
                        raise ValueError("additional boot/storage declaration outside its boot extent")
                if record["runs"][0]["closing_prompt_extent"] != record["runs"][1]["opening_prompt_extent"]:
                    raise ValueError("suite extents are not contiguous across their shared prompt")
                final_end = record["runs"][-1]["closing_prompt_extent"][1]
                if raw[final_end:]:
                    raise ValueError("unexpected serial tail after final prompt")
                for shape in (*SHAPES, b"fault=contained"):
                    count = sum(len(re.findall(shape, raw[run["body_extent"][0]:run["body_extent"][1]]))
                                for run in record["runs"])
                    if len(re.findall(shape, raw)) != count:
                        raise ValueError("suite/fault evidence outside the two command extents")
                for index, run in enumerate(record["runs"]):
                    for key in ("opening_prompt_extent", "closing_prompt_extent"):
                        begin, end = run[key]
                        if raw[begin:end] != PROMPT or (begin and raw[begin - 1:begin] != b"\n"):
                            raise ValueError("final serial has an inexact recorded prompt")
                    start, end = run["body_extent"]
                    if raw[start:end] != observed_bodies[index]:
                        raise ValueError("command body changed before process-tree retirement")
                    fresh = suite_evidence(raw[start:end], start, args.profile)
                    if any(run[key] != fresh[key] for key in fresh):
                        raise ValueError("final raw serial differs from observed command extent")
                    run["body_sha256"] = hashlib.sha256(raw[start:end]).hexdigest()
                if not record["private_kernel_unchanged"]:
                    raise ValueError("private kernel input changed")
                record["status"] = "pass"
        except BaseException as caught:
            error = repr(caught)
            record.update(status="fail", retirement_or_final_failure=error)
        finally:
            # An unproven-retirement record has no final serial/disk hashes.
            if not record["retirement"]["complete"]:
                record["hashes_withheld"] = "process tree retirement unproven"
            (args.out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
            for number, handler in old_signals.items():
                signal.signal(number, handler)
    if record["status"] != "pass":
        raise RuntimeError("write-seal observation failed: " + str(error))
    print(f"PASS {args.arch}/{args.mode}/{args.profile}: two actual QEMU suites; bootstrap privileged scope")


if __name__ == "__main__":
    main()
