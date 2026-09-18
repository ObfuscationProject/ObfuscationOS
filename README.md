# ObfuscationOS

ObfuscationOS owns the distribution: user programs, libc shim, root filesystem,
external drivers and compatibility code, external kernel extensions, and the
System GUI. ObfuscationKernel owns core kernel mechanisms, native interfaces,
boot/runtime code, and the low-level kernel compositor/debug GUI.

## Independent kernel SDK

There is no kernel source checkout or submodule in this repository. Build and
export the independent kernel repository first:

```sh
cd ../ObfuscationKernel
xmake f -y -a x86_64 -m debug
xmake -y -b kernel-sdk
cd ../ObfuscationOS
xmake f -y -a x86_64 -m debug
xmake -y -b kernel-sdk-check
xmake -y -b distro_image
```

The default input is `../ObfuscationKernel/build/sdk/<arch>/<mode>`. It can be
copied anywhere and selected explicitly with `--kernel_sdk=/path/to/sdk`.
ObfuscationOS never builds kernel sources. The SDK contains public headers,
`libokernel.a`, boot/runtime archive, linker script, boot image, and a manifest
with architecture, build mode, ABI/compiler information and SHA-256 hashes.
Missing, modified, or mismatched artifacts fail validation; no source-header
fallback or architecture globbing is used. The manifest content hash also enters
the compiler signature, so replacing an SDK invalidates consumer objects even
when copied headers retain old timestamps.

The `distro_image` target compiles OS-owned System GUI extension sources and
links them to the SDK archives. It is a statically linked boot extension; it
does not claim to implement arbitrary ELF module relocation/loading.

## Build

The four current userland targets remain `x86_64`, `aarch64`, `rv64`, and
`loongarch64`. The kernel independently retains all ten architecture profiles.
Export the matching kernel SDK before configuring each OS architecture/mode.
`arch-matrix` uses this default per-architecture layout; it rejects a single
`--kernel_sdk` override. A local toolchain override used by that matrix must
contain all four compiler triples in its `bin` directory.

```sh
xmake -y -b sysroot
xmake -y -b apps
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
xmake -y -b linux-driver-compat
```

Outputs are isolated by architecture and mode under `build/<arch>/<mode>/`:

- `sysroot/include` and `sysroot/lib/libokcrt.a`
- `apps/*.elf`
- `lib/liblinux-driver-compat.a`
- `rootfs.simplefs.img` and `rootfs.ext4.img`
- `distro/kernel.elf` and `distro/kernel.bin`

Validation:

```sh
python3 -B -m unittest discover -s tests/tools -p 'test_*.py'
xmake -y -b uapi-test
xmake -y -b libc-test
xmake -y -b compat-test
xmake distro-test --no-qemu
```

`compat-test` is an x86_64 host model test. Linux driver compatibility remains a
model, not a complete implementation of Linux kernel driver APIs. CI builds
and uploads the kernel SDK in a separate job; the OS job consumes only that
artifact. See [docs/CI.md](docs/CI.md).

## Toolchain

By default both projects resolve `systoolchain 0.1.0` from ObfuscationRepo with
its existing source-build policy. For an already installed toolchain, configure
both projects with the explicit opt-in:

```sh
xmake f -y -a x86_64 -m debug --systoolchain_dir=/path/to/systoolchain
```

The directory must contain `bin/<target>-gcc`, G++, Binutils, and the matching
QEMU executable for QEMU tasks. The OS extension compiler must match the SDK
compiler target and GCC version. This avoids silently mixing C++ object ABIs.

## User programs and GUI

The image contains `init`, `oksh`, basic file/identity utilities, `settings`,
`tasks`, `notes`, `about`, and `kmodload`. `oksh` remains builtin-only until
real process execution and `fork/exec/wait/pipe` are implemented.

The OS owns `modules/system-gui/`, including desktop/greeter policy and its
configuration package staged at `/boot/modules/system-gui.okmod`. The low-level
compositor remains in the kernel. Current GUI application behavior is an
in-kernel model associated with ELF metadata, not isolated user-mode execution.
See [docs/GUI.md](docs/GUI.md).

## Root filesystems and QEMU

SimpleFS is the current early module-loading path (flat entries, 512-byte
blocks, at most 32 entries). EXT4 images are checked offline with `e2fsck -n`.

```sh
xmake qemu-distro --fs=simplefs
xmake qemu-distro --fs=ext4
xmake qemu-distro-window --fs=simplefs
xmake qemu-distro-window --fs=simplefs --display=none --timeout=10
```

These tasks build the OS image from the configured kernel SDK. They never
reconfigure or rebuild a kernel repository. An explicit `--kernel=/path/to/image`
can override the selected image for testing. QEMU uses a temporary rootfs copy.
A debug boot marker verifies the kernel model tests; it is not proof that real
user-mode execution, hardware SMP, or dynamic native module loading works.
The OS runner requires `OK_SYSTEM_GUI boot=complete` after extension startup;
kernel boot/test markers alone do not complete distribution validation.
