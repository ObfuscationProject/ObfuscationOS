# Private x86_64 caught-signal execution fixture

`tests/musl/native_signal_delivery.c` is an experimental raw Linux ABI
fixture for an explicitly enabled x86_64 Debug Kernel. Ordinary builds still
return ENOSYS for action/return syscalls. This is not production signal support,
M3 completion, cancellation, blocked syscall restart, altstack or other ISA
frame qualification. The ten ordinary architecture profiles remain present.

The SDK-only qualifier builds the exact static-musl ELF and a fresh distribution
consumer, executes two invocations on ext4, and restores native pipeline/frame/
entry-stack baselines. Each invocation executes seven primary handlers and one
nested handler, blocked ordinary-signal coalescing, NODEFER, RESETHAND, edited
saved RAX, XMM preservation, and two fork children with corrupt return frames.
The children must terminate with SIGSEGV while their parent and shell survive.
The action/return fixture uses only same-group sends and disabled altstack.

The fixture also runs as the identical ELF on host Linux. Those runs establish
reference behavior, separately from OS QEMU execution and synthetic parser
checks. A success marker alone is insufficient: complete command boundaries,
resource retirement, ELF/SDK/input hashes and offline filesystem checks are
retained. The private Kernel option must never be mistaken for a qualified
release interface simply because its exported layout is still SDK28.

The optional `--probe pthread` lane instead executes
`native_pthread_signals.c` through ordinary musl `sigaction`, `raise`,
`pthread_create`, `pthread_kill` and `pthread_join`. A CPU-running peer must
receive exactly one directed signal with correct TLS/errno and blocked handler
mask; the main thread must receive only its own raise. This lane uses two
leases per invocation and the same independent resource-retirement checks.
Both Linux-reference and OS guest evidence must identify which lane executed.
A busy peer does not establish interruption of blocked syscalls or cancellation.

AArch64 integration is now under development using the same raw/libc probes
and architecture-specific SVC/restorer and FPSIMD corruption controls. The
qualifier admits only x86_64 or AArch64 Debug and checks profile-specific success
markers. Parser acceptance does not establish AArch64 execution; actual results
must be retained separately before any such claim. Other eight profiles remain
in scope but are not accepted by this dedicated two-profile experiment.
