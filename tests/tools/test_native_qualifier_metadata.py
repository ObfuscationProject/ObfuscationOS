"""Run qualifier preparation with stubbed inputs; no guest execution is claimed."""
import argparse
from contextlib import ExitStack
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

QUALIFIERS = tuple(importlib.import_module(name) for name in (
    "qualify_native_init", "qualify_native_pid1", "qualify_service_graph"))


class NativeQualifierMetadataTests(unittest.TestCase):
    def prepare(self, module, *, manifest=None, reject_source=False):
        """Exercise run/save through SDK admission, stopping before any build."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "qualification"
            args = argparse.Namespace(
                arch="x86_64", mode="debug", musl_mode="debug", output=out,
                softfp_build=None, softfp_manifest_sha256=None,
                source_inventory=root / "source-inventory.json",
                source_inventory_sha256="0" * 64,
                toolchain=root / "toolchain", compiler_sha256="0" * 64,
                qemu=root / "qemu", qemu_sha256="0" * 64,
                kernel_sdk=root / "input-sdk", sdk_manifest_sha256="0" * 64)
            saved = []
            original_save = module.save

            def save(path, record):
                saved.append(copy.deepcopy(record))
                original_save(path, record)

            def copy_inventory(source, target, files):
                if target == out / "sdk":
                    raise RuntimeError("stop before retained SDK copy or build")
                target.mkdir(parents=True, exist_ok=False)

            with ExitStack() as stack:
                stack.enter_context(patch.object(module, "save", side_effect=save))
                source = stack.enter_context(patch.object(module, "admit_source", return_value={}))
                if reject_source:
                    source.side_effect = ValueError("source rejected before SDK admission")
                stack.enter_context(patch.object(module, "copy_inventory", side_effect=copy_inventory))
                stack.enter_context(patch.object(module, "sha", return_value="0" * 64))
                stack.enter_context(patch.object(module, "require_hash"))
                stack.enter_context(patch.object(module.shutil, "which", return_value=str(root / "tool")))
                validator = stack.enter_context(patch.object(module, "validate_sdk", return_value=manifest))
                if manifest is None:
                    validator.side_effect = ValueError("SDK admission rejected")
                subprocess = stack.enter_context(patch.object(module.subprocess, "run"))
                guest = stack.enter_context(patch.object(module.subprocess, "Popen"))
                with self.assertRaisesRegex((ValueError, RuntimeError),
                        "source rejected|SDK admission rejected|stop before retained SDK copy"):
                    module.run(args)
                self.assertEqual(validator.call_count, 0 if reject_source else 1)
                subprocess.assert_not_called()
                guest.assert_not_called()
            result = json.loads((out / "result.json").read_text())
        self.assertEqual(saved[0]["status"], "preparing")
        self.assertIsNone(saved[0]["sdk_abi"])
        self.assertIsNone(saved[0]["native_init_profile"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["guest_executed"])
        self.assertFalse(result["native_execution_accepted"])
        self.assertFalse(result["kernel_source_compiled"])
        self.assertEqual(result["commands"], [])
        return result

    def test_pre_admission_failure_cannot_advertise_sdk_capabilities(self):
        for module in QUALIFIERS:
            with self.subTest(qualifier=module.__name__):
                result = self.prepare(module, reject_source=True)
                self.assertIsNone(result["sdk_abi"])
                self.assertIsNone(result["native_init_profile"])

    def test_rejected_sdk_cannot_advertise_sdk_capabilities(self):
        for module in QUALIFIERS:
            with self.subTest(qualifier=module.__name__):
                result = self.prepare(module)
                self.assertIsNone(result["sdk_abi"])
                self.assertIsNone(result["native_init_profile"])

    def test_admitted_metadata_comes_from_validator_result(self):
        # The second value tests data flow across the admission boundary; SDK
        # admission policy itself is covered by test_kernel_sdk.py.
        for abi, profile in ((67, "designated-pid1-native-linux-adoption-v2"),
                             (999, "validator-returned-profile-fixture")):
            for module in QUALIFIERS:
                with self.subTest(qualifier=module.__name__, profile=profile):
                    result = self.prepare(module, manifest=dict(
                        abi_version=abi, native_init_profile=profile,
                        compiler={"family": "gcc"}, files={}))
                    self.assertEqual(result["sdk_abi"], abi)
                    self.assertEqual(result["native_init_profile"], profile)


if __name__ == "__main__":
    unittest.main()
