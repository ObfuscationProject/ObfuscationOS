# musl/BusyBox gate on the lifted kernel limits

Slice of `feat/linux-personality` (plan WT1.5), paired with ObfuscationKernel
`feat/linux-personality` (Kernel issue #6) and validated together with Kernel
`fix/mips-signal-resume` (#8) and `fix/ext4-node-cache` (#7, paired OS
`fix/ext4-node-cache`). It follows [MUSL_USERLAND](MUSL_USERLAND.md), whose
kernel-limit table this updates.

## Kernel limits from MUSL_USERLAND, now

| Limit | Kernel change | Here |
| --- | --- | --- |
| `execve` at most 16 argv/envp strings under 256 bytes | ARG_MAX-sized argument arena (#6) | Patch 0002 dropped; runtest exports its option list again |
| `execve` of a non-ELF file returns EINVAL; no `#!` | ENOEXEC and `#!` interpreters (#6) | Patch 0001 dropped; new-style tests run by path |
| ext4 caches at most 128 inodes per mount | Node eviction in both ext4 providers (#7) | `sh-acceptance` creates and stats 320 files per boot; patch 0003 is no longer needed for capacity and is kept for suite run time |
| No `/dev/zero`, `/dev/null` | `fs::DeviceFileSystem` (#6) | The storage module mounts it on `/dev`; the `tail -c +N` case passes |
| `CLONE_VM\|CLONE_VFORK` returns ENOSYS | Copy-on-write vfork (#6) | Ports no longer build with `-Dvfork=fork` |
| MIPS signal delivery stops the guest | Resolved-fault captures (#8) | mips and mips64 pass like the other profiles |
| `link`, `symlink`, `utimensat`, `uname`, `sysinfo`, `statfs`, `fchownat` not routed | Routed (#6) | `ln`, `touch`, `uname`, `hostname`, `uptime`, `chown`, `chgrp` join `/bin` |
| MIPS ABI flags in the first 128 KiB; ppc section table in the first 512 KiB | The loader grows the prefix to what admission asks (#6) | The recipe's size checks are gone; `bc`, `dc` and the `bzip2` compressor join `/bin` |
| Path components of 32 bytes or more | Unchanged | Still the 8 reviewed failures |
| `mknodat`, `/proc` | Unchanged | `mkfifo`, `mknod`, `ps`, `top`, `free` and `df` stay held back (`df` also needs a mount table) |

`sh-acceptance.sh` gains `many_files` (#7) and `exec_args`, `exec_env`,
`exec_script`, `exec_enoexec`, `dev_null`, `dev_zero`, `dev_full`, `uname`,
`uptime`, `hostname`, `links`, `chown`, `touch`, `statfs`, `listing`,
`listing_glob`, `bc` and `bzip2` (#6).

## Results

Integration trees: Kernel `fix/mips-signal-resume`, `fix/ext4-node-cache`,
`feat/linux-personality` and `chore/hosted-runners` merged on `main`; OS
`fix/ext4-node-cache` and `feat/linux-personality` merged on `main`.
SysToolchain 0.1.0 (GCC 14.2.0, QEMU 10.2.0), debug SDKs, BusyBox 1.37.0 on
musl 1.2.5 rebuilt with this branch's configuration and patches.

| Check | Profiles | Result |
| --- | --- | --- |
| Kernel `xmake test`, `kernel-sdk` | all ten | pass |
| `xmake port-build` BusyBox (106 applets on ppc) | all ten | `built-not-executed` |
| `qemu-distro --fs=ext4 --require-native` | all ten | pass |
| `sh-acceptance.sh`, 54 checks | all ten | pass |
| BusyBox `testsuite/runtest`, 13 applets, 151 cases | all ten | 134 pass, the 8 reviewed failures (31-byte path components), 9 untested |

The WT1.5 exit gate (the complete suite) still waits for 255-byte path
components, FIFOs and `/proc`.
