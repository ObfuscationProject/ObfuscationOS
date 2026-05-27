#!/usr/bin/env python3
"""Run ObfuscationKernel with an ObfuscationOS rootfs image attached."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


QEMU_SYSTEM_BY_ARCH = {
    "x86_64": "qemu-system-x86_64",
    "aarch64": "qemu-system-aarch64",
    "rv64": "qemu-system-riscv64",
    "loongarch64": "qemu-system-loongarch64",
}


def normalize_arch(arch: str) -> str:
    aliases = {
        "x64": "x86_64",
        "amd64": "x86_64",
        "arm64": "aarch64",
        "riscv64": "rv64",
        "loong64": "loongarch64",
    }
    return aliases.get(arch, arch)


def virtio_disk_args(disk: Path) -> list[str]:
    return [
        "-drive",
        f"file={disk},format=raw,if=none,id=fsdisk",
        "-device",
        "virtio-blk-pci,drive=fsdisk",
    ]


def ramfb_args() -> list[str]:
    return ["-device", "ramfb"]


def command_for(arch: str, kernel: Path, rootfs: Path, display: str) -> list[str]:
    qemu = QEMU_SYSTEM_BY_ARCH.get(arch)
    if qemu is None:
        raise SystemExit(f"qemu-distro is not configured for {arch}")
    qemu_path = shutil.which(qemu)
    if qemu_path is None:
        raise SystemExit(f"QEMU executable missing: {qemu}")

    common = ["-serial", "stdio", "-monitor", "none", "-no-reboot", "-display", display]
    if arch == "x86_64" and kernel.suffix == ".bin":
        return [
            qemu_path,
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
    if arch == "x86_64":
        return [
            qemu_path,
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
    if arch == "aarch64":
        return [
            qemu_path,
            "-M",
            "virt",
            "-cpu",
            "cortex-a57",
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
            *virtio_disk_args(rootfs),
        ]
    if arch == "rv64":
        return [
            qemu_path,
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
            *virtio_disk_args(rootfs),
        ]
    return [
        qemu_path,
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


def run_until_marker(command: list[str], timeout: float) -> int:
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    markers = ("ObfuscationOS init: userland online", "OK_DEBUG boot=complete", "OK_TEST_PASS ")
    seen_boot = False

    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if line:
            print(line, end="")
            if any(marker in line for marker in markers):
                seen_boot = True
                break
        if process.poll() is not None:
            break

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    return 0 if seen_boot else 124


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
    parser.add_argument("--arch", required=True)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--rootfs", required=True, type=Path)
    parser.add_argument("--fs", choices=("simplefs", "ext4"), required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--display", default="none", help="QEMU display backend, for example none, gtk, or sdl")
    parser.add_argument("--interactive", action="store_true", help="Keep QEMU running until the window/process exits")
    args = parser.parse_args()

    arch = normalize_arch(args.arch)
    kernel = args.kernel.resolve()
    rootfs = args.rootfs.resolve()
    if not kernel.is_file():
        raise SystemExit(f"kernel image does not exist: {kernel}")
    if not rootfs.is_file():
        raise SystemExit(f"rootfs image does not exist: {rootfs}")

    command = command_for(arch, kernel, rootfs, args.display)
    print(f"[qemu-distro] arch={arch} fs={args.fs} kernel={kernel} rootfs={rootfs}")
    if args.interactive:
        print(f"[qemu-distro] display={args.display} interactive=1")
        return run_interactive(command)
    code = run_until_marker(command, args.timeout)
    if code == 124:
        print("[qemu-distro] timeout before boot/userland marker", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
