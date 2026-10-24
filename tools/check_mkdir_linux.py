#!/usr/bin/env python3
"""Boot a pinned Linux binary against a copy of an actual mkdir guest output."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/jbd2"))
from create_linux_fixture import cpio
from native_support import boot


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-evidence", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    record = dict(status="running", scope="actual-linux-readonly-mkdir-interoperability", commands=[],
                  host_mounts=False, linux_source_provenance="not-established", obfuscation_guest_boots=0, linux_guest_boots=0)
    def save():
        (out / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    def run(command, label):
        item = dict(command=list(map(str, command)), label=label); record["commands"].append(item); save()
        result = subprocess.run(item["command"], capture_output=True)
        (out / (label + ".log")).write_bytes(result.stdout + result.stderr)
        item["returncode"] = result.returncode
        if result.returncode: raise RuntimeError(label + " failed")
    save()
    try:
        evidence = args.native_evidence.resolve(); native = json.loads((evidence / "result.json").read_text())
        if native["status"] != "pass" or native.get("mkdir_checks") != "pass" or len(native.get("mkdir_nodes", {})) != 19:
            raise ValueError("passing actual mkdir source evidence required")
        source = evidence / "rootfs.ext4.img"
        if sha(source) != native["offline"]["disk_sha256"] or sha(evidence / "serial.log") != native["serial_sha256"]:
            raise ValueError("native source image or serial changed")
        record.update(native_evidence=str(evidence), native_receipt_sha256=sha(evidence / "result.json"),
                      source_image_sha256=sha(source), source_serial_sha256=sha(evidence / "serial.log"))
        capture = json.loads((args.fixture / "capture-manifest.json").read_text())
        kernel_source = args.fixture / "linux-bzImage"
        if sha(kernel_source) != capture["linux_image_sha256"]: raise ValueError("pinned Linux binary changed")
        kernel = out / "linux-bzImage"; shutil.copy2(kernel_source, kernel)
        record["linux_image_sha256"] = sha(kernel)
        record["tool_sha256"] = {name: sha(Path(shutil.which(name)).resolve()) for name in ("gcc", "qemu-system-x86_64", "e2fsck")}
        names = ("tests/linux/mkdir_init.c", "tools/check_mkdir_linux.py", "tools/jbd2/create_linux_fixture.py",
                 "tools/jbd2/native_support.py", "tools/kernel_sdk.py")
        record["source_sha256"] = {}
        for name in names:
            target = out / "sources" / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target); record["source_sha256"][name] = sha(target)
        init = out / "init"
        run(["gcc", "-static", "-O2", "-Wall", "-Wextra", "-Werror", out / "sources/tests/linux/mkdir_init.c", "-o", init], "compile-init")
        entries = [(name, 0o040755, b"", 0, 0) for name in ("dev", "mnt")]
        entries += [("dev/console", 0o020600, b"", 5, 1), ("init", 0o100755, init.read_bytes(), 0, 0)]
        initrd = out / "initramfs.cpio"; initrd.write_bytes(cpio(entries))
        disk = out / "guest-output.img"; shutil.copy2(source, disk)
        command = ["qemu-system-x86_64", "-m", "512M", "-kernel", str(kernel), "-initrd", str(initrd),
                   "-append", "console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr", "-drive",
                   f"file={disk},format=raw,if=none,id=fixture,readonly=on", "-device", "virtio-blk-pci,drive=fixture"]
        record["commands"].append(dict(label="linux-readonly", command=command)); save()
        boot(command, "LINUX_MKDIR_PASS nodes=19 files=4 mode=pass uid=pass gid32=pass links=pass contents=pass mount=readonly unmount=pass\r\n", out / "linux.log")
        if sha(disk) != record["source_image_sha256"]: raise ValueError("readonly Linux guest altered the image")
        run(["e2fsck", "-fn", disk], "post-linux-fsck")
        record.update(status="pass", nodes=19, files=4, image_unchanged=True, linux_guest_boots=1)
    except Exception as error:
        record.update(status="failed", error=str(error))
        print(str(error), file=sys.stderr)
    finally:
        record["artifact_sha256"] = {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob("*"))
                                     if path.is_file() and path.name != "result.json"}
        save()
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
