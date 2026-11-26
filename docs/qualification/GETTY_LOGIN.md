# getty and login on a PTY (WT2.2 feat/getty-login)

Slice log of the ObfuscationOS side of WT2.2 (`docs/PLAN.md`), built against
the ABI 81 / UAPI 0.17 kernel SDK of kernel `feat/tty-jobctl`. The branch was
later rebased onto OS main at module ABI 82 (UAPI still 0.17; the ABI 82
delta is network-only), and S5 ran against SDKs exported from kernel main
fd8abee. Each section says what a slice changed and which evidence class
backs it: hosted model tests substitute system calls and establish no guest
behaviour; guest runs execute the real programs under QEMU. Receipts are
packaged into ObfuscationEvidence at the end of the worktree, never into this
tree.

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
`native_console_login=y`, whose console service is `/bin/getty` (with
login on the pts) instead of the maintenance oksh; the staged
`etc/services.conf` must name `/bin/oksh` as the console service. When S2
landed the option was a boolean and the login console ran `/bin/login`
directly; since S5 it is tri-state and only `y` is refused: under the
default `auto`, which CI uses, and under `n` the full tree keeps the
maintenance oksh and is accepted. A guest that prints the acceptance marker fails at
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
`qemu-distro`, refuses `native_console_login=y` before building,
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

## S3: oksh job control

What changed: `oksh` has bounded job control (`apps/oksh/README.md`, "Job
control"). Every pipeline is a job; when one of descriptors 0-2 is the
shell's controlling terminal and its group is in the foreground, each job
gets its own process group and the terminal while it runs in the foreground.
The shell waits with `WUNTRACED`, reports `[n]+ Stopped`, `Done`, `Exit` and
`Killed`, runs a trailing `&` in the background, and has `jobs`, `fg [%n]` and
`bg [%n]` over an 8-entry table. At its prompt it ignores SIGINT, SIGQUIT,
SIGTSTP, SIGTTIN and SIGTTOU and resets them in children; SIGHUP stays at its
default. Native processes have no handlers and no SIGCHLD, so everything is
learned from `waitpid`. Without a controlling terminal (the maintenance
console, `oksh -c`, redirected input) job control degrades: no groups, `&`
jobs read `/dev/null`, and the table still works. The first `exit` with
stopped jobs warns; the second exits after SIGHUP and SIGCONT to each stopped
job. The SDK's `sys/wait.h` gained `WUNTRACED`, `WCONTINUED` and the
stop/continue status macros. BusyBox `ash` keeps `ASH_JOB_CONTROL` disabled;
enabling it is out of this worktree's scope (decision 0004).

Hosted model tests (no guest execution):

```sh
python3 -B -m unittest discover -s tests/tools -p test_oksh.py   # 50 tests, 17 of them job control
```

`JobControlTests` stop and continue real hosted children against the modelled
terminal of `tests/hosted/oksh_faults.c`: the stop report and terminal
reclaim, `fg`, `bg`, `&`, `jobs` and job specifications, completion reports,
a full table, `exit` with stopped jobs and the degraded mode.

Guest execution: `scripts/test_oksh_jobs.py` stages
`tests/native/oksh_job_probe.c` as `/bin/oksh-jobs` into a copy of the
maintenance root, packs it as plain ext4 and types at `oksh> `: a probe that
stops itself with SIGSTOP is reported Stopped through `WUNTRACED`, `jobs`
lists it, `exit` warns, `fg` continues it and the `||`/`&&` branches see a
nonzero and a zero status, `bg` continues one without the terminal, `&` jobs
are reported Done and read `/dev/null`, and `fg` waits for a running
background job. The maintenance console is not the shell's controlling
terminal and has ISIG off, so this is the degraded mode; ^C, ^Z and terminal
hand-over on a pts are the login lane's (S5).

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/test_oksh_jobs.py --arch ARCH --mode debug \
  --qemu TC/bin/qemu-system-... --out OUT
```

Kernel issue found by this runner, fixed in kernel `fix/jobctl-native-stop`
(72eb905, not merged at the time of writing): on mips and mips64 the probe's
SIGSTOP to itself was dropped while `kill` returned 0, so the shell never saw
a stop and the first step failed. The maintenance oksh's group is orphaned
(its parent, PID1, is in another session), and the kernel's orphaned-group
rule, which discards SIGTSTP, SIGTTIN and SIGTTOU but not SIGSTOP, compared
the native signal number with the Linux profile's SIGSTOP, which is 23 on
MIPS instead of 19. The fix compares in the recipient's numbering, with
hosted kernel tests for x86_64, mips and mips64. The login lane is not
affected: job groups that oksh creates on a pts are not orphaned (the shell,
their parent, is in the same session), and ^Z sends SIGTSTP from the line
discipline.

Result (QEMU 10.2.0 from SysToolchain 0.1.0, debug, ABI 82 SDKs): the runner
passes on i386, x86_64, aarch64, arm32, rv64, rv32, loongarch64 and ppc with
kernel main fd8abee, and on mips and mips64 with SDKs exported from kernel
`fix/jobctl-native-stop` 72eb905 (same ABI). A control run on mips with the
fd8abee SDK still fails at the first step: the probe reports that it was
continued without the shell ever seeing a stop. On every profile the jobs stay
in the shell's group, as they must without a controlling terminal. Single-CPU
QEMU only; no physical-hardware or SMP claim.
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

## S5: ten-profile login lane and console login by default

### The lane

`scripts/test_getty_login.py` (`xmake getty-login-test`) drives getty, login
and oksh over the serial console. It builds the distribution kernel, the
login tree and the journalled product image, admits the product image as
`xmake qemu-distro` does, and packs a lane disk from a copy of the same login
root with `tests/native/oksh_job_probe.c` added as `/bin/oksh-jobs`, with the
same Linux journal activation. The admitted product files of the lane disk
and the product image must be identical, so the helper changes nothing that
`tools/console_login_disk.py` pins, and the product image itself is never
booted. The first boot checks, in order:

1. `GETTY event=open pts=0` and first-boot enrollment of the administrator;
2. the shell on the pts: `whoami | cat`, `pwd`, `ls /dev/pts` lists only the
   session's pair, `stat` shows `S_IFCHR|0620` with inode 34816+N;
3. `oksh-jobs session` as a foreground job: its own group, which owns the
   terminal, in the session that the shell (the pid getty reported, login's
   pid after its exec) leads with the pts as controlling terminal;
   `oksh-jobs session &`: its own group without the terminal, which the
   shell's group keeps, then `[1]+ Done`;
4. `^C` (0x03) kills a foreground `oksh-jobs hold || echo hold-interrupted`:
   after the echoed command line, `^C` is echoed and the `|| echo` branch's
   output follows it, and the prompt returns with an empty `jobs`;
5. `^Z` (0x1a) stops the next one: `[1]+ Stopped`, `jobs` lists it, `exit`
   warns `oksh: there are stopped jobs`, `fg || echo fg-interrupted` resumes
   it in the foreground (no prompt for 2 s) and `^C` ends it, again with the
   branch's output after the echoed `^C`;
6. a job stopped with `^Z` at logout: `exit` warns, the second `exit` ends
   the session; getty reports `GETTY event=close ... status=256` (`exit`
   returns the warning's status 1), PID1 reaps getty with status 0 and
   relaunches the console service under the next generation, the next
   session gets the same pts index, and in that session `oksh-jobs alive`
   (`kill(pid, 0)`) finds its own shell but no longer the stopped job;
7. a wrong password is refused (`Login incorrect.`), the right one logs in,
   steps 2-3 again and logout;
8. `:useradd` of `alice`, logout, a login as `alice` (`uid1000` in
   `/home/alice`) with steps 2-3, logout.

Every logout must give the next session the same pts index. The kernel hands
out the lowest free pair and the lane runs one session at a time, so the same
index shows that both ends of the old pair were closed; `ls /dev/pts` cannot
show it, because `/dev/pts/N` disappears at the master's last close even while
a slave stays open. The close event's `reason` is recorded, not checked:
`hangup` when the slave's last close reaches getty before it reaps the shell,
`exit` otherwise; a job that kept the slave open would also give `exit`, and
the pts index and the pid check catch that case.

The second boot of the same disk logs the administrator in, runs steps 2-3
and logs out. Every typed password is absent from the serial log and the
echoed names have no extra blank line. The debug kernel's `OK_*` lines and
PID1's `NATIVE_PID1` lines are filtered before matching, because they
interleave with session output. Password timeouts are four times the largest
enrollment and login times measured per profile before the final run (S4 on
x86_64, the first S5 runs elsewhere), at least 300 s and 120 s; each other
step has `--timeout` (300 s). `tests/tools/test_getty_login_runner.py` feeds
the lane's session checks synthetic serial transcripts; it shows what they
accept and refuse (the echoed command line alone does not satisfy step 4 or
5), not how the guest behaves.

```sh
xmake f -c -y -m debug -a ARCH --kernel_sdk=SDK --systoolchain_dir=TC \
  --linux_journal_image=bzImage --linux_journal_image_sha256=SHA256
xmake getty-login-test [--out=DIR] [--timeout=300] [--no-second-boot]
```

The task refuses a configuration whose journalled image does not run login
(`native_console_login=n`, startup acceptance, an alternative PID1) or that
lacks the Linux image; CI does not run it because hosted runners have no
Linux activation image.

Result (QEMU 10.2.0 from SysToolchain 0.1.0, debug, kernel main fd8abee SDKs,
ABI 82 / UAPI 0.17): both boots pass on all ten profiles, i386, x86_64,
aarch64, arm32, rv64, rv32, loongarch64, mips, mips64 and ppc, in two runs:
before the default changed, with `--native_console_login=y` and the lane
script of f8548ac before its timeout table was updated from that run (script
sha256 `4089d690e6c2...`; it differs only in that table), and on the final tree through `xmake getty-login-test` with
the option left unset (script sha256 `291ccdfdeb15...`). A third run on the
same configuration, after review, used the script of 5820bc4 (sha256
`711c6e3a8cf5...`) with the checks of steps 4-6 as described above: on all
ten profiles every session reused pts 0 and the job stopped at logout was
gone. All 150 logouts (five per run and profile) reported `reason=hangup`.
Seconds under TCG on the development host, ranges over the first two runs,
with up to three lanes or other QEMU jobs running at once:

| Profile | boot to `GETTY event=open` | enrollment | login | wrong password to `Login:` | `:useradd` |
|---|---|---|---|---|---|
| i386 | 10-14 | 93-101 | 13-21 | 14-16 | 31-34 |
| x86_64 | 7-9 | 88-99 | 11-14 | 12-15 | 27-34 |
| aarch64 | 5-9 | 102-126 | 12-21 | 13-18 | 31-42 |
| arm32 | 7-9 | 102-119 | 11-14 | 12-14 | 30-37 |
| rv64 | 6-7 | 73-85 | 15-18 | 16 | 28-29 |
| rv32 | 6 | 72-75 | 14-15 | 15-16 | 27-28 |
| loongarch64 | 4-5 | 62-63 | 15-16 | 16-17 | 26 |
| mips | 7 | 77-95 | 11-17 | 12-19 | 26-28 |
| mips64 | 7 | 69-79 | 13-16 | 14-17 | 26-29 |
| ppc | 5-8 | 65-78 | 14-17 | 15-16 | 26-35 |

Enrollment is one PBKDF2 derive plus the store commits, login one PBKDF2
verify. The final run was slower than the first on most profiles (more
concurrent jobs); the largest enrollment, 126 s on aarch64, is well inside
the 300 s floor, but the script's per-profile table still holds the earlier
figures.

What the lane does not show: physical hardware, SMP, release builds (debug
only), a second concurrent session, `bg` on a pts (the maintenance runner
covers `bg`), and getty's lock-out once processes that outlive their session
hold all eight pts pairs (`docs/native-init.md`); that stays a documented
limit, narrowed by the final review below.

### Console login by default

With the lane passing on ten profiles, `native_console_login` became
tri-state (`docs/native-init.md`, "Persistent console login profile"). Unset,
which xmake shows as `auto`, the journalled product image selects getty and
login: it is packed from a separate login tree, `build/<arch>/<mode>/rootfs-login`,
whose PID1 is `init-login.elf` with the getty fallback manifest. The full,
rescue and release trees, and so the simplefs, plain ext4, boot archive,
release and acceptance images, keep the maintenance `service console simple
/bin/oksh -` without raising; so does the journalled image when startup
acceptance or an alternative PID1 is configured. `y` keeps the strict
behaviour (login on every tree, acceptance refused, `qemu-distro` only with
`--fs=ext4-journalled --interactive`), and `n` the maintenance console
everywhere. xmake itself refuses an explicit `=auto`; leaving the option out
selects it.

Checks:

- Tool tests that pin the selection: `test_native_console_profile.py` (the
  login tree's `/init` is `init-login.elf`, the maintenance one `init.elf`),
  `test_rootfs_profiles.py` (only the journalled image packs `rootfs-login`),
  `test_tty_sessions_runner.py` (only `y` is refused), `test_stage_rootfs.py`,
  `test_logging.py` and `test_console_logging_disk.py`.
- The compiled fallback, which PID1 runs when `/etc/services.conf` is
  missing and which the lane never reaches: `xmake native-init-model-test`
  builds `tests/native_supervisor_tests.c` a second time with
  `OK_NATIVE_CONSOLE_LOGIN`, and that build must exec `/bin/getty` as root
  for the fallback console while the plain build execs `/bin/oksh`; the
  `app-init` and `app-init-login` targets check after linking that
  `init.elf` carries only the oksh fallback and `init-login.elf` only the
  getty one, so a login PID1 built without the define fails its build.
- Configuration controls on x86_64: unset builds `rootfs`, `rootfs-rescue`
  with the maintenance console and `rootfs-login` with getty, and the product
  image passes `tools/console_login_disk.py` admission against `rootfs-login`;
  with `native_init_acceptance=y` the journalled image is the maintenance
  `rootfs.ext4-journalled.img`; `y` with acceptance, `qemu-distro
  --require-native`, `--fs=simplefs` or `tty-sessions-test` is refused; with
  `n` the journalled target selects `rootfs.ext4-journalled.img` and
  `getty-login-test` is refused; a value other than y or n is refused.
- The CI sequence of `.github/workflows/ci.yml` on x86_64, arm32 and ppc
  (`xmake f` without the option, `kernel-sdk-check`, `uapi-test`,
  `libc-test`, `compat-test` on x86_64, `distro_image`,
  `linux-driver-compat`, `rootfs-simplefs`, `rootfs-ext4`, `qemu-distro
  --fs=simplefs --require-native --timeout=90`, `tty-sessions-test
  --timeout=240`, and on x86_64 `scripts/test_persistent_ext4.py` with the
  host QEMU 8.2): passes on all three, with the local SysToolchain directory
  standing in for CI's packaged one. `artifact-test` (the tool suite) ran
  separately once.
- The final ten-profile lane above ran with the option unset.

Other runs on the final tree (kernel main fd8abee SDKs unless noted):
`xmake tty-sessions-test` (both runs, 20 cases) and the acceptance boot
(`kernel-sdk-check` plus `qemu-distro --fs=simplefs --require-native`) pass
on all ten profiles; `scripts/test_oksh_jobs.py` passes on all ten (mips and
mips64 with the fixed kernel, S3); the tool suite with the x86_64 debug SDK
runs 1382 tests, 35 skipped, all passing.

Open after S5:

- The mips/mips64 orphaned-group SIGSTOP fix is on kernel
  `fix/jobctl-native-stop`, not on kernel main; until it merges, the S3
  maintenance runner fails on those two profiles with main SDKs.
- `tests/native/native_password_rotation_input.c` still has its console-era
  `getppid() == 1` check and wraps `ok_login_read_line` for the password
  prompt; it has no runner. `tools/qualify_native_login.py` and
  `tools/read_native_login.py` stay pinned to ABI 69 history.
- BusyBox `ASH_JOB_CONTROL` and line editing stay disabled (decision 0004).
- Receipts are packaged into ObfuscationEvidence in S6.
