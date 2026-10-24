# Native journalled chmod recovery fixtures

These SDK30-only fixtures qualify the bounded regular-inode side mount described
in [NATIVE_JOURNALLED_MODE.md](NATIVE_JOURNALLED_MODE.md). They do not change the
default distribution root. Native execution, independent Linux execution and
offline transcript/disk checks are distinct evidence layers.

## Building explicit fixtures

`tools/test_journalled_mode_user.py` builds the ordinary UID1000/root/negative-clock
chmod fixture. `tools/test_journalled_mode_cut.py` builds a separate interrupt-only
fixture and requires `--cut-after 1..20`, UID1000 and an in-range clock. The normal
fixture retains its original source and behavior. The cut C++ is identical to
the implementation exercised by the original sixty-cut campaign.

`tools/test_journalled_mode_recovery.py` builds a separate recovery fixture with
a static musl reader. Each builder requires explicit architecture, mode, SDK
manifest hash, compiler directory, musl ELF/build receipt and image/facts hashes;
use its `--help` entry for the full argument list. The tools validate the SDK and
consume its exported objects and headers. They never compile Kernel sources.
Their output is a prepared image and `guest_argv`, not proof of execution.

Run each QEMU instance against disposable copies of both the boot image and the
guarded data disk. QEMU may hold an exclusive IDE boot-image lock even when the
fixture does not write that image. Concurrent processes must not share that
writable boot image. Preserve source images and original interruption snapshots.

## Recovery ownership and observations

On the second boot, the fixture acquires an exclusive, partition-bounded
`BlockSessions` writable session before constructing any mount or cache.
Overlapping aliases and device detach must fail while recovery owns the session.
It invokes exported `Ext4RecoveryCompletion` with session-relative bounds,
checks successful write/flush completions and all durability flags, then closes
the session. A stale session flush must fail without reaching the transport.
Only then does it construct the maintained-noatime mount and publish two VFS
aliases. `Ext4MountedMetadata::mount()` itself still requires a clean journal.

An unprivileged musl ELF compares pathname/descriptor/alias metadata, emits full
statx wire images for the seed, other owner and symlink, reads all 4,096 seed bytes
and the other payload, checks the symlink target, and calls file/directory fsync.
The fixture verifies normal exit, reaping, unchanged mount epoch and absence of
additional writes. A third boot repeats recovery admission and the same reader
on the completed disk, establishing clean-remount behavior for this profile.

The host oracle checks entry/owner/recovery/mount/user/exit ordering, exact sector
and flush sequences, byte counts, status, CRC32C and full statx bytes. It compares
the complete final guarded disk with the independently reconstructed cut result.
Cuts 1–10 retain the old inode; cuts 11–20 recover the committed inode.
The expected image must first be bound to the original native cut by
`tools/jbd2/journalled_mode_cut_evidence.py`; passing an arbitrary expected image
does not establish recovery correctness.

CRC32C of a complete checksummed block can have a fixed residue, so a matching
write CRC alone is not a unique byte-level identity for every intermediate
superblock. The pinned compiled implementation, final whole-disk comparison
and separate interruption snapshots provide the additional evidence. No claim
is made about interruption during this recovery campaign itself.

## Qualification scope

The original cut campaign covers twenty whole-completion boundaries on x86_64,
i386 and big-endian MIPS. Recovery and clean-remount campaigns use those retained
cuts. Normal chmod execution covers all ten Kernel architecture profiles; the
supported distribution userland matrix remains four profiles.

These are software transport-completion cuts. They do not simulate volatile cache
loss, torn writes, write reordering or physical power failure. The current
recovery profile remains synchronous, serialized and bounded; it does not close
default-root, general filesystem mutation, SMP or complete M4 acceptance.

## Retained transient transport failures

The first concurrent campaign encountered three MIPS recovery flush timeouts at
original chmod cuts 16, 17 and 18. Each failed before mount publication or user
entry. Their original disks and logs remain retained. Fresh copies of the same
original cuts and additional serialized pairs passed without changing the driver.
The timeout mechanism already uses a five-second monotonic deadline; its cause
has not been established or repaired by these results.

Six additional native boots start specifically from the three retained timeout
disks, then boot their recovered successors again. All pass exact disk, statx,
read and fsync checks. The cut-16 failure disk equals its original interruption
snapshot. Cut-17/18 failure disks already look clean after the final superblock
write, even though its flush timed out; the retry must still complete an initial
flush before publishing the mount. This tests those three observed failure states,
not every interruption point during recovery or concurrent transport stability.
