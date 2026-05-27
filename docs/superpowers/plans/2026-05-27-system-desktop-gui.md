# System Desktop GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution in this session because subagent spawning was not explicitly requested. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a filesystem-loaded system desktop GUI module, root documentation, and lightweight GitHub Actions CI.

**Architecture:** Keep `kernel-gui` as the compositor provider and add `system-gui` as an OS-side C++ OOP module package staged to `/boot/modules/system-gui.okmod`. After kernel boot, `kmodload` or the early `init` fallback calls `OK_SYS_LOAD_MODULE`; the kernel reads the OKMOD package through the VFS, validates the metadata, registers the compatible desktop module, starts it through `ModuleManager`, and routes the task monitor launcher to the existing task manager.

**Tech Stack:** C++23 kernel code, OKMOD metadata, xmake, Python helper checks, GitHub Actions.

---

### Task 1: Red Test For System Desktop Module

**Files:**
- Modify: `external/ObfuscationKernel/tests/kernel/roadmap/gui_tests.cpp`

- [ ] Add a failing roadmap test that expects post-boot loading of the OS-side `system-gui` module, a `gui.system-desktop` service, and a default login window.
- [ ] Run the focused kernel build/test command and confirm the test fails because the service/module is missing.

### Task 2: Implement System Desktop Module

**Files:**
- Create: `modules/system-gui/system-gui.okmod`
- Create: `modules/system-gui/system_gui.cpp`
- Create: `apps/kmodload/main.c`
- Create: `external/ObfuscationKernel/include/ok/core/external_module.hpp`
- Create: `external/ObfuscationKernel/src/core/external_module.cpp`
- Modify: `external/ObfuscationKernel/include/ok/core/kernel.hpp`
- Modify: `external/ObfuscationKernel/src/core/kernel.cpp`
- Modify: `external/ObfuscationKernel/include/ok/gui/gui.hpp`

- [ ] Add OS-side `system-gui` package metadata plus loader app.
- [ ] Add generic kernel external desktop module support with manifest, service export, scheduler/topology bindings, load metadata, default login surface, and stop/shutdown behavior.
- [ ] Stage `/boot/modules/system-gui.okmod`, then load/register/start it after core kernel boot through `OK_SYS_LOAD_MODULE`.
- [ ] Route `TaskbarApp::task_monitor` to `open_task_manager()`.
- [ ] Run the focused test and confirm it passes.

### Task 3: Documentation And CI

**Files:**
- Add: `.github/workflows/ci.yml`
- Add: `docs/GUI.md`
- Add: `docs/CI.md`
- Modify: `README.md`

- [ ] Document the filesystem-loaded GUI architecture and commands.
- [ ] Add root CI for submodule, UAPI, libc, and rootfs image checks.
- [ ] Run local validation commands that are available in this workspace.

### Task 4: Final Verification

- [ ] Run `git diff --check`.
- [ ] Run the relevant xmake validation commands.
- [ ] Report any unavailable checks with the exact reason.
