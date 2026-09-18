#!/usr/bin/env python3
"""Render production GUI pixels against a validated exported x86_64 debug SDK."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk


def png(path: Path, width: int, height: int, pixels: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    scanlines = b"".join(b"\0" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    validate_sdk(sdk, "x86_64", "debug")
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out.resolve()
    executable = output / "gui-render"
    module = ROOT / "modules/system-gui"
    subprocess.run([args.cxx, "-std=c++23", "-fno-exceptions", "-fno-threadsafe-statics", "-no-pie",
                    "-DOK_ARCH_TARGET_X86_64", "-DOK_ENABLE_TEST_POINTS", "-DOK_ENABLE_KERNEL_GUI",
                    "-I" + str(sdk / "include"), "-I" + str(module),
                    str(Path(__file__).with_suffix(".cpp")), str(module / "external_module.cpp"),
                    str(module / "system_gui_runtime.cpp"), str(sdk / "lib/libokernel.a"),
                    "-o", str(executable)], check=True)
    subprocess.run([str(executable), str(output)], check=True)
    for source in sorted(output.glob("*.ppm")):
        magic, dimensions, maximum, pixels = source.read_bytes().split(b"\n", 3)
        if (magic, dimensions, maximum) != (b"P6", b"480 270", b"255") or len(pixels) != 480 * 270 * 3:
            raise ValueError(f"Unexpected framebuffer format: {source}")
        scaled = bytearray()
        for y in range(270):
            row = b"".join(pixels[(y * 480 + x) * 3:(y * 480 + x + 1) * 3] * 2 for x in range(480))
            scaled.extend(row * 2)
        png(source.with_suffix(".png"), 960, 540, scaled)
    print(f"Rendered screenshots: {output}")


if __name__ == "__main__":
    main()
