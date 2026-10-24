#!/usr/bin/env python3
"""Package an explicit musl UDP boot archive without changing normal staging."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys

from build_musl_probe import admit_musl_build, verify_compile_dependencies
from musl_source import inspect_elf
from mkarchive import pack

ROOT = Path(__file__).resolve().parents[1]
SUPPLIED = ("x86_64", "aarch64", "rv64", "loongarch64")
FIXTURES = {
    "udp": ("tests/musl/udp.c", "tests/native/musl_udp_runner.c", "/bin/musl-udp-probe"),
    "udp-sockname": ("tests/musl/udp_sockname.c", "tests/native/musl_udp_sockname_runner.c",
                     "/bin/musl-udp-sockname-probe"),
    "udp-connected": ("tests/musl/udp_connected.c", "tests/native/musl_udp_connected_runner.c",
                      "/bin/musl-udp-connected-probe"),
}


def fixture_spec(name: str) -> tuple[str, str, str]:
    """Select one closed source/parent/archive-path tuple; no path overrides."""
    if name not in FIXTURES:
        raise ValueError("unknown explicit musl UDP fixture")
    return FIXTURES[name]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path: Path) -> dict:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("fixture input is not a regular file: " + str(path))
    return {"path": str(path.resolve()), "sha256": sha(path), "mode": oct(stat.S_IMODE(path.stat().st_mode))}


def inventory(root: Path) -> dict[str, dict]:
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("fixture root must be an existing directory")
    rows = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        name = "/" + path.relative_to(root).as_posix()
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("fixture root contains a symlink or special file")
        rows[name] = {"mode": mode,
                      "bytes": path.stat().st_size if stat.S_ISREG(mode) else 0,
                      "sha256": sha(path) if stat.S_ISREG(mode) else hashlib.sha256(b"").hexdigest()}
    return rows



def archive_inventory(root: Path) -> dict[str, dict]:
    """Independently admit exact OKAR v1 permissions, without importing owners.

    Keep inventory() for complete host metadata and endpoint preservation checks.
    Directories allow sticky/SGID; regular files allow ordinary permissions only.
    """
    rows = inventory(root)
    for row in rows.values():
        kind = row["mode"] & 0o170000
        allowed = 0o043777 if kind == 0o040000 else 0o100777
        if row["mode"] & ~allowed:
            raise ValueError("fixture root has unsupported archive permissions")
    return rows


def inspect_archive(blob: bytes) -> dict[str, dict]:
    """Independent bounded OKAR parsing, including all metadata and padding."""
    if len(blob) < 16:
        raise ValueError("fixture archive header is truncated")
    magic, version, count, reserved = struct.unpack_from("<4sIII", blob)
    if (magic, version, reserved) != (b"OKAR", 1, 0) or count > 4096:
        raise ValueError("fixture archive header is invalid")
    cursor, rows, previous = 16, {}, ""
    for _ in range(count):
        if cursor + 16 > len(blob):
            raise ValueError("fixture archive record is truncated")
        namesz, size, mode, flags = struct.unpack_from("<IIII", blob, cursor)
        cursor += 16
        if not 1 <= namesz < 128 or cursor + namesz + size > len(blob):
            raise ValueError("fixture archive path/payload length is invalid")
        try:
            name = blob[cursor:cursor + namesz].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("fixture archive path is not ASCII") from exc
        cursor += namesz
        parts = name.split("/")[1:]
        kind = mode & 0o170000
        allowed = 0o043777 if kind == 0o040000 else 0o100777
        if (not name.startswith("/") or name <= previous or name in rows or
                any(not part or part in (".", "..") or len(part) >= 32 or "\0" in part for part in parts) or
                not parts or flags or mode & ~allowed or kind not in (0o040000, 0o100000) or
                (kind == 0o040000 and size)):
            raise ValueError("fixture archive path, mode or ordering is invalid")
        payload = blob[cursor:cursor + size]
        cursor += size
        aligned = (cursor + 7) & ~7
        if aligned > len(blob) or any(blob[cursor:aligned]):
            raise ValueError("fixture archive padding is invalid")
        rows[name] = {"mode": mode, "bytes": size, "sha256": hashlib.sha256(payload).hexdigest()}
        previous, cursor = name, aligned
    if cursor != len(blob):
        raise ValueError("fixture archive has trailing data")
    return rows


def manifest(path: Path, expected: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or sha(path) != expected:
        raise ValueError("fixture manifest pin differs: " + str(path))
    return json.loads(path.read_text())


def inspect_static(path: Path, arch: str, osabi: int) -> None:
    inspect_elf(path, arch)
    data = path.read_bytes()
    if data[7:9] != bytes((osabi, 0)) or struct.unpack_from("<I", data, 20)[0] != 1:
        raise ValueError("fixture static ELF personality/version differs")
    entry, offset = struct.unpack_from("<QQ", data, 24)
    size, count = struct.unpack_from("<HH", data, 54)
    if size != 56 or not 1 <= count <= 128 or offset < 64 or offset + size * count > len(data):
        raise ValueError("fixture static ELF program-header table is invalid")
    executable = False
    for index in range(count):
        kind, flags, file_offset, address, _, file_size, memory_size, alignment = struct.unpack_from(
            "<IIQQQQQQ", data, offset + index * size)
        if kind in (2, 3):
            raise ValueError("fixture static ELF contains dynamic/interpreter segment")
        if kind != 1:
            continue
        if (file_size > memory_size or file_offset + file_size > len(data) or
                memory_size > (1 << 64) - 1 - address or
                (alignment not in (0, 1) and
                 (alignment & (alignment - 1) or address % alignment != file_offset % alignment))):
            raise ValueError("fixture static ELF load extent is invalid")
        executable |= bool(flags & 1 and address <= entry < address + file_size)
    if not executable:
        raise ValueError("fixture static ELF has no loaded executable entry")


def admit_child(build: Path, expected: str, musl: Path, musl_sha: str, arch: str, mode: str,
                fixture: str = "udp") -> dict:
    source_name, _, _ = fixture_spec(fixture)
    value = manifest(build / "manifest.json", expected)
    musl_manifest = manifest(musl / "manifest.json", musl_sha)
    if admit_musl_build(musl, arch) != musl_manifest or musl_manifest["mode"] != mode:
        raise ValueError("explicit musl sysroot profile differs")
    source, linker = ROOT / source_name, ROOT / "tests/musl/bootstrap.ld"
    if (value.get("schema_version") != 1 or value.get("architecture") != arch or value.get("mode") != mode or
            value.get("status") != "built-not-executed" or value.get("executed") is not False or
            value.get("source_manifest_sha256") != musl_sha or value.get("probe_sha256") != sha(source) or
            value.get("linker_script_sha256") != sha(linker) or value.get("elf_sha256") != sha(build / "bootstrap.elf")):
        raise ValueError("explicit UDP child manifest differs from source/sysroot/ELF")
    dependencies = value.get("compile_dependencies")
    if not isinstance(dependencies, dict) or not dependencies.get("same_command_as_object") or dependencies.get("command_index") != 0:
        raise ValueError("explicit UDP child requires actual compile dependency capture")
    verify_compile_dependencies(dependencies)
    if str(source.resolve()) not in dependencies["files"]:
        raise ValueError("explicit UDP compile dependencies omit this unchanged probe source")
    commands = value.get("commands")
    if not isinstance(commands, list) or len(commands) != 3 or str(source.resolve()) not in commands[0] or "-MD" not in commands[0]:
        raise ValueError("explicit UDP actual producing command differs")
    child = build / "bootstrap.elf"
    inspect_static(child, arch, 3)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=tuple(FIXTURES), default="udp")
    parser.add_argument("--arch", choices=SUPPLIED, required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--normal-root", type=Path, required=True)
    parser.add_argument("--native-parent", type=Path, required=True)
    parser.add_argument("--child-build", type=Path, required=True)
    parser.add_argument("--child-manifest-sha256", required=True)
    parser.add_argument("--musl-build", type=Path, required=True)
    parser.add_argument("--musl-manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        parser.error("use PYTHONDONTWRITEBYTECODE=1 python3 -B")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    record = {"schema": 1, "status": "failed", "arch": args.arch, "mode": args.mode,
              "normal_root_modified": False, "guest_executed": False, "linked_image_qualified": False,
              "construction_and_stack_closure_qualified": False}
    source_name, parent_name, child_name = fixture_spec(args.fixture)
    if args.fixture != "udp":
        record["fixture"] = args.fixture
    error = None
    before = None
    try:
        before = inventory(args.normal_root)
        record["normal_root_before"] = before
        probe = admit_child(args.child_build.resolve(), args.child_manifest_sha256,
                            args.musl_build.resolve(), args.musl_manifest_sha256, args.arch, args.mode, args.fixture)
        inspect_static(args.native_parent, args.arch, 0)
        inputs = {"native_parent": pin(args.native_parent), "child": pin(args.child_build / "bootstrap.elf"),
                  "child_manifest": pin(args.child_build / "manifest.json"), "musl_manifest": pin(args.musl_build / "manifest.json"),
                  "probe_source": pin(ROOT / source_name), "linker_script": pin(ROOT / "tests/musl/bootstrap.ld"),
                  "native_parent_source": pin(ROOT / parent_name),
                  "packager": pin(Path(__file__)), "archive_builder": pin(ROOT / "tools/mkarchive.py")}
        record["inputs_before"] = inputs
        record["probe_commands"] = probe["commands"]
        root = args.out / "root"
        shutil.copytree(args.normal_root, root, copy_function=shutil.copy2)
        shutil.copy2(args.native_parent, root / "init")
        shutil.copy2(args.child_build / "bootstrap.elf", root / child_name.lstrip("/"))
        (root / "init").chmod(0o755); (root / child_name.lstrip("/")).chmod(0o755)
        actual = inventory(root)
        expected_root = dict(before)
        for name, key in (("/init", "native_parent"), (child_name, "child")):
            input_path = Path(inputs[key]["path"])
            expected_root[name] = {"mode": 0o100755, "bytes": input_path.stat().st_size, "sha256": inputs[key]["sha256"]}
        if actual != expected_root:
            raise ValueError("fixture copied root differs outside its exact parent/child payloads")
        archive = args.out / "boot.okar"
        blob = pack(root)
        archive.write_bytes(blob)
        archive_expected = archive_inventory(root)
        if inspect_archive(blob) != archive_expected:
            raise ValueError("independent fixture archive payload inventory differs")
        include = args.out / "boot.okar.inc"
        include.write_text("// " + sha(archive) + '\n.incbin "' + str(archive) + '"\n')
        record.update(root=str(root), root_entries=actual, archive_entries=archive_expected,
                      archive_mode_masks={"directory": oct(0o043777), "regular": oct(0o100777)},
                      archive=pin(archive), archive_include=pin(include),
                      copied_parent=pin(root / "init"), copied_child=pin(root / child_name.lstrip("/")),
                      independent_archive_payloads_identical=True)
        record["inputs_after"] = {name: pin(Path(saved["path"])) for name, saved in inputs.items()}
        if record["inputs_after"] != inputs:
            raise ValueError("fixture packaging input changed at endpoint verification")
        admit_child(args.child_build.resolve(), args.child_manifest_sha256,
                    args.musl_build.resolve(), args.musl_manifest_sha256, args.arch, args.mode, args.fixture)
        if inventory(args.normal_root) != before or inventory(root) != actual:
            raise ValueError("normal or fixture root changed during packaging")
        record["status"] = "packaged-not-linked-or-executed"
    except (OSError, ValueError, KeyError, struct.error) as exc:
        error = str(exc)
    finally:
        if before is not None:
            try:
                record["normal_root_after"] = inventory(args.normal_root)
                if record["normal_root_after"] != before:
                    raise ValueError("normal root changed during fixture packaging")
            except (OSError, ValueError) as exc:
                error = error or str(exc)
        if error:
            record.update(status="failed", error=error)
        (args.out / "receipt.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    if error:
        print("MUSL_UDP_PACKAGE_FAIL " + error, file=sys.stderr)
        return 1
    print("MUSL_UDP_PACKAGE_PASS receipt=" + str(args.out / "receipt.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
