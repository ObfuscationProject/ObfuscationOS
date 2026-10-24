#!/usr/bin/env python3
"""Check the Virtio elapsed-time polling contract as a hosted model."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernel-sdk', type=Path, required=True)
parser.add_argument('--arch', default='x86_64')
parser.add_argument('--mode', default='debug')
parser.add_argument('--sanitize', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(root / 'tools'))
from kernel_sdk import validate_sdk
sdk = args.kernel_sdk.resolve()
validate_sdk(sdk, args.arch, args.mode)
with tempfile.TemporaryDirectory(prefix='os-virtio-poll-') as directory:
    output = Path(directory) / 'poll'
    subprocess.run(['g++', '-std=c++23', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    *(['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else []),
                    '-I', str(root), '-I', str(sdk / 'include'),
                    str(root / 'tests/drivers/virtio_poll_tests.cpp'), '-o', str(output)], check=True)
    subprocess.run([str(output)], check=True)
