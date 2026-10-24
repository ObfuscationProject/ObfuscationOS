#!/usr/bin/env python3
"""Freeze the repository-owned stat harness and its complete local build inputs."""
from pathlib import Path
import argparse
import json
import sys

sys.dont_write_bytecode = True
from test_linux_stat_user import ROOT, SOURCES, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = {ROOT / name for name in SOURCES}
    for directory in ('sdk/include', 'lib/okcrt'):
        files.update(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    record = dict(schema=1, scope='linux-stat-user-harness-sources',
                  files={str(path.relative_to(ROOT)): sha(path) for path in sorted(files)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    print(args.output, sha(args.output))


if __name__ == '__main__':
    main()
