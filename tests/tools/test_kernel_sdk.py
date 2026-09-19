"""Artifact contract tests independent of an installed cross compiler."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from kernel_sdk import BIOS_PAYLOAD_CAPACITY, assemble_image, validate_sdk


class KernelSdkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sdk = self.root / "sdk"
        self.sdk.mkdir()
        files = {}
        for name in ("lib/libokernel.a", "lib/libokernel_boot.a", "boot/linker.ld",
                     "image/kernel.bin", "image/kernel.elf", "include/ok/uapi/syscall.h", "boot/boot16.bin"):
            path = self.sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = bytes(510) + b"\x55\xaa" if name.endswith("boot16.bin") else name.encode()
            path.write_bytes(content)
            files[name] = hashlib.sha256(content).hexdigest()
        self.manifest = {"schema": 1, "abi_version": 3, "kernel_version": "0.1.0", "arch": "x86_64",
                         "mode": "debug", "triple": "x86_64-elf", "image_format": "bios-disk",
                         "cxxflags": [], "asflags": [], "ldflags": [], "defines": [],
                         "compiler": {"family": "gcc", "version": "14.2.0"}, "files": files}
        self.save()

    def save(self):
        (self.sdk / "manifest.json").write_text(json.dumps(self.manifest))

    def test_valid_sdk(self):
        self.assertEqual(validate_sdk(self.sdk, "x86_64", "debug")["arch"], "x86_64")

    def test_reject_wrong_arch_and_mode(self):
        for arch, mode in (("aarch64", "debug"), ("x86_64", "release")):
            with self.subTest(arch=arch, mode=mode), self.assertRaisesRegex(ValueError, "mismatch"):
                validate_sdk(self.sdk, arch, mode)

    def test_reject_old_native_interface_abi(self):
        for version in (1, 2):
            self.manifest["abi_version"] = version
            self.save()
            with self.subTest(abi_version=version), self.assertRaisesRegex(ValueError, "abi_version mismatch"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_assembler_abi_flags_are_required(self):
        for invalid in (None, "-mabi=64", [64]):
            self.manifest["asflags"] = invalid
            self.save()
            with self.subTest(flags=invalid), self.assertRaisesRegex(ValueError, "asflags"):
                validate_sdk(self.sdk, "x86_64", "debug")

    def test_matching_compiler_abi(self):
        with patch("kernel_sdk.subprocess.check_output", side_effect=["x86_64-elf\n", "14.2.0\n"]):
            validate_sdk(self.sdk, "x86_64", "debug", Path("g++"))

    def test_mismatched_compiler_abi(self):
        for triple, version in (("aarch64-elf", "14.2.0"), ("x86_64-elf", "13.3.0")):
            with self.subTest(triple=triple, version=version), patch(
                "kernel_sdk.subprocess.check_output", side_effect=[triple, version]
            ), self.assertRaisesRegex(ValueError, r"C\+\+ module ABI"):
                validate_sdk(self.sdk, "x86_64", "debug", Path("g++"))

    def test_missing_sdk_has_build_instruction(self):
        with self.assertRaisesRegex(ValueError, "kernel-sdk"):
            validate_sdk(self.root / "missing", "x86_64", "debug")

    def test_modified_headers_cannot_mix_with_old_library(self):
        (self.sdk / "include/ok/uapi/syscall.h").write_text("changed ABI")
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_missing_boot_library(self):
        (self.sdk / "lib/libokernel_boot.a").unlink()
        with self.assertRaisesRegex(ValueError, "artifact is missing"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_manifest_without_required_artifact(self):
        del self.manifest["files"]["lib/libokernel.a"]
        self.save()
        with self.assertRaisesRegex(ValueError, "missing artifacts"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_reject_path_escape(self):
        self.manifest["files"]["../secret"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            validate_sdk(self.sdk, "x86_64", "debug")

    def test_elf_image_is_copied_without_conversion(self):
        elf = self.sdk / "image/kernel.elf"
        output = self.root / "image.bin"
        assemble_image(elf, output, self.sdk, "elf", None)
        self.assertEqual(output.read_bytes(), elf.read_bytes())

    def assemble_bios(self, payload):
        def objcopy(args, check):
            Path(args[-1]).write_bytes(payload)
        output = self.root / "image.bin"
        with patch("kernel_sdk.subprocess.run", side_effect=objcopy):
            assemble_image(self.sdk / "image/kernel.elf", output, self.sdk, "bios-disk", Path("objcopy"))
        return output.read_bytes()

    def test_bios_sector_payload_and_padding(self):
        image = self.assemble_bios(b"payload")
        self.assertEqual(len(image), 512 + BIOS_PAYLOAD_CAPACITY)
        self.assertEqual(image[510:519], b"\x55\xaapayload")
        self.assertFalse(any(image[519:]))

    def test_bios_payload_overflow_fails(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            self.assemble_bios(bytes(BIOS_PAYLOAD_CAPACITY + 1))

    def test_bios_invalid_signature_fails(self):
        (self.sdk / "boot/boot16.bin").write_bytes(bytes(512))
        with self.assertRaisesRegex(ValueError, "boot sector"):
            self.assemble_bios(b"payload")


if __name__ == "__main__":
    unittest.main()
