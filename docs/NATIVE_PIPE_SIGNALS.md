# Private native pipe signal qualification

The collector rejects duplicate frame-accounting snapshots, privileged ARM CPSR
modes, and misaligned absolute instruction PCs as well as incorrect restart PC
deltas. x86 instruction addresses remain byte-aligned; RISC-V and Thumb retain
their two-byte alignment, while raw ARM mode requires four-byte alignment. These
collector checks do not execute a guest or qualify previously unsupported modes.

`tools/qualify_native_pipe_signal.py` consumes an explicitly hash-pinned SDK29
Debug export, matching target compiler, musl sysroot and exact OS source
inventory. It never opens or compiles a kernel checkout. All ten profiles remain
available. PPC retains scalar soft-float e500v2, RV32 retains its qualified musl
ABI, and n64 requires its explicitly pinned binary128 supplement.

The runner builds `tests/musl/native_pipe_signal.c` with the accompanying
`pipe_signal_raw.h` and unchanged `thread_syscall.h`. Compiler-emitted transitive
dependencies are pinned; merely hashing the C entry file is insufficient. Every
output directory is new. It runs an initial native pipeline, two complete probe
commands and a final native pipeline, retains exact command boundaries and
rechecks source/SDK/dependency hashes and offline ext4 consistency. Failed runs
retain their evidence without promotion.

`tools/native_pipe_signal_evidence.py` requires every initial owned WAIT to be
followed immediately by a bound ORIGIN. The ORIGIN PC is the captured continuation
following the syscall. Readiness rearm preserves origin/request/description/pipe
and advances only the current wait. Every interrupted retirement has the exact
current owner/wait and pin release, then an immediate SIGNAL record referring to
the original capture. EINTR has internal terminal result -4 and continuation PC;
restart has internal terminal result 0 and the original instruction PC. That
zero is retirement accounting, not a successful read return. SIGNAL is evidence
of the same retirement and cannot decrement the live-object ledger a second time.

The guest exercises raw EINTR, SA_RESTART, saved-PC/result edits, syscall-number
edits, fd/buffer/count edits, handler fd reuse, ordinary readiness fd reuse,
positive short progress, repeated restart, nested signals, and musl EINTR/restart.
Every signal is directed to a distinct nonleader reader; ownership, case ordering,
context fields, entry leases and resources must match. A restarted blocking call
requires a new arm and strictly newer origin. Descriptor replacement in the
handler resolves B on fresh entry, whereas ordinary readiness retains A. Context
edits control the subsequent user instruction; no hidden replay is accepted.

ARM has explicit ARM and Thumb raw forms with an ARM handler. PPC has initial
CR0.SO clear/set forms and checks saved SO/result/orig_r3. MIPS raw a3 is the
nonboolean original 0x1357. All per-target syscall numbers and error conventions
are validated. Native qualification does not infer MIPS branch-delay restart,
ARM IT-block execution or other unsupported instruction modes.

The synthetic fixtures in `tests/tools/test_native_pipe_signal.py` are parser
models. They test strict rejection of lost origins, stale waits, mismatched
owners, altered publication PC, wrong target contexts, missing cleanup, images,
faults, truncated events and Linux-only evidence. They are never native execution
or a substitute for the two actual QEMU commands. The separate sealed guest
stage provides all-ten compiler evidence and a Linux x86 reference; neither is
native OS evidence. Production signals, process-directed kill, no-handler
restart_syscall, other waits, SMP and physical hardware remain outside this test.

The PPC evidence decoder validates saved diagnostic_result and orig_r3 for both
restart and EINTR, including the libc EINTR path. The diagnostic result must be
zero on restart or the u32 representation of -EINTR otherwise; orig_r3 retains
the captured descriptor. Agreement between handler entry and return alone does
not establish either value. These checks do not add native guest executions.
