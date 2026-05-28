# Pre-Desktop System GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution in this session because the user already approved implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI boot stop at a real login greeter, move full desktop visuals into System GUI, and stop `qemu-distro-window` from forcing kernel rebuilds.

**Architecture:** Add compositor shell/chrome modes so `kernel-gui` can act as primitives while `system-gui` renders greeter and desktop shell surfaces. Split boot loading into greeter first, app modules after login. Remove forced clean/rebuild flags from the distro window task.

**Tech Stack:** xmake Lua tasks, C++23 kernel GUI/module code, OKMOD metadata, QEMU smoke tests.

---

### Task 1: qemu-distro-window Incremental Build

**Files:**
- Modify: `xmake/tasks.lua`
- Test: `tools/check_qemu_window_task.py`

- [x] Add a parser test that fails if qemu-distro-window uses `xmake f -c`, `--ccache=n`, or `xmake -r`.
- [x] Update the task to configure without `-c`, build without `-r`, and keep normal incremental behavior.
- [x] Run `python3 tools/check_qemu_window_task.py`.

### Task 2: Pre-Desktop Greeter State

**Files:**
- Modify: `external/ObfuscationKernel/include/ok/gui/compositor.hpp`
- Modify: `external/ObfuscationKernel/src/gui/gui.cpp`
- Modify: `external/ObfuscationKernel/include/ok/core/external_module.hpp`
- Modify: `external/ObfuscationKernel/src/core/external_module.cpp`
- Modify: `external/ObfuscationKernel/src/core/kernel.cpp`
- Modify: `external/ObfuscationKernel/src/core/entry.cpp`
- Modify: `external/ObfuscationKernel/tests/kernel/roadmap/gui_tests.cpp`

- [x] Add failing GUI roadmap tests for greeter-only load and Enter-to-login desktop transition.
- [x] Add compositor modes for kernel chrome, greeter, and System shell rendering.
- [x] Render System GUI greeter as a full-screen unframed surface.
- [x] On Enter, switch credentials to root, render the System desktop shell, and load app packages.
- [x] Ensure boot loading starts only the greeter.

### Task 3: Verification

- [x] Run the external kernel debug image build.
- [x] Run `python3 external/ObfuscationKernel/scripts/qemu_test.py --arch x86_64 --kernel external/ObfuscationKernel/build/linux/x86_64/debug/kernel.bin`.
- [x] Run `xmake qemu-distro-window --fs=simplefs --display=none --timeout=10`.
- [x] Run `git diff --check` in the root repo and the kernel submodule.
