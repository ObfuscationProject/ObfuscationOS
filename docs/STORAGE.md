# Persistent root filesystem

The OS discovers an external Virtio block device, checks for ext4, and asks the
kernel `Ext4FileSystem` to mount it. The OS selects root mount policy; filesystem
parsing and VFS mechanisms stay in the Kernel SDK. Unsupported ext4 metadata is
an error, never a reason to format the device. Missing disks or non-ext4 images
use the embedded archive rescue root.

## Format and platform scope

`rootfs-ext4` creates ext4 with 4 KiB blocks, 256-byte inodes, initialized inode
tables and the explicit features `extent,filetype,sparse_super,large_file`.
The first writer does not implement JBD2 journalling, metadata checksums,
64-bit descriptors, directory indexes, symlink traversal, rename or hard-link
creation. It supports inline extent mutation (four physical runs), sparse holes,
regular files and ordinary directories. See the Kernel's
`docs/modules/ext4-storage.md` for bounds and on-disk checks.

Real Virtio disk transports currently cover i386, x86_64, ARM32, AArch64, RV32,
RV64 and LoongArch. MIPS/MIPS64/PPC run native applications from the archive and
need separate PCI host bridge support for persistent disks. Disk discovery and
queue transfer are OS drivers, not kernel architecture dispatch.

## Keep data across sessions

Build a matching Kernel SDK and OS image, then create an initial disk once:

```sh
xmake -y -b distro_image
xmake -y -b rootfs-ext4
xmake qemu-distro --fs=ext4 --persist --interactive
```

The persistent task reuses an existing image without regenerating it. Inside
`oksh`, save or inspect a file and flush before closing the VM:

```text
notes /home/my-note.txt Saved in ext4
cat /home/my-note.txt
sync
```

Notes defaults to `/home/notes.txt` and calls fsync after saving. The default
non-persistent QEMU task uses a scratch copy. An explicit `rootfs-ext4` build
recreates the generated image; it is not an upgrade operation for a data disk.
For an installed toolchain without bundled QEMU, invoke the Python runner with
`--qemu /usr/bin/qemu-system-...` and the same `--persist --interactive` flags.

The non-journalled filesystem marks itself unclean before mutation and clean
after successful synchronization when no unlinked open inode remains. After
an interrupted write/session, repair offline with `e2fsck -f image` before
mounting again. There is no automatic repair or crash-atomic guarantee.

## Reproduce device/filesystem acceptance

```sh
python3 scripts/test_persistent_ext4.py --arch x86_64 \
  --qemu /usr/bin/qemu-system-x86_64 \
  --kernel build/x86_64/debug/distro/kernel.bin \
  --rootfs build/x86_64/debug/rootfs.ext4.img \
  --out build/x86_64/debug/persistence
```

This starts two separate QEMU instances using the same writable disk: native
`/init`/POSIX acceptance, save+sync, reboot, read+sync. It requires the real ext4
mount marker, runs `e2fsck -fn` after each VM, and checks the saved bytes with
`debugfs`. The original rootfs image is untouched; logs and a verified copy are
written beneath `--out`. This is QEMU execution, not physical-board validation.
