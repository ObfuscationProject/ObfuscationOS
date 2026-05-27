# System Desktop GUI Design

## Goal

ObfuscationOS should load a base GUI that feels like a real system desktop, not an okernel test surface. The base desktop belongs to the OS repository as a module package and is loaded after kernel boot through a kernel module loader.

## Architecture

The existing `kernel-gui` module remains the low-level compositor and desktop service provider. The OS-side `system-gui` C++ OOP module is described by `modules/system-gui/system-gui.okmod` and staged to `/boot/modules/system-gui.okmod`; after boot, `kmodload` or the early `init` fallback calls `OK_SYS_LOAD_MODULE`. The kernel reads that package through the VFS, validates its OOP entry marker and GUI imports/exports, registers the compatible desktop module with `ModuleManager`, and starts it. The module depends on `kernel-gui`, requires `gui.compositor` and `gui.desktop`, exports `gui.system-desktop`, and owns the default desktop session state.

`system-gui` draws a modestly artistic first-run dashboard using the compositor: a dark desktop-compatible palette, system branding, launcher hints, and live kernel metrics supplied by the scheduler/topology bindings. It opens after the OS loader runs, not during core kernel boot. Debug shell remains available but does not define the default GUI.

## User Experience

The first screen is the desktop, taskbar, launchers, and one system status window. The status window uses an OS-facing title and text, while the taskbar launchers continue to open terminal and file manager workflows. The task monitor launcher should open the existing task-manager workflow instead of doing nothing.

## Testing

Roadmap GUI tests verify that `system-gui` is not loaded during core boot, is loaded from the filesystem package by the module-loader syscall, is registered as a non-built-in module, publishes its service, opens a default status surface, and renders to the framebuffer. Existing compositor, shell, file manager, and task manager tests remain in place.

## Documentation And CI

Root documentation should explain the distro/kernel split, build commands, GUI module boundary, and validation workflow. GitHub Actions should run lightweight distro checks without requiring GUI QEMU as the first CI baseline.
