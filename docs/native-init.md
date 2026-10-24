# Native ordinary init

## Changing the first administrator password

Sign out of the console shell with `exit`. At the next fresh `Login:` prompt,
enter `:passwd`, then the administrator account name and current password.
After authentication, enter and repeat the new password. Input remains hidden.
The account name, UID/GID 0 and `/root` stay the same; the new verifier uses
fresh trusted entropy and the existing PBKDF2-HMAC-SHA-256 policy. This entry
runs in the new PID1 console leader before any shell or child process starts.

Rotation is available only for an active account with no recovery transaction.
Finish ordinary activation or authenticated recovery before selecting it.
Wrong current credentials retain the existing KDF cost and one-second monotonic
retry delay. Mismatching, empty or oversized new passwords cause another prompt
without starting a store transaction.

The protected account store durably stages the replacement before publishing
it. An interrupted save may require the new password on the next sign-in:
a complete same-account active staging record is authenticated before recovery.
Partial, malformed or conflicting staging keeps login closed and is never
automatically discarded. A failed save does not promise the old password is
still selected. This bounded single-administrator flow adds no offline reset,
multiuser policy or general shell `passwd` command.

## Persistent console login profile

`--native_console_login=y` selects the ordinary native PID1 and `/bin/login`
console service. It builds and stages the unwrapped login executable, uses
`config/services-login.conf`, and selects login if the leaf manifest is missing.
Malformed or unsafe manifests still hold PID1. The profile rejects Linux-init
replacements and startup acceptance modes, which could run before authentication.
The existing maintenance console remains the default while general journalled
root qualification is open.

Configure the selected architecture/mode SDK, compiler toolchain and explicit
Linux journal-activation image with its SHA-256, then run:

```sh
xmake -y -b distro_image
xmake qemu-distro --fs=ext4-journalled --interactive --qemu=/usr/bin/qemu-system-x86_64
```

The console profile uses `rootfs.login.ext4-journalled.img` and reuses that disk
so subsequent runs retain the account. Before each launch, it requires complete
activation evidence and reads the actual disk to match `/init`, `/bin/login`,
`/bin/oksh` and `/etc/services.conf` to the selected build, including protected
path metadata. A maintenance disk, incomplete publication or changed product
holds closed; select a fresh output or explicitly migrate the existing disk.
Journalled image creation refuses an existing image or evidence sidecar. First boot shows
`ObfuscationOS`, asks for the first administrator's name and password, and opens
the shell only after persistent publication. Later boots authenticate that same
account. Missing trusted entropy or persistent-sync support refuses enrollment.
The image never contains an initial password. This is native console login;
the isolated graphical greeter and complete desktop session remain M8/M9 work.
Closing QEMU is host retirement and does not establish clean shutdown.

The ordinary unwrapped product passes separate x86_64 Debug and Release
same-disk two-boot qualification through the actual xmake task, including hidden
input, wrong-password retry, `/root` shell entry and logout/relogin. Independent
readers bind original compile/dependency/link, serial input and PBKDF2/disk
metadata. Initial image admission plus eight malformed/stale-image controls
pass. Targeted init/login compile coverage has twenty positive rows; its original
aggregate run retains a top-level Lua diagnostic failure. The final option
callback has five actual exact rejection controls plus an unchanged-input
successor build join. Receipts are workspace
`build/qualification/native-console-login-product-{debug,release}-v2/`,
`native-console-login-product-prep-v1/`, `native-console-login-product-cross-v1/`
and `native-console-login-guard-successor-v2/`.

## Maintenance console and service supervision

The ordinary rootfs installs the native `app-init` product as `/init` on all ten
profiles. PID1 supervises a bounded service graph selected by `/etc/services.conf`.
The packaged default is `service console simple /bin/oksh -`. Missing leaf
configuration selects that same default; unsafe or malformed configuration
retains PID1 in a diagnostic hold without launching the service. The native
metadata adapter checks the fields supported by native stat. Device identity
and timestamp mutation checks require a future native stat contract.

Each service has its own child identity, generation, exec channel and restart
state. Failed pipe/fork allocation and exited services use the shared
50/100/200 ms retry burst and 2 second
cooldown. Stable operation resets the burst. A CLOEXEC error pipe frames one
native integer errno. `simple-ready` records conventional exec-channel closure
after a WNOHANG reap check; an actual prompt/command response establishes user
entry independently. Events are complete `NATIVE_PID1` lines and use bounded
64-bit formatting on 32-bit profiles. The single-console configuration retains
the `direct-child-v1` event profile; other graphs use `dependency-graph-v1`.

The shared graph admits `simple`, `notify` and `oneshot` services. A notify
service writes one `R` byte to `OK_SERVICE_READY_FD`; a oneshot becomes ready
only after a successful exit. Dependents launch after their dependencies are
ready. Losing a dependency retires the affected generation with native TERM,
then KILL if its deadline expires, and waits for reap before replacement. The
same retirement mechanism handles startup failure and timeout. Independent
services retain their own restart state. This requires an SDK with
`native_termination_profile=bootcpu-positive-pid-probe-term-kill-deferred-v1`;
the module ABI number alone does not establish this service.

Debug and Release both default to production supervision. Configure
`--native_init_acceptance=y` to run the retained native acceptance before the
manager starts. Existing `native_udp_probe` and `native_vm_acceptance` also
explicitly select those checks. `qemu-distro --require-native` selects the init
acceptance option before rebuilding; `distro-test` and `qualify_workstation.py`
select it for their Debug native gates. An external image must contain the
acceptance itself. `test_persistent_ext4.py --require-native` requires it from
an explicitly selected image, independently of its compiler mode.

Run hosted controls with `xmake native-init-model-test --out=NEW_DIRECTORY
--host-cc=/usr/bin/cc`. Hosted controls do not execute native processes.
Native acceptance must boot the packaged ELF, exit a shell, observe its matched
reap/relaunch and execute commands in the next shell. Text saved by Notes can
then be reopened to check continuity within that same boot.

`tools/qualify_native_service_graph.py` builds an explicitly selected SDK-only
consumer and runs native blocked-child TERM/KILL and self-KILL, oneshot/notify
startup, provider crash, dependent retirement, generation replacement and an
independent missing executable. Its test-only manifest stays in that retained
consumer; the packaged default remains the console. The qualifier preserves
actual guest evidence separately from hosted graph/channel tests and Kernel
boot diagnostics.

With `--native-adoption`, the qualifier also starts a oneshot native parent
which leaves live and completed descendants. PID1 adopts both and reaps their
distinct exit values 23 and 31; the live child observes `getppid()==1`. This
requires `native_init_profile=designated-pid1-native-linux-adoption-v2`. The
kernel rebinds live lineage on normal exit, native fatal termination and checked
administrative termination. Already-zombie Linux orphan notification/autoreap
policy remains outside this bounded adoption contract.

`--shell-acceptance` adds the native shell fixture to the same SDK-only consumer:
a 12,289-byte four-stage stream, ordered redirections, quoting, status/error
handling and twenty repeated pipelines. Current x86_64 Debug and Release guests
pass both optional lanes. Their exact results and stricter independent serial
readbacks are under workspace `build/qualification/native-m7-adoption-debug-v2/`,
`native-m7-adoption-release-v1/` and
`native-m7-adoption-independent-v1/{debug,release}/`. Post-retirement read-only
fsck exits zero for both. Host retirement after shell sync does not qualify
synchronized shutdown or physical durability.

Complete service shutdown policy and synchronized poweroff remain pending
mechanisms. Accounts/login, device/network/resolver,
logging, time and mount services also remain M7 work. The sealed musl
PID1/service-graph replacement paths retain their separate Linux-personality
mechanisms and admission. This native increment does not complete M7 or M0-M12.

Bounded native control is enabled by default; `--native_init_control=n` disables
the endpoint. The ordinary application set
includes `service-ctl status [SERVICE]` and `service-ctl restart SERVICE`.
Without an enabled PID1 endpoint the CLI reports a connection error.

The endpoint is `/run/init.sock`, in the root-owned RAM `/run` mounted by the
distribution. PID1 checks that `/run` is a directory owned by root without group
or world write permission, and refuses every existing endpoint name, including
symlinks. It does not unlink names on setup failure. The socket permits public
status queries; mutation requires the effective UID captured by server-side
`SO_PEERCRED` to be zero. The CLI authenticates server PID 1 and UID 0 through
`SO_PEERCRED` before sending a request. A requested UID or PID in text is never
an authentication input.

Each connection carries one ASCII line: `OK_INIT_CONTROL 1 STATUS`, optionally
followed by a service name, or `OK_INIT_CONTROL 1 RESTART NAME`, terminated by
LF. Names contain 1–31 letters, digits, underscores or hyphens. Requests are
smaller than 96 bytes; responses are at most 2,048 bytes. Replies start with
`OK_INIT_CONTROL 1 STATUS`, `ACCEPTED` or `ERROR`, contain explicit fields, and
end with an `END` line and connection EOF. The CLI validates complete response
syntax before printing it. An error response gives the CLI a nonzero exit code.
The server dispatches at the first buffered LF frame and closes after replying.
Extra bytes in that same received buffer are rejected. Later bytes cannot cancel
an already dispatched request, and no second request is processed.

An accepted restart reports the old PID and generation. It withdraws readiness
transitively, retires dependents before their provider, and reuses the graph's
existing TERM/KILL, exact reap and crash backoff. Acceptance does not imply that
the replacement is ready; a later status query establishes its new generation.
Unknown, unauthorized and busy requests do not mutate the graph. Completed
oneshots can also be restarted. The bounded quiescence operation below stops
services; synchronized shutdown remains outside this protocol.

PID1 processes at most two control clients per actor iteration. Each has a fixed
one-second deadline from acceptance, which activity never extends. Client I/O
also has a fixed one-second monotonic deadline. Sockets are nonblocking and
CLOEXEC; writes suppress SIGPIPE, and no received ancillary descriptors are
admitted. Fork children explicitly close all control descriptors before exec.
A control setup/transport failure is logged and disables control while service
supervision continues. Deadline exhaustion is reported as `EAGAIN` by the CLI.

`python3 -B -m unittest discover -s tests/tools -p test_native_control.py` runs
hosted protocol, authorization, dependency retirement, malformed response,
partial-I/O, descriptor and deadline fault controls against the actual server,
client and CLI sources. `OK_TEST_KERNEL_SDK` can select an explicit exported SDK
for its UAPI headers. These controls do not execute the native ABI. The separate
`tests/native/native_control_fixture.lua` target builds
`native-init-control-probe`; a retained consumer may stage it explicitly and run
it after the service graph reaches generation two. It invokes the packaged CLI
and verifies new provider/dependent identities. Its `denied` mode requires an
actual nonroot process and checks public status plus unchanged denied mutation.
Without `--native-credentials`, the root probe orchestrates that child through
the separately pinned static-musl `tests/musl/native_control_drop.c` helper,
staged as `/bin/native-control-drop`. It drops real, effective and saved UID/GID
to 1000 using the Linux personality, then execs the native probe. The later
native credential lane uses `tests/native/native_control_drop.c` instead, with
no Linux helper. The root probe also exercises malformed and fragmented requests,
disconnects and an activity-independent server deadline, then holds an
incomplete client during replacement. The native graph children check all
nonstandard descriptors at entry. The fixture emits acceptance records only
when run; its source is not guest evidence.

The corrected earlier control fixture passes actual x86_64 Debug and Release
SDK-only guests, alongside the original service graph, orphan adoption and shell
lists. The Linux bridge proves real/effective/saved IDs 1000 before native exec;
the native denied client checks public status and unchanged provider/dependent
generations. Root CLI restart replaces both generation 2 children with distinct
generation 3 PIDs, respecting dependent-first TERM/reap and provider-first
readiness. Entry fd scans find no unexpected inherited control descriptors.
Malformed, fragmented and disconnected clients are covered. A fixed monotonic
1200ms bound observes EOF at 1015/1014 ms despite activity at 607 ms; this rejects
the sliding timeout that the initial fixture could have accepted. A later
interactive shell pipeline succeeds, and both host-retired disks pass read-only
fsck. These are not synchronized guest shutdown or physical durability results.

Evidence is under workspace `build/qualification/native-m7-control-{debug,release}-v2/`
and `native-m7-control-readback-v3/{debug,release}/`. The original v1 guests remain
failed because their unknown-target test accidentally selected the configured
`missing` service. The initial reader's missing import closure is also retained.
`native-init-control-cross-v1/` and its separate readback qualify 120 freestanding
objects: six enabled implementation/fixture units on ten profiles with Debug
and Release flags. That matrix is compile-only; native control guest execution
is presently x86_64. All thirteen complete M0-M12 milestone gates remain open.

## Native service quiescence

`service-ctl state` reports the lifecycle phase independently of service status.
`service-ctl quiesce` requires peer effective UID 0 and starts a fixed 18,000 ms
retirement deadline. Repeated requests return the original start and deadline;
activity and EINTR never extend it. New launches and restarts are rejected.
PID1 withdraws readiness and uses dependency-first TERM/KILL and exact reap.

The version 1 `STATE` reply contains `phase=running|quiescing|quiesced`,
`graph=running|stopping|stopped`, `children=unknown|live|empty`, `started_ms` and
`deadline_ms`, followed by `END`. The version 1 `QUIESCE` acknowledgement contains
`accepted=1` and the same timestamps, followed by `END`. The client authenticates
PID1/root and validates complete replies. STATE is public; unauthorized QUIESCE
cannot change the lifecycle.

A stopped graph alone is insufficient: an adopted child may still be live.
Only a fresh `waitpid(-1, WNOHANG)` collection reporting `ECHILD` after the graph
boundary admits `quiesced`; a zero return still means live children. PID1 emits
`quiesce-started`, `graph-stopped` and `quiesced` lifecycle records. Successful
quiescence preserves PID1 and its control endpoint. A retirement, wait or fixed
deadline failure enters the existing fatal-hold path and closes the endpoint.

The actual x86_64 Debug and Release SDK-only guests pass public nonroot STATE,
denied nonroot QUIESCE, root CLI acknowledgement, duplicate deadline identity,
busy restart and dependent-before-provider retirement. A native observer is
adopted by PID1 and remains live through twenty post-graph state observations;
completion remains blocked until its actual exit 37 is reaped. The reader checks
the raw wait status 9472 and causal ordering before the sole completion record,
then observes another second without launches. The same guests retain native
credential/control/adoption, shell lists and a later pipeline before quiescence.
Both host-retired disks pass independent read-only fsck. No shell command runs
after quiescence. No sync, device FLUSH or platform power action is supplied by
this operation, and these results are not synchronized shutdown evidence.

Evidence is under workspace `build/qualification/native-quiesce-host-v2/`,
`native-quiesce-os-compile-v1/`, `native-quiesce-guest-{debug,release}-v2/` and
`native-quiesce-guest-readback-v2/{debug,release}/`. The hosted controls cover
protocol authorization, child collection, fixed deadlines and interrupted I/O.
The initial five-unit matrix contains 100 actual objects across ten profiles and
Debug/Release; it is compile-only coverage. The later probe-only twenty-row
compile and `canonical-v2-coverage-join.json` in
`native-quiesce-probe-compile-v2/` join unchanged eighty production objects to
twenty revised probes; all original hundred objects and dependency records
remain unchanged. Both original v1 guests passed and
remain retained. The v2 guest fixtures also admit a transient initial unknown
child observation and one exact shell prompt prefix on the CLI acknowledgement,
while requiring exact END framing and strict live-child observations after the
graph stops. Full M7 and all thirteen complete milestone gates remain open.

## Native halt and reboot policy

`service-ctl halt` and `service-ctl reboot` send the exact version 1 `HALT`
and `REBOOT` control requests. PID1 authorizes peer effective UID 0 before
calling `ok_power_prepare` with the corresponding existing power selector. A
refused or unsupported PREPARE leaves the running service graph and lifecycle
unchanged. The `HALT accepted=1 started_ms=... deadline_ms=...` or `REBOOT`
reply acknowledges the selected request only; it does not establish a clean
halt or an observed reset. The private positive token never enters a reply.

Both actions use one lifecycle. After PREPARE succeeds, PID1 uses the existing
reverse dependency retirement and retains one original 18,000 ms deadline,
including child collection and descriptor closure. Same-action repeats retain
the selected action, token, start and deadline. A different power request is
busy and cannot replace the reservation. A prior service-only QUIESCE cannot
be upgraded to either action. After the graph stops, PID1 requires a fresh
actual ECHILD, closes every original exec/ready channel and every control
client/listener with checked results, and calls `ok_power_commit` with the
exact PREPARE token. A queued COMMIT parks PID1; subsequent actor steps cannot
restart services or repeat the call. Any failure after power admission enters
a sticky OS fatal hold, even if the failed operation could later succeed.
Ordinary QUIESCE retains its existing service-only behavior and open control
endpoint. The kernel owns the final platform action and interrupt-disabled
terminal fallback if a qualified reset fails.

The storage callback admits HALT and REBOOT for the original owned journalled
root and runtime attachments, using the same action gate for preflight and
seal. Original provider, registry/session, device/buffer identity, geometry,
idle FLUSH-capable transport and exact one-shot barrier checks remain required.
It detaches `/run`, detaches `/`, freezes that original provider clean, then
stops its original transport. Poweroff, archive/nonjournalled roots and
unqualified owners remain unsupported. Storage admission alone does not grant
platform reboot support: kernel PREPARE must admit every owner and backend
before the service graph changes. The optional x86_64 PC 8042 reboot backend
requires an explicit qualified profile; all other profiles retain refusal.

The public power wrapper uses the existing UAPI and a matching exported SDK.
Hosted controls in `test_native_halt.py` exercise both actions through the
actual server/client/CLI and PID1 actor with deterministic syscall failures.
The separate `test_native_shutdown_storage.py` includes the actual OS storage
callbacks with hosted provider/VFS/transport seams and real exported SDK
status, ticket and barrier types. These controls establish OS policy and
ordering; they do not establish provider hardware execution or guest reset.

Native reboot qualification must use a fresh private journalled disk and
ordinary Debug and Release guests. Required observations are a unique
persisted marker, authenticated reboot, original clean seal, actual guest
reset and a second boot in the same QEMU process on the same disk. That boot
must authenticate the retained account and read the marker without host
repair. A later clean HALT and read-only filesystem inspection are separate
observations. QEMU debug-exit, host reset/quit and terminal hold do not count
as guest reboot. Physical-machine and manual desktop acceptance remain deferred.

## Native service identities

The native SDK capability
`native_credentials_profile=bootcpu-single-live-thread-real-effective-saved-v1`
provides `setuid`, `setgid`, `setreuid`, `setregid`, `setresuid`, `getresuid`,
`setresgid` and `getresgid`. Each credential setter requires a process with
exactly one live thread; supplementary groups, thread-group setxid and sessions
are outside this contract. The SDK ABI/UAPI version alone does not identify this
additive capability.

Version 1 manifests retain their implicit UID/GID 0. Version 2 adds canonical
decimal IDs, excluding the unchanged-ID sentinel:

```
OK_SERVICE_MANIFEST 2
service worker simple /bin/worker - 1000 1000
```

Only the fork child changes identity. After closing supervisor descriptors, it
sets real/effective/saved GID, then UID, reads back all six IDs and execs only
after exact agreement. A syscall failure or mismatch reports errno through the
existing exec channel and exits 127. The static-musl manager rejects version 2
instead of silently running a configured nonroot service as root. This is
numeric service identity policy; it does not authenticate a login or establish
a terminal session.

`--native-credentials --native-control --native-adoption --shell-acceptance
--shell-lists` qualifies a retained version 2 manifest and native-only helper.
Fresh x86_64 Debug and Release guests verify UID/GID 1000 service launch, denied
privilege regain, reversible saved-root changes, high unsigned IDs, pair setters,
failure atomicity, permanent drop, file permission denial and failed/successful
exec semantics. Control, adoption and the shell regressions also pass. Separate
readback binds the service's launch, identity record, successful reap and
oneshot readiness to the same PID; both host-retired disks pass read-only fsck.

The current receipts are workspace
`build/qualification/native-credentials-guest-{debug,release}-v2/` and
`native-credentials-guest-readback-v2/{debug,release}/`. The first Release guest
remains failed because an exec fixture record was attached to the shell prompt;
the successor prefixes fixture records with LF and waits for identity-service
completion before control testing. The first Debug guest passed separately.
These results do not establish authentication, TTY ownership or clean shutdown.

## Pending login and synchronized shutdown

The selected login policy is a local account database with password verification
and interactive first-boot creation of an administrator account. No default
password or build-time account import is selected. The `app-login` target implements the selected flow. The explicit console
profile packages it as the ordinary service; the maintenance default remains
separate until the general journalled-root default is qualified. Numeric service identities and quiescence alone do not
establish login sessions.

The kernel now protects actual serial-console input with a scheduler-owned
bounded lease. Input defaults closed. Only the original PID1 manager can claim
and revoke kernel-issued epochs; a claimed child and its later forks retain
membership across exec. Leader death retires the whole epoch before completion
becomes observable. Native/Linux read/readv, poll and blocked retries use the
same authority; stale requests cannot consume a later epoch. UART intake remains
without echo. Hosted production/model, sanitizer and standalone twenty-row SDK
checks pass. Actual x86_64 Debug/Release archive-only guests also pass unrelated
root and old-descendant input/control denial while new input is buffered,
revocation of blocked read/readv/poll, fresh-epoch input and exact adopted-child
reaps. Separate source/product/serial readers pass. The ordinary PID1
console fork blocks on a pipe until its parent registers ownership, claims input
and sends a complete epoch frame. Unrelated services receive no lease.

First-boot persistence should use one protected versioned account database with
explicit unconfigured, pending and active states. A missing or malformed database
must not reopen enrollment. Account/home admission needs a trusted writable
journalled-root contract, root-authorized creation with exact initial nonroot
ownership where needed, protected database packaging and crash/restart proof.
The current mounted provider does not implement general chown; current disk
policy gives /home root-owned0700. RAM-root fsync success is not account durability.
The initial administrator policy fixes UID/GID 0 and `/root`; ordinary-user home
ownership is a later policy. Packaging seeds only an explicit unconfigured
`/etc/accounts.db` as root:root0600 and `/root` as root:root0700; both ext4
normalizers preserve that policy, refuse protected-path symlinks and refuse
preconfigured account imports. Host staging, actual image metadata/content and
read-only fsck checks pass. This does not establish native enrollment durability.
Bounded password and account-format code now exists:
PBKDF2-HMAC-SHA-256 with 600,000 rounds, 16-byte salts, 32-byte verifiers and no
default password. Published vectors, an independent Python hashlib oracle and
hosted UBSan checks pass. Format version 1 strictly admits one administrator and
the unconfigured/pending/active states; malformed or unsupported bytes do not
reset state. Independent crypto/parser review found no defect; a separate
ASan/UBSan roundtrip and failure-atomicity harness passed 155,552 cases. The
pure policy library also passes all twenty architecture/mode compile rows and
an independent original-object/dependency/archive reader. These remain separate
from native account authentication.

The internal store validates root-owned directory descriptors, a single-link
0600 database and a 0700 `/root`, refusing symlinks and unqualified providers.
It writes an exclusive same-directory staging file, completes file persistent
sync and close, renames it, then syncs the parent. Any attempted mutation that
fails poisons the current store; reopening inspects actual state. A complete
legal staged successor retains its chosen identity and requires password
authentication before recovery. Malformed or conflicting staged content holds
closed. Eleven hosted UBSan groups cover partial I/O, interruption, every open,
commit and recovery I/O failure, close handling and uncertain rename results.
The account encoder rejects noncanonical bytes after the name terminator before
staging-file creation.
The harness explicitly substitutes ownership and strong-sync capability; it
does not establish device or crash durability.

The login executable validates its PID1 parent, real/effective/saved root
credentials and inherited console descriptors, and displays the selected
`ObfuscationOS` name after protected store admission. Input flushes the current epoch
before each prompt and never echoes entered bytes. Enrollment uses only trusted
`getrandom` salt acquisition and publishes pending then active credentials.
Authentication requires the verifier's explicit success value; failed attempts
use a monotonic delay. After authentication it closes the store, enters a held,
validated `/root` dirfd, constructs a fixed session environment and directly
executes `oksh` in the same leased process. Nine hosted input groups and sixteen
hosted main-flow groups pass, including explicit verifier-error refusal, entropy
failure without fallback, authentication before recovery, ordered pending/active
publication, retry delay and failures before shell execution. The maintenance default starts `oksh`. Actual x86_64 Debug and Release SDK-only
journalled guests pass five boots per mode: first enrollment, restart with
wrong-password delay and successful authentication, logout/relogin, a real
staged-write interruption followed by authenticated recovery, and trusted-entropy
refusal without account mutation. Independent readers verify serial noecho,
PBKDF2, original build inputs and protected disk metadata. The staged interruption
and session identity observations use explicit test fixtures; the ordinary
console product is separately qualified without those wrappers.

The `ok_sync_persistent` wrapper uses UAPI0.9 with
`native_persistent_sync_profile=retained-linked-mounted-ordered-journal-device-flush-v1`.
Its six syscall words are explicit. Strict consumer and rehashed-contract
rejection tests passed in the prior ABI68 qualification, including twenty
architecture/mode SDK producers, their independent readers and twenty OS
consumers. The current shutdown development cohort requires ABI69 and rebuilt
extensions; those historical ABI68 results do not qualify its changed object
layouts. Installation has a separate exact evidence gate and reversible
predecessor retention. Consult the installed SDK manifest for the active cohort.
UAPI remains 0.9.0 and no native power syscall is assigned by the ABI69 bump.

After service quiescence, synchronized shutdown still needs a kernel workload
admission barrier, complete resource retirement, ordered runtime/root mount
detach or sealing, filesystem sync/device FLUSH and a supported platform action.
Host QEMU retirement remains separate. Physical M11 and manual M12 acceptance
remain deferred by the user; their software requirements stay in scope.
