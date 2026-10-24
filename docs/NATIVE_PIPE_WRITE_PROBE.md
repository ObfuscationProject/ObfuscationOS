# Private scalar pipe write probe

`tests/musl/native_pipe_write.c` uses raw and musl scalar write on all ten
architecture profiles. ARM additionally covers Thumb and PPC both initial CR0.SO
states; both SA_RESTART settings run in every group. Each of 25 scenarios runs in
a real forked process with a writer pthread and parent status verification.

Coverage includes full-pipe interruption, PIPE_BUF atomic writes, nonblocking partial
large writes and complete blocking 4097-byte writes, source-byte mutation and mapping revalidation, retained open
descriptions after fd reuse, fresh resolution after caught interruption, ignored
and blocked signals, immediate EAGAIN/EPIPE, insufficient-space rearm, nested
signals/writes, edited sigreturn, thread/group/fatal cleanup and full ELF exec
replacement from a sibling or handler. Replacement verifies fresh globals and
TLS, leader identity, reset caught disposition and retained pipe contents.

A command runs 100 cases, or 150 on ARM/PPC. Two commands over ten profiles run 2200
cases. The independent Linux reference runs all 100 cases and explicitly
requests and verifies 4096-byte pipe capacity. Case 14 interrupts before progress,
then completes a fresh 4097-byte request through explicit retry or SA_RESTART.
The reader verifies the first 4096 bytes before joining the writer and the final
byte after join. A PAYLOAD_BEGIN marker binds the capacity release to the final
completion; byte proof may be printed after writer return due to scheduling. SIGPIPE is ignored for portable
EPIPE checks; this does not imply automatic native SIGPIPE support.

`tools/qualify_native_pipe_write.py` consumes explicit architecture/mode/compiler
pinned SDK29 artifacts only. It does not build or embed a Kernel checkout. The
shared scalar/vector ledger validates both small and LARGE write records,
including the exact 0 -> 4096 -> 4097 committed cursor. The strict write ledger matches copied pointer/count/fd/open description/pipe/request
and exact wait tickets, origin and signal publication, pin release and live
counts. The dedicated collector couples these records to guest actors, return
values, actual byte verification, causal order, nested/exec lifecycle and the
persistent init-to-shell child wait baseline. Read, futex, poll and child records
remain independently validated. Model/synthetic, static ELF, host Linux and
actual SDK-native results must be reported separately.

This probe does not claim writev/pwrite continuations, automatic SIGPIPE, arbitrary-size blocking-write coverage,
deliverable-signal/readiness-race completeness,
SMP, production enablement, full Linux/POSIX certification, physical-machine or
manual desktop acceptance. SDK-native qualification remains pending until root
runs and seals the complete matrix.
