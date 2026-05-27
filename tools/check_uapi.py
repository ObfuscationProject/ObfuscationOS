#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


REQUIRED_SYMBOLS = (
    "OK_UAPI_VERSION",
    "OK_SYS_EXIT",
    "OK_SYS_READ",
    "OK_SYS_WRITE",
    "OK_SYS_OPEN",
    "OK_SYS_CLOSE",
    "OK_SYS_STAT",
    "OK_SYS_GETDENTS",
    "OK_ENOSYS",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", required=True)
    args = parser.parse_args()

    include = Path(args.include)
    syscall = include / "ok" / "uapi" / "syscall.h"
    errno = include / "ok" / "uapi" / "errno.h"
    types = include / "ok" / "uapi" / "types.h"
    for path in (syscall, errno, types):
        if not path.is_file():
            raise SystemExit(f"missing UAPI header: {path}")

    text = syscall.read_text(encoding="utf-8") + errno.read_text(encoding="utf-8")
    for symbol in REQUIRED_SYMBOLS:
        if not re.search(rf"^\s*#define\s+{symbol}\b", text, re.MULTILINE):
            raise SystemExit(f"missing UAPI symbol: {symbol}")

    types_text = types.read_text(encoding="utf-8")
    for name in ("ok_stat", "ok_timespec", "ok_iovec"):
        if f"struct {name}" not in types_text:
            raise SystemExit(f"missing UAPI layout: struct {name}")

    print(f"[uapi] checked {include}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
