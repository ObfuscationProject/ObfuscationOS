#!/usr/bin/env python3
import argparse
import os
import shutil
import struct
from pathlib import Path


MAGIC = b"OKSFS1\0\0"
VERSION = 1
BLOCK_SIZE = 512
MAX_ENTRIES = 32
HEADER_STRUCT = struct.Struct("<8sIIII488s")
ENTRY_STRUCT = struct.Struct("<56sII")
DIR_BLOCKS = (MAX_ENTRIES * ENTRY_STRUCT.size + BLOCK_SIZE - 1) // BLOCK_SIZE
DATA_START_BLOCK = 1 + DIR_BLOCKS


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def flat_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 2 and parts[0] in {"bin", "etc"}:
        return parts[-1]
    return "_".join(parts)


def collect_files(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for dirpath, _, filenames in os.walk(root):
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            name = flat_name(root, path)
            if len(name.encode("utf-8")) > 55:
                raise SystemExit(f"SimpleFS flat name too long: {name}")
            if name in seen:
                raise SystemExit(f"SimpleFS flat name collision: {name}")
            seen.add(name)
            files.append((name, path))
    files.sort(key=lambda item: item[0])
    if len(files) > MAX_ENTRIES:
        raise SystemExit(f"SimpleFS supports at most {MAX_ENTRIES} entries, got {len(files)}")
    return files


def pack(root: Path, out: Path) -> None:
    files = collect_files(root)
    entries: list[bytes] = []
    data = bytearray()
    current_block = DATA_START_BLOCK

    for name, path in files:
        payload = path.read_bytes()
        offset_block = current_block
        entries.append(ENTRY_STRUCT.pack(name.encode("utf-8"), offset_block, len(payload)))
        data.extend(payload)
        padding = align_up(len(data), BLOCK_SIZE) - len(data)
        if padding:
            data.extend(b"\0" * padding)
        current_block = DATA_START_BLOCK + len(data) // BLOCK_SIZE

    while len(entries) < MAX_ENTRIES:
        entries.append(ENTRY_STRUCT.pack(b"", 0, 0))

    header = HEADER_STRUCT.pack(MAGIC, VERSION, BLOCK_SIZE, len(files), DATA_START_BLOCK, b"")
    directory = b"".join(entries)
    directory += b"\0" * (DIR_BLOCKS * BLOCK_SIZE - len(directory))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(header + directory + data)
    print(f"[simplefs] wrote {out} ({len(files)} entries)")


def read_image(image: Path) -> tuple[list[tuple[str, int, int]], bytes]:
    blob = image.read_bytes()
    if len(blob) < DATA_START_BLOCK * BLOCK_SIZE:
        raise SystemExit("image too small")
    magic, version, block_size, entry_count, data_start, _ = HEADER_STRUCT.unpack(blob[:BLOCK_SIZE])
    if magic != MAGIC or version != VERSION or block_size != BLOCK_SIZE or data_start != DATA_START_BLOCK:
        raise SystemExit("invalid SimpleFS header")
    if entry_count > MAX_ENTRIES:
        raise SystemExit("invalid SimpleFS entry count")

    entries: list[tuple[str, int, int]] = []
    directory = blob[BLOCK_SIZE : DATA_START_BLOCK * BLOCK_SIZE]
    for i in range(entry_count):
        raw_name, offset_block, size = ENTRY_STRUCT.unpack(
            directory[i * ENTRY_STRUCT.size : (i + 1) * ENTRY_STRUCT.size]
        )
        name = raw_name.split(b"\0", 1)[0].decode("utf-8")
        start = offset_block * BLOCK_SIZE
        end = start + size
        if not name or start < DATA_START_BLOCK * BLOCK_SIZE or end > len(blob):
            raise SystemExit(f"invalid SimpleFS entry {i}")
        entries.append((name, start, size))
    return entries, blob


def list_image(image: Path) -> None:
    entries, _ = read_image(image)
    for name, _, size in entries:
        print(f"{name}\t{size}")


def verify(image: Path, root: Path | None) -> None:
    entries, blob = read_image(image)
    if root is None:
        print(f"[simplefs] verified {image} ({len(entries)} entries)")
        return

    expected = {name: path.read_bytes() for name, path in collect_files(root)}
    actual = {name: blob[start : start + size] for name, start, size in entries}
    if expected != actual:
        raise SystemExit("SimpleFS roundtrip mismatch")
    print(f"[simplefs] roundtrip OK: {image}")


def extract(image: Path, out: Path) -> None:
    entries, blob = read_image(image)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name, start, size in entries:
        (out / name).write_bytes(blob[start : start + size])
    print(f"[simplefs] extracted {len(entries)} entries to {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    pack_parser = sub.add_parser("pack")
    pack_parser.add_argument("--root", required=True)
    pack_parser.add_argument("--out", required=True)

    ls_parser = sub.add_parser("ls")
    ls_parser.add_argument("image")

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("image")
    verify_parser.add_argument("--root")

    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("image")
    extract_parser.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.cmd == "pack":
        pack(Path(args.root), Path(args.out))
    elif args.cmd == "ls":
        list_image(Path(args.image))
    elif args.cmd == "verify":
        verify(Path(args.image), Path(args.root) if args.root else None)
    elif args.cmd == "extract":
        extract(Path(args.image), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
