# System GUI

ObfuscationOS now treats the graphical desktop as a system feature instead of a kernel test surface.

The low-level compositor still lives in the ObfuscationKernel submodule as `kernel-gui`. It owns the framebuffer compositor, kernel debug chrome, window surfaces, pointer state, and the `gui.compositor` / `gui.desktop` services. When System GUI is active, kernel taskbar/chrome rendering is disabled for the full-screen system surfaces.

The base desktop is an ObfuscationOS-side C++ OOP kernel module package named `system-gui`. Its manifest lives at `modules/system-gui/system-gui.okmod`, and root filesystem images stage it as `/boot/modules/system-gui.okmod`. System GUI apps are standalone tiny-c ELF programs staged in `/bin`: `/bin/oksh`, `/bin/settings`, `/bin/tasks`, `/bin/notes`, and `/bin/about`.

The kernel does not register System GUI as a built-in module during core boot. After boot, the OS module loader (`/bin/kmodload --all`, with the current kernel entry doing the same best-effort boot load until full `execve` handoff is available) calls `OK_SYS_LOAD_MODULE` for the desktop package only. The kernel reads the package through the VFS, or from the mounted SimpleFS rootfs package name when it came from the distro image, parses OKMOD metadata, validates `entry:oop`, `class:desktop`, required GUI imports, and the exported service, and starts it through `ModuleManager`.

The current loader path uses OKMOD metadata to bind a compatible C++ desktop-module ABI. Dock apps are not modules: login validates their ELF images, creates selected-user scheduler processes for them, and lets the System GUI host their windows until the user-space GUI drawing ABI is ready.

The GUI startup path provides:

- a full-screen ObfuscationOS Login greeter with root selected by default, plus a mouse-opened dropdown and Tab selection for the regular user;
- a pre-desktop state where app windows are not loaded yet;
- Enter/Space or mouse click to log in as the selected user;
- a distinct System Shell renderer with its own background, status panel, and dock;
- System app launchers handled by the System Shell dock instead of the kernel shell/file/task launchers;
- app windows launched after login from `/bin`: Tiny Shell, System Settings, Task Manager, Notes, and About ObfuscationOS;
- TUI startup selected by boot parameters/mode rather than by a GUI session picker;
- recovery after the GUI compositor is restarted.

The debug shell remains available through the launcher and keyboard path, but it is no longer the visual definition of the desktop. The internal `kernel` account is only exposed when the shell is explicitly switched into kernel debug mode; normal root/user sessions do not list it.

## Files

- `modules/system-gui/system-gui.okmod`
- `modules/system-gui/system_gui.cpp`
- `apps/settings/main.c`
- `apps/tasks/main.c`
- `apps/notes/main.c`
- `apps/about/main.c`
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
xmake f -P . -m debug -a x86_64 --kernel_gui=y
xmake -P . -y -b okernel_image
cd ../..
```

Build the distro images that stage `/boot/modules/system-gui.okmod` and the `/bin` app ELFs:

```sh
xmake -y -b rootfs-simplefs
xmake -y -b rootfs-ext4
```

For a visible QEMU graphics path, run:

```sh
xmake qemu-distro-window --fs=simplefs
xmake qemu-distro-window --fs=simplefs --display=none --timeout=10
```

`qemu-distro-window` now builds a release `kernel_gui` image incrementally when `--kernel` is omitted, attaches the ObfuscationOS SimpleFS rootfs, and boots into the System GUI greeter instead of the kernel debug shell. The regular `qemu-distro` and `distro-test` paths stay headless for CI. When QEMU uses the current emulated block path and the staged desktop package is not visible through the guest VFS, the kernel uses the same built-in `system-gui` OKMOD metadata as a boot fallback; dock apps still come from the `/bin` ELF programs.
