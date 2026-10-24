#!/usr/bin/env python3
"""Stage a disposable native JBD2 replay probe using only one exact exported SDK.

This never admits ext4, writes a journal or modifies repository files. Every
QEMU disk is freshly created under the requested output directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kernel_sdk import ARCH_TRIPLES, assemble_image, validate_sdk

STAGE = Path(__file__).resolve().parent
PROFILES = tuple(ARCH_TRIPLES)
QEMU = {
    "i386": "qemu-system-i386", "x86_64": "qemu-system-x86_64", "aarch64": "qemu-system-aarch64",
    "arm32": "qemu-system-arm", "rv32": "qemu-system-riscv32", "rv64": "qemu-system-riscv64",
    "loongarch64": "qemu-system-loongarch64", "mips": "qemu-system-mips",
    "mips64": "qemu-system-mips64", "ppc": "qemu-system-ppc",
}
DEFINES = {
    "replay": [], "reopen": ["OK_JBD2_REOPEN"], "readonly": ["OK_JBD2_READONLY"],
    "corrupt-commit": ["OK_JBD2_CORRUPT"], "read-error": ["OK_JBD2_READ_ERROR"],
    "write-error": ["OK_JBD2_WRITE_ERROR"], "flush-error": ["OK_JBD2_FLUSH_ERROR"],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def call(command, log):
    log.append([str(item) for item in command])
    subprocess.run(command, check=True)


def snapshot_sdk(source, target, arch, compiler, mode="debug"):
    source = source.resolve()
    manifest_bytes = (source / "manifest.json").read_bytes()
    manifest = validate_sdk(source, arch, mode, compiler)
    required_headers = {"include/ok/fs/jbd2.hpp", "include/ok/fs/jbd2_replay.hpp"}
    if not required_headers.issubset(manifest["files"]):
        raise ValueError("the exact SDK does not export both JBD2 headers")
    target.mkdir()
    for relative, expected in manifest["files"].items():
        data = (source / relative).read_bytes()
        if digest(data) != expected:
            raise ValueError("SDK changed while taking immutable snapshot: " + relative)
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    if (source / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("SDK manifest changed during snapshot")
    (target / "manifest.json").write_bytes(manifest_bytes)
    validate_sdk(target, arch, mode, compiler)
    return manifest, digest(manifest_bytes)


def machine(qemu, arch, image):
    if arch in ("i386", "x86_64"):
        return [qemu, "-m", "128M", "-drive", f"file={image},format=raw,if=ide", "-boot", "c",
                "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"]
    if arch in ("mips", "mips64", "ppc"):
        result = [qemu, "-M", "ppce500" if arch == "ppc" else "malta", "-m", "256M", "-kernel", str(image)]
        if arch == "mips64": result += ["-cpu", "MIPS64R2-generic"]
        return result
    result = [qemu, "-M", "virt", "-m", "2G" if arch == "loongarch64" else "256M", "-kernel", str(image)]
    if arch in ("arm32", "aarch64"):
        result += ["-cpu", "cortex-a15" if arch == "arm32" else "cortex-a57"]
    if arch in ("rv32", "rv64"): result += ["-bios", "none"]
    return result


def boot(command, marker, log_path):
    if "-display" not in command:
        command += ["-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        output = bytearray()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for key, _ in selector.select(timeout=0.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk: output.extend(chunk)
            if marker.encode() in output or b"JBD2_NATIVE_FAIL" in output or process.poll() is not None:
                break
        # Target only this freshly spawned disposable probe VM.
        if process.poll() is None:
            process.terminate()
        try:
            tail, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            tail, _ = process.communicate(timeout=5)
        output.extend(tail or b"")
        text = output.decode(errors="replace")
        log_path.write_text(text)
        print(text, end="", flush=True)
        if marker not in text or "JBD2_NATIVE_FAIL" in text:
            raise RuntimeError("native probe failed; inspect " + str(log_path))
        return process.returncode


