#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


EXPECTED_DEFINES = {
    "OK_UAPI_VERSION_MAJOR": 0,
    "OK_UAPI_VERSION_MINOR": 1,
    "OK_UAPI_VERSION_PATCH": 0,
    "OK_SYS_READ": 0,
    "OK_SYS_WRITE": 1,
    "OK_SYS_OPEN": 2,
    "OK_SYS_CLOSE": 3,
    "OK_SYS_STAT": 4,
    "OK_SYS_FSTAT": 5,
    "OK_SYS_LSEEK": 8,
    "OK_SYS_EXIT": 60,
    "OK_SYS_GETDENTS": 78,
    "OK_SYS_MKDIR": 83,
    "OK_SYS_UNLINK": 87,
    "OK_SYS_GETDENTS64": 217,
    "OK_SYS_OK_DEBUG": 1024,
    "OK_ENOENT": 2,
    "OK_EFAULT": 14,
    "OK_EINVAL": 22,
    "OK_ENOSYS": 38,
    "OK_O_DIRECTORY": 0x0200000,
    "OK_MODE_REGULAR": 0o100000,
    "OK_MODE_DIRECTORY": 0o040000,
}

EXPECTED_FIELDS = {
    "ok_timespec": [("int64_t", "seconds"), ("int64_t", "nanoseconds")],
    "ok_iovec": [("uintptr_t", "base"), ("uintptr_t", "length")],
    "ok_stat": [
        ("uint8_t", "type"),
        ("uintptr_t", "size"),
        ("uint32_t", "mode"),
        ("uint32_t", "uid"),
        ("uint32_t", "gid"),
        ("uint32_t", "link_count"),
        ("uint32_t", "block_size"),
        ("uint64_t", "blocks"),
    ],
}


def parse_int_token(token: str) -> int:
    token = token.strip()
    while token.startswith("(") and token.endswith(")"):
        token = token[1:-1].strip()
    while token and token[-1] in "uUlL":
        token = token[:-1]
    sign = -1 if token.startswith("-") else 1
    if sign < 0:
        token = token[1:]
    if token.lower().startswith("0x"):
        value = int(token, 16)
    elif len(token) > 1 and token.startswith("0") and token[1:].isdigit():
        value = int(token, 8)
    else:
        value = int(token, 10)
    return sign * value


def parse_defines(text: str) -> dict[str, int]:
    defines: dict[str, int] = {}
    for match in re.finditer(r"^\s*#define\s+([A-Za-z0-9_]+)\s+([^\s/]+)", text, re.MULTILINE):
        name, raw_value = match.groups()
        try:
            defines[name] = parse_int_token(raw_value)
        except ValueError:
            continue
    return defines


def struct_fields(text: str, name: str) -> list[tuple[str, str]]:
    match = re.search(rf"struct\s+{name}\s*\{{(?P<body>.*?)\}};", text, re.DOTALL)
    if not match:
        raise SystemExit(f"missing UAPI layout: struct {name}")
    fields: list[tuple[str, str]] = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("/*"):
            continue
        field = re.match(r"([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*;", line)
        if field:
            fields.append((field.group(1), field.group(2)))
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", required=True)
    args = parser.parse_args()

    include = Path(args.include)
    syscall = include / "ok" / "uapi" / "syscall.h"
    if not syscall.is_file():
        raise SystemExit(f"missing UAPI header: {syscall}")

    text = syscall.read_text(encoding="utf-8")
    defines = parse_defines(text)
    for symbol, expected in EXPECTED_DEFINES.items():
        if symbol not in defines:
            raise SystemExit(f"missing UAPI symbol: {symbol}")
        if defines[symbol] != expected:
            raise SystemExit(f"unexpected UAPI value: {symbol}={defines[symbol]} expected={expected}")

    for name, expected in EXPECTED_FIELDS.items():
        fields = struct_fields(text, name)
        if fields != expected:
            raise SystemExit(f"unexpected UAPI layout: struct {name} fields={fields} expected={expected}")

    print(f"[uapi] checked {include}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
