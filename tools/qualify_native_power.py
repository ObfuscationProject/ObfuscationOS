#!/usr/bin/env python3
"""Exercise ordinary console enrollment, clean halt and same-disk login in QEMU.

Consumes explicit prebuilt SDK-only artifacts. A successful serial marker alone
is insufficient: retain linked terminal instructions, QMP CPU state and direct
read-only disk checks. Never repair the guest disk between the two boots.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kernel_sdk import validate_sdk
from qemu_distro import command_for
from native_login_evidence import account, SEED
from native_power_observer import Qmp, require, terminal_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Guest:
    def __init__(self, campaign, label):
        self.campaign, self.label, self.data = campaign, label, bytearray()
        self.directory = tempfile.TemporaryDirectory(prefix="ok-power-qmp-")
        self.socket = Path(self.directory.name) / "control.qmp"
        command = command_for(campaign.args.qemu.resolve(), "x86_64", campaign.kernel,
                              campaign.disk, "none", native_profile=True)
        command += ["-smp", "1", "-accel", "tcg,thread=single", "-qmp",
                    "unix:" + str(self.socket) + ",server=on,wait=off"]
        self.row = {"label": label, "argv": command, "disk_before_sha256": sha(campaign.disk),
                    "host_retirement_after_observed_halt": False}
        campaign.report["guests"].append(self.row)
        campaign.save()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        self.qmp = None
        deadline = time.monotonic() + 5
        while not self.socket.exists() and self.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        try:
            require(self.socket.exists(), "QMP socket was not created")
            self.qmp = Qmp(self.socket, campaign.out / (label + ".qmp.json"))
        except BaseException:
            self.stop()
            raise

    def save(self):
        (self.campaign.out / (self.label + ".serial")).write_bytes(self.data)

    def prompt(self, marker, start=0):
        deadline = time.monotonic() + self.campaign.args.timeout
        while marker not in self.data[start:]:
            require(time.monotonic() < deadline, self.label + ": serial deadline exceeded")
            ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
            if not ready:
                require(self.process.poll() is None, self.label + ": QEMU exited before acceptance")
                continue
            chunk = os.read(self.process.stdout.fileno(), 16384)
            require(chunk, self.label + ": guest serial ended")
            self.data.extend(chunk)
            require(len(self.data) <= 4 * 1024 * 1024, "guest serial capacity exceeded")
            self.save()
            for bad in (b"OK_TEST_FAIL", b"event=fatal-hold", b"OK_SHUTDOWN failed=", b"Kernel panic", b"boot=failed"):
                require(bad not in self.data, self.label + ": guest failure " + bad.decode())
        return self.data.index(marker, start) + len(marker)

    def send(self, line):
        require(b"\n" not in line and b"\r" not in line, "one complete input line required")
        self.row.setdefault("input", []).append({"serial_offset": len(self.data), "bytes": len(line),
                                                 "sha256": hashlib.sha256(line).hexdigest()})
        self.process.stdin.write(line + b"\n")
        self.process.stdin.flush()

    def halt(self, start):
        self.send(b"service-ctl halt")
        self.prompt(b"OK_SHUTDOWN clean=1 action=halt\r\n", start)
        tail = bytes(self.data[start:])
        markers = [b"event=quiesce-started ", b"event=graph-stopped ", b"event=quiesced ",
                   b"OK_STORAGE_SHUTDOWN scope=provider state=clean_sealed platform=0",
                   b"OK_SHUTDOWN clean=1 action=halt"]
        positions = [tail.find(marker) for marker in markers]
        require(all(position >= 0 for position in positions) and positions == sorted(set(positions)),
                "shutdown causal marker sequence is missing or out of order")
        require(tail.count(markers[-1]) == 1, "clean action was published more than once")
        time.sleep(0.1)
        observation = self.qmp.observe_terminal(self.campaign.site,
            self.campaign.out / (self.label + ".terminal.json"))
        self.row["terminal_observation"] = {"path": str(self.campaign.out / (self.label + ".terminal.json")),
            "sha256": sha(self.campaign.out / (self.label + ".terminal.json"))}
        self.row["clean_storage_then_observed_terminal_halt"] = observation["status"] == "passed"
        self.row["causal_marker_offsets"] = positions

    def stop(self):
        if self.qmp:
            self.qmp.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        remaining = self.process.stdout.read()
        if remaining:
            self.data.extend(remaining)
        self.process.stdin.close()
        self.process.stdout.close()
        self.save()
        self.row.update(returncode=self.process.returncode,
            serial_sha256=hashlib.sha256(self.data).hexdigest(), disk_after_sha256=sha(self.campaign.disk),
            host_retirement_after_observed_halt=self.row.get("clean_storage_then_observed_terminal_halt", False))
        transcript = self.campaign.out / (self.label + ".qmp.json")
        if transcript.is_file():
            self.row["qmp_transcript_sha256"] = sha(transcript)
        self.directory.cleanup()
        self.campaign.save()


class Campaign:
    def __init__(self, args):
        self.args, self.out = args, args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.report = {"schema": 1, "status": "preparing", "scope":
            "Actual single-CPU x86_64 ordinary login and PID1-requested clean halt, same-disk authentication, QMP terminal observation and direct read-only fsck. No physical/SMP/reboot/poweroff/full-milestone claim.",
            "architecture": "x86_64", "mode": args.mode, "sdk_only": True,
            "kernel_source_compiled_by_os": False, "unwrapped_login": True, "unwrapped_shell": True,
            "physical": False, "smp": False, "full_M0_M12": False, "commands": [], "guests": [],
            "runner_sha256": sha(Path(__file__)), "observer_sha256": sha(Path(__file__).with_name("native_power_observer.py"))}
        self.kernel, self.elf = args.kernel.resolve(), args.elf.resolve()
        self.disk = self.out / "disk.img"

    def save(self):
        temporary = self.out / "result.tmp"
        temporary.write_text(json.dumps(self.report, indent=2) + "\n")
        temporary.replace(self.out / "result.json")

    def command(self, label, argv):
        path = self.out / (label + ".log")
        with path.open("xb") as stream:
            result = subprocess.run(list(map(str, argv)), stdout=stream, stderr=subprocess.STDOUT)
        self.report["commands"].append({"argv": list(map(str, argv)), "returncode": result.returncode,
                                         "log": path.name, "log_sha256": sha(path)})
        self.save()
        require(result.returncode == 0, label + " failed")
        return path.read_bytes()

    def verify_sources(self):
        for owner, pin in self.report["source_freezes"].items():
            path = Path(pin["path"])
            require(sha(path) == pin["sha256"], "source inventory changed")
            source = Path(pin["root"])
            inventory = json.loads(path.read_text())
            expected = {row["path"] for row in inventory["files"]}
            excluded = set(inventory["excluded_directory_names"])
            actual = set()
            for directory, children, files in os.walk(source, followlinks=False):
                children[:] = [name for name in children if name not in excluded]
                actual.update(str((Path(directory) / name).relative_to(source)) for name in files)
            require(actual == expected, owner + " frozen source file set changed")
            for row in inventory["files"]:
                require(sha(source / row["path"]) == row["sha256"], owner + " frozen source changed")

    def dump(self, label, path):
        destination = self.out / (label + ".bytes")
        before = sha(self.disk)
        self.command(label, [self.args.debugfs.resolve(), "-R", "dump " + path + " " + str(destination), self.disk])
        require(destination.is_file(), "disk pathname could not be read: " + path)
        require(sha(self.disk) == before, "read-only disk dump changed the disk")
        return destination.read_bytes()

    def check_disk(self, label):
        before = sha(self.disk)
        with self.disk.open("rb") as stream:
            stream.seek(1024)
            superblock = stream.read(1024)
        require(struct.unpack_from("<H", superblock, 56)[0] == 0xef53, "ext4 superblock missing")
        state = struct.unpack_from("<H", superblock, 58)[0]
        incompat = struct.unpack_from("<I", superblock, 96)[0]
        require(state & 1 and not state & 2 and not incompat & 4, "guest did not leave a clean recovery-free root")
        self.command(label + "-direct-fsck", [self.args.fsck.resolve(), "-fn", self.disk])
        require(sha(self.disk) == before, "read-only disk verification changed the disk")
        return {"sha256": before, "superblock_state": state, "feature_incompat": incompat,
                "host_recovery_performed": False}

    def run(self):
        args = self.args
        require(sha(args.build_receipt) == args.build_receipt_sha256, "build receipt pin differs")
        build = json.loads(args.build_receipt.read_text())
        require(build.get("status") == "passed" and build.get("mode") == args.mode and
                build.get("native_console_login") is True, "ordinary matching console build receipt required")
        sdk = Path(build["kernel_sdk"])
        require(sha(sdk / "manifest.json") == build["sdk_manifest_sha256"], "build SDK manifest changed")
        manifest = validate_sdk(sdk, "x86_64", args.mode)
        require(manifest["abi_version"] == 69 and manifest["native_power_profile"] ==
                "original-init-scalar-prepare-queued-commit-v1", "power SDK cohort differs")
        self.report["build_receipt"] = {"path": str(args.build_receipt.resolve()), "sha256": args.build_receipt_sha256}
        self.report["sdk"] = {"path": str(sdk), "manifest_sha256": build["sdk_manifest_sha256"]}
        self.report["source_freezes"] = build["source_freezes"]
        self.verify_sources()
        for path in (self.kernel, self.elf, args.initial.resolve()):
            require(build["products"].get(str(path)) == sha(path), "prebuilt product is not in exact build receipt")
        self.report["input_products"] = {str(path): sha(path) for path in (self.kernel, self.elf, args.initial.resolve())}
        for tool in (args.qemu, args.objdump, args.fsck, args.debugfs):
            require(tool.is_file(), "explicit tool is missing")
        self.report["tools"] = {str(path.resolve()): sha(path.resolve())
                                for path in (args.qemu, args.objdump, args.fsck, args.debugfs)}
        disassembly = self.command("linked-terminal-disassembly", [args.objdump.resolve(), "-d", "--demangle",
            "--disassemble=ok::arch::terminal_power_action(ok::SystemPowerAction)", self.elf])
        self.site = terminal_site(disassembly.decode())
        shutil.copy2(args.initial, self.disk)
        require(self.dump("initial-accounts", "/etc/accounts.db") == SEED, "initial disk is not unconfigured")
        password = ("PowerTestOnly-" + secrets.token_hex(10)).encode()
        wrong = ("WrongTestOnly-" + secrets.token_hex(10)).encode()
        token = ("POWER_PERSIST_" + secrets.token_hex(10)).encode()
        credentials = {"account": "qual_admin", "password": password.decode(), "wrong_password": wrong.decode(),
                       "test_credentials_only": True}
        (self.out / "qualification-credentials.json").write_text(json.dumps(credentials, indent=2) + "\n")
        os.chmod(self.out / "qualification-credentials.json", 0o600)
        self.report["status"] = "running"
        self.save()
        for index, label in enumerate(("enroll-halt", "restart-login-halt")):
            guest = Guest(self, label)
            try:
                if index == 0:
                    at = guest.prompt(b"Account name: ")
                    guest.send(b"qual_admin")
                    at = guest.prompt(b"Password: ", at)
                    guest.send(password)
                    at = guest.prompt(b"Repeat password: ", at)
                    guest.send(password)
                else:
                    at = guest.prompt(b"Login: ")
                    require(b"Create the first administrator" not in guest.data, "restart reopened enrollment")
                    guest.send(b"qual_admin")
                    at = guest.prompt(b"Password: ", at)
                    guest.send(wrong)
                    at = guest.prompt(b"Login incorrect.", at)
                    began = time.monotonic()
                    require(b"oksh> " not in guest.data, "wrong password entered a shell")
                    at = guest.prompt(b"Login: ", at)
                    observed_delay = time.monotonic() - began
                    # Exclude KDF time. Allow bounded serial-observer scheduling
                    # around the product's one-second absolute guest deadline.
                    require(observed_delay >= 0.9, "authentication retry delay was bypassed")
                    guest.row["retry_delay_after_failure_seconds"] = observed_delay
                    guest.send(b"qual_admin")
                    at = guest.prompt(b"Password: ", at)
                    guest.send(password)
                at = guest.prompt(b"oksh> ", at)
                command = b"echo " + token + b" > /root/power-persist" if not index else b"cat /root/power-persist"
                guest.send(command)
                if index:
                    at = guest.prompt(token + b"\r\n", at)
                at = guest.prompt(b"oksh> ", at)
                guest.halt(at)
                for secret in (password, wrong):
                    require(not any(secret[n:n + 8] in guest.data for n in range(len(secret) - 7)), "password was echoed")
                require(b"NATIVE_LOGIN_SESSION" not in guest.data and b"NATIVE_LOGIN_PUBLICATION" not in guest.data,
                        "ordinary console product was replaced by a login test wrapper")
            finally:
                guest.stop()
            disk = self.check_disk(label)
            data = self.dump(label + "-accounts", "/etc/accounts.db")
            disk["account"] = account(data, password, "active")
            require(self.dump(label + "-persisted-file", "/root/power-persist") == token + b"\n", "shutdown lost file bytes")
            self.report.setdefault("disks", []).append(disk)
            if index:
                require(self.report["disks"][0]["account"]["sha256"] == disk["account"]["sha256"],
                        "restart authentication changed credentials")
            self.save()
        self.verify_sources()
        for path, digest in self.report["input_products"].items():
            require(sha(Path(path)) == digest, "input product changed during qualification")
        self.report.update(status="passed", guest_boots=2, observed_terminal_halts=2,
                           same_disk_restart=True, host_recovery_performed=False)
        self.save()
        print("PASS ordinary enrollment, two observed terminal halts and same-disk authentication", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build-receipt", "kernel", "elf", "initial", "output", "qemu", "objdump", "fsck", "debugfs"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--build-receipt-sha256", required=True)
    parser.add_argument("--mode", required=True, choices=("debug", "release"))
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    campaign = Campaign(args)
    try:
        campaign.run()
    except BaseException as error:
        campaign.report.update(status="failed", error=repr(error))
        campaign.save()
        raise


if __name__ == "__main__":
    main()
