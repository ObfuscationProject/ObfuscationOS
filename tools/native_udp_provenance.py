"""Complete source and compiler-input inventories for native UDP qualification."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

EXCLUDED = {"build", ".xmake", "__pycache__"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping_digest(mapping: dict) -> str:
    return hashlib.sha256(json.dumps(mapping, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def source_inventory(kernel: Path, os_root: Path) -> dict[str, dict[str, str]]:
    result = {}
    for name, root in (("ObfuscationKernel", kernel), ("ObfuscationOS", os_root)):
        result[name] = {str(path.relative_to(root)): sha(path)
                        for path in root.rglob("*") if path.is_file() and
                        not (set(path.relative_to(root).parts) & EXCLUDED)}
    runner = os_root.parents[1]
    result["V3Runners"] = {name: sha(runner / name) for name in
                           ("produce_sdk_matrix.py", "qualify_native_udp_v3.py")}
    return result


def require_source_inventory(inventory: Path, kernel: Path, os_root: Path) -> str:
    expected = json.loads(inventory.read_text())["files"]
    actual = source_inventory(kernel, os_root)
    if actual != expected:
        difference = {name: sorted(key for key in set(actual.get(name, {})) |
                                   set(expected.get(name, {}))
                                   if actual.get(name, {}).get(key) != expected.get(name, {}).get(key))
                      for name in set(actual) | set(expected)}
        raise ValueError(f"complete native UDP source inventory differs: {difference}")
    return sha(inventory)


def compiler_inputs(prefix: Path, triple: str) -> dict[str, str]:
    """Pin compiler drivers, link helpers, runtime archives and their headers."""
    gcc = prefix / "bin" / f"{triple}-gcc"
    version = subprocess.check_output([str(gcc), "-dumpfullversion"], text=True).strip()
    gcc_dir = prefix / "lib" / "gcc" / triple / version
    libexec = prefix / "libexec" / "gcc" / triple / version
    paths = [prefix / "bin" / f"{triple}-{name}" for name in
             ("gcc", "g++", "as", "ld", "ar", "ranlib", "objcopy", "strip")]
    paths += [libexec / name for name in
              ("cc1", "cc1plus", "collect2", "lto-wrapper", "lto1", "liblto_plugin.so")]
    paths += [gcc_dir / name for name in ("libgcc.a", "crtbegin.o", "crtend.o")]
    paths.extend(path for path in gcc_dir.rglob("*") if path.is_file())
    for directory in (prefix / triple / "include", prefix / "include"):
        if directory.exists():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"compiler input is missing: {missing}")
    return {str(path.relative_to(prefix)): sha(path) for path in sorted(set(paths))}


def require_compiler_inputs(record: Path, prefix: Path, triple: str) -> str:
    expected = json.loads(record.read_text())
    if expected["triple"] != triple or expected["prefix"] != str(prefix.resolve()):
        raise ValueError("native UDP compiler profile does not match receipt")
    actual = compiler_inputs(prefix, triple)
    if actual != expected["files"]:
        raise ValueError("native UDP compiler or header input changed")
    return sha(record)
