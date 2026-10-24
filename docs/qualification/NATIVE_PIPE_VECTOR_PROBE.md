# Private native pipe vector probe

`native_pipe_vector.c` exercises raw and musl readv/writev on all ten native
profiles. ARM/Thumb and both PPC CR0.SO input forms remain explicit. Two directions,
raw/libc variants and restart off/on produce eight groups (twelve on ARM/PPC).
Each group contains 36 fork/thread scenarios. Two commands across all ten profiles
produce 6,336 scenarios. Each command must restore the shell's live child-wait,
frame and entry-stack baselines and pass native `hello | cat` before and after.

The copied vector array has zero-length entries and two discontiguous payload
spans with different byte values. The guest inspects every payload and guard byte.
Blocked array mutation, array protection, payload mutation, mapping faults,
descriptor reuse and restart establish the distinction between retained metadata,
current payload and a newly admitted syscall. Case 35 protects only the second
span, then checks the first read span or the write pipe is untouched before retry.
Case 34 completes the initially blocked 4097-byte write request separately from
case 13's nonblocking partial transfer. Its reader verifies the 2048-byte first
segment and first 2048 bytes of the second segment before joining, then verifies
the last second-segment byte after join. The owned LARGE cursor must move
0 -> 4096 -> 4097, with PAYLOAD_BEGIN preceding final publication. Read case 34
retains the bounded 4096-byte read result. Case 32 retains all sixteen vector entries.

Signal cases validate typed origin, interrupted retirement, exact raw trap labels,
libc return/errno, nested delivery, nested vector waits, edited saved context,
thread/process exit and full exec. Exec checks fresh globals/TLS, reset caught
disposition, leader identity and retained pipe bytes. No successful marker can
substitute for owned kernel waits and source-bound operation assertions.

`native_pipe_vector_events.py` accounts scalar and vector requests in the same
read/write live pools. It checks full copied pairs, immutable rearm/retirement,
origin/signal adjacency and image teardown. `pipe_vector_guest_protocol.py` binds
those records to guest roles, current/fresh vectors, readiness order, signal frames,
output bytes and guards. `native_pipe_vector_evidence.py` adds the distribution
command, image and resource envelope. `qualify_native_pipe_vector.py` admits exact
SDK29, source, compiler, musl, QEMU and optional n64/PowerPC tool inputs. It builds
only the OS consumer through xmake; it does not compile kernel source.

The host Linux reference is an explicitly separate mode. It observes blocked
readv/writev via `/proc/self/task/TID/syscall`, uses an actual 4096-byte pipe and
runs the same source with `PIPE_VECTOR_LINUX_REFERENCE`. Linux excludes count17
(native cap16), overflowing total validation ordering, eager initial mapping
validation and case35 (whole-vector prevalidation differs). It executes 256 cases, observes 208
waits and checks sixteen full execs. Native mode contains no skips.

Physical hardware and manual desktop acceptance remain outside this probe.
No preadv/pwritev, arbitrary-size blocking-write coverage, automatic SIGPIPE, SMP or
production signal-enable claim follows from this evidence.
