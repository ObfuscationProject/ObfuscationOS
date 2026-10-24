# Bounded journalled disk root fixture

This is an opt-in SDK-only M4 storage experiment. The default ObfuscationOS
root image and `modules/boot/storage.cpp` are unchanged. The fixture links
against one explicitly selected architecture/mode Kernel SDK34 artifact; the OS
build does not compile Kernel source. It starts with a deliberately empty rescue
archive, completes recovery on an exclusive block session, retires that session,
mounts `Ext4MountedMetadata<1>` at `/`, sets `FileSystemMode::ext4_journaled`,
and loads `/init` by pathname from the disk. A copy of the static musl ELF is
written to the volume with `debugfs` and read back byte-for-byte before boot.

The image is the fixed 1 KiB, 32 MiB, metadata-checksummed ext4/JBD2 profile
already admitted by the bounded Kernel completion and metadata writer. `/init`
reads `/seed`, `/child`, `/other-owner` and its own inode, then changes only the
permissions of the pre-existing `/seed` regular file and `/child` directory.
Each change is followed by `fsync`. A second boot reads the same image without
modification. On a partial first change, `/init` can resume just the missing
change. No write, truncate, create, unlink, rename, general allocation, orphan
recovery, or application-save operation is advertised by this fixture.

The first mount is admitted only after `Ext4RecoveryCompletion` reports complete
home, journal and filesystem durability. The test wraps the real Virtio device
and records every successful write/FLUSH completion with sector, size, CRC32C
and status. The regular build has no control input. Fault campaigns place a
`JROOTCTL` record in the out-of-volume guard sector to stop immediately after
one completed call or return one synthetic I/O error before calling Virtio.
This control is disarmed before recovery without modifying ext4 bytes. The
failure tests distinguish a synthetic transport result from a real media error.

The evidence under `build/prototypes/native-journalled-root-sdk34-v1` contains:

| Class | Executed evidence |
| --- | --- |
| Normal disk-root boots | SDK34 x86_64, i386 and big-endian MIPS Debug: first boot has 22 completed writes and 21 FLUSH calls; clean second boot has no writes and 3 FLUSH calls. Both boots execute disk `/init`. An independent libext2fs CRC32C transaction model matches the entire final volume byte-for-byte; offline `e2fsck -fn` passes. |
| Completed-call interruption | On each of those three architectures, all 20 boundaries of the first chmod transaction have a retained cut image, a new-QEMU recovery boot, and a further clean boot. Each cut image and final image matches the independent whole-volume model. This is 60 cut, 60 recovery and 60 clean guest boots. |
| Fault returns | Each architecture runs five controls: corrupt journal-superblock checksum, prepublication FLUSH error, descriptor-write error, payload FLUSH error and post-publication FLUSH error. Rejection before root publication changes no disk bytes. Injected transaction errors reach `/init`; the disarmed restart recovers or retries, then clean-boots and passes offline `e2fsck -fn`. |

The exact SDK manifests, compiler and QEMU hashes, musl source artifacts,
on-disk `/init` hash, baseline image, commands, logs and disk hashes are pinned
in each JSON receipt. `tools/run_journalled_root_matrix.py` builds the three
representatives from the accepted SDK34 promotion receipt;
`tools/run_journalled_root_cuts.py` and
`tools/run_journalled_root_faults.py` consume one exact prepared build receipt.
The cut runner checks completed-call prefixes and complete disk bytes, and the
normal runner checks every write/FLUSH CRC against an independent transaction
oracle. A passed guest exit alone is not used as storage evidence.

This does **not** qualify a production root or full M4. Only 3 of 10 Kernel
architectures and Debug mode are covered here; the complete 20 architecture/mode
root matrix and interruption matrix remain open. There is no Linux guest
remount/unmount interoperability run for this candidate, no second e2fsprogs
version, no volatile-cache or torn-sector device model, and no physical power
loss or reference-hardware acceptance. A successful QEMU Virtio FLUSH is an
interface completion, not proof of host-cache or media persistence.

The fixture's `KernelExtension::start` sets the already-loaded initial process
to UID 1000 before entry. The SDK34 loader constructed Linux auxv while the
process still had UID 0; this fixture does not verify that `AT_UID`, `AT_EUID`,
`AT_GID` and `AT_EGID` match the later credentials. The observed `getuid` and
filesystem permission behavior therefore do not qualify an unprivileged login
or session policy. A controlled user `exec` with rebuilt auxv would be needed
for that separate claim.
