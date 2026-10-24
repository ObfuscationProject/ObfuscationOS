# Linux stat user qualification

SDK21 candidate; native UAPI remains 0.6.0. The Kernel contract is
`ObfuscationKernel/docs/LINUX_STAT.md`. This fixture belongs to ObfuscationOS and
links only the exact exported architecture/mode/compiler SDK. It never builds
Kernel source from an OS build.

All ten profiles retain statx256. x86_64 also implements kernel-stat144;
AArch64/RV64 implement kernel-stat128. Other raw legacy layouts remain ENOSYS.
Only qualified readonly or explicitly maintained ext4 metadata projects basic
Linux attributes. Default writable roots and other providers remain unqualified.
No full POSIX, ext4, workstation, physical or SMP completion is asserted.

## Repository entry points

`tools/qualify_linux_stat.py` builds the native runner and both static musl probes,
then serially executes all six policy/epoch pairs: maintained, readonly and
unqualified, each at -123456789 or 2208988800 seconds. Supply explicit `--arch`,
`--mode`, `--kernel-sdk`, `--sdk-manifest-sha256`, `--toolchain`, `--rootfs`,
`--musl-build`, and a new `--output`. PPC also requires `--ppc-clang`.

The maintained native process runs as UID/GID1000, creates objects, keeps an
unlinked file descriptor and renamed directory descriptor, detaches its cwd, and
executes the musl probe. Public stat/lstat/fstat/fstatat/fdopendir and raw statx
checks exercise actual user traps, signed time, flags, fd lifetime, symlink
following and guarded-copy boundaries. Nine linked final statx snapshots are
compared with independently parsed raw ext4 inode fields and final e2fsck.
Unlinked objects remain actual-user checks because process exit releases them.

Readonly controls query fixed objects with seeded metadata and require unchanged
image bytes. Unqualified controls require native metadata success but Linux
EOPNOTSUPP and unchanged image bytes. These are explicit mount-policy fixtures;
ordinary distribution root policy has not changed.

Individual tools are `build_linux_stat_runner.py`, `build_linux_stat_musl.py`,
`freeze_linux_stat_sources.py` and `test_linux_stat_user.py`. The last command
prepares by default; `--execute` boots the private image. The old prototype flag
`--execute-after-sdk20-delivery` remains a compatibility alias. Source inventories
bind local scripts, templates, native libc, driver and fixture dependencies.
`xmake/linux_stat_runner.lua` is copied into a private native build project.

The full workstation qualifier accepts `--linux-stat-musl-builds` pointing to the
explicit pinned musl root containing `ARCH/debug-optimized-v1` and optional
`--linux-stat-ppc-clang`. Each Debug/Release SDK row receives freshly built native
runners, a retained source inventory, static Linux-ABI probe manifests and six
independent guest receipts. Musl artifact mode is recorded separately from the
Kernel/OS mode; use of an optimized pinned libc does not relabel it as a new libc
build.

## Evidence boundary

The isolated x86 Debug prototype passed all six policy/epoch combinations. The
repository migration passed a fresh maintained/post2038 user guest. Both positive/negative x86_64 Linux readonly references pass9 nodes and45
observations each, with unchanged images. Other nine architectures and Release
remain pending candidate qualification. Hosted model
and sanitizer tests, target compilation, actual user execution and Linux
interoperability have distinct receipts. Linux references mount only copied
images inside disposable guests; no host mount or host-clock mutation is needed.

The supported provider remains a bounded nonjournalled ext4 subset. Paths retain
255-byte whole-path and 31-byte component limits. Device identities are local to
the mounted instance; cross-kernel comparisons use inode fields and within-mount
device consistency. General threads/signals, utimens, journalled times, expanded
extents, default-root adoption and the remaining M0-M12 plan are separate work.
