#!/usr/bin/env python3
"""Package the explicit net_socketcall fixture: the rescue root plus
/bin/socketcall-probe, a freestanding Linux-personality program that drives
TCP and UDP through legacy socketcall(2) (tests/native/linux_tcp_socketcall_probe.c).

The program is built with the profile's SysToolchain compiler and the Linux
static-exec layout (ports/musl/static-exec.ld) and marked EI_OSABI Linux, as
tools/musl_cc.py marks musl ports. Only the profiles whose Linux ABI has
socketcall apply: i386, MIPS O32 and 32-bit PowerPC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/native/linux_tcp_socketcall_probe.c"
LINKER_SCRIPT = ROOT / "ports/musl/static-exec.ld"
PROGRAM = "socketcall-probe"
# Compiler flags and the ELF identity (data encoding, Linux ABI version).
PROFILES = {
    "i386": (["-m32", "-march=i686"], 1, 0),
    "mips": (["-march=mips32r2", "-mabi=32", "-EB", "-mno-abicalls", "-fno-pic", "-G0"], 2, 1),
    "ppc": (["-mcpu=8548", "-msoft-float", "-msdata=none"], 2, 0),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(arch: str, compiler: Path, out: Path) -> list[str]:
    flags, order, abi_version = PROFILES[arch]
    command = [str(compiler), *flags, "-std=c11", "-O2", "-ffreestanding", "-fno-stack-protector", "-fno-builtin",
               "-nostdlib", "-static", "-Wall", "-Wextra", "-Werror", "-Wl,-e,_start",
               "-Wl,-T," + str(LINKER_SCRIPT), "-Wl,--defsym,USER_BASE=0x40000000",
               "-Wl,-z,max-page-size=4096", "-Wl,-z,noexecstack", str(SOURCE), "-o", str(out)]
    subprocess.run(command, check=True)
    data = bytearray(out.read_bytes())
    if data[:7] != b"\x7fELF\x01" + bytes((order, 1)) or data[7] != 0 or data[8] != 0:
        raise SystemExit(f"unexpected ELF identity for the {arch} socketcall probe")
    if int.from_bytes(data[16:18], "little" if order == 1 else "big") != 2:
        raise SystemExit("the socketcall probe is not ET_EXEC")
    data[7], data[8] = 3, abi_version  # ELFOSABI_LINUX; MIPS O32 images carry ABI version 1.
    out.write_bytes(data)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=sorted(PROFILES), required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--rescue-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.compiler.is_file():
        raise SystemExit(f"missing compiler: {args.compiler}")
    if not (args.rescue_root / "init").is_file():
        raise SystemExit(f"rescue root is not staged: {args.rescue_root}")
    if args.out.exists():
        shutil.rmtree(args.out)
    root = args.out / "root"
    shutil.copytree(args.rescue_root, root, symlinks=True)
    program = root / "bin" / PROGRAM
    if program.exists():
        raise SystemExit(f"rescue root already has {program.name}")
    command = build(args.arch, args.compiler, program)
    program.chmod(0o755)
    archive = args.out / "boot.okar"
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/mkarchive.py"), "--root", str(root), "--out", str(archive)],
                   check=True)
    manifest = {"schema": 1, "fixture": "net-socketcall", "architecture": args.arch, "program": f"/bin/{PROGRAM}",
                "personality": {"elf_osabi": 3, "abi_version": PROFILES[args.arch][2]},
                "source_sha256": digest(SOURCE), "linker_script_sha256": digest(LINKER_SCRIPT),
                "compiler": {"path": str(args.compiler), "sha256": digest(args.compiler)}, "command": command,
                "program_sha256": digest(program), "archive_sha256": digest(archive)}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[net-socketcall] packaged {args.arch} probe {manifest['program_sha256'][:12]} into {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
