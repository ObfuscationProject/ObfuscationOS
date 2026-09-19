#!/usr/bin/env python3
"""Validate or assemble an image from an exported ObfuscationKernel SDK."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ARCH_TRIPLES = {
    "i386": "i386-elf", "x86_64": "x86_64-elf", "aarch64": "aarch64-elf",
    "arm32": "arm-none-eabi", "rv64": "riscv64-elf", "rv32": "riscv32-elf",
    "loongarch64": "loongarch64-elf", "mips": "mips-elf", "mips64": "mips64-elf", "ppc": "powerpc-eabi",
}
BIOS_PAYLOAD_CAPACITY = 256 * 32 * 512


def validate_sdk(sdk: Path, arch: str, mode: str, compiler: Path | None = None) -> dict:
    sdk = sdk.resolve()
    manifest_path = sdk / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"kernel SDK missing: {manifest_path}; build 'xmake -b kernel-sdk' in ObfuscationKernel first")
    manifest = json.loads(manifest_path.read_text())
    expected = {"schema": 1, "abi_version": 2, "arch": arch, "mode": mode, "triple": ARCH_TRIPLES.get(arch)}
    for key, value in expected.items():
        if value is None or manifest.get(key) != value:
            raise ValueError(f"kernel SDK {key} mismatch: expected {value!r}, found {manifest.get(key)!r}")
    if not manifest.get("kernel_version"):
        raise ValueError("kernel SDK has no kernel version")
    for field in ("cxxflags", "asflags", "ldflags", "defines"):
        flags = manifest.get(field)
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError(f"kernel SDK has invalid or missing {field}")
    image_format = manifest.get("image_format")
    if image_format not in {"bios-disk", "elf", "linux-image"}:
        raise ValueError(f"unsupported kernel image format: {image_format}")
    files = manifest.get("files", {})
    required = {"lib/libokernel.a", "lib/libokernel_boot.a", "boot/linker.ld", "image/kernel.bin", "image/kernel.elf", "include/ok/uapi/syscall.h"}
    if image_format == "bios-disk":
        required.add("boot/boot16.bin")
    if not required.issubset(files):
        raise ValueError(f"kernel SDK manifest is missing artifacts: {sorted(required - files.keys())}")
    for relative, digest in files.items():
        artifact = (sdk / relative).resolve()
        if not artifact.is_relative_to(sdk):
            raise ValueError(f"kernel SDK artifact escapes SDK root: {relative}")
        if not artifact.is_file():
            raise ValueError(f"kernel SDK artifact is missing: {relative}")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise ValueError(f"kernel SDK artifact checksum mismatch: {relative}")
    if compiler:
        triple = subprocess.check_output([str(compiler), "-dumpmachine"], text=True).strip()
        version = subprocess.check_output([str(compiler), "-dumpfullversion"], text=True).strip()
        if triple != manifest["triple"] or version != manifest["compiler"]["version"]:
            raise ValueError(f"C++ module ABI requires SDK compiler {manifest['triple']} GCC {manifest['compiler']['version']}; got {triple} GCC {version}")
    return manifest


def assemble_image(elf: Path, output: Path, sdk: Path, image_format: str, objcopy: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if image_format == "elf":
        shutil.copy2(elf, output)
        return
    if objcopy is None:
        raise ValueError("non-ELF image requires --objcopy")
    payload_path = output.with_name(output.stem + "_payload.bin")
    subprocess.run([str(objcopy), "-O", "binary", str(elf), str(payload_path)], check=True)
    payload = payload_path.read_bytes()
    if image_format == "linux-image":
        output.write_bytes(payload)
        return
    boot_sector = (sdk / "boot/boot16.bin").read_bytes()
    if len(boot_sector) != 512 or boot_sector[-2:] != b"\x55\xaa":
        raise ValueError("invalid BIOS boot sector in kernel SDK")
    if len(payload) > BIOS_PAYLOAD_CAPACITY:
        raise ValueError(f"kernel payload too large: {len(payload)} > {BIOS_PAYLOAD_CAPACITY}")
    output.write_bytes(boot_sector + payload + bytes(BIOS_PAYLOAD_CAPACITY - len(payload)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "assemble"))
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--objcopy", type=Path)
    args = parser.parse_args()
    try:
        manifest = validate_sdk(args.sdk, args.arch, args.mode, args.compiler)
        if args.command == "assemble":
            if args.elf is None or args.out is None:
                parser.error("assemble requires --elf and --out")
            assemble_image(args.elf, args.out, args.sdk, manifest["image_format"], args.objcopy)
        print(f"[kernel-sdk] {args.arch}/{args.mode} version={manifest['kernel_version']} verified: {args.sdk}")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"kernel SDK error: {exc}\n")


if __name__ == "__main__":
    main()
