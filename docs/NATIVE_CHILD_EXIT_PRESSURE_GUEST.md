# Private native child-exit pressure guest

`tests/musl/native_child_exit_pressure.c` is an OS-owned static musl workload.
It is designed for the existing private, serialized Debug SDK31 signal fixture
on all ten kernel profiles. Its journal parser validates user observations; it
does not admit kernel diagnostics or claim that a guest ran.

## Workload

One single-threaded Linux-personality process blocks SIGCHLD and performs three
pressure waves: default disposition, explicit SIG_IGN, and default disposition
with SA_NOCLDWAIT. Each wave forks until an actual ENOMEM/EAGAIN result, then
repeats the failing call twice while every successful child remains alive.
Every fork has a sequenced BEGIN and success/failure record. Reaching the safety
cap of 128 attempted calls is a failure, never a substitute for exhaustion.

Each child closes its inherited writer and calls blocking read on a pipe gate.
The parent retains the writer and supplies no gate byte before exhaustion.
The parent observes WNOHANG zero for every successful PID, WNOHANG zero for
wait-any and no pending SIGCHLD or zero-time signal-wait result before release.
It writes exactly one byte per successful child into the empty gate. The write
is at most 128 bytes, below the pinned scheduler pipe capacity of 4096.
Children consume one byte, close their reader and exit 37.

The ordinary wave reaps each successful PID with its exact exit status. The
automatic-reap waves require ECHILD for each PID after completion; a live child
returning zero remains live and is polled with a ten-second monotonic deadline.
After all children are collected or detached, the default/NOCLDWAIT waves read
one full 128-byte child siginfo. The sender may be any successful child and
must have the correct UID and cause. Explicit ignore requires no notification.
Every wave drains SIGCHLD completely before continuing.

An ordinary default-disposition gated fork/wait/notification cycle follows each
pressure wave, using exit status 39. This demonstrates subsequent successful
creation and collection after resource pressure. No fixed successful-child
count is expected; at least two are required for a meaningful coalescing check.

The pinned scheduler has a per-parent child table of 16 and a global process
table of 64. Thus this workload may reach the per-parent limit first. It claims
naturally executed fork exhaustion, not global process-table, VM-page or
privileged-stack exhaustion specifically. It does not inject later publication,
VM destruction or terminal scheduler failures.

## Required collector contract

`tools/native_child_exit_pressure_guest.py` returns original transcript
positions for each fork window, successful PID, pre-release observation,
release, wait result, signal payload and recovery cycle. The root-owned
collector must validate the complete native diagnostic stream independently:

- For every successful pressure child, require a uniquely owned pipe-read ARM
  before RELEASE, its successful one-byte completion after release, and its
  typed exit 37 after that completion and before the matching WAIT/ECHILD
  observation. Source gates, user WNOHANG observations and delays alone do not
  prove a kernel blocked wait. If scheduling does not produce all required
  ARM records, that execution is not qualified by this stronger contract.
- No successful child's completion may occur before release. No failed fork
  may publish a user-visible child, notify SIGCHLD or add a child returned to
  userland. The typed rollback diagnostic distinction below must be resolved
  explicitly; the journal parser does not silently remove such diagnostics.
- Ordinary completion records retain the main PID/TID as their parent owner.
  Default and NOCLDWAIT waves must have exactly one queued notification and
  `N-1` coalesced notifications before the user consumes it. Full siginfo must
  match the actual queued completion, without choosing a PID order in advance.
  IGN has no queued/coalesced notification. Automatic detach and physical safe
  reclaim are separate events, both requiring complete accounting.
- Parent WNOHANG polling legitimately produces no blocking CHILD_WAIT records.
  Join the returned PID/status or ECHILD observation to its typed completion.
  Validate any emitted blocking wait independently; do not manufacture pairs.
- Join each ordinary recovery PID to its release, exit 39, successful wait and
  full notification. Join the main process exit to its native shell wait after
  the final aggregate marker. Reject extra or reused published PIDs.
- The dynamic minimum entry lease count is successful pressure children plus
  three recovery children plus the main process. Command-boundary pages and
  privileged stacks must return to the live shell baseline with no new faults,
  quarantine or rejected entries. Preserve the inherited init/shell wait owner.

## Unpublished rollback diagnostic

The pinned Kernel885V2 may create an internal child PCB before a native fork
allocation fails. Its existing cleanup calls `finish(child,127)` and an
internal wait before returning ENOMEM. That path emits a typed CHILD_EXIT with
`published=0`, zero parent TID/epoch, normal cause/status 127 and no notification
or automatic reap. The failed call never returns that internal PID to userland.
This differs from a user-visible child exit.

The design sentence requiring no completion diagnostic therefore needs an
explicit collector interpretation. EAGAIN before PCB creation needs none.
If an ENOMEM run exercises cleanup after creation, a collector can separately
bind at most one exact unpublished rollback diagnostic inside that failed
FORK_BEGIN/FORK_FAIL window and verify its complete resource rollback. Unknown
or published completions remain forbidden. Accepting this path is a root
integration decision, not something this marker parser grants. There is no
claim that the current compile-only work has executed either failure path.

## Evidence boundaries

The pressure stage initially pins the exact frozen combined OS497V1 and
Kernel885V2 source inventories. Before any final acceptance it must rebind to
the lifecycle promotion. The compile matrix consumes pinned musl/toolchain
artifacts and does not build a kernel or execute the guest. Hosted fixtures
include variable capacities, both first/last retained sender choices, all ten
siginfo layouts and malformed/duplicate/causal mutations. Native collection,
SDK qualification and QEMU execution belong to root integration. No production,
physical hardware, SMP or full Linux/POSIX acceptance follows from this guest.

## Integration decision

The integration successor rebinds the four exact guest files onto the accepted
Kernel887/OS498 lifecycle promotion. The root-owned
`native_child_exit_pressure_join.py` admits the bounded unpublished ENOMEM
rollback described above and rejects EAGAIN-associated, published, unowned,
out-of-window or duplicate rollback exits. Absence of a rollback exit remains
valid when allocation failed before PCB creation; a marker-only transcript
cannot establish which internal allocation step failed.

The collector requires every pressure child to have an actual pipe-read arm
before release and a one-byte completion before its exit. Recovery reads may
already be ready; any emitted request still belongs to that recovery child.
An armed read can rearm when a wakeup finds the shared gate still empty. Such
records retain the original request, buffer, descriptor and pipe identity,
advance wait tickets and precede its single terminal completion. They do not
count as another user read or excuse a missing original pre-release arm.
All successful child completions retain the controller's single parent epoch.
The first actual queued completion must match the full guest siginfo payload.
Explicit reaper batches cover exactly the two automatic-policy waves. The
controller's own completion stays joined to the live native shell wait.

`test_native_child_exit_pressure_join.py` supplies hosted typed-stream and
typed-view controls. These tests are distinct from the guest journal tests and
from native qualification. The SDK-only qualifier retains the exact source,
artifact hashes, disks, command boundaries and original failed attempts. Its
successful replay is not another guest execution.
