#!/usr/bin/env python3
"""Inspect an actual x86_64 terminal hold through QMP and linked instructions.

This observes emulated CPU state. It does not establish disk durability, physical
execution, poweroff or reboot. Callers must separately verify clean storage.
"""
from __future__ import annotations
import json
import re
import socket
import time
from pathlib import Path

TERMINAL_SYMBOL = "ok::arch::terminal_power_action(ok::SystemPowerAction)"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def terminal_site(disassembly: str) -> dict:
    """Require the linked CLI/HLT loop rather than accepting an arbitrary HLT."""
    header = re.compile(r"^([0-9a-f]+) <" + re.escape(TERMINAL_SYMBOL) + r">:$", re.M)
    matches = list(header.finditer(disassembly))
    require(len(matches) == 1, "exact terminal action symbol is missing or ambiguous")
    start = int(matches[0].group(1), 16)
    body = disassembly[matches[0].end():]
    require(not re.search(r"^[0-9a-f]+ <", body, re.M), "unexpected second disassembly symbol")
    instructions = []
    for line in body.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(.*?)\s*", line)
        require(match is not None, "unrecognized terminal disassembly line")
        instructions.append((int(match[1], 16), bytes.fromhex(match[2]), match[3]))
    require(len(instructions) == 3, "terminal hold is not the expected bounded instruction loop")
    cli, hlt, branch = instructions
    require(cli == (start, b"\xfa", "cli") and hlt == (start + 1, b"\xf4", "hlt"),
            "terminal hold does not disable interrupts before HLT")
    require(branch[0] == start + 2 and branch[1] == b"\xeb\xfc" and
            re.fullmatch(r"jmp\s+" + format(start, "x") + r" <" + re.escape(TERMINAL_SYMBOL) + r">", branch[2]),
            "terminal hold does not loop back to CLI")
    return {"symbol": TERMINAL_SYMBOL, "begin": start, "halt_instruction": start + 1,
            "halted_rip": start + 2, "bytes_hex": "faf4ebfc"}


def halted_registers(registers: str, site: dict) -> dict:
    fields = {}
    for field in ("RIP", "RFL", "CPL", "HLT"):
        matches = re.findall(r"\b" + field + r"=([0-9a-fA-F]+)\b", registers)
        require(len(matches) == 1, "missing or ambiguous CPU register: " + field)
        fields[field] = int(matches[0], 16 if field in ("RIP", "RFL") else 10)
    require(fields["RIP"] == site["halted_rip"], "CPU is outside the linked terminal HLT")
    require(fields["HLT"] == 1 and fields["CPL"] == 0, "CPU is not halted in kernel mode")
    require(fields["RFL"] & 0x200 == 0, "terminal CPU still accepts maskable interrupts")
    return fields


class Qmp:
    """One bounded QMP connection, retaining commands, replies and events."""
    def __init__(self, path: Path, transcript: Path, timeout: float = 5):
        self.transcript, self.rows = transcript, []
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.settimeout(timeout)
        self.connection.connect(str(path))
        self.stream = self.connection.makefile("rwb", buffering=0)
        greeting = self._read()
        require(isinstance(greeting.get("QMP"), dict), "QMP greeting missing")
        self.sequence = 0
        self.call("qmp_capabilities")

    def _save(self):
        self.transcript.write_text(json.dumps(self.rows, indent=2) + "\n")

    def _read(self):
        raw = self.stream.readline(1024 * 1024)
        require(raw and raw.endswith(b"\n"), "QMP response ended or exceeded capacity")
        value = json.loads(raw)
        require(isinstance(value, dict), "QMP response is not an object")
        self.rows.append({"direction": "receive", "value": value})
        self._save()
        return value

    def call(self, command, arguments=None):
        self.sequence += 1
        request = {"execute": command, "id": self.sequence}
        if arguments is not None:
            request["arguments"] = arguments
        self.rows.append({"direction": "send", "value": request})
        self._save()
        self.stream.write((json.dumps(request) + "\n").encode())
        for _ in range(64):
            reply = self._read()
            if "event" in reply:
                continue
            require(reply.get("id") == self.sequence, "QMP response identity differs")
            require("return" in reply and "error" not in reply, "QMP command failed")
            return reply["return"]
        raise ValueError("QMP event capacity exceeded")

    def observe_terminal(self, site, output: Path):
        cpus = self.call("query-cpus-fast")
        require(isinstance(cpus, list) and len(cpus) == 1 and cpus[0].get("cpu-index") == 0 and
                cpus[0].get("target") == "x86_64", "terminal observation requires one explicit x86_64 CPU")
        snapshots = []
        for index in range(2):
            if index:
                time.sleep(0.1)
            registers = self.call("human-monitor-command", {"command-line": "info registers"})
            require(isinstance(registers, str), "HMP registers are not text")
            fields = halted_registers(registers, site)
            snapshots.append({"registers": registers, "fields": fields})
        require(snapshots[0]["fields"] == snapshots[1]["fields"], "terminal CPU state changed")
        result = {"schema": 1, "scope": "Actual single x86_64 QEMU CPU terminal observation; no disk/physical/poweroff/reboot claim.",
                  "status": "passed", "site": site, "cpu": cpus[0], "snapshots": snapshots}
        output.write_text(json.dumps(result, indent=2) + "\n")
        return result

    def close(self):
        self.stream.close()
        self.connection.close()
