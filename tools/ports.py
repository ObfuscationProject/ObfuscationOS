#!/usr/bin/env python3
"""Validate ports/*/port.json and print the build order.

  ports.py validate            check every descriptor
  ports.py order [NAME...]     print build order for the named ports (default: all)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTS = ROOT / "ports"
STATES = {"planned", "builds", "executes"}
PROFILES = {"i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"}
REQUIRED = {"name", "version", "archive", "sha256", "license", "depends", "profiles", "state", "build"}


def load() -> dict[str, dict]:
    ports = {}
    for descriptor in sorted(PORTS.glob("*/port.json")):
        data = json.loads(descriptor.read_text())
        ports[descriptor.parent.name] = data
    return ports


def validate(ports: dict[str, dict]) -> list[str]:
    errors = []
    for directory, p in ports.items():
        missing = REQUIRED - set(p)
        if missing:
            errors.append(f"{directory}: missing fields {sorted(missing)}")
            continue
        if p["name"] != directory:
            errors.append(f"{directory}: name {p['name']!r} differs from directory")
        if p["sha256"] and not re.fullmatch(r"[0-9a-f]{64}", p["sha256"]):
            errors.append(f"{directory}: sha256 is not 64 hex digits")
        if not p["sha256"] and p["state"] != "planned":
            errors.append(f"{directory}: state {p['state']} requires a pinned sha256")
        if p["state"] not in STATES:
            errors.append(f"{directory}: unknown state {p['state']}")
        if p["license"] == "review" and p["state"] != "planned":
            errors.append(f"{directory}: licence under review cannot leave planned")
        if not set(p["profiles"]) <= PROFILES:
            errors.append(f"{directory}: unknown profiles {sorted(set(p['profiles']) - PROFILES)}")
        if p["state"] == "executes" and not p["profiles"]:
            errors.append(f"{directory}: executes requires at least one qualified profile")
        for dep in p["depends"]:
            if dep not in ports:
                errors.append(f"{directory}: unknown dependency {dep}")
        if p["build"].get("system") not in {"configure", "make", "xmake"}:
            errors.append(f"{directory}: unknown build system")
    return errors


def order(ports: dict[str, dict], wanted: list[str]) -> list[str]:
    result: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in result:
            return
        if name in visiting:
            raise SystemExit(f"dependency cycle through {name}")
        visiting.add(name)
        for dep in ports[name]["depends"]:
            visit(dep)
        visiting.discard(name)
        result.append(name)

    for name in wanted:
        if name not in ports:
            raise SystemExit(f"unknown port {name}")
        visit(name)
    return result


def main(argv: list[str]) -> int:
    ports = load()
    if not argv or argv[0] == "validate":
        errors = validate(ports)
        for e in errors:
            print(e)
        print(f"{len(ports)} ports, {'ok' if not errors else f'{len(errors)} errors'}")
        return 1 if errors else 0
    if argv[0] == "order":
        errors = validate(ports)
        if errors:
            raise SystemExit("\n".join(errors))
        print(" ".join(order(ports, argv[1:] or sorted(ports))))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
