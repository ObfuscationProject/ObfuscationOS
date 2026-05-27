#!/usr/bin/env python3
import argparse
import shutil
import subprocess
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

    root = Path(args.root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    mke2fs = require("mke2fs")
    e2fsck = require("e2fsck")

    subprocess.check_call(
        [
            mke2fs,
            "-q",
            "-t",
            "ext4",
            "-L",
            "ObfuscationOS",
            "-m",
            "0",
            "-d",
            str(root),
            str(out),
            args.size,
        ]
    )
    subprocess.check_call([e2fsck, "-fn", str(out)])
    print(f"[ext4] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
