"""Strict complete-line observer for the native user UDP QEMU probe."""

from __future__ import annotations

from collections import Counter

PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32",
            "loongarch64", "mips", "mips64", "ppc")
MODES = ("debug", "release")
PARENT = (
    b"OK_NATIVE_UDP parent=ready port=54321",
    b"OK_NATIVE_UDP parent=trunc-ready",
    b"OK_NATIVE_UDP parent=zero-ready",
    b"OK_NATIVE_UDP parent=fault-ready",
    b"OK_NATIVE_UDP parent=dup-ready",
    b"OK_NATIVE_UDP parent=reuse-ready",
)
CHILD = (
    b"OK_NATIVE_UDP child=ready port=54320",
    b"OK_NATIVE_UDP child=pass port=54320",
)
UDP_PASS = b"OK_NATIVE_UDP scope=hardware acceptance=pass processes=2 ports=2"
USER_PASS = b"OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass"
EXPECTED = frozenset((*PARENT, *CHILD, UDP_PASS, USER_PASS))
FAILURES = (
    b"OK_TEST_FAIL", b"acceptance=FAIL", b"shell_pipeline=FAIL",
    b"boot=failed", b"boot=degraded", b"NATIVE_USER_UDP_FAIL",
)


def expected_markers(arch: str, mode: str) -> frozenset[bytes]:
    if arch not in PROFILES or mode not in MODES:
        raise ValueError("native UDP observer needs a supported architecture and mode")
    return EXPECTED | {f"OK_NATIVE_UDP profile={mode} arch={arch}".encode("ascii")}


def observe(serial: bytes, *, arch: str, mode: str, final: bool = False) -> frozenset[bytes]:
    """Return unique guest markers after validating their profile and boot diagnostics."""
    required = expected_markers(arch, mode)
    profile = f"OK_NATIVE_UDP profile={mode} arch={arch}".encode("ascii")
    debug_pass_prefix = f"OK_TEST_PASS arch={arch} ".encode("ascii")
    if any(token in serial for token in FAILURES):
        raise ValueError("native UDP serial contains a failure token")
    normalized = serial.replace(b"\r\n", b"\n")
    complete, fragment = normalized.rsplit(b"\n", 1) if b"\n" in normalized else (b"", normalized)
    if b"\r" in complete or (final and b"\r" in fragment):
        raise ValueError("native UDP serial contains a bare carriage return")
    if final and any(token in fragment for token in
                     (b"OK_NATIVE_UDP", b"OK_USERLAND scope=hardware", b"OK_MODE", b"OK_TEST_PASS")):
        raise ValueError("native UDP serial has an unterminated marker")
    try:
        complete.decode("ascii")
        if final:
            fragment.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("native UDP serial is not ASCII") from error
    lines = complete.split(b"\n") if complete else []
    markers = []
    diagnostics = []
    for line in lines:
        if b"OK_NATIVE_UDP" in line or b"OK_USERLAND scope=hardware" in line:
            if line not in required:
                raise ValueError("native UDP serial has a wrapped or unknown marker")
            markers.append(line)
        if b"OK_MODE" in line:
            if mode != "debug" or line != b"OK_MODE debug":
                raise ValueError("native UDP serial has an unexpected mode marker")
            diagnostics.append(b"OK_MODE debug")
        if b"OK_TEST_PASS" in line:
            if mode != "debug" or not line.startswith(debug_pass_prefix):
                raise ValueError("native UDP serial has an unexpected architecture pass marker")
            diagnostics.append(b"OK_TEST_PASS")
    counts = Counter((*markers, *diagnostics))
    if any(count != 1 for count in counts.values()):
        raise ValueError("native UDP serial has a duplicate marker")
    positions = {line: index for index, line in enumerate(lines) if line in required}
    for chain in ((profile, PARENT[0]), PARENT, CHILD, (CHILD[1], UDP_PASS, USER_PASS),
                  (PARENT[-1], UDP_PASS)):
        present = [positions[line] for line in chain if line in positions]
        if present != sorted(present):
            raise ValueError("native UDP serial marker order is invalid")
    if mode == "debug" and diagnostics:
        mode_at = lines.index(b"OK_MODE debug") if b"OK_MODE debug" in lines else None
        passes = [index for index, line in enumerate(lines) if line.startswith(debug_pass_prefix)]
        profile_at = positions.get(profile)
        if ((mode_at is not None and passes and mode_at >= passes[0]) or
                (passes and profile_at is not None and passes[0] >= profile_at)):
            raise ValueError("native UDP debug diagnostic order is invalid")
    if final:
        if set(markers) != required:
            raise ValueError("native UDP serial is missing required markers")
        if mode == "debug" and set(diagnostics) != {b"OK_MODE debug", b"OK_TEST_PASS"}:
            raise ValueError("native UDP serial is missing debug architecture diagnostics")
    return frozenset(markers)
