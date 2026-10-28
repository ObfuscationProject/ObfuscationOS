#!/usr/bin/env python3
"""Validate ports/*/port.json, print the build order and build one port.

  ports.py validate            check every descriptor
  ports.py order [NAME...]     print build order for the named ports (default: all)
  ports.py build --name NAME --arch ARCH --mode MODE --archive FILE --toolchain DIR --out DIR
                 [--musl-build DIR] [--ppc-clang FILE] [--softfp-build DIR --softfp-manifest-sha256 HEX]

`build` runs the descriptor's recipe with the freestanding-GCC fallback
(tools/musl_cc.py) until the `<arch>-linux-musl` toolchain family exists. Every
input is explicit: the archive must match the descriptor pin, a dependent port
names its admitted musl build, and the output directory must be new. A failed
build keeps its logs and partial output, labelled in its manifest. Nothing here
executes target code.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PORTS = ROOT / "ports"
STATES = {"planned", "builds", "executes"}
PROFILES = {"i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"}
REQUIRED = {"name", "version", "archive", "sha256", "license", "depends", "profiles", "state", "build"}
SYSTEMS = {"musl", "kconfig", "configure", "make", "xmake"}
RECIPES = {"musl", "kconfig"}
DEFINES = ["-D__linux__=1", "-D__linux=1", "-D__unix__=1", "-D__unix=1"]
# CLONE_VM|CLONE_VFORK is not routed by the Linux personality (it returns
# ENOSYS), so ports call fork where upstream calls vfork.
PORT_CFLAGS = ["-Dvfork=fork"]
LINKER_SCRIPT = PORTS / "musl/static-exec.ld"
# The kconfig recipe sets these; a fragment may not.
RECIPE_SYMBOLS = {"CONFIG_EXTRA_CFLAGS", "CONFIG_EXTRA_LDFLAGS", "CONFIG_EXTRA_LDLIBS", "CONFIG_DEBUG",
                  "CONFIG_CROSS_COMPILER_PREFIX", "CONFIG_SYSROOT"}
# The ppc kernel admits a Linux ELF only when its section table (and the
# .gnu.attributes soft-float proof it locates) lies in this file prefix.
SECTION_TABLE_BOUND = {"ppc": 512 * 1024}
APPLET = re.compile(r"\[\[?|[a-z0-9][a-z0-9_.+-]*")


def load() -> dict[str, dict]:
    ports = {}
    for descriptor in sorted(PORTS.glob("*/port.json")):
        data = json.loads(descriptor.read_text())
        ports[descriptor.parent.name] = data
    return ports


def validate(ports: dict[str, dict]) -> list[str]:
    errors = []
    for directory, p in ports.items():
        missing = REQUIRED - set(p)
        if missing:
            errors.append(f"{directory}: missing fields {sorted(missing)}")
            continue
        if p["name"] != directory:
            errors.append(f"{directory}: name {p['name']!r} differs from directory")
        if p["sha256"] and not re.fullmatch(r"[0-9a-f]{64}", p["sha256"]):
            errors.append(f"{directory}: sha256 is not 64 hex digits")
        if not p["sha256"] and p["state"] != "planned":
            errors.append(f"{directory}: state {p['state']} requires a pinned sha256")
        if p["state"] not in STATES:
            errors.append(f"{directory}: unknown state {p['state']}")
        if p["license"] == "review" and p["state"] != "planned":
            errors.append(f"{directory}: licence under review cannot leave planned")
        if not set(p["profiles"]) <= PROFILES:
            errors.append(f"{directory}: unknown profiles {sorted(set(p['profiles']) - PROFILES)}")
        if p["state"] == "executes" and not p["profiles"]:
            errors.append(f"{directory}: executes requires at least one qualified profile")
        for dep in p["depends"]:
            if dep not in ports:
                errors.append(f"{directory}: unknown dependency {dep}")
        if p["build"].get("system") not in SYSTEMS:
            errors.append(f"{directory}: unknown build system")
        if p["build"].get("system") == "kconfig" and not (PORTS / directory / str(p["build"].get("config"))).is_file():
            errors.append(f"{directory}: kconfig build needs its config fragment")
        for patch in p["build"].get("patches", []):
            if PurePosixPath(patch).parts[:1] != ("patches",) or ".." in PurePosixPath(patch).parts or \
                    not (PORTS / directory / patch).is_file():
                errors.append(f"{directory}: patch {patch} must be a file under ports/{directory}/patches")
    return errors


def order(ports: dict[str, dict], wanted: list[str]) -> list[str]:
    result: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in result:
            return
        if name in visiting:
            raise SystemExit(f"dependency cycle through {name}")
        visiting.add(name)
        for dep in ports[name]["depends"]:
            visit(dep)
        visiting.discard(name)
        result.append(name)

    for name in wanted:
        if name not in ports:
            raise SystemExit(f"unknown port {name}")
        visit(name)
    return result


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def config_lines(text: str) -> list[str]:
    """Requested `CONFIG_X=value` lines of a kconfig fragment, in order."""
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    for line in lines:
        if not re.fullmatch(r'CONFIG_[A-Z0-9_]+=(y|[0-9]+|"[^"\\]*")', line):
            raise ValueError(f"unsupported kconfig fragment line: {line}")
    names = [line.split("=", 1)[0] for line in lines]
    if len(set(names)) != len(names):
        raise ValueError("kconfig fragment sets a symbol twice")
    if RECIPE_SYMBOLS & set(names):
        raise ValueError("kconfig fragment sets recipe-owned symbols: " + ", ".join(sorted(RECIPE_SYMBOLS & set(names))))
    return lines


def config_symbol(line: str) -> str | None:
    match = re.fullmatch(r"(CONFIG_[A-Za-z0-9_]+)=.*|# (CONFIG_[A-Za-z0-9_]+) is not set", line.strip())
    return (match.group(1) or match.group(2)) if match else None


def merge_config(text: str, requested: list[str]) -> str:
    """Set the requested symbols in a .config, appending those it omits."""
    wanted = {line.split("=", 1)[0]: line for line in requested}
    lines = [wanted.pop(config_symbol(line)) if config_symbol(line) in wanted else line for line in text.splitlines()]
    return "\n".join(lines + list(wanted.values())) + "\n"


def disable_unrequested(text: str, requested: list[str]) -> str:
    names = {line.split("=", 1)[0] for line in requested}
    return "".join(f"# {config_symbol(line)} is not set\n" if line.endswith("=y") and config_symbol(line) not in names
                   else line + "\n" for line in text.splitlines())


def resolve_config(path: Path, base: str, requested: list[str], oldconfig) -> str:
    """Requested symbols on, every other boolean off unless a `select` forces it.

    BusyBox's kconfig resets all changeable symbols in allnoconfig even after
    reading KCONFIG_ALLCONFIG, so the fragment is merged into the allnoconfig
    result and `oldconfig` (default answers) runs until nothing changes.
    """
    current, previous = merge_config(base, requested), None
    for _ in range(12):
        path.write_text(current)
        oldconfig()
        resolved = path.read_text()
        if resolved == previous:
            return resolved
        previous = resolved
        current = merge_config(disable_unrequested(resolved, requested), requested)
    raise ValueError("kconfig resolution did not converge")


def unmet_config(requested: list[str], resolved: str) -> list[str]:
    """Requested lines the resolved .config does not contain verbatim."""
    present = set(resolved.splitlines())
    return [line for line in requested if line not in present]


def applet_names(links: str) -> list[str]:
    """Basenames of a BusyBox `busybox.links` install list, all to /bin."""
    names = []
    for line in links.splitlines():
        path = PurePosixPath(line.strip())
        if not line.strip():
            continue
        if (not path.is_absolute() or path.parts[1:-1] not in (("bin",), ("sbin",), ("usr", "bin"), ("usr", "sbin"))
                or not APPLET.fullmatch(path.name) or path.name == "busybox"):
            raise ValueError(f"unexpected applet install path: {line.strip()}")
        names.append(path.name)
    if not names or len(set(names)) != len(names):
        raise ValueError("applet list is empty or names an applet twice")
    return sorted(names)


def section_table_end(data: bytes) -> int:
    """File offset just past the ELF section header table."""
    if data[4] == 1:
        offset, size, count = struct.unpack_from((">" if data[5] == 2 else "<") + "I10xHH", data, 32)
    else:
        offset, size, count = struct.unpack_from((">" if data[5] == 2 else "<") + "Q10xHH", data, 40)
    return offset + size * count


def admit_archive(path: Path, port: dict) -> str:
    """Check the pinned archive bytes and that every member stays in one tree."""
    if digest(path) != port["sha256"]:
        raise ValueError(f"{port['name']} archive checksum differs from the descriptor pin")
    top = f"{port['name']}-{port['version']}"
    seen, total = set(), 0
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or "\\" in member.name or not name.parts or
                    name.parts[0] != top or not (member.isfile() or member.isdir()) or member.name in seen):
                raise ValueError(f"unsafe or duplicate {port['name']} archive member: {member.name}")
            seen.add(member.name)
            total += member.size
            if len(seen) > 20000 or total > 256 * 1024 * 1024:
                raise ValueError(f"{port['name']} archive exceeds the source extraction budget")
    return top


def extract(path: Path, directory: Path) -> None:
    # Called only after admit_archive on the same copied bytes.
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            target = directory / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode & 0o755)


def clean_env() -> dict:
    env = os.environ.copy()
    for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "LIBRARY_PATH",
                 "GCC_EXEC_PREFIX", "COMPILER_PATH", "CFLAGS", "CPPFLAGS", "LDFLAGS", "DESTDIR", "CC",
                 "CROSS_COMPILE", "MAKEFLAGS", "MFLAGS", "KCONFIG_CONFIG", "KCONFIG_ALLCONFIG"):
        env.pop(name, None)
    env.update(LC_ALL="C", SOURCE_DATE_EPOCH="1708128000", KCONFIG_NOTIMESTAMP="1",
               PYTHONDONTWRITEBYTECODE="1")
    return env


def fallback_toolchain(toolchain: Path, arch: str) -> dict:
    """Admit the freestanding `*-elf` compiler family for one profile."""
    from kernel_sdk import ARCH_TRIPLES
    from musl_source import FLAGS, validate_build_path
    triple = ARCH_TRIPLES[arch]
    bindir = toolchain.resolve() / "bin"
    linux = next(row["linux_target"] for row in json.loads((ROOT / "docs/plans/contracts/ledger.json").read_text())
                 ["architectures"] if row["id"] == arch)
    if (bindir / f"{linux}-gcc").exists():
        raise ValueError(f"{linux}-gcc found: the hosted musl toolchain family is not wired into this recipe yet")
    tools = {}
    for tool in ("gcc", "ar", "ranlib", "strip", "nm", "objcopy", "objdump", "readelf", "as", "ld"):
        if not (bindir / f"{triple}-{tool}").is_file():
            raise ValueError(f"missing explicit cross tool: {triple}-{tool}")
        tools[tool] = digest(bindir / f"{triple}-{tool}")
    compiler = bindir / f"{triple}-gcc"
    if subprocess.check_output([str(compiler), "-dumpmachine"], text=True).strip() != triple:
        raise ValueError(f"cross compiler target is not {triple}")
    validate_build_path(toolchain.resolve())
    if arch == "ppc":
        # Soft-float callers need the soft-float libgcc; a --disable-multilib
        # powerpc-eabi GCC only has the hard-float one and cannot link them.
        multilib = subprocess.check_output([str(compiler), *FLAGS[arch], "-print-multi-directory"], text=True).strip()
        if multilib != "nof":
            raise ValueError("PowerPC ports need a powerpc-eabi GCC whose -msoft-float multilib is 'nof'")
    return {"family": "elf-fallback", "triple": triple, "linux_target": linux, "bindir": str(bindir),
            "compiler": str(compiler), "tool_sha256": tools,
            "version": subprocess.check_output([str(compiler), "-dumpfullversion"], text=True).strip()}


def driver_profile(arch: str, musl: Path, manifest: dict, toolchain: dict, frontend: dict | None,
                   supplements: list[str]) -> dict:
    abi = [flag for flag in manifest["cflags"] if flag not in ("-O2", "-g")]
    include = subprocess.check_output([toolchain["compiler"], *abi, "-print-file-name=include"], text=True).strip()
    return {"schema_version": 1, "arch": arch, "compiler": toolchain["compiler"],
            "frontend": None if frontend is None else {
                "path": frontend["path"], "flags": frontend["flags"],
                "include": subprocess.check_output([frontend["path"], "-print-resource-dir"], text=True).strip() + "/include"},
            "abi_flags": abi, "defines": DEFINES, "include": str(musl / "sysroot/usr/include"),
            "lib": str(musl / "sysroot/usr/lib"), "compiler_include": include, "ldflags": manifest["ldflags"],
            "linker_script": str(LINKER_SCRIPT), "user_base": "0x10000000" if arch in ("aarch64", "arm32") else "0x40000000",
            "supplements": supplements, "elf_abi_version": 1 if arch in ("mips", "mips64") else 0}


def build_musl(port: dict, args) -> dict:
    from musl_source import build_static, source_pin
    if port["sha256"] != source_pin()["archive_sha256"]:
        raise ValueError("musl descriptor pin differs from the ledger musl reference")
    fallback_toolchain(args.toolchain, args.arch)
    return build_static(argparse.Namespace(archive=args.archive, arch=args.arch, toolchain=args.toolchain,
                                           mode=args.mode, out=args.out, jobs=args.jobs, ppc_clang=args.ppc_clang))


def build_kconfig(port: dict, args) -> dict:
    from build_musl_probe import admit_musl_build
    from musl_source import inspect_elf, ppc_frontend, validate_build_path
    from mips64_softfp import admit as admit_softfp
    import musl_cc
    if args.musl_build is None:
        raise ValueError(f"{port['name']} needs --musl-build with the admitted musl sysroot")
    musl = args.musl_build.resolve()
    musl_manifest = admit_musl_build(musl, args.arch)
    if musl_manifest["mode"] != args.mode:
        raise ValueError("musl build mode differs from the requested port mode")
    toolchain = fallback_toolchain(args.toolchain, args.arch)
    if musl_manifest["tool_sha256"]["gcc"] != toolchain["tool_sha256"]["gcc"]:
        raise ValueError("port compiler differs from the compiler that built the admitted musl sysroot")
    frontend = ppc_frontend(args.arch, args.ppc_clang, required=True)
    if bool(args.softfp_build) != bool(args.softfp_manifest_sha256):
        raise ValueError("soft-fp build and manifest hash must be supplied together")
    if (args.arch == "mips64") != bool(args.softfp_build):
        raise ValueError("MIPS64 ports need --softfp-build; other profiles refuse it")
    supplements, softfp = [], None
    if args.softfp_build:
        archive, runtime = admit_softfp(args.softfp_build, args.softfp_manifest_sha256, args.arch,
                                        args.mode, Path(toolchain["compiler"]))
        supplements = [str(archive)]
        softfp = {"manifest_sha256": args.softfp_manifest_sha256, "archive_sha256": digest(archive),
                  "profile": runtime["profile"]}
    fragment = PORTS / port["name"] / port["build"]["config"]
    patches = [PORTS / port["name"] / patch for patch in port["build"].get("patches", [])]
    requested = config_lines(fragment.read_text()) + (["CONFIG_DEBUG=y"] if args.mode == "debug" else [])
    requested.append(f'CONFIG_EXTRA_CFLAGS="{" ".join(PORT_CFLAGS)}"')
    output = args.out.resolve()
    if output.exists() or output.is_symlink():
        raise ValueError(f"output already exists; choose a new --out directory: {output}")
    validate_build_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    host_cc = shutil.which("gcc")
    if host_cc is None:
        raise ValueError("kconfig ports need a host gcc for their generators")
    work = Path(tempfile.mkdtemp(prefix=f".{port['name']}-stage-", dir=output.parent))
    commands: list[list[str]] = []
    manifest = {"schema_version": 1, "name": port["name"], "version": port["version"], "license": port["license"],
                "archive_sha256": port["sha256"], "descriptor_sha256": digest(PORTS / port["name"] / "port.json"),
                "architecture": args.arch, "mode": args.mode, "toolchain": toolchain, "frontend": frontend,
                "musl_manifest_sha256": digest(musl / "manifest.json"), "musl_build": str(musl),
                "compiler_runtime_supplement": softfp, "config_fragment_sha256": digest(fragment),
                "patches": {patch.relative_to(PORTS).as_posix(): digest(patch) for patch in patches},
                "requested_config": requested, "port_cflags": PORT_CFLAGS,
                "linker_script_sha256": digest(LINKER_SCRIPT), "driver_sha256": digest(Path(musl_cc.__file__)),
                "host_compiler": {"path": host_cc, "sha256": digest(Path(host_cc))},
                "personality": {"elf_osabi": 3, "name": "linux"}, "qualification": "cross-build-only",
                "commands": commands, "status": "building", "executed": False, "files": {}}
    env = clean_env()

    def run(command: list[str], log: str, answers: bytes | None = None) -> None:
        commands.append(command)
        with (work / log).open("a") as stream:
            if subprocess.run(command, cwd=work, env=env, input=answers, stdout=stream,
                              stderr=subprocess.STDOUT).returncode:
                raise ValueError(f"{log} failed")

    try:
        copy = work / port["archive"]
        shutil.copyfile(args.archive, copy)
        source = work / "source" / admit_archive(copy, port)
        extract(copy, work / "source")
        for patch in patches:
            run(["patch", "-p1", "--forward", "--batch", "--no-backup-if-mismatch", "-d", str(source),
                 "-i", str(patch)], "patch.log")
        driver = work / "driver"
        driver.mkdir()
        profile = driver_profile(args.arch, musl, musl_manifest, toolchain, frontend, supplements)
        (driver / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
        shim = driver / "cc"
        shim.write_text(f'#!/bin/sh\nexec {sys.executable} -B {musl_cc.__file__} {driver / "profile.json"} "$@"\n')
        shim.chmod(0o755)
        build = work / "build"
        build.mkdir()
        common = ["make", "-C", str(source), f"O={build}", f"HOSTCC={host_cc}"]
        run([*common, "allnoconfig"], "config.log")
        # Empty answers take each new symbol's default; resolve_config then
        # switches off everything not requested or selected.
        resolved = resolve_config(build / ".config", (build / ".config").read_text(), requested,
                                  lambda: run([*common, "oldconfig"], "config.log", b"\n" * 8192))
        unmet = unmet_config(requested, resolved)
        if unmet:
            raise ValueError("resolved .config drops requested symbols: " + ", ".join(unmet))
        cross = f"CROSS_COMPILE={toolchain['bindir']}/{toolchain['triple']}-"
        links = port["build"]["program"] + ".links"
        run([*common, f"CC={shim}", cross, f"-j{args.jobs}", port["build"]["program"], links], "build.log")
        program = build / port["build"]["program"]
        musl_cc.mark_linux(program, profile)
        manifest["elf"] = inspect_elf(program, args.arch)
        bound = SECTION_TABLE_BOUND.get(args.arch)
        if bound and section_table_end(program.read_bytes()) > bound:
            raise ValueError(f"{args.arch} program section table ends past the kernel's {bound}-byte admission prefix")
        applets = applet_names((build / links).read_text())
        stage = work / "stage"
        (stage / "bin").mkdir(parents=True)
        shutil.copy2(program, stage / "bin" / program.name)
        share = stage / "share" / port["name"]
        shutil.copytree(source / port["build"]["testsuite"], share / "testsuite")
        shutil.copy2(build / ".config", share / ".config")
        (share / "applets").write_text("\n".join(applets) + "\n")
        licenses = stage / "share/licenses" / port["name"]
        licenses.mkdir(parents=True)
        shutil.copy2(source / "LICENSE", licenses / "LICENSE")
        manifest.update(applets=applets, elf_sha256=digest(program), config_sha256=digest(build / ".config"),
                        status="built-not-executed")
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        manifest["status"] = "build-failed"
        manifest["failure"] = str(exc)
    finally:
        for path in sorted((work / "stage").rglob("*")) if (work / "stage").is_dir() else []:
            if path.is_file():
                manifest["files"][path.relative_to(work).as_posix()] = digest(path)
        (work / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        work.rename(output)
    if manifest["status"] != "built-not-executed":
        raise ValueError(f"{manifest['failure']}; failure record preserved in {output}")
    return manifest


def admit(build: Path, manifest_sha256: str, arch: str, mode: str | None = None) -> dict:
    """Admit one finished kconfig port build for image staging."""
    from musl_source import inspect_elf
    build = build.resolve()
    path = build / "manifest.json"
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256 or "") or digest(path) != manifest_sha256:
        raise ValueError("port build manifest hash mismatch")
    manifest = json.loads(path.read_text())
    port = load().get(manifest.get("name"), {})
    if (manifest.get("schema_version") != 1 or manifest.get("status") != "built-not-executed" or
            manifest.get("executed") is not False or manifest.get("architecture") != arch or
            (mode is not None and manifest.get("mode") != mode) or port.get("build", {}).get("system") != "kconfig" or
            manifest.get("version") != port.get("version") or manifest.get("archive_sha256") != port.get("sha256")):
        raise ValueError("port build is not a finished build of the pinned descriptor for this profile")
    files = manifest.get("files")
    program = f"stage/bin/{port['build']['program']}"
    if not isinstance(files, dict) or program not in files or files[program] != manifest.get("elf_sha256"):
        raise ValueError("port build lacks its audited program")
    for name, expected in files.items():
        target = build / name
        pure = PurePosixPath(name)
        if (pure.is_absolute() or ".." in pure.parts or target.is_symlink() or not target.is_file() or
                digest(target) != expected):
            raise ValueError("port build artifact mismatch: " + name)
    if inspect_elf(build / program, arch) != manifest.get("elf") or (build / program).read_bytes()[7] != 3:
        raise ValueError("port program ELF identity differs from its manifest")
    applets = manifest.get("applets")
    if not isinstance(applets, list) or applets != sorted(set(applets)) or not all(
            isinstance(name, str) and APPLET.fullmatch(name) for name in applets):
        raise ValueError("port build applet list is invalid")
    return manifest


def build_port(args) -> dict:
    ports = load()
    errors = validate(ports)
    if errors:
        raise ValueError("\n".join(errors))
    if args.name not in ports:
        raise ValueError(f"unknown port {args.name}")
    port = ports[args.name]
    if not port["sha256"]:
        raise ValueError(f"{args.name} has no pinned archive hash")
    if not 1 <= args.jobs <= 64:
        raise ValueError("jobs must be between 1 and 64")
    system = port["build"]["system"]
    if system not in RECIPES:
        raise ValueError(f"build system {system} has no recipe yet")
    return build_musl(port, args) if system == "musl" else build_kconfig(port, args)


def main(argv: list[str]) -> int:
    if argv and argv[0] == "build":
        parser = argparse.ArgumentParser(prog="ports.py build")
        parser.add_argument("--name", required=True)
        parser.add_argument("--arch", choices=sorted(PROFILES), required=True)
        parser.add_argument("--mode", choices=("debug", "release"), required=True)
        parser.add_argument("--archive", type=Path, required=True)
        parser.add_argument("--toolchain", type=Path, required=True)
        parser.add_argument("--out", type=Path, required=True)
        parser.add_argument("--musl-build", type=Path)
        parser.add_argument("--ppc-clang", type=Path)
        parser.add_argument("--softfp-build", type=Path)
        parser.add_argument("--softfp-manifest-sha256")
        parser.add_argument("--jobs", type=int, default=8)
        args = parser.parse_args(argv[1:])
        try:
            result = build_port(args)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"port build error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"name": args.name, **{key: result.get(key) for key in ("architecture", "mode", "status")}}))
        return 0
    ports = load()
    if not argv or argv[0] == "validate":
        errors = validate(ports)
        for e in errors:
            print(e)
        print(f"{len(ports)} ports, {'ok' if not errors else f'{len(errors)} errors'}")
        return 1 if errors else 0
    if argv[0] == "order":
        errors = validate(ports)
        if errors:
            raise SystemExit("\n".join(errors))
        print(" ".join(order(ports, argv[1:] or sorted(ports))))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
