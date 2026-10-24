# Workstation implementation progress

This file carries only the most recent continuation. The complete 2026-09/10
history (132 continuation sections, 846 KB) is frozen in the ObfuscationEvidence
repository as `frozen/ObfuscationOS-IMPLEMENTATION_PROGRESS-2026-10-24.md`. The
per-requirement capability matrix is generated from `contracts/ledger.json` into
[STATUS.md](STATUS.md) with `xmake plan-report --evidence-root=.. --output=docs/plans/STATUS.md`.
A new continuation replaces the section below and moves the previous one to the
frozen file; this file stays under 300 lines.

## Current continuation: qualified native raw PTY transport

Canonical Kernel/OS sources now include the 76-path raw PTY slice qualified from
`native-pty-cohort-candidate-v1/joined-source-attempt-05`: 55 replacements and
21 additions. Twenty explicit installed SDK replacements use ABI74/UAPI0.16.0.
The one new source directory is Kernel `tests/host/native_pty`; original source
bytes, SDK byte inverses and original SDK directory identities remain retained.
All ten native/Linux architecture profiles and four supplied musl profiles remain
in scope. A separately qualified two-file OS UAPI-admission repair accompanies the raw
slice: the checker and its maintained tests now accept 0.16 and require the
native PTY declarations. The combined reversible publication contains 78 paths
(57 replacements and 21 additions). The frozen joined05 source and qualification
receipts remain unchanged; this tooling supplement adds no new target-execution
claim. Its exact two-file scope and tests are retained alongside publication.
The ordinary `native_console_login` option still defaults to disabled.
The user-selected ObfuscationOS local first-administrator/password policy remains.

`ok_pty_pair` returns owned master/slave descriptions for eight bounded raw
pairs, each with independent 4096-byte queues per direction. Native read/write,
readv/writev and poll use retained OFD and generation identities; dup/fork,
CLOEXEC, failed user copies, exit and cancellation follow their real owners.
Accepted bytes drain before slave EOF or master EIO after peer retirement.
Character fstat, ESPIPE seek and ENOTTY terminal-ioctl refusals are explicit.
There is no termios, PTY controlling-session/foreground authority, terminal
signal generation, jobs, devpts, slave reopening, Linux PTY I/O or SCM_RIGHTS.
The existing lease-bound controlling console remains separate.

The frozen all-twenty SDK/SDK-only ordinary-console OS campaign passes 150
commands and ten standalone Debug boots. Independent raw readback binds 28,155
files, ordinary OS fingerprinted objects and the exact private-fixture recipe;
a separate supplement checks all twenty ordered boot archives. ELF-to-raw
kernel.bin encoding is hash/export-joined rather than independently reconstructed.
Release keeps optimization with `--cxflags=-g --policies=build.release.strip:n`;
debug test points remain disabled. Four unchanged musl console-probe compile/link
rows retain exact-source applicability; this adds no Linux PTY execution claim.

Exact joined05 maintained hosted runs pass eight suites in each of GCC13 Debug,
Release and ASan/UBSan. The 52-case runtime uses 48 consistently test-enabled
runtime translation units. Complete original/private Kernel source freezes and
a separate 3,688-file readback pass. Sanitizers use `detect_leaks=0`; retained
Clang18 failures are not Clang acceptance. Ten real target compilers accept
valid unsigned pointer aliases; forty invalid-type controls reject at constraints.

Separate actual x86_64 Debug and Release guests complete first-administrator
enrollment and four authenticated UID0 sessions with 52 fixture records. A
stopped-guest observer checks eight actual armed read/full-write waits, including
OFD, endpoint generation, saved frame, entry-stack lease and address-space owner,
before the host releases peer progress. The separate 3,555-file reader binds
serial chronology, sources, SDKs, ELFs and observer JSON/logs. It does not replay
GDB or inspect an independent memory dump. Binary payload checks execute inside
the pinned fixture; PIDs add no separate SID/UID evidence. Guests are host-retired,
so this campaign adds no orderly-shutdown or power-loss-persistence claim.

A fresh canonical standalone x86_64 Debug build/boot, all twenty installed SDK
admissions, targeted maintained contract/wrapper checks and SDK-only ordinary
Debug/Release distribution builds pass after publication. Source and SDK inverses,
original SDK directory identities, all pre-existing source directories/modes,
existing account disks and image namespaces are preserved. The exact one new
source directory is tracked for reversible restoration. Publication is reversible,
not globally atomic or crash atomic. Earlier failed attempts and reader/tool
successors remain separately retained and are never relabelled passed.

Two publication preparation attempts remain failed and retained before any
canonical source or SDK write. Their reader-alias and hosted-guard-time
schema assumptions are repaired by a separately reviewed successor that
checks exact symbolic-link chains and ordered UTC guard timestamps; no
target qualification evidence is relabelled or replaced.

The qualification receipt is
`native-pty-cohort-candidate-v1/joined05-bounded-qualification-completion-v1.json`.
Canonical publication, validation and document identities are joined by
`native-pty-completion-preparation-v1/canonical-rollout-completion-v1.json`;
the current pointer is `build/qualification/native-pty-current-handoff-v1.json`.
All thirteen full M0-M12 gates remain open. The ledger remains 95 seed
requirements, 175 test definitions and eleven historical evidence records with
zero verified requirements; this slice does not add ledger mappings. Physical
M11 and manual desktop M12 acceptance remain user-deferred. Production ext4
remains `<1,9>`, signed32 and without paired I/O. The next software slice is
per-generation PTY controlling-session/foreground authority and lifecycle-aware
read/readv/poll rechecks, followed by authenticated PTY launch and terminal work.
