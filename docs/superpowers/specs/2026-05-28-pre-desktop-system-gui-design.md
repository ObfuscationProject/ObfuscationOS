# Pre-Desktop System GUI Design

## Goal

ObfuscationOS boots into a real pre-desktop login state in GUI mode. The full desktop shell, taskbar, launcher, and app windows appear only after a user logs in. Whether the system starts in GUI or TUI mode is controlled by boot parameters, not by a GUI session picker.

## Selected Architecture

Use the System Shell Renderer split:

- `kernel-gui` provides primitives: framebuffer presentation, surface allocation, input routing, shared buffers, and low-level compositor APIs.
- `system-gui` owns user-visible policy and rendering: greeter, desktop shell, background, dock/taskbar, launcher state, app layout, and session state.
- app modules still depend on `gui.compositor`, `gui.desktop`, and `gui.system-desktop`, but they should not be loaded during the greeter phase.

## Boot Flow

In GUI boot mode, `ok_load_boot_gui_modules()` loads only `/boot/modules/system-gui.okmod`. The System GUI module starts in `greeter` state and renders one full-screen, unframed login surface with `root` selected by default. Pressing Enter logs in as root, switches the module to `desktop` state, renders the full System GUI shell, and then loads the app modules.

In TUI boot mode, the GUI boot module path is not used; the system stays on the terminal path. The GUI greeter does not offer a TUI option.

## Rendering Contract

`kernel-gui` gets explicit shell/chrome modes so it can avoid drawing its own taskbar/window chrome while System GUI is rendering the greeter or desktop shell. System GUI uses full-screen unframed surfaces for the greeter and desktop shell, which makes its visuals distinct from kernel debug windows.

## Build Contract

`xmake qemu-distro-window` must not force a clean kernel config or rebuild. When no `--kernel` is provided it may ensure the external kernel profile is configured with `kernel_gui=y`, but it must use normal xmake incremental build behavior.

## Validation

Regression coverage should prove:

- the qemu-distro-window task does not contain forced clean/rebuild flags;
- loading `system-gui` opens only the greeter, with no app windows and no kernel taskbar launcher;
- pressing Enter on the greeter logs in as root, switches to desktop state, and permits app modules to appear;
- debug QEMU tests still pass;
- GUI release distro smoke reaches `OK_SYSTEM_GUI boot=complete`.
