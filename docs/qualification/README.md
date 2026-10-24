# Qualification notes

Per-slice qualification notes for ObfuscationOS. Each file records one bounded
implementation slice, its exact scope, its tests and its limits at the time it was
qualified. They are historical records: `../GUI.md`, `../STORAGE.md`, `../VIRTIO_*.md`,
`../native-*.md` and `../plans/` describe current behavior, and the ledger-driven
`../plans/STATUS.md` is the capability matrix. Execution receipts live in the
separate ObfuscationEvidence repository.

| File | Subject |
| --- | --- |
| [JOURNALLED_BOOTSTRAP_METADATA.md](JOURNALLED_BOOTSTRAP_METADATA.md) | Journalled bootstrap metadata |
| [KERNEL_SDK31.md](KERNEL_SDK31.md) | Kernel SDK31 consumer boundary |
| [KERNEL_SDK32_INIT.md](KERNEL_SDK32_INIT.md) | Kernel SDK32 designated init contract |
| [KERNEL_SDK33_INIT.md](KERNEL_SDK33_INIT.md) | Kernel SDK33 designated init contract |
| [KERNEL_SDK65_DRAFT.md](KERNEL_SDK65_DRAFT.md) | Private Kernel SDK ABI65 source contract draft |
| [LINUX_STAT.md](LINUX_STAT.md) | Linux stat user qualification |
| [MIPS64_COMPILER_RUNTIME.md](MIPS64_COMPILER_RUNTIME.md) | MIPS64 binary128 user compiler runtime |
| [NATIVE_CHILD_EXIT_GUEST.md](NATIVE_CHILD_EXIT_GUEST.md) | Private child-exit userland probe |
| [NATIVE_CHILD_EXIT_LINEAGE_GUEST.md](NATIVE_CHILD_EXIT_LINEAGE_GUEST.md) | Private child-exit lineage probe |
| [NATIVE_CHILD_EXIT_PRESSURE_GUEST.md](NATIVE_CHILD_EXIT_PRESSURE_GUEST.md) | Private native child-exit pressure guest |
| [NATIVE_CHILD_EXIT_PRESSURE_QUALIFICATION.md](NATIVE_CHILD_EXIT_PRESSURE_QUALIFICATION.md) | Private SDK31 child-exit pressure qualification |
| [NATIVE_CHILD_LIFECYCLE_CONSUMERS.md](NATIVE_CHILD_LIFECYCLE_CONSUMERS.md) | Child lifecycle diagnostics in inherited signal collectors |
| [NATIVE_CHILD_WAIT_SIGNALS.md](NATIVE_CHILD_WAIT_SIGNALS.md) | Private child wait qualification |
| [NATIVE_FUTEX_SIGNALS.md](NATIVE_FUTEX_SIGNALS.md) | Native FUTEX_WAIT signal fixture |
| [NATIVE_JOURNALLED_DIRECTORY_MODE.md](NATIVE_JOURNALLED_DIRECTORY_MODE.md) | Ordinary-directory journalled chmod |
| [NATIVE_JOURNALLED_DIRECTORY_RECOVERY.md](NATIVE_JOURNALLED_DIRECTORY_RECOVERY.md) | Ordinary-directory chmod cuts and native recovery |
| [NATIVE_JOURNALLED_MODE.md](NATIVE_JOURNALLED_MODE.md) | Checked chmod on a maintained journal mount |
| [NATIVE_JOURNALLED_RECOVERY.md](NATIVE_JOURNALLED_RECOVERY.md) | Native journalled chmod recovery fixtures |
| [NATIVE_JOURNALLED_ROOT.md](NATIVE_JOURNALLED_ROOT.md) | Bounded journalled disk root fixture |
| [NATIVE_LOGGING.md](NATIVE_LOGGING.md) | Bounded native persistent logging |
| [NATIVE_MOUNT_INVENTORY.md](NATIVE_MOUNT_INVENTORY.md) | Native mount inventory |
| [NATIVE_PIPE_BLOCKING_WRITES.md](NATIVE_PIPE_BLOCKING_WRITES.md) | Complete blocking pipe writes |
| [NATIVE_PIPE_IO_DIAGNOSTICS.md](NATIVE_PIPE_IO_DIAGNOSTICS.md) | Composed pipe diagnostics |
| [NATIVE_PIPE_READ.md](NATIVE_PIPE_READ.md) | Owned scalar pipe read qualification |
| [NATIVE_PIPE_SIGNALS.md](NATIVE_PIPE_SIGNALS.md) | Private native pipe signal qualification |
| [NATIVE_PIPE_SIGPIPE.md](NATIVE_PIPE_SIGPIPE.md) | Private automatic SIGPIPE guest |
| [NATIVE_PIPE_VECTOR_PROBE.md](NATIVE_PIPE_VECTOR_PROBE.md) | Private native pipe vector probe |
| [NATIVE_PIPE_WRITE_PROBE.md](NATIVE_PIPE_WRITE_PROBE.md) | Private scalar pipe write probe |
| [NATIVE_POLL_MASK_EXEC.md](NATIVE_POLL_MASK_EXEC.md) | Temporary signal masks across exec |
| [NATIVE_POLL_SIGNALS.md](NATIVE_POLL_SIGNALS.md) | Copied poll/select signal fixture |
| [NATIVE_POLL_TEMPORARY_MASKS.md](NATIVE_POLL_TEMPORARY_MASKS.md) | Private ppoll/pselect temporary-mask execution probe |
| [NATIVE_PROCESS_SIGNALS.md](NATIVE_PROCESS_SIGNALS.md) | Native positive-target process signals |
| [NATIVE_PTHREAD_SMOKE.md](NATIVE_PTHREAD_SMOKE.md) | Bounded ordinary musl pthread execution |
| [NATIVE_RESOLVER.md](NATIVE_RESOLVER.md) | Native local resolver |
| [NATIVE_ROBUST_LISTS_PROBE.md](NATIVE_ROBUST_LISTS_PROBE.md) | Native robust-list probe |
| [NATIVE_SIGNAL_DELIVERY_X86_64.md](NATIVE_SIGNAL_DELIVERY_X86_64.md) | Private x86_64 caught-signal execution fixture |
| [NATIVE_SIGNAL_MASKS_PROBE.md](NATIVE_SIGNAL_MASKS_PROBE.md) | Native signal-mask probe |
| [NATIVE_SIGNAL_PROFILE.md](NATIVE_SIGNAL_PROFILE.md) | Ordinary bounded signal SDK capability |
| [NATIVE_SIGNAL_SLEEP.md](NATIVE_SIGNAL_SLEEP.md) | Private native signal interruption of sleep |
| [NATIVE_SIGNAL_WAIT_GUEST.md](NATIVE_SIGNAL_WAIT_GUEST.md) | Private synchronous signal wait guest |
| [NATIVE_THREADS_PROBE.md](NATIVE_THREADS_PROBE.md) | Raw thread execution probe |
| [NATIVE_ZERO_TRUNCATE.md](NATIVE_ZERO_TRUNCATE.md) | Linked-file zero-truncate user fixture |
| [NOTES_SAVE.md](NOTES_SAVE.md) | Default Notes save behavior |
| [OBJECT_PRESSURE.md](OBJECT_PRESSURE.md) | Actual userland object-pressure qualification |
| [SHARED_MUSL_BUILD.md](SHARED_MUSL_BUILD.md) | Shared musl build artifacts |
| [STATIC_IPV4_UDP.md](STATIC_IPV4_UDP.md) | Static ARP/IPv4/UDP service |
| [native-signal-production.md](native-signal-production.md) | Ordinary signal qualification |
