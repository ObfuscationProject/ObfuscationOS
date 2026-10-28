#!/usr/bin/env python3
"""C driver for static musl ports on the freestanding-GCC fallback.

  musl_cc.py PROFILE.json [compiler arguments...]

tools/ports.py writes PROFILE.json and a `cc` shim per port build. Compiles see
only the admitted musl headers and the compiler's own builtin headers. Links
produce a static ET_EXEC with the Linux-personality layout from
ports/musl/static-exec.ld and mark EI_OSABI as Linux: this distribution never
infers the syscall personality from a path or a syscall number. Relocatable
(`-r`) links, which Kbuild uses for its built-in objects, pass through without
startup files or libraries. Shared objects and PIE are refused. Once the `<arch>-linux-musl` toolchain
family exists this driver is not used (docs/decisions/0001).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ELF_IDENTITY = {
    "i386": (1, 1), "x86_64": (2, 1), "aarch64": (2, 1), "arm32": (1, 1), "rv64": (2, 1),
    "rv32": (1, 1), "loongarch64": (2, 1), "mips": (1, 2), "mips64": (2, 2), "ppc": (1, 2),
}
NO_LINK = {"-c", "-S", "-E", "-fsyntax-only"}
QUERIES = {"-v", "--version", "--help", "-dumpmachine", "-dumpversion", "-dumpfullversion",
           "-dumpspecs", "-print-search-dirs", "-print-libgcc-file-name", "-print-multi-lib",
           "-print-multi-directory", "-print-sysroot"}
REFUSED = {"-shared", "-pie", "-static-pie", "-nostartfiles", "-nodefaultlibs", "-nostdlib"}
# Options whose value is the next argument; their values are never inputs.
SEPARATE = {"-o", "-MF", "-MT", "-MQ", "-include", "-imacros", "-I", "-isystem", "-iquote",
            "-idirafter", "-D", "-U", "-L", "-x", "-Xlinker", "-Xassembler", "-T", "-u", "-l"}
SOURCES = (".c", ".i", ".s", ".S", ".sx")


def classify(argv: list[str]) -> tuple[str, list[int], str | None]:
    """Return (mode, source indices, output) for one invocation."""
    sources, output, link, skip = [], None, True, False
    partial = "-r" in argv
    for index, arg in enumerate(argv):
        if skip:
            skip = False
            if argv[index - 1] == "-o":
                output = arg
            continue
        if arg in SEPARATE:
            skip = True
        elif arg in REFUSED and not (partial and arg == "-nostdlib"):
            raise SystemExit(f"musl_cc: {arg} is not supported; ports link static ET_EXEC images only")
        elif arg in NO_LINK or arg in ("-M", "-MM"):
            link = False
        elif arg.startswith("-o") and len(arg) > 2:
            output = arg[2:]
        elif not arg.startswith("-") and arg.endswith(SOURCES):
            sources.append(index)
    inputs = [arg for arg in argv if not arg.startswith("-")]
    if any(arg in QUERIES or arg.startswith("-print-") for arg in argv) and not inputs:
        return "query", sources, output
    if partial and link:
        if sources:
            raise SystemExit("musl_cc: a relocatable link takes objects only")
        return "partial", sources, output
    return ("link" if link else "compile"), sources, output


def compile_options(argv: list[str], sources: list[int]) -> list[str]:
    """Options of a compile-and-link invocation that apply to its compile step."""
    result, skip = [], False
    for index, arg in enumerate(argv):
        if skip:
            skip = False
            if argv[index - 1] not in ("-o", "-Xlinker", "-L", "-l", "-T", "-u"):
                result.append(arg)
            continue
        if arg in SEPARATE:
            skip = True
            if arg not in ("-o", "-Xlinker", "-L", "-l", "-T", "-u"):
                result.append(arg)
        elif (index not in sources and arg.startswith("-") and
              not arg.startswith(("-Wl,", "-l", "-L", "-static", "-o")) and arg not in ("-s", "-rdynamic")):
            result.append(arg)
    return result


def compile_command(profile: dict, argv: list[str]) -> list[str]:
    front = profile["frontend"]
    command = [front["path"], *front["flags"]] if front else [profile["compiler"], *profile["abi_flags"]]
    builtin = front["include"] if front else profile["compiler_include"]
    return [*command, *profile["defines"], "-fno-pie", "-ftls-model=local-exec",
            "-nostdinc", "-isystem", profile["include"], "-isystem", builtin, *argv]


def link_command(profile: dict, argv: list[str]) -> list[str]:
    lib = Path(profile["lib"])
    return [profile["compiler"], *profile["abi_flags"], *profile["ldflags"], "-nostdlib", "-static",
            "-Wl,-e,_start", "-Wl,-T," + profile["linker_script"],
            "-Wl,--defsym,USER_BASE=" + profile["user_base"], "-Wl,-z,max-page-size=4096",
            "-Wl,-z,noexecstack", "-L" + str(lib), str(lib / "crt1.o"), str(lib / "crti.o"), *argv,
            "-Wl,--start-group", str(lib / "libc.a"), *profile["supplements"], "-lgcc",
            "-Wl,--end-group", str(lib / "crtn.o")]


def mark_linux(path: Path, profile: dict) -> None:
    data = bytearray(path.read_bytes())
    elf_class, order = ELF_IDENTITY[profile["arch"]]
    if (len(data) < 18 or data[:7] != b"\x7fELF" + bytes((elf_class, order, 1)) or
            data[7] not in (0, 3) or data[8] != profile["elf_abi_version"]):
        raise SystemExit(f"musl_cc: unexpected ELF identity before personality marking: {path}")
    if int.from_bytes(data[16:18], "little" if order == 1 else "big") != 2:
        raise SystemExit(f"musl_cc: link output is not ET_EXEC: {path}")
    data[7] = 3  # ELFOSABI_LINUX
    path.write_bytes(data)


def run(command: list[str]) -> int:
    return subprocess.run(command).returncode


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    profile = json.loads(Path(argv[0]).read_text())
    if profile.get("schema_version") != 1 or profile.get("arch") not in ELF_IDENTITY:
        raise SystemExit("musl_cc: unsupported driver profile")
    args = argv[1:]
    mode, sources, output = classify(args)
    if mode == "query":
        return run([profile["compiler"], *profile["abi_flags"], *args])
    if mode == "partial":
        return run([profile["compiler"], *profile["abi_flags"], *profile["ldflags"], *args])
    if mode == "compile":
        return run(compile_command(profile, args))
    with tempfile.TemporaryDirectory(prefix=".musl-cc-") as scratch:
        if sources and profile["frontend"]:
            # The Linux frontend compiles; the target GCC driver only links.
            options = compile_options(args, sources)
            for number, index in enumerate(sources):
                obj = str(Path(scratch) / f"{number}.o")
                if run(compile_command(profile, [*options, "-c", args[index], "-o", obj])):
                    return 1
                args[index] = obj
        elif sources:
            args = [*profile["defines"], "-fno-pie", "-ftls-model=local-exec", "-nostdinc",
                    "-isystem", profile["include"], "-isystem", profile["compiler_include"], *args]
        code = run(link_command(profile, args))
    if code:
        return code
    target = Path(output or "a.out")
    if target.is_file():
        mark_linux(target, profile)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
