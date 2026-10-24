"""Synthetic parser controls only; these tests do not execute a native guest."""
import copy
import unittest

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/jbd2"))
from journalled_directory_mode_cut_protocol import validate_cut


FACTS = dict(block_size=1024, feature_masks=[4, 0x42, 0x400], journal_start=0,
             origin=11, filesystem_blocks=32768, sectors=65536, journal_first=8709,
             journal_blocks=4096, nodes={"child": dict(inode=14, block=8, mode=0o40755,
                                                     uid=1000, gid=1000, version=2)})
# Literal sectors independently copied from the admitted first transaction.
SECTORS = (None, 17431, 17433, 17435, 17439, None, 17437, None, 13, None,
           17429, None, None, 13, 27, None, 17429, None, 13, None)
INODE = b"JDMODE_INODE io=15 inode=14 mode=17896 uid=1000 gid=1000 ctime_sec=1700000000 ctime_nsec=123456789 version=3"
HEADER = [
    b"JDMODE_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1 uid=1000 clock=in-range",
    b"OK_NATIVE_MEMORY stage=prepare source=firmware status=pass image_begin=0x0000000000100000 image_end=0x0000000002000000 limit=1024",
    b"JDMODE_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive clock=administrator-software",
    b"",
    b"OK_NATIVE_IMAGE personality=linux source=firmware pages=21 physical_first=0x0000000002000000 physical_last=0x0000000002014000 owner=retained",
    b"OK_NATIVE scope=hardware init=loaded",
    b"JDMODE_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1 personality=linux",
    b"OK_NATIVE scope=hardware timer=preempted",
    b"JDMODE_USER_BEGIN uid=1000 sdk=31 scope=actual-musl-syscalls",
    b"JDMODE_OP_BEGIN ordinal=1 name=chmod",
]


def sample(cut, arch="x86_64", crlf=False, terminated=False):
    lines = [line.replace(b"source=firmware", b"source=linker") if arch == "mips" else line for line in HEADER]
    writes = 0
    for ordinal, sector in enumerate(SECTORS[:cut], 1):
        if sector is None:
            lines.append(f"JDMODE_IO ordinal={ordinal} kind=flush sector=0 bytes=0 crc32c=0 status=0".encode())
        else:
            writes += 1
            lines.append(f"JDMODE_IO ordinal={ordinal} kind=write sector={sector} bytes=1024 crc32c={ordinal * 1000} status=0".encode())
        if ordinal == 15:
            lines.append(INODE)
    lines.append(f"JDMODE_CUT ordinal={cut} writes={writes} flushes={cut-writes}".encode())
    if terminated:
        lines.append(f"qemu-system-{arch}: terminating on signal 15 from pid 1234 (/usr/bin/python3.11)".encode())
    return (b"\r\n" if crlf else b"\n").join(lines) + (b"\r\n" if crlf else b"\n")


class CutEvidenceTests(unittest.TestCase):
    accepted = 0
    rejected = 0

    def accept(self, serial, cut, arch="x86_64", facts=None):
        result = validate_cut(serial, cut, arch, FACTS if facts is None else facts)
        type(self).accepted += 1
        return result

    def reject(self, serial, cut=20, arch="x86_64", facts=None):
        with self.assertRaises(ValueError):
            validate_cut(serial, cut, arch, FACTS if facts is None else facts)
        type(self).rejected += 1

    def test_every_cut_architecture_and_line_ending(self):
        for arch in ("x86_64", "i386", "mips"):
            for cut in range(1, 21):
                for crlf in (False, True):
                    for terminated in (False, True):
                        with self.subTest(arch=arch, cut=cut, crlf=crlf, terminated=terminated):
                            result = self.accept(sample(cut, arch, crlf, terminated), cut, arch)
                            self.assertEqual(result["writes"], sum(s is not None for s in SECTORS[:cut]))
                            self.assertEqual(result["writes"] + result["flushes"], cut)
                            self.assertEqual(len(result["io"]), cut)
                            self.assertEqual(result["inode"] is not None, cut >= 15)
                            self.assertFalse(result["operation"]["completed"])
                            self.assertFalse(result["disk_oracle_checked"])
                            self.assertFalse(result["native_execution_verified"])

    def test_every_cut_rejects_missing_duplicate_wrong_and_late_records(self):
        for arch in ("x86_64", "i386", "mips"):
            for cut in range(1, 21):
                data = sample(cut, arch)
                lines = data.splitlines(keepends=True)
                selected = next(line for line in lines if line.startswith(f"JDMODE_IO ordinal={cut} ".encode()))
                marker = lines[-1]
                variants = [data.replace(selected, b"", 1), data.replace(selected, selected * 2, 1),
                            data.replace(selected, selected.replace(b"status=0", b"status=1"), 1),
                            data.replace(selected, selected.replace(b"ordinal=", b"ordinal=0"), 1),
                            data.replace(selected, b"prefix " + selected, 1),
                            data.replace(selected, selected.rstrip(b"\n") + b" junk\n", 1),
                            data.replace(marker, b""), data + marker, data[:-1],
                            data.replace(marker, marker.replace(b"writes=", b"writes=9")),
                            data + selected, data + b"JDMODE_OP_END ordinal=1 mutation=1\n",
                            data + b"JDMODE_USER_PASS uid=1000 operations=11 checks=100\n",
                            data + b"JDMODE_FIXTURE_PASS uid=1000 exit=0 reaped=1 personality=linux epoch=6 writes=55 flushes=47\n",
                            data + b"unknown late output\n", data + b"\n",
                            data.replace(marker, b"noise\n" + marker), data + b"JDMODE_CUT ordinal=",
                            data.replace(selected, selected.replace(b"sector=", b"sector=9"), 1)]
                for index, changed in enumerate(variants):
                    with self.subTest(arch=arch, cut=cut, mutation=index):
                        self.reject(changed, cut, arch)

    def test_each_completed_call_is_owned_and_successful(self):
        data = sample(20)
        for line in data.splitlines(keepends=True):
            if not line.startswith(b"JDMODE_IO "):
                continue
            for changed_line in (line.replace(b"status=0", b"status=2"),
                                 line.replace(b"bytes=", b"bytes=1"),
                                 line.replace(b"kind=flush", b"kind=write") if b"kind=flush" in line
                                 else line.replace(b"kind=write", b"kind=flush")):
                self.reject(data.replace(line, changed_line, 1))

    def test_crc_domain_without_claiming_disk_oracle(self):
        data = sample(20)
        for value in (b"0", b"4294967295"):
            result = self.accept(data.replace(b"crc32c=2000", b"crc32c=" + value), 20)
            self.assertEqual(result["io"][1]["crc32c"], int(value))
            self.assertFalse(result["disk_oracle_checked"])
        for value in (b"4294967296", b"-1", b"00", b"18446744073709551616", b"9" * 100):
            self.reject(data.replace(b"crc32c=2000", b"crc32c=" + value))
        self.reject(data.replace(b"crc32c=0 status=0", b"crc32c=1 status=0", 1))

    def test_inode_only_after_fifteenth_call(self):
        for cut in range(1, 21):
            data = sample(cut)
            marker = data.splitlines(keepends=True)[-1]
            if cut < 15:
                self.reject(data.replace(marker, INODE + b"\n" + marker), cut)
            else:
                self.reject(data.replace(INODE + b"\n", b""), cut)
                self.reject(data.replace(INODE + b"\n", (INODE + b"\n") * 2), cut)
                for old, new in ((b"io=15", b"io=14"), (b"inode=14", b"inode=13"),
                                 (b"mode=17896", b"mode=36328"), (b"uid=1000", b"uid=0"),
                                 (b"gid=1000", b"gid=1001"), (b"version=3", b"version=2"),
                                 (b"ctime_sec=1700000000", b"ctime_sec=1699999999"),
                                 (b"ctime_sec=1700000000", b"ctime_sec=1700003600"),
                                 (b"ctime_nsec=123456789", b"ctime_nsec=1000000000")):
                    self.reject(data.replace(INODE, INODE.replace(old, new)), cut)
        data = sample(20)
        fifteenth = next(line for line in data.splitlines(keepends=True) if line.startswith(b"JDMODE_IO ordinal=15 "))
        self.reject(data.replace(fifteenth + INODE + b"\n", INODE + b"\n" + fifteenth))
        self.reject(data.replace(INODE, b"prefix " + INODE))

    def test_initial_entry_binding_and_order(self):
        data = sample(20)
        for index in (0, 2, 4, 5, 6, 8, 9):
            line = HEADER[index] + b"\n"
            self.reject(data.replace(line, b"", 1))
            self.reject(data.replace(line, line * 2, 1))
            self.reject(data.replace(line, b"prefix " + line, 1))
        for old, new in ((b"sdk=31", b"sdk=30"), (b"uid=1000", b"uid=0"),
                         (b"clock=in-range", b"clock=negative"), (b"before-entry=1", b"before-entry=0"),
                         (b"ordinal=1 name=chmod", b"ordinal=2 name=chmod"),
                         (b"name=chmod", b"name=fchmod"), (b"source=firmware pages=", b"source=linker pages="),
                         (b"personality=linux source=", b"personality=native source="),
                         (b"pages=21", b"pages=0"), (b"init=loaded", b"init=failed")):
            self.reject(data.replace(old, new, 1))
        image = HEADER[4] + b"\n"
        hardware = HEADER[5] + b"\n"
        credentials = HEADER[6] + b"\n"
        self.reject(data.replace(image + hardware, hardware + image))
        self.reject(data.replace(hardware + credentials, credentials + hardware))
        self.reject(data.replace(image, b"").replace(credentials, credentials + image))

    def test_tail_termination_must_be_exact(self):
        for arch in ("x86_64", "i386", "mips"):
            data = sample(20, arch, terminated=True)
            for old, new in ((b"signal 15", b"signal 9"), (b"pid 1234", b"pid 0"),
                             (b"pid 1234", b"pid 01234"), (b"python3.11", b"untrusted"),
                             (b"qemu-system-" + arch.encode(), b"qemu-system-arm")):
                self.reject(data.replace(old, new), 20, arch)
            termination = data.splitlines(keepends=True)[-1]
            self.reject(data + termination, 20, arch)
            self.reject(data + b"JDMODE_IO ordinal=21 kind=flush sector=0 bytes=0 crc32c=0 status=0\n", 20, arch)
            self.reject(data.replace(termination, b"").replace(HEADER[8], termination + HEADER[8]), 20, arch)

    def test_bounded_canonical_records(self):
        data = sample(20)
        for token in (b"JDMODE", b"JDMODE_IO ordinal=", b"JDMODE_UNRECOGNIZED", b"JDMODE_OP_END ordinal=1 mutation=1",
                      b"JDMODE_USER_FAIL line=1", b"OK_TEST_FAIL", b"PANIC", b"LINUX_CHMOD_SNAPSHOT name=x"):
            self.reject(data.replace(HEADER[8], token + b"\n" + HEADER[8]))
        self.reject(data + b"\x00\n")
        self.reject(data.replace(b"\n", b"\r", 1))
        self.reject(data.replace(b"\n", b"\v", 1))
        self.reject(data.replace(b"JDMODE_IO ordinal=2 ", b"JDMODE_IO ordinal=18446744073709551616 "))
        self.reject(b"x" * (256 * 1024 + 1))
        self.reject(b"\n" * 4097)
        self.reject(b"x" * 4097 + b"\n")
        self.reject(data.decode())
        self.reject(b"")
        for cut in (0, 21, -1, True, 1.0, "1"):
            self.reject(data, cut)
        for arch in ("ppc", "mips64", None, [], "X86_64"):
            self.reject(data, arch=arch)

    def test_fixture_fact_binding(self):
        data = sample(20)
        mutations = (("origin", -1), ("origin", True), ("origin", 13),
                     ("sectors", 1), ("block_size", 4096), ("journal_start", 1),
                     ("feature_masks", [4, 0x46, 0x400]), ("journal_first", 8710),
                     ("journal_blocks", 5), ("nodes", {}))
        for key, value in mutations:
            facts = copy.deepcopy(FACTS)
            facts[key] = value
            self.reject(data, facts=facts)
        for key, value in (("inode", 13), ("block", 7), ("mode", 0o100644),
                           ("uid", 0), ("gid", 1001), ("version", 1),
                           ("version", (1 << 64) - 1)):
            facts = copy.deepcopy(FACTS)
            facts["nodes"]["child"][key] = value
            self.reject(data, facts=facts)
        self.reject(data, facts=[])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CutEvidenceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"MODEL_ONLY accepted={CutEvidenceTests.accepted} rejected={CutEvidenceTests.rejected} native_executions=0")
    raise SystemExit(not result.wasSuccessful())
