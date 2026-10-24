# Checked chmod on a maintained journal mount

This is a bounded M4 integration slice, not a writable workstation root or a
completed ext4/POSIX implementation. It uses exported Kernel SDK ABI30 artifacts.
The distribution build never compiles Kernel sources.

`Ext4MountedMetadata` selects its immutable policy at construction. The
`maintained_noatime` policy publishes checked metadata and permits the existing
credential-aware `change_mode` operation on supported ordinary regular inodes.
It retains ownership, link count, allocation and access/modification timestamps,
updates ctime from the active realtime source, and increments the inode version.
The permission decision and durable publication share the same admitted mount
operation. Legacy credential-free chmod and maintenance-only metadata mutation
do not bypass this policy. The later
[ordinary-directory extension](NATIVE_JOURNALLED_DIRECTORY_MODE.md) adds allocated
ordinary directories to this checked operation without changing SDK30 layouts.
Root/reserved inodes and symlinks remain unsupported. The regular-file fixture
described here retains its root-directory rejection check. Negative or post-2038
ctime is rejected before any write.

The separate `maintenance_only` policy retains the earlier trusted maintenance
interface. The new class layout changes the Kernel SDK/module ABI from29 to30;
consumers must validate architecture, build mode, compiler and all SDK hashes.

## Native fixture

The SDK-only fixture mounts one guarded, Linux-created journal volume at two VFS
aliases and directly enters a static musl ELF. Its ordinary UID1000 and root runs
cover pathname/descriptor/relative chmod, same-mode updates, SGID removal,
permission denial, unsupported types, retained descriptors across fork, fsync,
stale descriptors and stat/statx observations. A private root fixture initializes
a negative software realtime clock to exercise the filesystem rejection; the
public Linux clock setter correctly rejects negative input itself.

The mount is explicitly placement-constructed in the boot hook. SDK boot enters
`kernel_main` directly and does not run hosted global constructor machinery.
PowerPC execution requires the qualified `e500v2_v22` CPU and single-threaded TCG
profile in addition to `-smp 1`; the QEMU default CPU is a different capability.

The observed block wrapper logs completed actual Virtio calls. The host collector
checks exact operation order, write CRC32C and FLUSH order, inode/home-write
association, complete statx wire bytes, mount epochs, process exit/reaping and
the entire guarded disk against an independently reconstructed transaction.
The fixture issues no extra cleanup sync after the user's workload.

## Interoperability and interruption evidence

Independent Linux guests read all fixture inode attributes, both file payloads
and the symlink target, then unmount; e2fsck checks the resulting copies. The
Linux binary hash is pinned. Its source provenance is not established by these
tests, and no host filesystem is mounted by the tools.

The interrupted-workload fixture stops after a selected successful completion in
the first musl chmod. It emits `JMODE_CUT ordinal=N writes=N flushes=N`, disables
interrupts and never returns to userspace or flushes additionally. Each disposable
QEMU instance is then terminated by its owning runner. Separate disk and recovery
tools must validate the saved image; the cut marker alone proves no recovery.

These cuts retain whole completed writes. They do not model volatile cache loss,
torn writes, reordering, IRQ-driven writeback, SMP or physical power loss. Before
the inode payload is written, its future ctime is unobservable: early descriptor
checks validate the descriptor checksum and fixed fields without inventing the
future payload checksum. The old inode must remain visible before journal
publication; the committed inode must recover afterward.

Hosted models, parser corruption controls, native OS execution, Linux execution
and physical/manual acceptance are separate evidence layers. The native harness
can qualify all ten Kernel profiles; this does not expand the distribution's
four supported userland profiles. M11 physical and M12 manual acceptance remain
deferred. Additional filesystem operations, general allocation/cache coherence,
default-root adoption and broader ext4 feature profiles remain separate work.
