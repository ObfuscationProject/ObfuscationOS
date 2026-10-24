"""Compose typed child completion diagnostics with the inherited wait ledger.

The original bytes remain authoritative for command grammar and causal joins.
Only successfully parsed EXIT/REAP records leave the separate wait-ledger view.
These adapters do not establish a complete orphan or physical-reap ledger.
"""
from native_child_events import native_events as wait_events, boot_baseline as wait_boot_baseline
from native_child_events import WAIT, SIGNAL, parsed
from native_child_exit_events import native_events as exit_events, wait_ledger_view
from native_child_exit_join import join_native_waits


def native_events(span, arch, baseline=None, allow_signal=False,
                  signal_numbers=(10,16), pc_bounds=(0x40000000,0x80000000)):
    lifecycle = exit_events(span, arch)
    # The wait ledger requires an interrupted terminal and its signal
    # publication to be consecutive nonempty original lines. Filtering an
    # intervening typed completion must not accidentally satisfy that rule.
    pending = False
    for line in span.splitlines():
        if not line:
            continue
        if pending and not SIGNAL.fullmatch(line):
            raise ValueError('child signal publication separated in original transcript')
        pending = bool(WAIT.fullmatch(line) and parsed(WAIT, line)['outcome'] == 'interrupted')
    waits = wait_events(wait_ledger_view(span, lifecycle), baseline=baseline,
                        allow_signal=allow_signal, signal_numbers=signal_numbers, pc_bounds=pc_bounds)
    join_native_waits(span, lifecycle)
    return waits + lifecycle


def boot_baseline(boot, arch, required=False):
    lifecycle = exit_events(boot, arch)
    baseline = wait_boot_baseline(wait_ledger_view(boot, lifecycle), required=required)
    join_native_waits(boot, lifecycle)
    return baseline
