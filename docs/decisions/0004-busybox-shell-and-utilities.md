# 0004: BusyBox supplies the musl shell and utility set

Date: 2026-10-28. Status: accepted.

## Decision

- BusyBox 1.37.0 (`ports/busybox`) is the POSIX shell (`ash` as `/bin/sh`) and
  the utility set of the static musl userland. One static multicall binary is
  built per profile; `/bin/<applet>` entries are symbolic links to it.
- The applet selection is `ports/busybox/busybox.config`. An applet is selected
  only when the Linux personality routes the syscalls on its main path; the
  okcrt program of the same name stays in `/bin` until then. The fragment lists
  each held-back applet with the missing call.
- dash 0.5.12 and toybox 0.8.12 are not ported; their candidate descriptors are
  removed.

## Licence review

| Candidate | Licence | Result |
| --- | --- | --- |
| BusyBox 1.37.0 | GPL-2.0-only | Selected. Shipped as a separate program next to the GPL-3.0 distribution code (aggregation); no OS source is linked into it. Corresponding source is the pinned upstream archive plus `ports/busybox/`, both distributed with the image sources. Patches under `ports/busybox/` are GPL-2.0-only. |
| toybox 0.8.12 | 0BSD | Not selected: its test suite needs bash (`scripts/test.sh`, `$'...'`, `<<<`, `${1::1}`) and its own shell is in `toys/pending`, so the exit gate "the utility set passes its own test suite in the guest" cannot be met without porting bash. |
| dash 0.5.12 | BSD-3-Clause; generated `mksignames` output GPL-2.0-or-later | Not selected: BusyBox already provides an Almquist shell; a second shell adds a port without closing a gate. |

musl 1.2.5 is MIT and is linked statically into every BusyBox image; MIT is
compatible with GPL-2.0-only.

## Why

The plan's exit gate needs both a POSIX shell and a utility set whose own test
suite runs in the guest. BusyBox's `testsuite/runtest` is a POSIX `sh` script
that runs under BusyBox `ash`, so the suite needs nothing beyond the port
itself. One multicall binary is also one admission, one static link and one
ELF per profile instead of two.

## Consequences

- `ports/busybox/port.json` pins the archive SHA-256; its `state` advances to
  `builds` only from a real build and to `executes` only from guest receipts.
- Applets that need `link`, `symlink`, `utimensat`, `uname`, `sysinfo`,
  `statfs`, `mknodat`, `fchownat` or `/proc` wait for the kernel to route them;
  each kernel addition moves the corresponding applet from okcrt to BusyBox.
- Job control (`ASH_JOB_CONTROL`) and line editing wait for termios and
  sessions on a PTY (`feat/getty-login`, kernel WT2.2).
