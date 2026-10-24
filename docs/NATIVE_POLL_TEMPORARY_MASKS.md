# Private ppoll/pselect temporary-mask execution probe

The SDK-only runner `tools/qualify_native_poll_temporary_mask.py` adds a static
musl guest to a fresh retained distribution consumer. The runner consumes an
explicit architecture/mode/manifest-pinned SDK29 and never compiles Kernel source.
This remains a private serialized single-CPU signal fixture, not production or
hardware acceptance. Full exec image replacement is qualified separately.

All ten profiles execute raw ppoll and pselect6, plus separate time64 forms where
present. ARM32 covers ARM and Thumb; PPC32 covers initial CR0.SO clear/set. Each
lane/form executes both SA_RESTART settings. Every caught wait must return EINTR
without rewinding its exact raw continuation; poll output-copy EFAULT instead
restores the original mask immediately. The trap/context headers are reused
unchanged from the independently authored sealed poll guest.

Each lane/form/restart group has 25 cases: original USR1 blocked/unblocked;
post-admission mask mutation; protected output; O_NONBLOCK pipe readiness;
blocked timeout; zero timeout; immediate readiness; invalid fd; unreadable mask;
wrong mask size; unreadable timeout preceding wrong size; unreadable fd storage;
ignored signal; temporary-blocked pending signal; signal queued before mask
admission; nested masked wait with a different active mask; edited sigreturn mask;
post-admission timeout mutation; revoked mask input mapping; SA_NODEFER plus
sa_mask; fatal disposition; group exit during a wait; group exit inside a handler;
and pthread exit inside a handler. The parent validates real child wait status.
The temporary mask includes KILL/STOP to test sanitation, signal62 versus original
signal63, and MIPS signal99 versus original signal100. All kernel mask words are
compared, not merely displayed signature bits. Case3 leaves original USR1
unblocked so immediate EFAULT restoration still permits the inspected handler.

The collector requires complete argument/case ordering and exact native poll
object/ticket ownership before any delayed mutation, signal or readiness action.
It validates original saved masks separately from handler-active masks, nested
restoration, edited sigreturn, architecture error flags, original deadlines,
all exit completions and final frame/entry-stack resource baselines. The optional
signal-number parameter in the inherited generic poll ledger defaults to its
original USR1 contract; only this collector admits the USR2 nested interrupt.
Synthetic collector fixtures are not execution evidence.

The Linux x86 reference uses `/proc/self/task/TID/syscall` with all six raw
arguments to observe outer blocking waits, plus syscall-number observation for
nested waits. Prequeued admission deliberately has no observed sleeping window.
Native execution uses kernel arm records for admission evidence. Linux reference,
static ELF audits, native SDK execution, and physical/manual checks remain
separate evidence classes.
