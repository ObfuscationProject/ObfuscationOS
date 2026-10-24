# Native positive-target process signals

`tests/musl/native_process_signals.c` exercises the SDK29 private Linux-personality
process-shared signal implementation on all ten kernel profiles: x86_64, i386,
aarch64, arm32, rv32, rv64, loongarch64, mips, mips64 and ppc. This test matrix does
not change the four public ObfuscationOS distribution architectures.

`tools/qualify_native_process_signals.py` consumes one explicit architecture/mode
Kernel SDK, pinned musl sysroot and source inventory. It does not compile kernel
source. It retains its source, tool inputs, disk, serial stream and failure logs.
The commands are `/bin/native-process-signal-ARCH`, using `x86-64` and `la64` for
the corresponding executable suffixes.

There are 33 cases for each raw/libc and restart-off/on combination. ARM raw
traps additionally cover Thumb; PPC raw traps cover both incoming SO values.
Consequently one command executes 132 cases normally and 198 on ARM/PPC. Every
case runs in a forked child; the outer parent checks exit status or SIGKILL.
Internal coordination has five-second deadlines, and the external command
harness has a bounded timeout. The parent's blocking `waitpid` has no separate
per-case watchdog.

## Covered behavior

- Positive process IDs and nonleader thread IDs address the shared queue;
  signal zero, invalid numbers, permissions, exited threads and reaped IDs are
  checked. Case 0 observes child pipe EOF before sending to the unreaped child.
  EOF alone does not prove publication of Linux's zombie state during exit.
- Same-number and different-number directed work precedes shared work. Shared
  signals select an eligible sibling, and two eligible siblings receive exactly
  one standard occurrence without requiring a preferred recipient.
- `sigpending` reports the caller's masked directed/shared union. New threads
  see existing shared work. Fork inherits masks/actions with empty queues; exec
  preserves the surviving thread's directed and shared queues, resets caught
  actions and retains ignored actions. Nonleader exec checks fresh TLS and the
  replacement leader's identity.
- Handler `siginfo` records the sending process PID and real UID. Standard
  coalescing retains the first sender even after its thread/process exits.
  Named-task masks control generation while ignored; changing disposition to
  ignore drains matching shared and directed pending work.
- Realtime instances, the private 32-payload limit, zero-sender fallback and
  later same-number payload subsumption are exercised separately.
- Shared delivery interrupts a sibling's owned pipe read, validating its exact
  saved context and a new read request after explicit EINTR retry or SA_RESTART.
  Positive-target SIGKILL cancels two simultaneous pipe reads or a console read
  plus a pipe read, and the parent observes whole-group termination.

## Evidence layers

The C assertions check actual syscall results, sender/recipient identities,
masks, pending sets, byte guards, fresh-image state and parent statuses.
`process_signal_guest_protocol.py` independently validates the full case matrix,
actor streams, command handshakes and handler occurrences. It permits legal
cross-thread interleavings and rejects unclaimed or duplicate guest records.

`process_signal_native_protocol.py` binds the timing cases to the common native
pipe ledger's copied descriptor/buffer, retained open description, pipe object,
request generation, origin, signal publication and terminal. A delay marker
without a live owned wait is insufficient. The complete command collector also
requires two guest commands, native pipelines before and after them, exact image
counts and restoration of frame and entry-stack accounting at shell boundaries.

Static all-ten builds and ELF trap audits, host Linux runs, compiled assertion
controls and synthetic parser controls are distinct from native execution.
The host Linux reference explicitly skips native credential policy (26/27),
private realtime capacity (29/30/31) and native console contract (32): 108 host
cases, with every exclusion recorded. Native runs have no skipped case.

## Limits

Nonpositive targets, process-group broadcast, stop/continue and job control,
caught or other default-action delivery from unqualified console waits, SMP and
production compatibility are outside this increment. Native group-fatal console
service does not imply general console interruption. M11 physical acceptance and
M12 manual desktop acceptance remain deferred separately by the user.
