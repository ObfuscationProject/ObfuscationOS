# Workstation implementation progress

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

## Previous continuation: bounded historical console evidence integration

The OS-only continuation under
`build/qualification/console-evidence-mapping-candidate-v1/` adds a read-only
historical receipt admission tool and portable synthetic controls, plus bounded
ledger/test/command/document mappings. The runtime remains the admitted
ABI73/UAPI0.15 console implementation. Kernel sources, all twenty installed SDKs,
existing account disks and image namespaces are preserved. No OS guest is
executed by this continuation. A fresh standalone Debug kernel boot checks the
unchanged integration boundary.

The ledger now contains 95 seed requirements, 175 test definitions and eleven
historical execution-evidence records: nine host/model/tool and two actual
x86_64 Debug/Release guest records. `P10.console-control` preserves all ten
profiles; `P10.console-control-x86_64` and
`N.console-login-pipeline-x86_64` state the narrower native scope. Existing
`A06.sdk` now names ABI73/UAPI0.15 and links the exact 91-test consumer command.
The console contract entry links its exact seven-test command. The general
shell, signal and service gates remain open with explicit bounded references.
No requirement is promoted to `verified`.

`tools/console_receipt_admission.py` requires the physical project root and
explicit completion SHA256. It streams 24,410 immutable retained files, including
all 24,340 qualification inputs, checks exact original/successor validator
provenance, publication/document relationships and canonical-validation products,
then emits eleven proposed mappings to stdout. It imports no receipt-supplied
code, executes no old helper/guard, writes no ledger and runs no guest. It
rechecks historical evidence, not current installed source/SDK directory identity,
inverse trees or protected disks. The reversible publication separately guards
those current resources. The ledger validator checks artifact hashes and
relationships and requires an explicit evidence root; xmake plan-check/report
now accept that root. Synthetic mutation tests keep their own artifact fixtures.

The historical native scope remains four authenticated UID0 sessions, UID1000
fixture peers, 136 native and twelve Linux console records. Ten hosted adapters
and ten standalone Debug boots do not become ten console-feature guests. Four
supplied musl profiles compile; actual musl console execution remains x86_64,
using the admitted debug-optimized-v1 static libc for both guest modes. Guest
armed waiting remains unproven and retained-group native foreground coverage is
absent. Raw readers do not reconstruct original nonce bytes. PTYs, termios,
terminal-generated signals, full jobs, graphical login and broader authority
remain open. No new orderly-shutdown, power-loss, SMP, physical or manual
desktop acceptance is claimed. Original failed controls remain retained.

Portable synthetic tests and exact retained-input admission pass. Ledger schema,
relationships and artifact hashes pass with the retained evidence root. The full
M0 gate intentionally remains nonzero for seed inventory, missing reviewed
normative source indexes/source-unit mappings and other qualification gaps.
All thirteen complete M0-M12 gates remain open. Physical M11 and manual desktop
M12 remain user-deferred. Production ext4 remains `<1,9>`, signed32 and without
paired I/O. The joined receipt is
`console-evidence-mapping-candidate-v1/canonical-rollout-completion-v1.json`; the
pointer is `build/qualification/console-evidence-mapping-current-handoff-v1.json`.

## Previous continuation: qualified bounded native controlling console

Canonical Kernel/OS sources now include the 90-path controlling-console slice
qualified under `build/qualification/native-console-control-candidate-v1/`:
72 replacements and eighteen additions, with no source removals or new source
directories. Twenty exact installed SDK replacements use ABI73/UAPI0.15.0,
session lifecycle v3, group signals v2 and the mandatory console-control profile.
Producer and consumer admission require nineteen console proof headers. All ten
native/Linux profiles and four supplied musl profiles remain in scope.

The boot-CPU serialized console keeps its lease epoch, controlling SID and
foreground PGID separate. Only the original lease's current session leader
acquires it, with scalar-zero attach and no steal. Login attaches after setsid
and before credential drop. Exact target-endian four-byte PID ioctl copies use
the generated encodings for all ten Linux profiles, including MIPS and PPC.
Same-session background foreground-setting is supported without SIGTTOU.
Background/detached read/readv returns EIO without consuming bytes; stale input
authority returns EACCES. Background poll reports ERR without HUP; Linux select
folds errors into interested descriptor sets. Attachment, foreground transfer
and process-group/session changes wake and recheck authority. Fork/exec preserve
identity; setsid logically detaches. Lease-leader/PID1 death or revocation clears
attachment and queued input. Retained zombies reserve group identity until reap;
an empty foreground group has no fallback.

The native shell gates pipeline launch, groups children, transfers foreground
ownership before releasing them and reclaims it afterward. A canonical CLOEXEC
console alias preserves this authority through redirection and nested shells.
ObfuscationOS still interactively creates the first password-protected UID/GID0
administrator, supports bounded ordinary local accounts and authenticated
password rotation, and checks private-home session entry. No seeded credentials
or account-initialization policy changes are introduced.

All twenty fresh Kernel SDK/SDK-only ordinary-console OS tuples and ten
standalone Debug QEMU boots pass. Hosted actual-runtime and sanitizer campaigns
each pass 75 native and 183 Linux calls across ten selected adapters. Existing
session/group-signal and sanitized lease regressions pass. Frozen contracts pass
233 tests with one existing UAPI skip. Four supplied musl profiles compile; this
does not establish general per-architecture musl execution.

Actual single-CPU x86_64 Debug and Release ordinary guests each complete two
authenticated UID0 logins, with normal PID1 generation1 reap before generation2
launch. Across four sessions, 136 native and twelve Linux records cover native
UID1000 fixture peers, nonce/input authority, explicit foreground transfer,
12,289-byte three-stage pipelines, redirected aliases, nested shells and actual
x86 musl/Linux select/read/readv/poll. Both modes use the admitted
debug-optimized-v1 static musl library and freshly compile their guest probes.
This is not a nonzero-UID account-login claim. Guest wait experiments retain
`armed=unproven`; actual scheduler-armed coverage is hosted only. The retained
group-identity foreground case remains untested in a guest.

The final runner passes 127 stream/parser/admission controls. Separate raw
contract readers check exact identities, serial cases and PID1 chronology with
thirteen rejection controls per mode, without importing the producer. They bind
the hashed host input and reported FNV64; original nonce bytes are not retained
or reconstructed. The producer checked the actual nonce and noecho during
execution. These are separate contract readers, not a newly completed peer
review. The host retires the guests; no synchronized shutdown or power-loss
persistence is claimed by this campaign.

Fresh canonical standalone Debug build/boot, all twenty installed SDK admissions,
190 targeted tests (one existing UAPI skip) and SDK-only Debug/Release OS
construction pass. The
canonical validator executes 35 commands. Publication retains all exact source
predecessors, source inverses, full SDK byte inverses and original SDK directory
identities. Complete source directory inventories/modes and existing images,
account disks and image namespaces remain preserved. It is reversible, not
globally atomic or crash atomic. The joined receipt is
`native-console-control-candidate-v1/canonical-rollout-completion-v1.json`; the
current pointer is `build/qualification/native-console-control-current-handoff-v1.json`.

Original fixture/link/assertion/SDK failures, the partial serial-prompt Release
attempt, development parser chronology failures, first raw-reader subset-field
mismatch and publisher-control diagnostic-count mismatch remain retained.
Accepted successors do not relabel them passed. The sealed v1 canonical
validator contains a plural publisher-filename typo and is preserved unchanged;
the admitted v2 successor corrects exactly that reference. Publisher controls
retain the original failed result and separately admit all twenty passing cases.

This supplies one lease-bound controlling console and bounded foreground
authority. Referenced independent terminals, PTYs, termios/line discipline,
generic `/dev/tty`, HUP/stop/continue/terminal-generated signals, complete shell
jobs, graphical login and broader service/session authority remain open. SMP,
physical execution and full POSIX terminal conformance are not inferred.
Production ext4 remains `<1,9>` with signed32 metadata time and no paired I/O.
All thirteen complete M0-M12 gates remain open. The ledger still records 92 seed
requirements, 168 test definitions and zero integrated execution entries;
separate qualification receipts do not close it. Physical M11 and manual desktop
M12 acceptance remain user-deferred while software work remains in scope.

## Previous continuation: qualified bounded native process-group signals

Canonical Kernel/OS sources now include the 60-path bounded process-group
signal slice qualified under `build/qualification/native-group-signals-candidate-v1/`:
52 replacements and eight additions. Twenty exact installed SDK replacements
use ABI72/UAPI0.14.0, session profile v2 and the mandatory bounded group-signal
profile. All original SDK directories, full byte inverses and source inverses
remain retained. Complete canonical source directory inventories and modes are
preserved. All ten native/Linux architecture profiles and four supplied musl
profiles remain in scope; this does not add general musl guest acceptance.

Native and Linux `kill` boundaries now accept selector zero for the sender's
current PGID and selectors below minus one for a named PGID. This slice supports
only signal-zero permission/existence probes, TERM15 and KILL9 for groups.
Selectors and signals use signed low32 values; INT_MIN returns ESRCH without
signed overflow. Broadcast minus one and other group signals remain unsupported.
Selection copies the sender's credentials/PID/PGID and snapshots at most 64
recipient PIDs, then resolves and checks each recipient independently. Any
accepted recipient yields success; an empty group yields ESRCH. PID1 protection,
UID permission checks and existing positive-PID native/Linux behavior remain.
Fatal delivery is deferred until the sender's saved syscall result is published,
before user reentry. Group membership can survive the original leader's reap.

Hosted actual-runtime checks pass 488 assertions with ten selected signal ABI
profiles, separately repeated under ASan/UBSan. Existing private process-signal
426 and ordinary production-signal Debug398/Release398 checks pass. Those are
hosted implementation checks with substituted architecture entry and user-copy
boundaries. Frozen producer/consumer, publication and Linux-generation controls
pass 220 tests with one existing UAPI skip. All twenty fresh Kernel SDK/SDK-only
ordinary-console OS tuples and all ten standalone Debug QEMU boots pass.

Separate actual single-CPU x86_64 Debug and Release guests each execute two
ordinary authenticated UID0 administrator logins. Across the four sessions,
32 group cases and 84 fork/exec peers exercise negative-PGID TERM/KILL,
current-group self termination, no post-kill user marker, a group-external
heartbeat, retained membership after leader reap, UID1000 partial permission
success and all-root EPERM, signal-zero no-death probes, absent-group/INT_MIN
ESRCH and broadcast refusal. Pipe handshakes establish child identity before
and after exec. Independent readback reconstructs the raw serial cases and
binds their SDK, compiler, linked image and source identities. This tests
nonzero UID senders inside the fixture, not a nonzero UID account login.
The host retires each guest after acceptance; no synchronized shutdown or
power-loss persistence is claimed by this campaign.

Fresh canonical standalone Debug build/boot, all twenty installed SDK
admissions, 177 targeted SDK/ABI tests and SDK-only Debug/Release OS construction
pass. Publication retains exact source predecessors, full byte inverses and
original SDK directory identities. It is reversible, not globally atomic or
crash atomic. Existing account disks, image namespaces and prior qualification
sources remain preserved. The joined receipt is
`native-group-signals-candidate-v1/canonical-rollout-completion-v1.json`; the
current pointer is `build/qualification/native-group-signals-current-handoff-v1.json`.

Original hosted fixture/link/entropy-provider failures, stale development-only
SDK rejection expectations and the initial parser replay's input-pin refusal
remain retained. Accepted successors do not relabel them passed. The final
candidate snapshots retain the complete canonical directory maps, including
empty directories. ObfuscationOS keeps interactive first-administrator setup
with a user-selected password and no seeded credentials, local account files,
bounded ordinary accounts and authenticated password rotation.

This adds bounded process-group termination/probes. Controlling terminals,
foreground terminal authority, PTYs, HUP, stop/continue, terminal-generated
signals, shell jobs, graphical login and broader service/session authority remain
open. Production ext4 remains `<1,9>` with signed32 metadata time and no paired
I/O. All thirteen complete M0-M12 gates remain open. The ledger still records
92 seed requirements, 168 test definitions and zero integrated execution entries;
separate receipts do not close it. Physical M11 and manual desktop M12 acceptance
remain user-deferred while software work remains in scope.

## Previous continuation: qualified native process sessions

Canonical Kernel/OS sources now include the 69-path process-session slice
qualified under `build/qualification/native-sessions-candidate-v1/`: 59
replacements and ten additions. Twenty exact installed SDK replacements use
ABI71/UAPI0.13.0; all original SDK directories, byte inverses and source inverses
remain retained. Canonical directory inventories and modes are preserved.
All ten native architecture profiles and four supplied musl profiles remain in
scope. ObfuscationOS continues interactive first-administrator enrollment with a
user-selected password and no seeded credentials, local password authentication,
bounded ordinary accounts and authenticated password rotation.

The Kernel exposes scalar `setsid`, `setpgid`, `getpgid`, `getsid` and `getpgrp`.
Fork inherits SID/PGID; successful exec and reparent preserve them. Parent
regrouping is limited to its own unexecuted same-session child, with explicit
ESRCH/EACCES/EPERM/EINVAL refusals. Zombie group retention, group-leader reap and
nonleader getter behavior have separate hosted coverage. Linux adapters retain
the exact generated numbers for all ten profiles and normalize signed32 PIDs.
Authenticated OS login closes account stores, creates and verifies its own
session/group, applies checked home/credential policy, and rechecks before shell
exec. Existing console-generation input leases remain independent.

All twenty fresh SDK/SDK-only ordinary-console OS tuples and ten standalone
Debug QEMU boots pass. Ten hosted lifecycle profiles each pass 510 checks;
separate x86_64 ASan/UBSan lifecycle and actual native/Linux dispatch checks
cover ten Linux adapters, 46 forms and 160 calls. Producer/consumer admission,
archive publication controls and Linux generation checks cover 215 tests, with
one existing UAPI skip. Actual x86_64 Debug and Release ordinary guests each
execute two authenticated first-administrator (UID0) login sessions and four
process/exec cases per session. The current guest slice does not test a nonzero
UID login; prior bounded-account evidence remains separate. Serial records join distinct
shell SID/PGIDs, successful exec pipe
handshakes, parent EACCES, the first shell's normal PID1 reap and its successor.
The host retires each guest after acceptance; this campaign claims no clean
shutdown or power-loss persistence.

Fresh canonical standalone Debug build/boot, all twenty installed SDK
admissions and SDK-only Debug/Release OS construction pass. Publication uses
retained inverse preflight, exact predecessor checks, original SDK directory
renames and checked journal updates. It is reversible, not globally atomic or
crash atomic. Existing images, account disks and image namespaces are preserved.
The joined receipt is
`native-sessions-candidate-v1/canonical-rollout-completion-v1.json`; the current
pointer is `build/qualification/native-sessions-current-handoff-v1.json`.

Original missing-link/snapshot hosted attempts, the guest PATH failure, the
first guest after-marker framing failure and the archive-test discovery
invocation failure remain retained. Accepted successors do not relabel them
passed. Private source snapshots use different directory metadata and omit
empty canonical directories; publication copies the exact frozen files while
preserving the full canonical directory inventory.

This supplies serialized boot-CPU process session/group identity. Controlling
TTYs, PTYs, foreground groups, group signals, stop/continue, interactive job
control, graphical login and broader service/session authority remain open.
Physical/SMP execution and complete POSIX-session conformance are not inferred.
Production ext4 remains `<1,9>` with signed32 metadata time and no paired I/O.
All thirteen complete M0-M12 gates remain open. The ledger still records 92 seed
requirements, 168 test definitions and zero integrated execution entries;
separate receipts do not close it. Physical M11 and manual desktop M12
acceptance remain user-deferred while software work remains in scope.

## Previous continuation: qualified synchronized native poweroff

Canonical Kernel/OS sources now include the 24-path synchronized poweroff slice
qualified under `build/qualification/native-poweroff-candidate-v1/`: nineteen
replacements and five additions without new source directories. Twenty exact
installed SDK replacements retain ABI70/UAPI0.12.0. Complete source and SDK
inverses remain available. All ten native architecture profiles and four supplied
musl userland profiles remain in scope.

Ordinary `service-ctl poweroff` uses the original root PID1 scalar PREPARE and
queued COMMIT coordinator, one immutable action/token, the original fixed
retirement deadline, fresh ECHILD, resource retirement and the original storage
owner's clean seal. The backend requires explicit
`native_qemu_piix4_poweroff=y`; its source default is disabled. Only the selected
x86_64 SDKs advertise
`terminal_poweroff_backend=x86_64-qemu-piix4-pm-v1`; other tuples advertise
`unsupported`. The final backend discovers the actual PCI device, validates
PIIX4 PM identity and enabled bounded PMBASE, performs non-consuming preflight
and revalidates before the interrupt-disabled S5 request. It neither guesses a
PM I/O port nor supplies a general ACPI implementation.

All twenty fresh Kernel SDK/SDK-only ordinary-console OS tuples and all ten
standalone Debug QEMU boots pass. Separate actual single-CPU x86_64 Debug and
Release campaigns each pass two boots and two natural shutdowns, including
same-private-disk restart, existing-account password authentication and exact
persisted-file read. The total is four boots and four shutdowns. Independent raw
readers bind the linked guest PM write, S5 device observation, guest-caused QMP
SHUTDOWN event, natural QEMU exit zero, account/KDF and metadata readback and
direct final read-only filesystem checks. The first retired-disk check uses
retained source-pinned capture and read-only raw logs; the final same disk is
independently reinspected. Device-trace/source observations do not establish
installed-QEMU and source-build equivalence. Hosted controls and standalone
boots remain distinct from these ordinary OS guest campaigns.

Fresh canonical standalone build/boot, installed-SDK admissions, targeted hosted
controls and SDK-only ordinary-console Debug/Release image construction pass.
Consumer builds use verified disposable source snapshots and explicit installed
canonical SDKs. Existing account disks and image namespaces are preserved, as
are the frozen source/SDK evidence and complete inverses. Publication is
reversible, not globally atomic or crash-atomic. The joined receipt is
`native-poweroff-candidate-v1/canonical-rollout-completion-v1.json`; the current
pointer is `build/qualification/native-poweroff-current-handoff-v1.json`.

Original trace, enrollment and independent-reader attempts remain failed.
The first staging operation exceeded its parent timeout and is not admitted as
completed staging. The first publication prepare also failed on a string/Path
type mismatch before publication; its corrected successor retains that failure.
Accepted successors do not relabel any of these attempts passed. The first
canonical validator retains its final-guard failure for two vanished,
unreferenced xmake probe temporaries. A separate read-only re-admission checks
all 37 successful command rows, complete remaining trees and products without
rebuilding or rerunning guests.

ObfuscationOS still creates the first UID/GID 0 administrator interactively at
first startup with a user-selected password and no seeded credentials. Bounded
ordinary local accounts, authenticated password rotation and checked private-home
session entry remain available. Broader accounts/sessions, graphical login,
PTYs, Internet DNS/NTP, mount mutation, general shutdown policy, general ACPI
and other reboot/poweroff backends remain open. Natural emulator teardown
can flush block state. The selected one-CPU QEMU PIIX4 orderly-shutdown result
does not qualify torn writes, volatile-cache loss, general power failure
or physical hardware. Production ext4 remains `<1,9>` with signed32 metadata
time and no paired I/O. All thirteen complete M0-M12 gates remain open. The
ledger still records 92 seed requirements, 168 test definitions and zero
integrated execution-evidence entries; separate receipts do not close it.
Physical M11 and manual desktop M12 acceptance remain user-deferred while their
software requirements remain in scope.

## Previous continuation: qualified bounded ordinary local accounts

Canonical Kernel/OS sources now include the 93-path accounts slice qualified
under `build/qualification/native-accounts-candidate-v1/`. All twenty installed
SDK tuples use ABI70/UAPI0.12.0 with checked mode/owner metadata operations.
The ten native architecture profiles and four supplied musl profiles remain
unchanged in scope. First startup still creates the administrator interactively
under the ObfuscationOS name; that account retains UID/GID 0 and `/root`.
At a fresh `Login:` prompt, authenticated `:useradd` creates a bounded ordinary
account and `:passwd` changes the authenticated account's password. The protected
registry supports at most sixteen ordinary users with salted PBKDF2 verifiers.

ADD stages the complete registry successor before home mutation, then checks
and durably prepares the matching 0700 home before publication. Recovery of a
pending ADD requires administrator authentication. Ordinary session entry closes
private registry descriptors, sets and verifies all real/effective/saved GIDs
and UIDs, enters the checked home, clears password material and applies umask
0077 before executing the native shell with fixed account environment values.
This does not establish a general PTY or graphical-session implementation.

All twenty fresh Kernel SDK/SDK-only ordinary-console OS tuples and all ten
standalone Debug QEMU boots pass. Separate actual x86_64 Debug/Release evidence
admits four ordinary boots/four stable linked QMP HALTs, same-disk account login,
private-home/file bytes and permissions, password changes and read-only final
filesystem checks. Two separate credential-fixture boots exercise permanent
ordinary-ID drops and refusals; their clean HALTs have serial evidence, not QMP
terminal observations. Ordinary producers retain their exact failed root-file
postcheck: root's inherited umask0022 creates0644 inside0700 `/root`, while the
ordinary session's0077 creates0600. The independent reader admits original raw
execution and corrected postchecks without relabelling those producers passed.

Separate x86_64 Debug readers admit eleven high-level ADD/ROTATE software-call
recovery cases and one checked-ownership no-cut control (label 0) plus fourteen completed-call interruptions (1-14).
They bind exact private products, phase disks, guest commands, serial records,
registry successors, home metadata, login recovery and read-only final fsck.
The ownership reader proves exact committed replay on the mounted disk before
authentication, so a later authenticated retry cannot hide missed replay.
The original pre-checkpoint R1 enrollment failure and failed ownership pilot
remain retained; the exact R1 failed call and a storage-flush cause remain
unconfirmed. Completed-call interruption is not torn-media, volatile-cache-loss
or general physical power-failure qualification.

The reversible rollout publishes 58 Kernel and 35 OS paths (64 replacements and
29 additions) and twenty exact SDK directories, retaining source/SDK inverses.
Fresh canonical standalone x86_64 Debug build/boot, installed-SDK admissions,
focused hosted controls and SDK-only ordinary image construction pass. The preserved v1 canonical reader counted ten fixture commands although the helper
executed eleven; v2 re-admits the exact 33 successful command rows and runs only
the five remaining fresh standalone/consumer commands. All 199 targeted unittest
methods and sanitized hosted results remain bound to their original execution.
This post-promotion rebuild adds no new account guest campaign. Existing account
disks and image namespaces are preserved. Publication is reversible, not
globally atomic or crash-atomic. The joined receipt is `native-accounts-candidate-v1/canonical-rollout-completion-v1.json`.

At the accounts publication, synchronized native poweroff was the next M7
slice and the default-off x86_64 QEMU PIIX4 PM profile was design preparation.
The current continuation above records its later bounded implementation and
qualification. General ACPI and other platform poweroff backends remain open.

Broader accounts/sessions, graphical login, PTYs, Internet DNS/NTP, mount mutation,
general shutdown and the other milestone requirements remain open. Production
ext4 remains `<1,9>` with signed32 metadata time and no paired I/O. All thirteen
complete M0-M12 gates remain open. The recorded ledger audit still contains 92
seed requirements, 168 test definitions and zero integrated execution-evidence
entries; separate receipts do not close that ledger. Physical M11 and manual
desktop M12 acceptance remain user-deferred, while their software work remains
in scope.

## Previous continuation: qualified synchronized native reboot

Canonical Kernel/OS sources now include the 39-path synchronized reboot slice
qualified under `build/qualification/native-reboot-candidate-v2/`. Ordinary
`service-ctl reboot` uses the original root PID1 scalar PREPARE and queued COMMIT
coordinator, one immutable action/token, the existing fixed retirement deadline,
fresh ECHILD, resource retirement and the original storage owner's clean seal.
The x86_64 PC/8042 backend requires explicit `native_pc8042_reboot=y`; its source
default is disabled. The two selected x86_64 installed SDKs advertise
`x86_64-pc-8042-v1`; the other eighteen advertise `unsupported`. ABI69 and
UAPI0.11.0 remain unchanged, with all ten native and four supplied musl profiles.

All twenty fresh Kernel SDK/SDK-only OS tuples and all ten standalone Debug
QEMU boots pass. Both ordinary x86_64 Debug/Release products pass enrollment,
persisted-file creation, synchronized reboot, same-process/same-disk existing
account authentication and exact file read, then a clean stable terminal HALT.
Together these successful campaigns contain four boots, two reboot requests
and two clean HALTs. The pinned SeaBIOS deliberately follows the one native
8042 reset with one firmware CF9 reset. Raw QMP and CPU reset traces bind both
origins, and reject extra resets; no host reset is sent. The final clean disks
pass independent read-only `e2fsck -fn`, account/KDF and persisted-file checks.
There is no intermediate account snapshot, measured replay count, host repair
or general power-loss safety claim.

Independent source, linked-code, firmware and raw guest readers pass. Hosted
policy/dispatch/storage controls remain distinct from native execution. The
original runtime shared-owner count assertion still fails and is reproduced
exactly on baseline; no unrelated assertion is weakened. Initial configuration,
preboot socket restriction and strict single-reset observer failures remain
retained separately from accepted campaigns. The corrected observer passes
33 offline controls normally and with optimized Python.

The reversible publication changes 32 existing source files, adds seven files
without adding source directories and replaces twenty exact SDK directories,
retaining all original-file and SDK inverses. Fresh canonical standalone Debug
boot, installed-SDK-only distro construction and 105 targeted tests pass;
existing account/image families retain their bytes and namespaces. Publication
is reversible, not crash-atomic. The joined receipt is
`native-reboot-candidate-v2/canonical-rollout-completion-v1.json`; the current
pointer is `build/qualification/native-reboot-current-handoff-v1.json`.

ObfuscationOS still creates the first local administrator interactively and
supports password login/rotation. General accounts, graphical login, PTYs,
Internet DNS/NTP, mount mutation, other reboot backends and poweroff remain
open. Production ext4 remains `<1,9>` with signed32 metadata time. All complete
M0-M12 gates remain open; the ledger retains 92 seed requirements, 168 test
definitions and zero integrated execution-evidence entries. Physical M11 and
manual desktop M12 acceptance remain user-deferred.

## Previous continuation: authenticated administrator password rotation

Canonical sources now include the eleven-file OS-only password rotation slice
qualified under `build/qualification/native-password-rotation-candidate-v1/`.
After exiting a shell, an administrator selects exact `:passwd` at a fresh
`Login:` prompt. Login verifies the current password with the full KDF and
monotonic retry delay, reads hidden matching new passwords and obtains a fresh
trusted salt before staging the unchanged account format. The administrator
identity remains UID/GID 0 with `/root`. Startup still creates the first account
interactively under the ObfuscationOS name.

All twenty native architecture/mode app compile tuples and ordinary x86_64
Debug/Release SDK-only image builds pass. Actual-source hosted account-store,
login/input/password and packaging checks remain separate from native execution.
The ordinary products pass six boots and six clean QMP-observed HALTs: enroll A,
refuse wrong current/mismatched new input, rotate to B after logout, reject A,
authenticate B and repeat authentication after restarting the same disk.
Independent raw readers bind completed processes, products, input/serial/QMP,
protected account metadata, password oracles and read-only filesystem checks.

Separate refusal campaigns pass four boots: unavailable entropy preserves A and
permits subsequent A login before clean HALT; deliberately partial staging holds
closed over two fresh login leaders without prompting or cleanup and is retired
intentionally. Separate authority fixtures pass two boots and two clean HALTs;
old adopted descendants cannot read, readv, duplicate, poll or control the fresh
console while new password input is buffered. Separate publication-cut fixtures
pass six boots and four clean HALTs, with two intentional interruptions after
complete B staging and before rename. Native recovery on the same disks rejects
A, authenticates B before publishing it and preserves the exact staged B bytes
and inode. There is no host repair, measured replay-count or general power-loss
safety claim. Together the lanes contain eighteen successful boots, fourteen
clean HALTs and four intentional forced retirements.

The reversible publication changes seven existing files and adds four fixture
sources with no new source directory. Fresh canonical Debug installed-SDK-only
image construction and 61 targeted tests pass with unchanged Kernel sources,
all twenty installed SDKs and existing account disks. No SDK or PID1 change is
included. Publication retains all seven original-file inverses and does not
claim crash atomicity. The joined receipt is
`native-password-rotation-candidate-v1/canonical-rollout-completion-v1.json`;
the continuation pointer is
`build/qualification/native-password-rotation-current-handoff-v1.json`.
Preboot sandbox/locking failures and earlier admission/parser attempts remain
retained separately from successful execution.

General accounts, graphical login, PTYs, Internet DNS/NTP, general mount mutation
and synchronized reboot/poweroff remain open. The next bounded system-service
slice is synchronized native reboot, with explicit platform admission and
storage consistency. Production ext4 remains `<1,9>` with signed32 metadata time.
All complete M0-M12 gates remain open; the ledger retains 92 seed requirements,
168 test definitions and zero integrated execution-evidence entries. Physical
M11 and manual desktop M12 acceptance remain user-deferred.

## Previous continuation: qualified managed local resolver

Canonical sources now include the twenty-file OS-only local resolver slice
qualified under `build/qualification/native-resolver-candidate-v1/`. PID1 starts
root `resolved` with notification readiness after completely parsing a protected
bounded `/etc/hosts` snapshot and opening its authenticated public UNIX socket.
Ordinary `resolvectl status` and `resolvectl lookup NAME` support normalized ASCII
names, aliases and strict dotted-decimal IPv4 literals. Conflicts and malformed
configuration reject startup without publishing a partial snapshot. Each query
uses one fixed 1000 ms monotonic request/reply deadline. Administrator edits take
effect after `service-ctl restart resolved`; hosts content is mutable configuration
and remains outside immutable executable hashes.

Fresh compilation passes all twenty native architecture/mode tuples: forty
executables, 440 objects and 500 dependency tables. Independent compiler readback
checks all products and actual logged commands. Both complete ordinary x86_64
Debug/Release SDK-only images pass. Hosted actual-source ASan/UBSan, independent
parser vectors, file/transport faults and 79 packaging controls remain separate
from native execution.

Actual single-CPU x86_64 Debug and Release ordinary products each pass first
administrator enrollment, snapshot queries, strict numeric/name input refusal,
configuration edit, notified daemon restart and a clean HALT. The same disk then
restarts without host recovery, refuses a wrong password, authenticates, loads
the persisted hosts file, repeats edits/restart checks and cleanly halts again.
Across four boots, fifty wire queries, eight malformed CLI refusals, four daemon
restarts and four existing mount-inventory regressions pass. Four stable linked
QMP terminal observations and independent raw readers bind serial/input/product
identities, both halted snapshots per mode, account/password and persisted-file
readback, executable/config metadata and direct read-only fsck. These ordinary
guests use administrator callers; no native non-root or malformed/deadline
transport fixture is claimed for this slice.

The exact twenty-file reversible publication adds three source directories and
retains every original-file inverse. Fresh canonical x86_64 Debug installed-SDK
image construction and 43 targeted tests pass while guarding Kernel sources,
all twenty installed SDK trees and existing account/image families. This rebuild
adds no new guest execution. Publication is reversible, not crash-atomic. The
joined receipt is `native-resolver-candidate-v1/canonical-rollout-completion-v1.json`;
the continuation pointer is `build/qualification/native-resolver-current-handoff-v1.json`.
Preliminary environment/observer failures and the independent reader's initial
incorrect QEMU retirement assumption remain retained with their successors.

This supplies local hosts resolution only. Internet DNS, libc-wide resolution,
NTP, general mount mutation, broader accounts/sessions and synchronized
reboot/poweroff remain open. The next bounded account slice is authenticated
administrator password rotation while preserving existing console authority.
Production ext4 remains `<1,9>` with signed32 metadata time. All complete M0-M12
gates remain open; the ledger retains 92 seed requirements, 168 test definitions
and zero integrated execution-evidence entries. Physical M11 and manual desktop
M12 acceptance remain user-deferred.

## Previous continuation: qualified read-only native mount inventory

Canonical Kernel/OS sources now include the 52-path mount-inventory slice
qualified under `build/qualification/native-mount-candidate-v1/`. All twenty
installed architecture/mode SDKs retain module ABI69 and advance to UAPI0.11.0.
The public native `mount_info` syscall returns an initialized 288-byte record
for each of nine lifetime slots. Generation is derived from existing attachment
and detached history; no class layout, vtable, mount authority or provider
callback is added. Ordinary `mountctl status` accepts only a coherent complete
inventory, bounds retries and escapes path bytes before printing.

Fresh standalone Kernel exports and SDK-only ordinary-console OS image builds
pass all twenty architecture/mode tuples. Standalone Debug QEMU checks pass on
all ten architectures. Hosted VFS, actual-source dispatch and sanitizer checks,
twenty emitted wire/header compile rows and 155 SDK/exporter/parser controls
remain distinct evidence lanes. The SDK consumer and standalone UAPI checker
also reject comment-decoy versions, expression tails and alternate preprocessor
contexts rather than accepting a numeric prefix as the version.

Actual single-CPU x86_64 Debug and Release ordinary products each pass first
administrator enrollment, persisted-file creation, a clean HALT, same-disk
restart without host recovery, wrong-password denial, successful login and a
second clean HALT. Across four boots, eight `mountctl status` executions report
72 rows: the covered underlying RAM namespace, owned ext4 provider, owned
`/run` RAM attachment and six unused slots, at topology generation 3.
Independent raw serial/ELF/QMP readers verify those outputs and four stable
terminal HALTs. Both halted disk snapshots per mode pass direct read-only fsck,
persisted program/account metadata and file/password readback. These guests
exercise administrator callers; a non-root native guest probe remains open.

The reviewed publication replaces exactly 31 Kernel and 21 OS source paths
and all twenty SDK directories, retaining complete original-file and UAPI0.10
SDK inverses. Publication is reversible, not crash-atomic. Fresh canonical
x86_64 Debug installed-SDK-only full image construction and 40 targeted tests
pass without replacing existing account disks or claiming another guest run.
The joined record is `native-mount-candidate-v1/canonical-rollout-completion-v1.json`;
the workspace pointer is `build/qualification/native-mount-current-handoff-v1.json`.
Retained reader/orchestration failures and their corrected successors remain
separate from accepted evidence.

This provides read-only topology observation. General mount/umount mutation,
resolver/network-time services, general account/session policy, synchronized
reboot/poweroff and every complete M0-M12 gate remain open. Production ext4
remains `<1,9>` with signed32 metadata time. The ledger still contains 92 seed
requirements, 168 test definitions and zero integrated execution-evidence
entries. Physical M11 and manual desktop M12 acceptance remain user-deferred.

## Previous continuation: qualified managed manual time

Canonical sources now include the sixteen-file OS-only manual time service
qualified under `build/qualification/native-time-candidate-v1/`. Ordinary
console login starts root `timed` through PID1 notification readiness;
`timectl status` is public and `timectl set` requires effective UID zero from
Kernel peer credentials. Strict versioned framing, protected socket identity,
checked stale endpoint reclamation and one fixed 1000 ms monotonic budget cover
request fragments, dispatch and response. Activity never renews that budget.
The daemon counts its own successful setter syscalls, including committed
changes whose replies are lost; restart resets that local count and preserves
the active Kernel clock. It supplies no NTP, accuracy guarantee, hardware RTC
write or persisted epoch replay.

Fresh app compilation passes all twenty native architecture/mode tuples:
forty executable ELFs, 400 objects and 460 dependency tables. The separate
native probe compiles and links on all twenty tuples, producing twenty ELFs
and eighty objects. Independent app compiler/product readback checks exact source,
SDK and tool inputs. These are compilation results, distinct from actual guest
execution. Both full ordinary x86_64 Debug/Release SDK-only image builds pass.

Actual ordinary single-CPU x86_64 Debug and Release products each pass first
administrator enrollment, forward/backward and post-2038 clock steps, daemon
restart, logging and a clean HALT. The same disk then restarts without host
recovery, rejects a wrong password, authenticates, repeats clock/restart checks,
reads persisted logging and cleanly halts again. Separate dedicated fixtures
in both modes execute actual permanent native UID/GID 1000 drops: public STATUS
succeeds, SET returns EPERM and root regain fails. Malformed/concatenated frames,
fragmentation, disconnects and direct forward/backward wall-clock changes do
not renew the fixed monotonic request deadline. Probe ELFs are added only to
private fixture disks and are absent from ordinary products.

Four independent raw readbacks qualify six actual boots and six clean HALTs,
with exact linked CPU terminal observations, actual ext4 account/log bytes and
direct read-only fsck. Forty-eight strict reader negatives pass in ordinary and
optimized Python modes. Hosted actual-source ASan/UBSan fault controls remain
separate, including unavailable-realtime injection and post-commit reply loss.
Ordinary guests start with software realtime provisionally seeded from validated
ext4 last-write time; they do not qualify unavailable-realtime startup or trusted
UTC. Production ext4 still refuses metadata timestamps beyond 2147483647
seconds. Every post-2038 guest test restores 1700000000 before persistent logging
or HALT. No post-2038 filesystem mutation is claimed.

The deterministic `qualification-v1.json` binds retained raw evidence and
survives optimized-Python recomputation. Original guest log-reader failures,
the fixture image-lock/transport failure, initial independent reader assumptions
and their corrected successors remain separately retained. The reversible
`native-time-canonical-promotion-v1/` publishes only the reviewed sixteen files,
with six original-file inverses and ten additions. Independent after readback
passes. Fresh canonical x86_64 Debug installed-SDK-only full image construction
and twenty-five targeted time/packaging controls pass. This rebuild adds no new
guest campaign. The joined receipt is
`native-time-candidate-v1/canonical-rollout-completion-v1.json`; the current
workspace pointer is `build/qualification/native-time-current-handoff-v1.json`.

Kernel sources, all twenty installed ABI69/UAPI0.10 SDKs and existing canonical
account disks remain unchanged. Publication is reversible, not crash-atomic.
General service/account/session breadth, resolver/mount services, synchronized
reboot/poweroff and every complete M0-M12 milestone gate remain open. Physical
M11 and manual desktop M12 acceptance remain user-deferred.

## Previous continuation: qualified persistent native logging

Canonical sources now include the seventeen-file OS-only persistent logging
slice qualified under `build/qualification/native-logging-candidate-v4/`.
The Kernel and all twenty installed ABI69/UAPI0.10 SDKs retain the qualified
native console HALT rollout described below. This bounded logging slice does
not close M7 or any other complete milestone gate.

The frozen v2 logging products pass all twenty app/okcrt compile tuples and
full SDK-only x86_64 Debug/Release image construction. Corrected ordinary
guests each obtain thirteen contiguous persistent acknowledgements, then fail
on the first rotation: record fourteen exists on the stopped disk but its
acknowledgement misses the original one-second deadline. These are retained
failures, not successful logging, clean-shutdown or crash-recovery campaigns.
Earlier overlong single-argument and QEMU image-lock harness failures remain
separate. No failed attempt is relabelled as qualification.

An isolated timing diagnostic identifies approximately eleven seconds in the
first checkpoint data-allocation write. Preseeding its exact checkpoint in a
copied initial disk permits first-generation readiness within 205 ms. The v3
correction therefore stages that checkpoint and separates the fixed one-second
request-admission deadline from a fixed thirty-second persistence/reply phase.
Actual delayed-I/O controls and both full SDK-only image builds pass. The v3
Debug guest reaches first-generation readiness and twenty-six contiguous
acknowledgements, then returns `EAGAIN` at the second rotation. The Release
producer fails to parse a readiness event interleaved with the password prompt.
Both attempts remain failed; their causes and corrected successors are retained.
The v3 twenty-tuple compilation retains its original failed
finalizer (a host/target configuration-path error). A separate successor now
verifies all eighty successful commands, forty ELFs, 440 objects and 500
dependency tables; independent readback passes 8,186 checks without replaying
builds or synthesizing missing historical configurations. Those failed guest
attempts did not authorize source publication.

The retained stopped v3 disk contains a complete checksummed record 27;
maintained inode events span 32731 ms during that rotation. A private timing
observer completes the same request in approximately 29 seconds; it is timing
evidence, not reproduction of the original failure. Hosted controls separately
confirm that a client can also wrongly recheck the old one-second budget after
a successful send returns late through scheduling.

The frozen v4 successor changes four paths. It selects an explicit fixed
60000 ms persistence/reply policy and anchors client completion to the sample
immediately before the final successful send. Time spent returning from that
send consumes the same cap. Partial-send/server admission and logd/PID1
readiness policies remain 1000/2500/3000 ms. Three targeted hosted tests pass,
including actual-code ASan/UBSan and both real ext4 normalizers. Exact-boundary,
combined send/reply/EOF, rollback, overflow, 32731 ms rotation and late durable
no-ACK restart controls pass. Fresh twenty-tuple compilation now passes all
eighty commands, forty executable ELFs, 440 objects and 500 dependency tables;
independent readback verifies 8,184 entries. The first v4 compile harness
mistakenly selected nonexistent rv42 instead of rv32. That eighteen-row failure
remains retained; `cross-apps-v2/` freshly rebuilds the entire correct matrix.

Both ordinary single-CPU x86_64 Debug and Release logging campaigns now pass
first-administrator enrollment, thirty full-size acknowledgements, a logd
restart with a new PID/generation, six more acknowledgements and a clean HALT.
The second boot uses the same disk without host recovery, rejects a wrong
password, authenticates the administrator, reads the persisted log through the
ordinary shell, adds eight acknowledgements and cleanly halts again. All
forty-four contiguous acknowledgements per mode are bound to exact 256-byte
payloads. Fresh independent readers verify serial/input/product/source joins,
both stable QMP terminal observations per halt, checksummed two-file rotation,
root-only metadata and direct read-only fsck. Retention is 14..36 after the
first halt and 27..44 after the second. A prior independent-reader failure
assumed the client's printed HALT reply preceded the server's quiesce record;
the corrected reader enforces actual lifecycle causality and twelve strict
controls without rerunning or changing either guest campaign.

The joined `qualification-v2.json` pins 21,032 evidence files, including raw
serial, QMP, halted disk snapshots, dumps, command logs, tools, sources and SDK
artifacts. Explicit validation survives optimized Python execution and returns
the same deterministic result. The unexecuted predecessor qualifier/publisher
remain retained after review found insufficient evidence binding. The hardened
`native-logging-canonical-promotion-v5/` pins the exact qualifier, output and
full totals, and recomputes qualification before source mutation. Its exact
seventeen-file reversible publication and independent after readback pass;
seven original files are retained as inverses and ten files are additions.
Publication is reversible, not crash-atomic. Fresh canonical x86_64 Debug
installed-SDK-only full image construction and eleven targeted logging,
console-disk admission and console-profile tests pass. This canonical rebuild
does not constitute a new guest campaign. The joined rollout record is
`native-logging-candidate-v4/canonical-rollout-completion-v1.json`; the current
workspace pointer is `build/qualification/native-logging-current-handoff-v1.json`.

Logging remains bounded and root-only: two files of at most 8192 bytes, one
client, no volatile success queue and checked persistence before acknowledgement.
This policy change does not improve the slow synchronous storage path or
qualify crash recovery, physical durability, general sessions or a full desktop.

Kernel sources and installed
SDKs are unchanged by this logging work. Physical M11 and manual M12 acceptance
remain user-deferred.

## Previous continuation: native console HALT

The frozen successor under workspace
`build/qualification/native-power-candidate-v2/` now implements native scalar
PREPARE/COMMIT, public `ok/power.h` wrappers and `service-ctl halt`. The original
native PID1 leader must retain all six root IDs and its runtime incarnation.
PREPARE precedes graph mutation. Dependency retirement, adopted-child reaping
and fresh ECHILD precede checked console/control closure and exact-token COMMIT.
COMMIT success means queued only; the Kernel advances at the outer service
boundary, retires resources and asks the original OS storage owner to detach
and clean-seal its journalled root before the terminal action. Failed cleanup
remains terminal. Repeated requests retain their original deadline.

The bounded slice completion is `software-slice-completion-v1.json`; the current
workspace pointer is `build/qualification/native-power-current-handoff-v1.json`.

Actual ordinary x86_64 Debug and Release console products each pass two boots:
first-administrator enrollment, a persisted file, native PID1-requested HALT,
same-disk restart without host recovery, wrong-password rejection, post-failure
retry delay, successful authentication, persisted-file read and a second HALT.
Each halt has two stable QMP observations of the actual single CPU at CPL0 in
the linked `cli; hlt; jmp` loop with interrupts disabled. Direct clean/no-replay
superblock checks and read-only `e2fsck -fn` pass after both halts. Independent
readers verify linked instructions, serial causality, actual boot products,
final disk, password verifier and protected account/home metadata. The Release
observer uses a symbol companion relinked from the exact original objects;
its raw payload is independently byte-identical to the stripped product that
actually boots.

The retained v1 Debug guest failed PREPARE. GDB found a null service reference:
the freestanding entry did not run the coordinator's dynamic constructor. The
v2 fix makes its constructor `constexpr` and both static owners `constinit`.
Linked-image checks admit v2 and reject the failed predecessor. All twenty
architecture/mode adapter objects have no dynamic initialization section.
Final specialized integration compilation passes 20 archives/280 objects, and
wire-boundary compilation passes twenty rows. Actual dispatch/coordinator
ASan/UBSan controls pass. Standalone x86_64 Debug boot reaches 75 test points;
both modes export ABI69/UAPI0.10 SDKs and independently checked SDK-only OS
products. Initial reader assumptions about Release-only symbol visibility and
Debug-only source units remain retained as failed attempts with explicit
corrected successors.

These results qualify single-CPU x86_64 console HALT only. Other nine terminal
backends, reboot and poweroff explicitly refuse; active unqualified network
owners and configured GUI applications also refuse PREPARE. This slice does
not close M7, SMP or desktop shutdown. Both candidate source trees remain
frozen. The full matching SDK/ordinary-console OS cohort now passes all twenty
architecture/mode tuples, with standalone Debug QEMU checks on all ten
architectures. Its first v1 receipt finalizer expected `/sbin/init` while the
actual rootfs stages `/init`; that failure remains retained. `full-cohort-v2/`
reuses the exact successful commands and completes the remaining rows.
Independent readback verifies the compiler, dependency, SDK, staging, archive,
ELF and image joins, including the two pinned x86_64 rows.

The reviewed 142-file source delta is now promoted to the canonical Kernel/OS
trees. All twenty default SDKs are ABI69/UAPI0.10, and independent complete
byte/kind/mode readback also verifies every retained ABI68 inverse. Fresh
canonical x86_64 Debug standalone build/QEMU and installed-SDK-only OS build
pass; SDK admission regressions pass. Source and SDK publication have separate
reversible inverses and are not crash-atomic. The joined receipt is
`native-power-candidate-v2/canonical-rollout-completion-v1.json`; publication
records are `native-power-canonical-promotion-v1/` and
`native-power-sdk-install-v1/`.

Protected persistent `logd`/`logger` is now qualified and promoted; see
the current continuation above. All thirteen
complete milestone gates remain open; physical M11 and manual M12 acceptance
remain deferred.

## Previous continuation: native shutdown adapters

The frozen successor is retained under workspace
`build/qualification/native-shutdown-candidate-v1/`; the current handoff is
`build/qualification/native-shutdown-current-handoff-v1.json`. Its internal
adapter resolves the actual original native PID1 leader and all six root IDs,
rechecks that every child was reaped, and advances only after the complete
native step returns to the typed desktop boundary. It closes producer and
scheduler admission, stops known owners once, uses actual native retirement,
drains scheduler resources and checks VFS references before the original OS
storage owner detaches `/run` and root, clean-seals its journal and performs a
checked one-shot block reset. Failed cleanup remains terminal. The x86_64
terminal backend disables interrupts and permanently holds; reboot, poweroff
and the other nine terminal backends explicitly refuse before retirement.
Application windows and active unqualified network owners also refuse PREPARE.

The candidate uses development C++ ABI69 and unchanged native UAPI0.9.0.
Runtime ASan/UBSan controls pass five ownership scenarios; storage passes 22
sanitized scenarios and separate CPU-MMIO block/RNG controls pass. Independent
input joins retain the one later comment-only transport-header change and the
unused Debug-test-header difference without relabelling earlier evidence.
Final frozen ten-architecture Debug/Release compilation passes 20 archives and
280 ELF objects, including byte-for-byte archive-member readback. This is
specialized compilation, not twenty complete SDK exports or target execution.

The frozen standalone x86_64 Debug SDK export and QEMU checks pass with 74
reachable Debug points. The SDK-only OS consumer passes 83 SDK validation
tests, actual image linkage and an independent join of 340 SDK artifacts,
94 compilation commands, 120 dependency records, 24 staged applications and
37 exact OKAR entries. Final ELF archive symbols and bytes match. A separate
simplefs desktop boot smoke passes; its marker runner retires QEMU from the
host. None of these results demonstrates native user-space initiated clean
halt or same-disk restart/login without recovery.

Both source inventories and all evidence remain frozen. At this internal
adapter freeze, scalar native PREPARE/COMMIT and PID1 power policy were still
pending. Their later implementation, retained failed v1 and successful v2
Debug/Release console HALT evidence are described above. All thirteen complete
milestone gates remain open; physical M11 and manual M12 remain deferred.

## Previous continuation: isolated shutdown mechanism

The next software slice is retained under workspace
`build/qualification/shutdown-coordinator-candidate-v1/`. It is an isolated
candidate, with no canonical Kernel promotion or installed SDK replacement.
The candidate removes the desktop loop's direct enum-to-platform path and makes
legacy power requests explicitly unsupported. A fixed-storage, statically
dispatched coordinator binds the original runtime/PID1 identity and a one-shot
action ticket, queues COMMIT, requires an outer service boundary and orders
admission closure, producer retirement, native retirement, resource drain and
original-provider storage sealing. Any advancement failure is terminal and
suppresses power; callback reentry cannot repeat cleanup. Independent review
found and repaired ticket reuse across reconstruction at the same address by
binding tickets to the nonrepeating runtime incarnation.

The candidate VFS inventory method checks exact issued handles, paths,
provider/RAM kinds and covered-parent handles, rejecting missing, extra,
borrowed, foreign, stale and duplicate owners. It is a read-only snapshot, not a
barrier, drained-owner report or clean seal. The OS must still supply its
original journalled provider and private `/run` and root handles.

The coordinator passes 235 hosted checks in ordinary and ASan/UBSan builds.
The exact product desktop loop passes 24 hosted cases; its original bypass is
retained as a rejected negative control. VFS hosted models pass all ten selected
profiles and a sanitizer successor with leak detection disabled; the initial
ptrace/LeakSanitizer failure remains failed. These simple VFS runs did not retain
their temporary binaries or complete at-run dependency freezes and are not
standalone SDK evidence. Ten-architecture Debug/Release freestanding compilation
passes 120 objects, with a separate twenty-object successor for added reachable
mount-inventory debug coverage. Standalone x86_64 Debug boot passes before and
after that model successor. Original strict-warning compile and OS result-path
finalizer failures remain separate from successful later compilation/readback.
The SDK-only x86_64 Debug consumer passes 82 SDK validation tests, actual image
link/OKAR/BIOS byte readback and a simplefs `OK_SYSTEM_GUI boot=complete` smoke.
The existing marker runner retires QEMU from the host; it does not exercise
native clean shutdown. The final boundary-runner successor removes a redundant
source-text policy mirror; actual Kernel request refusals stay covered by the
reachable Debug test, and all compiled inputs remain unchanged.

At this earlier mechanism freeze, the native runtime adapter, UAPI, service-control shutdown command, actual native
VM/wait retirement, producer barrier, original-provider clean seal and platform
action are still unimplemented. The candidate has no production power consumer.
No native clean-disk halt/reboot/poweroff, SMP, physical or full milestone claim
follows from these models and compile checks. ABI68 defaults and the qualified
login product remain unchanged; M11 physical and M12 manual acceptance remain
deferred, and all thirteen complete milestone gates remain open.

## Current continuation: native console login

The selected local-account policy is implemented: interactive first boot creates
an administrator with UID/GID 0 and a password chosen then. The banner is
`ObfuscationOS`. Missing or malformed account state never reopens enrollment.
The protected store uses trusted entropy, PBKDF2-HMAC-SHA256 with 600,000 rounds,
exclusive staging, checked persistent sync, rename and parent sync. Authentication
precedes staged recovery; input remains hidden and failed attempts have a fixed
minimum retry delay. Hosted account/store/input/main controls remain separate
from native execution evidence.

All twenty architecture/mode Kernel SDKs and OS consumers pass original build
and independent readback. ABI68/UAPI0.9.0 SDKs are now installed; independent
post-install inspection passes all twenty defaults and retains the complete old
inverse roots. Actual x86_64 Debug and Release journalled login campaigns pass
five boots per mode, including ordinary enrollment/restart, staged interruption
and authenticated recovery, logout/relogin and no-entropy refusal without
credential mutation. Their explicit test wrappers and original observer failures
remain retained separately.

The opt-in `--native_console_login=y` profile now packages the ordinary native
PID1, unwrapped `/bin/login`, unwrapped `oksh` and a dedicated native service
manifest. Separate Debug and Release product guests pass two boots each through
`xmake qemu-distro --fs=ext4-journalled --interactive`; account bytes survive the
same-disk restart, wrong authentication is denied and logout creates a new
console generation. Independent build/input/serial/PBKDF2/disk readers pass.
A distinct login disk pathname and actual offline product/metadata admission
prevent reuse of an older maintenance root. One matching-image and eight
malformed/stale-image admission controls pass without changing the originals.
Journalled image publication refuses existing images or evidence sidecars.

All twenty targeted init/login positive build rows and original-object readers
pass. Their aggregate campaign deliberately retains its original failure:
five invalid configurations were refused through an unsupported top-level Lua
error function. A one-file successor moves those checks into the supported
option callback. Its five exact policy refusals and ordinary configuration pass;
an actual successor Debug init/login build has identical compiler/link commands
modulo the private source root. All 841 other source files and every compiled
input remain unchanged. The guard join records this composition explicitly;
it does not relabel the earlier aggregate failure.

Evidence is under workspace `build/qualification/persistent-sync-sdk-install-v1/`,
`native-login-guest-{debug,release}-v2/`, `native-login-guest-readback-v3/`,
`native-console-login-product-{debug,release}-v2/`,
`native-console-login-product-prep-v1/`, `native-console-login-product-cross-v1/`,
`native-console-login-guard-successor-v2/` and
`native-console-login-canonical-promotion-v1/`.

The maintenance profile remains the default until general journalled-root
qualification closes. This login freeze does not supply an isolated graphical
greeter, PTY/controlling-terminal sessions, general account administration or
synchronized shutdown. The later power candidate described above supplies
bounded x86_64 console HALT evidence and is now promoted with all twenty ABI69
SDKs installed, as recorded above.
Host QEMU retirement alone does not establish clean shutdown.
M11 physical-machine and M12 manual desktop acceptance remain deferred. All
thirteen complete milestone gates remain open.

## Current continuation: native service quiescence

Native PID1 now accepts public lifecycle STATE and root-only QUIESCE requests.
A fixed 18,000 ms deadline covers dependency-first TERM/KILL/reap and interrupted
wait/read/write calls. Duplicate requests keep the original deadline; launches
and restarts stop. Graph retirement is separate from child emptiness: a fresh
post-graph collection must report ECHILD before completion. Success keeps PID1
and control alive; deadline/wait failures enter fatal-hold and close control.

Fresh frozen-v2 x86_64 Debug and Release SDK-only guests pass nonroot public
state/denied mutation, actual root CLI quiesce, idempotent deadline and busy
restart. A live adopted observer blocks completion through twenty post-graph
observations; PID1 must reap its actual exit 37 before the sole quiesced record.
No relaunch occurs during the subsequent observation. Credential, control,
adoption and shell-list/pipeline regressions precede quiescence. Separate exact
source/SDK/ELF/serial readback and unchanged-disk read-only fsck both pass. The
original v1 guests also passed and remain retained; v2 improves initial-state
and prompt-race tolerance without weakening post-graph liveness or END framing.

Hosted controls pass nine UBSan C suites, four Python controls and enabled/disabled
native syntax checks (25 actual commands). The five implementation/fixture units
compile to 100 objects across ten profiles and both modes, with separate command,
object and original-dependency readback. That is compile-only evidence. Current
receipts are workspace `build/qualification/native-quiesce-host-v2/`,
`native-quiesce-os-compile-v1/`, `native-quiesce-guest-{debug,release}-v2/` and
`native-quiesce-guest-readback-v2/{debug,release}/`.

Quiescence does not sync filesystems, FLUSH devices, seal/detach mounts or invoke
platform power. It is one prerequisite for synchronized shutdown. The separate
`native-quiesce-probe-compile-v2/canonical-v2-coverage-join.json` binds unchanged
eighty production objects and twenty freshly compiled revised probes to the v2
guest freeze; original objects/dependency records remain unchanged. At this
quiescence freeze, accounts, authentication and TTY/session ownership were
pending; the later console login slice is described above. All thirteen complete
milestone gates remain open; M11 physical and M12 manual acceptance stay deferred.

## Current continuation: native credentials and service identities

The native UAPI now has eight real/effective/saved UID/GID operations, with
immutable-old-tuple permission checks and single-live-thread setter admission.
Version 2 service manifests carry explicit numeric UID/GID. The native fork
child closes supervisor descriptors, drops GID before UID, verifies all six IDs
and execs only on exact agreement. Version 1 remains implicit root; the sealed
Linux-musl manager rejects version 2 because it does not enforce that policy.
Native wrappers preserve high unsigned IDs even where their bit patterns
overlap syscall error values. Authentication, supplementary groups and terminal
sessions remain pending.

Hosted production ASan/UBSan covers the native runtime operations and Linux
credential regressions; wrapper and supervisor fault controls cover conversion,
failed setters and mismatched readback. Sixty Kernel implementation/test objects
compile on all ten architectures in Debug and Release. A separate sixty-object
native fixture matrix retains an original metadata-path finalizer failure;
independent dependency/product readback accepts the actual compiled objects.
These are compile and hosted checks, separate from guest execution.

Fresh frozen-v2 x86_64 Debug and Release SDK-only guests pass native service
identity, saved-ID restoration/reset, high IDs, permanent drop, denied regain,
fork/exec inheritance, failed exec and file permission denial. The same guests
retain control/adoption/shell lists and a later interactive pipeline. Separate
strict source/SDK/product/serial readbacks and read-only fsck pass. The original
Release guest remains failed because its first exec marker lacked LF and was
attached to the shell prompt; the corrected successor was built separately.
Host retirement after sync is not synchronized shutdown.

Evidence is under workspace `build/qualification/native-credentials-host-v1/`,
`native-credentials-linux-regression-v1/`, `native-service-identities-host-v1/`,
`native-credentials-sdk-contract-v1/`, `native-credentials-compile-v1/`,
`native-credentials-os-compile-v1/readback-v1/`,
`native-credentials-guest-{debug,release}-v2/` and
`native-credentials-guest-readback-v2/{debug,release}/`.
The complete twenty-row SDK/OS product join, default artifact replacement and
independent installed-tree readback now pass. All twenty displaced SDK roots
remain under `native-credentials-sdk-install-v1/retired/ARCH/MODE` with exact byte
and permission identities. Prepare, apply and independent readback each have
actual exit-zero receipts; installation remains reversible, not crash-atomic.
The strict validator requires the new capability; predecessor adoption SDKs do
not satisfy it. `native-credentials-sdk-install-v1/independent-qualification.json`
joins the v1 production cross consumers to v2 guests through an explicit two-file
test-only delta. All thirteen complete milestone
gates remain open. M11 physical and M12 manual acceptance remain user-deferred.

## Current continuation: native service control

Native PID1 now exposes a bounded `/run/init.sock` endpoint and the ordinary
`service-ctl status [SERVICE]` / `service-ctl restart SERVICE` application.
Status is public; restart requires server-side peer effective UID 0. The client
authenticates PID 1/root, validates complete replies and has a monotonic deadline.
The supervisor bounds clients, request/reply sizes and absolute deadlines, closes
control descriptors in service children, and contains transport failure without
abandoning service ownership. Accepted restart reports the old generation;
dependency retirement/reap and later readiness establish the replacement.
Control is enabled by default and can be disabled explicitly.

Fresh x86_64 Debug and Release SDK-only guests pass real UID/GID 1000 status and
denied mutation, root CLI restart, dependent-first retirement and distinct
generation 3 provider/dependent replacements. An incomplete client remains open
during child launches; their fd scans report no leaks. Malformed, fragmented
and disconnected clients are covered. A corrected fixed monotonic 1200 ms bound
observes EOF at 1015/1014 ms after activity at 607 ms, rejecting a sliding deadline.
The same guests retain graph/adoption, shell lists and later interactive shell
acceptance. Both retired disks pass read-only fsck. Native control source and
fixture units compile into 120 objects on ten profiles with Debug/Release flags;
this matrix is compile-only. Evidence is under workspace
`build/qualification/native-m7-control-{debug,release}-v2/`,
`native-m7-control-readback-v3/{debug,release}/` and
`native-init-control-cross-v1/readback/`.

The original v1 guests remain failed: their unknown-target test named a service
actually present in the fixture manifest. Its initial timeout assertion was
also too broad. The first control reader lacked the new pure import closure;
that preflight failure remains separate from the later successful disk checks.
No failure was changed into a pass. These guests are host-retired after shell
sync; they do not establish synchronized shutdown or power-loss durability.

The preceding twenty adoption SDK defaults and old directory inverses passed
independent post-install readback. Accounts/login and shutdown are the user's
software priority. The later credential increment is recorded above;
TTY/session ownership and an OS-callable Kernel power/flush contract still need
implementation. Existing in-kernel user
switching and QEMU exit do not satisfy those requirements. All complete M0-M12
gates remain open; M11 physical and M12 manual acceptance remain user-deferred.

## Current continuation: native shell command lists

The bounded native shell now accepts sequential `;` lists and equal-precedence,
left-associative `&&`/`||` lists. It parses the entire line before execution,
suppresses skipped-branch side effects and propagates parent builtin/exit state.
The existing concurrent pipeline launch barrier and ordered redirections remain.
Twenty-five hosted groups pass, including injected pipe/fork failures and large
streams. Fresh x86_64 Debug and Release SDK-only guests pass the expanded native
fixture and a later interactive pipeline alongside the existing service graph,
TERM/KILL and orphan-adoption gates. Strict readback requires the new list record
before final shell success; both retired disks pass read-only fsck. The shell and
fixture compile into forty objects on all ten profiles with Debug/Release flags.
A separate command/product reader accepts those original products after a
path-only finalizer failure; both successful xmake commands were preserved.
This remains
bounded shell execution, with no scripts/expansion/jobs/PTY or clean shutdown
claim. Evidence is `build/qualification/oksh-lists-host-v1/`,
`native-m7-shell-lists-{debug,release}-v1/` and
`native-m7-shell-lists-readback-v1/{debug,release}/`.

All twenty final adoption SDKs are now independently admitted and installed as
the default architecture/mode artifacts. The byte/permission plan and every old
SDK directory are retained under `native-adoption-sdk-install-v1/`; preparation
and installation both exited zero. The original cross campaign still records
its MIPS64 Debug standalone apps255 failure. That row's successful original
distro dependency products receive separate independent admission, alongside
the other seventeen ordinary rows and the existing x86_64 guest pair. Successful
builds were not replayed. Installation is not crash-atomic across directories.
The user's next software priority is system services, login and shutdown.
M11 physical and M12 manual acceptance remain user-deferred; all thirteen
complete milestone gates remain open.

## Current continuation: native termination, service graph and orphan adoption

The ordinary native software path now has positive-PID signal-zero probes,
deferred TERM/KILL, a bounded PID1 dependency graph and native/Linux descendant
adoption to designated PID1. Published native administrative termination also
uses checked adoption before its existing immediate reap. A confirmed mixed
native-parent/Linux-descendant lineage failure is repaired; unpublished fork
rollback and resource-free model cleanup are preserved.

Current-source hosted production ASan/UBSan passes 398 checks in Debug and
Release. The original lifecycle suite passes 1,459 checks for each of ten hosted
architecture selections; original admin regressions pass 303 in each mode.
These hosted backends do not execute user instructions.

Fresh x86_64 Debug and Release SDK-only guests pass native TERM/KILL/self-KILL,
oneshot/notify dependency startup, provider crash and dependent retirement,
generation replacement and independent ENOENT. Native PID1 adopts a live and
already-completed descendant, then reaps exit values 23/31. Both current
init/okcrt compositions also pass the shell's 12,289-byte four-stage stream,
ordered redirects, quoting, statuses/errors and twenty repeated pipelines.
Stricter independent readers validate marker causality and raw wait statuses;
both retired disks pass read-only fsck. These host-retired guests do not qualify
synchronized shutdown or power-loss durability.

The final source snapshot exports x86_64 Debug/Release ABI67 SDKs with exact
native termination and init-adoption-v2 capabilities. Its standalone Debug
kernel boot and strict compiler-matched consumer checks pass. The other eighteen
Kernel SDK and actual OS consumer products now have separate independent
admission, retaining the original MIPS64 Debug apps255 failure and its successful
original distro dependency build. All twenty defaults are installed with their
old directory inverses retained; see the newer shell/SDK continuation above.
The older termination-only frozen matrix has a separate source revision and
historical validator.

The [milestone status review](MILESTONE_STATUS.md) records all thirteen open
M0-M12 gates. Production ext4 remains `<1,9>` with pair I/O disabled. Complete
POSIX/musl, Internet networking, isolated graphics/apps, system daemons and
shutdown remain implementation work. Physical M11 and manual M12 remain
user-deferred. Accepted guest evidence is under workspace
`build/qualification/native-m7-adoption-{debug-v2,release-v1}/` and
`native-m7-adoption-independent-v1/{debug,release}/`; source/SDK evidence is in
`native-adoption-sdk-v3/`, and the remaining matrix is `native-adoption-cross-v1/`.
Initial observer and harness failures remain failed and retained.

## Current continuation: preserving ABI67 installation

ABI67 is installed with all twenty explicitly selected Kernel SDKs. The original
installer completed 55 source operations (40 modifications and 15 additions)
and preserves the previous SDK64 roots, source inverses and original failures.
A distinct read-only inspection accepts the installed source/SDK contents,
transition bookkeeping and recovery inverses. Its new callback controls pass
one positive and 52 negative cases. The original inspector failure is retained:
the final callback saves its completion flag as false before returning, then
marks it true in the result. The successor accepts only that exact authenticated
terminal snapshot difference; all other ledger fields and gates remain strict.

This installation carries the accepted bounded boot-CPU entropy and futex
REQUEUE composition. It does not enable the ext4 pair or archive-permission
campaign. The archive wrapper's original external exit remains unknown. The
production ext4 owner remains `<1,9>`; the earlier twenty-row `<4,9>` slice is
compile-only evidence.

P02's original four hosted model groups pass xmake with assertions and
ASan/UBSan. P01's ten-architecture native context source and the ten boot-stack
alias sources are accepted at source scope. Native compilation, actual mapped
ranges and guards, guarded owner lifetime and the complete linked stack graph
remain required before pair I/O. The original i386 Debug SP preparation failed
before compilation because the addon read configuration during xmake option
discovery. That original failure and the unexecuted Release staging are retained;
a new source successor binds the four selected row literals explicitly. Source
freezing also encountered 40 pre-install canonical file owners; the new
preparation must bind their exact installer-completed replacements and preserve
the original failed finalizer and partial outputs.

All ten Kernel architectures, twenty Debug/Release rows and four supplied musl
profiles remain explicit. Networking/services and isolated default English
Notes/Files remain subsequent implementation work. Full M0-M12 is incomplete;
physical M11 and manual M12 remain user-deferred. Exact acceptance and the
separate preserving publication are recorded in
`build/prototypes/sdk67-installed-inspection-and-stack-continuation-v44/ROOT_CONTINUATION_V44.json`.


## Current continuation: accepted ext4 pair compile matrix

The allocated two-block ext4 slice now passes the private freestanding xmake
matrix on all ten Kernel architectures in Debug and Release: twenty original
configure/build rows. An independent join verifies all forty original command
exits, the exact object/archive bytes, ELF architecture identities, explicit
object/stack-sidecar associations and the Five/Nine preparation wrappers. The
original producer and independent reader both have externally observed exit0.
The reader's initial 16 MiB size-limit failure is retained; its fresh successor
uses a fixed 256 MiB bound only for the exact original object/archive paths.
No compiler or successful producer was replayed.

This is compile-only evidence for the bounded two-block slice and selective
preparation wrappers. The production OS owner is still `<1,9>`; complete linked
service/IRQ/helper/driver stack bounds, SDK integration and actual pair-write
guests remain pending. The initial synthetic stack analyzer failed independent
source review because switching back into a domain with parked live frames can
overwrite those frames. A fresh ownership-check repair is in progress. No
production stack safety, data atomicity or physical durability is claimed.

ABI64 remains the installed canonical baseline; its publication and retained
inverse are independently accepted. The eight original ABI67 entropy/REQUEUE
guest rows and their readers remain independently accepted within their bounded
UP test-image scope. Their observed counts are six cross-key moves, five wakes
and seven reaped children. The original partial LoongArch Debug fixture producer
remains partial, and canonical ABI67 integration is still pending.

The archive permission campaign reports all eight guest rows and all sixteen
phase exits zero. Its narrow integer source repair is independently accepted,
but runtime acceptance remains pending because the original Root wrapper exit
was omitted from a truncated tool result. That exit remains unknown. A separate
stopped-subject design is being reviewed; the existing strict-exit reader gate
is unchanged and no original guest is replayed.

The next implementation work is preserving ABI66/67 composition, conditional
pair integration after stack qualification, explicit twenty-row Kernel SDK
production and SDK-only OS consumption, followed by actual pair-write guests.
Networking/services and isolated default English Notes/Files remain subsequent
work. Full M0-M12 stays active and incomplete; physical M11 and manual M12 remain
user-deferred. Exact new evidence is recorded in
`build/prototypes/sdk64-sdk67-storage-and-runtime-continuation-v35/ROOT_CONTINUATION_V35.json`.

## Current continuation: installed mounted-root runtime and preserving ABI64 composition

The preserving ABI64 successor is installed: Kernel1,529 / OS750, Linux UAPI
0.7.0, and all twenty explicit architecture/mode default SDKs. The installation
applies 83 additions and 95 modifications, with no removals. It retains complete
old source, all twenty retired SDK59 originals, dirty Git HEAD/index bytes,
original build forests outside the explicit SDK replacements, both original
disk owners and the V85 public progress inverse. Forty-seven directory mode
exceptions preserve original owner directory permissions. Each completed
source/SDK transition has identity-bound bookkeeping. The installation and
this separate progress publication are not crash-atomic or power-loss safe.

Mounted-root runtime file routing is integrated with the preserving source
composition. The canonical boot-CPU shared-file provider, descriptor passing,
bounded pathname IPC and prepared TCP accept implementations remain bounded
mechanisms. Distribution builds consume explicitly selected architecture/mode
Kernel SDK artifacts. They do not compile a nested Kernel checkout. All ten
Kernel profiles, both modes and the four supplied OS/static-musl profiles
(x86_64, aarch64, rv64 and loongarch64) remain explicit.

The independent native join authenticates all twenty SDK/OS rows and their
source ownership. Nineteen rows produced the missing official SDK exports and
OS links. x86_64 Debug retains its successful SDK/Kernel proof and binds the
separate current OS-only link; that Kernel producer and boot were not replayed.
Debug standalone Kernel proofs, hosted models, SDK-only OS builds and actual
user execution remain separate evidence. Complete original compiler subprocess
hashes, full linker closure and equivalence of unmeasured parent compilation
closure remain unclaimed.

The admitted regression continuity join preserves twenty paired shared-file
guest rows, forty native files, forty native rights, forty static-musl files
and forty static-musl rights runs, bounded client TCP in two modes, eight
English Notes/GUI rows with 152 actions and four privileged Debug handoffs,
and three native plus three static-musl accept connections. It binds explicitly
named ancestor evidence and affected current-source observations separately.
Inherited source fields and limitations remain visible; receipt validation
does not turn ancestor execution into a new current-image run. Successful
producers, guests and earlier controls were preserved rather than replayed.

Actual mounted-root Files/runtime readback retains thirty bootstrap-root
actions, including its successful two-action prefix, nineteen new healthy
actions and nine new cold actions. A separate current runtime `notes` save
workflow executes twelve new actions in two retired guests: nine healthy and
three cold, including two saves. Native inode observations are 49 for the first
save, 50 for replacement and 50 after cold reopen, with sizes26/32/32 and
mode0600. Raw responses, linked confirmation/state oracles, retired process
trees and the exact healthy/cold media digest lineage are independently bound.
This establishes the observed save/replacement/reopen behavior on the retained
test media; it establishes neither power-loss durability nor clean shutdown.

Those mounted-root utilities and runtime Notes commands are bootstrap-root
workflows. They do not execute a native Files GUI process, unprivileged GUI
apps or an isolated desktop. The inherited default Files-to-Notes graphical
workflow remains prelinked and privileged; hosted handoff/provider tests are
models. Historical Notes8 GUI evidence and the separate actual mounted-root
save evidence retain their own scopes. No model result, metadata admission or
kernel bootstrap workflow is promoted to desktop isolation or hardware proof.

Independent installer review and retained one-shot private controls bind the
exact ABI64 admission, stage, inverses and mutation/bookkeeping adapters.
Identity reconciliation covers ordinary SIGINT and post-success BaseException
between namespace transition and completion bookkeeping; ambiguous ownership
stops recovery. Four missing historical preflight status artifacts remain
explicitly absent. Fresh current status is checked against available V85
anchors; missing historical bytes are not synthesized.

Full M0-M12 remains incomplete and active. Complete POSIX/musl semantics,
ordinary VFS page-cache coherence, broader ext4/durability, blocking Internet
networking, IPv6, service lifecycle, accounts/login, display/input ownership,
isolated compositor/apps, SMP, runtime modules and shutdown acceptance remain
work. Physical M11 and manual M12 remain user-deferred. The exact completed
ABI64 installation, its independent gates and this distinct progress exception
are recorded in the newly owned
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V86_V6.json`.


## Current continuation: installed volatile shared files and Linux seek

The preserving ABI59 source successor is installed: Kernel1,452 / OS744 and
all twenty explicit architecture/mode default SDKs. The installation applies
17 additions and 28 modifications, with no removals. It preserves the complete
old source, owner directory modes, Git indexes/status and SDK copies/originals.
Each completed source/SDK operation has recovery bookkeeping. Publication is
not crash-atomic or power-loss safe. V84 was retained during source publication;
this separate progress update records the resulting installation.

The serialized boot-CPU shared-file provider owns eager physical pages and
distinct mapping references, with allocator generations checked during alias
retirement. Native and Linux routes expose the bounded volatile sealed-size
profile: at most 16 files, 64 pages per file and 4 KiB pages. Descriptor passing,
fork and loaded-image retirement preserve backing ownership. Linux seek and
stat now select shared descriptions directly; directory metadata queries are
restricted to VFS-backed descriptions. This is not a durable file/page cache
or an unrestricted shared-memory/POSIX implementation.

All twenty standalone SDK exports and SDK-only OS consumers pass, alongside ten
standalone Debug Kernel boots. The selected measurements include 157 fresh and
43 reused production objects, and nine fresh and one reused Debug objects.
Actual graph output totals are 546 fresh Kernel units and 1,730 OS outputs.
Twenty paired guests execute forty native files, forty native rights, forty
static-musl files and forty static-musl rights runs. Raw serial binds matching
image/probe owners, stable physical accounting and five final zero shared-file
owner fields. Disposable ext4 disks pass offline filesystem checks. Successful
partial compiles/links were retained and narrow retries ran only missing work.

Independent joined admission reads 3,090 original compile records, 2,313
available raw dependency records, 3,163 owned command records and 110 retained
ancestry capsules. It admits measured and available dependency closure;
complete raw compiler coverage, first-row unmeasured OS graph closure and
original unmeasured parent Kernel closure equivalence remain unclaimed.
Original compiler subprocess hashes and complete linker closure also remain
unclaimed. Independent installer review binds the exact stage, inverses and
114 retained plus eleven new strict-status refusal/recovery controls.

The four supplied musl platforms each pass Debug and Release English Notes
workflows: eight actual guests and 152 actions. All eight have GUI boot markers;
four Debug rows pass privileged GUI handoffs. Actual x86_64 Debug and Release
client TCP regressions pass user syscalls, Virtio/slirp packets and owned host
connections. Both modes reuse the successful Debug user probe. Notes still
uses simplefs RAM and the GUI is prelinked and privileged. These tests establish
neither a durable/isolated desktop nor clean shutdown or complete Internet TCP.

The separate private TCP accept composition is Kernel1,466 / OS744. Its ABI60
declaration V12 passes 118 official Python test methods and independent source
review. Its first actual x86_64 Debug SDK producer and separate consumer pass,
with a standalone Kernel boot, 50 changed Kernel object compiles, 18 retained
objects and 87 fresh OS outputs. Remaining target rows, actual native/static-musl
accept guests and current-image regressions remain pending. ABI60 is not the
installed/default SDK and declaration parsing is not execution evidence.

Pathname IPC, display/input ownership, isolated compositor/apps, blocking TCP,
IPv6, multiple services, accounts/login, complete POSIX/musl and ext4 breadth,
SMP and runtime modules remain work. All ten native profiles, twenty mode rows
and four supplied musl profiles remain preserved. Physical M11 and manual M12
remain user-deferred. Full M0-M12 remains incomplete and active. Exact adoption
and the separate progress exception are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V85.json`.


## Current continuation: installed UNIX descriptor passing

The preserving ABI58 source01 successor is installed: Kernel1,441 / OS738 and
all twenty explicit architecture/mode default SDKs. The installation applies
thirteen additions and twenty-six modifications, with no removals. V83 progress
was preserved during source publication. Complete old source, Git index/status
bytes, old SDK copies and retired SDK originals remain retained. Each completed
source/SDK operation has recovery bookkeeping; publication is not crash-atomic
or power-loss safe.

UNIX socketpair descriptor passing now uses canonical open-file-description
queue holds and move-only receive transactions with reserved descriptor slots.
It preserves shared file offsets, close-on-exec, peek and truncation behavior,
cleans up ordinary reads and discarded messages, and collects queued cycles.
Process lifetime barriers prevent an outstanding transaction from borrowing a
replaced or compacted resource table.

All twenty standalone SDK exports and SDK-only OS consumers pass. Qualification
measures 200 production objects and ten separate Debug objects, and executes ten
standalone Debug Kernel boots. Twenty architecture/mode rights guests execute
forty native and forty static-musl runs, including file reopen, shared offsets,
CLOEXEC, peek, truncation, copy faults, ordinary-read cleanup and cycles. Disposable
ext4 disks pass offline filesystem checks. Five Notes guests execute 95 English
editor actions; actual bounded native TCP and privileged GUI regressions pass.

Independent joined readback passes 85,964 checks over 28,572 selected inputs and
63 captured components. It checks all 4,866 raw compilation dependency records
in 82 groups; only 854 missing preprocessing commands were executed. Original
compiler subprocess hashes and complete linker closure remain unclaimed. The
original TCP socket refusal and its successful reuse of the compiled fixture,
earlier failed recipes and the rollback ancestry defect reproduction are retained.
The corrected V3 adoption recipe checks destination directory ancestry before
SDK recovery and preserves unrelated recovery after a refusal.

Notes still uses simplefs RAM in these guests; rights ext4 is non-journalled.
These receipts do not establish a durable or isolated desktop. Shared-file
mapping and loaded-image retirement are implemented privately with hosted
qualification continuing. Prepared server TCP accept is a separate private
implementation. Pathname IPC, display/input ownership, isolated compositor/apps,
blocking TCP, IPv6, multiple services, accounts/login, complete POSIX/musl and
ext4 breadth, SMP and runtime modules remain work. All ten native profiles,
twenty mode rows and four supplied musl profiles remain preserved. Physical M11
and manual M12 remain user-deferred. Full M0-M12 remains incomplete and active.
Exact installation and the new progress exception are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V84.json`.

## Earlier continuation: installed native TCP and UNIX socketpair composition

The preserving Kernel1,432 / OS734 source04 successor and all twenty explicit
architecture/mode ABI57 SDKs are installed. The installation applies 43 source
additions and 34 modifications, with no removals. Complete old named source,
Git index/status bytes, old SDK copies and retired SDK originals are retained.
Source and SDK operations are individually recoverable; the installation is
not one crash-atomic transaction. Default Files-to-Notes editing is preserved.

The production qualification executes source03. Source04 changes only one
hosted UDP decoder test. Independent full dependency readback admits equal
project source/header bytes and modes for all 4,876 selected compiler commands
in 82 groups, with frozen generated inputs retained. This does not claim a
source04 rebuild, guest execution, original compiler subprocess hashes or
complete linker closure. All twenty standalone SDK exports and SDK-only OS
consumers pass, with 160 measured production objects, ten separate Debug test
objects and ten actual standalone Debug boots.

Actual static-musl UNIX socketpair runs pass twice in each architecture/mode
guest: forty runs across all twenty rows, with offline filesystem checks.
Bounded native x86_64 Debug TCP passes actual user syscalls, Virtio/slirp packets
and an owned host TCP connection. The privileged GUI handoff also passes.
Five native Notes guests execute 95 English editor actions. Notes uses the
simplefs RAM workflow; UNIX ext4 logs retain `journal=none`. These results do
not establish a durable or isolated graphical application environment.

The independent joined admission and root readback bind source review,
compilation, dependency equivalence and actual execution separately. Earlier
failed recipes, compiler-closure refusal, superseded stages and original defects
remain frozen. The V5 lexical object-path guard defect is fixed by the V6
canonical regular owner/build check before publication.

UNIX descriptor passing is being implemented privately with canonical OFD
queue holds, move-only receive reservations, cancellation, truncation, peek,
ordinary-read cleanup and cycle collection. It is not installed or qualified.
File-backed shared mappings, pathname IPC, display/input ownership, isolated
Wayland compositor/apps, blocking and server TCP, IPv6, multi-service lifecycle,
accounts/login, complete POSIX/musl and ext4 breadth, SMP and runtime modules
remain work. All ten native profiles, twenty mode rows and four supplied musl
profiles are preserved. Physical M11 and manual M12 remain user-deferred.
Full M0-M12 remains incomplete and active. Exact publication and the new
progress exception are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V83.json`.

## Earlier continuation: installed Files to Notes editing and preserving TCP join

The exact OS728 Files-to-Notes successor is installed: five additions and five
modifications, no removals. Complete live source readback preserves Kernel1,395,
all twenty default ABI55 SDK forests, Git indexes, toolchains and original
generated builds. Every replacement has a retained inverse. The installer is
per-file atomic, not a crash-atomic multi-file installation.

Default privileged Files now opens a captured ordinary private file in Notes;
Notes can edit, stage-save to that selected pathname, close and reopen it.
Rendered rows capture directory-relative identities. Bounded reads require
exact EOF, supported printable ASCII/LF/TAB, stable metadata and successful
descriptor closes before publishing text. Dirty or uncertain text refuses
replacement. Repeat saves refresh the published inode. Same-user namespace
checks are advisory; this remains prelinked privileged GUI, not isolated apps.

The author policy passes 7,629 hosted and ASan/UBSan checks each. The root's
separate provider models pass 45 scenarios and 1,737 checks in each lane.
One actual source07 x86_64 Debug GUI diagnostic exercises open/edit, dirty
refusal, save/reopen/repeat save, binary and stale-row refusal, and render
rollback. The complete root candidate builds twenty distribution images and
forty changed production objects with explicit validated SDK-only consumption.
Those twenty rows are compilation evidence; they are not twenty GUI executions.
Independent candidate/matrix readback passes 1,171 checks. Final installer
controls pass 28 actual private filesystem failure/recovery checks, including
both new and existing files when cleanup fails after a successful replacement.
The original replacement-bookkeeping defect and quoted-log reader failure stay
preserved. No test establishes clean shutdown or device-cache power-loss safety.

Private ABI56 source05 native TCP is independently reviewed and root-admitted.
Actual x86_64 Debug user syscalls, Virtio/slirp packets and owned host TCP sockets
exercise handshake, English payload, half-closes, partial reads/EOF, dup/fork/
final close, TIME_WAIT port reservation and closed-port refusal. The real guest
exposed a TIME_WAIT RST bug; source05 preserves unread bytes and the deadline.
Independent repaired transport models pass 84 cases and 3,332 hosted/sanitized
checks each, with the old defect reproduced separately. Root raw guest/socket/
packet readback passes 2,982 checks and ten hostile packet-parser controls.
Those synthetic refusals are parser controls, not extra hardware executions.

TCP historical source forests are partial and must never replace current trees.
The preserving reconstruction verifies seven exact source stages and six root
admissions: Kernel34 additions/17 modifications and OS3 additions/4 modifications.
It excludes historical modes, unrelated byte regressions and missing context.
Only reviewed members are composed onto complete Kernel1,395 and OS728: the
private joined source is Kernel1,429/OS731. Its preparation passes 1,645 checks;
the GUI clean three-way merge preserves the handoff, and xmake retains PID1 and
connected fixtures while appending the TCP fixture include. Fresh official
Kernel SDK exports, standalone Debug boots and SDK-only consumers are running
across all twenty profiles. Joined TCP/GUI execution, qualification and promotion
remain pending. Default SDK55 is unchanged.

The independently qualified historical AF_UNIX socketpair branch is being
rebased by explicit deltas into a separate private current-source successor;
its old musl guests do not execute the new source. Pathname sockets, descriptor
passing, isolated compositor/display/input, full POSIX/musl and ext4 breadth,
service signals/adoption/shutdown, accounts/login, SMP and runtime modules remain
work. All ten native architectures, twenty mode rows and four supplied musl
profiles remain preserved. Physical M11 and manual M12 stay user-deferred.
Full M0-M12 remains incomplete and active. Exact selections and the deliberate
new progress exception are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V82.json`.

## Earlier continuation: installed Notes/Files/PID1 and checked sparse rootfs packaging

The preserving OS723 successor is installed. All 33 explicit OS paths (16
additions and 17 modifications) passed independent source/inverse and installer
review, complete native/hosted qualification and immediate live drift checks.
Kernel1,395 source files, all twenty default ABI55 SDKs, original generated
builds, toolchains and Git indexes remain preserved. Per-file replacements have
recoverable inverses; this is not a crash-atomic 33-file installation transaction.
The earlier V1 installer rollback-parent exception is retained; V2 catches each
rollback-path refusal independently and continues recovery of earlier members.

Default privileged Notes uses staged saves with explicit publication uncertainty;
Files supports checked create/folder/rename/confirmed removal. Both leaves have
independent and root admissions. Native production PID1 reads its bounded console
configuration, keeps one managed shell alive, reaps its exact child and applies
bounded restarts. It still lacks multiple services, native signal management,
orphan adoption, accounts/login and clean shutdown. Its earlier 35-guest leaf
campaign remains separate from the new composed qualification.

The composed OS passes all ten architectures in Debug and Release: twenty actual
ordinary-init guests, 280 application action windows and 380 lifecycle records.
Every row executes Notes saves/reads across three managed shell generations,
pipelines, pwd, sync and two exact ENOENT launches on a disposable guest disk.
Each row consumes and validates an explicit ABI55 SDK without adjacent Kernel
source. Guests are retired by host SIGKILL after sync; this is not clean shutdown,
cold recovery, physical hardware or device-cache power-loss durability.

The i386 packaging defect is repaired: regular-file sparse holes reconstruct as
zero bytes through exact EOF; directories remain dense. The independent reader
checks malformed extents and initialized 32768-block encoding. Frozen i386 replay,
fresh packaging and real ext4/fsck controls pass. Five planning-model tests now
use an exact retained JSON fixture instead of requiring an adjacent Kernel tree;
this metadata is not a Kernel checkout or native ABI execution evidence.

The repaired complete tool suite passes 862 tests with no skips. Separate native
init/service models pass 3/5 programs; Notes/Files ASan/UBSan runs pass 1,646/1,882
controls. One actual composed x86_64 Debug privileged GUI diagnostic also passes.
These GUI paths are prelinked desktop policy, not isolated user applications.
Original packaging failures, five standalone model errors and reader/recipe
failures remain preserved and are not relabelled as successful qualifications.

The private immediate TCP source02 is independently reviewed and root-admitted.
Its 70 independent scenarios pass 3,594 hosted and sanitized checks each; twenty
production rows compile 80 actual ELF objects. Root readback passes 729 checks and
also binds 101 reviewed private ABI56 producer/archive/consumer contract tests.
Original OFD authority survives callback boundaries without accepting descriptor
reinstallation. Its private ABI56 source02 migrates one preserved process test
to actual canonical OFD inheritance. Independent root readback passes 1,441
checks and binds its standalone x86_64 Debug boot and 101 contract controls;
that boot retains model labels and is not native TCP execution. Private ABI56
standalone export and actual native NIC execution
continue separately; default ABI55 remains installed. Blocking/musl TCP, IPv6,
SIGPIPE execution, IRQ, SMP and complete Internet-host support remain open.

Files-to-Notes checked same-file editing is implemented in a private successor
under qualification, with independent review and adoption still pending. Its
interface preserves dirty text and captured directory/inode identity;
isolated display/input/compositor, POSIX/musl breadth, ext4 breadth, SMP and
runtime modules remain work. All ten native architectures, twenty mode rows and
four supplied musl profiles remain preserved. Physical M11 and manual M12 remain
user-deferred. Full M0-M12 is incomplete and the active goal continues.
Exact admissions and preserving installation receipts are in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V81.json`.

## Earlier continuation: default Files actions, staged Notes saves and persistent native PID1

The private default Notes source03 save leaf is independently reviewed and
root-admitted. Its unchanged source02 helper/dependency lineage passes 1,646
hosted and ASan/UBSan controls each and twenty SDK-header-only C++23 objects.
Actual source03 SDK-only QEMU GUI diagnostics execute the foreign-owner load
preservation and save-blocking control. Rename errors can follow namespace
publication: explicit uncertainty preserves dirty state and avoids destructive
cleanup. The original source01 defect and both GUI harness refusals remain.
This is privileged prelinked desktop policy, not isolated user applications,
musl execution, durable home policy or power-loss durability. Root admission
passes 152 checks; its first reader return-value failure remains preserved.

A private successor implements default Files prompts for empty files, private
folders, same-folder rename and confirmed file/empty-folder removal. Final
source02 captures the selected directory and inode before the prompt and checks
both before mutation; changed paths, stale selection and existing destinations
are refused. Publication-before-error is reported as uncertain. The exact
source02 passes 1,882 hosted and sanitized controls each, twenty SDK-only objects
and one actual SDK-only privileged GUI diagnostic. Source01 and its separate
successful GUI run remain superseded evidence. Files independent review and
preserving live composition are pending. External same-user rename prechecks
remain advisory; this is not an atomic rename-noreplace or isolated desktop claim.

The private native production PID1 source03 campaign completes twenty production
Debug/Release rows, ten explicit Debug acceptance rows and five configuration
control guests. All ten architectures execute three managed usable shells and
two exact ENOENT exec failures per main row. Configuration controls execute
malformed/unsupported/unsafe refusal and a missing-config default console.
Producer readback binds 35 actual guests, 151 launches, 91 usable shells, sixty
ENOENT failures, 577 lifecycle records and 391 raw response windows. Ten hosted
model programs and fifteen negative plus three positive observer controls remain
separate. The preserving handoff contains seventeen OS paths (seven additions,
ten modifications), with no live mutation. Independent review and composition
remain pending. Native multiple services, signals, orphan adoption and shutdown
are not implemented by this single-service persistent console supervisor.

The exact private TCP streams source04 is independently reviewed and root-admitted.
Canonical shared OFDs now own TCP edges; actual SchedulerState callbacks handle
close/exec/exit and real WaitTickets retain check/register/recheck ownership.
Copied reads preserve bytes on failed output; original fd closure cancels the
coordinator without rewriting an already delivered scheduler completion. FIN,
retry, prepared packets and TIME_WAIT prevent premature service replacement.
Author hosted/sanitized runs each pass 1,342 stream controls plus 19,514 transport
and 4,282 endpoint controls; separate independent runs each pass 1,221 controls.
Twenty architecture/mode rows compile forty freestanding objects. Root readback
passes 278 checks; the first capsule-shape reader failure remains preserved.
Actual trap capture, runtime clock/ISS and one joined UDP/TCP Ethernet pump are
under implementation in a successor. Native TCP, musl TCP, IPv6 and general
Internet support remain unqualified. Changed exported layouts require a future
coordinated SDK ABI before export or OS consumption; no TCP SDK was promoted.

Live source remains Kernel1,395 / OS707 with all twenty validated default ABI55
SDKs. All ten native architectures, twenty mode rows and four supplied musl
profiles remain preserved. The captured V78 progress in private leaves remains
an explicit baseline exception; it is not relabelled as current progress.
Exact admissions and pending selections are in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V80.json`.
Continue independent reviews, preserving OS composition, real TCP execution,
Files-to-Notes handoff, isolated display/input/compositor and remaining storage,
POSIX, SMP and module work. Physical M11 and manual M12 remain user-deferred.
Full M0-M12 is incomplete and the active goal continues.

## Earlier continuation: ABI55 SDK publication and ordinary native workflows

All twenty adopted-source standalone Kernel/export and explicit SDK-only OS
consumer rows pass across ten architectures and Debug/Release. Ten Debug rows
also execute standalone Kernel QEMU diagnostics; Release producer rows qualify
compilation and consumption only. The preserved first attempts failed on a
678-versus-707 harness source-count error. They do not become code-load failures.
The standalone script-generated UDP/TCP marker is not native networking evidence.

The separate ordinary OS campaign passes all twenty architecture/mode rows:
forty actual native user-space guest starts, 490 application commands and forty
read-only e2fsck checks. Debug executes `/init` acceptance and Release explicitly
runs `posix-check`. Default CLI Notes creates, saves, reopens and updates an English
document; Files moves files/directories, refuses hardlink replacement and removes
obsolete paths. Each row syncs a supported non-journalled ext4 disk, then a separate
cold start reads the final document from that exact healthy disk. Independent raw
ext4 readback checks content, directories, extents, link counts and path absence.
These are native okcrt CLI workflows, not musl or isolated desktop execution.
Guests are retired by host SIGKILL after application sync; this does not qualify
guest shutdown, crash recovery or device-cache power-loss durability.

Independent native and ordinary reviews bind the complete execution forests,
source, toolchains, SDKs, original ordered compiler inputs and retired process
groups. The ordinary review includes seventeen meaningful refusal controls.
The coordinated SDK stage and installer V2 received separate independent review
and root admission. Root now installed and validated all twenty default live ABI55
SDKs. Complete staged inverses and all old SDK originals remain preserved; source,
toolchains, the Git index and existing OS builds were unchanged by publication.
The previously installed source remains Kernel1,395 / OS707 files, with its
1,492-path preserving integration and 813 recoverable inverse files retained.

The private bounded TCP connection core and source02 endpoint/copied executor
are root-admitted. Transport author hosted and sanitized runs each pass 19,514
checks, with 176 independent checks each; endpoint runs each pass 4,282, with 480
independent lifecycle checks each. Both retain all twenty freestanding object
rows. Independent review found a legal-capacity 65,600-byte drainage stack frame;
source02 moves that scratch into the owner, with a measured 24-byte settle frame
and 96-byte release caller on the recorded hosted compiler. Original defects and
failures remain preserved. Root endpoint readback passes 247 checks. These leaves
remain private: canonical TCP descriptors/waiters, native NIC execution, musl TCP,
IPv6 and congestion/reassembly/persist mechanisms still need integration.

Exact records are in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V79.json`.
Continue canonical stream descriptors and copied NIC integration, managed ordinary
PID 1/services, storage breadth and isolated default Notes/Files. All ten native
profiles, twenty modes and four supplied musl profiles remain in scope. Physical
M11 and manual M12 remain user-deferred. Full M0-M12 is incomplete and active.

## Earlier continuation: live ABI55 source adoption and fresh native qualification

The top-level Kernel and OS repositories now contain the preserving cumulative
ABI55 source integration. Root installed exactly 1,492 reconciled named paths
after checking the complete staged package, current live bytes, Git bases/status
and 813 recoverable inverse files. The installed source manifest contains
Kernel1,395 and OS707 files. Existing tools, source inventories, four deleted
legacy desktop documents and current V77 progress were preserved. The Git index,
ignored generated builds and toolchains were not changed by source installation.
The standalone x86_64 Debug Kernel SDK export and explicit SDK-only OS image
build pass, along with the complete 848-case OS tool suite and 15 sanitized Notes
save-boundary controls. Initial merge, fixture and reviewer failures remain.

This is a source upgrade from the live ABI20 baseline. The earlier private
Kernel1159/OS632 checkpoint remains historical. Live generated SDK artifacts
were not overwritten or promoted. A fresh immutable snapshot of the actual
installed source is now running all ten Debug/Release standalone Kernel/export/
SDK-only OS build rows. Debug rows additionally run the standalone Kernel QEMU
script. These new rows remain pending; earlier private matrix or NIC executions
are not relabelled as execution of the newly installed source. Separate ordinary
OS user-space boot verification and coordinated artifact promotion follow.

The nine additional native startup refusal cases are independently reviewed and
root-admitted: six mount before/after first software-FLUSH errors and three
unsupported revoke-plus-checksum-v3 empty profiles. Every raw disk byte remains
unchanged, no WRITE occurs, root is unpublished and epoch stays zero. The exact
selection is source12/runner V13 and the unchanged native image; the independent
review adds twelve meaningful refusals without new QEMU or cold consumption.

The additive private TCP IPv4 codec source is also root-admitted after independent
review and a fresh ASan/UBSan oracle: 768 valid packets and 3,121 rejection packets
match independently generated full bytes and field expectations. Author hosted
and sanitized checks and all twenty freestanding objects are retained. This
codec is not included in the live source adoption. A separate bounded connection
core is under implementation and verification, including copied stream storage,
TX completion tokens, handshake, retransmission and FIN/TIME_WAIT. It provides
no admitted stream socket or actual TCP NIC execution yet.

Exact records are in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V78.json`.
Continue fresh adopted-source qualification, artifact publication, TCP/IPv6,
managed services and the isolated default Notes/Files desktop with basic English
automation. All ten native profiles, twenty modes and four supplied musl profiles
remain in scope. Physical M11 and manual M12 remain user-deferred; full M0-M12
is incomplete and the goal remains active.

## Earlier continuation: Release NIC and native storage fault/cold execution

Actual x86_64 Release associated-zero-default UDP NIC execution is now
independently reviewed and root-admitted, alongside the earlier Debug result.
The Release image review passes 81 checks and 191 controls; its actual NIC review
passes 72 checks and 1,314 controls (1,309 refusals and five healthy cases).
All 32 ordered application records, seven outgoing and eleven incoming complete
frames are retained. Root verifies 62 frame allocations/releases, two entry-stack
reservations/releases and no retained resources. Release uses its separately
built musl sysroot and the complete unique linked archive in loaded read-only
`.rodata`; the stripped image does not gain a symbol-qualified archive claim.
Termination remains host-requested. This is a bounded static-peer polling UDP
profile, with TCP, IPv6, general configuration, IRQ/SMP and other-architecture
NIC execution still pending.

The exact source12 ABI54 SDK-only native mounted-storage fixture has completed
three healthy writers, eighteen software-failed FLUSH writers and eighteen
separate cold boots of their exact complete post-disks. This primary campaign is
independently reviewed and root-admitted. The cold inputs are
reserved and consumed once each. The raw readers reconstruct every recorded
WRITE and compare the whole guarded disk; healthy/cold output checks cover
complete target contents, allocation maps and unrelated namespace/inode bytes.
All twenty-one pinned read-only e2fsck commands return zero through five passes
and explicitly skip journal recovery. Healthy and recovered caches drain; failed
writer quarantine deliberately retains state where applicable. The ordered
existing-file checkpoint fence can have no pending WRITE while retaining its
dirty transaction and four pins; this is not a healthy drainage claim.

Both initial QEMU refusals occur before guest startup and remain preserved.
Fresh runner successors use an IDE boot overlay and a newly created row-private
temporary directory; the immutable boot image, data drive, source and qualified
trace/raw readers are unchanged. The root's overly strict pending-WRITE issuance
failure is also retained. This campaign executes native Virtio block mechanisms,
not musl programs, a desktop, an emulated volatile cache, physical power loss or
general fsync durability. Independent review rechecks all 39 invocations and
adds 26 meaningful refusals; final readback checks the unchanged source12,
twenty explicit SDK forests and exact one-to-one cold reservations.

Six additional native mount-time FLUSH refusal cases and three unsupported
revoke-plus-checksum-v3 empty-profile cases have also executed successfully on
fresh original media. They remain pending separate independent admission.
The new private IPv4 TCP codec leaf passes hosted/sanitized checks and twenty
freestanding compilation rows; it is pending independent source admission and
does not provide a TCP connection, stream socket or NIC execution result.

The source-adoption inventory corrects an earlier installation-label ambiguity:
the live top-level Kernel and OS SDK validator declare ABI20. The retained
Kernel1159/OS632/SDK50/ABI49 label describes a separate historical private
checkpoint. The reviewed ABI55 Kernel1389 and OS686 candidate source and its
executed artifacts have not been adopted into these live trees. Complete
recoverable live copies and per-path Git/live/candidate hashes now identify
120 Kernel and 47 OS divergent files for reconciliation. Useful local tools,
tests, existing deletions and infrastructure files absent from filtered private
snapshots must be preserved. A staged cumulative source reconciliation is in
progress; no live source or SDK upgrade is admitted here.

Exact admissions and execution selections are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V77.json`.
V76 and all earlier source, recipes and failures remain. All ten native profiles,
twenty mode rows and four supplied musl profiles remain in scope. Continue
independent storage admission, preserving live source adoption, TCP/IPv6,
managed services and the isolated default Notes/Files desktop with basic English
automation. Physical M11 and manual M12 remain user-deferred. Full M0-M12 is
incomplete and the goal remains active.

## Earlier continuation: ABI55 native matrix and actual zero-destination UDP

All twenty ABI55 native producer/export/SDK/OS artifact consumer rows are now
independently reviewed and root-admitted. All ten architecture Debug builds also
ran the standalone Kernel QEMU script, which includes model diagnostics. Release
rows establish compilation, export and artifact consumption. They do not imply
Release user execution. Independent review passes 138 checks, 1,360 controls
(1,240 refusals and 120 healthy cases), and 42 owned validator/compiler/control
groups; the separate terminal readback rechecks the exact native runner/imports
and all ten complete toolchain inventories.

The corrected public-musl UDP fixture is also source/host-admitted. Its OS686
source changes seven paths, including two byte-identical SDK55 validator/test
adoptions. It retains seven outgoing and eleven closed incoming events and uses
the precise associated-zero-output profile. Hosted execution passes 140 tests;
independent review adds 117 checks, 572 refusals and seven healthy controls. The
original exact-profile documentation defect and reviewer count typo remain
preserved.

Actual x86_64 Debug static-peer polling Virtio NIC execution is admitted after
separate image and actual reviews. The static Linux child successfully sends a
connected-default datagram to destination port zero; supplied-address zero
sendto still returns EINVAL, and destination-zero ingress remains refused. The
complete raw terminal/transport evidence contains 32 ordered application records,
16 located names, seven outgoing and eleven incoming frames. Independent actual
review passes 69 checks and 1,299 controls (1,294 refusals and five healthy cases).
Its codec reconstructs complete Ethernet/IPv4/UDP frames and closed peer order.
The additional independent image review passes 68 checks and 187 controls
(177 refusals and ten healthy cases), including all 34 archive records and 19
actual compiler dependencies. Root checks balanced terminal runtime reports:
72 frame allocations/releases, two entry-stack reservations/releases, and no
remaining frames, objects, pins, pending releases or stack leases. Original
sandbox SO_TYPE failure and reviewer-only CRLF control failure remain sealed.
Termination is host-requested; clean guest shutdown is not observed.

A separately built x86_64 Release musl and Release image have also completed,
followed by a successful disposable actual NIC execution. They remain pending
independent Release admission. The Release sysroot has 233 exact audited files
and uses -m64/-mno-red-zone/-O2. The normal Release ELF is fully stripped; fresh
readback qualifies the unique complete archive in non-writable loaded .rodata,
all projected section bytes and BIOS assembly, rather than claiming a retained
global symbol interval. The exact unchanged Release image passes the complete
archive and corruption checks. Release reports 62 frame allocations/releases
and two entry-stack reservations/releases. Earlier musl dangling-link sealing,
archive-digest transcription and Release reader failures remain preserved.

The native failed-FLUSH and separate-cold fixture now compiles on all ten
architecture Debug/Release rows, with an exact-source x86_64 Debug linked image.
Independent prelaunch review has found and preserved serial parser acceptance
defects; strict successors and final review are in progress. No actual native
fault/restart campaign is admitted by this continuation. Software FLUSH
suppression/completion faults cannot establish device-cache or physical
power-loss durability; intentional failed-cache quarantine may retain dirty
transactions and pins until guest termination.

Exact admissions and pending Release selections are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V76.json`.
V75 and all earlier sources, recipes and failed attempts remain. Installed
Kernel1159/OS632/SDK50/ABI49 is unchanged. All ten native profiles, twenty mode
rows and four supplied musl profiles remain in scope. Continue storage fault and
cold-restart qualification, independent Release NIC admission, TCP/IPv6, managed
services and the isolated default Notes/Files desktop with basic English
automation. Physical M11 and manual M12 remain user-deferred. Full M0-M12 is
incomplete and the goal remains active.

## Earlier continuation: reviewed cross-profile healthy Notes cold readback

The aarch64, rv64 and loongarch64 Debug Notes campaigns now have independent
actual review, a separate frozen readback and root terminal raw acceptance.
Together with the earlier separately admitted x86_64 campaign, all four supplied
musl profiles have bounded healthy first-save and cold-reopen evidence. The
three new campaigns execute 156 first-phase and 24 cold-phase Linux image
launches. Each saves and replaces seven complete English documents, exercises
retained descriptors, rename/stat/removal and reopening, then reopens and
displays all seven after a separate boot. The sizes remain 1,206, 1,023, 1,024,
1,025, 2,048, 3,072 and 3,584 bytes.

For every new profile, the complete first output equals the cold input and cold
output byte for byte. The same normal ABI54 distribution image and five exact
static Linux ELFs are retained across both boots. Independent raw parsing checks
all document bytes, uid/gid1000, mode0600, sizes, inode identities, block maps,
allocation and metadata checksums, complete namespaces and unchanged unrelated
files. All 60 recorded read-only offline commands have exact argv, logs and
retirement receipts. Independent review passes 105 checks and 1,755 meaningful
in-memory corruption refusals; its separate final readback passes 97 checks.
Root repeats the literal serial, wait/resource, whole-disk and raw filesystem
parsers. An original reviewer-only readback schema failure remains sealed and
separate from the successful actual executions.

First/cold frame allocations and releases balance at 3,151/506 on aarch64,
3,107/498 on rv64 and 3,451/551 on loongarch64. All first phases balance 52 entry
stacks; all cold phases balance eight. No retained frames, objects, pins, pending
releases or stack leases are reported after completion. Aarch64 and rv64 use
firmware arenas. Loongarch64 retains its advertised linker-pool fallback and
does not gain firmware-memory qualification. Namespace PIDs and retirement
reports are captured command receipts, not independent host process history.

Every read-only fsck returns zero after five passes and explicitly skips journal
recovery. The images retain ext4 RECOVER and JBD2 sequence874/start0. This admits
healthy completion followed by cold mount/readback. Host-requested QEMU
termination does not establish guest shutdown. Interrupted replay, failed-FLUSH,
device-cache or physical power-loss durability, Release application execution,
isolated graphics and general ext4 qualification remain separate gates.

The exact V4 observer and preparation recipe scope is independently admitted.
Its review adds 196 checks, 169 refusal controls and nine actual disposable hosted
owner/observer fixtures, including descendant retirement and failure/timeout
paths. All 108 earlier diagnostic counterexamples are now refused. The exact
root pure controls remain 596 checks and 576 refusals. V1-V3, their failures and
the pre-review disposable execution selections remain historical evidence.

A fresh private ABI55 coordinator now couples the admitted zero-destination
UDP output leaf to the Kernel module/profile declarations, exporter and OS SDK
validator. Its complete Kernel1389/OS678 inverse is exact; 96 hosted synthetic
producer/archive/consumer contract tests pass. Earlier coordinator-only failures
remain preserved. Old ABI54 and capability declarations and future ABI56 are
explicit refusals; wire.hpp joins the required hashed header set. Independent
source/test review is admitted with 104 checks, 96 independently rerun cases,
534 refusal controls, five healthy controls and four retired owned groups.
All ten native architecture Debug/Release producer/SDK/OS consumer rows are in
progress. Their passing author results are disposable execution evidence,
not final SDK admission. A corrected public-musl zero-port
NIC fixture and actual execution remain pending. Linux supplied-address port
zero still returns EINVAL; connected default output and native supplied-address
output may use port zero; ingress destination zero is still rejected.

Native Virtio FLUSH suppression/completion fault and separate cold-restart
fixtures are being prepared in a private OS test lane. Their software hook
cannot claim a durable device cache or undo completed writes. No new native
failed-FLUSH or interrupted-recovery result is admitted here.

Exact new admissions are selected by
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V75.json`.
V74 and every earlier admission, source, recipe and failed attempt remain.
Installed Kernel1159/OS632/SDK50/ABI49 is unchanged. All ten native profiles,
twenty mode rows and four supplied musl profiles remain in scope. Continue native
storage fault/restart qualification, the coordinated UDP successor, TCP/IPv6,
managed services and the isolated default Notes/Files desktop with basic English
automation. Physical M11 and manual M12 remain user-deferred. Full M0-M12 is
incomplete and the goal is active.

## Earlier continuation: reviewed Notes, FLUSH models and zero-port UDP source

Independent review of the three actual Debug first Notes workflows is complete.
The selected aarch64, rv64 and loongarch64 executions retain their 156 Linux
launches, 21 full documents and 30 recorded read-only disk commands. The fresh
review passes 77 readback checks and 699 corruption refusals. Root joins that
review to the earlier raw acceptance and independently selected sources, images,
SDKs and disks. Whole namespaces, inode/directory/group and initialized bitmap
checksums, allocation bits, payload maps and transient frame/stack/wait lifetimes
are checked. This completes the additional independent first-workflow review
listed as pending in V73. It does not add a new target launch, cold boot, replay
or shutdown result. LoongArch remains a bounded linker-pool execution profile.

The unchanged ABI54 storage source now has a reviewed failed-FLUSH software
cache model. Ordinary and ASan/UBSan modes each pass 76 writer/recovery cut
cases and 2,848 checks over separate 32 MiB volatile and durable images. Independent
execution adds explicit process retirement, 84 positive control checks per mode
and eight exact assertion refusals per mode; its readback adds 42 checks and
11 refusal controls. A failed FLUSH either has no durable effect or performs
the complete effect before returning an error. Restart, old-home visibility,
sticky quarantine and retry exclusion follow those explicit model semantics.
Checksum-v3-only empty-head completion and unsupported revoke-plus-v3 empty-head
reentry remain separate outcomes. No device cache, physical power loss, actual
Virtio FLUSH fault, interrupted guest writer or complete ext4 qualification is
inferred. Native fault injection and separate cold restarts remain pending.

A private zero-destination UDP source leaf permits the output wire and native
frame builders to emit a selected port-zero datagram. Linux supplied-address
sendto still rejects port zero; ingress still rejects destination zero. The
unchanged native UAPI supplied-address path also reaches the newly permissive
output builder, so its concrete API effect is recorded separately. Ordinary
and sanitized wire/native/binding/captured/runtime suites pass, with all ten
freestanding wire objects. Independent review reruns 12 binaries, checks the
whole source inverse and unchanged OS, and adds 8,882 public control checks and
three rejected guard mutants. Its final readback passes 47 checks and 16
refusals. The actual host Linux loopback reference is inherited host evidence.
This leaf has no new SDK export, standalone Kernel/OS consumer qualification
or target NIC execution. The exported ABI54 connected profile and its actual
guest still advertise the earlier port-zero transmission gap. A coordinated
successor profile and new public-musl NIC fixture are required before promotion.

Three Debug first/cold Notes artifact sets are also admitted after independent
compiler dependency, SDK and ELF review: 81 owned build commands, 27 compile
units, 15 static Linux ELFs, 59 SDK tests and 309 independent corruption refusals.
The whole OS688 source is OS686 plus the unchanged admitted first/cold fixtures;
all four default application bytes per profile are unchanged. New private disks
have been prepared with 84 owned commands. Independently authored raw disk
readback passes; final independent handoff and actual first/cold execution remain
separate gates. Original V1 and V2 recipe reviews found serial failure-sentinel
omissions. Both versions and reproductions are preserved. Fresh V3 recognizes
failure fields and word-bounded sentinels without requiring a colon or a line
prefix, and passes 524 hosted checks including 504 refusals. Its independent
review remains pending; no cross-profile cold result is admitted here.

Exact new selections are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V74.json`.
V73 and every earlier admission, source, recipe and failed attempt remain.
Installed Kernel1159/OS632/SDK50/ABI49 is unchanged. All ten native profiles,
twenty mode rows and four supplied musl profiles remain in scope. Continue the
fresh first/cold campaigns, native storage fault/restart qualification, coordinated
UDP successor, TCP/IPv6 and managed services, and the isolated default Notes/Files
desktop with basic English automation. Physical M11 and manual M12 remain
user-deferred. Full M0-M12 remains incomplete and the goal is active.

## Earlier continuation: actual connected UDP and cross-profile Notes

The public-musl connected UDP fixture now passes actual x86_64 Debug execution
through the selected polling Virtio PCI NIC. Raw terminal evidence contains 32
ordered application records, 16 located endpoint names, seven outgoing frames
and 11 incoming frames. Association, duplicate descriptor lifetime and reuse,
wrong-source filtering, zero-source-port ingress, AF_UNSPEC, explicit local
address retention, autobind and reconnect execute in the guest. Default send
to remote port zero still returns EINVAL without transmission; this Linux ABI
compatibility gap remains explicit. The native parent and child finish with
72 balanced frame allocations/releases and two balanced entry stacks, without
reported retained frames, objects, pins, pending releases or stack leases.

Independent actual review passes 60 checks and 442 adversarial refusals, using
literal serial and independently checksummed Ethernet/IPv4/UDP byte oracles.
A second independent raw/resource review adds 24 controls. Root replays the
literal oracle and exact source, image, SDK and owned command lineage. Capture
proves per-direction closed stream order and source-gated peer events. It has
no cross-direction timestamps or indefinite quiet observation. QEMU termination
is host-requested; guest shutdown, general networking, IRQ/SMP, Release, other
NIC architectures and TCP/IPv6 remain separate gates. The original attempt is
preserved: sandbox SO_TYPE refusal stopped QEMU before any guest protocol or
frame. The same selected inputs pass a fresh owned local-socketpair execution
outside that restriction. V1 recipes and selections remain; V2 preserves
malformed-receipt and incomplete-precommand failures through 28 hosted checks.

The other three supplied musl profiles now complete actual Debug first Notes
workflows from their independently reviewed initial ext4 disks. Each runs all
seven save/replacement/retained-descriptor/rename/stat/removal/reopen cases at
1,206, 1,023, 1,024, 1,025, 2,048, 3,072 and 3,584 bytes. Each executes 52 Linux
image launches and balances all 52 entry stacks. Aarch64 balances 3,151 frames;
rv64 balances 3,107; loongarch64 balances 3,451. The first two use the admitted
firmware allocator. Loongarch64 uses its explicitly advertised linker pool
with unsupported firmware profile; this establishes bounded application
execution, not firmware VM qualification. All ten native and four supplied
musl architecture profiles remain in scope.

Separate root raw readback validates 21 complete final documents, uid/gid1000,
mode0600, sizes, inode identities and block maps, plus whole namespaces,
unchanged non-target metadata/maps/bytes and all 15 static Linux applications.
It checks group, inode and directory checksums, 30 actual owned read-only
commands and 69 in-memory corruption refusals. This is a root readback using a
separately implemented serial oracle and earlier independent raw/checksum
readers; an additional independent actual agent review remains pending.
All three read-only e2fsck commands return zero after five passes and explicitly
skip recovery. Final disks retain RECOVER and JBD2 sequence874/start0. No cold
boot, interrupted replay, failed-flush durability or clean shutdown is inferred.
The original duplicate-entropy preboot failures and LoongArch firmware-only
observer failure remain sealed. Corrected runners consume unchanged images,
SDKs, initial disks and applications.

V72 preserves the earlier actual x86_64 first and healthy cold Notes readback,
static cross artifacts and hosted connected fixture admissions. Exact new
selections are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V73.json`.
Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. Continue cross-profile
cold/recovery qualification, TCP/IPv6 and managed services, and the isolated
default Notes/Files desktop with basic English automation. Physical M11 and
manual M12 remain user-deferred. Full M0-M12 is incomplete and the goal is active.

## Earlier continuation: healthy Notes cold readback and cross artifacts

Default Notes now passes the actual x86_64 Debug first workflow followed by a
second boot from its preserved journalled ext4 disk. The first phase runs seven
save/replacement/rename/removal/reopen cases at 1,206, 1,023, 1,024, 1,025, 2,048,
3,072 and 3,584 bytes; the cold phase reopens all seven documents through the
default Notes readers. The first phase completes 52 Linux image launches with
2,957 balanced frame allocations/releases and 52 balanced entry stacks; the
cold phase completes eight launches with 472 balanced frames and eight stacks.
No retained native frames, objects, pins, pending releases or stack leases are
reported after either phase. Independent actual review passes 112 checks and
48 corruption refusals, with no additional guest launch.

The complete first output, second input and second output are byte-identical,
SHA256 f6326b5eaa42491f7b5c04e6fde9aea83e8f006cde37978971e57af86301991f.
Both boots use the exact normal ABI54 image. No host payload replacement,
disk repair or journal normalization occurs between them. Raw readback verifies
the full seven documents, their inode identities, uid/gid1000, mode0600, sizes,
write timestamps and maps, plus unchanged namespaces, home write metadata and
five ELF payloads. Both read-only fsck commands complete all five passes and
explicitly skip recovery. Both disks retain ext4 RECOVER, JBD2 sequence874/start0.
This admits healthy completion followed by cold mount/readback. Guest shutdown,
interrupted-transaction replay, crash/failed-flush durability and general ext4
remain separate gates. The fixture, prepared-media and runner-control reviews
retain their independent hosted and artifact-only scopes and preserved failures.

The remaining three supplied musl profiles now have admitted Debug static Notes
artifacts: aarch64, rv64 and loongarch64, with 15 exact Linux ELFs, 27 actual
compile units and 81 owned build commands. Useful 59 SDK tests and six actual
architecture/mode refusals remain. Independent review adds 229 corruption
refusals and a physical source inverse. Final source02 is the complete ABI54
OS678 plus the unchanged first-workflow fixture; source01 and its old artifact
rows remain historical and excluded. These three profiles have no admitted
target application, disk or QEMU execution yet.

The connected UDP public-musl fixture source and hosted qualification are also
admitted. Whole OS686 physically reverses to the normal ABI54 OS678, with eight
additions and two changes. Author 79 tests and two header compile checks pass;
independent execution covers those tests plus 13 reviewer-authored tests and
148 refusal cases. Literal serial/name and wire references cover 16 located
endpoint reports, 32 application records, seven outgoing and 11 ordered incoming
frames, source filtering, descriptor reuse, AF_UNSPEC and retained-address
autobind. The zero-destination default-send compatibility gap remains explicit.
Actual connected image/NIC admission is still pending. Earlier S4/S5 actual
selections and the normal twenty ABI54 native rows remain preserved by V71.

Exact current admissions are selected by
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V72.json`.
Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. All ten native and four
supplied musl profiles remain. Continue connected NIC execution, cross-profile
Notes execution, storage recovery, TCP/IPv6/services and the isolated default
Notes/Files desktop. Physical M11 and manual M12 remain user-deferred. Full
M0-M12 is incomplete and the goal remains active.

## Earlier continuation: journalled Notes execution and coordinated connected UDP

The admitted larger-text default Notes fixture now passes actual x86_64 Debug
execution from a mounted journalled ext4 disk. Seven ordered workflows save,
reopen, rename, inspect and remove files at 1,206, 1,023, 1,024, 1,025, 2,048,
3,072 and 3,584 bytes. The unchanged normal distribution image loads the five
static-musl applications from the disk. All 52 Linux image launches complete;
terminal frames balance 2,954 allocations/releases and entry stacks balance
52 reservations/releases, with no reported retained objects, pins or leases.
Raw offline readback verifies exactly seven final documents, their full bytes,
uid/gid1000, mode0600 and sizes. The prepared disk and actual run have separate
independent reviews; their exact capsules remain selected separately.

The first short-window guest failure remains preserved. Its successor extends
the observation window and correctly excludes inode-zero unused directory
slots. QEMU termination is host-requested, not guest shutdown. Read-only fsck
returns zero after five passes but skips journal recovery; the final ext4
RECOVER bit remains set, with JBD2 sequence874 and start0. This proves the
healthy first workflow only. Cold replay, crash/failed-flush durability, clean
shutdown, Release and other-profile execution remain separate gates.
A separate healthy cold-readback fixture is being qualified; this continuation
admits no actual cold execution.

Connected UDP S6 now has admitted production mechanisms and independent source
review. Association supports a zero remote port; getpeername returns ENOTCONN
before output access for an absent or zero-port association. Ingress filters
the remote source port when it is nonzero, and disconnect preserves an explicit
local address for later autobind. The existing wire builder still rejects
default send to port zero with EINVAL before transmission. Dedicated ordinary
and ASan/UBSan campaigns each pass 10,952 hosted checks; inherited suites remain.
These captured-trap and memory controls are distinct from a public-musl NIC run.

The complete reviewed S6 Kernel and Notes OS compose through coordinated private
ABI54, retaining UAPI0.7.0. Exactly eight contract/test files change; both entire
parent inverses are verified. Exporter and OS consumer synchronize connected
profiles, required headers and association/snapshot type assertions, and reject
ABI53/55 and mismatched capabilities. All 94 producer/consumer Python tests pass.
All twenty normal Debug/Release SDK and separate artifact-only OS builds pass,
alongside ten standalone Debug Kernel scripts. Root matrix readback binds 150
owned commands and outer vectors and 1,360 queried objects. This is no independent
compiler replay or qualification of connected NIC execution, whole call-chain
stack bounds, immutable nested construction, SMP or physical hardware.

Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. Exact selections are
recorded in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V71.json`;
V70 and the separate earlier S4/S5 actual selections remain preserved. All ten
native and four supplied musl profiles remain. Continue connected public-musl
NIC qualification, larger-text Notes on the remaining musl profiles, storage
recovery, TCP/IPv6/services and the isolated default Notes/Files desktop. Physical
M11 and manual M12 remain user-deferred. Full M0-M12 is incomplete and the goal
remains active.

## Earlier continuation: Notes staged-write boundaries and native artifacts

Default Notes now splits writes to its exclusive fresh staging file at 1 KiB
boundaries and advances its local position by actual positive write counts.
EINTR leaves the position unchanged; zero or oversized returns fail with EIO.
This fixes a reachable journalled-provider refusal: six 200-byte words would
issue a crossing request at offset1005, while five 240-byte words cross at964.
The generic output writer, unchanged application main, staging ownership,
fsync/close/recheck/rename/directory-fsync order and pre/post-replacement failure
semantics are preserved. This is an OS application change, not qualification of
general cross-block filesystem writes or larger/unbounded provider mappings.

The exact 678-member OS successor reverses completely to its 676-member admitted
local-name parent: two hosted additions and changes only to the Notes staged
helper and xmake task registration. Author ordinary and ASan/UBSan campaigns
pass 57 controls each, including the unchanged predecessor counterexample,
1,023/1,024/1,025/2,047/2,048/3,072-byte contents, separator/newline boundaries,
short writes, EINTR, later ENOSPC and invalid returned counts. Independent review
re-reads all 114 author observations and passes eleven additional controls,
including EINTR at1024/1027, clipped-request overreporting, exact staging prefix,
old retained descriptors and pre/post-rename failures. No candidate production
defect is found. Count-oracle and compiler-log-parser failures remain preserved;
their corrected successors do not rewrite the failed evidence.

All twenty native Debug/Release Notes application artifact builds pass through
separate SDK-only OS consumers. Root readback binds 81 successful owned commands,
the complete copied OS inputs, exact Notes compile units, persisted xmake
architecture/mode/SDK selections and ten architecture ELF identities. The new
xmake task registration and x86_64 Debug artifact are independently inspected;
the reviewer does not replay the native compiler or independently qualify all
twenty rows. The unchanged SDK producer retains its previously admitted twenty
native builds and ten standalone Debug Kernel scripts. No Kernel source is
compiled by an OS consumer, and the Notes change alters no Kernel/SDK ABI.

Three additional S5 public-musl local-name Debug child artifacts are admitted
for aarch64, rv64 and loongarch64. All eighteen owned commands and six actual
architecture/mode refusals pass. Each retains nineteen compiler dependencies,
the complete 676-member OS input and 233-member sysroot, persisted xmake
configuration and an inspected static Linux ELF. Independent readback repeats
no compiler or guest. These artifacts add no other-profile NIC execution;
V69's actual x86_64 local-name execution keeps its separate exact selection.

The new larger-text default Notes/mv/stat/rm fixture has an author-built x86_64
static-musl artifact route and seven host workflows through3,584 bytes. It is
not included in these source/native admissions: independent fixture readback,
explicit disk payload preparation and actual journalled CommonStorage execution
remain separate. Healthy first-workflow execution, recovery, failed-flush/crash
atomicity, cold restart, clean guest shutdown and isolated graphical workflows
must not be inferred from these hosted or artifact results.

Connected UDP DESIGN_V2 is reviewed for implementation, including zero-port
association/query/filter semantics, source-address-preserving autobind and the
explicit existing default-send zero-port wire gap. Its changed public endpoint
layout requires a coordinated private ABI54 producer/consumer transition before
new SDK export. Mechanism tests and source review are still in progress; no
connected UDP execution or ABI54 artifact is admitted here.

Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. Exact selections are
recorded in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V70.json`.
All ten native and four supplied musl profiles remain. Continue journalled
default Notes/Files English workflows, connected UDP, TCP/IPv6/services and
isolated desktop implementation. Physical M11 and manual M12 remain user-deferred.
Full M0-M12 is incomplete and the goal remains active.

## Earlier continuation: actual public-musl UDP local-name query

The private budget/trace/S5 composition is admitted after complete reverse
reconstruction, hosted review and the twenty-row native campaign. All ten
Debug/Release SDK and separate SDK-only OS builds, plus ten standalone Debug
Kernel scripts, pass. Root matrix readback checks 150 command/outer vectors and
1,360 queried objects. Independent native review checks the selected x86_64
Debug/Release endpoints; it does not replay the native compiler or independently
qualify the full matrix. Imported historical collector construction and complete
call-chain stack bounds remain open. Exact final metadata reservation remains
required; arbitrary over-reservation is not qualified.

The separate source03 public-libc getsockname fixture is now admitted through
hosted, image and actual x86_64 normal-Debug Virtio PCI execution. Its SDK-built
native parent forks, executes the static-musl child and waits for normal zero
exit. Six phases cover unbound and fixed names, full/short/zero/NULL output,
descriptor duplication and close/rebind lifetime, bind-zero and implicit send
binding. Nine located name reports and all 25 ordered application records match
seven guest and eight peer frames, including complete headers, checksums and
padding. Fixed/alias port54322, bind-zero port49152 and implicit port49153 agree
with the raw wire. Wildcard queries retain ANY while actual packets use the
configured local address. The peer verifies complete frames and matching name
reports before acknowledging them.

Independent hosted review executes 51 methods and 37 additional controls.
Independent image and actual readback retain three linked-artifact and four raw
capture corruption refusals; neither review repeats the compiler or QEMU.
Final reported frames balance 72 allocations/releases and entry stacks balance
two reservations/releases, with no reported retained owners. QEMU and outer
groups are retired. Host termination is not clean guest shutdown qualification.
The failed first dependency-test fixture and all source/test successors remain
preserved. The actual image and observer use the same exact source03.

This is a private static IPv4 peer over serialized boot-CPU polling Virtio PCI.
It does not qualify Release or other architecture NIC execution, IRQ/SMP,
physical hardware, TCP/IPv6, general network services, isolated desktop,
immutable nested construction or complete stack bounds. Earlier actual S4
restart remains tied to its separate V68 selection and is not relabelled onto
this new composition.

Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. Exact selections are
recorded in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V69.json`.
All ten native and four supplied musl profiles remain. Continue connected UDP,
TCP/IPv6/services, journalled storage and isolated default Notes/Files basic
English editing and file management. Physical M11 and manual M12 remain
user-deferred. Full M0-M12 is incomplete and the goal remains active.

## Earlier continuation: captured UDP restart, local-name query and native matrix

The private S4 source03 captured restart and separate source04 test maintenance
are hosted-admitted. Budget/S4 composition passes independent PASS138 review,
root PASS97 admission and complete 20-row native matrix readback PASS846. All ten
Debug/Release SDK and separate artifact-only OS builds, plus ten standalone
Debug Kernel scripts, pass. The reader binds 150 commands/outer vectors and 1,360
queried objects. Independent composition review selects x86_64 Debug and hosted
VM controls; it does not independently qualify all 20 native rows. Exact final
metadata reservation remains a precondition; arbitrary over-reservation and
nested compiler construction/whole-call-chain stack closure remain unqualified.

The original restart guest passed its application/wire protocol but did not
prove interruption of the flagged recvfrom. Independent early-signal controls
showed that unchanged C could pass without an interrupted receive. Its stronger
restart labels are superseded, and the predecessor remains preserved.

The separately selected normal-Debug trace successor uses OK_ENABLE_TEST_POINTS,
with Release silence controls. Diagnostics occur after successful publication,
exact ticket completion, receive retirement and pending-state clearing. The OS
observer enforces ready < committed route < handler for both phases and binds
host datagrams to the exact routes. Actual testing corrected an observer error:
wait rearm preserves the initial request and advances its ticket, so the valid
relation is 0 < request <= ticket, not equality. Failed equality and excessively
permissive successors, images, execution and reader setup remain preserved.

The exact public-libc C probe now passes actual x86_64 Debug execution with a
plain EINTR phase followed by original-call SA_RESTART completion. Two committed
routes, 12 application records, one guest and three peer frames match raw bytes.
The plain continuation PC is the restart PC plus two, and that restart PC maps
to 0f05 in the packaged static child's executable PT_LOAD. Final reported frames
balance 118 allocations/releases; entry stacks balance 4 reservations/releases.
Owned groups are retired; host termination is not guest shutdown qualification.
Independent final review passes 569 raw refusal controls; root admission passes
213 checks for this exact x86_64 Debug execution. Observer review separately
passes 19 fresh methods and 593 independent refusal controls.

Captured IPv4 UDP getsockname source02 is separately hosted-admitted after
independent PASS333 and root PASS245. Ten direct/three socketcall profiles cover
full/short/zero/signed capacity, ordered copy faults, canonical OFD/endpoint
identity, fd reuse and lease revocation. Ordinary and ASan/UBSan author campaigns
retain 54 rows / 416,018 checks; independent new tests pass 10,952 each. These are
hosted synthetic-trap/memory tests. Native SDK and public-libc guest query
qualification do not follow from them. A deliberate budget/trace/S5 composition
and separate OS guest query fixture are being prepared.

Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged. Exact selected receipts
are recorded in `build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V68.json`. All ten native and four supplied
musl profiles remain. Continue local-name query/native SDK qualification,
TCP/IPv6/services, journalled storage and isolated default Notes/Files basic
English editing and file management. Physical M11 and manual M12 remain
user-deferred. IRQ/SMP, other architecture signal execution, full construction
and complete stack bounds remain separate gates. Full M0-M12 is incomplete;
the goal remains active.

## Earlier continuation: actual blocking UDP caught-signal EINTR

The private x86_64 Debug S3 blocking signal fixture is admitted after complete
independent source/package/image/raw review and 51 root admission checks. Its
SDK-built native parent forks, executes the public-libc static-musl child and
waits for zero status. In each of two phases the child installs SIGUSR1, forks
a sender that actually sleeps and sends the signal, and blocks in recvfrom.
The actual handler runs once; recvfrom returns EINTR without changing payload
or source outputs. A subsequent receive gets the exact datagram and address,
reaps the sender with zero status, checks the empty queue and closes the socket.
The second phase explicitly tests S3's EINTR-only limitation under SA_RESTART.

All fourteen ordered application records, one guest ARP reply and three peer
frames match the raw capture. The peer withholds UDP until the exact handler,
EINTR and retry prefix; its sends retain prefixes 6 and 11. Independent review
imports neither product observer/peer nor the author wire constructor, rejects
542 raw corruption/truncation/serial controls, and separately retains 278
package plus 1,441 observer/image controls. Fresh product campaigns pass six
package and eleven combined groups; two cleanup models preserve first failure,
partial evidence, reap-before-drain and the 0.25 s / 1 MiB drain bounds.

The complete archive, embedded ELF interval and BIOS bytes were independently
reconstructed. Final reported frames balance 118 allocations/releases; entry
stacks balance four reservations/releases, with no reported retained owners.
Owned QEMU and outer groups are retired. Host termination is not guest shutdown
qualification. Explicit Virtio RNG readiness remains a Linux exec prerequisite;
cryptographic entropy quality is not qualified. The same unchanged C probe also
builds through xmake and audited public musl on aarch64, rv64 and loongarch64,
with actual compile dependency capture. Those three rows are build-only and
are root observations, rather than independently reviewed guest executions.

S4's sealed test successor passes ordinary and ASan/UBSan hosted campaigns,
each with 21 rows and 178,599 checks. They add genuine shared-backend captured
receive/restart across ten profiles and typed n64/PPC publication models;
metadata ELF admission is not loading or execution. Independent successor
controls, deliberate budget composition and native validation remain pending.
Preserve the admitted S3 fixture while building a separately selected actual
SA_RESTART guest. Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged.

Exact references are in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V67.json`.
V66 retains the eight-phase actual nonblocking UDP NIC admission; V65 retains
twenty composed builds and ten standalone Debug scripts. All ten native and
four supplied musl profiles remain. Continue S4, TCP/IPv6/services, journalled
storage and isolated default Notes/Files. Physical M11 and manual M12 remain
user-deferred. IRQ/SMP, other architecture signal execution, full construction
and whole-call-chain stack bounds remain separate gates. Full M0-M12 is
incomplete and the goal remains active.

## Earlier continuation: actual musl UDP over a Virtio NIC

The private x86_64 Debug nonblocking UDP fixture is admitted after independent
raw-byte review and 49 root admission checks. The SDK-built native parent
actually forks, executes the unchanged static-musl UDP child and waits for its
zero exit status. Eight public-libc phases cover the basic exchange, PEEK/TRUNC,
short receive, zero datagram, consuming source-output EFAULT, PEEK fault
retention, bind-zero and implicit bind. All twenty ordered application records,
seven guest Ethernet frames and twelve peer frames match the captured bytes.
Independent reconstruction imports neither the product observer nor its peer
and rejects 2,433 corruption, truncation and extra/reordered frame controls.

Actual Linux exec observes the distribution's existing Virtio RNG ready record.
Final reported frames and entry-stack owners are released, and owned QEMU and
outer process groups are retired. Host termination is not clean guest shutdown.
All eight source successors, three failed images and four failed NIC attempts
remain retained. The earlier missing RNG caused an actual exec refusal and zero
wire traffic; the successor adds the unchanged normal distribution RNG device
configuration, without a Kernel repair. OKAR v1's projection to ordinary 0777
permission bits remains explicit, with complete host metadata checked separately.

This is a private static IPv4 peer and serialized boot-CPU polling modern Virtio
PCI qualification. It does not qualify Release or other architecture NICs,
blocking signals/restart, IRQ/SMP, TCP/IPv6, cryptographic entropy quality,
hardware, isolated desktop, immutable nested construction or whole-call-chain
stack bounds. All ten native and four supplied musl profiles remain preserved.
Installed Kernel1159/OS632/SDK50/ABI49 is unchanged.

The separate public-libc blocking UDP signal fixture now has explicit nondefault
SDK-only package/image targets and a freshly built x86_64 Debug image. Its
source/package review and actual caught-signal execution are still pending.
The first target expects S3's declared EINTR-only behavior even with SA_RESTART.
S4 genuine captured ten-profile restart models and typed publication controls
continue separately; passing codec or host reference rows is not guest evidence.

Exact references are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V66.json`.
V65 retains the budget/S3 twenty-build and ten Debug-script evidence. Earlier
English Notes/file and ext4-subset observations remain linked through V64.
Continue signal/restart, TCP/IPv6/services, journalled storage and isolated
default Notes/Files. Physical M11 and manual M12 remain user-deferred. Full
M0-M12 is incomplete and the goal remains active.

## Earlier continuation: captured UDP interruption and composed native builds

The private S3 caught-signal component is admitted in hosted scope after
independent typed-record controls and root readback. Its ordinary and ASan/UBSan
campaigns each retain 15 rows and 136,379 checks. Six fresh independent commands
exercise canonical/foreign/stale owners and actual encoder/release failures.
The first publication error remains authoritative during cleanup, and exact
receive retirement precedes clearing the pending syscall. The generic restart
identity query is not a Linux UDP typed-record query; independent direct typed
record inspection closes that specific assertion gap. These tests use synthetic
traps, mappings and link frames. S3 returns EINTR even with SA_RESTART; genuine
typed restart is a separate S4 implementation gate.

The exact budget/S3 composition is now private source-admitted. Its two shared
runtime spans reverse byte-for-byte to S3 and reconstruct the complete admitted
budget repair from the common parent. All 663 OS source members are unchanged.
All twenty normal Debug/Release SDK and separate artifact-only OS builds pass,
along with ten standalone Debug QEMU scripts. Root readback verifies all 150
successful outer commands and their new precommand vectors through 865 checks.
Independent composition/runner review passes 48 checks and selects the two
x86_64 builds, one Debug script and 15 vectors. It does not independently
readmit the full twenty-build matrix. No Release guest or signal-specific guest
execution for this composed source is claimed here.

New vectors contain helper/tool pins and an explicit source-capsule reference.
Copied source bytes remain checked at endpoints, rather than serialized as
per-command file vectors. Historical missing vectors and nested immutable
compiler construction remain unestablished. The private VM repair still relies
on exact final metadata reservations and does not qualify manually over-reserved
directories. Installed Kernel1159/OS632/SDK50/ABI49 remains unchanged.

The nondefault musl UDP NIC fixture image has been built through a separate
SDK-only OS consumer. Actual guest attempts and their failures are retained;
complete wire/application acceptance is still pending. S4's typed owner-store
successor has passing ordinary and sanitized models but is not admitted by this
continuation. A new public-libc blocking UDP signal fixture passes a Linux host
reference and an x86_64 musl build; neither is target signal/NIC execution.

Exact admission and readback references are in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V65.json`.
Earlier English Notes/file and ext4-subset observations remain linked through
V64. Continue actual UDP NIC and caught-signal execution, genuine ten-profile
typed restart, TCP/IPv6/services, journalled storage and isolated default
Notes/Files. All ten native and four supplied musl profiles remain. Physical
M11 and manual M12 remain user-deferred. Full M0-M12 is incomplete and the goal
remains active.

## Earlier continuation: admitted private VM repair and native matrix

The private two-file shared VM quota repair is now source-admitted after root
readback and independent review. It preserves the 1,024-frame pool, object
capacities and unchanged guest pressure application. The original x86_64 failure
needed 844 user pages against a quota of 840; no frame leak was demonstrated.
The repaired quota is 856 pages, with 103 metadata and 65 object pages reserved.
Six conservative metadata blocks cover each of sixteen published owners, and
the complete seven-block staging owner remains available. Publication rejects
over-quota record counts before backend creation. This admission requires the
current private builders' exact final metadata reservations; it does not qualify
manually over-reserved directories or future alias builders.

All twenty repaired Debug/Release Kernel SDK builds and separate artifact-only
OS consumers pass. All ten standalone Debug Kernel QEMU scripts and all ten
unchanged Release POSIX/shared-pressure/shell/Notes scripts pass. These are 180
recorded normal commands, with 101,910 build terminal checks. The original PPC
Release attempt refused startup under the generic CPU profile; that failure is
preserved. A fresh PPC run uses the existing native profile explicitly:
e500v2_v22, one CPU and single-thread TCG. The reader, product source and emulator
output are unchanged. Independent review covers the complete selected matrix
and this actual PPC argument vector. Passing the bounded POSIX script does not
close the standards requirements ledger.

The earlier all-twenty English Notes/file workflows retain 380 actual native
user commands on RAM/simplefs. Separate x86_64 Debug ext4-subset execution retains
two boots, 23 native commands and ten independent read-only host checks. Saved
content and link identity survive the second boot. These results do not qualify
journal replay, crash atomicity, clean guest shutdown or isolated graphical apps.
The original normal build runner's missing historical outer input-pin vector
also remains explicit; current tool pins cannot establish past execution bytes.

Bounded original image/SDK callback and hosted archive/frontend component
acceptance remains as recorded at V63. Complete construction authority, general
Debug object byte transparency and linked receiver/service stack bounds remain
open. The instrumented original core archive timeout and partial archive remain
preserved. The newly admitted source and matrix are private; installed
Kernel1159/OS632/SDK50/ABI49 is unchanged and no SDK promotion occurs here.

Exact acceptance and selected matrix references are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V64.json`.
Implementation continues with S3 caught-signal EINTR, S4 typed UDP restart,
actual NIC user fixtures, TCP/IPv6 and services, journalled storage, and isolated
default Notes/Files. All ten native and four supplied musl profiles remain.
Physical M11 and manual M12 remain user-deferred. The goal is active and full
M0-M12 is incomplete.

## Earlier continuation: native workflows and shared VM pressure repair

The exact private 2,026-member SDK54/ABI53 source union now passes all twenty
normal native Debug/Release Kernel SDK builds and separate artifact-only OS
consumers. All ten Debug standalone Kernel QEMU scripts pass. These original
xmake builds use unchanged source, flags and native tools without compiler,
archive, linker or callback adapters. The selected matrix records 150 owned
outer commands and 101,908 terminal source/tool checks. Complete toolchain
inventories and endpoint outcomes are retained, but the normal runner omitted
its full initial input-pin vector: the historical outer xmake executable hash
cannot be independently reconstructed. Current pins do not repair that history.
Construction authority, linked receiver/service stack bounds and NIC execution
remain separate gates.

All twenty corresponding Debug/Release English Notes/file workflows pass 19
actual native user commands each: 380 commands cover save, reopen, update,
rename, move, reading, hardlinks, safe overwrite refusal and final reopen. Each
workflow packages a fresh SimpleFS image and pins its QEMU, Kernel and rootfs.
This is RAM/simplefs shell/application execution, not an isolated graphical
desktop or persistence claim. Independent x86_64 readback reconstructs all 68
native objects, the 65-member core and three-member boot archives, 279 SDK
entries, the separate 663-file OS consumer and all 19 serial responses. The
twenty-row selector's first refusal is retained: its reader assumed newer
inventory fields in an older x86_64 receipt; the fresh successor explicitly
checks that exact legacy runner and derives coverage from its matching build.

Separate x86_64 Debug ext4-subset execution passes two boots and 23 native
commands for save, rename, hardlink, symlinks, directory rename, sync and reopen.
Independent final readback reconstructs all 23 response/completion pairs and
checks the final disk through ten read-only host commands, including e2fsck and
debugfs. Content and link identity survive the second boot. The original reader
marker refusal is preserved. This is synced non-journalled ext4 mutation before
emulator termination; orderly guest shutdown, journal replay, crash atomicity,
concurrent writes and the isolated graphical desktop remain unqualified.

The unchanged full Release POSIX script exposes a shared anonymous VM quota
failure on x86_64, aarch64 and rv64, distinct from the passing English workflows.
The x86_64 diagnostic identifies the second 384-page allocation returning ENOMEM:
76 live user pages plus both allocations need 844 pages, above the original
840-page user-purpose quota. No frame leak is demonstrated. A private two-file
repair preserves the 1,024-frame pool, all object capacities and original test,
retains a full staging mapping directory and bounds published record count.
Its x86_64 user quota becomes 856 pages. Ordinary and sanitized hosted regressions
pass, while the original-budget control fails the same pressure assertion.
Fresh x86_64 Debug/Release SDK/consumer builds, Debug standalone QEMU and the
unchanged Release POSIX/shared-pressure/shell/Notes guest pass. Independent review
and all-twenty successor validation remain pending at this continuation; this
candidate is not installed or source-admitted by the author's tests.

Configured original image/SDK callbacks have bounded root component acceptance
with explicit bootstrap inputs: 22 author controls, eight real callback runs,
and both 15,653/31,488 authority postcheck epochs are retained. This is not the
complete original graph or exporter. Coordinated hosted original -cr archive/
frontend composition independently passes 683 review and 1,291 handoff checks,
including 18 physical archive reconstructions and repeated operands. Production
composition remains open. The original instrumented core pilot's 68 objects
qualify, but its ar command times out at 600 seconds and never publishes final
archive execution authority; that complete failed attempt and partial archive
remain preserved. General Debug object byte transparency remains false.

Exact rows and readback references are recorded in
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_CONTINUATION_V63.json`.
Next work is the shared VM successor matrix/review, S3 EINTR and S4 restart,
actual NIC fixtures, TCP/IPv6 and services, journalled storage, and isolated
default Notes/Files. All ten native and four supplied musl profiles remain.
Installed Kernel1159/OS632/SDK50/ABI49 is unchanged. Physical M11 and manual M12
remain user-deferred; the goal is active and full M0-M12 is incomplete.

## Earlier continuation: SDK construction component integration

The exact private S2 source04 retains independent and root source acceptance.
Single decode, owned continuation, public poll, shared open-description lifecycle
and first-failure containment run through product functions in hosted fixtures.
The author passes ten ordinary and ten ASan/UBSan suites, with 56 fresh compiler
closures per mode, plus twenty target runtime units. Independent ordinary and
sanitized controls each pass five cases with 47 fresh closures. Root readback
verifies 226 distinct object paths. The third synchronous caller guard remains
static-only. The admitted S2/exporter disjoint composition retains all 2,026
source members, 663 exact OS members, public SDK and architecture matrices.
Inherited source scopes do not qualify full links, exports, SDK consumers,
signals/restart, linked stacks or NIC execution. Source remains uninstalled.

Exact compiler V7 and frontend V5 now have bounded root mechanism acceptance
for later private composition. Independent compiler 30+29 and frontend xmake/
18 supplemental controls pass. Separate readback passes 13,218 checks over 12
current/preserved capsules and 132 current pins; root independently rechecks
those 132 pins and 12 capsule forests. Actual independent compiler object count
is nine, separate from queries and synthetic drivers. Frontend each xmake run
records five real objects, five queries, five scratch assembly and two help
probes. V7 records a selected six-key environment on every actual route. All
earlier environment/role/ownership failures remain preserved. Caller failure
boundary checks, runtime/forest ownership, early frontend setup and complete
dependency protocol remain explicit external limits; no producer is admitted.

A separate linker/archive successor now captures original ordered arguments,
preassigned object/library/script inputs, private output instrumentation and
actual linker dependency records. Normal ar physical member ordinals preserve
duplicate basenames. Static review exposed snapshot, final-output and forwarding
gaps. V2 root 29 passes; independent 22 rejects four late-close/command-record
cases after genuine hosted commands. Their exact failures remain frozen. V3
binds returned/persisted command records, argv/cwd, environment and evidence
pins, and independently checks inputs/outputs after descriptor close. Root 34
controls pass through xmake; independent root34, adversarial22 and eleven
supplements pass with 852 outer checks. Separate readback verifies seven
successful leaf rows with 621 checks. Root rechecks all five selected link/registry
capsule forests and eight current sources before bounded private leaf acceptance.
Failed fresh rows retain partial outputs without authority and never unlink public
paths. Direct hosted static ELF/ar/raw binary comparisons pass; the raw-link
fixture uses .code16 instructions in an ELF64 host container, not i386 hardware.

Twenty explicit historical rows retain 500 displayed links and 40 ordered ar
recipes. Read-only physical inspection verifies all 40 archive member orders and
payloads, including duplicates. Separate models pass all 540 grammar cases using
empty synthetic files and synthetic libgcc bindings without invoking a backend.
These models do not upgrade hidden historical argv or actual library selection.
The prior read-only target-query draft retains 62 host cases and two actual
synthetic queries; production query binding is still required. Private driver
selection and deterministic output-registry components are progressing separately
and carry no producer or SDK authority.

Output registry V3 passes 52 hosted filesystem methods and 24 final caller
checks. Independent read-only review passes 26,492 checks across all four preserved
control forests and exact current source/copy/recipe pins. Registry authority is
metadata; it does not by itself establish that a compiler or linker executed.
The helper has bounded root acceptance for later private metadata composition.

The separate construction frontend now performs a real hosted xmake target query
and API-driven compile/ar/static-link chain. It retains received/backend/actual
commands, reserves exact queried outputs, binds duplicate physical archive member
occurrences and independently rechecks known file/root boundaries. Successful
execution companions and final producer results are required in addition to registry
metadata; a late failed producer cannot feed a later archive. Actual compile failure,
stale/reordered/missing authority, same-byte inode replacement and late binding
failure are covered separately. The passing successor has 16 methods; all earlier
configuration-path, unsupported fixture-flag and archive tuple-transport failures
remain frozen. Independent review now passes the unchanged 16 plus 12 adversarial
methods. Its final readback binds both complete execution capsules, seven source
copies and terminal checks. Root separately rechecks all three selected capsule
forests and exact source copies with 124 checks before bounded private caller/
consumer component acceptance. The independent controls add zero backend commands;
the fixture has 12 genuine operation commands, including the expected compile
failure and a successful compile whose final caller publication is refused. The
first root readback incorrectly expected the author runner in the independent
execution capsule; that failed harness receipt remains frozen. Its successor uses
the exact independent runner boundary. This is hosted component integration.
Transparent xmake compiler launchers, complete production query/configuration/flag
authority, exporter/image routes and source/producer admission remain open.

Actual read-only target querying now uses the admitted 2,026-member union.
All ten native profiles in Debug and Release pass through the exact project and
catalog, with a separately assigned configuration/output root for each row.
The fresh V3 campaign has 20 configure and 20 actual query commands, 1,360 queried
object occurrences and 1,424 absent named-product observations. Root rederives
every ordered normalized query from its original command log, checks source/tool/
runtime pins and rechecks seven complete selected capsule forests. No product target
build is requested. V1 preserves the cross-target/host configuration-path failure;
V2 passes all20 queries but retains three independently rejected failure-path
patterns. V3 registers known input siblings before validation, separately checks
each source-root directory, records completed failures and reobserves product
absence. Eleven root-authored extracted dispatch controls, six grammar controls
and 6,074 readback checks pass. A separate independent review rederives all20
rows and verifies all40 tool endpoints and actual commands, then recommends exact
positive read-only observations only. Its two models expose initial tuple snapshot
loss when the later directory capture fails. V4 protects initial file/mode capture
separately, retains each successful snapshot immediately, and dispatches terminal
file/mode checks independently. Its fresh all20 query campaign passes with the same
1,360 objects and 1,424 absent products. Nineteen independent boundary methods
and exact final readback pass. Root separately verifies the complete selected
forests and source pins before accepting only exact V4 read-only observations
and bounded snapshot failure reporting. Query acceptance supplies no producing
flag, object, export, SDK consumer or guest authority.

A separate controlled transparent xmake fixture passes compile/ar/static-link
routing with caller-issued configuration and post-query construction phases.
The outer launcher successor requires its own successful final authority in
addition to the child constructor. Earlier default transient-dependency, wrong
compiler-hook API and evidence-domain failures remain preserved. The passing
fixture uses an explicit xmake compargv object hook without transient -MF output;
default xmake dependency lifetime and the complete original dependency protocol
remain open. Exact V6/V8 independent review passes the original15 plus21
supplemental methods and800 caller checks before/after the controls. Root readback
passes3,125 checks across four complete selected forests, exact sources/copies,
caller inode boundaries and actual command evidence before bounded private
execute/selected-launcher composition acceptance. Standalone wrapper lookup is
supplemental and must retain full child registry/execution authority. The first
root harness incorrectly treated the expected failing xmake build as a success;
its refused receipt remains immutable and the successor checks that exact negative
command independently from ownership and successful campaign commands.

A separate original dependency/lifetime candidate passes 16 hosted methods and
183 caller checks. Its selected MD/MF, ordered MT/MQ, MP and default target bytes
match direct GCC controls. The public MF is terminal-only, while retained command/
dependency/delivery evidence stays enduring. MMD is explicitly unsupported until
its full producing closure is qualified. Independent MD review rejects final-caller reuse: malformed command/root
metadata skips known sibling checks, and verified roots do not reach caller final
checks. Original16 and183 checks pass, while independent12 retain four discovery
errors and one root-transfer failure. V2 preserves those failures, protects sibling
discovery and transfers exact saved roots. It retains original MMD bytes and uses
actual producing H/save-temps records for full include names, with full prequery
equality as a crosscheck. Its31 hosted methods and337 final checks pass.
Independent V2 review then rejects whole-record type handling and CRLF line-control
splicing. V3 retains those failures, rejects malformed complete records, and
normalizes translation-phase splicing before refusing source/header directives.
Its36 inherited/added methods and373 checks pass;17 independent controls pass.
Root separately reconstructs four successful lifetime consumptions and actual
C/C++/assembly closures with306 checks, then accepts exact bounded hosted GCC13
V3 only. V1/V2 final-caller reuse remains rejected; GCC14 and complete GCC semantics
are separate gates. A first root harness incorrectly required ownership errors
for an intentional compiler failure and final producer files for compiler-only
fixtures; its refused frozen attempt remains preserved.

A separate default xmake integration now passes20 controls, four boundary models
and878 final checks. It uses genuine standard MMD/MF compilation without the prior
custom object hook, and successfully consumes/retires public MF before ordinary
archive/static-link consumption. Retained actual dependency evidence and exact
saved roots remain enduring; successful child compilation cannot bypass failed
outer publication. The campaign has22 physical backend records and five actual
xmake commands, plus one Python model command. A separate integration V2
selects the accepted dependency V3 while preserving the default xmake protocol.
The unchanged20 controls, four models and878 checks pass. Independent33 controls
and156 final readback checks pass; root separately rechecks the exact source/input
pins and complete forests before bounded private GCC13/default xmake acceptance.
Original-target/GCC14 qualification remains outside this acceptance.

A fresh original Kernel object-only pilot copies the complete2,026-member union,
uses the unchanged original project and caller-issued toolchain wrappers, queries
the complete target registry, and requests original kernel_main.cpp/boot.S through
standard xmake --files. Three frozen refusals remain: setup inventory followed130
broken legacy header aliases; the query helper expected the original scalar deps
field to be an array; Debug GCC14.2.0 emits a working-directory preprocessing
marker. Successors preserve alias text/modes as unselected metadata and permit a
scalar only for deps. The third attempt configures/queries successfully and both
boot.S compiler commands return zero, retaining an8,016-byte private object.
Compiler V3 refuses the additional Debug prologue and publishes no queried object.
Separate compiler/lifetime V4 now has root acceptance for exact optional Debug
cwd metadata and saved-root transfer. Its51 methods and602 terminal checks pass;
root reconstructs twelve bounded lifetimes and fourteen independent negative
models with253 checks. General Debug original-object byte transparency is false:
actual GCC13/GCC14 macro counterexamples show changed DWARF columns under
save-temps. Five separate diagnostic compiles also show H-only producer-byte
changes and failure to retain both full and filtered dependency outputs with a
second MD option. These diagnostics grant no product authority.

Default xmake integration V3 passes both positive modes but remains rejected:
independent malformed-sibling models reproduce missing producing-cwd discovery
before lifetime qualification. Fresh V4 independently registers plan, closure
and projected directory roots before old siblings; malformed/conflicting carriers
cannot suppress later known boundaries. Its separate Release/Debug campaigns each
pass22 controls, twelve boundary-model methods and879 final file checks, with
22/23 physical backend records. Independent46 methods per mode and344 final
readback checks pass; root reconstructs both author/replay actual command ledgers,
sixteen successful child cwd transfers and whole enclosing consumers with499 checks
before bounded composition acceptance. General Debug byte transparency remains
false. A first root harness incorrectly required every terminal-only public MF to
stay absent even after the deliberate caller mutation; that frozen refusal remains
preserved, and the successor checks exclusion from enduring authority.

The independent original-target V5 static audit exposed three failure-reporting
gaps: uninitialized predecessor selections, build refusal before child discovery,
and first-object refusal suppressing later objects. Fresh V6 repairs all three
and passes three separate nonproducing models. Its exact object-only attempt04
copies all2,026 original source members and uses original Debug -g and standard
xmake --files. Genuine GCC14 boot.S/kernel_main.cpp compiles succeed, producing
8,016/163,960-byte queried objects with full closure1/113 and filtered MMD1/54.
Original source/runtime/authority checks pass:572 root checks,401 persistent
terminal checks and11 inventoried wrappers. Archives, ELF/images and all other
queried objects remain absent in that preserved two-object observation.

Fresh V7 compiles the complete exact queried x86_64 Debug object set: 68 objects,
83,943,576 bytes, through the unchanged original xmake source list and flags with
explicit dependency instrumentation. Four enclosing commands retire successfully;
3,579 author checks, 3,404 authority checks and 77 wrapper observations pass.
Independent target/language-specific readback reconstructs 136 actual compiler
commands, 68 saved Debug cwd markers and 3,108 final consumer boundaries. The
first independent reader and root execution of that reader incorrectly required
the C++ -ffreestanding flag on core execution.S; both refusals remain preserved.
The original target only selects that flag for C++, while okernel_image separately
selects its assembly flags. The independent successor passes every queried unit;
root separately checks that exact declaration and command against the preserved
3,811 successful root checks. General Debug byte transparency remains false.
These are complete-object observations for one profile, with archives, ELF and
image outputs absent. Full original target/SDK/OS/guest composition remains open.

Original GNU rcs/SDK source-main publication V1 remains rejected because failed
final authority omitted old stage history checks. Separate V2 discovers original
route/result/worker/archive/map siblings independently and checks all known old
and published endpoints on refusal. Only whole successful qualification permits
individual stage retirement. Its40 methods,10,350 assertions,509 terminal checks
and118 actual hosted records pass. Independent715 checks and final2698 readback
checks pass; root reconstructs successful authority, physical core/boot payloads
and GNU indexes, and failed-final history with2892 checks before bounded component
acceptance. This supplies no original GCC14 target or product SDK admission.

The two-image-epoch design retains root acceptance for bounded implementation.
Candidate06 passes48 author controls and17 source/helper processes, but independent
review rejects erased retained/command/source-terminal closure and a retirement
caller-finish exception that saves no structured refusal. Its27-check receipt
preserves both failures and successful genuine BIOS byte/event observations.
Fresh image11 retains both original BIOS helper epochs and complete old/public
retirement evidence. Its 85 controls and 20 original-source helper runs pass;
independent 38 checks plus 40 final readback checks and root 30 checks plus 15,766
authority boundaries pass before bounded hosted component acceptance. This does
not admit the configured native graph, whole SDK hook or production images.

A separate private callback bridge installs/restores the actual configured xmake
image and SDK fields, their distinct private environments and identity-equal
lexical image helper. Ten nonproducing restoration models and 36 independent
static/frozen checks pass. A fresh real-target image adapter executes the original
fields using explicit hosted bootstrap inputs and stops at the original exporter
request. Independent review rejects candidate03 because identical wrapper bytes
at a new unassigned path/inode, with a rewired caller final, are accepted as real
execution evidence. That reproduced refusal remains frozen; the successor must
bind the assigned wrapper and original producer through the owned stdout.
Neither component supplies production image, export or loader admission.

The next work is original core archive/link construction, assigned real-callback
authority repair/review, production exporter composition and a
complete producer/collector over the accepted union. Fresh all 20 Debug/Release
standalone links, SDK exports and artifact-only OS consumers remain required.
S3/S4, linked entry/service bounds, ten-native/four-musl NIC guests, TCP/IPv6/
services, storage and English Notes/Files durability remain open. Installed
Kernel1159/OS632/SDK50/ABI49 stays unchanged. Physical M11 and human M12 remain
user-deferred; full M0-M12 completion is not claimed.

## Earlier ABI53 production matrix and provenance capture

Private ABI53/SDK54 contract source now has independent and root source admission.
All twenty Debug/Release rows completed actual standalone Kernel links, explicit
architecture/mode SDK exports and SDK-only OS distribution consumers. The matrix
retains 3,070 compiler closures and 150,780 dependency occurrences. Ten Debug
standalone QEMU checks pass; ten Release observations are the existing genuine
core-status records. Those records do not qualify extension/session/NIC readiness
or shutdown. All20 root admission is limited to the recorded matrix gates.

The separate 2,020-member musl UDP composition now has independent and root source
admission. Its 1,357 Kernel members exactly match the 2,015-member ABI53 production
source, with the admitted seven-file OS fixture overlay. Author and independent
fixture suites each pass 110 tests. Historical musl builds and ABI52 runner links
remain separately scoped. A historical runner was an empty 576-byte ELF because
the included Lua target resolved its source paths under xmake/. A separately
admitted one-expression path repair preserves all 2,020 source members and the
exact Kernel forest. Author and root each pass 110 inherited fixtures; four real
xmake target inspections now discover both the runner C source and crt0 assembly.

Fresh Debug SDK-only native runner and musl probe links now pass on x86_64,
aarch64, rv64 and loongarch64. All eight ELFs have valid entries in nonempty loaded
instructions and the required native/Linux personality. Four new SimpleFS images
contain the exact fresh /init and /bin/musl-udp-probe payloads. The campaign records
36 native producing objects, 220 separately queried native dependency occurrences,
64 producing-command musl dependency occurrences and 56 clean owned command
groups. Complete source/union/tool/SDK/production-row postchecks pass. Root artifact
readback independently validates all eight ELF load regions and all four complete
image payload pairs. Two failed root readback attempts are preserved separately:
symbol-table API iteration and volume-label padding checks were corrected in
fresh successors. The passing artifacts receive only fixture build/packaging
admission; actual library-member, receiver, kernel-stack and NIC guests remain open.

The complete four-module provenance collector preparation07 passed independent
review: 87 author tests, 27 supplemental controls and 15,000 binary corruption
cases. The independently checked i386 Debug row has 154 compiler closures and
25 links. Root execution admission binds the exact07 tool, reviewed process
helper and all20 V3 manifest. Five real host command-wrapper regressions inherit
only after AST equality of imports, environment and lifetime functions; they
do not qualify prior compiler/linker or guest execution.

The first actual i386 Debug collection preserves all 25 linker replays, each
with a clean saved owned-group record. Root readback independently compares all
25 original/replay images, including PT_LOAD bytes. Twenty-three complete link
contribution records were retained. The standalone Kernel and distribution links
refuse duplicate task_manager.cpp.o member names; no diagnostic compiler ran.
The failed capture and its exact execution receipt remain immutable. Original
archive offsets, payloads and duplicate groups are inventoried. A reviewed
successor must establish unique contribution/member identity before diagnostics;
an ambiguous member or partial map never authorizes arbitrary selection.
Duplicate-member design01 has a preserved independent rejection. Its successor
must scope strong-symbol uniqueness to the exact current link inputs and correlate
each witness with a unique archive symbol-index entry, header/payload and ordered
construction input. An SDK copy also requires full archive-byte identity.
Duplicate-member design02 now has independent and root design-only admission.
The new execution-free resolver retains the complete actual-link input universe,
correlates unique symbol-index/header/payload/ordered source witnesses, and binds
map output domains to file-backed executable ELF sections. It refuses missing
input identities, malformed output headers, input-occurrence collapse, unsupported
nonweak definitions, conflicting immediate symbols and script overrides. Explicit
fill ranges account for padding; unexplained code bytes remain failures. Initial
v2/v4/v6 review defects, provisional versions and their readbacks remain preserved.
The frozen v7 component passes 48 author model methods. Its read-only attempt06
passes all 25 immutable saved maps and independently identifies 20 duplicate-name
code contributions in the two original images; complete executable-byte coverage
includes 2,548 separately retained padding ranges. Original product/script/input
pins are checked before and after. These are parser/source-identity observations,
not new links or execution. Independent exact v7 review now accepts the supported
component domain after 48 author and 45 expanded independent methods; it does not
accept complete PT_LOAD source/padding ownership or linked stack closure. The full
five-module collector-v2 preparation02 passes all 168 author methods and 32
independent complete-flow controls. Independent read-only V3 admission verifies
the selected i386 Debug row's 154 closures, 25 links and two construction events.
The local loader restores imports on success/failure and binds every active
module's payload, mode and identity. Five real host wrapper regressions inherit
only from verified unchanged command-lifetime functions and reviewed imports.
The original live07/capture01, failed v6 integration and reviewer fixture refusal
remain preserved. Root has issued a fresh exact tool/row receipt for capture02.
Capture02 is now frozen as a failure after all 25 actual linker replays and
clean saved owned groups. Twenty-four complete contribution records are retained;
no diagnostic compiler ran. Root readback compares all 25 original/replay images,
including loaded bytes. Duplicate-member resolution passed; the final SDK-only
distribution link refuses a source-owned boot archive without its original
construction binding. Read-only inventory finds three physical members exactly
equal to three producing standalone objects. Byte equality cannot backfill the
missing historical invocation. The capture and exact execution receipt remain
immutable; no library/receiver/entry/service/NIC admission follows.

A separate exporter preparation now records future real ordered ar invocations,
tool/object byte and mode pins, staged archive and final publication pins. Eighteen
hosted error controls pass, including failed-publication restoration. A fresh real
i386 Debug archive/export from explicitly reused production inputs passes; all
three physical members and unchanged SDK inputs are verified. The archive differs
only in its regenerated symbol-index timestamp, and the unchanged manifest format
records its new hash. The initial strict-byte comparison failure is preserved.
This is exporter preparation evidence; full source review, matching production,
SDK-only consumer validation and collector integration remain required. No old
receipt was rewritten or inferred.

A separate source-only root addendum corrects the old LoongArch64 stack design:
enter_owned saves the original service SP, switches to the owned entry SP and
uses that saved owned resume SP for the compiled trap callback. Original service
SP restores only after that callback. The Debug/Release production and musl-union
source bytes agree; actual linked instructions and numeric bounds remain open.
The accepted four-musl fixture uses nonblocking polling. A separately pinned
source inventory defines bounded Linux blocking-receive, EINTR and exact restart
slices. The S1 move-only capture/OFD/ticket design is now finalized and frozen.
It requires discoverable staged membership, atomic transfer before wait arming,
copied request immutability, typed completion outcomes and borrow termination
before origin/object/OFD retirement. The original S1 candidate's invalid-fd rejection remains
preserved. Corrected source02 now has the narrow independent and root admission
recorded above, including corrected payload/OFD/flag precedence and static
transfer-failure containment. The source remains unwired and uninstalled. S2
validation, EINTR and restart remain separate implementation gates. The polling
fixture and source admission do not qualify guest blocking execution.

Full linked-library/source/receiver closure and separate 65,536-byte entry and
restored-service bounds remain open across all twenty rows. The service source
reservation is 1 MiB; its conservative 64 KiB review target remains distinct.
Actual native/four-musl NIC guests follow those closure gates. Compiler closures,
matrix boots and host loopback traffic do not imply M6 completion.

Storage remains at 363 Release graph nodes and 27 unresolved source positions.
The conditional twelve-position Session supplement does not close the nine
BlockDevice and six erased guard/context positions, upstream authority or
whole-operation/all20 bounds. Journalled English Notes/Files save/reopen/crash/
recovery/sync/reboot/fsck workflows remain open.

Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. All ten native and four supplied musl profiles are preserved,
as are original disks, interrupted metadata and rejected/failed attempts.
M0-M12 remains active and incomplete. Physical M11 and human M12 are user-deferred.

## Prior continuation: admitted Linux UDP runtime/autobind composition

Canonical bind(0), implicit send autobind and late-error port persistence are now
deliberately composed into the admitted immediate Linux UDP runtime. Complete
supplied sockaddr copying precedes port reservation; reservation survives later
protocol, route and payload-copy failures. Existing native bind/frame-building,
target errno publication and contained MIPS delay-slot refusal remain exact.
The frozen candidate has 2,013 members, four changes and one addition.

Ordinary and ASan/UBSan each pass 1,984 checks in 81 actual hosted runtime calls.
Twenty architecture/mode rows compile forty actual runtime/service objects,
with 134 compiler closures, 22,656 dependency occurrences and 110 commands.
Independent review and the root source receipt admit this bounded composition;
synthetic hosted extension execution does not qualify target traps or NICs.

Private ABI53/SDK54 is assigned with UAPI 0.7.0, 64-bit Session counters and the
same bounded common-storage profile. Its coordinated producer/consumer contract
candidate is sealed for independent review: explicit hashed UDP profiles,
ordinary C++23 contracts and a console-only Release core-status record. Saved
author tests pass 73 methods, forty target objects and 24 wrong-layout refusals.
No whole build, product export, SDK-only consumer or guest is yet qualified.

The separate public-libc musl UDP fixture leaf has conditional root admission.
Four supplied musl builds capture 64 actual dependency occurrences. Four native
runner links use explicitly historical ABI52 SDKs; independent host tests pass
37 tests and four real child-status cases. Its seventeen loopback datagrams are
host reference behavior. Deliberate union with ABI53 runtime/autobind, packaging,
full syscall stacks and actual four-musl NIC guests remain required. Failed
validation03 retains its original unqualified freeze and disclosed aftermath.

Matrix runner V3 preserves V1/V2 and corrects complete-line parsing, final drain
failure checks, live observer termination, compiler search environments, explicit
host compiler pins and assigned-source preflight. Sixteen real hosted child
process cases and nine contract refusals pass. Independent successor review
precedes builds. Observer termination is not guest shutdown or session readiness.

Storage still has 363 release graph nodes and 27 unresolved source positions.
The conditional twelve-position inlined Session supplement does not close the
nine BlockDevice and six erased guard/context positions, upstream authority or
whole-operation/all20 stack bounds. Journalled English Notes/Files
save/reopen/crash/recovery/sync/reboot/fsck workflows remain open.

Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
are unchanged. All ten native and four supplied musl profiles remain. Original
disks, interrupted metadata, rejected sources and failed attempts are preserved.
M0-M12 remains active and incomplete. Physical M11 and human M12 are user-deferred.

## Prior continuation: admitted Linux UDP runtime dispatch source

The private Linux-personality runtime now dispatches socket, bind, sendto and
recvfrom through the existing shared owned-backend capture, exact immediate
image capability and canonical UDP service. All ten direct/socketcall argument
layouts are preserved. Registers and the target stack pointer are copied before
argument callbacks; O32 copies exactly eight stack bytes and socketcall copies
one target-long argument array. Authority loss supersedes copy success or fault.

The bounded operation scratch is persistent and rejects reentry before decode.
The corrected one-use OFD guard rejects foreign process objects and zero-reference
or mixed-provider UDP shapes before retain, and preserves the original endpoint
and flags across descriptor reuse. Provider edges must remain immutable while
pinned. The result publisher completes the original captured frame synchronously;
access resets before final OFD release. The existing generic result path is
suppressed for this branch, preventing a second write after final release.

Operation errors already use the target errno numbering. The UDP publisher now
validates the reserved negative interval and encodes the target result directly,
preserving the existing n64/PPC completion gates without a second translation.
A fresh owned MIPS syscall observed in a branch delay slot takes a contained
unsupported-result path with no UDP decode, copy, OFD or device effects. Ordinary
missing immediate authority still fails closed. All-ten encoder/predicate models
and target compilation do not qualify actual MIPS delay-slot execution.

Receive owns packet/source/length scratch. Non-PEEK consumes before output and
publishes payload, then late signed source capacity, source prefix and length.
PEEK preserves the queued packet on a payload fault. Socket initialization checks
cached executor state and revalidates current image authority after the actual
extension link callback, before configuring/opening. Send copies owned payload
and constructs the actual service frame before immediate extension submission.

Binding snapshot, raw decoder, corrected immediate origin, original OFD guard,
receive body, captured decoder, operation body, runtime hook and autobind now have separate
root source receipts. Captured decoder ordinary and ASan/UBSan each pass 6,813
checks across ten profiles, with 278 shared captures, 140 reads and 1,440 copied
bytes; unchanged immediate and raw models also pass. Operation body each passes
29,750 all-ten-profile checks and twenty actual Kernel-wrapper probes. The
original-OFD independent models pass 212 existing plus 59 added checks each;
all twenty fresh target probes pass.

Actual x86_64 runtime/capture/OFD/POSIX/service code executes under explicit hosted
mappings and a boot-installed synthetic device extension. Each hosted mode passes
1400 checks in 29 invocations, with one owned wrapper entry per call,
balanced endpoint/stack cleanup and consumed old frame authority. Tests cover
socket flags, binding/conflict/length, send frame contents, empty payloads,
usercopy faults, device credit/link failures, receive consume/PEEK/TRUNC/late
capacity, descriptor/range ordering and unsupported flags. All twenty actual
freestanding runtime.cpp configurations pass, with 114 compiler closures,
21476 dependency occurrences and 66 commands. Compiler function
stack records are preserved; complete call-chain bounds remain open.

This first socket slice is nonblocking, IPv4 UDP with bounded queues/payloads and
the configured peer route. Its send error ordering and implicit port reservation
still require composition of the separately admitted autobind successor: full supplied sockaddr
copy must precede reservation, and reservation must survive later protocol and
payload-copy errors. That successor implements bind-to-port-zero and preserves
the existing native bind/frame-builder bodies exactly. Ordinary and ASan/UBSan
each pass 127,551 autobind checks, plus unchanged service/OFD regressions. Forty
actual wrapper/service target objects pass across twenty configurations. Those
changes remain outside the runtime receipt pending deliberate composition.
Blocking/restart, connect/options,
TCP/IPv6, general routing, sustained networking and services remain unfinished.
Hosted device frames are not NIC or guest execution. Fresh whole Kernel links,
coordinated successor ABI/SDK export, explicit SDK-only OS consumers, native NIC
guests and four supplied musl socket guests remain separate required gates.

Storage release evidence retains 363 nodes and 27 unresolved source positions.
Twelve positions have supplemental conditional inlined-Session machine evidence;
nine BlockDevice virtual and six erased guard/context positions remain. This
does not close upstream receiver/guard authority, whole-operation/all20 stacks
or journalled Notes/Files English save/reopen/crash/recovery/sync/reboot/fsck gates.

Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. All ten native and four supplied musl profiles remain. Original
disks, interrupted metadata, rejected sources and failed attempts are preserved.
M0-M12 remains active and incomplete; physical M11 and human M12 are user-deferred.

## Prior continuation: admitted captured UDP receive implementation

Native blocking UDP receive is implemented in the private candidate and admitted
at source, hosted-runtime and freestanding-unit scope. It uses the existing
shared owned-backend observation to mint a distinct opaque native binding,
retains the original canonical OFD and endpoint, and resumes an exact scheduler
ticket. Current-space full output preflight precedes packet consumption. Staged,
published and taken owner phases detach exact membership and consume independent
release edges once. Socket/installer and fcntl now admit clearing NONBLOCK; UDP
append remains rejected. The Linux restart permit path remains separate.

Independent review found and resolved a committed-exec ordering defect: UDP
owners now retire first in the committed before-retire callback, while old
nonleader entry leases remain escrowed and before fallible VFS retirement.
Process retirement stops on an invariant failure before backing release. The
rejected original source review and all failed test attempts remain preserved.

Exact candidate is
`m6-native-udp-receive-continuation-source-v1/source-review-attempt-01`:
1,984 files, six additions, five changes, no deletions. All 844 provider tests
and 30 build configuration files remain exact. Twenty architecture/mode rows
compile sixty actual runtime/fd/capture-probe units, with 64 compiler closures,
8,564 dependency occurrences and 46 successful commands. Their separate passive
provider regressions pass 407 checks in both hosted modes. The V5 test corrections
leave every V4 target compiler source dependency exact.

Actual receive owner, scheduler, OFD and copyout code executes with explicit
hosted flat mappings and synthetic owned-stack capture. Ordinary and ASan/UBSan
each pass 161 checks, with eleven owned wrapper entries and eleven balanced
owners. The 94 compiler closures and 17,186 dependency occurrences have separate
independent verification. Tests cover copied source capacity, output faults,
rearm, descriptor reuse, zero-length packets, cancellation/interruption, object
generation and committed exec retirement ordering. The exec model exercises the
public replacement engine and scheduler commit; full ELF exec dispatch and an
actual VFS failure are not executed by it.

Focused capture regressions separately pass UDP capture 291, shared statx
observer 363, pure restart adapter 1,462 and public Linux origin 243 checks in
each mode. Shared/pure adapters preserve ten typed profiles. There are 100
compiler closures and 18,742 dependency occurrences. Fresh public harnesses
correct hosted dependency omissions and exclude private counter/history access
and live backend injection. These models do not qualify target privileged
capture, real mappings, NICs, caught signal delivery or hardware execution.
Root receipt is `m6-native-udp-receive-continuation-source-v1/ROOT_SOURCE_ACCEPTANCE_V2.json`.

The pure UDP poll provider and Linux IPv4 copied-address codec are independently
admitted as source inputs. Provider queries remain cached and free of device
calls. Codec output preserves target family endian, network port order and zero
padding. Neither receipt qualifies Linux socket syscalls or musl execution.

x86_64 Debug storage now has admitted conditional Node/definition-selection and
physical Session components. Five original-OFD Node calls, 128 permanent vptr
stores, 2,133 selected definitions and 2,027 actual direct transfers are verified.
The physical component adds eleven IO definitions, 33 conditional calls, four
physical targets, three wrappers and 73 helper occurrences. Remaining unresolved
source locations for write/ftruncate/release/startup are 128/128/27/115. Complete
function gaps, upstream guard/wrapper authority, whole-operation stacks and all
twenty profile bounds remain open. NoDispatchGuard does not establish continuing
IO authority across reentrant teardown. These receipts cannot close journalled
Notes/Files crash, recovery, sync, reboot or fsck acceptance.

The Linux UDP adapter design derives all-ten direct/socketcall numbers, socket
flags, MSG constants and errno from pinned Linux/musl sources. Its implementation
needs typed native binding state, original canonical OFD retention, owned packet
scratch and Linux-specific consume/usercopy ordering. The proposed first
nonblocking slice remains a development step toward the complete network target.
It does not replace blocking sockets, TCP/IPv6, services or the M0-M12 gates.

Whole Kernel links, successor ABI/SDK export, explicit OS SDK-only consumers,
native guest receive/NIC and four supplied musl socket integration remain open.
Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. Ten native profiles and four supplied musl profiles remain.
Original disks, interrupted metadata and failed/rejected attempts are preserved.
M0-M12 remains active and incomplete; physical M11 and human M12 are user-deferred.

## Prior continuation: admitted readiness and UDP poll composition validation

The private receive service and bounded executor now have independently admitted,
nonwrapping readiness tokens and immutable explicit capacities. Zero-capacity
owners start terminal without device calls. Owners cannot copy, move or reset;
terminal state still permits queued-data drainage and final close, preserving the
first device failure cause. Exact source is
`m6-native-udp-readiness-capacity-correction-v1/source-review-attempt-01`:
1,975 files, two additions, four changes and no deletions. All 842 parent tests
and 30 build configuration files remain exact. The broader build-file count is
an inventory correction, not seven added configurations. Ordinary and ASan/UBSan
each pass parser 643, executor 1,199 and sequence 916 checks. Twenty architecture/
mode rows compile 100 actual affected Kernel units, with 108 compiler closures
and 13,172 dependency occurrences. Root receipt is
`m6-native-udp-readiness-capacity-correction-v1/ROOT_SOURCE_ACCEPTANCE_V1.json`.

Two further source candidates are sealed and pending independent source review.
The Linux IPv4 copied-address codec preserves raw target-endian family values,
uses network-order ports, ignores input padding and clears output padding. Exact
16-byte output size failure writes nothing. It passes 1,160 checks in each hosted
mode and twenty freestanding instantiation compiles. This does not qualify Linux
socket numbers, flags, operation admission, user copies or syscall behavior.

The pure UDP provider joins retained canonical description identity with cached
service/executor state in the existing native and Linux poll path. Zero-byte
datagrams supply requested IN, terminal state supplies unconditional ERR, healthy
active cached credit supplies requested OUT, and stale endpoints supply NVAL.
Queries perform no device I/O or queue/token mutation. Source is
`m6-native-udp-poll-provider-source-v1/source-review-attempt-01`, with three
additions, one actual runtime change and no deletions. Ordinary and ASan/UBSan
each pass 407 checks. All twenty actual freestanding runtime.cpp rows pass,
with 24 compiler closures, 4,684 dependency occurrences and 46 successful saved
commands. Models do not execute canonical OFD retention or scheduler registration.
Whole links, successor ABI/SDK export, OS consumers and guests remain unqualified.

Child/recovery callback evidence is independently admitted conditionally through
`sdk53-abi52-child-recovery-callback-v1/ROOT_CHILD_RECOVERY_COMPONENT_ACCEPTANCE_V1.json`:
six actual calls, eight pointer/seal stores, eight context/seal stores, twelve
complete caller ranges, 235 relocation words and 45 algorithm controls. Local
components require original nonmoving Context/workspace storage, admitted C++
lifetime/nonaliasing and synchronous retirement. They do not close whole stacks.

The fresh x86_64 Debug diagnostic storage capture is independently admitted for
identity/provenance: 74 C++ and three assembly objects, 44,392 executable
relocations and 2,614,647 text bytes. Its kernel_main frame is 496 bytes,
dynamic,bounded; the i386 336-byte frame does not transfer. Actual OS Debug argv
retains the later -O2 override. Six string helpers each have an 8-byte static
frame. Dynamic Node/device receivers, assembly/IRQ/SMP and whole-operation/all20
stack bounds remain open. Capture receipt is
`sdk53-abi52-x86_64-debug-whole-storage-stack-v1/ROOT_CAPTURE_ACCEPTANCE_V1.json`.

The reviewed UDP continuation design requires a distinct native captured binding,
the same real BackendCapture observation, a retained original OFD/endpoint and an
exact scheduler ticket. It preserves current mapping-aware copyout before consume,
two-token post-arm recheck and once-only cleanup. Native caught signals and Linux
restart authority remain separate work. No production zero-origin fallback is
admitted. Concrete typed interfaces are under review before implementation.

Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. Ten native profiles and four supplied musl profiles remain.
Original disks, interrupted metadata and failed/rejected attempts are preserved.
M0-M12 remains active and incomplete; physical M11 and human M12 are user-deferred.

## Prior continuation: bounded UDP executor and corrected stack components

The private bounded native UDP executor is implemented and independently admitted
as source input. It owns two persistent frame buffers and a two-entry copied ARP
reply FIFO inside Kernel, uses constrained static transport dispatch, and crosses
the actual OS device boundary through immediate copied TX and bounded completion
reap. The desktop loop polls before userland stepping, including with no runnable
task. Native recvfrom now reads its protocol queue without pumping the NIC or
synchronously sending ARP. Each executor turn admits at most eight RX calls,
eight TX reaps and one control submit. Cached queries perform no device I/O;
terminal errors retain io_error/cause and prevent further executor device calls.
The old synchronous application send remains a separate predecessor path.

Exact source: `m6-native-udp-executor-source-v1/source-review-attempt-01`,
RESULT `0922c95af0b2af6616719a44274832d9f046964d538319208562ab3f523b1af6`.
The 1,973-member forest has two additions, nine changes and no deletions. All 842
predecessor test files and 23 build configuration files remain exact. Ordinary
and ASan/UBSan each execute parser 643 and executor 1,199 checks. All twenty target/
mode rows compile four actual affected Kernel units: eighty freestanding compiles,
86 total compiler closures and 11,572 dependency occurrences. This is standalone
unit validation, not whole Kernel or OS consumer linkage. No OS source-header
fallback, SDK export, successor ABI assignment, guest or installation is claimed.
Independent review RESULT:
`fcbe710bac4fbef989bfe6c0cf37ca33796420b6b25bb3858903988e40dea38f`.
Root source acceptance:
`f5c35f2c8e29ff5cc408fbbe40038d71e614291fa305f003937402839e3fddf9`.

Physical Session callback evidence is now independently accepted conditionally
for the exact permanent capacity-one journal Registry/Session composition: 72
calls, 24 complete caller ranges and six local compiler sums 480, 560, 560, 1,064,
1,256 and 1,400 bytes. Root receipt:
`6baf763f43e2e03b3b0182a9989567ff8a1bf91a146d08646e45d357273b4ab0`.
Typed attempt03 remains rejected because its raw-symbol metadata serialized a
register-definition list. Corrected attempt04 is independently admitted for 16
calls, nine caller ranges, seven thunks/eighteen pointer references and a
conditional 808-byte component. Both rejected typed attempts remain immutable.
Root corrected typed receipt:
`ac854a1db8b8710bd20479b79acd19e099a4e481f5402c96b245e550c5c35af5`.

The independent i386 outer-path review verifies 24 complete functions, 1,509
relocation words, fifteen direct pairs/nineteen actual transfers and three syscall
registration windows. Permanent kernel_main contributes 336 compiler bytes; the
20-byte entry service save and transient IRET components are dead before later
dispatch. Partial write/ftruncate/path-mutation/path-lookup/startup-mount spines
are 14,112/13,792/13,952/20,288/12,256 bytes. These exclude downstream Node lifetimes,
callbacks and branch/helper peaks: thirty-eight indirect instructions remain
open. The 1 MiB reservation is not a complete stack bound. Root receipt:
`89ce07c0230416c4091e9421b8c4906307125149a116caff78a14cbe13b174d6`.

The author has additionally sealed the remaining four child/recovery callbacks
and two inlined child-guard outer calls in
`sdk53-abi52-child-recovery-callback-v1/attempt-03`, RESULT
`97841f9dcc4a5094c7839c10bd73529655d5010a91bfcf8cacbcd4d9dd77ee24`.
Seven conditional local components and 45 algorithm controls are saved; independent
review is still required. This does not close all device/Node contexts or stacks.

The next UDP sequence mechanism is in progress in its separate private lane.
Root reviewed a conservative global receive token plus independent executor token
with terminal saturation, continued queued-data/final-reference drainage, and a
pure joined wait predicate. Actual owners must expose no copy/assignment reset.
Canonical OFD/ticket registration/cancellation, Linux socket codecs, fresh successor
SDK producer/consumer links, whole production stacks and actual blocked-task/NIC
guest joins remain open. Ten native profiles and four supplied musl profiles stay.

Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. Original/interrupted disks and every failed attempt are retained.
M0-M12 remains active and incomplete; physical M11 and human M12 stay user-deferred.

## Prior foundation: ABI52 composition and UDP receive readiness

The exact private retained-common source is independently accepted for its
serialized implementation and saved author evidence. It contains 1,957 files,
six additions and ten changes. Root readback verifies 36 actual compiler
closures, 8,036 dependency occurrences, four matching ordinary/ASan+UBSan model
pairs and eleven preserved earlier attempts. The eight saved executions total
1,537,672 checks. Hosted09 remains globally failed because its auxiliary probe
used invalid bound member-address syntax; four corrected private denials and
matching positive controls are recorded separately. No acceptance rewrites a
failed attempt, and root repeated no runtime.

Exact source: `sdk53-mounted-common-opening-source-v1/source-review-attempt-01`,
RESULT `bfceab8cfaee72b1bc1c5919954f563cfd9a6c67510d67b1267958b89ac5cc58`.
Independent review: `sdk53-mounted-common-opening-independent-review-v1/attempt-02`,
RESULT `84642ecc8b76aaaf1c79d89eb6a7c0f0972c5d37ab8c8f4c0af3387a90030038`.
Root private-source acceptance receipt:
`b16d1a93909e7698af469b7e3c56285eef4b3f6484f1d95d39454f52342692fe`.
This accepts original lifetime/authority, seven-family reservation/selection,
retained locator adoption and failure provenance. It excludes complete target
stacks, IRQ/SMP, public storage, ABI/SDK export, OS consumers and installation.

The SDK50 default nonjournalled storage/TX composition now passes all twenty
native architecture/mode rows: forty complete distro boots, 680 captured actual
Ethernet frames and 540 English native okcrt Notes/file-management commands.
Sync, fresh boot, file/namespace/symlink readback and forty read-only fscks pass.
Four existing Debug successes were reused without reruns. Handoff:
`m6-virtio-tx-storage-recomposition-v1/HANDOFF_V2.json`, SHA256
`5d2a7a3ef3fd4bb432d7e6b526fc9aa507908d348c827c1870f606aad230124c`.
Root composition disposition is
`99e9bae0c25544c473567faa7bd2f26397b48c39f17d0bf514709b3df127b9f6`.
These are serialized healthy native workflows; musl, external socket/service
exchange, IRQ/SMP and SDK53 storage composition remain separate.

The accepted private common source compiles on all twenty target rows. Root
independently verifies 100 actual compiler closures, 9,980 dependency occurrences,
100 static archive payloads and 666 object/section-proved aliases. All 140 selected
roots have no reachable direct recursive components. Forty internal helper
graphs close, with retained-exact sums of 528-608 bytes and endpoint-selection
sums of 896-1,216 bytes. Eighty main common/typed/request roots and reclaim guards
remain open at erased callbacks, compiler helpers or downstream boundaries.
Reachable legacy helpers have individual frames as large as 13,120 bytes.
Capacity2 mechanism compilation does not qualify the actual capacity1 production
caller, final linked stack, assembly entry or configured stack capacity. Original
parser failures and the MIPS64 Debug disassembly timeout remain failed; analysis
correction inspected the same objects without recompilation. Root readback:
`sdk53-common-opening-target-stack-v1/root-readback-attempt-01`, RESULT
`21fb56b329121400bed2a39a5edba8ca533a37895b86d89f48ad66bb25319927`.

Actual default Notes static-musl English workflows are independently accepted in
the optional SDK50 Debug lane on x86_64, aarch64, rv64 and loongarch64. Eight full
distro boots execute 68 real Linux-personality Notes processes: 52 successful
exits and sixteen expected refusals, observed by the native parent's exec/wait.
Create/edit/reopen, rename, hardlink/symlink replacement refusal and directory
relocation pass, alongside 108 separately labelled native Notes/files regressions.
Sync/fresh-boot persistence, offline byte/namespace checks and eight read-only
fscks pass. Exact default Notes main/save sources and Kernel/SDK50 are unchanged;
OS builds no Kernel source. The optional profile requires active realtime or a
bounded provisional volume last-write anchor before the existing maintained-
timestamp mount. This is not a trusted-time or RTC-accuracy qualification.
The original four timestamp refusals and the failed deleted-dirent readback
oracle remain preserved. Root acceptance:
`m5-default-notes-static-musl-v1/ROOT_SOURCE_ACCEPTANCE_V1.json`, SHA256
`2365fbd4762eda2ca59e198da8c19df7acae9026f8786dc64c8a921ea525772a`.
Dynamic/shared musl, GUI workflows, installation and full M5 remain open.

`sdk53-public-common-storage-source-v1/source-review-attempt-01` now seals the
public CommonStorage interface and normal Mount/Node zero/refill dispatch: 1,960
files, three new test files, one mechanism change and two scope-comment changes.
Author normal-access freestanding compilation and ordinary/ASan+UBSan models pass
35 actual compiler closures and 6,206 dependency occurrences. Each mode performs
2,477 checks, seven genuine startup recoveries, 74 opening transport failures,
six request failures, four zero mutations, six refills, six no-op controls, 174
permanent storage reuse refusals and two supported ordinary overwrites. All
sixteen terminal media outputs match between modes. Public retained VFS roots
and Nodes block close until references drain; permanent storage reuse refuses
before I/O, including after failed opening or Mount destruction.
The existing strict completion preparation safely refuses revoke+checksum-v3
legacy overwrite before publication, preserving complete media, write/flush,
epoch, native Session and inode lifetime while restoring readable admission.
That profile remains unsupported. All three failed oracles remain sealed.
Exact source RESULT:
`34a3ef1f0ec51e2db0d5f2eb9b14fd7628435871a81f82c5cf1502ae14d6fec4`;
root saved-evidence readback RESULT:
`5e084edf5297f8b7333b3e98e3bd3e0cbca35d60b0f7cdd8eec5431a0f500e40`.
Independent public-source review now passes with zero bounded-scope blockers:
`sdk53-public-common-storage-independent-review-v1/attempt-01`, RESULT
`ef57af3d3ec4ff533fca132fa52871b00d1fb9689ae5c456b6f744e0622af6be`.
Root accepts this serialized public source scope in
`sdk53-public-common-storage-source-v1/ROOT_SOURCE_ACCEPTANCE_V1.json`, SHA256
`8427e7d907f42745c43629a219e022e71277e10a9c67724d385e813e707d8a8b`.
No reviewer compiler/runtime rerun was required. ABI52 contract/profile,
exporter/validator and actual capacity1 caller source are now implemented in
`sdk53-abi52-common-integration-v1/source-review-attempt-01`. The exact 1,967-file
successor has seven additions, sixteen changes and no deletions. It restores
five inherited omitted tracked Linux compatibility files from separately frozen
Git-matching inputs and retains their useful tests. Contract attempt02 passes
104 Python tests and a normal-access capacity1 freestanding profile compile,
with one actual compiler closure and 214 dependencies. Failed contract01 remains
preserved; only the runner's individual-test tools import path was corrected.
Source RESULT `c40a86f7bdf2dc8e723a7620d1c40c4b47c20b7d4b90aa5be351d35ac337ed23`.
Independent coordinated source review passes with no bounded source blockers:
`sdk53-abi52-common-integration-independent-review-v1/attempt-02`, RESULT
`aa8091503c9aebcff17acac47944e3b8e6afa620e3ddf1ee61568eb1205432ec`.
Root source acceptance is
`b0cd5298b48d8483005420787a5be69042d4ce16fd5a4d9c2f5b9b632cd1baa5`.
Fresh standalone Kernel/exported SDK/SDK-only OS builds pass all twenty rows in
`matrix-attempt-01`, with ten separate standalone Debug Kernel boots. Independent
offline readback verifies 3,070 actual compiler closures, 149,392 dependency
occurrences, 500 compiler links, 1,440 captured archive object members and 5,424
SDK manifest member occurrences. Every row compiles the actual capacity1 caller
from OS source against its explicitly selected ABI52 SDK. OS compiles no Kernel
source. Independent review RESULT is
`b99fc38f926ba5e97c9d3c09de3eed95a63ea62924470fe20225344ce9e7d455`.
Root scoped matrix acceptance is
`sdk53-abi52-common-integration-v1/ROOT_MATRIX_ACCEPTANCE_V1.json`, SHA256
`0458de35cd3a060b8c1051578cc73ec3a0ce6439e151e78757bf7a763125fcec`.
Four saved compatibility-model executions remain separately labelled; their
temporary objects and host compiler/dependency identities remain unqualified.
Two real artifact layout controls pass: copied i386 Release and x86_64 Debug
SDKs retain correct admission metadata and refreshed hashes, but changing only
SessionCounter to u32 causes the normal OS caller's exact 64-bit static assertion
to refuse compilation. Original successful objects are the positive controls.
Control RESULT `5ad29271073839b6e77e395121736ee64c75f7b335595f788d6fc466e90fc805`.
Independent saved-control review RESULT is
`7d32e103593771e55c0ba1714b49c43ad5cef99ef5231046b3a50a112559c43f`.
No product selection or installation is claimed.

Private helper graphs cannot substitute for complete production stack/callback
evidence. Actual i386 Release linked capture now matches 56 diagnostic C++
objects, three assembly roots and the replayed distro executable's code bytes.
Independent stack-context audit verifies twenty frozen assembly restore paths,
ten Debug linked service-call paths and all ten 1 MiB permanent boot/service
stack reservations. Each backend restores the caller/service SP before runtime
decodes and dispatches the syscall. The 64 KiB pool carries privileged trap
capture. Canary pages are mapped diagnostics, not faulting guards. Root accepts
only this context correction in `ROOT_STACK_CONTEXT_ACCEPTANCE_V1.json`, SHA256
`054e565df8e589e094a4e4b75e95004e86bb49c0b8b546349ecac90d2caf5c7f`.
The i386 Release author lane provides a conservative 140-byte normal capture
component and five byte-checked linked libgcc leaf bounds of 48-80 bytes. Its 31
tool controls pass, but complete service callback, outer caller and other-profile
bounds remain open. Release linked dynamic
mapping, IRQ/fatal roots and full stack acceptance are not inferred. Earlier
64 KiB full-dispatch descriptions remain immutable historical evidence and are
superseded by this actual-path distinction. LeakSanitizer remains unqualified.

The saved i386 production evidence now passes independent tool/input review:
`sdk53-abi52-production-stack-independent-review-v1/attempt-01`, RESULT
`54b017ffe0cd74995425be7498abfa19f4dd8f3ed2ebafd017cbb00c01c32054`.
This independently verifies executable relocations as well as bytes, all 56
compiler graphs, 77 original/replay vtable words and five helper CFG/stack walks.
Root accepts only these bounded observations, including normal capture 140 bytes,
in `ROOT_BOUNDED_I386_STACK_ACCEPTANCE_V1.json`, SHA256
`1f68dd2a1ecf562b8b931cebb2ee28c21b0164add0fefc6aa5943ad9314e6d29`.
The maximum known individual frame reachable from the kernel_main root is 48,416 bytes; it is
not a complete chain bound. The normal mount/write/truncate roots remain open.

A parallel `m6-virtio-rx-source-v1/source-review-attempt-01` seals the bounded
copied receive FIFO and ordinary poll/receive/retry/reset ownership successor.
Author evidence passes all twenty native Debug/Release rows: forty actual distro
boots, 680 exact local-backend ingress frames, 560 guest byte-compared copied RX
payloads, 120 deliberately reset-discarded held frames, 680 exact TX frames,
540 native English Notes/files commands and forty clean read-only fscks.
Hosted and distro C++ dependency closures total 221 and 19,492 occurrences.
The original socket-query refusal before guest execution remains preserved.
Source RESULT `54d6a43e7824c9405b7339412f02f6064729c158b18242da0651d1e334bf9a12`.
Independent final source/runtime readback now passes with no scoped blockers:
`final-independent-readback-v1`, RESULT
`544fd6e69d0ac0f3ea5227ff4ec1398eb7fd6328e86f5cf199ff8374b333bf96`.
Root readback verifies the exact frozen source and twenty saved rows, all 221
C++ closures and 19,492 dependencies without repeating compiler, guest, socket
or media operations. Root accepts the serialized SDK50 healthy-device RX/TX and
default nonjournalled native Notes/files scope in
`ROOT_SOURCE_RUNTIME_ACCEPTANCE_V1.json`, SHA256
`37ada783b4b19ab5d8c1a1e076258cfffb59cf9bf054e2616c3a11a994ea07b8`.
These healthy serialized local-device checks do not qualify delayed duplicate
generation after repost, malformed active rings, failed active reset, IRQ/SMP,
native or musl sockets, SDK53 storage recomposition or complete M6.

A fresh exact source composition now joins the complete accepted TX and RX
union with the accepted ABI52 common-storage source in
`sdk53-abi52-rx-storage-composition-v1/source-attempt-01`. It has 1,971 files,
four additions and four changes, no deletion and no Kernel change. The existing
ABI52 NIC files match the TX predecessor's original input; the xmake difference
contains only four inserted targets. Storage, SDK validation, restored Linux
compatibility files, default-app/musl work and the predecessor queue test retain
their exact bytes. Source RESULT is
`c657df42b2a8d676c0784c66697de34316a8de319c864af9be2c6ce472f506d4`.
Independent exact composition review passes with RESULT
`b8cf961044d4bb3aac3ec4a3b55f70c3d9ca3913b1a6710ae6d469db2966e09b`.
Root accepts the exact source union in `ROOT_SOURCE_ACCEPTANCE_V1.json`, SHA256
`d3af105992373171ed79d1115814f650b1f97917334ad12f41b4f218decaa739`.
All twenty fresh selected-SDK OS-only builds now pass in
`sdk53-abi52-rx-storage-build-v1/matrix-attempt-01`: 1,710 compiler closures,
170 C++ units, 27,550 dependency occurrences, 480 links and 140 captured archive
object members. Kernel source is neither copied into those rows nor compiled by
OS; the original standalone producer/SDK matrix remains unchanged. Build RESULT
is `d0b97caa709a73bad766235ea16d90df7d27520165d1ceb0ee1dad9b68562495`.
The four preserved queue/TX/RX/inactive targets pass ordinary and ASan/UBSan
checks, with ten compiler source-dependency closures. Host RESULT is
`fd7f04866fa7addd5b4262f356e7b4fdc823ca1cc563deddec3b374ac7ea82dd`.
Root offline readback now verifies every saved row/source/SDK, all 1,710 actual
compiler closures, all 27,550 dependencies, 480 ELF links, 140 archive payloads,
2,258 products, ten host closures and 1,260 host dependency occurrences. Root
accepts the bounded build/model scope in `ROOT_BUILD_MODEL_ACCEPTANCE_V1.json`,
SHA256 `ca467728174193dcdcd80d9781e2ce9685f6b0b3ea0240304335d53a6fa5c885`.
The root readback repeats no compiler, model or guest execution. These builds do
not transfer the old SDK50 RX runtime acceptance; journalled guest workflows
still await complete production-stack qualification. No installation is claimed.

The next private Kernel source implements a pure copied receive-readiness query
and returns the exact generation-tagged destination handle only after UDP queue
publication. Zero-length datagrams remain readable; close/reuse rejects old
generations; snapshots neither borrow payloads nor reserve a later receive.
`m6-native-udp-receive-readiness-source-v1/source-review-attempt-01` preserves the
complete 1,971-file composed parent, changing only the UDP header, implementation
and retained/extended model test. Both ordinary and ASan/UBSan models pass 643
checks; all twenty standalone freestanding C++23 service unit builds pass. The
24 actual compiler closures contain 1,670 dependency occurrences, confined to
the selected Kernel/toolchain for each standalone row. Source RESULT is
`fd35d28d2277eab115eb7e77f7d12cb1377170278a8204daeffe989f3101edd9`.
Independent source/evidence review passes in
`m6-native-udp-receive-readiness-independent-v1/attempt-03`, RESULT
`c88470848ce510f4dfa1bd887babaa80d2e1599ddda7835826af820949bc7d85`.
Root source acceptance is SHA256
`a03dd582b196ef799187f8ebfd1e8bb2bcb1ab30b7910b6dda3e7e741a46fa63`.
The returned frame layout changes, so this private fork must not export or use
old ABI52 consumer binaries; coordinated successor assignment remains pending.
Nonwrapping readiness sequences, autonomous ingress, retained-OFD receive waits,
poll/Linux socket integration, complete links/stacks and guest execution remain
separate implementation gates. The two failed reviewer ABI-spelling checks are
preserved; i386 u32's actual emitted type is unsigned long on this toolchain.

The production-stack author now byte-binds 72 physical-device Session indirect
instructions in 24 functions and observes permanent disk/cache/128-node
construction. Six conditional local graphs close, including NoDispatch read,
write and flush components of 560/560/480 bytes. This new author slice still
requires independent review, leaves other BlockDevice contexts admitted, and
does not close mount/write/truncate or the outer service stack. Its RESULT is
`1508499a598932c50c03ac0e092d87c394486ef91a9b0502ff37cd3c4443767d`.
The subsequent `typed-guard-callback-attempt-01` is explicitly not accepted:
its tool misclassified typed_derive/typed_handoff's immutable outer_check loads
at context offset 0x20 as child guards. Its sealed passed field and failed
classification remain preserved; no derived graph or stack bound is promoted.
The author is producing a fresh provenance-checked attempt. This is an analysis
tool defect and does not establish a source defect or new guest execution.

All ten Kernel/native profiles and four supplied musl profiles remain intact.
Accepted Kernel919/OS623/SDK41 and installed private Kernel1159/OS632/SDK50/ABI49
remain unchanged. The private wide/common source retains ABI51 without binary
compatibility; its next export requires coordinated ABI52 and explicit matching
consumers. M0-M12 remains incomplete. Physical M11/manual M12 are user-deferred;
default English Notes/Files remains the requested workflow. Original media,
zero-byte interrupted metadata, rejected sources and failed attempts remain
preserved. No user input is needed.

## Previous continuation: accepted arithmetic and native common opening

The exact private common-opening budget and cv-bool repair is independently
accepted in its arithmetic/source scope:
`sdk53-mounted-common-opening-budget-source-v1/source-review-attempt-01`, RESULT
`36f7a4758630fed670461c05afa62b9564fb08f449b24c7ad9115c8525acf39b`,
FREEZE `55d31a54252ccdc5e6017f4a49430c07bdec126da1c9ec17bb00af2e205e9269`.
Its 1,951 files contain nine changes. Fourteen author compiler closures and
2,270 dependency occurrences verify ordinary/ASan parity: 395 new common-budget
checks, 107 wide arithmetic checks, 127 Session checks and 40,741 typed-budget
checks per mode. The separate independent disposition has no findings, verifies
the exact source/oracle, and adds normal-access compile-only policy evidence.
Root acceptance receipt is
`955ff685cc57091c037a52ceaaa876e6727c0a52cbc646fdee558b30dadf809d`.

The seven-family union covers 58,811,342,498 READs, 120 WRITEs and 64 FLUSHes in
all six attempted/completed headrooms. Selected route arithmetic requires exact
four/five-read progress and subtracts classifier reads from the original route
once. It rejects classifier write/flush progress and cv-qualified bool policies.
These are inert arithmetic facts, not native selection or writer authority.
The original wide source/disposition and failed oracle-alias compile are retained.
All twenty normal-access Debug/Release exact successor compilation cases passed,
with 3,740 dependency occurrences and exact ELF/archive checks. Debug forces O2;
individual frames do not qualify complete production call chains or execution.

The repaired failed-child source now has an independent functional disposition
for its existing serialized private ownership/cleanup scope. Preserved ordinary
and ASan/UBSan logs agree at 45,819 checks each. Root reverified eleven capsules,
2,027 preserved partial files, nineteen independent compiler graphs, 4,044
dependency occurrences and ten object artifacts. Nine old graphs are reconstructed
from saved outputs, with continuation-time header observations; ten fresh graphs
remain distinct. No runtime was repeated. General retirement-failure recovery,
concurrency and public storage remain unqualified. Root receipt:
`53c938f69aa67775c8789243894b6e299ab878bcc487acf667d008e6aceff852`.

Standalone unchanged Kernel1159/SDK50/ABI49 builds and explicit exports passed
all twenty architecture/mode cases. Separate readback verified 1,360 actual
compiler events, 120,792 dependency occurrences, all original objects, image ELF
profiles, both native/boot archive payloads and exact compiler-associated tools.
Dependency/header observations are readback-time evidence; historical snapshots
or boot execution are not claimed. All twenty OS-only TX consumers passed with
twenty normal-access closures and 1,220 dependencies; direct independent readback
checks SDK identity, ELF and archive bytes. The OS consumer builds no Kernel
source. Initial configuration-only failures and incomplete consumer rows remain
frozen. Scratch exports do not overwrite installed artifacts or export SDK53.

The TX source also has independently accepted actual healthy x86_64 Debug Virtio
execution: 258 decoded backend Ethernet frames, 256 bounded completions, sixteen
full refusals, two synchronous completions and two start/stop cycles. All nine
runtime attempts remain preserved; no extra guest ran during readback. External
peer delivery, ingress, sockets, IRQ/SMP, integrated storage recomposition and M6
completion remain open. Root combined validation receipt:
`6a732d403743765f75a84cd56c5fbdc3e83bb53fe95f53ddd9d8834eae91868c`.

A native common-opening successor is now under implementation in
`sdk53-mounted-common-opening-source-v1/source-v1`. Its design retains one actual
Mount/Owner/Session and permanently claimed workspace through the existing
locator, authenticated family selection, genuine typed endpoint adoption or
legacy continuation, cache renewal and root publication. Original standalone
cold tests and generic active-startup denials remain separate. Compile attempt
01's dependent-expression parser failure is sealed; corrected attempt 02 and
static authority/exclusion review continue. Root early review records off-stack
snapshot storage and strict typed sequence refinement obligations. This native
candidate is neither frozen nor accepted; public storage remains disabled.

All ten Kernel profiles and four supplied musl profiles remain in scope. The
private u64 source retains ABI51 without binary compatibility; future export
requires coordinated ABI52 and matching artifacts. Accepted/installed baselines
are unchanged. M0-M12 is incomplete. Original disks, interrupted metadata,
rejected candidates and failed attempts stay preserved. Physical M11 and manual
M12 remain user-deferred; default Notes/Files and English automation remain the
requested product workflow. No user input is needed.

## Current publication capture and lifetime review

The isolated typed/legacy composition now passes all twenty runtime suites in
both ordinary and ASan/UBSan modes: 56 commands and 90 actual compiler dependency
closures, including eight production freestanding compilations with normal
access control. Root verifies 4,277 complete capsule members and 844 directory
modes. Exact source: `sdk53-mounted-typed-legacy-composition-source-v1/
source-review-attempt-01`, result
`dec83de53bae2ea55fbcac0903dad5f66214cb6adef05ffbb1c1b9ea107d56c9`,
freeze `c829d00197c61f7bc14b2a8df2b37cfb560ab459772b767516164a8d12aa6001`.
The actual source manifest is
`d4234f2841abd49115016dbe7b02c347c882820fc13ccd8cfadc782c0bb4b3bb`;
`9ea5c15109c6844bdf3ec281f61a299fb781b9cf569eb76efb9929d192f95089`
identifies SOURCE_REVIEW_INPUT_V1.json instead. Independent composition review
accepts this exact source scope: `sdk53-mounted-typed-legacy-composition-
independent-review-v1/review-attempt-01`, result
`8f11a93a804a5538e761a8a92369510945d804a7e86b6d75dc9c676d80bbecd4`,
freeze `38212f1eb57d9d81fb3605b546d5d79194864b0372704a71fe464cdf9b149a64`.
Both modes pass 6,148 independent checks, ten commands, 46 compiler closures
and eight normal-access freestanding compiles. Root verifies all 34 disposition
members/modes and two directory modes. The scoped root acceptance receipt is
`d2f62f825022a7c27519b0ddd7f3e4c677de51563296fbc0187134d872204d55`.
No renewal, snapshot or cursor leaf is selected in this composition.

A separate original-anchor renewal repair is frozen for independent review:
`sdk53-owner-workspace-renewal-anchor-repair-source-v1/source-review-attempt-01`,
input `ff7c69386b4ff57dfc813376ab9d07c601e8c0ca4ca046bde22ad49cbc1d81b1`,
result `d3945a02f2d834e377a5b3f7ad38e2d0f4da4dab1162c418f0ed25d7e4faf980`,
freeze `f175f669b5b2d9445e0c06a0708f56c27a9fa09d926ee43180ee78fed9c520ed`.
Root verifies all 1,923 capsule members/modes. Actual admission retains immutable
references to the original Owner, workspace and native Session. Coherent serial
exhaustion follows complete integrity/terminal checks; strict child-terminal
Session equality is preserved. Eighteen author commands and thirty compiler
closures pass. Both modes pass 326 repair controls, seventeen renewals, zero
callbacks and the retained regressions. These remain author results, with no
independent acceptance of the original repair controls or mounted suffix
integration. A separate independent maintenance review passes static lifetime
analysis and positive/quiet-refusal execution in both modes: 524 checks, sixteen
renewals, 26 quiet refusals and four coherent serial-exhaustion refusals per mode.
Review: `sdk53-renewal-integrity-maintenance-review-v1/attempt-01`, result
`674416783600def8309627f07a27e3bc3f9de1592cd021d44a81eb90db67e43b`, freeze
`ed2fb41cab8dd289dd8985a809331be0677c477941d92cfa00c5c04a211bb7d9`.
Root verifies all 62 review members/modes. Six compiler closures and two normal-
access freestanding compiles pass. Dynamic integrity controls were not executed
in that review; the root maintenance receipt explicitly retains that limit and
the repair remains unselected.

Independent review of the preceding completed-ownership snapshot reproduces
two defects. Selected child retained()/idle() can observe a coherently changed
original pointer or callback before provenance and retirement checks, and the
post-visitor path omits the complete terminal-child predicate. That exact source
remains unselected. The original reviewer did not produce a terminal RESULT/FREEZE capsule.
Root preserves its complete current forest in
`sdk53-completed-ownership-snapshot-review-preservation-v1/attempt-01`: 2,078
files and 360 directory modes, result
`186d86011c2d9f7628d8abbd522ff17acb5814bdebd84dcce512e5ab12de7c94`, freeze
`094faa27be0018aa7775fbf34d6891d232d46983a9d08859f823e60579e88344`.
This preservation does not turn the interrupted review into completed independent
acceptance. No accepted or frozen source is edited to apply the repair.

A new isolated successor adds immediate published-cache capture and repairs
both visitor boundaries: `sdk53-published-cache-snapshot-source-v1/
source-review-attempt-02`, input
`5a99f6e8d2b1d752e8047e933315c0639b042000426ba253b8a5dc9851298d30`,
result `5ddfaf4281d080dd7ed730d44fbcc417f72ca46bb0dc4644070df905983e2048`,
freeze `b51a98c9e1348c090dda1a81e01a42921104c237335875496b62b393692d61d7`.
Root verifies all 28 source-capsule members/modes and six directory modes.
The actual successful Owner handoff captures every reconciled cache entry,
including unused canonical/staged bytes, before returning. The capture checks
the expected unchanged/replaced/retired result from the actual reconciliation;
later ownership capture cannot seal cache drift after publication. Original
Session and callback retirement precede retained observation, and the complete
same terminal-child predicate is checked after the private visitor. All storage
remains off-stack. No mounted callback runs under Owner/cache locks.

Six authored commands and eight exact compiler dependency closures pass.
Ordinary and ASan/UBSan each execute 356,954 checks across ten actual native
Session/child fixtures: 165,440 cache controls, eighty visitor controls and zero
callback invocations. Seven normal-access compilation snippets genuinely reject
the private APIs. Nine selected new frames are static; a tenth capture frame is
208 bytes, dynamic,bounded. The maximum selected individual frame is 352 bytes,
not a whole-target call-chain qualification. The original overly strict sealer
classification and superseded author campaign are preserved. All five retained
Owner, large ownership, prefix, legacy owned and invariant suites now pass in
ordinary and ASan/UBSan modes. The final regression capsule is
`sdk53-published-cache-snapshot-source-v1/retained-regression-attempt-03`, result
`76dd539387b6964b311e0abb6220de4985af3197cff7b3ae22cd119bd486a37a`, freeze
`104aa5a0a13ac7ab5c782372575ccad12077bb648afbeb7de54368e05d5bac6c`.
Root verifies all 78 members/modes and twenty exact compiler closures. Three
unchanged ordinary suites and the explicitly hash-verified ordinary binaries
are retained from frozen attempt 02; nine successor commands complete the
remaining ordinary runs and all sanitizer runs. Both earlier harness failures
remain preserved, with the failed compile's nine exact dependency closures
captured separately. Independent published-cache/visitor successor review now passes in its exact
source scope: `sdk53-published-cache-snapshot-independent-review-v1/
disposition-attempt-01`, result
`a21ddcdfc2028d4e6d754f9bf1af25623caec358392be7fd67fe65829e33752d`, freeze
`bd9d067e91487aaa344d188026c0937160bc31cb3a8a5d5ba5eb925db643c5a6`.
Each ordinary/ASan mode passes 496,817 independent checks across ten fixtures,
including 165,660 cache comparisons, 340 visitor boundary controls and fourteen
lifecycle controls. Independent expected images cover unchanged, replaced,
retired and unused slots with 327,680 compared bytes. Fifteen actual compiler
closures, two normal-access production compiles and seven private API denials
pass; callback invocations are zero. The reviewer fixture failure is preserved.
Root verifies all eight disposition members and the unchanged 28-member candidate.
Scoped root receipt:
`81597a9674e2e1a0d0e671c6707fcfdae04df7be413b4aaa82c30be007540312`.

The separate completed-global-proof birth-seal implementation is frozen:
`sdk53-completed-ownership-birth-seal-source-v1/source-review-attempt-01`, result
`f3a966ef54469d7b2592af51de83f9799ea56c93ae968d1a3c60f354984c028d`, freeze
`1c979534704a3e498e385ed2dd4cd320a679e7719fe6be4ed39a1bf43518394e`.
Root verifies all 1,940 capsule files and 165 directory modes. Both author modes
pass 19,962 checks, eighteen fixtures and 9,372 callback-free saved-field
comparisons; eight compiler closures and two normal-access whole Mount/Owner
compiles pass. Independent static review requires revision: successful native
transport needs an authority check before its post-transport geometry callback,
and global birth progression must not fall back to unused when a saved minted
flag changes. The terminal independent disposition rejects that original source:
`sdk53-completed-ownership-birth-seal-independent-review-v1/disposition-attempt-01`,
result `f0b0ffef2cf9122a6ef377c2b2a1ad90e24ea1840ec7174988e45427e53aff73`.
Passing safe lifecycle tests does not waive either static finding. The original
candidate and failed reviewer fixture remain preserved.

The additive dispatch-order/progression repair is independently accepted in
its exact source scope: `sdk53-completed-ownership-birth-dispatch-order-source-v1/
source-review-attempt-01`, result
`7efaec75eb187ff36eb73c06ecc511c4346dff9a304849da9dea4efa75944284`, freeze
`57d5285e1914437e56b86a1a7dd1dc4da14cd37fef781d16a5b65fd387a90260`.
Separate child-held progression prevents captured global state from selecting
the unused fallback. Successful native transport validates authority before and
after post-transport geometry; failed transport performs no later device
observation. Strict child-terminal Session equality remains unchanged.
Independent ordinary and ASan/UBSan each pass 1,074,820 birth checks across
22 fixtures and 54 native ordering cases with 3,633 checks. Twenty-one exact
compiler closures, two production compiles and eleven private API denials pass.
Independent result:
`c6d0018f0e7998a3587125c09b4739179dd6f7642ac7c68b41374ed9e05541f7`;
root scoped receipt:
`035ded6140557dbbc06c3bd115f2efe1a7e28c784542b2cd06d0c8ef6e26867d`.
Root verifies 1,975 candidate files, eight disposition files and 2,051 runtime
files with their recorded modes and compiler inputs. This grants no mounted,
suffix, renewal, SDK or target qualification.

The private native completed-child cursor bridge is frozen separately.
It admits original Owner exclusion before classifier READ1, seals actual child
completion into a distinct suffix endpoint, preserves child terminal progress,
and wires continuing birth/cache checks through an immutable Owner callback.
Its final author campaign consumes the exact repaired birth source and passes
19,837 checks across 75 fixtures in each ordinary/ASan/UBSan mode, with 480
suffix READs and 6,666 in-flight observations. It covers all five child families,
cross-group cases, recovery home masks and maximum journal-sequence no-op.
Six commands, eight compiler closures, two normal-access production compiles
and seven genuine private API denials pass. Consumed receipts retain an inert
terminal predicate after active cursor pointers retire; Owner exclusion remains
active until authenticated renewal. Frozen source:
`sdk53-native-child-cursor-bridge-source-v1/source-review-attempt-01`, result
`fa68da7d6191665ae5a6e603fca3da06f5f4d7ceac1e68b2f3d55046b2432a35`, freeze
`6d43f29959f6bbd9e38a4b0cd3e4e77271c9e6c746f2fdcfb048fbdbd5720edb`.
All seven source files and explicit dependency-parent pins are retained.
The maximum selected individual host frame is 640 bytes, dynamic,bounded;
complete target call chains remain unqualified. Static bridge review finds no
remaining blocker in its four-file scope and grants no execution acceptance.
Independent safe runtime review accepts this exact private source scope:
`sdk53-native-child-cursor-bridge-independent-review-v1/disposition-attempt-01`,
result `e5c2a7b683d67be0ce21cdbac07a8a1df45bffd9c7253ccb6b47bc0ab92bd5de`,
freeze `5db3bcc2dadc0b8a6265215eae9376cb5c299e1da800fdb88e50af22e9ba444c`.
Both modes pass 822,832 independent checks across 75 fixtures, 480 suffix READs,
45 restored scalar comparisons and 1,551 device-audited endpoint checks. Two
normal-access production compiles, eight compiler closures and seven private
denials with seven closures pass. Root verifies the unchanged candidate, four
disposition files, 136 runtime files and all fifteen compiler closures. Scoped
root receipt:
`4a79725702c82a3afa2c821e9d21c96ce7cc975d9a650c34da4eb4c4e07295be`.
The first two harness/compile failures
and historical third campaign remain preserved. Actual suffix filesystem
semantics, mounted Node/Lease admission, maximum-epoch no-op, serial renewal and
target execution remain separate ongoing work. The actual semantic suffix and
original Node authority are being implemented in separate named lanes.

The serial-bound mounted receipt renewal author candidate is frozen:
`sdk53-mounted-receipt-owner-workspace-renewal-source-v1/source-review-attempt-01`,
result `d719163d10064029a8b1ec171207674b588d4566856cb8312956b86bd9b1bc1a`,
freeze `577d814b34f304d71ffc17fd99ab9d67011cbe641244847ed6af94f6db3b09b5`.
Both author modes pass 23,645 checks, nineteen actual renewals, 81 quiet refusals,
ten detached serial controls and two coherent exhausted refusals. Fourteen
compiler closures, two normal-access production compiles and ten private denials
pass. Independent renewal review accepts the exact private source scope:
`sdk53-mounted-receipt-owner-workspace-renewal-independent-review-v1/
disposition-attempt-01`, result
`8c583aa7e0a25abf01da95d06ed34749ddb3ef35c8411c3fea80eb0d6bc52f54`, freeze
`341517c37ce26163abe01837b43411726841a3fd25555360331cf76fb10fd5a6`.
Both independent modes pass 179,712 checks across 75 fixtures, 82 actual renewals,
337 quiet refusals, 43 restored scalar comparisons, 31 detached serial controls,
eight repeat admissions and three sticky legitimate service-fence refusals.
The reviewer audits 491 suffix READs and 725 native endpoints. Fourteen compiler
closures, two normal-access builds and ten private denials with ten additional
closures pass. Root verifies all 101 candidate files, five disposition files,
197 runtime files, their directory modes and all 24 compiler closures. Root
scoped receipt:
`6a3ee9684c56c1b65556d045eb31e47b1dd07feef161b868b83790fa2f7d0408`.
Maximum serial boundaries use static and detached predicates; no synthetic live
serial history is transported. Reviewer attempt 01 remains preserved after a
test assertion mistake about successful Session quarantine. The candidate keeps permanent
Owner/workspace/Session binding, distinct child and suffix endpoints, checked
private operation serials and callback-free destructor-safe reconstruction;
it does not weaken child idle checks or rewrite child terminal progress.
Clean classifier cancellation, actual Node/Lease integration, semantic suffix
and target execution remain outside this renewal author result.

Original mounted Node authority and guarded child entry are separately frozen:
`sdk53-mounted-original-node-authority-source-v1/source-review-attempt-01`, result
`860015cfa0b0b5352912a26dd46b403da743eec509376074c8467e84b6afcd32`, freeze
`60f4a1b5eb6c1f0e39b74f46248164c0051b630986eb3bf59a823d3304e27143`.
The actual local I/O Lease and immutable NodeMutationContext are claimed before
classification and released last. Continuing outer authority surrounds inert
Owner/cache checks outside their locks. Both author modes retain the 75-fixture
bridge and pass 142 actual Node/Lease scope checks plus 189,735 guarded-child
checks. Twenty compiler closures, two normal-access production builds and twelve
private denials pass. Independent static review finds no blocker in its declared
scope; independent runtime acceptance remains outstanding. Maximum-epoch no-op
is admission-only in this candidate. Its clean cancellation needs permanent
anchor composition before selecting the renewal successor.

Concrete semantic suffix author source is also frozen:
`sdk53-mounted-typed-suffix-semantics-source-v1/source-review-attempt-01`, result
`38ab911b4565b4b408799fc6b02d19c941f982269da7e7627afa90d87cf7bb76`, freeze
`3688d8d681768145fba573f1b44c9088602063c311e67d10d5c8a7d6efbdd0ec`.
An authentic resumed child authorizes seven actual ext4 validation stages, or
one physical terminal READ for no-op. All transport uses the original native
Session; the adapter preserves writable geometry while refusing WRITE/FLUSH.
Both author modes pass 29,428 checks, eighteen positives, nine declared transport
failures/invalid responses, 1,473 suffix READs and 114 semantic completions.
Eight compiler closures and two normal-access production builds pass. Root
verifies all 1,953 capsule files and 167 directory modes. Seven failed author
attempts remain preserved. Independent suffix review accepts the declared private
source and safe hosted scope: `sdk53-mounted-typed-suffix-semantics-independent-
review-v1/disposition-attempt-01`, result
`66795b709e89dd4df6839b29c2cd882002dcee4cf41b3cc23f2877df9a7ee974`, freeze
`11db2e3b655a615f29192dca66fd58d003ce27150b6e74f8b5531565f5912682`.
Both modes pass 62,080 checks, 28 positives, seventeen declared failures, 6,036
restored callback-free scalar comparisons, 364 quiet guards and 2,580 suffix
READs. Eight hosted compiler closures, two normal-access production units and
four private denials with four closures pass. Root verifies the unchanged
candidate and all 3,942 disposition files / 418 directory modes, plus all twelve
compiler closures. Scoped receipt:
`7b9e8b9885a845940cf414a993f260dddea8b5afb073fa7ec46ea935546424d8`.
Inherited ordinary host helper frames reach 4,560 bytes; off-stack workspace
storage does not qualify full target call chains. Original outer-child dispatch,
publication,
epoch commit, renewal, startup and target execution remain separate gates.

Private composition preparation now explicitly selects the frozen birth repair,
bridge, renewal, suffix and original Node authority by path/hash. Preserved
three-way merge proposals resolve both serial and outer authority fields, retain
both Mount includes, and compose callback-free cancellation with permanent
Owner/workspace/Session anchors. Cancellation consumes its admission serial,
retains earlier authentic handoff history and never creates a child or Receipt.
Named lane: `sdk53-mounted-node-suffix-renewal-composition-source-v1`.
Its first hosted attempt is preserved after a nested test-entrypoint macro
compile failure; the failed compiler dependency closure is captured separately.
A test-only entrypoint repair starts attempt 02. Its ordinary mode passes all
six suites, including 24 genuine cancellation cycles and two later real-child
reentries. Independent static review requests a cache-lock correction: the
cache-idle failure path calls quarantine while holding the nonrecursive cache
lock, and quarantine reacquires it. Exact rejected source and review remain
preserved: review result
`cdda2c31feb8100d0976c2615fc9b96baa91094a1e43f309525c4408851f7218`, freeze
`ed8e297d60579de0992c154f85e96a0a65c48c66129a7c2ef3871ee8cc499350`.
No unsafe runtime defect reproduction is performed. Additive `source-v2` releases
the cache guard before quarantine while retaining the original Owner lock.
It adds six cancellation/repeated-admission scopes using the actual local
Node/Lease role. Hosted attempt 03 passes all six suites in ordinary and ASan/UBSan:
251 actual
Node checks / ten scopes, 24 cancellation cycles, two later real-child reentries,
eighteen genuine renewals and the retained child/suffix tests. Twelve
syntax-only private interface denials and their dependency closures pass.
The corrected candidate is sealed as `source-review-attempt-01`, result
`977ea56ff4694b61b09a64c426995c411b4202072c990562c2cab98a8195e4f6`, freeze
`79a34cdcd28dcc8d22eac06891612cdd5faa3a2bb393097267a3945ee9d45bbc`.
Root verifies 2,072 files and 169 directory modes. Independent static re-review
now clears the original recursive-cache-lock blocker; the accepted scope is
recorded with the full v3 composition below.

Concrete View publication authoring is frozen separately:
`sdk53-mounted-suffix-view-publication-source-v1/source-review-attempt-01`, result
`2bcf51bec78400a64b240f88954c20dfee051f45e96548c1057cda472730c5b5`, freeze
`a56c49e9ae48a15f8791184cd05d7a0b2067651c4de48b5290389a8454ac5d91`.
Both ordinary and ASan/UBSan modes pass 28 real publications inside the actual
original Node scope: sixteen single epoch commits, twelve unchanged no-ops,
ten later no-ops on the same genuinely renewed workspace, 112 quiet lifecycle
refusals and 16,144 checks. Publication performs zero READ/WRITE/FLUSH or clock
calls. Every View field is transferred with the original generic Reader; actual
child lineage authenticates the fresh checked state before genuine one-use
renewal, and the original Lease is released last. The maximum selected new host
frame is 272 bytes, not a whole-target stack qualification. Eight compiler
closures and two normal-access builds pass. Root verifies all 1,955 capsule files
and 168 directory modes. A read-only design audit finds no material blocker in
its declared scope. Publication-specific independent review now accepts the exact
private source/safe hosted scope:
`sdk53-mounted-suffix-view-publication-independent-review-v1/disposition-attempt-01`,
result `6ac644e1bc2f6b40485b6eea29b9a56437f1c9d923e4181a11786323fbe70c24`,
freeze `c6a78ed3f78cdbe58cbcc1c7f1c9845d0fc046d38f4e1d03c87191a0cc1ca841`.
Each ordinary/ASan/UBSan mode passes 60 publications, 26 epoch commits, 34 no-ops,
32 same-workspace reuses, 352 quiet refusals, 220,352 detached restored scalar
comparisons, 56 detached complete-field transfers and 400,718 checks. Publication
READ/WRITE/FLUSH counts are all zero. Eight exact hosted compiler closures,
two normal-access production compilations and five private denials/closures pass.
Root verifies the unchanged candidate, all 2,028 disposition files and 252
directory modes, plus all thirteen compiler closures. Scoped root receipt:
`1ed686a6be23e8155848a31c542d5220d5bd8bc6355f0aadd77f2a699d6268e1`.
The reviewer does not independently self-accept its authored renewal dependency.
The prescribed begin-before-Attachment-admission integration is tested; the helper
itself checks an unused Cursor, not a separate admitted flag. This
publication leaf's captured parent still needs the separate cancellation lock
correction when composing it into an enabled successor.

Additive root `source-v3` explicitly combines that frozen publication include
and its metadata import with corrected `source-v2` cancellation. All 1,927 source
files and directory modes are captured against the actual runtime input. A new
combined campaign, hosted attempt 04, runs the six retained suites plus real View
publication in ordinary and ASan/UBSan modes. Its publication fixtures declare
maximum mount epoch before the first mutation role and exercise genuine complete
no-op child/suffix/renewal terminals on both group profiles, plus quiet ordinary
mutation admission refusal. Native Session and operation serial histories are
unchanged. This is private terminal coverage; an actual public mutation request
classifier, startup provisional-root path, target stack qualification and SDK/OS
enablement remain outstanding. Hosted attempt 04 now passes all seven suites in
both modes: eighteen commands, 48 exact compiler dependency closures and six
normal-access freestanding compilations. Fifteen private API denials and their
fifteen dependency closures pass. Each mode completes 32 actual publications,
sixteen epoch commits, sixteen no-ops, twelve workspace reuses, 128 quiet refusals
and 17,940 publication checks with zero publication I/O. The runner omitted the
publication prefix from its marker filter; the raw logs retain it and both the
sealer and root capture explicitly verify the complete marker.

The full candidate is sealed as `source-review-attempt-02`, input
`3c107c597930e6e11532232e58e86c2fc362b0080a34cefb6a885abfb438e080`, result
`ef8b2cf304851727bda9be29a5bccec79445d4343302665724426be52f450e1b`, freeze
`fc268b22bd67e7e2a59e8280f1779e11871a6f89f3861d8220edabb066e2a124`.
Root verifies 2,107 candidate files / 170 directory modes, 2,177 runtime files /
514 directory modes, 64 private-control files and every compiler dependency.
The preceding root assertion expected 46 runtime closures; the actual manifest
has 48. That bookkeeping assertion affected no compile or model result.
`ROOT_AUTHOR_CANDIDATE_CAPTURE_V3.json` records the completed verification.
Independent full composition review now accepts the exact corrected v2 static
path and v3 private source/safe hosted execution:
`sdk53-mounted-node-suffix-renewal-composition-independent-review-v1/
disposition-attempt-01`, result
`cee31da9e8cc23bfc648ae4c589b85848491dc42eeb133c9a4a87346aa8182c1`, freeze
`1b14f09abb92cb7acea79337a54829738168b6f2c7adc8abb6d3d525d6cfcdf0`.
Each ordinary/ASan/UBSan mode passes 22 fixture mounts, 32 publications (sixteen
epoch commits/sixteen no-ops), 24 genuine pre-child cancellations, 194 quiet
refusals, 32 restored scalar comparisons, 5,126 transport observations of the
original Node authority, 1,088 real suffix READs and 40,675 checks. Publication
performs zero I/O and a second renewal is refused. Twelve actual compiler
closures, six normal-access production compilations and fifteen genuine private
denials with fifteen closures pass. Root verifies the unchanged candidates,
seventeen disposition files / one directory, 2,136 runtime files / 356 directories
and all 27 compiler closures. The first reviewer harness-name collision remains
preserved with 1,958 files / 180 directories. Scoped root receipt:
`2ccafda64696ee36f58b2160362fd75b948a00a251fadc7af2a21f3d366f3ea1`.
This grants private source/safe hosted acceptance only, with no public request,
startup, SDK, OS, guest or complete target-stack qualification.

Actual private zero/refill request classification and callers now have an exact
frozen candidate in `sdk53-mounted-request-zero-refill-source-v1/
source-review-attempt-01`, input
`c4c1772deef9a5496482f6def7bd926abab04fded0fa6dee5ead586a71123efe`, result
`8da93a2b3bcebf13fc7ed106c1559f1f994a3c230a3bd9638efbdfc43c0b38eb`, freeze
`a03a95ea266d498b46bc8922e1bd2ff882d70becf90a0621ac3ef5d3a3dc90e2`.
The actual private callers use reusable off-stack operation storage, full checked
View projection, two real decoder passes and one physical raw inode observation,
an original-lock-selected opening and real fresh requests. Six early author
attempts remain preserved: two test compile failures, two overly strict expected
classifier-READ assertions and two authentic large-volume fixture mount failures.
The corrected physical journal inode identity/checksum and empty head are declared
before mount; production validation remains unchanged. Author ordinary and
ASan/UBSan each pass twenty requests, ten normal refusals, two sticky child
failures, four maximum-epoch cases and a real 32-group u32 family refusal before
READ1 without editing native counters. Twenty-two compiler closures, two
normal-access freestanding compiles and eight private denials pass. Root verifies
2,006 candidate members / 170 directories and 2,074 author-runtime members /
283 directories; the three production files match the preceding static capture.

Root's independent ordinary and ASan/UBSan review now accepts this exact private
fresh-request scope. Each mode completes 52 requests: sixteen zero mutations,
eight refills and 28 no-ops, with thirty ordinary refusals, 8,192 physical data
comparisons, sixteen workspace reuses and 33,178 checks. Full-block, final-byte,
half-block and one-byte writes are checked against actual persisted media;
retained canonical Pins, root-directory targets, clock absence, foreign original
storage, invalid ranges and nonempty refill refuse correctly. Review disposition:
`sdk53-mounted-request-independent-review-v1/disposition-attempt-01`, result
`94abbaad2aea42de19cfe464f6b48987091fb02ea7e0311ddd09e1319f7bbbf0`, freeze
`718cbae7cc840e05a663c1a45ddaa29b436b1fa07e22418f041fa0731f8d78d9`.
Root verifies 2,045 runtime members / 244 directories, sixteen compiler closures,
two normal-access production compiles and eight private-access denials. The
reviewer's compiler-symlink capture failure and unsupported initial journal
fixture-profile attempt remain frozen. Scoped root acceptance receipt:
`a5b68dd8fe311aa274a7a783e9665be869254aba2df72bbd189de30b87633111`.
Pure whole-family capacity
preflight must precede Owner admission; admission must precede cursor reserve.
Classification uses finite original native transport and checked raw inode
state. An exhausted mount epoch permits only an authentic complete no-op, with
nonempty targets refusing before clock or writer admission. These implementation
contracts do not mark any product or release gate complete.

The exact frozen full composition also passes normal-access freestanding
compilation for all ten profiles in Debug and Release:
`sdk53-mounted-publication-profile-compile-v1/attempt-01`, result
`de5733dd2c95be528ea0c2acf118088589bfbfaa619de9b33e6018255283644e`, freeze
`8e8086c178028dbb6004e3fa85f0486c5197c6910030d8ee43e164d101eaa23c`.
This compiles the concrete Owner/Mount/cursor, original Node authority, guarded
children and cancellation with twenty exact dependency closures. Individual
stack frames are recorded per target. Complete-class compilation exposes inherited
directory-list/ownership frames around 15 KiB; passing compilation does not
qualify complete target call chains or the 64 KiB native entry-stack budget.
Standalone Kernel boot, explicit SDK export and OS artifact consumers remain
separate gates.

The exact frozen request successor separately passes all twenty normal-access
freestanding architecture/mode compiles:
`sdk53-mounted-request-profile-compile-v1/attempt-01`, result
`f9abf9dc1a7239546abd8d8d5fd1573cb9e9f0e395c639cff795e97ec6e8545f`, freeze
`b100491a000c882a2f61b495cf6fb7a1f76e4d6ed24b2783d61dd4e29f9e2715`.
Root verifies 2,377 files / 820 directory modes, twenty actual compiler dependency
closures, explicit object ELF class/machine and single-member archive
identities. Request-helper individual frames reach 4,528 bytes on x86_64 and
rv64; the full class's largest inherited frame is 15,008 bytes. Root compile
receipt: `05ec889a12733dd1f25a2babf86a635ef7e0838c4aa7c10389cae4b08660a85a`.
This is compilation and individual-frame evidence. It does not qualify complete
production call chains, SDK exports, standalone Kernel, OS or guests.

The frozen cold-startup predecessor was independently rejected. Ordinary mode
passed 32 root publications, eighteen writer cuts, fourteen mixed-home inputs,
256 post-scope Node operations and 58 transport failures, but ASan found a failed
native child retaining its original Session after Mount destruction. Rejection:
`sdk53-mounted-typed-cold-startup-independent-review-v1/disposition-attempt-01`,
result `ceb295f0e5960743c6428e43693003ac0df362f0e76ce17b4bb85ddf92d5ce46`.
The failed runtime, offline diagnosis and rejected source remain preserved.
The known failing predecessor was not reexecuted.

Root implemented a private terminal retirement for the two concrete typed
children. It requires the original quarantined, drained Session and its actual
terminal binding while that Session still lives. The retirement clears anchor
borrows, prohibits rebinding and preserves failed history and pending-write
diagnostics. Permanent child storage correctly outlives Mount/Owner/Session.
Exact repaired source:
`sdk53-mounted-failed-child-retirement-source-v1/source-review-attempt-01`,
result `d681ccc68b96c0ccdeb77bd7b120fa4f120e84444b402d2eb2b47ced91e1819a`,
freeze `a2634272d4092180a29c5ce5e2348a64bbc26621713365378eb72bd9e8785fcc`.
Its 1,942 files differ from the preserved unselected cold/request composition
parent in four production files and two fixture lifetime-order files.

Repaired author ordinary and ASan/UBSan cold metrics agree: 32 publications,
58 I/O failures, 60 total failures, 294 quiet refusals and 19,370 checks per mode.
Positive cold/request composition retains the same actual root, Node, Owner,
Session and permanent child for zero/no-op/refill/read: four recoveries, eighteen
mutations, fourteen no-ops, four foreign-workspace refusals, 584 compared bytes
and 1,807 checks per mode. Root reverified both runtime freezes, sixteen actual
compiler closures, four normal-access freestanding compiles, twelve private
denials and three additional private-retirement compiler closures/denials:
4,156 dependency occurrences. Independent successor review remains required,
including discarded retirement Status and unmatched-anchor branches. Fresh
ten-profile Debug/Release compilation of this repaired source passed all twenty
cases in `sdk53-mounted-retirement-profile-compile-v1/attempt-01`, result
`229138423d6bf40c8d2050e149e5afa3f7ffc9dd7402fc9bb1a0f6155550d2f7`.
Integrity review verified twenty actual normal-access compiler closures and
3,660 dependency occurrences. Debug uses the recipe's forced O2. Individual
frames and compilation do not qualify complete production call chains,
standalone Kernel, exported SDK, OS consumers or guests.

The next production boundary design is
`sdk53-mounted-production-storage-design-v1/DESIGN_V1.md`, SHA256
`5673fabc76290c93d1f8fe166bfb4ee7bf0afcf470db7907232e4c178a711776`.
Actual Owner admission permanently borrows its first typed child workspace:
cold recovery and subsequent requests must use that same workspace address,
while keeping cold and mutation operation objects distinct and off-stack. The
design also requires explicit genuine cancellation before any nonempty-write
legacy fallback and single-Session ordinary/typed/legacy startup selection.
Independent design advice is sealed. This design neither enables a public
route nor inherits product acceptance.
Independent advisory review identifies a concrete prerequisite: the existing
legacy startup entry requires untouched native counters and cannot follow a
typed locator on the same Session unchanged. Design V2 therefore specifies one
common opening/union reservation before READ1, an authenticated private transfer
of the actual five-read locator endpoint to the typed Attachment/cursor, and
unchanged legacy continuation for the other families. No counter reset, Session
reopen or report-based fallback is permitted. V2 SHA256:
`38b27c92cfb38292a1f442c7ba52e2ce9283000c714e250e5d4df90b08f3205b`.
Source-derived advice includes all seven route families, root continuation,
locator once and final journal admission once. The conservative union reserves
58,811,342,498 READs, 120 WRITEs and 64 FLUSHes independently in both attempted
and completed counters. The ordinary route dominates reads; typed G4 routes
individually fit u32. Native 32-bit accounting must refuse this complete union
before READ1; at least 36 read-counter bits are required. Advice result:
`bb734ef51551346282a43261db539160f6ee80e3fa691c9503f685b7901ab9df`;
integrity result `26392234263bdb201279078c539c4cbd1c2574f8dfea021975f5bb1c6233a23d`.
The u64 accounting design and ten-profile Release inert ABI/layout probes are
sealed. Native32 reports grow by 24 bytes and BlockSessions<4> by 96 bytes;
the five native64 layouts are unchanged. These are candidate-mirror measurements,
not implemented-successor layout qualification. Actual counter migration is
active in `sdk53-wide-session-io-accounting-source-v1`, with export/install
prohibited until a coordinated ABI revision and complete artifact validation.
This private common-opening bridge still needs counter implementation,
authenticated endpoint adoption and independent acceptance before public
storage/dispatch can be enabled.

Target callgraph preparation is terminal: twenty profile/mode cases, sixty
actual compiler closures and 6,520 dependency occurrences. Combined result:
`b0d6b0a9f36d27b3ead19762ee277688ab0f4e7a911d0cb4f9ac9304ef4293ea`.
The largest individual frame is 15,008 bytes; unresolved and indirect edges and
an actual startup-reclaim SCC remain. Two Debug auxiliary disassemblies timed
out. These inventories do not qualify complete production call chains.

A separate OS-only Virtio TX submission candidate is frozen in
`m6-virtio-tx-submission-source-v1/source-review-attempt-01`, result
`39ac6c1227e23347324a9810090b62cce25d2480e66ed60085326340c79adbed`.
It implements immediate copied submission, bounded completion reaping and
CPU-owned credit accounting, with no Kernel source delta. Independent review
accepts only the preparatory serialized source and safe hosted scope:
`m6-virtio-tx-submission-independent-review-v1/disposition-attempt-01`, result
`93682b9c2a80673c04a187e69a6b4f5f3a5e513f5c738f93897befe75b805dfd`.
All 40,320 completion permutations at budgets 1-8, interleaved hole refills and
genuine model u16 wrap passed ordinary/ASan/UBSan; 22,844,133 ledger checks per
mode. Root verified fifteen independent closures and 1,817 dependencies.
Root receipt `23d22a6dfd47ee7c1f74b3851a2a684ccdc2e83941881d64ec6aae954566e96b`
does not select the source for the integrated product. Model completion tests
and a normal-access SDK50 x86_64/debug consumer compile do not establish active
NIC/DMA, guest packets or connected-host support. Full consumer/device validation
and recomposition with the eventual admitted storage successor remain required.

The earlier published-cache leaf grants no suffix or mounted authority by itself.
SDK53 is unexported/uninstalled; installed
SDK50/ABI49 and accepted SDK41 remain unchanged. All ten architecture profiles
are preserved. Full M0-M12 remains incomplete; physical M11 and manual M12 remain
user-deferred.

## Earlier private composition and accepted budget leaf

A named private composition now combines the accepted mounted v4 base, canonical
Owner prefix/recovery successor and inert typed-route budget. It retains the
exact v4 actual Node/context/Lease role and all six associated implementation,
documentation and test files; older Owner files cannot replace or delete them.
Twenty-eight Owner differences and four budget additions are individually
selected by path, hash and mode. All 1,898 source files match the selection
manifest. Composition receipt:
`sdk53-mounted-typed-composition-source-v1/composition-attempt-01`, result
`896cb0be0960a0c3fbf21064abc06375e98fd37a95aacb98e0f0430d1d3700b8`,
freeze `a45b2430e789e3bcc54d3eb4764f23408c514ede89b7f38e61ed5012f6e86c2f`.
This preparation enables no mounted typed route. Legacy and renewal leaves
are not selected yet. All seventeen hosted compatibility suites pass in both ordinary and ASan/UBSan
modes: fifty xmake commands. Root verifies all 2,450 capsule members/modes
and 84 actual compiler dependency closures. Result
`9e4a900a7b3f40af3333f4a52c8fd1eb99805192dbbde90e55537732427b03c9`,
freeze `7284f53c5aeb37ce6e6ae0d78829b173caae3df7ba7676221afb945853053241`.
This is hosted compatibility only; no mounted typed runtime is enabled. A single x86_64 Debug standalone Kernel
build and QEMU boot pass, with the debug marker and 66 reported test points.
Root verifies all 1,414 capsule members/modes and the explicit ELF class/machine.
Probe result `5cfd3beefa3df2dff791cd1ea8e486ba730e24b83b6b9c887ad5bd676dbad0f4`,
freeze `8ba66ced02107a8dc8dfd0697e1cbcbad8fe56a592ee6f962f2af89808f422f1`.
It executes the existing standalone boot path, not a new mounted typed route,
and does not supply the remaining nineteen profile/mode or OS consumer gates.
The initial cross-platform phony-target toolchain configuration failure is
preserved; the successful probe uses the project's normal Linux build platform
and explicit freestanding cross compiler. The first hosted runner omitted
required fixture arguments; its successful build and failed harness invocation
are preserved as attempt-01, not passing execution. Attempt-02 corrects only
the runner and uses three exact pinned media copies.

Canonical Owner prefix/recovery source paths are independently accepted in the
exact forwarding successor. Both independent ordinary and ASan/UBSan runs pass
141,023 checks, including 900 prefix boundaries, 60 prefix READ faults,
12 foreign-prefix controls, eight optional Hook controls, 1,404 delegated
recovery boundaries and 10,628 retirement controls per mode. Review:
`sdk53-owner-prefix-forwarding-independent-review-v1/attempt-02`, result
`dac0ad86ccd6d5c439c05490bb3155e08bbe22fb64c01f6ad84e573161e72a85`,
freeze `b033e78b34fa37d52fdebbfc56b518e41423037089cacdbedbba59bc293bc364`.
Root verifies both review capsules (3,850 and ten members/modes). Owner V5 stays
rejected. This acceptance permits continued private work on the exact canonical
paths; mounted integration, full repository/target suites and SDK installation
remain separate gates.

The exact legacy source-v10 review requires revision. Static review found the
missing continuing non-reclaim selector and original direct-READ workspace
attachment. Rejection:
`sdk53-legacy-active-startup-independent-review-v1/attempt-01`, result
`d3f851c868de19fb7e7edd495d4881a97312863c3899c7a54b2778924e67c7ae`,
freeze `2dd88ec4c689e02888cab02ee203cf8c09b299be68dafc350daec2f669a24ed9`.
A separate successor in `sdk53-legacy-original-route-source-v1` changes only the
startup port and its retained legacy model. All twenty-six ordinary and
ASan/UBSan commands pass with 48 new route/workspace controls and 204,100 checks
per mode. Frozen source:
`sdk53-legacy-original-route-source-v1/source-review-attempt-01`, result
`29be76d10fa1ad6de6dd9d517554a76913bb94d0f3364f8859301134b9881f71`,
freeze `5be2949db8f51c8aae480a0f9ec71339a971aaa400866beb28d70372b9cb2b6a`.
Root verifies 1,914 complete members/modes. The exact successor is independently
accepted for its original-route scope. Twenty-six independent commands pass,
with 512 integrated controls and twelve actual caller-Pin controls per mode,
plus retained strict mixtures/refusals and production access-control compilation.
Review: `sdk53-legacy-original-route-independent-review-v1/attempt-01`, result
`b2d1ed960f2b874a3ec17266d057406665e67958a9b4f687e22799243073c87e`,
freeze `67cc25192002618d19aa30ad2f67464f604e30134c2d0ad600aa11e955b2ccb0`.
Root verifies all 2,136 review members/modes and 511 directory modes. Root
acceptance receipt SHA256
`41279c403af7b067cbfed6c521a9f33d0f36af450d0d20841633fd4ba2378f7f`.
A separate named legacy composition is being authored, preserving the typed
Owner and explicitly resolving its shared startup-port admission check. The
initial composition remains unchanged. No mutable source is substituted into
an accepted composition.

A new pure mounted typed-route budget implements checked u64 sums/products,
full classifier/eight-slot Owner prefix/child/suffix reservations, all six
attempt/completion counter checks, sequence refinement separated from cold
counter reservation, fixed startup G4/F32768 refusal and zero-WRITE/FLUSH no-op
capacity. All eight actual-input-bound ordinary/ASan/UBSan commands pass,
with 38,656 checks per mode: 5,010 counter controls, 40 sequence controls and
32,800 attempted-directory-prefix controls. Frozen source:
`sdk53-mounted-typed-route-budget-source-v1/source-review-attempt-01`, result
`ffc50936db9c44c2cfa586219298f66d45904f154edf9fe83e1285f5562e991f`,
freeze `7c41c6af0407976087a113cb1ffe181a811a39c5bd7c37f6352546d82c3243e4`.
Its first input-capture harness schema failure is preserved separately; no
compiler had run. The exact inert leaf is now independently accepted with no
material findings. Eight independent commands pass; ordinary and ASan/UBSan
each pass 1,673,115 checks. The probes retain access control and cover all four
unsigned counter widths. Final independent disposition:
`sdk53-mounted-typed-route-budget-independent-review-v1/disposition-attempt-01`,
result `77dc3582fe3f2f38d9d1442b6664683be98a145b8ce5c35ec1b9e01cf2af085d`,
freeze `0188f5b765375c17c128b0433b7424a34a94ebc94e762a40fa320d6acf83f1c0`.
Root verifies the source, both independent attempts, disposition and cross
capsules: 18, 22, 62, six and 385 members/modes. Root scoped acceptance receipt:
`sdk53-mounted-typed-route-budget-source-v1/ROOT_SOURCE_ACCEPTANCE_V1.json`,
SHA256 `1a898adb6658dc1f27ecd903c97c469aaea6664d9fde8c7a552ebf0297d95013`.

The exact budget leaf also compiles with access control intact for all ten
Kernel architectures in Debug and Release: twenty cases, forty xmake commands.
Root verifies all 385 frozen campaign members/modes and explicit ELF class/
machine identities. Single recorded compiler frames range from zero to 480
bytes; i386's 48-byte wrapper is correctly recorded as dynamic,bounded. An
initial overly strict metadata assertion is corrected without recompilation.
Campaign: `sdk53-mounted-typed-route-budget-source-v1/cross-attempt-01`, result
`6c12fa689aa5b6bd7d09dc3631d994ed32e761c036dbecf630e40ee2e9f47e93`,
freeze `c82f521b9d993affcdadc3a95b309b9408257c42d7f2500f46500948f516703d`.
These are leaf compiles and hosted arithmetic, with no transport or mounted
admission. They do not qualify the standalone Kernel, target call chains, SDK
consumer, actual maximum-epoch no-op or safe workspace renewal.

Safe typed-workspace renewal was frozen separately from the exact accepted
Owner source. Its independent review rejects the original anchor and early
max-serial quarantine gaps. Fourteen commands reproduce thirteen integrity gap
controls per mode in both ordinary and ASan/UBSan; 252 selected/unused child,
preview and exact-terminal sticky controls pass. Review:
`sdk53-owner-workspace-renewal-independent-review-v1/attempt-05`, result
`25c026e4b4c7cc3c4a73a9449efe6b21c242ee58634b866aa7b89dba247c46bf`,
freeze `09f0e83bec788814ebdcd03621974694103594c70d6ae73f0c04c5c0bc558ec4`.
Root verifies all 2,028 total members/modes and 388 directory modes. The candidate
is preserved and unselected; a separate anchor/integrity successor is active. All sixteen ordinary/ASan commands
and 26 exact compiler dependency closures pass, including production access
control. The new model passes 2,369 checks per mode, seven renewals, fourteen
refusals, 25 sticky controls and zero callbacks. Root verifies all 1,927 capsule
members/modes. Frozen source:
`sdk53-owner-workspace-renewal-source-v1/source-review-attempt-01`, result
`c5433c72d4b43876b1ded9d4ca6b598a7be89cbfaaaffc15a299f3955b133190`,
freeze `0b2bf5017a0793c4740f2f6b3342d678e33c0e54e5e38f074a4542c7d8157b86`.
The permanent actual workspace/Owner/Session binding,
private operation serial and exact child-terminal Session are retained across
rearm; completed and unused callbacks must retire before subobject reuse.
The corrected additive integration contract requires a separate private,
authenticated suffix handoff before renewal, because suffix READs change the
live Session. It does not permit arbitrary intervening READs or public proof
snapshots. Contract: `sdk53-mounted-zero-refill-startup-integration-v1/
corrections-attempt-02`, result
`bcc90bdfcbf5cc29feba2c4e5d20b74be23dd653d0808d7e717789dd69d1482b`,
freeze `0c5f0f36db2da1ed83c6253ebc729cc7fa79b9f4726b9dece3b806c52e5af745`.
The actual native-Session finite READ cursor is independently accepted as a
private mechanics leaf. Twenty-nine independent commands pass; ordinary and
ASan/UBSan each pass 3,304 independent checks/402 fixtures and the 1,624-check
authored regression. Nine genuine private API denials and nine exact compiler
dependency closures pass. Root verifies all source, author hosted, independent
and disposition members/modes (29, 61, 78 and five total regular members).
Disposition: `sdk53-mounted-typed-cursor-independent-review-v1/
disposition-attempt-01`, result
`5aca9281ed397eba30153ec133f85ccb332dd65b67a29b76e08be3c555dbf812`,
freeze `981a2190d05aada861d85b2b569c1e3770c4fddd7d69887c0d91656fe818875d`.
Its actual-child proof mint remains unavailable; privileged suffix mechanics
controls do not establish mounted or child authority. A separate strict-terminal completed-child ownership snapshot prerequisite was
frozen for independent review and is now rejected for the validation-order defects
recorded above. It remains unselected. Ordinary and ASan/UBSan each pass 25,604 checks
across ten actual native-Session/child fixtures, including 10,240 range-field
controls. All six xmake commands, eight exact compiler dependency closures and
four genuine private-access denials pass. Twelve selected new static frames
range from 32 to 320 bytes; these are not a whole-call-chain bound. Root verifies
27 source-capsule and 77 final hosted members/modes. Source:
`sdk53-completed-ownership-snapshot-source-v1/source-review-attempt-01`, result
`2d602653e981c1dfb0c0c4004e7b89aca5c6c2ea167939d23d853579c05f0f30`,
freeze `cc4ccb1f464c9bed174956b112d480bb1756967e92feb992ce67f2a91df91cb9`.
It retains strict child-terminal Session equality, actual selected const view/
Reader/target proof and every declared decoder/group/range field without new
friendship. It supplies no mounted admission, suffix permission, published cache
snapshot, operation-serial receipt or sealing of drift before capture. Those
remain work for the authentic handoff bridge; independent leaf review is pending. The renewal source is independently rejected for the original workspace-anchor
and unsealed max-serial quarantine gaps; the separate integrity successor is
active. Five snapshot harness/compiler/link/model attempts remain preserved.
Both modes passed on attempt-06, but four syntax-only private probes accidentally
added stack-report files inside that already frozen output directory. All
original frozen member hashes/modes remain unchanged; the membership finding
is retained separately and fresh identical-source attempt-07 passes. Isolated private-controls-attempt-02
also passes and verifies the complete final hosted capsule remains unchanged. No immutable-capsule acceptance
is based on that changed-membership attempt.
All rejected sources, failed/incomplete campaigns and original
media remain preserved. SDK53 is still unexported/uninstalled. M0-M12 is active
and incomplete; physical M11 and manual M12 remain user-deferred. The candidate
notes below are historical evidence and are superseded by this current disposition.

## Historical frozen legacy and Owner read-forwarding successors

Legacy startup source-v10 now passes all 26 actual-input-bound ordinary and
ASan/UBSan commands. It retains the original mounted Owner/cache/Session and
unpublished root through first-data, next-data, create and rename recovery.
The direct dispatcher now forwards exact in-flight checks and rechecks scope
following external hooks. Its deferred canonical-pin guard validates the
original Session/workspace, loading slot, generation and actual Pin before
and after geometry and physical READ, before completion credit. Each mode
passes 185,944 checks, 24 geometry drifts and 24 canonical drifts.
Frozen capsule: `sdk53-legacy-active-startup-source-v1/source-review-attempt-01`,
result `c4aa36403a759aa74990aa4eec23936219e9c39eb17f6706276791da733fde67`,
freeze `f5d067eec12061d239e010d24757cb5795ba63e609e48e6108d198ba2d8397fb`.
Root verifies all 1,922 members and modes. Exact independent review is dispatched.
The preserved source-v8 sanitizer build timeout and source-v9 test expectation
failure remain failed campaigns. They are superseded by the frozen source-v10
pass, not reclassified as passing.

Canonical Owner V5 is rejected overall by its independent review. Its repaired
delegated recovery passes scoped tests, but the inherited resident-prefix
dispatch omission allows physical READ and completion after authority drift.
All 108 independent cases per mode confirm that gap. Final rejection:
`sdk53-canonical-typed-owner-independent-review-v1/attempt-09`, result
`b6f50e0547919027226e2cdb1fbdf7376c052773922a3c8473c4ef2708682cea`,
freeze `c470e50a38093b3e9efe81b36ae795a53d063bffc9676c4feefa9d21b3a636d8`.

An isolated root-authored prefix successor repairs only that forwarding method
and adds retained model coverage. All 84 ordinary/ASan/UBSan commands pass,
including 324 pregeometry/physical/postgeometry controls per mode. Frozen source:
`sdk53-owner-prefix-forwarding-source-v1/source-review-attempt-01`, result
`442b6ca6c0b096bcf0381959ed773bba5ab8cfd4efc957cbe1fc35c04e79fac1`,
freeze `0f36affabe87a7661bbe8510aa8a670033a763974a97167de32bb2d8ae51adef`.
Root verifies all 1,985 members and modes. Exact independent review is dispatched.
Neither author pass grants source composition, SDK export, installation or native
acceptance. The separately authored direct-read successor's active-startup
sanitizer timeout remains incomplete; the exact selected test files pass in the
root source-v10 campaign.

The frozen mounted-route preparation needs the recorded static budget corrections:
include the first attempted failing mapped directory block, require the actual
continuing child ownership proof, preserve delegated-preview failure accounting,
check wide arithmetic and all six counters before classification, and reserve
cold-start counters before authenticating sequence at journal head READ4.
3616 is a conservative G4 no-op reservation. Startup remains fixed G4/F32768;
G32 startup totals are hypothetical. Maximum-epoch no-op admission and safe
workspace renewal remain new implementation work. M0-M12 is incomplete, SDK53
is unexported/uninstalled, and physical/manual acceptance remains user-deferred.

## Historical private ext4 implementation and review follow-up

The current legacy-startup leaf preserves the original mounted Owner/cache/Session
for first-data, next-data, create and rename journal recovery with permanent
startup storage. It compares all 104 home mixtures against the inherited strict
route, preserving legitimate refusals rather than accepting every mixture.
Source-v5's eight hosted commands passed, but independent static review found
missing WRITE/FLUSH dispatch authority. Source-v6 repairs that gap and its eight
ordinary/ASan/UBSan commands pass; the later independent READ finding still
supersedes that author result. Source-v7 adds the missing direct dispatcher
in-flight forwarding and external-Hook recheck. Its eight commands pass, with
24 geometry drift controls; actual legacy READ6 refuses before transport with
five physical READs and zero WRITE/FLUSH. These are hosted source facts, not SDK,
native, installation or complete-startup acceptance.

The source-v7 campaign is
`sdk53-legacy-active-startup-source-v1/hosted-attempt-07`, result
`baae98056a5b2815ce6530c446b680031101f55c40bfccfc38cb081d42fc3c91`,
freeze `b4f8c2623697b64b59d4205f2776807f454f382fc9b57e2f92e5a959f7270af8`.
A separate static review also identified the inherited post-recovery canonical
miss fallback: StartupPinReadGuard lacks in-flight dispatch authority. Source-v8
supplies an anchored call-only guard for the original Owner/Session/workspace,
selected route, loading slot and Pin, with deferred begin outside the cache lock.
Its ordinary legacy suite passes 173,776 checks, including eight canonical-miss
drift controls, and all seven inherited mounted suites pass. The full sanitizer
campaign and exact independent source acceptance remain pending. Direct-read
test successors are separately preserving physical-attempt versus completion
accounting and exercising optional external Hook boundaries; their qualification
is still running. No mutable successor is selected into an installed build.

Canonical Owner source-v4 exposed a guard-retirement assertion and remains
preserved as failed. Source-v5 retires both selected and unused child/preview
slots after successful handoff and passes all 82 ordinary/ASan/UBSan commands.
Its exact repaired capsule is
`sdk53-canonical-typed-owner-source-v1/source-review-attempt-04`, result
`05d0881f5ac8a0db823bc25f2fedb54d4e92141a17fcf4b8b9136f2feb675fb6`,
freeze `75b78344c95741169a2d99a55b191f95f9708e4d724218f9fde0a4868814dd00`.
Independent review is pending. The inherited missing direct READ forwarding also
exists in this capsule's Owner resident-prefix helper; its scope must be audited
before any complete Owner or composed-source acceptance. Existing rejected v3
results and failed v4 remain authoritative historical evidence.

All four finite V2 recovery campaigns have actual terminal passes: each supplies
72 build/media/capture/semantic stages for nine A/R pairs at cuts38/42/44.
The separately reviewed read-only collector binds all 288 stages, 72 actual
native captures, 504 owned stage receipts and 72 whole 32 MiB semantic proofs.
It rehashes complete original forests and individual pins before/after, binds
family0/family2 R compilation to the actual A classification, and preserves the
four failed V1 captures, stopped campaigns and previous p36 checkpoint. Result:
`build/prototypes/sdk52-finite-remaining-v2-checkpoint-source-v1/root-checkpoint-attempt-01`,
result `381153b754518e18b454e3b2e7a459ba4de94f6e41dd32a179bc107bb2ed1314`,
freeze `589e8d106382dbf5ff75bbe23069ae7540f4d53ad9c8913bc234415ceb8cc5c2`.
The collector itself starts no compiler/guest or admission. Its source-v1 review
passes 1,580 inherited/author controls and 241 independent inert controls:
`build/prototypes/sdk52-finite-remaining-v2-checkpoint-independent-review-v1/attempt-01`,
result `3391503f69626a1c1d22257cf198425ae7c381a0ad7f7bacc0dc72efa4962760`,
freeze `a23a418ef2f4981e23b937e31ee8dc489d09dbec9f2cef80cd97ecd0d18cf3f1`.
The exact accepted successful source-v1 route is used. Its failure report has a
recorded historical p36 diagnostic label; a separate frozen source-v2 fixes only
that label and its fresh hosted-output path, passes all 1,580 author controls
and remains pending independent review. It is not substituted into this
checkpoint. The completed campaigns and collection do not install/promote SDK52,
qualify failed-FLUSH durability, physical hardware, SMP or exhaustive M4.

The allocated-empty first-block planner has a separate source-only companion
witness capsule. It stores the exact original 256-byte inode, reconstructs the
four before homes by checked inverse allocation, and requires byte-for-byte
canonical regeneration with the retained inode bitmap. It preserves the old
64-bit version and rejects exhausted versions. Whole old/after home hashes,
JBD2 tags, escaping, UUID, sequence, fixed fields and padding are checked. The
mixed-home classifier covers all sixteen exact old/after combinations. These
image facts do not provide transport, ownership or recovery authorization.

The final actual-input-bound ordinary and ASan/UBSan runs pass fourteen xmake
commands: 240 positive checks, 10,422 refusals, 1,920 exact mixtures, 2,040
repaired-descriptor corruptions and 8,192 repaired-after-image drifts. Inherited
allocated-empty, first-data, next-data and zero-truncate planning regressions
pass. Leak scanning is disabled. Host compiler encode/decode frames are 144/224
bytes; full target call-chain qualification has not run. Frozen source:
`build/prototypes/sdk53-allocated-empty-witness-source-v1/source-review-attempt-01`,
result `fe8b923fa8731ba71c0397812b586a0ee67149c5baef5916db74677bd4e6ced9`,
freeze `9d1c63e2d8bbcf4e7e71a0af1bbd3e6b188aef84326c547ad29c1ca47b7eb724`.
Its planner parent is independently accepted for continued private source work.
Ordinary and ASan/UBSan repeats pass 450 author positives/62 refusals and 154
independent positives/476 malformed-image refusals/27 overlap refusals. Root
verifies all 1,933 review members/modes. Review:
`build/prototypes/sdk53-allocated-empty-rewrite-independent-review-v1/attempt-01`,
result `eb18100b966a6db0f0566d1b9723168404ee6c0326c39d201dfe9c01e34106da`,
freeze `9e6480c4b7d4ad035cdec758a3d0704c27ae1ca93d5f56ea778f7c297d58adb1`.
The companion witness is independently accepted within its pure-image scope.
All fourteen author replay commands and six independent ordinary/ASan/UBSan
commands pass. Independent controls add 108 positives, 1,728 mixtures and 83
semantic/geometry/candidate/alias/counter/classifier checks per mode. Root
verifies 1,970 frozen members plus FREEZE and all recorded modes. Review:
`build/prototypes/sdk53-allocated-empty-witness-independent-review-v1/attempt-02`,
result `10fc50cae21179b662575352272125137acdab592a4f955524d0f53e4a87a41a`,
freeze `defac7e1ffdc0124d7cae417fded98fa62267ebee7248371077bb575daf70a94`.
Reviewer harness failures remain distinctly preserved. The inherited public
fresh-first-data convenience planner has a separately recorded alias limitation;
the new allocated-empty call path uses disjoint guarded scratch and does not
call that convenience API.

Independent slice4 review found stale final original-Session observations after
one of three retained anchor pointers drifts. The original Session is correctly
quarantined/drained and the foreign Session remains untouched, but requiring
all three anchors to agree prevents final report refresh. The six reproductions
are preserved separately and are not passing acceptance:
`build/prototypes/sdk53-zero-truncate-slice4-independent-review-v1/anchor-observation-probe-attempt-01`,
result `9c20906f7006fa3cdfce3934534f1f7d2b61c9eb123db76e170e2a70ca642e6a`,
freeze `b1cceb6347b48114b7f7fed80c0af1d1915fab70431f1d8442254d054e3ab392`.

A fresh repair capsule adds an anchor-owned rejection observation that captures
the agreed original once for both abort and final readback. Strict dispatch
admission is unchanged. Ordinary and ASan/UBSan runs pass all twenty-six xmake
commands, including six exact final observations per mode, foreign-Session
preservation, the inherited formatter/preview/ownership/planning suites and
32-group/128-record/1024-directory-block models. The local guard tally is still
explicitly incomplete after integrity failure; final Session counters are the
transport observation. Repair independent review has passed for the declared original-Session
observation scope. All twenty-six author commands and six independent commands
pass in ordinary/ASan/UBSan modes; each mode adds 228 integrated cases, eleven
direct anchor cases and four no-agreement refusals. Twelve transport-error cases
are included. Exact drained final original observations, foreign Session
preservation and unchanged model images pass. Root verifies 2,020 frozen members
plus FREEZE and modes. Review:
`build/prototypes/sdk53-zero-truncate-observation-repair-independent-review-v1/attempt-01`,
result `091ee3553f4fadd1028c4001ef59faf206892df3889fbdd008f2906ac63ac21a`,
freeze `ceb3bd5e28005da0dfa8c0f98103c42b2ccdf8d9bf3b4a1bb873a78dbfceaf6b`.
Historical rejection and reviewer harness failure remain preserved. Frozen source:
`build/prototypes/sdk53-zero-truncate-observation-repair-source-v1/source-review-attempt-01`,
result `55551a95b513dcee82dbb9be18890a2495894f9f22c943e589120f8b4973d0ac`,
freeze `e0f9b32db8ac47316ec38126b320c73fd480da03cd1eb6b841a121aecbde240a`.
The historical slice4 claim is rejected by its finding, with the rejecting
review retained at
`build/prototypes/sdk53-zero-truncate-slice4-independent-review-v1/historical-source-rejection-attempt-01`,
result `8f6fe87a3ff17b73e51c6c3837a530b46a4991cab81d5b030c3f29e604c2e81f`,
freeze `437d48a85d9042796045f38bb1526b9e72d16eed2bc51d0a9b403c43a04de4ea`.
Root verifies the owned five-member forest and 11,491 inherited input records.

The allocated-empty ownership source capsule is frozen as Kernel1198 /
OS649 and independently accepted for continued private source work. It reuses the accepted complete
empty-inode/global ownership proof, captures the real bitmap/inode bitmap/table,
regenerates the proposed plan from that exact view and rechecks all five source
images at the end. Scratch, output, view, retained reader and source overlap
checks occur before clearing state. It supplies read-only candidate facts, not
writer or device lifetime authority. Sixteen hosted xmake commands pass in
ordinary and ASan/UBSan modes: 16 positives, 45 refusals, all 25 READ failures and
five final bookend drifts. Planner/witness/first/next/zero regressions pass. The
host ownership frame is 368 bytes; no target call-chain claim is made. Failed
compile/harness attempts and the earlier passing source remain frozen and are
not reclassified. Capsule:
`build/prototypes/sdk53-allocated-empty-ownership-source-v1/source-review-attempt-01`,
result `e8c9df48fcd4b068e932710a885be582ff0fbb51900bf05b3524fd645fc09349`,
freeze `2ef95d9afe79d0a481bd0983b863b0449ab8733a5f2f8a4fd5e8e7ef04da82cc`.
All sixteen author and six independent ordinary/ASan/UBSan commands pass. Each
independent mode adds fourteen positives, 8,212 canonical parity refusals,
fifteen global ownership controls, five bookend drifts, 150 failed/partial READ
cases, seven alias refusals, eleven binding refusals and six failed openings.
Root rehashes 2,004 frozen members plus FREEZE and recorded modes. Review:
`build/prototypes/sdk53-allocated-empty-ownership-independent-review-v1/attempt-01`,
result `e0e2f31fe014ccb18265db6f0c81257e1d694ed7e26a46701a3014594678cb5f`,
freeze `baec3f0197ca5363c503e321e18e3bb639ea0a9011534eee1546e0ba8144f51b`.
Failed reviewer compilation remains preserved. Caller exclusion and reader/backing
storage lifetimes remain required; arbitrary reader-reachable storage aliases
and target call chains are not qualified. Output facts remain inert.

The allocated-empty committed-journal verifier and formatter are now frozen as
a separate Kernel1199 / OS649 source-only capsule, branching from the accepted
exact-old-inode witness. They check the complete fixed-ring JBD2 grammar,
synchronous commit image, canonical witness reconstruction, all sixteen exact
home mixtures, escaped images, UUID/sequence/counter limits and active/next/empty
heads. The formatter round-trips through the complete verifier. Sixteen ordinary
and ASan/UBSan hosted xmake commands pass: 4,947 positives, 12,313 refusals,
4,656 mixtures, 2,040 repaired commits, 2,040 repaired descriptors and 8,192
repaired after images. Host formatter/verifier/parser frames are 464/224/432
bytes; target and full call-chain qualification remain pending. Capsule:
`build/prototypes/sdk53-allocated-empty-journal-source-v1/source-review-attempt-01`,
result `56210e95e6c4b47fe7d06a404aae3e259506befe1f8c251d9bcf0bef8a5e5f00`,
freeze `2cbd4e6ecb5f956c7a532bb95d801796c24f56b7b024b764b7849bf5fce2b1d6`.
Independent review passes all twenty hosted commands. Each ordinary/sanitized
independent mode adds 24 positives, 256 mixtures, 1,024 CRC-repaired commit
refusals, 1,024 end-record refusals, 4,096 third-home refusals, 177 grammar
refusals and seventeen alias controls. All 23 nonidentity action permutations
per group are refused; timestamp/sequence boundaries and unused head bytes pass.
Root verifies 1,994 frozen members plus FREEZE and modes. Review:
`build/prototypes/sdk53-allocated-empty-journal-independent-review-v1/attempt-03`,
result `09d6205e5bc88cce23403b22d73cf1c071c69d6b0f9f5c90e437e5f1d7454ce7`,
freeze `e5de29e56e38f7c18604973a206da092a0146a8d6442195f0033557150fe29de`.
Failed author and reviewer attempts remain preserved. Historical rejected slice4 is a formatter source reference only and
contributes no acceptance. This capsule performs pure image operations; it does
not provide data WRITE/FLUSH, transaction, mounted lifetime or native admission.

The exact independently reviewed ownership and journal deltas are composed in
`build/prototypes/sdk53-allocated-empty-preview-source-v1/source-v1`. The common
parent's complete source bytes/modes, both companion deltas and both review
forests are checked before copying and after composition. The only shared
edited path is the hosted xmake project, composed from the exact journal file
and ownership's exact appended suffix. Parent-copy record SHA256 is
`1645b9cb421c591f8a8e3fcee7b486d4526febf0320d3fed3dbb221f5f39f79c`.
A new one-shot read-only preview captures journal, inode bitmap, actual homes
and data bytes, proves old/final global ownership through private overlays and
rereads all fourteen captured images. All twenty actual-input-bound ordinary and
ASan/UBSan xmake commands pass, including companion regressions and explicit
freestanding template instantiation. Each mode passes 64 positives/mixtures,
302 exercised READ failures, fourteen changed bookends, 328 permanent-claim
controls and thirteen structural/alias/global ownership refusals. One/two-group
traces consume 58/70 READs. The hosted prepare frame is 240 bytes; no target
chain qualification is inferred. The final source is Kernel1207 / OS649:
`build/prototypes/sdk53-allocated-empty-preview-source-v1/source-review-attempt-02`,
result `85046681e8ae477192a666c8a66807f05f3241f77138d08a94db40003ffcb9ff`,
freeze `7729e03f1aa5e6cefaf4d6f1f93532cde5aeece318b27d90df05c8da514b047a`.
Root verifies every frozen member/mode. The first capsule's text xmake diff
used the journal file rather than the composed before image; that packaging
diagnosis and immutable capsule remain preserved. Attempt02 asserts the text
diff's old bytes equal the composed manifest; source and hosted compiler inputs
are unchanged. Exact attempt02 preview is independently accepted in
`build/prototypes/sdk53-allocated-empty-preview-independent-review-v1/attempt-03`,
result `45bc623cc65f8cbdd809f12dc6a99c2feef1d1fe54465a178126cfeb9135736a`,
freeze `eaf79e10418822b0184bc6ee33ebfa2ad875cdc1df232c03cc9f9e28a7a07df0`.
All 26 actual-input-bound ordinary/ASan/UBSan commands pass. Per mode, independent
controls cover 432 positives, 2376 failed or poisoned READs, 42 bookend changes,
301 grammar/binding/third-home refusals, 97 old/final ownership refusals, five
aliases and 5627 permanent claims. Traces are 58/70/70 READs, including inode269
in the second group. The complete conservative bound `2876 + 1062G` is derived
independently. Root rechecks all 2032 review members and modes. Reviewer attempts
01/02 preserve an unused-variable compiler error and an inert checksum mutation
that restored its original bytes; neither is an author-source finding. Reader
and reachable backing-storage lifetime, exclusion and disjointness obligations
persist. No Session wiring, mounted writer, target/guest execution or SDK export
is claimed.

Typed zero-truncate transaction has an English design and versioned API notes
in `build/prototypes/sdk53-zero-truncate-typed-transaction-source-v1`. Its final
source is frozen from the independently accepted observation-repair parent in
`source-review-attempt-01` as Kernel1199 / OS649, with eight Kernel deltas and
unchanged OS source. The historical source-v5 copy is unchanged. Fresh and recovery paths require the
exact retained original Session, private owner admission and complete route
counter reservations; inode checkpoint plus FLUSH must precede allocation
homes. Design bounds are source planning, not native qualification.
The final typed transaction capsule passes thirty ordinary and ASan/UBSan
hosted commands. Each mode passes 56 positives, 528 refusals, 408
transport faults, 58 retained-field changes and 518 capacity controls. The final
author fresh READ reservation is `5849 + 2124G`; the earlier proposal's `5836`
constant remains preserved as historical design. Recovery/no-op reservations
are `4351 + 1593G` / `1446 + 531G`. Fresh WRITE/FLUSH reservations are 13/6,
recovery 5/3 and no-op 0/0. A pre-seal static audit found omitted local failed
attempt accounting; the final source fixes directly dispatched exact failures,
while API_NOTES_V3 documents failed delegated-preview tally limits and retains
the authoritative original Session observation. The original finding and all
earlier attempts remain preserved. Final result is
`9f50be4fe0277687a8697102845a6416246937e1f710be4599e7b8fb92d1fba2`,
freeze `f58d9515502d21051a815e26db5eb61e34b675026160861377222b20817c29db`,
manifest `84752e9521603a61dd2f46cf815cf9d4cd95b8889c29e8d59864adbf8d8fda21`.
Root verifies all 1880 listed members using both `files_sha256` and `file_modes`,
plus FREEZE identity and exact membership; the read-only receipt is
`ROOT_FROZEN_REVERIFICATION_V1.json`, SHA256
`8c31f80dc2c9c78df1cbdc52239329c00157bdc8a28c4308a7b01436b410840b`.
Exact typed transaction capsule is independently accepted in
`build/prototypes/sdk53-zero-truncate-typed-transaction-independent-review-v1/attempt-04`,
result `c3a25d1f814bf377a7c6eefbe3e91fc3d312e001327976ef6f7c5621b67c47cd`,
freeze `028ef58afa659d49c69e001555cada70a09165595bbbe9924fe2be633b43b871`.
All 42 ordinary/ASan/UBSan xmake commands pass. Each mode adds 5953 independent
hostile cases: 44 positives/equivalents, 5074 boundary refusals, 816 whole/partial
transport faults, 1404 authority/report substitutions, three exclusions, 1126
budget controls and eighteen inter-stage refusals. Twenty complete maximum
scenarios exercise 32 groups, 128 allocated records, 1024 root blocks, four
cross-group peer extents, sixteen released mappings and all recovery mixtures;
the maximum actual READ count is 6204. Reviewer attempts01-03 preserve a private
visibility compile error and corrected harness assumptions about manually forged
idle in-flight flags and WRITE acquisition's pending-write normalization. Root
verifies the exact complete review forest, including 2061 listed members plus
FREEZE and all modes. No blocking source finding exists in the private serialized
scope. API_NOTES_V3 and caller exclusion/lifetime obligations remain. Neither
these models nor unchanged hosted layouts qualify target stack chains, mounted
execution, export or installation.

The exact two independently accepted forests are now composed as Kernel1219 /
OS649 in `build/prototypes/sdk53-allocated-empty-session-preview-source-v1/source-v1`.
All six shared-file selections use exact accepted whole-file bytes; 20
allocated-empty-only paths and all typed-only paths are retained. Before/after
verification covers all four source/review forests and modes. Parent-copy record
SHA256 is `52caf60c57f29c61a3d24534780e9304d4af30fc6bff0c2d60cc9d055cee9834`.
A new noncopyable read-only Session adapter is implemented and frozen as
Kernel1223 / OS649 in
`build/prototypes/sdk53-allocated-empty-session-preview-source-v1/source-review-attempt-01`,
with five Kernel deltas and no OS delta. It has complete `2876 + 1062G` READ
reservation, guarded original-Session dispatch, minority-anchor-safe quarantine/
final observation and overlap refusal before mutation. All 52 actual-input-bound
ordinary/ASan/UBSan commands pass, covering both families of inherited models.
Per mode, the new adapter passes 208 positives, 512 exact/partial READ faults,
64 retained-state/bookend changes, 237 budget controls, two overlap-before-mutation
controls and one grammar refusal before home reads. One/two-group traces are
58/70 READs; all adapter attempts issue zero WRITE/FLUSH and preserve the medium.
The host prepare frame is 512 bytes; no target call-chain qualification is
inferred. Final review input is
`257cd32b8080a9fcf965d1a1def4ca9bf783ea72f18e28d307b7303c468072a9`,
result `dbd8897a69e58db9933994db12a9b6214d5a98ad31a36ca5bb098b574843e6af`,
freeze `e9bf7abc08cceef470985cc365fc650ce507dce525132f7343365cd08e00c40e`.
Root checks all 1938 listed members plus FREEZE and all `file_modes`; receipt
SHA256 is `7d969cd9ab8cb2f0cce61f4bcb82e8e4561e3a67079172081a41bc83019e88e7`.
Exact independent source acceptance is now frozen at
`build/prototypes/sdk53-allocated-empty-session-preview-independent-review-v1/attempt-01`.
All 64 ordinary/ASan/UBSan xmake commands pass: 52 inherited author commands and
12 new independent commands. Per mode, independent coverage includes 867
positives, 2376 exact/partial READ faults, 42 bookend drifts, 141 retained-field
mutations, 271 capacity/stability controls, 14 early refusals, three aliases,
three foreign runtime callbacks and 45 authoritative Registry report/Session
geometry/bounds drifts. Original final observations are exact; foreign report,
abort, geometry, bounds, transfer and transport calls stay zero. There are no
material source findings. Result is
`8b08558551f80843c9a94b693a3fecbffb425522458a9de8e7a6db13cfb5b54b`,
freeze `991b21236b867999b5128e937036f69079ee0679eba660c06b7f936d485497d6`.
Root verifies all 2261 members including FREEZE and all modes; receipt SHA256 is
`9ec9f9df015e9166ac71e4d98578566802b79e3bc1864d9a2887f61ec61c27b5`.
This accepts only the private source scope, retaining caller exclusion/lifetime
obligations; it grants no mounted writer, SDK, target or guest admission.

The frozen read-only mounted integration preparation is
`build/prototypes/sdk53-mounted-integration-design-v1/attempt-01`,
result `be32965abd58e35fcb618f0bbbafb4c34db36c41f04a4a192382be6a04ca231b`,
freeze `928779fcf856c27c5eb375891acc8b2816479c3992af9552eb87e2531e0f1452`.
It identifies private owner attachment, resident no-I/O cache reconciliation
while the typed child retains exact Session counters, authentic Node/root/device
holds, complete reservations, terminal handoff, both startup families and actual
target stack paths. It copies or accepts no source and starts no compiler/guest.
Ordered-data transaction preparation is recorded separately in
`build/prototypes/sdk53-allocated-empty-ordered-transaction-source-v1/DESIGN_V1.md`.
It proposes data WRITE+FLUSH before WAL and allocation homes+FLUSH before inode
publication. Proposed fresh/recovery WRITE/FLUSH maxima are 14/7 and 5/3; READ
bounds `5884 + 2124G` / `4366 + 1593G` await derivation from final implementation.
No ordered-data writer or recovery companion is implemented by this design.

The subsequent parallel author-only copy now implements the fresh ordered-data
transaction and its recovery companion in
`build/prototypes/sdk53-allocated-empty-ordered-transaction-source-v1/source-v1`.
The exact guarded Session dependency has now passed independent source review.
The separate writer candidate still requires its own review. Fresh
preparation additionally searches initialized candidate group bitmaps, producing
the implemented READ reservation `5884 + 2125G`; recovery remains
`4366 + 1593G`. Fresh WRITE/FLUSH maxima are 14/7, recovery 5/3. Full request/data
images, original Session counters and stage controls are sealed off-stack.
Data WRITE+FLUSH precedes WAL; allocation homes+FLUSH precede inode publication.
Freestanding explicit instantiation passes in the preserved exact-input
`compile-probe-attempt-01`, result
`b9526f2978042ccf9391003f1a9e75fa7f07dad6c2cce8637244de2485c6f549`,
freeze `22db47becad6dfd645f970aebb4ef542d7be58462d4158bc0d5658b0759755f0`.
The writer and both inherited model families now pass all 58 ordinary and
ASan/UBSan xmake commands. Per mode, the new suite passes 3459 cases: 220
positives, 1874 transport faults including 937 partial-copy variants, 1352
retained/interstage changes, two aliases, 3457 one-shot/admission refusals and
842 capacity controls. The 104 interstage controls are included in retained
changes. Fresh one/two-group traces are 266/284 READ, 14 WRITE and seven FLUSH;
recovery zero-mask traces are 157/172 READ, five WRITE and three FLUSH. All sixteen
recovery masks and three data sizes/gaps pass. Exact bytes, complete unrelated
media preservation, attempted/completed credits and ordered barriers are checked.
This remains source/model evidence, without failed-FLUSH durability or a data
checksum claim for recovery.

The selected clean candidate is Kernel1229 / OS649 at
`build/prototypes/sdk53-allocated-empty-ordered-transaction-source-v1/source-review-attempt-02`.
It has eight Kernel deltas and no OS delta. Attempt01 passed all author checks
but included nine local xmake cache members; it is preserved. An explicit
nine-member exclusion copied source-v2 without deleting the original. The fresh
58-command clean-input campaign also passes, result
`368f4ad60c3cf7aca10354c7ad95d472ee600b52587d720a345f01b67cadf882`,
freeze `173b6ebdfbc4e37a064b95b2511ca9d562e7ee982cb3d43a2e01e19c9645ab06`.
Final review input is
`9448a7a4612e933d70fe871640ca8e1e0254e5f6854be598aa165df8b8a5f84c`,
result `a7019d281fc7c40e74d9dbc6445e33028a6c2fdf81fdc441eadad8327225d7a0`,
freeze `052139e22355a5ed440f46d1108429834bd5ba485cb80130448ee07f4104776d`.
Root verifies all 1961 members including FREEZE and all modes, with 1878 exact
source entries and no .xmake cache members; receipt SHA256 is
`20b6c246a6c84f950ae376411db78da703c016805cccaed6b65a5cdac5af8a2b`.
The writer subsequently passed exact independent source review at
`build/prototypes/sdk53-allocated-empty-ordered-transaction-independent-review-v1/attempt-01`:
result `c6d94bbeda9468f72f129a7fd6fa66ac17b4de1221c8b183463c87e29a410fd7`,
freeze `0c833ae3990a07071c0a70fc4d2edcf1dc7afef18e94f06ee9b47a3b3f66705f`.
All 66 commands pass ordinarily and with ASan/UBSan. Per mode, separately authored
controls supply 3046 cases, 229 positives, 1874 transport faults, 916 drifts,
1208 capacity controls, two aliases and 25 admission refusals, plus 21 private
handoff and nine foreign runtime callback controls. The actual 32-group,
128-record, 1024-root-block case with inode269 in group1 and candidate group31
passes fresh 6236 READ/14 WRITE/seven FLUSH and all sixteen recovery masks at
4636 READ/(5-popcount) WRITE/three FLUSH. Root verifies all 2304 frozen members
and modes. Complete target call chains, canonical owner/mount integration and
external device qualification remain pending. Review steering selects exact
source attempt02 and retains every earlier attempt; no newest-directory glob
is used.

A separate private cache prerequisite is implemented and frozen as Kernel1226 /
OS649 at `build/prototypes/sdk53-typed-cache-reconciliation-source-v1/source-review-attempt-01`.
It seals complete cache state, validates exact old canonical images, separately
normalizes dormant staging storage, and atomically replaces or retires retained
resident entries with no transport. Unrelated slots stay byte-exact. A dormant
staged image need not equal a freshly loaded canonical image; explicit
normalization handles that legitimate state instead of misreporting corruption.
Private retirement requires an expected old image for every affected key;
future mounted prefix budgets must account for obtaining those physical bytes
before exact child counter ownership. No owner is attached by this prerequisite.
Eight xmake commands pass ordinary/ASan/UBSan: 2017 typed checks, 172 refusals,
88 drift controls and 320 existing cache regression checks per mode. Hosted
compile frames are prepare144, validate80 and normalize/publish wrappers64 bytes;
they do not qualify target chains. Hosted attempts01-05 remain preserved, with
05 selected. Review input is
`c8f791ff846ef7d82dffb44cd9224fb71f55b744f43c2755fae6fde18b6ea723`,
result `081570709fc12d6f4de38197d7e835ceb1ea63806899420e7a141c8a25d4eb39`,
freeze `f0d63815c0aed72f1826d7bcf48dfa8eee539c35ee5a026bb4e48ab6378b2812`.
Root verifies all 5650 members including FREEZE and modes; receipt SHA256 is
`e1d8b28d1a1e01f0c07edb866757d8b91c3871469770dc9e2742d3e0c485a251`.
The exact cache candidate was subsequently rejected by independent review at
`build/prototypes/sdk53-typed-cache-reconciliation-independent-review-v1/attempt-02`.
Both ordinary and ASan/UBSan reproduce sixteen missed refusals: actual Session
bounds/access/geometry and Registry owner/device/geometry/transfer drifts are
accepted at normalization and publication while the diagnostic identity stays
unchanged. Result is
`0d0c28ae9109b956543c95e3bde7408b08ebd9c1e0c094a88087e4ac9b93b916`,
freeze `8ab6c322a75399300608db70946800e3d449ea3014400af1599cbf16de142b06`.
All fourteen review commands pass with these findings recorded as rejection;
the original candidate, all compiler inputs and failed reviewer attempt01 remain
preserved. This candidate must not be selected for owner attachment.

A separate author repair now captures a no-I/O actual Session/Registry binding
at cache open and revalidates it before every private cache phase. Its private
plan seals every observation field. Cached origin, sector count, access and
sector-to-block ratio must also agree with the opening observation before mint.
Original completed child READ/WRITE/FLUSH counter advances remain permitted;
pending writes and restored terminal refusals cannot publish. The selected
author attempt02 passes twelve ordinary/ASan/UBSan xmake commands: per mode,
2017 inherited typed checks, 320 cache checks, 127 Session checks and 1614 repair
checks with 33 controls. All sixteen preserved authority findings now refuse
without cache mutation or helper transport. Passing attempt01 remains historical;
attempt02 includes independent static scrutiny's pre-mint consistency controls.

The exact repair is Kernel1227 / OS649 at
`build/prototypes/sdk53-typed-cache-binding-repair-source-v1/source-review-attempt-01`.
Review input is
`59589c097263fc62c7776280f672895dd8ff7a823d60c79b84d64d5567d4a6fe`,
result `f0a9c2615ddce200c8d74a8975da02f5071ae9c91c4254208d20d23112b6a063`,
freeze `7c23c3bbd47c7c08db3f11296fb8487728d3bb9e1234fa99c375609fae1a12e9`.
Root verifies all 5650 members including FREEZE and their modes, including both
exact 1876-member compiler source forests. The exact cache repair subsequently
passes independent source review at
`build/prototypes/sdk53-typed-cache-binding-repair-independent-review-v1/attempt-02`,
result `9b95243b6be00695d55bd80440c30203f87382996f69db9bac81aa2e91b7787a`,
freeze `0ac12b6b6c62d77c7b02b4ae624f3d8533255a006cb83657e18005ab86e45369`.
All 24 ordinary/ASan/UBSan commands pass. Per mode the independently authored
controls supply 2571 checks, 286 refusals, complete binding/alias/target controls,
zero helper callbacks and legitimate counter advances. Root verifies all 3799
final members and modes plus the preserved initial 3867-member review capsule.
This is acceptance of private source; mounted integration, native execution,
SDK export and installation qualification remain separate gates.

Root additionally runs the externally authored repair controls from exact
immutable compiler copies in
`build/prototypes/sdk53-typed-cache-binding-root-control-replay-v1/attempt-01`.
All eighteen commands pass ordinarily and with ASan/UBSan. Per mode the external
model supplies 2454 checks, 275 refusals, 66 actual-binding drifts, 45 opening
observation drifts, 30 private plan drifts, 18 cached-prefix drifts and three
counter controls, with zero helper callbacks. Result is
`801579f830d947a7c25b9073b04aa6ce7d83595379903ab98701f822adc7d93a`,
freeze `aabd55e63c8120424db9aa8815501cb1b4f20db5cdadba550e3a1294a3fb3fc8`.
The execution disposition explicitly identifies root as the repair author;
this replay is useful regression evidence, not independent source acceptance.

The separate mounted Node mutation prerequisite is implemented in the private
`sdk53-mounted-mutation-identity-source-v1` lane. It acquires an actual I/O Lease
under the mount gate, validates the original Node address/full lifetime key and
physical inode checksum/generation, and keeps the hold across commit and renewal.
Initial author tests pass all 1596 observed transport-failure positions, but
author scrutiny reproduces a combined private binding-erasure defect: eight
WRITEs occur and admission becomes readable while the actual local I/O hold
remains live before terminal refusal. That source-v1 is not accepted. Its images,
failed fixture attempts and passing intermediate runs are preserved. The author
has implemented source-v2 with an actual noncopyable local mutation context
passed through identity, commit and rejection checks. Its ordinary development
model passes 120 original-binding drifts across six phases and both operations,
all 1596 transport failures and the inherited identity/generation/capacity
controls. All 70 ordinary/ASan/UBSan commands in author attempt04 and root replay
attempt05 pass against the same exact source. The selected source-v2 is
`source-review-attempt-02`, result
`703443af746e29405f3cfafeb17d24c2b5f249179b97ceca9bc07714831944cc`,
freeze `df2596dfc08a38fd73aae21138c569c3478604ce34cba5682669e43d00e69683`.
Root verifies all 1966 members/modes and 1876 source entries. The root replay
passes with result
`6c44c68efbcdf7b9442959bfadabb3badf12b965e480f6c925fd282de7170a63`,
freeze `28a19a001896d986e9304070185e3b74e8434652090de1ce14332da2fe210f75`.
An additive correction records that inability to poll the sibling agent's
session did not establish process completion; author04 and root05 both ran to
completion and all prior records remain preserved.

Source-v2 is subsequently rejected by separately authored root admission
controls in
`build/prototypes/sdk53-mounted-mutation-identity-independent-review-v1/admission-attempt-01`,
result `30fe4053f6404bb4a8349e2f4ddc7fca81b0039f1a571e4c8808a890aa13111e`,
freeze `9e6de72e62473d009c7a59002f61d84f397657358c8490d7974e1389516fbefe`.
Both ordinary and ASan/UBSan report 19539 checks, 24 controls, 19152 original
callbacks, 12 correct baseline refusals and 12 missed refusals. Restoring the
diagnostic readable phase permits a fresh Node descriptor hold while the actual
mutation I/O Lease and original context remain live. The control acquires and
releases the new hold through public Node methods without helper transport.
The earlier static-only report is preserved; a subsequent static follow-up
confirms this gap. No mounted enablement is granted by either passing regression
campaign.

Source-v3 moves the provider-only mutation role into the actual occupied I/O
Lease slot, independent of mutable mount pointers, diagnostic phase and summary
hold counts. Its 70-command author campaign passes, but separate static scrutiny
finds that generic release could consume the claimed role and the claimed Lease
could still move. The author reproduces that defect in
`release-boundary-control-attempt-01`, result
`bd8afbc27d8816209c49e2290e12fc56a11d103b53f9833fa7a8edf8c45ea168`,
freeze `a1943e6e14612dd941c00b20890a255a686b14a316b63b0299d34f0fae962091`.
Source-v3 and its complete passing campaign remain preserved and rejected.

The source-v4 successor refuses generic claimed release and refuses movement
before transfer, preserving the original valid Lease and leaving the destination
invalid. Only provider-private terminal release with the actual original Lease
address, complete key, immutable context and epoch consumes the role. Ordinary
unclaimed reader I/O retains its useful descriptor-retention behavior. The exact
selected capsule is `source-review-attempt-04`, result
`27bbb8994b54b248035e41c47edd7435323942e4783d1c199fdf78687656e382`,
freeze `dbb459d8fb62f456befb5ac196474109dabd3f0cd4a5b596b9d317f1fc29ecd4`.
All 70 author ordinary/ASan/UBSan commands pass against its exact 1876-member
source forest (Kernel1227 / OS649). The full capsule has 1978 members including
FREEZE and six explicit Kernel deltas.

Root independently qualifies that exact source in
`sdk53-mounted-mutation-identity-independent-review-v1/selected-attempt-02`,
result `2525354db57b8c1e8087163c8596946bb1bc6f4e91ddb37ca58eacd73643db53`,
freeze `383dd88d68617d752176dfb8db571dd28dad0099807d7e2bd4c5365e1b7210f6`.
All ten commands pass. Each mode supplies 57273 checks, 96 public-admission
controls, 55354 original callbacks and zero missed refusals. Separate controls
refuse generic release, movement, different-address forged terminal release and
wrong terminal key/context/epoch without helper I/O; original terminal cleanup,
ordinary reader retention, listing, lifetime and root-retention regressions pass.
The first reviewer build fails only on misleading indentation under Werror and
remains frozen in `selected-attempt-01`; the successor preserves those controls
and adds direct private terminal-release identity checks.

Separate static review at
`sdk53-mounted-mutation-identity-v4-static-review-v1/attempt-01` finds no material
defect in the documented serialized defensive lifecycle scope. Result is
`422d76322652d2979cb3e946765dcb5b688337a0374306818fdc27d6ba44b3a4`,
freeze `9e7ddef04e57290738fdd07a1b4c1b689ae488bac8c76352a878f61ab7292a1f`.
Root verifies complete candidate, independent dynamic/static review and failed
reviewer forests/modes, both exact independent compiler copies and the original
70-command compiler input linkage. The additive source disposition is
`ROOT_SOURCE_V4_INDEPENDENT_DISPOSITION_V1.json`, SHA256
`a1ad1f19b15f830bd8652b6f5dc39cca9dcbaab5d0d52a3f541cab46163d8462`.
It accepts this private source for later integration composition only. Permanent
corruption of actual Lifetime records and concurrent SMP execution are outside
this source scope. An inherited root-reference clone is a separate no-I/O
retention interface; a refused claimed move alone does not quarantine a valid
operation. No native, SDK53, installed or physical acceptance follows.

Canonical typed owner attachment proceeds in the separate
`sdk53-canonical-typed-owner-source-v1` lane from the exact independently
accepted guarded-preview, ordered-writer and repaired-cache sources. Its
1882-member composed baseline uses 14 explicit whole-file selections. This
lane does not select either rejected mounted mutation candidate. The private
design retains off-stack child/cache workspaces, original Session authority,
explicit prefix credits and no-I/O terminal cache publication. The private owner
captures every resident canonical image physically before child counter
ownership, retains the complete allocated-data request off-stack before any
prefix callback and validates the complete outer/cache authority at every child
runtime boundary. Nonresident retirement keys are omitted only with complete
retained absence proof; no expected old image is fabricated.

Its first exact author campaign is preserved and rejected at an inherited
allocated writer transport-failure assertion: a new live binding observation
rejects legitimate post-I/O quarantine before completing failure accounting.
`hosted-attempt-01` has result
`47a6b750c6c1d3a3ec9f53f3ceaee6da8c29bc9a96ebeeaa93d8fd06a9da8442`,
freeze `1fb0168987d46f954c083cfa3112414def5df5464ebd9109c9f7bc81871c630a`.
Separate source scrutiny also requires whole workspace/owner and binding
disjointness before the first retained image copy. Source-v2 repairs both paths,
including inert authoritative terminal-backing observation for quarantine and
pre-copy no-mutation controls. Its clean ordinary/ASan/UBSan qualification is
running; the independent reviewer has prepared recovery, callback exclusion,
original/foreign failure-accounting, alias, prefix and terminal controls. No
canonical-owner source acceptance or mounted composition is yet granted.

The preserved second campaign additionally exposes original failure-report
pointer drift; its successor refreshes terminal diagnostics from the agreed
original anchor rather than a mutable report pointer. Source-v3 now passes all
82 ordinary/ASan/UBSan commands, including both fresh/recovery families, all
sixteen home masks and 34 maximal G32 ownership cases. Eighteen byte-exact alias
controls reject before mutation; ten terminal observation controls check
authoritative quarantined backing. The actual parent and delegated child failed
dispatch ledgers remain distinct. Callable owner guards retire before the local
context expires.

The exact source-v3 capsule is `source-review-attempt-03`, result
`6841e3e592d1dd5f6dcdd91b5a0a50039274ac31662da53e0ca1f41103e1b907`,
freeze `3069c178b3ef6a379fda2365bc88f298b5ba2ba943b6ac603971d4850d39c7ce`.
Review input is
`84696218d42b4fecc52ea5092392f4ec3fbfa17d9835d387f70547d009209e4a`.
Root verifies all 5731 capsule members/modes: 1889 source entries, Kernel1240 /
OS649 and thirteen explicit Kernel deltas. Independent review executes from
exact copies and separately checks production freestanding compilation/private
access denial. A reviewer fixture-name compilation collision and a delegated
recovery failure-accounting expectation are preserved as harness findings; they
do not themselves reject the source. Independent review confirms a material
delegated recovery guard defect and rejects source-v3. Clearing the original
workspace owner on the first child READ still permits 70 total READs before
terminal refusal, rather than the expected 17 (sixteen prefix READs plus one
child READ). No WRITE or FLUSH occurs. The parent passes its actual Session into
the delegated recovery preview but does not propagate the sealed outer
owner/cache guard. Root confirms the source path and records the successor
repair in `ROOT_CONFIRMED_RECOVERY_GUARD_FINDING_V1.json`. The rejecting
reproduction is `sdk53-canonical-typed-owner-independent-review-v1/attempt-04`,
result `79da56a92557ad50c8303558e24e1123934f561bf398686e4ed55e0f3bee750c`,
freeze `ecd67fc201ba5a178c41418920a873a38c093b2c0607caca0ee7a8c03a084e8b`.
Both delegated recovery types must check the fixed outer context at every
retained and dispatch boundary and retire callbacks before its lifetime ends.
The actual Session anchor and separate failed delegated READ accounting remain
required. Source-v3 and its passing author campaigns remain preserved; they
provide no composition or installation authority.

The completed independent disposition confirms both recovery families in
ordinary and ASan/UBSan: zero recovery allows 53 extra READs; allocated recovery
allows 57. Fresh controls stop immediately. Final rejection is
`sdk53-canonical-typed-owner-independent-review-v1/attempt-06`, result
`5c34ac9a6b4a6b535db6625a4e08a3dfa0b92b67a2dbed41f9231803e00db93c`,
freeze `07bbfddb662df48df3fbee50019a2f4fb6d5c3a577f1cebe6756ccec92b1e4b0`.
The delegated preview owns failed READ attempts until successful parent handoff;
the failed parent grants no credit. Root verifies the complete confirmation and
disposition forests. A preserved source-v4 successor is repairing the fixed
parent/outer guard chain and callback retirement; it has no acceptance yet.

The mounted integration preparation is frozen in
`sdk53-mounted-zero-refill-startup-integration-v1/preparation-attempt-01`, result
`50b5bb7e79b9a837dc933ecdcd04018793705296878b71f43e5cff6a152f78cf`,
freeze `4e08edd6a7d7645c5fd5639fa0e157dc15f7521b09af0c0d2c61475501b04648`.
Its 12-member forest contains the complete 1876 baseline whole-file selections,
Node/root/transport ownership, finite classification/child/suffix arithmetic,
separate startup/mutation storage and a legacy-family preservation matrix.
113319 pure arithmetic/format checks and 912 attempted/completed counter
boundaries pass. The conservative suffix requires the actual child's continuing
global unique-ownership proof; no copied report grants it. Large profiles that
overflow 32-bit counters require an explicit refusal or a separately reviewed
bounded renewal validator. This preparation composes or executes no Owner and
does not qualify target frames or native integration.

The frozen budget reinspection has six corrections and two clarifications, with
separate independent static confirmation. Its author also authored the original
preparation; that provenance is explicitly recorded. Review is
`sdk53-mounted-zero-refill-startup-budget-independent-review-v1/attempt-01`,
result `bc66c54d7e2566dfa709faa76769663ab06232942022370a0e01ce570ae53762`,
freeze `1163b45203d9f75c674ed16abbf130d852095e0291b8e5e1545235d1d9a98adc`.
45,432 six-counter boundary checks and 65,760 directory algebra checks pass.
Directory prefix `r` must include the first failing attempted mapped READ;
the coefficients remain conditionally conservative. Existing maximum-epoch
admission needs a separate authentic no-op path. Failed delegated preview counts
stay with the preview until successful parent handoff. All counter reservations
must precede classification; cold-start sequence is learned from the authenticated
head before writer admission. The 3616 no-op figure is a conservative reservation,
not an exact count. Startup remains G4/F32768, and legacy families must be preserved.
This confirms conditional algebra, not implemented route authorization.

The OS boot-consumer leaf is implemented privately in
`sdk53-os-startup-storage-source-v1`. Its sole OS change constructs permanent,
distinct, aligned SDK startup storage and passes it alongside the reclaim
workspace to the actual journalled-root provider. OS source remains 649 members;
no Kernel source is copied or compiled. The exact source capsule is
`source-review-attempt-01`, result
`7f90bc2de89347bc795371f085c8f13881774749a83fe54c74c94904b29c7a0e`,
freeze `37329537d2cbb40685f5d7305a5cea12185d786137aac39fc3c6fd447168eae2`.
The explicit, unchanged SDK52 x86_64/debug manifest is
`d2a76fc6d15430d9b8785ead550c3f28c6811faa45be5dfce76be3a2436fc126`.
Its validated consumer compiles and links the distribution image; result
`609feb663d434a65596fd8044ab6b763d8c27c784906f4ae1fa7611def881658`,
freeze `9f6a332335837772d3c5b2a3f11104397e7b0f977dbe59eeb60688a618dd1c1d`.

The exact consumer executes QEMU ordinary startup with real Virtio journalled
ext4 and distribution-started markers in `boot-attempt-03`, result
`b69603d3e304f62265f7c5410b1f9aed5a643d8534217bea50d12edaf742724e`,
freeze `20404779f6919b039c29ffb0d347ef84035a55f39e64edfbb552866eb8c95b0b`.
A fresh private copy of the previously qualified Notes fixture runs the actual
musl default-app first workflow: save, replacement, old descriptor survival,
rename, removal, reopen and exact namespace all pass. Native result in
`notes-workflow-attempt-01` is
`324081cd458592541ef3d631baa97acb10534d7a01e09442c20422d19cb87981`,
freeze `df88010279429e2f949c5aa52d74dbf7f828bdb226307d9e50b5bcd59da46a8b`.
External Linux read-only e2fsck, directory/stat inspection and saved payload
readback pass without modifying either disk copy. Payload is exactly
`Updated English document.` plus newline. Readback result is
`675a0a3f8876f6590eae3776c3713f5caf627668a3c254cd2d918c862e0f7b9b`,
freeze `788e61b4fe8b57a29b790e9bf0d27aa91dc33c228fb88e044b8a8aba4a150ef4`.
The read-only fsck explicitly skips journal replay; this is not cold-replay or
clean-shutdown acceptance. Failed read-only IDE launch and CRLF observer attempts
remain preserved, as do completed fixture files that refuse a fresh-workflow
rerun. All original media and the exported SDK remain unchanged.

The boot leaf independently passes source review for later private integration:
`sdk53-os-startup-storage-independent-review-v1/attempt-01`, result
`3f47add71dec5fbf927f41afe596047ee323cc9eb5c75b7f9ea6a5a5072173bf`,
freeze `19998b1b1dc21902ba6e245d4cfa05a7c038e09aacb46a4318e317dc79e68a84`.
The reviewer checks the exact source, all 242 exported SDK members, actual
compiler inputs, compile/link and raw QEMU/Linux receipts. No leaf alignment,
alias or storage lifetime defect is found. Older Notes dependency freezes lack
historical mode maps; their complete hashes/membership and current before/after
modes are verified, without a historical mode attestation. This acceptance does
not authorize installation. All legacy active recovery families, intended volume
policy under the fixed 32 MiB startup locator, new typed startup families, all twenty
consumer selections and target call chains must qualify before enablement or
installation. Its x86_64 first workflow does not replace the preserved four
musl execution profiles or the ten architecture matrix, and does not assert an
isolated graphical desktop or physical durability.

Layout/stack recipe v4 is independently accepted for its documented serialized
metadata interface. All 135 author controls and 154 independent controls pass.
Required pins, selected artifact paths, regenerated plan/command bytes, matrix
and output protection checks pass. The rejecting v3 review and failed reviewer
harness attempts remain preserved. Review:
`build/prototypes/sdk53-layout-stack-recipe-v4-independent-review-v1/attempt-01`,
result `244914438d73e6a88f2c7cd01002d754f43f8c5b1182b0c0519f87fa90bc63f4`,
freeze `7d8f60ffcf9bb77bba274a2abceb8102d07e5a64a8ab70cb23af83a63efbb600`.
Root rehashed the whole 42,670-member frozen forest and modes. This review does
not execute a target compiler, exporter, real SDK consumer or guest.

All of the above is private source and hosted-model work. Accepted Kernel919 /
OS623 / SDK41, installed private Kernel1159 / OS632 / SDK50 / ABI49, and the
uninstalled SDK52 candidate remain unchanged. No SDK53 export, mounted writer
integration, native zero-truncate/allocated-empty recovery, physical acceptance
or full M0-M12 completion is claimed.


## Linked-file zero-truncate implementation and user fixture preparation

The first private mechanism slice is implemented and independently accepted for
continued source work. Its exact Kernel1180/OS649 capsule contains the off-stack
four-home planner, bounded zero-to-sixteen-block admission, checked 64-bit
version/no-op behavior and full allocation-ownership proof. Root repeated the
299 planner and 30 ownership models plus the legacy first/next-data regressions
in an independent copy; the measured host64 ABI51 layouts remain identical.
Independent review:
`build/prototypes/sdk53-zero-truncate-source-v1/root-slice1-independent-review-attempt-01`,
result `00d21d7574a6fa000976ae42ef3cbd237696af11ca54c9f1a057b551cf9b2c14`,
freeze `fcd159b8241d3e811ab688e3f7f63071905a980851d4cfcb5bd10af1044712cf`.

The second source slice is frozen as Kernel1183/OS649 and independently accepted
for continued private source work. It adds an exact-original-inode witness, checked
inverse bitmap/counter reconstruction, full canonical plan regeneration and
all sixteen old/after home mixtures. Author-hosted models pass 264 positive,
226 refusal and 32 mixture checks; these are model results. Review input:
`build/prototypes/sdk53-zero-truncate-source-v1/slice2-source-review-attempt-01/SOURCE_REVIEW_INPUT_V1.json`,
SHA256 `2ea8fa1a1a3ddc5a2003b5789dcd6db52fb983b01a110dd0766f960a19a9dd30`.
Independent review adds 57 positive, 5120 repaired-checksum corruption,
15 refusal and 768 exact-mixture controls; ASan/UBSan pass with leak scanning
disabled for the ptrace environment. The first environmental-failure attempt is
preserved. Root verifies the full 1842-file source capsule and 1918-file review
freeze. Accepted review:
`build/prototypes/sdk53-zero-truncate-slice2-independent-review-v1/attempt-02`,
result `2f3c1d2b07311cae70866e78d08e9dd46968f54f9f32936668440d90b78637f4`,
freeze `328e4972d5832ab0d0cee4f28174b73d9c075010b7abb4a03c26c75dbe2c822b`.
The third slice is frozen as Kernel1187/OS649 and independently accepted for
continued private source work. It
adds the complete four-action committed-journal verifier, strict old/final
allocation-ownership overlays, a one-shot noncopyable preview workspace and
off-stack read-only opening/directory iteration. Author-hosted models pass 114
positive and 126 refusal controls, including every 54 physical-read failure
position. Source capsule:
`build/prototypes/sdk53-zero-truncate-source-v1/slice3-source-review-attempt-01`,
result `56b23fb0948328f0bc47bfcb284c8e93e24145ebaa9df369d32cf94ddcc9a5cd`,
freeze `91347c0b38b54711effd64f1f37add3ba0bf89ac5e9893e6edf361c16e173841`.
Independent review verifies the complete capsule, modes and history, repeats
inherited models and adds 1024 repaired-CRC commit refusals, 234 captured-source
drifts, 258 permanent workspace-claim checks and exact convenience/scratch parity
on twelve one/two-group fixtures. ASan/UBSan pass with leak scanning disabled.
Review:
`build/prototypes/sdk53-zero-truncate-slice3-independent-review-v1/attempt-01`,
result `c8029d2631daa196d6d66e29adae33a370dd7060c3fdc46cda5a254906aef34f`,
freeze `1c42ff01d41cd8c738de77c140cb551b715463d37503d7aac0d31454f1a61286`.

The fourth private slice is frozen as Kernel1193/OS649, with independent review
pending. It implements guarded original-Session read preview and canonical
journal formatting. Its final thirteen hosted commands pass: preview 132
positives/151 refusals including 54 READ faults and 44 retained-state drifts;
formatter 442 positives/29 refusals/416 mixtures; large 32-group, 128-record,
1024-directory-block fixtures and record129 refusal. Source capsule:
`build/prototypes/sdk53-zero-truncate-source-v1/slice4-source-review-attempt-01`,
result `9db5e7ba9b672d7930b341981ac16111d0b2ca902a563e694f47b54f02d88a47`,
freeze `5808bd67b62c3baaf643dc6875ad692d82927e0622de77cc5edb6c427c1839fd`.
Fresh source-v5 copies are prepared for typed publication/checkpoint/recovery;
their implementation has not yet been accepted. Typed transaction/recovery, mounted owner
lifetime/cache integration, generalized allocated-empty rewrite and both startup
families still precede production enablement. No SDK53 export or native
zero-truncate gate has run. Packaging OS635 retains its separate lineage;
installed and accepted sources are unchanged.

A separate private allocated-empty first-block planner now preserves the exact
old inode/home images, generation, credentials, access/creation times and
neighboring inode bytes while allocating the canonical free block and incrementing
the full checked 64-bit version. It uses caller-owned scratch and shares the
accepted empty-inode/allocation validation. Hosted 450 positive and 62 refusal
controls pass, as do legacy first-data, next-data and zero-truncate planning
regressions. A measured host compiler frame fell from 4352 to 272 bytes after
removing a four-block aggregate temporary; this does not qualify target call
chains. Candidate:
`build/prototypes/sdk53-allocated-empty-rewrite-source-v1/source-review-attempt-01`,
result `538d365d90747e92d26c940865a123e90e564438e409bed6eb62ef1b6eb4616d`,
freeze `533c84cd082f73a7e8ad6dd3ee0423e84d31b8942d1b135dc9de5b322f8d5ab2`.
All twelve final xmake host commands pass in ordinary and ASan/UBSan modes,
including the three legacy regressions. Complete actual copied source inputs,
modes and original/copy readbacks are bound in hosted attempt06. Earlier failed
path-selection/test-compatibility attempts and intermediate measurements remain
preserved. Model result `17fa12bdd698512e0dcfdadd68a7bba99628c721002d1936b3bdf21a16514e99`,
freeze `18ca211fc7bae7169baac836c16e252daaf83373ccbd81a694e39d69692a41bf`.
Independent source acceptance, a complete exact old-empty witness, typed journal
publication/recovery, mounted integration and native execution remain pending.

The source-only twenty-profile layout/stack metadata recipe preserves all ten
architectures and eighty producer/SDK-consumer probes. Root reproduces and fixes
summary outputs written under selected source/SDK/toolchain forests. The v3
independent review then finds missing recipe-pin and parsed-artifact binding
checks; its rejecting result and all reproductions are preserved. Fresh v4
regenerates the whole plan, commands, project bytes and exact artifact closure
from the validated selections and requires all five recipe-file pins. All 135
hosted metadata controls pass; independent v4 acceptance is pending. Capsule:
`build/prototypes/sdk53-layout-stack-qualification-recipe-v1/source-v4-review-attempt-01`,
result `ca66cd9c9cf7728fffecf36e87c2b196e50556b72a303d21bc4e29a31382d081`,
freeze `883f425511bb134dbf2379f464f803b92c3f0c1889dded659aae29bf443cb9b2`.
This recipe has invoked no target compiler, exporter, OS consumer or guest.

The independently reviewed OS fixture includes `tests/musl/zero_truncate.c`
and an explicit xmake musl probe task. It covers ftruncate, O_TRUNC and pathname truncate,
inode identity, independent and dup-shared descriptor offsets, EOF, writable-fd
and negative-length refusals, empty-file reallocation with zero-filled gaps,
save/reopen and a separate cold-restart content role. A host reference run through
xmake passes 445 first-role and 152 restart-role checks. Three additional reference
commands validate restart, exclusive-create refusal and invalid-role refusal
without changing the retained document. This validates the fixture on the host
filesystem, not Kernel execution, crash recovery, durability or desktop isolation.
The restart marker explicitly leaves cross-restart identity and offset continuity
unclaimed. Receipt:
`build/prototypes/sdk53-zero-truncate-fixture-reference-v1/root-readback-attempt-01`,
result `95e5e88caaef6603ae827ba3222db0d1678ff8ac6e81926cdb7c824daf8a1543`,
freeze `3379b452d8280ac9c37288e6d5a9b7804b88c936e9de1c85ac1f1948b970ae6f`.
A separate agent accepted the exact fixture after 99 controls, strict independent
host compilation and eleven host runs. Review:
`build/prototypes/sdk53-zero-truncate-user-fixture-independent-review-v1/attempt-01`,
result `e25ad727c6c877c2361591d8cd74af39336d4570a557d1a5af29bdbe052184c6`,
freeze `58dc01ae9817530911fd93b581bb6d7dc61669962add8bb604c58720f1cbda66`.
The fixture has no Kernel execution or SDK53 acceptance yet.

Root prepares all forty remaining finite recovery pairs with fresh attempt02
outputs, beginning with cut36 cleanup-after on the four supplied musl profiles.
The selection checks all 640 admission/stage paths are absent and rehashes the
four complete historical failed-capture forests without changing their failed,
unfrozen status. This selection is not an execution admission. Runner and issuer
independent source reviews precede any new native stage. Both reviews are now
independently accepted: runner review repeats 1678 controls and issuer review
passes 235 controls. Fresh attempt02 build and media stages pass on all four
profiles. All four new A/R pairs now pass: 32 stages, eight actual native
captures and eight complete 32 MiB semantic proofs. Each actual A endpoint
independently classifies restart family0; every new R stage binds that exact A
capture and semantic result. Root-selected records are in
`build/prototypes/sdk52-finite-recovery-successor-v1/root-direct-p36-cleanup-after-v2-workflow-attempt-01/ROOT_STAGE_SELECTORS_V1.json`,
SHA256 `88e436ff01ec7842a8267b27fc5481fcaa26ae2dfda9ffe9e7156da18a51c2b6`.
The independently reviewed read-only checkpoint collector now passes. It binds
the 32 stages, 56 actual ownership receipts, eight complete-image semantic
proofs and 164 complete inherited input forests; it launches no native work.
Checkpoint:
`build/prototypes/sdk52-finite-p36-v2-checkpoint-source-v1/root-checkpoint-attempt-01`,
result `3b98bba509cedf9f97dfccf1f2d093389c9f6f622a954b20456502bc1b28eb88`,
freeze `df4df4493d1f6be677ebc2cee63d3e6ec1e142813c986e861ce3f8541a695a21`.
This completion does not qualify failed-FLUSH durability, exhaustive M4 or installation.
Original failed captures and stopped coordinators remain unchanged. Selection:
`build/prototypes/sdk52-finite-recovery-successor-v1/root-v2-forty-pair-selection-attempt-01`,
result `a57225b2ed686bbf6974f47856fcad907ec84f0a6547dffdc1eb981a29b44bd9`,
freeze `034ee0ea4dc4fe3fe986c0313c7557888b0e1f77196cfd451007bf6e583254c1`.
The remaining thirty-six A/R pairs at cuts38/42/44 are now running in fresh
per-profile V2 campaigns. A separate agent independently accepts the exact
coordinator after 462 additional controls and all 28 inherited controls, with
103 protected forests unchanged. Root verifies its complete source and review
freezes before main. Coordinator review:
`build/prototypes/sdk52-finite-campaign-orchestration-v2/independent-review-attempt-01`,
result `9eeffb14fff753079254a385de577288df6214417805a6ee228823db9cacc206`,
freeze `0e1700b44a5a26992b1147f0c61db728601c6946f8e9e1822b7ed3278e3dfd6d`.
Full M0-M12 remains incomplete; physical M11 and manual M12 acceptance remain
user-deferred.

## SDK52 fresh service lifecycle and Linux-copy acceptance

The generation fixture repair now has four fresh static-musl builds and eight
actual production-init workflows on x86_64, aarch64, rv64 and loongarch64. The
four valid workflows pass readiness, two service restarts, dependent retirement,
adopted orphan reaping and reverse dependency stop. The four cycle workflows
reject configuration before any service launch. Actual child compiler records
bind the changed source and generation header. Twelve fresh ELF artifacts are
validated; the separately compiled test manager is not installed or executed.
Final generation bytes are 2 for valid workflows and 0 for cycle workflows.

Root revalidates causal logs and twice rehashes the 41 complete source, stage and
binding forests in
`build/prototypes/sdk52-service-config-native-v1/root-v4-native-checkpoint-attempt-01`,
result `65b341683c60a0cbd68e79296a7529dba63bafb7169dd14888caf8f171fcec53`,
freeze `36808264aca4a703a605a03b377cedb5b5e94782e44543b251e3cacfa0bb0db2`.
Root verifies the V4 issuer's unchanged independently reviewed V3 helpers and
its generation-manifest/fresh-build changes. A fresh independent-agent review
now passes 387 checks of the exact V4 issuer and concrete binding provenance,
including all 20 stages/bindings, 156 receipts, 12 fresh ELF files and eight raw
guest logs. Review:
`build/prototypes/sdk52-service-config-native-v1/root-issuer-v4-independent-review-attempt-02`,
result `fe08e788aeb2b66a264c464ffcf75b8c8da03c9e8a61bbe6eefa362334f6ef50`,
freeze `5b79e72f3d42819eb3c3e0c831e648261c9b9d25013598e20993860cfaf66222`.
The original pre-run issuer-review gap remains recorded; this later review
accepts experimental evidence within scope and grants no retrospective pre-run
authority or installation acceptance. Journal replay and
read-only checks use external copies only. Captured images remain untouched by
offline tools. Clean system shutdown, durability, full M7 and an isolated
graphical desktop are not qualified.

Four additional cleanup-before R images pass twelve actual read-only Linux
commands, exact peer/original-init readbacks and complete original/copy hash
checks. No replay or repair runs. The independently reviewed copy runner and
issuer preserve exact A-to-R semantic lineage. Root twice rehashes 16 complete
forests in
`build/prototypes/sdk52-finite-r-linux-copy-v1/root-four-profile-cleanup-before-linux-checkpoint-attempt-01`,
result `9680145fc3c0bcf47405663f68248efed1601712f1a507f63c651cf44c18cbde`,
freeze `2a64681974e25bf1e18ba9fdc423644e39da2d9feab8a7300af8a5e7c1187aa2`.
The four stopped recovery campaigns remain stopped. A guarded read-only Root
diagnosis binds each exact compiled observer/selector, re-parses the raw log,
reproduces the historical validator refusal and compares every byte of all four
32 MiB endpoints against the successful physical WRITE effects. All four match;
complete original build/media/failed-capture forests remain unchanged. Diagnosis:
`build/prototypes/sdk52-synthetic-after-effect-diagnosis-v1/root-attempt-01`,
result `b7d2910ed13d8701ab696ff837b21b202cabf59beebe3a7b3042cd246aa8307c`,
freeze `113273ddc34f5c9f81ccd12ba97f4b309763100c48002704807297c91eac6117`.
This is defect diagnosis only: the historical captures remain failed, with no
passing freezes or semantic/durability acceptance. The synthetic after-effect
parser successor now independently passes 136 hosted controls and four further
complete-image raw-log comparisons. Raw return fields are unchanged; derived
physical outcomes are revalidated from original text/selectors before image
comparison. Genuine failed/unreturned physical WRITEs remain refused. Review:
`build/prototypes/sdk52-diagnostic-parser-after-effect-independent-review-v1/root-attempt-01`,
result `f6da0187b34c9cac180ad9f3e0ef275277e3a2e8f899600a50f1eabb29be46e8`,
freeze `14b13333f5dc6486a8d9d4b994ba953917c8cb01ecb25417a1b70abf877559bb`.
Finite runner source-v2 is frozen with explicit parser/review closure and the
same compiled observer. Its 476 positive and 995 refusal controls pass; actual
copied compiled observer bytes are required in build prerequisite maps. Source
result `fb479b29d9f28dcb368529a8c2a0160bb689dbc29e303e95250fae1d44855a6f`,
freeze `e2d76d199810e9613a673126b1fc42fe9b06417ded8a94c5aeee3fc7e33d1d06`,
review input
`build/prototypes/sdk52-finite-recovery-successor-v1/SOURCE_V2_REVIEW_INPUT_FINAL_V1.json`.
The issuer V2 draft retains all V1 helpers and adds the parser source/review to
the complete input closure; it has not issued bindings or invoked its main.
Independent runner/issuer acceptance must precede new native stages. The forty
remaining selected pairs remain open.

The zero-truncate mechanism design is reviewed for fresh source preparation.
It preserves linked inode identities/open descriptions, releases proven data
blocks through a distinct four-home journal transaction, and includes both
allocated-empty rewrite and typed startup-recovery companions. Its initial
scope is one-link ordinary files with at most sixteen initialized 1 KiB blocks
in one allocation group. Source preparation scope review:
`build/prototypes/sdk52-zero-truncate-design-v1/root-scope-review-attempt-01`,
result `a1b018c9e70bcd9c9b06c54064dd5c704c676f202b1a4a30c8d2097627e02112`,
freeze `4c1980c0a936830797cf0c40f86910cd0b8ce5eeff01bbcc910a7e54e535c4af`.
No zero-truncate implementation, test execution or production enablement is
claimed by that design receipt. Broader storage/product/installation gates remain
open. Accepted SDK41 and installed private SDK50 remain unchanged. Full M0-M12
is incomplete; physical M11 and manual M12 acceptance remain user-deferred.

## SDK52 generation fixture repair and recovery campaign stop

The generation fixture successor is implemented in a fresh 646-file OS source
with a six-path delta from the accepted service implementation. It securely
overwrites and reads the existing one-byte root-owned marker without creation or
truncation. Descriptor identity/security/geometry checks, bounded transfer EINTR,
single close/error precedence and delayed read publication are covered by 107
hosted cases. The child retries only the immediately preceding generation;
future or regressed states fail. The production manager, loader and configuration
remain byte-identical. The sealer binds the new child header in actual compiler
dependency closure. Independent review repeats five C suites through xmake on a
separate source copy and all 19 guarded Python methods. Review:
`build/prototypes/sdk52-service-generation-fixture-independent-review-v1/source-v1-attempt-01`,
result `6b05af107ddf7288d04886c5c2792cb0b15c2e0b1b1375ab62c3dcb359a59fa7`,
freeze `44619430bd90f2463c59a213e17dc622a6d60a2cfd7e29e28a9feeabe39c2adf`.
Fresh four-profile child builds and positive service lifecycle workflows are
completed in the checkpoint above. Zero-length truncation and block reclamation
remain unfinished storage implementation work.

The four remaining-pair coordinators each complete the cut36 cleanup-before A/R
pair and the cleanup-after A build/media stages, then stop at the after-effect
capture validator. Eight new actual captures and eight whole-32-MiB semantic
proofs pass. Four further actual captures reach their exact injected failure
marker, exit 0 and complete owned cleanup, but the current image ledger rejects
the synthetic after-effect error as an uncertain physical WRITE. Those captures
have no passing freeze or semantic acceptance. All four coordinators have stopped
without retry/resume; 36 selected pairs remain entirely unrun and four after-effect
pairs are incomplete. Root preserves and twice rehashes 92 complete forests in
`build/prototypes/sdk52-finite-campaign-orchestration-v1/root-cleanup-before-pairs-and-cleanup-after-refusals-checkpoint-attempt-01`,
result `65a7618745776ba70fbd75f1740d428998130a0fc85f60072dfb5a10a0f5e962`,
freeze `a788d25a933300d556fadc47b2cc2b70b11e75797b4127674549396f512af03b`.
The original failed stages and campaigns remain unchanged. Correct attribution
requires a reviewed successor; this is not exhaustive M4 or failed-FLUSH
durability acceptance.

The read-only Linux-copy runner source independently passes 337 guarded controls
and retains exact finite R admission/semantic provenance. Source review:
`build/prototypes/sdk52-finite-r-linux-copy-independent-review-v1/attempt-01`,
result `d9ce866a8081a6ad3cfc7bebe1d825390090417b596ff48e3628ed17d4c97564`,
freeze `29d5a14d3d27a4b708128bac909f94b92e398f8cbf13e5492b6c949b463c24de`.
Concrete copied-media executions are completed in the checkpoint above. Accepted
SDK41 and installed private SDK50 remain unchanged. Full M0–M12 is incomplete;
physical M11 and manual M12 acceptance remain user-deferred.

## SDK52 completed terminal-FLUSH restarts and service rejection workflow

The four cut36 terminal-FLUSH pairs now complete all 32 separately admitted
build/media/capture/semantic stages. Eight actual captures reach their complete
markers and exit 0. Eight semantic proofs compare every byte of their 32 MiB
images; each R starts from its exact new A endpoint and uses the independently
classified restart family 0. Root twice rehashes all stage and issuance forests,
checks exact parent links and reads back successful input/owned-process
postchecks. Checkpoint:
`build/prototypes/sdk52-finite-recovery-successor-v1/root-p36-terminal-flush-checkpoint-attempt-01`,
result `22107c07e139a3a6f076662b98735d217ba7e2a4f41b51cb7a73d7449c6a3277`,
freeze `fe1125f20c549b8ce99f1d1dcc597361dabc008ee832d16c45c9dfbe0998ae01`.

The remaining 44 A/R pairs are dispatched through four explicit profile
coordinators. The unchanged accepted finite issuer and stage runner retain
separate admissions, complete freeze checks and actual-A family binding before
each subsequent stage. The six-file orchestration capsule passes an independent
guarded repeat of 19 controls, including the mocked 22-case/88-stage sequence;
Root also verifies all four exact selections and absent output sets. Review:
`build/prototypes/sdk52-finite-campaign-orchestration-v1/root-independent-review-attempt-01`,
result `9563a60366cee7a9adff5048023c2b1c85b66fa8794501cf0e0fbebb52eea25d`,
freeze `4d4405748dd6c6339edbd42fe33ee1afa631484c327bce6a88898fc32f53d5b5`.
Dispatched cases remain pending until their individual frozen results pass.

Service V3 completes eight new journalled preparations and four actual cycle
rejection workflows on x86_64, aarch64, rv64 and loongarch64. Each cycle emits
config-invalid before any child launch, preserves exact configuration/marker
contents, and passes journal-only replay plus read-only validation on a separate
external copy. Captured images remain untouched by those tools. Each guest has
its own unchanged boot-image copy. Whole-volume immutability and clean shutdown
are outside this acceptance scope.

Root twice rehashes the 16 complete V3 stage/binding forests and their recorded
successful ownership/input postchecks in
`build/prototypes/sdk52-service-config-native-v1/root-v3-native-checkpoint-attempt-01`,
result `ccc2be21e7f787367ceebf43cc0a67cfdc8d76bfbe200fd2975d81e685a58815`,
freeze `1fcba3d60f6930345823f6c5d18c3fcbc59498a16a429c20f99f7026ef5a5410`.

All four valid V3 attempts load the production configuration and launch setup,
then fail while opening the generation file with O_TRUNC. Independent source,
ELF and media readback confirms that journalled truncate-to-zero is explicitly
unsupported and the open path maps that status to ENOSYS38. A bounded successor
interface now specifies secure overwrite/read of the preinstalled one-byte
marker while preserving the service lifecycle assertions. Fresh implementation,
child builds and positive native service acceptance remain outstanding.
Zero-length truncation and block reclamation remain separate storage
implementation items. Original V1/V3 failures, interrupted metadata, accepted
and installed baselines remain preserved. Full M0–M12 remains incomplete;
physical M11 and manual M12 acceptance remain user-deferred.

## SDK52 four-profile terminal-FLUSH regression and service successor

All four cut36 terminal-FLUSH A cases pass separately admitted build, media,
native capture and semantic stages. Each captured guest reaches its complete
marker and exits0; the independent semantic oracle compares all33,554,432 bytes
and classifies its actual endpoint as restart family 0. Independent frozen
readback verifies all 16 complete stage forests, exact parent/issuance links,
recorded input postchecks and zero remaining owned processes. Its receipt is
`build/prototypes/sdk52-finite-p36-capture-independent-readback-v1/attempt-02`,
result `e76801e50a4c34e4ba573d5fc915590b2593591a703e0697d52b8a08cd5e2f1e`,
freeze `0d2247564bd15644a72a1982305f1a4f45b19f1f75fb0c147af36a6bc0dcd62e`.
Root additionally rehashes each stage freeze. The corresponding actual-A-bound
R restart stages subsequently complete in the checkpoint above. This remains
representative recovery coverage; exhaustive M4 and failed-FLUSH durability
require their separate gates.

The service runner V3 now binds exact maintained journalled Notes media and
accepted production service builds, gives each guest an owned boot-image copy,
and retains secure configuration loading. Its first freeze preflight and an
independent review caught an x86_64 Notes-source lineage mismatch; the preserved
finding is closed by the exact accepted Notes workflow/run/preparation chain,
including actual source-v3 on x86_64 and source-v4 on the other three profiles.
The final frozen27-file runner independently passes325 guarded hosted controls.
Review is
`build/prototypes/sdk52-service-config-native-independent-review-v1/service-source-v3-attempt-01`,
result `0ddded9bf85aa1c4b6c065ea9d31238e2761b1fbfdf697bdbf33d872bc70aa61`,
freeze `91f7d39625426b1edfbe5b6dcb368e21665cbba0d5bad54232f87793b3821d6f`.
Root rehashes all 137 review members. The fresh V3 prepare/run stages complete
above with four cycle passes and four preserved valid fixture failures. Positive
service lifecycle acceptance and installation remain pending; original V1
failures and all prior records remain preserved.

## SDK52 service builds and native fixture findings

The production configuration runner source passes independent review, including
183 hosted controls and six additional descriptor controls. Four fresh static
musl builds of the production service manager and graph child pass, preserving
all ten Kernel profiles and four supplied musl profiles. Independent readback
verifies all four complete freezes, copied644-file OS and selected SDK maps,
actual compiler/link records and eight static ELF byte streams. No test-manager
macro or Kernel source dependency occurs. The independent build review is
`build/prototypes/sdk52-service-config-native-build-independent-readback-v1/attempt-03`,
result `fa615c9404df5208b5fcbdd250d2a4ca5c1a85b138f9dfb5924c25e3325f7187`.

All eight valid/cycle preparation stages pass secure inode and exact-byte
readback plus read-only fsck. The first two x86_64 native attempts are preserved
failures, not service passes. Valid configuration reaches production PID1 but
its first directory fstat returns EOPNOTSUPP95: the selected writable legacy
nonjournalled provider uses unqualified timestamps, while Linux stat requires
qualified epoch fields. Parsing never begins. The concurrent cycle guest fails
to obtain QEMU's write lock on the shared frozen boot image and never boots.
Original inputs remain unchanged and both owned process trees are reclaimed.

Root rehashes all14 complete stage freezes in
`build/prototypes/sdk52-service-config-native-v1/root-v1-native-attempt-checkpoint-attempt-01`,
result `bb51e8cbedd2bedd5fd235bd217541cdb00beaf5f9046c89f1a3a23f42257d44`,
freeze `e5ff219d85ab603b3da1d67d4d7eae072ce7c202ecb9c7e2406ed025eca5241e`.
Other-profile service run stages are not admitted. A fresh runner successor
will use exact maintained journalled baselines and an owned boot image per
guest, retain the loader's full security checks, distinguish mount bookkeeping
from user mutation, and perform journal-only recovery on separate external
copies before read-only validation. Independent final-source review and exact
Root stage bindings remain required. No installation or native service pass is
claimed.

The finite recovery runner independently passes472 positive/991 refusal
controls and128 added prerequisite/lineage checks, with no material source
finding. Its review is
`build/prototypes/sdk52-finite-recovery-independent-review-v1/attempt-01`,
result `19738e55964cd46358eff37aaf5e402c59060c75eee28e276b14c44e4a973340`,
freeze `cc1565e23138fc13438f0e62268134b255caa4ba083cc29ba834b4d9b8e78169`.
The first admitted x86_64 cut36 terminal-FLUSH observer build passes six actual
commands, five compile records and one SDK-only link record. Media, captures
and semantic proofs continue separately. This remains a representative48A/48R
campaign; it does not establish exhaustive M4 or complete M0–M12.

## Persistent service configuration: implementation and packaging correction

The OS-only service successor implements a bounded boot-time manifest for the
existing production supervisor: eight services, named forward dependencies,
simple/notify/oneshot readiness, owned configuration strings and atomic graph
publication. Its loader pins root-owned `/etc`, opens a bounded root-owned
regular file without following the final symlink, checks opened-file stability,
and closes inputs before launch. A present invalid configuration emits
`config-invalid` and exits13 before any fork. The absent final file alone keeps
the default console. This is a no-argument boot configuration slice, not full M7.

The source-v1 candidate has644 OS files on exact SDK52 OS635, with17 deltas.
Seven hosted plain/sanitized model executions,16 Python methods and219 C/Python
grammar comparisons pass. Independent completed-code review additionally runs
four C models and16 Python methods and verifies the complete644/635 source maps.
It finds no parser, loader, committed-pointer or production actor defect.

That review nevertheless withholds source acceptance for a reproduced packaging
defect: service-build admission and rootfs staging independently reread the
configuration, allowing valid replacement bytes to differ from the sealed
configuration digest. The untouched candidate's hosted interleaving control
stages hash `43afcb323811052667402cde8d1ce760fafce47e19058dcef9c4e04fb7a1dbd7`
while its accepted build config is
`ba8968b42fa7d38f40029637b0b1f6abf0d2d779006a2a1cc4929f6b2525d6a6`.
Review result SHA-256 is
`646bf9bc94b420cd54e5655af24551b246080a296d560588fe58a0cef31b7996`,
freeze SHA-256
`e3102925b1cf338e9002a77c89432eeb37b15f9468ef38e139bc56577fa0eabb`.
Root rehashes every review member. Source-v1 and the refusal remain preserved.

A fresh source-v2 correction now closes F1: take one owned config snapshot,
bind those exact parsed bytes to service-build admission, and stage the same
bytes after validation. Root independently reviews the five-path repair,
rehashes complete644-file successor/preserved644-file V1/635-file parent maps,
and runs all12 affected Python methods under a guard forbidding external/native
execution. Three added regressions prove original snapshot staging after source
replacement, seal-mismatch refusal before output mutation, and immutable/parsed/
seal-matching explicit inputs. Runtime C bytes remain unchanged and are not rerun.
Accepted review result SHA-256 is
`4caa21513902ccbc5fea24995e0cd925826cf5eceffd042ff0a123644490fcc4`,
freeze SHA-256
`9cdbb524a31840f02f566f21262129d88d72ce3f25553fd48767a7d1c1078f0d`.
The accepted644-file source-v2 freeze is
`91a0ded56b25441f672a82d42a4334a0b9e1693204d118d38b617e597a1b2c3a`.

The four-profile SDK-only manager builds now pass, as recorded above; production
main does not define `OK_SERVICE_GRAPH_TEST`. Config-driven native acceptance
remains pending the recorded fixture corrections. No source installation,
promotion, native service pass or configuration durability is claimed.

The fresh SDK52 finite recovery successor has independently accepted source. Its
design retains the four-profile/cuts36/38/42/44 terminal-boundary domain with48
new A attempts and48 separate actual-A cold restarts. This is a representative
migration regression, explicitly narrower than exhaustive WAL/home-boundary
qualification. Original SDK51 campaigns and interrupted evidence remain intact.

## SDK52 independent semantic recovery and Linux-copy checks

The four separately captured SDK52 diagnostic images now pass the unchanged,
independently reviewed semantic byte/trace contracts. The original producers
remain SDK51; the new native execution remains SDK52/ABI51. Root compares exact
historical selectors and unmodified recovery traces against independently
generated operations, route reports and every byte of each 32 MiB volume. The
A-LoongArch64 ordinal10 before-effect failure proves quarantine, no further
mutation, no published root and no user entry. The three R captures prove active
reclaim recovery, fourteen read-only musl checks, resource drainage, clean sealing
and a mutation-free fresh mount. These are four new pure proofs over the already
admitted captures, with no new guest or compiler executions.

The complete proof receipt is
`build/prototypes/sdk52-diagnostic-semantic-qualification-v1/root-attempt-01`,
result SHA-256
`1b1f4c752e226a33770564fadb95d39bdb2a5bef237b0d76c007399c036dc036`,
freeze SHA-256
`7432a212a5dae27e0a5503fe86448b2f8aa655f8e7a3346a0f333729c6c2ac93`.
All 26 consumed forests and the separate readiness record remain unchanged.

Fresh external copies of the three sealed R images also pass actual e2fsck
read-only checks and debugfs readback of the exact untouched peer and immutable
original musl init. All nine Linux-tool commands terminate successfully; every
whole copy remains unchanged. The Linux receipt is
`build/prototypes/sdk52-diagnostic-semantic-qualification-v1/linux-copies-attempt-01`,
result SHA-256
`a1fb17f7870fbac4d9ab3240e5abd9b5ef123cf290cd992ba433bf1c37d1f158`,
freeze SHA-256
`508cc6902c44f78355081a381bf097b29fb139ff360398cac1c377de31398bad`.

Independent review repeats all four pure proofs with identical complete returned
objects and accepts both Root helpers, their observer applicability and all nine
Linux receipts without material findings. Its result SHA-256 is
`0d02f46267144ef3879f0f4e9d6a94264ef83a29ed746c480d4a076883065f90`,
freeze SHA-256
`0c631ceb1a4f7d2f41fac2b73ce85c5e46d6561a46ad19a175aabc0e8b6a67ce`.
The original transport status11 cause and failed-FLUSH durability remain
unqualified. Historical/corrupt SDK51 campaigns are preserved and not restarted.

Separate SDK52 integration review confirms that the private SDK50 working target
still exactly matches archived Kernel1159/OS632. SDK52 has 30 edits and 16
additions, no removals, including 18 production paths; no new production defect
is identified. Review result SHA-256 is
`45fad475a6a9f3814fde95e5d9acd0e355491ed691ae33940f9b0f279a9f85d6`.
This source review and bounded recovery/application passes do not install or
promote the candidate. Fresh finite journal qualification, remaining ordinary
product gates and a separately checked transaction are still required.
The next parallel OS implementation adds persistent production service
configuration to the existing bounded supervisor. Networking, isolated desktop,
six further musl execution ports, advanced ext4, SMP and full M0-M12 remain open;
physical and manual desktop acceptance stay user-deferred.

## SDK52 cross-toolchain successors and additional diagnostic consumers

Fresh Notes/Files source-v4 closes NF4 with explicit compiler-path/target checks
and explicit tool-loading callbacks in both emitted standalone toolchains. It
also refuses conflicting authoritative pin merges. Its hosted controls pass
122 positives/359 refusals, including 16 emitted projects across the four
supplied musl profiles and both modes. Root rehashes the complete 27-file source
freeze: result SHA-256
`c7d06e6be491ca0abeb040344c7dcfa2d1581624a123d25eb8849a7471b215d3`,
freeze SHA-256
`17344b8eef7a2b0025c144687f9f0f78a6ed659e8af73a7c39111a27ebdd1c65`.
Fresh non-x86 application execution is still pending.
All V1-V3 sources, passing x86 workflows and the failed RV64 configure attempt
remain preserved.

Fresh diagnostic observer source-v2 applies the same explicit check/load repair
to `diagnostic-cross` and binds parent stages to its exact V2 source descriptor.
Hosted controls pass 89 positives/183 refusals, including production generator
checks for all ten profile triples. Root rehashes the complete 15-file freeze:
result SHA-256
`1422f91e2e5b7ad6d5000b71f0d728d9917857136b94ec88fd119eb1c2c52e3b`,
freeze SHA-256
`6468879dadb8133bbb39a4c2d4e4fd67a017ad200f691e5df751bb76b437584b`.
The four historical cases, parser, deadline and failure selectors remain
unchanged. Independent source review and actual observer execution remain
separate gates. Root's first source-only admission assembler incorrectly assumed
that consumer RESULT records carried original admission path fields. That source
and finding are preserved; its fresh V2 selects the exact same-profile/attempt
Root admission and requires byte equality with the frozen consumer copy.

Actual six-command OS638 diagnostic artifact consumption now additionally passes
x86_64 Debug and RV64/AArch64/LoongArch64 Release. Root rehashes every file and
checks terminal owned cleanup, unchanged source/SDK inputs and recorded SDK-only
dependency closures. Readback records are
`build/prototypes/sdk52-block-diagnostic-successor-v1/ROOT_CONSUMER_READBACK_X86_RV_V1.json`
(SHA-256 `f1441ad9747f8233df731eed9094deac3c4cb631fba2f6a64e19945cd8fd9062`)
and `ROOT_CONSUMER_READBACK_AARCH_LOONG_RELEASE_V1.json`
(SHA-256 `71a9cf3b188e4a5df6501c0029ee253bb86b3793e2b983099c0901644bb6a3fe`).
The remaining profile/mode consumers subsequently complete below.
These are build/artifact checks, not diagnostic device execution,
installation, promotion or full M0-M12 completion. Physical and manual desktop
acceptance remain user-deferred.

The fresh OS638 artifact campaign now completes all twenty architecture/mode
combinations and all 120 consumer commands. Root rehashes each complete frozen
forest and binds each receipt to the exact same-profile SDK52 producer from the
accepted twenty-export checkpoint. The combined diagnostic consumer checkpoint
is `build/prototypes/sdk52-block-diagnostic-successor-v1/root-twenty-profile-mode-consumer-checkpoint-attempt-01`,
result SHA-256
`a9be6ae8ab00758a9bc311eadb4daed3d83c44fe36565a2bdf5477800902f268`,
freeze SHA-256
`604eaca7b4a4a94147fdbfc3651ca80c0787d420d1f5bcf4b074e349e9439924`.
All six additional Debug consumers have terminal owned handles and verified
cleanup; their separate agent readback is also byte-verified by Root.

Independent observer V2 and Root assembler V2 acceptance is now frozen under
`build/prototypes/sdk52-block-diagnostic-observer-independent-review-v1/source-v2-attempt-01`,
result SHA-256
`f20423a6318160f1927659c50e24109959a349315d1f6fb49812ca6f996a685e`,
freeze SHA-256
`fb8bd6f3fe4bf8edb08fc41cd9f4a790b7186ec3ad682081b21fc460b8c6bb51`.
Root rehashes all 123 review files. Independent full production admission models
pass eight positives/fifteen refusals, with synthetic own-review/parent contracts
clearly marked powerless. Actual separately admitted observer builds now pass
all four historical case selectors: A-LoongArch64, R-AArch64, R-RV64 and
R-LoongArch64. Each executes the six expected build commands and verifies five
SDK-only compile records plus its exact linker record. Actual xmake configure,
compilation and linkage therefore verify NF4's diagnostic repair on the three
nonhost architectures used by these cases. Fresh media and native capture are
separate stages; successful compilation does not qualify recovery
semantics, failed-FLUSH durability or a fault root cause.

Root, independently of the original Notes/Files V4 author, reviews both complete
V3-to-V4 production diffs, repeats 122 positives/359 refusals under a guard that
forbids every actual external process, and reruns full production admission
feasibility on real x86_64/RV64 SDK, musl and tool inputs. These models retain
clearly powerless product-review/prior-stage placeholders. Its complete 2716-file
review is frozen under
`build/prototypes/sdk52-notes-files-native-independent-review-v1/root-source-v4-attempt-01`,
result SHA-256
`d3c7a134d331e4489ead3d43e6b892dcc75986abcd661c48b024b5f3ff12d0f5`,
freeze SHA-256
`6f601e347181a100ba830f348e81571c1c850a2f66475582e82da4aa2b2e1653`.
Root verifies the exact source/review-binding-only delta from independently
reviewed stage assembler V1 to V2. Actual RV64 Debug build attempt02 now passes
all nine commands, fresh static-musl builds and ELF checks for init, Notes, mv,
rm and stat. Root rehashes all 955 files, result SHA-256
`a66c619bdfb13828e9897c5930a4947d159ea98241742c159d7f149dec8c1b79`.
AArch64 and LoongArch64 fresh builds also pass. Distinct prepare/run stages
remain required before recording their actual product workflows. The previous
RV64 configure failure stays preserved.

All four diagnostic media stages pass whole-image copy checks, leave historical
media unchanged, and execute no guest. Separately admitted captures are now
running against fresh copies. Native capture completion, parsed diagnostics,
image conservation and independent semantic recovery remain distinct gates.

All four captures now complete with bounded owned QEMU cleanup, unchanged input
closures, parsed observer outcomes and whole-image WRITE-ledger conservation.
None reproduces the original physical status11. The A-LoongArch64 case preserves
the selected software failure at ordinal10 and refuses root publication; the
three R cases emit startup/user/clean-seal/fresh-mount completion markers. These
markers and byte conservation still require the separate independent semantic
volume oracle before a recovery-success claim. The original failure cause and
failed-FLUSH durability remain unqualified. Root's frozen four-case checkpoint
is `build/prototypes/sdk52-block-diagnostic-successor-v1/root-four-case-diagnostic-capture-checkpoint-attempt-01`,
result SHA-256
`ac19a63c4337996a863717a1d4ddee75df2530f969308b33b85334f32b712abd`,
freeze SHA-256
`8a22324efd4ef66646bf729d6042cb3520cec5a89a5d64dddf345c6c039fd5b8`.
All three new Notes/Files prepare stages also pass Linux journal activation,
filesystem/application readback and SDK-only first/restart observer compilation;
Root rehashes their complete freezes. Their actual product run stages are now
the next gate. SDK50 installation and accepted baselines remain unchanged.

The actual Notes/Files Debug workflows now pass on all four supplied musl
profiles. The complete Root runtime checkpoint binds all 3609 files across the
four frozen receipts, including the earlier valid x86_64 V3 run and three fresh
V4 runs. All eight first/restart boots have complete ordered success markers,
verified owned cleanup and no captured failure. The x86_64 ISA debug-exit code33
is the admitted success convention; Root records and corrects two source-only
readback assumptions about exit codes and appended success-line fields without
rerunning or changing any native receipt. Every workflow performs the exact
English Notes save/display/replace and `notes.txt` to `saved-note.txt` rename,
retained old-file-description/reclaim checks, user1000/group1000/home0700,
distinct read-only cold restart with the entire disk unchanged, and external
Linux-copy filesystem/content checks. The checkpoint is
`build/prototypes/sdk52-notes-files-native-successor-v1/root-four-profile-notes-files-workflow-checkpoint-attempt-01`,
result SHA-256
`52f49382b3c266693f39f25941481646370dda760dcf43c28cada614b698cfb5`,
freeze SHA-256
`572518e23090bc1ced435949140f68e9de5b92d75184af062c36ebbe8c0b2c5d`.
This qualifies the bounded default application workflow on the SDK52 candidate.
Isolated graphical desktop behavior, broader POSIX/ext4 semantics, the six
additional musl execution ports, complete networking/services, SMP, installation
and full M0-M12 remain outstanding. Physical/manual gates stay user-deferred.

## Restored workspace: interrupted evidence and SDK52 source gates

The 2026-10-08 restored-workspace audit preserves both original SDK51 campaign
forests. Missing observer handles and the different PID namespaces exposed by
separate command sessions do not prove global process termination. Historical
exit codes and cleanup remain unknown; original campaign outputs are not reused.
The read-only audit is frozen under
`build/prototypes/sdk51-v38-campaign-recovery-audit-v1/attempt-01`, with result
SHA-256 `935e0bd1c7f56d9898b153da21dfc69c767fd29b8d7ec0c8a36fbaeab71e4ab7`.

AArch64 first-mutation evidence currently has 26 valid groups, 68 valid build
admissions and 67 valid runtime receipts. A separately reported completion has
empty runtime freeze, capture and oracle records and remains unadmittable; V12
already excluded it. Seven groups and eight never-completed cases remain.
X86_64 aftermath has 26 valid runtime receipts. Its interrupted next admission
has empty RESULT, FREEZE and ADMISSION records, with no runtime output; all three
files remain preserved. Of its 49 remaining cases, 48 were never attempted.
All 49 prerequisite first-mutation freezes were byte-verified. One valid aftermath
receipt postdates V12 (`x86_64-producer38-failure-before-ordinal3`); this audit does
not rerun a guest or replace the historical V12 inventory. The corruption cause
and the four physical transport fault11 causes remain unknown.

Independent review refused SDK52 runner source-v4: unsupported driver option
spellings could select unlisted linker scripts, include files, specs or libraries.
An inert fixture reproduced the linker-script omission through the shared
dependency verifier. No compiler ran in that reproduction. The refused source
and review remain frozen. Source-v5 closes the driver grammar and passes
independent review, result SHA-256
`3a8b1585d5634dd0abf52d38f77d224ac12ddcebf339aec78657fadd428dbad6`.
The shared verifier accepts five positive fixtures and refuses 43 input-selector
fixtures; all 2210 saved SDK51 records across twenty profile/mode receipts remain
compatible. Those are source/metadata controls, not fresh compilation.

Root issued a concrete source-v5 build admission with SHA-256
`58c5b68d9a0efa9660e991c1e123e00d49c4607880b0607f5256ccd8376886f2`,
protecting 28 complete forests and 5912 individual pins. The first x86_64 and
RV64 Debug attempts both exited one during the real preflight, before output
creation, process-owner initialization or any native command. Required-absent
RC paths were incorrectly passed to an existing-input canonicalization gate;
both failed on absent `/etc/xmakerc.lua`. Root's preserved finding is
`build/prototypes/sdk52-sdk-consumer-v1/ROOT_RC_ABSENCE_PREFLIGHT_FINDING_V1.json`,
SHA-256 `6ae8706be2421b31d317876f351502e7f05512736eed375fdb04f31d8675dffd`.
No SDK52 export or standalone/product guest pass is recorded.

Fresh source-v6 preserves V5 and adds a separate required-absent input isolation
gate. Ordinary protected inputs still require existence. Its controls exercise
the actual gate with the real external RC paths without writing those paths,
and reject existing entries, dangling symlinks and both overlap directions.
Source controls08 pass 68 positives/53 refusals, including two direct absent-path
positives and eleven refusals; the five/43 shared dependency controls and 2210
saved-record checks also pass. Source-v6 result SHA-256 is
`6817e5099951bece8b407653f9b0fa93e1e5a291bf7cc60a4f4d8e557c6c70d5`;
freeze SHA-256 is
`71c65e6e79aa8e8c06b432ed335cdc68082c96d99eef9054e4bb8856ede097e4`.
Independent source-v6 review now passes, with result SHA-256
`d535c68c6ae31c547c9f6ff0b48c0380425f4e2ced7b28ecc205475cdc5b4d5c`
and freeze SHA-256
`958641da9763d39837904f7698bc3c58a13c8947ab6c25975e555c1806d21da7`.
Root rehashed all 1252 review files. The independent actual RC controls pass
four positives and 21 refusals. Root admission02, SHA-256
`a1e91eeb8439eee8c603002372b0b2f80927c1ee7ec924fec8249a0639fc1c96`,
protects 32 complete forests and 5914 individual pins and retains the twenty
architecture/mode combinations. Fresh x86_64 and RV64 Debug attempt02 now pass
all nine commands, including actual SDK52/ABI51 exports, standalone Kernel Debug
QEMU boots, OS distribution/rootfs builds and UAPI/libc checks. The recorded OS
dependency closures exclude Kernel source compilation; owned cleanup and
unchanged source/SDK postchecks pass. Root rehashed the complete 2540-file
x86_64 freeze and 2534-file RV64 freeze. Their result SHA-256 values are
`bc627df32185ec326b71c13a874975aba50fad4a12b7c9d4014b05e7aa55d50e`
and `440fedf3526373bacf07bf180bf48d55d4f66cdc049311e2322ddd562ff62228`.
AArch64 and LoongArch64 Debug attempt01 now also pass all nine commands and
complete frozen readback. Their result SHA-256 values are
`b3d05ddeeced7cf290f4e8b5992ced4af5d30b3a6fe233e95bdd731c8c6c7444`
and `1f00672e1de90056a8d1b82fbc1c9e90debc67297d3f522f27bb7b79b1bd882f`.
All ten Debug profile receipts now pass and have complete frozen Root readback.
The checkpoint is
`build/prototypes/sdk52-sdk-consumer-v1/root-debug-checkpoint-attempt-01`, result
SHA-256 `f30c108f99159fc87cd9a23369889fa05e107fa3ea50b315398158395646820e`.
It binds ten actual exports, ten standalone Kernel Debug QEMU boots and ten
passing OS artifact consumers. All ten Release receipts now also pass; Root
rehashes every complete forest in the combined checkpoint
`build/prototypes/sdk52-sdk-consumer-v1/root-twenty-profile-mode-checkpoint-attempt-01`,
result SHA-256
`265d45a0bb83a4622b95cbf5736e4b0d6f9a1c375b2642ed5cbabc5b14727a93`.
That checkpoint binds twenty actual SDK52/ABI51 exports and passing OS artifact
consumers plus ten standalone Kernel Debug boots. Release export/consumption
does not add Release guest qualification.
This does not qualify
OS product guests, actual musl applications, installation or promotion. The
failed attempt01 selectors and original V5 admission are preserved.

The OS-private physical block diagnostic source-v3 is frozen under
`build/prototypes/sdk52-block-diagnostic-successor-v1/source-v3`; its manifest
SHA-256 is `edd8a48e3ed3c8bd88371c76f6271d68fc5540263683cf8ed7fbb50ae0ce9678`.
Plain and ASan/UBSan hosted controls each pass 23 scenarios and 2443 checks using
the production request path with static fake transport and clock inputs. These
are model controls, not native device evidence. Independent source review now
accepts the declared serialized boot-CPU scope, with result SHA-256
`a5d595f9c89de674723954edf7deb5ff2036d277ec4b00e38acf62dc4716c353`.
Root readback verifies the complete ten-file review freeze. Ten-profile
freestanding consumption and native diagnostic execution remain pending. The
five-second deadline, FLUSH policy and retry behavior are unchanged.

The source-only Notes/Files successor retains the exact English workflow and
`notes.txt` to `saved-note.txt` rename, with separate first mutation and read-only
cold restart evidence. Its initial hosted controls pass 28 positives/37 refusals,
with no native process. Root found the same RC absence defect and an incomplete
driver selector grammar in its actual dependency verifier; the first source and
controls are preserved. Fresh source-v2 repairs those gates, pins the exact
link-input recipe and resolves ordinary recorded relative dependency paths from
their exact project cwd before checking admitted files. Hosted controls04 pass
42 positives and 129 refusals, including 87 coherent fixtures through the actual
shared product verifier. Source-v2 manifest/result SHA-256 is
`889e5671caf7223d482d23fe840ab24688aa4c00259715491c182b3353c26ce5`;
freeze SHA-256 is
`5768997337618014452a3377b84d7bb5b8e402e46de619bdb73432c80c542bd2`.
Root rehashed its complete 21-file source freeze. Independent review found a
further preflight blocker: all four historical musl build roots retain dangling
`build/Makefile` symlinks, while the required full ordinary protected-forest
inventory rejects symlinks. Root confirmed the actual preserved links without
rewriting them. Source-v2 acceptance is withheld; a fresh successor must record
the complete regular-file and literal-link musl closure and still pin every
selected static link input. No Notes/Files native compiler or guest has started
in this successor.
Fresh Notes/Files source-v3 now implements that closure before its selected-musl
gate. Controls05 pass 61 positives/188 refusals, including seventeen actual-musl
admission positives and 59 refusals with file/link/alias mutations. All four
historical musl record inventories and original dangling links are preserved.
Root rehashed its complete 24-file source freeze. Result/manifest SHA-256 is
`e000e38a45814c5ba9c507d87c87d8029591d62e6e87059a1cd236babe642c76`;
freeze SHA-256 is
`7bd695c9484d4c447e006c72b9c569d53135f3e549f230027f44f1a0d6571b31`.
Independent V3 review now accepts the source, result SHA-256
`200d348c106a3f2983e040de9201d6defcf44e5003ef20b824a848f4ee6078cc`.
Root rehashes its complete 26-file review freeze. Full production admission
feasibility controls pass five positives/four refusals using actual SDK/tool/musl
inputs and explicitly inert future-review/prior-stage fixtures, with no execution
authority. Root's concrete x86_64 Debug build admission passes the real validator.
A mistaken first CLI option exits two before preflight; its record and admission
are preserved. Fresh build attempt02 passes actual compilation and static ELF
checks for init, Notes, mv, rm and stat, with verified dependency closure and
owned cleanup. Root rehashes its complete 956-file freeze, result SHA-256
`cd8fc9865667b92de20f257ebb96c96af2da1f0b16127d45b4540bdee56eb2e2`.
Separate prepare attempt01 now passes Linux journal activation, filesystem and
application-byte checks, and actual SDK-only observer compilation. Root rehashes
its complete 999-file freeze. Actual x86_64 run attempt01 now passes first user
mutation, exact Notes save/display/replace and long-name rename, retained old
file-description/reclaim checks, distinct read-only cold restart and external
Linux-copy checks. The cold restart leaves every disk byte unchanged. Root
rehashes its complete 903-file runtime freeze, result SHA-256
`ff7c7d632ae9a627651783069918a9f25222e0454146bef28b2602f167065cad`.
This is actual musl/native application execution, separate from desktop/manual
acceptance. RV64 build attempt01 queries the correct compilers but fails xmake
configuration with `toolchain("product-cross"): not found!`; no application
compilation begins. Its complete 899-file failure freeze and verified cleanup
are preserved. Root finding NF4 traces the installed xmake generic cross
check/load fallback selected by bare standalone toolchains; the generated
product, native and diagnostic toolchains need explicit admitted compiler checks
and load behavior in fresh successors. Original passing x86_64 evidence remains
valid; the remaining three product architectures are not qualified.
The diagnostic artifact consumer's initial source is also preserved. Fresh
artifact-consumer-source-v2 binds the exact accepted V6 utility and tests its
production required-absent RC preflight. Its controls07 pass 73 positives and
53 refusals, plus two actual RC positives and eleven refusals. Its result
SHA-256 is `125c3323109528d699068ba1b2a707f2ab3bad4a7163429f96065d5850a33596`;
freeze SHA-256 is
`31a677f29c5a29155f67bffa3886d9458ef1c86f9885cc454bfd6221a69cff8f`.
Independent V2 review refuses contradictory declared input pins that were
overwritten by fixed manifest/design/review values. The exact actual production
validator accepted that inconsistent admission model; it did not accept wrong
SDK artifacts or launch a native tool. The refused receipt result SHA-256 is
`f1ae72f788465e905140ca308ed94bc697e67cbcb8fafba71e1135641a703037`.
Fresh artifact-consumer-source-v3 consistently checks every authoritative pin
merge, including admission, provenance, review, helper, tools and configuration.
Controls08 retain 73 positives/53 refusals and the actual RC two/eleven controls.
Pin regression controls pass 36 positives/18 refusals; complete production
admission models pass 23 positives/123 refusals using two real passing SDK52
producers and a clearly synthetic own-review contract with no execution authority.
Root seals and rehashes the complete seven-file source freeze, result SHA-256
`993e83b316039c07ac100091dacc2e03379e9c9618158bb0a5171173f657d14c`
and freeze SHA-256
`17dd6847c8c6ca5e259bac28c30b88d3dc4e623f316fffaf73a072b3598f9057`.
Independent V3 review now accepts the source and the V2 Root assembler, result
SHA-256 `c7427ea2cad645c71aa9f5141f5ebf75fa701a94ec8dd2f51a235b35da9dcc4e`.
Root rehashes the complete 75-file review freeze. Concrete same-profile Debug
admissions and all six native OS638 artifact-consumer commands now pass for
AArch64, RV64 and LoongArch64; their complete forests are independently rehashed
by Root. No Kernel checkout is copied or compiled. Other profile/mode diagnostic
consumers remain outstanding. The twelve-file observer/media/capture source is
sealed with 44 positives/109 refusals and real RC two/eleven controls, result
SHA-256 `99277376340feed02cfa5855c6b615d7b8cf968c780cb1e756d52f6cf7abbb27`.
It requires separate independent acceptance and concrete stage admissions;
no new diagnostic observer build or physical-failure capture has executed.
WRITE-ledger conservation does not prove semantic recovery, failed-FLUSH
durability or a root cause.
Installed SDK50 and the accepted baselines remain unchanged.
Complete M0-M12, M11 physical acceptance and M12 manual desktop acceptance remain
incomplete; the latter two are user-deferred.

## SDK52 build preparation and SDK51 checkpoint V12

Append-only Root checkpoint V12 rehashes every included frozen runtime forest
and records 284 new first-mutation passes and 75 new aftermath restart passes.
The x86_64 and RV64 first-mutation coordinators each complete all 76 new cases
across 33 groups. AArch64 first-mutation and x86_64 aftermath remain live at the
observation; all four unexpected physical FLUSH failures remain preserved.
Checkpoint SHA-256 is
`1742e9a925cc96c23d00d4b056c9a61d6a781579956e9ac292cde3299e86d7a3`.
This inventory launches no new compiler, guest, filesystem tool or volume proof.

SDK52's producer/consumer runner and strict dependency parser are being completed.
Root requires an explicit minimal launch environment so local build receipts
contain no unrelated inherited credentials or application settings. No build
admission or SDK52 export has been issued. The accepted OS-private physical block
diagnostic design is now assigned for implementation in a fresh source capsule;
the five-second deadline, FLUSH policy and lack of retries remain unchanged.
The installed private and accepted baselines remain unchanged. M0-M12, physical
M11 and manual M12 acceptance remain incomplete or user-deferred as recorded below.

## SDK51 finite first-failure and actual aftermath recovery qualification

All 48 representative SDK51 first startup attempts now pass: four supplied
static-musl profiles at producer cuts 36/38/42/44, each with interruption after
its final startup FLUSH and before/after-effect failure of its cleanup-head
WRITE. The exact selectors are FLUSH 11/10/7/6 and WRITE 10/9/6/5. Each actual
native attempt preserves P, publishes no root, executes no user program and
performs no next mutation. Complete ordered transport and all 32 MiB match the
independently generated first outcome. These are controlled software injections,
not physical power loss. Four separately frozen twelve-output Root readbacks
rederive all complete serial/volume/SDK/compiled-selector/dependency/argv proofs.
Their 48-row consolidation verifies 35,785 current file pins and complete frozen
output forests; it explicitly records 48 prior proofs and zero new proofs.
Consolidated result SHA-256 is
`67ed6f082941d3135ce6fc1713a31e2fb547fc42607f4695cf6fb195fae26bb6`;
freeze SHA-256 is
`df781c36a2b900a7479a39b1dfe1e4a6703a9144f1e85b07243bf03a7cb8fd71`.

All 48 separately owned actual aftermath cold restarts R also pass across the
same domain. Every R begins from an external copy of its actual unsealed A;
the distinct original SDK51 P and failed/interrupted A remain unchanged. The
native recovery, immutable musl init's fourteen read-only checks, drainage,
clean sealing and fresh mount execute, and the complete 32 MiB R endpoint and
ordered phases match the independently accepted oracle. Before cleanup-head
WRITE effect, family 2 re-entry has six startup operations and initial orphan
head zero; after effect or the selected interruption, ordinary dirty family 0
re-entry has one startup FLUSH, followed by its separate five-operation seal.
The four final R readbacks are separately frozen. Their consolidation verifies
39,222 current consumed pins, all 48 original output forests and the exact
four-profile/cut/case domain, retaining 48 prior complete proofs and recording
zero new guest or proof executions. Consolidated result SHA-256 is
`efb42d3588d6f8803d96aaf48118bd62631a9f3575d96b97c49923396edf96bb`;
freeze SHA-256 is
`fcc8a7e2e6cc4d74404f3de8f846562d10bd0cdb44540171ed274bcc8184aa3d`.
No Linux check or ordinary editor-write workflow is inferred from these boots.

First-attempt execution uses repaired independently accepted V2 source. V1 and
FM1/FM2 remain frozen: imports preceded its bytecode gate, and the launcher
omitted the complete consumed V4 forest. V2 changes only launcher main/inputs;
runtime, protocol and 48 recipes match V1. Source acceptance result SHA-256 is
`d8b40e11502e5e972c1bd31bf6e91dabf3f5695e1e292e8768584f21459c3ae3`.
The pure aftermath oracle's 472 positives/113 refusals are hosted controls,
including synthetic A/R fixtures and explicit SDK50 marker adaptations. Root's
independent oracle acceptance result is
`27594384cf87424ec29893213517d9ab6056eb7afd9fad9b9fbe30aeea6cdcd4`.
The actual P/A/R runtime has separate Root and independent source acceptance:
`92a2664c8a2cc2f9224a878e3eb8dca98a1a7e11ea8c0a068f84b39bd413dd0f`
and `636c23d269f5573a9064eb1ec4ca47acb449e83d5ba5c241a8cd35dffa932670`.
The latter has nine positive, 149 refusal and sixteen modeled lifecycle controls;
source review does not itself attest R execution. Its first harness failure is
preserved: sticky cleanup correctly withheld FREEZE despite diagnostic RESULT.

Independent review found an output-location gap in the Root pure evidence
helpers. V1 and finding receipt
`85d7b519e906ae6c432432d42751f99240db1dffa9b6ff806fab9887a7a11c8c`
remain frozen. Append-only V2 unions every admitted protected tree and pin before
mkdir. Consolidation also reads each frozen row ADMISSION to recover protection
omitted from old readback records. Root author controls pass one positive and
184 refusals over 91 complete input trees; the two actual V1 readback destinations
are proven disjoint and unchanged. Independent V2 source review now accepts all
three helpers with no material findings, binding the frozen source capsule and
all 39,250 current consumed pins. It also verifies the earlier cut36 V1 precursor
destination is disjoint. Review result SHA-256 is
`1ba25aa053537286afcf60ed16b7e9460f7a4a3f0f7ebe63c7547d329c700410`;
freeze SHA-256 is
`1f280b8aca5d39b3bedecdb56ee898bf2d58ab21a5613819cb175c1b2c2c1d67`.
This is source acceptance with zero new volume proofs or runtime executions.
All actual V2 destinations remain separate sibling forests.

The external R-copy Linux helper's preserved V1 CLI generator omits
original consumed forests in the readback recipe. Root's preserved finding is
`f670ecf5e54ecfee62f4152af22be361fc0f0812a54819ec9674db2a5b6557fe`.
Fresh V2 preserves the helper byte-for-byte and changes only generator recipe:
it consumes the complete frozen Root input pins and each frozen R ADMISSION's
protected trees before admitting recipe or future execution destinations.
Actual twelve-row metadata controls pass one positive and two refusals with the
permission gate explicitly modeled; controls execute no arrays or Linux tool.
Result SHA-256 is
`f16bdfe87dc0a2008ab400686592c90d3e41d02ac75e81550d384d4a39397229`.
Independent V2 review finds the same missing original forest protection in the
generator's Linux phase. Both recipe and future execution destinations could
pass its metadata gate beneath an original fixture, although the actual helper
would refuse them before Linux execution. The preserved finding result is
`398741b53d59f1b6c9a22a13f6ebbd792f674a424f2e80fe7cad3618839d9507`;
no dangerous output path was created. Fresh V3 recovers the exact frozen original
Root manifest and all R ADMISSION protected trees in both CLI phases, preserving
the actual helper byte-for-byte. V3 source result SHA-256 is
`38b09ca33daadce874cde9b5dd766e8e11921ab07eb3c9e755757d4f8d1bd064`;
freeze SHA-256 is
`74772e62fdc79aec04549c0432c65d555b926fba705f919ff595656b4f726603`.
Complete-source independent V3 acceptance passes with eight positives and 252
refusals: result SHA-256
`48c25ac33e751d13e3459f37ac9e396d3f726698ee52df3783dd756a3ca506f6`.
Actual V3 nonexecuting twelve-row readbacks pass on all four supplied profiles.
The first external-copy attempt on each profile is refused before tool startup:
CPython preserves the `PosixPath` cwd in its subprocess audit event, whereas the
guard compared it with a string. Actual `e2fsck.receipt.json` records show
`process_started=false`; the outer attempted-invocation flag is not execution
evidence. No e2fsck process or Linux pass occurred. All three other-profile
refusals are frozen, with original/copy bytes and consumed inputs unchanged.

Two x86_64 host Python attempts separately report SIG11: one initial readback
and one Linux failure postcheck. A faulthandler readback retry passes, but does
not establish the cause or repair of either crash. The partial Linux attempt
remains unfrozen and is preserved by an external diagnostic receipt, result
SHA-256 `d581358d5108469365eedde0fd8bfbadf5491a1a6de937e203d6b21e8dc518f4`.
It verifies zero tool starts, unchanged original/copy bytes and 11,395 consumed
pins; it does not accept the partial running-status result as a pass.

Append-only V4 changes only the exact cwd comparison in the execution guard:
admit a string or the concrete owned Path type, then compare `os.fspath(cwd)`
with the owned canonical cwd. Executable/argv/environment restrictions remain.
Source result SHA-256 is
`c22f56312e52887be4b601473938d41caabc1db5cbcac3fa84f1e37e871bc0de`;
freeze SHA-256 is
`a0e65d11ea6e48333bf9dfb7fe7d3bda1940d1396311a3efb00b851512c03031`.
Author controls include a real CPython audit event, accepted by V4 and stopped
by a separate sentinel hook before fork/exec. Independent V4 acceptance now
passes four positives and 181 refusals, including 29 real CPython audit events
and the unchanged protection of 74 original trees. Review result SHA-256 is
`410e1ae00fef1e0e0c3c32278ffa6fb796a2b585b472e94e3733aa49fe82781e`;
freeze SHA-256 is
`c132bd7b1eca69e4d2dcf642f4262c8d316568a515f0fecb9122cc0423f83d5a`.
Four fresh V4 helper readbacks and Linux batches now pass, twelve actual
external-copy checks per supplied profile. All 48 `e2fsck -fn` processes start
and exit zero, with separately verified owned cleanup; all original inputs,
sealed R outputs and external 32 MiB copies remain unchanged. Their result
SHA-256 values in profile order are
`f147e9cf5efcec25807e539447ae804ca976723d19fbb0177b32f742d8a55faa`,
`479f2faef8017943bbd02cbad52398d4297b13912c367eb9d320f3bdfe69a82d`,
`bdb1cecdc6b5b43d50d59b3261f7332237d975300711fd3f355551410fe33249`,
and `1ba147adac1ed152db4e626520dbde160d006f8244a37d63507e4ca6b1e5f113`.
The Root wrapper captures faulthandler host logs and returncodes separately.
The independent V2 matrix source accepts complete helper argv comparisons and
supplemental recipe pin closure. Its pure 48-row consolidation now passes:
all 48 P/A/R proofs are rederived, all 48 prior e2fsck starts and zero exits are
validated, and 39,578 consumed pins are checked. It starts no new process and
does not add executions to the prior 48. Matrix result SHA-256 is
`62d3ced36fe4e5bb475bf327ec8e176488326df47e3e0a6214100525b9216531`;
freeze SHA-256 is
`675932a60366dc3237178d6cb13f989086805659c992661e72dace8f38a8e222`.
Source review result SHA-256 is
`9450882003e599ecd6b4f79eb3a84667ad76bed2d784425061dc31bc8a3c67b6`.
V1-V3, both CLI
findings, Path refusals and host crashes remain preserved.

The exhaustive 352-case candidate is frozen and independently source-accepted.
Root has started its 304 missing actual first attempts, with one serial
coordinator per supplied architecture; the original 48 are explicitly skipped
as preserved evidence. All four coordinators remain running. Their mutable
progress results are not completion receipts; only separately frozen passing
children count as completed execution. Hosted author controls
pass 1,198 positives/64 refusals. Root reads the full runner/launcher/protocol and
independently counts 80 interruption/272 failure cases and 132 selector groups.
The accepted finite 48 cases remain a separate preserved subset; 48 groups can
bridge, leaving 84 new groups. Independent review re-admits all 48 actual finite
build closures, four cross-producer bridge closures and four launcher input
closures, retaining the original finite wrapper label gate, all six selectors
and every builder operand except output. Review result SHA-256 is
`6f0a372925724040708b8ce1fa324334e8430cb4348e6addc65335c595fba0c8`;
freeze SHA-256 is
`aff9ca502b23b3a8aecbde17c34556cca544e44570a5a2b956b687b80c3eb2d9`.
Its frozen execution plan binds all sixteen actual P descriptors, 48 prior A
references, 132 group actions and 304 missing first-attempt cases. These source
controls are not actual execution of those cases. Root's prior preparation result is
`04086296e76b8a68b2dccb9e8f8c51e1ab268210b424cc4cc10862e083e496b5`.
Expanded compiler-bound builds and native first attempts are now executing
under that exact review. The separate exhaustive aftermath runtime extension
also passes Root independent source review: result SHA-256
`f15af0388a1b1b9d500821b12d4eb5262994c169919d94cc83de80af4747ab7b`;
freeze SHA-256
`0b67796abb3dedb328df7f91b6a550e12956c10cc928d8c5aefd9532755fac71`.
It explicitly distinguishes finite48 and exhaustive352 and requires the exact
selected ordinal. Root rederives four actual expanded A proofs during source
review; the 352 domain controls and 202 refusals remain hosted controls.

Four actual expanded R cold restarts now pass: producer36/interruption/ordinal1
on x86_64, aarch64, rv64 and loongarch64. Each uses its distinct unsealed actual
A, executes native recovery and fourteen immutable musl init read-only checks,
and matches its complete independently generated 32 MiB endpoint. Their result
SHA-256 values are respectively
`94ee0e848a04b0870a6b3ecc25d7fadbb1aefb94b69f9b63c3cac765f1fa4474`,
`fbb4798eeb9216f296b78c24d2a7657a83036c0a3e03fd90c3a96728d07fc3a1`,
`69e2bd4c39dff86ee00af7ba64572de0f1cd06cf30941874b4ff9fd16a593d5c`,
and `d690ccd17d28759992eda21cc6208edca066724047c9e5e4ea2913c7b330d2e2`.
These are four new R executions, separate from the preserved finite48; the
remaining 300 expanded R cases are now dispatched, with one serial coordinator
per supplied profile. Each waits only for its exact frozen A, rederives the
entire admitted A proof, and selects an existing distinct family 2/0 restart
artifact. The original 48 R and four separate expanded R are explicitly skipped;
running coordinator results are not completion receipts. Root source review
result SHA-256 is
`653e20ad6f59c8881aa3ce5183cc615a8094b07768c9e5442ec52975613c8657`.
Pure expanded evidence and Linux consumer successors are being implemented
separately. No installation,
promotion, Linux result or ordinary Notes/Files workflow follows from these
storage failure boots.

Append-only `ROOT_CHECKPOINT_V6.json` records a frozen-child snapshot of 58 new
passing A attempts (14/12/16/16 by the supplied profile order) and the four new
R passes, retaining the distinct original finite48. Its SHA-256 is
`c7ccdaa275cb26d37249168de64ef421782ab0be1608b2908a663d5080f2e3fd`.
It binds completed receipts and identifies running sessions without treating
their mutable coordinator results as frozen completion. Later execution is not
retroactively included in that snapshot.

Append-only `ROOT_CHECKPOINT_V7.json` records a later frozen-leaf snapshot:
144 new A passes and 17 new R passes, excluding the original finite48 from both
new counts. Every included leaf freeze inventory is checked; no frozen new
child failure is present in that snapshot. It records the 48 completed finite
Linux checks and the still-running per-profile A/R coordinators. SHA-256 is
`a924229bb9d38c4eb2c808566fe6f4d766b3f6ea5607618bb2161c7c2ebc1872`.
The Linux matrix completes after that snapshot and is recorded above.

The expanded pure R helper V2 is independently accepted with 18 positive and
205 refusal controls and seven actual prior P/A/R proofs rederived. Root's
separate four-expanded-R readback now passes with all complete 32 MiB endpoints,
serial phases and SDK/build lineage checked. Result SHA-256 is
`3487d136dfe8ba1a939d5a87e55c852a7a408c05d64923a09c2f9e63c4473a40`;
freeze SHA-256 is
`7c139a75fc5d39e49dbb74a752f7721ca51246ce343694456970e7dc14149d71`.
Its coverage is explicitly subset4, not full352 or new guest execution. The
expanded external-copy Linux consumer is independently source-accepted with
41 positives, 361 refusals and 17 real Popen audit events stopped before launch.
It rederives four actual expanded P/A/R proofs and three preserved finite-case
matrix links, retaining 41,172 consumed pins unchanged. Acceptance result
SHA-256 is `d20f9b1e6d991b1194269fcb6a5fabef8d85a3270c1ec4d940a101c2d83c29d7`.
Root's separate expanded4 before-Linux readback and actual external-copy checks
now pass. All four e2fsck processes start and exit zero with verified owned
cleanup, unchanged original inputs/outputs and unchanged 32 MiB copies. Result
SHA-256 is `04eb080678dad77b323662efb694e9b8a9206aedfb4eb5d0244e185def17ba3e`;
freeze SHA-256 is
`a1bc293f4a197a62560974c828b9a7301a3c442ef3d78ca43fe935328ffdb8ef`.
These are four additional Linux checks, distinct from the original48 and still
subset coverage; original48 checks are never rerun or counted as new.

Append-only `ROOT_CHECKPOINT_V8.json` checks every included frozen-leaf inventory
and records 191 new A passes and 40 new R passes (including the four separately
executed expanded R). No frozen new A/R failure is present at that snapshot.
It binds the completed finite48 Linux matrix, four-profile fresh product builds,
actual Notes/Files first-boot rename failure and its external-copy diagnosis,
and preserved Release failures. SHA-256 is
`517f1f987230176a9e827bb1b9a0cd7ba102115061d5e5b49aa38d9477a2e0ba`.
The separate expanded4 Linux checks complete after this snapshot; later runs
are not retroactively included in it.

Append-only V9 uses the exact immutable A/R plans to enumerate runtime leaves,
rehashes every included complete frozen inventory and preserves all V8 runtime
descriptors. It records 214 new A passes and 53 new R passes, including the four
separate expanded R, with zero frozen new A/R failures at its snapshot. The
expanded4 actual Linux receipt is now included, giving 52 separate external-copy
e2fsck starts and zero exits together with the preserved original48. No new
complete-volume proof or guest runs in this inventory step. V9 SHA-256 is
`f712d0ff1fbc00576c6424cfc2132772b1cf11386cbb69133f4bb8197131ca59`.

Append-only V10 rehashes the complete planned frozen leaves and preserves every
V9 descriptor. It records 261 new A passes and 69 new R passes, including the
four separate expanded R, and four frozen native failures. The LoongArch64 A
coordinator and AArch64/RV64/LoongArch64 R coordinators are terminal exit1, with
their complete coordinator and failed-leaf forests retained. Actual serial
records show unexpected device-called FLUSH status11: A LoongArch64 ordinal8
before selected ordinal10; R AArch64 ordinal14, RV64 ordinal6 and LoongArch64
ordinal13. The wrapper's generic terminal-pass error is not a diagnosis. These
are not coordinator timeouts; no host-load cause or absence of user execution
is inferred from unset wrapper flags. Independent driver/source/transport
diagnosis is active, and no failed campaign is automatically restarted. Four
other handles remain live at this observation. V10 SHA-256 is
`81eb5c8fbeeeb726fd6cf553d2c389d9d8525122dd2d86c8b7acda11494a06d2`.
It also binds the completed ten-profile bounded Release readback below. The
52 existing external-copy Linux checks remain distinct; no new Linux process,
guest or complete-volume proof runs in this inventory step.

V11 records 280 new A passes and 74 new R passes, with the same four frozen
native failures. RV64 completes all 33 selected groups and 76 missing A cases;
its coordinator exits zero and its complete frozen forest is independently
rehash-checked. The other three observed handles remain running. V11 binds the
SDK52 source/hosted contract reviews and the read-only failure diagnosis, while
retaining all V10 runtime descriptors. SHA-256 is
`8c8ce8c1790a38bd6788288df6f0934567b9f301f795e0bea667da68f8d72b90`.
This is another complete frozen inventory snapshot, with zero new guest,
complete-volume proof or Linux execution in the snapshot operation itself.

A separate Release native-CRT regression runner is exercised against exact
frozen SDK51 consumers. The V2 terminal CRLF/LF mismatch and V3 stale ext4
symlink marker failures remain frozen. V4 passes the x86_64 simplefs POSIX,
path, VM, time, poll, pipeline and Notes save/reopen checks. Its ext4 POSIX,
path, VM and pipeline checks also pass, but Notes saving to `/home` reports
`Permission denied`. The original staged ext4 `/home` inherited host UID/GID
1000 and umask-derived mode 0775; the bootstrap init runs as root, and Notes
requires matching ownership without group/other write permission. This is an
actual packaging-policy defect, not a passing Release workflow. V4 result
SHA-256 is `4922fcedb768b9227f82e61acf7dcddfdad89849853d0f677716c546c43ccaa0`;
freeze SHA-256 is
`445772cb80ff9e49d23f8e250f3c3aa2746f161a7fa8c74d03ce616a18bf21bb`.
A fresh explicit bootstrap-root policy composition and separate user1000
journalled product lane are being implemented. Source V5 admits only a complete
frozen composition bound to the same Release producer and rejects a completed
shell response lacking its outcome immediately. These same-boot checks do not
qualify journalled recovery, musl, restart durability or clean shutdown.

Independent V5 runner review withholds source acceptance because the serial
receive loop can retain unbounded bytes before its time deadline. The preserved
review reproduces 16 MiB retention; its result SHA-256 is
`3175d9b8f7c6cd1266f5a79f64772d32f83b3c55e233f1c4142d7dc3c4ed8087`.
Append-only V6 enforces a 4 MiB per-filesystem limit before appending or writing
each chunk and retains explicit overflow diagnostics. Independent source review
passes 31 positive and 46 refusal controls. The exact extracted receive loop
refuses chunk 513 before append/write, retaining and logging 4,194,304 bytes
and diagnosing the rejected 8,192-byte chunk. Both existing x86 compositions
and their 2,494 consumed pins are admitted separately. Review result SHA-256 is
`68dfeef52df8048e1842611fcb4406af33682789523c8b5372142e90ebb08cb8`;
freeze SHA-256 is
`d36fbf0ca000954e0a4f6dae7477c91f149924433dc7bf018e62aa55c01207e5`.
These controls execute no guest, compiler or Linux checker. The fresh actual
x86_64 V6 composed-root smoke now passes both simplefs and ext4. Each runs
POSIX/path/VM/time/poll checks, the shell pipeline, Notes save/reopen and file
stat; each separately verifies complete owned guest cleanup. Root rechecks
the complete frozen output forest and every command's response interval.
Result SHA-256 is
`299ddc27c6039be5485ead544b4a0d43e29c003eb509b13f2164d8bdd39d88d2`;
freeze SHA-256 is
`5b8d3f91b2caf1f1b04b7393ca54fd6bfde201f09028f9ae5332f84c689525a2`.
This attests the existing x86 bootstrap-root artifact and same-boot native CRT
workflow only; the other nine Release profiles and composer source repair
remain open, as do journal restart, ordinary user1000 and musl acceptance.

Two explicit x86_64 bootstrap-root compositions have completed actual xmake,
mke2fs and read-only e2fsck execution under host umasks 0002 and 0077. Both
independently rederived artifacts have the same 34 guest paths, metadata and
25 regular-file hashes, with `/home` owned by 0:0 and mode 0700. Whole images
differ because of mkfs identifiers and timestamps. The existing artifacts are
valid inputs for a separate Release smoke; the composer source remains
unaccepted. Its independent review requires removing or admitting inherited
configuration selectors, revoking the tool-launch permit when log opening
fails, and checking intended inode types. Finding result SHA-256 is
`10e8dc16ee12e37d831fe3fda673db492c268b0bc681fbf423b20ad61e3d1866`.
A disjoint source successor is being repaired before further compositions.

The preserved V3 review verifies the permit, inode-type, exponent, bounded-pipe
and terminal-state repairs, but finds another default xmake RC input outside
the closure. V4 preserves inherited HOME, records canonical system/user/fresh
global RC lookup paths and requires their observed absence before and after
execution. It pins the installed RC-resolution implementations and explicitly
does not claim resistance to concurrent host configuration mutation.
Independent V4 source acceptance passes 66 positive and 76 refusal controls
with zero native processes. Review result SHA-256 is
`b885387c8cb6a7e3ac058752d790de9aa7e5482ff9867bec73473bfd07d25bca`;
freeze SHA-256 is
`575b7ae0948e88e3056354f5510899a2d546949b70c50a50b8ebc21038401eea`.
Root then executes all nine remaining explicit Release root compositions.
Each actual xmake/mke2fs/e2fsck sequence passes with unchanged protected inputs,
preserved HOME, observed RC absence and verified owned cleanup. Their exact
recipes are retained in `ROOT_REMAINING_NINE_V4_COMPOSITION_PLAN_V1.json`.
Fresh V6 native Release guests for these nine architectures all pass in three
serial groups, each against its own frozen composed artifact. Together with
the earlier x86_64 smoke, all ten profiles complete twenty actual native CRT
guests, one simplefs and one ext4 per profile, and 100 shell commands. Root's
separate pure readback rehashes every full run/producer/composition/policy
forest, verifies all command response intervals and owned cleanup, and checks
24,788 current consumed input pins. It executes no new guest or tool.
Matrix result SHA-256 is
`c170cedc1dbd8bfc8f011901ccfde6c6793e4a0bebe049b7cd35ea2b784bd0a5`;
freeze SHA-256 is
`7afe0ed660c8de83312dc83cc0960ab0a76f8911b83cf4d933d6e2333ca86afa`.
The x86_64 input remains the independently rederived V2 artifact; the other
nine use accepted V4 composition source. This closes the bounded Release
native boundary/Notes same-boot lane. Journal restart, user1000, musl, shutdown,
SMP, hardware and full Release qualification remain separate gates.

The separate OS632-derived Notes/Files V2 application slice passes 32 actual
host-file controls in both ordinary and ASan/UBSan xmake builds. Mv and Rm anchor
parent descriptors, commit with renameat/unlinkat, synchronize the affected
parents and consume each close once. A committed operation whose completion
fails reports that distinct outcome. The preserved V1 unreadable-parent
permission regression is repaired in V2; an independent unwrapped eight-case
permission check also passes. Production Notes remains unchanged. Its actual
save/replace, retained old descriptor, move/remove and fresh-process English
reopen workflow is covered on host files. Hosted result SHA-256 values are
`0860a70aea1db98859e2ceec8c7792569d821055b7556f18fdb86fb4d6328db5`
and `c35c515dd10dcd583edf070075bd9569dc2830805b4631e2d0bebb74cbe4d23b`.
These results are not native or journal-restart evidence. A new immutable musl
first/restart fixture requires user1000 and private home0700, exact Notes stdout,
stable rename identity, retained replacement/removal descriptions and read-only
restart checks. Its four-profile product builds and normal writable provider
composition use a separate successor; immutable failure observers are not reused
or modified. All five fresh application targets compile through xmake on all
four supplied musl profiles. The first missing app-library include build failure
is preserved; successor build result SHA-256 is
`aeabc4e295cd85a35b1a66b9e949a5ac6e95a18e0e5757e43f977198e9dc1aba`.
All four native SDK-only ordinary-root compositions also compile. The ordinary
OS journalled provider needed a private off-stack reclaim workspace, which the
fresh production storage successor supplies without changing immutable SDK51.

The actual x86_64 first user1000 boot saves and displays Notes, replaces the
file with the old open description retained, and closes/reclaims that old inode.
Mv then fails with ENOSYS before namespace commit. An external-copy diagnosis
confirms the actual directory has a 20-byte source record (12-byte name capacity)
and a 968-byte free record. The requested `saved-note.txt` needs 14 name bytes;
SDK51's fit-only rename planner refuses directory-record allocation. Updated
English content remains intact and the destination is absent. First-run result
SHA-256 is `e375a217900726cba11d8eb6b27e654fd42dabcc2edff1e9a6612918346152bc`;
freeze SHA-256 is
`81a139d7d8995e47c5d8acb09c53119645f42c7f9248be8ca5049af71ecb9c9d`.
This is an unmet Kernel mechanism gate. The fixture names remain unchanged;
absent-target directory-record allocation/relocation must be implemented and
qualified before this default product workflow or its cold restart can pass.

A separate SDK52 Kernel successor implements bounded relocation within
the existing single directory block. Its design preserves the fit path and
old-source before-image anchor, validates the complete block before selecting
an unused record or occupied-record slack, and refuses ENOSPC when no donor
fits. Root has accepted the design only. Hosted, journal-failure, cold-replay,
exact SDK export/consumer and native Notes/Files acceptance remain separate
gates; no frozen SDK51 header or immutable application fixture is changed.

The exact SDK52 relocation candidate now contains 1172 source files, retaining
all 1162 parent paths with fourteen changed/new paths and no removals. Fresh
xmake qualification passes all eleven suites in both plain and ASan/UBSan
modes, plus ten freestanding architecture probes. The planner has 21 checks;
owned models cover free/slack publication, checkpoint, cold replay and reopening,
before/after-effect write/flush faults, torn journal heads and noncanonical
replay images. Existing fit regressions remain in the same qualification.
Result SHA-256 is
`4378c0a021d9c96b86b693f916a80fdba3c36633beb5d21aa832fab622fcbcba`;
freeze SHA-256 is
`9ca5ce812e1019712753c2fec491f49c76d4bdba56aaac70cb0ac9c13a667e3c`.
Four model-media reference checks and independent e2fsprogs journal replay also
pass, result SHA-256
`1f9a8c52d65c73fb968c87f97a3b706419be9b58618a4e0b68ebc34b115a9219`.
The test-formatting build failure and the initial reference oracle's omitted
needs-recovery bit clearing remain frozen. The final review handoff SHA-256 is
`dbf8d58acf310d7269180bad3b583ed29242cf69a6e5629b5cd5091ccb7714b7`.
Independent source acceptance has completed; fresh SDK52/ABI51
export/consumer/native qualification is pending. ABI51 accompanies the revised
fit-or-relocate capability profile; the plan layout and journal format are
unchanged. No SDK52 artifact is exported, installed or promoted by these models.

Independent relocation source and hosted-evidence review accepts the changed
Kernel C++ without material findings. Extra plain and ASan/UBSan controls each
pass seven planner, twelve replay/prefix and seven checksum-valid forgery
refusal cases, covering donor-before-source layouts, maximum names, exact slack
and global unused-record precedence. Leak checking remains disabled after a
preserved ptrace-environment failure. The original acceptance result is
`361f33075e5b66b5a0631ad4e4ead6fce149c5fbaef39f30aa8bb0e5a329edb4`.
Its top FREEZE mistakenly includes its own empty-file hash; Root retains that
metadata defect and rehashes all 43 actual original files into a separate
ordinary complete byte-readback capsule, preserving the independent acceptance
payload and every source/control artifact without repeating controls. The valid
Root readback result is
`8854703016bdab477b67aef61e44f2be269c45a8fc014691fc4d33a4a33431ce`;
freeze is `0ac517f8064839fcbdc9e0f184e93f79cbcb6f3d303d6f1f54550d3c3cc7f0d7`.
Future generic qualification/reference launcher authority remains excluded.

A separate frozen packaging source pair preserves the Kernel1172 candidate
and derives the OS consumer from exact OS632 sources. It revises ABI/exported
capabilities, retains the admitted Notes/Files V2 application and immutable
workflow sources, and adds only the production off-stack reclaim workspace.
The SDK supplies the architecture UAPI; no borrowed prototype UAPI or prototype
xmake project replaces the distribution build. Accepted V4 bootstrap rootfs
policy remains separate from the journalled user1000 product volume. Kernel1172
and OS635 preserve all parent paths with twenty explicit changed/added paths.
Manifest SHA-256 is
`7b280df34ca5ecd321edc3618bb6d278c7f7be4eb885159cc6f1dbea8ec6d293`.
Root independently rehashes the complete 1817-file packaging forest and exact
parent/delta/overlay maps, then passes thirteen producer, fifty OS SDK and
twenty-seven pressure contract tests in a fresh source copy. These ninety
hosted tests use packaging fixtures and no target compiler or guest; the mocked
export fixture's host archive invocation is not an actual Kernel SDK export.
The review result is
`71d40d427c3bb1dba8bce253299bda9f5f85a7bfbbc680329ee2adc1efcbf34f`;
freeze is `dd2cb8e9546c22f6aac3e7a8105591f77feffa931e01ffa2660707fdca3ec378`.
The initial Root review's mistaken overlay-root layout is preserved separately;
it failed before any command or review output creation. Fresh bounded SDK52
producer/consumer runner source and its dependency closure are being authored.
Runner acceptance and fresh SDK-only builds remain pending; no SDK52 build
admission or export has been issued.

The four-failure read-only diagnosis verifies 20,336 input files across eighteen
frozen forests. The device returns fault11, while the fixture's selected
io_error is16. Two R failures occur during seal after the actual user/read-only
checks and drainage; one R and the A fail during startup. All four final images
match successful WRITE prefixes, which does not prove the failed FLUSH was
durable. Dropped physical messages, clock samples and completion fields prevent
identifying timeout, device IOERR or invalid completion. The separate 300-second
host capture wait also waits after a fixture failure and does not establish an
I/O latency cause. Diagnosis result is
`44488e035a04c79da6308a1a71134f8ef7f06118170f02426b3feff906a42526`;
freeze is `c10c95bad666f8848336b4a285041646338306969a7c956d86b57f9eda061e07`.
A bounded OS-private request diagnostic design is accepted only; implementation,
fresh controlled native diagnosis and any repair remain pending. Five-second
fail-closed deadlines, FLUSH and no-retry behavior are unchanged.

Root's static review separately withholds generic future acceptance of
`reference_check_v2.py`: it lacks protected output-overlap admission before
mkdir and bounded, explicitly admitted tool environment/cwd/log lifecycle.
Finding SHA-256 is
`a8ca9af96213e9185ae24f27a0731b07a18a8fbd19600470aeafdbb66eb971ab`.
The actual reference-attempt02 destination is a canonical disjoint sibling of
qualification-attempt02. Its observed model-media checks remain distinct from
generic launcher source acceptance; no further reference launcher is executed
by this review, and Kernel C++ source acceptance is assessed separately.

Private Kernel1159/OS632/SDK50/ABI49 and accepted Kernel919/OS623/SDK41 remain
unchanged. The ten Kernel architectures and four supplied musl profiles are
preserved. ELF e_flags and cumulative native-stack qualification limitations are
not extended by these runs. Full M0-M12, the other six musl ports, full Release
qualification, default English Notes/Files persistence, networking/services,
isolated desktop and SMP remain incomplete. Physical M11 and manual M12 remain
deferred by the user.

## SDK51 actual active recovery and separate cold restart

The four supplied static-musl profiles now pass all 32 actual SDK51 active
recovery and separate cold boots: x86_64, aarch64, rv64 and loongarch64 at original
cuts 36, 38, 42 and 44, each with an active first recovery and an ordinary second
boot. All first/second pairs match their respective complete source-derived
32 MiB endpoints. The original SDK50 producer lineage remains explicit in these
32 runs. The ten Kernel profiles are preserved; this four-profile runtime lane
does not qualify the other six musl ports, Release, SMP or physical machines.
Root completes the other-24 readback, independently rederiving every serial and
complete-volume proof and checking each current build/argv/SDK binding. Output
index SHA-256 is
`f98ed94ff9085a4077a4ebfa823b783d3c0aab204d1bfb9d8ef97acee1219129`;
readback result SHA-256 is
`0f9f9136c4714330644c8e05c680765139198c80a578c9804b47513e522e91d0`.
Actual read-only `e2fsck -fn` passes on all 24 external copies, with zero exits,
complete serial/volume rederivation before and after tools, unchanged original
and copy bytes, and unchanged consumed inputs. Linux result SHA-256 is
`79d8233df3676a83ee84f6794fc8e1292db470b316e675c5a494b5b0d095b9ec`;
freeze SHA-256 is
`6867a74088d46ce1c10a8dfd7adf59adf159c5386e6fb51bf0eedb49198c160f`.
Together with the separately preserved eight x86_64 checks, all 32 outputs now
have actual external-copy Linux checks. Root's complete 32-output inventory and
sixteen first/second pair index SHA-256 is
`efda0a8a0d2fed82a95852bfdd1a2743261a286705d8c897feb8e589b1ccca1d`.
Root's separate Linux receipt/copy readback result SHA-256 is
`ad4a22dd6561652a7f923a862548eb59f83c77e0c72ad9dc9a421cf4e7cf6e33`.
Its initial read-only aggregation precheck incorrectly refused the source
receipt's additional `schema=1` field before creating an output or running any
tool. That refusal is retained separately; the successor accepts and checks the
explicit schema while still rehashing the complete source inventory. No native
or Linux execution failure is inferred from this Root precheck.

Sixteen new actual SDK51/ABI50 producer-prefix captures now also pass, separately
from those SDK50-origin recoveries: four profiles at all four active named cuts.
Every capture executes the native producer and immutable static-musl init, stops
immediately after its selected successful Virtio FLUSH and matches the complete
independently generated 32 MiB prefix. Root rederives all sixteen prefix/volume
proofs, all actual build dependencies and 17,932 unchanged consumed input pins.
The producer-output index SHA-256 is
`4e58e18827e8787af1bb516c883938dd3a9d91c932975fb78d1acff65b3dea6f`;
readback result SHA-256 is
`3c7c750c7f04dfcf54b12b881b580df425e6ee73fb7521a848a98ffb3d542c8e`.
Independent producer-runtime source review SHA-256 is
`a7fbd5dc9e38cd53523a9f161aa6569381f699db6b5425d2e7ba415f2c0c6a3e`.
These are producer captures, not recovery-after-failure or ordinary distribution
workflow qualification. Their process, build, SDK and source evidence stays in
separate frozen forests.

The four-profile external-copy Linux helper's V1 missed current-row argv and
SDK-manifest comparisons. Root finding L4-1 remains frozen with V1. Append-only
V2 adds both checks before the byte snapshot, output creation and tool launch;
independent AST comparison proves these are its only executable changes. Eight
actual first/second record-value controls and 48 in-memory binding refusals pass
across all four profiles. Accepted source-review result SHA-256 is
`1509b4b3c77a5fcc536a76a4ad083be1569e182425a638520576245cef15f8f2`.
This source review invokes no guest or Linux tool; the actual other-profile
Linux checks are the separate successful execution receipt recorded above.

The SDK51/ABI50 provider now passes eight actual x86_64 active-recovery boots:
original cuts 36, 38, 42 and 44, each followed by a separate ordinary second
cold boot. Every first boot executes the source-derived WRITE/FLUSH operations,
the unchanged static-musl `/./init` and its fourteen read-only checks, resource
drainage, clean sealing and a fresh mount. Each second boot uses its actual
sealed first output, executes eight operations and the same user checks, and
retains the original producer separately. Every output matches its independently
generated complete 32 MiB endpoint and named operations. First and second
endpoints agree within each cut; endpoints from different cuts are not all
identical. The complete eight-output index SHA-256 is
`9e734754d2cad1c86874e83f1914ed969c934aed476ef69b160104cf6ca52b1f`.
The index command's final cross-cut equality assertion failed after writing both
indexes; this was an incorrect summary predicate, not a failed guest. Root's
separate full freeze/image readback verifies all eight successful outputs and
each first/second pair, retaining the distinct cut endpoints. Correction receipt
SHA-256 is
`f3021ceddbcb79f031ea769d6a7b2ca82fea6b7c8d7a513604d96b26f4e469fb`.
Cut 36 first result SHA-256 is
`c1ca22397c56bcb605b3d83ef011f0b1e28420316e3e00d601560ec604b4a03e`;
second result is
`8bb0eeff66c346784ac8b7ab33af6f09e19101a4c0ec2370f654f5cac390b036`.
Actual read-only `e2fsck -fn` checks pass on external copies of these two
endpoints; neither frozen capture is used as a tool input. All original/copy
bytes and admitted inputs remain unchanged. Linux result SHA-256 is
`8ec3b2b33d1a0bb520817ef2a465996adedbaf5a43a84d192d1c47b381c1cf4e`.
The initial Linux helper V1 omitted output exclusions for imported generic
Linux/provenance forests. Its first-two actual lane is disjoint and remains
preserved with that finding. Append-only V2 adds these exclusions and complete
input coverage checks; independent review accepts its exact source after 51
isolation refusals, sixteen main-path refusals before output/tool creation and
three postcheck mutation refusals. Review result SHA-256 is
`7174487cbfc1d94ea2713d94c8182e9c07b31014b9c8403b94289b724131b15b`.
Actual V2 read-only `e2fsck -fn` now passes on external copies of the remaining
six outputs (cuts 38, 42 and 44, first and second). It rederives every complete
guest serial/image proof before tool launch and again after tool completion;
all original/copy bytes and admitted source/provenance inputs remain unchanged.
Result SHA-256 is
`d12f8ffb838de223b1610e89f37434341998c5eecba970ca773ae0ab0fa45a50`;
freeze SHA-256 is
`c9d442e0fe8af43b3038a618c0d4b28806c0abf80e0b0d491dbf7ba66ec5754a`.
Together with the preserved first-two lane, all eight x86_64 endpoints have
actual external-copy Linux checks.

The original producer generation is explicitly 50. Its SDK50/ABI49 lineage,
unchanged baseline/facts/header/init identities and complete prefix evidence
are revalidated against the new SDK51 consumer. These are not new SDK51
producer captures. All four first recoveries and all four second boots pass.
No interrupted-recovery or injected
I/O-failure aftermath is qualified by these successful boots.

The runtime helper V4 passes independent source review after three preserved
findings: uncertain cleanup could permit a freeze, the first seal lacked
complete runner/build/argv and serial/byte rederivation, and conventional
toolchain symlinks caused preparation refusal. V4 saves diagnostics before
withholding authority after sticky cleanup failure or remaining descendants,
fully rebinds/rederives the first output before the second, and protects the
whole toolchain path while hashing exact consumed tools/dependencies.
Independent review SHA-256 is
`3e6ac03b913858ef4038c4dc3271f7a5dab9467a121233158ec071f3305a9405`.
The first 90-second actual attempt remains frozen as a timeout; the same
admission succeeds within the permitted 300-second deadline. Source inspection
finds repeated whole retained-table validation in physical scans, rather than
a fixed operation-7 hang. Performance optimization remains separate work and
must preserve the lifetime and corruption checks. Two parallel invocations
were refused by QEMU's boot-image write lock before native execution and remain
frozen; consumers sharing that exact boot artifact are now run serially.

All six x86_64 native builds now pass (four new producer selectors and two
recovery selectors). Six additional recovery builds pass on aarch64, rv64 and
loongarch64. They consume existing exact fresh Debug SDK51 exports and do not
compile Kernel source or export another SDK. These build receipts record only
compilation; the later actual execution receipts above are separate. Their receipt indexes are
`c4b0f2d8c020160024ec6172b128833d6db96b3ebb243bf43810a2bc9d3f9db3`
and `3cabd9d8c3d456ba02e6e2f9e3b51afd2f8e70cc3a0121df4b7ca3854659ff5c`.
All twelve additional producer selectors now also compile on the other three
supplied userlands. Root rehashes the complete eighteen-build artifact forests,
SDK contents and actual dependencies, and repeats exact compiler-bound selector
validation for six recovery and twelve producer builds. Complete other-profile
build index SHA-256 is
`26604684d5035b7707c59ad857cfafc7a63f89341d7e5f8af3ba026c26b0b305`.
No new SDK51 producer capture or other-profile active guest is inferred from
these compilation receipts. The architecture-aware runtime successor now passes
independent source review. Its exact source SHA-256 is
`2ce2efadc3aca6917fd5163fa30feee2e5b465b09bd7d69a3a218c6e852d05db`;
review result SHA-256 is
`ce0fe2a528cbf24c83409ba29a3e69bdba8029b2b421aec62d9940ae605f2417`.
The delta requires matching architecture through original capture, recovery
build, SDK, first receipt and runtime argv; all cleanup/freezer gates remain
unchanged. Root completes full preflight admission for all twelve other-profile
first recoveries, index SHA-256
`adcb6d92dd76ddc373c420f2f8507aaff34cc217ed09db52fc3030c4b9b2ef6f`.
The cut-36 first recoveries on rv64 and loongarch64 now pass actual execution,
complete endpoint/serial proof, fourteen read-only user checks, drainage, clean
seal and fresh mount. rv64 result SHA-256 is
`dacfb5155854f938c75f4f6f1cb8bfc3404e92c58873c349cb5d8b8387094d4c`;
loongarch64 result SHA-256 is
`5c3a2d58b901423b838e3762a034a26caf6eabf5f50ebb12507d83953d70e4f5`.
Their separate second boots and all remaining first/second cuts on all three
other supplied profiles now pass, giving 24 other-profile outputs. The retained capture helper
accepts only deadlines up to 300 seconds. Root's three initial 600-second
invocations were refused at its first statement, before QEMU/log creation; all
copied disk bytes equal their immutable inputs. These refusals and their
conservative unknown launch metadata remain frozen, separately explained by
Root receipt SHA-256
`372a21f137ad8a8b612739ac191e3a257b986e432f6a8bd054d8f825ca7a44a7`.
Fresh successors use the supported 300-second deadline.

Independent readback of the remaining nineteen Debug/Release SDK producer and
consumer forests and twenty Debug native OS outputs also passes: 62,531 file
hashes, 2,916 actual compile commands and 16,028 consumer dependency records.
Readback result SHA-256 is
`a48080b4eb1eab7276b958526afa5ecf8b223c54f42317f8c8c0469edf97ace4`.
Separate independent source review now accepts the exact frozen readback helper
for its documented scope: sixteen positive controls, 23 refusals, complete
source/receipt binding and independent inspection of all 1,624 current consumer
compile lines. Source-review receipt SHA-256 is
`411dab6e949ca570f3bfd0514aaa2e03c56c6dcffd082c8ca63545c38dbcaf88`.
Its ELF metadata reader does not validate target `e_flags`; this review does
not extend its stated metadata checks to ABI-flag or execution qualification.
Existing failed build attempts stay frozen. These records do not qualify
Release execution, the other six musl
ports, an isolated desktop, SMP or physical platforms.

No successor is installed or promoted. Private Kernel1159/OS632/SDK50/ABI49
and accepted Kernel919/OS623/SDK41 remain unchanged. M0-M12 remains incomplete;
physical M11 and manual M12 remain user-deferred.

## V38 completed cold restarts and ABI50 target compilation

All forty SDK50/ABI49 cold-success campaigns now pass: the four supplied musl
userlands at cuts 24, 32, 34, 46 and 51, with twenty first recoveries and twenty
separate second cold restarts. Each executes the native observer and unchanged
static-musl `/init`, verifies its complete 32 MiB volume and named transport
operations, retains original/first/second lineage and proves owned cleanup.
Root's complete readback independently rederives all forty whole images and
10,248 admitted input pins. Readback result SHA-256 is
`69ca5aef5faf231a96d877083dacb288ab7cbfe433eb3a0ba3f4841a227e915f`;
the complete output manifest SHA-256 is
`05ff50838562f71eae11cf2aab3fd090eadd65a252233d4a082a8d70481296aa`.
These successes qualify empty-log orphan and ordinary recovery. They do not
qualify the SDK51 active-reclaim writer.

Independent review found a proof-before-tool copy defect in the retained V1
Linux-check helper. Root's append-only V2 reads one snapshot, verifies it against
the admitted endpoint, copies it and verifies the completed copy against the
same endpoint before invoking Linux. The V1 source and finding remain preserved.
V2 passes seven positive and twenty-two refusal predicate controls, plus two
positive and three source-extracted in-memory copy controls. Independent V2 delta
review passes two positive and eight refusal controls. Actual read-only Linux
checks on all forty external copies now pass; all original and copy bytes remain
unchanged. Linux result SHA-256 is
`e924b356e32da1cd3b2e8d9fe2438ab141f59d1633a5e3ef94034b3194dc6993`.
No Linux tool operates on a frozen native capture. A relative-path invocation was refused before output
creation and is retained separately; the unchanged helper is running with
explicit absolute paths.

The exact SDK51/ABI50 complete source also passes actual full-provider target
compilation on all ten architecture profiles. Complete `-MD` ownership, executable
ELF function witnesses, ABI flags, eleven required active-source dependencies,
source/tool/evidence hashes and owned cleanup pass. Maximum individual frames
range from 12,712 to 13,008 bytes, below the exclusive 16,384-byte limit. This is
target compilation evidence, without a nested-stack or guest-execution claim.
Target result SHA-256 is
`da33b971a6920851ce51c3e159e9ea2bf033fa70aaf79763f7d469f5946de1ad`.
Independent complete target readback also passes 13,405 input pins, 1,206 target
outputs, 1,500 dependencies, 8,339 frame rows and 8,977 executable function
symbols. Its acceptance SHA-256 is
`cedaafa0be1625976660f46f15d3422446585ba04f295adda9e1c017cc5f22b5`.

Fresh SDK51/ABI50 Debug exports, standalone Kernel QEMU and SDK-only OS consumer
builds now pass on all ten profiles. The explicit ten-profile receipt index
SHA-256 is `5ad9f40243745ccebd7dc2532792ac994f4551f8beb423b3740f723d0cb348b6`.
Independent x86_64 artifact readback verifies producer/consumer source and
dependency ownership, all SDK files and actual standalone boot; acceptance
SHA-256 is `550c2570b00113a8574b033593ddb1d2dedb47b8dd640d30fed76c226359ba75`.
Twenty additional actual native OS distribution guests now pass: simplefs and
the existing ext4 subset on each of the ten profiles, using external disk copies.
These native boundary checks do not qualify musl on the other six profiles or
the new active-reclaim recovery path. All ten Release exports/consumers also
pass, closing the twenty-combination Debug/Release artifact build matrix.
Release guest execution remains a separate gate. The twenty Debug native guest
receipt index SHA-256 is
`2dc3d83d77ee2cedeb319f1e4f3e3f9b07579e38ae514079c6570177e6758af1`.

Failed orchestration attempts remain frozen: an unsupported task option, xmake
configuration loaded from the wrong cwd, and missing QEMU executables inside
three compiler-only toolchains. Successors use project-local cwd and explicit
installed QEMU paths. Source review also found quote parsing before command
filtering, an ambiguous compiler-invocation substring and missing preflight error
receipts. Append-only V6 repairs these reporting paths and passes four positive
and three source-extracted refusal controls. No failed attempt is relabelled.

The source-derived active-reclaim native observer, producer and byte oracle are
in an isolated candidate. Its pure controls pass 136 positives and 52 refusals.
Independent review refused the first builder's selector cardinality and cleanup
diagnostic handling; the append-only V2 repair now passes source and predicate
review. Its independent review result SHA-256 is
`23c3da2015f3563922859a520a60b88758722ef37a92b9c8c0e917e296b20f10`.
No active-reclaim guest success is inferred from the ordinary-recovery or SDK
boundary runs. The separate limited actual SDK51 successes are recorded above;
the remaining active-recovery campaigns stay open. No successor is installed or promoted; private
Kernel1159 / OS632 / SDK50 / ABI49 and accepted Kernel919 / OS623 / SDK41 remain
unchanged. M0-M12 is incomplete. Physical M11 and manual M12 remain user-deferred.

## V38 native interruption captures and cold-startup qualification

All 36 frozen Debug SDK-only consumers and actual QEMU producer-prefix captures
now pass: x86_64, aarch64, rv64 and loongarch64 at each successful-FLUSH cut 24,
32, 34, 36, 38, 42, 44, 46 and 51. Each capture matches the complete attempted
payload/actual-return trace, selected terminal counters, independently generated
named journal prefix and every byte of the origin-zero 32 MiB raw volume. The
prepackaged `/init` is unchanged. These are interrupted native producer prefixes,
not completed normal workflows or cold recovery. The complete36 frozen handoff
SHA-256 is `c92adc4da5fc0a0d5f88899f7a6ea1cb8399214b2ab2b1f82a29d04499a16389`;
complete independent readback now passes all 36 captures, 1,388 transport events,
whole-volume prefixes, complete artifact bindings and owned cleanup. Its receipt
SHA-256 is `8382a60f89d9a1a0c6b5264e160250f078dd47e3d4006a52d7fc3cf1694bc747`.

Review of the cold-recovery build helper V2 found that unrelated `g++ -c` lines
could satisfy its selector-count check. V2 is preserved and refused. V3 binds
selectors to the exact compiler/source/object identities in actual dependency
records and passes independent source review, 62 hosted positives and 171
refusals, including the old false-admission case on all four profiles. The same
loose gate is retained
in the frozen producer harness, so Root separately verified all 144 actual C++
commands across the 36 captures by their exact dependency identities and cut
defines; all passed. This actual-artifact readback does not repair the retained
harness. Complete independent readback repeats the stronger check for all 144
commands; its separate checker passes 23 positive and 48 refusal controls.

Four fresh SDK50 Debug cold-refusal observer builds now pass against exact
family 2 / refusal / absent-seed selectors. Root repeated complete frozen
SDK/source/dependency/object/selector/frame readback; maximum individual frames
are 12,784 / 12,768 / 12,848 / 12,784 bytes. All sixteen actual cold-refusal
campaigns now pass: four profiles at cuts 36, 38, 42 and 44. The original Session
becomes quarantined with `unsupported`; no root is published, no user is loaded
and no WRITE or FLUSH occurs. Root repeated exact serial and entire-image proof
over 536,870,912 compared bytes. Its receipt SHA-256 is
`9e607b761c18d1de35d2856f76c20115e9adde8676e19255d48e91038ff83885`.
These are unsupported refusals, not successful recovery or musl execution.
Independent V2 parser review and complete16 actual readback now pass, including
88 independent parser controls, all 7,358 admission input pins, complete image
comparisons and exact dependency-bound recovery compile selectors. Receipt
SHA-256 is `c9018fe247b9b4c817a85252810392d9bc1986a5f984029dbc897ce1f17f1163`.
The four V1 runtime attempts are preserved: genuine zero-mutation refusals passed
the image gate but failed an incorrect parser requirement that the observed
Session remain owned and error-free. Append-only V2 requires exact unsupported
quarantine; it retains all image, source, cleanup and no-user gates.
Build readiness receipt SHA-256:
`67f15bebfaea212970629b5c03c59d96ed61894a86f3d7ea7f91a6578bd4db7b`.

Four immutable dual-role static-musl `/init` packages and generated headers now
pass independent complete source/SDK/compiler/header/link/ELF/package readback.
The review rehashed 7,202 unique files and independently reconstructed all four
complete packaged volumes. Literal initial paths `/init`, `/./init` and
`/././init` select unchanged producer, absent-seed recovery or present-seed
recovery behavior from the same disk inode; the recovery roles perform read-only
file checks. Captured images need no executable replacement or transformation.
The independent receipt SHA-256 is
`0fe3119b93fc17d62c6f8e3ff6d83ff1bcf6188b72bbbb254c2d1e60491fc08c`.

The cold-startup observer passed source review and complete retained x86 SDK-only
development-build readback. Its unpublished-root assertion agrees with the
exported startup report and precedes owned-root retention/publication. It observes
original/terminal Session lineage, checks a selected zero-mutation refusal or
executes the unprivileged read-only init, drains resources, seals and remounts.
The x86 BIOS payload is 3,288,168 bytes within the 8 MiB export limit; maximum
individual frame is 12,784 bytes, without a total nested-stack claim. This
development build selects seed absence against an intact seed-present baseline
and is compilation evidence only. Runtime recipes bind family, refusal and
seed visibility to each actual immutable capture. Cold-refusal guests and the
forty successful cold starts described above have now executed.
An isolated successful-recovery byte/transport oracle is frozen for empty-log
orphan cuts 24/32/34 and ordinary cuts 46/51. Its hosted synthetic controls pass
43 positives and 121 refusals; independent pure-oracle source review now passes.
Its receipt SHA-256 is
`63fab9566e03efc870b3aef84437009589da0edda92911b56c363a10d68c5ce8`. The
source-derived first-boot mutation counts are 28/6/8, followed by eight operations
on each separate second restart. Eight fresh family3/family0 Debug SDK-only
consumers now pass complete Root artifact/SDK/source/dependency/ELF/frame readback,
including 32 exact actual C++ selector commands. Build-readiness SHA-256 is
`e5aa21a35e1868d849ff28ec6f1a81f0e81a72d26abca874a5fded0bf81525b5`.
Root refused the V3 harness before execution because its output exclusions omitted
the frozen helper tree and outer successful-build forests. The append-only V4
repair passed independent review and executed all forty successful cold starts;
the V3 source and refusal remain retained. The installed active writer refusal
is unchanged.

The interrupted-prefix oracle preserves every accepted V37 oracle byte and adds
four pure functions for exactly nine named successful-FLUSH cuts: 24, 32, 34, 36,
38, 42, 44, 46 and 51. Root source review and a separately retained hosted rerun
passed all 36 four-profile positives and 122 corruption refusals, with all four
normal APIs retained. Acceptance requires complete attempted payload/actual-return
pairing, one immediate terminal interrupt with exact counters, the selected
phase prefix, independently generated named journal operations and the entire
captured raw volume. Observed transport replay alone cannot pass. Root review
receipt SHA-256:
`1bb5c5c445ed0b44238bf89b9d8ed0769f1352e9b2534c3c6bc6c7dbdcc0aa3a`.
These controls are synthetic host evidence, not native interruption or recovery.

Isolated Kernel prerequisite V4 passed independent source review plus ordinary
and ASan/UBSan/vptr controls: 225 states, 3,941 block comparisons, 289 refusals,
40 absent future images, eight external full goldens and 97 raw-cache-slot
controls. It supplies a stage-specific media resolver, same-Owner one-shot
read-to-write handoff and five-FLUSH accounting, while retaining the original
active-reclaim unsupported gate. Full noncopyable attachment, exact in-flight
writer ledger, complete READ budget and remaining-row checkpoint integration
are implemented in an isolated candidate. Independent source review found
operation-ledger comparison and post-geometry-callback authority-check gaps,
then an unbound live Session volume origin. Exact V8/input06 now passes independent
source review: live first/count changes quarantine the original Session; a pending
failed dispatch is accounted once by paired finish without completion credit or
a next WRITE. The bounds guards add no transport READ. Source-review receipt
SHA-256 is `ef2d90ce256ddfe6294602712732564c89a94c2b3a6deea63112f817f553542e`.
All six V8 hosted plain and ASan/UBSan/vptr suites pass, including eight whole-volume
goldens, 12 transport failures, 15 callback authority refusals and 18 Session
volume-bound controls. Hosted result SHA-256 is
`ccda2769a0deae39f5a57e48b5db3bbe23ef37d49253848eef54bc8fd2905ecd`.
Root repeated complete source/hosted/independent-review readback. The earlier
target admission and V1 helper are preserved but refused: the hosted snapshot
was not a complete Kernel tree, and the helper lacked complete probe, tool,
dependency and output-tree gates. A complete SDK51/ABI50 source successor now
preserves Kernel1162 and OS632 files, including all useful baseline tests and
the exact reviewed V8 changes. The changed public Owner/provider contracts need
ABI50; existing SDK50/ABI49 bytes remain unchanged. Root independently
reconstructed all 26 exact source deltas and rehashed both source trees. Source
partition receipt SHA-256 is
`6b58120239495328b73072c3e3537a51aeea455e3b419840ae012f78a157bcbf`.
Independent source-partition acceptance now passes all 1835 unchanged mapped
leaves and 4227 input pins, with no unresolved source finding. Its receipt
SHA-256 is `ea5cea2acf2f2532770b02d60d78e96cd591bcf465cb636d82b12f3f113ba3b4`.
The exact successor also passes 90 hosted ABI/export/consumer fixture tests:
13 Kernel export, 50 OS SDK and 27 OS pressure controls. No compiled SDK artifact
or target execution is inferred from these fixture tests. Hosted result SHA-256
is `4502601c2b0e705014c34ede3e31cb5597de2ea7a96cf59af8a0a5cf8798e91e`.

The original successor freeze accidentally included a concurrently edited target
helper. Root's whole-map readback refused that helper drift; source bytes and
manifest remained unchanged. The invalid whole-map claim is retained, and the
new Root receipt explicitly admits only the unchanged source/evidence partition.
Further helper work uses an independent sibling directory. Ten-profile target
probes now pass; fresh standalone Kernel/SDK export and OS consumer qualification
are in progress as described above. No prerequisite source is installed.

Root repeated all ten selected GCC/backend/assembler and loader identity queries
with the actual restricted per-toolchain PATH and no compiler prefix override.
The retained closure covers 40 complete search trees, 9505 tree files, five
explicit loader/tool leaves and three loader symlink hops. These are live
identity queries without target code generation. Exact query result SHA-256 is
`223c4a6b6cf16b43748a58335abcd0a6b25371175d16c3a2d4ab1fb81981c983`.

The interrupted producer harness, Root launcher V3 and complete immutable
admission passed source/control review before the 36 actual captures. Admission
rehashed 10,861 explicit inputs and bound all exact recipes. Recovery still needs
full-volume origin/journal/transport oracles, separate Linux compatibility copies,
a second cold restart and recovery interruption/failure controls. Private state
remains Kernel1159 / OS632 / SDK50 / ABI49, unpromoted; accepted Kernel919 /
OS623 / SDK41 is retained. M0-M12 is incomplete. Physical M11 and manual M12
remain user-deferred; default English Notes/file-management, networking/services
and isolated desktop work remain open.

## V37 four-profile native unlink retention and reclaim

Observer V5 passed independent source and complete retained x86 SDK-consumer
readback. Root sealed final V5 readiness and a normal-only four-profile admission,
rehashing 2,556 explicit input files, full retained SDK inventories, frozen OS
sources and per-profile packages. All four fresh Debug SDK-only consumers and
actual static-musl QEMU campaigns passed: x86_64, aarch64, rv64 and loongarch64.
Each executed genuine fork, inherited/shared and independent open descriptions,
unlink with two surviving holds, non-reclaiming intermediate closes, last-close
reclaim, child exit/wait, complete resource drain, sealing and a fresh mount.

Each campaign matched all 51 real write/FLUSH attempt-return pairs and exact
write payloads, the independent named namespace/reclaim journal transactions,
intermediate volumes and the entire captured final volume. Durable frontiers
were 23, 46 and 51; read-only e2fsck passed without changing the captured image.
Maximum individual frames were 12,784 / 12,768 / 12,848 / 12,784 bytes; these
measure individual compiler frames, not the complete nested call stack. Complete
independent native-campaign readback passed all four profiles, including repeated
whole-volume/journal reconstruction and read-only fsck with unchanged captures.
Final independent review SHA-256:
`d8a9b4b91647726d5672a0d164ed5b96ed25ec05b59f7cb36a9b2511aa2ddfd4`.
Qualification is limited to these frozen Debug single-vCPU normal campaigns.
No V37 source is installed
or promoted, and no unchanged standalone Kernel qualification was rerun.

Admission SHA-256:
`8ec1609c1e4eea4b9cd62866e51f363218edd726894a09104c85bb33d27e0833`.
Four-profile readback handoff SHA-256:
`7c776cc98ca97ca67363441cccef59107c95e574d19a8326afc500dcb78a4ed8`.

V38 startup design independently identified a required one-time same-Owner
read-to-write handoff, a fifth active-reclaim FLUSH, immutable origin histories,
stage-specific expected media and exact first physical C1/result binding.
Isolated prerequisite implementation is proceeding while the installed
active-reclaim writable refusal remains intact. QEMU durable interruption and
fresh-startup recovery still need actual qualification. Distribution workspace,
default Notes/file-management workflows, networking/services, isolated desktop
and the remaining M0–M12 gates remain open. Physical M11 and manual M12 remain
user-deferred. Four V38 dual-role static-musl inputs now compile and pass Root's
full artifact/header/link/tool and independent ELF-layout readback. Their exact
literal initial paths select producer or read-only recovery checks from the
same `/init` inode, preserving capture bytes; packaging and startup execution
remain separate gates. The earlier recovery-only input remains preserved.

## V37 native reclaim observation and exact input preparation

Four pinned static-musl C programs and per-profile on-disk `/init` images are
prepared. Packaging preserves private/seed/peer raw identities and data, checks
all extracted program bytes and ELF identities, full-image allocation differences,
read-only fsck and reproducibility; native execution is still pending. The exact
four-profile `/init` package independent review passed. Root also rehashed all
four complete retained SDK50 inventories, frozen OS helpers and sealed package
inputs. These host/source checks remain separate from guest acceptance.

Observer V4 adds distinct complete drain/fresh-mount checks, explicit original
boot cwd identity and retirement, clears its borrowed victim pointer on reclaim,
and emits every exact 1 KiB attempted write in bounded 128-byte hexadecimal
chunks. Actual namespace inode/parent time facts and a stable-wall-generation
last-close clock interval enable an independent middle-transaction oracle.
Two source/API target failures remain preserved; exact V4 compiled against the
installed SDK50 on x86_64 at a maximum individual frame of 12,784 bytes, followed
by complete target/dependency/frame readback. Its first exact `/init` consumer
build then compiled and linked but failed BIOS assembly: an initialized reclaim
workspace produced a 10,404,816-byte payload, exceeding the exported 8 MiB limit.
V5 preserves that failure and uses aligned static zero storage with explicit
one-time workspace construction before the provider. Its x86 consumer build now
passes with a 3,292,264-byte payload and the same maximum individual frame.
Independent V5 source/readback review and formal native execution remain pending.

The harness V1 independent review required stronger compiler/process/source/frame/
phase/capture checks. A separate V2 passed isolated controls and independent delta
review. V4 added strict payload/clock handling and corrected protocol binding;
V5 closes its two remaining source-loader/time-domain gates and passed independent
delta review plus all-four frozen oracle API readback. The native-specific oracle
independent review passed four synthetic profiles, 111 refusals and 93 CRC library
cross-checks, with all selected witnesses and 51 whole-image snapshots verified.
These are host controls, not user execution. Independent
source review found that deferred reclaim preserves the unlink timestamp, so
protocol V2 requires both commit timestamps to equal the observed namespace time.
The last-close bracket separately observes execution order. Observer V4 remains
unchanged by that timestamp correction, and the original protocol is preserved.
Formal guest acceptance must independently reconstruct and match selected
namespace/reclaim journal records, all transport
attempt/return pairs, intermediate images and the entire final volume before a
normal guest result can pass. Payload replay or the generic host endpoint oracle
alone is insufficient. No V37 source has been installed; active-reclaim startup
and distribution workspace wiring remain gated. Installed private state remains
Kernel1159/OS632/SDK50 ABI49; M0–M12 is not complete. An uncompiled V38 producer
and recovery-user draft prepares actual successful-FLUSH interruption frontiers;
active-reclaim writable startup still requires its separate mechanism change.

## V36 formal native acceptance and private SDK50 installation

The complete final V36 gates passed: the unchanged Kernel V4 models cover 36
hosted executions and 40 full-TU probes across all ten profiles. Fresh standalone
Debug66 Kernel/SDK producers and exact SDK-only OS consumers passed for x86_64,
aarch64, rv64 and loongarch64. All twelve actual static-musl guest rows passed:
normal root-retention/drain/seal/reopen and two injected seal failures per profile.
Independent SDK and native readbacks verified entire frozen inventories, actual
compiler dependencies, individual frames, controlled guards, full-volume oracles,
transport traces and fsck/recovery. Largest individual frames were 12,784,
12,768, 12,848 and 12,784 bytes respectively; this is not total nested-stack proof.

Final independent provider, VFS and OS source reviews and the V3 transaction
installer review passed. Exact complete installation admission passed verify-only,
then installed the archived 38 Kernel and nine OS source deltas. Post-install
readback verified both complete source maps, all staged/original bytes, transaction
publication and exact SDK manifest/artifacts. Private state is now **Kernel1159 /
OS632 / SDK50 / ABI49**, unpromoted. Accepted Kernel919/OS623/SDK41 is retained.
The first verify-only tool invocation used a mistyped admission digest and was
refused before mutation; that Root invocation failure is preserved separately.

Installed readback SHA-256:
`48503ee924ab2ffe11cbf93d56830b77d5183c25943ad76fa3b0d505b84fd11b`.
ROOT_STATE_V8 SHA-256:
`6fd946cb2f48c2a3e6a20ebf4a6da6b314f5ab225dd92847ee7477ffaeea89b2`.
V37 is dispatched for actual unlinked-inode retention/last-OFD-close reclaim.
Its four new C fixtures compiled against pinned static musl and passed full
artifact/header/link/tool/ELF readback, but have not executed. The host-only
private/seed/peer image oracle separately passed independent CRC/negative/fsck
review; its synthetic retired-inode control is not a Kernel reclaim result.
Per-profile exact /init packaging, native-specific journal/transport/full-image
oracle and actual four-profile execution remain upcoming gates. Active-reclaim
startup and distribution workspace admission remain closed. M0–M12 remains
incomplete; networking/services, isolated desktop/app work and remaining standard,
format and platform gates continue. Physical M11 and manual M12 stay user-deferred.

## V36 OS public-API repair and x86 development acceptance

The repaired native fixture uses public read-only recovery inspection, accounts
for the actual boot process cwd hold, and checks quarantine denial while retaining
the original sealing I/O failure in the provider report. OS candidate V2 freezes
632 files and the same nine private-parent deltas; its only change from OS V1 is
`tests/native/mounted_root_retention.cpp`. The Kernel V4 source and passed
36-hosted/40-target/ten-profile model qualification remain unchanged.

The successor runner corrects the fault-selector overwrite to exactly nine bytes
and compares both complete disk guards with each row's exact input. Independent
review passed five helper acceptance rows and 6,223 corruption refusals. x86
**development** build05 and all three actual musl guest rows passed using preserved
SDK02: normal sealing/reopen, failure before sealing, and failure during sealing.
The campaign includes actual fork/exit/wait and retained OFD/cwd release, entire
volume oracles, transport traces and host fsck/recovery. Campaign RESULT SHA-256:
`56b4a84b40da372ac64875dd11922d6c1de59f033a3d9d74aa79b763a4f18837`.

Frozen OS V2 handoff SHA-256:
`4cb1ac5f8d98f07904b0185e4090c501f3740123c16d984cf76a6fd888c26d63`.
Fresh successor SDK consumer and four-architecture native campaigns, independent
source/readback gates and private installation remain pending. No source has
been installed or promoted; accepted Kernel919/OS623/SDK41 and private
Kernel1151/OS630/SDK49 remain unchanged. M0–M12 remains incomplete; physical M11
and manual M12 acceptance are user-deferred.

## Root retention and resource drainage in implementation (V36)

The installed private state remains Kernel1151 / OS630 / SDK49 ABI48 at
ROOT_STATE_V7.json; accepted Kernel919 / OS623 / SDK41 is unchanged. The isolated
SDK50 V36 lane is implementing exported ABI49 layouts without narrowing the ten
Kernel profiles or four supplied musl userlands. No V36 install or promotion has
occurred.

The development implementation adds provider-issued, move-only root references,
owned operational VFS mounts, child-first one-way detachment and permanent mount
ID tombstones. Stale context IDs are checked before dereferencing node pointers.
Provider drainage gates final close/seal on actual root and inode leases; legacy
raw exposure permanently refuses qualified teardown. Scheduler cleanup consumes
all fd/cwd edges while recording the first failure independently of child exit
and wait status. Kernel member order/destructor drainage keeps VFS and UDP
backing storage alive. The OS journalled-root publication now uses the retained
SDK interface and records its attachment, with reconstruction refused after first
placement construction. These changes are in the lane, not the installed state.

Root packaging development checks pass 13 Kernel export, 50 OS SDK and 27 object
pressure contract tests. The latter's invalid BIOS fixture and obsolete negative
ABI case were corrected with the original failure preserved. The added point66
refusal model passes a hosted development run; its first missing memory/clock
link inputs are also preserved. Agent VFS development has passed the owned model
under all ten selected profile definitions plus legacy and O0 ASan/UBSan controls;
these are hosted binaries, not target ELF/hardware execution.

Candidate V1 freezes 1,159 Kernel source files and 33 changes, but is explicitly
unqualified. A retained mounted-lifetime regression subsequently exposed that
ordinary media failure must stop new publication without preventing authentic
existing lease cleanup. Provider corruption must still retain exact failure
evidence. This correction requires a separately frozen V2 after the final
provider, lifetime and resource regressions and independent review. Candidate V1
will not be exported or installed. Root checkpoint SHA-256 is
`33586f938f7b528c5dad74fdc12b18dc8f5ffd7d78a4ec80e18bab68a1d5fb12`
at `build/prototypes/sdk50-v36-root-provider-retention-v1/ROOT_CHECKPOINT_V1.json`.

Further review found two teardown admission gaps. Borrowed publication of a
node obtained through a retained path must still record permanent raw exposure;
the repaired VFS has passed 21 development checks. A real mounted-provider
retained-path alias reproduces failure against the old frozen VFS and now refuses
teardown permanently without preceding raw root/lookup exposure. An erased
mounted deferred-orphan pointer must not hide the real Owner's pending cleanup.
The private no-I/O Owner preflight checks actual admission/startup/seals,
operation/reclaim records, canonical transactions/participants/slots and the
original Session. Focused ordinary/sanitized root and orphan suites passed;
each root run passed 2,462 checks across 245 cases. Three authentic pending-unlink
erasure/restoration controls and six fsck outputs passed. Earlier
snapshots and failures remain preserved. A root native-runner review also caught
an SDK identity mismatch before execution: experimental SDK50 exports manifest
ABI49 and module ABI49. Its correction is separate from native qualification.

Candidate V2 now freezes 1,159 Kernel files and 35 deltas at handoff SHA-256
`dc596e918e4183243bcd37d1041ae0a19b3adfdd5ad15f7ed52842476c60bae1`.
Reciprocal review excludes each agent's own implementation; the independent VFS/
resource review verifies the complete frozen inventory. Exact final all-nine-suite
development regressions passed 18 executions and 14 fsck controls, with complete
frozen-source and 251-dependency readback. Combined frozen attempt01 is preserved
as failed: the child fixture enabled its compaction-hook definitions only in its
test executable, leaving the shared Scheduler core without those hooks. The
original assertion is retained. The harness now directly compiles that fixture's
Scheduler/process/architecture support with the same private definitions, matching
the separately qualified resource recipe. Attempt02 runs the corrected child
first and then the complete campaign; no product/frozen source changed. SDK and
native exports remain gated on its successful full result. The combined campaign
includes 36 hosted ordinary/sanitized executions and 40 freestanding compiles
across ten explicit profiles. Root checkpoint V2
SHA-256 is `3a38fdae60ea2299a6c9d3e5145270c56800beee6ff63cbc9a6364255b730caa`.

The frozen OS consumer has 632 files and nine deltas at handoff SHA-256
`db7d915d0dcc991aeb97cc81db46412988e578de225a21bee9ac33b652736306`.
All four supplied static-musl lifecycle executables and exact on-disk `/init`
inputs passed independent readback and offline fsck. Their preparation supplies
no native execution result. The native runner's distinct experimental SDK50 /
manifest ABI49 / module ABI49 gates and process-group timeout controls are
qualified separately. All three additional producer toolchains/QEMUs are
available; profile campaigns refuse the failed model receipt before creating an
attempt. Source review, hosted checks, target compiles, SDK consumption and actual
native execution remain separate gates.

Retry02 has passed the child, root, owned-VFS, resource, point66, dirty,
startup and startup-route suites in both modes, plus ordinary namespace C1;
the complete result is still pending. The first root SDK waiting launcher
exited before export after reading an in-place JSON update. Its failure is
preserved in ROOT_SDK_WATCHER_FAILURE_V1.json. A separately saved V2 launcher
retries transient incomplete JSON and still requires a passed terminal result
and complete matching freeze; the SDK qualifier independently checks every
frozen artifact before creating an attempt. This is a harness correction only.
The complete x86 SDK/native pipeline now has one owner: startup_guard's saved
runner. Root's replacement watcher was stopped before export to avoid competing
attempt creation; ROOT_X86_ORCHESTRATION_HANDOVER_V1.json records that transfer.

Retry02 subsequently failed the full-provider target frame gate after all36
hosted executions and ten fsck controls passed. The i386 listing/read-operation
frame is 27,136 bytes; other emitted profiles also exceed 16 KiB. This is the
actual provider directory-list path, exposed by full template instantiation,
not a fixture-only stack allocation. The passed hosted checks do not qualify
this attempt. RESULT SHA-256 is
`854592fc393f9c5fa31bbdb4f263ec6613c7726e9916ed8c7045fb036d3ef85d`;
FREEZE SHA-256 is
`cc2b1418d45c4cfddbac031c59a8f0cfc82cd0f2a50d30c7aee4892e952000b9`.
Both gated pipelines stopped before SDK creation. A separate successor must
reduce the real result-storage frame, retain the full provider/ten-profile
measurement and preserve the source, lifetime and read/error semantics.

The development repair now constructs one caller-local listing Result in place
and lets the unchanged admission/lease/cleanup wrapper return Status while filling
that payload. It adds no shared scratch or capacity reduction. The unchanged full
provider probe passes all ten profiles at 12,712--13,008 bytes per largest frame;
independent exact ELF/dependency/tool/frame readback also passes. Four earlier
stack trials remain preserved, including three failed storage approaches. The
existing mounted-lifetime suite now covers checked listing/data, 64 entries,
65-entry overflow, reentry refusal, original media failure, I/O lease release and
owned teardown; its existing ordinary/sanitized slots keep the formal campaign
at 36 executions. Final constructor, empty/independent-result and cleanup
precedence controls passed ten development executions across five suites and
six fsck controls. A root
freeze precheck refused a test-source tuple mismatch before creating a candidate.
The final08/15/16 complete artifact inventories and exact three-file source delta
subsequently passed root readback. Candidate V3 freezes 1,159 Kernel files and
37 deltas from the installed private parent, at handoff SHA-256
`537b68e297384423e8c785c17e924aebd33d2be3fa2b9b45e796a9dc95b274a5`.
The OS V1 freeze remains unchanged. Complete attempt03 now runs forty target
probes before the thirty-six hosted executions and fsck controls; its reordered
harness has a separate independent review. Exact SDK inputs V3 bind these
successor paths. SDK export and private installation remain gated on complete
qualification; writer admission stays closed. Root checkpoint V5 SHA-256 is
`e6dbd002b67cf7eceb4f8e74a6b10ca86b434669297c674b0349bf48b35a9d74`.

Attempt03 failed before hosted execution or SDK export on the full VFS frame
gate: i386 `with_retained` listing cleanup uses 18,048 bytes, and RamNode listing
also exceeds the unchanged 16 KiB gate. The provider repair remains retained;
the next repair must reduce listing/result duplication in the VFS/RAM paths
while preserving fallible retained-path cleanup and operation-error precedence.
Failed RESULT SHA-256 is
`4342efda02fad4b667a372be5a26d252eaeb4c851166db22330936eeec04a91f`,
with FREEZE SHA-256
`73c3537768561a0f1d9777278e9c792d3fcd7d3a6fde447c232dd7b8a705fa19`.
Candidate V3 remains unqualified and will not be installed or exported.
The twenty otherwise unreached resource/point66 target compiles subsequently
passed a separate development preflight on the unchanged frozen V3 source:
resource maxima are 11,432--15,792 bytes and point66 maxima 12,712--13,008.
This does not qualify failed attempt03. Preflight RESULT SHA-256 is
`1ea6be558f55ce9195ce03a38d8c365d5c513c56df657f1f7ba99cecc1a9869a`.

The VFS/RAM storage repair reduces full-TU frames to 9,200--10,544 bytes on
all ten profiles. Its first added RAM test expectation failed on block accounting
and is preserved. Independent preliminary review then identified a Status-only
success-message difference. Root implemented the suggested compile-time Status
merge branch and added distinct mutation/cleanup success messages to the existing
matrix. That test reproduces the predecessor difference; corrected attempt03
passes all twelve ordinary/sanitized runs across six suites and all ten complete
VFS target probes. Exact source and all 44 hosted/10 target dependencies pass
readback. This is a root-resolved review finding, not a post-correction independent
agent runtime review. A separate append-only receipt corrects inherited attempt02
freeze paths in the first Root readiness metadata; code and measured maps are
unchanged.

Candidate V4 now freezes 1,159 Kernel files and 38 private-parent deltas at
handoff SHA-256
`5812db46543c4b24f077025c69aca1c6cc100d1e87196674bdf26dafb4d2358d`.
OS V1 stays exact. Complete attempt04 has passed all forty target probes before
the hosted campaign. SDK inputs V4 bind that exact handoff/model path. No V36
SDK or native result is yet claimed and installation/writer admission remain
closed pending the remaining gates.

Attempt04 completed all 36 hosted executions, forty target probes and ten fsck
controls. RESULT SHA-256 is
`bc349e25458edcfb2aeeaf0b865ae5e0f884d54e2164100ee9fd0f919bed8e86`;
FREEZE SHA-256 is
`9fb4da9bfec5d0112d84939b86d21e1bfc0be4250c3cd0fba71bcb521abe7855`.
The preserved reviewer-authored consistency program passed full source, artifact,
tool, dependency, frame and fixture readback at receipt SHA-256
`d7c06cf0e28a7da58e27c25a8662f43ddb4977976bdd3ed12dc1afd852655157`.
Root invoked that program; its author label does not claim a new independent
agent runtime review.

Fresh SDK/profile attempt01 builds and standalone debug66 QEMU passed, but the
gates remained failed before native lifecycle execution. The x86 helper lacked
one required transitive header dependency, although the empty-orphan header was
present in the SDK. Each other profile's dependency auditor searched source
project/build, while xmake stored actual records in attempt/build. All four
failures remain frozen. Successor harnesses retain every required header by
constructing an explicit SDK-header wrapper around the exact full-provider probe,
and select actual xmake records from observed compile outputs instead of an
assumed directory. Preflight compiled that wrapper at a 12,816-byte maximum and
read back all 86 captured consumer compile/dependency records on each other
profile. Product sources and the passed model freeze are unchanged. Fresh verbose
producer and consumer partition checks remain required before native execution.

Root launched the successor x86 pipeline03 / SDK02 and three-profile02
campaigns after the complete frozen model gate passed. These active attempts
use unchanged V4 Kernel and V1 OS sources; no result from an earlier failed
campaign is admitted. ROOT_CHECKPOINT_V8.json records the exact runner/input
pins at SHA-256
`7070e0850242766a9010e2a966a5e4d7150a662861513b518c92f65085430798`.
Independent final VFS semantics and corrected readiness metadata review passed,
including four focused replay executions and exact frozen artifact readback, at
receipt SHA-256
`c9c25f9634f54f9c150a0ca96cb4d77d945771c9be0760554277728d346fb365`.

SDK02 passed the x86 exact producer/consumer and standalone debug66 gate at
RESULT SHA-256
`13768e872c659b04e7787839b2271e42a02b3df15f2110b69b0e1199c6e2cf8f`.
All three other producer/consumer builds and actual dependency partitions also
passed. Native compilation then refused all four OS fixture builds: the fixture
called the private RecoveryCompletion prepare/binding helpers. No native guest
ran. Each complete failure remains frozen. An OS-only successor uses public
RecoveryBinding inspection plus a ready, empty-log ReplayPreview, with explicit
zero-write/FLUSH checks. Kernel V4 and its complete model freeze stay unchanged;
the corrected fixture requires fresh source review, OS consumer and native gates.

Installer V1 independent controls also exposed optional untyped source reviews,
a replacement-before-rollback-registration window and final receipt publication
outside rollback protection. It is not approved or executed. A successor must
require the exact accepted source reviews and preserve rollback intent before
mutation, including protected final receipt publication. The profile harness's
reader-admission error path also needs caught terminal/freeze handling. These
corrections do not waive any source, model, SDK or execution gate.

Final SDK consumer readback and native detach/drain/seal/reopen execution remain
pending. Active-reclaim writer admission stays closed.
Full M0-M12 remains incomplete; physical M11 and manual M12 remain user-deferred.

## Direct-read lifecycle repair installed (V35)

The private successor is now Kernel1151 / OS630 / experimental SDK49 ABI48.
Accepted Kernel919 / OS623 / SDK41 remains unpromoted and unchanged. The ten
Kernel profiles and four supplied musl userlands are retained.

Five direct physical read leaves now use a noncopyable, synchronous one-read
scope anchored to the original Session and an independently paused Owner shadow.
Successful finish verifies physical progress; the shadow advances once only
after the complete dispatcher, including external finish hooks, succeeds.
Transport errors keep priority, integrity rejection quarantines the original
Session, and clean pre-dispatch refusal spends no read credit. Terminal reads
retain odd-sector and variable sector-aligned transfers. The true startup opening
branch keeps its existing Budget; post-opening calls never reuse that closed
Budget. Balanced exhausted write/flush counters do not prevent the final available
read. Readback content mismatch retains completed accounting.

The frozen V2 has 1,151 files and ten deltas from V34. Independent V1 source
review accepts the production logic, final tests and reached diagnostic coverage.
Its single documentation finding is corrected in V2: routine begin/capacity/shape
refusal leaves the Session unchanged, unlike finish refusal or integrity rejection.
Root verifies this is the only change after that independent review; all reviewed
production, test, diagnostic and probe hashes remain exact. The installation
records this root resolution explicitly rather than claiming another independent
agent runtime review.

The formal campaign passes all fourteen hosted executions across seven suites
in ordinary and O0 ASan/UBSan/vptr modes, plus forty freestanding compiles across
all ten profiles. New scope/actual-leaf suites pass 2,089 checks across 122 cases
per mode. They cover paused prefixes, original versus decoy quarantine, retained
field and callback drift, reentry, refusal/media precedence, bounds, last credit,
three completed content mismatches and both startup branches. Existing Owner,
Budget, startup-route and standalone recovery assertions are preserved. The full
kernel point65 model also reaches seven new cases. These are serialized model
checks; fixture publication may perform earlier writes, while the read scopes
add none. Maximum individual frame is 13,008 bytes, not a cumulative-stack or
SMP qualification. LeakSanitizer is disabled for the ptrace environment;
ASan/UBSan/vptr remain enabled.

Three failed formal link attempts remain frozen. The harness corrections add the
declared ext2fs CRC oracle, isolate retained unused fixture-generation functions,
and link actual VFS code for sanitizer-retained RamNode typeinfo. No product/test
code changed during those corrections and no passing hosted execution was rerun.
Attempt04 passes and freezes 324 artifacts. Earlier development/diagnostic
preparation failures and successful receipts also remain intact.

All seven standalone x86_64 Debug Kernel/QEMU, SDK export, exact OS630 consumer
and exported full-provider probe commands pass. The SDK exports 233 headers and
239 artifacts; manifest SHA-256 is
`3dfc7d7ad5fb47146e48996b543ee3c829ff0999c3a4a4e8aa00da682d193ec2`.
Separate readback checks all 2,472 build freeze entries, forty profile ELF/frame/
dependency outputs, 43 compiled OS sources, 86 object/dependency records and
188 transitive dependency files. OS image link uses the exact SDK libraries and
linker; no Kernel source is compiled by the OS. The first reader's overly broad
compiler-line assumption is preserved. Its successor separately validates the
explicit four-source host mock-libc command and rereads the identical successful
artifacts without new compiler/guest execution.

The exact ten-file delta is installed in the private tree after these gates,
archiving six replaced originals and adding four files. Complete installed
Kernel1151/OS630 maps and all 239 SDK artifacts pass root readback. The current
artifact path and exact maps are recorded in ROOT_STATE_V7.json. V34's earlier
two-boot Notes/Mv/Stat evidence remains bound to V34; V35 does not claim another
default-app guest campaign, native mounted-reclaim admission or clean shutdown.

Evidence under `build/prototypes/`:

| Receipt | SHA-256 |
| --- | --- |
| `sdk49-v35-direct-read-guard-v1/candidate-v2/SOURCE_HANDOFF_V2.json` | `b2b0a265c78d3f601e1aba6ffcac33e2922d18ca8f499ce08a4072d87f7184fa` |
| `sdk49-v35-direct-read-review-v1/FROZEN_SOURCE_RECEIPT_V1.json` | `780a0c3706478074c37e8044ed0b3f382a5196a4b4877d16367ca40f48d6385e` |
| `sdk49-v35-direct-read-guard-v1/qualification-attempt-04/RESULT.json` | `9ba9f29ce97bbf379a2ecd9b91a9b42a030719cd17394fce8784e23d9a96dbe1` |
| `sdk49-v35-direct-read-sdk-v1/sdk-attempt-01/RESULT.json` | `963c1612adf44d2b1293e253eddbcd012f1bf900c082cf9ba05105ab784c0c38` |
| `sdk49-v35-direct-read-sdk-v1/sdk-readback-attempt-02/RESULT.json` | `4aacfc2e29e1f161bb8c0027b50734c69559204e178c4918e5d252c19fc61f9d` |
| `sdk49-v35-direct-read-sdk-v1/install-01/RESULT.json` | `89ea7eb43cab0a24ad9de9e1190012e02ae009cf51642647ed85a58fc07dc757` |
| `sdk49-v35-direct-read-sdk-v1/ROOT_INSTALLED_READBACK_V1.json` | `b40731ed86da97beb7d29acace3ae54d7d96d2ca1c59b8753eaa607efdb16d3b` |
| `sdk49-notes-replacement-private-v1/ROOT_STATE_V7.json` | `654d8b48c301139ecfd2906e142e9f5d4d5f7706e6baf24f78b49c41c13c13ab` |

The next approved V36 design covers provider-issued root retention, operational
owned VFS mount/detach with tombstoned IDs, one-way provider drainage and fallible
descriptor/cwd cleanup. It also requires VFS borrowers to retire before covered
nodes/locks, and Scheduler resources before VFS destruction. Exported layout
changes require module ABI49 and fresh experimental SDK50; old ABI48 modules
cannot be admitted. The design originally reviewed V35 V1, whose mechanism hashes
are unchanged in V2. Root's decision SHA-256 is
`29652707b77b8783797288ed1acd51d101e4c6fe5dd7c715e82033534ab9da71`.
The assignment is a specification, not a live implementation job; no V36 source
has been implemented or installed at this checkpoint.

Active-reclaim writer admission remains closed. Root/provider lifetime, native
durability/interruption, replacement/unlink/directory persistence and clean power
flow still need completion. Full M0-M12 remains incomplete; physical M11 and
manual M12 remain user-deferred.

## Plain capture Guard successor installed (V32)

The frozen 1,139-file Kernel candidate adds constrained per-call Guard overloads
for orphan-chain capture and later `plan_head` comparisons. Guard propagation
covers physical bootstrap, table, directory and comparison reads through the
original Session. Retained-memory reads and delegated history/composed views
receive no duplicate charge. The Guard is not stored in Capture. Twelve actual
Owner call sites receive fresh local read-only budget scopes; the closed startup
opening budget is not reused and no new writer authority is granted.

The new regression passes 278,529 checks across 92 cases in both ordinary and
ASan/UBSan executions, including refusal, media-error priority, original Session
quarantine, unchanged decoy Sessions and destruction of an earlier Guard.
Independent public-interface tests pass success, five failures and subsequent
planning after Guard destruction in both modes. The existing kernel diagnostic
point 65 also executes an invalid-superblock Capture using actual Session code
against a model device. The first full hosted attempt is preserved after its
composed ASan/UBSan suite reaches a 900-second limit. The selected positive
cases finish, but final failure controls and later suites/probes do not complete;
this is not a passing full qualification. A second attempt preserves that failed
freeze and reuses only its successful checks against the identical source/tool
tuple. With a 2,700-second per-command allowance, the composed sanitizer now
passes all 22 independent complete golden cases, 26 rejection cases, nine
original-domain controls and 188,752 callbacks, with zero writes or flushes.
The second full attempt now passes all 55 commands, 26 hosted executions across
13 suites, offline recovery/fsck comparisons and twenty freestanding probes over
all ten profiles. Its 2,691 frozen artifacts are fully read back. Twenty-three
earlier successful commands are reused only after exact source/tool and complete
failed-attempt freeze checks. Maximum individual frame is 13,008 bytes; this is
not a cumulative-stack or SMP qualification.

All seven standalone x86_64 Debug SDK/QEMU and exact OS628 consumer build
commands pass, exporting 231 headers and 237 artifacts. The new SDK manifest
SHA-256 is `d6acde90cfff76bd2c1ec0fecc33db81346ae90e371c2a2cbc4162a4de1506af`.
However, the parallel SDK qualification reaches its model-report waiting limit
before the full hosted campaign closes. That unqualified receipt and all
successful build evidence are preserved. A separate finalization admits these
identical artifacts against the passing second model receipt without recompiling
or repeating the guest. Independent readback verifies all 237 SDK artifacts,
43 actual OS compiled sources, 86 dependency records, 187 dependency files and
the exported public probe, excluding Kernel-source compilation by the OS.
After these gates, the eight-file delta is installed into the private Kernel,
with six replaced originals archived and the complete 1,139-file map verified.
The installed OS remains 628 files; SDK49 remains ABI48 and unpromoted. Accepted
Kernel919 / OS623 / SDK41 is unchanged.

Evidence under `build/prototypes/`:

| Receipt | SHA-256 |
| --- | --- |
| `sdk49-v32-chain-read-guard-v1/candidate/SOURCE_HANDOFF_V1.json` | `c471f402479fe1b8bc926880b150630efaf7c1dcec4e82e7d35a67ff41e169c4` |
| `sdk49-v32-capture-route-review-v1/attempt-01/RESULT.json` | `8c4494b38b8925d6d1fcf532032ba341d73e1df49a2559629c188ff4c643611d` |
| `sdk49-v32-chain-read-guard-v1/qualification-attempt-01/RESULT.json` | `f76f02604bcd3824a23fb1db3df8435f3f8728efcdcc22cde43632c15c92c2a1` |
| `sdk49-v32-capture-sdk-v1/sdk-attempt-01/RESULT.json` | `34e57deede451504e6bb135f97fda0a96d8ca0eca5f6510fbb8db08eb85f3117` |
| `sdk49-v32-chain-read-guard-v1/qualification-attempt-02/RESULT.json` | `3718665a244963a32ce49efdafab59436510b9413e87da8ddb204775cc829ade` |
| `sdk49-v32-chain-read-guard-v1/FINAL_READBACK_V1.json` | `07b8e0b6a56782d567048bd21db61737f15d6810988e7bdd8ab0278529220b96` |
| `sdk49-v32-capture-sdk-v1/sdk-finalization-01/RESULT.json` | `8328fd77a43a31828de7fb5521bd8eecd1cfe02330edd5cf1d99eaf0888f339e` |
| `sdk49-v32-capture-sdk-v1/sdk-readback-attempt-01/RESULT.json` | `93965e9cb5d0f2066d32dd29c65852a4d0d930cac1021a1d30fef5ce37147582` |
| `sdk49-v32-capture-sdk-v1/install-01/RESULT.json` | `98e6f03ab5649dcc75e377a658bfc030748be2c4e1e27c60b421d8dff4c30da2` |

Complete history/recovery routing, final Owner/root lifetime reconciliation and
native interrupted-write campaigns remain prerequisites for active-reclaim
writer admission. Full M0-M12 is incomplete; physical M11 and manual M12 remain
user-deferred. This installation has no native mounted-reclaim or SMP acceptance.

## Linux access queries and special descriptor correction installed

The installed V32-based successor connects `access`, three-argument `faccessat`
and four-argument `faccessat2` through the ten-profile Linux syscall adapter.
The shared service selects real UID/GID by default or effective IDs with
`AT_EACCESS`, applying the selected IDs to both pathname search and final DAC
checks. It validates modes/flags and supports no-follow and empty-path queries
without mutating process credentials or granting later I/O authority.

Root independently checks this bounded design against `fs/open.c` in the pinned
Linux 6.13.4 archive. The source confirms argument counts, flag admission and
separate mandatory mount-policy behavior. Independent service execution also
finds a flaw in the original frozen V3 candidate: a UID 1000/GID2000-created pipe
is checked against fabricated UID 0/GID0 fstat metadata, producing EACCES. That
candidate and the failed first reproduction compilation remain preserved. The
V4 correction supports empty-path F_OK on valid pipe, UDP socket and console
descriptors, while R_OK/W_OK/X_OK returns ENOSYS until their metadata is qualified.
Backed node and cwd queries continue to use ordinary DAC. UDP's branch is source
reviewed; its access query is not part of the executed native/hosted checks.

Both plain and ASan/UBSan suites pass 19,501 checks, including 16,384 mode-oracle
cases and ten adapter profiles. Ten freestanding dispatcher objects and the
saved-ID regression pass. A fresh standalone x86_64 Debug Kernel boots and
exports 232 headers/238 SDK artifacts. Its explicit OS630 SDK consumer builds;
the actual static-musl Linux-personality guest passes 69 assertions through
executed traps, including pipe and console refusal/existence controls. The
native storage path is nonjournalled Virtio ext4; this is no clean-shutdown,
active-reclaim or SMP evidence. Root and independent readers verify all 3,182
frozen SDK/native files, 43 compiled OS sources, 86 objects/dependency records
and 187 transitive dependencies without compiling Kernel source in the OS.
The initial model reader's generated-xmake provenance mismatch is preserved;
the corrected reader reconstructs that harness from all ten exact ABI48 flag
manifests and passes without rerunning successful suites.

After these gates, the 13 Kernel/two OS file delta is installed into private
Kernel1145/OS630, archiving seven replaced originals and verifying both complete
maps. Accepted Kernel919/OS623/SDK41 remains unchanged; SDK49 stays ABI48 and
unpromoted. Supplementary groups, capabilities, ACLs, read-only/noexec mount
policy, blocked resolution and SMP credential races remain gaps. W_OK evaluates
DAC only. This is not complete access conformance or full M0-M12.

Evidence under `build/prototypes/sdk49-access-special-fd-successor-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `SOURCE_HANDOFF_V4.json` | `ce54c317aa86046d95fc525efd3344b257cfae605854a01730567bd0873cab61` |
| `ROOT_MODEL_READBACK_V2/RESULT.json` | `63ba233cfdacee33dde2103418ccf3bfa2903501809086d45e5183842fe297d1` |
| `sdk-native-attempt-01/RESULT.json` | `521c97fc49e9f4c504ac76f43009b1e4a759cf9d316888a5ebd8d4a221435774` |
| `ROOT_SDK_READBACK_V1/RESULT.json` | `ee4250c576914894299486145a283539148234fad61bf9c5be6772b4b3d0e819` |
| `independent-v4-review-v1/RESULT_V2.json` | `63ced2d0b5704515f46d3d3018e5a08f8fbf452afdf339546b7a6751a0b571e5` |
| `install-01/RESULT.json` | `459a1544b5c3f097228cd074f05b71bff5f8a9322c179ea51ba7da274c568def` |

Evidence: `build/prototypes/sdk49-access-semantics-v1/ROOT_LINUX_SOURCE_AUDIT_V1.json`,
SHA-256 `c509c8fd343202076271ef293c835d7fffa5429aef9a19e3dfa028e75f28dd37`.

The reviewed V33 storage successor now starts from the frozen access V4 map.
It forwards the same synchronous opening-route Guard through active recovery,
capture and retained-history delegates to the original Session leaves, removes
duplicate Owner external charges and preserves success-only logical shadows.
Transport/finish failures must reach the caller before mutable callback checks.
The V33/V34 cumulative implementation is now installed as described below;
the active writer gate remains closed. Existing physical enumeration/read
capacities are retained: review found no admitted missing physical key. Design
decision: `sdk49-v33-history-route-review-v1/ROOT_DESIGN_DECISION_V1.json`, SHA-256
`b38e7501134df8ef1b3aece5cf5014339e7966d76693284bf76b9cf4a4b3136a`.

### Four supplied musl access guests qualified; automation installed

An isolated two-file OS automation successor adds an explicit four-profile
`--arch` selector while preserving the x86_64 default and all 69 guest assertions.
Compiler triples, SDK architecture/mode/compiler validation, musl manifests,
QEMU binaries, guest profile markers and one-CPU execution are bound to the
selected supplied userland. Native backing is firmware on x86_64/aarch64/rv64
and linker-reserved on loongarch64; these backing markers do not identify the
ELF's file origin. The ten Kernel profiles remain in the capability inventory.

All four actual Linux-personality static-musl/Virtio ext4 guests pass 69 checks
each (276 total). The changed x86_64 probe executes against the unchanged exact
V4 SDK/distro artifacts. Fresh V4 Kernel1145 SDKs for aarch64, rv64 and
loongarch64 pass standalone Debug kernel execution and OS630 artifact-consumer
builds. Each contains 232 headers and 237 artifacts; x86_64 has the additional
boot16 artifact, for 238 total. The initial three producer launchers fail before
QEMU starts because the supplied compiler directories lack its binary. Those
receipts remain preserved. A second attempt copies the hash-verified successful
source/tool-identical SDK outputs, then uses the pinned explicit QEMU executable;
successful producer compilations are not repeated.

Root readback verifies every frozen SDK/native artifact, each native ELF's
architecture/personality, matching on-disk /init, unique correct 69-check marker
and 43 OS compiled sources/86 dependency records per profile. For the unchanged
x86_64 distro, neither of the two changed test/tool files is a compiled source or
transitive dependency. Independent execution and provenance review now passes
for all four profiles, including 187 exact transitive dependencies per consumer.
Its first two readback attempts preserve incorrect assumptions about the x86
top-level receipt location and the unpopulated artifact map in an earlier failed
producer receipt; no successful test execution is repeated. The two-file OS
automation delta is installed into private OS630, with both originals archived
and the complete map independently read back. Private Kernel1145 is unchanged.
This is DAC qualification only, with no full access, durability,
clean-shutdown, SMP, physical or complete M0-M12 claim.

Evidence under `build/prototypes/sdk49-access-four-userland-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `candidate/SOURCE_HANDOFF_V1.json` | `6f359ed5251bb32be81b86b788634bc25a6fa9daf2ffb56353e9564ec8c61dea` |
| `aarch64/qualification-attempt-02/RESULT.json` | `59f83fb8610c2a850e3bed2895941398fc02e8e12fb285a6e2cad25319a27052` |
| `rv64/qualification-attempt-02/RESULT.json` | `e3034c10a37b00f63ec1b9549263878d819a4156d1fb08473d0b2e9b59a6e7ed` |
| `loongarch64/qualification-attempt-02/RESULT.json` | `a40d23d921dc53eedc5e5890c06c41925cf17c697f922b066ece0a809ab0e3b2` |
| `ROOT_READBACK_V1/RESULT.json` | `0d8196e43f51b1e4aa41fc874a2b1f2a5f70ce06442633db4bfc714ac8eba8cf` |
| `../sdk49-access-four-userland-independent-v1/RESULT_V1.json` | `380452f385aab15858519969ea0eb55e756a295370f7bbe1350234fab61e8ca9` |
| `install-01/RESULT.json` | `c19320c727f5cd1f89fe77e1969d14b64f0dcbd571139820d2cbf43338ed4b88` |
| `ROOT_INSTALLED_READBACK_V1.json` | `66c206917f0613037d2945236dfbc61fb80243cfa1523f7b4e7dafeae5aff099` |

### V33 history Guard integration and V34 Owner destruction repair installed

The frozen V33 V2 candidate preserves all access V4 deltas and forwards one
synchronous Guard through active recovery/capture/history views, charging only
the three original Session physical leaves. Its new plain and ASan/UBSan suite
passes 2,087,805 checks per mode across 164 cases, 104,139 exact callbacks,
three independent golden routes, 66 original/decoy controls and six destroyed
Guard scopes. Independent public tests pass four successes, 32 failures,
36 untouched decoys and four destroyed initial Guard scopes per mode, with
10,829 exact callbacks and zero writes/flushes. The complete campaign passes
57 commands and 28 hosted runs, including the legacy sanitizer suites,
recovery/fsck comparisons and ten profiles with two freestanding probes each.
All 2,726 frozen artifacts are read back. Maximum individual frame is 13,008
bytes; cumulative stack use and SMP remain separate gates.

A fresh exact V33 standalone x86_64 Debug Kernel boot, SDK export, OS630
artifact consumer and exported Binding/Capture probe pass seven commands,
retaining 65 debug points and 238 SDK artifacts. Root build-only readback verifies
all 1,790 frozen files, 43 compiled OS sources, 86 dependency records and the
45 public-probe dependencies. The initially failed probe-header admission
assumption is preserved separately. The V33 build-only receipt remains preserved
as historical evidence, superseded for installation by the V34 SDK below.

A further independent source audit finds an embedded Owner destruction defect:
`startup_route_budget_` is declared before `cache_`, so reverse member destruction
ends the original Session lifetime before a still-pending Budget can abort it.
Finish-integrity rejection can leave that pending operation. Earlier passed
synchronous Guard tests do not qualify this enclosing lifetime. V33 installation
was withheld pending the bounded V34 destruction repair. The repair declares
Cache before every embedded reclaim/capture/Budget borrower; reverse destruction
now retires borrowers before Cache/Session. Budget's fail-closed destructor and
Owner quarantine body remain intact. Both ordinary and O0 ASan/UBSan/vptr
executions pass 65 checks across six cases. An earlier O1 nondetection is
preserved. The existing route-budget regression passes 2,301 checks. Focused
qualification initially fails on an incorrect log-marker assumption, then on
an incomplete-provider compile probe. Both failed aggregates are preserved;
the corrected complete-provider wrapper reuses only hash-verified successful
hosted commands, without changing candidate source or rerunning the earlier
observation. Thirty Owner/Capture/Startup freestanding probes pass across all
ten profiles, with a maximum individual frame of 13,008 bytes.

Independent source/dependency review confirms the member ordering and six-case
coverage, then independently checks all thirty probes and the build-only SDK.
A separate final adapter admits the exact frozen SDK against the passing V34
three-probe campaign and V33 two-probe prerequisite. It does not reuse the old
build harness's inapplicable two-probe admission helper or stale failed-attempt
path. Fresh standalone x86_64 Kernel execution, SDK export and explicit OS630
consumer pass seven commands. Root final readback verifies 238 artifacts,
43 OS compiled sources, 86 dependency records, 187 transitive dependencies and
45 exported-probe dependencies. The SDK manifest is
`9c2c6234ef84d1b54781e61714bf6cac153de36796d4aa809156bc2be81cbe19`.

After these gates, the cumulative fifteen-file delta is installed into private
Kernel1147/OS630, archiving thirteen replaced originals and adding two tests.
Complete installed Kernel/OS maps and archives are independently read back.
Accepted Kernel919/OS623/SDK41 remains unchanged; SDK49 remains ABI48 and
unpromoted. No unfixed V33-only tree is installed.
Dynamic root/provider teardown and remaining direct reads remain separate work;
the active-reclaim writer gate stays closed.

Evidence under `build/prototypes/`:

| Receipt | SHA-256 |
| --- | --- |
| `sdk49-v33-history-route-guard-v1/candidate-v2/SOURCE_HANDOFF_V2.json` | `16d0b9ee2bcf999c48c2402dbe606d765ddc49ce0fadacf68ceef0ad8cc42fbc` |
| `sdk49-v33-history-route-guard-v1/guard-test-attempt-03/RESULT.json` | `5bbe9a82350904e75632e1af28cc5cd243fc8cc4560a7a3b2c811429da28fc66` |
| `sdk49-v33-history-route-independent-v1/public-attempt-01/RESULT.json` | `1f1803d20bbee31b9a63ce52a2834fc0890c6f54189991433162ac6bc3a44dfb` |
| `sdk49-v33-history-sdk-v1/sdk-attempt-02/RESULT.json` | `c9cb94ea92ea3c7ce23abba1937ea101dd5e2652a6903ed67ea2b824b5b96e52` |
| `sdk49-v33-history-sdk-v1/ROOT_BUILD_READBACK_V1.json` | `0828a18c5f56117fa699ac59430350c720595c20328823ba8e9023d5ffb4c80e` |
| `sdk49-v33-history-route-independent-v1/RESULT_V2.json` | `419f12b5d9ce485f2234e47620b9023f5f6cb72aae02ed6c57b8051fa7a86187` |
| `sdk49-v33-history-route-guard-v1/qualification-attempt-02/RESULT.json` | `f80f7b12c194b1c922a179c15fc4261b0bcffb681627aa85b04e4809dff91355` |
| `sdk49-v33-history-route-guard-v1/FINAL_READBACK_V2.json` | `f90f89a6a1536b068d76ff9720283e0561ad539f0c20400ea705a89b39aadf5b` |
| `sdk49-v34-writer-guard-review-v1/candidate/SOURCE_HANDOFF_V1.json` | `050b7d66a893788dc96347aa93d95c1ed01e648f6456a68a18296e4cf747fa11` |
| `sdk49-v34-writer-guard-review-v1/qualification-attempt-03/RESULT.json` | `805e72a28399332a467647bf8fe24997e9308336cd6440532fb87828c065cc49` |
| `sdk49-v34-owner-lifetime-independent-review-v1/REVIEW_RECEIPT_V1.json` | `65e622e7f3bd70c61d00bd57a9245f36625c0b9f4e8feb2017dc444577b925aa` |
| `sdk49-v34-owner-lifetime-independent-review-v1/completed-evidence-review-v2/REVIEW_RECEIPT_V2.json` | `9854ce0cbaea900cbfa93d45a0fc7dcb69d4dab40df1a39ce9e9340bf23d5265` |
| `sdk49-v34-owner-lifetime-sdk-v1/sdk-finalization-01/RESULT.json` | `3ff6cbfce077154e1138373590b65f65487433be2bd30b7b83da3f850a205cdf` |
| `sdk49-v34-owner-lifetime-sdk-v1/sdk-readback-attempt-01/RESULT.json` | `7aaa9d12ec40e416fb7824be7cebbb7fa6da3e75e567cce9689bd1d12f20f77f` |
| `sdk49-v34-owner-lifetime-sdk-v1/install-01/RESULT.json` | `df88815e02cdf87191ddc62be0f2bebe5c49b65c2b5a794a9742ef9a7cae95a6` |
| `sdk49-v34-owner-lifetime-sdk-v1/ROOT_INSTALLED_READBACK_V1.json` | `18cfbac70bfd6599b2d1bf9c189bf28797e30a60255e30576f26b4133b0a2ca6` |

### V34 default-app journalled workflow qualified and automation installed

The one-file OS630 qualifier successor adds the explicit `owner-lifetime-v34`
receipt profile, keeping the existing V29/V31 profiles and original default.
It pins the V34 Kernel1147 source and 232 exported headers/238 artifacts, requires
the qualified V34/V33 model identities and member-lifetime repair, and permits
only its explicitly pinned qualifier override in the exact OS630 map. Twenty-three
metadata admission refusals pass, including unqualified receipts, missing model
pins, writer scope, header/source drift and an incorrect profile. These are
metadata controls, separately classified from native execution.

A fresh two-boot x86_64 one-CPU campaign executes the default static-musl Notes,
Mv and Stat as UID/GID 1000 against the exact V34 SDK-only distribution image.
English content creation/save/reopen, rename with stable inode, parent fsync and
restart readback pass. Both preserved native disk hashes agree. Native and
Linux-recovered content readbacks match, and fsck passes. Existing-file replacement
remains unadmitted; refused unlink returns ENOSYS and preserves namespace, inode
and bytes. The boundary is fsync followed by preserved QEMU stop/restart, not
clean guest shutdown or graphical/manual desktop acceptance.

Root independently reads all 1,148 frozen campaign artifacts, both actual guest
logs, complete candidate/SDK-baseline source maps and all nine tool identities,
and adds nine admission refusal checks. Source review confirms the original
profile default, exact single-file exception and unchanged native application
sources. Only the qualifier is installed into private OS630, with its original
archived and complete Kernel1147/OS630 maps read back. No successful guest is
repeated. Accepted Kernel919/OS623/SDK41 and the closed active-reclaim writer
gate remain unchanged.

Evidence under `build/prototypes/sdk49-v34-journalled-workflow-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `SOURCE_HANDOFF_V1.json` | `6ca35cb85c910a0c55fa8da287d9dd2867878ccf45e086fee9353d4a08ffc300` |
| `attempt-01/RESULT.json` | `351c18b875a4a9fefc0d929c0d0338d477a980bf34e735b8b0b38ea1276c3ee6` |
| `ROOT_REVIEW_V1.json` | `7bfa702b92e971ceef330e08b87628c6070f38ec37248f1e8f7ccdc156e74a7b` |
| `install-01/RESULT.json` | `8718daac030cabfc25ec78e52f97636b9e386fe2cd54fcd65f9cae855470ee45` |
| `ROOT_INSTALLED_READBACK_V1.json` | `1efc7fd4ebbbdd2d8216c787e1719d506cd3c22e194544ee5bc718198d289aa6` |

The approved V35 follow-up covers the five remaining direct physical read leaves
with one-read anchored scopes and success-only Owner shadow adoption. It preserves
terminal sector-shaped transfers and avoids the whole-opening-route headroom
reservation for a single read. Design and assignment are frozen under
`sdk49-v35-direct-read-design-v1/`. This was the V34 planning checkpoint;
the completed V35 private installation and its bounded evidence are recorded above.
Full M0-M12 remains incomplete. Physical M11 and manual M12 remain user-deferred.

## Reviewed V31 SDK native workflow automation installed

The private OS628 qualifier now accepts the reviewed V31 SDK campaign through
an explicit `startup-read-guard-v31` receipt profile. It pins the declared SDK,
distribution image and complete OS628 source map, permitting only the explicitly
pinned qualifier update. The existing named V29 profile remains available.
Wrong profiles, artifact/header drift, matrix drift, writer scope and unrelated
application/source changes are refused before guest execution.

A fresh two-boot x86_64 campaign runs the default static-musl Notes, Mv and Stat
as UID/GID 1000 on the V31 Virtio journalled root. Save, reopen, rename with stable
inode, parent fsync and restart readback pass. Refused unlink remains ENOSYS and
preserves the file. Native disk hashes after both boots agree; content readback,
offline recovery on a copy and fsck pass. Root independently reads all 1,145
frozen files and adds nine metadata admission refusal checks to the candidate's
twenty controls. Two root readback-script assertion mistakes are preserved; the
native campaign itself passed its first attempt.

Evidence beneath `build/prototypes/sdk49-v32-journalled-workflow-v1/`:

| Receipt | SHA-256 |
| --- | --- |
| `attempt-01/RESULT.json` | `6e246c1c8cedeaf22ecae66b2e4eda8bd705a9050588d963d8aed13590e0ed50` |
| `ROOT_REVIEW_V1.json` | `099d7a007b7636f6ba393284652e7236e71578053dc2b80ef997627ed012906d` |
| `install-01/RESULT.json` | `26d4482230b83fee5f56e575ae3388eb4824b623c148cd0cdddc2c2ee3ae2c5e` |

Only `tools/qualify_journalled_workflow.py` is installed into the private OS628
tree, with the original archived. Accepted Kernel919 / OS623 / SDK41 is
unchanged. This is fsync followed by preserved QEMU stop and restart, not clean
guest shutdown, graphical desktop acceptance or reclaim-writer admission.
Existing-file replacement, unlink and interrupted writes remain open. Full
M0-M12 is incomplete; physical M11 and manual M12 remain user-deferred.

## Mounted startup direct-read integration installed (V31)

The private Kernel now attaches `guarded_read_blocks` to the mounted Owner's
opening-route reads. The synchronous helper pairs begin, one original Session
read and finish without retaining authority. Transport failure keeps priority
over both route accounting failure and a later attachment fault; successful
reads still pass the existing attachment, identity, seal and completion checks.
Four combined media/counter/detachment cases verify original Session quarantine,
one attempted read and zero completions, no writes/flushes, blocked root
publication and an unchanged independent decoy Session.

Ordinary and ASan/UBSan suites each pass 158 startup-route checks, 169 direct
helper checks, 8,463 mounted checks and seven/twelve invariant cases. The V30
parent fails the added regression. Both offline fsck/recovery comparisons and
ten ELF-checked freestanding probes pass; maximum individual frame is 13,008
bytes, without a cumulative-stack or SMP claim. Root's independent public
mount tests pass 50 checks per mode and its hostile detach controls pass twelve.

The exact 1,137-file Kernel and installed 628-file OS combination passes the
standalone x86_64 Debug SDK export, QEMU65 diagnostics, exported helper compile
and OS image/rootfs/UAPI/libc builds. Independent readback reconstructs the
actual consumer compiler commands and dependency records, verifies all 237 SDK
artifacts and excludes Kernel-source compilation by the OS. The new SDK
manifest SHA-256 is
`34ee8fb98619d5f6212ae05daed2917569c4f8ecd03917987459fa34448032f7`.
After these gates, the exact seven-file delta is installed into the current
private 1,134-to-1,137-file Kernel tree. SDK49 still declares ABI48 and is not
promoted; accepted Kernel919 / OS623 / SDK41 remains unchanged.

Receipts under `build/prototypes/`:

| Receipt | SHA-256 |
| --- | --- |
| `sdk49-v31-startup-read-priority-v1/qualification-attempt-01/RESULT.json` | `c189d74b442146406d17472b27f738aae9d499f7e9f4e37bd6c80b33e53718cd` |
| `sdk49-v31-startup-read-priority-independent-v1/attempt-01/RESULT.json` | `0716c1c5317ed14e592265a2aaf85cef60f790e1db189150cbe4d5a26879979e` |
| `sdk49-v31-startup-read-priority-v1/sdk-attempt-01/RESULT.json` | `5409df1307e3f3d9d354ef4464dfea85a4619bae5faa03e0f36c3c3fc3bf76e9` |
| `sdk49-v31-startup-read-priority-independent-v1/sdk-readback-attempt-01/RESULT.json` | `c4bd217e5f84ea15f9419cd7ab393f46674d02921794682d1c1b289b9ea96931` |
| `sdk49-v31-startup-read-priority-v1/install-01/RESULT.json` | `25edaa79e5016f56352a59cbbd7b354df4ebdf267e002dce14fdca74c619489c` |

This closes the opening-route direct-read attachment slice. Raw reads in nested
capture/history/recovery paths still need per-dispatch integration, complete
retained-history enumeration and final Owner/root lifetime reconciliation before
active-reclaim write admission. The diagnostic guest uses model media; native
startup reclaim, missing-home writing, interrupted-write campaigns, physical
durability and SMP remain open. M0-M12 is incomplete; physical M11 and manual
M12 acceptance remain user-deferred.

## Native journalled default-app workflow and OS installation

The exact SDK49 ABI48 OS successor now runs default Notes, Mv and Stat compiled
with pinned musl 1.2.5 on an actual x86_64 QEMU Virtio journalled ext4 root.
The guest drops to UID/GID 1000, creates and saves basic English text through
Notes, reopens it, renames it with a stable inode, runs Stat and fsyncs the parent
directory. A second boot reads the same bytes and namespace. Refused unlink
returns ENOSYS and preserves the file. The two post-boot disk hashes agree;
independent host readback, journal recovery on a copy and subsequent read-only
fsck pass. This is a static CLI `/init` acceptance fixture, not a graphical
desktop, PID 1 service session or clean guest shutdown.

Two application fixes request the POSIX `renameat` declarations before libc
headers in Notes and match Stat's `unsigned long` mode argument with `%lx`.
The candidate also supplies a reusable SDK-only qualifier and native guest
probe. Existing Notes fault controls pass all 41 cases in ordinary and
ASan/UBSan builds. Root reads back all 1,145 frozen files, reviews the exact
four-file delta and installs the 626-to-628-file private OS successor.
Accepted Kernel919 / OS623 / SDK41 remains unchanged.

Evidence under `build/prototypes/sdk49-v30-journalled-workflow-v1/` includes
`attempt-06/RESULT.json` (SHA-256
`901937ed2671c0445e7d06a54c4cc507224630213c04eaffdd62c1a0942df716`),
`ROOT_REVIEW_V1.json` (SHA-256
`7d2ce124c0d5aa1abda3278a05736758b1bfeb7c1125746a53b02c42c70c3d6a`)
and `install-01/RESULT.json` (SHA-256
`48ba7dd485555d56314cf3fe4c631fed476bf6aa0621a2537844b5e78ebd2ac5`).
Failed attempts remain preserved: missing `renameat` declaration, unsupported
native `access`, the correct Notes same-owner refusal for bootstrap UID 0 and an
incorrect xmake output-directory API. The successful probe uses `stat` and
ordinary credentials; it does not qualify `access` or relax save authorization.

Existing-file replacement, unlink/reclaim, directory creation, interrupted
write campaigns and the shutdown/VFS-drain path remain open. File/directory
fsync followed by a preserved QEMU stop/restart does not prove clean shutdown
or arbitrary power-loss durability. This x86_64 Debug result does not narrow the
ten Kernel/four supplied musl architecture matrices or complete M0-M12. Physical
M11 and manual M12 acceptance remain user-deferred.

## Kernel-executed read guard and exact SDK consumer (V29 candidate)

The isolated read-guard successor snapshots the actual private Kernel tree,
including its additional startup-route/platform changes, and adds the synchronous
direct-read helper and a kernel diagnostic point. Its 1,137-file source passes
ordinary and ASan/UBSan executions of the five-scenario diagnostic model and ten
freestanding architecture probes with checked ELF identity. The standalone
x86_64 Debug Kernel then exports 231 headers and 237 explicitly declared SDK
artifacts, still ABI48. QEMU reaches the new diagnostic through `kernel_main`,
passes all 65 debug points and the existing UDP/TCP diagnostic. This executes
actual Session/cache/route code against a memory-model device; it does not
exercise native mounted media or the active-reclaim writer.

The exact 626-file OS snapshot builds its distribution, both rootfs formats,
UAPI and libc fixtures against that exported SDK. A freestanding public helper
probe also compiles using exported headers. Receipts beneath
`build/prototypes/sdk49-v29-read-guard-kernel-v1/` are
`models-attempt-01/RESULT.json` (SHA-256
`49c6dc64aa26a405006f0b12a3f3d1143ef7f4ca1a5a30f87e435ee10dc30151`)
and `sdk-current-attempt-01/RESULT.json` (SHA-256
`ac6aeca2cd8f2a880f75fad00ee5b7fd5deeea92b95c1685a52921c31ded2043`).
The SDK manifest SHA-256 is
`1661df9388bc16eabcdd00354d4494aaeae1f007bb541bac882e4264be6ee13e`.
Independent compiler-dependency readback passes: 86 actual OS object/dependency
records cover 43 compiled OS sources and 186 unique dependency files. Every
source dependency belongs to the exact OS snapshot or manifest SDK. The public
helper probe has 43 dependencies confined to its source and the SDK. Receipt
`build/prototypes/sdk49-v29-read-guard-independent-v1/readback-attempt-02/RESULT.json`
has SHA-256 `47c5a8c96f666f7fd998beaeff70e773dee0c2aab5cf64ed674f06d9a31ba170`.
A successor that attaches this helper to the mounted Owner's opening reads
was independently rejected. Its hosted regressions and ten architecture probes pass, but an
independent hostile-callback check finds a remaining error-priority defect:
simultaneous media failure and route detachment return the later attachment
fault. The original Session is quarantined and no root is published, but the
caller loses the earlier media error. The rejected candidate and passing narrow
tests remain preserved; the installed V31 successor above adds the case and fixes the order.
Receipt `build/prototypes/sdk49-v30-startup-direct-guard-independent-v1/attempt-01/RESULT.json`
has SHA-256 `064a2d58c76b60aaff592982464d84a04f4eca838528de45dedf58fa0e3831b6`.
The V29 candidate is
not installed or promoted; accepted Kernel919 / OS623 / SDK41 remains unchanged.

Independent lifetime review confirms that the current inode Lease deletes copy
construction/assignment, invalidates its move source and refuses replay after
release. Explicit cloning increments the actual hold count. Ordinary and
ASan/UBSan tests each pass 28 lifetime checks, four repeated diagnostic-model
rounds and 169 direct-helper checks. The review receipt is
`build/prototypes/sdk49-v29-read-guard-independent-v1/REVIEW.json`, SHA-256
`b97933b65745e651da4c1d4eec813cab173b1bdd7f1debcd7602525a54804486`.
The initial output-path and unavailable LSan-under-ptrace attempts remain
preserved; LSan is explicitly excluded from the passing sanitizer execution.

Additional private OS boot work already selects `Ext4MountedMetadata` on
journalled media. Its earlier native campaign reaches musl `/init` but still refuses
unlink because the boot mount supplies no admitted reclaim workspace. Earlier
V28 statements about a legacy-only boot module describe that qualification's
snapshot. The separate default-app acceptance above covers initial save and
rename/restart; replacement and reclamation still need native acceptance.
Full M0-M12 remains incomplete. M11 physical
and M12 manual acceptance remain user-deferred.

## Private mounted root publication guard (V28)

The SDK49 private candidate remains unfrozen, unpromoted and ABI48. Its mounted
metadata provider previously returned a root Node after the original block
Session had already been externally aborted. The new regression reproduces that
failure against the V27 private header. `Ext4MountedMetadata::root()` now checks
the original Session identity while holding its publication gate, fails the
mount and declines to publish the root after a completed abort. Owner quarantine
runs after releasing the mount lock. The changed mounted header SHA-256 is
`83c06bb588a126e8e86ff7fd7783b0f3598500ec2d96285e8fc254fc9cf0304b`.

The exact private 1,132-file Kernel source passed the full mounted metadata
hosted model (8,463 checks), seven private invariants, twelve persistent
invariants, offline `e2fsck`/journal-recovery comparison and ten freestanding
architecture compiles. Ordinary and ASan/UBSan executions passed. A stale
compile probe still required SDK ABI41; its private assertion was updated to
the current ABI48 before the successful full run. An isolated x86_64 Debug
Kernel SDK export, QEMU diagnostic and SDK-only OS image/UAPI/libc consumer
build then passed independent byte and dependency readback. The OS compiler
records contain 86 dependency entries, 43 compiled OS sources and 129 checked
dependencies; no Kernel source was compiled by the OS. Receipts are
`build/prototypes/sdk49-v28-mounted-root-session-guard-v1/INSTALL_V28.json`
(SHA-256 `e5dab09df7c809cdf13945a5878f0c11502c8a376752fc32334bf4332ee576f9`)
and `sdk-consumer-01/POST_BUILD_REVIEW.json` beneath that directory
(SHA-256 `9e43ea668a4937ab35cffdf6122388b40be818c1ce4aee0868a7856d5bb51c2c`).

At the V28 qualification snapshot, the distribution boot module still mounted its legacy non-journalled
`Ext4FileSystem`; this guard was tested in the private side-mount provider, not
in a native mounted-root guest. It does not connect active-reclaim routing,
qualify SMP, enable the pending writer, complete M4 or promote SDK49. M0-M12
remain incomplete, with M11 physical and M12 manual acceptance deferred.

## Private V3 metadata Session guard and M0 ext4 crosswalk

The accepted snapshot remains Kernel919 / OS623 / SDK41. SDK49 remains an
unfrozen ABI48 successor. V26's private storage tree now includes the reviewed
V3 metadata Session guard: after the original block Session is quarantined,
cached hits and retained Pins stop exposing canonical data; a route refusal that
leaves the Session owned does not fail the cache. The exact V26-to-V3 patch
changes `include/ok/fs/metadata_buffers.hpp` from SHA-256
`29b4be725f6b6238628fd689826980db5c33031054d4c5b1b9b059cab153865f`
to `0ba487b762e26319fada7202e7eb9fc5dc65214430194ace392cbb0e8010266b`.
A public-interface regression and the private `test_metadata_buffers.py` runner
are installed alongside it. Ordinary and ASan/UBSan hosted suites each passed
320 ownership checks and 33 Session-invalidation checks; the existing guard
suite passed 203 checks, and a 100-trial hosted in-flight abort check passed.
The new regression fails against the exact V26 header at the first externally
aborted Session report, confirming that it detects the predecessor defect;
`build/prototypes/sdk49-v27-owner-session-guard-install-v1/V26_REGRESSION_DETECTED.json`
records that controlled run.
All ten architecture profiles compiled both freestanding metadata probes with
verified ELF identity. The private installation receipt is
`build/prototypes/sdk49-v27-owner-session-guard-install-v1/RESULT.json`, SHA-256
`4d04136419d03d13d7d397059e84b2a71fe137c8b534a624bfd62a16ff882570`.
It verifies that the prior isolated V3 x86_64 Debug SDK, QEMU diagnostic and
SDK-only OS consumer readback used identical Kernel and OS product source bytes;
only test and runner files differ. The prior isolated readback is
`build/prototypes/sdk49-cache-route-guard-v3-sdk-v1/attempt-02/POST_BUILD_REVIEW.json`,
SHA-256 `ddd73e8f700376fdee8acb027c1abea60fcffdab3bfb84a5cd8685670c3181c1`.
This does not qualify native SMP, attach the storage Owner, enable the writer,
promote an SDK or complete M0-M12.

The source-pinned M0 ext4 superblock-bit crosswalk compares 45 literal bits in
Linux 6.13.4 and e2fsprogs 1.47.0/1.47.2 with the storage matrix: 30 are
named, four have prose aliases, three have only related topics, and eight lack
individual disposition. Its receipt is
`build/prototypes/sdk49-cache-route-v26-independent-v1/EXT4_FEATURE_MATRIX_CROSSWALK.json`,
SHA-256 `929ea8c470895ca8bd3153f1807de05c2467a503f5ec342f79423f776c53731b`.
Semantic, read/write/replay, combination and JBD2 review remain open. Four
reviewed normative indexes are still absent, so M0 is not complete. The user
has no reference hardware or manual desktop test environment yet; retain the
M11 physical-machine and M12 manual-workflow gates as incomplete.

The storage plan now individually disposes of the eleven formerly missing or
indirectly mentioned literal bits, and the documentation-only `EXCLUDE_INODE`
bit. A fresh archive/member/row readback covers all 45 literal bits (41 named,
four prose aliases) and the extra documented bit. This supplies planned rejection
and future qualification rules; no mount capability or admitted index changes.
Receipt `build/prototypes/m0-ext4-bit-dispositions-v1/RESULT.json` has SHA-256
`9ed16706ca9fd284ca1d3a8b45615ca7f56e49d081a2e43082dfca3b387d0147`.
The earlier crosswalk retains its original plan snapshot and findings.

## Replacement, checked inode reuse and cleanup (SDK49 successor, unfrozen)

The accepted snapshot remains **Kernel919 / OS623 / SDK41**. SDK49 is an
unfrozen successor of the frozen SDK48 tree. It still declares ABI48. An
earlier isolated Debug experimental SDK export and exact OS consumer builds pass
on x86_64, aarch64, rv64 and loongarch64;
this is not a complete twenty-profile SDK qualification or a promotion.
The historical composed read-budget SDK gate below covers x86_64 Debug only.
Historical private checkpoint **V25** retains reviewed Linux rename dispatch,
bounded whole-volume orphan ownership, mounted C1 startup and the qualified
same-Owner namespace checkpoint followed by physical C1 recovery, plus the
read-only active-reclaim retained-history seal, prospective terminal projection
and the original-Session single-pointer substitution repair. V23 added the
reviewed read-only composed-history and dry-planning route. V24 adds the complete
additional dry-route READ reservation and checked accounting. V25 adds the
reviewed pre-dispatch BlockSessions counter-capacity check; mounted active
reclaim writing and root admission remain disabled.
The actual Debug UID 1000
musl CLI Notes fixture on all four supplied userland profiles passes twelve replacements, retained old-descriptor
and seeded-link checks, clean freeze, independent ext4 checks and same-disk
read-only reboot. This is a static `/init` fixture, not isolated graphical apps
or a completed workstation. M0-M12 remains incomplete.

### Prospective active-reclaim history and original-Session repair (V22)

The independently rejected prospective V1 revealed three rejection-path defects:
mutable result-seal Session, nested history origin and inherited V21 binding
original-Session pointers could redirect quarantine to a valid decoy Session.
V21's historical receipts remain preserved; their original-Session claim does
not cover these later counterexamples. The accepted SDK41 snapshot is unaffected.

Frozen prospective V2 adds a private noncopyable one-shot SessionAnchor at the
binding, original Capture, result history and nested chain Capture boundaries.
Success requires three retained pointers to agree; rejection uses the matching
pair so one substituted pointer cannot redirect original quarantine. This
bounded borrowing contract does not claim coherent multi-anchor corruption or
SMP containment. The source adds typed whole-block terminal projection, distinct
zero/nonzero remaining-chain proofs and 25 original/decoy substitution controls.
It retains admitted reports and uses independent exact Session read accounting.

The exact 1,124-file candidate compiles 20 freestanding probes across all ten
profiles, including typed history/chain instantiations and mounted startup.
The maximum individual frame is 13,008 bytes below 16,384; cumulative stack and
native execution are unproven. Independent source and profile audits pass;
the three repaired original-Session counterexamples and seven-suite hosted
read-only aggregate now pass. The exact standalone SDK and OS-consumer gate also
passes, with independent artifact and source readback. Hosted
attempts01/02/03 remain failed with successful partial executions retained.
Attempt03 completed twelve fresh executions before an auxiliary renamed-main
warning failed its build. Attempt04 completed only the last two targets. The
audited aggregate binds 14 fresh executions with zero reused executions; its
scope receipt records that attempt03 repeated eight earlier passing tests
instead of reusing them. Plain and ASan/UBSan markers agree, including the 25
original-Session quarantine controls; startup and C1 output disks agree by
SHA-256. The three independently repeated V1 substitution probes now verify
original quarantined, decoy owned and zero writes/flushes in both modes. These
are hosted read-only results, not guest, hardware or writable recovery gates.
V22 is installed in the private implementation tree. Independent full-map
readback matches all 1,121 V21 preimage files and 1,124 V22 installed files,
including exactly six modifications and three additions. Rename, lifecycle,
V20 and V21 test migrations and inherited checkpoint fields are preserved.
Four isolated staging/interruption controls pass; these do not establish
arbitrary process-death or power-loss recovery.

The exact 1,124-file standalone producer passes x86_64 Debug xmake configuration,
SDK export and QEMU diagnostics (`OK_TEST_PASS`, 64 debug test points). Its
233 explicitly declared ABI48 SDK artifacts supply the exact 627-file OS
consumer; distro, rootfs, UAPI and libc builds pass. Independent readback checks
338 build artifacts, 43 compiled OS sources and 86 dependency records. Producer
references in the consumer are confined to the exported SDK. This diagnostic
guest is not native execution of the new reclaim route; Release, SMP, physical
hardware and complete architecture/mode SDK qualification remain open. SDK41
is unchanged and no ABI49 promotion is made.

| V22 evidence under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V22.json` | `24adf9b5ef76298955b6b26f10aa0898a36302cf753a12fcb14813d7dab90af4` |
| `sdk49-reclaim-prospective-v22-integration-v1/install-01/result.json` | `b005039186ff401bdd93040bc0a2d051ceaefe7ea97b1eec72039bc91c2c6460` |
| `sdk49-reclaim-prospective-v22-integration-v1/independent-readback-01/result.json` | `d847e9853951e77e6e2c07e2764ff7c8f30138542e77028f654e9a14b8ef6d04` |
| `sdk49-reclaim-prospective-v22-integration-v1/sdk-readback-01/result.json` | `3eac77ade28ef10a0f8ddfc1d35caf48a07eda0ec69b13f9d8beb75b4109d2db` |
| `sdk49-reclaim-prospective-sdk-v1/attempt-01/build-attempt-01/result.json` | `8a76c823276777d1f6143feee24798a3c3231f06a7ef5b36a1fafbfe00bebad1` |

Candidate handoff SHA-256:
`ea7d1c62e291c784912321b1f875a3b50c02421654c3a19b59152b32e25de228`.
Ten-profile result SHA-256:
`2e6f628909d7d738a96b1b6fee19a9aefa04914df4fd227634cc8c8210909aa2`.
Hosted aggregate SHA-256:
`57f323b15d6d161596d9bc9a7d5ae3a4f1668be89837c1e04ec35cbdc7aeaace`.
Independent repair-probe result SHA-256:
`f9b2ddba4fc97258e4c169b63558a3a34ca89c695981b6eef9d8701fc4e06811`.
Evidence is under `build/prototypes/sdk49-reclaim-prospective-history-v1/`.

The next proposed read-only route retains evolving shared-home/WAL expectations
across at most seven later C1 members. Its known ninth journal-block observation
has a distinct pre-mutation reservation; budget V2 adds `8*n+3` READ attempts to
reviewed V1, with a conservative maximum of 22,747,871. This is a design bound,
not observed performance or implemented reservations. Independent review accepts
the proposed V2 read-only source contract and all eight budget rows (result
`79ed007fb38503a1ccda5835805e52bf068de5c1b547a9516854d5d1e0538eb8`).
The next candidate in `sdk49-reclaim-composed-history-v1/` is now frozen. Its
1,126-file map adds a permanent eight-row composed ledger, the original offset-8
observation, private typed dry planning and complete ordinary metadata/directory
preflight. Whole before/after lineage includes shared homes, complete WAL images
and stale tails. Independent named-stage counters equal the original Session
delta and reject exhausted allowances before dispatch. Original admitted reports,
public prospective `plan_head` refusal and mounted writer/root gates are retained.

Final initial attempt06 passes composed, mounted and prospective plain programs
with finite 8 MiB child stacks. All legal initial masks produce 22 independent
complete-image equalities, including zero/one/seven remaining members and the
explicit `[4,5,4,4,4,4,4,5]` WAL-width sequence. Twenty refusal cases and nine
original/decoy substitution controls retain zero dry-route WRITE/FLUSH. The
one-member dry route uses 4,396 READs; seven members use 23,423, including exactly
one original extension READ. These are observed hosted dry-route counts, not the
complete future writer reservation. Attempts01-04 remain failed; attempt05 is a
passing predecessor snapshot and attempt06 is the exact final source evidence.

Twenty freestanding probes across all ten architectures also pass, with 6,156
function records and maximum individual frame 13,008 bytes. This is not a
cumulative-stack or native-execution proof. The exact 1,126-file standalone
producer and historical 627-file SDK-only OS consumer are archived without
overlays. The complete root hosted campaign passes all 16 fresh plain and
ASan/UBSan executions with matching markers and startup/C1 output disks.
Independent source and profile audits find no blocking source issue or artifact
drift. The independent full composed sanitizer run reaches all 22 complete
golden comparisons before its 900-second external timeout; a focused successor
passes all 20 refusals and nine original-Session controls. The timeout and an
environmental LeakSanitizer failure remain preserved. Root accepts this scoped
independent evidence together with the complete root campaign for the private
read-only SDK build, without calling it an independent full-suite pass.
The exact SDK execution passes all five commands: standalone x86_64 Debug
configuration/export, existing QEMU diagnostics and exact SDK-only OS
configuration/build. Full readback verifies 1,126 producer and 627 consumer
source files, 234 explicitly named SDK artifacts, four consumer images, 43
compiled OS sources and 86 dependency records. An independent audit agrees.
The existing diagnostic guest does not execute the new reclaim route. Mounted
active writer and root admission stay disabled.

Independent review of the initial V23 installer preparation found a rollback
defect: a foreign checkpoint appearing at publication would leave the candidate
source map installed without a valid successor checkpoint, and a foreign
directory could interrupt exception handling. That initial preparation did not
execute controls or mutate private main and remains preserved. Corrected
preparation-02 requires a matching stable regular
checkpoint before suppressing rollback. Nine isolated interruption controls
pass, including foreign file and directory publication races: both preserve
the foreign target and restore all ten source paths. Independent control
readback rehashes 30,776 frozen artifacts and all nine complete case maps.
The exact ten-path V23 private installation now passes. Independent post-install
readback matches all 1,126 installed source files, the preserved generated
exclusions, the inherited checkpoint fields and the exact two-addition/eight-
modification delta. The accepted Kernel919/OS623/SDK41 snapshot is unchanged;
this is not a new native reclaim guest, writable recovery, full ext4, SMP,
physical M11, manual M12 or complete workstation qualification.

| Composed candidate evidence under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-reclaim-composed-history-v1/candidate-v1/SOURCE_HANDOFF_V1.json` | `aa1a2ec27e4e138df067f2ee47f74cd98b58ea337d26cfd33f1b3518a21e3a51` |
| `sdk49-reclaim-composed-history-v1/initial-hosted-attempt-06/result.json` | `5c04e8a2ca2649449c088b131130bbc6fcc9af758cdb80c9598e1a4cdae56110` |
| `sdk49-reclaim-composed-history-v1/profiles-attempt-01/result.json` | `69f79eba3ec46bf30998bec80764c23d92f96df8fe23782d2077cfe6fbe3b171` |
| `sdk49-reclaim-composed-history-v1/hosted-attempt-01/result.json` | `3d762e0976606f7aabc0d3cf46161afa92e5c1c3b4158c855618aeb253f862db` |
| `sdk49-reclaim-composed-independent-v1/source-review-01/RUNTIME_AUDIT_V1.json` | `bf4db80c343bb756235595ad3bb290307f2595f68ca68577818f4ae4c062e99f` |
| `sdk49-reclaim-composed-sdk-v1/GATE_CONTRACT_V1.json` | `db5986075ba7f520ac726d9b8a9fa0637e1971a90b1f6abad278d62c18f20836` |
| `sdk49-reclaim-composed-sdk-v1/attempt-01/ARCHIVE_COMPLETE.json` | `563e18c1e37047d1cbd285f203593365e5e706f6a15f60377656124d854c39d6` |
| `sdk49-reclaim-composed-sdk-v1/attempt-01/build-attempt-01/result.json` | `9ad436719214500e39e6ec4b4b46f6e6cecde6ff47a2fbeedcc7de5435c3e806` |
| `sdk49-reclaim-composed-sdk-v1/sdk-readback-01/result.json` | `a791bd765abf2f224e70d27074c0888aca7aafb52e98b4b5c4865950d6adb063` |
| `sdk49-reclaim-composed-v23-integration-v1/preparation-02/FREEZE.json` | `96e3a7b65d4e0a4b32a58a7c8de7c6ad5d6fd218a6c65844434606cb2c194aef` |
| `sdk49-reclaim-composed-v23-integration-v1/interruption-controls-01/FREEZE.json` | `340857fbd962a4111ccfe93de94bce3cf279efdd18d07283af0b1d36a03975a7` |
| `sdk49-reclaim-composed-v23-control-independent-v1/review-02/result.json` | `938746453a3e70c78b8025316f0a1f337e62dc296c40ac3f890e843c370fb11e` |
| `sdk49-reclaim-composed-v23-integration-v1/install-01/result.json` | `3c32403232f7e6828c52e82a9c091d92b01e09b6fbc602e94d6b67c2b131ae45` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V23.json` | `222a5128ce6ce4794eb014d6b24e40e4ca5ad937de6b3dbf625ddb2f77d4aa6e` |
| `sdk49-reclaim-composed-v23-control-independent-v1/installed-readback-01/result.json` | `fd1cf46dfc9036e1e04f542cc8d80cc6c5865c13aedd1c33275a26d9785b8d5d` |

### Complete composed read-only reservation successor

The separate `sdk49-reclaim-composed-budget-v1` candidate adds an actual
noncopyable one-shot read budget to the composed route. Before its first
additional READ it reserves the complete named-stage allowance against attempt
and completion counters and the complete projected sequence advance. Retained
checks reconstruct the budget from the original route facts, compare both seals
and require the stage sum to equal the exact original Session delta. The maximum
is 10,214,478 additional READs for seven remaining members with the optional
extension. This is a conservative dry-route allowance, not observed performance
or the proposed complete physical writer budget.

The exact 1,127-file candidate changes three paths from installed V23. Hosted
plain and ASan/UBSan markers agree: 22 whole-image goldens, 26 refusals, nine
original-Session controls, and six counter/sequence boundary pairs. Same-Owner
mounted plain and sanitized tests each retain three validated dry routes and
three blocked mounts, with zero WRITE/FLUSH. Attempt01 remains failed because
LeakSanitizer cannot inspect exit state in the ptrace environment. Attempt02
disables only leak checking, reuses two hash-verified xmake builds and one
previously passing plain execution, and executes the sanitizer and two mounted
cases freshly. It does not claim four fresh executions or qualified leak checks.

Independent source and profile readback passes for all three changed paths and
all ten architectures: 20 probes, 6,206 function records, maximum individual
frame 13,008 bytes. An informational ARM32 compiler ABI note is retained; the
independent audit's first incorrect empty-log assumption remains a failed
attempt. Source/profile audit is not independent C++ execution.

Focused independent C++ plain and ASan/UBSan executions now pass with finite
8 MiB stacks and `detect_leaks=0`. They cover 16 counter/sequence combinations,
successful and refused one-shot use, four retained-state mutations before READ
and two callback mutations. Both modes quarantine the original Session in all
six mutation controls, with zero further denied READs and zero WRITE/FLUSH.
This independent campaign does not rerun full goldens, the ordinary endpoint or
mounted runtime. It rehashes 1,197 frozen artifacts without mismatch.

The exact 1,127-file Kernel and historical 627-file OS snapshot now pass all five
standalone x86_64 Debug SDK/consumer commands. The producer exports 235 explicitly
named ABI48 SDK artifacts, including the new budget header. Existing QEMU
diagnostics pass 64 test points; this does not execute the new reclaim route.
Independent readback verifies all source maps, SDK artifacts, four consumer
images, 43 compiled OS sources and 86 dependency records. Kernel references in
the consumer remain confined to its explicit SDK. Historical source/profile
receipts remain immutable; root gate wrappers accurately preserve the focused
runtime scope and three-fresh/one-reused hosted composition.

V24 is installed after frozen preparation and nine isolated interruption
controls pass independent readback. The stable regular-file checkpoint
publication rule from repaired V23 is retained. Foreign checkpoint files and
directories preserve their contents while all three source changes roll back;
an interruption after valid checkpoint publication retains the complete new
map. The original nine controls did not execute symbolic-link or unreadable-
target cases. Two supplementary isolated controls now pass for a foreign
symbolic link and an injected `PermissionError` at `lstat`; both preserve the
foreign target and roll back all three paths. These controls do not establish
behavior under actual permission changes. Independent installed readback verifies 1,126 preimage files,
1,127 installed files, the exact two-modification/one-addition delta and 248
unchanged inherited checkpoint fields. Root's duplicate freeze publication
attempt was refused without overwriting the already frozen 30,803 control
artifacts; that disposition is retained separately. These injected Python
interruptions do not establish arbitrary process-death or power-loss recovery.
Accepted Kernel919/OS623/SDK41 remains unchanged. V24 remains private ABI48;
writer authority, mounted physical admission, new guest reclaim execution,
cumulative-stack proof, SMP and complete M0-M12 remain open.

| Read-budget successor evidence under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-reclaim-composed-budget-v1/candidate/SOURCE_HANDOFF_V1.json` | `c4e9fd4e0d236d1e3200b4c182be4f8ca4768fcec25875eb98831dac2b736547` |
| `sdk49-reclaim-composed-budget-v1/RESULT_V1.json` | `24fd795792f28bee3d1707cabdc9c60ac35113360f362edc20e94a579e5a3b59` |
| `sdk49-reclaim-composed-budget-v1/FREEZE_V1.json` | `3b07233192f5397568940560b1ddc696808d62cd48bf10ebe83d92014241dc82` |
| `sdk49-reclaim-composed-budget-independent-v1/review-02/SOURCE_REVIEW_V1.json` | `ea87e72ad88e9fca71e1227a445d11166b3f5761f8caf2abdc017503c295d453` |
| `sdk49-reclaim-composed-budget-independent-v1/review-02/PROFILE_AUDIT_V1.json` | `25c3454c2ea8a03e45d009dba315affbaaab5955f0ab002b1927d2e73261c62e` |
| `sdk49-reclaim-composed-budget-independent-v1/runtime-attempt-01/result.json` | `a22c5831e4ba92ddb8adea2e1410bcd851e974ed2d5bba396e42cc41de086be0` |
| `sdk49-reclaim-composed-budget-sdk-v1/attempt-01/build-attempt-01/result.json` | `cf5dd1bbffe368107a03b15f32d69a5735c0a31cce85cfd306d2af2e1d6f0184` |
| `sdk49-reclaim-composed-budget-sdk-independent-v1/sdk-review-02/result.json` | `75518d17a75db5ada1290241d8d941931b30fc870fc2bc74e4624783ab9a200b` |
| `sdk49-reclaim-composed-budget-v24-integration-v1/interruption-controls-01/FREEZE.json` | `aac5d66e710e46ca48b8d9437dd299c5d7c4e39550ff372c35e7e1dfabe95feb` |
| `sdk49-reclaim-composed-budget-v24-integration-v1/install-01/result.json` | `557af79d4347e3127cfa8794d5cc0ad75c60e33fe50c79fd48a551d5aff4a282` |
| `sdk49-reclaim-composed-budget-sdk-independent-v1/v24-install-review-01/result.json` | `6884386a0e72d29cdacf57b28337edd177d72ffbd8c4c56f53164e2c9bc65206` |
| `sdk49-reclaim-composed-budget-sdk-independent-v1/v24-publication-edges-01/result.json` | `ca717e4555254d0158b6d8fb8ea40f404e065e39aa5c45f760f6a0392a8e9812` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V24.json` | `1ca93d51a76a8d922822010bb518450ebe12883e7358769430c361ab207ab82c` |

### Pre-dispatch counter protection (installed V25) and isolated cache guards

The `sdk49-session-counter-capacity-v1` candidate adds a locked, statically
selected capacity check at the actual BlockSessions dispatch boundary. Either
selected attempt or completion counter at `usize` maximum refuses before
geometry queries, transport callbacks, request pinning or pending-write changes.
Existing stale/closed/quarantined, reentrant, access and bounds errors keep their
precedence. Last-fit requests may reach maximum; failing callbacks retain their
real attempt without a fabricated completion. Only `sessions.hpp` changes in
the exact 1,127-file V24 map. Both hosted modes pass 249 checks across 33 variants,
both unchanged regressions pass 127 checks, and all ten ELF-checked freestanding
profiles compile. Independent plain and ASan/UBSan tests each pass 181 checks
across 25 variants with finite 8 MiB stacks. Exact standalone x86_64 Debug SDK
export, existing QEMU diagnostics and the historical 627-file OS consumer pass;
235 explicit ABI48 artifacts, 43 compiled OS sources, 86 compiler records and
129 distinct actual dependencies are read back independently. The QEMU guest
does not exercise the counter boundary cases.

V25 installs exactly this one-header change in the private 1,127-file tree.
Frozen preparation, six isolated publication/interruption controls, independent
gate review and installed full-map readback pass. The immutable V24 preimage
and all earlier failed SDK/readback attempts remain preserved. One generated
Python bytecode file is retained outside the checkpoint map. All 289 inherited
V24 fields are verified, with five scoped changes and explicit additions. These
injected interruptions do not establish arbitrary process-death or power-loss
recovery. Accepted Kernel919/OS623/SDK41 is unchanged; no ABI49 promotion is made.

The separate `sdk49-metadata-read-guard-v1` v2 candidate adds a borrowed static
guard to canonical cache misses. Cache hits call neither hook. A refused begin
leaves slot eviction, generation/exhaustion bookkeeping, pins and Session counts
unchanged. The hook receives the actual transfer length; a 1 KiB guard refuses
2 KiB and 4 KiB cache transfers before transport. A failed finish uses the
existing failed-entry and original-Session quarantine path, preserving an
earlier transport error. Its exact 1,129-file candidate has one changed header
and two added test/probe files. Six fresh plain/sanitized executions, 203 focused
checks per mode, the original ownership/retirement regressions and 20 probes
across all ten architectures pass. Two supplementary transfer-size executions
pass 28 checks per mode. The earlier two-argument hook candidate and its passing
attempt remain preserved; they do not establish the v2 transfer-size contract.
Independent plain and ASan/UBSan tests each pass 144 checks across eight variants,
including hook timing, actual transfer sizes, exhausted slots and failed geometry
accounting; all 20 profile objects are read back. This overload is not yet attached to the mounted
Owner, direct capture reads or root-construction lifetime.

The repaired complete-route budget design passes independent lineage and
arithmetic review: eight rows, 48 counter boundaries and eight sequence
boundaries, with a conservative maximum of 22,754,896 opening READs, 111 WRITEs,
60 successful FLUSHes and sequence advance 23. The original receipt accidentally
stored a sequence integer instead of the three-path source map; that failed
receipt remains frozen, and repaired `reviewable-02` keeps those variables
distinct and asserts the source map before publication. This is a design gate.
The separate route-budget primitive now implements one-shot maximum reservation,
narrowing, original-Session accounting and synchronous read begin/finish hooks.
Its private writer methods remain inaccessible and unconnected to the Owner.
V1's mechanism tests and independent review pass, but root review found that its
transfer-size/alignment and zero-sequence admission were weaker than the planned
complete route. Frozen V2 requires 512-byte geometry, even sectors, exactly 1 KiB
transfers and a nonzero actual active sequence. Its plain and ASan/UBSan tests
each pass 2,276 checks, including 749 callbacks and 25 refusals. Independent V2
tests each pass 60 checks, and the two 2,276-check regressions also pass; ten fresh
ELF profile probes are read back. V1 evidence remains historical and does not
cover these repaired profile requirements.

The exact 1,131-file V25/cache-v2/route-v2 combination passes ten hosted
executions. Its actual Cache/BlockSessions integration tests each pass 18
variants, 297 checks and 13 callbacks, with hits consuming zero READs, refused
misses preserving cache generations, and media/geometry/pending-write failure
tuples retained. Twenty fresh ELF probes cover all ten architectures. A separate
independent callback probe passes four variants and 40 checks in each mode.
Its x86_64 Debug ABI48 SDK exports 230 headers and 236 explicit artifacts; seven
standalone SDK/QEMU/OS/API-probe commands pass. The historical 627-file OS still
compiles 43 sources with 86 records and 129 actual dependencies; the new public
SDK-only probe compiles one source with 43 dependencies and uses all three
exported interfaces. Root reconstructs both dependency closures. Independent
Independent SDK readback and V26 publication review subsequently passed. The
first installer failed the identical-content foreign-checkpoint inode control;
its failed evidence remains preserved. The repaired installer verifies staged
hardlink identity, passes eleven isolated interruption/checkpoint controls and
installs the exact 1,131-file V26 tree. Receipts are
`sdk49-cache-route-v26-integration-v1/install-02/RESULT.json` (SHA-256
`16840c4e614fec3b0fc67ea9e2d41939dbd1ef580c8a3332529995be5b1a32b8`)
and `sdk49-cache-route-v26-independent-v1/POST_INSTALL_REVIEW.json` (SHA-256
`445a8c1a7e9b8706b4e849b0a76dfbbb5e86c4a53f1b0ffac2d19b84253cbb8e`).
Neither the diagnostics nor the API compile is native reclaim execution.

The next isolated direct-read helper synchronously pairs begin, one actual
Session READ and finish without returning a lease or retaining a pointer. Begin
refusal performs no READ/finish/abort; later failures quarantine the original
Session and preserve an earlier transport error. Its exact 1,133-file successor
passes 169 checks across 11 hosted cases in each mode and ten freestanding
profile probes. Independent original/decoy Session tests each pass 34 checks
across five cases, including dual failure precedence and callback-before-I/O
geometry refusal. This helper is not part of the 236-artifact SDK qualification
and remains unattached to capture/Owner/root lifetimes.

Supplemental immutable-history enumeration, physical writer, direct/cache
attachment through the mounted Owner and final root reconciliation remain
implementation and execution obligations. The isolated candidates do not grant
mounted writing or root admission. Accepted Kernel919/OS623/SDK41 is unchanged.

| Guard/design evidence under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-session-counter-capacity-v1/qualification-attempt-03/RESULT.json` | `93ccf1fcd7b32f6b641e3993c2b4c3f57741251a3da2748f86b8aa57e62bf968` |
| `sdk49-session-counter-capacity-independent-v1/review-01/RESULT.json` | `140974e866fe0315b7ff0daad8d599d404a8450a27648b4bd502a3cb61b1cb29` |
| `sdk49-session-counter-capacity-sdk-v1/attempt-04/RESULT.json` | `8c25baf7fbcb9ee4869bd053aed26f48946eccf219eba8353c5763853debc34d` |
| `sdk49-session-counter-capacity-sdk-v1/root-readback-03/RESULT.json` | `87cb540e8ae601c90779b402ae9f08fc6b7418736a317b1f6b24c35219352b24` |
| `sdk49-session-counter-v25-integration-v1/install-01/RESULT.json` | `90c9038e29a63c510defc17fbd4601a1f40e75a62392beaba2f03dc3c67d7254` |
| `sdk49-session-counter-v25-independent-review-v1/post-install-01/RESULT.json` | `ca39836e0567e3bad5c5cd88d680a67082c87b729b50bd8e334a1f04d2546602` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V25.json` | `04647b9ec862e3139843c296230d407d6a43aaf0f9e8551881260302dca08f90` |
| `sdk49-metadata-read-guard-v1/candidate-v2/SOURCE_HANDOFF_V1.json` | `0e12b7efd2991db60cab72268903f5c047fc3040afbe47e372e0aca8bfb7bc21` |
| `sdk49-metadata-read-guard-v1/qualification-attempt-02/RESULT.json` | `934e8adcd2ccaf618f201fb49b203f79adca916e853dcffc4c8fd0a18be5bb8c` |
| `sdk49-metadata-read-guard-v1/transfer-size-attempt-01/RESULT.json` | `88661b8b15743df2b8d14ffc6e2d08b4b1ddeba06ab8289e39b285138b20f5bd` |
| `sdk49-metadata-read-guard-independent-v1/review-01/RESULT.json` | `d7a05bfeeeea27f7975e9f81c683bdf6f7450390255621fff7f09380893be5a4` |
| `sdk49-reclaim-writer-budget-design-v1/reviewable-02/RESULT_V1.json` | `77d6cfa95ecb235d627306cd43c119e133f256cd5411cb2602b395b621b9ae49` |
| `sdk49-reclaim-writer-budget-design-independent-v1/review-02/RESULT_V1.json` | `befec848bc3beee91ee1e8553b96dd4c8e8ff140b89b4df104240f9f1474740b` |
| `sdk49-reclaim-route-budget-v1/RESULT_V1.json` | `af4b3e73ad4efc804a20ae247b2bf18a8ca439f839429f6a043a7480c960e91c` |
| `sdk49-reclaim-route-budget-root-review-v1/FINDINGS_V1.json` | `dec2631a1edc2139a51148a8b7e3be18743a647954b670b4beded0272bbb1742` |
| `sdk49-reclaim-route-budget-v2/candidate/SOURCE_HANDOFF_V1.json` | `634bc3e558ae1352a3bb6e0535a4d55f15e35410d31bc716c26d13dfabc71910` |
| `sdk49-reclaim-route-budget-v2/RESULT_V1.json` | `d5459bf85c60afc3f07a38f0067e5519bc35574790f3ab2ab421b5379169ae76` |
| `sdk49-reclaim-route-budget-v2-independent-v1/attempt-03/RESULT.json` | `a6304391f4da6b19149ce1199ebd3144026f47767142038d57584eebb5b21cc3` |
| `sdk49-cache-route-composition-v1/candidate/SOURCE_HANDOFF_V1.json` | `a9fbdb1c3f9af4783d3c10e62fa21ceeeb1af8239cfa52d58015d4aa64a34a4f` |
| `sdk49-cache-route-composition-v1/qualification-attempt-01/RESULT.json` | `c1924d6b9760d2ec7936376aa8ccdd222c7e44f1d7206cf3a5ba52e1050a0c52` |
| `sdk49-cache-route-composition-independent-v1/attempt-02/RESULT.json` | `3f9c1672ef6e1db3c3dcab015d9dfbe45a07d093cfc35708f3e2135176e02b2e` |
| `sdk49-cache-route-composition-sdk-v1/attempt-02/RESULT.json` | `ba3e247b4bc574346444ec6769ecfae3b7050519256ff047b5205e3e14d49511` |
| `sdk49-cache-route-v26-integration-v1/preparation-01/RESULT.json` | `8b13ddf671a44e8a8fd758c36c9c90a58b185a16c91d45371a00005c3c178aa1` |
| `sdk49-cache-route-v26-integration-v1/controls-01/RESULT.json` | `4334749fa705b507c47f1b749a011c792377e8cc0f171dd47e6b3aded1eb591d` |
| `sdk49-direct-read-guard-v1/qualification-attempt-01/RESULT.json` | `1ec86c19928f49176db85c8b0153116b255cdc447bd17787c7f1068e10c99622` |
| `sdk49-direct-read-guard-independent-v1/attempt-01/RESULT.json` | `5cb4d3651e65af81f03deccd532eff97406af0aec86e54b61337e5a4bb9f434d` |

### Current-main default Notes automation

The existing bounded Notes safe-save implementation is now present in the
primary OS tree, with native `openat`/`fstatat`/`unlinkat` wrappers and its xmake
source linkage. Its exclusive same-directory temporary, complete writes,
checked sync/close, metadata recheck, rename and checked parent sync preserve
the old destination on pre-rename failure. A post-rename failure reports
replacement without successful completion. This contract requires a
caller-owned nonshared directory and an ordinary caller-owned single-link file;
metadata checks are not inode identity, compare-and-swap or writer locking.

Fortified host `__read_chk` interception is repaired in the test fixture. The
retained first sanitizer attempt failed that injection gap and the first native
attempt failed an obsolete helper argument; successful successors preserve
both failures. Current-main hosted and ASan/UBSan runs each pass 40 fault/file
controls. Its explicit older ABI20 x86_64 Debug SDK consumer and 19-command
native English Notes/file-management workflow also pass. Root readback binds
398 artifacts and matching plain/sanitized case traces. This ABI20 main-tree
run does not promote accepted SDK41 or qualify private ABI48.

`xmake notes-save-check --output=DIR [--cc=CC] [--sanitize]` now provides the
repeatable hosted entry point, preserves existing output directories and disables
Python bytecode. Its two fresh task executions each pass 40 controls; ASan/UBSan
does not qualify leak checking. Root rehashes both results and 240 case logs.
`xmake plan-check` also passes 67 tests against the 90-requirement/163-test seed
ledger. These Notes workflows use RAM/SimpleFS in QEMU and do not establish
reboot persistence, ext4 editor power-loss durability or isolated graphical
editing. GUI Notes remains a separate prelinked runtime path. Physical M11
and manual M12 remain user-deferred.

Current-main Notes receipt SHA-256:
`ad0b84106d7de5994ee3ec68e3827203d00165e21f963a78129685317024ed60`.
The separate xmake-task readback receipt SHA-256:
`ebeb545f8db3e7e46293612aba2a74eea767e45faac12f887f3f654ed0b002a6`.
Evidence is under `build/prototypes/notes-main-integration-v1/root-review-01/`
and `build/prototypes/notes-save-xmake-task-v1/`.

### M0 storage tooling source pins

The 47 RFC Editor text references printed in the network plan's section 12
have been acquired and independently checked byte for byte (4,320,930 bytes).
Their draft manifest now has an offline source-readback tool and six regression
tests, including five negative controls, in `plan-check`; an additional direct
readback of the original 47 files
passes. This is source-reference preservation only: updates, obsoletes, errata,
normative clause scope and owner/test mappings remain unreviewed. The
`internet-rfc-clauses` index stays null and M0 remains open. Acquisition receipt
SHA-256: `9cdc15e559ea492f6b36f74c1ced03580a53399309b1dc2e3b64394ecdf04d09`;
independent receipt SHA-256:
`cfb855cff4ef791548c9daf07c1c1ca623e041a9d5e5109ca0a8c5bbdaf0d114`.
The repeatable manifest SHA-256 is
`81124829a7ea740ac09cd785d113e8533cf8ceb697888547acd70acc33d26aff`;
the direct readback receipt SHA-256 is
`45768d761da3751171f056fb07e5f2f29ec469b602524699e0d595bc02e00319`.

The official e2fsprogs 1.47.0 and 1.47.2 source archives are now fixed in the
contract ledger. The former matches the installed host tool version; the latter
is the selected second source baseline. The source-pin qualification itself
did not build or execute either release.
`tools/check_e2fsprogs_source.py` checks complete archive hashes, safe unique
member names, eight exact format/checksum/journal/tool source files per release,
and matching release headers without extracting or executing upstream code.
Four wrong-pin/duplicate-input controls fail without publishing passing output.
Detached signatures are retained; packet inspection identifies the same issuer
but does not verify either signature.

The separate `e2fsprogs-dual-tool-interop-v1` lane now builds unmodified pinned
1.47.2 source through an isolated xmake target and its upstream build recipe.
It uses bundled ext2fs, UUID and blkid libraries and installs nothing into the
host or rootfs. The first configure attempt incorrectly selected an unavailable
external UUID development library; its failure and recipe remain preserved.
The successor build passes, retaining 2,319 regular source files, the one
upstream release-notes symlink, 420 build files, tools and exact executables.
Both installed primary 1.47.0 and built secondary 1.47.2 pass read-only
`e2fsck -fn` for seven explicitly pinned recovery/Notes images. Each refuses the
damaged root-inode-checksum copy with exit 4. All 16 checks leave image hashes
unchanged, and independent readback passes. These are bounded host-tool image
checks, not new native writer execution, general two-version filesystem round
trips, authenticated signatures or reproducible tool builds. The build receipt
pins the xmake target and recipe; a separate outer xmake launcher log is absent.

Secondary build receipt SHA-256:
`30ff66d105f73f0fb39ff766719cdf5b02a7100b5e9470f75ccefbcb5ff2664b`.
Dual-tool interoperability receipt SHA-256:
`dcb181914ee5e6d941b41b4bbff507e17c042c29c58349a8a5d0676c0c46e1fb`.
Independent audit receipt SHA-256:
`1db4f1e356f3cfa481b4c8afb47b9cbf9ec1b92729796cfb50c8c629bae1e2a2`.

The ledger still has 90 seed requirements, 163 tests and all ten architectures.
All four complete reviewed source indexes remain absent, and `gate-m0` still
fails with an explicit source root. Ledger/source validation and 67 `plan-check`
tests pass. The initial stale ABI-draft revision failure is preserved; regeneration
changes its ledger revision while retaining all ten unqualified ABI profiles.
No requirement, architecture row, tool execution or ext4 qualification is added
by these source pins.

A separate source audit adds a draft catalog of 40 ext4 and seven JBD2 literal
feature macros, checked directly against four members of the pinned Linux
6.13.4 archive. It records exact source lines, raw existing mask checks, all ten
architectures and candidate owner/test links. The draft remains outside admitted
coverage and does not enumerate reserved bits, format fields or legal feature
combinations. The four-domain gap audit now reflects both e2fsprogs byte pins;
POSIX/RFC/xmake pins, signature authentication and full reviewed indexes remain
open. Its receipt is
`m0-source-index-gap-audit-v1/attempt-01/result.json`, SHA-256
`ca3865e310989892a41465f0091ed9802714ce146a14c6824a2def13abceb19b`.

| M0 source-pin evidence under `build/prototypes/m0-e2fsprogs-source-pins-v1/` | SHA-256 |
| --- | --- |
| `SOURCE_PIN_QUALIFICATION.json` | `3506b4a38b029670e21d28184960cded05eaa640081fde74eed6c59d0ac7244f` |
| `FREEZE.json` | `071454735c1e9642f5d9a4253622b043fdaea104efe3b1909eebe0a1b4377e22` |

### Read-only active-reclaim retained history (V21, experimental ABI48)

V21 installs the exact reviewed V6 seal and three legacy Owner test migrations:
seven modified paths and one new header, with complete 1,120-file before and
1,121-file after archives. Independent readback confirms all source bytes,
generated exclusions, checkpoint fields and the exact eight-path delta with
zero mismatches. The seven rename paths, five lifecycle paths and both V20
startup/history test migrations are preserved.

The seal retains original capture bytes, semantic results, reclaim plans and
canonical WAL independently from verifier scratch. Exact callback progress,
original Session lineage and independent admission latches prevent stale or
substituted state from granting admission; uncertainty quarantines the original
Session. This slice does not enable the active-reclaim writer.

The exact V6 gate passes 40 probes in ordinary and ASan/UBSan campaigns with
per-child attested 8 MiB soft stack limits. Ten freestanding architecture profiles
compile; 6,070 function records have a maximum individual frame of 13,008 bytes,
below 16,384. This is not a cumulative call-stack bound. All 17 legacy inline
Owner test objects move to heap-backed fixtures without changing assertions or
destructor boundaries. Six canonical Owner campaigns and six adjacent
C1/startup/namespace campaigns pass, including complete disk parity, independent
goldens and read-only e2fsck checks.

The exact 1,121-file producer passes standalone x86_64 Debug xmake/QEMU diagnostics
and exports 231 declared experimental ABI48 SDK artifacts. The exact 627-file OS
consumer passes distro, rootfs, UAPI and libc builds using only those artifacts.
This does not qualify a new active-reclaim guest, native SMP, Release, hardware,
or a complete twenty-profile SDK matrix. The accepted SDK41 baseline is unchanged.

| V21 evidence under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V21.json` | `64c77329acc8a56515334dc1c3c03f2cc1bb202b716b5a54af34b7baf4745729` |
| `sdk49-reclaim-retained-v21-integration-v1/install-01/result.json` | `69e3f873915b8210e367b76dae028b9800bfcbef904e4445000d8d32d4b8cdd5` |
| `sdk49-reclaim-retained-v21-integration-v1/independent-readback-01/result.json` | `d503987533d882c9000ec993a6624f7cc503fcba2678704c4959f96df4d5af09` |
| `sdk49-reclaim-retained-seal-v1/freeze-v6-01/FREEZE.json` | `1ca0830364001fd8e565df00a2eef1f475f65ddc3c9d5301b93f8fb00a2a6a4e` |
| `sdk49-reclaim-retained-v21-integration-v1/sdk-readback-01/result.json` | `45057e6d0d7573cf9137e7ce317db6cbb061bd0f44b876a8262b2066c1fd8e9a` |

The rejected installer and all earlier failed controls remain separate evidence.
Its successor passes bounded source review and four isolated filesystem controls,
including an interruption after checkpoint publication. These controls do not
claim arbitrary process-death or power-loss recovery. Next work is the prospective
read-only terminal-history proof, with distinct zero/nonzero remaining-chain
branches. Before writer implementation, resolve C1-evolved shared-home/WAL history
and computable complete-route reservations/accounting from the independent V3
design review. Mounted active-reclaim dispatch remains disabled.

### Actual default Notes saves and same-disk reopen (V18 source, experimental SDK48)

V17 installs only the independently reviewed seven-path Linux rename delta onto
V16. Generated mappings preserve all ten ABI profiles. Ordinary `rename`,
`renameat` and zero-flag `renameat2` use the existing native backend; unsupported
special flags fail before mutation. V18 adds only two storage headers and one
hosted test. Linked regular nonmembers may use larger initialized inline extents
within the checked 32 MiB profile, and linked fast symlinks may use 1–59 inline
bytes. Orphan victims and directories keep their 64-block limits; allocation,
alias, checksum, directory reference and exact whole-bitmap checks remain.

Plain and ASan/UBSan each pass 65,905 storage checks, two actual hosted canonical
Owner recoveries and 28 zero-WRITE/FLUSH refusals. Four recovered images pass
read-only e2fsck; retained regressions and all ten freestanding profiles pass.
Independent adversarial/source audits and standalone xmake/QEMU diagnostics
pass. Exact V18 installation reads back all 1,107 sources with zero mismatch,
preserving the seven rename and five lifecycle paths. Generated bytecode is
explicitly excluded from the source inventory and retained separately.

An isolated producer with the byte-exact V18 composition exports experimental
ABI48 x86_64 Debug artifacts. The OS passes SDK-only distro/rootfs/UAPI/libc
builds. The Notes native fixture also builds only through those exported
artifacts, retaining its original static musl ELF and initial guarded filesystem.
An early combined guest completes all twelve saves but fails clean freeze:
native startup deliberately retains the selected root in PID0 boot cwd for
kernel diagnostics. A preserved diagnostic successor identifies exactly this
one root descriptor hold and zero owner buffer work.

The terminal OS fixture now checks that every native user has stopped, retires
only its owned boot cwd through checked `Node::release()`, and verifies zero root
descriptor holds. Production clean-freeze checks remain in force. This fixture
policy is not a general service shutdown API. The initial guest passes twelve
production Notes replacements, old bytes/identity after replacement, seeded
hardlink lifecycle, default CLI reopen, `ls`/`cat`/`mv`/`rm`, and clean seal.
Completed actual Virtio I/O is 1,619 writes and 1,326 flushes. Independent e2fsck,
inode checksum/mode/ownership/link/size/content checks and partition guards pass.

The second boot uses the same kernel image, exact `/init` ELF, argv and scratch
disk without reseeding or reinstalling. It executes only the read-only Round12
reopen protocol at epoch1 with zero user mutations. Its three writes and five
flushes are dirty-open and clean-seal transport operations. Complete records and
payload CRCs are checked; the entire final guarded disk is byte-identical to the
first final disk (`89d3e0bfdfeec6226e96ab89abe3eee221b1bdd93dd09f43e653202a75a7b4c0`).
Second-boot e2fsck and Notes inode/content checks pass. Independent actual-log
review rejects 31 adverse controls. Earlier substring and wrapped-I/O observers,
their findings, failed controls and unsuccessful guests remain preserved.

| Exact receipt under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V18.json` | `74bb57c350194582c7ecd350dae14f897c995d16cfc9b665f987c7a923ada29e` |
| `sdk49-orphan-nonmember-v18-integration-v1/RESULT.json` | `0136d5c25fc890c3fc5a35b14a2c8bcc70c7ea241a5c3a3ef22c5aa394c9e1c2` |
| `sdk49-v16-rename-storage-experimental-sdk-v1/attempt-01/result.json` | `c43eb9ba686a78eda7473177ad84a1f41f9a62ca2e1ca28b061bedf9ced92200` |
| `sdk49-notes-terminal-drain-fixture-v1/build-attempt-01/result.json` | `dcd7d8efb2dc38048a4951e8fe253886728649f009ea7c275c64e0323f7f68e2` |
| `sdk49-notes-terminal-drain-fixture-v1/initial-guest-attempt-01/result.json` | `a245a6c4662f6d18e3688c2de323630a7c0ab2d882eda2ab990db773526cb3c5` |
| `sdk49-notes-terminal-drain-fixture-v1/reopen-guest-attempt-01/result.json` | `09e929369be86dc39d61f65d381261a044edede9030425a0a5e28f6386869b6e` |
| `sdk49-notes-reopen-observer-independent-v1/actual-v3-01/result.json` | `6d9cc6b3b14532fedc2d268f9e8711ad718eb13fd19d456decc55d2ef6dc9e6e` |
| `sdk49-notes-terminal-drain-fixture-v1/RESULT.json` | `7d9ef9695c8f14f642a467736af1a6929d5185ded3d638df5f070cf758cb77f2` |
| `sdk49-notes-terminal-drain-fixture-v1/FROZEN_WORKFLOW_V1.json` | `1b615d2a97d53649495db041d59cbe78a54f023124c6ce047895d4a485723b2f` |

Final readback confirms the SDK producer's 1,107-file source map equals private
V18, all SDK/native artifacts retain their pins, and both guest receipts and
independent tool logs remain intact. The aggregate checks the initial complete
records and replays the reviewed second-boot oracle without rerunning guests.
All 403 workflow artifacts are frozen with zero readback mismatch.

This closes the bounded automated CLI save/reopen scenario only. Installed
separate application exec, GUI, full POSIX, full ext4, mounted startup recovery,
active reclaim recovery, interrupted-write campaigns, SMP and complete M0-M12
qualification remain open. All ten Kernel and four supplied musl userland
profiles remain in the matrix. Accepted Kernel919/OS623/SDK41 is unchanged;
physical M11 and manual M12 remain user-deferred.

### Four supplied userland profiles: actual default Notes save and reboot

The additional aarch64, rv64 and loongarch64 Debug producers compile exact V18
archives of 1,107 Kernel sources and export their own architecture/mode/compiler-
bound experimental ABI48 SDKs. Their OS consumers each compile 627 pinned OS
sources through those artifacts. SDK-only distro/rootfs/UAPI/libc builds pass;
the byte-exact terminal fixture consumes each new SDK and its original pinned
static musl executable and guarded Notes disk. There is no Kernel source fallback.

Each additional actual QEMU/Virtio guest performs twelve production CLI Notes
replacements, retained old-descriptor and seeded hardlink checks, default reopen,
`ls`/`cat`/`mv`/`rm`, and checked boot-cwd retirement followed by production clean
freeze. All three report epoch161, 160 mutations, 1,619 completed writes and
1,326 flushes. Each second boot retains its exact kernel, ELF, argv and live
disk, without reseeding or reinstalling, and executes read-only Round12 reopen
at epoch1 with zero user mutations and three writes/five flushes. Read-only
e2fsck, inode checksum/metadata/content checks and unrelated-file checks pass
after both boots. First final, second input and second final guarded disk bytes
are identical within each profile.

Unlike the x86_64 debug-exit, these three platform debug-exit functions are
no-ops. The host observer requires a unique complete native terminal seal,
then requests QEMU termination and archives that observation separately. This
is neither a power-loss campaign nor a production shutdown API. The original
LoongArch attempt completed its saves and seal but was refused by a firmware-
only image-source observer. V2 binds `linker` to loongarch64 and `firmware` to
the other two profiles; a fresh LoongArch campaign passes. V2 also revalidates
both earlier successful profile logs. The first failed CRC control is retained:
its replacement value was already zero, so it did not change the log. Corrected
controls require changed input and pass seven positives and 114 refusals,
including malformed/duplicate/wrapped records, wrong credentials/image source,
missing rounds/drain, post-seal I/O, changed CRCs and incomplete async output.

| Receipt under `build/prototypes/sdk49-v18-notes-four-profile-v1/` | SHA-256 |
| --- | --- |
| `aarch64/two-boot-attempt-01/result.json` | `3cd64a3fa1eb75ab07c44a84b8d31818f2941440a61c117a3af5000cdc1c148e` |
| `rv64/two-boot-attempt-01/result.json` | `77f3af37b6e3b42ab44233bf1a1f180730b19cb015767f428d99649a7dc8933f` |
| `loongarch64/two-boot-attempt-02/result.json` | `361da607d088d17f1b0f84a86d85687a7cd5f2900fd5675dbc310fa9c9b03084` |
| `observer-controls-attempt-02/result.json` | `2b14fe17c54cb107697f6d60623048e9b375aed08ad30afce01dc1b317802808` |
| `RESULT.json` | `c134845e206b2afd6bda204286422ebf0c1e2f5ac3f27be7787e197406d87de8` |
| `FROZEN_CAMPAIGN_V1.json` | `9618a6d0997ad714afd30055b4cb3f7191ec14bf3b8c52adc1f669c8a0dffe63` |

All 8,398 campaign artifacts are frozen with zero readback mismatch; the prior
x86_64 workflow freeze is rechecked unchanged. Independent campaign review passes
eight positives and 22 refusals, rechecks each native ELF architecture and raw
disk, and independently verifies all 23 changed sectors are covered by actual
writes and 18 nonoverwritten write ranges match persisted CRCs on each profile.
Its receipt is `sdk49-v18-notes-four-profile-independent-v1/attempt-01/result.json`
(`4190fe6caca69eb066181ac5caa89bace2ed0b1653a4578e3c76a4d532de0983`).
The immutable aggregate still records review as pending at its original creation;
the later independent receipt is the additional review evidence.

Explicit observer limits are recorded separately in
`sdk49-v18-notes-four-profile-independent-v1/limits-attempt-01/result.json`
(`916d82668878601421fda7df944b415cb7ac56d6f98c6a88023604deb29432a5`).
The first-boot line parser validates CRC width and I/O bookkeeping; its raw
payload binding comes from the independent final-media oracle, which rejects a
changed CRC. Image-source markers alone cannot distinguish the two firmware-
backed architectures; complete qualification also pins architecture-bound SDK,
kernel and user ELF inputs. A forced-kill observer control is refused, while V2
recognizes the preserved original LoongArch log. These are hosted controls over
existing guest evidence and do not execute additional guests.
The independent review is frozen in
`sdk49-v18-notes-four-profile-independent-v1/FROZEN_REVIEW_V1.json`
(`0739f50c859cb59750d002ea220c28e051c4eeff74243e5645c98a0910dc6dce`),
with 66 artifacts and zero drift. Its aggregate `RESULT.json` is
`2d4dcbced926735575825564c52e4f712e85b1d924364ffa46e4bcc2428a3094`.

This qualifies the four supplied static musl CLI fixtures only: all
ten Kernel profiles remain required, and remaining musl ports, Release, shared
loader, separate application exec, GUI, mounted startup/active recovery,
interrupted writes, SMP and hardware remain open. Accepted Kernel919/OS623/SDK41
is unchanged; this does not close M0-M12.

### Actual standalone C1 recovery of the original failed Notes disk

The original failed Notes disk is copied once into a new SDK-only x86_64 Debug
standalone recovery lane. Actual QEMU/Virtio C1 recovery now succeeds: 6,041
reads, 15 writes and eight flushes clear the one-member orphan chain and empty
the journal, ending at sequence37. Read-only e2fsck passes; `/init`, the original
Notes destination, `/seed` and `/other-owner` contents remain unchanged. All 18
changed physical sectors are covered by actual writes; 14 final write-range
CRCs agree with the resulting disk. The original failed image is untouched.

The receipt is
`build/prototypes/sdk49-empty-orphan-sdk48-native-v2/RESULT.json`
(`325ab5dcea0a60367a3e107643fc2905e3ad074c31d25ddd1405d901c3c381d5`).
This executes the standalone fresh Owner, retains the recovery dirty bit and
does not prove mounted startup recovery, active reclaim recovery or clean
shutdown. The continuing Owner/cache/Session startup port has separate evidence
below; the standalone receipt alone does not establish it.

### Continuing-Owner mounted C1 candidate and whole-chain preflight

The isolated mounted startup candidate adds an optional, permanent startup
workspace separate from live reclaim storage. Its claim precedes Owner open;
policy/overlap preflight precedes the claim. The original Owner, canonical cache,
Session, partition bounds and exact operation counters continue through checked
classification, complete chain capture, C1 publication/checkpoint/readback and
strict ordinary admission. During callbacks, the mount remains opening at
epoch zero with no published root or populated runtime Nodes. Complete initial
member identities and preceding actual all-after history remain retained across
handle rearm. Ordinary mount epoch is one after admission, with a separate
monotonic startup seal generation.

The first frozen attempt-06 passed its hosted/compile/standalone gates but failed
independent mounted acceptance: a checksummed later member with exhausted
generation was refused only after the first member's 15 writes/eight flushes.
Root remained unavailable and the Session quarantined, but this deterministic
capacity limitation was already known from the complete initial capture. The
successor therefore checks every captured member's generation, supported ctime
and single data-allocation-group limit before the first WAL write. Independent
zero-write requirements are retained. The original candidate, failed controls
and finding freeze remain intact. A separate valid-CRC cross-data-group fixture
reproduces the older partial commit and confirms successor zero-write refusal.

The strengthened attempt-08 has exactly 1,113 source files: two modified V18
headers and six additions, including all private `.inc` dependencies. Its source
archive is separate from standalone build output. Plain and ASan/UBSan both pass
seven accepted mounts, 19 refusals, three transport faults and 164,188 callbacks.
Each accepted case compares whole-volume startup goldens, performs two ordinary
existing-file writes through the same Session, syncs, freezes and reopens.
28 read-only e2fsck outputs, prior mounted-dirty and 23 Owner invariant cases,
ten architecture mounted and standalone Owner probes, and the ordinary x86_64
Debug Kernel/QEMU diagnostic pass. The latter boot does not execute the new
mounted route. Independent source review verifies all 1,113 source and 2,574
artifact hashes. Independent actual hosted mounted execution now passes on the
same exact archive: eight mounted cases, 16 ordinary writes, five active-family
refusals, 17 other zero-write controls, 50 transport faults, a post-checkpoint
history drift and permanent workspace reuse after destruction with a fresh
ready registration. Plain and ASan/UBSan agree; 32 read-only e2fsck checks pass.
All 3,514 acceptance artifacts read back with zero mismatch. This hosted result
remains distinct from the actual Virtio execution below.

| Receipt under `build/prototypes/sdk49-mounted-startup-c1-successor-v1/` | SHA-256 |
| --- | --- |
| `evidence/attempt-08/result.json` | `947e8d1c97eaf6cd25ef7c3ce63461004a6d17c81ea47b9adab622893fb45782` |
| `FROZEN_V2.json` | `d67f9ab67eb4a00f8014e6cc988b4c7d6f6ce227e40699a39a911c339f2b42c1` |
| `DATA_GROUP_BINDING_V1.json` | `6c92fbca2f06104a2244f4b618ca2033f92be09302374ca16752302c7dda024e` |

The SDK-only native lane in `build/prototypes/sdk49-mounted-startup-c1-native-v1/`
now passes an actual x86_64 Debug single-CPU QEMU/Virtio campaign. An exact
1,113-file Kernel producer exports experimental ABI48 artifacts; the 627-file
OS consumer builds its distribution/rootfs/UAPI/libc targets through those
artifacts. The native fixture compiles only its guest and pinned OS
Virtio/entropy/archive sources, linking exact SDK libraries and extracted boot
objects. No Kernel source is compiled by the OS fixture. The SDK inventory
rejects unlisted entries, special files and root/ancestor symlinks.

The guest uses the original failed guarded Notes disk and one continuing
mount/cache/Session. Every opening callback observes epoch zero and no root.
Recovery clears orphan head20 at sequence37; two actual ordinary same-byte
Notes writes advance epoch1 to epoch3, followed by production clean freeze and
detach. Completed transport is 9,034 reads, 33 writes and 27 flushes; the guest
exits through the x86 debug-exit with code33. Retained strict admission counters
are separate from root construction and subsequent stage snapshots.

Independent review checks complete records, all Session identities/counters,
the 11-sector prefix and 19-sector suffix, 20 changed-sector write coverage and
15 surviving write-range CRCs. Overwritten writes are not claimed as persistent
CRC observations. Read-only e2fsck, inode checksums and Notes mode/ownership/
links/size/content pass; both seeded hard links, `/init`, `/seed`, `/other-owner`
and complete `/home` namespace remain correct. The final journal is empty at
sequence43. All 92 adverse observer controls are refused. The aggregate freezes
7,867 artifacts with zero readback mismatch.

Earlier SDK/helper root-symlink gaps, the missing clock-header build failure,
the first successful guest's overly narrow `/home` oracle, and all superseded
and failed attempts remain preserved. The corrected oracle includes both
existing hard links. This is kernel-native mounted execution; `/init` and musl
are not executed by this fixture. Namespace-to-C1, writable active reclaim,
interrupted-write/restart campaigns, other native mounted architectures,
Release/SMP, GUI and hardware remain open. Accepted Kernel919/OS623/SDK41 is
unchanged and M0-M12 is incomplete.

| Receipt under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-mounted-startup-c1-independent-fixtures-v1/mounted-attempt-06/result.json` | `4aaef01cec9c246cac273695a1b364a1ce6ff15f4c57f22c77cb335d07cbc2fc` |
| `sdk49-mounted-startup-c1-native-v1/sdk-attempt-03/result.json` | `4867bbdc5d8a6f6bbdf3385e708503f151494b58cf53544ed94fd164a00ccd6b` |
| `sdk49-mounted-startup-c1-native-v1/native-build-attempt-02/result.json` | `cd4d85405983e02c14621db6a5b7c88c4fc70041dc88380914d7151e098758ee` |
| `sdk49-mounted-startup-c1-native-v1/native-guest-attempt-02/result.json` | `b49e460495cbc4fd4058fdc2483c2626875771ba85b9f1f49b89dc01a18b80d6` |
| `sdk49-mounted-startup-c1-native-v1/RESULT.json` | `9b4ec9221c27da97556f666146f256799ab756452a0aed5492d259aaeeed967f` |
| `sdk49-mounted-startup-c1-native-v1/FROZEN_NATIVE_V1.json` | `3f4b1d456b227ba748b85726b394f5013dbdfa0edef089a087b38a8769599cd2` |
| `sdk49-mounted-startup-c1-independent-v1/NATIVE_GUEST_REVIEW_02.md` | `65cad69c3894e5b038c785528abeaa972b722cc1e51583aab760cb41e20f1175` |

### Prospective namespace result history (isolated implementation)

`build/prototypes/sdk49-namespace-result-history-v1/` adds a private one-shot
prospective capture over the exact mounted C1 archive. It retains the strong
namespace proof, original locator/participant/bitmap/descriptor/journal-inode
bytes and derived empty
head, then validates the complete prospective orphan/ownership/directory source
set using physical reads on the continuing Session. It distinguishes these
expected bytes from an executed checkpoint. The active namespace route still
refuses before WRITE/FLUSH, preserves epoch zero and denies root publication;
prospective capture cannot produce a reclaim plan through the public interface.

The independent baseline corpus executes actual hosted canonical namespace
checkpoints for every one of the five-home transaction's 32 whole-home
combinations. All terminal images match, with orphan inode14 and cleanup
sequence22. Its 1,275 frozen artifacts read back without mismatch. The new
provider's self qualification passes 48 commands: plain and ASan/UBSan agree
on 233,102 checks, 32 prospective cases, three read faults, seven source drifts,
one locator substitution and 39,598 callbacks. All retain zero WRITE/FLUSH,
zero namespace checkpoints and no root publication. Mounted C1 and physical
capture regressions, 19 read-only fsck checks, ten new-history probes and ten
standalone Owner probes pass. The maximum reported per-function stack frame is
13,008 bytes; this is not a cumulative native stack measurement.

The final 1,117-file source map and 1,347-artifact self freeze have an independent
complete-hash audit. Full independent provider execution subsequently rejected
this frozen candidate: a final comparison callback could alter already compared
prospective result storage or initialized-group interpretation while the
provider still reported validation. Its source and failed receipt remain
unchanged. Neither the baseline corpus nor self qualification proves a
continuing namespace-to-C1 transition. An earlier review found that already observed
descriptor/journal-inode bytes were not compared on later capture reads. The
final candidate seals and compares them, with checksummed drift controls.
A nonparticipant change before its first retained observation cannot be inferred
retroactively. No namespace or active-reclaim writable gate is supplied here.

The isolated `sdk49-mounted-namespace-c1-v1` successor seals the complete
prospective storage, source pointers, recovery binding, initialized groups,
chain/directory/bootstrap counts and report identity before the final capture
comparison. It checks the retained result before and after callbacks, keeps its
capture counters separate from later Owner I/O, and checks the exact terminal
verification count. An independently reproduced `seal.ready` rollback bypass in
the first repair is preserved with its self freeze and explicit rejection.
The corrected successor uses a separate established state, rejects inconsistent
seal state and includes twelve late-result controls. Its latest self qualification
passes all 48 commands: plain and ASan/UBSan agree on 301,856 checks, 32
prospective cases, twelve late-result controls and 53,320 callbacks, with zero
WRITE/FLUSH/namespace checkpoints. Mounted C1/physical capture regressions,
nineteen fsck outputs and twenty probes across all ten architectures pass;
maximum per-function stack remains 13,008 bytes. Its 1,354-file self freeze reads
back without mismatch. Final independent acceptance binds the exact latest
archive and freeze: eighteen required groups pass in plain and ASan/UBSan,
including latch rollback and simultaneous latch/ready rollback; category logs
and media agree, and all 1,117 source entries remain unchanged. Independent
source/receipt review accepts this read-only hosted scope only.
The combined acceptance reads back 2,624 self/independent evidence files with
zero mismatch. It is the pinned predecessor for the separate
`sdk49-mounted-namespace-c1-writable-v1` implementation lane. That lane now
self-qualifies the bounded same-Owner writable namespace checkpoint followed
by physical C1; independent frozen-provider and SDK/native gates remain pending.

The preceding corrected archive passes all seventeen required independently
authored groups in plain and ASan/UBSan, including thirty-two complete golden
comparisons, retained storage/structure/pointer/counter changes and the final
journal-record callback. Two physical-only changes after a source's last read
remain recorded as temporal observation limits: serialized block reads do not
provide an atomic media snapshot. A writable successor must retain exclusive
device ownership and compare the sealed complete history before checkpoint,
after the homes become durable and after journal cleanup. This read-only
successor still performs zero WRITE/FLUSH, publishes no root and enables no
writable namespace-to-C1 path. The reviewed writable design and independently
generated namespace-terminal-to-C1 golden are preparatory evidence only.

V19 installs only the qualified C1 eight-path delta onto V18: two modified
headers, six additions and 1,105 unchanged files. Independent readback confirms
all 1,113 private sources equal the qualified C1 candidate; all 1,107 V18
predecessor sources, seven rename paths, five lifecycle paths and historical
receipt references are retained. The namespace prospective candidate remains
in its separate lane. Accepted Kernel919/OS623/SDK41 is unchanged.

| Receipt under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V19.json` | `99d3038fc3816d1dd1131710daa00216850d7199cf3f9755fd792193ed6c6319` |
| `sdk49-mounted-startup-c1-v19-integration-v1/install-01/result.json` | `2c0e0ab1621b92e654f6a55feb976e61aede63aecc7e9be5767c7b7c306e9c1b` |
| `sdk49-namespace-result-history-v1/evidence/attempt-02/result.json` | `892243a7f1570ef5ed5d5b3f0625a095d3b1708977a39ec9dd9a39c156e8c357` |
| `sdk49-namespace-result-history-v1/FROZEN_SELF_QUALIFICATION_V1.json` | `c7cd79b4b3e83c9cd3aaf07a3e23da95f6d075367e09d9b3c9aadc0ad0ea4980` |
| `sdk49-namespace-result-history-independent-v1/FROZEN_NAMESPACE_AND_V19_AUDIT_V1.json` | `6a411a32d5b211b20915e51f4a00c63db855c5316ab17bcf04c7b736ee7e5db0` |
| `sdk49-namespace-result-history-independent-v1/provider-attempt-03/result.json` (rejected) | `43ece62f0dcd4441902d3acae6c7504f6e2d8d98456fef45750820baa08e00aa` |
| `sdk49-mounted-namespace-c1-v1/READONLY_ATTEMPT_01_DISPOSITION.json` (rejected repair) | `b8a0db52bf0968eeff41c9709c03e738abf8ffecb9214a98e782ed78031d6484` |
| `sdk49-readonly-seal-independent-v1/attempt-04/result.json` (preceding corrected archive) | `7198bf1e7044147dffdfeeaec1be69a97b6b46db30b037421b54003a8470bbc0` |
| `sdk49-mounted-namespace-c1-v1/readonly-attempt-03/result.json` (latest self qualification) | `5e37a1666d46b95f83dca2eb716a717fc59931297d52239f361137e85e1760ea` |
| `sdk49-mounted-namespace-c1-v1/FROZEN_READONLY_SELF_QUALIFICATION_V4.json` | `59293b1e94f966e432d4edece6720b2ff422c9d1ada77955553f4f99e94d3566` |
| `sdk49-readonly-seal-independent-v1/attempt-06/result.json` (latest independent acceptance) | `80d30fa2ac678c69518659aaab591d8d7f6ca3f210d88d58b11b8c4826b7d36b` |
| `sdk49-readonly-seal-independent-v1/INDEPENDENT_REVIEW_V4.md` | `0324a425e9250c5c9a09914f037e53718d49721296942e1437175342b5e2e10d` |
| `sdk49-mounted-namespace-c1-v1/FROZEN_READONLY_V4_ACCEPTANCE.json` | `56069beb06b87c5fdf71d35943276218ffa55be240efeed0f80c5a4b9b90aee2` |
| `sdk49-mounted-namespace-c1-independent-v1/HANDOFF_V1.json` (fresh Owner golden only) | `3f3a8418327399cc8fbe91b613cf5df70481ea1249223ebcff4e640adc4aeba7` |

### Writable namespace checkpoint to physical C1 (isolated candidate)

The accepted read-only V4 seal is the exact predecessor of a separate writable
lane with 1,120 source files. The private namespace executor retains the same
mounted Owner, canonical cache, registration and Session, keeps public Owner
admission excluded, publishes canonical images twice, and compares complete
physical history before ordering I/O, after durable homes and after empty-head
cleanup. It writes only checked before homes and the derived empty journal
head; committed records remain unchanged. It drains its transaction and pins,
privately rearms, and compares the first physical C1 capture with the retained
prospective result before planning and again after preparation callbacks.

Self attempt-02 passes 52 commands. Plain and ASan/UBSan agree on 3,231,788
checks, 32 legal home-state combinations, four zero-WRITE/FLUSH refusals, nine
I/O faults, five history controls, one ordinary save/reopen flow and 365,703
callbacks. All 32 startup images equal the independent terminal C1 golden
`1cdd9f130ecace35630f2053236fccc523a22635d1dee7a1e42bb90e8a04939f`.
Mounted C1 and physical-capture regressions, 23 read-only e2fsck outputs and
twenty freestanding probes across all ten architectures pass. Maximum
per-function stack is 13,008 bytes, not a cumulative native-stack bound.
The self freeze reads back 1,497 declared artifacts with zero mismatch.

Attempt-01 remains preserved: all 32 complete startup images matched the
golden, but its late root-construction read-fault assertion incorrectly required
the historical strict-admission flag to be cleared. The corrected test binds
that flag to the admission event actually observed during callbacks; failed
mount, epoch zero, no root/lifetime, quarantined original Session and no further
I/O remain required. Production source is unchanged between these attempts.
A separate twelve-header source review found no actionable ordinary correctness
issue; this review alone is not writable execution acceptance.

| Receipt under `build/prototypes/sdk49-mounted-namespace-c1-writable-v1/` | SHA-256 |
| --- | --- |
| `evidence/attempt-02/result.json` | `1c9cd3e8ff6b1b8271c3629e44d4a48c34461299d22f8f925b49bd020eafbc09` |
| `evidence/attempt-02/ARCHIVE_COMPLETE.json` | `f4514a785ad1b6eb75a89cebc0efd48d9339c0cccf17c0cd1f1e71c5c144a22f` |
| `FROZEN_WRITABLE_SELF_V1.json` | `daec536885f7b2c1b3ab06f37d6e685b1734c8c9eaec50225af2af8e2e5956f2` |
| `ATTEMPT_01_DISPOSITION.json` | `ba1c485a161d962fe460c6f8b2fcf6aeb99ec2f808b76b0b7b276de1e4ecdc79` |
| `evidence/independent-source-review-01/result.json` | `513869c006d28a1dec1652a197310773ed07b84710cbe690dff90913fe8a3d97` |

Formal independent frozen-provider acceptance now passes plain and ASan/UBSan
with 32/32 complete-media positives, 35/35 adverse controls and six read-only
e2fsck outputs. The full 1,120-source archive and independent copy remain
unchanged; category logs and final media agree. The combined hosted acceptance
reads back 2,702 artifacts with zero mismatch. These results are hosted only.

| Additional receipt under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-mounted-namespace-c1-provider-independent-v1/attempt-01/result.json` | `6fc6447d099bcce86225ae49d68e0ab0832ab4d4abb12f8b45aa3623af96ad40` |
| `sdk49-mounted-namespace-c1-provider-independent-v1/REVIEW.md` | `44af70ec2bd184b847babc588fe97a09b9baaca45b244d4e82d488da07428400` |
| `sdk49-mounted-namespace-c1-provider-independent-v1/FROZEN_INDEPENDENT_V1.json` | `84e5dcc809bd70b050b592f90c64f61e856d2b0150647ed71e4e931cce987043` |
| `sdk49-mounted-namespace-c1-writable-v1/FROZEN_WRITABLE_ACCEPTANCE_V1.json` | `395d2f11b88abf36be4ca334879470ee4796595d0a96797f192195ce8c1b57fb` |
| `sdk49-mounted-namespace-c1-writable-v1/evidence/independent-source-review-02/SOURCE_ACCEPTANCE.md` | `76bc04e4340b78b437fd113a832b0dddc86704218ff5b49e86e6ab4d897d8880` |
| `sdk49-mounted-namespace-c1-native-v1/sdk-attempt-01/result.json` | `8fd19b9c906b4f997c10e58acfcc0cfede5bbf572e23cf4dd881a7e2946d6707` |

The exact candidate exports an isolated x86_64 Debug experimental ABI48 SDK.
Standalone xmake/QEMU diagnostics and SDK-only OS distro/rootfs/UAPI/libc
builds pass. All namespace .inc dependencies are explicitly manifest-bound,
and the manifest/file map is unchanged through consumption. The native
successor's source, design and guarded-media observer are prepared in a separate
lane. Two actual x86_64 Debug CPU1 guests complete namespace-to-C1 startup,
two ordinary basic-file prefix writes and production clean freeze, with 10,967
reads, 39 writes and 30 flushes each. Their original receipts remain failed:
the initial final-media oracle incorrectly advanced inode generation instead of
ordinary version64. Independent byte diagnosis confirms only the derived inode/
WAL checksum consequences of that oracle mistake; generation remains0 and
version advances4 to6. Corrected observers and both read-only revalidations now pass independent
acceptance. Each complete 32 MiB actual volume equals the golden-derived oracle;
four regular files, final sequence31/head0, version6/generation0 and e2fsck pass.
All four observed stage boundaries end with completed FLUSH. Startup evidence
contains seventeen CRC-bound write payloads; it is not a direct raw startup
snapshot. Eighteen final surviving write payloads match their CRC bindings.
The original failed receipts, raw disks and logs remain unchanged, with no new
build or guest. The bounded native scope is x86_64 Debug CPU1 actual Virtio,
not a musl Notes/editor or isolated graphical application workflow.

| Native read-only acceptance receipt under `sdk49-mounted-namespace-c1-native-v1/` | SHA-256 |
| --- | --- |
| `native-revalidation-attempt-01/result.json` | `39cc517eb48ec010b64993c5c8c9b66f81dcb06bf00ce61f27270b169bf96365` |
| `root-revalidation-attempt-01/result.json` | `7af22af9b6673689d7beb94e39dd56afdb4cd62ebdb6ce5edd481ada9808b70f` |
| `NATIVE_REVALIDATION_FREEZE_V1.json` | `395152af1c25dbd33609cdcda843a4a5cff494f4edd943a462c797f9f75e1e14` |
| `evidence/independent-native-revalidation-acceptance-01/result.json` | `4b0daea50d3d9032a68bd551b8a26aa6cd6690a287f43e4df6d6e493c6e7c1e2` |
| `evidence/independent-native-revalidation-acceptance-01/REVIEW.md` | `3bbd648f3c0c4a91980791b0b0ecf253456a7ba26655855229f1e16c9cabfbcd` |

A separate two-test migration preserves useful C1 and namespace-history coverage
on the new behavior. Plain and ASan/UBSan agree on seven C1 positives, seventeen
zero-I/O refusals, three faults, 32 actual namespace mounts and 23 negative
zero-WRITE/FLUSH controls; four read-only e2fsck outputs pass. The 1,120-source
production archive remains unchanged. The migrated test source and standard
integration patch are separate frozen artifacts, to be composed explicitly
before private adoption. Its result is
`sdk49-mounted-namespace-c1-test-migration-v1/attempt-01/result.json`
(`bc2c3eb26bd84ec2b7f031da7e783f509cf2f89e2ebad31729ccff4b5ac6904c`)
and freeze is `FROZEN_TEST_MIGRATION_V1.json`
(`42163eecfa27877397cfca84245ab11a36aedcc8116c6955c442d753097fea5c`).
Private V20 now installs the exact qualified composition: thirteen paths, six
modified and seven added, with the two independently migrated tests. Complete
before/after archives and independent root readback match all 1,120 source
files with zero mismatch. The 1,107 unchanged V19 paths, seven rename paths,
five lifecycle paths, excluded generated files and historical receipt references
remain preserved. Installation adds no build or guest execution; the recorded
candidate Kernel/SDK/OS and native acceptance remains its exact source evidence.
Accepted Kernel919/OS623/SDK41 remains unchanged.

| Private V20 composition receipt under `build/prototypes/` | SHA-256 |
| --- | --- |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V20.json` | `c533b1340868d111e1bd9d44e30bc2d49105a044875c08c0ecf6583613e3d54a` |
| `sdk49-mounted-namespace-c1-v20-integration-v1/install-01/result.json` | `a0ab0a08f36d8f989409d8c4d915c50bf07c5ad5b145b21454b689501022e40f` |
| `sdk49-mounted-namespace-c1-v20-integration-v1/independent-readback-01/result.json` | `8597ce875c2184273a455d414925ebbc3f12bed89a3c11c8ca0ed13e9d12228f` |

This bounded slice does not close interrupted startup, active-reclaim recovery,
full ext4, POSIX, desktop, SMP, Release or complete M0-M12 qualification. The
next isolated read-only active-reclaim candidate seals retained capture bytes,
bootstrap/WAL sources, original semantic and generated plans, exact callback
progress and admission latches. Independent review found admission/attempt
rollback and preseal nested-binding lineage gaps; successors repair them and
retain rejected candidate-v1/v3 evidence. Writer admission remains disabled
until read-only qualification and separate writable/restart gates pass.

### Cancellation before native lease retirement (V16, preserved predecessor)

V16 composes the reviewed exact five-file lifecycle delta onto V15, preserving
its newer owned-stat/bootstrap and cold-recovery sources. Before exit, image
installation or exec retires a native entry lease, the runtime cancels its exact
pending VFS request. Cleanup failure retains the pending record and lease.
Exec stages old tickets before scheduler commit and cancels them after a
successful commit but before peer lease release. Failed commit preserves old
waits; a committed cancellation failure escrows unreleased peers.

The actual serialized helper/provider and scheduler paths pass 48 commands,
including 517 lifecycle checks in each ordinary/sanitized mode and existing
origin/shared/continuation/signal regressions. Twenty signal-enabled objects
compile across all ten architectures. An independent x86_64 Debug standalone
xmake image build and QEMU diagnostics pass. The composed archive freezes 3,423
artifacts with zero mismatches; installation reads back all 1,104 source files
and preserves all 14 newer V15 dependencies.

The checkpoint is
`build/prototypes/sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V16.json`
(`89b606e4af412f4e2da23543681af7f710f3828b4d0653ce09d7718e8a7cafb2`).
The integration aggregate is
`build/prototypes/sdk49-vfs-lifecycle-v16-integration-v1/FINAL_RESULT.json`
(`089cf0b1dd116b0b898c19c828fb9cafe722897c8a1844784336df99268c6ac0`).
Full waiting-stat dispatch/load, partial cancellation recovery, guest lifecycle,
SA_RESTART and SMP are still unqualified. V16 is a private checkpoint; the
accepted Kernel919/OS623/SDK41 snapshot is unchanged.

### Fresh empty-orphan Owner and experimental artifact consumer (V15, predecessor)

V15 integrates the independently reviewed standalone fresh empty-journal orphan
recovery Owner. Its permanent, exclusive, off-stack workspace and original
canonical cache/Session retain the complete source history through actual
WAL/FLUSH, home readback and terminal ordinary binding. Hosted ordinary and
ASan/UBSan controls, 62 read-only e2fsck image checks, planner regression and all
ten freestanding profiles pass. The x86_64 standalone xmake image and QEMU
diagnostics also pass; that diagnostic boot does not execute cold recovery.
Mounted startup and active reclaim recovery remain unwired.

The predecessor private checkpoint is
`build/prototypes/sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V15.json`
(`060ad59286c3b1d2f45e4a1c43b74a13da4ec1308ffd5a7cb778422d9c75e849`).
Its inherited source-count field is corrected separately by
`V15_SOURCE_COUNT_CORRECTION_V1.json`: the pinned source map contains 1,102 files.
The immutable checkpoint has not been rewritten.

An exact isolated V15 producer exports ABI48 x86_64 Debug test artifacts. The
OS consumes only those exported artifacts and passes distribution, SimpleFS,
ext4-root, UAPI and libc build checks. The receipt is
`build/prototypes/sdk49-v15-experimental-sdk-consumer-v1/attempt-01/result.json`
(`a329e0b488814cfe9d3126a6eca32a62493006c8fd276fd3ee82c0cd97b663cb`).
The native Notes fixture also links and assembles through that exact SDK after
moving the exclusive reclaim workspace into BSS and constructing it once by
placement new. The original pinned musl ELF and offline disk are retained.

The first actual UID 1000 musl CLI Notes guest writes and syncs its temporary
file, then fails its first replacement with `ENOSYS`. Independent review
confirms that Linux `rename`/`renameat` dispatch is missing although the native
VFS backend exists. The failed disk, serial trace and completed Virtio calls
are preserved in
`build/prototypes/sdk49-default-notes-sdk48-native-consumer-v1/guest-attempt-02`.
This is evidence of an integration gap, not successful Notes save, clean
shutdown, reboot or GUI acceptance. A checked Linux rename-family successor
and a separate seed-aware read-only reboot probe are being implemented.

An additional standalone C1 fixture builds through the same exact experimental
SDK and attempts recovery on the captured failed Notes disk over actual Virtio.
It rejects before any WRITE/FLUSH with `orphan ownership ordinary inode profile`:
the present ownership profile excludes the larger executable and fast symlink
already in that disk. The receipt is
`build/prototypes/sdk49-empty-orphan-sdk48-native-v1/attempt-01/result.json`
(`489c152853181db8d2022eaf254c5f5a9f6d782ecf0c141eea0799865b20954b`).
This is a preserved native refusal, not completed recovery. The failed Notes
disk has an allocated orphan with an empty journal and remains dirty; offline
read-only e2fsck therefore reports cleanup still required. A bounded ownership
and directory-type extension is being qualified separately, retaining all
block alias, allocation, checksum and original-chain checks.

### Native UDP/ARP continuation matrix (accepted SDK34 path)

The isolated network continuation lane passes twenty actual QEMU guests: all
ten architectures in both Debug and Release, using frozen SDK34 user UDP
images and real Virtio NICs. Independent review checks each receipt/input/log
hash and every captured Ethernet frame, including guest HELLO IPv4/UDP checksums
and the ARP reply. Each run captures two guest frames and nineteen host frames;
the host submits eleven hostile frames before the ordinary two-process UDP
continuation completes. The initial premature timeout attempt is preserved.

Evidence is recorded in
`build/prototypes/sdk41-native-udp-arp-hostile-independent-v1/REVIEW.md`.
Submission and continuation do not prove that every hostile frame was processed.
This qualifies a frozen polling path; IRQs, TCP, IPv6, Linux socket semantics,
loss/reordering and the current private SDK combination remain open. It is not
a complete M6 or physical-platform result.

### Owned synchronous stat and shared entry capture (V14, predecessor checkpoint)

V14 integrates 17 reviewed additions/changes on the exact V13 foundations,
retaining 1,099 qualified source files. Linux stat-family dispatch now freezes
the saved frame, reads the MIPS O32 stack argument once when needed, copies the
pathname once, and consumes a move-only payload. Existing synchronous
relative/cwd/dirfd/direct/empty-path semantics and checked output copies remain.
The native runtime uses one persistent shared-entry coordinator for syscall
origin and the VFS continuation observer.

Ordinary and ASan/UBSan dispatcher runs each pass 71,875 checks across ten ABI
profiles. Ten dispatcher probes and twenty composed runtime/VFS objects compile
with freestanding/native-signal flags across all ten architectures, with checked
ELF identities and no dynamic static initialization. The composed x86_64 Debug
Kernel links through xmake and passes QEMU diagnostics. Shared/mounted-provider
regressions are inherited from the separately qualified exact composition;
these results do not execute a waiting stat syscall or mounted reclaim in a guest.

The predecessor checkpoint is
`build/prototypes/sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V14.json`
(`59444043bece0cdd55f1fd968d79e538c1a0ae22c6c56113fb12d8f323dde965`).
The final integration summary is
`build/prototypes/sdk49-stat-shared-composition-v1/FINAL_RESULT_V2.json`
(`c2a42a57ff967a6a5660252165501f983304ffce4aa117166b76a2435f979a6f`).
Failed harness/assembly attempts and the superseded review aggregate remain
preserved. The source install is checked byte for byte; its bounded checkpoint
completion does not reinstall source. V13 remains an immutable predecessor.

Pending VFS requests still need exact cancellation before exit, exec, teardown
and lease reuse. That fix is in a disjoint successor lane. Waiting stat dispatch,
retained deferred cwd/dirfd/process/credential context, signal restart and SMP
entry safety remain open. Accepted Kernel919/OS623/SDK41 and the unfrozen ABI48
declaration remain unchanged. V14 alone supplies no SDK export or OS consumer
result; the experimental V15 artifact consumer is recorded separately above.

### Read-only fresh recovery binding (V13, predecessor checkpoint)

V13 adds the independently reviewed fresh reclaim recovery binding and its two
tests to private main without changing any existing V12 source. All 220 formal
compiled dependencies byte-match the private composition. Independent plain and
ASan/UBSan controls verify exact Session reads/counters, bootstrap and complete
directory/table source drift, foreign reads, transfer/geometry restrictions,
readonly admission and stale/one-shot registration. Device WRITE/FLUSH is zero.

The binding derives its layout from actual media and validates the active
reclaim journal plus strict whole-home states. It grants no write or ordinary
mount authority and has no native runtime caller yet. Storage and the Session
remain exclusively borrowed for the binding lifetime; closing the Session first
invalidates revalidation but cannot quarantine an already-ready registration.
Writable empty-journal orphan recovery is frozen in a disjoint successor lane
against the pinned V12 foundations and is under independent review. It passes
ordinary/ASan/UBSan memory-device fault controls, 62 actual read-only e2fsck checks
and all ten freestanding profiles; no mounted writer or guest result is claimed.
Active reclaim completion, startup routing,
Virtio cuts/restarts and default Notes/Files guest flows remain open.

The integration receipt is
`build/prototypes/sdk49-readonly-binding-integration-v1/RESULT.json`
(`5d5c24b48bfd94d48816cf2db220be7ffe502697fe7bec80e16d6ca1ccb9247d`).
The predecessor checkpoint is
`build/prototypes/sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V13.json`
(`b8c540e4f4a1336a3d4e49e0524eb91d6e479c9509474754f70df967c982f265`);
follow `COLD_RECOVERY_NEXT_INTEGRATION_V2.md` in that lane. V12 remains an
immutable predecessor checkpoint. No SDK49 freeze, export or promotion follows.

### Mounted orphan reclaim and VFS admission (V12, predecessor checkpoint)

The private Kernel integrates five mounted/planner headers and two tests from
formal attempt-10, following independent review. Mounted unlink/replacement
uses the same Owner's namespace prepare/commit/checkpoint, preserves old-fd
reads and clone holds, and defers final-reference cleanup during admitted I/O.
Only durable reclaim retires an unexposed node slot and permits inode/address
reuse. Mount/Session/generation and exclusive off-stack workspace identities
are checked; sticky raw exposure blocks reclaim. Fifteen append-only rename
names preserve previously borrowed views, with capacity refusal before I/O.

Formal plain and ASan/UBSan runs cover 45 write cuts, 16 FLUSH failures and
three read failures. Ten freestanding mount instantiations preserve the full
architecture matrix. Independent controls add non-last-link aliases, detached
clones, actual host-thread release during namespace/read I/O, generation drift
and workspace exclusion. Twenty-two commands and ten e2fsck images pass. This
is hosted execution of actual VFS/provider/device paths, not Kernel SMP.

The create planner consumes the canonical free directory record left by unlink;
first-data publication preserves the checked source generation. Eight existing
planner/replay suites pass plain and ASan/UBSan, with independent hostile and
counterfactual controls. The separate VFS/legacy integration includes checked
release errors, owned lookup/create transfers and all 17 VFS provider callback
scopes without a global spinlock spanning I/O. Legacy quarantine preserves
ordinary reads while refusing writes/sync. Synchronous contention still returns
busy/null; full POSIX blocking is open. The frozen native statx continuation
prototype has not been integrated into the trap/service/signal lifecycle.

Integration checks every formal dependency and matches 1,085 archived sources
from the standalone composition. Its forced x86_64 Debug xmake archive build,
fresh mounted-template probe and actual standalone QEMU diagnostic boot pass.
The wrapper's earlier emulator lookup failure is retained. Existing guest
diagnostics do not execute the new mounted reclaim path. SDK49 OS consumer,
writable cold recovery, Virtio power-failure/restart and repeated UID 1000
default Notes/Files English workflows remain open.

The aggregate is
`build/prototypes/sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V12.json`;
the next contract is
`build/prototypes/sdk49-notes-replacement-private-v1/RECLAIM_RUNTIME_NEXT_INTEGRATION_V6.md`.
Retained storage must remain exclusively owned and immutable; simultaneous
retained-source/media mutation is outside the historical proof contract.
SDK49 stays ABI48, unfrozen/unexported/unpromoted. Full M0-M12 is incomplete;
physical M11 and manual M12 remain user-deferred.

### Further isolated recovery and native capture preparations

The new fresh read-only reclaim binding derives its layout and metadata domain
from actual Session media and a strict declared-before overlay. It no longer
requires an externally supplied binding. Formal attempt-04 passes plain and
ASan/UBSan plus ten freestanding profiles: each hosted mode records 32 accepts,
54 barrier rejects, 38 hostile/foreign-home controls, 12 read failures and
88,360 unlocked diagnostic callbacks. It performs no external WRITE/FLUSH.
Large storage is noncopyable and remains exclusively owned, immutable, disjoint
and off-stack. Independent review and the V13 private addition now pass; no writable
recovery or ordinary mount authority is supplied. Its freeze is
`build/prototypes/sdk49-reclaim-recovery-binding-successor-v1/FROZEN_READONLY_BINDING_V1.json`.
The reviewed cold design separately records 5 gates and 19 controls; follow
`build/prototypes/sdk49-notes-replacement-private-v1/COLD_RECOVERY_NEXT_INTEGRATION_V1.md`.

The isolated shared authenticated backend capture successor makes the copied
native runtime invoke one coordinator for restart-origin and ordinary VFS
observers. Move-only capabilities and per-lease-epoch claims reject replay and
changed owners/views. Six hosted runs pass 362 shared-capture, 684 continuation
and 258 runtime-origin checks per mode. Eighty ten-profile objects include forty
with freestanding Kernel/native-signal flags; retained restart logic remains
byte-identical. Its freeze is
`build/prototypes/sdk49-vfs-shared-owned-capture-prototype-v1/FROZEN_SHARED_CAPTURE_V1.json`.
Main integration, Linux statx waiting dispatch, teardown/signal policy and actual
native trap/SDK/guest execution remain open.

M0 admission machinery now pins reviewed clause/unit indexes and maps each unit
through matching requirement levels and planned tests for every applicable
architecture. Source-pinned references require archive files, and passing M0
requires their actual hashes checked under an explicit source root. Forty ledger
tests pass; four complete reviewed source universes remain absent, so `gate-m0`
continues to fail. An explicit-input draft generator records ten unqualified
Linux ABI profiles, 90 selected syscall names, 670 numbered entries and 110 errno
values from the Kernel's bootstrap model manifest. This is partial model data,
not a complete ABI inventory or execution qualification. Receipts are under
`build/prototypes/m0-inventory-coverage-v1/evidence/attempt-02/` and
`build/prototypes/m0-linux-abi-draft-v1/evidence/attempt-02/`.

Independent M0 review checked 132 controls and found that the standalone ABI
draft generator silently accepted duplicate OS architecture rows. The repair
rejects duplicate identifiers before selecting the exact ten-profile set,
including identical duplicates and conflicting rows in either input position.
Five new tests are part of `xmake plan-check`; all 57 plan-check tests pass.
The exact independent conflicting-i386 reproducer now fails without publishing
an output, and the clean draft remains byte-equivalent. Frozen qualification is
`build/prototypes/m0-abi-duplicate-admission-v1/evidence/attempt-01/result.json`
(`fe8a26042e745b82ee7cbf1f9984a3135265221c7f5ad692c7294ad7f7e62611`).
This fixes draft input admission; the four full reviewed source indexes and
native ABI qualification remain open.

### Same-owner orphan publication and checkpoint (V11, predecessor checkpoint)

Six qualified source/test files integrate private reclaim publication/checkpoint
and an owner-bound lifetime claim on the original record/dispatch serial.
Public retry, acknowledgement, retain and scheduler rollback cannot undo the
claim. No lifetime spinlock spans I/O. The original cache/pins/generations,
transaction and exact same-Session counters are rechecked around each operation.
Uncertainty quarantines the owner and retains the cleanup obligation.

Publication writes actual descriptor/payload/end, commit and active journal head
with four flushes. Fresh device capture reconstructs every original before/after
home, released mapping and canonical journal byte. Home checkpoint writes the
inode tombstone, allocation metadata and superblock in order, with flushes and
exact expected home-mask readbacks. A fresh all-after capture precedes journal
cleanup; the empty sequence is parsed-next + 1. Final homes/head readback precedes
canonical publication, drainage and private completion of the original claim.
The current obligation is explicitly cleared and rearm preserves serial history.

Three memory-device successes, 45 torn-write failures, 16 before/after-effect
flush failures, eight read failures and seven hostile controls pass plain and
ASan/UBSan, together with preparation/namespace regressions. Ten fresh objects
preserve all profiles. Independent plain and ASan/UBSan each pass 16 rejects,
three accepts, four counter boundaries, three home-mask controls and 3,852
reentrant lifecycle callbacks. A second independent plain/ASan/UBSan review
also rejects stale/failed scheduler rollback, wrong Owner authority, counter
drift/exhaustion and coherent alternate journal history accepted by the cold
verifier. Three suites pass after byte-exact integration.
An isolated x86_64 Debug xmake forced build and selected-compiler probe pass;
the production archive does not instantiate the private writer methods.

Exclusive immutable caller storage remains a mandatory gate: coherent mutation
of both unrelated media bytes and their retained original table is accepted by
an explicitly excluded dual-alias control. Device-only drift is rejected and
target homes/journal stay privately bound. Actual mount identity and exclusive
Session/storage admission remain runtime work; no whole-volume authentication
against simultaneous original-storage and media mutation is claimed.

The isolated VFS release-error successor reproduces the predecessor's false
success on intermediate cleanup failure, then passes eight suites plain and
ASan/UBSan plus 30 ten-profile objects. Use final attempt-02; attempt-01 retains
the corrected unspecified evaluation-order defect. Legacy ext4 ownership is
implemented in an unfrozen successor under qualification. Neither VFS candidate
is integrated here. The global VFS spinlock across provider I/O, mounted reuse,
writable cold recovery, Virtio restart and repeated UID 1000 default Notes/Files
guest workflows remain open.

V11 is private host publication/checkpoint/acknowledgement, not mounted runtime
support. Follow
`build/prototypes/sdk49-notes-replacement-private-v1/RECLAIM_RUNTIME_NEXT_INTEGRATION_V5.md`.
SDK49 stays ABI48, unfrozen/unexported/unpromoted. Full M0-M12 remains incomplete;
physical M11 and manual M12 remain user-deferred.

### Same-owner orphan preparation (V10, predecessor checkpoint)

The private Kernel integrates shared empty-journal chain capture, clean cache
retirement, exact-head lifetime scheduling and private Owner preparation.
Sixteen source/test files moved byte-exact from qualified successors. Tests
execute a real namespace prepare/commit/checkpoint on a memory device, then
prepare cleanup through the same writable Session and canonical cache. No
mounted method calls cleanup yet; preparation performs no new WRITE/FLUSH,
allocation release or ticket acknowledgement. Public commit/checkpoint,
pin/prepare, discard/rearm and close reject the new private prepared phase.

Preparation binds the original namespace checkpoint, complete orphan head and
mapping, actual dispatched ticket, raw bitmap/table/directory observations and
resident canonical before bytes. It retires clean released-block cache
identities only after whole preflight, preserving Session and transaction/slot
generation history. Exhausted cache generations remain exhausted. A second
whole-source reread/replan checks the staged transaction. Five accepts, seven
preflight rejects, six hostile rejects and eight read faults pass plain and
ASan/UBSan, including empty/data-bearing unlink, replacement, cache hits/misses,
physical partition origin 37, retained work, source/cache drift and exhaustion.
Independent controls also reject a nonhead ticket and a corrupted nonzero hold
before I/O. Uncertain preparation quarantines the owner and retains cleanup.

An executed failure exposed a mutable Ticket-reference alias: a transport
callback could retry/re-dispatch and replace the caller's ticket before later
checks. The fixed method copies the original Ticket at entry and rejects that
case. Failed source/compile/test attempts remain preserved. The earlier
copyable inode Lease defect is already repaired by the V2 move-only interface;
Ticket copies instead represent dispatch identity and still need worker
serialization at writable publication.

The shared borrowed capture retains the readonly wrapper's acquisition/closure
contract and counts actual bootstrap reads against the original completed
READ/WRITE/FLUSH baseline. Four host suites pass plain and ASan/UBSan; ten fresh
objects instantiate both wrapper and borrowed helper. Closed/reacquired owner
tests preserve the new Session, and borrowed destruction never closes its
owner. Counter exhaustion is explicitly whitebox model coverage. Cache
retirement passes 65 direct checks and the existing 320-check regression,
including a subsequent fresh READ after simulated physical-block reuse.
Exact-head scheduling retains existing dispatch behavior; independent host
threads dispatch once per eight contenders across 32 rounds and preserve a
newer dispatch when an older callback fails. TSan failed during environment
startup and is not counted as a pass; Kernel SMP is not established.

Eleven integrated host suites and 30 fresh freestanding objects across all ten
profiles pass. Four independently rebuilt composed suites pass ASan/UBSan.
An x86_64 Debug standalone xmake `-r` build passes, with cache compilation still
reported; four fresh explicit probes use its selected compiler. The direct
cache test probe alone uses test-only private access. Its initially omitted
flag and the corrected successor are retained. No new SDK49 OS consumer,
Virtio workload or default Notes/Files guest workflow has run.

Unreviewed VFS handoff edits were preserved in a named snapshot and the V9
working baseline restored. A separate retained-identity successor is still
under review for lock ordering, legacy provider compatibility and raw identity
exposure; V10 does not integrate it or claim mounted node retirement safety.
Same-Session exclusivity, actual mount identity and serialization of lifetime
retry/acknowledgement with publication remain mandatory. A sampled zero/one
READ delta cannot identify which concurrent caller performed that read.

The V10 aggregate binds 21 new receipt entries, 30 current feature header pins
and 2,368 additional artifact hash checks. The next contract is
`build/prototypes/sdk49-notes-replacement-private-v1/RECLAIM_RUNTIME_NEXT_INTEGRATION_V4.md`:
complete retained VFS handoff, original live publication seal, durable reclaim
writer/checkpoint and mounted unlink/replace before actual inode/block reuse.
Physical M11 and manual M12 remain user-deferred. SDK49 remains ABI48,
unfrozen/unexported/unpromoted; full M0-M12 remains incomplete.

### Reclaim foundation (V9, predecessor checkpoint)

The private Kernel now integrates the reviewed four/five-home reclaim journal,
reversible witness, complete semantic cold verifier, read-only capture through
an existing BlockSessions session, and dispatched lifetime-ticket validation.
The 15 moved source/test files are byte-exact with their qualified inputs;
five executable host suites pass against the integrated tree. No mounted
cleanup method calls these foundations yet. `orphan_cleanup_pending` continues
to bar ordinary pin, prepare, rearm and close.

The cold verifier derives the chain from complete observations, reconstructs
declared-before homes, repeats strict bootstrap and global directory/ownership
planning, and compares canonical records and allowed whole-home states. It
admits 26 states, rejects 54 durability-barrier states and 45 hostile inputs.
Independent review reproduced a forged `layout.first_sector` acceptance in V1;
V2 requires partition-relative sector zero and rejects both forged fixtures.
V1 and its original evidence remain preserved. Three coherent all-after
alternate-history cases remain accepted as declared history; CRCs do not
authenticate overwritten historical bytes or replace a live publication seal.

The new capture borrows the existing session, retains the complete active
journal, actual bitmap blocks, initialized tables and every mapped directory,
then rereads every retained whole block. It checks identity and relative READ,
WRITE and FLUSH counters, including sessions with earlier completed writes.
Twenty accepts, 32 barrier rejects, 14 read faults, 14 byte-drift rejects and
eight counter/binding rejects pass. Independent host/sanitizer review rejects
78 binding/metadata mutations and 41 retained-block mutations. Tests use memory
devices at physical partition origin 37; capture performs no WRITE/FLUSH.
Raw alias exclusion and exclusive large caller storage remain owner obligations.
Actual raw INODE_UNINIT bitmap tails are byte-compared even where allocation
semantics ignore them. No cache epoch or writable cleanup authority follows.

Ticket validation checks private record and dispatch serials, expected mounted
identity, dispatched state and all four hold counts individually. Plain and
ASan/UBSan tests cover ten accepts and 25 rejects; existing VFS lifetime
regressions pass. Validation proves its instant only: a cleanup worker still
needs serialization and a recheck before publication/allocation writes.

The integrated journal/cold/capture/lifetime probes compile into 40 fresh
freestanding ELF objects across all ten profiles. An x86_64 Debug standalone
xmake build with `-r` passes; xmake still reports cache compilation. Its archive
does not instantiate these foundations, so four explicit fresh compilations
with the selected standalone compiler supply that gate. No new SDK49 OS
consumer, Virtio workload or mounted default Notes/Files workflow has run.

The V9 aggregate binds 20 new receipt entries, 28 current feature headers and
1,651 additional artifact hash checks. Physical M11 and manual M12 remain
user-deferred. The next contract is
`build/prototypes/sdk49-notes-replacement-private-v1/RECLAIM_RUNTIME_NEXT_INTEGRATION_V3.md`:
same-owner empty-journal capture, canonical cache retirement, original live
publication seal, actual ticket binding, durable writer/checkpoint and mounted
unlink/replace remain required before inode/block reuse. SDK49 is still ABI48,
unfrozen/unexported/unpromoted; full M0-M12 remains incomplete.

### Earlier private checkpoints


Default Notes now includes inode identity in its advisory destination recheck.
Plain and ASan/UBSan hosted lanes pass 41 cases each, including a competitor
with the same mode, size, owner and link count but a different inode. The
unchanged predecessor negative control overwrites that competitor. Ordinary
rename still cannot atomically compare Notes' earlier user-space observation.

The pure namespace planner constructs up to five deduplicated before/after
homes for same-parent replacement or unlink. It checks names, inode generations,
checksums, allocation bits and bounded extents, preserves unrelated inode slots
and directory records, and supports checked same-name and different-name same-inode no-ops. Last-link
removal publishes a zero-link allocated orphan only from an independently
checked empty prior orphan chain. It does not reclaim or free allocation.
The empty-file extension covers SDK46-created empty temporary files, empty
replacement and unlink. Hosted, ASan/UBSan and ten freestanding object profiles
pass; these are model results and do not enable mounted removal.

A pure replay-family preflight derives roles from the bounded metadata domain
and independently checked directory ownership. It explicitly retains ambiguous
rename/namespace candidates, requires a separate semantic decision for every
candidate, and rejects recognized invalid transitions even if another candidate
accepts. Source review found that the first model guessed allocation/create home
order incorrectly. The corrected classifier follows the actual canonical
planners: bitmap/descriptors/superblock/table for allocation, and deduplicated
tables/inode bitmap/descriptors/superblock/directory for create. Corrected
hosted, ASan/UBSan and ten-profile object checks pass; a separate regression
uses actual Create/FirstData/NextData planner output on pinned 32 MiB images.
The old model receipt remains predecessor evidence. The current
mounted recovery dispatcher is unchanged; the helper supplies no semantic
payload proof, device/session authority or permission to replay.

Pure JBD2 record preparation calls the canonical namespace planner and generates
checked descriptor, escaped payload, commit, journal head and end-marker images.
The generated records round-trip through the existing JBD2 parser, preserve
canonical two-to-five-home order and accept checksum-v3 with or without the
optional revoke flag. Models cover five distinct homes, sequence limits,
same-inode no-op, CRC failures and rejection before output publication;
ASan/UBSan and ten freestanding object profiles pass. This is journal format
preparation, not a writer, checkpoint or cold-replay implementation. The first
two attempts incorrectly required the optional revoke flag; the third used a
fixture dirent without enough alias space. All failed attempts are retained.

The legacy pure namespace replay verifier parses the supplied JBD2 transaction and
compares every record and participant home with the canonical journal and
before/after images. It passes 144 complete home mixtures and 76 invalid cases,
ASan/UBSan and ten architecture objects. Its result requires an independently
checked old source and empty journal head; it provides no cold all-after
historical inference, replay authority or device/session capability.

A separate read-only orphan-chain validator admits up to eight supplied,
allocated zero-link regular inodes, checking exact chain order, generations,
checksums, bitmap bits and inline extents. Empty and data-bearing chains and
16 negative cases pass hosted, sanitizer and ten-profile object checks. The
ordinary pathname decoder still rejects those zero-link inodes. This is an
image proof; global ownership, live descriptor references and disk provenance
remain separate obligations. It is not wired into cold recovery or reclaim.

A separate durable journal planner now reserves descriptor bytes 128..1019
for a versioned complete original-byte witness after the final JBD2 tag. It
records actual old inode fields, removed dirents and changed padding as sorted,
maximal undo runs with whole-preimage CRCs. Capacity exhaustion rejects before
I/O with no witness-free fallback. The cold byte verifier parses actual records,
restores escaped magic, reconstructs whole preimages, reruns the canonical
namespace/durable-journal planners and requires each observed home to equal
its complete before or after image. It uses no external old snapshot or guessed
historical timestamps. All-after identity is supplied by the durable witness.
Its 176 home mixtures, 251 invalid cases, old timestamp/version carry, escaped
payload and oversize-witness rejection pass plain, ASan/UBSan and ten objects.
An independently authored suite passes 52 mixtures and 25 hostile cases,
including a two-home synthetic shared-table view; that fixture does not prove
whole-volume ownership or mounted directory provenance.

The private canonical owner now prepares and commits namespace journal images
through the same session/cache seal as other transactions. Its writer publishes
descriptor/witness/payload/end, then commit, then active head, with four ordered
FLUSHes and no home writes. The four-home replacement fixture passes before/
after failures at eight WRITEs and four FLUSHes, plus six partial head writes;
uncertain publication quarantines the owner. Hosted, ASan/UBSan and ten-object
writer lanes pass, together with five existing owned-operation regressions and
fresh mounted absent-target/no-op rename regressions against the current owner.
The original writer receipts predate namespace checkpoint integration and
retain their checkpoint-refusal test. No VFS replacement/remove method calls
this private writer. An independent owner-to-
cold model accepts actual published and simulated all-after bytes; a separate
89-state failure model accepts three complete durable transactions and rejects
86 incomplete logs. A failed commit report can still leave a complete log, so
recovery must inspect actual bytes. These are memory-device models, not boots.

The orphan-authorized read-only snapshot decoder reruns the complete supplied
chain proof and matches UUID/head/inode/generation before copying a bounded
mapping. Empty/data-bearing fixtures, 11 negatives, ordinary-path rejection,
ASan/UBSan and ten objects pass. It does not retain a file description or grant
I/O/free authority. An independent read-only before-overlay prototype admits
the original binding over reconstructed old homes and empty head, including
nonzero partition origin and half-block reads, while denying writes/FLUSH.
Hostile overlay tests show that ordinary binding success alone does not prove
the complete target set or correct old sequence; production must bind all old
bytes and the exact published head to the cold canonical result before sealing.
Those overlay prototypes preceded the owner-bound integration below.

Pinned e2fsprogs accepts the descriptor extension in seven scenarios and all
112 whole-home mixtures: 112 strict journal-only recoveries and 112 full fsck
recoveries, followed by 224 successful read-only fsck checks. Raw/debugfs checks
cover namespace, inode identity, allocation bits and surviving data; last-link
orphans are reclaimed by e2fsprogs. All 224 outputs agree after only documented
tool time/written-kilobyte/checksum and orphan-deletion-time normalization.
This is external tooling recovery, not Kernel reclaim, Linux kernel mounting,
Virtio or user ELF execution. The first lane's purported journal-only command
included `-f` and ran all fsck passes; it remains preserved as full-tooling
evidence. The corrected second lane checks that journal-only output has no
Pass 1 and full recovery reaches Pass 5. Failed normalization attempts are
also retained. The SDK49 V5 aggregate rehashes completed evidence and binds
current feature headers; its first audit's wrong mounted snapshot-root
assumption is retained, and the corrected successor passed.

The private mounted VFS now returns success when both names identify the same
ordinary regular inode, including same-name and hard-link aliases. Hosted
POSIX rename/renameat calls preserve disk images, timestamps, links, cached node
identity and mount epoch, issue no writes/FLUSHes, and perform no clock sample.
Missing source, trailing slash and denied parent credentials retain their
errors. The existing two journalled absent-target renames and restart regression
pass; ASan/UBSan and ten mounted-header objects pass. A narrow successor corrects
the test's former "no I/O" wording and explicitly checks zero clock calls;
it reuses the unchanged header's earlier ten-object receipt rather than claiming
another architecture build. Lookup may still read disk. This remains hosted
execution, not an actual-device or user ELF no-op acceptance lane.

Private owner/session-bound namespace cold admission and checkpoint are now
implemented. A bounded bootstrap reads the actual committed witness, reconstructs
all old homes and the exact empty old head, runs unchanged ordinary ext4 binding
through a read-only before overlay, and binds the complete overlay/history to
the canonical cold verifier. The same exclusive BlockSessions/MetadataBuffers
owner seals identity, partition/session/cache serials, participant slots and
generations. Preparation is read-only. Live checkpoint also compares the entire
fresh descriptor/witness, payloads, commit/end and old bytes with that owner's
successful original publication. A valid foreign history with identical head
and all after homes is rejected before any WRITE/FLUSH.

Checkpoint rechecks actual records and current homes, FLUSHes, writes only homes
still before in canonical order, FLUSHes those homes, cleans the journal head,
FLUSHes and verifies physical bytes. Every all-after case emits exactly one
head WRITE and two FLUSHes, with no home writes. Cleanup preserves the existing
`parsed.next_sequence + 1` reservation convention, matching all 224 frozen
Linux tooling outputs. Non-last links reach checkpointed; last-link removal
reaches `orphan_cleanup_pending`, retaining the recovery bit and allocated
inode/data and denying regular pin, prepare, rearm and close. It is not ordinary
mount or reuse availability. An empty journal after a failed cleanup write
still requires a separate orphan recovery path.

The root owner suite passes 112 cold home mixtures, seven live publication/
checkpoints, all-after trace checks, 54 WRITE/FLUSH/cut failures, eight selected
read failures and a live foreign-history rejection. Plain, ASan/UBSan (leak
checks disabled) and ten freestanding objects pass. Updated original writer
checks, five prior owned-operation regressions and mounted absent-target/no-op
rename plain/sanitizer/ten-object regressions pass. Independent owner execution
checks 112 mixtures, 63 hostile state/geometry mutations and 28 reader/second-
owner exclusions. Independent fault execution passes 108 cuts, exact target/
ordering prefixes and retry quarantine: 80 power-loss model images equal known
whole-home mixtures, four have a complete clean head and 24 partial-media
states are not admitted. Its latest plain/sanitizer successor compares both
endpoints directly with frozen Linux fixtures. These are memory-device tests,
not Virtio, Kernel boots or user ELF workflows.

A separate pure global orphan allocation validator scans all allocated inode
records, including reserved records and the journal, checks complete inode
tables and bitmaps, and requires exact unique ownership of every allocated
block. Filled/empty fixtures, 11 negatives, sanitizer and ten objects pass;
independent execution adds 23 hostile variants and the same ten profiles.
The pure head-reclaim planner reruns that proof, releases only checked inode/
data bits from one data allocation group, changes at most five home images,
stamps checksums/counters and advances the orphan head. Populated two-member
and empty-file models, eight negatives, sanitizer and ten objects pass. It
retains a checksummed nonzero free-slot marker and increased inode generation.
The preserved reclaim-to-create counterexample records the earlier all-zero
free-slot barrier. Checked marker consumption and exact create replay have now
been implemented as described below. No reclaim writer, runtime lifetime
authority or actual block/inode freeing is enabled; repeated Notes saves still
require those integrations.

The V6 aggregate binds 17 new receipts and 15 current feature headers, with
2,226 new artifact hash checks and 20 predecessor receipt rehashes. Independent
used source bytes are archived separately; two failed archive attempts caused
by an advancing review probe are retained. Completed V5 and all successful/
failed model predecessors remain unchanged. Runtime inode/generation keyed
file descriptions, mappings, I/O and pins, directory-reference retirement,
device-bound global ownership and durable reclaim/replay remain required before
VFS replacement/unlink, repeated Notes save and failed-save cleanup. SDK49 stays
unfrozen/unexported at ABI48; it has no complete standalone Kernel/OS consumer
matrix, actual-device namespace cuts or user ELF replacement acceptance. M0-M12
remains incomplete, and accepted Kernel919 / OS623 / SDK41 is unchanged. See
`build/prototypes/sdk49-notes-replacement-private-v1/NAMESPACE_RECOVERY_OWNER_IMPLEMENTATION_V1.md`
for the implemented state machine and remaining gates.

Checked private create now consumes either the legacy zero slot or an exact,
checksummed ORF1 free-slot record bound to inode number, filesystem UUID and
retained generation. It proves the selected free bit, clears all 256 record
bytes and fills the new allocated inode with that generation; the ORF1 marker
is absent afterward. Reclaim increments generation and create consumes it.
Create rejects UINT32_MAX before I/O, reserving one identity increment for
later retirement. This makes the checked creation mechanism accept previously
reclaimed slots; it does not execute reclamation or prove repeated save cycles.

Every new create descriptor carries a complete before-image undo witness for
all five/six homes, including the erased marker, parent ctime/mtime/version,
descriptor high-water state, allocation counts and directory slack/checksums.
The cold preview validates descriptor CRC/sequence/tags, reconstructs declared
whole preimages, reruns the canonical create planner and compares every target,
before/after/raw home and canonical witness encoding. Oversize preparation
rejects before publication; malformed private padding cannot fall back to the
legacy zero-generation inverse. Live owner checkpoint compares the original
head, descriptor/witness, payloads, commit and end before WRITE/FLUSH.

Plain and ASan/UBSan create-reuse models pass 48 legal persistence masks across
four retained generations, 208 barrier-invalid masks, 22 hostile/foreign-witness
cases, six invalid/exhausted-marker cases and 52 WRITE/FLUSH failure restarts.
All ten freestanding objects, shared/separate-table witness unit cases, legacy
witness-free replay and five existing owned-operation regressions pass. Strict
e2fsprogs journal-only recovery has no full-fsck Pass 1 and its recovered bytes
match the Kernel-completed image after documented tool/recovery bookkeeping;
read-only fsck checks pass. The fixture uses pure caller-image reclamation and
synthetic name removal; it is not a runtime reclaim or physical power-loss test.
The failed combined runner's extra rename-test argument is preserved; a named
successor finishes its unexecuted gates and reuses only individually passing
plain/sanitizer results. Earlier assertions incorrectly compared inactive
journal debris and foreign-history inactive descriptor bytes; failures remain.

Independent frozen create review covers legacy/recycled publications, legal
checkpoint combinations, repaired-CRC witness attacks and exact live foreign
history rejection. A coherent alternative overwritten ctime history can be
admitted once all homes already equal the final payload. CRC and undo bytes
prove a self-consistent declared transaction, not authenticated historical disk
provenance. Such cold acceptance is idempotent; live publication provenance is
stronger. Current create completion still rewrites admitted homes in its
existing table/allocation/directory order. Namespace all-after optimization is
separate. A fresh sanitizer/ten-object namespace-owner regression against the
changed owner retains all 112 mixtures, seven live cases, 54 failures, eight
read failures and foreign-history rejection.

The pure inode/generation lifetime table tracks descriptor, mapping, I/O and
pin holds, detached identities and scheduling after releasing its spinlock.
Independent review found that ordinary Lease copies falsely appeared to retain
a hold. The current fix deletes copying and move assignment, clears moved-from
state and requires explicit counted clone. Current host/VFS PathReference
models, ASan/UBSan and all ten objects pass; original V1 evidence is historical.
At the V7 checkpoint, the mounted provider still had unkeyed references and
unsupported remove. The V8 descriptor/I/O integration below supersedes that
reference gap; mapping and open/unlink race acceptance remain open.

A complete supplied-directory validator now checks all allocated directory
blocks, mapping/checksums, names/types, dot entries and duplicate names and
rejects any live name pointing to an orphan. Two positive and 13 negative
fixtures, ASan/UBSan and ten objects pass; independent execution adds three
positive and five negative cases. The composed pure directory-qualified head
reclaim planner reruns directory/ownership proof and existing allocation
planning against the same inputs; two successive populated-chain plans, one
empty plan and five rejects pass sanitizer/ten-object checks. Both exact
reviewed headers are copied into the private candidate. These results provide
no device/session/cache epoch, runtime-reference barrier or freeing authority.
Unused bitmap padding outside represented inode bits is not fully validated.

The V7 aggregate binds seven new completed receipts, 23 current feature headers,
1,029 artifact hash checks and all 37 predecessor receipts. It separately binds
the failed partial lane and its passing gates without changing its failure
status. SDK49 remains ABI48, unfrozen/unexported; mounted unlink/replace,
owner-bound durable reclaim, actual Virtio/restart and UID 1000 ELF Notes/Files
workflows, standalone SDK export and exact OS consumer matrix remain required.
Full M0-M12 stays incomplete. See
`build/prototypes/sdk49-notes-replacement-private-v1/CREATE_REUSE_IMPLEMENTATION_V1.md`
and `RECLAIM_RUNTIME_NEXT_INTEGRATION_V1.md` for current semantics and next gates.


The V8 private candidate integrates mount/session/inode/generation identities,
move-only VFS Node descriptor leases and per-operation I/O holds. Actual hosted
PathReference acquire/release, retained-node release during a read, quarantine
drainage, 512-slot exhaustion and checked create generation pass; mounted create,
rename and no-op regressions pass plain/ASan/UBSan with ten object profiles. The
provider lock stays outside device I/O. File mappings, last-link detachment,
post-unlink cloning, cache retirement and mounted remove/replace remain open;
the inherited VFS resolver's spinlock across provider callbacks needs separate
review. A durable create can precede later PathReference capacity failure.

Read-only cold orphan snapshot admission now acquires its own private session,
reads complete initialized tables/allocation bitmaps and every directory, and
rechecks actual whole blocks before admission and head planning. Ordinary
recovery binding remains fail-closed on orphan heads. Independent review
reproduced a bootstrap-to-snapshot gap in the first candidate: a checked journal
inode could change coherently before the complete table read. The current fix
retains original bootstrap reads, repeats strict checks on retained images,
and rejects both journal-mode and descriptor drift. Two accepted scenarios,
36 rejects and 13 read faults pass plain/ASan/UBSan and ten freestanding objects;
independent hostile and ten-profile instantiation lanes pass. These are memory
devices at physical partition origin 37, with no WRITE/FLUSH. The private session
is readonly and separate from the mounted owner's existing session; live cache
epoch and runtime freeing are not supplied. Caller storage is large and must
remain exclusive, disjoint from scratch and off the kernel stack.

A standalone x86_64 Debug xmake `okernel` archive build passes. Its source list
does not instantiate the changed mounted template, so a separate fresh explicit
freestanding instantiation also passes against the xmake-selected compiler.
This validates the standalone build and changed template, not SDK49 export,
the full twenty producer matrix, new OS consumers or guest execution.

An isolated reclaim JBD2/witness format candidate now passes four/five-home
reconstruction, 22 rejects, escape/commit/parser checks, ASan/UBSan and ten
objects. Its complete reversible witness binds old/new homes and released
physical blocks. The current V2 pin accurately labels it a candidate; V1's
premature reviewed label and receipts remain historical. Independent format
review, global semantic cold replay and owner-bound durable writer/checkpoint
are still required before integration or any inode/block reuse.

The V8 aggregate binds eight new receipts, 24 current feature headers and 681
new artifact hash checks; a supplementary source/compiler/log/object audit adds
1,319 checks. Existing V7 receipts and failed lanes remain unchanged. SDK49 is
still ABI48, unfrozen/unexported/unpromoted; M0-M12 remains incomplete. Follow
`build/prototypes/sdk49-notes-replacement-private-v1/RECLAIM_RUNTIME_NEXT_INTEGRATION_V2.md`
for the remaining cleanup and actual default Notes/Files acceptance gates.


| Receipt under `build/prototypes/` | SHA256 |
| --- | --- |
| `sdk49-notes-identity-private-v1/HOSTED_RESULT.json` | `e4e45c3ee01d420cfd7922a04ed4a65c3ef643ddc1b40370ac2d43263e0b1391` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-same-name-attempt-01/result.json` | `cc3581b12a9a560a977e181bdfaa33e0e3a1e40ddb035cc9a3c51d030f162a43` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-journal-attempt-06/result.json` | `9e48eeb0a79cd5add34df95dbff4683eaf1796f94c13402980f3202256c3b689` |
| `sdk49-notes-replacement-private-v1/evidence/replay-shape-attempt-02/result.json` | `0325162b5ff867f81e5a8b7e64dfdd588913166b3c63bb4ed889f5282824806d` |
| `sdk49-notes-replacement-private-v1/evidence/replay-shape-planner-outputs-attempt-01/result.json` | `2e967468e420b951e2be56227682d5e4653c5ce8b2648db7e64f1d3af7b1e144` |
| `sdk49-notes-replacement-private-v1/evidence/orphan-chain-attempt-01/result.json` | `5c7b5efb920a913319cc62d04b73e191f822ae48d422fa4271b372f16f2a31da` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-replay-attempt-01/result.json` | `a558f7ea17b8329afcecb78e121935e42f74d8159c9603a8d7f276669de4fa41` |
| `sdk49-notes-replacement-private-v1/evidence/mounted-rename-noop-attempt-01/result.json` | `adeb90c11a825842723954ee2ea77b5620461a819db45a3c2eb0efe8db8a3ec1` |
| `sdk49-notes-replacement-private-v1/evidence/mounted-rename-noop-clock-attempt-01/result.json` | `86dcc62a2c3a6c713e8847cd171457cdd7745b6156274785a13ac24d052ae94c` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V4.json` | `d4b8dbb009e4d5c6198961b6c1ce9e491f6ef1c6eb62f177c9e89423613edfd8` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-cold-attempt-01/result.json` | `ad3c19af8137a0f6c7afdf01dff3a8742d09eb7e18ab802a9c3f3b87071f7398` |
| `sdk49-notes-replacement-private-v1/evidence/orphan-access-attempt-02/result.json` | `e086d2107432a9aead2cddc0faf48cab308a66092c89250ab92b20c164204baa` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-writer-attempt-02/result.json` | `43ff48d446ff3df681629782c2433e501cbd29485c11bd77ef74c8280d607cba` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-writer-sanitized-attempt-02/result.json` | `53649ee7f5ca840a31ad03fd847b526b2828f69704a50a57b65e61d378a8c6bc` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-owner-regressions-attempt-01/result.json` | `d3f93f004decd3f03bd92f2ca51ea25d1ce56b7396b9fcd6c97edd5438878056` |
| `sdk49-notes-replacement-private-v1/evidence/mounted-rename-noop-owner-attempt-01/result.json` | `cde7cd2031fcee91669b34c8c1133e6d33c5c8fc57ad92fc1ad508d98f591e00` |
| `sdk49-cold-namespace-independent-review-v1/RESULT.json` | `7421ca71acaa111e7f9ac4a36e0c3453d936e373f4d246efb4ecdc7a111bf432` |
| `sdk49-namespace-owner-cold-independent-v1/RESULT.json` | `4c56dcd556a7912e41560b6550eb8a72024ee388edb0269701ee6e36fd2bda2d` |
| `sdk49-namespace-owner-cold-fault-independent-v1/RESULT.json` | `6fb1114ad4b52f3343a908c2806e9674a17cd94e15bacc618a4080900d45978f` |
| `sdk49-namespace-owner-regression-independent-audit-v1/RESULT.json` | `33d9ceaa512b63b6da1b5add1326b7e78e5999d6be0ee85fd21197ca9e7d5f91` |
| `sdk49-namespace-before-overlay-independent-v1/RESULT.json` | `8f8de479ee9ded46f2adf2f5372eb67b40be73b486124f6188f5bf4763974337` |
| `sdk49-durable-witness-linux-interop-v1/evidence/attempt-02/result.json` | `8b709464d2b5655c1990b7eac973c6e9adc3ae035975e246816d55a0b8b48c5a` |
| `sdk49-model-preparation-v5-independent-audit-v1/RESULT.json` | `59b404f631693b40fb797de68929a7360930bee94bc9a78fe65b929f0ea14c90` |
| `sdk49-durable-witness-linux-interop-v1/evidence/attempt-02/NORMALIZED_OUTPUT_AUDIT_attempt-03.json` | `7bb326dc51ab560f2a924a71757c5a5ca0e3336ebe719e07c29bcc844b184ef9` |
| `sdk49-namespace-before-overlay-hostile-independent-v1/RESULT.json` | `2a5cc1660b927ee8b5ba6fa4c51511fc3b0d0530754b0def04171c613f7f5d06` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V5.json` | `1a4788238b070cfcc79328ccf975bc85cf7f2921450aa17401c247a2acf0518e` |
| `sdk49-linux-interop-independent-review-v1/RESULT.json` | `d0ba9f1b49615f380c53d2a20e6ddaeafd4e0aa90f50e4f016649a59a12295f3` |
| `sdk49-namespace-cut-final-source-archive-v1/RESULT.json` | `aa557ade1ec4f68542d113e3c977a12cb4fac5f305ef97eda59249d850a62f53` |
| `sdk49-namespace-production-review-v1/SEQUENCE_AUDIT.json` | `6c40b8b3852abf9f72090d0a971a526f073ae6c5b0f4ece8ba6c98457e8ca19f` |
| `sdk49-namespace-production-review-v1/admission-attempt-03/RESULT.json` | `d136f04e97a8525db4a1a90f3c6cd82069a3c1b2c2ac13a8c51c405c14f105a8` |
| `sdk49-namespace-production-review-v1/cut-attempt-04/RESULT.json` | `421cfe62de97078766e333fb533534c8e50a111d04379b3cc751cb4da7ed29a5` |
| `sdk49-namespace-production-review-v1/cut-attempt-05/RESULT.json` | `91cc87a30040363b63ceff7d48b2239ccf4a3cbd4886ba41211c519260bc3587` |
| `sdk49-namespace-production-review-v1/live-seal-attempt-02/RESULT.json` | `19aaaa0d830a01fe697b734ff3dae7c561a20bb21712e7ff1ed2c3d64b45b1db` |
| `sdk49-namespace-production-review-v1/owner-attempt-01/RESULT.json` | `2349a83558b1d6f424fa578653b7ef1989ccf2c204194bd69f2441239c9c2bc8` |
| `sdk49-namespace-proof-source-archive-v3/RESULT.json` | `6444d97aac36259001a265b2c50f4686c6f1ab113e2c6c8d6162d3253b4e884f` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V6.json` | `4bb587bc3a1d0a23a882cb4dbbb7bd5d68f81ea223a59ee2a606c1b1b912ee2b` |
| `sdk49-notes-replacement-private-v1/evidence/mounted-rename-noop-owner-attempt-02/result.json` | `0d7749ada76dc34dbec17cde7f35e3c3a4bfbd2eaf3ed790674655d1f37de114` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-completion-attempt-05/result.json` | `143b55531e3bb8528503777ed2feab8930d1e7e9f78446b32025e87a8a7cbd06` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-completion-sanitized-attempt-02/result.json` | `c77323cc4f4655a62295db8d1566fa2df3baf11bb2a1c318224052dd068b8828` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-owner-regressions-attempt-02/result.json` | `c8086a03e73363407f891a26890db695afdcf88c7d88fa37790e5e5c635b1ef4` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-recovery-admission-attempt-03/result.json` | `f7d9ba60ab50c7d1bb84c5d2df1a0ea9739f0aebdc23ac6a4687be5993af58c1` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-recovery-admission-sanitized-attempt-03/result.json` | `d97bada0beabb08f1025ddba770c909a58d90bd673cccb96e9c600110aea966b` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-writer-checkpoint-attempt-01/result.json` | `6d53c3590b09e6f0dd72551a1a8fb16197fbdab13c838290d874b1324fb9f1cd` |
| `sdk49-notes-replacement-private-v1/evidence/orphan-ownership-attempt-02/result.json` | `59f4828106989e3cfeffbdf8dc483aab0d849ffe8d47ab50419fad9f09185035` |
| `sdk49-notes-replacement-private-v1/evidence/orphan-reclaim-attempt-01/result.json` | `672f538e27e9f646a5e44b982682f3a6116f0e4928afa42a0f3d9f9b24980f55` |
| `sdk49-orphan-ownership-independent-v1/evidence/attempt-01/result.json` | `3b18f50026b80e18902bf416b254f989ff60a5c607770a7c71df3d2eb6b15340` |
| `sdk49-directory-reference-independent-review-v1/result.json` | `6a8d06e57eabe6a8320740ddc9ca523163be12a6f9f637362ce60a0b7560b334` |
| `sdk49-namespace-production-review-v1/create-generation-witness-review-attempt-03/RESULT.json` | `5f2fe52096beebd0499deb71d4226c604fd989d4c6aa72306423eaca8e40b01e` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V7.json` | `6fded4b2e0796fbf22ccb33567bd9ee6e11f6e0a658076508e55fc26ce06eca1` |
| `sdk49-notes-replacement-private-v1/evidence/create-reuse-attempt-02/result.json` | `49afdf32b1a3d33c7d7119565e09c1a11f999b79ffba0e77f5925e7476085454` |
| `sdk49-notes-replacement-private-v1/evidence/create-reuse-completion-attempt-01/result.json` | `1a7f63f3851dd8dab19ea12a42b2a023fdddf0c64dff18bd3fc2cabc8c3cdd8f` |
| `sdk49-notes-replacement-private-v1/evidence/namespace-completion-create-reuse-regression-attempt-01/result.json` | `ae87a94ee56747557f80694c450e255db6a16c57e3dc00e8b4213a913338880a` |
| `sdk49-notes-replacement-private-v1/evidence/orphan-lifetime-attempt-02/result.json` | `d1b93bee09e64a6a020a4dd1b29ff7dcef01790a6d96151e1888e97edbecfa49` |
| `sdk49-orphan-directory-refs-successor-v1/evidence/attempt-01/result.json` | `6b59b520126421ddad9a1804d3755856883982104741652db4f7423131906c8c` |
| `sdk49-orphan-directory-refs-successor-v1/evidence/combined-attempt-01/result.json` | `fe831be0d8742cc84ddea45adb9c14c743d2df30be55be10b0392b351ce02ccb` |
| `sdk49-mounted-lifetime-integration-v1/RESULT.json` | `a1c14c4d30a1bbc9549872c60ba8d9c1ea95e981719cc77b00702ebc4491d8bd` |
| `sdk49-mounted-lifetime-standalone-v1/attempt-01/result.json` | `b96e4941d0186c64504791d711ec0a32be5151e922d9a8e258793bcaf5fba58c` |
| `sdk49-mounted-lifetime-standalone-v1/attempt-02/result.json` | `6b2ce51052ae0fc89293a6077e3a89407535b4d0fc5ec33099f9c00fac5ef863` |
| `sdk49-namespace-production-review-v1/mounted-lifetime-reference-candidate-v1/evidence/mounted-lifetime-attempt-02/result.json` | `d23a472187e47032f7c3ee365eea099f97a5f77e698a5b7d95bdd41fc61d15d8` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V8.json` | `07820bdc1dc1f7397999c7ed21c8cfde425587c573f0e28be3d6e59907237020` |
| `sdk49-orphan-device-snapshot-independent-v1/evidence-final-v1/result.json` | `3ced582763efbbf91e296a06be1c93e2d76113fa7cc27012c0d92270a9657670` |
| `sdk49-orphan-device-snapshot-independent-v1/evidence-original-v1/result.json` | `7d55ea861d7dd91abc6fa6a78548c7fcc1ffae841853bd848d0a284e55171dc9` |
| `sdk49-orphan-device-snapshot-integration-v1/RESULT.json` | `b7122c74aef49130445759776ef316eeba95908d3edbaf7b1741773823b7960e` |
| `sdk49-orphan-device-snapshot-v1/evidence/attempt-01/result.json` | `c79d5d442b08d99f98f70f62e885b1c8a893b142f2edc537e1fa3d6961fc7dd2` |
| `sdk49-orphan-snapshot-cross-independent-v1/attempt-01/result.json` | `ecd027987cac2ac29e2dbff5857f713450cc337869f39036e63edaa2f8f5847b` |
| `sdk49-progress-update-v4/BUILD_ARTIFACT_AUDIT.json` | `9e6d705a6aa97e311bbe06cc911b573a6504c7e0d13e92a9f4ab38ea1d8dd2ab` |
| `sdk49-reclaim-journal-witness-successor-v1/evidence/orphan-reclaim-journal-attempt-02/result.json` | `d7437fd5374fe21f929652647707b6a03c240fceea5284a44c500da1d606e354` |
| `sdk49-lifetime-ticket-successor-v2/evidence/attempt-01/result.json` | `17d389dff14533d6f6e1808db9fda5c251295280d7273b775b0dcb96f2470cdc` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V9.json` | `cef36d4b42287b278adb046376aa82df7a5d6d637b3e233962110eb8c86d0569` |
| `sdk49-progress-update-v5/AGGREGATE_RESULT.json` | `fcda73bdd9a02976da55ac543d4f3e2831a11e195e527111b50840bb497945a8` |
| `sdk49-reclaim-capture-design-review-v1/REVIEW.json` | `2f0209021db16b4736aec86e02e0909c09a5a96e54c28cbc73c36606e8097981` |
| `sdk49-reclaim-cold-state-identity-review-v1/attempt-01/result.json` | `b9fcc16ccc464dbda95e329709539ba19ea5c8e8ea1289d64f149fbf19d25591` |
| `sdk49-reclaim-cold-state-identity-review-v2/attempt-01/result.json` | `abde1d5f5236d3c00fddd83f78399a5653d4d8de464e7916cdc1280db0d62fb0` |
| `sdk49-reclaim-device-capture-independent-review-v1/attempt-01/result.json` | `9dfa746b2370a70bfdcda19c31dd2def6b62effe1387f55b0a12df463cc2736c` |
| `sdk49-reclaim-device-capture-v1/evidence/attempt-01/artifact_audit.json` | `efb4f1d39fe7523d9b1bec97c46060709d3a1ba0339c8e41992b06ab3314ca50` |
| `sdk49-reclaim-device-capture-v1/evidence/attempt-01/result.json` | `924219bdbc03585165dd536871fa2c3e0eb41699e664a340540fd7ddcef2fef1` |
| `sdk49-reclaim-foundation-independent-regression-v1/attempt-01/result.json` | `044cbaa534978c8ed1f5a13074eb21c2bb58bb85ef29c474a96c0412be0e31b4` |
| `sdk49-reclaim-foundation-independent-regression-v1/cross-attempt-01/result.json` | `27c9f7d032cdde6a8edb298b2fa2643846da3398fbd91de59fdee2a7a96674eb` |
| `sdk49-reclaim-foundation-integration-v1/RESULT.json` | `9e60059b151515ba713c68769104e05a92792beb91df302a9ffa22957fc2e54d` |
| `sdk49-reclaim-foundation-standalone-v1/attempt-01/result.json` | `6bb37913ba5d25191579424050e517296f12dcad98cc0d2e44c29fcfa81b0203` |
| `sdk49-reclaim-foundation-standalone-v1/attempt-02/result.json` | `92bf43d8f3bf4a836fa33d17b06a524e6daf32376b258478ed3cb6b3aaff8fb8` |
| `sdk49-reclaim-journal-linux-review-v1/attempt-04/result.json` | `ab9518730584e1ea1369614f6ccc939de1191c9f7c23e427134f31d6f6c63f50` |
| `sdk49-reclaim-journal-linux-review-v1/hostile-attempt-02/result.json` | `cb1dc6cb8f45770ca9a5c4d715f79ea6fcf97532e0d9a8b58eedf57e29a7ad12` |
| `sdk49-reclaim-journal-linux-review-v1/mutational-attempt-01/result.json` | `dd091f8d0302bde9cf873d818fb0961651a8732f65fcd20b471983d3cfade22d` |
| `sdk49-reclaim-owner-design-v1/RESULT_V2.json` | `f98a768638c8e4496857ba440f5619845b930fc3b3e8207280c0d39c5ebe8454` |
| `sdk49-reclaim-semantic-cold-successor-v1/evidence/attempt-01/result.json` | `cc4c85e084d3edd09caafe3a94512eeb7b6784d42b390c1e2f1cb39dcb7f0a37` |
| `sdk49-reclaim-semantic-cold-successor-v2/evidence/attempt-01/artifact_audit.json` | `c197a8c2f3d96bb235ff7b907c64ffd60d9fe7fefe5765e6e6fb9736b8be04e8` |
| `sdk49-reclaim-semantic-cold-successor-v2/evidence/attempt-01/result.json` | `bd462e02daf7f30e9ad4c7dbfcd296e9989a72f265b04279d22fcb13bd27fcb5` |

| `sdk49-cache-retirement-successor-v1/attempt-03/result.json` | `104e78563cdbefb45d6f0f6f8a161658fd0a91752c48cd4f333c9e826cd0a799` |
| `sdk49-lifetime-exact-scheduler-independent-review-v1/attempt-01/result.json` | `8ab5372e6c70f90907b3ef8d5834c7da47361e6d52522dafbc77ce25a2a100f9` |
| `sdk49-lifetime-exact-scheduler-successor-v1/evidence/attempt-01/result.json` | `9e6b896356554e1dd240b973c39b4e9f84ec0c2c08a67397b1f620ae34744745` |
| `sdk49-notes-replacement-private-v1/MODEL_PREPARATION_V10.json` | `c56e5eb9f1944ef6bc456dd977326d0cf8d86c69c5bee03346c7d99ef974cf12` |
| `sdk49-orphan-chain-capture-independent-review-v1/attempt-01/result.json` | `bad088ea74ced13536485794b3cccff0f88cac46849547c48aee95c2095e7fad` |
| `sdk49-orphan-chain-capture-qualification-v1/FINAL_VALIDATION.json` | `c176e21aec2fa3b7a78f544dc0e65a7c190ebf1df8c4e97fe123a29344e26046` |
| `sdk49-orphan-chain-capture-qualification-v1/evidence/attempt-01/artifact_audit.json` | `1d896e05a723f5939f360fc8c5220f729e70c4f93ee65f95da278ed243a8cc06` |
| `sdk49-orphan-chain-capture-qualification-v1/evidence/attempt-01/result.json` | `c49fd3621ee5221b1ffb73695279d62ef960a7f55393a1bbfa47a86dc26694d5` |
| `sdk49-orphan-owner-integrated-sanitizer-independent-v1/INTEGRATED_AUDIT.json` | `2f1eb03e0d46ffe17d7da5452ea6809f2b91a5de2dff8cae789573977888f19f` |
| `sdk49-orphan-owner-integrated-sanitizer-independent-v1/attempt-01/result.json` | `d942bfa718894f370a66ee2bf14018819859d934da21088d2ccbd20cf314c6c7` |
| `sdk49-orphan-owner-preparation-independent-review-v1/sanitized-attempt-02/result.json` | `54d4b21462c05b8c2b9beaf9b2d99f03c724f4881602963f94db3e59dc5545f7` |
| `sdk49-orphan-owner-preparation-independent-review-v2/hostile-attempt-01/result.json` | `bb171641193ad80caf8ed90086d48eef4b5783e243ca6c20c9f2597e2382a91d` |
| `sdk49-orphan-owner-preparation-independent-review-v3/AUDIT_V3.json` | `e3e9f5fa1842e1e55085007f5e49fbeb98138263ca9b3f80a43343ec222471bc` |
| `sdk49-orphan-owner-preparation-integrated-regression-v1/FINAL_VALIDATION.json` | `efc16c3454f9287b68809ce33da3e6c194609bac1e3313265665ad25663f888f` |
| `sdk49-orphan-owner-preparation-integrated-regression-v1/evidence/attempt-02/artifact_audit.json` | `95bed1b6bce520bbc587c06c40ca65ca9d0acc9d108f8ea706a64531c985dd73` |
| `sdk49-orphan-owner-preparation-integrated-regression-v1/evidence/attempt-02/result.json` | `429724566adffb6e7e5b2603065c1d03ae64f5e66aa7a1f7414edebe3021012a` |
| `sdk49-orphan-owner-preparation-integration-v1/RESULT.json` | `c3c8886ebe1ac1b3f9b5690ac1b21c2c8028f4b9040d5860e2c9b0fa516d130c` |
| `sdk49-orphan-owner-preparation-regression-harness-review-v1/RESULT.json` | `009c3dc071f157631c4b40ec059d7409b497978290bab715fcba64ad8a699498` |
| `sdk49-orphan-owner-preparation-standalone-v1/attempt-01/result.json` | `1bc70dde39eaa3e93aab2c7a5727ca1bc83c3665c1b24e4348de619862d3eac3` |
| `sdk49-orphan-owner-preparation-standalone-v1/attempt-03/result.json` | `52042d84ae3d3b5977519e9920bcf52ffcfcae0f9efb6ba58b841725ca359617` |
| `sdk49-orphan-publication-seal-design-v1/RESULT.json` | `6d665854105db5c94224a1236c63afdecaacbe8835e2b40689a385625f8b9318` |
| `sdk49-orphan-owner-publication-successor-v1/evidence/attempt-01/result.json` | `b7a62ce1251775613de7179de6353246e18408ae706436c599dba47025d20969` |
| `sdk49-orphan-owner-publication-independent-v1/evidence/attempt-01/result.json` | `74136fecdd02956ec00692425584976ec5eec0bf4242e872559ac75cb3cbee7f` |
| `sdk49-orphan-owner-publication-independent-v1/REVIEW_RESULT.json` | `9f827c1337aa60c7e2c9eee0b005e9fb8fd015947d79161081cb72f07627b954` |
| `sdk49-orphan-publication-standalone-v1/RESULT.json` | `c7d72e9c231ec056bffe3719cc2b24cca5541ef33c5de2b6a72719af7d913ebf` |
| `sdk49-orphan-owner-publication-integration-v1/RESULT.json` | `a11cfe19d5416def7bfaad1898f7a925168e9f3df3bfe4538a9967f6a6168ff5` |
| `sdk49-orphan-owner-publication-integrated-regression-v1/RESULT.json` | `c831a0d8baaafbedabd90393d33969a4f3db12e9a3a44bd06f3d367919ac2503` |
| `sdk49-owner-publication-independent-hostile-v1/evidence/attempt-01/result.json` | `19ebc76bbddaab6932fbb1cf6481da06e62c2e6a569d825d504da9fc2831ce31` |
| `sdk49-vfs-release-error-successor-v1/evidence/attempt-02/result.json` | `f16676c871ef3c20ed1681c747c1326fee92213b2fe72711aac0e841ba393646` |
| `sdk49-orphan-owner-preparation-successor-v1/evidence/attempt-01/result.json` | `ca2503425eace1ce263735324f3bea237549b98b17a3d7cb6df63433753bd298` |
| `sdk49-vfs-baseline-restoration-v1/RESULT.json` | `a877662c6f659d543848a83c1fb5dc3847816ef1ee4c70229cbc2e3f79b42db3` |

## Next initialized file-data block (SDK48, private qualification complete)

The accepted snapshot remains **Kernel919 / OS623 / SDK41**. The newly frozen,
unpromoted SDK48 candidate contains **Kernel974 / OS624**, 1,598 source files,
C++ ABI **48** and unchanged UAPI **0.7.0**. M0-M12 remains incomplete.

The mounted ext4 subset can allocate one next initialized 1 KiB block after an
aligned 1-15-block regular-file prefix. It preserves the old data, initializes
the complete new block including gap and tail, checks unique block ownership,
extends or coalesces at most four inline extents, and increments the complete
64-bit inode version. Capacity, ownership and unsupported shapes fail before
write/FLUSH. The owner seals ordered data with the journal and metadata homes,
flushes data before publication, and allocation homes before the inode home.

Recovery uses exact first/next allocation policies. An old inode home supplies
its actual mapping and timestamps for a unique complete transition proof.
When all four homes already equal their journal payloads, recovery checks the
complete final view and a separate 128-allocated-record global ownership scan,
including reserved records. It only flushes existing homes and clears and flushes
the journal: one write/two FLUSHes in mounted retain-dirty mode, no home writes.
It cannot identify a unique historical target when valid siblings share the
inode table. That historical limit is explicit in the recovery resolution.

Final hosted owner/mounted, first/next replay, ownership, ABI and legacy gates
pass, with separate ASan/UBSan and ten-profile freestanding evidence. Both
replay models now cover 24 restart cuts, including six all-after cleanup cuts;
the mounted owner includes two sets of 47 restart checks and same-table siblings.
Independent e2fsprogs replay comparisons and read-only fsck pass. The unchanged
OS624 tooling inventory passes 708 tests. These are hosted/model results;
they do not establish device transactions or user ELF execution.

The exact twenty producer/OS-only consumer builds pass: all ten architectures
in Debug and Release, with SDK48 artifacts consumed by an OS-only build. Ten
separate standalone Debug Kernel QEMU boots pass. A read-only build artifact audit
checks the frozen sources, exact matrix rows, SDK artifacts, consumer outputs
and standalone boot binding. Its root-authored successor adapts the earlier
independently authored SDK47 audit; it is not a new independent build audit. The interim four-row matrix remained incomplete;
the final twenty-row receipt supplies the build result.

A private OS625 integration image built against the exact final x86_64 Debug
SDK passes two actual UID 1000 native ELF boots: create and independent QEMU
restart. The child writes one aligned 1024-byte block, then a second block with
a seven-byte zero gap, fsyncs the file and directory, and verifies the 1071-byte
file after restart. The serial logs show child exit and PID 1 reaping. An
independent read-only audit matches the archive's init/probe ELF bytes, the
guarded ext4 snapshots and CRC32C, and confirms exactly one new inode (14) and
two new blocks (535, 596), including 977 zero tail bytes. Both snapshots pass
`e2fsck -fn`. The post-boot ext4 `needs_recovery` bit remains set, so that
read-only check skips journal replay; these boots do not qualify interrupted
recovery or physical power loss. The earlier syntax preflight against SDK47
remains only predecessor evidence, not ABI48 runtime evidence.

The actual Virtio mounted-service campaign now passes 375 QEMU boots: two
variants, six controls, 184 fault/restart pairs and one old-block-alias rejection.
Each variant measures 14 writes and nine FLUSHes for next-block allocation, then
injects before/after error and cut modes at all 23 operations. Target-only and
same-inode-table sibling layouts both recover; the alias attempt leaves disk
unchanged with zero writes/FLUSHes during attempted pwrite. This executes POSIX
service code in Kernel context and does not execute a user ELF.

An independently authored read-only audit rehashes 2,720 campaign artifacts,
194 SDK artifacts and 1,598 frozen sources, inspects all 375 boot records, and
performs 184 fresh read-only fsck checks and 72 e2fsprogs journal replays on
temporary copies. A completed V4 audit successor additionally checks sector and transfer length
for every one of the 184 cuts against its successful baseline.
Both explicit all-after F8 cuts show one journal-head write
and two FLUSHes, zero home writes. A separate root-authored raw JBD2/CRC audit
confirms the same no-home cleanup for all 16 live all-after cuts. No audit
rebuilds or boots the guest again.

The private SDK48 qualification summary binds these results to the completed
twenty-build matrix, ten standalone boots, two UID 1000 boots and 708 hosted OS
tests. The candidate is still unpromoted. Evidence limitations remain explicit:
the campaign did not record QEMU exit codes, and reused 72 offline fsck log
names, overwriting their first outputs. Final logs, command metadata, replay
images and fresh independent checks are verified; overwritten outputs cannot
be restored or claimed preserved. Both failed smoke receipts, failed independent
audit attempts and failed root all-after audit drivers remain retained. The
failed smoke lanes do not contain complete original runtime-driver snapshots.
Actual user fault recovery, physical power loss and SMP are not qualified.

The ambiguous-sibling and unrelated-block-alias failures remain retained.
The first readiness audit failed because its OS profile expectation was four
while the unchanged artifact consumer supports ten; a named successor corrected
that audit expectation and passed. Earlier inherited preservation deviations
remain documented in SDK47. No failed or preliminary lane becomes a final pass.

Replacement rename, failed-save unlink/orphan cleanup, inode reuse, directory
growth and complete default Notes/Files workflows remain open. A separate SDK49
application patch has completed an advisory inode-identity recheck; ordinary
rename still cannot atomically compare an earlier user-space observation.
Networking/services, isolated graphics, broader ext4, POSIX/musl, SMP and full
release gates remain open. Physical and manual acceptance remain deferred.

| Receipt under `build/prototypes/` | SHA256 |
| --- | --- |
| `sdk48-next-data-allocation-private-v1/source-manifest.json` | `6a8c7e0bb5dbbdf224629704c4c156328bc371a153130d809e27156ee24c6007` |
| `sdk48-next-data-allocation-private-v1/FREEZE.json` | `65f6fedcaac44ef1e6ff985cd0aeb23bcd7159fa56b972d3db01a980fde5bcd9` |
| `sdk48-freeze-readiness-v2/readiness-review-v1.json` | `78d08d30199905689ab41bf1459f1d41a487917f02b248323d0ee18149beb069` |
| `sdk48-next-data-hosted-receipts-v3/INPUTS.json` | `c044d9c52249ea2c7a3a9252e8a3f8ceb926741154cc078ee949ec2a77f0c092` |
| `sdk48-next-data-final-combined-attempt-11/result-v1.json` | `c3cddf3fcd231d0e7e00a4f1f75d51dc32f8808610320168d105352866cc7722` |
| `sdk48-hosted-os-tooling-v1/result-v1.json` | `79cfe1a6b99b196400a9267c8e82169edaa934d35f8429a277a743b7a7fb37a9` |
| `sdk48-producer-consumer-build-v1/matrix-v1.json` | `1c9afe0a2715fb86994c0ac55c374f41ab0180eda75bab05f2d70a8bb47004cf` |
| `sdk48-kernel-debug-runtime-v1/result-v1.json` | `a4b07c71f70783a737edb478c6ed1b7075d7736ad18eeab13ad4a11ea1ce80de` |
| `sdk48-build-artifact-audit-v2/result-v1.json` | `383a114564bb1e0bbb1d0d042247ed4e2c8f4928e00824a236a38cfb24fa9084` |
| `sdk48-user-first-next-private-v1/RUNTIME.json` | `2f75c99a66d8c5f349c4ffb231021e8422d8bf39f2e0712bf2b3c29fcbf76619` |
| `sdk48-user-first-next-independent-audit-v1/result-v1.json` | `cbed687d7135565ee062cf6d4e6015be0c0d0f31d3ed53736b9ced10cd12e726` |
| `sdk48-qualification-summary-v1/result-v1.json` | `1c933bf2ec29272f09074fad2adbb0b3cf7f93666b4bcff9920cf6ee20832a4e` |
| `sdk48-next-data-virtio-cuts-prep-v1/runtime-full-attempt-01/RUNTIME.json` | `f565bf49cefbef390865005c1619ccb93a99a258966b09d35ec1ea811403001f` |
| `sdk48-next-data-virtio-independent-audit-v1/attempt-v3/RESULT.json` | `c31a57810e4b5266c5cca40d035e0261e4d8b62b014f90943d55d2882f6d61f3` |
| `sdk48-next-data-service-root-review-v1/ALL_AFTER_RESULT_V3.json` | `7c3a30838c47a2301d512ee4bb9cea6a7c4bb67fddc4ac0386a89e7d9a54dcc9` |
| `sdk48-next-data-virtio-independent-audit-v1/attempt-v4/RESULT.json` | `dffab7653f1ef54fc3146a02bc7491e1a8b8218c6c88fa6a9cb70cecff90e939` |

## First initialized file-data block and default Notes first save (SDK47, private)

The accepted snapshot remains **Kernel919 / OS623 / SDK41**. The frozen,
unpromoted SDK47 candidate is **Kernel956 / OS624 / SDK47**, UAPI **0.7.0**,
with 1,580 source files. Separate UID 1000 probes use private OS625 trees; they
are not the frozen candidate or an accepted distribution. M0-M12 remains open.

The bounded ext4 writer allocates the first initialized 1 KiB data block for
an SDK46-created empty regular inode. It proves that the chosen free block is
unreferenced through a checked, 128-record allocated-inode scan, seals the
complete zero-filled data image with the journal and four metadata homes,
and writes and flushes data before publishing metadata. Allocation homes are
flushed before the inode home. Recovery admits the eight old-inode allocation
mixtures and all-after state; an after inode with old allocation homes is
rejected. This is an ext4 subset, not general file-data allocation.

Qualification is complete for this private slice:

- **20 fresh producer/OS-only SDK consumer builds** cover all ten Kernel
  architectures in Debug and Release, with a separate static libc test per
  tuple. The consumer compiles no Kernel sources. **10 separate standalone
  Debug Kernel QEMU gates** pass. Interim runtime matrix observations remain
  unchanged and are bound to final rows by exact Debug SDK/image hashes.
- The fresh complete hosted OS tooling suite passes **707 tests**. Final
  source owner/mounted, replay, ownership, ABI and legacy regressions pass;
  ASan/UBSan and ten freestanding object profiles are separate evidence.
  Ownership cross objects use predecessor SDK46 flags with ABI47 source;
  they are not an SDK47 consumer build. Leak detection remains disabled.
- **Two actual UID 1000 native ELF boots** save two files consecutively,
  exercise an offset-seven zero gap, file/directory fsync, reopen, EOF and
  exclusive-create rejection, and verify the same bytes and inode identities
  after host-terminated QEMU restart. Exactly two inodes and two data blocks
  are allocated. Offline CRC, e2fsck/stat/readback and partition guards agree.
- The separate actual Virtio mounted-service campaign passes **46
  fault/restart pairs and four controls, 96 QEMU boots**, covering 14 writes
  and nine FLUSHes. Independent audit rehashes 853 artifacts, performs 132
  offline checks and compares 18 cuts with separate e2fsprogs replay images.
  These POSIX calls execute in Kernel context; this campaign is not user ELF
  execution or physical power-loss evidence.
- **Two further actual default Notes boots** execute unchanged native Notes
  new-file save/read and unchanged command-line ls. Each child is reaped;
  restart preserves inode 14, data block 535 and the exact 20-byte English
  note, with zero tail and no temporary filename. Independent source/archive
  ELF and raw storage audit checks exactly one inode/block allocation and
  unchanged guards. This is not the graphical Files or complete editor gate.

The inherited deletion of three earlier failed mounted-harness scratch
directories remains an unrecoverable preservation deviation. Two early user
pre-output failures have no captured terminal logs; one original preparation
driver is reconstructed, explicitly labelled. Notes V1/V2 build failures, V3
runtime failure and the service campaign's initial control-marker failure are
retained in their own named lanes. No successor relabels them as passes.

No SDK47 promotion is claimed. Subsequent-block allocation, replacement rename,
failed-save unlink/orphan cleanup, directory growth, inode reuse and the full
Notes atomic save workflow remain open. SDK48 is a separate private successor
for one next block after an aligned 1-15-block prefix; its preparation is not
qualification. Connected networking/services, isolated graphics, broader ext4,
POSIX/musl conformance, SMP and release gates remain open. Physical hardware and
manual desktop acceptance remain deferred by the user. Software epoch fixtures
do not qualify a physical RTC or shutdown durability.

Primary evidence under `build/prototypes/`:

| Receipt | SHA256 |
| --- | --- |
| `sdk47-first-data-allocation-private-v1/source-manifest.json` | `648aed4f75d9b9cc358fc9b12572ff0d9f84515863f98c4bc4dfedb6e1a46a9e` |
| `sdk47-first-data-allocation-private-v1/FREEZE.json` | `5b2402b521dc13073bd3af0bf898d2a9074b79ac45aee68831f5b874930757dd` |
| `sdk47-producer-consumer-build-v1/matrix-v1.json` | `9d95fc3a4bc7d9ccaacccbd0bc51ab4875453b5331c6377c0f994cf15f3e5860` |
| `sdk47-kernel-debug-runtime-v1/result-v1.json` | `3517ebbbb3fcee4db74ac4740afadea72ebdf26ba04106c7dbe71c35bf6004df` |
| `sdk47-hosted-os-tooling-v1/result-v1.json` | `3d0835a3c4b016a10041dbb8365c86397def6609a9e7c29a61e953f875cfd653` |
| `sdk47-user-first-data-private-v1/RUNTIME.json` | `a42471c5dbed1d39f09cd6911d04105848220d7e440ce7ea27e6eb2e2b0a115a` |
| `sdk47-build-user-audit-v1/result-v1.json` | `725e493e81dfcdbb8c62d25db7faf7acecb7ecc5ae71cce3e394f49039eb1574` |
| `sdk47-first-data-qemu-service-cuts-v1/full-x86_64-debug-attempt-02/result.json` | `0f3cf91d12bad1423e41bcf6d5ae5e40ac25f04fcbeb7b809da3a30c8b87cc53` |
| `sdk47-first-data-qemu-service-cuts-v1/audit-full-x86_64-debug-v1/result.json` | `84f4d9d72d119e66d9df55c8f8ea4603bcbd41db5be436e698b505969ef47599` |
| `sdk47-default-notes-first-save-private-v4/NOTES_RUNTIME.json` | `3d05f50abb14161c51b7555ad7de5fda882e8a4b7dd50be51f6ffd4d1ab0cf27` |
| `sdk47-notes-independent-audit-v1/result-v1.json` | `0f41f9acd8d4d3d20197cec6bf95b2c854c1844acad61231f1754996dc417b97` |
| `sdk47-qualification-summary-v1/result-v1.json` | `2b95d58d59678cf0a20cfd9826eed778341eefbaf9e8e52542b89d389f32e647` |

## Empty regular-file creation slice (SDK46, private)

The accepted snapshot remains **Kernel919 / OS623 / SDK41**. The frozen,
unpromoted SDK46 source candidate is **Kernel942 / OS624 / SDK46**. The separate
UID 1000 user-probe fixture is a private **OS625** source tree; it is not the
frozen OS624 candidate or an accepted distribution. This qualification covers
creation of an empty ext4 regular file in a bounded existing directory slot.
It does not complete M0-M12.

The exact SDK46 producer and OS-only consumer build passes **20 tuples** (all
ten Kernel architectures in Debug and Release), each with a separate static
libc test and an architecture- and mode-specific SDK manifest. **10 independent
standalone Debug Kernel QEMU boots** pass. Their receipt observed an interim
build-matrix hash while the matrix was still running; each boot's Debug SDK
manifest and kernel image are instead checked against the corresponding final
matrix row. A fresh full hosted OS tooling run passes **705 tests**. The
read-only build/user audit checks 1,566 frozen source files, 3,784 SDK files,
100 build command logs and 60 OS consumer artifacts.

On x86_64 Debug, **two actual UID 1000 native ELF boots** exercise exclusive
empty-file creation and post-termination QEMU restart. The user probe verifies
`O_EXCL`/`EEXIST`, file and directory `fsync`, ownership, inode identity and
restart persistence. The created inode is 14; free inodes change from 8,178
to 8,177 and remain there after restart, while free blocks remain 26,529.
The fixture selects a software epoch and does not qualify a physical RTC.

A separate native mounted-service campaign uses actual Virtio transport and
kernel-executed POSIX create calls: **52 fault/restart pairs plus four controls,
108 QEMU boots**. An independent read-only audit checks 954 hashed campaign
artifacts, performs 156 fresh offline e2fsck/debugfs checks and compares 24
cuts with separate e2fsprogs replay images. This device campaign does not
execute a user ELF; the two UID 1000 boots are distinct evidence.

Frozen-source hosted evidence includes ABI guards, planner, owner, mounted and
replay checks. Owner V3 and replay V3 each cover ten cross profiles. The owner
sanitizer receipt uses the **frozen V2 owner source snapshot**, not an owner
V3 sanitizer rerun. Mounted sanitized V3 and replay sanitized V4 are separate
receipts bound to the final source. The owner V3 hosted test has a recorded
test-only successor difference, checked by the final-source audit.

The earlier three failed mounted-harness scratch directories were deleted and
cannot be recovered; that preservation deviation is recorded in the freeze
and final-source audit. Other failed preparation/audit receipts remain retained.
The operation allocates one inode and no data block. It does not qualify
general data-block allocation, Notes temporary-file/atomic-replacement save,
user-side FLUSH fault tracing, physical power loss, real hardware, SMP, manual
desktop workflows or M0-M12 completion. The user has no reference hardware
or manual desktop acceptance environment yet, so those gates remain open.

Primary evidence under `build/prototypes/`:

| Receipt | SHA256 |
| --- | --- |
| `sdk46-empty-create-private-v1/source-manifest.json` | `6f0189bd9780993be7ad932ad30900bc1f7b29c179012ab942d49068ddbd95ef` |
| `sdk46-empty-create-private-v1/FREEZE.json` | `3a5e9194f99de662b211051ac3bc790c18f9c7b3e9ff20ff1741be4a427f6075` |
| `sdk46-final-source-audit-v1/result-v1.json` | `07799273c8c172b4400b01291f4e15dcd75c44442826e971e1133a3b1542fcef` |
| `sdk46-producer-consumer-build-v1/matrix-v1.json` | `a7e09f30b08e4b7502a3d3844559341e67f97f8b1baa9fcfde7513f793316183` |
| `sdk46-kernel-debug-runtime-v1/result-v1.json` | `6bc432bd133b869a6900dc01e7b9af278859e7f7c3bda491bea744ae28d84893` |
| `sdk46-hosted-os-tooling-v1/result-v1.json` | `ece4bc503aeb1c6c8c27b5e7c3ffb54586f08dd662a08b2f805992a7176fceb2` |
| `sdk46-user-create-private-v5/RUNTIME.json` | `2cce12e9f73676f2254893911250bc61c9cc8782ccb99d0443c4534bcd8a64ff` |
| `sdk46-build-user-audit-v2/result-v2.json` | `3818ef58e37d7b48948637f750e37e41406bc3bdfa696cc22da9fdeb774067f4` |
| `sdk46-create-qemu-service-cuts-v2/full-x86_64-debug-v1/result.json` | `b70f8cd894eff170bf83ba5b98a647216983e144f10eaa0dba23dff9508ce3f5` |
| `sdk46-create-qemu-service-cuts-v2/audit-full-x86_64-debug-v1/result.json` | `d39cbf3384f1e549f6cba76d46998a5cba7f4cafeec7942bcef35a9bb4aaa847` |
| `sdk46-empty-create-owner-hosted-v1/sanitizer-v1/result-v1.json` (V2 owner source) | `a84935a3d3b7154ae73e4d5b4273b9247a83da75467f8015d370b16908809ba0` |
| `sdk46-empty-create-private-v1/mounted-create-evidence-sanitized-v3/result.json` | `831706a917a3b054273b91ab6860b59d245d735106c1c9f43d11d6e3505673a2` |
| `sdk46-create-replay-review-v1/evidence-v4-sanitized/result.json` | `24157910a06bdec7ab4e38f473bf8f4fb745ac3c470d5627eeac1c84c4c1ef3c` |
| `sdk46-qualification-summary-v1/result-v2.json` | `efe000b14b5a9a54deb396de85509f376108c0f64b30ac1e26216d119ae8253d` |

## Native stat identity and executed file-edit slice (SDK45, private)

The accepted snapshot remains **Kernel919 / OS623 / SDK41**. The new private
candidate is **Kernel931 / OS624 / SDK45 V3**, with UAPI **0.7.0**. It is not
promoted and does not complete M0-M12 or change the deferred physical/manual
acceptance gates.

Native `fstat_v2` (1026) and `newfstatat_v2` (1027) return an unchanged `ok_stat`
prefix and a 64-bit inode identity. Legacy calls retain their numbers and exact
write size. The same provider query supplies metadata and identity, unadvertised
identity becomes zero, and padding is zero. The distribution static libc uses
the v2 calls and a 64-bit `st_ino` on every target. Linux stat layouts are
unchanged. Native device/timestamp metadata and full POSIX stat remain open.

Qualification completed:

- Ten hosted architecture configurations cover inode validity, full-width
  values, legacy bounds, padding and retained descriptors. The actual native
  dispatch model and ASan/UBSan pass; LeakSanitizer remains disabled in this
  environment. The direct file-attribute runner's missing link dependencies were
  repaired and its x86_64 execution passes. Hosted profiles are not target boots.
- The complete V1 hosted OS tooling suite passes **704 tests**. V3 inherits the
  unchanged tooling and Python test inventory; its only later OS change repairs
  a constant in the native libc fixture. That fixture is separately qualified
  against an exact exported SDK and through all twenty final build tuples. This
  is not a fresh full V3 hosted-suite run.
- **20 fresh SDK45 V3 producer/OS-only consumer tuples** pass: all ten
  architectures in Debug and Release, with exact SDK/compiler admission,
  distribution images, ext4 rootfs, UAPI checks and a separate libc test for each
  tuple. The OS consumer has no sibling Kernel checkout.
- **10 standalone Debug Kernel QEMU boots** pass, including reached stat-v2
  projection test points with the actual target layouts.
- **2 actual x86_64 UID 1000 native ELF boots** pass. The probe reads the initial
  4096-byte file, writes `EDIT` at offset 100, calls `fsync`, rechecks every byte,
  renames the file, reads through the retained descriptor, and checks the final
  path/inode/ownership/EOF. After host-terminated QEMU restart it verifies the
  full saved payload and absent old name. `/init` observes exit status zero and
  reaps the child. Legacy fstat output canaries also pass inside the user ELF.
- Offline e2fsck/debugfs, raw inode/data inspection and partition guards agree
  with both guest snapshots. The saved payload SHA256 is
  `d61a0aa572ff1a9cda83eb6cdd4ba54ccef92a280191773b86eb8159317f3cba`.

The user fixture explicitly selects an administrator software epoch through SDK
interfaces. x86_64 physical RTC remains unavailable; this does not qualify RTC
accuracy, physical power loss, shutdown or SMP. The user runner does not trace
FLUSH fault ordering. The earlier SDK44 240-boot mounted rename campaign remains
separate kernel-service evidence.

Primary evidence under `build/prototypes/`:

| Receipt | SHA256 |
| --- | --- |
| `sdk45-native-stat-identity-private-v3/source-manifest.json` | `cbaf2e32d88d5403d9b8f6c2205c1b58c5c519ff2cb644c71dfaa09410dea40a` |
| `sdk45-native-stat-identity-private-v3/FREEZE.json` | `649bdc27051378ecc35a9016b9920e46aecd26ef53665a596fae4e2a8f1a27f0` |
| `sdk45-producer-consumer-build-v3/matrix-v1.json` | `5c137f83fb3551f9de06ee3794803d9b6de202f55838ae4b21968fbcc3847671` |
| `sdk45-kernel-debug-runtime-v1/result-v1.json` | `eabfc04c67af8124ff133270d8061c2768d5a7b7bee25afdefd0df9eec6f6d4c` |
| `sdk45-user-edit-runtime-v1/result-v1.json` | `3cd56a9d54db9cba21d1cc165d8df11f22a204a315264274a386680848437afa` |
| `sdk45-user-edit-evidence-audit-v1/result-v1.json` | `870207ad41e139f0b6475325970ddec5f1a87aeb76334fdddea00b87cd52003d` |
| `sdk45-qualification-summary-v1/result-v1.json` | `5f7057e270a224b4493144cb8d41620b3bce9ee7cd134ee513a042e0873a4420` |

Preserved predecessors include the actual SDK44 `path-stat-identity` failure,
the SDK45 V1 stale Debug UAPI assertion, V2 libc constant-macro compile failure,
the initial tooling timeout and the initial freeze check's overly strict log
footer assumption. Successor receipts do not overwrite or relabel those results.

The mounted writer still rejects new-file allocation, replacement rename and
unlink. Consequently the default Notes temporary-file/atomic replacement save
workflow is not completed by this existing-file probe. The next M4 design is
`sdk46-empty-create-design-v1/DESIGN.md`: initial ownership in one journalled
empty-file creation transaction, explicit allocation replay validation and
separate fault/user acceptance. Data allocation, replacement and cleanup remain
further prerequisites. General ext4/POSIX, connected networking, the isolated
desktop, conformance inventories and release qualification remain open.


## Accepted SDK41 baseline and earlier private SDK44 work

Accepted source is **Kernel919 / OS623 / SDK41**, published to the isolated
`build/prototypes/native-signal-actions-sdk29-v1/working` snapshot. The primary
repositories retain their existing changes. The complete SDK37 source snapshot
and backups are retained. SDK exports remain at the explicit architecture/mode
paths recorded in the publication receipt; the source snapshot does not embed
the Kernel SDK artifacts.

The [SDK41 final integration audit](../../../build/prototypes/sdk41-final-integration-v1/audit-v1.json)
admits legacy80, production20, Notes20, hosted697, shared-futex40 and the bounded
storage campaign with their separate independent reviews. Publication SHA256 is
`c5ce6d742d29555ac013da333f85edbe308af0dee7d2326ee65b6d9a1a71f601`;
[post-publication review](../../../build/prototypes/sdk41-final-integration-v1/post-audit-v1.json)
SHA256 is `d9e21a0f0ba048b8cb2daa1f53c8313d808439f1999f4b12784ef76cbbbb6981`.
The live source, retired SDK37 source and complete backups match their admitted
byte inventories, and all twenty exported SDK profiles were checked.

The Notes20 independent reviewer previously rejected the valid OS-composed
image because it incorrectly required equality with the standalone Kernel SDK
image. That failed reviewer and its failure evidence are preserved. The
[V5 successor review](../../../build/prototypes/sdk41-notes-independent-v5/audit-notes-v1.json)
instead checks exact SDK/compiler admission, OS-only xmake command/log binding
and byte-exact reconstruction of all twenty distribution images from their
ELFs. It also checks 280 installed application payloads, 380 actual English
command responses and 500 serial negatives. These workflows execute native
applications over RAM/SimpleFS; they do not establish journalled editor saves
or isolated graphical workflows. Retained V3 hosted/sanitizer controls are
explicitly inherited, not fresh V4 executions.

Private SDK44 supplies ordered same-directory rename of a preallocated regular
file to an absent name fitting its original directory record. Inode-table home
writes are flushed before the directory home write in both checkpoint and boot
replay. General allocation, replacement, cross-directory moves and unlinks are
still outside this profile. The original after-effect ordering failure is
preserved; the repair completed 54 hosted fault cases with sanitizers,
independent e2fsprogs replay and thirty cross-compiled objects.

The [SDK44 V2 producer/consumer build20](../../../build/prototypes/sdk44-producer-consumer-build-v1/matrix-v1.json)
uses separate Kernel producer and OS-only consumer directories. All ten
architectures and Debug/Release modes pass. The
[standalone Kernel10 QEMU gate](../../../build/prototypes/sdk44-kernel-debug-runtime-v2/result-v1.json)
boots the actual xmake-produced Debug Kernel images on all ten architectures.
These standalone boots are distinct from the mounted rename probes.

SDK44 V2 and V3 hosted failures are retained. Frozen V4 corrects the two active
ABI41-only guards while preserving the GCC requirement and historical SDK41
fixture. Its independent OS source copy passes 73 targeted tests, ten ABI/GCC
controls and [the full 699-test suite](../../../build/prototypes/sdk44-hosted-tooling-v4-v1/hosted-tools-v1.json).
All 1553 frozen source hashes match before and after execution. Relative to V2,
only the two evidence tools and their hosted fixture differ. The
[artifact inheritance review](../../../build/prototypes/sdk44-v4-artifact-inheritance-v2/result-v1.json)
checks both frozen trees, actual producer/consumer source trees, twenty exact
SDK manifests/artifact inventories, compilers and consumer artifacts. V2 builds
are retained because their compilation inputs are identical; they are not
reported as fresh V4 builds. The first inheritance reviewer had a manifest-map
schema assumption error; its failed version is preserved.

The strengthened [mounted rename campaign](../../../build/prototypes/sdk44-mounted-rename-payload-guest-private-v2/representative-full-v1/result.json)
passes i386, x86_64 and mips full matrices: **240 guest boots**, with every one of
eleven write and eight FLUSH boundaries tested by an error after completion and
an immediate guest cut, followed by restart. A separate x86_64 smoke run passes
32 boots. Tests check all 4096 file bytes, length and EOF, exact I/O order,
guarded partition bounds, changed-block limits, offline fsck, namespace and
independent e2fsprogs replay. Both malformed inputs refuse with zero writes and
zero FLUSHes. The [independent full review](../../../build/prototypes/sdk44-mounted-rename-payload-review-v1/full-result.json)
checks all 240 logs, forty complete-file snapshots and forty-one terminal
guarded disks per architecture. Initial fault disks were reused by restart;
only terminal disk hashes are available for direct rechecking. These probes
execute mounted POSIX service calls in kernel context (`user_elf=0`), not
unprivileged user ELF rename syscalls. QEMU termination does not prove physical
power-loss behavior. SDK44 has not been promoted.

Complete M0-M12 remains open. The default distribution root still reports
`journal=none`; general durable creation and atomic editor replacement need
further implementation. Full POSIX/musl/DSO/TLS/pthread support, connected
Internet networking, isolated compositor/apps, synchronized guest shutdown,
SMP and remaining release gates also remain open. Default applications and
basic English text-editing/file-management flows remain the automation focus.
M11 physical-machine and M12 manual desktop acceptance remain user-deferred.



Implementation started on 2026-09-20. This record describes executable changes,
not completion of the [M0–M12 workstation target](README.md). The normative
inventories remain incomplete and no milestone is waived by a passing subset.

## Earlier SDK41 V4 integration and mounted rename durability work

Accepted source remains **Kernel917 / OS599 / SDK37**. No successor is published.
The SDK41 V3 source (Kernel919 / OS623) completed all twenty producer/consumer
builds, ten actual xmake Debug Kernel boots, ten separately compiled O2 native
probes, forty fresh shared-futex/cleanup guests and the bounded three-profile
storage campaign. Storage evidence includes six boots, forty-eight completed
device-call cuts and twenty-four pre-device injected faults. Bounded V3
qualification SHA256 is
`3a642030fb035d40e79bc88086b68d390a292c5bf9d41ba7ba61861a26d606ef`.
The independent shared-futex review is complete; an additional independent
storage evidence review is in progress. These are separate evidence layers.

V3's complete hosted tool suite passed 697/697, but its root legacy driver
stopped after a successful first pressure guest: the qualifier emitted a stale
SDK37 receipt field after admitting SDK41. The raw failed campaign and native
result remain unchanged. Isolated V4 fixes exactly two OS qualifier receipt
fields, taking the ABI from the fully admitted manifest. Kernel source, all
twenty exported SDK artifacts and production OS code remain byte-identical.
V4 manifest SHA256 is
`28b55fd727d70b3a47378b913ea30969870bb314d2751f92b707ae9aea301a02`;
freeze SHA256 is
`96df76784977bd676ceefd36b624490bbc80dc082d9dc9e238eb80c1c29c9542`.
The independent V4 source and retained-artifact review has passed. Fresh V4
hosted tools pass 697/697; receipt SHA256 is
`5ff16cee7c0a9689e18cc5b30313fec3fd37899a167f241d8fbebeb5fe4d9576`.
Fresh legacy80 is running. The serialized follow-through driver will run its
read-only disk/serial review, production20 and review, then fresh Notes20;
it never restarts the active campaigns and has no publication operation.
The Notes40 hosted and forty Clang18 sanitizer controls are explicitly retained
V3 executions: exact application/fixture/runner source identity was independently
checked against V4. Inheritance receipt SHA256 is
`a071759766ed3637d2e4a6469397177781ba514cb5fa4d515335085aac079b9d`.

Private mounted rename now reaches VFS through the canonical owner/cache.
It accepts a same-parent regular-file rename to an absent name that fits the
original dirent; no allocation, replacement or directory move is supplied.
Frozen private-v1 passed hosted ASan/UBSan, eighteen before-effect cut points,
six torn journal-head cases, all-ten freestanding compilation, independent
e2fsprogs replay and three representative standalone Kernel boots. Qualification
SHA256 is
`7a5d33b585f3b68690e98db8eb59868b28f005215225fd91abeb0c2094760daf`.
These boots do not execute native rename. An isolated after-effect successor
found a durability gap: the directory home block can persist before unflushed
inode-table home writes. The strict recovery policy safely refuses this image,
but automatic recovery is not qualified. The next repair must establish the
inode-table FLUSH boundary before the directory home write in checkpoint and
boot recovery, then retest every new failure/cut boundary. Failed generations
remain retained. Preliminary ABI41 composition builds are not a new accepted
SDK; a formal mounted-rename export is planned as SDK44 after these gates.

Default distro root remains `journal=none`. General durable creation/rename,
atomic editor saves, connected host networking, isolated desktop and full
M0-M12 remain open. Default applications and basic English text/file workflows
remain the user-selected automation scope. Physical M11 and manual desktop M12
acceptance remain user-deferred.

## Accepted SDK37 shared anonymous frames and retained entropy

The latest accepted isolated source is **Kernel917 / OS599 / SDK37**, at
`build/prototypes/native-signal-actions-sdk29-v1/working`. The next mandatory
promotion predecessor is `build/prototypes/sdk37-final-promotion-v1/promotion-v1.json`,
SHA256 `aca878fd1e3757eb164ad4a1941dff122c1ed195cc31115f8d1b012ec49deec9`.
Post-publication review SHA256 is
`83f14863d583332813749da3891cf9f5fc2f975157f87aca933ff5c3775c24e2`.
It verifies all 917/599 live sources, complete retained SDK35 backups/retired
trees, twenty explicit SDK37 manifests and 3,704 exported artifact hashes.
The dirty primary implementation repositories remain preserved. Completed
promoters and source-before auditors must not be rerun.

SDK37 adds counted anonymous shared frames across fork, independent retirement
pins and generation-checked final-reference/final-pin release retry ownership.
It retains SDK35 host Virtio entropy/getrandom/AT_RANDOM and qualified private
futex behavior. Shared-frame futex and coherent shared file/page cache remain
unsupported at this accepted checkpoint. The runtime is serialized on one CPU;
physical hardware, SMP/TLB shootdowns and general dynamic loading remain open.

All eighty pressure/adoption/PID1/service-graph architecture/mode rows and twenty
production `/init` console restarts passed. Independent final disk, installed
ELF and complete serial reviews passed with 100 fresh read-only filesystem checks,
200 serial-damage controls and forty PID1/graph terminal-retirement observations.
Legacy review SHA256 is
`a59e4439ba94771ea0bd247bd85d251033b48b151a9b2c2faa850c375003d6ca`;
production review SHA256 is
`d199f0803464bc3c698bbb59c797ff6ff22bef1833531759de4a6661faf3df50`.
Supplemental frozen producer evidence retains twenty SDK/OS builds, ten standalone
Debug Kernel boots, ten Debug OS guests, ten Release pipeline guests, ten Debug
pressure/removal qualifiers, six static and six dynamic entropy/control combinations,
696 hosted tools and hosted/sanitized models. Its separate review includes 42
fresh filesystem checks. No guest synchronized shutdown claim follows from host
QEMU termination. The one-console production manager uses pinned Debug musl in
both Kernel modes; pressure uses matching-mode musl.

### Qualified private successors and English application workflow

The accepted predecessor remains SDK37. These later source candidates are
frozen or undergoing integration; their results do not promote them or close
any full milestone. Completed preparations, freezes and auditors remain one-shot.

SDK39 shared-futex is frozen at
`build/prototypes/native-shared-futex-sdk39-v1`. Source-manifest SHA256 is
`b09540c661b049b0ff57c2304e93e502379ba06cd0809c8caafbad3e890a4ddd`;
freeze SHA256 is `876f09433c44d77966f66bbff82474e136c38cfac9e6ecc41e020e2de6cc15d3`.
All forty shared-futex/cleanup QEMU guests now pass: ten architectures, Debug
and Release, ordinary and signal/SIGKILL/exec cleanup. The matrix SHA256 is
`456b8b25bbb704a6ba0337c6085138e3e3aa081c853c4dce1933be474043298e`.
Debug proves strict WAIT arm before MAP_FIXED replacement WAKE, exact old-frame
pin retention, distinct replacement generation and WAKE=0; ordinary cross-PID
WAKE=1 also passes. Release proves actual user outcomes and final resource
cleanup without claiming Debug trace order. Independent review SHA256 is
`8198ccf1b2b2af4ffbb6cd2a99c969f5b9f8d0ed8efee4f260cf36e86b4a2264`;
it includes forty fresh read-only fscks and five serial-damage controls. Root
source replay SHA256 is
`b9acb9e5b0e85158a1ab0fd981eaa02a47ce88d2d13900f33d6bee52ebb2b5b6`.
Six explicit aggregate evidence-path corrections leave frozen metadata intact;
failed path reviews and earlier finite V1/V2/V3 conclusions remain retained.

SDK40 is the separate bounded mounted-dirty storage successor. Its qualification
SHA256 is `9a117fd9877f433af9dada6e549221f233c971a70edbeff13c156bd1ccff4e49`;
root source freeze SHA256 is
`c363aa0b7aa43b9d9b56e0f183b054c1880635814bf3c9797d6874273264ae25`.
All 1,519 sources match the freeze. x86_64, i386 and big-endian MIPS Debug pass
standalone boots, UID 1000/credential-auxv two-boot write/reopen tests, sixteen
completed Virtio-call recovery cuts and eight injected pre-device failures each.
Hosted lifecycle checks and all-ten cross compilation pass. The x86_64 OS
artifact consumer builds and boots; ABI and mounted-dirty profile mismatch
are rejected. The full tooling result remains **682/683**, with one inherited
SDK34-specific object-pressure fixture admission error. The dedicated current
SDK validator passes 38/38; this remaining broad error is a composition repair
gate, not a waived pass.

The separate SDK40 root runtime review SHA256 is
`08a59fd23c1af013d3a75f926e382fde900b9d0a89bd183c35b45e4927c773f1`.
It checks exact source/SDK/build bindings, 138 complete success logs, 48 cut
logs, 24 injected-failure logs, 1,104 damaged/echo-only controls and 69 fresh
read-only checks of retained Linux-replayed images. It does not rerun native
guests or rederive the producer byte oracle. Two failed reviewer assumptions
remain retained: reopen has sixteen controls rather than fourteen, and an
intentional sixteen-byte fault-control header is outside filesystem media.
The successor binds that exact header and every other disk byte.

Storage40 supports only existing preallocated-file bounded journalled writes,
mounted dirty lifetime and one-way clean freeze. Other seven architectures and
Release remain unqualified for its storage execution. The generic distro boot
still reports `journal=none`; separate journalled campaigns cannot qualify a
journalled default distro root. General creation/rename/atomic editor saves,
full M4 and modern ext4 breadth remain open.

The OS-only Notes branch at `build/prototypes/notes-safe-save-v1` freezes 605
sources and consumes explicit SDK37 artifacts. All twenty architecture/mode
native English workflows now pass nineteen commands each (380 total): create,
save, reopen, replace, move/read, hardlink-save refusal preserving both names,
unlink and final save. Complete hosted OS tools pass **696/696**; forty
scratch-file/fault controls pass in each ordinary and ASan/UBSan lane. Matrix
SHA256 is `6576be70b86ad6c19928f5a371ab25340df5b4589c62aca612702c1b24910332`;
root review SHA256 is
`36e597150ed03c61bb78864526a668bd5ce1ec8845481281e82c2caaa9d343fa`.
The review binds all sources and SDKs, 280 installed application payloads,
380 full command responses and 500 serial-damage/echo-only controls. The initial
AArch64 boot-recipe failure and successful successor retain frozen production
sources unchanged. The branch README links exact evidence and qualification
boundaries.

Notes uses an exclusive same-directory temporary, complete short/EINTR-safe
writes, checked file fsync/close, metadata recheck, dirfd rename and checked
parent fsync/close. Pre-rename errors preserve the old destination; later errors
report replacement without successful completion. The lane requires a
caller-owned nonshared directory and ordinary caller-owned single-link file.
Native stat lacks inode identity, so the final metadata/presence/length check is
not writer locking or compare-and-swap. Restrictive umask can fail safe before
replacement. The native workflow changes a loaded RAM/SimpleFS namespace;
restart persistence, journalled creation/rename, power-cut editor durability,
arbitrary metadata preservation and isolated graphical editing remain open.

SDK41 composes exact source37, the shared-futex39 delta against37, the
storage40 delta against retained accepted34, and the Notes delta against37.
The storage ancestry is accepted34 through ordered-data38 and private
mounted-dirty storage39, not a source37 descendant. Its delta is nineteen
modified files and eighteen additions with no removals; the whole storage
source must never overwrite accepted entropy and terminal fixes.

The retained V2 composition builds all twenty architecture/mode SDK-to-OS
profiles and passes the hosted mounted lifecycle/SDK/object/Notes checks. Its
matrix artifact review SHA256 is
`6992a9115fb1ff7959490541c2f39d058edefc481122fd6032300fc8b5736f0c`.
Three storage guests exposed a missing entropy boot-service link in their
fixture. The LoongArch low-level O2 execution probe exposed a test lifetime
bug: it mutated mapping records still borrowed by its first address space.
The diagnostic observes 222 instead of 111 in all three runs; separate live
mapping arrays pass all original isolation/FP/NX assertions in all three
control runs. Control receipt SHA256 is
`df68303796b2197c0ac87875e9e268c0463053728c9d053aae678d4cc07f88f2`.
No Kernel production runtime or original assertion is relaxed.

V3 freezes exactly those two source repairs: the storage fixture links the
existing real Virtio RNG driver/entropy service, and the LoongArch test retains
independent mapping arrays. Source-manifest SHA256 is
`ac40c28fdc455fdf6020e04123adef55680c4acd792d5e815dcc5ddb1f311d13`;
freeze SHA256 is
`cd3224dbed49c1dcdb939be4aed3ea90a7cacf109c85bd55f11329752c1d345c`.
The tree is Kernel919 / OS623. Fresh V3 producer/consumer, actual xmake
standalone Kernel, shared-futex, storage, legacy service, production manager
and English application campaigns remain required before publication.
Separately compiled architecture probes are not xmake Kernel boot evidence.
The V2 generic OS observer is retained as incomplete/failed: it chose an ELF
rather than the explicit SDK-assembled AArch64 Linux image and required
Debug-only markers in Release. Those external recipe failures do not justify
production firmware-memory changes. V2 futex execution has 39 observed rows,
with PPC Release cleanup missing; it is explicitly not a qualified matrix.
Partial read-only review SHA256 is
`2ae06b5c11fabb327d2387988dd59164480476ee1a5ce5ffcb484d15ce1fabfd`.

SDK42 Unix socketpair remains separate on frozen37, with Kernel919 / OS602.
Qualification SHA256 is
`1e195a560911a133463299ee366697801e5b624d4d47ef97db791d1d17b820d7`.
All twenty SDK-to-OS builds, ten Debug and ten Release profiles with two
actual static-musl executions each now pass. Independent Debug review SHA256
is `2625967098c573334eb26204533df11281a5c865974e720ed820d13c0e64945b`;
Release review SHA256 is
`f6d60cf7b0f0d9ce64748ebaeb862d0e96bb121048e287810bb8758bb94365af`.
Twenty artifact admissions include wrong-mode refusal. Each ten-profile guest
review also performs ten fresh read-only fscks and damaged-serial controls.
Release outcome checks do not assert Debug trace order. This is bounded
AF_UNIX stream socketpair ownership, duplex/blocking/nonblocking/EOF and
fork teardown; pathname AF_UNIX, descriptor passing and full M2 remain open.

The separate same-directory rename planner and directory-replay successor
are private storage slices. Directory replay freezes 1,525 sources with seven
expected changes; delta SHA256 is
`374961cda028ec6ccc8d107f2633d2a52062c71e59fcf8194b2a58c36b569568`;
qualification SHA256 is
`8b1d9a3c35c4b896c4930a7315603a668e996f67c7d3a569940c8cd62fab91ff`.
Hosted ASan/UBSan tests exercise three actual JBD2 recovery actions, successful
prefix restart, malformed target/CRC/mapping refusal before writes and I/O
failures. The prior 209 completion cases, planner regression and all-ten cross
compilation pass. x86_64/i386/big-endian MIPS standalone xmake Kernel boots and
host e2fsck/debugfs checks are recorded separately from directory operation
execution. No new SDK export, mounted-cache/VFS rename, OS consumer, native
directory guest or atomic editor-save durability is qualified. Canonical
mounted owner/cache publication is the next private design and implementation.

The user selected project default applications and basic English files/text
first. UTF-8/CJK and accessibility remain target gates. M0-M12 remains incomplete;
implementation and automation continue in the confirmed foundation/storage/
network/services/isolated-desktop order. M11 physical hardware and M12 manual
desktop acceptance remain user-deferred.

## Earlier accepted SDK35 host entropy, getrandom and AT_RANDOM

At that checkpoint, the accepted isolated source was Kernel917 / OS599 / SDK35 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. The one-shot promotion
`build/prototypes/sdk35-final-promotion-v1/promotion-v1.json`, SHA256
`706f5c278481cd9eba14162ca3170c9dcf5d7c6ccf7bb19dce3825f56398c51c`,
was the mandatory predecessor for SDK37 integration. It binds frozen entropy
V3 source inventory `99fada5400143c8c66f9f872814f1b69240eb667cb852be698431b666cb8e7f5`
and composition `6a35f4eecacc497eef2a30a353912cec0e0597962788a35ccd82d6b16152cab1`.
Both repositories are published by one complete-tree RENAME_EXCHANGE; full
SDK34 backups and the retired source tree remain. Six disposable publication
controls cover success, stale inputs, interrupted exchange, receipt failure and
post-receipt failure. The dirty primary repositories remain preserved.

The Kernel owns a typed entropy source, staged getrandom copying, a real
AT_RANDOM auxv payload and failed-exec rollback. The OS supplies a modern
Virtio RNG driver on the four MMIO and six PCI architecture profiles. QEMU
uses an explicitly selected host `/dev/urandom` backend. This profile trusts
that host CSPRNG; it does not establish entropy quality, provide a Kernel
CSPRNG, qualify physical DMA/IRQ/SMP entropy, or implement the complete
blocking/GRND_RANDOM contract. Missing-device tests return unavailable and
prove that failed Linux exec can resume its native caller.

All 20 SDK35 architecture/mode exports and ten standalone Debug boots retain
their frozen V1 producer scope. V2/V3 change only test/tooling inputs; production
Kernel sources and exported headers match V1. Twenty V1 OS consumers and forty
static success/no-device guests remain separately pinned. A fresh V2 x86_64
Debug producer/standalone/OS-consumer build passed and records its distinct SDK
manifest. Six fresh V2 shared-musl success/no-device/missing-loader lanes passed
under Debug/Release, each with two static and two dynamic/control commands.
Shared-musl execution remains x86_64 only.

The final V3 complete OS tooling suite passed **696/696** with preserved raw
output, log SHA256 `e527f750c2d112722010ca3f6d01dfb4f860b1ab98bde18c3b3cbb43585f511d`.
V2 mounted-ext4 normal/sanitizer and ten target cross checks passed. Ten V2
default Debug QEMU boots and three representative no-device controls passed.
Supplemental review SHA256 is
`ea37fb57b528d3a5f9239840f4dc737589d49a44be8279eb7af8a1481ad25304`.
Its first attempt retained a lowercase-marker matching error after all fifteen
dynamic/static-control disk reviews; the successor rechecks that retained
evidence and completes the default logs without repeating those guests.

Forty V2 pressure/adoption guests retain their complete review scope. The V2
driver also reported PID1/graph passes, but its root reviewer stopped after 44
rows on a QEMU-termination-truncated final frame record. That failure remains.
V3 changes exactly four tooling/test paths and waits for complete post-success
zero-owned-frame and zero-leased-entry-stack records before terminating QEMU.
All forty fresh V3 PID1/graph consumers passed on ten architectures in both
Kernel modes. Root review SHA256 is `29425cd5d32ac079a29f3cfdb2edce8e8497f59b7529dd9116dccb770e17815f`;
independent review SHA256 is `5828e4d48fa78db0ebffe308c877de6150145179237b177d8a2b8981fc2785cf`. The reviewers keep
the V2 failed capture separate from V3 complete retirement evidence. The six
parser tests and twelve independent damage controls do not replace guest runs.

Twenty exact V2 production `/init` guests reaped the first console shell and
started a distinct ready second-generation shell. Root review SHA256 is
`77cba05a48ac17c7d6192e1ec8b7baaf808b01e03288c90bcc1225fd06fd188e`; it independently checks twenty final disks and
their installed manager ELFs. Production manager dependencies are identical in
V3. The manager still supervises one console. Adoption/PID1/graph/production
lanes use a pinned Debug musl manager under both Kernel modes; pressure uses
matching-mode musl. Disposable-workload retirement and host termination of a
live production guest are distinct from synchronized system shutdown.

Post-publication review SHA256 is `0d99d35cf19e8b63c67c356ca81e83e85378a3061521098b2c519a407582f27f`. It checks all
917/599 live source hashes, complete predecessor backups/retired sources,
twenty explicit SDK manifests and 3,704 exported artifact hashes. Older
promoters and source-before auditors must not be rerun after publication.

SDK36 shared anonymous mapping remains a frozen, integration-blocked private
predecessor. Its SDK37 composition includes entropy and V3 terminal capture,
repairs legacy ABI fixtures and final-reference/pin release retries, and is
under fresh qualification. SDK38 ordered-data ext4 work is also private; its
native x86_64 spike exposed missing Linux ftruncate dispatch and records that
adapter repair separately. Neither candidate is included in this accepted
SDK35 checkpoint.

M0-M12 remains incomplete: coherent shared-file/page cache, shared-frame futexes,
general dynamic libraries, TCP/IPv6, complete services/accounts, durable default
root, isolated desktop, SMP/runtime modules and full standards/release gates
remain open. M11 physical hardware and M12 manual desktop workflows remain
user-deferred; implementation and automatic qualification continue.

## Retained SDK37 integration preparation and provenance

The integration started from Kernel917 / OS599 / SDK35, with mandatory
promotion predecessor
`706f5c278481cd9eba14162ca3170c9dcf5d7c6ccf7bb19dce3825f56398c51c`.
The retained Kernel917 / OS599 / SDK37 composition at
`build/prototypes/sdk37-entropy-shared-v1` is frozen; its exact source has now
been published to the accepted isolated root described above.
Freeze SHA256 is
`9bbbb958e0d9b6090522de4908cc80f2f75345cc601d608729f4452619791289`;
source-manifest SHA256 is
`406d08d4595dd3f825dedfc440110f909aaf8cac82bef6703b2a100551964711`;
canonical source-tree SHA256 is
`3bd69beb0eed5676b794bcd6a98054432082ef3c3dda0ffdf73f7ac8182dbfc9`.

SDK37 combines the entropy/AT_RANDOM implementation with counted anonymous
shared frames across fork, independent mapping-retirement pins and private-page
copying. Final-reference/final-pin allocator-release failures retain their
canonical owner for a diagnosable retry. Module ABI and legacy fixture/receipt
assertions are aligned to 37. Shared file mappings and shared-frame futexes remain
explicitly unsupported in this frozen candidate.

The frozen producer/consumer evidence includes all twenty SDK-to-OS builds, ten
standalone Debug Kernel boots, ten Debug OS guests and ten Release shell-pipeline
guests. The Debug object-pressure and deletion qualifiers passed on all ten
architectures; six representative static-musl and six x86_64 dynamic-musl
entropy/rollback combinations passed. The complete OS tool suite passed 696
tests. Retained raw-image selection failures, a container LeakSanitizer failure
and an incorrect deletion aggregate remain separately recorded; successful
successors have their own recipes and receipts.

Root independently replayed the initial shared/entropy composition and its
seven final successor changes, comparing all 917 Kernel and 599 OS source files.
Source review SHA256 is
`b6ffd1ea5c61cb4b5c2437552cd450d3ce44ae45240b04e0263e7340ad61b8fc`.
The fresh eighty-profile pressure/adoption/PID1/service-graph campaign and twenty
production `/init` restarts completed, with independent disk, ELF and
complete-serial review passing before promotion. The first aggregate driver
failed on a missing field in an inherited row; its completed i386 Release
pressure guest and x86_64 Debug production restart are retained in explicit V2
successors rather than rerun or overwritten. No synchronized guest shutdown,
SMP, IRQ, physical-hardware, complete shared cache or full M0-M12 claim follows.

The SDK38 ordered-data prototype remains private. Its mounted-dirty,
`freeze_clean()` and pre-exec UID 1000/credential-auxv work has a separately retained
experimental ABI39 candidate. ABI39 is reserved for the shared-futex successor;
the storage branch therefore continues in a source-only ABI40 successor with
fresh source/artifact qualification. Neither branch replaces the accepted root.

The user keeps the implementation order: shared memory/futex, ext4 durability,
network/services, then isolated desktop. Initial application acceptance uses the
project's default editor and file manager and starts with basic English files and
text. File creation, save/reopen, rename and crash preservation require explicit
execution evidence; the initial language scope does not close the full target's
UTF-8/CJK and accessibility gates. M11 physical-machine and M12 manual desktop
acceptance remain user-deferred; implementation and automated acceptance continue.

## Earlier accepted SDK34 paging, private files and x86_64 interpreted startup

At that checkpoint, the accepted isolated source was Kernel913 / OS588 / SDK34 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. The one-shot promotion
`build/prototypes/sdk34-final-promotion-v1/promotion-v1.json`, SHA256
`c0e96b783f629907c22ac50cdb90fc598f289d720a8f7c567d4d75616f097f93`,
is the mandatory predecessor for the next integration. It applied 66 Kernel and
31 OS source additions/modifications. Complete source backups and the retired
working tree remain in the promotion directory. The existing dirty primary
repository sources were preserved; this progress file is updated separately.

The accepted mechanisms include page-pool-owned mapping metadata, structural
MappingView validation at all ten architecture backends, bounded eager regular
file MAP_PRIVATE copying and x86_64 PT_INTERP/shared-musl startup. Private file
mapping covers nonzero offsets, short requested lengths, partial EOF zeroes,
closed/unlinked backing, private writes and eager fork isolation. It does not
provide MAP_SHARED/page-cache coherence, truncate SIGBUS, COW or demand paging.
The dynamic path checks main/interpreter roles and full PT_TLS memory extents.
Actual shared-musl startup remains x86_64 only; general DSO/dlopen, dynamic
pthreads and the other nine dynamic execution profiles remain open.

The final Kernel913 producer exported 20 explicit architecture/mode SDKs and
passed ten separate standalone Debug Kernel QEMU boots. Its exact joint V1
OS588 consumer passed 20 native ext4 guests. The joint runtime campaigns passed
60 pressure/adoption/PID1 guests, 20 service-graph guests, 80 static UDP scenario
rows and 20 native-user UDP guests. These receipts retain their exact joint V1
OS source scope. The final V4 successor changes four OS test/observer paths;
its Kernel and production OS sources match the producer. Those changed paths
were requalified separately, with precise inheritance exclusions rather than
relabeling the older executions as exact V4 source executions.

The final V4/Kernel913 static-musl campaign passed all 20 matching-mode guests,
with two actual probe executions each: ten mmap2 and ten mmap profile rows.
Root review `build/prototypes/sdk34-final-musl-root-review-v1/audit-v1.json`,
SHA256 `4d400d9077a4dfc231e01855d5abe394cec1691c64b92688f31f05a85e627b6f`,
adds 100 serial negative controls, 20 fresh read-only final fscks and 40 disk ELF
payload checks. The V4 x86_64 dynamic path passed Debug/Release startup and
missing-loader controls, two executions per control. Independent root review
SHA256 is `5cc48bdd64f4a2403c26667568a82572ab69935173287072e5c0f3be91b9206e`.
It replays five source stages, checks all 20 SDKs, four dynamic guest receipts,
24 serial negatives, four fresh read-only disk checks and hosted ELF admission
negatives. The complete final V4 OS tool suite passed **682/682** on a disposable
source copy; receipt SHA256 is
`442babe98a104e25072225d2249bd438520ee1e2f59bcb5934a26eb4e79ae98b`.

Twenty additional actual production `/init` guests on Kernel913 reaped the first
console shell and started a distinct ready second-generation shell. They inherit
V1 production artifacts through identical compiler-discovered V4 dependencies.
Root review SHA256 is
`00a4df923c54fdb81d7c31465ae9c517e3b7938694fbf7eb1c0cd8f7b2822082`.
Pressure and the private-file probe use mode-matching musl; adoption, PID1,
service graph and production manager use Debug musl for both Kernel modes.
The host terminates QEMU; no synchronized guest shutdown or durability claim
follows from final offline filesystem checks. The production graph still has
one console service, with accounts and installed system daemons outstanding.

Final integration audit v2 SHA256 is
`0650e1d9ee334d5e0ef6b7a9caea78693a316a42b9b76c8bd13677490e819170`.
Publication uses one complete-working-tree Linux RENAME_EXCHANGE, with rollback
on verification or receipt-writing failure. Disposable full-source controls
exercise success, receipt failure, post-receipt failure and rejection of Python
optimized mode; their receipt SHA256 is
`5cdf10c0b4e05b8a344b4a5b52e4c704fe4651117731f4901d59d2b67d44c042`.
Earlier promoter/auditor snapshots and rejected review receipts remain retained.
Do not rerun predecessor promoters or their source-before auditors after this
promotion: their accepted-source inventories intentionally describe the past.

AT_RANDOM is still absent in SDK34 and inherited getrandom is deterministic
functional-only. An isolated SDK35 trusted-entropy/AT_RANDOM experiment is in
progress; it has not replaced this accepted checkpoint. Bounded UDP does not
complete IRQ networking, Linux sockets, TCP/IPv6 or Internet-host support.
General journalled root, shared cache/mappings, services/accounts, isolated
Wayland desktop, SMP/runtime modules, standards inventories and the remaining
M0-M12 release gates remain open. Physical M11 and manual M12 acceptance remain
user-deferred; implementation and automated qualification continue.

## Private integration successors and bounded journalled root

The candidates below began from Kernel913 / OS588 / SDK34, whose predecessor
promotion was `c0e96b783f629907c22ac50cdb90fc598f289d720a8f7c567d4d75616f097f93`.
SDK35 V2 evidence retains its exact scope in the accepted V3 successor above;
the SDK36 shared-map and SDK34 journalled-root experiments remain private.
None closes M0-M12.

The frozen entropy V2 successor at
`build/prototypes/native-entropy-sdk35-all-v2` is Kernel917 / OS597 / SDK35.
Source inventory SHA256 is
`67241e7b566ac57bedbe52deeff3e848e23e7528233047757bb3f5c58aeb302b`;
composition SHA256 is
`f2aeba3f3e589beb047e7847a30b7a8d8fd86e5299cf8f5b93111ff4ba3b0988`.
Its exact 31-path delta repairs the mounted-ext4 ABI assertion/link inputs,
SDK35 pressure/removal receipt text, default modern RNG selection on all ten
QEMU profiles, and PPC qualifier command references. Explicit no-device controls
attach no RNG. All production Kernel and OS implementation files are unchanged
from frozen V1; V1 receipts retain their original source and artifact scope.

V2 passed 690 hosted OS tool tests, ordinary/sanitized mounted-ext4 models and
ten target cross-objects. Its default QEMU harness passed ten Debug guests using
byte-pinned V1 production inputs, and three representative no-device controls
each executed twice. A fresh x86_64 Debug V2 Kernel export/standalone boot and
exact-SDK OS consumer/guest passed; that new SDK manifest is distinct from V1.
The source root review is
`build/prototypes/sdk35-v2-source-root-review-v2/audit-source-v1.json`, SHA256
`23eadcc4b353cd9a9790f5391c6bb058832c9c2f75fb6253c8b3e893cfaf630b`.
It independently replays the patch, checks all 1,514 source files and 3,704 V1
exported artifacts, and exercises forty QEMU command-generation model cases.
The first root reviewer attempt failed while writing its receipt because its
hash helper received a string; its failed output and corrected successor remain.

Separate fresh exact V2 OS builds passed six x86_64 Debug/Release dynamic
success/no-device/missing-loader lanes against explicitly selected V1 SDK35
exports whose production Kernel inputs remain identical. Receipt
`build/prototypes/sdk35-v2-dynamic-runtime-v1/result.json` has SHA256
`a2dd6907c46f92528475a8caff5c0c60b953967037411a1f29f9714874cfbb1f`.
The V2 eighty-row driver completed under
`build/prototypes/sdk35-v2-active-runtime-v1`, but its strict root review retains
the final diagnostic truncation failure described above. Forty fresh V3
terminal consumers replace that capture scope. Twenty production-manager
guests completed under `build/prototypes/sdk35-v2-production-runtime-v1` and
passed independent disk/ELF review. No guest shutdown or durability follows.

An independent shared-anonymous candidate at
`build/prototypes/native-shared-anonymous-sdk36-v1` implements counted shared
frames across fork and retirement while preserving private-page copying.
Twenty SDK36 producer/OS consumer builds and ten Debug native shared-map guests
passed; x86_64/i386/PPC static-musl guests also exercised shared-anonymous mmap
and explicit shared-frame futex rejection. Its complete 682-test tooling run
retains one old-ABI fixture error. Native module ABI34 and mounted/pressure
qualifier assertions also require reconciliation before integration. It remains
a private candidate with integration blockers, not an accepted shared-cache,
shared-file, shared-futex, SMP or complete M1/M5 claim.

The frozen SDK34-only journalled-root experiment at
`build/prototypes/native-journalled-root-sdk34-v1` adds nine OS fixture/tool/doc
files and leaves all 913 Kernel and 588 accepted OS baseline files unchanged.
Review SHA256 is
`d77d90978312334bc9ecb81f5c63b7e6fe250040ae554ddbf17612f0751f333f`.
It directly executes on-disk /init through a 1 KiB/32 MiB checked internal JBD2
root and modifies only permissions of existing file/directory inodes. On
x86_64, i386 and big-endian MIPS Debug, two normal boots, twenty completed-call
cuts with recovery and clean reboots, and five fault controls per architecture
passed. Successful write/FLUSH traces and entire volumes match an independent
libext2fs CRC model; this is 60 cut, 60 recovery and 60 clean boots, plus fifteen
fault controls. Independent review
`build/prototypes/independent-native-journalled-root-review-v1/result.json`,
SHA256 `f3b6afa318fc3fedb77391f76c25e7b78727686f8cbe5e5c4e24091a9044c556`,
rehashed those sources/receipts and reran read-only e2fsck on all sixty final
cut volumes. The remaining seventeen architecture/mode rows, ordinary file
data mutation, Linux remount, volatile/torn-sector behavior and physical power
loss remain unqualified. Its post-load UID 1000 drop does not qualify credential
auxv or login/session policy. It does not complete M4 or replace the default root.

Shared-futex generation keys and ordered regular-file data/resize are separately
designed under `build/prototypes/native-shared-futex-design-v1` and
`build/prototypes/m4-ordered-data-design-v1`; those designs are not execution
evidence. M11 physical hardware and M12 manual desktop workflows remain
user-deferred. Implementation and automated qualification continue.

## Private all-profile SDK35 trusted entropy execution

The accepted source remains Kernel913 / OS588 / SDK34 with promotion predecessor
`c0e96b783f629907c22ac50cdb90fc598f289d720a8f7c567d4d75616f097f93`.
The isolated Kernel917 / OS597 / SDK35 candidate is
`build/prototypes/native-entropy-sdk35-all-v1`; it has not replaced that checkpoint.
Its source inventory SHA256 is
`38e8a5371c2bfa10bb6b82cd2417d79c7579e908d3fd8971bb38aa927fffa403`,
and composition SHA256 is
`310e7ac30aa73e67f9a078562788c1ba1d3533d9fa5beb04b90de4cd508bb68a`.
SDK35 and native module ABI35 cover the changed public C++ service boundary.

The kernel now stages trusted-provider getrandom transfers in 256-byte chunks
and writes sixteen source bytes to Linux initial-stack AT_RANDOM before image
publication. A failed first transfer exposes no caller bytes; a later failure
returns the committed prefix. Missing entropy returns EAGAIN and discards the
unpublished Linux image. Deterministic random-device bytes are removed;
/dev/random remains unavailable. The distribution driver selects modern Virtio
MMIO on AArch64/ARM32/RV64/RV32 and PCI on the other six profiles, with explicit
little-endian rings and platform bridge/DMA addressing. Static private DMA
backing survives queue retirement after a timeout.

Twenty SDK producers, ten separate standalone Debug Kernel boots and twenty
OS artifact consumers passed. The matching-mode static-musl campaign executed
40 actual QEMU guests: each architecture/mode has two Linux probe runs with
the explicit RNG and two native EAGAIN rollback controls without it, followed
by a native pipeline. Probes check AT_RANDOM, getrandom, a 600-byte transfer,
guard bytes, invalid flags and zero-length requests. Six additional x86_64
Debug/Release guests each execute two static and two dynamic/control commands,
covering shared-musl startup, missing-loader ENOENT and no-device EAGAIN.
Those executions are exact V1 sources, not a later integration repair.

Kernel producer receipt SHA256 is
`8f078024ee84c0440ee9d802141d78a43affd432317f42fe34abdc0668c8c11c`;
consumer receipt is
`0a5afa6f7a487fc53d721511c36874409d2d46bbee359716f4fca14b4c900ba2`;
dynamic matrix is
`870ca85816544fd0c5eed0654b2189d69c0c7346d7521fc3bbbae51f957eacac`.
The root runtime review at
`build/prototypes/sdk35-all-entropy-runtime-root-review-v1/audit-v1.json`, SHA256
`b7fce0b2c234c353c363b048549833882ae50a7cb43ca8777401903caa634cbb`,
checks 3,704 exported artifacts, 184 mutated transcript negatives, 46 fresh
read-only final fscks and 108 on-disk ELF payloads. The complete V1 OS tooling
suite passed 689 tests and its source inventory remained unchanged; completion
receipt SHA256 is
`1145073bb456faef6178a037f55d0806c337b3a683700f12c735b4dc18f7044a`.
Its saved log contains the terminal completion summary; the complete progress
stream remains in the task tool outputs.

Independent source review SHA256 is
`060cf7598fb654ec13c0abca5b7165e8381a0367ef68ec5250583d481236b099`.
It validates all ten freestanding RNG objects and hosted models while retaining
three inherited defects: an ABI30 mounted-provider compile assertion and two
SDK35 qualifier receipts still recording ABI34. Normal legacy QEMU/Linux test
callers also need a working entropy-device selection. An isolated V2 repairs
these integration paths; V1 is not eligible for promotion as-is. Anonymous
shared mappings and a bounded journalled-root implementation are being developed
separately, with their own ownership and execution gates.

This Virtio path trusts QEMU and host /dev/urandom. Functional transfers do not
measure entropy quality. There is no kernel CSPRNG/reseeding policy, complete
blocking getrandom/GRND_RANDOM API, IRQ/SMP or physical entropy qualification.
Offline disk checks do not establish synchronized shutdown or durability.
General dynamic linking, coherent file cache/mappings, journalled production
root, TCP/IPv6/Linux sockets, accounts/services, isolated desktop and remaining
normative inventories still leave M0-M12 incomplete. Physical M11 and manual
M12 acceptance remain user-deferred; implementation and automation continue.

## Earlier private SDK34 regressions and shared-musl execution

The accepted checkpoint remains Kernel904 / OS578 / SDK33 with the mandatory
`d72d960f51a7c6ecc0d5bdad6081e984b44fc55f08d9eb94590281a138208e1c`
promotion predecessor. No SDK34 promotion or primary production replacement
follows from the private results below.

The repaired V4-derived pressure, init-adoption and PID1 campaign completed
60 actual QEMU guests, 20 per lane. Pressure uses mode-matching static musl;
adoption and PID1 use Debug musl for both Kernel modes. Root review
`build/prototypes/sdk34-active-consumers-root-review-v2/audit-v1.json`, SHA256
`4da9448c094b91a337953f47b5f8608c3465685e528b30245bcb0e71667d9a1e`,
rechecked 122,370 inputs, 78,556 outputs, 120 serial negative controls,
60 fresh read-only fscks and 100 final-disk payload dumps. It requires zero
pending, pinned and mapping-object quarantine records and preserves the strict
pressure/PID1 resource baselines. The retained failed review v1 assumed an
unqualified fsck executable name; pressure correctly binds its absolute path.

Twenty bounded service-graph guests also passed. Root review
`build/prototypes/sdk34-service-graph-root-review-v1/audit-v1.json`, SHA256
`f3b0cd40d3e9a5247a65968f7c4e692ef69a908a89bcb33e10a8adf8a1a19412`,
validates complete service records, negatives, exact artifacts and final disks.
These guests execute the designated test manager and children; they admit and
package the production artifact without executing the production manager.
They use Debug musl managers in both Kernel modes. Native user UDP separately
passed 20 actual Virtio NIC consumers over closed local Ethernet peers. Root
review SHA256 is `1711ff69740f991aee2b6cf2fba8427a51a14593f25c3841339aadfd310bfcfe`,
with 60 serial negatives and 160 independently checksum-checked Ethernet/UDP
packets. Neither lane establishes IRQ networking, Linux socket ABI, TCP/IPv6,
Internet-host completion, synchronized shutdown or physical hardware.

The guarded V9 candidate is Kernel909 / OS582. Root replayed the frozen V5-to-V9
source deltas, checked all ten MappingView backend entry guards, reran normal
and sanitizer mapping models, and reviewed its 20 SDK producers, ten standalone
Debug Kernel boots and 20 native ext4 consumers. Root review is
`build/prototypes/sdk34-joint-source-root-review-v1/audit-v1.json`, SHA256
`485817328e6f0f5e11213ff77307e1d312cc63f9ccf2d73a1b8f7971601f53b7`.
Its complete OS tooling suite passed 674 tests. It is private and requires final
consumer reconciliation. The separate nonzero-offset static-musl file-mapping
campaign uses these exact V7 SDKs and V9 images with mode-matched musl; its
all-profile execution is in progress. Its three-file probe/observer delta is
`26a8865ff9bad265dbc6e6a82a2ae8f0d044cb86b82ff5cdb7582b3e69dde799`.

The separate V5-derived x86_64 PT_INTERP candidate now executed shared-musl
programs twice in Debug and twice in Release. Both modes also executed two
missing-interpreter controls: exec fails before replacement, the original
native child reports ENOENT, its parent reaps it, and subsequent native commands
continue. Successful guests check main/interpreter identity, AT_BASE/PHDR/ENTRY,
a real data-pointer relocation, libc calls and TLS errno. Final offline fscks
pass. Its frozen composition SHA256 is
`4cc3545490ba188bfc65493a88e28cd26cb6478f3d2a4c46d8e84ccd45bc00d4`.
PT_TLS admission now checks the full memory extent, with negative models.
AT_RANDOM is absent and the inherited tick/xorshift getrandom is functional-only;
there is no secure entropy, general DSO/pthread or complete M5 claim. Dynamic
execution is qualified only for x86_64 in this separate candidate.

Root selectively composed the guarded source, dynamic delta and extended musl
probe as Kernel913 / OS588 under
`build/prototypes/native-dynamic-startup-sdk34-joint-v1`. Source inventory SHA256
is `24a51f13831b6616e000af87e3b65b102b5c5e4c3c2ce03f764a3e2827ccf50b`;
composition SHA256 is
`ea7f7f2376ff4610ffd77b05eb2b42f98be2001eed1df367b54739c1da4c109d`.
Its 20 SDK exports and subsequent OS/ext4 and specific runtime campaigns are
running, not accepted results. The root dynamic observer also gained a separate,
two-file successor rejecting unreviewed gaps between commands. Normal replay
and five observer tests pass; new actual dynamic executions and final review
remain pending. Its Kernel source is byte-identical to the joint producer.

M0-M12 remains incomplete. M11 physical hardware and M12 manual desktop
acceptance remain user-deferred; implementation and automation continue.

## Private SDK34 paging/removal qualification and remaining integration gates

The accepted source is still Kernel904 / OS578 / SDK33 with promotion predecessor
`d72d960f51a7c6ecc0d5bdad6081e984b44fc55f08d9eb94590281a138208e1c`.
The isolated SDK34 V4 source is Kernel907 / OS582. It selectively composes paged
mapping metadata, the no-overlap munmap quota repair, Linux unlink/unlinkat/rmdir,
and active consumer admission changes on that exact predecessor. It is not yet
promoted, and no primary production source was replaced.

The V2 Kernel producer exported all 20 architecture/mode SDK34 profiles and ran
ten separate standalone Debug Kernel QEMU boots. The V4 OS consumer ran 20 actual
native ext4 guests with 192-page mappings, eager fork isolation, protection,
remapping and cleanup checks. These producer invocations use xmake `-b`, not a
forced fresh rebuild. Root separately reviewed the complete source/composition
chain, exact SDK/header/artifact bindings, 40 serial negative controls, 20 fresh
read-only packaged-image fscks and 40 on-disk init/posix-check payload dumps.
The bounded review is
`build/prototypes/sdk34-v4-root-review-v1/audit-v1.json`, SHA256
`8dafff288068110d5b042fcb630ab486f68d7689f817d545a8708338563da6ce`.
It explicitly leaves integration defects and inherited consumers pending; it is
not a promotion receipt.

A separate OS582 static-musl removal campaign passed all 20 Debug/Release guests,
with two eight-case runs each. Each row uses mode-matching musl inputs, preserves
open-unlinked file identity and recreated-path identity, checks unlinkat flags
and directory errors, runs a later native pipeline, and passes final fsck.
Independent review is
`build/prototypes/native-removal-sdk34-final-independent-review-v2/audit-v1.json`,
SHA256 `ddfc351550c565f9767876d853a30f6404e6e7d5fbe212aa047bf87819a6af5c`.
It rechecked 40,910 input and 26,132 output hashes, complete serial records,
20 fresh read-only final-disk checks, and every on-disk probe ELF. A separately
retained actual-guest final-fsck fault control correctly leaves its result failed.
These are guest executions and offline checks, not shutdown/durability evidence.

Requalifying inherited pressure exposed a stale 128-page fixture ceiling and
old telemetry/baseline assumptions. The failed i386 guest is retained under
`build/prototypes/sdk34-active-consumers-root-v1`. The five-file repair under
`sdk34-active-consumers-root-v3` caps each child at 256 pages so later peers can
actually exhaust the global quota; checks zero mapping-object quarantine; and
accounts for the live PID1 mapping metadata at cleanup. Historical parser records
remain readable, while current pressure/adoption execution requires the new
quarantine field. Its frozen repair SHA256 is
`9c43ef1ea8bc68e044361e7d5ab3258465a1ffe394918ce2fd50bf341ab99316`.
Actual all-profile pressure, init adoption, PID1 and service graph campaigns are
in progress. A malformed chunked MappingView also needs structural rejection
before any architecture backend indexes it.

The independent SDK34 V5 regular-file MAP_PRIVATE candidate remains separate.
It implements bounded eager private copying, including the whole valid final
file page for short mappings, partial EOF zeros, retained data after close/unlink,
and independent eager fork. It does not implement MAP_SHARED, a coherent page
cache, truncate SIGBUS or executable mappings. Its producer passed 20 profiles;
consumer and musl execution evidence still require final review and integration.
The first x86_64 PT_INTERP/shared-musl startup implementation is underway in a
separate private candidate. Shared-libc artifacts alone are not loader execution.

M0-M12 remains incomplete. M11 physical hardware and M12 manual desktop
acceptance remain user-deferred; implementation and automated acceptance continue.

## Accepted SDK33 production manager execution evidence

The accepted source remains Kernel904 / OS578 / SDK33 with the mandatory
`d72d960f51a7c6ecc0d5bdad6081e984b44fc55f08d9eb94590281a138208e1c`
service-graph promotion predecessor. A separate, unchanged-source campaign now
executes the actual installed production `/init` on all ten profiles with both
Debug and Release Kernel SDKs. The manager and its static-musl input were built
in Debug for both Kernel modes; this is not a Release userland build qualification.

All 20 production guests booted the sealed one-console manager from ext4,
reaped the first shell after serial `exit`, and launched and confirmed readiness
of a distinct second-generation shell. Initial and final offline filesystem
checks passed. The production `/init` was read back from each final disk with
debugfs and matched the built ELF. The matrix is
`build/prototypes/service-graph-production-runtime-v1/matrix-v1.json`, SHA256
`e6375506481ef5b911921d5b972a049de9f10483cf2a267c36031ba661a83295`.
Root review is
`build/prototypes/service-graph-production-runtime-root-review-v1/audit-v1.json`,
SHA256 `46064f676d12ff0f21f00ec987942a0ea656cf454d80928b0bdd8a9747178d22`.
It rechecked frozen source/build/artifact inputs, 20 final disks, complete service
records and 40 negative controls, including incomplete and contradictory
post-success service records. These rechecks are not additional guest executions.

The harness terminates QEMU after the second shell starts. No guest shutdown,
sync/quiesce, crash recovery, physical poweroff or disk-durability claim follows.
The production graph still has only one console service. Accounts, installed
system daemons, durable shutdown and the other M7 gates remain open. M0-M12 is
incomplete; M11 physical and M12 manual acceptance remain user-deferred.

## Accepted SDK33 bounded service graph checkpoint

The latest accepted isolated source is Kernel904 / OS578 / SDK33 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. Primary repository
sources remain separate. The one-shot promotion
`build/prototypes/service-graph-sdk33-composition-v1/promotion-v1.json` has SHA256
`d72d960f51a7c6ecc0d5bdad6081e984b44fc55f08d9eb94590281a138208e1c`.
Its complete after inventories are the mandatory predecessor for subsequent
integration. Complete Kernel/OS source backups, merge conflicts, earlier failed
qualifier attempts and audit controls are retained.

Fourteen new OS files and four selectively merged xmake/rootfs paths add a
bounded service graph with simple, notify and oneshot readiness. Reservations
and dependency-generation snapshots reject stale launch publication. Dependency
loss retires transitive dependents; the runtime reaps before replacement,
uses bounded restart delay, reaps adopted orphans, and stops services in reverse
dependency order with TERM/KILL deadlines measured from completed signal calls.
The production graph still contains one `/bin/oksh` service and is installed only
through an explicit sealed artifact and exact manifest hash.

The composed SDK33 source passed 666 hosted tool tests and 20 actual ten-profile
Debug/Release QEMU consumers. Production init artifacts were built, admitted and
staged in each row; the execution disks then used the designated test manager
and child to exercise the three-service lifecycle. These executions do not prove
that the production manager itself booted. Root full-serial/offline audit SHA256
is `2acd2bb208a1965619d54dab598f0c852701eaf877f77b9b6827127591f1401b`,
including 40 negative serial controls. Independent composition audit SHA256 is
`d0f18833e66a60dfa6f4c926500cc1c7323006024bb4075cfdbc3253acc61eab`;
it rechecked 40,790 inputs, 26,392 outputs and 20 read-only final disk checks.
All service records are complete. QEMU is terminated after the fixture marker;
post-marker non-service diagnostics can be partial, so this is not physical
poweroff or filesystem-synchronized system shutdown evidence.

The Kernel904 SDK33 producer, native UDP, pressure, existing PID1 supervisor,
static UDP and strict shared-musl artifact recipes are preserved. This remains
a bounded M7 slice. Persistent service configuration, accounts/login, installed
system daemons, durable shutdown, default journalled root, Internet TCP/IPv6,
shared-libc guest execution and an isolated desktop remain open. The private
allocator-backed mapping repair requires SDK34 because exported C++ layouts
changed; its older OS538 snapshot is not accepted wholesale.
M0-M12 is incomplete. M11 physical hardware and M12 manual desktop acceptance
remain user-deferred while implementation and automated acceptance continue.

## Earlier accepted cumulative SDK33 native user UDP checkpoint

At that checkpoint, the accepted isolated source was Kernel904 / OS564 / SDK33 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. Primary repository
sources remain separate. The one-shot successor promotion
`build/prototypes/native-user-udp-sdk33-root-integration-v1/promotion-v1.json`
has SHA256 `5ea08896ffb82f585bd1f9767a8848f86504daf3b5a6e0f7c71522232b57ab77`.
Its complete after inventories are the mandatory predecessor for further
integration; complete Kernel/OS backups and all failed attempts are retained.

Nineteen Kernel and 28 OS path changes preserve strict shared-musl builds,
the existing production PID1 supervisor, static UDP and pressure admission.
Twenty SDK producer invocations/exports and 20 actual user UDP QEMU consumers
passed. These used xmake `-b`; they are not described as forced fresh
recompilations. Ten standalone Kernel Debug boots passed. The final composed
SDK33 source passed 655 hosted tooling tests and fresh 20-profile QEMU matrices
for PID1 supervision, orphan adoption, and object pressure, plus 80 static UDP
scenarios in 20 profiles. All ten Release pressure rows use their separately
built, mode-matching static musl inputs. PPC uses the measured e500v2_v22 CPU;
ELF/CPU admission was not weakened.

Final offline-fsck failures now remain authoritative in both legacy PID1 and
adoption qualifiers. Two real x86_64 guests completed their lifecycle sequence,
then an injected final filesystem-check failure was correctly rejected; their
failed receipts, serial and disks are retained. Root audit SHA256 is
`ae9d7dcf603b6fd95ce2b7a75220e830be95a6250bfe820324855f24076f858a`.
This is a bounded polling native UDP path, not Linux sockets, IRQ networking,
TCP/IPv6, full M6 or full M7. Shared-libc target execution is still open.

A separate SDK33 service-graph composition preserves this OS564 predecessor
and adds 14 files plus four merged build/rootfs paths, producing OS578. Its
20 actual SDK33 QEMU consumers and 666 hosted tests passed; independent
integration review is pending, so it is not part of this accepted checkpoint.
The graph supports bounded simple/notify/oneshot readiness, dependency loss,
generation-aware restart, orphan reaping and ordered TERM/KILL handling. It
does not supply system accounts, persistent service configuration, installed
system daemons or durable shutdown.

The private allocator-backed 192-page mapping candidate passed its original
20 QEMU profiles. Independent review reproduced a `munmap` no-op failure under
metadata quota exhaustion; a retained repair is in progress. Its exported C++
layout changes require an SDK34 composition and new consumer qualification;
the older OS538 snapshot will not be promoted wholesale. Default root remains
a nonjournalled ext4 subset and the system desktop remains privileged.
M0-M12 is incomplete. M11 physical hardware and M12 manual desktop acceptance
remain user-deferred while implementation and automated acceptance continue.

## Earlier accepted shared-musl artifact checkpoint

At that checkpoint, the accepted isolated source was Kernel901 / OS556 / SDK32 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. The successor promotion
`build/prototypes/shared-musl-build-v1/promotion-v7.json` has SHA256
`6b3768b22bcc6a0ded7ccb4af97a4d8d7cce90a58774e976a3427203f4619e12`.
Its complete after inventories are the mandatory predecessor for further
integration. Complete source backups and earlier failures are retained.

Seven added OS files and one xmake contract change provide strict shared musl
1.2.5 builds. All ten architectures in Debug and Release passed 20 fresh xmake
artifact builds, and 637 hosted tooling methods passed. Independent review and
the root audit bind complete source, command logs, toolchain and runtime inputs,
artifact inventories and ELF identities. The root audit SHA256 is
`329f438b75703de9de3d7dacb0b6124e07aa0b58ccafd51de8e2621b5afaebbe`.
Kernel sources and SDK generation are unchanged; accepted PID1, pressure and
privileged static UDP additions remain present. This campaign did not execute
target code and does not establish an interpreter, file mappings, shared
applications, dlopen, TLS, pthreads or M5 completion.

Private SDK33 user UDP V3 passed 20 bound actual user QEMU runs and 20 successful
producer invocations/exports. Root serial/frame audit passed with 540 negative
controls. SDK33 composition must preserve the current OS556 and requalify its
inherited consumers; the older author OS541 is not accepted wholesale. Private
allocator-backed mapping and multi-service supervision implementation is active.
Exact continuation pins are in
`build/prototypes/shared-musl-build-v1/PRIVATE_PROGRESS_V8.md`.
M0-M12 remains incomplete. M11 physical hardware and M12 manual desktop
acceptance remain user-deferred while implementation and automation continue.

## Earlier accepted isolated SDK32 PID 1 supervisor checkpoint

The current accepted isolated source is Kernel901 / OS549 / SDK32 at
`build/prototypes/native-signal-actions-sdk29-v1/working`. Primary repository
sources remain separate. The one-shot promotion receipt is
`build/prototypes/native-pid1-supervisor-integration-v1/promotion-v1.json`, SHA256
`08456afbc1b265eb352136d5e65de4f1d4033e055440e259a316310ecf689cb9`.
It adds 13 OS files and changes five, preserving the SDK32-only pressure helper,
strict init observer and static UDP task. Complete backups and post-promotion
inventories passed; the previous accepted OS536 checkpoint is retained.

Final composed sources passed 630 hosted tool tests, 20 fresh ten-architecture
Debug/Release deterministic PID1 guests against exact current Kernel901 SDK32,
and three production x86_64 guests: Debug/Release shell restarts and repeated
missing-service exec diagnostics. The root strict audit rechecks every pinned
source, SDK, command, compiler input, serial, disk and ELF and rejects 80
observer controls. Its SHA256 is
`7b7f99d3407fe493d2c89cd0c2d1161033b30c1074c87264412c052ece2a11c1`.
The independent V8 review covers re-signed ELF-machine/word-limit mutations and
three hosted pending-TERM mask/launch controls. These rechecks are not extra
executions. Original V6/V7 failures and earlier Kernel896 SDK32 campaigns remain
separate evidence.

This is a bounded one-service static-musl supervisor, not complete M7.
Readiness/dependency graphs, accounts/login, persistent configuration, full
filesystem sync/quiesce shutdown, rescue and init-death recovery remain open.
The default root remains nonjournalled and both OS modes explicitly use pinned
Debug static musl. Private SDK33 user UDP and shared-musl artifact work continues;
neither is part of this accepted checkpoint. M11 physical hardware and M12
manual desktop acceptance stay open by user direction.

## Earlier accepted isolated SDK32 static IPv4/UDP checkpoint

The root integrated this bounded service into the accepted isolated consumer,
preserving the strict init observer and pressure-admission fixes. The complete
checkpoint is Kernel901 / OS536 / SDK32 at
`build/prototypes/native-signal-actions-sdk29-v1/working`; primary repository
sources remain separate. The one-shot promotion receipt is
`build/prototypes/native-static-ipv4-udp-integration-v1/promotion-v1.json`, SHA256
`5cb897a4175120820bff9e91dc74e0c3fa2d92dd88cd19af40c7128eb2a7c4fb`.
It applies eight OS additions and one xmake contract change, with complete
Kernel/OS backups and post-promotion inventories verified.

The root audit also rejects embedded carriage returns and unterminated serial
tails, for 15 negative controls total. Its rechecks and 80 image reconstructions
do not add new executions. A fresh final-source ASan/UBSan endpoint model passed
121,557 assertions and the xmake compile entry passed. LeakSanitizer is disabled
because of the sandbox ptrace restriction; the original failure is retained.
The isolated implementation is a privileged fixed-peer polling service. M6,
ordinary user socket integration and M12 remain open.

V6/V7 PID 1 candidates remain held for independently reproduced defects. The
accepted successor is V8 composed onto OS549, as recorded above. A separate
private SDK33 user UDP path has x86_64 native evidence and ongoing ownership
review; it has not been accepted or promoted.

## Original SDK32 static IPv4/UDP network prototype

An isolated OS candidate adds a boot-CPU-polling Virtio NIC service for one
statically configured ARP/IPv4/UDP peer. It consumes an explicit architecture-
and mode-specific SDK32 export; it does not include or build Kernel source.
The frozen 534-file OS candidate and the SDK32 producer matrix are retained
under `build/prototypes/native-static-ipv4-udp-v1` and
`build/prototypes/native-network-wire-v1` at the workspace root. The former
contains an English handoff with exact source, SDK, matrix and audit hashes.

The final consumer matrix passed 20 ten-architecture Debug/Release qualifiers
and 80 actual QEMU scenarios. An external QEMU peer verified 20 ARP replies,
1,940 UDP replies and 240 hostile packets without a reply. An independent strict
audit reconstructed all 80 images from retained ELFs, checked the full serial
and bidirectional frame evidence, and rejected 13 corrupted-evidence controls.
The hosted packet model separately passed 121,557 checks; the x86_64 Debug
xmake compile entry passed. These diagnostic profiles do not change the ordinary
four-architecture OS userland matrix. Earlier failed/diagnostic attempts remain
retained.

This candidate is not yet promoted into the main OS and Kernel trees, which
still require a controlled cumulative SDK integration. No socket API, general
IPv4/IPv6 host stack, IRQ networking, SMP, physical-machine or desktop-network
acceptance is claimed. M6 and M12 remain open. The user has deferred physical
M11 and manual M12 desktop acceptance; automatic acceptance continues.

## ABI 20 maintained ext4 timestamp integration

Shared Kernel SDK/native modules use generation 20 with native UAPI0.6.0.
Explicit maintained mounts of the clean nonjournalled ext4 subset update A/M/C
from one checked realtime sample per provider event. Encoding all affected records
precedes writes. Strict access errors publish no provider data, and uncertain
storage effects quarantine maintained metadata. The contract is
`ObfuscationKernel/docs/MAINTAINED_EXT4_TIMESTAMPS.md`.

The frozen776-file candidate passed20 Debug/Release rows and610 commands across
all ten profiles, retaining cumulative musl, storage, metadata, RTC and clock-set
gates. New SDK-only native fixtures cover120 ext4 geometry/architecture/mode
combinations. Twenty actual UID 1000 native-to-musl boots validate file operations,
automatic timestamp authority, denied clock setting and7 final raw nodes per boot.
Linux stat stays ENOSYS. All mutable input and output disk bytes are retained.

Six-layout hosted event/fault runs pass in normal and ASan/UBSan modes, including
four-extent growth/refusal boundaries and lossless reconstruction of cache and
durable images for injected read/write/flush faults. These are model results,
separate from real guest execution. LeakSanitizer was disabled. Independent review found and drove fixes for remove error masking,
unsupported access mutation flags and continued directory reads after failure.
Evidence validation additionally rejects unequal samples within one event.

Sixteen extra epoch0/2040 boots retain cumulative public-clock/mkdir coverage.
Fresh Linux readonly references check mounted metadata, directory creation and
21 exact maintained A/M/C fields on7 nodes, including new extra-isize16 at2040.
Linux binary provenance is pinned; full source-build provenance is not established.
A fresh shared x86 Debug producer and SDK-only consumer passes21 commands with
three rebuilt musl probes. The shared tool suite passes144 tests.

Initial parallel native lanes include three retained failures. One
explicitly reports a Virtio completion timeout; two generic fault assertions do
not establish their original error status. Exact-original AArch64 replays pass,
and final selected replacement lanes are rerun from identical frozen sources
with lower I/O concurrency. Failed attempts remain failures; no timeout policy
or acceptance assertion was relaxed. Receipts identify the selected lane set.

Default writable root policy remains unqualified. Existing inode extra extents
never grow; newly zeroed256-byte maintained inodes declare16 bytes. RAM/archive
and synthetic timestamps remain unavailable. No Linux stat, default-root adoption,
utimens, birthtime, journalled timestamp updates, power-loss atomicity, complete
ext4/POSIX, physical platform or SMP claim follows. Calls retain serialized
boot-CPU ownership. The ledger has90 requirements and163 tests; M0–M12 remains
open. Exact frozen/retry/model/Linux/review/export receipts are retained under
`/tmp/obfuscation-writable-timestamp-stage` and the workspace build directories
`workstation-abi20-maintained-ext4-v1` and `workstation-abi20-timestamps`.

## ABI 19 administrative realtime integration

Shared Kernel SDK/native modules now use generation 19 with native UAPI 0.6.0.
Native clock_settime (227) and 14 Linux setter forms across ten profiles share a
checked CLOCK_REALTIME operation. Explicit administrative software time retains
the physical boot-clock provenance and never writes the RTC or resets monotonic
time. The contract is `ObfuscationKernel/docs/REALTIME_SETTING.md`.

The frozen 759-file candidate passed **20 Debug/Release rows and 550 commands**.
The new gates comprise 20 privileged software-provenance diagnostics and 40
actual native/musl root or initial-UID 1000 fixture boots. Independent retained
serial audits checked 240 clock changes while waiters were blocked, 120 elapsed
wait instances, 80 exact wall/monotonic brackets and 56 raw setter-form records.
Relative sleep, absolute monotonic sleep, poll, select, ppoll and pselect preserve
their elapsed behavior across forward/backward wall changes. The fixture directly
observes sleep deadline/generation stability; poll/select deadlines remain
private and are covered by pending-syscall observations plus elapsed checks.
Root/fork/exec share the selected software clock; actual nonroot calls reject.

The cumulative suite retains 40 musl executions, 2680 storage cases, 328 mounted
metadata cases and 56 privileged RTC cases. **16 additional epoch0/2040 boots
and 32 cumulative musl executions** pass on the four qualified RTC profiles.
The native-created x86 image passes a fresh actual Linux readonly mount checking
19 nodes and four file payloads; two further Linux reference boots verify mounted
metadata. These runners now retain pre-guest and final disk bytes. That closes
the retention gap for this generation without retroactively qualifying missing
inputs from earlier generations. All disk, source, tool, SDK and probe identities
are bound to exact preserved artifacts; same-basename probe files cannot collide.

A further fresh shared x86_64 Debug producer and SDK-only consumer passed 18
commands, rebuilding both cumulative and clock musl probes and the native
launchers. Its two authority boots and privileged diagnostic are additional to
the frozen matrix. Hosted coordinator/adapter/empty-TLS tests, sanitizer runs,
all-ten target compiles, strict evidence parser tests and 136 OS tool tests are
separate from guest execution. A binary-pinned disposable Linux clock reference
checks root/UID 1000 validation ordering and elapsed arithmetic; the host clock
is untouched. Full Linux source provenance is not established by that hash.

The exact delivered SDK18 negative returns ENOSYS for native/Linux setters.
Earlier empty-PT_TLS exec failures remain preserved; the admitted empty segment
fix retains duplicate/range/alignment and nonempty-template rejection. Initial
cross-fixture host-toolchain failures and the MIPS64 long-double printf link
failure also remain preserved. Final probes use integer diagnostics; complete
printf/math support is not claimed. Independent representative i386/ppc/mips64
Debug gates passed before the final matrix, with a standalone cross toolchain.

Authority remains effective UID 0 or trusted kernel credentials, without Linux
CAP_SYS_TIME or user namespaces. Execution is the serialized boot-CPU main loop;
IRQ/NMI callers and secondary CPUs must not use this unsynchronized service.
No NTP, RTC calendar writes, absolute realtime timers, suspend/migration,
filesystem timestamp maintenance, Linux stat, general threads/signals, physical
platform or SMP qualification follows. The ledger has 88 requirements and 158
tests; it remains a seed inventory and every M0–M12 completion gate stays open.
Exact source, matrix, review, shared rebuild and SDK export receipts are retained
under `/tmp/obfuscation-clock-setting-stage`. Earlier delivery history follows.

## ABI 18 directory creation integration

Shared Kernel SDK/native modules now use generation18 with native UAPI0.5.0.
Linux mkdir/mkdirat use the common resolver, credentials and process creation
mask. The filesystem creation boundary accepts final mode and full UID/GID before
publication, returning a stable borrowed child. RAM and nonjournalled ext4 inherit
a setgid parent's group; directories also inherit setgid. Existing entries,
pathname copies, directory descriptors and duplicate/permission ordering have
explicit checked behavior. Readonly mounted metadata remains a separate provider.

The frozen739-file candidate passed **20 Debug/Release rows,470 commands and40
cumulative musl executions** across all ten profiles. Independent raw inode and
directory audits checked380 created/fixture nodes and80 new file payloads over
20 guest images (19 distinct nodes/four new files per boot). Another **16 fresh
epoch0/2040 boots and32 musl executions** on the four qualified RTC profiles
checked304 nodes/64 new payloads, alongside224 prior payloads. The previous2680
storage cases,328 mounted-metadata cases,56 privileged RTC cases and two Linux
mounted-metadata reference boots remain present. A further actual Linux guest
mounted the native-created image readonly, checked19 nodes/four files, and left
the disk unchanged. The Linux binary is pinned; full Linux source provenance
is not asserted.

A fresh shared x86_64 Debug Kernel producer, exact SDK-only OS consumer and musl
probe passed14 commands, two cumulative musl executions,19 node/four new payload
checks and14 prior file checks. This rebuild is additional to the frozen matrix.
All ten common/adapter models, all16 declared mkdir syscall forms, target
compiles and sanitizer checks pass. Six ext4 block/inode layouts cover3108
transport-fault scenarios and18 fsck-clean success/rollback images. Prior Linux
adapter regressions retain120 model-profile runs; these are hosted evidence.
ASan/UBSan ran with leak detection disabled because the sandbox uses ptrace.

Four earlier Debug prototypes passed56 commands/eight musl executions. The exact
ABI17 negative reaches ENOSYS at the first mkdir after passing public clocks.
The initial prototype failure was a host fixture parser rejecting debugfs's
signed rendering of a valid high GID; the corrected parser validates its range
before uint32 normalization. Those failed artifacts are retained. The mounted
model's initial wrong-fixture attempt and source/log-only legacy ext4 evidence
are also preserved. Pre-guest mutable disk bytes were not retained by the musl
runner, so recorded initial disk hashes cannot be independently replayed from
those final disks; retained final image bytes are independently verified.

This remains a bounded filesystem/ABI slice. Nonjournalled creation can fail
after correct-attribute publication; it does not promise crash atomicity or
all-errors rollback. Readonly providers currently report unsupported, without
an EROFS claim. The inherited allocator does not reconcile every corrupted
bitmap/count combination; a dedicated transport-fault trace for three-allocation
extent cleanup is still absent. ACLs, fsuid/fsgid, general limits, writable epoch
timestamps, Linux stat, threads/signals, SMP, physical platforms, networking and
isolated graphics remain open. The ledger contains86 requirements/152 tests;
M0–M12 are incomplete. Exact receipts and retained evidence live under
`obfuscation-linux-directory-create-stage`; earlier ABI17/16/14/13 history follows.

## ABI 17 checked public realtime integration

The shared source and matching SDK/native modules now use generation17 with
native UAPI0.5.0. Native and Linux clock_gettime/getres share a checked provider;
native legacy time/gettimeofday now use UNIX epoch time. Unavailable or invalid
sources return EIO before output. Native time checks register-width and errno
collision limits before optional copying; Linux time32/time64 layout and overflow
are explicit. Fork, exec and process switching preserve the one-shot RTC anchor.

The frozen R3 union passed **20 Debug/Release rows,470 producer/consumer commands
and40 cumulative musl executions** across all ten profiles. It also passed
**16 fresh epoch0/2040 boots and32 additional cumulative musl executions** on
AArch64/ARM32/RV64/RV32 in both modes. Default matrix clocks used leap-day2024.
Each boot includes native and musl parent, fork and exec checks;
protected-page copies, elapsed sleep, capability errors and legacy overflow are
checked. Independent retained-byte/UTC audits reread14 files per date boot and
verify exact SDK, source, direct tool, binary and serial identities.

All previous storage gates remain present:2680 earlier storage cases,328 mounted
metadata cases,56 privileged RTC cases and two actual Linux reference boots.
A forced shared x86_64 Debug producer/consumer and fresh musl build passed14
commands, two cumulative executions and14 offline file checks. These shared
checks are additional to the frozen matrix, not a replacement for it.

Positive realtime sources remain ARM32/AArch64/RV32/RV64. The six other profiles
explicitly refuse unavailable sources. musl time/gettimeofday ignore upstream
clock failures, so their wrappers are tested only after a successful realtime
preflight. Legacy-time32 musl clock_getres supplies an internal output even when
its caller passes NULL; that wrapper correctly returns EIO without an RTC, while
the raw NULL syscall remains identity-only. No source/calendar fallback is used.

The R2 i386 full-matrix attempt exposed an incorrect probe assumption about that
libc NULL behavior. Its failed row and cancelled remainder remain retained. R3
corrected only the probe and documentation; tested production inputs stayed
identical. The102 R2 hosted commands and ten target compiles were rehashed and
reused explicitly, not relabeled as new executions. Four corrected R3 prototypes
passed56 commands, and the exact ABI16 negative fails at the new realtime gate
after all earlier umask checks. R1/R2/component evidence remains separately bound.

The seed ledger has84 requirements and146 tests. General POSIX, writable epoch
timestamps, Linux stat, realtime clock setting/absolute timers, threads/signals,
SMP, physical UTC accuracy, networking and the isolated desktop remain open.
M0–M12 are incomplete. Final artifacts are retained under
`obfuscation-public-realtime-r3-stage`; earlier ABI16 history follows unchanged.

## ABI 16 directory, creation mask, mounted metadata and RTC integration

The shared source and matching SDK/native-module artifacts now use generation16;
native UAPI0.4.0 is unchanged. The frozen combined source passed **20 Debug/Release
rows,470 commands and40 cumulative musl executions** across all ten profiles.
Independent byte/identity audits verified **2,680 earlier storage cases,328
mounted-metadata cases,56 privileged RTC cases and two actual Linux reference
boots**. The four isolated build lanes used identical722-file frozen inputs.
A fresh shared x86_64 Debug producer, SDK consumer and musl rebuild passed14
commands and two cumulative executions, with14 independently reread disk files.

Bounded getdents64 uses real provider inode identities, explicit target-endian
records and retained shared directory cookies. Missing identities remain errors;
directory SEEK_END rejects. The process creation mask follows common resource
ownership through fork and exec; all eight new files per musl boot retain the
expected modes and existing-inode truncation preserves its original mode.
The isolated directory and umask components also passed their separate full
20-row/270-command/40-musl matrices; those artifacts remain generation-specific.

Mounted ext4 keeps namespace/data readonly and permits only trusted internal
metadata maintenance through its private retained transaction/session/cache.
Repeated inode changes, all qualified publication/flush cuts, recovery and Linux
interop are included. The shipped persistent invariant regression additionally
covers post-success generation exhaustion and stale/foreign authority. The
initial owned-regression run used an incompatible mounted fixture; its failure
is preserved, and the unchanged suite passed against its exact original fixture.

RTC/epoch diagnostics qualify selected ARM32/AArch64/RV32/RV64 sources and retain
explicit unavailable-source refusals elsewhere. Public realtime is still disabled
in ABI16. The live monotonic getres correction is included. Separate SDK17 public
clock development remains a candidate, never an ABI16 capability claim.

The seed ledger remains83 requirements and143 tests. M0–M12 remain incomplete:
general POSIX, Linux stat, namespace races, threads/signals, journalled default
root, SMP, physical hardware, networking and the isolated desktop remain open.
Qualification artifacts are retained under `obfuscation-abi16-integration`.

## ABI 14 positional I/O, select, file attributes and owned ext4 integration

This combined candidate uses **Kernel SDK/native extension ABI 14** and native
UAPI **0.4.0**. Exported operation arrays, wait records and filesystem attributes
require rebuilt extensions; provisional ABI14 candidates are distinct snapshots.
The shared source and exact producer/consumer artifacts now use ABI14.

Linux pread/pwrite uses retained common file descriptions without changing their
shared position. Target-width aligned offset pairs and MIPS stack arguments are
decoded explicitly. Linux O_APPEND uses a static policy; the native positional
policy is preserved. Transfers remain bounded to4096 bytes and signed native-word
offsets/endpoints; full off64 and arbitrary partial-copy semantics remain open.

Select/pselect shares the existing retained poll wait engine. It preserves target
word/endian fd sets, real oldselect signatures, bit counts across sets, ordered
copyout and timeout updates. Inputs are copied once and saved frames complete
once; exec/exit cancel retained registrations. The local descriptor capacity is32;
nonnull temporary signal masks, signals/restarts/cancellation, sockets and native
SMP are separate work. The cumulative musl suite now runs positional checks before
select, with separate diagnostic ranges and strict complete-run evidence parsing.

File attributes carry explicit validity and provider provenance. RAM nodes have
monotonic inode identities; retained provider identities map to anonymous device
minors. Real epoch timestamps are decoded only from admitted clean readonly ext4.
Writable/RAM/archive/pipe/console timestamps remain unavailable. Linux stat-family
success stays disabled because the current musl fallback would expose unavailable
fields. Native stat copies exactly its unchanged UAPI size using zero-initialized
field-by-field byte projection. Root reproduced and corrected unspecified padding
in the initial candidate, and corrected its stale module-generation constant.
The candidate's previous artifacts remain preserved separately.

The owned ext4 transaction privately retains the canonical cache and its exclusive
block session through publication and checkpoint. Reader admissions quiesce before
mutation; credits and generation advances are checked in advance. Sealed images
and durability authority cannot be supplied by callers. Failure quarantines the
owner without retry/close escape. Logical partition offsets are normalized once.
This is a bounded metadata transaction, not journalled mount admission or an
unrestricted filesystem/cache implementation.

The positional candidate passed ten Debug rows,140 commands and20 cumulative
musl executions with exact disk contents and an old-ABI ENOSYS control. Owned ext4
independently passed3,879 sanitizer checks,23 authority-corruption cases, two edge
cases, ten standalone boots,120 SDK-only native device cases and two Linux guest
interoperability boots. Candidate evidence does not qualify the combined source.

Combined preparation passed all-ten select, positional and poll sanitizer models,
ten freestanding adapter compiles, ten cumulative musl builds, six ext4 attribute
fixture combinations and110 OS tool regressions. Independent integration reviews
also exercised the exact-boundary native stat runtime and combined owner headers.
The exact-source Debug/Release matrix passed **20 rows /430 commands /40
cumulative musl executions /2,680 storage device cases**. It includes every
earlier journal/session/cache gate, all44 owned transaction cases and six
readonly attribute device cases per architecture/mode. Eighteen original rows
and two fresh complete Release rows are independently audited. The first
MIPS64 Release attempt timed out in a block-session fault probe; its partial
row and failure logs remain preserved and excluded. The fresh same-source
retry retained the exact runner and assertions.

After integration, a forced shared x86_64 Debug SDK, OS and musl rebuild
passed14 commands and two cumulative executions, with fresh offline byte
checks. Every shared build input matches the qualified frozen generation.
The qualification receipt is retained under `obfuscation-abi14-integration`.

The ledger now records **78 seed requirements and133 tests**. M0 and every complete
M1–M12 workstation milestone remain incomplete. Physical devices, SMP, general
threads/signals, full POSIX, networking and the isolated desktop are not implied.

## Prior ABI 13 poll, legacy open, canonical buffers and ARM32 integration

The combined source uses **Kernel SDK/native extension ABI 13**, with native
UAPI **0.4.0** unchanged. Added Linux operation arrays and typed poll completion
metadata require rebuilt native extensions. ARM32 now uses the explicitly
validated `arm32-linux-image` boot artifact at `0x40010000`. Earlier provisional
ABI 13 candidate artifacts are not interchangeable with this final source union;
all exported SDKs and consumers are rebuilt together.

Linux poll/ppoll/time64 freezes target-endian descriptor inputs, retains open
file descriptions and completes saved frames once. A static policy preserves
native pipe behavior while providing Linux EOF/error/normal-event semantics.
Raw ppoll remainder copyback uses full timespec endpoints separately from bounded
wait deadlines. Non-null signal masks remain unsupported after checked admission;
no signals, EINTR/restart, cancellation, sockets, select/epoll or native SMP claim.
Legacy open/creat adapts the six profiles defining those syscalls to the existing
checked openat service. Public musl open/creat uses openat on the remaining four.
Current-directory object identity, narrow scalar flags/modes, copy errors and
resource/large-file admission before create or truncate are retained.

Canonical MetadataBuffers privately owns an exclusive block session and admits
bounded 1/2/4 KiB immutable canonical blocks, read pins and discardable private
transaction copies. Complete participant reservation precedes edits. A reviewed
transfer-bound defect was fixed: incompatible block size rejects before I/O and
cleanly releases the healthy session. There is no commit, checkpoint, home
writeback, journalled mount or production cache/reclaim claim. Quarantine retains
backing; it does not establish asynchronous cancellation or DMA fencing.

ARM32 captures actual loader registers/state, rejects unsupported data endianness
before stack/BSS stores, and checks mode/MMU/cache/CPU state before FDT access.
The full FDT, boot prefix and complete linked image including NOLOAD are excluded
from allocation. Runtime frames use the existing 256 MiB supervisor aperture,
while upper firmware RAM remains represented. Seven profiles now support bounded
firmware-backed process frames; LoongArch64/MIPS/MIPS64 retain explicit linker
backing. Missing/bad ARM firmware fails without fallback. The 1024-frame global
and 128-page process limits remain; this is not general allocation or board support.

Independent candidates passed and were separately audited:

- Poll and legacy open each passed ten Debug rows, 140 commands and 20 actual
  cumulative musl executions. Older kernels fail at the first newly required
  call with ENOSYS. Independent reviews reran sanitizer suites and rehashed the
  source, SDKs, artifacts, logs and expected persisted bytes.
- Canonical buffers passed 320 sanitizer checks, 127 session regressions, ten
  freestanding compiles, ten standalone boots and 50 SDK-only native device
  cases. Every scratch disk remained byte-identical. The original transfer-bound
  reproducer now rejects open without quarantining the device.
- Final ARM source passed ten Debug rows plus ARM Release: 153 commands and
  22 cumulative musl executions, 38 firmware/page/frame probes, 27 Debug session
  device cases and nine startup negatives. Its earlier successful generation
  predates the endian correction and remains historical evidence only.

Combined host validation passed Linux poll/open and native poll sanitizers,
metadata/session checks, firmware normalization/frame checks, strict evidence
parsers and **108 OS tool tests**. The frozen combined Debug/Release matrix
passed **20 rows /390 commands /40 cumulative musl executions** under
`obfuscation-poll-cache-arm-integration`. Its independent audit and shared
x86 rebuild remain preserved as ABI13 evidence, separate from ABI14.
The shared working tree separately force-rebuilt its x86_64 Debug ABI13 SDK and
exact OS consumer in `build/workstation-abi13-shared-x86/run-v1`: **14 commands
passed**, including standalone boot, native execution, persistence and two
cumulative musl executions including legacy open and poll. An independent audit
rechecked its557 source inputs/archive, exact SDK/artifacts/logs, frame provenance,
all five stored probe files and fsck. All557 shared build inputs match the frozen
union; other shared architecture/mode artifacts have not been relabelled.

The ledger records **73 seed requirements and 121 tests**. These additions do
not close M0 or any complete M1–M12 workstation milestone.

## ABI 12 sleep and exclusive block-session integration

This qualified generation uses **Kernel SDK/native extension ABI 12**, with native
UAPI **0.4.0** unchanged. Added sleep operations change the exported ProfileData
array layout, requiring rebuilt extensions and explicit rejection of older SDKs.
Linux nanosleep, clock_nanosleep and monotonic clock_getres use target-endian
legacy/time64 records and the shared native deadline helper. Saved-frame
completion never rereads the request. Successful calls leave remainder memory
untouched. Signals, EINTR/restart, cancellation, absolute realtime and CPU clocks
remain unavailable; this does not satisfy complete clock/wait or POSIX semantics.

Kernel-owned BlockSessions adds bounded exclusive registration, partition views,
request ownership and dirty/unflushed accounting. Transport calls run outside the
metadata lock. Duplicate registration rejects before raw geometry queries,
including during initial admission and after quarantine. I/O/integrity/geometry
failure or dirty abandonment quarantines the device without a reset escape.
The boot owner must still withhold independent raw aliases. Canonical metadata
cache, journalled mount admission, asynchronous cancellation, DMA fencing, native
SMP and physical power-loss qualification remain separate work.

Independent sleep qualification passed ten Debug rows, 140 commands and 20 actual
musl executions, including legacy/time64 and unchanged-remainder probes. The old
ABI 11 kernel negative control stops at clock_getres with ENOSYS. Independent
review reran sanitizer adapter, native poll/deadline and supplemental saved-frame,
exec/exit and stale-generation tests without a remaining blocker. The block
session candidate passed 118 hosted checks, ten target compiles, ten standalone
boots and 78 native device cases; every write/flush fault was exercised on
x86_64 and PPC, with independent reservation/error review.

The shared working tree force-rebuilt its own x86_64 Debug ABI 12 SDK and exact
OS consumer in `build/workstation-abi12-shared-x86/run-v1`: **14 commands passed**,
including standalone boot, native simplefs/ext4 execution, persistence and two
cumulative musl executions including sleep. The independent receipt rechecks the
source archive, retained SDK, artifacts and logs, runtime frame provenance,
offline file bytes and fsck. This explicitly selected row does not qualify the
remaining architectures or Release mode.

The frozen combined source completed
`obfuscation-sleep-sessions-integration/ObfuscationOS/build/workstation-sleep-sessions/run-v1`:
**20 Debug/Release rows and 370 passing commands**, including **40 cumulative musl
executions**. Independent audits rehashed every source/archive, retained SDK,
primary/nested artifact and log, parsed actual musl/runtime-frame evidence, and
checked offline file bytes and fsck. Device cases include 60 replay, 60 preview,
380 recovery-completion, 540 transaction and 540 exclusive-session boots; every
write/flush fault point ran on every architecture/mode. All **541 shared source
files** matched this qualified snapshot before the next integration.

Combined hosted checks passed the sleep sanitizer suite, 118 block-session
checks and all-ten compiles, and 94 OS tool regressions. This generation's ledger
has **69 seed requirements and 113 tests**. QEMU completed-operation faults do
not establish physical power-loss durability, DMA fencing or native SMP.
M0 and all other workstation milestones remain incomplete.

## ABI 11 pipe/seek/metadata-writer integration

The shared combined source uses **Kernel SDK/native extension ABI 11**; native UAPI
remains **0.4.0**. Added Linux operations change the exported ProfileData arrays,
so the OS rejects ABI 10 and earlier artifacts and native extensions must rebuild.

Linux pipe/pipe2 now use the common native endpoints, with MIPS two-register
pipe returns, target-endian descriptor pairs, NONBLOCK/CLOEXEC, copied-output
rollback and reference lifetimes. Admission preserves flags, global ENFILE,
per-process EMFILE and output EFAULT precedence. SIGPIPE is not implemented;
readerless writes only return EPIPE. Linux lseek/_llseek use shared native file
positions, including signed-word/split-offset adaptation, MIPS stack argument,
unaligned endian result copyout and retained position after EFAULT. Actual 32-bit
positions remain capped at INT32_MAX; full off64 and DATA/HOLE are still open.

The bounded ext4 writer durably stages a checksum-v3 descriptor, two metadata
payloads and end sentinel, then commit, recovery flag and journal publication.
Only one ordinary inode's permissions, ownership, ctime and version may change.
Successful publication leaves home metadata old until separate recovery
completion checkpoints it. Exclusive quiescent device ownership remains a caller
precondition. Journalled mounts, allocation/data/directory writes, general cache
coherence and arbitrary torn-control reconstruction remain unavailable.

Corrected pipe and seek candidates each passed ten Debug rows, 140 commands and
20 musl executions with exact source/SDK/artifact audits. The writer candidate
passed 438 hosted cases, 210 completion regressions, ten target compiles and
standalone boots, 78 private-device cases and two Linux interoperability guests.
These isolated results do not substitute for combined-source qualification.

The frozen combined source completed
`obfuscation-pipe-seek-writer-integration/ObfuscationOS/build/workstation-pipe-seek-writer/run-v1`:
**20 Debug/Release rows and 350 passing commands**, including 40 complete musl
executions. Exact-source and deep audits rechecked the archive, every retained
SDK file, primary/nested artifacts and logs, runtime frames, offline ext4 bytes
and all device-case receipts. Every architecture/mode ran all writer and
completion fault points: 60 replay, 60 preview, 380 completion and 540 transaction
private-device boots. All 531 shared source files matched the qualified snapshot
before ABI 12 integration. These are completed-operation fault injections, not
physical power-loss or native SMP qualification.

Combined hosted gates passed all-ten pipe/seek sanitizers and target compiles,
process-resource regressions, 438 writer cases, 210 completion regressions,
ten musl probe builds and 93 OS tools. The ABI 11 ledger had **67 seed requirements
and 108 tests**; M0 and all other milestones remained incomplete.

The shared working tree also force-rebuilt its own x86_64 Debug ABI 11 SDK and
exact OS consumer under `build/workstation-abi11-shared-x86/run-v1`: 14 commands
passed, including standalone boot, OS userspace, persistence and both cumulative
pipe/seek musl runs. Its receipt rechecks all 531 captured source files, source
archive, retained SDK, artifacts and logs. Shared build artifacts now include
this current x86_64 Debug generation; staged matrix artifacts remain separate.

## ABI 10 runtime/storage integration

Kernel SDK/native extension ABI is **10**; native UAPI remains **0.4.0**.
The descriptor large-file admission field and atomic CLOEXEC duplication method
require rebuilt native extensions; the OS rejects ABI 9 and earlier SDKs.

The current combined source adds:

- Actual process allocation from qualified firmware frames on i386, x86_64,
  AArch64, RV32, RV64 and PPC. ARM32, LoongArch64, MIPS and MIPS64 retain explicitly
  labeled linker pools. Supported firmware discovery failures cannot silently
  fall back. Final linked images, including OS extensions/archive/NOLOAD, are
  excluded before allocation. Owner/generation handles and all shared/staged
  backing remain pinned until failed replacement tables are actually retired.
- Linux getcwd/chdir/fchdir/readlink/readlinkat and scalar dup/dup2/dup3/fcntl
  operations through common native objects. Linux scalar widths, per-descriptor
  CLOEXEC, shared offsets/status and large-file admission metadata are preserved.
  New probes execute real PROT_NONE buffer edges, fork/exec inheritance and
  descriptor exhaustion/reuse; offline descriptor-test bytes must be `abcdef!x`.
- Bounded ext4 recovery completion on an exclusive private device: validate the
  final view and allocated ordinary inodes, flush home writes, publish an empty
  journal, then clear the filesystem recovery flag and flush again. The admitted
  one-transaction 1 KiB profile remains narrow; no journalled mount or writer is
  enabled. Invalid torn checksummed metadata rejects before further mutation.

Independent stages passed ten Debug architecture rows each. Frame ownership
passed 80 commands and eleven actual startup rejection cases. Path and descriptor
stages each passed 140 commands with exact retained source/SDK/artifact/log hashes.
Completion passed 209 recovery/fault cases plus one inode-budget case, 410 existing
preview regressions, ten target compiles, ten standalone boots, 62 private-device
recovery boots and two Linux guest interoperability boots. Linux independently
recovers the original dirty image; our completed image is readable on a readonly
Linux device and remains byte-identical. The journal sequence is 4 for the pinned
sequence-2 fixture. QEMU completed-operation fault injection is not physical
power-loss qualification.

Independent reviews found no remaining blocker in these bounded contracts.
The completion review corrected overly broad unchanged-bitmap target admission.
The path follow-up now explicitly tests permission-denied cwd changes and an
unlinked cwd. Combined hosted checks passed both VM backing modes, frame registry,
Linux runtime/poll/path/descriptor adapters, 210 completion cases and 91 OS tools.
The contract ledger now contains **63 seed requirements and 100 tests**; its
schema validates, while the complete normative inventory and M0 remain open.

The ABI 10 combined source completed `build/workstation-runtime-completion/run-v1`:
**20 Debug/Release rows and 330 passing commands**. Its `verified-summary.json`
rechecks the source archive, every retained SDK file, primary artifacts and logs
against the source before ABI 11 integration. Every recovery write/flush point
ran on each profile/mode, totaling 380 private-device completion boots. The 1024-frame global/128-page process and 32-fd limits
remain. General allocation, threads/signals, complete POSIX, journal writer,
network/services, isolated graphics, SMP and physical workstation gates remain
unfinished. No M0–M12 milestone is complete. Separate pipe/seek and journal-writer
candidates are still outside this shared integration.

## ABI 9 integration: completed qualification

Kernel SDK/native extension ABI is **9**; native UAPI is **0.4.0**. The new
fallible VFS metadata/lookup slots require rebuilding every native extension.
The OS validator rejects ABI 8 and earlier. UAPI 0.4 adds the native `MAP_FIXED`
flag without renumbering existing syscalls.

Integrated typed captured-firmware discovery, checked VFS resolver/open metadata
and lookup, consuming `PathReference::release()` with explicit open cleanup,
actual mapped `brk` and private-anonymous fixed replacement, and read-only
device-derived ext4 internal-journal binding. No journalled mount gate was
relaxed. Firmware discovery still does not enable a native allocator. Other VFS
metadata callers and complete Linux process/thread semantics remain work.

The canonical musl probe now executes heap allocation, zeroing, alignment,
replacement, reuse and exhaustion/recovery. All ten applications use
`-fno-builtin`: a retained PowerPC negative control demonstrates that Clang 18
otherwise removes a malloc pressure loop and folds its errno test. This was a
probe compiler issue; libc is unchanged. `--musl-heap` and
`--jbd2-runtime-binding` select the new gates in the workstation qualifier.
The integrated hosted checks passed VM/runtime/path sanitizers, all-ten path
ownership and Linux adapter compilation, 418 ext4 binding cases, 84 OS tool
tests, 29 QEMU runner tests, and ten actual standalone firmware probes.
`build/workstation-abi9/run-v2` passed all ten Debug rows. Its first Release
build stopped on a GCC 14.2.0 internal compiler error in `kernel_syscalls.cpp`;
the compiler crash and logs are retained, and its cause is not established.
`run-v3-release` passed all ten Release rows with an identical source-hash
snapshot. The combined result is **20 rows and 290 passing commands**;
`build/workstation-abi9/abi9-exact-source-summary.json` records verification of
source archives, retained SDK contents, primary artifacts and log hashes.
The first attempt
stopped during compilation on a preserved debug
assertion still naming UAPI minor 3; it was updated to 4 before the fresh run.
The completed Debug rows retain exact ABI 9 SDKs, source archives and all guest
inputs. Staged results do not qualify later combined source.

The next batch has integrated Linux identity/fork/exec/wait including RV32's
musl waitid path, qualified firmware RAM normalization, entry-to-runtime frame
ownership probes, checked POSIX/VFS and executable-load callers, and a read-only
journal replay view. Independent review added a hard-link destination lookup
guard, corrected Linux leader identity/LP64 wait scalars, and retired ext4 views
on dangling selected directory targets or any underlying reader failure.
These follow-up changes are separate from the preceding ABI 9 baseline matrix.
`build/workstation-process-preview/run-v1` completed all ten Debug/Release rows: **20 rows / 310 commands**. Its `verified-summary.json` rechecks the source archive,
all retained SDK contents, primary artifacts and logs against that exact source.
Thirteen integrated host/build/tool checks passed, including 410 ext4 preview
cases, the normalization oracle, native VM rollback and checked exec cleanup.
An old runtime test expected native TID from Linux set_tid_address; it now checks
the admitted Linux leader PID. ASan/UBSan remain enabled; LeakSanitizer cannot
run under this ptrace environment and is explicitly disabled. They add no existing object
layout or virtual-slot changes, so SDK ABI 9 and UAPI 0.4.0 remain unchanged.
No M0–M12 milestone is complete.

The subsequently integrated process-frame, recovery-completion, pathname and
descriptor work is described in the ABI 10 section above; this completed ABI 9
result does not qualify that later source.

## ABI 8 boot/file/replay: completed qualification

Kernel SDK/native extension ABI is **8**; native UAPI remains **0.3.0**.
Implemented Linux openat with architecture-specific flags/errno, bounded checked
pathname copies, pre-mutation descriptor admission, append read/write behavior,
and 32-bit large-file policy. Linux fsync/fdatasync share the native node sync
path. Existing tests remain intact; all-ten adapter/open/sync models and process
resource ASan/UBSan pass. OS tool regressions pass **83 tests**.

Virtio now uses an exported monotonic-clock deadline instead of a CPU iteration
count. All ten staged driver probes passed ordinary read/write/flush/ring wrap,
reopen, readonly, injected read error/recovery, absence, healthy delayed I/O and
elapsed-time timeout with queue retirement. The independent healthy-device
failure establishes the old polling defect; it does not identify either
historical ext4 failure's exact first operation.

JBD2 supports an explicit caller-qualified Linux internal-journal tag UUID form,
while default strict tag checks and superblock/checksum identity remain intact.
All ten staged Debug guests replayed a Linux-created dirty journal through real
Virtio and reopened it in a fresh VM; an exported ABI 7 x86_64 pilot also passed.
This preserves the dirty journal/recovery flag and does not enable journalled
mounts, checkpointing or a journal writer.

The exported-SDK x86_64 musl pilot executed two complete file/sync probes with
native parent exec/wait/exit checks and a following shell pipeline; offline
stored bytes were `abcdef` and e2fsck passed. ABI 7 `run-v1` stopped at MIPS64
with a stale incremental `posix.cpp.o`: disassembly returned the old overflow
status although the source returned the new descriptor-limit status. Source
copies had preserved mtimes, and incremental compilation reused the old object.
That run is a failed mixed-build attempt, not exact-source qualification.
A cache-disabled full rebuild passed the same MIPS64 file/sync guest and offline
checks; exact old/fresh objects and logs remain preserved.

ABI 8 adds owned raw boot-register capture on all ten entry paths and the bounded
BIOS E820 collector/parser. Eighteen isolated verification commands passed,
including all ten native profiles, x86 poisoned tables, selected kernel-fault
variants, and hosted E820 ASan/UBSan. Capture does not enable firmware allocation.
Pathname truncate now preserves a release-time I/O failure after successful
truncation and retains the original error when truncation itself fails. Hosted
1/2/4 KiB ext4 validation passed 303 clean sequences, 126 single I/O faults and
three dual-fault priority cases. This does not identify the original historical
LoongArch failure.

The forced ABI 8 `run-v2-abi8` passed seven complete Debug rows, then the
ARM32 standalone harness lost a prefetched completion marker by combining
`select()` with buffered `readline()`. The unchanged retained image passes an
unbuffered binary reader. A two-line child independently reproduces the reader
bug; the repaired transport and preserved QEMU/window tests pass 29 cases.
The failed run and exact ARM32 SDK/raw serial remain retained.

`run-v3-abi8-debug-tail` passed ARM32/RV64/RV32, followed by
`run-v3-abi8-release` passing all ten Release profiles. Each row retains its own
source archive and runner revision. Only the standalone reader and its tests
changed from run-v2; production Kernel/OS sources did not change. All compiled
Kernel/OS images and musl runners are forcibly rebuilt with compiler cache
disabled. The qualifier retains source, build policy, completed SDK/artifact
rows and logs itself. Collective qualification is complete: **20 rows and 290
passing commands**. `build/workstation-files-replay/abi8-equivalent-production-summary.json`
records the exact two runner/test differences. Source archives, logs, primary
artifacts and all retained SDK contents were rehashed. These are equivalent
production-source results with two declared harness revisions, not a claim that
every byte of the harness was identical.

The following changes were independently staged and subsequently integrated as
ABI 9; they are not part of this ABI 8 qualification:
typed captured-firmware discovery; checked VFS metadata/lookup and consuming
path cleanup; actual mapped brk/fixed anonymous replacement with musl heap
pressure tests; and runtime on-device ext4 internal-journal binding. Their
hosted/build/native evidence remains separate until explicit integration.

## ABI 6 bootstrap history

This historical batch used Kernel SDK/native extension ABI **6**, and native UAPI is **0.3.0**. The
ABI 5 clock/ext4 batch below completed its full ten-profile debug/release matrix.
ABI 6 adds per-image native/Linux personality, Linux auxv and bounded adapter
dispatch, plus best-effort child-tid clearing before teardown. Its native musl
guest acceptance passed x86_64, i386, MIPS, AArch64, ARM32, RV64 and RV32
Debug rows in `build/workstation-linux-bootstrap/run-v2`. That attempt then
failed on the LoongArch64 musl probe; the standalone/native gates for that
profile had passed. The full ABI 6 debug/release matrix remains incomplete;
the ABI 5 result does not qualify changed ABI 6 source. Clear-tid does not implement
futex wake or thread join semantics.

`scripts/test_musl_userland.py` stages an explicit hashed bootstrap ELF and a
native parent runner in an isolated ext4 rootfs. Its acceptance requires two actual
musl startup/TLS/errno/monotonic-clock runs, native parent exec/wait/exit checks
and a subsequent native shell pipeline. Initial `run-v1` correctly failed because
the simplefs disk did not publish appended probes into the embedded-archive
namespace. `run-v2` uses ext4 for the musl lane and keeps simplefs/archive native
regression. Failed attempts remain recorded. An available runner is not a pass.

The LoongArch64 failure was an unoptimized libc LL/SC loop in first-clock
initialization: the exact probe also times out in QEMU Linux user emulation.
An optimized musl build passes both that emulator and the actual OS ext4 guest
with repeated exec/wait/exit. The recipe now uses `-O2` in both modes, with `-g`
for Debug. New all-ten artifacts and final qualification must use that corrected
recipe. [The diagnosis](contracts/LOONGARCH_MUSL_ATOMICS.md) preserves the
failure, CPU samples and successful comparison without attributing Linux-user
emulation to native Kernel execution.

The corrected v6 musl artifacts now exist for all ten profiles. Independent
manifest/compiler/ELF/TLS inspection passed; that inspection is not guest execution.
`run-v3` passed MIPS64 and PowerPC Debug, then stopped at a LoongArch native
ext4 pathname-truncate assertion before its musl lane. The old harness deleted
the actual temporary guest disk; the preserved packaging image is explicitly
not a failure-disk capture. Twenty subsequent clean scratch boots passed, so
the original cause remains undetermined. Failure diagnostics now emit errno and
preserve the actual mutated guest disk, command and hashes via `--failure-dir`.
`run-v4` stopped at an i386 native-ext4 open returning EIO; its actual scratch
disk was preserved and passed readonly e2fsck. It is not a complete matrix.
Its completed rows and preserved SDK/source/artifact copies are under
`build/workstation-linux-bootstrap/run-v4`. An in-progress run is not a full pass.

A separate staged driver experiment reproduces fixed-iteration Virtio timeout
on a healthy QEMU disk limited to one I/O per second. A clock-deadline candidate
passes delayed completion and actual elapsed-time timeout/queue-retirement
checks on LoongArch. This finding does not identify the original truncate
failure, and the candidate is not part of the frozen ABI 6 qualification.

Hosted tests now cover actual image loading with mapped-copy mocks, maximum
argv/envp, auxv pointers, exec rollback, result selection and exit child-tid
clearing. ASan/UBSan, the ten-profile process-resource/readiness models and 79 OS
tool tests pass. Bootstrap stdout/stderr now correctly report O_WRONLY through
F_GETFL. Linux scalar I/O checks descriptor access before copying; set_tid_address
records an arbitrary pointer without dereferencing it, matching Linux behavior.

## ABI 5 clock/ext4: completed qualification

Implemented in this batch:

- Calibrated architecture-selected monotonic clocks on all ten retained profiles;
  native relative/absolute sleep with copied requests and deadline completion.
  `/init` exercises a sole sleeper; child/parent tests exchange timestamps to
  check progress inside the sleeping child's interval.
- Descriptor-shared NONBLOCK/APPEND flags, atomic pipe2 flags, pipe readiness,
  retained description pins, and bounded native poll with finite/infinite waits.
  Requests are frozen and pins are released on completion/teardown. Console input
  remains owned by the native input loop. Signals, select/pselect/ppoll, socket
  events, general wait queues and SMP synchronization remain unfinished.
- Native tasks now run through the console/GUI service loop from startup, so a
  live sleeper or persistent background task does not prevent console service.
- ext4 fast and one-block symlinks, malformed-layout rejection, failure-atomic
  creation and retained unlink/replacement. The native shell has `ln -s`; restart
  acceptance checks both relative and absolute links against offline debugfs.
- ELF load segments stream from the retained executable after prefix/header
  validation. Large debug files no longer exceed a whole-file bootstrap buffer;
  unsupported dynamic images are rejected explicitly.
- Independent Linux ABI codecs and saved-frame adapters cover ten profiles,
  endian/word-width handling, time32/time64, bounded MIPS stack arguments and
  MIPS/PowerPC error conventions. Static ELF PHDR/TLS admission and auxv encoding
  plus a bounded syscall adapter now have separate hosted/build tests. They were
  independent of ABI 5 native execution; ABI 6 integration is described above.

The native VM still uses the linker-reserved page arena. Independent firmware
memory parsing and JBD2 replay planning now exist; native firmware handoff,
allocator integration, journal replay, static musl execution, services/network
and isolated graphics remain open work. See Kernel [native waits](../../../ObfuscationKernel/docs/NATIVE_WAITS.md),
[platform clocks](../../../ObfuscationKernel/docs/PLATFORM_CLOCKS.md),
[path resolution](../../../ObfuscationKernel/docs/PATH_RESOLUTION.md) and
[Linux codecs](../../../ObfuscationKernel/docs/abi/linux-user-codecs.md) for exact
contracts and restrictions. These changes do not complete M1, M2 or M3.

The final `run-20260920T202929Z` under `build/workstation-clock-ext4/` passed all
**230 steps**. All ten profiles passed debug/release native simplefs, native
ext4 and ext4 sync/restart acceptance, together with SDK/OS packaging, UAPI and
libc checks. All ten debug profiles also passed standalone Kernel QEMU tests.
This includes native wait/time and ext4 symlink behavior; it does not exercise a
Linux personality, journal crash recovery, physical hardware or SMP.

`abi5-matrix-summary.json` records the exact commands and 230 verified log hashes.
`abi5-artifacts.json` captures 100 input/output artifact hashes;
`abi5-sdk-manifests/` preserves all 20 architecture/mode SDK manifests; and
`abi5-source-before-linux.json` pins the source before ABI 6 changes. Later
rebuilds may replace ordinary build paths, so use these preserved records to
identify the qualified snapshot. Earlier failed attempts remain in the same
evidence root. No ABI 5 execution claim is carried over to ABI 6.

## Independent foundations and musl build evidence

The current source ledger contains **50 seed requirements and 73 tests**. The
new foundations remain `model-only`, while complete Linux ABI/static-musl
requirements remain planned. The source ledger has no execution receipts;
available entrypoints and artifact inspection do not establish a verified gate.

| Foundation | Implemented scope and recorded validation | Remaining integration |
| --- | --- | --- |
| Linux ABI/frame bridge | All-ten hosted codec/frame checks; ASan/UBSan; isolated freestanding frame builds; pinned Linux 6.13.4/musl 1.2.5 definitions and save/restore source anchors | ABI 6 native dispatch qualification; complete syscall/structure/flags/errno coverage |
| Static ELF/auxv | Exact static ET_EXEC prefix, readable PHDR and initialized TLS mapping; target-width/endian auxv; all-ten hosted, sanitizer and isolated target checks | ABI 6 stack/entry qualification, TLS runtime and qualified entropy |
| Linux bootstrap adapter | Bounded I/O/VM, monotonic time, TLS and tid registration delegated through checked copies; hosted x86/i386/MIPS cases; all-ten target compilation | ABI 6 native guest acceptance, complete tid wake/join lifetime and broader semantics |
| Firmware parser | Bounded FDT RAM/reservation parsing; hostile-input and unchanged-output failures; sanitizer, six explicit QEMU DTB audits and isolated ten-target compilation | Actual boot arguments, full-map/capacity policy and allocator ownership |
| JBD2 plan | Checksum-v3, committed ordered actions, revoke filtering and wrap; synthetic fixture checked against e2fsprogs CRC32C; GCC/Clang and sanitizer runs | Replay writes/durability, mount admission and Linux crash interoperability |
| JBD2 executor | Private plan/scratch, validated contiguous journal mapping, journal exclusion, ordered BlockDevice reads/writes and flush; 1/2/4 KiB exact-byte and partial-write/flush/crash models, sanitizer and all-ten target compilation | Filesystem-derived admission, checkpoint/clean-state protocol, actual guest replay and Linux/e2fsck interoperability |

Kernel reproduction entrypoints are `scripts/test_linux_user_abi.py`,
`scripts/test_linux_native_bridge.py`, `scripts/test_linux_exec.py`,
`scripts/test_linux_bootstrap.py`, `scripts/test_native_poll.py`,
`scripts/test_linux_runtime.py`, `scripts/test_fdt_memory.py`, `scripts/test_jbd2.py`
and `scripts/test_jbd2_replay.py`. The bridge/exec/replay runners
use `--cross`; the bootstrap runner is itself compile-only. These tests are
independent of the native qualification matrix. The FDT audit records missing
ARM32 direct-ELF DTB handoff and malformed QEMU 8.2.2 LoongArch memory cells;
neither is accepted as a valid physical memory map.

All ten explicit musl 1.2.5 `build/musl-bootstrap-v4/<arch>/bootstrap.elf` files
now link and have inspected readable PHDR/TLS mappings, non-executable GNU_STACK
and explicit Linux ELF identity. The PowerPC C application uses Clang 18 with
the Linux musl target and retained musl startup/libc/cross-linker; the native
Kernel SDK compiler remains unchanged. This resolves the earlier ordinary-main
link blocker for this probe and corrects the initially unmapped PHDR layouts.
The original nine-profile GCC success and PowerPC GCC failure remain historical
results, not the current bootstrap build count.

Every v4 manifest remains **built-not-executed**. The
[exact artifact audit](contracts/MUSL_BOOTSTRAP_BUILD_AUDIT.json) verifies all ten
manifest/ELF/source/tool identities and records decoded layout and command-log
hashes. It is a read-only inspection of local builds, not native musl execution,
full compiler ABI qualification or completion of M3/L01. See the
[contract ledger guide](contracts/README.md) for the bounded test contracts.

## ABI 4 foundation: historical implemented slices

| Work | Behavior now implemented | Remaining gate |
| --- | --- | --- |
| M0 contract/evidence tooling | Versioned requirement/test/reference schema, all ten native/Linux ABI tuples, dependency/evidence validation, generated capability report, strict SDK generation 4, pinned musl source audit | Full clause/interface/utility/option inventories, qualified Linux ABI layouts and complete dependency/reference pins |
| P02 allocator foundation | Reserved regions override usable ranges; sparse/overlapping RAM accounting; bounded capacity failure; owner/generation handles and stale-release rejection; explicit fallible kernel allocation contract | Firmware RAM/reservations, general object allocation, quotas/reclaim and SMP lifetime rules; the boot diagnostic map remains synthetic |
| P08 pathname foundation | One object/mount resolver for POSIX and native exec; search checks for each component; retained cwd/dirfd after rename/cover; bounded RAM symlinks; follow/no-follow/exclusive creation and retained new objects | ext4 symlink format, larger paths/pools, general mount/dentry lifetimes, supplementary groups, full metadata and concurrent permission semantics |
| P03 native anonymous VM | Real anonymous private mmap, mprotect and partial munmap; zero-fill; inaccessible-page backing retention; eager fork; transactional mapping replacement and failure rollback | General allocators, shared/file mappings, brk, COW, faults/demand paging, SMP shootdown and complete mmap flags/protections |
| L00 source/build spike | Exact musl 1.2.5 archive/content hash, all ten source ports audited, explicit cross-build recipe, static libc/probe artifacts isolated from the native sysroot | Correct Linux personality, auxv/TLS/threads/signals/futexes and actual musl execution; bare-metal compiler success alone is not ABI qualification |

The native VM uses the existing linker-reserved 1024-page arena, with 128 pages
and 16 coalesced areas per process, plus a spare backend address-space slot for
replacement. It does not allocate from the synthetic boot memory map.
Supported protections are NONE, READ and READ|WRITE. The retained MIPS CPUs
still lack hardware execute-inhibit support. The new frame allocator remains a
separate, bounded ownership bookkeeping component.

The source descriptions are in Kernel [pathname resolution](../../../ObfuscationKernel/docs/PATH_RESOLUTION.md),
[native VM](../../../ObfuscationKernel/docs/NATIVE_VM.md) and
[allocation contract](../../../ObfuscationKernel/docs/DEVELOPMENT.md).
The historical public native UAPI was 0.2.0; existing syscall numbers/layouts remained,
with added symlink/readlink calls. Native extension/SDK ABI 4 rejects older SDKs.
The native personality continues to use project syscall numbering on all CPUs;
this is not a Linux ABI declaration.

At that foundation snapshot the contract ledger had 43 seed requirements and
50 planned/available tests. musl static libc and an ordinary probe ELF built on
nine profiles; no musl program executed. The retained PowerPC bare-metal compiler injects
`__eabi` even with Linux/no-EABI command-line options. Its separately documented
[compiler startup blocker](contracts/PPC_MUSL_BLOCKER.md) requires a Linux-targeted
user compiler; it does not remove PowerPC from the native OS matrix. Two isolated
x86_64 musl builds matched all 234 installed/probe file hashes.

## ABI 4 foundation: historical validation and evidence

Qualification on 2026-09-20 independently built the Kernel, exported its exact
architecture/mode SDK, validated the OS consumer, built sysroot/apps/rootfs and
executed guest tests. All 20 architecture/mode combinations passed:

| Architecture | Debug native: simplefs / ext4 | Release native: simplefs / ext4 | ext4 sync/restart/e2fsck: debug / release |
| --- | --- | --- | --- |
| i386 | pass / pass | pass / pass | pass / pass |
| x86_64 | pass / pass | pass / pass | pass / pass |
| aarch64 | pass / pass | pass / pass | pass / pass |
| arm32 | pass / pass | pass / pass | pass / pass |
| rv64 | pass / pass | pass / pass | pass / pass |
| rv32 | pass / pass | pass / pass | pass / pass |
| loongarch64 | pass / pass | pass / pass | pass / pass |
| mips | pass / pass | pass / pass | pass / pass |
| mips64 | pass / pass | pass / pass | pass / pass |
| ppc | pass / pass | pass / pass | pass / pass |

Standalone debug Kernel QEMU gates passed on all ten profiles. Each mode also
passed UAPI validation, native libc checks and rootfs packaging. The host checks
passed 73 OS Python tool tests, 25 Kernel QEMU harness tests, all-ten-profile
process-resource models, VFS/archive/kernel-service tests, ext4 mutation/reopen
tests, and allocator/native-VM transaction checks under ASan/UBSan. Leak detection
was disabled for the sandboxed sanitizer runs; VM sanitization excludes unrelated
virtual-device vptr instrumentation.

Logs and command/hash records are in `build/workstation-foundation/results.json`;
raw logs and scratch ext4 restart images live alongside it. The final qualification
summary is `matrix-summary.json`, with SDK/image/rootfs hashes in
`native-artifacts.json`. `final-source-hashes.json` identifies the build-source
snapshot; later documentation edits do not alter that source evidence. The early
i386/MIPS/AArch64/ARM32/RV64 debug builds passed a separate recorded refresh
against the final `statat` flag validation and VFS interface comment, checking
unchanged linked app/boot-archive/rootfs hashes. The first refresh stopped on an
overly strict intermediate-libc-archive hash check after all i386 execution gates
passed: this xmake configuration can rebuild dependencies despite `--shallow`.
Its recorded follow-up verifies that the actual reused executable/disk inputs
were unchanged. The remaining refresh permits re-archiving intermediate libraries
while retaining those executable/disk checks. These generated artifacts are local
and unversioned.

`ledger.evidence.json` overlays the source ledger with 66 hash-checked execution
records, including the incomplete musl cross-build result. The final SDK/image/
rootfs manifest covers 100 artifacts; all 20 SDKs match current exported headers
and the required compiler identities. This does not promote partial requirements
or waive missing gates:

```sh
python3 tools/plan_ledger.py validate \
  --manifest=build/workstation-foundation/ledger.evidence.json \
  --evidence-root=build/workstation-foundation
```

The hosted suites separately exercise namespace/state behavior, allocator
bookkeeping and VM transactions with injected pool/table/retirement failures.
ASan/UBSan runs do not turn these into hardware tests. QEMU native acceptance
executes user instructions and syscalls; it still does not qualify physical
machines or SMP.

The new required guest markers are:

```text
OK_VM_NATIVE scope=hardware map=pass zero=pass protect=pass unmap=pass fork=pass pressure=pass
OK_PATH scope=hardware relative_exec=pass symlink=pass
```

The ext4 lane requires the same relative-exec and memory tests but reports
`symlink=unsupported-filesystem`. That limitation is permitted only in the
explicit ext4-subset lane; a RAM-root run missing symlink coverage fails.
Release images run `posix-check` through the serial shell. Persistence tests
write/rename/link/sync, restart the guest and run host e2fsck/debugfs against
scratch images. They test the current non-journalled ext4 subset, not JBD2 crash
recovery.

## Reproduction

From the Kernel repository, select the target/mode and explicit toolchain, then
build `kernel-sdk`; in debug also run `xmake qemu-test`. From the OS repository,
select the same target/mode/toolchain and build `distro_image`, `uapi-test`,
`libc-test`, `rootfs-simplefs` and `rootfs-ext4`. The OS build consumes SDK
artifacts only. Debug guest acceptance uses:

```sh
xmake qemu-distro --fs=simplefs --require-native --timeout=100
xmake qemu-distro --fs=ext4 --require-native --timeout=100
```

Release shell acceptance uses `scripts/test_interactive_userland.py` with
explicit `--arch`, `--qemu`, `--kernel`, `--rootfs`, `--log` and `--posix-check`.
The separate `scripts/test_persistent_ext4.py` uses explicit images and output
paths and never operates on an installed disk.

Contract validation/reporting is available through `xmake plan-check` and
`xmake plan-report`. `tools/plan_ledger.py gate-m0` deliberately fails until a
complete normative inventory replaces this seed schema. An accepted schema or
an artifact hash is not a completed requirement.

## Remaining dependency work

Finish the M0 clause/option inventories and remaining per-architecture Linux ABI
layouts; connect real boot RAM/reservations to allocator ownership; qualify the
ABI 6 Linux bootstrap changes and thread/TLS/signal lifetimes. The existing
FDT parser does not complete native memory handoff. Storage recovery must build
on the independent JBD2 parser/plan with safe replay writes, durability and real
crash fixtures before any journalled writer is enabled. Real network services and the
isolated Wayland desktop remain later work, with existing rescue paths retained.

The P04 clock/sleep/poll implementation above replaces the foundation's nominal
trap-count clock. Full event waits, signal interruption and Linux time64 execution
remain separate acceptance gates. No physical-hardware or SMP result is inferred
from the QEMU or hosted test results.

## Earlier private V6 artifact and UDP preparation update

Accepted source remains Kernel901 / OS549 / SDK32 with predecessor promotion
`08456afbc1b265eb352136d5e65de4f1d4033e055440e259a316310ecf689cb9`.
No successor was promoted. Shared-musl V6 is composed on OS549 (553 files) and
passed 635 hosted tool tests. Its strict Debug/Release ten-architecture xmake
artifact campaign has 10 passes and 10 preserved failures. MIPS32 Debug later
passed a fresh full shared-libc build using the V3 Linux-assembler PIC runtime.
RISC-V/LoongArch PIC helpers and PPC secure-PLT runtime still need final artifact
qualification. These artifacts are not native dynamic-loader/TLS/pthread execution.
See `build/prototypes/shared-musl-build-v1/PRIVATE_PROGRESS_V7.md` for exact receipts.

Independent UDP V2 lifetime repair review passed. Private V3 is preparing a
frozen, mode/architecture-bound twenty-case actual user UDP QEMU campaign.
Current accepted SDK remains32. M0-M12 is incomplete; physical and manual
acceptance remain user-deferred.
