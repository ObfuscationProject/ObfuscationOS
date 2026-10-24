#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path
from service_manifest_config import snapshot as service_config_snapshot
from console_login_disk import CHECKPOINT0, SERVICES as CONSOLE_SERVICES, hosts_snapshot


APPS = (
    "init",
    "oksh",
    "posix-check",
    "udp-probe",
    "hello",
    "cat",
    "ls",
    "stat",
    "mkdir",
    "rm",
    "mv",
    "ln",
    "pwd",
    "whoami",
    "uname",
    "uptime",
    "touch",
    "settings",
    "tasks",
    "notes",
    "about",
    "sync",
    "kmodload",
    "service-ctl",
    "logd",
    "logger",
    "timed",
    "timectl",
    "mountctl",
    "resolved",
    "resolvectl",
)


OS_RELEASE = """NAME=ObfuscationOS
ID=obfuscationos
VERSION_ID=0.1.0-userland
PRETTY_NAME="ObfuscationOS userland MVP"
"""

# Enrollment is explicit. Images never contain an imported account or password.
ACCOUNT_DATABASE_SEED = b"OKACCOUNTS 1\nstate unconfigured\n"

ELF_PROFILES = {
    "i386": (1, 1, 3), "x86_64": (2, 1, 62),
    "aarch64": (2, 1, 183), "arm32": (1, 1, 40),
    "rv64": (2, 1, 243), "rv32": (1, 1, 243),
    "loongarch64": (2, 1, 258), "mips": (1, 2, 8),
    "mips64": (2, 2, 8), "ppc": (1, 2, 20),
}


def inspect_managed_init_elf(payload: bytes, arch: str) -> dict:
    """Verify a static Linux executable independently of its build manifest."""
    if arch not in ELF_PROFILES:
        raise ValueError("unsupported managed init architecture")
    elf_class, byte_order, machine = ELF_PROFILES[arch]
    header_size = 52 if elf_class == 1 else 64
    ph_size = 32 if elf_class == 1 else 56
    abi_version = 1 if arch in ("mips", "mips64") else 0
    if (len(payload) < header_size or payload[:7] != b"\x7fELF" +
            bytes((elf_class, byte_order, 1)) or payload[7:9] != bytes((3, abi_version))):
        raise ValueError("managed init ELF class, endian, version or Linux personality mismatch")
    endian = "<" if byte_order == 1 else ">"
    elf_type, actual_machine, version = struct.unpack_from(endian + "HHI", payload, 16)
    if elf_type != 2 or actual_machine != machine or version != 1:
        raise ValueError("managed init ELF type or machine mismatch")
    if elf_class == 1:
        entry, phoff = struct.unpack_from(endian + "II", payload, 24)
        ehsize, phentsize, phnum = struct.unpack_from(endian + "HHH", payload, 40)
    else:
        entry, phoff = struct.unpack_from(endian + "QQ", payload, 24)
        ehsize, phentsize, phnum = struct.unpack_from(endian + "HHH", payload, 52)
    if (ehsize != header_size or phentsize != ph_size or phnum == 0 or phnum > 128 or
            phoff < header_size or phoff + phentsize * phnum > len(payload)):
        raise ValueError("managed init ELF program header table is invalid")
    load_count = 0
    executable_entry = False
    for index in range(phnum):
        offset = phoff + index * phentsize
        if elf_class == 1:
            kind, file_offset, vaddr, _, file_size, mem_size, flags, alignment = struct.unpack_from(
                endian + "IIIIIIII", payload, offset)
        else:
            kind, flags, file_offset, vaddr, _, file_size, mem_size, alignment = struct.unpack_from(
                endian + "IIQQQQQQ", payload, offset)
        if kind in (2, 3):
            raise ValueError("managed init ELF must be static and have no interpreter")
        if kind != 1:
            continue
        load_count += 1
        if (file_size > mem_size or file_offset + file_size > len(payload) or
                mem_size > ((1 << (32 if elf_class == 1 else 64)) - 1) - vaddr or
                (alignment not in (0, 1) and
                 (alignment & (alignment - 1) or vaddr % alignment != file_offset % alignment))):
            raise ValueError("managed init ELF load segment is invalid")
        if flags & 1 and vaddr <= entry < vaddr + file_size:
            executable_entry = True
    if not load_count or not executable_entry:
        raise ValueError("managed init ELF lacks an executable entry in PT_LOAD")
    return {"class": 32 if elf_class == 1 else 64,
            "byte_order": "little" if byte_order == 1 else "big",
            "machine": machine, "type": "ET_EXEC", "interpreter": None, "executed": False}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apps-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--managed-init-build", type=Path)
    parser.add_argument("--managed-init-manifest-sha256")
    parser.add_argument("--service-graph-build", type=Path)
    parser.add_argument("--service-graph-manifest-sha256")
    parser.add_argument("--arch")
    parser.add_argument("--console-login", action="store_true")
    args = parser.parse_args()

    if bool(args.managed_init_build) != bool(args.managed_init_manifest_sha256):
        raise SystemExit("managed init build and exact manifest hash must be supplied together")
    if bool(args.service_graph_build) != bool(args.service_graph_manifest_sha256):
        raise SystemExit("service graph build and exact manifest hash must be supplied together")
    if args.managed_init_build and args.service_graph_build:
        raise SystemExit("only one explicit production init profile may be installed")
    if args.console_login and (args.managed_init_build or args.service_graph_build):
        raise SystemExit("native console login requires the ordinary native PID1")
    project = Path(__file__).resolve().parent.parent
    service_config = service_config_snapshot(project / "config" /
        ("services-login.conf" if args.console_login else "services.conf"))
    if args.console_login and service_config != CONSOLE_SERVICES:
        raise SystemExit("native console login requires the exact selected service configuration")
    hosts = hosts_snapshot(project / "config/hosts")
    apps = APPS + ("login",) if args.console_login else APPS
    managed_elf = None
    if args.managed_init_build:
        if not args.arch:
            raise SystemExit("managed init requires an explicit architecture")
        build = args.managed_init_build.resolve()
        manifest_path = build / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        expected = args.managed_init_manifest_sha256
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or hashlib.sha256(manifest_bytes).hexdigest() != expected:
            raise SystemExit("managed init manifest hash mismatch")
        manifest = json.loads(manifest_bytes)
        project = Path(__file__).resolve().parent.parent
        source = project / "apps/init/pid1.c"
        policy = project / "apps/init/pid1_policy.h"
        linker = project / "tests/musl/bootstrap.ld"
        dependencies = manifest.get("project_source_dependencies")
        if (manifest.get("schema_version") != 1 or manifest.get("status") != "built-not-executed" or
                manifest.get("executed") is not False or manifest.get("architecture") != args.arch or
                manifest.get("source_mode") != "debug" or manifest.get("mode") != "debug" or
                manifest.get("probe_sha256") != hashlib.sha256(source.read_bytes()).hexdigest() or
                manifest.get("linker_script_sha256") != hashlib.sha256(linker.read_bytes()).hexdigest() or
                not isinstance(manifest.get("personality"), dict) or
                manifest["personality"].get("elf_osabi") != 3 or
                dependencies != {"apps/init/pid1.c": hashlib.sha256(source.read_bytes()).hexdigest(),
                                 "apps/init/pid1_policy.h": hashlib.sha256(policy.read_bytes()).hexdigest()}):
            raise SystemExit("managed init build is not the pinned production source/architecture/musl profile")
        managed_elf = build / "bootstrap.elf"
        payload = managed_elf.read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest.get("elf_sha256"):
            raise SystemExit("managed init ELF does not match its audited build")
        try:
            identity = inspect_managed_init_elf(payload, args.arch)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        if manifest.get("elf") != identity:
            raise SystemExit("managed init ELF identity differs from build manifest")

    if args.service_graph_build:
        from service_graph_build import admit
        if not args.arch: raise SystemExit("service graph requires an explicit architecture")
        try:
            managed_elf = admit(args.service_graph_build, args.service_graph_manifest_sha256,
                                args.arch, project, configuration=service_config)
        except ValueError as error:
            raise SystemExit(str(error)) from error

    apps_dir = Path(args.apps_dir)
    system_gui_module = project / "modules" / "system-gui" / "system-gui.okmod"
    for app in apps:
        src = apps_dir / f"{app}.elf"
        if not src.is_file():
            raise SystemExit(f"missing app: {src}")
    if not system_gui_module.is_file():
        raise SystemExit(f"missing system GUI module package: {system_gui_module}")
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)

    bin_dir = out / "bin"
    etc_dir = out / "etc"
    modules_dir = out / "boot" / "modules"
    out.mkdir(parents=True)
    out.chmod(0o755)
    # Host umask and SGID ancestry must not choose guest directory permissions.
    for relative in ("bin", "etc", "boot", "boot/modules", "home", "root", "run", "dev", "tmp", "var", "var/log"):
        directory = out / relative
        directory.mkdir()
        directory.chmod(0o1777 if relative == "tmp" else 0o700 if relative in ("root", "var/log") else 0o755)

    for app in apps:
        src = apps_dir / f"{app}.elf"
        dst = out / "init" if app == "init" else bin_dir / app
        shutil.copy2(src, dst)
        dst.chmod(0o755)

    if managed_elf:
        shutil.copy2(managed_elf, out / "init")
        (out / "init").chmod(0o755)

    (etc_dir / "os-release").write_text(OS_RELEASE, encoding="utf-8")
    (etc_dir / "os-release").chmod(0o644)
    (etc_dir / "services.conf").write_bytes(service_config)
    (etc_dir / "services.conf").chmod(0o644)
    (etc_dir / "hosts").write_bytes(hosts)
    (etc_dir / "hosts").chmod(0o644)
    (etc_dir / "accounts.db").write_bytes(ACCOUNT_DATABASE_SEED)
    (etc_dir / "accounts.db").chmod(0o600)
    if args.console_login:
        (out / "var/log/system.log").write_bytes(CHECKPOINT0)
        (out / "var/log/system.log").chmod(0o600)
    shutil.copy2(system_gui_module, modules_dir / "system-gui.okmod")
    (modules_dir / "system-gui.okmod").chmod(0o644)
    print(f"[rootfs] staged {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
