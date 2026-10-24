#!/usr/bin/env python3
"""Create the supported non-journalled ext4 format without clobbering on failure."""
import argparse
import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def normalize_bootstrap_root(payload: bytes, staging: Path, *, profile='bootstrap') -> bytes:
    source = Path(__file__).with_name("rootfs_policy.py")
    spec = importlib.util.spec_from_file_location("obfuscation_native_rootfs_policy", source)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    return policy.normalize_bootstrap_root(payload, staging, profile=profile)


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
    parser.add_argument("--profile", choices=("bootstrap", "linux-stat-fixture-v1"), default="bootstrap",
                        help="Explicit disposable stat fixture policy; normal images use bootstrap")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    if not root.is_dir():
        raise SystemExit(f"root must be an existing directory: {root}")
    mke2fs = require("mke2fs")
    e2fsck = require("e2fsck")
    out.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, LC_ALL="C", TZ="UTC")
    for name in ("MKE2FS_CONFIG", "E2FSCK_CONFIG", "LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix=".ext4-", dir=out.parent) as directory:
        image = Path(directory) / "rootfs.img"
        subprocess.check_call([
            mke2fs, "-q", "-t", "ext4", "-b", "4096", "-I", "256",
            "-O", "none,extent,filetype,sparse_super,large_file",
            "-E", "lazy_itable_init=0", "-L", "ObfuscationOS", "-m", "0",
            "-d", str(root), str(image), args.size,
        ], env=environment)
        # The native /init bootstrap runs as guest root. Host ownership and
        # umask must not become guest policy through mke2fs -d staging.
        image.write_bytes(normalize_bootstrap_root(image.read_bytes(), root, profile=args.profile))
        subprocess.check_call([e2fsck, "-fn", str(image)], env=environment)
        image.replace(out)
    print(f"[ext4] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
