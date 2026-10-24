# Private synchronous signal wait guest

`tests/musl/native_signal_wait.c` exercises the exported Debug Kernel SDK's
Linux `rt_sigtimedwait`, explicit time64 variants and `rt_sigsuspend`, together
with the pinned musl 1.2.5 wrappers. The OS qualifier builds an SDK-only consumer;
it does not compile kernel sources. These private probes preserve all ten
kernel profiles and do not change the four-profile distribution matrix.

The guest has 32 timed-receive and 17 suspend scenarios. Raw admission tests
exercise mandatory set size, inaccessible input, timeout validation precedence,
zero timeout, KILL/STOP filtering and destructive siginfo copy failure. Behavior
cases cover directed-before-shared selection, complete 128-byte ABI siginfo,
realtime sender FIFO, process-shared queue fallback and subsumption, copied
inputs, finite and saturated deadlines, ignored generation under real-blocked
masks, musl EINTR retry, temporary/live/saved handler masks, and fork, exec,
thread-exit and group-exit cleanup.

| Profiles | Cases per command | Linux images per command | Minimum entry leases |
| --- | ---: | ---: | ---: |
| x86_64, aarch64, rv32, rv64, loongarch64, mips64 | 184 | 13 | 337 |
| i386, mips | 248 | 15 | 449 |
| arm32, ppc | 410 | 23 | 735 |

Each applicable case runs with SA_RESTART disabled and enabled. ARM includes
ARM and Thumb traps; PPC includes both incoming SO values. i386, ARM, MIPS o32
and PPC cover legacy and explicit time64 calls. RV32 uses syscall 421 only.
Musl on 32-bit profiles also exercises time64 selection above INT32_MAX seconds.
The raw time64 padding scenario retains nonzero high nanosecond padding on
32-bit profiles; native 64-bit invalid nanoseconds are a distinct admission test.

Every scenario forks a child and checks its exact exit status. Worker commands
carry per-actor ordinals and causal acknowledgements. A fixed delay only emits
an AWAIT claim: native acceptance requires a preceding, still-owned kernel
registration for the exact call, TID, copied mask and deadline. The Linux
reference build instead samples `/proc/self/task/TID/syscall`, and its evidence
is never admitted as native kernel execution.

T18 separately verifies ignored WINCH generation naming an unblocked waiter
(the send drops) and a blocked leader (shared pending work interrupts raw
sigtimedwait without a handler). Both default-ignore and explicit-ignore actions
are covered. Musl retries the latter raw EINTR and must establish a second
owned request before a wanted signal releases it. T16 permits a raw loser to
retry an observed EINTR when another waiter consumes shared work; each attempt
has its own checked return and ordinal. There is no assumed preferred waiter.

T22/T23 fill the process-shared queue using `kill`. Its realtime fallback is a
shared-queue policy and is not a directed `tgkill` queue guarantee. The fallback
has SI_USER and zero PID/UID, and a later allocated same-number payload subsumes
it. Linux reference runs explicitly exclude these two private-capacity cases.
S09 proves ignored shared pending work has drained while suspend still owns the
same logical request, before a later caught release signal. S04's auxiliary
zero-timeout receive drains the still-blocked directed signal under the enclosing
suspend scenario key while publishing its actual timed-wait syscall number.

`signal_wait_guest_protocol.py` checks the exact architecture matrix, actor
streams, send plans, pending observations, command acknowledgements, returned
values and errno, copied siginfo checksum, handler context, image replacement
state and cleanup totals. C independently compares all 128 siginfo bytes and
redzones; the checksum is an additional transcript check.

`native_signal_wait_events.py` checks ARM, COMPLETE, REARM, COMMIT and RETIRE
ownership. A staged suspend EINTR is not a terminal user return. Only a later
COMMIT records handler-frame publication; the guest HANDLE separately proves
handler execution. Rearms preserve copied inputs and deadlines. Exec retirement
is a contiguous batch with pre-batch live counts. Epochs are entry-stack-slot
local and are not ordered by PID/TID across operations. Scheduler wait tickets
retain their per-TCB high-water mark until an explicit retirement boundary.

`signal_wait_native_protocol.py` binds those native records to each invocation,
including libc retries, pre-send blocking, ignored draining and retirement
before image replacement. `native_signal_wait_evidence.py` additionally requires
two complete dedicated commands between native `hello | cat` checks, exact
image counts, all inherited pipe/futex/poll/child ledgers, no outstanding wait at
command boundaries, and restored frame/entry-stack accounting.

The standalone kernel runtime/model tests cover forced cancellation, final-match
versus deadline ordering, readiness deferral and exhausted generation authority.
Guest sleeps do not establish deterministic scheduler race coverage. Static ELF
checks, synthetic parser schedules, host Linux references and actual native
QEMU executions remain separate evidence classes. These probes do not imply
production enablement, SMP, physical-machine acceptance or manual desktop
acceptance.
