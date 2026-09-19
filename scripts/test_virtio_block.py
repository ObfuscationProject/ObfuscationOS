#!/usr/bin/env python3
"""Run the OS Virtio driver against real QEMU disks using only an exported SDK."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk, assemble_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=("i386", "x86_64", "aarch64", "arm32", "rv32", "rv64", "loongarch64", "mips", "mips64", "ppc"))
    parser.add_argument("--kernel-sdk", required=True, type=Path)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--qemu")
    parser.add_argument("--modern-mmio", action="store_true")
    parser.add_argument("--modern-pci", action="store_true")
    args = parser.parse_args()
    mmio = args.arch in ("aarch64", "arm32", "rv32", "rv64")
    if args.modern_pci and mmio:
        parser.error("--modern-pci requires a PCI architecture")
    if args.modern_mmio and not mmio:
        parser.error("--modern-mmio requires an MMIO architecture")
    sdk, out = args.kernel_sdk.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    triple = {"i386":"i386-elf", "x86_64":"x86_64-elf", "aarch64":"aarch64-elf", "arm32":"arm-none-eabi",
              "rv32":"riscv32-elf", "rv64":"riscv64-elf", "loongarch64":"loongarch64-elf",
              "mips":"mips-elf", "mips64":"mips64-elf", "ppc":"powerpc-eabi"}[args.arch]
    prefix = args.toolchain.resolve() / "bin" / (triple + "-")
    cxx, ar, objcopy = [str(prefix) + name for name in ("g++", "ar", "objcopy")]
    manifest = validate_sdk(sdk, args.arch, "debug", Path(cxx))
    boot_archive = sdk / "lib/libokernel_boot.a"
    members = subprocess.check_output([ar, "t", str(boot_archive)], text=True).splitlines()
    if members.count("boot.S.o") != 1:
        raise RuntimeError("SDK must contain one explicit boot.S.o artifact")
    boot = out / "boot.o"
    boot.write_bytes(subprocess.check_output([ar, "p", str(boot_archive), "boot.S.o"]))
    flags = ["-std=c++23", *manifest["cxxflags"], "-fno-builtin", "-fno-rtti", "-Werror", "-I", str(sdk / "include"), "-I", str(ROOT)]
    driver = out / "driver.o"
    subprocess.run([cxx, *flags, "-c", str(ROOT / "drivers/virtio/block.cpp"), "-o", str(driver)], check=True)
    qemu = args.qemu or {"i386":"qemu-system-i386", "x86_64":"qemu-system-x86_64", "aarch64":"qemu-system-aarch64",
                         "arm32":"qemu-system-arm", "rv32":"qemu-system-riscv32", "rv64":"qemu-system-riscv64",
                         "loongarch64":"qemu-system-loongarch64", "mips":"qemu-system-mips",
                         "mips64":"qemu-system-mips64", "ppc":"qemu-system-ppc"}[args.arch]
    disk = out / "scratch.img"
    initial = bytes([0xa5]) * (1024 * 512)
    disk.write_bytes(initial)
    expected = bytearray(initial)
    expected[40*512:56*512] = bytes((i ^ 0x5a) & 255 for i in range(8192))
    for scenario in ("write", "reopen", "readonly", "read_error", "absent"):
        obj, elf, image = [out / (scenario + suffix) for suffix in (".o", ".elf", ".bin")]
        defines = {"readonly": "OK_BLOCK_READ_ONLY", "absent": "OK_BLOCK_NO_DEVICE", "read_error": "OK_BLOCK_READ_ERROR"}
        define = ["-D" + defines[scenario]] if scenario in defines else []
        subprocess.run([cxx, *flags, *define, "-c", str(ROOT / "tests/drivers/virtio_block_probe.cpp"), "-o", str(obj)], check=True)
        subprocess.run([cxx, *manifest["ldflags"], "-nostdlib", "-static", "-Wl,--build-id=none", "-Wl,-T," + str(sdk / "boot/linker.ld"),
                        str(boot), str(driver), str(obj), "-lgcc", "-o", str(elf)], check=True)
        assemble_image(elf, image, sdk, manifest["image_format"], Path(objcopy))
        if args.arch in ("i386", "x86_64"):
            command = [qemu, "-m", "128M", "-drive", f"file={image},format=raw,if=ide", "-boot", "c"]
        elif args.arch in ("mips", "mips64", "ppc"):
            command = [qemu, "-M", "ppce500" if args.arch == "ppc" else "malta", "-m", "256M", "-kernel", str(image)]
            if args.arch == "mips64":
                command += ["-cpu", "MIPS64R2-generic"]
        else:
            command = [qemu, "-M", "virt", "-m", "2G" if args.arch == "loongarch64" else "256M", "-kernel", str(image)]
            if args.arch in ("arm32", "aarch64"):
                command += ["-cpu", "cortex-a15" if args.arch == "arm32" else "cortex-a57"]
            if args.arch in ("rv32", "rv64"):
                command += ["-bios", "none"]
        if args.modern_mmio:
            command += ["-global", "virtio-mmio.force-legacy=false"]
        if scenario != "absent":
            backing = str(disk)
            if scenario == "read_error":
                fault = out / "read-error.conf"
                fault.write_text('[inject-error]\nevent = "read_aio"\nerrno = "5"\nsector = "40"\nonce = "on"\nimmediately = "on"\n')
                backing = f"blkdebug:{fault}:{disk}"
            drive = f"file={backing},format=raw,if=none,id=testdisk" + (",readonly=on" if scenario == "readonly" else "")
            transport = "virtio-blk-device" if mmio else "virtio-blk-pci"
            command += ["-drive", drive, "-device", transport + ",drive=testdisk" + (",disable-legacy=on" if args.modern_pci else "")]
        command += ["-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=5)
            serial = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            serial = (error.stdout or b"") + (error.stderr or b"")
        text = serial.decode(errors="replace")
        (out / (scenario + ".log")).write_text(text)
        print(scenario + ":\n" + text, end="")
        marker = {"write":"write=pass flush=pass ring_wrap=pass", "reopen":"reopen=pass", "readonly":"readonly=pass",
                  "read_error":"read_error=pass recovery=pass", "absent":"absent=pass"}[scenario]
        if "VIRTIO_BLOCK_PASS scope=hardware " + marker not in text or "VIRTIO_BLOCK_FAIL" in text:
            raise RuntimeError("Virtio block hardware probe failed: " + scenario)
        if disk.read_bytes() != expected:
            raise RuntimeError("host disk bytes differ from exact expected write region")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
