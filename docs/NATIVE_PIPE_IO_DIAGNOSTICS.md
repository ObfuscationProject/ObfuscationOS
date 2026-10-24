# Composed pipe diagnostics

Scalar and vector reads share a read continuation pool; scalar and vector writes
share a separate write pool. `native_pipe_vector_events` accounts the combined
live counts, retained vector pairs and per-thread wait/origin generations. One
thread cannot hold simultaneous read and write waits. An unattributed image
publication may belong to another process, so it preserves every live owner's
request and generation history. Dedicated exec cases prove their own retirement.

`native_pipe_io_events` uses this combined ledger for incidental diagnostics in
the existing read, futex, poll, temporary-mask, full-exec and child-wait wrappers.
Every arm, optional origin, rearm and terminal is checked in the original event
order. Incidental caught signals are rejected. The dedicated scalar read/write
guests retain their own operation-specific checks and do not claim vector cases.

The read view preserves a nonempty placeholder at each validated write line.
Removing such lines entirely could hide an intervening operation between a
read arm and origin, or between interrupted retirement and signal publication.
The original transcript and command boundaries remain immutable. Final command
validation admits only actual records from the validated namespaces.

The write guest additionally checks the exact original description and pipe
across descriptor replacement. Closing/replacing the descriptor wakes its
blocked operation; the retained full pipe must rearm before the controlled
drain (or before the subsequent caught signal). These rearm events are distinct
from the PIPE_BUF case that drains one byte before enough space is available.
Neither path permits changing the copied input, count or retained object.

Synthetic composition tests include all ten profiles and all six current
collector families, malformed/unbalanced/pinned/oversized/unknown write records,
incidental signals, publication adjacency and descriptor-replacement ordering.
Additional all-ten controls interleave different-owner scalar/vector writes,
check shared live counts, reject mutated vector metadata and preserve original
publication adjacency in the inherited consumers. Historical transcript replay,
fresh native regressions and dedicated vector execution remain separate evidence.
