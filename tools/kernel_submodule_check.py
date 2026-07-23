#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path


EXPECTED_PREFIX = "2e22c7a619d58f012ab27577a16dd4a469734c8d"


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--expected", default=EXPECTED_PREFIX)
    args = parser.parse_args()

    repo = Path(args.project) / "external" / "ObfuscationKernel"
    if not repo.exists():
        raise SystemExit(
            "external/ObfuscationKernel is missing. Run: "
            "git submodule update --init --recursive external/ObfuscationKernel"
        )

    try:
        head = git_output(repo, "rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"external/ObfuscationKernel is not a usable git checkout: {exc}")

    if not head.startswith(args.expected):
        raise SystemExit(
            f"external/ObfuscationKernel is at {head}, expected {args.expected} "
            "(repository gitlink baseline)"
        )

    syscall = repo / "uapi" / "include" / "ok" / "uapi" / "syscall.h"
    if not syscall.is_file():
        print("[kernel] warning: canonical uapi/include path not found; sysroot will probe fallbacks")

    print(f"[kernel] submodule OK: {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
