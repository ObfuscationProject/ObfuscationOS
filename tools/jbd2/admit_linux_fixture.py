#!/usr/bin/env python3
"""Admit the exact Linux fixture's ext4 geometry and immutable journal extent.

This bounded offline test-fixture admission is not a general ext4 mount parser.
"""
from __future__ import annotations
import argparse
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import struct
import subprocess

STAGE = Path(__file__).resolve().parent
library = ctypes.CDLL(ctypes.util.find_library("ext2fs") or "libext2fs.so.2")
crc = library.ext2fs_crc32c_le
crc.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t]
crc.restype = ctypes.c_uint32


def checksum(seed, data):
    return crc(seed, bytes(data), len(data))


def le16(data, offset): return struct.unpack_from("<H", data, offset)[0]
def le32(data, offset): return struct.unpack_from("<I", data, offset)[0]
def be32(data, offset): return struct.unpack_from(">I", data, offset)[0]


def inspect(data, dirty):
    if len(data) != 32 * 1024 * 1024:
        raise ValueError("fixture must be the explicit 32 MiB raw filesystem")
    sb = data[1024:2048]
    if (le16(sb, 56), le32(sb, 24), le32(sb, 4), le32(sb, 20), le32(sb, 32), le32(sb, 40), le16(sb, 88)) != \
            (0xef53, 0, 32768, 1, 8192, 2048, 256):
        raise ValueError("unexpected ext4 fixture geometry")
    masks = [le32(sb, offset) for offset in (92, 96, 100)]
    if masks != [4, 0x46 if dirty else 0x42, 0x400] or le32(sb, 224) != 8 or le32(sb, 228) != 0:
        raise ValueError("unexpected feature masks or journal inode/device binding")
    if any(sb[208:224]) or le32(sb, 232) != 0 or sb[373] != 1:
        raise ValueError("external journal, classic orphan head or checksum algorithm outside fixture contract")
    if checksum(0xffffffff, sb[:1020]) != le32(sb, 1020):
        raise ValueError("ext4 superblock CRC32C")
    uuid = sb[104:120]
    seed = checksum(0xffffffff, uuid)
    ranges = []
    groups = []
    for group in range(4):
        descriptor = bytearray(data[2048 + group * 32:2048 + (group + 1) * 32])
        recorded = le16(descriptor, 30)
        descriptor[30:32] = b"\0\0"
        if checksum(checksum(seed, struct.pack("<I", group)), descriptor) & 0xffff != recorded:
            raise ValueError("ext4 group descriptor CRC32C")
        block_bitmap, inode_bitmap, table = struct.unpack_from("<III", descriptor)
        begin = 1 + group * 8192
        end = min(32768, begin + 8192)
        locations = [(begin, 2), (block_bitmap, 1), (inode_bitmap, 1), (table, 512)]
        for first, count in locations:
            if first < begin or first + count > end:
                raise ValueError("group metadata range outside its exact group")
        for index, (first, count) in enumerate(locations):
            if any(first < other + length and other < first + count for other, length in locations[index + 1:]):
                raise ValueError("overlapping group metadata ranges")
        ranges.extend(locations)
        groups.append({"block_bitmap": block_bitmap, "inode_bitmap": inode_bitmap, "table": table})

    def inode(number):
        group, local = divmod(number - 1, 2048)
        offset = groups[group]["table"] * 1024 + local * 256
        item = bytearray(data[offset:offset + 256])
        if le16(item, 128) != 32:
            raise ValueError("inode extra-isize outside exact fixture contract")
        recorded = le16(item, 124) | (le16(item, 130) << 16)
        item[124:126] = b"\0\0"; item[130:132] = b"\0\0"
        state = checksum(checksum(seed, struct.pack("<I", number)), item[100:104])
        if checksum(state, item) != recorded:
            raise ValueError("ext4 inode CRC32C")
        return data[offset:offset + 256], offset

    journal, journal_offset = inode(8)
    if le16(journal, 0) != 0o100600 or le32(journal, 4) != 4 * 1024 * 1024 or le32(journal, 108) != 0 or \
            le32(journal, 32) != 0x80000 or le32(journal, 104) != 0:
        raise ValueError("journal inode identity, size, ACL or flags")
    extent = journal[40:100]
    if tuple(le16(extent, offset) for offset in (0, 2, 4, 6)) != (0xf30a, 1, 4, 0) or \
            le32(extent, 12) != 0 or le16(extent, 16) != 4096 or le16(extent, 18) != 0:
        raise ValueError("journal must have one initialized inline 4096-block extent")
    first = le32(extent, 20)
    if first + 4096 > 32768 or any(first < start + count and start < first + 4096 for start, count in ranges):
        raise ValueError("journal extent overlaps validated metadata")
    journal_sb = data[first * 1024:(first + 1) * 1024]
    if be32(journal_sb, 0) != 0xc03b3998 or be32(journal_sb, 12) != 1024 or be32(journal_sb, 16) != 4096 or \
            journal_sb[48:64] != uuid:
        raise ValueError("JBD2 geometry/UUID binding")
    if dirty and (be32(journal_sb, 28) == 0 or be32(journal_sb, 40) not in (16, 17)):
        raise ValueError("Linux capture needs a nonempty checksum-v3 journal with at most the revoke bit")
    seeded, seed_offset = inode(12)
    if le16(seeded, 0) != 0o100644 or le16(seeded, 2) != 0 or le16(seeded, 24) != 0 or le32(seeded, 4) != 4096:
        raise ValueError("home inode was checkpointed or differs from clean seeded identity")
    return {"uuid": uuid.hex(), "filesystem_blocks": 32768, "block_size": 1024, "feature_masks": masks,
            "journal_first": first, "journal_blocks": 4096, "journal_inode_sha256": hashlib.sha256(journal).hexdigest(),
            "journal_inode_offset": journal_offset, "journal_features": be32(journal_sb, 40),
            "journal_sequence": be32(journal_sb, 24), "journal_start": be32(journal_sb, 28),
            "metadata_ranges": ranges, "seed_inode": 12, "seed_block": seed_offset // 1024,
            "seed_offset": seed_offset % 1024, "seed_inode_sha256": hashlib.sha256(seeded).hexdigest()}


def header_for(facts):
    header = "#pragma once\nnamespace fixture {\nusing namespace ok;\nusing namespace ok::fs::jbd2;\n"
    header += f'inline constexpr RecoveryLayout layout{{0, 32768, {facts["journal_first"]}, 4096, 1024}};\n'
    header += "inline constexpr std::array<u8,16> uuid{" + ",".join(str(byte) for byte in bytes.fromhex(facts["uuid"])) + "};\n"
    header += f'inline constexpr std::array<BlockRange,{len(facts["metadata_ranges"])}> ranges{{{{'
    header += ",".join("{" + str(first) + "," + str(count) + "}" for first, count in facts["metadata_ranges"]) + "}};\n"
    header += f'inline constexpr u64 seed_block = {facts["seed_block"]};\ninline constexpr usize seed_offset = {facts["seed_offset"]};\n'
    header += "}\n"
    return header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    root = args.fixture.resolve()
    manifest = json.loads((root / "capture-manifest.json").read_text())
    before = (root / "baseline-clean.img").read_bytes()
    captured = (root / "linux-dirty-capture.img").read_bytes()
    if hashlib.sha256(before).hexdigest() != manifest["baseline_sha256"] or \
            hashlib.sha256(captured).hexdigest() != manifest["capture_sha256"]:
        raise ValueError("fixture identity changed")
    baseline = inspect(before, False)
    facts = inspect(captured, True)
    for key in ("uuid", "journal_first", "journal_blocks", "journal_inode_sha256", "metadata_ranges", "seed_inode_sha256"):
        if facts[key] != baseline[key]: raise ValueError("immutable mapping/identity changed: " + key)
    (root / "admission.json").write_text(json.dumps(facts, indent=2) + "\n")
    header = header_for(facts)
    (root / "linux_fixture.hpp").write_text(header)
    print(json.dumps(facts, indent=2))


if __name__ == "__main__": main()
