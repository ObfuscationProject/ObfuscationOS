#!/usr/bin/env python3
import argparse
import os
import shutil
from pathlib import Path

from kernel_sdk import validate_sdk


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for root, _, files in os.walk(src):
        root_path = Path(root)
        rel = root_path.relative_to(src)
        out_dir = dst / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copy2(root_path / name, out_dir / name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--sysroot", required=True)
    parser.add_argument("--lib", required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--kernel-sdk", required=True, type=Path)
    parser.add_argument("--mode", required=True)
    args = parser.parse_args()
    validate_sdk(args.kernel_sdk, args.arch, args.mode)

    project = Path(args.project)
    sysroot = Path(args.sysroot)
    include_dir = sysroot / "include"
    lib_dir = sysroot / "lib"

    if sysroot.exists():
        shutil.rmtree(sysroot)
    include_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)

    kernel_uapi = args.kernel_sdk / "include" / "ok" / "uapi"
    print(f"[sysroot] using exported kernel UAPI: {kernel_uapi}")

    copy_tree(kernel_uapi, include_dir / "ok" / "uapi")
    copy_tree(project / "sdk" / "include", include_dir)
    copy_tree(project / "lib" / "okcrt" / "include", include_dir)

    lib = Path(args.lib)
    if not lib.is_file():
        raise SystemExit(f"libokcrt.a not found: {lib}")
    shutil.copy2(lib, lib_dir / "libokcrt.a")

    (sysroot / "ARCH").write_text(args.arch + "\n", encoding="utf-8")
    print(f"[sysroot] installed {sysroot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
