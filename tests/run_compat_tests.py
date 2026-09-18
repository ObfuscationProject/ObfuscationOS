#!/usr/bin/env python3
"""Run the OS-owned Linux adapter model against an exported native Kernel SDK."""

import argparse
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-sdk", required=True, type=Path)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    sdk = args.kernel_sdk.resolve()
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "tools"))
    from kernel_sdk import validate_sdk

    if platform.machine().lower() not in {"x86_64", "amd64"}:
        parser.error("the host model test needs an x86_64 host")
    import json
    metadata = json.loads((sdk / "manifest.json").read_text())
    if metadata.get("arch") != "x86_64":
        parser.error("the host model test needs an x86_64 Kernel SDK")
    validate_sdk(sdk, "x86_64", metadata.get("mode", ""))
    model_tests = (
        ("linux-pci-model", "linux_pci_model_tests.cpp", "pci_model.cpp"),
        ("linux-abi-snapshot", "linux_abi_snapshot_tests.cpp", "abi_snapshot.cpp"),
    )
    with tempfile.TemporaryDirectory(prefix="obos-compat-") as work:
        for name, test_source, implementation in model_tests:
            executable = Path(work) / name
            subprocess.run([
                args.cxx, "-std=c++23", "-Wall", "-Wextra", "-Werror", "-no-pie",
                "-I", str(sdk / "include"),
                "-I", str(project / "compat/linux/include"),
                str(project / "tests/compat" / test_source),
                str(project / "compat/linux/src" / implementation),
                str(sdk / "lib/libokernel.a"), "-o", str(executable),
            ], check=True)
            subprocess.run([str(executable)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
