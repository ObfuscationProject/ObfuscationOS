#!/usr/bin/env python3
"""Login lane: drive getty, login and oksh over the serial console of a journalled login image.

For the configured profile the runner builds the distribution kernel, the
journalled product image (`rootfs-ext4-journalled` with getty and login
selected) and the lane-only native helper tests/native/oksh_job_probe.c. It
admits the product image like `xmake qemu-distro`, then packs a lane disk from
a copy of the same login root with the helper added as /bin/oksh-jobs, with
the same Linux journal activation; the admitted product files of both disks
must be identical. The product image itself is never booted or changed.

The first boot of the lane disk enrolls the administrator and checks on the
pts: the shell is the session leader with the pts as its controlling
terminal; a foreground job runs in its own group, which owns the terminal; a
background job runs in its own group without it and is reported Done; ^C
kills a foreground job; ^Z stops one (`[1]+ Stopped`), `jobs` lists it,
`exit` warns, `fg` resumes it in the foreground and ^C ends it; a job stopped
with ^Z at logout is hung up by the second `exit`. Each logout is followed by
getty's close event, PID1's restart of the console service and a new session;
a wrong password is refused before the right one logs in, and every session's
pts list shows that earlier pairs were released. An ordinary account can also
be created and logged in. The second boot of the same disk logs the
administrator in and out. This is guest execution under QEMU, not physical
hardware.
"""
from __future__ import annotations

import argparse
import hashlib
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
from test_tty_sessions import configured_profile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from console_login_disk import SERVICES, admit  # noqa: E402
from kernel_sdk import ARCH_TRIPLES  # noqa: E402
from musl_source import inspect_elf  # noqa: E402

NAME = b"chosen_admin"
PASSWORD = b"Getty-S5-correct-horse"
WRONG = b"Getty-S5-wrong-battery"
USER, USER_PASSWORD = b"alice", b"Getty-S5-ordinary-staple"
PROMPT = b"oksh> "
FAILURES = (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed", b"event=fatal-hold",
            b"login: unable to establish", b"GETTY event=error", b"oksh: console input is not available")
# The serial line shows every newline as CRLF; the pts adds its own CR (ONLCR).
OPEN = re.compile(rb"GETTY event=open pts=([0-9]+) pid=([0-9]+)\r*\n")
CLOSE = re.compile(rb"GETTY event=close pts=([0-9]+) pid=([0-9]+) status=(-?[0-9]+) reason=([a-z]+)\r*\n")
REAP = re.compile(rb"event=reap service=console pid=([0-9]+) generation=([0-9]+) [^\r\n]* status=([0-9]+)\r*\n")
LAUNCH = re.compile(rb"event=launch service=console pid=([0-9]+) generation=([0-9]+) ")
REPORT = re.compile(rb"OKSH_JOBS (session|hold)((?: [a-z_]+=-?[0-9]+)+)\n")
# stat prints st_mode in hex: S_IFCHR | 0620. Slave inodes are 34816 + N.
PTS_MODE = b"mode=2190 "
PTS_INODE = 34816
# Seconds of one enrollment (PBKDF2 derive plus the store commits) and of one
# login (PBKDF2 verify): the largest measured per profile under TCG on the
# development host with the debug image, with up to three lanes running at
# once (docs/qualification/GETTY_LOGIN.md). Timeouts are four times these, at
# least 300 s for an enrollment and 120 s for a login.
KDF_SECONDS = {
    "i386": (93, 14), "x86_64": (135, 31), "aarch64": (103, 13), "arm32": (110, 13), "rv64": (74, 15),
    "rv32": (81, 14), "loongarch64": (63, 16), "mips": (77, 12), "mips64": (70, 14), "ppc": (84, 14),
}
# The ^C and ^Z target runs this long unless the lane ends it first.
HOLD = 600


# Debug kernels write "[CRLF]OK_<NAME> ...CRLF" diagnostics, and PID1 its
# NATIVE_PID1 events, into the serial stream at any point, even inside a line
# the pts is echoing. A CRLF that ends pts output is CR CR LF (ONLCR plus the
# serial CR), so it is never taken.
DIAGNOSTIC = re.compile(rb"(?:(?<!\r)\r\n)?(?:OK_[A-Z][A-Z0-9_]*|NATIVE_PID1) [^\r\n]*\r\n")


def clean(data: bytes) -> bytes:
    return DIAGNOSTIC.sub(b"", data).replace(b"\r", b"")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    def read(self, deadline: float, what: str) -> None:
        """Reads what the guest has written within 0.1 s; fails after the deadline."""
        if time.monotonic() > deadline:
            self.save()
            raise Failure(f"{self.log.name}: no {what} after {len(self.data)} bytes")
        ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
        if not ready:
            if self.process.poll() is not None:
                self.save()
                raise Failure(f"{self.log.name}: QEMU exited")
            return
        chunk = os.read(self.process.stdout.fileno(), 16384)
        if not chunk:
            self.save()
            raise Failure(f"{self.log.name}: serial output ended")
        self.data.extend(chunk)
        self.save()
        for marker in FAILURES:
            if marker in self.data:
                raise Failure(f"{self.log.name}: guest failure {marker.decode()}")

    def receive(self, pattern: bytes | re.Pattern, start: int, timeout: float | None = None) -> re.Match | int:
        """Waits for a raw pattern after start: the offset after a bytes pattern, or the match."""
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
            self.read(deadline, repr(pattern))

    def cleaned(self, pattern: bytes | re.Pattern, start: int, timeout: float | None = None):
        """Waits for a pattern in the diagnostics-free text after start; returns the match or True."""
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            text = clean(bytes(self.data[start:]))
            found = pattern.search(text) if isinstance(pattern, re.Pattern) else pattern in text
            if found:
                return found
            self.read(deadline, repr(pattern))

    def quiet(self, pattern: bytes, start: int, seconds: float) -> None:
        """Requires that the pattern does not appear after start within the given time."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if pattern in self.data[start:]:
                raise Failure(f"{self.log.name}: unexpected {pattern!r}")
            self.read(deadline + self.timeout, repr(pattern))
        if pattern in self.data[start:]:
            raise Failure(f"{self.log.name}: unexpected {pattern!r}")

    def send(self, line: bytes, newline: bool = True) -> int:
        offset = len(self.data)
        self.process.stdin.write(line + (b"\n" if newline else b""))
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


def fields(match: re.Match) -> dict[str, int]:
    return {name.decode(): int(value) for name, value in re.findall(rb"([a-z_]+)=(-?[0-9]+)", match[2])}


class Session:
    def __init__(self, guest: Guest, steps: list, enroll_timeout: float, login_timeout: float):
        self.guest, self.steps = guest, steps
        self.enroll_timeout, self.login_timeout = enroll_timeout, login_timeout
        self.reasons: list[str] = []

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

    def output(self, sent: int, end: int) -> bytes:
        return clean(bytes(self.guest.data[sent:end]))

    def command(self, line: bytes, start: int) -> tuple[bytes, int]:
        """Types one line at the next prompt; returns its output and the offset of the following prompt."""
        self.guest.receive(PROMPT, start)
        sent = self.guest.send(line)
        end = self.guest.receive(PROMPT, sent)
        output = self.output(sent, end - len(PROMPT))
        # The pts echoes the typed line before the command's output.
        if not output.startswith(line + b"\n"):
            raise Failure(f"command {line!r} was not echoed on the pts: {output!r}")
        return output[len(line) + 1:], end - len(PROMPT)

    def shell(self, pts: int, start: int, user: bytes, home: bytes = b"/root") -> int:
        output, start = self.command(b"whoami | cat", start)
        if output != user + b"\n":
            raise Failure(f"whoami pipeline printed {output!r}")
        output, start = self.command(b"pwd", start)
        if output != home + b"\n":
            raise Failure(f"pwd printed {output!r}")
        # Only this session's pair exists: earlier sessions released theirs.
        listing, start = self.command(b"ls /dev/pts", start)
        if listing.split() != [str(pts).encode()]:
            raise Failure(f"/dev/pts lists other pairs besides the session's pts {pts}: {listing!r}")
        stat, start = self.command(b"stat /dev/pts/" + str(pts).encode(), start)
        if PTS_MODE not in stat or b"ino=" + str(PTS_INODE + pts).encode() not in stat:
            raise Failure(f"the session's pts is not a 0620 character device: {stat!r}")
        self.step("shell", pts=pts, whoami=user.decode(), pts_listing=listing.decode(errors="replace"),
                  pts_stat=stat.decode(errors="replace"))
        return start

    def session(self, pts: int, leader: int, start: int) -> int:
        """The shell leads the session on its pts; each job gets its own group."""
        output, start = self.command(b"oksh-jobs session", start)
        report = REPORT.search(output)
        if not report or report[1] != b"session":
            raise Failure(f"no session report: {output!r}")
        job = fields(report)
        expected = dict(pid=job["pid"], ppid=leader, pgrp=job["pid"], sid=leader, tty_pgrp=job["pid"],
                        tty_sid=leader, tty_ino=PTS_INODE + pts)
        if job != expected or job["pid"] == leader:
            raise Failure(f"foreground job identity {job} differs from {expected}")
        self.step("session-foreground", leader=leader, **{"job_" + key: value for key, value in job.items()})
        # A background job: its own group, while the shell's group keeps the terminal.
        self.guest.receive(PROMPT, start)
        sent = self.guest.send(b"oksh-jobs session &")
        launched = self.guest.cleaned(re.compile(rb"\n\[1\] ([0-9]+)\n"), sent)
        job = fields(self.guest.cleaned(REPORT, sent))
        expected = dict(pid=int(launched[1]), ppid=leader, pgrp=int(launched[1]), sid=leader, tty_pgrp=leader,
                        tty_sid=leader, tty_ino=PTS_INODE + pts)
        if job != expected:
            raise Failure(f"background job identity {job} differs from {expected}")
        start = self.until_report(b"[1]+ Done oksh-jobs session\n", sent)
        self.step("session-background", leader=leader, **{"job_" + key: value for key, value in job.items()})
        return start

    def until_report(self, expected: bytes, sent: int) -> int:
        """Presses Enter at each prompt until a job report precedes one; returns that prompt's offset."""
        deadline = time.monotonic() + self.guest.timeout
        at = sent
        while time.monotonic() < deadline:
            at = self.guest.receive(PROMPT, at)
            if expected in self.output(sent, at):
                return at - len(PROMPT)
            time.sleep(0.2)
            self.guest.send(b"")
        raise Failure(f"no {expected!r} before a prompt")

    def hold(self, start: int, suffix: bytes = b"") -> tuple[int, int]:
        """Starts the ^C/^Z target; returns its pid once it reports that it owns the terminal."""
        self.guest.receive(PROMPT, start)
        sent = self.guest.send(b"oksh-jobs hold %d" % HOLD + suffix)
        report = self.guest.cleaned(REPORT, sent)
        job = fields(report)
        if report[1] != b"hold" or not job["pid"] == job["pgrp"] == job["tty_pgrp"]:
            raise Failure(f"the foreground job does not own the terminal: {job}")
        return job["pid"], sent

    def interrupted(self, sent: int, marker: bytes, what: str) -> int:
        """After ^C: the job died, the rest of its list ran and the prompt is back."""
        end = self.guest.receive(PROMPT, sent)
        output = self.output(sent, end)
        if b"^C" not in output or marker + b"\n" not in output or b"OKSH_JOBS held" in output:
            raise Failure(f"^C did not end the {what}: {output!r}")
        output, start = self.command(b"jobs", end - len(PROMPT))
        if output.strip():
            raise Failure(f"the {what} is still listed: {output!r}")
        return start

    def interrupt(self, start: int) -> int:
        # oksh has no $?: the || branch runs only for a nonzero status.
        pid, sent = self.hold(start, b" || echo hold-interrupted")
        self.guest.send(b"\x03", newline=False)
        start = self.interrupted(sent, b"hold-interrupted", "foreground job")
        self.step("interrupt", job=pid)
        return start

    def suspend(self, start: int) -> tuple[int, int]:
        """^Z stops the foreground job; returns its pid and the next prompt."""
        pid, sent = self.hold(start)
        self.guest.send(b"\x1a", newline=False)
        stopped = b"[1]+ Stopped oksh-jobs hold %d\n" % HOLD
        end = self.guest.receive(PROMPT, sent)
        output = self.output(sent, end)
        if b"^Z" not in output or stopped not in output:
            raise Failure(f"^Z did not stop the foreground job: {output!r}")
        output, end = self.command(b"jobs", end - len(PROMPT))
        if output != stopped:
            raise Failure(f"jobs does not list the stopped job: {output!r}")
        return pid, end

    def stopped_exit(self, start: int) -> int:
        output, start = self.command(b"exit", start)
        if output != b"oksh: there are stopped jobs\n":
            raise Failure(f"exit with a stopped job did not warn: {output!r}")
        return start

    def job_control(self, start: int) -> int:
        pid, start = self.suspend(start)
        start = self.stopped_exit(start)
        self.guest.receive(PROMPT, start)
        sent = self.guest.send(b"fg || echo fg-interrupted")
        self.guest.cleaned(b"fg || echo fg-interrupted\noksh-jobs hold %d\n" % HOLD, sent)
        # Resumed in the foreground: the shell waits, and ^C reaches the job.
        self.guest.quiet(PROMPT, sent, 2)
        self.guest.send(b"\x03", newline=False)
        start = self.interrupted(sent, b"fg-interrupted", "resumed job")
        self.step("stop-jobs-fg", job=pid)
        return start

    def logout(self, pts: int, pid: int, start: int, stopped_job: bool = False) -> tuple[int, int, int]:
        if stopped_job:
            job, start = self.suspend(start)
            start = self.stopped_exit(start)
        self.guest.receive(PROMPT, start)
        sent = self.guest.send(b"exit")
        close = self.guest.receive(CLOSE, sent)
        if (int(close[1]), int(close[2])) != (pts, pid) or close[4] not in (b"exit", b"hangup"):
            raise Failure(f"unexpected close event {close[0]!r} for pts {pts} pid {pid}")
        status = int(close[3])
        self.reasons.append(close[4].decode())
        self.step("logout", pts=pts, pid=pid, status=status, reason=close[4].decode(), stopped_job=stopped_job)
        # `exit` without an argument returns the previous status; after the
        # stopped-jobs warning that is the warning's 1.
        if status != (256 if stopped_job else 0):
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
            before = time.monotonic()
            at = self.guest.receive(b"Login incorrect.", at, self.login_timeout)
            at = self.guest.receive(b"Login: ", at)
            self.step("wrong-password-refused", seconds_to_prompt=round(time.monotonic() - before, 3))
        self.guest.send(name)
        at = self.guest.receive(b"Password: ", at)
        sent = self.guest.send(password)
        before = time.monotonic()
        end = self.guest.receive(PROMPT, sent, self.login_timeout)
        self.step("login", user=name.decode(), seconds_to_shell=round(time.monotonic() - before, 3))
        return end - len(PROMPT)

    def enroll(self, start: int) -> int:
        at = self.answer(b"Account name: ", NAME, start)
        at = self.answer(b"Password: ", PASSWORD, at)
        at = self.guest.receive(b"Repeat password: ", at)
        sent = self.guest.send(PASSWORD)
        before = time.monotonic()
        at = self.guest.receive(PROMPT, sent, self.enroll_timeout) - len(PROMPT)
        self.step("enrolled", seconds_to_shell=round(time.monotonic() - before, 3))
        return at

    def add_user(self, start: int) -> int:
        """:useradd as the administrator; the shell that follows is the administrator's."""
        at = self.answer(b"Login: ", b":useradd", start)
        at = self.answer(b"Login: ", NAME, at)
        at = self.answer(b"Password: ", PASSWORD, at)
        at = self.guest.receive(b"New account name: ", at, self.login_timeout)
        self.guest.send(USER)
        at = self.answer(b"New password: ", USER_PASSWORD, at)
        at = self.guest.receive(b"Repeat new password: ", at)
        sent = self.guest.send(USER_PASSWORD)
        before = time.monotonic()
        at = self.guest.receive(b"Account created.", sent, self.enroll_timeout)
        end = self.guest.receive(PROMPT, at)
        self.step("user-added", user=USER.decode(), seconds_to_shell=round(time.monotonic() - before, 3))
        return end - len(PROMPT)


def check_serial(data: bytes) -> None:
    data = clean(data)
    # Passwords are read with ECHO cleared; account names are echoed by the pts.
    for secret in (PASSWORD, WRONG, USER_PASSWORD):
        if secret in data:
            raise Failure("a password was echoed to the console")
    if b"Login: " + NAME + b"\n" not in data:
        raise Failure("account names were not echoed by the pts line discipline")
    if b"Login: " + NAME + b"\n\n" in data:
        raise Failure("login wrote an extra newline after echoed input")


def boot(args, image: Path, label: str, steps: list, first: bool) -> tuple[bytes, list[str]]:
    command = [str(part) for part in command_for(args.qemu.resolve(), args.arch, args.kernel, image,
                                                  "none", native_profile=True)]
    guest = Guest(command, args.out / f"{label}.serial.log", args.timeout)
    enroll, login = KDF_SECONDS[args.arch]
    session = Session(guest, steps, max(300, 4 * enroll), max(120, 4 * login))
    session.step("boot", label=label, argv=command)
    try:
        pts, pid, at = session.opened(0)
        session.step("getty-open", pts=pts, pid=pid)
        at = session.enroll(at) if first else session.login(at, wrong_first=False)
        at = session.shell(pts, at, b"root")
        at = session.session(pts, pid, at)
        if first:
            at = session.interrupt(at)
            at = session.job_control(at)
            pts, pid, at = session.logout(pts, pid, at, stopped_job=True)
            at = session.login(at, wrong_first=True)
            at = session.shell(pts, at, b"root")
            at = session.session(pts, pid, at)
            pts, pid, at = session.logout(pts, pid, at)
            if args.ordinary:
                # login hands the pts to the user (fchown, 0620) before the
                # credentials drop and checks it again afterwards.
                at = session.add_user(at)
                pts, pid, at = session.logout(pts, pid, at)
                at = session.login(at, wrong_first=False, name=USER, password=USER_PASSWORD)
                at = session.shell(pts, at, b"uid1000", b"/home/" + USER)
                at = session.session(pts, pid, at)
                pts, pid, at = session.logout(pts, pid, at)
        else:
            pts, pid, at = session.logout(pts, pid, at)
        guest.receive(b"Login: ", at)
        session.step("login-prompt-again")
    finally:
        guest.stop()
    return bytes(guest.data), session.reasons


def build_inputs(args) -> tuple[Path, Path, Path, Path]:
    """Builds (unless --no-build) and returns the kernel, product image, login root and helper."""
    build = ROOT / "build" / args.arch / args.mode
    product = build / "rootfs.login.ext4-journalled.img"
    if not args.no_build:
        arch, mode, _ = configured_profile(args.xmake)
        if (arch, mode) != (args.arch, args.mode):
            raise ValueError(f"the project is configured for {arch}/{mode}, not {args.arch}/{args.mode}")
        for target in ("app-oksh-job-probe", "distro_image"):
            subprocess.run([args.xmake, "-P", str(ROOT), "-y", "-b", target], check=True, cwd=ROOT)
        # Image creation refuses an existing image, which may hold an account
        # enrolled through `xmake qemu-distro`; an existing one is admitted as it is.
        if not product.exists():
            subprocess.run([args.xmake, "-P", str(ROOT), "-y", "-b", "rootfs-ext4-journalled"], check=True, cwd=ROOT)
    kernel = build / "distro/kernel.bin"
    root = build / "rootfs"
    helper = build / "apps/oksh-jobs.elf"
    for path in (kernel, product, helper, root / "bin/getty", root / "bin/login", args.qemu):
        if not path.is_file():
            raise FileNotFoundError(path)
    if (root / "etc/services.conf").read_bytes() != SERVICES:
        raise ValueError(f"{root / 'etc/services.conf'} does not select getty and login")
    inspect_elf(helper, args.arch)
    if helper.read_bytes()[7] != 0:
        raise ValueError("the helper lacks the native ELF personality")
    return kernel, product, root, helper


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    parser.add_argument("--mode", default="debug", choices=("debug", "release"))
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--linux-image", required=True, type=Path, help="pinned Linux journal-activation image")
    parser.add_argument("--linux-image-sha256", required=True)
    parser.add_argument("--xmake", default="xmake")
    parser.add_argument("--no-build", action="store_true", help="use the existing build outputs")
    parser.add_argument("--timeout", type=float, default=300, help="seconds for the boot and each non-KDF step")
    parser.add_argument("--no-second-boot", action="store_true")
    parser.add_argument("--ordinary", action="store_true", help="also create and log in an ordinary account")
    args = parser.parse_args()
    kernel, product, root, helper = build_inputs(args)
    debugfs = Path(shutil.which("debugfs") or "/missing-debugfs")
    selected = admit(product.absolute(), root.resolve(), debugfs)

    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    lane_root = args.out / "root"
    shutil.copytree(root, lane_root, symlinks=True)
    shutil.copy2(helper, lane_root / "bin/oksh-jobs")
    (lane_root / "bin/oksh-jobs").chmod(0o755)
    image = args.out / "lane.img"
    with (args.out / "package.log").open("xb") as log:
        subprocess.run([sys.executable, "-B", str(TOOLS / "mkext4_journalled.py"), "--root", str(lane_root),
                        "--out", str(image), "--console-login", "--linux-image", str(args.linux_image.resolve()),
                        "--linux-image-sha256", args.linux_image_sha256],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    if admit(image, lane_root, debugfs) != selected:
        raise ValueError("the lane disk's admitted product differs from the product image")
    args.kernel = args.out / "kernel-input.bin"
    shutil.copy2(kernel, args.kernel)
    steps: list = []
    result = dict(schema=1, scope="getty-login-lane-qemu-guest", arch=args.arch, mode=args.mode, physical=False,
                  status="failed", product_image=str(product), product_image_sha256=sha(product),
                  product=selected, helper_sha256=sha(helper),
                  helper_source_sha256=sha(ROOT / "tests/native/oksh_job_probe.c"),
                  lane_disk_sha256=sha(image), kernel_sha256=sha(args.kernel),
                  qemu_sha256=sha(args.qemu.resolve()), script_sha256=sha(Path(__file__)),
                  kdf_seconds=KDF_SECONDS[args.arch], ordinary=args.ordinary, steps=steps)
    try:
        serial, reasons = boot(args, image, "boot1", steps, first=True)
        check_serial(serial)
        if not args.no_second_boot:
            second, more = boot(args, image, "boot2", steps, first=False)
            check_serial(second)
            reasons += more
        result.update(status="passed", close_reasons=reasons)
    except BaseException as error:
        result["failure"] = repr(error)
        raise
    finally:
        for log in sorted(args.out.glob("boot*.serial.log")):
            result[log.name.replace(".", "_") + "_sha256"] = sha(log)
        (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"[getty-login] {args.arch} passed: {args.out}")


if __name__ == "__main__":
    try:
        main()
    except Failure as error:
        raise SystemExit(f"[getty-login] FAIL: {error}")
