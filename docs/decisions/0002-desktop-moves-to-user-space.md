# 0002: the prelinked kernel-space desktop is frozen

Date: 2026-10-24. Status: accepted.

## Decision

- `modules/system-gui` receives regression fixes only. No new application view,
  dialog or policy is added to the `KernelExtension` desktop.
- The desktop is rebuilt as user-space processes: a Wayland compositor, greeter,
  panel and separate applications (`feat/compositor`, `feat/desktop-apps`), on
  top of the display/input/seat UAPI (`feat/display-input-uapi`).
- The Kernel keeps a text rescue GUI and diagnostic shell under `kernel_gui`;
  its kernel-resident file manager and task manager move to `src/rescue/` and
  are not product features.

## Why

The current desktop runs in kernel service context, applications are views bound
to scheduler records rather than isolated processes, and the 8 x 4 KiB desktop
buffer slots are not shared mappings. The workstation plan (DESKTOP_APPS.md, G01)
already selects an isolated Wayland compositor. Continued investment in the
prelinked path produces code that the target architecture discards.

## Consequences

- Renderer tests and screenshots under `docs/gui/` remain as visual regression
  fixtures for the user-space desktop.
- `OK_SYSTEM_GUI boot=complete` stays the distribution completion marker until the
  compositor replaces it; the marker's meaning does not widen.
