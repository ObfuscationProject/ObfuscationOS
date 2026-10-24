#!/usr/bin/env python3
"""Build a deterministic, directly mapped boot archive from the OS rootfs."""
import argparse
import hashlib
import stat
import struct
from pathlib import Path


def pack(root: Path) -> bytes:
    try:
        directory = stat.S_ISDIR(root.lstat().st_mode)
    except FileNotFoundError:
        directory = False
    if not directory:
        raise ValueError(f"archive root is not an existing directory: {root}")
    entries = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
    output = bytearray(struct.pack("<4sIII", b"OKAR", 1, len(entries), 0))
    for entry in entries:
        host_mode = entry.lstat().st_mode
        kind = stat.S_IFMT(host_mode)
        if kind not in (stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"unsupported archive entry: {entry}")
        permissions = 0o3777 if kind == stat.S_IFDIR else 0o777
        if host_mode & ~(kind | permissions):
            raise ValueError(f"unsupported archive permissions {host_mode:o}: {entry}")
        path = ("/" + entry.relative_to(root).as_posix()).encode("ascii")
        if len(path) >= 128 or any(len(p) >= 32 for p in path.split(b"/")):
            raise ValueError(f"archive path exceeds kernel limits: {entry}")
        contents = entry.read_bytes() if kind == stat.S_IFREG else b""
        # OKAR ownership is root-owned at import; host UID/GID are never encoded.
        # Preserve approved permissions exactly instead of silently masking them.
        mode = kind | (host_mode & permissions)
        output.extend(struct.pack("<IIII", len(path), len(contents), mode, 0))
        output.extend(path)
        output.extend(contents)
        output.extend(bytes((-len(output)) % 8))
    return bytes(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    blob = pack(args.root)
    if not args.out.exists() or args.out.read_bytes() != blob:
        args.out.write_bytes(blob)
    include = args.out.with_suffix(args.out.suffix + ".inc")
    assembly = f'// {hashlib.sha256(blob).hexdigest()}\n.incbin "{args.out.resolve()}"\n'
    if not include.exists() or include.read_text() != assembly:
        include.write_text(assembly)
    print(f"[boot archive] {len(blob)} bytes: {args.out}")
