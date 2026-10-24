"""Bounded mkdir guest evidence and independently reread ext4 metadata."""
import hashlib
import re
import subprocess

GROUP_ID = 0x87654321
MARKER = rb"OK_MUSL_MKDIR slot=([01]) mkdir=pass mkdirat=pass modes=offline inheritance=offline copies=pass dirfd=pass errors=pass readdir=pass\r?\n"


def creation_slots(serial):
    lines = [line for line in serial.splitlines(keepends=True) if line.startswith(b"OK_MUSL_MKDIR ")]
    matches = [re.fullmatch(MARKER, line) for line in lines]
    if len(matches) != 2 or not all(matches) or [int(match[1]) for match in matches] != [0, 1]:
        raise RuntimeError("mkdir evidence requires two ordered distinct complete creation slots")
    return [0, 1]


def expected_nodes():
    nodes = {"/home/musl-mkdir-sgid": ("directory", 0o2777, 0, GROUP_ID, 4, None)}
    for slot in (0, 1):
        plain = f"/home/musl-mkdir-{slot}"
        group = f"/home/musl-mkdir-sgid/run-{slot}"
        nodes[plain] = ("directory", 0o1750, 0, 0, 6, None)
        for name in ("child", "cwd", "legacy", "retained"):
            nodes[plain + "/" + name] = ("directory", 0o750, 0, 0, 2, None)
        nodes[plain + "/data"] = ("regular", 0o640, 0, 0, 1, b"created")
        nodes[group] = ("directory", 0o3750, 0, GROUP_ID, 3, None)
        nodes[group + "/nested"] = ("directory", 0o2750, 0, GROUP_ID, 2, None)
        nodes[group + "/data"] = ("regular", 0o640, 0, GROUP_ID, 1, b"group")
    return nodes


def check_metadata(text, expected):
    identity = re.search(r"^Inode:\s+(\d+)\s+Type:\s+(\w+)\s+Mode:\s+([0-7]+)\s", text, re.M)
    owner = re.search(r"^User:\s+(-?\d+)\s+Group:\s+(-?\d+)\s", text, re.M)
    links = re.search(r"^Links:\s+(\d+)\s", text, re.M)
    if not identity or not owner or not links:
        raise RuntimeError("mkdir offline inode record is incomplete")
    # debugfs 1.47 prints uint32 inode owners through signed decimal formatting.
    # Admit either presentation without truncating an out-of-range source value.
    owners = tuple(int(owner[index]) for index in (1, 2))
    if any(value < -(1 << 31) or value > (1 << 32) - 1 for value in owners):
        raise RuntimeError("mkdir offline inode owner exceeds 32 bits")
    actual = (identity[2], int(identity[3], 8), *(value & 0xffffffff for value in owners), int(links[1]))
    if actual != expected[:5] or int(identity[1]) <= 0:
        raise RuntimeError(f"mkdir offline metadata mismatch: expected {expected[:5]}, found {actual}")
    return int(identity[1])


def qualify_disk(disk, output):
    receipts = {}
    for index, (name, expected) in enumerate(expected_nodes().items()):
        result = subprocess.run(["debugfs", "-R", "stat " + name, str(disk)],
                                text=True, capture_output=True, check=True)
        log = output / f"mkdir-{index:02d}.stat.log"
        log.write_text(result.stdout + result.stderr)
        inode = check_metadata(result.stdout, expected)
        receipt = dict(inode=inode, type=expected[0], mode=expected[1], uid=expected[2],
                       gid=expected[3], links=expected[4], stat_file=log.name,
                       stat_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        if expected[5] is not None:
            result = subprocess.run(["debugfs", "-R", "cat " + name, str(disk)],
                                    capture_output=True, check=True)
            if result.stdout != expected[5]:
                raise RuntimeError("mkdir offline file contents differ: " + name)
            data = output / f"mkdir-{index:02d}.bin"
            data.write_bytes(result.stdout)
            receipt.update(data_file=data.name, data_sha256=hashlib.sha256(data.read_bytes()).hexdigest())
        receipts[name] = receipt
    if len({row["inode"] for row in receipts.values()}) != len(receipts):
        raise RuntimeError("mkdir output nodes unexpectedly alias")
    return receipts
