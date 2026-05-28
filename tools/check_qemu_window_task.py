#!/usr/bin/env python3
"""Check that qemu-distro-window keeps normal xmake incremental behavior."""

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
        '"-c"': "qemu-distro-window must not clean external kernel config every run",
        '"--ccache=n"': "qemu-distro-window must not disable compiler cache",
        '"-r"': "qemu-distro-window must not force a rebuild",
    }
    failures = [message for token, message in banned.items() if token in body]
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    if '"-b", "okernel_image"' not in body:
        print("FAIL: qemu-distro-window should still build okernel_image incrementally")
        return 1
    print("qemu-distro-window incremental build policy: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
