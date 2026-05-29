#!/usr/bin/env python3
import argparse
import os
import shutil
import struct
from pathlib import Path


MAGIC = 0x53464B4F
VERSION = 1
BLOCK_SIZE = 512
MAX_ENTRIES = 32
ENTRY_SIZE = 64
TABLE_BLOCKS = 4
DATA_START_BLOCK = 1 + TABLE_BLOCKS
NAME_CAPACITY = 32
LABEL_CAPACITY = 17

SUPERBLOCK_STRUCT = struct.Struct("<IHHQII")
ENTRY_STRUCT = struct.Struct("<BBHIII32sIIII")

NODE_DIRECTORY = 0
NODE_REGULAR = 1
MODE_REGULAR = 0o100000
MODE_DIRECTORY = 0o040000


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def blocks_for_size(size: int) -> int:
    return (size + BLOCK_SIZE - 1) // BLOCK_SIZE


def flat_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 2 and parts[0] in {"bin", "etc"}:
        return parts[-1]
    if len(parts) >= 3 and parts[0] == "boot" and parts[1] == "modules" and parts[2] == "apps":
        return f"apps_{parts[-1]}"
    if len(parts) >= 2 and parts[0] == "boot" and parts[1] == "modules":
        return parts[-1]
    return "_".join(parts)


def collect_files(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for dirpath, _, filenames in os.walk(root):
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            name = flat_name(root, path)
            if len(name.encode("utf-8")) >= NAME_CAPACITY:
                raise SystemExit(f"SimpleFS flat name too long: {name}")
            if name in seen:
                raise SystemExit(f"SimpleFS flat name collision: {name}")
            seen.add(name)
            files.append((name, path))
    files.sort(key=lambda item: item[0])
    if len(files) > MAX_ENTRIES:
        raise SystemExit(f"SimpleFS supports at most {MAX_ENTRIES} entries, got {len(files)}")
    return files


def pack_name(name: str, capacity: int) -> bytes:
    raw = name.encode("utf-8")
    if len(raw) >= capacity:
        raise SystemExit(f"SimpleFS name too long: {name}")
    return raw + b"\0" * (capacity - len(raw))


def make_superblock(file_count: int, block_count: int, label: str) -> bytes:
    block = bytearray(BLOCK_SIZE)
    block[: SUPERBLOCK_STRUCT.size] = SUPERBLOCK_STRUCT.pack(
        MAGIC,
        VERSION,
        BLOCK_SIZE,
        block_count,
        file_count,
        DATA_START_BLOCK,
    )
    block[24 : 24 + LABEL_CAPACITY] = pack_name(label, LABEL_CAPACITY)
    return bytes(block)


def make_entry(name: str, start_block: int, payload_size: int) -> bytes:
    block_count = blocks_for_size(payload_size)
    mode = MODE_REGULAR | 0o755
    return ENTRY_STRUCT.pack(
        1,
        NODE_REGULAR,
        0,
        payload_size,
        start_block,
        block_count,
        pack_name(name, NAME_CAPACITY),
        mode,
        0,
        0,
        1,
    )


def pack(root: Path, out: Path) -> None:
    files = collect_files(root)
    entries: list[bytes] = []
    data = bytearray()
    current_block = DATA_START_BLOCK

    for name, path in files:
        payload = path.read_bytes()
        entries.append(make_entry(name, current_block, len(payload)))
        data.extend(payload)
        data.extend(b"\0" * (align_up(len(data), BLOCK_SIZE) - len(data)))
        current_block = DATA_START_BLOCK + len(data) // BLOCK_SIZE

    while len(entries) < MAX_ENTRIES:
        entries.append(b"\0" * ENTRY_SIZE)

    directory = b"".join(entries)
    directory += b"\0" * (TABLE_BLOCKS * BLOCK_SIZE - len(directory))
    block_count = DATA_START_BLOCK + len(data) // BLOCK_SIZE
    image = make_superblock(len(files), block_count, "ObfuscationOS") + directory + data

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(image)
    print(f"[simplefs] wrote {out} ({len(files)} entries, {block_count} blocks)")


def unpack_name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8")


def read_image(image: Path) -> tuple[list[tuple[str, int, int]], bytes]:
    blob = image.read_bytes()
    if len(blob) < DATA_START_BLOCK * BLOCK_SIZE:
        raise SystemExit("image too small")
    magic, version, block_size, block_count, entry_count, data_start = SUPERBLOCK_STRUCT.unpack(
        blob[: SUPERBLOCK_STRUCT.size]
    )
    if magic != MAGIC or version != VERSION or block_size != BLOCK_SIZE or data_start != DATA_START_BLOCK:
        raise SystemExit("invalid SimpleFS header")
    if entry_count > MAX_ENTRIES:
        raise SystemExit("invalid SimpleFS entry count")
    if block_count * BLOCK_SIZE > len(blob):
        raise SystemExit("invalid SimpleFS block count")

    entries: list[tuple[str, int, int]] = []
    directory = blob[BLOCK_SIZE : DATA_START_BLOCK * BLOCK_SIZE]
    for i in range(MAX_ENTRIES):
        offset = i * ENTRY_SIZE
        used, node_type, _, size, start_block, block_count, raw_name, _, _, _, _ = ENTRY_STRUCT.unpack(
            directory[offset : offset + ENTRY_SIZE]
        )
        if not used:
            continue
        name = unpack_name(raw_name)
        start = start_block * BLOCK_SIZE
        end = start + size
        if node_type != NODE_REGULAR or not name or start < DATA_START_BLOCK * BLOCK_SIZE or end > len(blob):
            raise SystemExit(f"invalid SimpleFS entry {i}")
        expected_end = (start_block + block_count) * BLOCK_SIZE
        if expected_end > len(blob):
            raise SystemExit(f"invalid SimpleFS extent {i}")
        entries.append((name, start, size))
    if len(entries) != entry_count:
        raise SystemExit(f"SimpleFS superblock count mismatch: {entry_count} != {len(entries)}")
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
