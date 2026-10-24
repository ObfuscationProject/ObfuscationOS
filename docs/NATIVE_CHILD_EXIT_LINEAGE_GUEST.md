# Private child-exit lineage probe

`tests/musl/native_child_exit_lineage.c` extends the policy probe with seven
isolated user processes. Its `child-exit-lineage` command is
`/bin/native-child-lineage-<arch>` using `x86-64`/`la64` filename aliases. There
is one image admission and a minimum22 entry-stack leases: main, seven scenario
processes, seven children and seven pthreads. This count requires confirmation
against actual target accounting; compilation does not establish execution.

Cases0--1 distinguish the nonleader creator from a blocked leader. While the
unblocked creator is alive, default SIGCHLD is suppressed. After its raw exit,
the blocked surviving leader becomes the named parent and notification is
required. `set_tid_address` registers a real writable atomic word. Its observed
clear establishes raw thread retirement in this serialized private service;
there is no claim about SMP memory ordering. The fixture does not pretend that
raw exit completed libc pthread_join bookkeeping. Its isolated process uses
exit_group to reclaim remaining mappings and never reuses those stacks.

Cases2--4 fork a child group whose leader raw-exits17. A surviving worker observes
the clear-TID word and acknowledges over a pipe. The parent requires WNOHANG0 and
no pending SIGCHLD before releasing the final worker. Final raw exit23,
exit_group23 and SIGTERM15 must preserve notification CLD_EXITED17 while wait
reports the final cause23/23/SIGTERM15. This is the selected Linux6.13.4 reference
contract; a documented later Linux kernel can differ. Native procfs/WNOWAIT are
not prerequisites because the fixture uses clear-TID plus owned pipe gates.

Case5 receives default SIGCHLD in active sigtimedwait: the original blocked mask
is `real_blocked` while its active wanted bit is cleared. Case6 observes default
SIGCHLD suppression during ppoll's temporary unblocked mask; ppoll's saved
blocked return mask must not become `real_blocked`. A helper reaps the completed
child and writes a readiness pipe, so this poll completes on actual readiness.

`tools/native_child_exit_lineage_guest.py` validates exact, complete user
journals and all128 payload bytes. `validate_joins(span, guest, exits,
signal_waits, poll_waits)` accepts only rows already validated by the integration
collector's complete typed kernel parsers. It binds creator/replacement TIDs,
notification and final wait causes, queued policy, and per-case completion
boundaries. Both final cases require actual ARM < CHILD_EXIT < COMPLETE/RETIRE
within their user call boundaries. A helper's scheduling delay is not accepted
as proof of an armed syscall. Missing or reversed native records fail the join.

The existing generic signal-wait ledger must admit a typed CLD_EXITED/CLD_KILLED
completion for SIGCHLD before it can qualify the active case. The old sender-only
whitelist `(SI_USER, SI_TKILL, SI_KERNEL)` is insufficient. Root integration owns
that shared parser extension; this probe does not relax it or filter child
records into a sender form. Signal-wait copy failures retain their existing
consume-before-copyout semantics.

The kernel primitive audit found no missing prerequisite for these seven cases.
Unavailable native procfs/WNOWAIT are replaced by direct retirement observations
or exact kernel wait joins. Multiple surviving replacement candidates, delivery
to an eligible caught-handler sibling, nonleader exec, failure/pressure injection,
administrative termination, SMP, hardware and manual desktop acceptance remain
outside this probe. Privileged entry-stack slot/generation reuse cannot be
inferred from user PASS markers or aggregate counters.

All ten target profiles remain supported. Musl's RV32 waitpid uses waitid;
PPC retains the big-endian scalar soft-float frontend. The workload is compiled
and linked against explicit pinned musl artifacts and consumes exported SDKs
only when root integration builds its distribution image. Hosted marker and
join mutation tests are separate from native guest execution.
# Surrounding native pipeline protocol

The lineage qualifier permits immediate-ready native waits, which produce no
blocking WAIT arm/complete records. The first x86 lineage execution observed
this for the right child after the left child completed. Both native pipeline
children still require unique EXIT records with exact persistent-shell parent,
native personality, UID0, successful cause and no automatic reap. Every emitted
wait must retain that shell's PID/TID and succeed after its matching completion.
Unknown children, missing EXITs and canceled/error waits remain rejected.

This differs explicitly from the policy campaign's two-pair qualification
protocol. `all_native_waits_traced` is false for lineage: immediate collection is
established by the pinned shell path reaching its next prompt and complete
resource accounting, not a fabricated blocking wait record.

