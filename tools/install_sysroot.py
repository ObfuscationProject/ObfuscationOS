#!/usr/bin/env python3
import argparse
import os
import shutil
from pathlib import Path


UAPI_CANDIDATES = (
    "uapi/include",
    "include/uapi",
    "include",
)


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


def find_kernel_uapi(kernel_dir: Path) -> Path | None:
    if not kernel_dir.exists():
        return None
    for candidate in UAPI_CANDIDATES:
        path = kernel_dir / candidate
        syscall = path / "ok" / "uapi" / "syscall.h"
        if syscall.is_file():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--sysroot", required=True)
    parser.add_argument("--lib", required=True)
    parser.add_argument("--arch", required=True)
    args = parser.parse_args()

    project = Path(args.project)
    sysroot = Path(args.sysroot)
    include_dir = sysroot / "include"
    lib_dir = sysroot / "lib"

    if sysroot.exists():
        shutil.rmtree(sysroot)
    include_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)

    kernel_uapi = find_kernel_uapi(project / "external" / "ObfuscationKernel")
    if kernel_uapi is None:
        kernel_uapi = project / "uapi" / "include"
        print(f"[sysroot] external kernel UAPI not found, using local fallback: {kernel_uapi}")
    else:
        print(f"[sysroot] using kernel UAPI: {kernel_uapi}")

    copy_tree(kernel_uapi, include_dir)
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
