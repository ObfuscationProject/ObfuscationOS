# Complete blocking pipe writes

`tests/musl/native_pipe_blocking.c` exercises scalar `write` and copied `writev`
requests larger than the 4096-byte pipe capacity. The probe uses the validated,
architecture-specific Kernel SDK and the existing musl xmake guest adapter. It
never builds a kernel checkout. These private qualification guests do not enable
production signal support, establish SMP behavior, or qualify physical hardware.

All ten profiles are retained: x86_64, i386, aarch64, arm32, rv32, rv64,
loongarch64, mips, mips64 and ppc. Each profile exercises raw traps and libc,
with and without SA_RESTART. ARM also exercises Thumb and PPC both incoming SO
states. There are 26 scenarios per group, 208 cases per ordinary invocation and
312 on ARM/PPC. Two dedicated commands, bounded by native `hello | cat` runs,
are required by `tools/qualify_native_pipe_blocking.py` (`pipe-blocking-writes`).

The scenarios cover complete multi-wait writes, a final one-byte suffix,
zero-progress EINTR and restart, committed-prefix signal returns, reader loss
and automatic SIGPIPE, an unpublished-page fault, copied iovec metadata,
revoked consumed pages, changed unpublished payloads, descriptor replacement,
shared O_NONBLOCK changes, ignored signals, handler thread exit, group exit,
full exec replacement, fatal signals, original small atomic writes, immediate
nonblocking operations, zero-length writes, and two simultaneous write owners.
The two writers retain distinct pipes and independently patterned byte streams.
Their explicit 64 KiB stacks and 4 KiB guards keep both stack allocations and
two 64 KiB payload mappings inside the native 128-page process limit. Default
musl stacks previously caused the second thread creation to return EAGAIN;
that failed native experiment is preserved outside the source inventory.

Each consumed byte is compared against its logical offset and stream. Prefixes
consumed before interruption remain part of the proof. READ_BEGIN records bound
when a reader may first release capacity; BYTES records attest the completed
read and checksum. Full 64 KiB mapping guards and original descriptor metadata
are checked before cleanup. A positive committed count must not authorize a
restart, while a zero-progress restart must acquire a fresh owned request.
Reader-loss SIGPIPE is associated with an error terminal, not a caught-signal
interruption. The small-write scenario explicitly retains all-or-nothing
publication after a one-byte drain.

`tools/native_pipe_large_events.py` and the shared scalar/vector ownership ledger
validate immutable original requests, copied vectors, retained descriptions,
monotonic bounded committed cursors, exact origin PCs, live-owner counts,
terminal causes, adjacent caught-signal records and cancellation. The dedicated
protocol additionally binds diagnostics to guest operations, verifies that
publication follows available capacity, enforces native descriptors below 32,
and checks lifecycle ordering and byte proof scope. Native fixtures, including
resource accounting and full command boundaries, remain synthetic parser tests;
they are not evidence that a native syscall executed.

The inherited scalar case 14 and vector write case 34 now drain and verify the
first 4096 bytes before joining the writer, require a full 4097-byte return, and
verify the final byte afterward. Their strict collectors require LARGE
ownership records. The nonblocking partial-write and original small atomic
regressions remain distinct.

The optional `PIPE_BLOCKING_LINUX_REFERENCE` build observes blocked syscalls via
`/proc/self/task/TID/syscall` and actual pipe occupancy. It executes 200 cases
and explicitly excludes the eight instances of native final-suffix case 2,
because Linux pipe-page geometry differs. No native case is skipped. Linux
reference execution, compiled assertion controls, static ten-profile ELF trap
checks, synthetic parser controls and actual native QEMU campaigns are separate
evidence classes. Hardware and manual desktop acceptance remain outstanding.
