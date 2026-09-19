#!/usr/bin/env python3
"""Run ObfuscationKernel with an ObfuscationOS rootfs image attached."""

from __future__ import annotations

import argparse
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def normalize_arch(arch: str) -> str:
    aliases = {
        "x64": "x86_64",
        "amd64": "x86_64",
        "arm64": "aarch64",
        "riscv64": "rv64",
        "loong64": "loongarch64",
    }
    return aliases.get(arch, arch)


def virtio_disk_args(disk: Path, mmio: bool = False) -> list[str]:
    return [
        "-drive",
        f"file={disk},format=raw,if=none,id=fsdisk",
        "-device",
        "virtio-blk-device,drive=fsdisk" if mmio else "virtio-blk-pci,drive=fsdisk",
    ]


def ramfb_args() -> list[str]:
    return ["-device", "ramfb"]


def command_for(qemu: Path, arch: str, kernel: Path, rootfs: Path, display: str) -> list[str]:
    if arch not in {"i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"}:
        raise SystemExit(f"qemu-distro is not configured for {arch}")

    common = ["-serial", "stdio", "-monitor", "none", "-no-reboot", "-display", display]
    if arch == "i386":
        common += ["-cpu", "max"]
    if arch in {"x86_64", "i386"} and kernel.suffix == ".bin":
        return [
            str(qemu),
            "-drive",
            f"file={kernel},format=raw,if=ide",
            "-boot",
            "c",
            "-vga",
            "none",
            *common,
            *ramfb_args(),
            *virtio_disk_args(rootfs),
        ]
    if arch in {"x86_64", "i386"}:
        return [
            str(qemu),
            "-m",
            "512M",
            "-kernel",
            str(kernel),
            "-vga",
            "none",
            *common,
            *ramfb_args(),
            *virtio_disk_args(rootfs),
        ]
    if arch in {"aarch64", "arm32"}:
        return [
            str(qemu),
            "-M",
            "virt",
            "-cpu",
            "cortex-a57" if arch == "aarch64" else "cortex-a15",
            "-m",
            "512M",
            "-kernel",
            str(kernel),
            *common,
            "-device",
            "ramfb",
            "-device",
            "virtio-keyboard-device",
            "-device",
            "virtio-mouse-device",
            *virtio_disk_args(rootfs, mmio=True),
        ]
    if arch in {"rv64", "rv32"}:
        return [
            str(qemu),
            "-M",
            "virt",
            "-m",
            "512M",
            "-bios",
            "none",
            "-kernel",
            str(kernel),
            *common,
            "-device",
            "ramfb",
            "-device",
            "virtio-keyboard-device",
            "-device",
            "virtio-mouse-device",
            *virtio_disk_args(rootfs, mmio=True),
        ]
    if arch in {"mips", "mips64", "ppc"}:
        cpu = ["-cpu", "MIPS64R2-generic"] if arch == "mips64" else []
        return [str(qemu), "-M", "ppce500" if arch == "ppc" else "malta",
                *cpu, "-m", "256M", "-kernel", str(kernel), *common,
                *virtio_disk_args(rootfs)]
    return [
        str(qemu),
        "-M",
        "virt",
        "-m",
        "2G",
        "-kernel",
        str(kernel),
        *common,
        "-device",
        "ramfb",
        "-device",
        "virtio-keyboard-pci",
        "-device",
        "virtio-mouse-pci",
        *virtio_disk_args(rootfs),
    ]


def run_until_marker(command: list[str], timeout: float, require_native: bool = False, require_storage: bool = False) -> int:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    pending = b""
    result = 124
    observed = set()

    def inspect_line(raw: bytes) -> int | None:
        line = raw.decode(errors="replace")
        print(line, end="" if line.endswith("\n") else "\n")
        if line.startswith("OK_TEST_FAIL ") or "boot=degraded" in line or "boot=failed" in line:
            return 1
        # Kernel boot and test markers precede extension startup. Only the
        # OS-owned final marker proves the distribution extension started.
        if "acceptance=FAIL" in line or "shell_pipeline=FAIL" in line or line.startswith("POSIX_CHECK failed:"):
            return 1
        if require_storage and (line.startswith("OK_STORAGE source=archive") or line.startswith("OK_NATIVE startup=")):
            return 1
        if line.startswith("OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw"):
            observed.add("storage")
        if line.startswith("OK_SYSTEM_GUI boot=complete"):
            observed.add("gui")
        if line.startswith("OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass"):
            observed.add("userland")
        if line.startswith("OK_NATIVE scope=hardware timer=preempted"):
            observed.add("preemption")
        required = {"gui", "userland", "preemption"} if require_native else {"gui"}
        if require_storage:
            required.add("storage")
        if required <= observed:
            return 0
        return None

    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout], [], [], 0.1)
            if not readable:
                continue
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                if pending:
                    inspected = inspect_line(pending)
                    if inspected is not None:
                        result = inspected
                break
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                inspected = inspect_line(line + b"\n")
                if inspected is not None:
                    return inspected
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        else:
            process.wait()
        process.stdout.close()
    return result


def run_interactive(command: list[str]) -> int:
    process = subprocess.Popen(command, text=True)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            return process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qemu",
        required=True,
        type=Path,
        help="Absolute QEMU executable from the systoolchain package",
    )
    parser.add_argument("--arch", required=True)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--rootfs", required=True, type=Path)
    parser.add_argument("--fs", choices=("simplefs", "ext4"), required=True)
    parser.add_argument("--require-native", action="store_true", help="Require actual userland acceptance and timer preemption")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--display", default="none", choices=("none", "sdl"), help="QEMU display backend")
    parser.add_argument("--interactive", action="store_true", help="Keep QEMU running until the window/process exits")
    parser.add_argument("--persist", action="store_true", help="Use the supplied ext4 image directly; preserve guest writes")
    args = parser.parse_args()
    if args.persist and args.fs != "ext4":
        raise SystemExit("--persist requires --fs ext4")

    arch = normalize_arch(args.arch)
    qemu = args.qemu.resolve()
    kernel = args.kernel.resolve()
    rootfs = args.rootfs.resolve()
    if not qemu.is_file():
        raise SystemExit(f"QEMU executable does not exist: {qemu}")
    if not kernel.is_file():
        raise SystemExit(f"kernel image does not exist: {kernel}")
    if not rootfs.is_file():
        raise SystemExit(f"rootfs image does not exist: {rootfs}")

    with tempfile.TemporaryDirectory(prefix="obfuscationos-qemu-") as temp_dir:
        runtime_rootfs = rootfs if args.persist else Path(temp_dir) / rootfs.name
        if not args.persist:
            shutil.copy2(rootfs, runtime_rootfs)
        command = command_for(qemu, arch, kernel, runtime_rootfs, args.display)
        print(f"[qemu-distro] arch={arch} fs={args.fs} qemu={qemu} kernel={kernel} rootfs={rootfs}")
        if args.interactive:
            print(f"[qemu-distro] display={args.display} interactive=1")
            return run_interactive(command)
        code = run_until_marker(command, args.timeout, args.require_native, args.fs == "ext4")
        if code == 124:
            print("[qemu-distro] timeout before required OS completion markers", file=sys.stderr)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
