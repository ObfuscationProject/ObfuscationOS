#!/usr/bin/env python3
"""Drive getty, login and oksh over the serial console of a journalled login image.

The image comes from `--native_console_login=y` and `xmake -b rootfs-ext4-journalled`
(plus `distro_image` for the kernel). It is admitted like `xmake qemu-distro`
does, then copied, so the built image stays unenrolled. The first boot enrolls
the administrator, checks the shell on its pts, logs out, sees getty close the
session and open a new one, fails one login and logs in again. An optional
second boot of the same disk logs in once more. Serial logs, the steps and
their timings (PBKDF2 enrollment and login under the selected QEMU) go to
--out. This is a single-architecture driver; it does not admit receipts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from console_login_disk import admit
from kernel_sdk import ARCH_TRIPLES

NAME = b"chosen_admin"
PASSWORD = b"Getty-S4-correct-horse"
WRONG = b"Getty-S4-wrong-battery"
USER, USER_PASSWORD = b"alice", b"Getty-S4-ordinary-staple"
FAILURES = (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed", b"event=fatal-hold",
            b"login: unable to establish", b"GETTY event=error", b"oksh: console input is not available")
# The serial line shows every newline as CRLF; the pts adds its own CR (ONLCR).
OPEN = re.compile(rb"GETTY event=open pts=([0-9]+) pid=([0-9]+)\r*\n")
CLOSE = re.compile(rb"GETTY event=close pts=([0-9]+) pid=([0-9]+) status=(-?[0-9]+) reason=([a-z]+)\r*\n")
REAP = re.compile(rb"event=reap service=console pid=([0-9]+) generation=([0-9]+) [^\r\n]* status=([0-9]+)\r*\n")
LAUNCH = re.compile(rb"event=launch service=console pid=([0-9]+) generation=([0-9]+) ")
# stat prints st_mode in hex: S_IFCHR | 0620.
PTS_MODE = b"mode=2190 "


# Debug kernels write "[CRLF]OK_<NAME> ...CRLF" diagnostics, and PID1 its
# NATIVE_PID1 events, into the serial stream at any point, even inside a line
# the pts is echoing. A CRLF that ends
# pts output is CR CR LF (ONLCR plus the serial CR), so it is never taken.
DIAGNOSTIC = re.compile(rb"(?:(?<!\r)\r\n)?(?:OK_[A-Z][A-Z0-9_]*|NATIVE_PID1) [^\r\n]*\r\n")


def clean(data: bytes) -> bytes:
    return DIAGNOSTIC.sub(b"", data).replace(b"\r", b"")


class Failure(RuntimeError):
    pass


class Guest:
    """One QEMU process with its serial console on stdin/stdout."""

    def __init__(self, command: list[str], log: Path, timeout: float):
        self.log, self.timeout = log, timeout
        self.data = bytearray()
        self.started = time.monotonic()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)

    def receive(self, pattern: bytes | re.Pattern, start: int, timeout: float | None = None) -> re.Match | int:
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            if isinstance(pattern, bytes):
                found = self.data.find(pattern, start)
                if found >= 0:
                    return found + len(pattern)
            else:
                match = pattern.search(self.data, start)
                if match:
                    return match
            if time.monotonic() > deadline:
                self.save()
                raise Failure(f"{self.log.name}: no {pattern!r} after offset {start}")
            ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
            if not ready:
                if self.process.poll() is not None:
                    self.save()
                    raise Failure(f"{self.log.name}: QEMU exited")
                continue
            chunk = os.read(self.process.stdout.fileno(), 16384)
            if not chunk:
                self.save()
                raise Failure(f"{self.log.name}: serial output ended")
            self.data.extend(chunk)
            for marker in FAILURES:
                if marker in self.data:
                    self.save()
                    raise Failure(f"{self.log.name}: guest failure {marker.decode()}")
            self.save()

    def send(self, line: bytes) -> int:
        offset = len(self.data)
        self.process.stdin.write(line + b"\n")
        self.process.stdin.flush()
        return offset

    def save(self) -> None:
        self.log.write_bytes(bytes(self.data))

    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.save()


class Session:
    def __init__(self, guest: Guest, steps: list):
        self.guest, self.steps = guest, steps

    def step(self, name: str, **facts) -> None:
        facts.update(step=name, serial_offset=len(self.guest.data),
                     seconds=round(time.monotonic() - self.guest.started, 3))
        self.steps.append(facts)
        print(f"[getty-login] {name} {json.dumps({k: v for k, v in facts.items() if k != 'step'})}", flush=True)

    def answer(self, prompt: bytes, line: bytes, start: int) -> int:
        at = self.guest.receive(prompt, start)
        self.guest.send(line)
        return at

    def opened(self, start: int) -> tuple[int, int, int]:
        match = self.guest.receive(OPEN, start)
        return int(match[1]), int(match[2]), match.end()

    def command(self, line: bytes, start: int) -> tuple[bytes, int]:
        at = self.guest.receive(b"oksh> ", start)
        sent = self.guest.send(line)
        end = self.guest.receive(b"oksh> ", sent)
        output = clean(bytes(self.guest.data[sent:end - len(b"oksh> ")]))
        # The pts echoes the typed line before the command's output.
        if not output.startswith(line + b"\n"):
            raise Failure(f"command {line!r} was not echoed on the pts: {output!r}")
        return output[len(line) + 1:], end - len(b"oksh> ")

    def shell(self, pts: int, start: int, user: bytes, home: bytes = b"/root") -> int:
        output, start = self.command(b"whoami | cat", start)
        if output != user + b"\n":
            raise Failure(f"whoami pipeline printed {output!r}")
        output, start = self.command(b"pwd", start)
        if output != home + b"\n":
            raise Failure(f"pwd printed {output!r}")
        output, start = self.command(b"ls /dev/pts", start)
        if str(pts).encode() not in output.split():
            raise Failure(f"/dev/pts does not list the session's pts {pts}: {output!r}")
        stat, start = self.command(b"stat /dev/pts/" + str(pts).encode(), start)
        if PTS_MODE not in stat or b"ino=" + str(34816 + pts).encode() not in stat:
            raise Failure(f"the session's pts is not a 0620 character device: {stat!r}")
        self.step("shell", pts=pts, whoami=user.decode(), pts_listing=output.decode(errors="replace"),
                  pts_stat=stat.decode(errors="replace"))
        return start

    def logout(self, pts: int, pid: int, start: int) -> tuple[int, int, int]:
        at = self.guest.receive(b"oksh> ", start)
        sent = self.guest.send(b"exit")
        close = self.guest.receive(CLOSE, sent)
        if (int(close[1]), int(close[2])) != (pts, pid) or close[4] not in (b"exit", b"hangup"):
            raise Failure(f"unexpected close event {close[0]!r} for pts {pts} pid {pid}")
        status = int(close[3])
        self.step("logout", pts=pts, pid=pid, status=status, reason=close[4].decode())
        if status != 0:
            raise Failure(f"login session exited with status {status}")
        # getty exits 0 and PID1 starts the console service again: a new lease.
        reap = self.guest.receive(REAP, close.end())
        launch = self.guest.receive(LAUNCH, reap.end())
        if int(reap[3]) != 0 or int(launch[2]) != int(reap[2]) + 1:
            raise Failure(f"PID1 did not restart the console service: {reap[0]!r} {launch[0]!r}")
        self.step("console-restart", getty=int(launch[1]), generation=int(launch[2]))
        new_pts, new_pid, end = self.opened(close.end())
        if new_pid == pid:
            raise Failure("getty did not start a new login child")
        self.step("getty-restart", pts=new_pts, pid=new_pid)
        return new_pts, new_pid, end

    def login(self, start: int, wrong_first: bool, name: bytes = NAME, password: bytes = PASSWORD) -> int:
        at = self.guest.receive(b"Login: ", start)
        if wrong_first:
            self.guest.send(name)
            self.answer(b"Password: ", WRONG, at)
            at = self.guest.receive(b"Login incorrect.", at)
            at = self.guest.receive(b"Login: ", at)
            self.step("wrong-password-refused")
        self.guest.send(name)
        at = self.guest.receive(b"Password: ", at)
        sent = self.guest.send(password)
        before = time.monotonic()
        end = self.guest.receive(b"oksh> ", sent)
        self.step("login", user=name.decode(), seconds_to_shell=round(time.monotonic() - before, 3))
        return end - len(b"oksh> ")

    def add_user(self, start: int) -> int:
        """:useradd as the administrator; the shell that follows is the administrator's."""
        at = self.answer(b"Login: ", b":useradd", start)
        at = self.answer(b"Login: ", NAME, at)
        at = self.answer(b"Password: ", PASSWORD, at)
        at = self.answer(b"New account name: ", USER, at)
        at = self.answer(b"New password: ", USER_PASSWORD, at)
        at = self.guest.receive(b"Repeat new password: ", at)
        sent = self.guest.send(USER_PASSWORD)
        before = time.monotonic()
        at = self.guest.receive(b"Account created.", sent)
        end = self.guest.receive(b"oksh> ", at)
        self.step("user-added", user=USER.decode(), seconds_to_shell=round(time.monotonic() - before, 3))
        return end - len(b"oksh> ")


def check_serial(data: bytes) -> None:
    data = clean(data)
    # Passwords are read with ECHO cleared; account names are echoed by the pts.
    for secret in (PASSWORD, WRONG, USER_PASSWORD):
        if secret in data:
            raise Failure("a password was echoed to the console")
    if b"Account name: " + NAME + b"\n" not in data or b"Login: " + NAME + b"\n" not in data:
        raise Failure("account names were not echoed by the pts line discipline")
    if b"Login: " + NAME + b"\n\n" in data:
        raise Failure("login wrote an extra newline after echoed input")


def boot(args, image: Path, label: str, steps: list, first: bool) -> bytes:
    command = [str(part) for part in command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), image,
                                                  "none", native_profile=True)]
    guest = Guest(command, args.out / f"{label}.serial.log", args.timeout)
    session = Session(guest, steps)
    session.step("boot", label=label, argv=command)
    try:
        pts, pid, at = session.opened(0)
        session.step("getty-open", pts=pts, pid=pid)
        if first:
            at = session.answer(b"Account name: ", NAME, at)
            at = session.answer(b"Password: ", PASSWORD, at)
            at = guest.receive(b"Repeat password: ", at)
            sent = guest.send(PASSWORD)
            before = time.monotonic()
            at = guest.receive(b"oksh> ", sent) - len(b"oksh> ")
            session.step("enrolled", seconds_to_shell=round(time.monotonic() - before, 3))
        else:
            at = session.login(at, wrong_first=False)
        at = session.shell(pts, at, b"root")
        pts, pid, at = session.logout(pts, pid, at)
        if first:
            at = session.login(at, wrong_first=True)
            at = session.shell(pts, at, b"root")
            pts, pid, at = session.logout(pts, pid, at)
            if args.ordinary:
                # login hands the pts to the user (fchown, 0620) before the
                # credentials drop and checks it again afterwards.
                at = session.add_user(at)
                pts, pid, at = session.logout(pts, pid, at)
                at = session.login(at, wrong_first=False, name=USER, password=USER_PASSWORD)
                at = session.shell(pts, at, b"uid1000", b"/home/" + USER)
                pts, pid, at = session.logout(pts, pid, at)
        guest.receive(b"Login: ", at)
        session.step("login-prompt-again")
    finally:
        guest.stop()
    return bytes(guest.data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    for name in ("qemu", "kernel", "image", "root", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--second-boot", action="store_true")
    parser.add_argument("--ordinary", action="store_true", help="also create and log in an ordinary account")
    args = parser.parse_args()
    debugfs = Path(shutil.which("debugfs") or "/missing-debugfs")
    admit(args.image.resolve(), args.root.resolve(), debugfs)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    image = args.out / "disk.img"
    shutil.copyfile(args.image.resolve(), image)
    steps: list = []
    result = dict(arch=args.arch, image=str(args.image.resolve()), steps=steps, status="failed")
    try:
        serial = boot(args, image, "boot1", steps, first=True)
        check_serial(serial)
        if args.second_boot:
            check_serial(serial + boot(args, image, "boot2", steps, first=False))
        result["status"] = "passed"
    finally:
        (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"[getty-login] {args.arch} passed: {args.out}")


if __name__ == "__main__":
    try:
        main()
    except Failure as error:
        raise SystemExit(f"[getty-login] FAIL: {error}")
