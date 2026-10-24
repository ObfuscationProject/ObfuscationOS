#!/usr/bin/env python3
"""Bind compiler-reported project dependencies into a static-musl PID 1 build."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    project = args.project.resolve()
    source = args.source.resolve()
    if not source.is_file() or not source.is_relative_to(project):
        raise ValueError("PID 1 source must be inside the explicit OS project")
    manifest_path = build / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema_version") != 1 or manifest.get("status") != "built-not-executed" or
            manifest.get("executed") is not False or manifest.get("probe_sha256") != sha(source)):
        raise ValueError("unadmitted PID 1 build/source")
    compile_command = manifest["commands"][0]
    at = compile_command.index("-c")
    command = [*compile_command[:at], "-M", "-MT", "pid1-guest", str(source)]
    output = subprocess.check_output(command, text=True).replace("\\\n", "")
    if not output.startswith("pid1-guest:"):
        raise ValueError("unexpected compiler dependency result")
    include_at = compile_command.index("-isystem")
    include = Path(compile_command[include_at + 1]).resolve()
    found = {}
    for token in shlex.split(output.split(":", 1)[1]):
        path = Path(token).resolve()
        if not path.is_file():
            raise ValueError("compiler dependency disappeared: " + token)
        if path.is_relative_to(project):
            found[str(path.relative_to(project))] = sha(path)
        elif not path.is_relative_to(include):
            raise ValueError("compiler dependency is outside explicit project and musl sysroot: " + token)
    expected = {str(source.relative_to(project))}
    if source.name in ("pid1.c", "pid1_init.c"):
        expected.update({"apps/init/pid1.c", "apps/init/pid1_policy.h"})
    if set(found) != expected:
        raise ValueError("PID 1 compiler dependencies differ from the explicit source contract")
    manifest["project_source_dependencies"] = found
    manifest["project_dependency_command"] = command
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(manifest_path)
    print("PASS sealed PID 1 project dependencies:", ", ".join(sorted(found)))


if __name__ == "__main__":
    main()
