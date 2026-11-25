# WT2.2 getty and login on a PTY

Slice log of `feat/getty-login` (docs/PLAN.md WT2.2), the ObfuscationOS side
of the kernel's ABI 81 terminal and job-control contract (kernel
`docs/modules/tty.md`). Each slice appends its section.

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
81, debug): both runs pass all 19 cases on all ten profiles. A run takes
1.4 s (x86_64) to 4 s (loongarch64) of guest time. This is single-CPU QEMU
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
