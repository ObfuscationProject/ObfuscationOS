#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


REQUIRED_SYMBOLS = (
    "OK_UAPI_VERSION_MAJOR",
    "OK_UAPI_VERSION_MINOR",
    "OK_UAPI_VERSION_PATCH",
    "OK_SYS_EXIT",
    "OK_SYS_READ",
    "OK_SYS_WRITE",
    "OK_SYS_OPEN",
    "OK_SYS_CLOSE",
    "OK_SYS_STAT",
    "OK_SYS_GETDENTS",
    "OK_SYS_GETDENTS64",
    "OK_ENOSYS",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", required=True)
    args = parser.parse_args()

    include = Path(args.include)
    syscall = include / "ok" / "uapi" / "syscall.h"
    if not syscall.is_file():
        raise SystemExit(f"missing UAPI header: {syscall}")

    text = syscall.read_text(encoding="utf-8")
    for symbol in REQUIRED_SYMBOLS:
        if not re.search(rf"^\s*#define\s+{symbol}\b", text, re.MULTILINE):
            raise SystemExit(f"missing UAPI symbol: {symbol}")

    for name in ("ok_stat", "ok_timespec", "ok_iovec"):
        if f"struct {name}" not in text:
            raise SystemExit(f"missing UAPI layout: struct {name}")

    print(f"[uapi] checked {include}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
