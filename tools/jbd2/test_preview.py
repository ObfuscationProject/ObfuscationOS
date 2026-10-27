#!/usr/bin/env python3
"""Boot an SDK-only ext4 final-view inspector against private read-only disks.

This qualifies no-write inspection, not replay execution or filesystem mounting.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
sys.dont_write_bytecode = True
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, machine, boot, validate_sdk
from admit_linux_fixture import inspect, header_for, checksum
ROOT = Path(__file__).resolve().parents[2]
CASES = {"metadata-preview": [], "mapping-reject": ["-DOK_EXT4_PREVIEW_MAPPING_REJECT"],
         "payload-corrupt": ["-DOK_EXT4_PREVIEW_PAYLOAD_CORRUPT"]}


def sha(data): return hashlib.sha256(data).hexdigest()


def altered(captured, facts, scenario):
    data = bytearray(captured)
    size = facts["block_size"]
    first = facts["journal_first"] * size
    inode = first + size * 3 + facts["seed_offset"]
    if scenario == "payload-corrupt":
        data[inode + 124] ^= 1
    elif scenario == "mapping-reject":
        physical = struct.unpack_from("<I", data, inode + 60)[0]
        struct.pack_into("<I", data, inode + 60, physical + 1)
        data[inode + 124:inode + 126] = bytes(2)
        data[inode + 130:inode + 132] = bytes(2)
        seed = checksum(0xffffffff, bytes.fromhex(facts["uuid"]))
        crc = checksum(checksum(seed, struct.pack("<I", facts["seed_inode"])), data[inode + 100:inode + 104])
        crc = checksum(crc, data[inode:inode + 256])
        struct.pack_into("<H", data, inode + 124, crc & 0xffff)
        struct.pack_into("<H", data, inode + 130, crc >> 16)
        sequence = data[first + size + 8:first + size + 12]
        crc = checksum(checksum(seed, sequence), data[first + size * 3:first + size * 4])
        struct.pack_into(">I", data, first + size + 56, crc)
        struct.pack_into(">I", data, first + size * 2 - 4, 0)
        crc = checksum(seed, data[first + size:first + size * 2])
        struct.pack_into(">I", data, first + size * 2 - 4, crc)
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arch", choices=tuple(ARCH_TRIPLES), required=True)
    p.add_argument("--mode", choices=("debug", "release"), default="debug")
    p.add_argument("--kernel-sdk", type=Path, required=True)
    p.add_argument("--toolchain", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--qemu")
    args = p.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    commands, cases = [], []
    report = {"scope": "booted-device-ext4-final-view-inspection", "arch": args.arch, "mode": args.mode,
              "status": "running", "commands": commands, "cases": cases, "mount_admission": False,
              "replay_execution": False, "writes": False, "flushes": False, "physical_power_loss": False}
    def save(): (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    def run(command, label):
        record = {"argv": [str(x) for x in command], "label": label, "status": "running"}
        commands.append(record); save(); start = time.monotonic()
        result = subprocess.run(record["argv"], capture_output=True, text=True)
        (out / (label + ".log")).write_text(result.stdout + result.stderr)
        record.update(status="passed" if not result.returncode else "failed", returncode=result.returncode,
                      seconds=time.monotonic() - start); save()
        if result.returncode: raise RuntimeError(label + " failed; inspect retained output")
        return result.stdout
    save()
    try:
        prefix = args.toolchain.resolve() / "bin" / (ARCH_TRIPLES[args.arch] + "-")
        cxx, ar, objcopy = [Path(str(prefix) + x) for x in ("g++", "ar", "objcopy")]
        sdk = out / "sdk"
        manifest, manifest_sha = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if not {"include/ok/fs/ext4/layout.hpp", "include/ok/fs/ext4/txn.hpp", "include/ok/fs/ext4/journal.hpp"}.issubset(manifest["files"]):
            raise ValueError("exact SDK lacks the ext4 binding/view headers")
        if "-frtti" not in manifest["cxxflags"] or "-fno-rtti" in manifest["cxxflags"]:
            raise ValueError("SDK must retain RTTI")
        report.update(sdk_abi=manifest["abi_version"], sdk_manifest_sha256=manifest_sha,
                      sdk_source=str(args.kernel_sdk.resolve()), compiler=manifest["compiler"])
        for path in sdk.rglob("*"):
            if path.is_file(): path.chmod(0o444)
        for path in sorted(sdk.rglob("*"), reverse=True):
            if path.is_dir(): path.chmod(0o555)
        sdk.chmod(0o555)
        fixture = args.fixture.resolve()
        capture_manifest = json.loads((fixture / "capture-manifest.json").read_text())
        captured = (fixture / "linux-dirty-capture.img").read_bytes()
        if sha(captured) != capture_manifest["capture_sha256"]: raise ValueError("Linux capture identity changed")
        facts = inspect(captured, True)
        if json.loads(json.dumps(facts)) != json.loads((fixture / "admission.json").read_text()):
            raise ValueError("independently inspected admission facts changed")
        header = header_for(facts)
        if header != (fixture / "linux_fixture.hpp").read_text(): raise ValueError("fixture header differs from admitted facts")
        (out / "linux_fixture.hpp").write_text(header)
        (out / "linux-dirty-capture.img").write_bytes(captured)
        (out / "capture-manifest.json").write_bytes((fixture / "capture-manifest.json").read_bytes())
        (out / "admission.json").write_bytes((fixture / "admission.json").read_bytes())
        report.update(capture_sha256=sha(captured), linux_image_sha256=capture_manifest["linux_image_sha256"],
                      linux_source_provenance=capture_manifest["linux_source_provenance"])
        sources = {}
        for relative in ("drivers/virtio/block.cpp", "drivers/virtio/block.hpp", "drivers/virtio/poll.hpp"):
            target = out / "external" / relative
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes((ROOT / relative).read_bytes())
            sources["external/" + relative] = sha(target.read_bytes())
        for relative in ("tools/jbd2/test_preview.py", "tools/jbd2/native_support.py", "tools/jbd2/admit_linux_fixture.py", "tools/kernel_sdk.py", "tests/native/ext4_preview.cpp"):
            target = out / "sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes((ROOT / relative).read_bytes())
            sources["sources/" + relative] = sha(target.read_bytes())
        report["source_sha256"] = sources
        members = run([ar, "t", sdk / "lib/libokernel_boot.a"], "boot-members").splitlines()
        if members.count("boot.S.o") != 1: raise ValueError("SDK needs exactly one boot.S.o")
        command = [str(ar), "p", str(sdk / "lib/libokernel_boot.a"), "boot.S.o"]
        commands.append({"argv": command, "label": "extract-boot"}); save()
        (out / "boot.o").write_bytes(subprocess.check_output(command))
        flags = ["-std=c++23", *manifest["cxxflags"], "-fno-builtin", "-Werror",
                 *("-D" + value for value in manifest["defines"]), "-I", str(sdk / "include"),
                 "-I", str(out / "external"), "-I", str(out)]
        run([cxx, *flags, "-c", out / "external/drivers/virtio/block.cpp", "-o", out / "driver.o"], "compile-driver")
        qemu = shutil.which(args.qemu or QEMU[args.arch])
        if not qemu: raise ValueError("explicit QEMU profile absent")
        report["qemu"] = run([qemu, "--version"], "qemu-version").splitlines()[0]
        for scenario, definitions in CASES.items():
            obj, elf, image = [out / (scenario + suffix) for suffix in (".o", ".elf", ".bin")]
            run([cxx, *flags, *definitions, "-c", out / "sources/tests/native/ext4_preview.cpp", "-o", obj], "compile-" + scenario)
            run([cxx, *manifest["ldflags"], "-nostdlib", "-static", "-Wl,--build-id=none", "-Wl,-T," + str(sdk / "boot/linker.ld"),
                 out / "boot.o", out / "driver.o", obj, sdk / "lib/libokernel.a", "-lgcc", "-o", elf], "link-" + scenario)
            run([sys.executable, out / "sources/tools/kernel_sdk.py", "assemble", "--sdk", sdk,
                 "--arch", args.arch, "--mode", args.mode, "--compiler", cxx,
                 "--elf", elf, "--out", image, "--objcopy", objcopy], "assemble-" + scenario)
            scratch = out / (scenario + ".img")
            data = altered(captured, facts, scenario); scratch.write_bytes(data)
            command = machine(qemu, args.arch, image)
            transport = "virtio-blk-device" if args.arch in ("aarch64", "arm32", "rv32", "rv64") else "virtio-blk-pci"
            command += ["-drive", f"file={scratch},format=raw,if=none,id=preview,readonly=on,cache=writeback", "-device", transport + ",drive=preview"]
            item = {"scenario": scenario, "status": "running", "disk_before_sha256": sha(data), "readonly_device": True}
            cases.append(item); commands.append({"argv": command, "label": "qemu-" + scenario}); save()
            boot(command, "EXT4_PREVIEW_PASS scope=hardware case=" + scenario +
                 " writes=0 flushes=0 mount=none\n", out / (scenario + ".log"))
            if scratch.read_bytes() != data: raise ValueError("preview changed its disk")
            item.update(status="passed", disk_after_sha256=sha(scratch.read_bytes()), full_image_unchanged=True); save()
            print("PASS " + args.arch + " " + scenario, flush=True)
        validate_sdk(sdk, args.arch, args.mode, cxx)
        report.update(status="passed", sdk_snapshot_revalidated=True)
    except Exception as error:
        report.update(status="failed", error=str(error)); print("FAIL " + str(error), flush=True)
    finally:
        report["artifacts_sha256"] = {str(path.relative_to(out)): sha(path.read_bytes()) for path in sorted(out.rglob("*"))
                                      if path.is_file() and path.name != "result.json" and "sdk" not in path.relative_to(out).parts}
        save()
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__": raise SystemExit(main())
