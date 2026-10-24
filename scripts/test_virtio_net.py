#!/usr/bin/env python3
"""Compile an SDK-only modern Virtio NIC probe and verify external Ethernet bytes.

This is a polling NIC qualification, not socket, IP, IRQ or physical acceptance.
The host peer is a separate endpoint on QEMU's framed socket network backend;
RX enters through the emulated NIC and DMA, never a driver receive injection.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk, assemble_image

PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc")
MMIO = ("aarch64", "arm32", "rv64", "rv32")
TRIPLES = dict(zip(PROFILES, ("i386-elf", "x86_64-elf", "aarch64-elf", "arm-none-eabi", "riscv64-elf", "riscv32-elf", "loongarch64-elf", "mips-elf", "mips64-elf", "powerpc-eabi")))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_frame(sequence: int) -> bytes:
    length = 1514 if sequence % 3 == 0 else 60 + sequence
    return bytes.fromhex("02aabbccddee02112233445588b5") + struct.pack("!H", sequence) + bytes(((i * 37) ^ sequence ^ 0x5a) & 255 for i in range(16, length))


def receive_exact(peer: socket.socket, size: int) -> bytes:
    parts = bytearray()
    while len(parts) < size:
        data = peer.recv(size - len(parts))
        if not data: raise RuntimeError("external peer stream closed")
        parts.extend(data)
    return bytes(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=PROFILES, required=True)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu")
    parser.add_argument("--compile-only", action="store_true")
    args = parser.parse_args()
    if not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        parser.error("use PYTHONDONTWRITEBYTECODE=1 python3 -B")
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    sdk = args.kernel_sdk.resolve()
    prefix = args.toolchain.resolve() / "bin" / (TRIPLES[args.arch] + "-")
    cxx, ar, objcopy = (Path(str(prefix) + name) for name in ("g++", "ar", "objcopy"))
    mmio = args.arch in MMIO
    transport = "mmio" if mmio else "pci"
    receipt = dict(schema=1, scope="SDK-only polling modern Virtio " + transport.upper() + " NIC", status="failed",
        architecture=args.arch, mode=args.mode, commands=[], executions=[], physical_acceptance=False,
        socket_acceptance=False, ip_acceptance=False, irq_acceptance=False,
        source_sha256={name: sha(ROOT / name) for name in ("drivers/virtio/net.hpp", "drivers/virtio/net.cpp", "drivers/virtio/net_queue.hpp", "drivers/virtio/poll.hpp", "tests/drivers/virtio_net_probe.cpp", "scripts/test_virtio_net.py", "tools/kernel_sdk.py")},
        tool_sha256={str(p): sha(p) for p in (cxx, ar, objcopy)})

    def command(argv: list[str], name: str) -> bytes:
        run = subprocess.run(argv, capture_output=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        stdout, stderr = out / (name + ".stdout"), out / (name + ".stderr")
        stdout.write_bytes(run.stdout); stderr.write_bytes(run.stderr)
        receipt["commands"].append(dict(argv=argv, returncode=run.returncode, stdout=stdout.name,
            stdout_sha256=sha(stdout), stderr=stderr.name, stderr_sha256=sha(stderr)))
        if run.returncode: raise RuntimeError("command failed: " + name)
        return run.stdout

    try:
        manifest = validate_sdk(sdk, args.arch, args.mode, cxx)
        receipt["sdk"] = str(sdk); receipt["sdk_manifest_sha256"] = sha(sdk / "manifest.json")
        flags = ["-std=c++23", *manifest["cxxflags"], *["-D" + d for d in manifest["defines"]],
            "-fno-builtin", "-Werror", "-Wframe-larger-than=1024", "-I", str(sdk / "include"), "-I", str(ROOT)]
        driver = out / "net.o"
        command([str(cxx), *flags, "-c", str(ROOT / "drivers/virtio/net.cpp"), "-o", str(driver)], "driver")
        receipt["driver_sha256"] = sha(driver)
        if args.compile_only:
            receipt["status"] = "passed-compile-only"; return 0
        archive = sdk / "lib/libokernel_boot.a"
        members = command([str(ar), "t", str(archive)], "boot-members").decode().splitlines()
        if members.count("boot.S.o") != 1: raise RuntimeError("SDK must contain exactly one boot.S.o")
        boot = out / "boot.o"; boot.write_bytes(command([str(ar), "p", str(archive), "boot.S.o"], "boot-extract"))
        for scenario in ("exchange", "absent", "legacy"):
            object_path, elf, image = (out / (scenario + suffix) for suffix in (".o", ".elf", ".bin"))
            extra = [] if scenario == "exchange" else ["-DOK_NET_" + scenario.upper()]
            command([str(cxx), *flags, *extra, "-c", str(ROOT / "tests/drivers/virtio_net_probe.cpp"), "-o", str(object_path)], scenario + "-compile")
            command([str(cxx), *manifest["ldflags"], "-nostdlib", "-static", "-Wl,--build-id=none",
                "-Wl,-T," + str(sdk / "boot/linker.ld"), str(boot), str(driver), str(object_path),
                str(sdk / "lib/libokernel.a"), "-lgcc", "-o", str(elf)], scenario + "-link")
            assemble_image(elf, image, sdk, manifest["image_format"], objcopy)
            qemu = args.qemu or {"i386":"qemu-system-i386", "x86_64":"qemu-system-x86_64",
                "aarch64":"qemu-system-aarch64", "arm32":"qemu-system-arm",
                "rv64":"qemu-system-riscv64", "rv32":"qemu-system-riscv32",
                "loongarch64":"qemu-system-loongarch64", "mips":"qemu-system-mips",
                "mips64":"qemu-system-mips64", "ppc":"qemu-system-ppc"}[args.arch]
            if args.arch in ("i386", "x86_64"):
                argv = [qemu, "-m", "128M", "-drive", f"file={image},format=raw,if=ide", "-boot", "c"]
            elif args.arch in ("mips", "mips64", "ppc"):
                argv = [qemu, "-M", "ppce500" if args.arch == "ppc" else "malta",
                    "-m", "256M", "-kernel", str(image)]
                if args.arch == "mips64": argv += ["-cpu", "MIPS64R2-generic"]
            else:
                argv = [qemu, "-M", "virt", "-m", "2G" if args.arch == "loongarch64" else "256M", "-kernel", str(image)]
                if args.arch in ("aarch64", "arm32"):
                    argv += ["-cpu", "cortex-a57" if args.arch == "aarch64" else "cortex-a15"]
                if args.arch in ("rv64", "rv32"): argv += ["-bios", "none"]
            argv += ["-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot", "-nic", "none"]
            if mmio:
                argv += ["-global", "virtio-mmio.force-legacy=" + ("true" if scenario == "legacy" else "false")]
            peer, backend = socket.socketpair(); peer.settimeout(8)
            if scenario != "absent":
                device = "virtio-net-device" if mmio else "virtio-net-pci"
                properties = "" if mmio else (",disable-modern=on" if scenario == "legacy" else ",disable-legacy=on")
                argv += ["-netdev", f"socket,id=net0,fd={backend.fileno()}", "-device",
                    f"{device},netdev=net0,mac=02:11:22:33:44:55{properties}"]
            serial_path = out / (scenario + ".serial.log")
            capture_path = out / (scenario + ".peer.bin")
            frames, captured, process = [], bytearray(), None
            execution = dict(scenario=scenario, argv=argv, image_sha256=sha(image), elf_sha256=sha(elf),
                executed=False, accepted=False, frames=frames)
            receipt["executions"].append(execution)
            try:
                with serial_path.open("wb") as serial:
                    process = subprocess.Popen(argv, stdout=serial, stderr=subprocess.STDOUT,
                        pass_fds=(backend.fileno(),) if scenario != "absent" else ())
                    execution["executed"] = True; backend.close()
                    if scenario == "exchange":
                        for sequence in range(96):
                            size = struct.unpack("!I", receive_exact(peer, 4))[0]
                            if size > 1514 or size < 14: raise RuntimeError("external peer received invalid Ethernet size")
                            frame = receive_exact(peer, size)
                            captured.extend(struct.pack("!I", size)); captured.extend(frame)
                            if frame != expected_frame(sequence): raise RuntimeError(f"external peer bytes differ at sequence {sequence}")
                            reply = frame[6:12] + frame[:6] + frame[12:]
                            peer.sendall(struct.pack("!I", len(reply)) + reply)
                            frames.append(dict(sequence=sequence, bytes=size, transmitted_sha256=hashlib.sha256(frame).hexdigest(), received_sha256=hashlib.sha256(reply).hexdigest()))
                    expected = "VIRTIO_NET_PASS scope=native-" + transport + " " + {
                        "exchange": "packets=96 ring=pass bytes=pass retry=pass restart=pass",
                        "absent": "absent=pass", "legacy": "legacy=unsupported"}[scenario]
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        records = serial_path.read_text(errors="replace").replace("\r", "").splitlines()
                        if "VIRTIO_NET_FAIL" in "\n".join(records): raise RuntimeError("native probe reported failure")
                        if records.count(expected) == 1 and records.count("VIRTIO_NET_BEGIN scope=native-" + transport) == 1:
                            execution["accepted"] = True; break
                        if process.poll() is not None: raise RuntimeError("QEMU exited before acceptance")
                        time.sleep(0.01)
                    if not execution["accepted"]: raise RuntimeError("native serial acceptance timed out")
            finally:
                peer.close(); backend.close()
                if process is not None:
                    if process.poll() is None: process.terminate()
                    try: process.wait(timeout=2)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                    execution["returncode"] = process.returncode
                capture_path.write_bytes(captured)
                execution["serial_log"] = serial_path.name
                if serial_path.exists(): execution["serial_sha256"] = sha(serial_path)
                execution["external_capture"] = capture_path.name; execution["external_capture_sha256"] = sha(capture_path)
            print(args.arch, args.mode, scenario, "passed", flush=True)
        receipt["status"] = "passed-native-" + transport
        return 0
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        with (out / "result.json").open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True); stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
