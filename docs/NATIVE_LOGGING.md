# Bounded native persistent logging

This OS-only slice supplies `/bin/logd` and `/bin/logger`. The explicit
`native_console_login=y` profile starts logd as an independent UID/GID 0 notify
service. Maintenance does not start it. Console login, recovery and HALT do not
depend on a logging reply. The system name is ObfuscationOS. This does not
complete M7 or the deferred M11 physical and M12 manual desktop acceptance.

`logger MESSAGE...` joins arguments with spaces and accepts 1 through 256 bytes.
It reports a sequence only after the complete successful reply and EOF. Failure
may mean an already persistent record whose acknowledgement was lost. Retrying
can duplicate a message; there is no exactly-once guarantee.

## Transport and identity

The endpoint `/run/logd.sock` is root-owned 0600 in checked root-owned,
non-writable directory ancestry. There is one active connection and backlog 1.
Connections use nonblocking pathname AF_UNIX SOCK_STREAM. Request admission has
one fixed 1000 ms monotonic deadline, including complete frame and suffix
validation. An admitted frame then receives one fixed 60000 ms persistence and
reply budget. Partial input, storage progress and partial replies never renew
either deadline. Clients start each send attempt within one fixed 1000 ms
setup/partial-send deadline. Only a successful complete send selects a fixed
60000 ms completion deadline, anchored to the monotonic sample immediately
before that final send. Syscall and scheduling delay before its return consume
the same budget, even when the return occurs after the setup deadline. The
complete reply and EOF must both arrive before that completion deadline;
neither progress nor syscall return resets it. Rollback and checked deadline
arithmetic overflow refuse. The 60000 ms profile cap allows margin for measured
native rotation work of roughly 29–33 seconds; it does not improve filesystem
latency or cancel synchronous I/O.
Buffers, work per service step and responses are bounded.
Native connect is immediate; resource exhaustion fails explicitly. Kernel
endpoint, stream-buffer and descriptor pools are shared; none are reserved.

A request is exactly `OKL1 DDD\n` followed by DDD opaque payload bytes, where DDD
is three decimal digits (001 through 256). The CLI cannot supply NUL arguments,
but the protocol safely encodes any byte. Extra already-buffered bytes,
multiple coalesced frames, invalid syntax/length and truncated EOF are rejected.
Stream packet boundaries and half-close are not framing. Later-arriving bytes
cannot revoke a first dispatched frame and are never processed as another
request. Ancillary receive capacity is zero; output flags/control length are
rejected. No descriptors are received.

The server accepts effective UID 0 and stores kernel SO_PEERCRED PID/effective
UID/effective GID snapshots. Clients verify the protected socket identity and a
positive server PID with UID/GID 0. Payload identity claims have no meaning.
These are connection snapshots, not per-record credentials, PID-incarnation
tokens, a stable boot ID or authentication between hostile root processes.
Timestamp is logd receive-time monotonic milliseconds, not wall time or a
kernel-authenticated source timestamp.

A pre-existing owned socket is probed once. Successful connect or EAGAIN
(including full backlog) never permits unlink. Only ECONNREFUSED, checked
socket type/0600/root ownership and unchanged named inode identity permit stale
removal. Wrong types, symlinks, changed inodes and ambiguous errors refuse.
Trusted-root, single-supervisor policy excludes hostile-root unlink races;
an atomic compare-and-unlink primitive would remove that assumption. Exit or
fatal native TERM leaves the RAM name for checked restart.

## Storage and recovery

`/var/log` is root-owned 0700 under checked `/` and `/var`. Both bootstrap
normalizers enforce guest permissions. `system.log` and `system.prev` are
regular root-owned 0600 single-link no-follow files, each at most 8192 bytes.
Named/opened identities are checked. Every physical write ends at or before the
next exact 1024-byte boundary. There is one writer and no accepted RAM queue.

A new file starts with a checksummed `OKLB1` sequence checkpoint. Fresh console
images seed the exact 33-byte sequence-0 checkpoint offline as root-owned 0600,
so ordinary startup does not allocate its first data block synchronously.
Maintenance does not seed a log. Runtime rotation still creates and persists
its own checkpoint. Records use
`OKLR1`, fixed-width hexadecimal server sequence and receive milliseconds,
PID/UID/GID, three-digit length, hexadecimal payload, FNV-1a framing checksum
and newline. The checksum detects accidental framing corruption; it is not
cryptographic tamper evidence. Complete record sequences strictly increase.
Payload newlines cannot forge records. Sequence overflow refuses operation.

Success (`OKL1 OK ` plus 16 hexadecimal sequence digits and newline) is prepared
only after the complete append, identity recheck, `ok_sync_persistent(file)`
and `ok_sync_persistent(directory)` succeed. Ordinary fsync is not substituted.
Volatile/unsupported providers refuse admission. Write, sync, close and
publication failures may leave durable unacknowledged bytes. The daemon fails
and supervision supplies backoff; uncertainty never produces success. Native
TERM is fatal with no final user flush handler; acknowledged records were
already persistent.

Before a record would exceed 8 KiB, logd syncs and closes current/probe holds,
renames current over previous, syncs the directory, creates a new current
exclusively and persists its checkpoint plus directory before appending.
Rename and create are separate transactions. Two files retain at most 16 KiB;
older acknowledged records deliberately expire through rotation.

Startup checks at most two bounded files and recovers the largest complete
sequence/checkpoint. Missing current with valid previous creates current;
both missing initializes sequence 0. A valid incomplete final record is
preserved through archival rotation, including a partial first record after a
complete checkpoint. History survives a second restart. A cut checkpoint or
legacy partial-only current that would discard a higher sequence in previous
refuses readiness and preserves both files. Complete corruption, wrong types,
hardlinks, ownership/mode changes and oversize also refuse. There is no
arbitrary truncation, O_TRUNC repair, corrupt-tail deletion or repair CLI.

An external reader of a replaced previous inode can retain native pending
orphan state and block later root mutations. Logging then fails without
acknowledging and can reopen after the reader closes/reclamation completes.
Continuous archive tail readers and uninterrupted retained-victim operation
are unsupported. Filesystem I/O/FLUSH is synchronous; socket deadlines do not
interrupt it. A write completing after its fixed persistence budget may leave
durable bytes but never prepares a success reply. PID1 retains its 3000 ms
ready timeout. logd checks a 2500 ms
userspace startup budget, then sends exactly one `R` and closes the inherited
writer only after storage/listener admission.

## Evidence boundaries

`tests/logging_tests.c` includes actual product protocol/storage/transport behind
deterministic syscall seams: all payload lengths/fragments, corruption/tails,
short/zero/oversized transfers, EINTR/EAGAIN, credential/ancillary refusal,
deadline/clock bounds, success-after-sync, startup/rotation fault positions,
checkpoint double restart, more than 129 rotations, descriptor accounting,
retained archive busy/recovery, stale sockets and readiness ordering.
Timing controls exercise actual code with a 32731 ms append/rotation, the exact
60000 ms boundary, unacknowledged late-write restart, fixed fragment/reply
expiry, delayed complete sends and combined send/reply or EOF delays. Separate
controls verify the final-fragment pre-send anchor, post-send clock rollback
and refusal of an eleven-second late readiness.
`tests/tools/test_logging.py` runs ASan/UBSan plus both actual normalizers on ext4
fixture images and independent e2fsck checks. LeakSanitizer is disabled under
the host execution ptrace; the harness maintains an explicit descriptor ledger.
These are hosted syscall-seam/packaging checks, not native provider, guest,
physical power-loss or desktop execution. Builds identify the explicit exported
SDK/architecture/mode. Guest/matrix qualification and canonical rollout remain
separate. There are no stdout/stderr collectors, kernel ring import, remote
syslog, compression, multiple archives, authenticated service labels or
wall-clock/boot identity.

The ordinary console disk product profile is
`ordinary-native-console-login-logging-v2`. Its exact service configuration and
product hashes include logd and logger, with a separate exact initial-checkpoint
hash. Fresh-image construction checks the checkpoint bytes in the actual image
before publication. Reuse checks immutable binaries/configuration plus root-owned
`/var`, private `/var/log` and bounded 0600 single-link live log metadata. Mutable
log bytes are not compared with the initial seed: incomplete/corrupt records and
missing current files remain daemon recovery/readiness decisions and cannot
prevent ordinary console access. A disk admitted for the older
console-only product does not match this selected build; existing account disks
are never overwritten automatically. The initial frozen logging candidate's
disk build correctly refused its stale console-only admission contract; that
failed build remains retained separately from this correction. Hosted real-image
controls cover evolved checkpoints/records, incomplete tails, preserved corrupt
bytes, missing current, archive metadata and initial-seed refusal after use.
