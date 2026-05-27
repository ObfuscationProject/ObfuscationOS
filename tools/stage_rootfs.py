#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


APPS = ("init", "oksh", "hello", "cat", "ls", "stat", "mkdir", "rm")


OS_RELEASE = """NAME=ObfuscationOS
ID=obfuscationos
VERSION_ID=0.1.0-userland
PRETTY_NAME="ObfuscationOS userland MVP"
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apps-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    apps_dir = Path(args.apps_dir)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)

    bin_dir = out / "bin"
    etc_dir = out / "etc"
    bin_dir.mkdir(parents=True)
    etc_dir.mkdir(parents=True)

    for app in APPS:
        src = apps_dir / f"{app}.elf"
        if not src.is_file():
            raise SystemExit(f"missing app: {src}")
        dst = bin_dir / app
        shutil.copy2(src, dst)
        dst.chmod(0o755)

    (etc_dir / "os-release").write_text(OS_RELEASE, encoding="utf-8")
    print(f"[rootfs] staged {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
