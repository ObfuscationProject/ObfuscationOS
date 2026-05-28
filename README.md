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

The expected first baseline is `v0.1.0-2` /
`b8a4d5af31141663686587b97409c53f29114f2e`.

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

The root repository also has GitHub Actions CI in `.github/workflows/ci.yml`.
It checks the kernel submodule baseline, UAPI, libc shim, and both root
filesystem image formats for the x86_64 first-stage distro.

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
- `kmodload`

`oksh` is intentionally builtin-only until the kernel grows `fork`, `execve`,
`wait`, `pipe`, `select`, and `poll`.

## System GUI

The kernel submodule provides the low-level `kernel-gui` compositor service and
debug chrome in C++. The user-visible greeter and desktop shell live on the OS
side at
`modules/system-gui/system-gui.okmod` and is staged into the root filesystem as
`/boot/modules/system-gui.okmod`. Small demo GUI apps live in
`modules/system-apps` and are staged under `/boot/modules/apps`. After the
kernel has completed boot, the OS module loader (`/bin/kmodload --all`, and the
current boot fallback until `execve` handoff is enabled) calls
`OK_SYS_LOAD_MODULE` to ask the kernel to load those packages. The desktop module
consumes `gui.compositor` / `gui.desktop`, exports `gui.system-desktop`, and
opens a pre-desktop ObfuscationOS Login greeter with root selected as the default
user. Pressing Enter logs in as root, switches to the System Shell renderer, and
then loads the About, Preferences, and Notes app modules. Text-mode TUI boot is
selected by startup parameters/mode rather than by a GUI session picker.
See [docs/GUI.md](docs/GUI.md).

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
xmake qemu-distro-window --fs=simplefs
xmake qemu-distro-window --fs=simplefs --display=none --timeout=10
```

`qemu-distro` is the headless smoke path used by CI. `qemu-distro-window`
builds a release GUI kernel when `--kernel` is omitted, attaches the SimpleFS
rootfs, loads the System GUI packages from `/boot/modules`, and keeps the QEMU
window open until it exits. Passing `--timeout` validates the same System GUI
path headlessly and exits after the boot marker. The headless release smoke
marker for that path is `OK_SYSTEM_GUI boot=complete`; debug-kernel distro
tests still accept the debug boot marker. QEMU runs against a temporary rootfs
copy so an open GUI window does not lock the staged image.
