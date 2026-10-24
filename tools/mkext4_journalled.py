#!/usr/bin/env python3
"""Create the selected Linux-activated 1 KiB journalled ext4 startup image."""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from journalled_rootfs_policy import normalize as normalize_journalled_bootstrap_root


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def journal_first_block(image: Path) -> int:
    with image.open("rb") as stream:
        stream.seek(1024)
        superblock = stream.read(1024)
        if (struct.unpack_from("<H", superblock, 56)[0] != 0xef53 or
                struct.unpack_from("<I", superblock, 24)[0] != 0 or
                struct.unpack_from("<I", superblock, 4)[0] != 32768):
            raise ValueError("journal root geometry differs from selected 32 MiB profile")
        stream.seek(2048 + 8)
        inode_table = int.from_bytes(stream.read(4), "little")
        stream.seek(inode_table * 1024 + 7 * 256)
        inode = stream.read(256)
    if (len(inode) != 256 or struct.unpack_from("<H", inode, 0)[0] != 0o100600 or
            struct.unpack_from("<I", inode, 4)[0] != 4 * 1024 * 1024 or
            struct.unpack_from("<HHHH", inode, 40) != (0xf30a, 1, 4, 0) or
            struct.unpack_from("<IHH", inode, 52) != (0, 4096, 0)):
        raise ValueError("journal inode is not one initialized inline extent")
    first = struct.unpack_from("<I", inode, 60)[0]
    if first < 1 or first + 4096 > 32768:
        raise ValueError("journal extent is outside selected filesystem")
    return first


def cpio(entries: list[tuple[str, int, bytes, int, int]]) -> bytes:
    output = bytearray()
    for inode, (name, mode, content, major, minor) in enumerate(
            entries + [("TRAILER!!!", 0, b"", 0, 0)], 1):
        encoded = name.encode() + b"\0"
        values = (inode, mode, 0, 0, 2 if mode & 0o040000 else 1, 0,
                  len(content), 0, 0, major, minor, len(encoded), 0)
        output.extend(b"070701" + b"".join(f"{value:08x}".encode() for value in values) + encoded)
        output.extend(bytes((-len(output)) % 4))
        output.extend(content)
        output.extend(bytes((-len(output)) % 4))
    return bytes(output)


def require(program: str) -> str:
    found = shutil.which(program)
    if not found:
        raise SystemExit(f"required program not found: {program}")
    return found


def create_activation_marker(staged_root: Path) -> None:
    marker = staged_root / ".journal-profile"
    try:
        # Exclusive creation also refuses dangling links. Testing exists()
        # first would follow such a link when writing the marker afterwards.
        with marker.open("xb") as stream:
            stream.write(b"linux journal activation marker\n")
            os.fchmod(stream.fileno(), 0o644)
    except FileExistsError as error:
        raise ValueError("rootfs already contains the journal activation marker") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--size", default="32M")
    parser.add_argument("--console-login", action="store_true",
                        help="Bind the ordinary console product for later persisted-disk admission")
    parser.add_argument("--linux-image", type=Path, required=True,
                        help="Explicit Linux x86_64 reference kernel for journal activation")
    parser.add_argument("--linux-image-sha256", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    selected_output = Path(args.out).absolute()
    if selected_output.is_symlink():
        raise SystemExit("journalled image output must not be a symlink")
    out = selected_output.resolve()
    if not root.is_dir():
        raise SystemExit(f"root must be an existing directory: {root}")
    console_product = None
    if args.console_login:
        from console_login_disk import product
        console_product = product(root)
    outputs = (out, out.with_name(out.name + ".activation.log"),
               out.with_name(out.name + ".manifest.json"))
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise SystemExit("journalled image or evidence already exists; select a fresh output to preserve accounts")
    mke2fs = require("mke2fs")
    e2fsck = require("e2fsck")
    debugfs = require("debugfs")
    gcc = require("gcc")
    qemu = require("qemu-system-x86_64")
    linux_image = args.linux_image.resolve()
    if not linux_image.is_file() or sha(linux_image) != args.linux_image_sha256:
        raise SystemExit("Linux reference image does not match its explicit SHA-256 pin")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ext4-journalled-", dir=out.parent) as directory:
        stage = Path(directory)
        image = stage / "rootfs.img"
        staged_root = stage / "rootfs"
        shutil.copytree(root, staged_root, symlinks=True)
        create_activation_marker(staged_root)
        from journalled_dense_files import (prepare as prepare_dense, restore as restore_dense,
                                           validate_initialized_inline)
        dense_plan = prepare_dense(staged_root)
        subprocess.check_call([
            mke2fs, "-q", "-t", "ext4", "-b", "1024", "-I", "256",
            "-O", "none,has_journal,extents,filetype,metadata_csum",
            "-J", "size=4", "-E", "lazy_itable_init=0,lazy_journal_init=0",
            "-L", "ObfuscationOS", "-m", "0", "-d", str(staged_root),
            str(image), args.size,
        ])
        dense_files = restore_dense(Path(debugfs), image, staged_root, stage, dense_plan)
        bootstrap_metadata = normalize_journalled_bootstrap_root(Path(debugfs), image, staged_root, stage)
        # Host UID/GID and umask are staging details. libext2fs updates inode
        # checksums, then the ordinary offline checker validates the image.
        subprocess.check_call([e2fsck, "-fn", str(image)])
        source = Path(__file__).resolve().parent / "jbd2/activate_root_journal.c"
        init = stage / "init"
        subprocess.run([gcc, "-static", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(init)], check=True)
        archive = stage / "initramfs.cpio"
        archive.write_bytes(cpio([
            ("dev", 0o040755, b"", 0, 0), ("mnt", 0o040755, b"", 0, 0),
            ("dev/console", 0o020600, b"", 5, 1),
            ("init", 0o100755, init.read_bytes(), 0, 0),
        ]))
        command = [qemu, "-m", "512M", "-kernel", str(linux_image), "-initrd", str(archive),
                   "-append", "console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr",
                   "-drive", f"file={image},format=raw,if=none,id=journal,cache=writeback",
                   "-device", "virtio-blk-pci,drive=journal"]
        import sys
        sys.path.insert(0, str(source.parent))
        from native_support import boot
        from admit_linux_fixture import checksum
        activation_log = stage / "activation.log"
        boot(command, "LINUX_JOURNAL_ACTIVATED clean=1 checksum=v3", activation_log)
        subprocess.check_call([e2fsck, "-fn", str(image)])
        journal = stage / "journal.bin"
        subprocess.run([debugfs, "-R", f"dump <8> {journal}", str(image)], check=True,
                       stdout=subprocess.DEVNULL)
        header = journal.read_bytes()[:1024]
        features = int.from_bytes(header[40:44], "big")
        start = int.from_bytes(header[28:32], "big")
        head = int.from_bytes(header[88:92], "big")
        with image.open("rb") as stream:
            stream.seek(1024 + 96)
            incompat = int.from_bytes(stream.read(4), "little")
        if features != 16 or header[80] != 4 or start != 0 or incompat & 4:
            raise ValueError(f"Linux did not produce the selected clean CRC32C v3 journal: "
                             f"features={features} checksum_type={header[80]} "
                             f"start={start} head={head} recovery={bool(incompat & 4)}")
        first = journal_first_block(image)
        with image.open("r+b") as stream:
            stream.seek(first * 1024)
            if stream.read(1024) != header:
                raise ValueError("debugfs journal and raw extent disagree")
            normalized = bytearray(header)
            normalized[88:92] = bytes(4)
            normalized[252:256] = bytes(4)
            normalized[252:256] = checksum(0xffffffff, normalized).to_bytes(4, "big")
            stream.seek(first * 1024)
            stream.write(normalized)
        inline_files = validate_initialized_inline(Path(debugfs), image, staged_root)
        subprocess.check_call([e2fsck, "-fn", str(image)])
        if console_product is not None:
            from console_login_disk import initial_seed
            initial_seed(image, debugfs)
        manifest = {"schema": 1, "profile": "linux-activated-clean-1k-jbd2-crc32c-v3-normalized-head",
                    "image_sha256": sha(image), "linux_image_sha256": sha(linux_image),
                    "activation_source_sha256": sha(source), "activation_log_sha256": sha(activation_log),
                    "journal_features": 16, "journal_start": start,
                    "linux_journal_head": head, "normalized_journal_head": 0,
                    "journal_first_block": first, "needs_recovery": False,
                    "bootstrap_metadata": bootstrap_metadata,
                    "dense_files": dense_files,
                    "initialized_inline_regular_files": inline_files,
                    "dense_files_policy_source_sha256": sha(Path(__file__).with_name("journalled_dense_files.py")),
                    "bootstrap_metadata_policy_source_sha256": sha(Path(__file__).with_name("journalled_rootfs_policy.py"))}
        manifest_path = stage / "manifest.json"
        if console_product is not None:
            manifest["console_login"] = console_product
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        # Same-filesystem hard links publish without replacing a disk or an
        # evidence file created during activation. Partial publication is kept.
        for original, destination in zip((image, activation_log, manifest_path), outputs):
            os.link(original, destination, follow_symlinks=False)
    print(f"[ext4] wrote selected journalled profile {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
