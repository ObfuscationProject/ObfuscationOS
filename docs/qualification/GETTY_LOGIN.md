# getty and login on a PTY (WT2.2 feat/getty-login)

Slice log of the ObfuscationOS side of WT2.2 (`docs/PLAN.md`), built against
the ABI 81 / UAPI 0.17 kernel SDK of kernel `feat/tty-jobctl`. Each section
says what a slice changed and which evidence class backs it: hosted model
tests substitute system calls and establish no guest behaviour; guest runs
execute the real programs under QEMU. Receipts are packaged into
ObfuscationEvidence at the end of the worktree, never into this tree.

## S4: getty and login on a pts

What changed:

- `apps/getty` (`app-getty`, `/bin/getty`) is the login profile's PID1
  `console` service. It keeps the console lease, runs `/bin/login` as the
  leader of a new session on a fresh `/dev/pts/N` and relays bytes between the
  console and the master until the session ends; then it closes the master,
  which hangs up what is left, reaps login and exits 0 so that PID1 restarts
  it under a new lease epoch. The behaviour and the `GETTY event=...` lines
  are described in `docs/native-init.md` (getty, login and the pts).
- `apps/login` accepts only a pts session: descriptors 0-2 are one read-write
  pts description that login leads and whose foreground group is login's,
  owned by root with no access beyond 0620; the parent is no longer required
  to be PID1. Passwords are read with ECHO cleared and the attributes restored
  on every path; names are echoed by the line discipline without an extra
  newline from login. `tcflush(TCIFLUSH)` replaces `ok_console_flush`.
  Ordinary accounts get the pts (`fchown`, 0620) before the credentials drop.
  login ignores SIGINT and SIGQUIT besides the job-control stops and executes
  oksh with SIGHUP at its default. Enrollment, rotation, user creation and
  their persistence are unchanged.
- The login manifest is `service console simple /bin/getty - 0 0` in
  `config/services-login.conf`, the PID1 fallback, the disk admission pins
  (`tools/console_login_disk.py`: services, `/bin/getty` in the product and the
  metadata checks, profile
  `ordinary-native-console-getty-login-logging-time-mount-resolver-v1`) and the
  staging (`tools/stage_rootfs.py` stages getty and login; `getty` joins the
  okcrt-reserved names). Disks of the previous direct-login profile are refused
  before inspection.

Hosted model tests (no guest execution):

```sh
python3 -B -m unittest discover -s tests/tools -p test_native_getty.py        # 11 tests
python3 -B -m unittest discover -s tests/tools -p test_native_login_main.py   # 46 tests
python3 -B -m unittest discover -s tests/tools -p test_native_login_input.py  # 12 tests
```

`test_native_getty.py` builds `apps/getty/main.c` with host headers against a
scripted console, master and child: master setup before the fork, relay in
both directions, drain at exit, partial console and master writes, master
backpressure, slave hangup (POLLHUP and EIO), the SIGKILL grace, lease
revocation, the child's session setup and its failures, setup failures, and
one console write per event line. Twelve source mutations (dropping
close-on-exec, the drain, the master close, backpressure, the kill, the ctty
check, `setsid` or revocation handling; `O_NOCTTY` on the slave; leaking the
environment; single writes; events without their own line) each fail it.
`test_native_login_main.py` keeps the 44 earlier control-flow tests, with the
pts identity in place of the console one, and adds the signal dispositions
and the secret/echoed read for every prompt. The packaging tests
(`test_native_console_profile.py`, `test_stage_rootfs.py`,
`test_console_logging_disk.py`, `test_logging.py`) pin the getty manifest and
product.

Guest execution, x86_64 debug (kernel SDK 5815814, ABI 81), SysToolchain QEMU
10.2 under TCG, journalled login image built with `--native_console_login=y`
and the pinned Linux activation image:

```sh
xmake -y -b distro_image && xmake -y -b rootfs-ext4-journalled
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_getty_login.py --arch x86_64 \
  --qemu QEMU --kernel build/x86_64/debug/distro/kernel.bin \
  --image build/x86_64/debug/rootfs.login.ext4-journalled.img \
  --root build/x86_64/debug/rootfs --out OUT --timeout 300 --second-boot --ordinary
```

The driver admits the disk as `xmake qemu-distro` does, boots a copy and
checks, on the first boot: `GETTY event=open pts=0`, first-boot enrollment,
the shell on the pts (`whoami | cat` prints `root`, `pwd` prints `/root`,
`ls /dev/pts` lists the session's pts, which `stat` reports as `S_IFCHR|0620`
with inode 34816+N), `exit` followed by `GETTY event=close`, the PID1 reap of
getty with status 0 and its relaunch under the next generation, a new
`GETTY event=open` and `Login:` prompt, one refused wrong password, login and
logout again, `:useradd` of `alice` and a login as `alice` (shell `uid1000`
in `/home/alice`, which needs login's `fchown`/`fchmod` handover to pass its
post-drop checks). The second boot of the same disk logs the administrator in
and out. Every typed password is absent from the serial log and both echoed
names are present without an extra blank line. The driver filters the debug
kernel's `OK_*` diagnostics and PID1's `NATIVE_PID1` lines, which the serial
stream interleaves with session output.

Result: passed. Every logout reported `reason=hangup` (the slave's last close
was seen before login was reaped). Serial logs: boot1 sha256
`d8c7ad43add249d435f37ada1e4593cf0a65edb33b22d1edf61b0994b7a06901`, boot2
`b9872b42a412ecbd7f4d77b9a4edd79af95202fa656cad151df5099543e38c04` (kept
with the worktree's scratch logs until the receipts are packaged).

Timings under TCG on the development host (five runs of the debug image; a
loaded host makes them vary):

| Step | Seconds |
|---|---|
| boot to `GETTY event=open` | 8-12 |
| enrollment: repeated password sent to `oksh> ` (one PBKDF2 derive plus the store commits) | 93-135 |
| login: password sent to `oksh> ` (one PBKDF2 verify) | 12-31 |
| wrong password to the next `Login:` (verify plus the 1 s delay) | 19-24 |
| `:useradd`: repeated password to `oksh> ` (derive plus registry and home commits) | 37 |
| `exit` to the next `GETTY event=open` (PID1 back-off included) | 0.1-0.2 |

Open after S4:

- Only x86_64 ran in the guest; i386 and ppc compile getty and login. The
  ten-profile lane, its timeouts and `^C`/`^Z` job control on the pts are S5.
- `tests/native/native_password_rotation_input.c` still wraps
  `ok_login_read_line` for the `Password: ` prompt, which now goes through
  `ok_login_read_secret`; with its `getppid() == 1` check it belongs to the
  stale console-era probes that S2 rewrites. `tools/qualify_native_login.py`
  and `tools/read_native_login.py` stay pinned to ABI 69 and the direct-login
  manifest.
- Processes that outlive a session in a group other than its foreground group
  keep their pts pair, and the kernel has 8 pairs. Once S3's `&` lands, a user
  who leaves enough running background jobs behind at logout locks the console
  out: getty fails with `stage=open errno=11` and PID1 restarts it until a
  pair is free (`docs/native-init.md`). getty, like Linux getty, does not kill
  processes outside its session. S5 should cover this in the lane or its docs;
  more pairs are a kernel change.
