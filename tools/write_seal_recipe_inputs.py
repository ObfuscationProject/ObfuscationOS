"""Source-only SDK65 recipe admission draft; review and execution remain pending.

These checks consume future build/package receipts. They do not build, certify,
seal or compose source. Receipt truthfulness needs independent qualification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

from kernel_sdk import (ARCH_TRIPLES, contract_declaration_values,
                        shared_file_contract_code, validate_sdk)
from musl_source import inspect_elf

OS = Path(__file__).resolve().parents[1]
ARCHES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc")
MUSL_ARCHES = ("x86_64", "aarch64", "rv64", "loongarch64")
AUDITED_MANIFEST = "7f2c2ab59282578af718a4a92df3f2133f272a3b64a13bfcc568054191ddfca2"
BASE_MANIFEST = "1f5cd6e94b553f10a881492dcfe1102eaa127ed9302a8b98162a4ef32c98cf06"
PROFILE = "bootcpu-volatile-sealed-size-write-eager-pages-v2"
PROBE_SOURCES = {
    "shared_files_probe.c": "ba873b8229a5c2003c611b3b503e497ed188aa50a6b57b5d41cb8dc55ec5b04f",
    "shared_rights_probe.c": "8ec7fb63b5aa7b93551bb11e62e93346b5dc25d19398b4aa4f482791d4cb55d9",
    "shared_write_seal_probe.c": "320293baba94d669fe29e15593f13bbea7b1e1bf932bc33c3c7ddd545efca8c0",
    "shared_files_suite_runner.c": "ba06aa533e4e528e62454b751cc4e36ab8a14c8eb48526d9feb057af807dfcd9",
}
ARTIFACTS = {
    "shared-files-native": ("shared_files_probe.c", 0),
    "shared-rights-native": ("shared_rights_probe.c", 0),
    "shared-write-seal-native": ("shared_write_seal_probe.c", 0),
    "shared-write-seal-suite": ("shared_write_seal_suite_runner.c", 0),
    "shared-files-suite": ("shared_files_suite_runner.c", 0),
    "shared-files-static": ("shared_files_probe.c", 3),
    "shared-rights-static": ("shared_rights_probe.c", 3),
    "shared-write-seal-static": ("shared_write_seal_probe.c", 3),
}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> dict:
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    value = json.loads(path.read_text(), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("receipt must be an object")
    return value


def pin(path: Path) -> dict:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("input must be an explicit absolute canonical path: " + str(path))
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("input must be a regular file: " + str(path))
    return {"path": str(path), "sha256": sha(path), "mode": oct(stat.S_IMODE(info.st_mode)), "size": info.st_size}


def admit_pin(value: dict, tracked: dict) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "mode", "size"}:
        raise ValueError("exact path/hash/mode/size pin required")
    path = Path(value["path"])
    if pin(path) != value:
        raise ValueError("input pin mismatch: " + str(path))
    prior = tracked.setdefault(str(path), value)
    if prior != value:
        raise ValueError("conflicting input pins")
    return path


def require(record: dict, expected: dict) -> None:
    for key, value in expected.items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError("input contract mismatch: " + key)


def closure(value: dict, tracked: dict) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError("explicit nonempty input/log closure required")
    for entry in value.values():
        admit_pin(entry, tracked)


def declaration(path: Path, name: str, kind: str, expected: str) -> None:
    code = shared_file_contract_code(path.read_text())
    pattern = (rf"^[ \t]*inline[ \t]+constexpr[ \t]+{kind}[ \t]+{name}"
               rf"[ \t]*=[ \t]*([0-9]+)[ \t]*;[ \t]*$")
    if contract_declaration_values(code, name, pattern) != [expected]:
        raise ValueError("current SDK declaration mismatch: " + name)


def admit_inputs(args) -> dict:
    if set(ARCH_TRIPLES) != set(ARCHES):
        raise ValueError("ten-architecture consumer matrix changed")
    if args.expected_abi != 65 or args.profile == "paired" and args.arch not in MUSL_ARCHES:
        raise ValueError("require ABI65 and an explicitly supplied paired musl profile")
    tracked = {}
    contract_pin = pin(args.inputs)
    admit_pin(contract_pin, tracked)
    contract = load(args.inputs)
    common = {"abi_version": 65, "architecture": args.arch, "mode": args.mode}
    require(contract, {"schema": 1, "kind": "sdk65-write-seal-execution-inputs-v1",
                       "profile": args.profile, **common})
    files = contract["files"]
    if set(files) != {"qemu", "kernel", "rootfs", "sdk_manifest"}:
        raise ValueError("unexpected or missing named launch input")
    build_root = Path(contract["fresh_build_root"])
    if (not build_root.is_absolute() or build_root.resolve(strict=True) != build_root or
            not build_root.is_dir() or OS.is_relative_to(build_root)):
        raise ValueError("explicit separate fresh build root required")
    for role, supplied in (("qemu", args.qemu), ("kernel", args.kernel),
                           ("rootfs", args.rootfs), ("sdk_manifest", args.kernel_sdk / "manifest.json")):
        if admit_pin(files[role], tracked) != supplied:
            raise ValueError("explicit CLI input differs from contract: " + role)
        if role != "qemu" and not supplied.is_relative_to(build_root):
            raise ValueError("SDK/kernel/rootfs must come from this fresh build root")
    if not int(files["qemu"]["mode"], 8) & 0o111:
        raise ValueError("QEMU must be an explicit executable file")
    composition_path = admit_pin(contract["composition"], tracked)
    composition = load(composition_path)
    require(composition, {"schema": 1, "kind": "sdk65-composition-review-v1",
                          "status": "independently-reviewed", "abi_version": 65,
                          "audited_write_seal_manifest_sha256": AUDITED_MANIFEST})
    # Composition belongs to a separate ABI owner. Pin their actual overlay and
    # source inventory; a SDK64 tree relabelled by this recipe cannot qualify.
    base_manifest = admit_pin(composition["base_source_manifest"], tracked)
    if sha(base_manifest) != BASE_MANIFEST:
        raise ValueError("recipe requires the exact qualified SDK64 source base")
    admit_pin(composition["abi_overlay_manifest"], tracked)
    source_inventory = admit_pin(composition["source_manifest"], tracked)
    sources = load(source_inventory)["files"]
    closure(sources, tracked)
    for relative in ("scripts/observe_shared_write_seal_qemu.py", "scripts/qemu_distro.py",
                     "tools/write_seal_recipe_inputs.py", "tools/kernel_sdk.py", "tools/musl_source.py",
                     "tools/plan_ledger.py", "docs/plans/contracts/ledger.json",
                     "xmake/shared_files_fixture.lua", "apps/oksh/main.c"):
        if admit_pin(sources["ObfuscationOS/" + relative], tracked) != OS / relative:
            raise ValueError("observer must run from the reviewed composed OS source")
    sdk = validate_sdk(args.kernel_sdk, args.arch, args.mode)
    require(sdk, {"abi_version": 65, "arch": args.arch, "mode": args.mode,
                  "native_shared_file_profile": PROFILE, "linux_shared_file_profile": PROFILE})
    shared_header = args.kernel_sdk / "include/ok/user/native_shared_files_sdk_profile.hpp"
    declaration(args.kernel_sdk / "include/ok/core/module.hpp", "kernel_module_abi_version", "u32", "65")
    declaration(shared_header, "native_shared_file_module_abi", "u32", "65")
    declaration(shared_header, "native_shared_file_supported_seals", "u32", "15")
    # validate_sdk checks global ABI, all profiles and header hashes. Retain the
    # complete SDK file inventory for the final unchanged-input comparison.
    for relative in sdk["files"]:
        path = args.kernel_sdk / relative
        admit_pin(pin(path), tracked)
    identity = {**common, "sdk_manifest_sha256": files["sdk_manifest"]["sha256"],
                "source_manifest_sha256": sha(source_inventory),
                "composition_sha256": sha(composition_path), "triple": sdk["triple"],
                "compiler_abi": sdk["compiler"]}
    for role in ("sdk_build", "kernel_build"):
        receipt_path = admit_pin(contract[role], tracked)
        if not receipt_path.is_relative_to(build_root):
            raise ValueError("build receipt is outside the fresh build root")
        receipt = load(receipt_path)
        require(receipt, {"schema": 1, "kind": "sdk65-fresh-build-v1",
                          "status": "built-not-executed", "executed": False, **identity})
        if role == "kernel_build":
            require(receipt, {"output_sha256": files["kernel"]["sha256"],
                              "link_source": "exported-sdk-only", "no_kernel_checkout": True})
            if receipt["build_inputs"].get("sdk_manifest") != files["sdk_manifest"]:
                raise ValueError("OS image must link only the explicitly selected SDK")
        else:
            require(receipt, {"output_sha256": files["sdk_manifest"]["sha256"]})
        closure(receipt["build_inputs"], tracked)
        closure(receipt["build_logs"], tracked)
        if not receipt.get("commands"):
            raise ValueError("actual build command record missing")
    names = set(ARTIFACTS) if args.profile == "paired" else {
        "shared-files-native", "shared-rights-native", "shared-write-seal-native", "shared-write-seal-suite"}
    if set(contract["artifacts"]) != names:
        raise ValueError("artifact set differs from selected suite; no implicit artifacts")
    destinations = {}
    for name in sorted(names):
        entry = contract["artifacts"][name]
        executable = admit_pin(entry["elf"], tracked)
        receipt_path = admit_pin(entry["build_receipt"], tracked)
        if not executable.is_relative_to(build_root) or not receipt_path.is_relative_to(build_root):
            raise ValueError("probe/runner and build receipt must be freshly built for this row")
        receipt = load(receipt_path)
        source_name, osabi = ARTIFACTS[name]
        source = OS / "tests/native" / source_name
        if admit_pin(sources["ObfuscationOS/tests/native/" + source_name], tracked) != source:
            raise ValueError("wrong current probe or driver source")
        if source_name in PROBE_SOURCES and sha(source) != PROBE_SOURCES[source_name]:
            raise ValueError("probe source differs from exact audited/base input")
        require(receipt, {"schema": 1, "kind": "sdk65-fresh-probe-build-v1", "artifact": name,
                          "status": "built-not-executed", "executed": False,
                          "source_sha256": sha(source), "elf_sha256": sha(executable),
                          "elf_osabi": osabi, **identity})
        closure(receipt["build_inputs"], tracked)
        closure(receipt["build_logs"], tracked)
        build_inputs = receipt["build_inputs"]
        for key in ("source", "sdk_manifest", "compiler", "linker"):
            if key not in build_inputs:
                raise ValueError("missing named build input: " + key)
        if (build_inputs["source"] != pin(source) or
                build_inputs["sdk_manifest"] != files["sdk_manifest"]):
            raise ValueError("build input closure omits the actual source/SDK")
        if not receipt.get("commands") or receipt.get("dependency_capture") != "compiler-and-linker-inputs":
            raise ValueError("actual build commands and full dependency input record required")
        if osabi == 0:
            require(receipt, {"target": "app-" + name,
                              "sdk_fingerprint": "OK_KERNEL_SDK_FINGERPRINT_" + files["sdk_manifest"]["sha256"]})
            for key in ("fixture", "crt0", "okcrt", "okcrt_receipt", "libgcc"):
                if key not in build_inputs:
                    raise ValueError("missing native link input: " + key)
            if build_inputs["fixture"] != pin(OS / "xmake/shared_files_fixture.lua"):
                raise ValueError("native build did not select the reviewed fixture")
            crt = load(Path(build_inputs["okcrt_receipt"]["path"]))
            require(crt, {"kind": "sdk65-fresh-okcrt-build-v1", "status": "built-not-executed",
                          "executed": False, "output_sha256": build_inputs["okcrt"]["sha256"], **identity})
            if (not Path(build_inputs["okcrt"]["path"]).is_relative_to(build_root) or
                    not Path(build_inputs["okcrt_receipt"]["path"]).is_relative_to(build_root)):
                raise ValueError("okcrt must be rebuilt against this row's SDK65")
            closure(crt["build_inputs"], tracked)
            closure(crt["build_logs"], tracked)
            if not crt.get("commands") or crt["build_inputs"].get("sdk_manifest") != files["sdk_manifest"]:
                raise ValueError("okcrt build lacks exact SDK65 input and command record")
        else:
            # Ordinary builder manifests alone lack the SDK65/kernel binding.
            # Require them in addition to the future recipe build receipt.
            musl_path = admit_pin(entry["musl_manifest"], tracked)
            musl = load(musl_path)
            require(musl, {"architecture": args.arch, "mode": args.mode,
                           "status": "built-not-executed", "native_execution": False, "version": "1.2.5"})
            sysroot_files = musl.get("files", {})
            for relative in ("sysroot/usr/lib/crt1.o", "sysroot/usr/lib/crti.o",
                             "sysroot/usr/lib/crtn.o", "sysroot/usr/lib/libc.a",
                             "sysroot/usr/include/unistd.h", "sysroot/usr/include/errno.h"):
                if relative not in sysroot_files:
                    raise ValueError("musl manifest lacks required startup/libc/header input")
            for relative, digest in sysroot_files.items():
                if not relative.startswith("sysroot/"):
                    continue
                artifact = musl_path.parent / relative
                if not artifact.resolve().is_relative_to(musl_path.parent):
                    raise ValueError("musl manifest input escapes its build root")
                entry_pin = pin(artifact)
                if entry_pin["sha256"] != digest:
                    raise ValueError("musl sysroot hash mismatch")
                admit_pin(entry_pin, tracked)
            for key in ("linker_script", "libc", "crt1", "crti", "crtn", "libgcc", "link_driver", "assembler"):
                if key not in build_inputs:
                    raise ValueError("missing static link input: " + key)
            builder_path = admit_pin(entry["builder_manifest"], tracked)
            if not builder_path.is_relative_to(build_root):
                raise ValueError("static probe builder manifest must be from this fresh row")
            raw = load(builder_path)
            require(raw, {"architecture": args.arch, "mode": args.mode, "status": "built-not-executed",
                          "executed": False, "probe_sha256": sha(source), "elf_sha256": sha(executable),
                          "source_manifest_sha256": sha(musl_path)})
            require(receipt, {"musl_manifest_sha256": sha(musl_path)})
            dependencies = raw.get("compile_dependencies")
            if not isinstance(dependencies, dict):
                raise ValueError("static builder must capture real compile dependencies")
            require(dependencies, {"compiler_generated": True, "includes_system_headers": True,
                                   "same_command_as_object": True, "captured_after_object_compilation": True,
                                   "source": str(source)})
            if str(source) not in dependencies["files"]:
                raise ValueError("static compile dependency closure omits the source")
            for filename, expected in dependencies["files"].items():
                actual = pin(Path(filename))
                if {"sha256": actual["sha256"], "mode": actual["mode"]} != expected:
                    raise ValueError("static compile dependency changed")
                admit_pin(actual, tracked)
            depfile = dependencies["depfile"]
            actual = pin(Path(depfile["path"]))
            if {key: actual[key] for key in ("path", "sha256", "mode")} != depfile:
                raise ValueError("static compiler dependency record changed")
            admit_pin(actual, tracked)
            for key, relative in (("libc", "sysroot/usr/lib/libc.a"), ("crt1", "sysroot/usr/lib/crt1.o"),
                                  ("crti", "sysroot/usr/lib/crti.o"), ("crtn", "sysroot/usr/lib/crtn.o")):
                if build_inputs[key] != pin(musl_path.parent / relative):
                    raise ValueError("static link input differs from admitted musl sysroot")
        inspect_elf(executable, args.arch)
        with executable.open("rb") as stream:
            if stream.read(16)[7] != osabi:
                raise ValueError("ELF syscall personality differs: " + name)
        destinations["/bin/" + name] = {"sha256": sha(executable), "mode": "0o755"}
    package_path = admit_pin(contract["package_receipt"], tracked)
    if not package_path.is_relative_to(build_root):
        raise ValueError("package receipt must belong to the fresh build root")
    package = load(package_path)
    require(package, {"schema": 1, "kind": "sdk65-write-seal-package-v1",
                      "status": "packaged-not-executed", "executed": False,
                      "profile": args.profile, "filesystem": "ext4",
                      "rootfs_sha256": files["rootfs"]["sha256"],
                      "kernel_sha256": files["kernel"]["sha256"],
                      "suite_entries": destinations, "all_userland_rebuilt": True,
                      "image_entries_verified": True, "journal": "none",
                      "execution_scope": "bootstrap-privileged-not-isolated-desktop", **identity})
    closure(package["package_inputs"], tracked)
    closure(package["package_logs"], tracked)
    if not package.get("commands") or "image_entry_inspection" not in package["package_logs"]:
        raise ValueError("actual packaging commands and image-entry inspection log required")
    return {"files": files, "sdk": sdk, "tracked_inputs": tracked,
            "contract_sha256": contract_pin["sha256"], "profile": args.profile,
            "scope": "bootstrap-privileged-not-isolated-desktop"}


def verify_inputs(record: dict) -> None:
    for entry in record["tracked_inputs"].values():
        if pin(Path(entry["path"])) != entry:
            raise ValueError("input changed during observation: " + entry["path"])
