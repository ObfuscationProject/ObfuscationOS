# Bounded native PID 1 supervisor candidate

The static-musl program in `apps/init/pid1.c` is an OS-owned first service
supervisor. It requires an exported SDK33 with
`native_init_profile=designated-pid1-adoption-v1` and
`native_signal_profile=bounded-bootcpu-v1`. The kernel reserves user-visible
PID 1 and adopts Linux user descendants to that live process; `/init` supplies
the distribution policy. The [SDK33 init contract](../qualification/KERNEL_SDK33_INIT.md)
records the boundary. The OS build validates the SDK artifact manifest and
never compiles kernel source.

The current policy has one foreground service, `/bin/oksh`. PID 1 forks with
an explicit argument vector and small environment, uses a CLOEXEC error pipe
to distinguish exec failure, and never interprets a child PID as readiness.
It reaps with `waitpid(-1, WNOHANG)`, including adopted unknown children.
Every service exit schedules a bounded exponential delay; four quick exits
cause a two-second cooldown. A five-second stable run resets the quick-failure
count. PID 1 unblocks TERM and INT during initialization, then blocks them
while it checks pending stops, forks and
publishes a launch. Fork is the launch commit point: a stop observed in the
final pending check cancels the launch and records a stop request even if the
previous mask blocked that signal. A later stop is delivered on mask restore
and handled in the next supervision loop.
The child restores its inherited
signal mask before exec. TERM or INT begins shutdown: PID 1 sends TERM to the foreground child,
sends KILL after a 1.5-second deadline, waits at most another 0.5 seconds for
that child and any remaining adopted children, then reports a failure if the
deadline expires. The direct child remains waitable until PID 1 reaps it, so
the tracked numeric PID cannot be recycled before the stop signal.

`xmake musl-pid1-guests` builds the production init and two deterministic
acceptance executables from an explicit pinned Debug musl sysroot. To install
the production ELF in a distribution rootfs, configure xmake with both
`--managed_init_build=<production-init-build-directory>` and
`--managed_init_manifest_sha256=<exact-sha256>`. Rootfs staging verifies the
manifest, compiler-reported production source and policy header dependencies,
target architecture, static Linux ELF class, endianness, machine, executable
entry/load structure, target-word address bounds and digest before replacing
`/init`. Both Debug and Release OS
images currently use the pinned Debug static musl build; this is explicit
libc provenance, not a Release libc rebuild.

The acceptance guest deliberately uses a different compile-time service path.
Its child crashes twice, then creates a grandchild that becomes an adopted
orphan. The serial observer requires two matching service exit statuses,
the orphan's `getppid()==1` and wait-any status, and a clean TERM shutdown.
The pure policy assertions are hosted model tests; the SDK-only QEMU receipts
are actual user-mode execution. Neither implies physical hardware or SMP
qualification.

This is the early N2 supervisor base. It does not provide a service manifest,
readiness, dependency graph, control IPC, accounts, login, logging, persistent
configuration, filesystem sync/quiesce, rescue policy, or a full N6 shutdown
transaction. PID 1 failure currently returns a nonzero status to the kernel;
the kernel's documented init-death recovery path and generation-safe external
service control still need work before a managed-system release.
