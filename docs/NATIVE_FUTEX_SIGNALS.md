# Native FUTEX_WAIT signal fixture

`tools/qualify_native_futex_signal.py` consumes an explicitly pinned SDK29 Debug
export, musl build, compiler, QEMU executable and complete OS source inventory.
It builds the OS consumer and one static guest through xmake, retains all inputs,
packages ext4, runs a native pipeline, two complete guest commands and another
native pipeline, and retains serial, disk, offline fsck and input rechecks.
It does not open or compile kernel source. Failed runs retain their evidence.

The fixture preserves all ten profiles. x86_64 uses futex202; i386/ARM32 use
240/422; AArch64/RV64/LoongArch64 use98; RV32 uses422; MIPS o32 uses4238/4422;
MIPS n64 uses5194; PPC32 uses221/422. The two-number lanes separately exercise
time32 and time64. ARM has ARM/Thumb raw instructions with an ordinary ARM C
handler; PPC has initially clear/set CR0.SO. Each domain/ABI/form has a distinct
child, two rounds and19 distinct nonleader target threads per round.

Both existing WAIT domains0/128 and WAKE1/129 are exercised. Domain0 in this
private runtime is PID+VA keyed, not a true process-shared backing key. This
fixture makes no cross-process or cross-domain key-isolation claim.

For each form times ABI, one command has76 cases,68 initial arms,20 fresh restart
arms,12 EINTR retirements,36 restart publications,32 ready retirements,8 timeout
retirements,8 immediate results,60 outer handlers,4 nested handlers,64 main sends
and188 wake assertions. ARM/PPC each have304 cases per command. The guest checks
word/timeout guards, exact raw results with unchanged errno111, joins and cleanup
wake0 on both addresses. A parent validates all child exit statuses.

The cases cover untimed caught EINTR/restart; timed EINTR with and without
SA_RESTART; changed word/expected EAGAIN; saved PC/result77, getpid number and
alternate address edits; repeated restart; copied relative timeout mutation;
ordinary wake; wake/timeout winning before signal; masked delayed delivery;
ignored signal; nested handler; zero timeout and initial mismatch. No hidden
replay is permitted after a user context edit.

Guest timeout returns use the target Linux errno ABI: ETIMEDOUT is145 for MIPS
o32/n64 and110 for the other eight profiles. This applies to copied-timeout,
timeout-before-signal and zero-timeout cases10/12/17, including both time32 and
time64 lanes where present. Native RETIRE diagnostics use the kernel's canonical
internal timeout result -110 on every profile. The collector validates these two
representations separately; accepting an internal -110 as a MIPS guest return,
or a guest -145 as a kernel diagnostic, would hide an ABI defect.

`native_futex_events.py` validates every native ARM/RETIRE/SIGNAL diagnostic,
including incidental libc waits, using exact owner/wait/origin bindings and live
counts. Every interrupted retirement immediately precedes its signal publication.
Timed waits cannot publish restart; untimed restart uses a fresh origin and wait.
The case parser requires the original arm after ATTEMPT and before SEND/WAKE/
MUTATE_TIMEOUT; guest delays and entered flags are not accepted as blocked proof.
The parser checks original syscall and all four inputs, absolute deadline shape,
time ABI, instruction alignment, legal ARM user state, MIPS result/a3 encoding and
PPC saved restart diagnostics. Non-target incidental waits cannot claim a signal
publication. Native pipe diagnostics also remain paired and accounted.

The OS successor pipe collector also validates these incidental futex events;
it forbids futex signal publication in pipe commands. Both collectors reject
duplicate/stale paired resource snapshots. Existing frozen collector evidence is
unchanged; a replay under the successor is a separately attributable result.

Python fixtures are synthetic parser tests, not native execution. Linux reference
and all-ten static build/ELF checks are prerequisites, not native acceptance.
The collector requires two real complete commands, one Linux image per command,
zero newly captured faults, and final frame/entry resources at the shell baseline.
It does not claim PI/requeue/bitsets, true shared backing, no-handler
restart_syscall, o32 inaccessible unused-stack execution, MIPS branch-delay
restart, ARM IT-block execution, production signals, SMP, physical hardware,
manual desktop acceptance, or completion of M0-M12.
