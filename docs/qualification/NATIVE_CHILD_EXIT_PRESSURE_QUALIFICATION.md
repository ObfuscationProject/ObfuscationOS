# Private SDK31 child-exit pressure qualification

The bounded [pressure workload](NATIVE_CHILD_EXIT_PRESSURE_GUEST.md) and its
SDK-only collector now pass fresh QEMU execution twice on all ten profiles:
x86_64, i386, aarch64, arm32, rv64, rv32, loongarch64, mips, mips64 and ppc.
The accepted Kernel887 remains unchanged. The ordinary distribution profiles
remain x86_64, aarch64, rv64 and loongarch64; these probes do not change that set.

Twenty fresh commands cover sixty natural-exhaustion waves. Each observed wave
created thirteen children before ENOMEM; the collector still accepts dynamic
capacities and does not infer which allocation failed. There are 780 successful
pressure children, 180 failed forks with exact unpublished exit127 rollback,
60 successful recovery children and 20 controllers: 860 published completions
plus 180 internal rollback completions. The two automatic policies physically
reap 520 pressure children. Every pressure child has an actual pipe-read arm
before gate release, a checked one-byte completion and a subsequent owned exit.

Shared-gate wakeups can legitimately rearm an existing read. The typed parser
requires the copied request, descriptor, pipe and buffer identity, advancing
tickets and a single terminal completion. Rearming does not waive the original
pre-release arm. The controller epoch, first queued SIGCHLD payload, explicit
reap batches, shell parent and final page/entry-stack baseline are all joined.
Recovery reads and native pipelines may be immediately ready and produce no
blocking wait pair. No new faults, rejected entries or quarantine are accepted.

The full consumer tool regression passes 66 suites / 598 methods. The pressure
guest, join and execution-observation suites contribute 15 distinct methods.
An independent review of the root collector/qualifier passes 488 complete
transcript controls (22 admissions / 466 rejections), with 244 controls checking
the intended failing gate, plus 60 execution-observation controls. Its author
also authored the guest journal parser and does not claim independent review of
those original guest files. All ten fresh original receipts replay identically.

The portable independent controls are retained at
`tests/tools/audit_native_child_exit_pressure.py`. Run with explicit source,
source inventory and its SHA256, original result, serial and new output paths.
It replays existing evidence and never launches a guest. The final source adds
only this audit utility and this document to the exact 507-file executed V3.

Evidence under `build/prototypes/native-child-exit-pressure-integration-v1`:

- `pressure-matrix-v1/result.json`: ten fresh qualifiers / twenty commands,
  SHA256 `d94c15204c2fe255c4ed79e82cf41fad7d10fbe217d134f5e8084ffa7d841a79`.
- `tools-v3/result.json`: hosted regressions,
  SHA256 `63d19422bbb96f01eb503ee4be9576675d325b2d526cb98e04c350072a70d1a7`.
- The sibling `native-child-exit-pressure-review-v1/HANDOFF-v1.json` binds
  independent controls/provenance,
  SHA256 `4fd949dad99cf43017a45fd2f5e774a8c3377847fc50fe42b1ba9222924aa690`.

The earlier x86 V2 qualifier actually executed two successful commands but
incorrectly rejected legitimate pipe rearms. Its original failed receipt stays
unchanged: executed=true, native_execution_accepted=false. V3 replays those
bytes successfully; that replay is not another execution and is not included
in the twenty fresh commands above. The initial overstrict hosted rollback
test and reviewer test-premise corrections also remain preserved.

This establishes natural fork-pressure cleanup and recovery for the serialized
private Debug runtime. It does not establish global process-table, VM or stack
exhaustion separately, injected terminal failures, production signal enablement,
SMP, physical hardware or full Linux/POSIX conformance. CPU-time siginfo fields
remain zero. The existing SDK30 journal campaigns and unresolved historical
MIPS FLUSH timeouts are unchanged. M0-M12 remains incomplete; physical and
manual desktop acceptance remain deferred.
