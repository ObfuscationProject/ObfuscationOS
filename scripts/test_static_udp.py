#!/usr/bin/env python3
"""Native QEMU static ARP/IPv4/UDP request-response qualifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import assemble_image, validate_sdk  # noqa: E402
import static_udp_peer as peer_protocol  # noqa: E402

PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc")
MMIO = {"aarch64", "arm32", "rv64", "rv32"}
TRIPLES = dict(zip(PROFILES, ("i386-elf", "x86_64-elf", "aarch64-elf", "arm-none-eabi", "riscv64-elf", "riscv32-elf", "loongarch64-elf", "mips-elf", "mips64-elf", "powerpc-eabi")))
QEMU = dict(zip(PROFILES, ("qemu-system-i386", "qemu-system-x86_64", "qemu-system-aarch64", "qemu-system-arm", "qemu-system-riscv64", "qemu-system-riscv32", "qemu-system-loongarch64", "qemu-system-mips", "qemu-system-mips64", "qemu-system-ppc")))
SOURCES = ("drivers/virtio/net.hpp", "drivers/virtio/net.cpp", "drivers/virtio/net_queue.hpp", "drivers/virtio/poll.hpp",
           "drivers/net/static_udp.hpp", "drivers/net/static_udp.cpp", "drivers/net/static_udp_service.cpp",
           "tests/drivers/static_udp_probe.cpp", "scripts/static_udp_peer.py", "scripts/test_static_udp.py", "tools/kernel_sdk.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive_exact(stream: socket.socket, size: int) -> bytes:
    output = bytearray()
    while len(output) < size:
        chunk = stream.recv(size - len(output))
        if not chunk:
            raise RuntimeError("external peer stream closed")
        output += chunk
    return bytes(output)


def send_frame(stream: socket.socket, frame: bytes, capture: bytearray) -> None:
    assert 14 <= len(frame) <= 1514
    record = struct.pack("!I", len(frame)) + frame
    stream.sendall(record)
    capture.extend(record)


def receive_frame(stream: socket.socket, capture: bytearray) -> bytes:
    length = struct.unpack("!I", receive_exact(stream, 4))[0]
    if not 14 <= length <= 1514:
        raise RuntimeError("external peer received invalid Ethernet size")
    frame = receive_exact(stream, length)
    capture.extend(struct.pack("!I", length) + frame)
    return frame


def records(path: Path) -> list[str]:
    return path.read_text(errors="replace").replace("\r", "").splitlines() if path.exists() else []


def wait_record(path: Path, process: subprocess.Popen, expected: str, deadline: float = 15) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        lines = records(path)
        if any(line.startswith("STATIC_UDP_FAIL") for line in lines):
            raise RuntimeError("native static UDP probe reported failure")
        if lines.count(expected) == 1:
            return
        if process.poll() is not None:
            raise RuntimeError("QEMU exited before static UDP acceptance")
        time.sleep(0.01)
    raise RuntimeError("native serial record timed out: " + expected)


def qemu_argv(arch: str, image: Path, scenario: str, backend: socket.socket, override: str | None) -> list[str]:
    qemu = override or QEMU[arch]
    if arch in ("i386", "x86_64"):
        argv = [qemu, "-m", "128M", "-drive", f"file={image},format=raw,if=ide", "-boot", "c"]
    elif arch in ("mips", "mips64", "ppc"):
        argv = [qemu, "-M", "ppce500" if arch == "ppc" else "malta", "-m", "256M", "-kernel", str(image)]
        if arch == "mips64":
            argv += ["-cpu", "MIPS64R2-generic"]
    else:
        argv = [qemu, "-M", "virt", "-m", "2G" if arch == "loongarch64" else "256M", "-kernel", str(image)]
        if arch in ("aarch64", "arm32"):
            argv += ["-cpu", "cortex-a57" if arch == "aarch64" else "cortex-a15"]
        if arch in ("rv64", "rv32"):
            argv += ["-bios", "none"]
    argv += ["-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot", "-nic", "none"]
    if arch in MMIO:
        argv += ["-global", "virtio-mmio.force-legacy=" + ("true" if scenario == "legacy" else "false")]
    if scenario != "absent":
        device = "virtio-net-device" if arch in MMIO else "virtio-net-pci"
        properties = "" if arch in MMIO else (",disable-modern=on" if scenario == "legacy" else ",disable-legacy=on")
        argv += ["-netdev", f"socket,id=net0,fd={backend.fileno()}", "-device",
                 f"{device},netdev=net0,mac=02:11:22:33:44:55{properties}"]
    return argv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=PROFILES, required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu")
    parser.add_argument("--compile-only", action="store_true")
    args = parser.parse_args()
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or not sys.dont_write_bytecode:
        parser.error("use PYTHONDONTWRITEBYTECODE=1 python3 -B")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sdk = args.kernel_sdk.resolve()
    triple = TRIPLES[args.arch]
    prefix = args.toolchain.resolve() / "bin" / (triple + "-")
    cxx, ar, objcopy = (Path(str(prefix) + name) for name in ("g++", "ar", "objcopy"))
    transport = "mmio" if args.arch in MMIO else "pci"
    receipt = dict(schema=1, scope="static ARP/IPv4/UDP over modern Virtio " + transport.upper(), sdk_abi=None,
                   status="failed", architecture=args.arch, mode=args.mode, commands=[], executions=[],
                   physical_acceptance=False, socket_api_acceptance=False, irq_acceptance=False,
                   ip_stack_acceptance=False, source_sha256={name: sha(ROOT / name) for name in SOURCES},
                   tool_sha256={str(path): sha(path) for path in (cxx, ar, objcopy)})

    def command(argv: list[str], name: str) -> bytes:
        run = subprocess.run(argv, capture_output=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        stdout, stderr = output / (name + ".stdout"), output / (name + ".stderr")
        stdout.write_bytes(run.stdout); stderr.write_bytes(run.stderr)
        receipt["commands"].append(dict(argv=argv, returncode=run.returncode, stdout=stdout.name,
                                        stdout_sha256=sha(stdout), stderr=stderr.name, stderr_sha256=sha(stderr)))
        if run.returncode:
            raise RuntimeError("command failed: " + name)
        return run.stdout

    try:
        manifest = validate_sdk(sdk, args.arch, args.mode, cxx)
        receipt["sdk_abi"] = manifest["abi_version"]
        receipt["scope"] = f'SDK{manifest["abi_version"]} static ARP/IPv4/UDP over modern Virtio {transport.upper()}'
        if "include/ok/net/wire.hpp" not in manifest["files"]:
            raise RuntimeError("explicit SDK has no exported network wire header")
        receipt["sdk"] = str(sdk)
        receipt["sdk_manifest_sha256"] = sha(sdk / "manifest.json")
        receipt["wire_header_sha256"] = sha(sdk / "include/ok/net/wire.hpp")
        flags = ["-std=c++23", *manifest["cxxflags"], *["-D" + item for item in manifest["defines"]],
                 "-fno-builtin", "-Werror", "-Wframe-larger-than=1024", "-I", str(sdk / "include"), "-I", str(ROOT)]
        objects = []
        for name, relative in (("net", "drivers/virtio/net.cpp"), ("endpoint", "drivers/net/static_udp.cpp"),
                               ("service", "drivers/net/static_udp_service.cpp")):
            target = output / (name + ".o")
            command([str(cxx), *flags, "-c", str(ROOT / relative), "-o", str(target)], name)
            objects.append(target)
        receipt["driver_sha256"] = {item.name: sha(item) for item in objects}
        if args.compile_only:
            receipt["status"] = "passed-compile-only"
            return 0
        archive = sdk / "lib/libokernel_boot.a"
        members = command([str(ar), "t", str(archive)], "boot-members").decode().splitlines()
        if members.count("boot.S.o") != 1:
            raise RuntimeError("SDK must contain exactly one boot.S.o")
        boot = output / "boot.o"
        boot.write_bytes(command([str(ar), "p", str(archive), "boot.S.o"], "boot-extract"))
        for scenario in ("exchange", "hostile", "absent", "legacy"):
            object_path = output / (scenario + ".o")
            elf, image = output / (scenario + ".elf"), output / (scenario + ".bin")
            extra = [] if scenario == "exchange" else ["-DOK_STATIC_UDP_" + scenario.upper()]
            command([str(cxx), *flags, *extra, "-c", str(ROOT / "tests/drivers/static_udp_probe.cpp"),
                     "-o", str(object_path)], scenario + "-compile")
            command([str(cxx), *manifest["ldflags"], "-nostdlib", "-static", "-Wl,--build-id=none",
                     "-Wl,-T," + str(sdk / "boot/linker.ld"), str(boot), *map(str, objects), str(object_path),
                     str(sdk / "lib/libokernel.a"), "-lgcc", "-o", str(elf)], scenario + "-link")
            assemble_image(elf, image, sdk, manifest["image_format"], objcopy)
            local, backend = socket.socketpair()
            local.settimeout(15)
            argv = qemu_argv(args.arch, image, scenario, backend, args.qemu)
            serial_path, inbound_path, outbound_path = (output / (scenario + suffix) for suffix in
                                                       (".serial.log", ".peer-in.bin", ".peer-out.bin"))
            inbound, outbound = bytearray(), bytearray()
            execution = dict(scenario=scenario, argv=argv, image_sha256=sha(image), elf_sha256=sha(elf),
                             executed=False, accepted=False, frames=[])
            receipt["executions"].append(execution)
            process = None
            try:
                with serial_path.open("wb") as serial:
                    process = subprocess.Popen(argv, stdout=serial, stderr=subprocess.STDOUT,
                                               pass_fds=(backend.fileno(),) if scenario != "absent" else ())
                    execution["executed"] = True
                    backend.close()
                    wait_record(serial_path, process, "STATIC_UDP_BEGIN transport=" + transport)
                    if scenario == "exchange":
                        wait_record(serial_path, process, "STATIC_UDP_READY")
                        send_frame(local, peer_protocol.arp_request(), inbound)
                        observed = receive_frame(local, outbound)
                        if observed != peer_protocol.arp_reply():
                            raise RuntimeError("external ARP reply differs byte for byte")
                        execution["frames"].append(dict(kind="arp", transmitted_sha256=hashlib.sha256(
                            peer_protocol.arp_request()).hexdigest(), received_sha256=hashlib.sha256(observed).hexdigest()))
                        for sequence in range(96):
                            sent = peer_protocol.request(sequence)
                            send_frame(local, sent, inbound)
                            observed = receive_frame(local, outbound)
                            peer_protocol.verify_reply(observed, sequence)
                            execution["frames"].append(dict(kind="udp", sequence=sequence,
                                transmitted_sha256=hashlib.sha256(sent).hexdigest(),
                                received_sha256=hashlib.sha256(observed).hexdigest()))
                    elif scenario == "hostile":
                        wait_record(serial_path, process, "STATIC_UDP_READY")
                        for index, (name, sent) in enumerate(peer_protocol.hostile()):
                            send_frame(local, sent, inbound)
                            wait_record(serial_path, process, f"STATIC_UDP_DROP index={index}")
                            execution["frames"].append(dict(kind="hostile", name=name,
                                transmitted_sha256=hashlib.sha256(sent).hexdigest()))
                        if select.select([local], [], [], 0.2)[0]:
                            raise RuntimeError("hostile traffic produced an external reply")
                        sent = peer_protocol.request(0)
                        send_frame(local, sent, inbound)
                        observed = receive_frame(local, outbound)
                        peer_protocol.verify_reply(observed, 0)
                        execution["frames"].append(dict(kind="recovery",
                            transmitted_sha256=hashlib.sha256(sent).hexdigest(),
                            received_sha256=hashlib.sha256(observed).hexdigest()))
                    expected = "STATIC_UDP_PASS scenario=" + scenario + {
                        "exchange": " arp=1 udp=96", "hostile": " drops=12 recovery=1",
                        "absent": "", "legacy": ""}[scenario]
                    wait_record(serial_path, process, expected)
                    execution["accepted"] = True
            finally:
                local.close(); backend.close()
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                    execution["returncode"] = process.returncode
                inbound_path.write_bytes(inbound); outbound_path.write_bytes(outbound)
                execution["serial_log"] = serial_path.name
                if serial_path.exists():
                    execution["serial_sha256"] = sha(serial_path)
                execution["external_inbound"] = inbound_path.name
                execution["external_inbound_sha256"] = sha(inbound_path)
                execution["external_outbound"] = outbound_path.name
                execution["external_outbound_sha256"] = sha(outbound_path)
            print(args.arch, args.mode, scenario, "passed", flush=True)
        receipt["status"] = "passed-native-static-udp"
        return 0
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        with (output / "result.json").open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
