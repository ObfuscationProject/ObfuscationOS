#!/usr/bin/env python3
"""Build and admit portable GCC 14.2 PIC libgcc archives for musl targets.

The builder runs only upstream ``make libgcc.a`` in a fresh artifact directory.
Every compiler input and selected tool is retained as a regular file. Admission
does not access the original GCC source archive or configured build tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


SOURCE_ARCHIVE_SHA256 = "a7b39bc69cbf9e25826c5a60ab26477001f7c08d85cec04bc0e29cabed6f3cc9"
ARCH = {
    "rv32": {"triple": "riscv32-elf", "flags": ("-march=rv32gc", "-mabi=ilp32d"),
             "profile": "rv32gc-ilp32d", "elf_class": "ELF32", "machine": "RISC-V",
             "e_flags": "0x5"},
    "rv64": {"triple": "riscv64-elf", "flags": ("-march=rv64gc", "-mabi=lp64d"),
             "profile": "rv64gc-lp64d", "elf_class": "ELF64", "machine": "RISC-V",
             "e_flags": "0x5"},
    "loongarch64": {"triple": "loongarch64-elf",
                    "flags": ("-march=loongarch64", "-mabi=lp64d", "-msimd=none"),
                    "profile": "loongarch64-lp64d-no-simd", "elf_class": "ELF64",
                    "machine": "LoongArch", "e_flags": "0x43"},
}
MODE = {"debug": ("-O2", "-g3"), "release": ("-O2", "-g0")}
LICENSES = {"COPYING", "COPYING3", "COPYING.LIB", "COPYING3.LIB", "COPYING.RUNTIME"}
GENERATED_CONFIG = ("Makefile", "config.status", "auto-target.h", "libgcc_tm.h", "stamp-h")
TOOL_NAMES = ("gcc", "cc1", "as", "ar", "ranlib", "nm", "strip", "readelf")
ENV_REMOVE = ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "CPATH",
              "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH",
              "GCC_EXEC_PREFIX", "COMPILER_PATH", "CC", "CFLAGS", "CPPFLAGS",
              "LDFLAGS", "LD_PRELOAD", "PYTHONPATH")


def safe_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    result = {"PATH": "/usr/bin:/bin", "LC_ALL": "C",
              "PYTHONDONTWRITEBYTECODE": "1", "SOURCE_DATE_EPOCH": "1708128000"}
    if extra:
        result.update(extra)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output(argv: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(argv, cwd=cwd, env=safe_environment(), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv}\n{result.stdout}")
    return result.stdout


def source_selected(name: str, arch: str) -> bool:
    parts = PurePosixPath(name).parts
    if not parts or parts[0] != "gcc-14.2.0" or ".." in parts:
        return False
    if len(parts) == 2 and parts[1] in LICENSES | {"move-if-change", "mkinstalldirs"}:
        return True
    if len(parts) < 3:
        return False
    if parts[1] in ("libgcc", "include"):
        return True
    if parts[1] != "gcc":
        return False
    if len(parts) == 3 and (PurePosixPath(name).suffix in (".h", ".def")
                            or parts[2] == "BASE-VER"):
        return True
    if len(parts) >= 4 and parts[2] == "config":
        target = "riscv" if arch in ("rv32", "rv64") else "loongarch"
        return parts[3] == target or (len(parts) == 4 and name.endswith(".h"))
    return False


def extract_source(archive_path: Path, root: Path, arch: str) -> list[str]:
    selected = []
    with tarfile.open(archive_path, "r|xz") as archive:
        for member in archive:
            if not source_selected(member.name, arch):
                continue
            if not member.isfile():
                continue
            relative = PurePosixPath(member.name)
            destination = root / "source" / Path(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream, destination.open("xb") as target:
                shutil.copyfileobj(stream, target)
            destination.chmod(member.mode & 0o777)
            selected.append(destination.relative_to(root).as_posix())
    missing = [name for name in LICENSES
               if not (root / "source/gcc-14.2.0" / name).is_file()]
    if missing or not (root / "source/gcc-14.2.0/libgcc/libgcc2.c").is_file():
        raise RuntimeError(f"incomplete GCC 14.2 source extraction: {missing}")
    return sorted(selected)


def compiler_program(compiler: Path, name: str) -> Path:
    value = output([str(compiler), f"-print-prog-name={name}"]).strip()
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError(f"compiler did not select absolute {name}: {value}")
    return path.resolve()


def tool_paths(compiler: Path, arch: str) -> dict[str, Path]:
    triple = ARCH[arch]["triple"]
    compiler = compiler.resolve()
    if compiler.name != f"{triple}-gcc":
        raise RuntimeError(f"compiler target mismatch: {compiler}")
    if output([str(compiler), "-dumpmachine"]).strip() != triple:
        raise RuntimeError(f"compiler reported a different target than {triple}")
    tools = {"gcc": compiler, "cc1": compiler_program(compiler, "cc1"),
             "as": compiler_program(compiler, "as")}
    for name in ("ar", "ranlib", "nm", "strip", "readelf"):
        tools[name] = compiler.with_name(f"{triple}-{name}").resolve()
    if not all(path.is_file() for path in tools.values()):
        raise RuntimeError("missing compiler tool")
    return tools


def copy_inputs(root: Path, configured: Path, compiler: Path,
                tools: dict[str, Path]) -> tuple[list[str], dict]:
    generated = configured / "gcc"
    generated_paths = []
    for source in sorted(generated.iterdir()):
        if source.is_file() and (source.suffix == ".h" or source.name == "libgcc.mvars"):
            destination = root / "generated-gcc" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            generated_paths.append(destination.relative_to(root).as_posix())
    triple = compiler.name.removesuffix("-gcc")
    original = configured / triple / "libgcc"
    config_paths = []
    for name in GENERATED_CONFIG:
        destination = root / ("configured-inputs" if name == "libgcc_tm.h" else "build") / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original / name, destination)
        config_paths.append(destination.relative_to(root).as_posix())
    internal = Path(output([str(compiler), "-print-file-name=include"]).strip()).resolve()
    if not internal.is_dir():
        raise RuntimeError(f"missing compiler internal headers: {internal}")
    header_paths = []
    for source in sorted(internal.rglob("*")):
        if not source.is_file():
            continue
        destination = root / "compiler-include" / source.relative_to(internal)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        header_paths.append(destination.relative_to(root).as_posix())
    pins = {}
    for name, path in tools.items():
        destination = root / "tool-pins" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        pins[name] = {"path": str(path), "sha256": sha256(path),
                      "retained": destination.relative_to(root).as_posix()}
    for name, path in (("make", Path(shutil.which("make", path="/usr/bin:/bin") or "").resolve()),
                       ("python", Path(sys.executable).resolve())):
        if not path.is_file():
            raise RuntimeError(f"missing host build tool: {name}")
        destination = root / "tool-pins" / name
        shutil.copy2(path, destination)
        pins[name] = {"path": str(path), "sha256": sha256(path),
                      "retained": destination.relative_to(root).as_posix()}
    return sorted(generated_paths + config_paths + header_paths), pins


def make_command(root: Path, arch: str, mode: str, tools: dict) -> list[str]:
    profile = ARCH[arch]
    compiler = tools["gcc"]["path"]
    driver = root / "compiler_driver.py"
    cc = f"{tools['python']['path']} -B {driver} {compiler}"
    flags = [*profile["flags"], *MODE[mode], "-fPIC", "-v", "-nostdinc",
             "-fno-stack-protector", "-isystem", str(root / "compiler-include")]
    return [tools["make"]["path"], "-j4", "-o", "Makefile", "-o",
            "config.status", "-o", "stamp-h", "-o", "auto-target.h",
            "libgcc.a", f"CC={cc}", f"gcc_objdir={root / 'generated-gcc'}",
            f"srcdir={root / 'source/gcc-14.2.0/libgcc'}",
            f"libgcc_topdir={root / 'source/gcc-14.2.0'}",
            f"CFLAGS={' '.join(flags)}", "HOST_LIBGCC2_CFLAGS=-fPIC",
            f"LIBGCC2_DEBUG_CFLAGS={MODE[mode][1]}",
            *[f"{name.upper()}={tools[name]['path']}"
              for name in ("ar", "ranlib", "nm", "strip")],
            "AR_FLAGS=rcD", "AR_FLAGS_FOR_TARGET=D", "MULTIDIRS=",
            "enable_gcov=no"]


def compiler_programs_from_log(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith(" "):
            continue
        try:
            first = shlex.split(line)[0]
        except (ValueError, IndexError):
            continue
        executable = Path(first)
        if executable.is_absolute() and executable.name in ("cc1", "as"):
            found[executable.name] = str(executable.resolve())
    return found


def dependency_paths(path: Path, original_root: Path) -> list[str]:
    data = path.read_text().replace("\\\n", " ")
    if ":" not in data:
        raise RuntimeError(f"invalid dependency file: {path}")
    names = [token.rstrip(":") for token in data.split(":", 1)[1].split()]
    result = set()
    for name in names:
        if not name or name == "\\":
            continue
        candidate = Path(name)
        absolute = (candidate if candidate.is_absolute() else original_root / "build" / candidate).resolve()
        if not absolute.is_relative_to(original_root):
            raise RuntimeError(f"compiler read an unretained file: {name}")
        result.add(absolute.relative_to(original_root).as_posix())
    return sorted(result)


def replace_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        resolved = path.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(root):
            raise RuntimeError(f"build created an external or invalid symlink: {path}")
        contents = resolved.read_bytes()
        mode = resolved.stat().st_mode & 0o777
        path.unlink()
        path.write_bytes(contents)
        path.chmod(mode)


def file_inventory(root: Path) -> list[dict[str, str]]:
    pins = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"artifact contains a symlink: {path}")
        if path.is_file() and path != root / "manifest.json":
            pins.append({"path": path.relative_to(root).as_posix(), "sha256": sha256(path)})
    return pins


def audit_object(path: Path, arch: str, readelf: Path) -> dict[str, str]:
    header = output([str(readelf), "-h", str(path)])
    profile = ARCH[arch]
    for required in (f"Class:                             {profile['elf_class']}",
                     "Data:                              2's complement, little endian",
                     "Type:                              REL (Relocatable file)",
                     f"Machine:                           {profile['machine']}"):
        if required not in header:
            raise RuntimeError(f"object ABI mismatch ({required}): {path}")
    flags = next((line.strip() for line in header.splitlines() if "Flags:" in line), "")
    match = re.search(r"\bFlags:\s*(0x[0-9a-fA-F]+)", flags)
    if not match or match.group(1).lower() != profile["e_flags"]:
        raise RuntimeError(f"object ELF ABI flags mismatch: {path}: {flags}")
    if arch in ("rv32", "rv64") and ("RVC" not in flags or "double-float ABI" not in flags):
        raise RuntimeError(f"RISC-V compressed/double-float ABI flags missing: {path}")
    if arch == "loongarch64" and ("DOUBLE-FLOAT" not in flags or "OBJ-v1" not in flags):
        raise RuntimeError(f"LoongArch double-float ABI flags missing: {path}")
    return {"sha256": sha256(path), "header_flags": flags}


def build(arch: str, mode: str, toolchain: Path, source_archive: Path,
          configured_build: Path, artifact: Path) -> tuple[Path, str]:
    mode = mode.lower()
    if arch not in ARCH or mode not in MODE:
        raise RuntimeError("unsupported architecture or mode")
    if artifact.exists() or artifact.is_symlink():
        raise RuntimeError(f"artifact output must be fresh: {artifact}")
    source_archive = source_archive.resolve()
    if sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise RuntimeError("GCC 14.2 source archive checksum mismatch")
    triple = ARCH[arch]["triple"]
    compiler = (toolchain.resolve() / "bin" / f"{triple}-gcc").resolve()
    configured_build = configured_build.resolve()
    tools = tool_paths(compiler, arch)
    root = artifact.resolve()
    root.mkdir(parents=True)
    (root / "build").mkdir()
    (root / "logs").mkdir()
    shutil.copy2(Path(__file__), root / "gcc_pic_runtime.py")
    shutil.copy2(Path(__file__).with_name("compiler_driver.py"), root / "compiler_driver.py")
    source_paths = extract_source(source_archive, root, arch)
    copied_inputs, tool_pins = copy_inputs(root, configured_build, compiler, tools)
    build_inputs = {name: sha256(root / name) for name in source_paths + copied_inputs}
    command = make_command(root, arch, mode, tool_pins)
    environment = safe_environment({"PIC_RUNTIME_LOG_DIR": str(root / "logs")})
    with (root / "logs/build.log").open("xb") as log:
        result = subprocess.run(command, cwd=root / "build", env=environment,
                                stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"upstream libgcc.a build failed ({result.returncode}); see {root / 'logs/build.log'}")
    archive = root / "build/libgcc.a"
    if not archive.is_file():
        raise RuntimeError("upstream make succeeded without libgcc.a")
    ranlib_command = [tool_pins["ranlib"]["path"], "-D", str(archive)]
    with (root / "logs/ranlib.log").open("xb") as log:
        ranlib_result = subprocess.run(ranlib_command, env=safe_environment(),
                                       stdout=log, stderr=subprocess.STDOUT,
                                       check=False)
    if ranlib_result.returncode:
        raise RuntimeError("deterministic ranlib failed")
    replace_symlinks(root)
    for name, digest in build_inputs.items():
        if sha256(root / name) != digest:
            raise RuntimeError(f"GCC source or configured input changed during build: {name}")
    if tool_paths(compiler, arch) != tools:
        raise RuntimeError("compiler tool selection changed during build")
    for name, path in tools.items():
        if sha256(path) != tool_pins[name]["sha256"] or sha256(root / tool_pins[name]["retained"]) != tool_pins[name]["sha256"]:
            raise RuntimeError(f"compiler tool bytes changed during build: {name}")
    invocation_file = root / "logs/invocations.jsonl"
    invocations = [json.loads(line) for line in invocation_file.read_text().splitlines()]
    if not invocations or any(item["returncode"] != 0 for item in invocations):
        raise RuntimeError("missing or failed compiler invocation")
    for item in invocations:
        if item["argv"][0] != tool_pins["gcc"]["path"]:
            raise RuntimeError("compiler driver invoked an unexpected tool")
        log = root / item["log"]
        item["log_sha256"] = sha256(log)
        item["actual_programs"] = compiler_programs_from_log(log)
        if "-c" in item["argv"]:
            if item["actual_programs"] != {name: tool_pins[name]["path"] for name in ("cc1", "as")}:
                raise RuntimeError(f"actual compiler program selection changed: {log}")
            for required in (*ARCH[arch]["flags"], *MODE[mode], "-fPIC", "-nostdinc"):
                if required not in item["argv"]:
                    raise RuntimeError(f"compiler flag missing ({required}): {log}")
    deps = {}
    for dep in sorted((root / "build").glob("*.dep")):
        used = dependency_paths(dep, root)
        for entry in used:
            if not (root / entry).is_file():
                raise RuntimeError(f"compiler dependency missing from artifact: {entry}")
        deps[dep.relative_to(root).as_posix()] = used
    if not deps:
        raise RuntimeError("upstream compiler did not retain dependency files")
    objects = {}
    for obj in sorted((root / "build").glob("*.o")):
        objects[obj.name] = audit_object(obj, arch, tools["readelf"])
    if not objects:
        raise RuntimeError("upstream build produced no ELF objects")
    members = output([str(tools["ar"]), "t", str(archive)]).splitlines()
    if len(members) != len(set(members)) or not members:
        raise RuntimeError("empty or duplicate-member archive")
    for member in members:
        if member not in objects:
            raise RuntimeError(f"archive member has no retained object: {member}")
        contents = subprocess.check_output([str(tools["ar"]), "p", str(archive), member],
                                           env=safe_environment())
        if hashlib.sha256(contents).hexdigest() != objects[member]["sha256"]:
            raise RuntimeError(f"archive member differs from retained object: {member}")
    manifest = {
        "schema": 1, "arch": arch, "mode": mode, "profile": ARCH[arch]["profile"],
        "mode_flags": list(MODE[mode]), "target_executed": False,
        "status": "upstream-PIC-libgcc-archive-built", "host_install": False,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "original_build_dir": str(root), "tools": tool_pins,
        "source_files": source_paths, "configured_inputs": copied_inputs,
        "build_command": command, "build_returncode": result.returncode,
        "ranlib_command": ranlib_command, "ranlib_returncode": ranlib_result.returncode,
        "compiler_invocations": invocations, "dependencies": deps,
        "objects": objects,
        "archive": {"path": "build/libgcc.a", "sha256": sha256(archive),
                    "members": members, "deterministic": True},
        "files": file_inventory(root),
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return archive, sha256(path)


def retained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeError(f"invalid retained path: {relative!r}")
    path = root
    for part in Path(relative).parts:
        if part in (".", ".."):
            raise RuntimeError(f"invalid retained path component: {relative}")
        path = path / part
        if path.is_symlink():
            raise RuntimeError(f"symlink in retained path: {relative}")
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise RuntimeError(f"missing or escaping retained file: {relative}")
    return path


def reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"symlink in artifact directory path: {current}")


def admit(build_dir: Path, manifest_sha256: str, arch: str, mode: str,
          compiler: Path) -> tuple[Path, dict]:
    reject_symlink_components(build_dir.absolute())
    root = build_dir.resolve()
    path = root / "manifest.json"
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256 or "") or sha256(path) != manifest_sha256:
        raise RuntimeError("explicit PIC libgcc manifest checksum mismatch")
    record = json.loads(path.read_text())
    mode = mode.lower()
    if (arch not in ARCH or mode not in MODE or record.get("schema") != 1
            or record.get("arch") != arch or record.get("mode") != mode
            or record.get("profile") != ARCH[arch]["profile"]
            or record.get("mode_flags") != list(MODE[mode])
            or record.get("status") != "upstream-PIC-libgcc-archive-built"
            or record.get("target_executed") is not False
            or record.get("host_install") is not False
            or record.get("source_archive_sha256") != SOURCE_ARCHIVE_SHA256):
        raise RuntimeError("unsupported architecture, mode or profile in PIC runtime")
    current_tools = tool_paths(compiler, arch)
    tools = record["tools"]
    if set(tools) != set(TOOL_NAMES) | {"make", "python"}:
        raise RuntimeError("compiler tool inventory changed")
    for name in TOOL_NAMES:
        path = current_tools[name]
        if {"path": str(path), "sha256": sha256(path),
                "retained": f"tool-pins/{name}"} != tools[name]:
            raise RuntimeError(f"selected compiler tool changed: {name}")
    for name, pin in tools.items():
        file = retained(root, pin["retained"])
        if pin["retained"] != f"tool-pins/{name}" or sha256(file) != pin["sha256"]:
            raise RuntimeError(f"retained tool bytes changed: {name}")
    original = Path(record["original_build_dir"])
    if not original.is_absolute() or record["build_command"] != make_command(original, arch, mode, tools):
        raise RuntimeError("upstream build command or mode changed")
    if record["build_returncode"] != 0 or record["ranlib_returncode"] != 0:
        raise RuntimeError("upstream build did not complete")
    if record["ranlib_command"] != [tools["ranlib"]["path"], "-D", str(original / "build/libgcc.a")]:
        raise RuntimeError("deterministic archive command changed")
    if not record["source_files"] or not all(
            name.startswith("source/gcc-14.2.0/") for name in record["source_files"]):
        raise RuntimeError("missing GCC source provenance")
    for name in LICENSES:
        if f"source/gcc-14.2.0/{name}" not in record["source_files"]:
            raise RuntimeError(f"missing GCC license: {name}")
    if not record["configured_inputs"]:
        raise RuntimeError("missing configured GCC inputs")
    files = file_inventory(root)
    if files != record["files"]:
        raise RuntimeError("retained source, header, log, tool, object or archive changed")
    all_paths = {item["path"] for item in files}
    if not set(record["source_files"] + record["configured_inputs"]).issubset(all_paths):
        raise RuntimeError("recorded compiler inputs are missing")
    invocations_file = retained(root, "logs/invocations.jsonl")
    raw_invocations = [json.loads(line) for line in invocations_file.read_text().splitlines()]
    invocations = record["compiler_invocations"]
    if len(raw_invocations) != len(invocations) or not invocations:
        raise RuntimeError("compiler invocation record changed")
    for raw, item in zip(raw_invocations, invocations):
        if any(raw[key] != item[key] for key in ("argv", "returncode", "log")):
            raise RuntimeError("compiler command or exit status changed")
        if item["returncode"] != 0 or item["argv"][0] != tools["gcc"]["path"]:
            raise RuntimeError("compiler invocation failed or changed")
        log = retained(root, item["log"])
        if sha256(log) != item["log_sha256"]:
            raise RuntimeError("compiler invocation log changed")
        actual = compiler_programs_from_log(log)
        if actual != item["actual_programs"]:
            raise RuntimeError("actual compiler program log changed")
        if "-c" in item["argv"]:
            if actual != {name: tools[name]["path"] for name in ("cc1", "as")}:
                raise RuntimeError("actual cc1 or assembler selection changed")
            for flag in (*ARCH[arch]["flags"], *MODE[mode], "-fPIC", "-nostdinc"):
                if flag not in item["argv"]:
                    raise RuntimeError(f"compile mode or PIC flag changed: {flag}")
    for dep_name, expected in record["dependencies"].items():
        used = dependency_paths(retained(root, dep_name), original)
        if used != expected or not set(used).issubset(all_paths):
            raise RuntimeError(f"compiler dependencies changed: {dep_name}")
    if not record["dependencies"]:
        raise RuntimeError("missing compiler dependency inventory")
    objects = record["objects"]
    if not objects:
        raise RuntimeError("missing compiler runtime objects")
    for name, audit in objects.items():
        if audit_object(retained(root, f"build/{name}"), arch, current_tools["readelf"]) != audit:
            raise RuntimeError(f"compiler runtime object ABI changed: {name}")
    archive_record = record["archive"]
    if archive_record["path"] != "build/libgcc.a" or archive_record["deterministic"] is not True:
        raise RuntimeError("unexpected compiler runtime archive")
    archive = retained(root, archive_record["path"])
    if sha256(archive) != archive_record["sha256"]:
        raise RuntimeError("compiler runtime archive digest changed")
    members = output([str(current_tools["ar"]), "t", str(archive)]).splitlines()
    if not members or members != archive_record["members"] or len(members) != len(set(members)):
        raise RuntimeError("compiler runtime archive member list changed")
    for name in members:
        if name not in objects:
            raise RuntimeError(f"compiler runtime archive member missing object: {name}")
        contents = subprocess.check_output([str(current_tools["ar"]), "p", str(archive), name],
                                           env=safe_environment())
        if hashlib.sha256(contents).hexdigest() != objects[name]["sha256"]:
            raise RuntimeError(f"archive member differs from retained object: {name}")
    return archive, record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--arch", required=True, choices=tuple(ARCH))
    builder.add_argument("--mode", required=True, choices=("Debug", "Release", "debug", "release"))
    builder.add_argument("--toolchain", required=True, type=Path)
    builder.add_argument("--source-archive", required=True, type=Path)
    builder.add_argument("--configured-build", required=True, type=Path)
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
                                args.source_archive, args.configured_build, args.output)
        print(json.dumps({"archive": str(archive), "manifest_sha256": digest}, sort_keys=True))
    else:
        archive, record = admit(args.build_dir, args.manifest_sha256, args.arch,
                                args.mode, args.compiler)
        print(json.dumps({"archive": str(archive),
                          "archive_sha256": record["archive"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
