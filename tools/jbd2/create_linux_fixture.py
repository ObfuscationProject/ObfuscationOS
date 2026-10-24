#!/usr/bin/env python3
"""Create one explicitly disposable ext4 journal through an existing Linux guest."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from native_support import boot

STAGE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpio(entries):
    output = bytearray()
    for inode, (name, mode, content, major, minor) in enumerate(entries + [("TRAILER!!!", 0, b"", 0, 0)], 1):
        encoded = name.encode() + b"\0"
        values = (inode, mode, 0, 0, 2 if mode & 0o040000 else 1, 0, len(content), 0, 0, major, minor, len(encoded), 0)
        output.extend(b"070701" + b"".join(f"{value:08x}".encode() for value in values) + encoded)
        output.extend(bytes((-len(output)) % 4))
        output.extend(content)
        output.extend(bytes((-len(output)) % 4))
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux-image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    kernel = out / "linux-bzImage"
    shutil.copyfile(args.linux_image.resolve(), kernel)
    init = out / "init"
    init_source = out / "fixture_init.c"
    init_source.write_bytes((STAGE.parents[1] / "tests/linux/jbd2_fixture_init.c").read_bytes())
    (out / "create_linux_fixture.py").write_bytes(Path(__file__).read_bytes())
    (out / "native_support.py").write_bytes((STAGE / "native_support.py").read_bytes())
    commands = [["gcc", "-static", "-O2", "-Wall", "-Wextra", "-Werror", str(init_source), "-o", str(init)]]
    subprocess.run(commands[-1], check=True)
    entries = [(name, 0o040755, b"", 0, 0) for name in ("dev", "proc", "sys", "mnt")]
    entries += [("dev/console", 0o020600, b"", 5, 1), ("init", 0o100755, init.read_bytes(), 0, 0)]
    initrd = out / "initramfs.cpio"
    initrd.write_bytes(cpio(entries))
    baseline = out / "baseline-clean.img"
    with baseline.open("xb") as output:
        output.truncate(32 * 1024 * 1024)
    command = ["mke2fs", "-F", "-t", "ext4", "-b", "1024", "-I", "256", "-O",
               "none,has_journal,extents,filetype,metadata_csum", "-J", "size=4", "-E",
               "lazy_itable_init=0,lazy_journal_init=0", "-U", "f2026092-0000-4000-8000-000000000001", str(baseline)]
    commands.append(command)
    formatted = subprocess.run(command, check=True, capture_output=True, text=True)
    (out / "mke2fs.log").write_text(formatted.stdout + formatted.stderr)
    seed = out / "seed.bin"
    seed.write_bytes(bytes((index * 17 + 29) & 255 for index in range(4096)))
    debug = out / "seed.debugfs"
    debug.write_text("write seed.bin /seed\nset_inode_field /seed mode 0100644\nset_inode_field /seed uid 0\nset_inode_field /seed gid 0\n")
    command = ["debugfs", "-w", "-f", str(debug), str(baseline)]
    commands.append(command)
    seeded = subprocess.run(command, check=True, capture_output=True, text=True, cwd=out)
    (out / "debugfs-seed.log").write_text(seeded.stdout + seeded.stderr)
    command = ["e2fsck", "-fn", str(baseline)]
    commands.append(command)
    checked = subprocess.run(command, check=True, capture_output=True, text=True)
    (out / "baseline-e2fsck.log").write_text(checked.stdout + checked.stderr)
    for request, name in [("stats", "baseline-stats"), ("stat <8>", "baseline-journal"), ("blocks <8>", "baseline-journal-blocks"),
                          ("stat /seed", "baseline-seed")]:
        result = subprocess.run(["debugfs", "-R", request, str(baseline)], check=True, capture_output=True, text=True)
        (out / (name + ".log")).write_text(result.stdout + result.stderr)
    captured = out / "linux-dirty-capture.img"
    shutil.copyfile(baseline, captured)
    command = ["qemu-system-x86_64", "-m", "512M", "-kernel", str(kernel), "-initrd", str(initrd),
               "-append", "console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr", "-drive",
               f"file={captured},format=raw,if=none,id=fixture,cache=writeback", "-device", "virtio-blk-pci,drive=fixture"]
    commands.append(command.copy())
    # boot() only terminates the child it started; no host mounts or loop devices.
    boot(command, "LINUX_JBD2_FIXTURE_COMMITTED", out / "linux-capture.log")
    commands[-1] = command.copy()
    for request, name in [("stats", "capture-stats"), ("stat <8>", "capture-journal"), ("stat /seed", "capture-seed")]:
        result = subprocess.run(["debugfs", "-R", request, str(captured)], check=True, capture_output=True, text=True)
        (out / (name + ".log")).write_text(result.stdout + result.stderr)
    manifest = {
        "kind": "linux-guest-created-dirty-journal", "linux_image_sha256": sha(kernel),
        "linux_image_source_path": str(args.linux_image.resolve()), "linux_source_provenance": "not-established",
        "guest_version_log": "linux-capture.log", "baseline_sha256": sha(baseline), "capture_sha256": sha(captured),
        "init_sha256": sha(init), "initramfs_sha256": sha(initrd), "seed_sha256": sha(seed),
        "e2fsprogs": subprocess.check_output(["mke2fs", "-V"], stderr=subprocess.STDOUT, text=True).strip(),
        "commands": commands, "host_mounts": False, "checkpoint_support_claim": False,
        "debugfs_seed_working_directory": str(out),
        "source_sha256": {name: sha(out / name) for name in ("fixture_init.c", "create_linux_fixture.py", "native_support.py")},
    }
    (out / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS Linux-created fixture capture " + str(out / "capture-manifest.json"))


if __name__ == "__main__":
    main()
