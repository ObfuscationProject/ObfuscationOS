# System GUI

ObfuscationOS now treats the graphical desktop as a system feature instead of a kernel test surface.

The low-level compositor still lives in the ObfuscationKernel submodule as `kernel-gui`. It owns the framebuffer compositor, taskbar drawing, window surfaces, pointer state, and the `gui.compositor` / `gui.desktop` services.

The base desktop is an ObfuscationOS-side C++ OOP kernel module package named `system-gui`. Its manifest lives at `modules/system-gui/system-gui.okmod`, and root filesystem images stage it as `/boot/modules/system-gui.okmod`. Demo GUI app packages live in `modules/system-apps` and are staged under `/boot/modules/apps`.

The kernel does not register System GUI as a built-in module during core boot. After boot, the OS module loader (`/bin/kmodload --all`, with the current kernel entry doing the same best-effort boot load until `execve` handoff is available) calls `OK_SYS_LOAD_MODULE`. The kernel reads the package through the VFS, or from the mounted SimpleFS rootfs package name when it came from the distro image, parses OKMOD metadata, validates `entry:oop`, `class:desktop` or `class:app`, required GUI imports, and the exported service, and starts it through `ModuleManager`.

The current loader path uses OKMOD metadata to bind a compatible C++ desktop-module ABI. Arbitrary external ELF relocation and text execution remain part of the kernel module roadmap, so the GUI module is external at the OS package/loading boundary while native dynamic linking is still growing.

The default GUI session provides:

- an artistic dark desktop background and taskbar;
- shell, file manager, and task monitor launchers;
- an ObfuscationOS Login window with root selected as the default user;
- CPU, process, and app availability status on the login surface;
- demo app windows: About ObfuscationOS, System Preferences, and Notes;
- a `system tui` command for text-mode system status and login context;
- recovery after the GUI compositor is restarted.

The debug shell remains available through the launcher and keyboard path, but it is no longer the visual definition of the desktop. The internal `kernel` account is only exposed when the shell is explicitly switched into kernel debug mode; normal root/user sessions do not list it.

## Files

- `modules/system-gui/system-gui.okmod`
- `modules/system-gui/system_gui.cpp`
- `modules/system-apps/*.okmod`
- `modules/system-apps/system_apps.cpp`
- `apps/kmodload/main.c`
- `external/ObfuscationKernel/include/ok/gui/compositor.hpp`
- `external/ObfuscationKernel/src/gui/gui.cpp`
- `external/ObfuscationKernel/include/ok/core/external_module.hpp`
- `external/ObfuscationKernel/src/core/external_module.cpp`
- `external/ObfuscationKernel/src/core/kernel.cpp`
- `tools/stage_rootfs.py`

## Validation

Build the kernel profile:

```sh
cd external/ObfuscationKernel
xmake f -P . -c -m debug -a x86_64
xmake -P . -y -b okernel
cd ../..
```

Build the distro images that stage `/boot/modules/system-gui.okmod` and `/boot/modules/apps/*.okmod`:

```sh
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
```

For a visible QEMU graphics path, run:

```sh
xmake qemu-distro-window --fs=simplefs
xmake qemu-distro-window --fs=simplefs --display=none --timeout=10
```

`qemu-distro-window` now builds a release `kernel_gui` image when `--kernel` is omitted, attaches the ObfuscationOS SimpleFS rootfs, and boots into the System GUI modules instead of the kernel debug shell. The regular `qemu-distro` and `distro-test` paths stay headless for CI. When QEMU uses the current emulated block path and the staged package is not visible through the guest VFS, the kernel uses the same built-in OKMOD metadata as a boot fallback so the login surface and app windows still appear.
