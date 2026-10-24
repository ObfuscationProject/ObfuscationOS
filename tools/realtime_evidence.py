"""Validate complete native/Linux user-mode clock receipts against a fixed UTC base."""
import calendar
import datetime
import re

POSITIVE = {"aarch64", "arm32", "rv64", "rv32"}


def fixture_seconds(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
        raise ValueError("RTC fixture requires exact YYYY-MM-DDTHH:MM:SS UTC")
    instant = datetime.datetime.fromisoformat(value)
    seconds = calendar.timegm(instant.timetuple())
    if not 0 <= seconds <= 0xffffffff - 60:
        raise ValueError("RTC fixture is outside the qualified nonwrapped source range")
    return seconds


def validate_realtime(serial, arch, fixture):
    expected = fixture_seconds(fixture)
    positive = arch in POSITIVE
    summary = {"fixture": fixture, "oracle_seconds": expected,
               "capability": "available" if positive else "unavailable", "personalities": {}}
    offsets = []
    for personality, repeats in (("NATIVE", 1), ("MUSL", 2)):
        prefix = "OK_" + personality + "_REALTIME"
        lines = [line for line in serial.splitlines(keepends=True) if line.startswith((prefix + " ").encode())]
        roles = {role: [] for role in ("parent", "fork", "exec")}
        for line in lines:
            if not line.endswith(b"\n"):
                raise ValueError("incomplete realtime capability receipt")
            text = line.rstrip(b"\r\n").decode("ascii")
            match = re.fullmatch(prefix + r" role=(parent|fork|exec) (.*)", text)
            if not match:
                raise ValueError("invalid realtime role receipt")
            roles[match[1]].append(match[2])
        if any(len(items) != repeats for items in roles.values()):
            raise ValueError("missing or duplicate realtime process roles")
        if not positive:
            wanted = "capability=unavailable errors=pass copies=unchanged monotonic=pass"
        elif personality == "NATIVE":
            legacy = "overflow" if arch in ("arm32", "rv32") and expected > 2147483647 else "pass"
            wanted = "capability=available legacy=" + legacy + " copies=pass sleep=pass"
        else:
            legacy = ("overflow" if expected > 2147483647 else "pass") if arch == "arm32" else "not-declared"
            wanted = "capability=available wrappers=pass legacy=" + legacy + " copies=pass sleep=pass"
        if any(value != wanted for items in roles.values() for value in items):
            raise ValueError("realtime capability or legacy-width claim differs from profile")
        sample_lines = [line for line in serial.splitlines(keepends=True) if line.startswith((prefix + "_SAMPLE ").encode())]
        if len(sample_lines) != (3 * repeats if positive else 0):
            raise ValueError("missing, duplicate or fabricated realtime samples")
        samples = []
        for line in sample_lines:
            if not line.endswith(b"\n"):
                raise ValueError("incomplete realtime sample")
            match = re.fullmatch(prefix + r"_SAMPLE role=(parent|fork|exec) seconds=(\d+) nanoseconds=(\d+) monotonic_seconds=(\d+) monotonic_nanoseconds=(\d+)", line.rstrip(b"\r\n").decode("ascii"))
            if not match:
                raise ValueError("invalid realtime sample")
            sec, ns, mono_sec, mono_ns = map(int, match.groups()[1:])
            if not (expected <= sec <= expected + 30 and 0 <= ns < 1_000_000_000 and 0 <= mono_ns < 1_000_000_000 and 0 <= mono_sec <= 30):
                raise ValueError("realtime sample does not match independent UTC/normalized-time oracle")
            offsets.append((sec - mono_sec) * 1_000_000_000 + ns - mono_ns)
            samples.append({"role": match[1], "seconds": sec, "nanoseconds": ns,
                            "monotonic_seconds": mono_sec, "monotonic_nanoseconds": mono_ns})
        if positive and any(sum(s["role"] == role for s in samples) != repeats for role in roles):
            raise ValueError("sample roles do not match native process lifetimes")
        summary["personalities"][personality.lower()] = {"roles": roles, "samples": samples}
    if offsets and max(offsets) - min(offsets) > 50_000_000:
        raise ValueError("realtime anchor changed across sleep/fork/exec or personalities")
    summary["offset_spread_ns"] = max(offsets) - min(offsets) if offsets else None
    return summary
