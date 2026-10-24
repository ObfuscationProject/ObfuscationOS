#!/usr/bin/env python3
"""Build and admit retained GCC 14.2 PowerPC e500v2 PIC runtime archives.

The archive is a link input for a scalar soft-float, big-endian ELF32 target.
This tool validates object provenance and ABI; it does not execute target code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import struct
import subprocess
import tarfile
from pathlib import Path


SOURCE_ARCHIVE_SHA256 = "a7b39bc69cbf9e25826c5a60ab26477001f7c08d85cec04bc0e29cabed6f3cc9"
SOURCE_FILES = (
    "gcc/config/elfos.h", "gcc/config/freebsd-spec.h", "gcc/config/gnu-user.h",
    "gcc/config/initfini-array.h", "gcc/config/newlib-stdint.h",
    "gcc/config/rs6000/eabi.h", "gcc/config/rs6000/option-defaults.h",
    "gcc/config/rs6000/rs6000-modes.h", "gcc/config/rs6000/rs6000-opts.h",
    "gcc/config/rs6000/rs6000.h", "gcc/config/rs6000/sysv4.h",
    "gcc/config/usegas.h", "gcc/config/vxworks-dummy.h", "gcc/coretypes.h",
    "gcc/defaults.h", "gcc/flag-types.h", "gcc/tsystem.h",
    "include/ansidecl.h", "include/filenames.h", "include/hashtab.h",
    "include/longlong.h", "libgcc/fp-bit.c", "libgcc/fp-bit.h",
    "libgcc/libgcc2.c", "libgcc/libgcc2.h",
)
LICENSE_FILES = ("COPYING", "COPYING3", "COPYING.LIB", "COPYING3.LIB", "COPYING.RUNTIME")
GENERATED_GCC = ("auto-host.h", "insn-constants.h", "insn-modes.h",
                 "options.h", "tconfig.h", "tm.h")
TOOLCHAIN_HEADERS = ("float.h", "stddef.h")
LIBGCC2 = (
    ("mulsc3", ("__mulsc3",)), ("muldc3", ("__muldc3",)),
    ("fixunsdfsi", ("__fixunsdfsi",)), ("fixsfdi", ("__fixsfdi",)),
    ("fixdfdi", ("__fixdfdi",)), ("fixunssfdi", ("__fixunssfdi",)),
    ("fixunsdfdi", ("__fixunsdfdi",)), ("floatdidf", ("__floatdidf",)),
    ("divdi3", ("__divdi3",)), ("moddi3", ("__moddi3",)),
    ("udivdi3", ("__udivdi3",)), ("umoddi3", ("__umoddi3",)),
)
FP_SINGLE = (
    ("pack_sf", ("__pack_f",)), ("unpack_sf", ("__unpack_f",)),
    ("addsub_sf", ("__addsf3", "__subsf3")), ("mul_sf", ("__mulsf3",)),
    ("div_sf", ("__divsf3",)), ("fpcmp_parts_sf", ("__fpcmp_parts_f",)),
    ("eq_sf", ("__eqsf2",)), ("ne_sf", ("__nesf2",)),
    ("gt_sf", ("__gtsf2",)), ("ge_sf", ("__gesf2",)),
    ("lt_sf", ("__ltsf2",)), ("le_sf", ("__lesf2",)),
    ("unord_sf", ("__unordsf2",)), ("si_to_sf", ("__floatsisf",)),
    ("sf_to_si", ("__fixsfsi",)), ("make_sf", ("__make_fp",)),
    ("sf_to_df", ("__extendsfdf2",)), ("thenan_sf", ("__thenan_sf",)),
)
FP_DOUBLE = (
    ("pack_df", ("__pack_d",)), ("unpack_df", ("__unpack_d",)),
    ("addsub_df", ("__adddf3", "__subdf3")), ("mul_df", ("__muldf3",)),
    ("div_df", ("__divdf3",)), ("fpcmp_parts_df", ("__fpcmp_parts_d",)),
    ("eq_df", ("__eqdf2",)), ("ne_df", ("__nedf2",)),
    ("gt_df", ("__gtdf2",)), ("ge_df", ("__gedf2",)),
    ("lt_df", ("__ltdf2",)), ("le_df", ("__ledf2",)),
    ("unord_df", ("__unorddf2",)), ("si_to_df", ("__floatsidf",)),
    ("df_to_si", ("__fixdfsi",)), ("make_df", ("__make_dp",)),
    ("df_to_sf", ("__truncdfsf2",)), ("thenan_df", ("__thenan_df",)),
    ("usi_to_df", ("__floatunsidf",)),
)
MEMBERS = tuple((name, symbols, kind) for kind, group in
                (("libgcc2", LIBGCC2), ("single", FP_SINGLE), ("double", FP_DOUBLE))
                for name, symbols in group)
MODE_FLAGS = {"debug": ("-O2", "-g"), "release": ("-O2", "-g0")}
PROFILE = "powerpc-e500v2-elf32-big-scalar-soft-float-secure-plt-pic"
SAFE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
            "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str], log: Path | None = None) -> str:
    result = subprocess.run(argv, env=SAFE_ENV, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    if log is not None:
        log.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv}\n{result.stdout}")
    return result.stdout


def file_pin(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"missing tool: {path}")
    path = path.resolve()
    return {"path": str(path), "sha256": sha256(path)}


def tool_inventory(compiler: Path) -> dict[str, dict[str, str]]:
    compiler = compiler.resolve()
    if compiler.name != "powerpc-eabi-gcc":
        raise RuntimeError(f"wrong compiler target: {compiler}")
    if run([str(compiler), "-dumpmachine"]).strip() != "powerpc-eabi":
        raise RuntimeError("compiler dumpmachine target is not powerpc-eabi")
    if run([str(compiler), "-dumpfullversion"]).strip() != "14.2.0":
        raise RuntimeError("compiler version is not GCC 14.2.0")
    tools = {"gcc": file_pin(compiler)}
    for name in ("cc1", "as"):
        selected = Path(run([str(compiler), f"-print-prog-name={name}"]).strip())
        if not selected.is_absolute():
            raise RuntimeError(f"compiler did not select an absolute {name}")
        tools[name] = file_pin(selected)
    for name in ("ar", "ranlib", "readelf", "nm"):
        tools[name] = file_pin(compiler.with_name(f"powerpc-eabi-{name}"))
    return tools


def compiler_spec_sha256(compiler: Path) -> str:
    specs = run([str(compiler.resolve()), "-dumpspecs"])
    return hashlib.sha256(specs.encode()).hexdigest()


def retained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeError(f"invalid retained path: {relative!r}")
    raw = root / relative
    current = root
    for component in Path(relative).parts:
        if component in (".", ".."):
            raise RuntimeError(f"invalid retained path component: {relative}")
        current = current / component
        if current.is_symlink():
            raise RuntimeError(f"symlink in retained path: {relative}")
    path = raw.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise RuntimeError(f"missing or escaping retained file: {relative}")
    return path


def relative_pin(root: Path, path: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}


def verify_pin(root: Path, pin: dict[str, str]) -> Path:
    path = retained(root, pin["path"])
    if sha256(path) != pin["sha256"]:
        raise RuntimeError(f"retained file digest changed: {pin['path']}")
    return path


def expected_inputs() -> list[str]:
    names = [f"inputs/gcc-14.2.0/{name}" for name in SOURCE_FILES + LICENSE_FILES]
    names += [f"inputs/generated/gcc/{name}" for name in GENERATED_GCC]
    names += ["inputs/generated/powerpc-eabi/libgcc/libgcc_tm.h"]
    names += [f"inputs/toolchain-include/{name}" for name in TOOLCHAIN_HEADERS]
    return sorted([*names, "ppc_pic_runtime.py"])


def dependencies(dep: Path, original: Path) -> list[str]:
    content = dep.read_text().replace("\\\n", " ")
    if ":" not in content:
        raise RuntimeError(f"invalid dependency file: {dep}")
    used = set()
    for name in content.split(":", 1)[1].split():
        path = Path(name).resolve()
        if not path.is_relative_to(original):
            raise RuntimeError(f"compiler read an unretained source: {path}")
        used.add(path.relative_to(original).as_posix())
    return sorted(used)


def actual_programs(log: Path) -> dict[str, str]:
    found = {}
    for line in log.read_text().splitlines():
        if not line.startswith(" "):
            continue
        try:
            first = shlex.split(line)[0]
        except (ValueError, IndexError):
            continue
        path = Path(first)
        if path.is_absolute() and path.name in ("cc1", "as"):
            found[path.name] = str(path.resolve())
    if set(found) != {"cc1", "as"}:
        raise RuntimeError(f"actual compiler program selection missing: {log}")
    return found


def stack_note_flags(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 52 or data[:6] != b"\x7fELF\x01\x02":
        raise RuntimeError(f"invalid PPC ELF32 header: {path}")
    section_offset = struct.unpack_from(">I", data, 32)[0]
    section_size, count, names_index = struct.unpack_from(">HHH", data, 46)
    if not section_size or not count or names_index >= count or section_offset + section_size * count > len(data):
        raise RuntimeError(f"invalid PPC ELF section table: {path}")

    def section(index: int) -> tuple[int, ...]:
        return struct.unpack_from(">IIIIIIIIII", data, section_offset + section_size * index)

    names_header = section(names_index)
    names_start, names_size = names_header[4], names_header[5]
    if names_start + names_size > len(data):
        raise RuntimeError(f"invalid PPC ELF section names: {path}")
    names = data[names_start:names_start + names_size]
    for index in range(count):
        header = section(index)
        name_start = header[0]
        if name_start >= len(names):
            raise RuntimeError(f"invalid PPC ELF section name offset: {path}")
        name_end = names.find(b"\x00", name_start)
        if name_end < 0:
            raise RuntimeError(f"unterminated PPC ELF section name: {path}")
        if names[name_start:name_end] == b".note.GNU-stack":
            return header[2]
    raise RuntimeError(f"missing GNU stack note: {path}")


def audit_object(path: Path, symbols: tuple[str, ...], tools: dict) -> dict:
    header = run([tools["readelf"]["path"], "-h", str(path)])
    for required in ("Class:                             ELF32",
                     "Data:                              2's complement, big endian",
                     "Type:                              REL (Relocatable file)",
                     "Machine:                           PowerPC",
                     "Flags:                             0x8000, relocatable-lib"):
        if required not in header:
            raise RuntimeError(f"unexpected PPC ELF header in {path}: {required}")
    sections = run([tools["readelf"]["path"], "-W", "-S", str(path)])
    stack_flags = stack_note_flags(path)
    if stack_flags & 0x5:
        raise RuntimeError(f"writable or executable GNU stack note: {path}: {stack_flags:#x}")
    relocations = run([tools["readelf"]["path"], "-r", str(path)])
    section = ""
    for line in relocations.splitlines():
        if line.startswith("Relocation section '"):
            section = line.split("'", 2)[1]
        if section.startswith((".rela.text", ".rel.text")) and re.search(
                r"\bR_PPC_(?:ADDR(?:32|24|16(?:_HA|_HI|_LO)?)|REL24)\b", line):
            raise RuntimeError(f"absolute or non-PLT text relocation: {path}: {line}")
    defined = run([tools["nm"]["path"], "-g", "--defined-only", str(path)])
    for symbol in symbols:
        if not re.search(rf"\b[BDRT] {re.escape(symbol)}$", defined, re.MULTILINE):
            raise RuntimeError(f"missing expected GCC symbol {symbol}: {path}")
    return {"sha256": sha256(path), "symbols": list(symbols),
            "defined_globals": defined.splitlines(),
            "relocations_sha256": hashlib.sha256(relocations.encode()).hexdigest(),
            "sections_sha256": hashlib.sha256(sections.encode()).hexdigest(),
            "stack_note_flags": stack_flags}


def compile_argv(root: Path, mode: str, tools: dict, name: str, kind: str) -> list[str]:
    source = "libgcc2.c" if kind == "libgcc2" else "fp-bit.c"
    argv = [tools["gcc"]["path"], "-mcpu=8548", "-msoft-float",
            "-mlong-double-64", "-msdata=none", "-fPIC", "-msecure-plt",
            "-Wa,--noexecstack",
            *MODE_FLAGS[mode], "-ffreestanding", "-fno-stack-protector",
            "-nostdinc", "-Dinhibit_libc", "-DIN_LIBGCC2", "-DIN_GCC",
            "-fbuilding-libgcc", "-DHAVE_CC_TLS"]
    if kind != "libgcc2":
        argv.append("-DFINE_GRAINED_LIBRARIES")
    argv.append(f"-DL_{name}")
    if kind == "single":
        argv.append("-DFLOAT")
    argv += ["-I", str(root / "inputs/generated/powerpc-eabi/libgcc"),
             "-I", str(root / "inputs/generated/gcc"),
             "-I", str(root / "inputs/gcc-14.2.0/libgcc"),
             "-I", str(root / "inputs/gcc-14.2.0/gcc"),
             "-I", str(root / "inputs/gcc-14.2.0/include"),
             "-isystem", str(root / "inputs/toolchain-include"),
             "-MD", "-MF", str(root / "objects" / f"{name}.d"),
             "-c", str(root / "inputs/gcc-14.2.0/libgcc" / source),
             "-o", str(root / "objects" / f"{name}.o"), "-v"]
    return argv


def build(mode: str, compiler: Path, source_archive: Path,
          generated_headers: Path, output: Path) -> tuple[Path, str]:
    mode = mode.lower()
    if mode not in MODE_FLAGS:
        raise RuntimeError(f"unsupported mode: {mode}")
    if output.exists():
        raise RuntimeError(f"output must be a fresh directory: {output}")
    if sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise RuntimeError("GCC 14.2 source archive checksum mismatch")
    tools = tool_inventory(compiler)
    specs_sha256 = compiler_spec_sha256(compiler)
    root = output.resolve()
    root.mkdir(parents=True)
    (root / "objects").mkdir()
    (root / "logs").mkdir()
    shutil.copy2(Path(__file__), root / "ppc_pic_runtime.py")
    with tarfile.open(source_archive, "r:xz") as source:
        for name in SOURCE_FILES + LICENSE_FILES:
            member = source.getmember(f"gcc-14.2.0/{name}")
            if not member.isfile():
                raise RuntimeError(f"unexpected GCC source archive member: {name}")
            destination = root / "inputs/gcc-14.2.0" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as original, destination.open("wb") as target:
                shutil.copyfileobj(original, target)
    for name in GENERATED_GCC:
        original = generated_headers / "gcc" / name
        destination = root / "inputs/generated/gcc" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    original = generated_headers / "powerpc-eabi/libgcc/libgcc_tm.h"
    destination = root / "inputs/generated/powerpc-eabi/libgcc/libgcc_tm.h"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, destination)
    internal = Path(run([tools["gcc"]["path"], "-print-file-name=include"]).strip()).resolve()
    for name in TOOLCHAIN_HEADERS:
        destination = root / "inputs/toolchain-include" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(internal / name, destination)
    inputs = [relative_pin(root, retained(root, name)) for name in expected_inputs()]
    manifest = {"schema": 1, "architecture": "ppc", "mode": mode,
                "profile": PROFILE, "status": "PIC-archive-built",
                "target_executed": False,
                "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
                "compiler_specs_sha256": specs_sha256,
                "subprocess_environment": SAFE_ENV,
                "original_build_dir": str(root), "tools": tools,
                "inputs": inputs, "members": [], "archive": {}}
    for name, symbols, kind in MEMBERS:
        obj = root / "objects" / f"{name}.o"
        dep = root / "objects" / f"{name}.d"
        log = root / "logs" / f"compile-{name}.log"
        argv = compile_argv(root, mode, tools, name, kind)
        run(argv, log)
        actual = actual_programs(log)
        if actual != {key: tools[key]["path"] for key in ("cc1", "as")}:
            raise RuntimeError(f"unexpected compiler program selection for {name}: {actual}")
        used = dependencies(dep, root)
        for relative in used:
            if relative not in expected_inputs():
                raise RuntimeError(f"compiler used an unretained source: {relative}")
        manifest["members"].append({
            "name": f"{name}.o", "kind": kind, "source_macro": f"L_{name}",
            "symbols": list(symbols), "command": argv, "exit_status": 0,
            "actual_programs": actual, "compile_log": relative_pin(root, log),
            "dependency_file": relative_pin(root, dep),
            "dependencies": [relative_pin(root, root / entry) for entry in used],
            "object": audit_object(obj, symbols, tools),
        })
    archive = root / "libgcc_pic.a"
    run([tools["ar"]["path"], "crD", str(archive),
         *(str(root / "objects" / f"{name}.o") for name, _, _ in MEMBERS)],
        root / "logs/archive.log")
    run([tools["ranlib"]["path"], "-D", str(archive)], root / "logs/ranlib.log")
    names = run([tools["ar"]["path"], "t", str(archive)]).splitlines()
    if names != [f"{name}.o" for name, _, _ in MEMBERS]:
        raise RuntimeError("unexpected archive member order")
    manifest["archive"] = {"path": "libgcc_pic.a", "sha256": sha256(archive),
                           "members": names, "deterministic_ar": True}
    manifest["archive_logs"] = [relative_pin(root, root / "logs/archive.log"),
                                relative_pin(root, root / "logs/ranlib.log")]
    if tool_inventory(compiler) != tools or compiler_spec_sha256(compiler) != specs_sha256:
        raise RuntimeError("compiler or binary tool changed during the build")
    if sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise RuntimeError("GCC 14.2 source archive changed during the build")
    for pin in inputs:
        verify_pin(root, pin)
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return archive, sha256(path)


def admit(build_dir: Path, manifest_sha256: str, arch: str, mode: str,
          compiler: Path) -> tuple[Path, dict]:
    root = build_dir.resolve()
    path = retained(root, "manifest.json")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256 or "") or sha256(path) != manifest_sha256:
        raise RuntimeError("explicit PPC PIC manifest checksum mismatch")
    record = json.loads(path.read_text())
    mode = mode.lower()
    if (arch != "ppc" or mode not in MODE_FLAGS or record.get("schema") != 1
            or record.get("architecture") != arch or record.get("mode") != mode
            or record.get("profile") != PROFILE
            or record.get("status") != "PIC-archive-built"
            or record.get("target_executed") is not False
            or record.get("source_archive_sha256") != SOURCE_ARCHIVE_SHA256
            or record.get("subprocess_environment") != SAFE_ENV):
        raise RuntimeError("unsupported PPC PIC runtime manifest")
    tools = tool_inventory(compiler)
    if record["tools"] != tools:
        raise RuntimeError("compiler, cc1, assembler or archive tool identity changed")
    if record.get("compiler_specs_sha256") != compiler_spec_sha256(compiler):
        raise RuntimeError("compiler specs changed")
    if [item["path"] for item in record["inputs"]] != expected_inputs():
        raise RuntimeError("retained input inventory changed")
    for item in record["inputs"]:
        verify_pin(root, item)
    original = Path(record["original_build_dir"])
    if not original.is_absolute():
        raise RuntimeError("invalid original build directory")
    expected_names = [f"{name}.o" for name, _, _ in MEMBERS]
    if [item["name"] for item in record["members"]] != expected_names:
        raise RuntimeError("PPC PIC member set changed")
    for item, (name, symbols, kind) in zip(record["members"], MEMBERS):
        obj = retained(root, f"objects/{name}.o")
        dep = verify_pin(root, item["dependency_file"])
        log = verify_pin(root, item["compile_log"])
        if (item["kind"] != kind or item["source_macro"] != f"L_{name}"
                or item["symbols"] != list(symbols)
                or item["command"] != compile_argv(original, mode, tools, name, kind)
                or item["exit_status"] != 0):
            raise RuntimeError(f"PPC PIC compile recipe changed: {name}")
        selected = actual_programs(log)
        if (selected != item["actual_programs"]
                or selected != {key: tools[key]["path"] for key in ("cc1", "as")}):
            raise RuntimeError(f"actual compiler program selection changed: {name}")
        used = dependencies(dep, original)
        if [pin["path"] for pin in item["dependencies"]] != used:
            raise RuntimeError(f"compiler dependency list changed: {name}")
        for pin in item["dependencies"]:
            verify_pin(root, pin)
        if sha256(obj) != item["object"]["sha256"]:
            raise RuntimeError(f"retained object digest changed: {name}")
        if audit_object(obj, symbols, tools) != item["object"]:
            raise RuntimeError(f"retained object ABI changed: {name}")
    for pin in record["archive_logs"]:
        verify_pin(root, pin)
    archive_pin = record["archive"]
    archive = retained(root, archive_pin["path"])
    if archive_pin["path"] != "libgcc_pic.a" or sha256(archive) != archive_pin["sha256"]:
        raise RuntimeError("PPC PIC archive digest changed")
    actual = run([tools["ar"]["path"], "t", str(archive)]).splitlines()
    if (actual != expected_names or archive_pin["members"] != expected_names
            or archive_pin["deterministic_ar"] is not True):
        raise RuntimeError("PPC PIC archive member order changed")
    for item in record["members"]:
        content = subprocess.check_output([tools["ar"]["path"], "p", str(archive), item["name"]],
                                          env=SAFE_ENV)
        if hashlib.sha256(content).hexdigest() != item["object"]["sha256"]:
            raise RuntimeError(f"archive member differs from retained object: {item['name']}")
    return archive, record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--mode", required=True, choices=("Debug", "Release", "debug", "release"))
    builder.add_argument("--compiler", required=True, type=Path)
    builder.add_argument("--source-archive", required=True, type=Path)
    builder.add_argument("--generated-headers", required=True, type=Path)
    builder.add_argument("--output", required=True, type=Path)
    validator = commands.add_parser("admit")
    validator.add_argument("--arch", required=True, choices=("ppc",))
    validator.add_argument("--mode", required=True, choices=("Debug", "Release", "debug", "release"))
    validator.add_argument("--compiler", required=True, type=Path)
    validator.add_argument("--build-dir", required=True, type=Path)
    validator.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if args.command == "build":
        archive, digest = build(args.mode, args.compiler, args.source_archive,
                                args.generated_headers, args.output)
        print(json.dumps({"archive": str(archive), "manifest_sha256": digest}, sort_keys=True))
    else:
        archive, record = admit(args.build_dir, args.manifest_sha256,
                                args.arch, args.mode, args.compiler)
        print(json.dumps({"archive": str(archive), "archive_sha256": record["archive"]["sha256"]},
                         sort_keys=True))


if __name__ == "__main__":
    main()
