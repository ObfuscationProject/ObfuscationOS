# M0-M12 implementation status

Reviewed on 2026-10-17 against the [milestone exit gates](README.md#6-milestones-and-executable-exit-gates).
All thirteen complete milestone gates remain open. Useful implementation and
bounded execution evidence exist across several milestones; neither test counts
nor a list of API names measures completion of the full workstation target.
M11 physical-reference-machine testing and M12 manual desktop acceptance remain
explicitly user-deferred. Their software requirements remain in scope.

The current ledger validator accepts 95 requirements and 175 test definitions
across all ten profiles. Eleven admitted historical console-evidence entries
now include nine host/model/tool records and two actual x86_64 Debug/Release
guest records. The separate read-only receipt admission checks 24,340 immutable
qualification inputs and the promoted rollout relationships. This bounded
integration does not close the seed ledger, normative source indexes or any
complete milestone gate.

| Milestone | Current implementation | Remaining release gate |
| --- | --- | --- |
| M0: contracts | Ten architecture tuples, strict SDK admission, source pins, requirement/test schema, inventory admission tools and eleven bounded console evidence mappings | Complete reviewed normative indexes, source-unit/requirement/test mappings and evidence-backed ledger closure. The ledger is still a seed inventory; its schema passes and M0 gate fails. |
| M1: resources | Actual native entry, bounded firmware/linker page pools, private mappings, checked user access, owned waits/time and entry-stack leases; instantaneous service-stack checks | General allocation/reclaim/OOM policy, complete VM semantics, service-stack guards and full linked stack/lifetime proof, synchronization and sustained ten-guest pressure/protection qualification. |
| M2: common objects | Owned descriptors, cwd/path identity, bounded UNIX socket/descriptor passing, permissions, VFS lifetime work, public read-only mount inventory, lease-bound controlling console/foreground groups and referenced native raw PTY pairs | Complete resolver/symlink/mount/race semantics, independent PTY session/foreground authority, termios and broad IPC/resource failure behavior. |
| M3: libc substrate | Native fork/exec/wait, per-architecture ABI mechanisms, bounded Linux threads/futex/signals/time; four supplied musl userland profiles | Complete libc/thread/signal/cancellation behavior, all applicable 32-bit/endian/time64 layouts and full per-architecture musl acceptance. Hosted architecture selections remain separate from native guests. |
| M4: durable root | Real Virtio/ext4 roots, bounded mutation/recovery transactions and separate journalled qualification lanes | General default journalled root, full metadata/cache/request ownership and crash/FLUSH qualification. Production ext4 owner remains `<1,9>`; two-block pair work is not enabled. |
| M5: userland | Bounded native shell pipelines, ordered redirections, sequential/conditional command lists and utility execution; separate shared-musl/loader slices | Shell expansion/scripts/functions/control structures/jobs, PTY semantics, coherent general file mappings/cache, full shared loader/TLS/dlopen/cancellation and conformance/ports breadth. |
| M6: networking | Actual bounded Virtio/ARP/IPv4/UDP paths and selected native/Linux socket/TCP mechanisms | General reliable Internet TCP/IPv6, IRQ-driven network execution, configuration, DNS and HTTP/TLS applications under loss/reordering/pressure. |
| M7: managed system | Ordinary native PID1, bounded dependency graph, TERM/KILL retirement, orphan adoption, authenticated service control, numeric service identities and fixed-deadline quiescence; opt-in persistent ObfuscationOS console first-administrator enrollment, bounded ordinary local accounts, authenticated password rotation and checked private-home session entry; synchronized HALT, opt-in x86_64 PC/8042 reboot and bounded single-CPU QEMU PIIX4 poweroff; bounded logging, manual time, read-only mount inventory and local hosts resolver; native process SID/PGID lifecycle, authenticated controlling-console login, bounded current/negative-PGID signal-zero/TERM/KILL delivery and explicit foreground transfer/reclaim with background EIO; installed ABI74/UAPI0.16 cohort with separate actual x86_64 Debug/Release account, session, raw PTY and poweroff evidence | Broader account lifecycle and service/session authority, graphical login and PTY session/foreground integration; general logging, Internet DNS, mount mutation and network time; general shutdown policy, general ACPI and other reboot/poweroff backends. |
| M8: isolated graphics | Prelinked privileged desktop/kernel graphics and model/interface work | Separate user compositor and clients, protected shared display buffers, display/input ownership, fonts/toolkit/Wayland and isolated PTY terminal execution. |
| M9: daily desktop | Existing privileged Files/Notes interactions and separate actual native mounted-root save/reopen slices | Unprivileged GUI applications, graphical login/network/package/installer/recovery workflows, accessibility, UTF-8/CJK, lock and clean shutdown. |
| M10: ext4 breadth | Selected ext4 subsets and bounded interoperability/recovery evidence | Complete feature/combination inventory and qualification of every advertised read/write/replay profile, with explicit unsupported-format rejection. |
| M11: execution breadth | Ten native architecture profiles, QEMU paths and hosted SMP/module/IRQ/DMA-related mechanisms | Real concurrent SMP/TLB/IRQ/DMA/hotplug behavior, actual module relocation/execution/unload and concurrency stress. Physical reference machines remain deferred. |
| M12: full target | Explicit architecture/mode artifacts, retained failures, diagnostic and product qualification tools | Closed mandatory/selected-profile ledger, complete Debug/Release/user ABI gates, reproducible release/recovery artifacts and documentation. Manual desktop acceptance remains deferred. |

## Newly verified software slices

Bounded native raw PTY transport is now qualified and promoted as 76 source
paths (55 replacements, 21 additions and one explicit new source directory),
with twenty exact ABI74/UAPI0.16 SDK replacements. A separately qualified two-file
OS UAPI checker/test repair accompanies publication (78 combined paths); it
accepts 0.16 and requires the native PTY declarations. Eight raw pairs retain real
OFD/generation ownership for native scalar/vector I/O and poll, with explicit
peer drain/EOF/EIO behavior. All twenty candidate SDK/SDK-only OS rows, ten
standalone Debug boots, exact-source hosted suites and actual x86_64 Debug/Release
guests pass. Four authenticated UID0 sessions yield 52 fixture records; eight
stopped-guest observations establish actual armed waits. Fresh canonical build,
boot, installed-SDK admissions and SDK-only Debug/Release consumers pass. Complete
source/SDK inverses, original SDK directory identities and existing disks remain
retained. This supplies raw transport only: PTY controlling-session/foreground
authority, termios, signals, jobs, devpts and Linux PTY I/O remain open. Detailed
evidence and its limits are in [the current continuation](IMPLEMENTATION_PROGRESS.md)
and `native-pty-completion-preparation-v1/canonical-rollout-completion-v1.json`.
All full milestone gates remain open, including the user-deferred physical M11
and manual desktop M12 acceptance.

Two publication preparation attempts remain failed and retained before any
canonical source or SDK write. Their reader-alias and hosted-guard-time
schema assumptions are repaired by a separately reviewed successor that
checks exact symbolic-link chains and ordered UTC guard timestamps; no
target qualification evidence is relabelled or replaced.

Bounded historical console evidence is now integrated into the M0 ledger as
three explicit subrequirements and seven available test definitions. The ledger
contains 95 requirements, 175 test definitions and eleven execution-evidence
records: nine host/model/tool and two actual x86_64 Debug/Release guest records.
The all-ten console parent is separate from explicitly x86_64 native and login
subrequirements; no requirement becomes `verified`. A read-only tool checks
24,410 immutable files, including all 24,340 qualification inputs, canonical
validation products and the exact validator successor. It imports no producer
code and runs no historical baseline guard or guest. Synthetic and portable
regressions, actual retained-input admission and ledger relationships pass;
the full M0 gate still fails on explicit seed/source-index/qualification gaps.
This OS-only tool/data/document change preserves Kernel sources, all twenty
SDKs and existing disks. All thirteen complete milestone gates remain open.
See `console-evidence-mapping-candidate-v1/canonical-rollout-completion-v1.json`
and [the ledger contract](contracts/README.md).

Bounded native controlling-console authority is now qualified and promoted as
a 90-path Kernel/OS slice (72 replacements and eighteen additions) with twenty
exact ABI73/UAPI0.15 SDK replacements. All twenty SDK/SDK-only ordinary-console
OS tuples and ten standalone Debug boots pass. Login attaches its new session
to the lease-bound console before credential drop. The shell groups and gates
pipeline children, transfers foreground ownership before release and reclaims
it afterward. Background/detached reads return EIO without consuming bytes;
stale leases fail EACCES. Exact four-byte target-endian PID ioctls are checked
across all ten Linux adapters. PTYs, termios, terminal-generated signals and
complete job control remain open.

Hosted actual-runtime and ASan/UBSan checks each exercise 75 native and 183
Linux calls; frozen SDK/ABI controls pass 233 tests with one existing skip.
All four supplied musl profiles compile. Separate actual x86_64 Debug/Release
ordinary guests pass four authenticated UID0 sessions, 136 native and twelve
Linux console records, including UID1000 fixture peers, 12,289-byte pipelines,
redirected console aliases and nested shells. Both modes use the admitted
debug-optimized-v1 static musl library, with freshly compiled guest probes.
Guest scheduler-armed waiting remains explicitly unproven; armed-state coverage
is hosted only. Retained-group foreground selection is not guest-qualified.
A separate raw contract reader binds records and identities without importing
the producer or reconstructing historical nonce bytes. Guests are host-retired;
this campaign claims no orderly shutdown or power-loss persistence.

Fresh canonical standalone build/boot, all twenty installed SDK admissions,
190 targeted tests (one existing UAPI skip) and SDK-only Debug/Release OS
construction pass. Source
inverses, original SDK directories, full SDK byte inverses and existing disks
remain preserved. Publication is reversible, not globally crash atomic.
Original fixture, link, parser, partial-serial-prompt, raw-reader and publisher
control failures remain retained. The sealed v1 canonical validator's plural
publisher-filename typo is preserved; its admitted v2 successor changes only
that reference. All thirteen complete M0-M12 gates remain open. Physical M11
and manual desktop M12 remain user-deferred; production ext4 remains `<1,9>`,
signed32 and without paired I/O. See
`native-console-control-candidate-v1/canonical-rollout-completion-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Bounded process-group signal selection is now qualified and promoted as a
60-path Kernel/OS slice with twenty exact ABI72/UAPI0.14 SDK replacements.
All twenty SDK/SDK-only ordinary-console OS tuples and ten standalone Debug
boots pass. Hosted actual-runtime and sanitizer checks cover bounded snapshots,
signed selectors, precise refusals, per-recipient permissions, partial success
and deferred fatal delivery; existing positive-PID regressions pass. Frozen
SDK/ABI controls pass 220 tests (one existing skip). Separate actual x86_64
Debug/Release ordinary guests execute four authenticated UID0 sessions, 32
group cases and 84 fork/exec peers. UID1000 fixture senders establish partial
success and all-denied behavior; this is not a nonzero UID account-login claim.
Independent raw readers bind all cases to exact source/SDK/compiler/products.
Guests are host-retired; no synchronized shutdown or power-loss persistence is
claimed. Fresh canonical standalone, all twenty installed SDK admissions and
SDK-only consumer builds pass with complete inverses and protected disks intact.
This supports only group probes, TERM and KILL. Broadcast, HUP, stop/continue,
controlling terminals, foreground terminal groups, PTYs and job control remain
open. All full milestone gates remain open. See
`native-group-signals-candidate-v1/canonical-rollout-completion-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Bounded native process sessions are now qualified and promoted as a 69-path
Kernel/OS slice with twenty exact ABI71/UAPI0.13 SDK replacements. All twenty
SDK/SDK-only OS tuples and ten standalone Debug boots pass. Hosted lifecycle,
sanitized native/Linux dispatch and 215 contract tests (one existing skip)
remain separate from actual x86_64 Debug/Release ordinary guest execution.
Each guest completes two authenticated UID0 administrator sessions, four
process/exec cases per session, distinct SID/PGIDs and the first shell's normal PID1 reap before its
successor launch. Guests are host-retired after acceptance; no shutdown or
power-loss persistence is claimed. Fresh canonical standalone, installed-SDK
admission and SDK-only consumer construction pass with retained inverses and
original SDK directory identities. Existing source directory metadata, images
and account disks are preserved. Controlling TTYs, PTYs, foreground groups,
group signals and job control remain open. All complete M0-M12 gates stay open,
including user-deferred physical M11 and manual desktop M12. See
`native-sessions-candidate-v1/canonical-rollout-completion-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Synchronized native poweroff is now qualified and promoted as a 24-source-path
Kernel/OS slice: nineteen replacements and five additions without new source
directories, plus twenty exact ABI70/UAPI0.12 SDK replacements. Complete source
and SDK inverses are retained. The explicit `native_qemu_piix4_poweroff` policy
defaults to disabled and selects only `x86_64-qemu-piix4-pm-v1`; every other SDK
advertises `terminal_poweroff_backend=unsupported`. Actual PCI discovery and
validated PMBASE supply the final S5 request through the original PID1
PREPARE/queued-COMMIT, fixed retirement deadline and original storage clean-seal
coordinator.

All twenty SDK/SDK-only OS tuples and ten standalone Debug boots pass. Separate
actual single-CPU x86_64 Debug and Release campaigns each pass two boots and two
natural shutdowns with same-private-disk restart, password login and exact
persisted-file read: four boots and four shutdowns in total. Independent raw
readers bind the linked guest PM write, S5 device observation, guest-caused QMP
SHUTDOWN, natural QEMU exit zero, account/KDF and metadata readback and direct
final read-only filesystem checks. The first retired-disk check uses retained
source-pinned capture and read-only raw logs; the final same disk is independently
reinspected. Device-trace/source observations do not establish installed-QEMU
and source-build equivalence. Hosted policy/dispatch/storage controls remain
separate from this native execution evidence.

Fresh canonical standalone validation, installed-SDK admission, targeted hosted
controls and SDK-only ordinary-console OS image construction pass. These
consumer builds use verified disposable source snapshots and explicit installed
SDKs. Existing account disks, image namespaces, retained source snapshots and
SDK inverses are preserved. Original trace, enrollment and independent-reader
failures, the first staging timeout and the publication prepare-path type error
remain retained as failures; accepted successors do not relabel them passed.
The first canonical validator also retains its final-guard failure for two
vanished, unreferenced xmake probe temporaries. Separate read-only re-admission
checks all 37 successful command rows and unchanged products without rebuilding
or rerunning guests.

Natural emulator teardown can flush block state. This qualifies bounded orderly
shutdown on the selected QEMU PIIX4 backend, not general ACPI, other platforms,
torn writes, volatile-cache loss, general power failure or physical machines.
Production ext4 remains `<1,9>`, signed32 and without paired I/O. All thirteen
complete M0-M12 gates remain open; physical M11 and manual desktop M12 acceptance
remain user-deferred. See
`native-poweroff-candidate-v1/canonical-rollout-completion-v1.json`, current
pointer `build/qualification/native-poweroff-current-handoff-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Bounded ordinary local accounts are now qualified and promoted as a 93-path
Kernel/OS slice with twenty exact ABI70/UAPI0.12 SDK replacements and complete
inverses. All twenty SDK/SDK-only OS tuples and ten standalone Debug boots pass.
ObfuscationOS retains interactive creation of the first UID/GID 0 administrator;
authenticated `:useradd` adds protected ordinary accounts, and `:passwd` supports
authenticated password rotation. Ordinary sessions enter checked private homes
after setting and verifying all real/effective/saved IDs. Independent retained
evidence admits four ordinary Debug/Release boots with four linked QMP-observed
clean HALTs, plus two separate credential-fixture boots with serial clean-HALT
evidence. Original ordinary producer postcheck failures remain failed. Separate
independent readers admit eleven high-level ADD/ROTATE software-call cases and
one checked-ownership no-cut control (label 0) plus fourteen completed-call interruptions (1-14), including exact
mounted replay before authentication. Fresh canonical standalone and
installed-SDK consumer validation pass. These bounded results do not qualify
torn writes, volatile-cache loss, general power failure, physical machines or
manual desktop use. Production ext4 remains `<1,9>`, signed32 and without paired
I/O. Full M7 and every complete M0-M12 gate remain open. See
`native-accounts-candidate-v1/canonical-rollout-completion-v1.json` and [the current continuation](IMPLEMENTATION_PROGRESS.md).

Synchronized native reboot is now qualified and promoted as a 39-source-path
Kernel/OS slice with twenty exact SDK replacements, retaining complete inverses.
All twenty SDK/OS tuples and ten standalone Debug boots pass. The ordinary
x86_64 Debug/Release campaigns pass four boots, two synchronized reboot requests,
same-process/same-disk account authentication and persisted-file read, followed
by two stable clean HALTs. Independent raw readers bind native 8042 and pinned
SeaBIOS CF9 reset origins, products, serial/QMP, account/KDF and read-only final
filesystem checks. Fresh canonical standalone and installed-SDK consumer checks
pass. This supplies the explicitly enabled PC backend; other reboot backends,
poweroff and general account/session behavior remain open. A preexisting
shared-owner assertion failure is retained with exact baseline reproduction.
See `native-reboot-candidate-v2/canonical-rollout-completion-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Authenticated administrator password rotation is now qualified and promoted as
an eleven-file OS-only slice. Exact `:passwd` at a fresh ordinary `Login:` prompt
verifies the current password and obtains matching hidden new input before
writing complete salted PBKDF2 staging. Twenty native app compile tuples and
both ordinary x86_64 Debug/Release image builds pass. Ordinary campaigns pass
six boots/six clean HALTs with A-to-B rotation and same-disk authentication.
Separate refusal campaigns pass four boots/two clean HALTs/two intentional
retirements; separate authority/publication-cut fixtures pass eight boots/six
clean HALTs/two known-cut interruptions. Independent raw readers bind products,
completed processes, original input/QMP/serial, account bytes/metadata, console
authority and recovery publication order, with read-only filesystem checks.
No host repair or general power-loss guarantee is claimed. Fresh canonical
SDK-only image construction and 61 targeted tests pass, retaining all seven
original-file inverses while preserving Kernel/all20 SDKs and existing account
disks. This supplies administrator rotation; general accounts, graphical login,
PTYs and synchronized reboot/poweroff remain open. See
`native-password-rotation-candidate-v1/canonical-rollout-completion-v1.json`
and [the current continuation](IMPLEMENTATION_PROGRESS.md).

The bounded managed local resolver is now qualified and promoted as a
twenty-file OS-only slice. All twenty native app compile tuples and both ordinary
x86_64 Debug/Release image builds pass. Four actual ordinary boots pass fifty
wire queries, eight malformed CLI refusals, four notified restarts, persisted
hosts edits, same-disk password login and four stable QMP-observed clean HALTs.
Independent compiler/raw/disk readers bind original evidence; hosted parser,
transport and 79 packaging controls remain separate from native execution.
Fresh canonical installed-SDK-only image construction and 43 targeted tests
pass with unchanged Kernel/all20 SDKs and existing account disks. Preliminary
observer failures and the initial independent QEMU-retirement reader failure
remain retained. This supplies local hosts and strict IPv4 resolution; Internet
DNS, libc-wide resolution, NTP, general account/session behavior and full M7
remain open. See `native-resolver-candidate-v1/canonical-rollout-completion-v1.json`
and [the current continuation](IMPLEMENTATION_PROGRESS.md).

The read-only native mount-inventory slice is now qualified and promoted.
All twenty installed SDK/ordinary-console OS tuples pass with ABI69/UAPI0.11.0;
all ten standalone Debug QEMU boots pass. Actual x86_64 Debug/Release ordinary
products pass four boots, four stable QMP-observed clean HALTs and eight
`mountctl status` executions containing 72 rows. Independent raw readers verify
serial, linked terminal code, both halted snapshots per mode, persisted program
and account metadata, password authentication and read-only fsck. The exact
52-path Kernel/OS publication and twenty-SDK replacement retain complete
inverses. Fresh canonical installed-SDK-only image construction and 40 targeted
tests pass; existing account disks are preserved. SDK/parser hardening has
155 passing controls. This adds public read-only topology observation, with
no mount mutation, non-root native guest, SMP or full-milestone claim. See
`native-mount-candidate-v1/canonical-rollout-completion-v1.json` and
[the current continuation](IMPLEMENTATION_PROGRESS.md).

Managed manual `timed`/`timectl` is now qualified and promoted as a sixteen-file
OS-only slice. All twenty native Debug/Release app and dedicated-probe compile
tuples pass. Actual single-CPU x86_64 Debug/Release ordinary console and separate
credential/transport fixtures pass six boots and six clean QMP-observed HALTs,
with independent raw serial, product and disk readback. First-admin enrollment,
same-disk password login, root-only SET, public STATUS, forward/backward and
post-2038 clock changes, daemon restart and fixed monotonic deadlines pass.
Ordinary boot software time is provisionally seeded from ext4 last-write time;
it is not trusted UTC or actual unavailable-realtime startup evidence. Production
ext4 metadata still limits timestamps to 2147483647 seconds; tests restore a
supported epoch before storage writes/HALT and claim no post-2038 filesystem
mutation. Canonical installed-SDK-only image construction and twenty-five
targeted controls pass. Kernel/all20 SDKs and existing account disks remain
unchanged. NTP, general time/session policy and full M7 remain open. See
`native-time-candidate-v1/canonical-rollout-completion-v1.json` and [the current continuation](IMPLEMENTATION_PROGRESS.md).

The frozen `native-power-candidate-v2/` now supplies scalar native
PREPARE/queued-COMMIT and ordinary PID1 `service-ctl halt`, building on the
original native runtime, producer, scheduler-resource and OS storage adapters.
Actual single-CPU x86_64 Debug and Release products each pass enrollment, clean
HALT, same-disk restart without host recovery, wrong-password denial, successful
login, persisted-file read and a second clean HALT. Every halt has stable QMP
proof of the linked interrupt-disabled terminal loop, clean/no-replay disk
state and direct read-only fsck. Independent product/CPU/serial/disk/password
readers pass. The failed v1 guest exposed absent freestanding dynamic
initialization; v2 enforces `constexpr`/`constinit` and retains that failure as a
negative control. Hosted/sanitized dispatch controls, twenty wire rows,
20 integration archives/280 objects, standalone Debug's 75 reachable points
and SDK-only Debug/Release product readback pass. These are bounded console
HALT results. Other terminal backends, reboot and poweroff explicitly refuse;
active unqualified network owners and configured GUI applications also refuse.
The matching full SDK/OS cohort and independent readback now pass all twenty
architecture/mode tuples. The source delta is promoted and all twenty default
SDKs are ABI69/UAPI0.10, with complete ABI68 inverses retained and independently
checked. Fresh canonical standalone Debug boot (75 test points), installed-SDK
OS build and SDK admission tests pass. The joined publication record is
`native-power-candidate-v2/canonical-rollout-completion-v1.json`.
Protected persistent `logd`/`logger` is now a qualified and promoted OS-only slice.
The frozen v2 products pass all twenty app/okcrt compile tuples and full
x86_64 Debug/Release image builds. Both ordinary guests obtain thirteen
contiguous persistent acknowledgements, then fail the first rotation's
one-second reply deadline with record fourteen present but unacknowledged.
Those failures are retained. A separate v3 correction stages the initial
checkpoint and gives complete-frame persistence/reply its own fixed deadline.
Both full v3 image builds pass; actual Debug stops after twenty-six
acknowledgements at the second rotation, while the Release producer cannot
parse readiness interleaved with a password prompt. These remain failed
attempts. The compile-finalizer correction has a separate successful readback.
The frozen v4 successor uses a measured fixed 60000 ms completion
policy with a pre-final-send client anchor. Its targeted actual-code sanitized
and real-image packaging controls pass. Fresh compilation and independent
readback now pass all twenty architecture/mode tuples, forty executables,
440 objects and 500 dependency tables. Both actual ordinary x86_64 modes pass
forty-four contiguous full-size persistent acknowledgements, logd restart,
same-disk password login and persisted read, and two clean HALTs with stable
QMP and direct read-only disk checks. Initial v4 compile-name and independent
reader-ordering failures remain retained with corrected successors.
The joined qualification binds 21,032 files and survives optimized-Python
recomputation. The hardened v5 publisher revalidates the exact qualification
before its reversible seventeen-file source publication; independent after
readback passes. A fresh canonical x86_64 Debug installed-SDK-only full image
build and eleven targeted logging/disk/profile tests pass. The joined receipt is
`native-logging-candidate-v4/canonical-rollout-completion-v1.json`. Kernel/SDK
artifacts remain unchanged. Slow rotation, general logging and the complete M7 gate
remain open.
See the current continuation in
[IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md).

Actual x86_64 Debug and Release login campaigns now pass first-boot enrollment,
same-disk restart/authentication, hidden input, staged-write interruption and
authenticated recovery, logout/relogin and no-entropy refusal. The separate
ordinary console product passes two boots per mode without login/session test
wrappers. Its opt-in `native_console_login` profile requires an interactive
journalled disk, rejects startup acceptance/Linux PID1 replacements, uses a
separate login image and verifies actual disk product bytes/metadata before reuse.
The matching disk and eight rejection controls pass. All twenty init/login
positive compile rows are retained separately from a corrected build-guard-only
successor; the original aggregate diagnostic failure remains failed. ABI68/UAPI0.9
SDK installation and independent all-twenty readback pass with complete old
inverses retained. See the current continuation in
[IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) and
[native-init.md](../native-init.md). General accounts/sessions, graphical login
and the complete synchronized-shutdown policy remain open.

Native service quiescence now passes actual x86_64 Debug and Release SDK-only
guests plus independent source/SDK/product/serial and read-only disk checks.
Public STATE and root-only QUIESCE preserve the original 18-second deadline on
repeat requests and stop launches/restarts. Dependent services retire before
providers. A live adopted observer blocks completion through twenty post-graph
observations; only its actual exit-37 reap followed by fresh ECHILD admits the
sole quiesced record. PID1/control survive success; fatal-hold closes control on
failure. Hosted deadline/interruption controls and a separate 100-object,
ten-profile Debug/Release compile matrix pass. This operation provides no sync,
FLUSH or platform power and does not close the synchronized-shutdown gate.
Receipts are under workspace `build/qualification/native-quiesce-guest-{debug,release}-v2/`,
`native-quiesce-guest-readback-v2/{debug,release}/`, `native-quiesce-host-v2/` and
`native-quiesce-os-compile-v1/`. The separate
`native-quiesce-probe-compile-v2/canonical-v2-coverage-join.json` binds unchanged
eighty production objects and twenty freshly compiled revised probes to the v2
guest freeze; original objects/dependency records remain unchanged. Both initial v1 guests also passed and remain
retained. Physical and manual acceptance remain deferred.


The current native termination and adoption source passes ordinary hosted
production ASan/UBSan tests in Debug and Release (398 checks each), the existing
lifecycle suite on ten hosted architecture selections (1,459 checks each), and
original administrative regressions in both modes (303 checks each). The latter
caught and repaired a real native administrative-termination path that changed
PCB parentage without rebinding a live descendant's private lineage. Unpublished
fork rollback and resource-free model cleanup retain separate controls.

Fresh x86_64 Debug and Release SDK-only guests execute the ordinary native
service graph, native TERM/KILL/self-KILL, dependency retirement/restart,
oneshot/notify readiness and independent exec failure. Each also adopts one live
and one completed native orphan and reaps exit values 23 and 31. A live child
observes parent PID 1. Already-zombie Linux orphan SIGCHLD/autoreap policy is
outside this contract.

Those same current init/okcrt guests pass the shell's 12,289-byte four-stage
stream, quoting, ordered file/fd redirections, last-stage/error statuses and
twenty repeated pipelines, then run a fresh interactive pipeline. This replaces
the integration gap of the separate earlier shell proof, whose init/okcrt source
composition preceded native termination. Native fixture compilation preserves
all ten architectures; this suite's guest execution is presently x86_64 only.

On the 2026-10-17 continuation, fresh x86_64 Debug and Release guests also pass
bounded `;`, `&&` and `||` command lists, including equal left-associative
precedence, short-circuit side-effect suppression, parent builtin/exit handling,
whole-line syntax admission and twenty repeated pipeline/list combinations.
The separate `OKSH_LISTS` record is required before the final shell record.
Twenty-five hosted groups cover larger streams, injected allocation/launch
failures, descriptor restoration and repeated lists. The later shell and expanded
fixture each compile on all ten profiles with Debug and Release compiler flags:
forty actual ELF objects. This is compile-only coverage. Its original finalizer
failed because it omitted xmake's target/platform suffix from expected paths;
separate strict command/product readback accepts the existing objects without
replaying compilation or relabelling that original failure.

Independent readback uses stricter causal marker ordering and verifies raw wait
statuses, SDK/product identities and the retained serial bytes. Both retired
guest disks pass read-only fsck. Host retirement after shell sync is not a clean
guest shutdown or power-loss durability result.

The corrected control fixture passes later x86_64 Debug and Release SDK-only
guests. A real Linux-personality credential drop to UID/GID 1000 is preserved
across native exec: status remains public and restart is denied without changing
provider/dependent identities. Root CLI restart retires dependents before their
provider and starts distinct generation 3 replacements after readiness. Children
scan their descriptor tables for leaks while an incomplete client is held.
Malformed/fragmented requests and disconnects do not disrupt supervision. The
fixed deadline test sends activity at 607 ms and observes EOF at 1015/1014 ms under
an absolute 1200 ms bound, rejecting a sliding timeout. Shell lists/adoption and a
later interactive pipeline also pass; both retired disks pass read-only fsck.

Six enabled implementation/fixture units compile on every architecture with
Debug and Release flags: 120 ELF objects, with exact command/product readback.
That is compile-only coverage; native control guest execution is x86_64 only.
The endpoint is now enabled by default and can be disabled explicitly. Original
v1 fixture failures and the initial reader import failure remain retained.
This adds service control; login, synchronized shutdown and full M7 remain open.

The next software slice adds native real/effective/saved UID/GID operations and
version 2 numeric service identities. Only the fork child drops GID then UID,
verifies all six IDs and execs; errors fail closed through the existing exec
channel. Version 1 remains implicit root, and the Linux-musl service manager
rejects version 2. Native wrappers preserve high unsigned identity values.
Credential changes require exactly one live thread and do not provide
supplementary groups, account authentication or terminal sessions.

Later x86_64 Debug and Release SDK-only guests execute native saved-ID and
permanent-drop rules, fork/exec inheritance, failed exec and file permission
denial. A configured UID/GID 1000 oneshot is bound to its actual PID1 launch,
identity record, successful reap and readiness. Native control denial uses a
native helper; graph/adoption/shell regressions remain passing. Separate
source/product/serial readbacks and both read-only fsck checks pass. The first
Release fixture remains failed because a marker was attached to the prompt;
corrected successors use explicit LF framing and wait for identity completion.
Kernel and fixture compile-only matrices preserve all twenty architecture/mode
rows. This increment leaves accounts/login and synchronized shutdown open.

The boot-archive directory permission gap is now repaired. The packer admits
directory modes through `03777` and regular-file modes through `0777`; the Kernel
imports exact root-owned RAM directory attributes, rejects conflicting existing
entries and does not inherit a parent's SGID into an imported child. Explicit
staging modes are independent of host umask and SGID ancestry. Actual archive-only
x86_64 Debug/Release guests verify imported modes, sticky deletion denial between
UIDs 1000/1001 and runtime SGID inheritance, including actual child reaps and the
later interactive shell. These guests attach no distribution disk and establish
no account durability or shutdown behavior.

The separate composite standalone Kernel qualification covers all twenty SDK
rows and the standalone Debug boot. The first producer's source-wiring formatting
failure and its corrected x86 successor remain separate. A fresh frozen-v4 OS
campaign passes all twenty architecture/mode rows and 140 original commands.
Independent readback binds 1,950 objects/dependency records, 560 actual link/ELF
outputs, twenty CRT archives and exact OKAR bytes through each archive object and
both final images. Receipts are `archive-permissions-sdk-v1/`,
`archive-permissions-x86-recovery-v1/`,
`archive-permissions-x86-recovery-v1/readback-v2/`,
`native-archive-permissions-guest-{debug-v3,release-v1}/`,
`native-archive-permissions-guest-readback-v4/{debug,release}/` and
`archive-permissions-cross-os-v2/`. Installed defaults are unchanged.

The next login boundary, scheduler-owned console input leases, is implemented
with default-closed input, original-PID1-only claim/revoke, kernel-issued epochs,
fork/exec membership and complete leader-exit revocation. Ordinary hosted,
ASan/UBSan and reachable Debug model checks pass. A new twenty-row standalone
SDK campaign with ABI67/UAPI0.8.0 passes all 61 original commands and the x86_64
Debug boot with 72 points; its independent source/product/compiler/dependency
reader passes 100 records. Actual archive-only x86_64 Debug/Release SDK-only
guests now pass unrelated-root and old-descendant read/readv/duplicate-descriptor
denial while a new epoch's input is buffered, current-epoch control denial,
revoked blocked reads/poll, exact adopted-child reaps and no input echo. Separate
readers bind each original compile/object/link/CRT, staged ELF, complete OKAR and
final image to its serial result. The first guest failures remain retained: short
syscall stubs left reserved argument registers nonzero; the corrected wrappers
explicitly zero all five reserved words. These results do not implement account
authentication, durable storage or shutdown. Receipts are `console-input-sdk-v2/`,
`console-input-lease-host-v4/`, `console-input-lease-host-asan-v1/` and
`console-input-debug-model-v1/`,
`native-console-lease-guest-{debug,release}-v2/` and
`native-console-lease-guest-readback-v1/{debug,release}/`.
The separate OS console cohort has 160 successful commands on all twenty rows;
its original finalizer and first reader remain failed because two archive-fixture
staging paths were absent after a callback collision. A successor reader admits
the actual console products without rebuilding: 2,010 original objects and
dependency records, 580 links, twenty CRT archives and forty complete final OKAR
embeddings. This is console-product evidence, not combined archive-fixture staging
acceptance. Receipts and retained failures are in `console-input-cross-os-v1/`.
Installed defaults have not been replaced.

First-administrator account policy now has strict versioned state parsing and
PBKDF2-HMAC-SHA256 with 600,000 rounds, no default password and no entropy
fallback. Independent crypto/parser review and hosted sanitizer/oracle checks
pass. `native-account-policy-compile-v1/` independently admits forty original
objects/dependencies and twenty static libraries across all ten architectures
Debug/Release; it is compile-only evidence. Protected image seeds remain explicit
unconfigured root:root0600 databases with root:root0700 `/root`.

A nondefault login executable and account store now implement interactive setup,
pending/active publication, authenticated staged recovery, bounded hidden input,
password verification and same-process shell execution. Eleven hosted store groups
cover syscall failures and uncertain publication with substituted ownership and
persistence capability, including rejection of noncanonical name tails before
staging. Nine hosted input and sixteen main-flow groups pass with injected
process/store/entropy/exec boundaries and actual production password code.
The selected `ObfuscationOS` banner is present in the rerun main-flow source.
Receipts are `account-storage-host-v2/` and `login-control-host-v2/`. The stronger Kernel
persistent-sync operation, ABI68/UAPI0.9 exports, SDK-only OS consumption and
actual journalled-disk two-boot login/recovery are still under qualification.
No default login or synchronized shutdown gate is closed by these host checks.

## Artifact state and evidence

The current validated accounts rollout is `native-accounts-candidate-v1/canonical-rollout-completion-v1.json`: twenty installed
architecture/mode SDKs use ABI70/UAPI0.12.0 and the checked native metadata
profile. All ten native profiles and the four supplied musl profiles remain in
scope; this slice does not add general musl execution acceptance. The following
credential/adoption entries describe historical artifact transitions and are not
the current default SDK inventory.

The credential source now supplies all twenty installed default SDKs, with
ABI67/UAPI0.7.0 and the additional mandatory capability
`native_credentials_profile=bootcpu-single-live-thread-real-effective-saved-v1`.
Current OS source requires the later ABI68/UAPI0.9 persistent-sync contract and
rejects these older defaults until an exact qualified replacement is installed.
Separate exact-row qualification, prepare/apply and independent post-install
readback pass. Every displaced adoption SDK remains under
`native-credentials-sdk-install-v1/retired/ARCH/MODE`. Current SDK validation
checks the new capability; it does not admit those predecessors as current.
The operation preserves complete bytes and permissions for restoration and is
not crash-atomic. The twenty-row join pins production OS v1 and the explicit
two-file fixture/evidence delta used by the later v2 guests. Its failed initial
x86 Release bootstrap-size expectation is retained; the successor checks three
4KiB page tables plus the 1MiB stack without rebuilding products.

The preceding adoption frozen source exported x86_64 Debug and Release SDKs with ABI67 and
explicit capabilities `designated-pid1-native-linux-adoption-v2` and
`bootcpu-positive-pid-probe-term-kill-deferred-v1`. Its standalone Debug kernel
boot and strict compiler-matched consumer admission pass. All twenty exact
architecture/mode SDKs were independently admitted and installed as the previous
default artifacts, with every older SDK directory retained for restoration.
The installer validates staged and installed bytes, permissions, compiler and
architecture/mode identities against a pinned plan. This operation is reversible
within its retained evidence; it is not crash-atomic across twenty directories.

The original eighteen-row cross campaign remains `fail`: seventeen ordinary
rows pass, while MIPS64 Debug's standalone apps command returned 255 when xmake's
midnight cleaner removed its temporary directory. Its subsequent original
distribution dependency build succeeded, including all 23 applications.
Independent source/ELF/archive/compile/link/rootfs readback admits those exact
products separately. No successful build was replayed and the original failure
was not changed. The independent twenty-row join combines those eighteen
products with the existing x86_64 SDK-only guests and stricter disk readbacks.
New control software is a later OS revision with a separate acceptance lane.

Evidence is under workspace `build/qualification/`:

- `native-credentials-host-v1/`, `native-credentials-linux-regression-v1/` and
  `native-service-identities-host-v1/`: hosted runtime, wrappers and service
  identity fault controls, separate from native execution.
- `native-credentials-sdk-contract-v1/`, `native-credentials-compile-v1/` and
  `native-credentials-os-compile-v1/readback-v1/`: strict capability admission
  and twenty-row compile/dependency/product checks.
- `native-credentials-sdk-install-v1/`: exact twenty-row qualification, actual
  prepare/apply/readback exit receipts, installed tree checks and all old SDK
  inverses. `native-credentials-cross-os-v1/` retains its original path-only
  finalizer failure after all 108 child commands exited zero, then separate
  corrected product admission and independent full readback. The initial
  product reader's incorrect special-mode expectation also remains retained.
- `native-credentials-guest-{debug,release}-v2/` and
  `native-credentials-guest-readback-v2/{debug,release}/`: actual native
  credential/service/control/adoption/shell execution and offline fsck.
- `native-init-control-default-v1/`: separate ordinary default-on builds.
- `milestone-status-2026-10-16-v1/result.json`: seed ledger audit (92 requirements,
  168 tests, zero ledger execution-evidence entries at audit time); M0 gate fails.
- `adoption-admin-fix-production-{debug,release}-v1/`,
  `adoption-admin-fix-lifecycle-all-v1/` and
  `adoption-admin-fix-original-admin-regression-v1/`: hosted implementation tests.
- `native-adoption-sdk-v3/`: final frozen source and x86_64 SDK/boot qualification.
- `native-adoption-cross-v1/`: terminal eighteen-row original build result and
  separately reviewed build-product admission, including the retained MIPS64
  Debug failure and successful distro dependency products.
- `native-adoption-sdk-install-v1/`: independent exact twenty-row qualification,
  byte/permission installation plan, actual prepare/apply exit receipts and all
  twenty old SDK directory inverses. The installer completed with exit zero.
- `native-m7-adoption-debug-v2/`, `native-m7-adoption-release-v1/` and
  `native-m7-adoption-independent-v1/{debug,release}/`: actual bounded guest
  execution, stricter readback and offline fsck.
- `native-adoption-shell-compile-v1/`: twenty fixture objects on ten profiles.
- `oksh-lists-host-v1/` and `oksh-lists-reader-v1/`: hosted shell and synthetic
  reader controls, separate from native execution.
- `native-m7-shell-lists-{debug,release}-v1/` and
  `native-m7-shell-lists-readback-v1/{debug,release}/`: later actual shell lists,
  existing graph/adoption regression, strict readback and read-only fsck.
- `oksh-lists-cross-v1/readback/`: forty compile objects and exact compiler/
  include/header/architecture checks, following a retained path-only finalizer
  failure after both original xmake commands exited zero.
- `native-m7-control-{debug,release}-v2/` and
  `native-m7-control-readback-v3/{debug,release}/`: actual control, UID 1000 denial,
  fixed deadline, dependency generation identities, shell/adoption and fsck.
- `native-init-control-cross-v1/readback/`:120 enabled control compile objects
  on ten profiles and two compiler flag modes, separate from native guests.

The separate termination-only frozen matrix retains its earlier init capability
and matching historical validator. It is not evidence for the later adoption
source. Initial fixture/observer and harness failures remain retained; later
successors do not relabel them as passing runs.
