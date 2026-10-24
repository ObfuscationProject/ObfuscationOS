# Raw thread execution probe

`tests/musl/native_threads.c` links the pinned musl1.2.5 startup and raw assembly
`__clone` trampoline. The public musl `clone()` wrapper intentionally rejects
THREAD/SETTLS/CLEARTID and is not used to construct a fake pthread. Child code
uses raw syscall trampolines and an explicit TLS block, without libc thread-state
access. This fixture does not claim pthread, signals, SMP or hardware support.

Each run performs16 create/retire cycles, verifies TID/TGID, separate TLS and
parent TLS preservation and PARENT_SETTID/CHILD_SETTID. At least one cycle must
complete an actually queued ordinary-futex wait from clear-child-TID on exit. A
predicate handles the valid zero-waiter result of the private gate WAKE. A
separate forked group exits its leader before a surviving peer writes through
shared descriptors and supplies the final group status. Two runs surround a
fresh native pipeline and verify user pages/object allocations return to baseline.

`tools/qualify_native_threads.py` consumes only an exact architecture/mode SDK27
and pinned matching-mode musl sysroot. It snapshots OS sources, builds a fresh
consumer and probe, retains compiler dependencies and raw QEMU serial, and
validates the original serial boundaries again after termination. A complete
failure diagnostic is retained before QEMU is stopped. All failures keep their
original receipts; changed fixture sources require a new generation.

The first probe attempted the public clone wrapper and was rejected by musl
before syscall entry. A later gate assertion incorrectly required a waiter to
have queued before its user predicate was published. The corrected predicate
allows WAKE0/1. SDK27 later exposed a second fixture race: the child may exit
before the parent enters clear-TID WAIT, producing legitimate EAGAIN with an
already-cleared word. The corrected check accepts that case, requires a zero
TID and successful child checks, and separately counts actual zero-return exit
wakes. A checked child timeout encourages queued waits; it is not assumed to
guarantee scheduling. Zero actual exit wakes across all16 cycles still fails.
These author failures remain failed evidence.

Ten architecture probe compilations are not ten architecture executions. Actual
results belong to the exact SDK/source/guest receipts, not this document.
