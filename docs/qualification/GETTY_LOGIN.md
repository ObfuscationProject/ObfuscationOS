# getty and login on a PTY (WT2.2 feat/getty-login)

Slice log of the ObfuscationOS side of WT2.2 (`docs/PLAN.md`), built against
the ABI 81 / UAPI 0.17 kernel SDK of kernel `feat/tty-jobctl`. Each section
says what a slice changed and which evidence class backs it: hosted model
tests substitute system calls and establish no guest behaviour; guest runs
execute the real programs under QEMU. Receipts are packaged into
ObfuscationEvidence at the end of the worktree, never into this tree.

## S2: guest TTY, session and job-control probe

`tests/native/native_tty_sessions.c` (target `app-tty-sessions-probe`, not
built by default) is a native okcrt probe that needs nothing from the
console but a place to print. Each case opens its own `/dev/ptmx` pair and
forks a session leader that runs the checks; native processes have no
handlers and no SIGCHLD, so every signal outcome is read from `waitpid`
status words. Every case that expects a terminal-generated signal for a
group gives that group a second member that never touches the terminal and
checks it too, so delivery to the caller or the group leader alone fails.
Every wait and read is bounded, so a broken kernel fails a
case instead of hanging the shell. The cases, in order:

| # | Name | Checks |
|---|---|---|
| 1 | `acquire` | open without `O_NOCTTY` by a session leader acquires the slave; `tcgetsid`/`tcgetpgrp`; the master reports the slave's session and group; `/dev/tty` is the same terminal (a write reaches the master with ONLCR) |
| 2 | `noctty` | `O_NOCTTY` does not acquire (`tcgetsid`/`tcgetpgrp` ENOTTY, `/dev/tty` ENXIO); `TIOCSCTTY(0)` then acquires |
| 3 | `sctty_eperm` | `TIOCSCTTY` on the own ctty is 0 for arg 0 and 1; on a master ENOTTY; a leader that already has a ctty, a member with or without one, a write-only descriptor and another session's terminal (also with arg 1: no steal) give EPERM; a new leader then acquires a free terminal |
| 4 | `notty_member` | `TIOCNOTTY` by a foreground member detaches only it (ENOTTY, `/dev/tty` ENXIO afterwards); on a master ENOTTY; the leader keeps the terminal |
| 5 | `notty_leader` | `TIOCNOTTY` by the leader kills both members of the foreground group with SIGHUP and clears the association; the leader may acquire again |
| 6 | `pgrp` | `tcsetpgrp` EINVAL (negative), ESRCH (no group), EPERM (group of another session); setting through the master; handing the foreground to a member and reclaiming it from the background with SIGTTOU ignored |
| 7 | `ttin_stop` | a background read stops the reader and its group's other member with SIGTTIN (WUNTRACED); after the foreground is handed over and `kill(-pgid, SIGCONT)` is seen for both (WCONTINUED) the same read completes |
| 8 | `ttin_eio` | with SIGTTIN ignored a background read is EIO, and background poll reports nothing |
| 9 | `ttou_stop` | background `tcsetattr` and `tcsetpgrp` stop with SIGTTOU; with SIGTTOU ignored `tcsetattr`, `tcflush` and `tcsetpgrp` go through |
| 10 | `tostop` | with TOSTOP a background write stops the writer and its group's other member with SIGTTOU and nothing reaches the master; ignored SIGTTOU, or TOSTOP clear, lets it through |
| 11 | `isig_int` | `0x03` written to the master kills the foreground reader and its group's other member with SIGINT (`WTERMSIG`) and echoes `^C` |
| 12 | `isig_tstp` | `0x1a` stops the foreground reader and its group's other member with SIGTSTP (WUNTRACED); `kill(-pgid, SIGCONT)` is seen for both with WCONTINUED and the reader's read then completes |
| 13 | `canonical` | pts defaults (ISIG, ICANON, ECHO, ECHOE, OPOST, ONLCR, ICRNL, ^C ^Z ^D); erase echo `\b \b`; one line per read; no partial line readable; CR becomes NL; ONLCR on output; VEOF at line start reads 0 |
| 14 | `echo_off` | with ECHO clear nothing is echoed; restored ECHO echoes again |
| 15 | `master_close` | the master's last close kills the session leader with SIGHUP (seen by the probe); a member that ignores SIGHUP sees POLLHUP, read 0, write and TCGETS EIO, `/dev/tty` ENXIO |
| 16 | `leader_exit` | the leader's exit kills both members of the foreground group with SIGHUP (seen by a background witness) and clears the association |
| 17 | `orphan_stop` | when the leader exits, a group with stopped members is orphaned: a SIG_DFL member dies of SIGHUP, a member ignoring SIGHUP is continued (WCONTINUED) |
| 18 | `orphan_read` | in a background group orphaned by its parent's exit, read and `tcsetattr` give EIO and TIOCSPGRP ENOTTY instead of a stop |
| 19 | `winsize` | the initial window is 0×0; TIOCSWINSZ on either end reads back on the other; a foreground member at the default SIGWINCH disposition is neither stopped nor killed (SIGWINCH delivery itself is not observable natively; the kernel's hosted tests check it) |
| 20 | `pts_capacity` | run last: besides the case's own pair exactly `OK_PTS_CAPACITY` - 1 more pairs open before `posix_openpt` fails with EAGAIN (the kernel's ENOSPC), and a pair opens again once they are closed |

The probe prints `TTY_SESSIONS_CASE n=<n> name=<name> result=pass` per case
and finally `TTY_SESSIONS_PROBE stage=PASS cases=20 arch=<arch>`, or at the
first failure `TTY_SESSIONS_PROBE stage=FAIL case=<n> name=<name>
line=<source line> value=<v> errno=<e> arch=<arch>`, where `line` is the
line of the failed check in the source (0: the leader's wait status was
wrong, given as `value`; -1: a case process was lost or a witness did not
report). An optional argument runs one case by number.

`scripts/test_tty_sessions.py` checks that the tree is configured for the
requested profile and refuses a configuration with startup acceptance
(`native_init_acceptance`, `native_vm_acceptance`, `native_udp_probe`),
whose init runs posix-check and the shell pipeline before the shell, and
`native_console_login`, whose console service is `/bin/login` instead of
the maintenance oksh; the staged `etc/services.conf` must name `/bin/oksh`
as the console service. A guest that prints the acceptance marker fails at
once instead of waiting for the prompt. It then builds the probe,
`rootfs-stage` and `distro_image`, copies `build/<arch>/<mode>/rootfs`, adds the probe as `/bin/tty-sessions`,
packs it with `tools/mkext4.py`, boots it with `qemu_distro.command_for`
(`native_profile=True`, which selects the native e500v2 profile on ppc) and
types the probe at the maintenance `oksh> ` prompt, twice per boot. Within
a run, a case passes only once every process of the case has exited (its
report pipe reaches end of file), and the last case counts the free PTY
slots, so a slot that any earlier case failed to release fails that run;
process-table slots are not counted. Each run must list all 20
cases and print the exact PASS marker; `serial.log` and `result.json` are
kept in the output directory. `xmake tty-sessions-test` resolves QEMU like
`qemu-distro`, refuses `native_console_login` before building,
reconfigures the tree without startup acceptance when it is on, and runs it for the configured profile:

```sh
xmake f -y -m debug -a ARCH --kernel_sdk=SDK [--systoolchain_dir=TC]
xmake tty-sessions-test [--out=DIR] [--runs=2] [--timeout=300]
# or directly
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_tty_sessions.py --arch ARCH --mode debug \
  --qemu TC/bin/qemu-system-... --out OUT
```

CI runs `xmake tty-sessions-test` on x86_64, arm32 and ppc after the QEMU
acceptance boot.

Result (QEMU 10.2.0 from SysToolchain 0.1.0, kernel main 5815814 SDKs, ABI
81, debug): both runs pass all 20 cases on all ten profiles. A run takes
1 s (x86_64) to 3 s (aarch64) from typing the command to the next prompt. This is single-CPU QEMU
execution; it makes no physical-hardware or SMP claim, and the probe runs
as root in the maintenance session, so it does not exercise login, getty or
the console's lease-gated job control.

Stale probes rewritten to the ABI 81 semantics (kernel
`docs/qualification/TTY_JOB_CONTROL.md` obligation 3). None has an in-tree
runner; each is built for x86_64 and ppc (the musl probe for x86_64 against
a musl build):

- `tests/native/native_console_control.c`: TIOCSCTTY(0 and 1) EPERM for the
  non-leader session process; background reads EIO only with SIGTTIN
  ignored and without consuming input; background poll without POLLERR
  (nothing, or POLLIN once input is buffered); the peer's nonce read stops
  with SIGTTIN and completes after the foreground hand-over and SIGCONT;
  reclaims from the background with SIGTTOU ignored, and a SIGTTOU stop at
  SIG_DFL; blocked waiters keep waiting across a foreground change (poll
  times out, reads give EIO only after a stop and continue); TIOCNOTTY by
  the peer detaches only it.
- `tests/musl/native_console_control.c`: TIOCSCTTY(1) EPERM; the reader's
  select times out instead of seeing POLLERR; reads EIO with SIGTTIN
  ignored; a SIGTTIN stop seen through WUNTRACED; reclaim with SIGTTOU
  ignored.
- `tests/native/native_group_signals.c`: `kill(-pgid, SIGHUP)` terminates
  the group instead of failing with EOPNOTSUPP; the group is also stopped
  and continued.
- `tests/native/native_password_rotation_session.c`: the session leader
  ignores SIGHUP before forking the old readers, which its exit would
  otherwise hang up.

`tools/console_receipt_admission.py` reads a sealed historical ABI 73
receipt and keeps its claim text. The hosted models (`test_oksh.py`
console tests, `test_native_login_main.py`, the wrapper tests) stay; the
guest probe runs beside them.

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
