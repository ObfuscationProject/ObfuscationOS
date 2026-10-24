#!/usr/bin/env python3
"""Run default Notes/Mv/Stat as static-musl programs on a journalled disk root.

The exact SDK-only distro image is an explicit input. The campaign never builds
Kernel sources or admits reclaim writers. Stopping QEMU after fsync is a restart
test, not a clean guest shutdown; the original dirty disks remain available.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "scripts")]
from build_musl_probe import admit_musl_build
from kernel_sdk import validate_sdk
from musl_source import inspect_elf
from qemu_distro import command_for


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


KERNEL_PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32",
                   "loongarch64", "mips", "mips64", "ppc")
SUPPLIED_MUSL = ("x86_64", "aarch64", "rv64", "loongarch64")
RECEIPT_PROFILES = {
    "read-guard-v29": ("passed-exact-current-read-guard-sdk-qemu-and-os-consumer", 626),
    "startup-read-guard-v31": ("passed-exact-startup-read-guard-sdk-qemu-and-os-consumer", 628),
    "owner-lifetime-v34": ("passed-exact-owner-lifetime-sdk-qemu-and-os-consumer", 630),
}
WORKFLOW_SOURCE = "tools/qualify_journalled_workflow.py"
V34_WORKFLOW_BASE_SHA256 = '424125570b99e26bdca989980151abfe0373144970292c43d4cfc8d757ffd8e7'
V34_HANDOFF_SHA256 = "050b7d66a893788dc96347aa93d95c1ed01e648f6456a68a18296e4cf747fa11"
V31_WORKFLOW_BASE_SHA256 = "1e7c783f0f266e1a9e0215b614fd3d1e4e56e37fb8fe94f3b3210837d42a7e47"


def admit_receipt_profile(qualified, profile, sdk_pin, distro_pin,
                          source_map, workflow_pin):
    """Admit one named reviewed SDK campaign, never infer profile from a status."""
    if profile not in RECEIPT_PROFILES:
        raise ValueError("unreviewed SDK receipt profile")
    status, os_count = RECEIPT_PROFILES[profile]
    modern = profile == "owner-lifetime-v34"
    kernel_count, header_count, artifact_count = (1147, 232, 238) if modern else (1137, 231, 237)
    if modern:
        guard_qualified = (qualified.get("owner_member_lifetime_repair") is True and
            qualified.get("source_handoff_sha256") == V34_HANDOFF_SHA256 and
            qualified.get("expected_model_status") == "passed-hosted-owner-budget-lifetime-and-ten-profile-compile" and
            all(isinstance(qualified.get(name), str) and len(qualified[name]) == 64 and
                all(char in "0123456789abcdef" for char in qualified[name])
                for name in ("models_result_sha256", "parent_models_result_sha256")))
    else:
        guard_qualified = qualified.get("read_guard_debug_model_reached") is True
    if (qualified.get("schema") != 1 or qualified.get("status") != status or
            qualified.get("abi_version") != 48 or
            qualified.get("sdk_manifest_sha256") != sdk_pin or
            qualified.get("consumer_artifacts", {}).get("distro/kernel.bin") != distro_pin or
            qualified.get("kernel_profiles") != list(KERNEL_PROFILES) or
            qualified.get("supplied_musl_userlands") != list(SUPPLIED_MUSL) or
            qualified.get("qemu_debug_points") != 65 or
            not guard_qualified or
            any(qualified.get(name) is not False for name in (
                "writer_enabled", "native_media", "native_smp", "hardware",
                "manual_desktop", "full_m0_m12"))):
        raise ValueError("explicit distro/SDK qualification profile mismatch")
    kernel = qualified.get("kernel_sources")
    baseline = qualified.get("os_sources")
    artifacts = qualified.get("sdk_artifacts")
    if (not isinstance(kernel, dict) or len(kernel) != kernel_count or
            not isinstance(baseline, dict) or len(baseline) != os_count or
            not isinstance(artifacts, dict) or len(artifacts) != artifact_count):
        raise ValueError("reviewed SDK receipt source/artifact inventory mismatch")
    headers = {name: value for name, value in kernel.items() if name.startswith("include/")}
    other = {"boot/boot16.bin", "boot/linker.ld", "image/kernel.bin", "image/kernel.elf",
             "lib/libokernel.a", "lib/libokernel_boot.a"}
    if (len(headers) != header_count or set(artifacts) != set(headers) | other or
            any(artifacts[name] != expected for name, expected in headers.items())):
        raise ValueError("SDK exports differ from the reviewed Kernel source headers")
    if profile == "startup-read-guard-v31":
        if (baseline.get(WORKFLOW_SOURCE) != V31_WORKFLOW_BASE_SHA256 or
                not workflow_pin or source_map.get(WORKFLOW_SOURCE) != workflow_pin):
            raise ValueError("V31 workflow source override lacks its explicit baseline/current pin")
        expected = dict(baseline)
        expected[WORKFLOW_SOURCE] = workflow_pin
        if source_map != expected:
            raise ValueError("V31 native campaign requires exact OS628 with only its pinned qualifier update")
    elif modern:
        if (baseline.get(WORKFLOW_SOURCE) != V34_WORKFLOW_BASE_SHA256 or
                not workflow_pin or source_map.get(WORKFLOW_SOURCE) != workflow_pin):
            raise ValueError("V34 workflow qualifier override lacks its exact baseline/current pin")
        expected = dict(baseline)
        expected[WORKFLOW_SOURCE] = workflow_pin
        if source_map != expected:
            raise ValueError("V34 native campaign requires exact OS630 with only its pinned qualifier update")
    elif workflow_pin:
        raise ValueError("workflow source override requires a reviewed named profile")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--sdk-manifest-sha256", required=True)
    parser.add_argument("--distro-image", type=Path, required=True)
    parser.add_argument("--distro-sha256", required=True)
    parser.add_argument("--sdk-receipt", type=Path, required=True)
    parser.add_argument("--sdk-receipt-sha256", required=True)
    parser.add_argument("--sdk-receipt-profile", choices=tuple(RECEIPT_PROFILES),
                        default="read-guard-v29",
                        help="Explicit reviewed SDK campaign; the V29 default preserves its original caller")
    parser.add_argument("--workflow-source-sha256",
                        help="V31/V34: exact updated qualifier hash; all other sources must match the named receipt")
    parser.add_argument("--musl-build", type=Path, required=True)
    parser.add_argument("--musl-manifest-sha256", required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--linux-image", type=Path, required=True)
    parser.add_argument("--linux-image-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "status": "running", "architecture": "x86_64",
              "sdk_mode": "debug", "scope": "actual-static-musl-journalled-root-workflow",
              "kernel_source_compiled": False, "physical_hardware": False,
              "native_smp": False, "reclaim_writer_enabled": False,
              "kernel_architectures": ["i386", "x86_64", "aarch64", "arm32", "rv64", "rv32",
                                       "loongarch64", "mips", "mips64", "ppc"],
              "supplied_musl_userlands": ["x86_64", "aarch64", "rv64", "loongarch64"],
              "native_uid": 1000, "native_gid": 1000,
              "guest_clean_shutdown": False,
              "shutdown_boundary": "fsync, preserved QEMU stop, native restart; no unmount/reboot syscall",
              "commands": []}

    def save():
        (output / "RESULT.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")

    environment = dict(os.environ, XMAKE_ROOT="y", TZ="UTC", PYTHONDONTWRITEBYTECODE="1",
                       XMAKE_GLOBALDIR=str(output / "xmake-global"),
                       TMPDIR=str(output / "tmp"))
    (output / "tmp").mkdir()
    for name in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH", "LIBRARY_PATH",
                 "GCC_EXEC_PREFIX", "COMPILER_PATH"):
        environment.pop(name, None)

    def run(argv, label, allowed=(0,)):
        argv = list(map(str, argv))
        row = {"label": label, "argv": argv}
        report["commands"].append(row)
        save()
        result = subprocess.run(argv, env=environment, cwd=output, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        log = output / (label + ".log")
        log.write_bytes(result.stdout)
        row.update(exit_code=result.returncode, log_sha256=sha(log))
        save()
        if result.returncode not in allowed:
            raise ValueError(label + " failed: " + str(log))
        print(label + " passed", flush=True)
        return result.stdout

    def pinned_copy(source, target, expected):
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("input pin mismatch: " + str(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def guest(stage, disk):
        qemu = Path(shutil.which("qemu-system-x86_64") or "")
        argv = command_for(qemu, "x86_64", output / "kernel.bin", disk, "none")
        argv += ["-smp", "1"]
        row = {"label": "guest-" + stage, "argv": list(map(str, argv))}
        report["commands"].append(row)
        save()
        process = subprocess.Popen(argv, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        assert process.stdout
        log_path = output / ("guest-" + stage + ".log")
        marker = "OK_JOURNALLED_WORKFLOW result=pass stage=" + stage
        pending = bytearray()
        observed = set()
        start = time.monotonic()
        outcome = "timeout"
        try:
            with log_path.open("wb") as log:
                while time.monotonic() - start < 90:
                    ready, _, _ = select.select([process.stdout], [], [], 0.1)
                    if not ready:
                        if process.poll() is not None:
                            outcome = "process-exited"
                            break
                        continue
                    data = os.read(process.stdout.fileno(), 8192)
                    if not data:
                        outcome = "output-ended"
                        break
                    log.write(data)
                    log.flush()
                    pending.extend(data)
                    while b"\n" in pending:
                        raw, _, rest = pending.partition(b"\n")
                        pending = bytearray(rest)
                        line = raw.decode(errors="replace").strip()
                        if line.startswith("OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=ordered-data"):
                            observed.add("journalled-root")
                        if line.startswith("OK_NATIVE scope=hardware timer=preempted"):
                            observed.add("preemption")
                        if line.startswith("OK_TEST_PASS ") and "debug_test_points=65" in line:
                            observed.add("kernel65")
                        if "result=FAIL" in line or "boot=failed" in line or line.startswith("OK_TEST_FAIL "):
                            outcome = "guest-failed"
                            break
                        if line.startswith(marker):
                            observed.add("workflow")
                            outcome = "passed"
                            break
                    if outcome in ("passed", "guest-failed"):
                        break
        finally:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()
            row.update(outcome=outcome, observed=sorted(observed),
                       seconds=time.monotonic() - start, exit_code=process.returncode,
                       log_sha256=sha(log_path), disk_sha256=sha(disk))
            save()
        if outcome != "passed" or observed != {"journalled-root", "preemption", "kernel65", "workflow"}:
            raise ValueError("native " + stage + " failed; disk/log preserved")
        print("native " + stage + " passed", flush=True)

    save()
    try:
        source_map = {}
        for path in sorted(ROOT.rglob("*")):
            if (path.is_file() and not any(part in ("build", ".xmake", "__pycache__")
                                           for part in path.relative_to(ROOT).parts) and
                    path.suffix != ".pyc"):
                source_map[path.relative_to(ROOT).as_posix()] = sha(path)
        report["source_sha256"] = source_map
        source = output / "source/ObfuscationOS"
        for name, expected in source_map.items():
            pinned_copy(ROOT / name, source / name, expected)
        receipt = output / "sdk-receipt.json"
        pinned_copy(args.sdk_receipt.resolve(), receipt, args.sdk_receipt_sha256)
        qualified = json.loads(receipt.read_text())
        admit_receipt_profile(qualified, args.sdk_receipt_profile,
                              args.sdk_manifest_sha256, args.distro_sha256,
                              source_map, args.workflow_source_sha256)
        report.update(sdk_receipt_profile=args.sdk_receipt_profile,
                      sdk_receipt_status=qualified["status"],
                      sdk_os_baseline_count=len(qualified["os_sources"]),
                      sdk_os_baseline_sources=qualified["os_sources"],
                      workflow_source_sha256=source_map[WORKFLOW_SOURCE])
        original_sdk = args.kernel_sdk.resolve()
        if sha(original_sdk / "manifest.json") != args.sdk_manifest_sha256:
            raise ValueError("SDK manifest pin mismatch")
        sdk = output / "sdk"
        pinned_copy(original_sdk / "manifest.json", sdk / "manifest.json", args.sdk_manifest_sha256)
        for name, expected in qualified["sdk_artifacts"].items():
            pinned_copy(original_sdk / name, sdk / name, expected)
        compiler = args.toolchain.resolve() / "bin/x86_64-elf-gcc"
        sdk_manifest = validate_sdk(sdk, "x86_64", "debug",
                                    compiler.with_name("x86_64-elf-g++"))
        if sdk_manifest["abi_version"] != 48:
            raise ValueError("experimental SDK requires ABI48")
        if sdk_manifest["files"] != qualified["sdk_artifacts"]:
            raise ValueError("exported SDK manifest differs from the exact reviewed artifact inventory")
        pinned_copy(args.distro_image.resolve(), output / "kernel.bin", args.distro_sha256)
        musl = args.musl_build.resolve()
        if sha(musl / "manifest.json") != args.musl_manifest_sha256:
            raise ValueError("musl build pin mismatch")
        musl_manifest = admit_musl_build(musl, "x86_64")
        pinned_copy(musl / "manifest.json", output / "musl-manifest.json", args.musl_manifest_sha256)
        for name, expected in musl_manifest["files"].items():
            if name.startswith("sysroot/"):
                pinned_copy(musl / name, output / "musl" / name, expected)
        report.update(sdk_manifest_sha256=args.sdk_manifest_sha256,
                      sdk_receipt_sha256=args.sdk_receipt_sha256,
                      distro_image_sha256=args.distro_sha256,
                      musl_manifest_sha256=args.musl_manifest_sha256,
                      musl_version=musl_manifest["version"], sdk_abi=48)
        # Only two project-private declarations are visible: project libc
        # headers must never shadow the copied musl headers.
        include = output / "app-include"
        for name, origin in (("ok/dirent.h", "sdk/include/ok/dirent.h"),
                             ("ok/syscall.h", "lib/okcrt/include/ok/syscall.h")):
            pinned_copy(source / origin, include / name, source_map[origin])
        project = output / "app-project"
        project.mkdir()
        lib = output / "musl/sysroot/usr/lib"
        musl_include = output / "musl/sysroot/usr/include"
        quote = lambda value: json.dumps(str(value))
        values = lambda rows: ", ".join(quote(row) for row in rows)
        flags = ["-std=c11", "-O2", "-m64", "-mno-red-zone", "-fno-builtin",
                 "-fno-stack-protector", "-fno-pie", "-ftls-model=local-exec",
                 "-ffunction-sections", "-fdata-sections", "-nostdinc",
                 "-isystem", str(musl_include), "-Wall", "-Wextra", "-Werror"]
        link = ["-nostdlib", "-static", "-no-pie", "-Wl,-e,_start",
                "-Wl,-T," + str(source / "tests/musl/bootstrap.ld"),
                "-Wl,--defsym,USER_BASE=0x40000000", "-Wl,-z,max-page-size=4096",
                "-Wl,-z,noexecstack", "-Wl,--gc-sections", str(lib / "crt1.o"),
                str(lib / "crti.o"), "-Wl,--start-group", str(lib / "libc.a"),
                "-lgcc", "-Wl,--end-group", str(lib / "crtn.o")]
        lua = ["set_project(\"journalled-musl-workflow\")", "set_languages(\"c11\")",
               "toolchain(\"workflow-cross\")", "set_kind(\"standalone\")",
               "set_toolset(\"cc\", " + quote(compiler) + ")",
               "set_toolset(\"ld\", " + quote(compiler) + ")", "toolchain_end()"]
        for name, sources in {
            "init": [source / "tests/musl/journalled_workflow.c"],
            "notes": [source / "apps/notes/main.c", source / "apps/notes/save.c"],
            "mv": [source / "apps/mv/main.c", source / "apps/lib/commands.c"],
            "stat": [source / "apps/stat/main.c", source / "apps/lib/commands.c"],
        }.items():
            lua += ["target(" + quote(name) + ")", "set_kind(\"binary\")",
                    "set_toolchains(\"workflow-cross\")",
                    "set_targetdir(" + quote(output / "apps") + ")",
                    "set_filename(" + quote(name + ".elf") + ")",
                    "add_files(" + values(sources) + ")",
                    "add_includedirs(" + values([include, sdk / "include", source / "apps/lib"]) + ")",
                    "add_cflags(" + values(flags) + ", {force = true})",
                    "add_ldflags(" + values(link) + ", {force = true})", "target_end()"]
        (project / "xmake.lua").write_text("\n".join(lua) + "\n")
        xmake = Path(shutil.which("xmake") or "")
        tool_paths = [compiler, compiler.with_name("x86_64-elf-g++"), xmake,
                      Path(shutil.which("qemu-system-x86_64") or ""),
                      Path(shutil.which("mke2fs") or ""), Path(shutil.which("e2fsck") or ""),
                      Path(shutil.which("debugfs") or ""), Path(shutil.which("gcc") or ""),
                      Path(sys.executable)]
        report["tool_sha256"] = {str(path.resolve()): sha(path.resolve()) for path in tool_paths}
        run([xmake, "f", "-P", project, "-y", "--ccache=n", "-o", output / "app-build"],
            "apps-configure")
        run([xmake, "build", "-P", project, "-vD", "-j", "2"], "apps-build")
        rootfs = output / "rootfs"
        (rootfs / "bin").mkdir(parents=True)
        (rootfs / "home").mkdir(mode=0o700)
        (rootfs / "tmp").mkdir(mode=0o1777)
        user_artifacts = {}
        for name in ("init", "notes", "mv", "stat"):
            executable = output / "apps" / (name + ".elf")
            data = bytearray(executable.read_bytes())
            if data[:7] != b"\x7fELF\x02\x01\x01" or data[8] != 0:
                raise ValueError("unexpected ELF before Linux personality marking")
            data[7] = 3
            executable.write_bytes(data)
            identity = inspect_elf(executable, "x86_64")
            target = rootfs / ("init" if name == "init" else "bin/" + name)
            shutil.copy2(executable, target)
            target.chmod(0o755)
            user_artifacts[name] = {"sha256": sha(executable), "elf": identity,
                                    "static_musl": True}
        report["user_artifacts"] = user_artifacts
        linux = args.linux_image.resolve()
        if sha(linux) != args.linux_image_sha256:
            raise ValueError("Linux activation kernel pin mismatch")
        disk = output / "disk.img"
        run([sys.executable, "-B", source / "tools/mkext4_journalled.py", "--root", rootfs,
             "--out", disk, "--linux-image", linux,
             "--linux-image-sha256", args.linux_image_sha256], "journalled-image")
        # mke2fs -d preserves host ownership. Bind the fixture's ordinary user
        # directory explicitly instead of depending on the invoking host UID.
        run(["debugfs", "-w", "-R", "set_inode_field /home uid 1000", disk], "home-uid")
        run(["debugfs", "-w", "-R", "set_inode_field /home gid 1000", disk], "home-gid")
        run(["e2fsck", "-fn", disk], "initial-fsck")
        shutil.copy2(disk, output / "initial.img")
        run(["debugfs", "-R", "dump /init " + str(output / "disk-init.elf"), disk], "initial-init-readback")
        if sha(output / "disk-init.elf") != user_artifacts["init"]["sha256"]:
            raise ValueError("disk root init readback mismatch")
        guest("first", disk)
        shutil.copy2(disk, output / "after-first.img")
        guest("restart", disk)
        shutil.copy2(disk, output / "after-restart.img")
        run(["debugfs", "-R", "dump /home/workflow.txt " + str(output / "saved-note.txt"), disk],
            "native-content-readback")
        if (output / "saved-note.txt").read_bytes() != b"Basic English journalled workflow\n":
            raise ValueError("native saved text differs from expected English workflow")
        namespace = run(["debugfs", "-R", "ls -l /home", disk], "native-namespace-readback")
        if b"workflow-first" in namespace or b".notes-" in namespace or b"workflow.txt" not in namespace:
            raise ValueError("native saved namespace differs from completed rename")
        recovered = output / "offline-recovered.img"
        shutil.copy2(disk, recovered)
        run(["e2fsck", "-fy", recovered], "offline-recovery", allowed=(0, 1))
        run(["e2fsck", "-fn", recovered], "offline-fsck")
        run(["debugfs", "-R", "dump /home/workflow.txt " + str(output / "recovered-note.txt"), recovered],
            "recovered-content-readback")
        if (output / "recovered-note.txt").read_bytes() != (output / "saved-note.txt").read_bytes():
            raise ValueError("offline recovery changed completed note")
        if any(sha(ROOT / name) != expected for name, expected in source_map.items()):
            raise ValueError("source changed during campaign")
        if sha(args.kernel_sdk.resolve() / "manifest.json") != args.sdk_manifest_sha256:
            raise ValueError("producer SDK changed during campaign")
        validate_sdk(args.kernel_sdk.resolve(), "x86_64", "debug",
                     compiler.with_name("x86_64-elf-g++"))
        if any(sha(Path(path)) != expected for path, expected in report["tool_sha256"].items()):
            raise ValueError("executed tool changed during campaign")
        report.update(status="passed-native-journalled-save-reopen-rename-restart",
                      native_execution=True, guest_boots=2,
                      unlink="ENOSYS; original namespace, inode and bytes preserved",
                      replacement_save="not admitted; pending reclaim writer",
                      manual_desktop=False, full_m0_m12=False,
                      disks={name: sha(output / name) for name in (
                          "initial.img", "after-first.img", "after-restart.img", "offline-recovered.img")})
        save()
        freeze = {"schema": 1, "scope": report["scope"], "files_sha256": {
            path.relative_to(output).as_posix(): sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.name != "FREEZE.json" and
               ".xmake" not in path.relative_to(output).parts}}
        (output / "FREEZE.json").write_text(json.dumps(freeze, sort_keys=True, indent=2) + "\n")
        print(report["status"], flush=True)
    except Exception as error:
        report.update(status="failed-preserved", failure=str(error))
        save()
        raise


if __name__ == "__main__":
    main()
