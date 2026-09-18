#!/usr/bin/env python3
"""Build a deterministic, directly mapped boot archive from the OS rootfs."""
import argparse
import hashlib
import struct
from pathlib import Path


def pack(root: Path) -> bytes:
    if not root.is_dir():
        raise ValueError(f"archive root is not an existing directory: {root}")
    entries = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
    output = bytearray(struct.pack("<4sIII", b"OKAR", 1, len(entries), 0))
    for entry in entries:
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise ValueError(f"unsupported archive entry: {entry}")
        path = ("/" + entry.relative_to(root).as_posix()).encode("ascii")
        if len(path) >= 128 or any(len(p) >= 32 for p in path.split(b"/")):
            raise ValueError(f"archive path exceeds kernel limits: {entry}")
        contents = entry.read_bytes() if entry.is_file() else b""
        mode = (0o100000 if entry.is_file() else 0o040000) | (entry.stat().st_mode & 0o777)
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
