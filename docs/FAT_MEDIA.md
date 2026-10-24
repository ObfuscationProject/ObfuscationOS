# FAT32 and exFAT data media

The boot storage extension mounts a supported FAT32 or exFAT whole-volume Virtio
disk at `/media`. The embedded archive remains the system root. Supported ext4
media continues to replace the system root. Unknown media keeps the archive;
recognized but invalid FAT media fails boot storage admission without formatting.
Partition discovery and mounting a second disk are not part of this profile.

`distro_image` requires freshly exported architecture/mode-specific Kernel SDK
artifacts containing `ok/fs/fat_fs.hpp` and `ok/fs/fat.hpp`. The SDK validator
checks the manifest and artifact hashes before compiling the extension. The OS
never compiles kernel filesystem sources. This is an additive provider API;
existing module ABI 74 and UAPI 0.16 layouts are unchanged.

The provider supports regular-file read/write, creation, truncation, directory
creation/listing, unlink/rmdir, retained descriptors after unlink, and ordinary
`fsync` device flushes. Disk names use case-insensitive ASCII (including FAT32
long names) within the current 31-byte VFS component limit. FAT media has fixed
root ownership with file mode 0644 and directory mode 0755. Requests for other
ownership or permission attributes are rejected before publication. This data
volume is not a POSIX root: hardlinks, symlinks and arbitrary chmod/chown are not
available. Use ext4 for those operations. Notes' atomic rename workflow is not
qualified for FAT.

Both formats are nonjournalled. They use dirty indicators and fail closed after
uncertain I/O completion; the implementation does not promise power-loss atomic
transactions or the stronger `sync_persistent`/clean system-power contract.
Use ordinary file/directory `fsync` or `sync /media` before host-controlled QEMU
stop/start tests. With no path, `sync` retains its existing system-root behavior.
See the Kernel FAT provider documentation for geometry and allocation limits.

## Native integration test

With a Release distribution image and an explicit exported Kernel SDK, run:

```sh
python3 -B scripts/test_fat_media.py --arch x86_64 \
  --qemu /absolute/path/qemu-system-x86_64 \
  --kernel /absolute/path/kernel.bin --filesystem fat32 \
  --mkfs /absolute/path/mkfs.fat --fsck /absolute/path/fsck.fat \
  --out /fresh/output/directory
```

Repeat with `--filesystem exfat`, `mkfs.exfat` and `fsck.exfat`. The runner creates
a new scratch image, executes `posix-check --fat-write`, `--fat-read` and
`--fat-delete` across separate guest boots, and runs independent read-only fsck
at each boundary. It retains serial logs, exact commands, hashes, and a file-bearing
image checkpoint. It tests QEMU execution, not a physical machine or power cuts.

Use `scripts/test_interactive_userland.py --posix-check` and
`scripts/test_persistent_ext4.py` for ext4/POSIX regression coverage. SimpleFS
packaging retains its existing capacity constraint and is not part of FAT or
ext4 acceptance.
