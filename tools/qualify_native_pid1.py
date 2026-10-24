#!/usr/bin/env python3
"""Freeze OS source, then run a pinned SDK-only PID 1 supervisor guest.

Every run receives a fresh output directory. A failed run retains its source,
SDK, commands, serial, root disk and machine-readable result for diagnosis.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from qemu_distro import command_for
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import FLAGS, inspect_elf, ppc_frontend
from mips64_softfp import admit as admit_softfp
from object_pressure_evidence import relative_file, require_hash, sha, source_files
from pid1_events import validate as validate_execution, PASS
from native_offline_fsck import require_final_fsck
from native_terminal_evidence import inspect_terminal

FAILURES = (b"OK_TEST_FAIL", b"acceptance=FAIL", b"boot=degraded", b"boot=failed",
            b"PID1_EVENT kind=init-invalid", b"PID1_EVENT kind=clock-failed",
            b"PID1_EVENT kind=signal-mask-failed",
            b"PID1_EVENT kind=wait-failed", b"PID1_EVENT kind=service-lost",
            b"PID1_EVENT kind=launch-failed", b"PID1_EVENT kind=exec-failed",
            b"PID1_EVENT kind=stop-timeout", b"PID1_EVENT kind=orphan-timeout")


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def copy_inventory(root: Path, target: Path, files: dict[str, str]) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for name, digest in sorted(files.items()):
        original = relative_file(root, name)
        require_hash(original, digest, name)
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
        require_hash(destination, digest, "retained " + name)


def admit_source(root: Path, inventory: Path, digest: str) -> dict:
    require_hash(inventory, digest, "source inventory")
    value = json.loads(inventory.read_text())
    if (value.get("schema") != 1 or value.get("scope") != "native-pid1-supervisor-sdk34-os-sources" or
            not isinstance(value.get("files"), dict) or value["files"] != source_files(root)):
        raise ValueError("source inventory is incomplete, changed or wrong scope")
    return value["files"]


def qemu_command(qemu: Path, arch: str, image: Path, disk: Path) -> list[str]:
    command = list(map(str, command_for(qemu, arch, image, disk, "none")))
    if arch == "ppc":
        command += ["-cpu", "e500v2_v22", "-smp", "1", "-accel", "tcg,thread=single"]
    return command


def dependencies(compile_command: list[str], source: Path, roots: tuple[Path, ...]) -> dict:
    at = compile_command.index("-c")
    command = [*compile_command[:at], "-M", "-MT", "init-probe", str(source)]
    text = subprocess.check_output(command, text=True).replace("\\\n", "")
    if not text.startswith("init-probe:"):
        raise ValueError("unexpected compiler dependency target")
    found = {}
    for name in shlex.split(text.split(":", 1)[1]):
        path = Path(name).resolve()
        if not path.is_file() or not any(path.is_relative_to(root) for root in roots):
            raise ValueError("probe dependency outside retained inputs: " + name)
        found[str(path)] = sha(path)
    if str(source.resolve()) not in found:
        raise ValueError("compiler dependencies omitted init probe source")
    return {"command": command, "files": found}


def run(args: argparse.Namespace) -> None:
    if args.musl_mode != "debug":
        raise ValueError("this qualification requires an explicit pinned Debug musl sysroot")
    if bool(args.softfp_build) != bool(args.softfp_manifest_sha256):
        raise ValueError("binary128 build and manifest hash must be supplied together")
    if (args.arch == "mips64") != bool(args.softfp_build):
        raise ValueError("MIPS64 requires its pinned binary128 supplement; other profiles reject it")
    out = args.output.resolve()
    if out == ROOT or ROOT.is_relative_to(out) or out.is_relative_to(ROOT):
        raise ValueError("output must be outside the OS source tree")
    out.mkdir(parents=True, exist_ok=False)
    record = dict(schema=1, status="preparing", arch=args.arch, mode=args.mode,
                  sdk_abi=None, native_init_profile=None,
                  musl_mode=args.musl_mode, sdk_only=True, kernel_source_compiled=False,
                  guest_executed=False, native_execution_accepted=False,
                  physical=False, smp=False, full_service_manager=False,
                  inputs={}, commands=[], scope="native PID 1 foreground supervisor and adopted orphan on one QEMU CPU")
    source = ROOT
    consumer = out / "ObfuscationOS"
    sdk = out / "sdk"
    musl = out / "musl-build"
    process = None
    serial = bytearray()
    disk = None
    env = os.environ.copy()
    for key in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH",
                "GCC_EXEC_PREFIX", "COMPILER_PATH"):
        env.pop(key, None)
    env.update(XMAKE_ROOT="y", XMAKE_GLOBALDIR=str(out / "xmake-global"),
               PYTHONDONTWRITEBYTECODE="1")

    def write_record() -> None:
        save(out / "result.json", record)

    def pin(path: Path, expected: str | None = None) -> str:
        path = path.resolve()
        digest = sha(path)
        if expected is not None:
            require_hash(path, expected, str(path))
        old = record["inputs"].get(str(path))
        if old is not None and old != digest:
            raise ValueError("input changed between uses: " + str(path))
        record["inputs"][str(path)] = digest
        return digest

    def call(label: str, command: list, capture: bool = False) -> bytes:
        command = list(map(str, command))
        row = dict(label=label, argv=command, status="running")
        record["commands"].append(row)
        record["status"] = "running-" + label
        write_record()
        start = time.monotonic()
        with (out / (label + ".log")).open("xb") as log:
            result = subprocess.run(command, cwd=consumer, env=env,
                                    stdout=subprocess.PIPE if capture else log,
                                    stderr=log if capture else subprocess.STDOUT)
        if capture:
            (out / (label + ".stdout")).write_bytes(result.stdout)
        row.update(status="passed" if result.returncode == 0 else "failed",
                   returncode=result.returncode, seconds=time.monotonic() - start,
                   log_sha256=sha(out / (label + ".log")))
        write_record()
        if result.returncode:
            raise RuntimeError(label + " failed; retained log contains diagnostics")
        return result.stdout if capture else b""

    write_record()
    try:
        files = admit_source(source, args.source_inventory, args.source_inventory_sha256)
        pin(args.source_inventory, args.source_inventory_sha256)
        copy_inventory(source, consumer, files)
        for name, digest in files.items():
            pin(source / name, digest)
            pin(consumer / name, digest)
        toolchain = args.toolchain.resolve()
        triple = ARCH_TRIPLES[args.arch]
        compiler = toolchain / "bin" / (triple + "-g++")
        c_compiler = toolchain / "bin" / (triple + "-gcc")
        pin(compiler, args.compiler_sha256)
        pin(args.qemu, args.qemu_sha256)
        for name in ("gcc", "g++", "as", "ld", "ar", "ranlib", "readelf", "objcopy"):
            pin(toolchain / "bin" / (triple + "-" + name))
        for name in ("xmake", "python3", "mke2fs", "e2fsck"):
            installed = shutil.which(name)
            if installed is None:
                raise ValueError("required program is missing: " + name)
            pin(Path(installed))
        original_sdk = args.kernel_sdk.resolve()
        pin(original_sdk / "manifest.json", args.sdk_manifest_sha256)
        manifest = validate_sdk(original_sdk, args.arch, args.mode, compiler)
        record["sdk_abi"] = manifest["abi_version"]
        record["native_init_profile"] = manifest["native_init_profile"]
        write_record()
        if manifest["compiler"].get("family") != "gcc":
            raise ValueError("native extension SDK requires GCC")
        sdk_files = {**manifest["files"], "manifest.json": args.sdk_manifest_sha256}
        copy_inventory(original_sdk, sdk, sdk_files)
        validate_sdk(sdk, args.arch, args.mode, compiler)
        for name, digest in sdk_files.items():
            pin(original_sdk / name, digest)
            pin(sdk / name, digest)
        original_musl = args.musl_build.resolve()
        pin(original_musl / "manifest.json", args.musl_manifest_sha256)
        musl_manifest = admit_musl_build(original_musl, args.arch)
        if (musl_manifest.get("mode") != args.musl_mode or
                musl_manifest["compiler"]["triple"] != manifest["triple"] or
                musl_manifest["compiler"]["version"] != manifest["compiler"]["version"]):
            raise ValueError("pinned musl mode or compiler differs from SDK")
        musl_files = {name: digest for name, digest in musl_manifest["files"].items()
                      if name.startswith("sysroot/")}
        musl_files["manifest.json"] = args.musl_manifest_sha256
        copy_inventory(original_musl, musl, musl_files)
        admit_musl_build(musl, args.arch)
        for name, digest in musl_files.items():
            pin(original_musl / name, digest)
            pin(musl / name, digest)
        for name, digest in musl_manifest["tool_sha256"].items():
            pin(toolchain / "bin" / (triple + "-" + name), digest)
        runtime = subprocess.check_output([str(c_compiler), *FLAGS[args.arch],
                                           "-print-libgcc-file-name"], env=env, text=True).strip()
        pin(Path(runtime), musl_manifest["compiler_runtime"]["sha256"])
        frontend = ppc_frontend(args.arch, args.ppc_clang, required=True)
        if frontend:
            pin(Path(frontend["path"]), frontend["sha256"])
        extra = []
        if args.softfp_build:
            supplement = args.softfp_build.resolve()
            pin(supplement / "manifest.json", args.softfp_manifest_sha256)
            _, supplement_manifest = admit_softfp(supplement, args.softfp_manifest_sha256,
                                                  args.arch, args.musl_mode, c_compiler)
            retained = out / "softfp-build"
            supplement_files = {**supplement_manifest["files"], "manifest.json": args.softfp_manifest_sha256}
            copy_inventory(supplement, retained, supplement_files)
            admit_softfp(retained, args.softfp_manifest_sha256, args.arch, args.musl_mode, c_compiler)
            for name, digest in supplement_files.items():
                pin(supplement / name, digest)
                pin(retained / name, digest)
            extra = ["--softfp-build", retained, "--softfp-manifest-sha256", args.softfp_manifest_sha256]
        guests = out / "guests"
        call("musl-build", [shutil.which("xmake"), "musl-pid1-guests",
             "--arch=" + args.arch, "--musl-build=" + str(musl),
             "--toolchain=" + str(toolchain), "--out=" + str(guests),
             *(["--softfp-build=" + str(extra[1]),
                "--softfp-manifest-sha256=" + str(extra[3])] if extra else []),
             *(["--ppc-clang=" + str(args.ppc_clang.resolve())] if args.ppc_clang else [])])
        guest_sources = {"production-init": "apps/init/pid1.c",
                         "test-init": "tests/musl/pid1_init.c",
                         "test-service": "tests/musl/pid1_service.c"}
        record["guests"] = {}
        for name, relative in guest_sources.items():
            source_path = consumer / relative
            probe = guests / name
            probe_manifest = json.loads((probe / "manifest.json").read_text())
            if (probe_manifest["status"] != "built-not-executed" or probe_manifest["executed"] is not False or
                    probe_manifest["probe_sha256"] != sha(source_path) or
                    probe_manifest["source_manifest_sha256"] != args.musl_manifest_sha256 or
                    probe_manifest["mode"] != args.musl_mode):
                raise ValueError(name + " musl build differs from frozen inputs")
            expected_sources = {relative}
            if name in ("production-init", "test-init"):
                expected_sources.update({"apps/init/pid1.c", "apps/init/pid1_policy.h"})
            bound = probe_manifest.get("project_source_dependencies")
            if (not isinstance(bound, dict) or set(bound) != expected_sources or
                    any(sha(consumer / path) != digest for path, digest in bound.items())):
                raise ValueError(name + " compiler source dependency binding differs from frozen inputs")
            elf = probe / "bootstrap.elf"
            pin(elf, probe_manifest["elf_sha256"])
            pin(probe / "manifest.json")
            inspect_elf(elf, args.arch)
            if elf.read_bytes()[7] != 3:
                raise ValueError(name + " lacks explicit Linux OSABI")
            deps = dependencies(probe_manifest["commands"][0], source_path, (consumer, musl))
            depfile = out / (name + "-dependencies.json")
            save(depfile, deps)
            pin(depfile)
            for dependency, digest in deps["files"].items():
                pin(Path(dependency), digest)
            record["guests"][name] = {"elf_sha256": probe_manifest["elf_sha256"],
                                       "manifest_sha256": sha(probe / "manifest.json"),
                                       "dependencies_sha256": sha(depfile)}
        xmake = shutil.which("xmake")
        production = guests / "production-init"
        production_manifest_sha256 = sha(production / "manifest.json")
        call("os-configure", [xmake, "f", "-P", consumer, "-c", "-y", "-a", args.arch,
             "-m", args.mode, "--systoolchain_dir=" + str(toolchain),
             "--kernel_sdk=" + str(sdk),
             "--managed_init_build=" + str(production),
             "--managed_init_manifest_sha256=" + production_manifest_sha256,
             "--ccache=n"])
        for target in ("distro_image", "rootfs-stage"):
            call("os-" + target, [xmake, "build", "-P", consumer, "-j2", "-v", target])
        built = consumer / "build" / args.arch / args.mode
        if sha(built / "rootfs/init") != sha(production / "bootstrap.elf"):
            raise ValueError("production rootfs init differs from pinned musl supervisor")
        record["production_rootfs_init_sha256"] = sha(built / "rootfs/init")
        image = out / "kernel-input.bin"
        shutil.copy2(built / "distro/kernel.bin", image)
        pin(image)
        pin(built / "distro/kernel.elf")
        root = out / "root"
        shutil.copytree(built / "rootfs", root, symlinks=True)
        test_init = guests / "test-init/bootstrap.elf"
        test_service = guests / "test-service/bootstrap.elf"
        shutil.copy2(test_init, root / "init")
        (root / "init").chmod(0o755)
        shutil.copy2(test_service, root / "bin/pid1-service")
        (root / "bin/pid1-service").chmod(0o755)
        record["rootfs_files"] = {
            str(path.relative_to(root)): ({"symlink": os.readlink(path)} if path.is_symlink()
                                           else {"sha256": sha(path)})
            for path in sorted(root.rglob("*")) if path.is_file() or path.is_symlink()}
        if (record["rootfs_files"].get("init") != {"sha256": sha(test_init)} or
                record["rootfs_files"].get("bin/pid1-service") != {"sha256": sha(test_service)}):
            raise ValueError("boot /init differs from pinned musl ELF")
        disk = out / "rootfs.ext4.img"
        call("package", [sys.executable, "-B", consumer / "tools/mkext4.py", "--root", root,
             "--out", disk])
        call("initial-fsck", ["e2fsck", "-fn", disk])
        shutil.copy2(disk, out / "rootfs-input.ext4.img")
        pin(out / "rootfs-input.ext4.img")
        for name, digest in record["inputs"].items():
            require_hash(Path(name), digest, "pre-execution input " + name)
        command = qemu_command(args.qemu.resolve(), args.arch, image, disk)
        record.update(status="running-guest", qemu_command=command)
        write_record()
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if not select.select([process.stdout], [], [], .1)[0]:
                continue
            data = os.read(process.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError("QEMU exited before guest completion")
            serial.extend(data)
            if len(serial) > 16 * 1024 * 1024:
                raise RuntimeError("guest serial exceeds evidence budget")
            if any(token in serial for token in FAILURES):
                record["guest_executed"] = b"PID1_" in serial
                raise RuntimeError("guest or kernel failure marker")
            terminal = inspect_terminal(bytes(serial), PASS, args.arch)
            if terminal is not None:
                record["guest_executed"] = True
                record["terminal_retirement"] = terminal
                break
        else:
            raise RuntimeError("guest timed out")
        record["execution"] = validate_execution(bytes(serial))
        record["status"] = "guest-passed-awaiting-offline"
    except BaseException as error:
        record.update(status="failed", error=repr(error))
        raise
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            serial.extend(process.stdout.read())
            process.stdout.close()
            record["qemu_returncode"] = process.returncode
        (out / "serial.log").write_bytes(serial)
        record["serial_sha256"] = sha(out / "serial.log")
        if disk is not None and disk.is_file():
            record["final_disk_sha256"] = sha(disk)
            if consumer.is_dir():
                require_final_fsck(record, lambda: call("final-fsck", ["e2fsck", "-fn", disk]), write_record)
            else:
                write_record()
        else:
            write_record()
    try:
        record["execution"] = validate_execution(bytes(serial))
        if inspect_terminal(bytes(serial), PASS, args.arch, complete=True) != record["terminal_retirement"]:
            raise ValueError("terminal retirement changed during QEMU termination")
        for name, digest in record["inputs"].items():
            require_hash(Path(name), digest, "final input " + name)
        admit_source(source, args.source_inventory, args.source_inventory_sha256)
        record.update(status="passed", native_execution_accepted=True, inputs_rechecked=True,
                      outputs={str(path.relative_to(out)): sha(path) for path in sorted(out.rglob("*"))
                               if path.is_file() and not path.is_symlink() and path != out / "result.json"})
    except BaseException as error:
        record.update(status="failed", error=repr(error))
        raise
    finally:
        write_record()
    print("PASS", args.arch, args.mode, record["execution"]["orphan_pid"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--output", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--arch", choices=tuple(ARCH_TRIPLES), required=True)
    execute.add_argument("--mode", choices=("debug", "release"), required=True)
    execute.add_argument("--musl-mode", choices=("debug",), required=True)
    for name in ("kernel-sdk", "toolchain", "qemu", "musl-build", "source-inventory", "output"):
        execute.add_argument("--" + name, type=Path, required=True)
    for name in ("sdk-manifest-sha256", "compiler-sha256", "qemu-sha256",
                 "musl-manifest-sha256", "source-inventory-sha256"):
        execute.add_argument("--" + name, required=True)
    execute.add_argument("--softfp-build", type=Path)
    execute.add_argument("--softfp-manifest-sha256")
    execute.add_argument("--ppc-clang", type=Path)
    execute.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.command == "freeze":
        with args.output.open("x") as stream:
            json.dump(dict(schema=1, scope="native-pid1-supervisor-sdk34-os-sources", files=source_files(ROOT)),
                      stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(sha(args.output))
    else:
        if not 0 < args.timeout <= 600:
            raise ValueError("timeout must be in (0, 600] seconds")
        run(args)


if __name__ == "__main__":
    main()
