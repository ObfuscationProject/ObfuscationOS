#!/usr/bin/env python3
"""Run actual-device Linux-created JBD2 replay against one exact exported SDK.

An optional, explicitly labelled candidate header overlay supports mechanism
qualification before SDK export. Without it every Kernel header is SDK-owned.
Only newly created output-directory disk files are attached to QEMU.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, machine, boot, validate_sdk, assemble_image
from admit_linux_fixture import inspect, header_for

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("strict-reject", "replay", "reopen")


def sha(data): return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument("--mode", choices=("debug", "release"), default="debug")
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--os-root", type=Path, default=ROOT)
    parser.add_argument("--candidate-headers", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu")
    parser.add_argument("--runtime-binding", action="store_true",
                        help="derive journal ownership/mapping using the exported Kernel recovery binding")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, results = [], []
    summary = {
        "scope": "booted-guest-virtio-linux-created-journal-replay", "arch": args.arch, "mode": args.mode,
        "candidate_is_exported_sdk": args.candidate_headers is None,
        "mechanism": "exported-sdk" if args.candidate_headers is None else "explicit-staged-header-overlay",
        "runtime_binding": args.runtime_binding,
        "journal_writer": False, "checkpoint": False, "mount_admission": False, "physical_power_loss": False,
        "commands": commands, "results": results, "status": "running",
    }
    def save(): (out / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    def run(command, label, *, capture=False):
        command = [str(item) for item in command]
        commands.append({"argv": command, "kind": label, "status": "running"}); save()
        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True)
        (out / (label + ".log")).write_text(result.stdout + result.stderr)
        commands[-1].update({"status": "passed" if result.returncode == 0 else "failed",
                             "returncode": result.returncode, "seconds": time.monotonic() - started})
        save()
        if result.returncode: raise RuntimeError(label + " failed; output retained")
        return result.stdout if capture else None
    save()
    for source in (Path(__file__), Path(__file__).with_name("native_support.py"),
                   Path(__file__).with_name("admit_linux_fixture.py"), ROOT / "tools/kernel_sdk.py"):
        target = out / "harness" / source.name
        target.parent.mkdir(exist_ok=True); target.write_bytes(source.read_bytes())
    try:
        triple = ARCH_TRIPLES[args.arch]
        prefix = args.toolchain.resolve() / "bin" / (triple + "-")
        cxx, ar, objcopy = [Path(str(prefix) + name) for name in ("g++", "ar", "objcopy")]
        sdk = out / "sdk"
        manifest, manifest_sha = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if args.runtime_binding and "include/ok/fs/ext4/journal.hpp" not in manifest["files"]:
            raise ValueError("runtime binding requires its header and implementation in the exported SDK")
        if "-frtti" not in manifest["cxxflags"] or "-fno-rtti" in manifest["cxxflags"]:
            raise ValueError("SDK must retain RTTI")
        summary.update({"sdk_abi": manifest["abi_version"], "sdk_manifest_sha256": manifest_sha,
                        "sdk_source": str(args.kernel_sdk.resolve()), "compiler": manifest["compiler"]})
        # Read-only snapshot, validated again after all compilation/native execution.
        for item in sdk.rglob("*"):
            if item.is_file(): item.chmod(0o444)
        for item in sorted(sdk.rglob("*"), reverse=True):
            if item.is_dir(): item.chmod(0o555)
        sdk.chmod(0o555)
        fixture = args.fixture.resolve()
        capture_manifest = json.loads((fixture / "capture-manifest.json").read_text())
        qualification = json.loads((fixture / "qualification.json").read_text())
        captured = (fixture / "linux-dirty-capture.img").read_bytes()
        expected = (fixture / "native-expected.img").read_bytes()
        control = (fixture / "e2fsprogs-recovery.img").read_bytes()
        baseline = (fixture / "baseline-clean.img").read_bytes()
        if sha(captured) != capture_manifest["capture_sha256"] or sha(baseline) != capture_manifest["baseline_sha256"]:
            raise ValueError("captured/baseline identity changed")
        if sha(expected) != qualification["native_expected_sha256"] or sha(control) != qualification["independent_control_sha256"]:
            raise ValueError("qualified expected/control identity changed")
        facts, baseline_facts = inspect(captured, True), inspect(baseline, False)
        for key in ("uuid", "journal_first", "journal_blocks", "journal_inode_sha256", "metadata_ranges", "seed_inode_sha256"):
            if facts[key] != baseline_facts[key]: raise ValueError("fixture binding changed: " + key)
        if json.loads(json.dumps(facts)) != json.loads((fixture / "admission.json").read_text()): raise ValueError("admission facts changed")
        changed = [i for i in range(len(captured) // 1024)
                   if expected[i*1024:(i+1)*1024] != control[i*1024:(i+1)*1024]]
        if changed != [1, facts["journal_first"]]: raise ValueError("independent control differs outside cleanup blocks")
        if expected[facts["journal_first"]*1024:(facts["journal_first"]+facts["journal_blocks"])*1024] != \
                captured[facts["journal_first"]*1024:(facts["journal_first"]+facts["journal_blocks"])*1024]:
            raise ValueError("oracle modifies journal")
        for name, data in (("linux-dirty-capture.img", captured), ("native-expected.img", expected),
                           ("e2fsprogs-control-at-native-check.img", control)):
            (out / name).write_bytes(data)
        if (fixture / "linux_fixture.hpp").read_text() != header_for(facts):
            raise ValueError("fixture header does not match independently validated mapping")
        for name in ("capture-manifest.json", "qualification.json", "admission.json", "replay-plan.json", "linux_fixture.hpp"):
            shutil.copy2(fixture / name, out / name)
        summary.update({"capture_sha256": sha(captured), "expected_sha256": sha(expected),
                        "control_sha256_at_native_check": sha(control), "control_image": "e2fsprogs-control-at-native-check.img",
                        "linux_image_sha256": capture_manifest["linux_image_sha256"], "linux_source_provenance": "not-established",
                        "ext4_feature_masks": facts["feature_masks"], "journal_extent": [facts["journal_first"], facts["journal_blocks"]],
                        "journal_features": facts["journal_features"], "metadata_domain": facts["metadata_ranges"],
                        "e2fsprogs_different_blocks": changed, "inode_table_block_7_exact_match": True})
        # Freeze every source read by this harness, retaining explicit provenance.
        source_files = {}
        for relative in ("drivers/virtio/block.cpp", "drivers/virtio/block.hpp", "drivers/virtio/poll.hpp"):
            data = (args.os_root.resolve() / relative).read_bytes()
            target = out / "external" / relative
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            source_files[relative] = sha(data)
        probe = out / "probe.cpp"
        probe.write_bytes((ROOT / "tests/native/jbd2_linux.cpp").read_bytes())
        source_files["probe.cpp"] = sha(probe.read_bytes())
        for source in (Path(__file__), Path(__file__).with_name("native_support.py"),
                       Path(__file__).with_name("admit_linux_fixture.py"), ROOT / "tools/kernel_sdk.py"):
            target = out / "harness" / source.name
            target.parent.mkdir(exist_ok=True); target.write_bytes(source.read_bytes())
            source_files["harness/" + source.name] = sha(target.read_bytes())
        summary["source_sha256"] = source_files
        extra_headers = []
        if args.candidate_headers:
            for name in ("ext4/journal.hpp",):
                source = args.candidate_headers.resolve() / "ok/fs" / name
                target = out / "candidate/ok/fs" / name
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes())
                source_files["candidate/ok/fs/" + name] = sha(target.read_bytes())
            extra_headers = ["-I", str(out / "candidate")]
        members = run([ar, "t", sdk / "lib/libokernel_boot.a"], "boot-archive-members", capture=True).splitlines()
        if members.count("boot.S.o") != 1: raise ValueError("SDK boot archive lacks exactly one boot.S.o")
        commands.append({"argv": [str(ar), "p", str(sdk / "lib/libokernel_boot.a"), "boot.S.o"], "kind": "boot-extract"}); save()
        (out / "boot.o").write_bytes(subprocess.check_output(commands[-1]["argv"]))
        flags = ["-std=c++23", *manifest["cxxflags"], "-fno-builtin", "-Werror",
                 *(["-DOS_EXT4_RUNTIME_BINDING"] if args.runtime_binding else []),
                 *("-D" + item for item in manifest["defines"]), "-I", str(sdk / "include"),
                 "-I", str(out / "external"), "-I", str(out)]
        run([cxx, *flags, "-c", out / "external/drivers/virtio/block.cpp", "-o", out / "driver.o"], "compile-driver")
        qemu = shutil.which(args.qemu or QEMU[args.arch])
        if not qemu: raise ValueError("explicit QEMU profile unavailable")
        summary["qemu"] = run([qemu, "--version"], "qemu-version", capture=True).splitlines()[0]
        replay_disk = out / "candidate-scratch.img"
        replay_disk.write_bytes(captured)
        for scenario in SCENARIOS:
            extra = ["-DOK_LINUX_REQUIRE_REJECTION"] if scenario == "strict-reject" else extra_headers
            if scenario == "reopen": extra = [*extra, "-DOK_LINUX_REOPEN"]
            obj, elf, image = [out / (scenario + suffix) for suffix in (".o", ".elf", ".bin")]
            run([cxx, *extra, *flags, "-c", probe, "-o", obj], "compile-" + scenario)
            run([cxx, *manifest["ldflags"], "-nostdlib", "-static", "-Wl,--build-id=none",
                 "-Wl,-T," + str(sdk / "boot/linker.ld"), out / "boot.o", out / "driver.o", obj, sdk / "lib/libokernel.a",
                 "-lgcc", "-o", elf], "link-" + scenario)
            if manifest["image_format"] != "elf":
                commands.append({"argv": [str(objcopy), "-O", "binary", str(elf), str(image.with_name(image.stem + "_payload.bin"))], "kind": "image-objcopy"}); save()
            assemble_image(elf, image, sdk, manifest["image_format"], objcopy)
            disk = out / "strict-reject-scratch.img" if scenario == "strict-reject" else replay_disk
            if scenario == "strict-reject": disk.write_bytes(captured)
            before = disk.read_bytes()
            command = machine(qemu, args.arch, image)
            transport = "virtio-blk-device" if args.arch in ("aarch64", "arm32", "rv32", "rv64") else "virtio-blk-pci"
            command += ["-drive", f"file={disk},format=raw,if=none,id=linuxfixture,cache=writeback", "-device", transport + ",drive=linuxfixture",
                        "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
            record = {"scenario": scenario, "before_sha256": sha(before), "status": "running", "kernel_mechanism":
                      "exported-sdk" if scenario == "strict-reject" else summary["mechanism"]}
            results.append(record)
            commands.append({"argv": command, "kind": "qemu-" + scenario, "status": "running"}); save()
            try:
                code = boot(command, "JBD2_LINUX_PASS scope=hardware case=" + scenario, out / (scenario + ".log"))
                if args.runtime_binding and "EXT4_RECOVERY_BINDING_PASS scope=hardware mapping=device-derived writes=0 mount=none" not in \
                        (out / (scenario + ".log")).read_text():
                    raise ValueError("runtime binding acceptance marker missing")
                commands[-1].update({"returncode": code, "status": "passed"})
                after = disk.read_bytes()
                if after != (captured if scenario == "strict-reject" else expected):
                    raise ValueError("full disk differs from exact oracle: " + scenario)
                record.update({"status": "passed", "full_image_oracle": True})
            except Exception:
                commands[-1]["status"] = record["status"] = "failed"
                raise
            finally:
                record["after_sha256"] = sha(disk.read_bytes())
                save()
            print("PASS " + args.arch + " " + scenario, flush=True)
        before_check = sha(replay_disk.read_bytes())
        run(["e2fsck", "-fn", replay_disk], "post-native-readonly-e2fsck")
        if sha(replay_disk.read_bytes()) != before_check: raise ValueError("readonly check changed disk")
        run(["debugfs", "-R", "stat /seed", replay_disk], "post-native-seed")
        validate_sdk(sdk, args.arch, args.mode, cxx)
        summary.update({"status": "passed", "readonly_e2fsck_exit": 0, "journal_retained": True,
                        "ext4_needs_recovery_retained": True, "sdk_snapshot_revalidated": True})
    except Exception as error:
        summary.update({"status": "failed", "error": str(error)})
        print("FAIL " + args.arch + ": " + str(error), flush=True)
    finally:
        summary["artifacts_sha256"] = {str(path.relative_to(out)): sha(path.read_bytes())
                                       for path in sorted(out.rglob("*"))
                                       if path.is_file() and path.name != "result.json" and "sdk" not in path.relative_to(out).parts}
        save()
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__": raise SystemExit(main())
