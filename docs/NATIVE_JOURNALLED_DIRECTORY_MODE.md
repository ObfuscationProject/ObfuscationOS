# Ordinary-directory journalled chmod

This bounded extension uses the immutable `maintained_noatime` side-mount
policy and exact Kernel SDK ABI30 artifacts. It adds allocated ordinary
directories to checked chmod. Root inode2, reserved inodes, symlinks, namespace
changes and allocation changes remain unsupported. SDK public layouts are
unchanged; exported artifact hashes must still match the new producer.

Directory mutation preserves inode type, uid/gid, all directory entries,
extents, size, block count, links, atime, mtime and birth metadata. Only permission
bits, qualified ctime, inode version and their checksums may change. Recovery
independently validates this narrow byte allowlist and existing allocated
directory structure. The mounted trusted `maintenance_only` update interface
remains limited to regular files.

Directory enumeration uses readability saved by the successful open description.
After removing read/search permission, a retained readable descriptor, duplicate
or fork-inherited description can still enumerate the directory. Fresh opens,
relative pathname search and fchdir continue to check current permissions.
Saved readability does not grant search permission or chmod authority. The
unreadable-description rejection is a hosted synthetic control because writable
directory opens and O_PATH descriptors are not supplied by this profile.

## Separate automated fixture

`tools/jbd2/journalled_directory_image.py` derives a disposable image from an
explicitly pinned regular-mode Linux fixture. It creates `/child/leaf` at inode16
inside the ordinary directory inode14, preserving the existing seed, second
owner and symlink. Offline e2fsck checks are fixture preparation, not native
execution.

`tests/musl/journalled_directory_mode.c` directly calls static musl from native
user mode through the SDK-only `tests/native/journalled_directory_mode.cpp`
fixture. Owner and root workloads check mode/SGID/sticky behavior, same-mode
updates, statx, aliases, dirfd-relative chmod, fork-retained descriptors, namespace
entry identities, leaf and complete seed contents, search revocation/restore,
unsupported types, fsync and stale descriptors. Negative and post-2038 clock
cases reject unsupported ctime before writes. User and root identities are
selected before entry; the private root negative-clock case is separate.

The observer records completed actual Virtio writes/flushes. The strict collector
checks complete framing, Linux loader order, operation order, inode home-write
association, full statx bytes and the complete guarded disk reconstructed by a
type-preserving libext2fs-based oracle. The independent Linux fixture checks six
inode records, three payloads, the symlink, readonly disk identity and e2fsck.
Each actual run must retain the SDK/source/tool/binary hashes and process result;
parsing synthetic logs does not establish execution.

The existing regular-file tests are retained separately. These tests do not
establish a default journalled root, full ext4/POSIX/M4, SMP, physical power-loss
durability, M11 physical acceptance or M12 manual desktop acceptance. A successful
guest FLUSH is a Virtio-interface observation; a new QEMU process can acknowledge
a clean-image FLUSH without issuing a host sync. Whole completed-file software
cuts and exact byte recovery must not be reported as physical durability.

## Repaired-source automated qualification

The final 869-file Kernel candidate uses SDK30 with unchanged public layouts and
new exact artifact hashes. Its inherited generation-exhaustion regression,
directory/regular-file ASan/UBSan tests, all-ten Linux directory dispatch and ABI
layout comparisons pass. Earlier candidates performed a redundant metadata read
before writer admission and failed cache-generation exhaustion; their successful
guest runs were retained as diagnostics and excluded from final qualification.

Fresh qualification passes 20 architecture/mode SDK builds, ten private Debug
standalone boots and one ordinary Debug boot with experimental signals disabled.
Thirty native directory workloads and thirty independent Linux readonly checks
pass 373,338 user checks, 120 directory changes,
1,320 writes and 1,140 guest FLUSH completions.
Conditional clock-boundary assertions make the C check count timing-dependent;
each exact execution record retains its observed count. The existing regular-file
probe also passes on the repaired x86 SDK. Five ordinary distro links and ten
boots preserve the four distribution profiles and the existing default root.

The separate [interruption and recovery campaign](NATIVE_JOURNALLED_DIRECTORY_RECOVERY.md)
qualifies sixty software completion boundaries, 120 native recovery/clean boots
and sixty Linux recoveries. Source/model, QEMU, Linux and physical evidence remain
separate. These bounded results do not close an entire workstation milestone.
