#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


EXPECTED_DEFINES = {
    "OK_UAPI_VERSION_MAJOR": 0,
    "OK_UAPI_VERSION_MINOR": 16,
    "OK_UAPI_VERSION_PATCH": 0,
    "OK_MAP_FIXED": 0x10,
    "OK_SYS_READ": 0,
    "OK_SYS_WRITE": 1,
    "OK_SYS_POLL": 7,
    "OK_SYS_PIPE2": 293,
    "OK_SYS_OPEN": 2,
    "OK_SYS_CLOSE": 3,
    "OK_SYS_STAT": 4,
    "OK_SYS_FSTAT": 5,
    "OK_SYS_LSEEK": 8,
    "OK_SYS_EXIT": 60,
    "OK_SYS_KILL": 62,
    "OK_NATIVE_CREDENTIALS_VERSION": 1,
    "OK_NATIVE_SESSIONS_VERSION": 3,
    "OK_SYS_SETPGID": 109,
    "OK_SYS_GETPGRP": 111,
    "OK_SYS_SETSID": 112,
    "OK_SYS_GETPGID": 121,
    "OK_SYS_GETSID": 124,
    "OK_ESRCH": 3,
    "OK_NATIVE_CONSOLE_LEASE_VERSION": 1,
    "OK_NATIVE_CONSOLE_CONTROL_VERSION": 1,
    "OK_SYS_IOCTL": 16,
    "OK_TIOCSCTTY": 0x540e,
    "OK_TIOCGSID": 0x5429,
    "OK_TIOCGPGRP": 0x540f,
    "OK_TIOCSPGRP": 0x5410,
    "OK_EIO": 5,
    "OK_EBADF": 9,
    "OK_ENOTTY": 25,
    "OK_NATIVE_PERSISTENT_SYNC_VERSION": 1,
    "OK_NATIVE_POWER_VERSION": 1,
    "OK_NATIVE_METADATA_VERSION": 1,
    "OK_SYS_CHMOD": 90,
    "OK_SYS_FCHMOD": 91,
    "OK_SYS_CHOWN": 92,
    "OK_SYS_FCHOWN": 93,
    "OK_SYS_FCHOWNAT": 260,
    "OK_SYS_FCHMODAT": 268,
    "OK_AT_EMPTY_PATH": 0x1000,
    "OK_POWER_TOKEN_MAX": 0x3fffffff,
    "OK_POWER_HALT": 1,
    "OK_POWER_REBOOT": 2,
    "OK_POWER_POWEROFF": 3,
    "OK_CONSOLE_EPOCH_MAX": 0x3fffffff,
    "OK_SYS_SETUID": 105,
    "OK_SYS_SETGID": 106,
    "OK_SYS_SETREUID": 113,
    "OK_SYS_SETREGID": 114,
    "OK_SYS_SETRESUID": 117,
    "OK_SYS_GETRESUID": 118,
    "OK_SYS_SETRESGID": 119,
    "OK_SYS_GETRESGID": 120,
    "OK_SYS_GETDENTS": 78,
    "OK_SYS_RENAME": 82,
    "OK_SYS_MKDIR": 83,
    "OK_SYS_RMDIR": 84,
    "OK_SYS_LINK": 86,
    "OK_SYS_UNLINK": 87,
    "OK_SYS_SYMLINK": 88,
    "OK_SYS_READLINK": 89,
    "OK_SYS_GETDENTS64": 217,
    "OK_SYS_CLOCK_SETTIME": 227,
    "OK_SYS_RENAMEAT": 264,
    "OK_SYS_LINKAT": 265,
    "OK_SYS_SYMLINKAT": 266,
    "OK_SYS_READLINKAT": 267,
    "OK_SYS_OK_DEBUG": 1024,
    "OK_SYS_LOAD_MODULE": 1025,
    "OK_SYS_FSTAT_V2": 1026,
    "OK_SYS_NEWFSTATAT_V2": 1027,
    "OK_SYS_CONSOLE_CLAIM": 1028,
    "OK_SYS_CONSOLE_REVOKE": 1029,
    "OK_SYS_CONSOLE_FLUSH": 1030,
    "OK_SYS_SYNC_PERSISTENT": 1031,
    "OK_SYS_POWER_PREPARE": 1032,
    "OK_SYS_POWER_COMMIT": 1033,
    "OK_NATIVE_MOUNT_INFO_VERSION": 1,
    "OK_SYS_MOUNT_INFO": 1034,
    "OK_SYS_PTY_PAIR": 1035,
    "OK_NATIVE_PTY_PAIR_VERSION": 1,
    "OK_NATIVE_PTY_NONBLOCK": 0x0800,
    "OK_NATIVE_PTY_CLOEXEC": 0x080000,
    "OK_MOUNT_INFO_CAPACITY": 9,
    "OK_MOUNT_INFO_PATH_CAPACITY": 256,
    "OK_MOUNT_STATE_UNUSED": 0,
    "OK_MOUNT_STATE_UNDERLYING_RAM": 1,
    "OK_MOUNT_STATE_BORROWED": 2,
    "OK_MOUNT_STATE_OWNED_PROVIDER": 3,
    "OK_MOUNT_STATE_OWNED_RAM": 4,
    "OK_MOUNT_STATE_DETACHED": 5,
    "OK_ENOENT": 2,
    "OK_EFAULT": 14,
    "OK_EINVAL": 22,
    "OK_ENOSYS": 38,
    "OK_ELOOP": 40,
    "OK_O_NOFOLLOW": 0x020000,
    "OK_O_NONBLOCK": 0x0800,
    "OK_POLLIN": 1,
    "OK_POLLOUT": 4,
    "OK_POLLERR": 8,
    "OK_POLLHUP": 16,
    "OK_POLLNVAL": 32,
    "OK_AT_SYMLINK_NOFOLLOW": 0x0100,
    "OK_O_DIRECTORY": 0x0200000,
    "OK_AT_FDCWD": -100,
    "OK_MODE_REGULAR": 0o100000,
    "OK_MODE_DIRECTORY": 0o040000,
}

EXPECTED_FIELDS = {
    "ok_mount_info": [("uint32_t", name) for name in (
        "version", "size", "generation", "slot", "capacity", "state", "parent_id", "path_length")]
        + [("char", "path[OK_MOUNT_INFO_PATH_CAPACITY]")],
    "ok_stat_v2": [("struct ok_stat", "basic"), ("uint64_t", "inode")],
    "ok_pollfd": [("int32_t", "fd"), ("int16_t", "events"), ("int16_t", "revents")],
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


def uapi_code(text: str) -> str:
    """Preserve token boundaries and newlines while excluding comment decoys."""
    if any(token in text for token in ('\\', '??', '%:')):
        raise SystemExit("unsupported UAPI line splicing")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", lambda match: re.sub(r"[^\n]", " ", match[0]),
                  text, flags=re.DOTALL)
    if any(token in text for token in ('/*', '*/', '"', "'")):
        raise SystemExit("unsupported UAPI syntax")
    return text


def parse_defines(text: str) -> dict[str, int]:
    text = uapi_code(text)
    defines: dict[str, int] = {}
    seen: set[str] = set()
    integer = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)"
                         r"(?:[uU](?:ll|LL|l|L)?|(?:ll|LL|l|L)[uU]?)?")
    for line in text.splitlines():
        match = re.fullmatch(r"[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)(.*)", line)
        if not match:
            continue
        name, replacement = match.groups()
        if name in seen:
            raise SystemExit(f"duplicate UAPI symbol: {name}")
        seen.add(name)
        value = replacement.strip()
        # Admit the canonical (-100) constant and nested parentheses around
        # one complete literal. Parentheses cannot discard an expression tail.
        while value.startswith("("):
            depth, closing = 0, None
            for index, byte in enumerate(value):
                if byte == "(":
                    depth += 1
                elif byte == ")":
                    depth -= 1
                    if not depth:
                        closing = index
                        break
            if closing != len(value) - 1:
                break
            value = value[1:-1].strip()
        # A function-like macro has no separating space before its opening
        # parenthesis. Never let it impersonate an expected object constant.
        if (replacement and replacement[0] not in " \t") or not integer.fullmatch(value):
            if name in EXPECTED_DEFINES:
                raise SystemExit(f"unsupported UAPI value: {name}")
            continue
        defines[name] = parse_int_token(value)
    return defines


def validate_directives(text: str) -> None:
    """Refuse preprocessing contexts outside this header's canonical grammar."""
    text = uapi_code(text)
    directives = [" ".join(line.split()) for line in text.splitlines() if line.lstrip().startswith("#")]
    if (directives[:2] != ["#ifndef OK_UAPI_SYSCALL_H", "#define OK_UAPI_SYSCALL_H"] or
            not directives or directives[-1] != "#endif"):
        raise SystemExit("unsupported UAPI include guard")
    for line in directives[2:-1]:
        if line == "#include <stdint.h>":
            continue
        if not re.match(r"#define OK_[A-Z0-9_]+(?:\s|\(|$)", line):
            raise SystemExit("unsupported UAPI directive: " + line)


def struct_fields(text: str, name: str) -> list[tuple[str, str]]:
    text = uapi_code(text)
    match = re.search(rf"struct\s+{name}\s*\{{(?P<body>.*?)\}};", text, re.DOTALL)
    if not match:
        raise SystemExit(f"missing UAPI layout: struct {name}")
    fields: list[tuple[str, str]] = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("/*"):
            continue
        field = re.fullmatch(r"((?:struct\s+)?[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)"
                             r"(?:\s*\[\s*([A-Za-z_][A-Za-z0-9_]*|[1-9][0-9]*)\s*\])?\s*;", line)
        if not field:
            raise SystemExit(f"unsupported UAPI field: struct {name}: {line}")
        suffix = "[" + field.group(3) + "]" if field.group(3) else ""
        fields.append((field.group(1), field.group(2) + suffix))
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
    validate_directives(text)
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
