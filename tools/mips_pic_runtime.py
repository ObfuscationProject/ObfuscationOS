#!/usr/bin/env python3
"""Build and admit relocatable GCC 14.2 MIPS PIC runtime archives.

The artifact retains every source and header read by the compiler. Admission
requires only that artifact and the explicitly selected cross compiler; it
does not access the original GCC source archive or generated-header tree.
This is an ELF/archive qualification, not target execution.
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

SAFE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1", "SOURCE_DATE_EPOCH": "1708128000"}


ARCHIVE_SHA256 = "a7b39bc69cbf9e25826c5a60ab26477001f7c08d85cec04bc0e29cabed6f3cc9"
SOURCE_SHA256 = "0bf1fa3e4b9be1fd45a47682cb119d4f8fda17f02398d157a189d49c6f2d2919"
LINUX_AS_MANIFEST_SHA256 = "dfb65c6dab0b92d967db7ee6093fffb8315fcedcd0089351787ca27f4995f925"
LINUX_AS_SHA256 = "57ee66b7e1226d114da2400a2a58a9936e3ce37e7ee3eb36fd29c36a7a30fded"
SOURCE_FILES = (
    "gcc/config/elfos.h", "gcc/config/initfini-array.h",
    "gcc/config/mips/elf.h", "gcc/config/mips/mips-opts.h",
    "gcc/config/mips/mips.h", "gcc/config/newlib-stdint.h",
    "gcc/config/vxworks-dummy.h", "gcc/coretypes.h",
    "gcc/defaults.h", "gcc/flag-types.h", "gcc/tsystem.h",
    "include/ansidecl.h", "include/filenames.h", "include/hashtab.h",
    "include/longlong.h", "libgcc/libgcc2.c", "libgcc/libgcc2.h",
)
LICENSE_FILES = ("COPYING", "COPYING3", "COPYING.LIB", "COPYING3.LIB", "COPYING.RUNTIME")
GENERATED_GCC = ("auto-host.h", "insn-constants.h", "insn-modes.h",
                 "options.h", "tconfig.h", "tm.h")
TOOLCHAIN_HEADERS = ("float.h", "stddef.h")
MEMBERS = {
    "mips": (("clz", "__clz_tab"), ("divdi3", "__divdi3"),
             ("moddi3", "__moddi3"), ("udivdi3", "__udivdi3"),
             ("umoddi3", "__umoddi3"), ("mulsc3", "__mulsc3"),
             ("muldc3", "__muldc3"), ("fixsfdi", "__fixsfdi"),
             ("fixdfdi", "__fixdfdi"), ("fixunssfdi", "__fixunssfdi"),
             ("fixunsdfdi", "__fixunsdfdi"), ("floatdidf", "__floatdidf")),
    "mips64": (("mulsc3", "__mulsc3"), ("muldc3", "__muldc3"),
               ("multc3", "__multc3")),
}
ARCH = {
    "mips": ("mips32r2", "32", "ELF32", "o32", "mips32r2-o32-big-hard-float-pic"),
    "mips64": ("mips64r2", "64", "ELF64", "mips64r2", "mips64r2-n64-big-hard-float-pic"),
}
MODE_FLAGS = {"debug": ("-O0", "-g3"), "release": ("-O2", "-g0")}


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


def pinned_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"missing file: {path}")
    return {"path": str(path.resolve()), "sha256": sha256(path.resolve())}


def tool_path(compiler: Path, name: str) -> Path:
    value = run([str(compiler), f"-print-prog-name={name}"]).strip()
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError(f"compiler did not select an absolute {name}: {value}")
    return path.resolve()


def tool_inventory(compiler: Path, arch: str) -> dict[str, dict[str, str]]:
    compiler = compiler.resolve()
    if compiler.name != f"{arch}-elf-gcc":
        raise RuntimeError(f"compiler target mismatch: {compiler}")
    tools = {"gcc": pinned_file(compiler),
             "cc1": pinned_file(tool_path(compiler, "cc1")),
             "as": pinned_file(tool_path(compiler, "as"))}
    for name in ("ar", "ranlib", "readelf", "nm"):
        tools[name] = pinned_file(compiler.with_name(f"{arch}-elf-{name}"))
    return tools


def relative_pin(root: Path, path: Path) -> dict[str, str]:
    relative = path.relative_to(root).as_posix()
    return {"path": relative, "sha256": sha256(path)}


def retained_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeError(f"invalid retained path: {relative!r}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise RuntimeError(f"missing or escaping retained file: {relative}")
    return path


def verify_pin(root: Path, pin: dict[str, str]) -> Path:
    path = retained_path(root, pin["path"])
    if sha256(path) != pin["sha256"]:
        raise RuntimeError(f"retained file digest changed: {pin['path']}")
    return path


def dependencies(dep: Path, root: Path) -> list[str]:
    content = dep.read_text().replace("\\\n", " ")
    if ":" not in content:
        raise RuntimeError(f"invalid dependency file: {dep}")
    names = content.split(":", 1)[1].split()
    result = set()
    for name in names:
        path = Path(name).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f"compiler read an unretained header: {path}")
        result.add(path.relative_to(root).as_posix())
    return sorted(result)


def actual_compiler_programs(log: Path) -> dict[str, str]:
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
        raise RuntimeError(f"missing actual cc1/as invocations in {log}")
    return found


def audit_object(path: Path, arch: str, symbol: str,
                 tools: dict[str, dict[str, str]]) -> dict:
    header = run([tools["readelf"]["path"], "-h", str(path)])
    relocations = run([tools["readelf"]["path"], "-r", str(path)])
    symbols = run([tools["nm"]["path"], "-g", "--defined-only", str(path)])
    _, _, elf_class, abi_flag, _ = ARCH[arch]
    for required in (f"Class:                             {elf_class}",
                     "Data:                              2's complement, big endian",
                     "Type:                              REL (Relocatable file)",
                     "Machine:                           MIPS R3000"):
        if required not in header:
            raise RuntimeError(f"unexpected {arch} ELF header in {path}: {required}")
    flags = next((line.strip() for line in header.splitlines() if "Flags:" in line), "")
    if not all(token in flags for token in ("pic", "cpic", abi_flag)):
        raise RuntimeError(f"missing PIC/ABI flag in {path}: {flags}")
    if not re.search(rf"\b[BDRT] {re.escape(symbol)}$", symbols, re.MULTILINE):
        raise RuntimeError(f"missing real GCC symbol {symbol} in {path}")
    section = ""
    for line in relocations.splitlines():
        if line.startswith("Relocation section '"):
            section = line.split("'", 2)[1]
        if section.startswith((".rel.text", ".rela.text")) and re.match(
                r"^[0-9a-fA-F]{8,16}\s", line) and re.search(
                r"\bR_MIPS_(?:HI16|26)\b", line) and not line.endswith("_gp_disp"):
            raise RuntimeError(f"non-PIC text relocation in {path}: {line}")
    return {"sha256": sha256(path), "header_flags": flags,
            "defined_global_symbols": symbols.splitlines(),
            "relocations_sha256": hashlib.sha256(relocations.encode()).hexdigest()}


def audit_local_symtab_order(path: Path) -> list[dict[str, int]]:
    """Reject SHT_SYMTAB local symbols at or beyond its sh_info boundary."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[5] != 2:
        raise RuntimeError(f"unexpected ELF encoding: {path}")
    if data[4] == 1:
        section_offset = struct.unpack_from(">I", data, 32)[0]
        section_size, section_count = struct.unpack_from(">HH", data, 46)
        format = ">IIIIIIIIII"
        symbol_info_offset = 12
    elif data[4] == 2:
        section_offset = struct.unpack_from(">Q", data, 40)[0]
        section_size, section_count = struct.unpack_from(">HH", data, 58)
        format = ">IIQQQQIIQQ"
        symbol_info_offset = 4
    else:
        raise RuntimeError(f"unexpected ELF class: {path}")
    if not section_count or section_offset + section_size * section_count > len(data):
        raise RuntimeError(f"invalid ELF section table: {path}")
    result = []
    for index in range(section_count):
        section = struct.unpack_from(format, data, section_offset + section_size * index)
        if section[1] != 2:
            continue
        offset, size, info, entry_size = section[4], section[5], section[7], section[9]
        if not entry_size or size % entry_size or offset + size > len(data):
            raise RuntimeError(f"invalid ELF symbol table: {path}")
        count = size // entry_size
        if info > count:
            raise RuntimeError(f"invalid ELF local symbol boundary: {path}")
        for symbol_index in range(count):
            binding = data[offset + symbol_index * entry_size + symbol_info_offset] >> 4
            if binding == 0 and symbol_index >= info:
                raise RuntimeError(
                    f"local symbol at index {symbol_index} >= sh_info {info}: {path}")
        result.append({"section_index": index, "symbol_count": count, "sh_info": info})
    if not result:
        raise RuntimeError(f"missing ELF symbol table: {path}")
    return result


def compile_argv(root: Path, arch: str, mode: str, tools: dict,
                 override_as: bool = False) -> list[str]:
    march, abi, _, _, _ = ARCH[arch]
    prefix = [tools["gcc"]["path"]]
    if override_as:
        prefix.append(f"-B{root / 'tools/assembler'}/")
    return [*prefix, f"-march={march}", f"-mabi={abi}", "-EB",
            "-mhard-float", "-mabicalls", "-G0", "-fPIC", *MODE_FLAGS[mode],
            "-ffreestanding", "-fno-stack-protector", "-nostdinc",
            "-Dinhibit_libc", "-DIN_LIBGCC2", "-DIN_GCC",
            "-fbuilding-libgcc", "-DHAVE_CC_TLS",
            "-I", str(root / "inputs/generated" / f"{arch}-elf/libgcc"),
            "-I", str(root / "inputs/generated/gcc"),
            "-I", str(root / "inputs/gcc-14.2.0/libgcc"),
            "-I", str(root / "inputs/gcc-14.2.0/gcc"),
            "-I", str(root / "inputs/gcc-14.2.0/include"),
            "-isystem", str(root / "inputs/toolchain-include"), "-v"]


def expected_inputs(arch: str, override_as: bool = False) -> list[str]:
    paths = [f"inputs/gcc-14.2.0/{name}" for name in SOURCE_FILES + LICENSE_FILES]
    paths += [f"inputs/generated/gcc/{name}" for name in GENERATED_GCC]
    paths += [f"inputs/generated/{arch}-elf/libgcc/libgcc_tm.h"]
    paths += [f"inputs/toolchain-include/{name}" for name in TOOLCHAIN_HEADERS]
    paths += ["mips_pic_runtime.py"]
    if override_as:
        paths += ["inputs/assembler/manifest.json", "tools/assembler/as"]
    return sorted(paths)


def checked_linux_as_manifest(path: Path, digest: str) -> tuple[dict, Path]:
    if digest != LINUX_AS_MANIFEST_SHA256 or sha256(path) != digest:
        raise RuntimeError("explicit Linux assembler manifest checksum mismatch")
    record = json.loads(path.read_text())
    if (record.get("schema") != 1 or record.get("architecture") != "mips"
            or record.get("native_compiler_triple") != "mips-elf"
            or record.get("assembler_sha256") != LINUX_AS_SHA256):
        raise RuntimeError("unsupported Linux assembler manifest")
    binary = Path(record["assembler_path"])
    if not binary.is_absolute() or sha256(binary) != LINUX_AS_SHA256:
        raise RuntimeError("Linux assembler binary checksum mismatch")
    return record, binary


def build(arch: str, mode: str, toolchain: Path, source_archive: Path,
          generated_headers: Path, output: Path,
          assembler_manifest: Path | None = None,
          assembler_manifest_sha256: str | None = None) -> tuple[Path, str]:
    mode = mode.lower()
    if arch not in ARCH or mode not in MODE_FLAGS:
        raise RuntimeError("unsupported architecture or mode")
    override_as = arch == "mips"
    if override_as and (assembler_manifest is None or assembler_manifest_sha256 is None):
        raise RuntimeError("MIPS32 requires an explicit Linux assembler manifest and SHA256")
    if not override_as and (assembler_manifest is not None or assembler_manifest_sha256 is not None):
        raise RuntimeError("MIPS64 uses its compiler-selected assembler")
    if override_as:
        as_record, as_binary = checked_linux_as_manifest(
            assembler_manifest.resolve(), assembler_manifest_sha256)
    if output.exists():
        raise RuntimeError(f"output must be a fresh directory: {output}")
    source_archive = source_archive.resolve()
    if sha256(source_archive) != ARCHIVE_SHA256:
        raise RuntimeError("GCC 14.2 source archive checksum mismatch")
    generated_headers = generated_headers.resolve()
    compiler = (toolchain.resolve() / "bin" / f"{arch}-elf-gcc").resolve()
    tools = tool_inventory(compiler, arch)
    root = output.resolve()
    root.mkdir(parents=True)
    (root / "objects").mkdir()
    (root / "logs").mkdir()
    shutil.copy2(Path(__file__), root / "mips_pic_runtime.py")

    with tarfile.open(source_archive, "r:xz") as archive:
        for name in SOURCE_FILES + LICENSE_FILES:
            member = archive.getmember(f"gcc-14.2.0/{name}")
            if not member.isfile():
                raise RuntimeError(f"unexpected GCC archive member: {name}")
            destination = root / "inputs/gcc-14.2.0" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
    if sha256(root / "inputs/gcc-14.2.0/libgcc/libgcc2.c") != SOURCE_SHA256:
        raise RuntimeError("GCC 14.2 libgcc2.c checksum mismatch")
    for name in GENERATED_GCC:
        source = generated_headers / "gcc" / name
        destination = root / "inputs/generated/gcc" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    source = generated_headers / f"{arch}-elf/libgcc/libgcc_tm.h"
    destination = root / "inputs/generated" / f"{arch}-elf/libgcc/libgcc_tm.h"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    internal = Path(run([str(compiler), "-print-file-name=include"]).strip()).resolve()
    if not internal.is_dir():
        raise RuntimeError(f"compiler internal include directory missing: {internal}")
    for name in TOOLCHAIN_HEADERS:
        destination = root / "inputs/toolchain-include" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(internal / name, destination)
    if override_as:
        destination = root / "inputs/assembler/manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assembler_manifest, destination)
        destination = root / "tools/assembler/as"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(as_binary, destination)
        if sha256(destination) != LINUX_AS_SHA256:
            raise RuntimeError("retained Linux assembler digest changed")
        selected = run([str(compiler), f"-B{destination.parent}/",
                        "-print-prog-name=as"]).strip()
        if Path(selected).resolve() != destination:
            raise RuntimeError(f"compiler did not select the retained Linux assembler: {selected}")
    pins = [relative_pin(root, root / name)
            for name in expected_inputs(arch, override_as)]
    manifest = {"schema": 3 if override_as else 2,
                "architecture": arch, "mode": mode,
                "profile": ARCH[arch][4], "status": "PIC-archive-built",
                "target_executed": False,
                "source_archive_sha256": ARCHIVE_SHA256,
                "original_build_dir": str(root), "tools": tools,
                "inputs": pins, "members": [], "archive": {}}
    if override_as:
        manifest["assembler_override"] = {
            "kind": "retained-linux-as-override",
            "source_manifest": relative_pin(root, root / "inputs/assembler/manifest.json"),
            "source_assembler_path": as_record["assembler_path"],
            "source_assembler_sha256": LINUX_AS_SHA256,
            "retained_as": relative_pin(root, root / "tools/assembler/as"),
            "selected_as": str(root / "tools/assembler/as"),
            "baseline_as": tools["as"],
        }
    for name, symbol in MEMBERS[arch]:
        obj = root / "objects" / f"{name}.o"
        dep = root / "objects" / f"{name}.d"
        log = root / "logs" / f"compile-{name}.log"
        argv = compile_argv(root, arch, mode, tools, override_as) + [f"-DL_{name}",
                "-MD", "-MF", str(dep), "-c",
                str(root / "inputs/gcc-14.2.0/libgcc/libgcc2.c"), "-o", str(obj)]
        run(argv, log)
        selected = actual_compiler_programs(log)
        if selected["cc1"] != tools["cc1"]["path"]:
            raise RuntimeError("actual compiler cc1 differs from selected tool")
        expected_as = str(root / "tools/assembler/as") if override_as else tools["as"]["path"]
        if selected["as"] != expected_as:
            raise RuntimeError(f"actual assembler differs from selected tool: {selected['as']}")
        used = dependencies(dep, root)
        expected = sorted(name for name in expected_inputs(arch, override_as)
                          if name.startswith("inputs/") and name not in
                          [f"inputs/gcc-14.2.0/{license_name}" for license_name in LICENSE_FILES]
                          and name != "inputs/assembler/manifest.json")
        if used != expected:
            raise RuntimeError(f"compiler dependencies differ from retained inventory: {set(used) ^ set(expected)}")
        member = {"name": f"{name}.o", "source_macro": f"L_{name}",
                                    "symbol": symbol, "command": argv,
                                    "exit_status": 0, "actual_programs": selected,
                                    "compile_log": relative_pin(root, log),
                                    "dependency_file": relative_pin(root, dep),
                                    "dependencies": [relative_pin(root, root / entry)
                                                     for entry in used],
                                    "object": audit_object(obj, arch, symbol, tools)}
        if override_as:
            member["symtab_order"] = audit_local_symtab_order(obj)
        manifest["members"].append(member)
    archive = root / "libgcc_pic.a"
    members = [str(root / "objects" / f"{name}.o") for name, _ in MEMBERS[arch]]
    run([tools["ar"]["path"], "crD", str(archive), *members], root / "logs/archive.log")
    run([tools["ranlib"]["path"], "-D", str(archive)], root / "logs/ranlib.log")
    actual = run([tools["ar"]["path"], "t", str(archive)]).splitlines()
    expected_members = [f"{name}.o" for name, _ in MEMBERS[arch]]
    if actual != expected_members:
        raise RuntimeError("unexpected archive member order")
    manifest["archive"] = {"path": "libgcc_pic.a", "sha256": sha256(archive),
                           "members": actual, "deterministic_ar": True}
    manifest["archive_logs"] = [relative_pin(root, root / "logs/archive.log"),
                                relative_pin(root, root / "logs/ranlib.log")]
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return archive, sha256(path)


def admit(build_dir: Path, manifest_sha256: str, arch: str, mode: str,
          compiler: Path) -> tuple[Path, dict]:
    root = build_dir.resolve()
    path = root / "manifest.json"
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256 or "") or sha256(path) != manifest_sha256:
        raise RuntimeError("explicit PIC runtime manifest checksum mismatch")
    manifest = json.loads(path.read_text())
    mode = mode.lower()
    schema = manifest.get("schema")
    override_as = schema == 3 and arch == "mips"
    if (arch not in ARCH or mode not in MODE_FLAGS
            or not (override_as or (schema == 2 and arch == "mips64"))
            or manifest.get("architecture") != arch or manifest.get("mode") != mode
            or manifest.get("profile") != ARCH[arch][4]
            or manifest.get("status") != "PIC-archive-built"
            or manifest.get("target_executed") is not False
            or manifest.get("source_archive_sha256") != ARCHIVE_SHA256):
        raise RuntimeError("unsupported PIC runtime manifest")
    tools = tool_inventory(compiler, arch)
    if tools != manifest["tools"]:
        raise RuntimeError("compiler, cc1, assembler or binary tool identity changed")
    expected = expected_inputs(arch, override_as)
    if [pin["path"] for pin in manifest["inputs"]] != expected:
        raise RuntimeError("retained compiler input inventory changed")
    for pin in manifest["inputs"]:
        verify_pin(root, pin)
    if sha256(root / "inputs/gcc-14.2.0/libgcc/libgcc2.c") != SOURCE_SHA256:
        raise RuntimeError("GCC 14.2 source checksum changed")
    original = Path(manifest["original_build_dir"])
    if not original.is_absolute():
        raise RuntimeError("invalid original build directory")
    if override_as:
        override = manifest.get("assembler_override")
        if not isinstance(override, dict) or override.get("kind") != "retained-linux-as-override":
            raise RuntimeError("missing explicit Linux assembler override")
        source_manifest = verify_pin(root, override["source_manifest"])
        retained_as = verify_pin(root, override["retained_as"])
        if (override["source_manifest"]["path"] != "inputs/assembler/manifest.json"
                or override["source_manifest"]["sha256"] != LINUX_AS_MANIFEST_SHA256
                or override["retained_as"]["path"] != "tools/assembler/as"
                or override["retained_as"]["sha256"] != LINUX_AS_SHA256
                or override["source_assembler_sha256"] != LINUX_AS_SHA256
                or override["selected_as"] != str(original / "tools/assembler/as")
                or override["baseline_as"] != tools["as"]):
            raise RuntimeError("Linux assembler provenance changed")
        source_record = json.loads(source_manifest.read_text())
        if (source_record.get("schema") != 1
                or source_record.get("architecture") != "mips"
                or source_record.get("native_compiler_triple") != "mips-elf"
                or source_record.get("assembler_path") != override["source_assembler_path"]
                or source_record.get("assembler_sha256") != LINUX_AS_SHA256
                or not Path(override["source_assembler_path"]).is_absolute()
                or retained_as != root / "tools/assembler/as"):
            raise RuntimeError("Linux assembler source manifest changed")
        expected_as = str(original / "tools/assembler/as")
    else:
        if "assembler_override" in manifest:
            raise RuntimeError("unexpected assembler override")
        expected_as = tools["as"]["path"]
    expected_members = [f"{name}.o" for name, _ in MEMBERS[arch]]
    if [item["name"] for item in manifest["members"]] != expected_members:
        raise RuntimeError("PIC runtime member set changed")
    for item, (name, symbol) in zip(manifest["members"], MEMBERS[arch]):
        obj = root / "objects" / f"{name}.o"
        dep = verify_pin(root, item["dependency_file"])
        log = verify_pin(root, item["compile_log"])
        expected_argv = compile_argv(original, arch, mode, tools, override_as) + [f"-DL_{name}",
                "-MD", "-MF", str(original / "objects" / f"{name}.d"),
                "-c", str(original / "inputs/gcc-14.2.0/libgcc/libgcc2.c"),
                "-o", str(original / "objects" / f"{name}.o")]
        if (item["symbol"] != symbol or item["source_macro"] != f"L_{name}"
                or item["command"] != expected_argv or item["exit_status"] != 0):
            raise RuntimeError(f"unexpected compile recipe for {name}")
        selected = actual_compiler_programs(log)
        if (selected != item["actual_programs"]
                or selected["cc1"] != tools["cc1"]["path"]
                or selected["as"] != expected_as):
            raise RuntimeError(f"actual compiler tool selection changed for {name}")
        used = dependencies(dep, original)
        dep_pins = item["dependencies"]
        if [pin["path"] for pin in dep_pins] != used:
            raise RuntimeError(f"compiler dependency list changed for {name}")
        for pin in dep_pins:
            verify_pin(root, pin)
        if not obj.is_file() or sha256(obj) != item["object"]["sha256"]:
            raise RuntimeError(f"retained object digest changed: {name}")
        if audit_object(obj, arch, symbol, tools) != item["object"]:
            raise RuntimeError(f"retained object ABI changed: {name}")
        if override_as and audit_local_symtab_order(obj) != item["symtab_order"]:
            raise RuntimeError(f"retained symbol table order changed: {name}")
    for pin in manifest["archive_logs"]:
        verify_pin(root, pin)
    archive_pin = manifest["archive"]
    archive = retained_path(root, archive_pin["path"])
    if archive_pin["path"] != "libgcc_pic.a" or sha256(archive) != archive_pin["sha256"]:
        raise RuntimeError("PIC runtime archive digest changed")
    actual = run([tools["ar"]["path"], "t", str(archive)]).splitlines()
    if actual != expected_members or archive_pin["members"] != expected_members or not archive_pin["deterministic_ar"]:
        raise RuntimeError("PIC runtime archive member order changed")
    for item in manifest["members"]:
        content = subprocess.check_output([tools["ar"]["path"], "p", str(archive), item["name"]], env=SAFE_ENV)
        if hashlib.sha256(content).hexdigest() != item["object"]["sha256"]:
            raise RuntimeError(f"archive member differs from retained object: {item['name']}")
    return archive, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--arch", required=True, choices=tuple(ARCH))
    builder.add_argument("--mode", required=True, choices=("Debug", "Release", "debug", "release"))
    builder.add_argument("--toolchain", required=True, type=Path)
    builder.add_argument("--source-archive", required=True, type=Path)
    builder.add_argument("--generated-headers", required=True, type=Path)
    builder.add_argument("--assembler-manifest", type=Path)
    builder.add_argument("--assembler-manifest-sha256")
    builder.add_argument("--output", required=True, type=Path)
    validator = commands.add_parser("admit")
    validator.add_argument("--arch", required=True, choices=tuple(ARCH))
    validator.add_argument("--mode", required=True, choices=("Debug", "Release", "debug", "release"))
    validator.add_argument("--compiler", required=True, type=Path)
    validator.add_argument("--build-dir", required=True, type=Path)
    validator.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if args.command == "build":
        archive, digest = build(args.arch, args.mode, args.toolchain,
                                args.source_archive, args.generated_headers, args.output,
                                args.assembler_manifest, args.assembler_manifest_sha256)
        print(json.dumps({"archive": str(archive), "manifest_sha256": digest}, sort_keys=True))
    else:
        archive, record = admit(args.build_dir, args.manifest_sha256,
                                args.arch, args.mode, args.compiler)
        print(json.dumps({"archive": str(archive), "archive_sha256": record["archive"]["sha256"]},
                         sort_keys=True))


if __name__ == "__main__":
    main()
