#!/usr/bin/env python3
"""Package a non-default native TCP /init fixture with exact archive readback."""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys

from mkarchive import pack
from package_musl_udp_fixture import archive_inventory, inspect_archive, inspect_static, inventory, pin, sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("x86_64",), required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--normal-root", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        parser.error("use PYTHONDONTWRITEBYTECODE=1 python3 -B")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    before = None
    error = None
    record = {"schema": 1, "status": "failed", "arch": args.arch, "mode": args.mode,
              "normal_root_modified": False, "guest_executed": False}
    try:
        before = inventory(args.normal_root)
        probe = pin(args.probe)
        inspect_static(args.probe, args.arch, 0)
        root = args.out / "root"
        shutil.copytree(args.normal_root, root, copy_function=shutil.copy2)
        shutil.copy2(args.probe, root / "init")
        (root / "init").chmod(0o755)
        expected = dict(before)
        expected["/init"] = {"mode": 0o100755, "bytes": args.probe.stat().st_size,
                             "sha256": probe["sha256"]}
        if inventory(root) != expected:
            raise ValueError("native TCP root differs outside the explicit /init replacement")
        archive = args.out / "boot.okar"
        blob = pack(root)
        archive.write_bytes(blob)
        if inspect_archive(blob) != archive_inventory(root):
            raise ValueError("native TCP independent archive payload readback differs")
        include = args.out / "boot.okar.inc"
        include.write_text('// ' + sha(archive) + '\n.incbin "' + str(archive) + '"\n')
        if pin(args.probe) != probe or inventory(args.normal_root) != before:
            raise ValueError("native TCP fixture input changed during packaging")
        record.update(status="packaged-not-linked-or-executed", normal_root_before=before,
                      probe=probe, copied_probe=pin(root / "init"), root_entries=expected,
                      archive=pin(archive), archive_include=pin(include),
                      archive_entries=archive_inventory(root), independent_archive_payloads_identical=True)
    except (OSError, ValueError) as failure:
        error = str(failure)
    finally:
        if before is not None:
            try:
                record["normal_root_after"] = inventory(args.normal_root)
                if record["normal_root_after"] != before:
                    error = error or "normal root changed during native TCP packaging"
            except (OSError, ValueError) as failure:
                error = error or str(failure)
        if error:
            record.update(status="failed", error=error)
        (args.out / "receipt.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if error:
        print("NATIVE_TCP_PACKAGE_FAIL " + error, file=sys.stderr)
        return 1
    print("NATIVE_TCP_PACKAGE_PASS receipt=" + str(args.out / "receipt.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
