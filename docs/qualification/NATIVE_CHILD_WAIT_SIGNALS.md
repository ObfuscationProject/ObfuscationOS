# Private child wait qualification

`tests/musl/native_child_wait.c` executes raw wait4 (RV32 waitid) and musl
waitpid against explicitly selected SDK29 private Debug artifacts. Every
architecture retains its raw register/trap checks. ARM and PPC have two raw
instruction forms. Each command runs 22 cases per group, except the two RV32
libc output-protection cases: musl copies its private siginfo to the caller's
status in userspace. Raw RV32 still exercises the kernel output-fault path.

Coverage includes positive/any-child selectors, EINTR and SA_RESTART, copied
output addresses, protected output, nonblocking/error/ready cases, pending and
ignored signals, action replacement, nested handlers and waits, edited saved
contexts, competing waiters, thread/group exit, fatal cleanup, failed exec and
complete image replacement. Parent checks validate scenario status and drain
the descendant pipe. Each qualifier runs two commands around native pipelines,
checks object/frame/entry-stack retirement, performs offline fsck and rehashes
all retained inputs. Linux reference execution is separate evidence.

The generic `native_child_events` ledger validates ownership and balanced
request/ticket retirement. The dedicated collector additionally validates
case topology, directed sends, exact saved ABI fields, output identity and
temporal causes. An explicit retry after EINTR selects the known child even
when the interrupted request selected any child. A restarted request preserves
the any-child selector. RV32 musl preserves -1 in waitid's ignored P_ALL id
field; the raw lane supplies zero. Both remain exact saved-register checks.

The kernel diagnostic's `complete result` is the readiness probe before reaping
and copying. Early output admission can report EFAULT before child release.
Such a diagnostic must follow the protection action and precede the error
return. Successful child completions must follow the selected child's release.
Fresh outer waits follow handler return and any explicit retry; nested arms,
interruptions, reentry, completion and userspace reap are ordered separately.

Entry-stack minimums follow the actual process/thread topology: one executable
plus 71 leases per group (22 leaders, 25 children, 24 workers). Two RV32 skipped
libc scenarios remove six leases. The resulting minimums are 279 for RV32,
427 for ARM/PPC, and 285 for other profiles. A persistent init-to-shell wait
accounts for exactly one object page, with its exact request retained across
commands. Previous no-child-diagnostic consumers still require their original
zero-page baseline.

This is an exited-child subset. WNOWAIT, process groups, rusage, stop/continue,
automatic SIGCHLD, SA_NOCLDWAIT, SMP, production signal enablement, physical
hardware and full POSIX/M0-M12 completion remain outside this qualification.
Replay of retained serial evidence is not a new native execution.
