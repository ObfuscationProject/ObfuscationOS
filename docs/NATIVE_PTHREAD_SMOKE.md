# Bounded ordinary musl pthread execution

`tests/musl/native_pthread_smoke.c` uses the pinned musl 1.2.5 public pthread
implementation. Each invocation performs eight `pthread_create`/`pthread_join`
cycles with default attributes, real per-thread TLS and errno, caller-mask
inheritance and independent child unblocking, thread-specific values and their
destructors, and a checked nanosleep. It verifies the parent remains unchanged
after each join. Child unblocking is verified by reading the mask back.

`tools/qualify_native_pthread_smoke.py` consumes an exact SDK28 GCC artifact for
the selected architecture and mode. It does not compile Kernel source. The
qualifier retains the source inventory, musl sysroot, probe, SDK, linker inputs,
OS image, scratch ext4 disk and serial transcript, with explicit hashes. It runs
two complete probe invocations between separate native shell pipelines and
checks command boundaries, unique exact success markers, balanced frame/object
accounting and at least nine fresh entry leases per probe command: one process
and eight threads. Failures retain evidence and offline filesystem diagnostics.

The initial x86_64 Debug v2 guest passed two invocations. Ten target musl builds,
Linux-host execution and the admission parser were independently reviewed.
Compilation is distinct from guest execution; the all-ten Debug/Release guest
matrix remains a separate required gate.

This checks default-attribute stack execution, not guard-page fault enforcement.
It does not qualify cancellation, caught signal delivery, detached threads,
general pthread synchronization, SMP or full M3. All ten architecture profiles
remain required; this bounded smoke is not complete pthread support.

The earlier v1 probe did not query the child mask after a successful unblock.
An independent no-op-unblock mutant passed v1 and is rejected by v2. Original
v1 evidence is retained separately; new qualification uses the repaired source.
