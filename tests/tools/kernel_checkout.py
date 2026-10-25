"""The sibling ObfuscationKernel checkout used by producer/consumer suites.

Most SDK suites run against the exported SDK artifact alone. A few also load the
kernel's own SDK producer (tools/export_sdk.py) or read its source headers, to
prove that both sides of the boundary agree. Those exist only in a workspace that
holds both repositories, so they skip when the checkout is absent, as in the OS
CI, which consumes only the SDK artifact. The workspace lane sets
OK_REQUIRE_KERNEL_CHECKOUT=1, which turns a missing checkout into an error.
OK_KERNEL_CHECKOUT selects a checkout other than ../ObfuscationKernel.
"""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT = Path(__file__).resolve().parents[2]
KERNEL_ROOT = Path(os.environ.get('OK_KERNEL_CHECKOUT', ROOT.parent / 'ObfuscationKernel')).resolve()
PRODUCER = KERNEL_ROOT / 'tools/export_sdk.py'
INCLUDE = KERNEL_ROOT / 'include'
REQUIRED = os.environ.get('OK_REQUIRE_KERNEL_CHECKOUT') == '1'


def available() -> bool:
    return PRODUCER.is_file() and INCLUDE.is_dir()


if REQUIRED and not available():
    raise RuntimeError(f'OK_REQUIRE_KERNEL_CHECKOUT=1 but no kernel checkout at {KERNEL_ROOT}')

requires_checkout = unittest.skipUnless(
    available(), f'needs the sibling kernel checkout ({KERNEL_ROOT}); runs in the workspace lane')


def load_producer(name: str):
    """Load the kernel SDK producer as module `name`, or return None without a checkout."""
    if not available():
        return None
    spec = importlib.util.spec_from_file_location(name, PRODUCER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
