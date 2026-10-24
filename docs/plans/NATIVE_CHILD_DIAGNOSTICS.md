# Owned child waits in SDK consumer evidence

Kernel827 emits owned child-wait records during ordinary native shell execution,
not only during a dedicated wait4/waitid test. The init process waits for the
interactive shell across commands. That exact live request retains one object
page. Command completion must restore the same owner, selector, copied output,
request and ticket; a zero-object assertion would incorrectly reject this state.

The generic child ledger validates admission, rearming, retirement, live counts
and immediate caught-signal publication. The pipe, futex, poll, temporary-mask
and full-exec signal collectors explicitly consume these validated records.
Older transcripts without child records retain the zero-object requirement.
All inherited guest assertions, resource accounting and collector tests remain.

Only two observed complete user banners may be split from a following complete
WAIT diagnostic. The parser recalculates command offsets on this logical view;
the retained serial bytes and accounting are unchanged. Unknown prefixes and
malformed or incomplete diagnostics are rejected. x86 syscall addresses may be
odd; guest-specific collectors must validate the actual instruction/resume PC.

The WAIT complete result describes the ready probe before reaping and copying.
It is not proof of the final syscall result: waitid publishes zero on success,
and a later checked copy can fail. Guest assertions must check ABI results,
status/siginfo and reap behavior. Diagnostic parsing alone proves no execution.

The exploratory x86 smoke guest covers positive/any-child selectors with and
without SA_RESTART. It checks saved RIP, result and arguments, fresh waits,
exit status, reaping and ECHILD. It is separate from the full ten-profile guest
qualification. Production signals, SMP, physical hardware, full Linux/POSIX
wait semantics and milestone completion are not implied by these tests.
