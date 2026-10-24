# Private native signal interruption of sleep

The dedicated `qualify_native_signal_sleep.py` runner builds a fresh OS image
using an explicitly pinned architecture/mode-specific SDK29 export. It compiles
only OS sources and a static musl guest, retains the source/tool/artifact closure,
runs two complete probe commands surrounded by native pipelines, and checks the
scratch filesystem after execution. Ordinary production signals are not enabled
by this runner. This document describes the acceptance contract, not a completed
execution claim; retained campaign results establish which profiles passed.

`native_signal_sleep_evidence.py` validates the exact command, image source,
per-case sequence, final aggregate, resource retirement and native entry counts.
Each case identifies its receiver PID/TID, syscall form, relative/absolute mode,
time32/time64 layout and required interruption count. A counted kernel diagnostic
must match that receiver and an increasing wait generation, report the expected
EINTR/EFAULT result and precede the stored deadline. Repeated absolute calls must
retain the original deadline. Masked, ignored, expired and ordinary completion
cases must have no interruption diagnostic. Missing/duplicate/reordered or
outside-command events are rejected. A case flag or sender delay alone does not
prove the target blocked.

The probe covers libc nanosleep and clock_nanosleep plus the supplied raw syscall
forms. It distinguishes libc clock_nanosleep's direct error result from syscall's
errno convention. Remainder pointer faults use raw forms because a time32 libc
wrapper may copy a temporary remainder in userspace. Case processes validate
child status, sender thread completion and guarded buffers. Assertion diagnostics
are drained completely before the runner stops QEMU.

Synthetic parser controls are separate from actual native execution. Linux
qemu-user references characterize the ABI and libc only. The runner is single
CPU and does not qualify pipe restart, futex interruption, cancellation, job
control, production signals, SMP, physical machines or complete M3/M0-M12.

RV32 canonical Linux qualification uses libc and raw clock_nanosleep_time64.
The existing OS legacy syscall101 extension is excluded from this Linux ABI
probe because Linux RV32 does not provide legacy nanosleep. It remains a
separate documented ABI compatibility limitation, not a dropped architecture.
