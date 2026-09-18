#!/usr/bin/env python3
"""Check that qemu-distro-window keeps artifact-only incremental behavior."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "xmake" / "tasks.lua"


def task_body(text: str) -> str:
    start = text.index('task("qemu-distro-window")')
    end = text.index("task_end()", start)
    return text[start:end]


def main() -> int:
    body = task_body(TASKS.read_text())
    banned = {
        '"-c"': "qemu-distro-window must not clean configuration every run",
        '"--ccache=n"': "qemu-distro-window must not disable compiler cache",
        '"-r"': "qemu-distro-window must not force a rebuild",
    }
    failures = [message for token, message in banned.items() if token in body]
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    if '"-b", "distro_image"' not in body:
        print("FAIL: qemu-distro-window should build the OS distro_image incrementally")
        return 1
    for token in ("external/ObfuscationKernel", '"kernel_dir"', '"--kernel_gui=y"', '"okernel_image"'):
        if token in body:
            print("FAIL: qemu-distro-window must only consume kernel SDK artifacts")
            return 1
    print("qemu-distro-window artifact-only incremental build policy: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
