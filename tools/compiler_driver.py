#!/usr/bin/env python3
"""Record each upstream libgcc compiler invocation and its actual output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("compiler driver requires compiler and arguments")
    directory = Path(os.environ["PIC_RUNTIME_LOG_DIR"])
    identifier = uuid.uuid4().hex
    command = sys.argv[1:]
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                   "PYTHONDONTWRITEBYTECODE": "1", "SOURCE_DATE_EPOCH": "1708128000"}
    result = subprocess.run(command, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log = directory / f"compile-{identifier}.log"
    log.write_bytes(result.stdout)
    record = {"argv": command, "returncode": result.returncode,
              "log": f"logs/{log.name}"}
    with (directory / "invocations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    sys.stdout.buffer.write(result.stdout)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
