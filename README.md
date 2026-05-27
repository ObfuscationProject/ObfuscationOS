# ObfuscationOS

ObfuscationOS is now a tiny userland distribution for ObfuscationKernel.  The
repository builds a freestanding SDK, `libokcrt.a`, MVP user programs, and two
root filesystem images.

## Kernel Submodule

The kernel lives outside this tree:

```sh
git submodule update --init --recursive external/ObfuscationKernel
xmake build kernel-submodule-check
```

The expected first baseline is `v0.1.0` /
`104f2091feeed4a6f600ea371c44779de5b9bb85`.

## Build

The first-stage 64-bit architectures are `x86_64`, `aarch64`, `rv64`, and
`loongarch64`.

```sh
xmake f -a x86_64
xmake build sysroot
xmake build apps
xmake build rootfs-simplefs
xmake build rootfs-ext4
```

The top-level `xmake.lua` only wires the project together.  Architecture data,
toolchain definitions, targets, and developer tasks live under `xmake/` to match
the kernel submodule layout.

Useful validation commands:

```sh
xmake toolchain-check --all
xmake arch-matrix
xmake distro-test --kernel=external/ObfuscationKernel/build/linux/x86_64/debug/kernel.bin
```

Primary outputs:

- `sysroot/include`
- `sysroot/lib/libokcrt.a`
- `build/apps/*.elf`
- `build/rootfs.simplefs.img`
- `build/rootfs.ext4.img`

## Toolchain

If a configured cross compiler is missing, bootstrap it with:

```sh
xmake toolchain          # configured arch
xmake toolchains -a all  # every first-stage arch
```

Supported target triples are:

- `x86_64-elf`
- `aarch64-elf`
- `riscv64-elf`
- `loongarch64-elf`

## User Programs

The MVP image includes:

- `init`
- `oksh`
- `hello`
- `cat`
- `ls`
- `stat`
- `mkdir`
- `rm`

`oksh` is intentionally builtin-only until the kernel grows `fork`, `execve`,
`wait`, `pipe`, `select`, and `poll`.

## Root Filesystems

`rootfs-simplefs` creates a flat SimpleFS image for the current kernel path.  It
maps paths such as `/bin/init` to root entries such as `init`, with 512-byte
blocks and a maximum of 32 entries.

`rootfs-ext4` creates a standard EXT4 image with `/bin/init` and
`/etc/os-release`.  It is validated offline with `e2fsck -n`.

## QEMU

After the kernel submodule has been built:

```sh
xmake qemu-distro --fs=simplefs --kernel=external/ObfuscationKernel/build/linux/x86_64/debug/kernel.bin
xmake qemu-distro --fs=ext4 --kernel=external/ObfuscationKernel/build/linux/x86_64/debug/kernel.bin
```

Until the kernel mounts the supplied disk as the process root and hands off to
`/bin/init`, `qemu-distro` accepts the kernel debug boot marker as the smoke
baseline.  Once that dependency lands, the task should tighten to require the
`ObfuscationOS init: userland online` marker.
