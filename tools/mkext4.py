#!/usr/bin/env python3
"""Create the supported non-journalled ext4 format without clobbering on failure."""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def require(program: str) -> str:
    found = shutil.which(program)
    if not found:
        raise SystemExit(f"required program not found: {program}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--size", default="16M")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    if not root.is_dir():
        raise SystemExit(f"root must be an existing directory: {root}")
    mke2fs = require("mke2fs")
    e2fsck = require("e2fsck")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ext4-", dir=out.parent) as directory:
        image = Path(directory) / "rootfs.img"
        subprocess.check_call([
            mke2fs, "-q", "-t", "ext4", "-b", "4096", "-I", "256",
            "-O", "none,extent,filetype,sparse_super,large_file",
            "-E", "lazy_itable_init=0", "-L", "ObfuscationOS", "-m", "0",
            "-d", str(root), str(image), args.size,
        ])
        subprocess.check_call([e2fsck, "-fn", str(image)])
        image.replace(out)
    print(f"[ext4] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
