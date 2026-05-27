# System GUI

ObfuscationOS now treats the graphical desktop as a system feature instead of a kernel test surface.

The low-level compositor still lives in the ObfuscationKernel submodule as `kernel-gui`. It owns the framebuffer compositor, taskbar drawing, window surfaces, pointer state, and the `gui.compositor` / `gui.desktop` services.

The base desktop is an ObfuscationOS-side C++ OOP kernel module package named `system-gui`. Its manifest lives at `modules/system-gui/system-gui.okmod`, and root filesystem images stage it as `/boot/modules/system-gui.okmod`.

The kernel does not load it during core boot. After boot, the OS module loader (`/bin/kmodload`, with `init` directly invoking the same syscall until `execve` handoff is available) calls `OK_SYS_LOAD_MODULE`. The kernel then reads the package through the VFS, parses OKMOD metadata, validates `entry:oop`, `class:desktop`, required GUI imports, and the exported service, and starts it through `ModuleManager`.

The current loader path uses OKMOD metadata to bind a compatible C++ desktop-module ABI. Arbitrary external ELF relocation and text execution remain part of the kernel module roadmap, so the GUI module is external at the OS package/loading boundary while native dynamic linking is still growing.

The default GUI session provides:

- an artistic dark desktop background and taskbar;
- shell, file manager, and task monitor launchers;
- a startup status window with CPU and process metrics;
- recovery after the GUI compositor is restarted.

The debug shell remains available through the launcher and keyboard path, but it is no longer the visual definition of the desktop.

## Files

- `modules/system-gui/system-gui.okmod`
- `modules/system-gui/system_gui.cpp`
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
xmake f -P external/ObfuscationKernel -c -m debug -a x86_64
xmake -P external/ObfuscationKernel -y -b okernel
```

Build the distro images that stage `/boot/modules/system-gui.okmod`:

```sh
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
```

For a booted graphics path, build the submodule kernel image and run the QEMU GUI task from the kernel project when the local toolchain and QEMU are available.
