# Kernel SDK31 consumer boundary

SDK31 plus the explicit [ordinary signal capability](NATIVE_SIGNAL_PROFILE.md)
is required by this consumer successor. The qualified private lifecycle baseline
below remains historical evidence until the new ordinary build passes its own
integration gates. SDK31 is required by the distribution tools. Typed child-exit payloads
change PendingSignalInfo, pending queue entries and architecture signal-frame
Info records relative to SDK30. All consumers retain exact architecture, mode,
compiler and manifest/artifact hash checks. Older and future ABI versions are
rejected. SDK31 lifecycle additions preserve the existing public layout values;
the exact matching exported libraries and headers remain required.

The Kernel owns trusted child status, the common 128-byte target siginfo encoder,
exit notification policy, parent-thread lineage and checked deferred autoreaping.
ObfuscationOS compiles its user programs, fixtures and extensions against the
exported SDK. Nine frame policies instantiate ten Kernel profiles. Ordinary
distribution userland remains x86_64, aarch64, rv64 and loongarch64; qualification
fixtures for the other six profiles preserve the full Kernel/ABI test matrix.

The private Debug exit-only path now generates automatic SIGCHLD. It distinguishes
default disposition, explicit ignore and SA_NOCLDWAIT, retains the first coalesced
payload, selects the actual creator or replacement parent thread, and keeps the
saved raw leader notification cause separate from the final group wait cause.
CPU-time fields stay zero. Native parents preserve native waiting for Linux
children. This serialized experiment has no general init/subreaper adoption,
stopped/continued event handling or SMP lifetime contract. In that earlier baseline, production caught
signal flags remained disabled. The successor enables the bounded runtime in
ordinary modes independently of private diagnostics; see the capability contract.

Fresh SDK31 qualification supplies twenty Debug/Release exports and ten private
standalone boots, one ordinary signals-off Debug export/boot, five ordinary
distribution links and ten distribution boots. Policy and lineage probes each
run twice on all ten profiles: 360 policy and 140 lineage cases. Inherited frame
delivery and synchronous waits pass on all ten profiles; x86 process/directed
signals complete 22 inherited qualifiers and 44 commands in total. Hosted fault
tests, native instructions, original execution and transcript replay remain
separate evidence layers.

The lifecycle-aware collectors validate typed EXIT/REAP records before forming
the inherited wait-ledger view. Positive owned waits require a unique preceding
owned completion. Original interrupted-wait/signal adjacency remains mandatory;
filtering a typed completion cannot create artificial adjacency. The retained
init/shell owner cannot retire and reappear across image records. General orphan
reconciliation is not claimed, and immediate-ready wait calls need not produce
a blocking wait pair. See [policy](NATIVE_CHILD_EXIT_GUEST.md),
[lineage](NATIVE_CHILD_EXIT_LINEAGE_GUEST.md) and
[inherited consumers](NATIVE_CHILD_LIFECYCLE_CONSUMERS.md).

Old SDK30 records retain their original identities, including the earlier
journalled directory campaigns and unresolved MIPS FLUSH timeouts. No later
SDK31 signal result relabels that storage evidence. Failed collector and
pre-execution attempts remain retained. This bounded integration does not
complete M3, POSIX or M0-M12; physical and manual desktop acceptance are deferred.
