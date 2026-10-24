# Child lifecycle diagnostics in inherited signal collectors

The signal-frame, synchronous-wait, process-shared-signal, directed-signal,
child-wait, child-wait-smoke, pipe-write, pipe-vector, pipe-SIGPIPE, pipe-signal,
pipe-blocking, futex-signal, poll-signal, temporary-poll-mask and poll-mask-exec
collectors consume SDK31 child EXIT/REAP diagnostics through
`native_child_lifecycle_evidence.py`. Their public command boundaries, return
contracts and existing guest, frame, entry-stack and inherited-init-wait checks
remain unchanged.

Each original command span first passes the architecture-specific typed
completion/reaper parser. Only those validated exact lines leave the separate
child-wait ledger view. The ledger still validates request tickets, selectors,
copied outputs, owner counts, terminal outcomes and the retained init waiter.
Every recorded successful positive child wait must join a unique preceding
non-autoreaped completion owned by the waiting process. Command grammar admits
the exact validated lifecycle lines; malformed and unknown child diagnostics
cannot be dropped by a prefix whitelist. Boot uses the same typed composition
before deriving its inherited wait baseline.

The adapter forwards the existing caught-signal admission switch, architecture
signal numbers and saved-PC bounds without widening them. Interrupted WAIT and
its SIGNAL publication must remain consecutive nonempty lines in the original
span. A validated EXIT or REAP between them is rejected before filtering;
otherwise removing it would hide a violation of the inherited wait protocol.

The public child WAIT/SIGNAL pattern tuples and guest-specific pattern tuples
retain their previous members. A separate lifecycle tuple extends only the
complete command grammar. Guest-specific child-wait validation excludes typed
lifecycle rows from its wait maps after adapter validation, preserving the
existing owner, request, handler and restart joins. Synthetic fixture producers
emit a typed owned EXIT before each positive successful WAIT; they do not add
invented REAP batches to satisfy unrelated pattern-enumeration tests.

This migration validates successful checked reaper results, including typed
count and failure fields. It does not infer a complete orphan lifetime ledger
or equate REAP counts with the set of observed autoreap exits. Legacy guests can
leave waitable children for later reparenting, and immediate waits have no
blocking-wait diagnostic. Full guest-specific process coverage and physical
reap reconciliation require a separately qualified launch/lifetime protocol.

`tests/tools/test_native_child_lifecycle_consumers.py` provides synthetic
all-ten typed-parser and causal-wait controls, plus complete wrapper controls
for the first four migrated consumers.
`tests/tools/test_native_child_lifecycle_remaining.py` covers the eleven
additional wrappers, keeps the exploratory smoke guest limited to x86_64,
and checks original interrupted-publication adjacency on all ten profiles.
These controls are not native execution.
Fresh SDK31 native runs are collected by the integration stage. Production
signal enablement, SMP and physical/manual desktop acceptance are unchanged.
