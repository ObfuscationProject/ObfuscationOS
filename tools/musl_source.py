#!/usr/bin/env python3
"""Inspect/build an explicit pinned musl archive; never execute a target binary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import struct
import sys
import tarfile
import tempfile

from kernel_sdk import ARCH_TRIPLES
from plan_ledger import CONTRACTS, load_json

VERSION = "1.2.5"
PORTS = {"i386": "i386", "x86_64": "x86_64", "aarch64": "aarch64", "arm32": "arm",
         "rv64": "riscv64", "rv32": "riscv32", "loongarch64": "loongarch64", "mips": "mips", "mips64": "mips64", "ppc": "powerpc"}
# These are explicit compiler experiments preserving existing CPUs and FP choices.
# They do not turn an ELF-targeted compiler into a qualified Linux toolchain.
FLAGS = {
    "i386": ["-m32", "-march=i686"], "x86_64": ["-m64", "-mno-red-zone"],
    "aarch64": ["-march=armv8-a"], "arm32": ["-march=armv7-a", "-marm", "-mfloat-abi=soft"],
    "rv64": ["-march=rv64gc", "-mabi=lp64d"], "rv32": ["-march=rv32gc", "-mabi=ilp32d"],
    "loongarch64": ["-march=loongarch64", "-mabi=lp64d", "-msimd=none"],
    "mips": ["-march=mips32r2", "-mabi=32", "-EB", "-mhard-float", "-mabicalls", "-G0"],
    "mips64": ["-march=mips64r2", "-mabi=64", "-EB", "-mhard-float", "-mabicalls", "-G0"],
    "ppc": ["-mcpu=8548", "-msoft-float", "-mlong-double-64", "-msdata=none"],
}

# Explicit local tool pin used by the audited PowerPC application experiment.
# This is the installed binary identity, not an upstream release-authentication claim.
PPC_CLANG_SHA256 = "8ef402d453d1ba4902e4ee0f0f847f6cfa01400c95aa43c24e97818b9c0e3f45"
PPC_CLANG_TARGET = "powerpc-unknown-linux-musl"
PPC_CLANG_FLAGS = ["--target=powerpc-linux-musl", "-mcpu=8548", "-msoft-float",
                   "-mlong-double-64", "-ftls-model=local-exec"]


def ppc_frontend(arch: str, path: Path | None, *, required: bool = False) -> dict | None:
    if path is None:
        if required and arch == "ppc":
            raise ValueError("PowerPC ordinary main requires explicit --ppc-clang; EABI GCC injects __eabi")
        return None
    if arch != "ppc":
        raise ValueError("--ppc-clang is only supported for PowerPC")
    compiler = path.resolve()
    if not compiler.is_file() or digest(compiler) != PPC_CLANG_SHA256:
        raise ValueError("PowerPC Clang executable does not match the audited binary SHA-256 pin")
    command = [str(compiler), *PPC_CLANG_FLAGS]
    version = subprocess.check_output([str(compiler), "--version"], text=True).splitlines()[0]
    target = subprocess.check_output([*command, "-dumpmachine"], text=True).strip()
    if "clang version 18.1.3 " not in version or target != PPC_CLANG_TARGET:
        raise ValueError("PowerPC Clang version or effective Linux target mismatch")
    macros = subprocess.check_output([*command, "-nostdinc", "-dM", "-E", "-x", "c", "-"],
                                     input="", text=True)
    definitions = {}
    for line in macros.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[0] == "#define":
            definitions[parts[1]] = parts[2]
    expected = {"__SIZEOF_POINTER__": "4", "__SIZEOF_LONG_DOUBLE__": "8",
                "__BYTE_ORDER__": "__ORDER_BIG_ENDIAN__", "__powerpc__": "1",
                "__linux__": "1", "__clang_major__": "18"}
    if any(definitions.get(name) != value for name, value in expected.items()):
        raise ValueError("PowerPC Clang effective ABI macros mismatch")
    return {"path": str(compiler), "sha256": PPC_CLANG_SHA256, "version": version,
            "target": target, "flags": list(PPC_CLANG_FLAGS), "abi_macros": expected,
            "scope": "ordinary C application frontend; native SDK and musl libc compiler unchanged"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_pin() -> dict:
    pin = next(row for row in load_json(CONTRACTS / "ledger.json")["references"] if row["id"] == "musl")
    if pin["version"] != VERSION or pin["status"] != "source-pinned" or not pin["archive_sha256"]:
        raise ValueError("musl source pin is missing or unsupported by this recipe")
    return pin


def inspect_archive(path: Path) -> dict:
    pin = source_pin()
    if digest(path) != pin["archive_sha256"]:
        raise ValueError("musl archive checksum mismatch")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        seen = set()
        total = 0
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or "\\" in member.name
                    or not name.parts or name.parts[0] != f"musl-{VERSION}"
                    or not (member.isfile() or member.isdir()) or member.name in seen):
                raise ValueError(f"unsafe or duplicate musl archive member: {member.name}")
            total += member.size
            if len(members) > 10000 or total > 64 * 1024 * 1024:
                raise ValueError("musl archive exceeds source extraction budget")
            seen.add(member.name)
        for row in pin["audited_files"]:
            item = archive.extractfile(f"musl-{VERSION}/" + row["path"])
            if item is None or hashlib.sha256(item.read()).hexdigest() != row["sha256"]:
                raise ValueError(f"musl audited source checksum mismatch: {row['path']}")
        for port in PORTS.values():
            if f"musl-{VERSION}/arch/{port}/syscall_arch.h" not in seen:
                raise ValueError(f"musl port missing: {port}")
    return {"schema_version": 1, "version": VERSION, "archive_sha256": pin["archive_sha256"],
            "source_url": pin["url"], "signature_verified": False, "ports_present": PORTS,
            "qualification": "source-inspection-only", "native_execution": False}


def extract_archive(path: Path, directory: Path) -> Path:
    # Called only after archive admission; the official pin contains files/dirs only.
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            target = directory / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
    return directory / f"musl-{VERSION}"



def inspect_elf(path: Path, arch: str) -> dict:
    expected = next(row for row in load_json(CONTRACTS / "ledger.json")["architectures"] if row["id"] == arch)
    data = path.read_bytes()
    elf_class = 1 if expected["elf_class"] == 32 else 2
    order = 1 if expected["byte_order"] == "little" else 2
    machine = {"i386": 3, "x86_64": 62, "aarch64": 183, "arm32": 40, "rv64": 243,
               "rv32": 243, "loongarch64": 258, "mips": 8, "mips64": 8, "ppc": 20}[arch]
    if len(data) < (52 if elf_class == 1 else 64) or data[:7] != b"\x7fELF" + bytes((elf_class, order, 1)):
        raise ValueError("probe ELF class/endian/version mismatch")
    endian = "<" if order == 1 else ">"
    elf_type, actual_machine = struct.unpack_from(endian + "HH", data, 16)
    if elf_type != 2 or actual_machine != machine:
        raise ValueError("probe must be ET_EXEC for the selected architecture")
    phoff = struct.unpack_from(endian + ("I" if elf_class == 1 else "Q"), data, 28 if elf_class == 1 else 32)[0]
    phsize, phcount = struct.unpack_from(endian + "HH", data, 42 if elf_class == 1 else 54)
    if phsize < (32 if elf_class == 1 else 56) or phcount == 0 or phoff + phsize * phcount > len(data):
        raise ValueError("probe ELF program headers are invalid")
    kinds = [struct.unpack_from(endian + "I", data, phoff + index * phsize)[0] for index in range(phcount)]
    if 3 in kinds or 1 not in kinds:
        raise ValueError("probe must contain PT_LOAD and have no PT_INTERP")
    return {"class": expected["elf_class"], "byte_order": expected["byte_order"], "machine": machine,
            "type": "ET_EXEC", "interpreter": None, "executed": False}



def validate_build_path(path: Path) -> None:
    # configure stores these paths in shell/make source, so only literal path
    # characters are accepted. Source archive paths are handled directly by Python.
    if re.fullmatch(r"/[-A-Za-z0-9_./+]+", str(path)) is None:
        raise ValueError("upstream configure/make requires an absolute path using only letters, digits, /, -, _, ., +")


def build_static(args) -> dict:
    inspection = inspect_archive(args.archive)
    if args.jobs < 1 or args.jobs > 64:
        raise ValueError("jobs must be between 1 and 64")
    frontend = ppc_frontend(args.arch, getattr(args, "ppc_clang", None))
    project = Path(__file__).resolve().parents[1]
    output = (args.out or project / "build/ports/musl" / VERSION / args.arch / args.mode).resolve()
    if output.exists():
        raise ValueError(f"output already exists; choose a new --out directory: {output}")
    toolchain = args.toolchain.resolve()
    triple = ARCH_TRIPLES[args.arch]
    bindir = toolchain / "bin"
    compiler = bindir / (triple + "-gcc")
    for tool in ("gcc", "ar", "ranlib", "readelf", "as", "ld"):
        if not (bindir / (triple + "-" + tool)).is_file():
            raise ValueError(f"missing explicit cross tool: {triple}-{tool}")
    identity = subprocess.check_output([str(compiler), "-dumpmachine"], text=True).strip()
    if identity != triple:
        raise ValueError(f"cross compiler target mismatch: expected {triple}, got {identity}")
    version = subprocess.check_output([str(compiler), "-dumpfullversion"], text=True).strip()
    validate_build_path(toolchain)
    validate_build_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".musl-stage-", dir=output.parent))
    commands = []
    manifest = {**inspection, "architecture": args.arch, "mode": args.mode, "compiler": {"triple": triple, "version": version},
                # musl's inline LL/SC primitives require optimization. At -O0,
                # LoongArch inserts stack stores between LL and SC and its
                # clock initialization spins even under Linux user emulation.
                "cflags": FLAGS[args.arch] + ["-O2"] + (["-g"] if args.mode == "debug" else []),
                "ldflags": ["-Wl,--oformat=elf64-bigmips"] if args.arch == "mips64" else [],
                "tool_sha256": {tool: digest(bindir / (triple + "-" + tool)) for tool in ("gcc", "ar", "ranlib", "readelf", "as", "ld")},
                "probe_compiler": frontend or {"path": str(compiler), "sha256": digest(compiler), "target": triple, "version": version},
                "linux_target": next(row["linux_target"] for row in load_json(CONTRACTS / "ledger.json")["architectures"] if row["id"] == args.arch),
                "qualification": "cross-build-spike-only", "commands": commands, "status": "building", "files": {}}
    env = os.environ.copy()
    for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "LIBRARY_PATH", "GCC_EXEC_PREFIX", "COMPILER_PATH", "CFLAGS", "CPPFLAGS", "LDFLAGS", "DESTDIR", "CC", "CROSS_COMPILE", "MAKEFLAGS", "MFLAGS"):
        env.pop(name, None)
    env.update(LC_ALL="C", SOURCE_DATE_EPOCH="1708128000")

    def run(command, cwd, logname):
        commands.append([str(part) for part in command])
        with (work / logname).open("w") as log:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f"{logname} failed with exit {result.returncode}")

    try:
        # Copy the admitted bytes once: build extraction cannot race a changing input file.
        archive_copy = work / f"musl-{VERSION}.tar.gz"
        shutil.copyfile(args.archive, archive_copy)
        inspect_archive(archive_copy)
        source = extract_archive(archive_copy, work / "source")
        build = work / "build"
        build.mkdir()
        stage = work / "sysroot"
        flags = manifest["cflags"] + [f"-ffile-prefix-map={work}=/usr/src/musl-spike", f"-fdebug-prefix-map={work}=/usr/src/musl-spike"]
        manifest["path_remapping"] = "Build/source/debug paths remapped to /usr/src/musl-spike; full reproducibility still requires comparing all generated artifacts."
        libgcc = Path(subprocess.check_output([str(compiler), *flags, "-print-libgcc-file-name"], text=True).strip())
        if not libgcc.is_file():
            raise ValueError("compiler runtime library missing")
        manifest["compiler_runtime"] = {"path": str(libgcc.resolve()), "sha256": digest(libgcc)}
        run([str(source / "configure"), f"--target={triple}", "--disable-shared", "--disable-wrapper", "--prefix=/usr", "--syslibdir=/lib",
             f"CC={compiler}", f"CROSS_COMPILE={bindir / (triple + '-')}",
             f"AR={bindir / (triple + '-ar')} -D", f"RANLIB={bindir / (triple + '-ranlib')} -D", "CFLAGS=" + " ".join(flags)], build, "configure.log")
        run(["make", f"-j{args.jobs}"], build, "build.log")
        run(["make", "install", f"DESTDIR={stage}"], build, "install.log")
        license_dir = stage / "usr/share/licenses/musl"
        license_dir.mkdir(parents=True)
        shutil.copyfile(source / "COPYRIGHT", license_dir / "COPYRIGHT")
        probe = work / "probe.c"
        probe.write_text('#include <unistd.h>\nint main(void) { return write(1, "musl source spike\\n", 18) == 18 ? 0 : 1; }\n')
        lib = stage / "usr/lib"
        probe_input = probe
        if frontend:
            probe_input = work / "probe.o"
            frontend_flags = frontend["flags"] + ["-O2"] + (["-g"] if args.mode == "debug" else [])
            frontend_flags += [f"-ffile-prefix-map={work}=/usr/src/musl-spike", f"-fdebug-prefix-map={work}=/usr/src/musl-spike"]
            run([frontend["path"], *frontend_flags, "-fno-pie", "-nostdinc", "-isystem", str(stage / "usr/include"),
                 "-c", str(probe), "-o", str(probe_input)], build, "probe-compile.log")
        run([str(compiler), *flags, *manifest["ldflags"], "-nostdinc", "-isystem", str(stage / "usr/include"), "-nostdlib", "-static", "-Wl,-e,_start",
             str(lib / "crt1.o"), str(lib / "crti.o"), str(probe_input), "-Wl,--start-group", str(lib / "libc.a"), "-lgcc", "-Wl,--end-group", str(lib / "crtn.o"), "-o", str(work / "probe.elf")], build, "probe-link.log")
        run([str(bindir / (triple + "-readelf")), "-h", "-l", str(work / "probe.elf")], build, "probe-elf.log")
        manifest["probe_elf"] = inspect_elf(work / "probe.elf", args.arch)
        manifest["status"] = "built-not-executed"
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        manifest["status"] = "build-failed"
        manifest["failure"] = str(exc)
    finally:
        for path in sorted(work.rglob("*")):
            if path.is_file() and (path.is_relative_to(work / "sysroot") or path.name.endswith(".log") or path.name in ("probe.c", "probe.o", "probe.elf")):
                manifest["files"][path.relative_to(work).as_posix()] = digest(path)
        (work / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # Preserve failed build logs and partial staging, accurately labeled in the manifest.
        work.rename(output)
    if manifest["status"] == "build-failed":
        raise ValueError(f"{manifest['failure']}; failure record preserved in {output}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "build-static"))
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--arch", choices=ARCH_TRIPLES)
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--mode", choices=("debug", "release"), default="debug")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--ppc-clang", type=Path,
                        help="Explicit pinned Linux Clang frontend for the PowerPC ordinary application probe")
    args = parser.parse_args()
    if args.command == "build-static" and (args.arch is None or args.toolchain is None):
        parser.error("build-static requires --arch and --toolchain")
    if args.command == "inspect" and args.ppc_clang is not None:
        parser.error("--ppc-clang is only valid for build-static")
    try:
        result = inspect_archive(args.archive) if args.command == "inspect" else build_static(args)
        print(json.dumps(result if args.command == "inspect" else {key: result[key] for key in ("architecture", "status", "native_execution", "compiler")}, indent=2))
        return 0
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"musl source error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
