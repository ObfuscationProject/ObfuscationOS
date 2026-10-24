# Private child-exit userland probe

`tests/musl/native_child_exit.c` is an OS-owned musl probe for the private kernel
child-exit policy experiment. Compilation and hosted parser tests do not qualify
native execution. Root integration must provide an exact exported Kernel SDK,
validate lifecycle diagnostics and resources, and execute the resulting image.

The `child-exit-policy` probe runs eighteen isolated cases in order. Cases 0--11
cover default/ignore/caught dispositions, blocked/unblocked SIGCHLD and both
SA_NOCLDWAIT settings. Remaining cases observe CLD_KILLED, first-payload standard
coalescing after both children are reaped, a prior user-generated SIGCHLD,
non-retroactive ignore/NOCLDWAIT changes, fork inheritance and failed/successful
exec inheritance. SA_NOCLDSTOP retention is checked without claiming stop or
continue support. Siginfo checks cover all 128 target bytes, including zero
CPU-time fields; these are not CPU-accounting measurements.

Children wait behind explicit pipe gates. Five-second monotonic bounds cover
polling, handler observation and WNOHANG waits. A wait result, observed handler,
pending child notification or ECHILD supplies completion evidence; elapsed time
does not. The fixture does not call WNOWAIT or procfs. Musl waitpid selects the
supported waitid subset on RV32. PPC uses the existing scalar soft-float frontend;
MIPS target siginfo header order and big-endian profiles remain explicit.

`tools/native_child_exit_guest.py` checks complete ordered user marker journals,
PID ownership, exact per-case operation sequences, wait statuses, pending masks,
handler counts and full target siginfo bytes. It returns `native_execution=False`
because a parser cannot establish execution provenance. Other namespaces remain
the integration collector's responsibility. In particular, this helper does not
allow kernel EXIT/REAP records through a prefix whitelist.

The image name is `/bin/native-child-exit-<arch>` with existing filename aliases
`x86-64` and `la64`. `probe_spec` returns the exact aggregate marker, success
prefix, image command and minimum 40 entry-stack leases per run: one main image,
eighteen scenario processes and twenty-one children/inspector processes. A
successful exec reuses the live leader lease. There are two Linux image admissions per command, including
the initial probe and successful exec. A failed exec contributes no image.

The integration collector requires the continuously live native shell to remain
the main process's parent. Its exact blocking wait must start before the first
scenario and report success only after the main's kernel completion. Guest
workers use WNOHANG; a service-parent0 launch or an unrelated wait ledger cannot
qualify this campaign. Captured faults and rejected kernel entries invalidate
the command even when final frame and stack totals are balanced.

Both surrounding native `hello | cat` commands require two successful native
child completions owned by the persistent shell and two exact blocking wait
pairs. This launch protocol is observed on all ten pinned single-CPU targets;
immediate waits without records require separate qualification. Canceled waits,
unknown waiter TIDs and removal of an entire wait pair are rejected.

Qualification receipts count submitted commands, returned prompts and observed
PASS markers before semantic acceptance. `executed` records an observed guest
PASS marker; `native_execution_accepted` becomes true only after complete causal,
resource, input-identity and offline disk checks. A failed collector can thus
retain actual execution evidence without presenting it as an accepted run.

The guest marker sequence and kernel completion sequence are distinct. Root
integration should join each observed scenario and child PID to its qualified
parent, selected exit cause, publication/coalescing/autoreap policy and final
wait or ECHILD result. Service physical reaping can batch unrelated parent-zero
processes and must be checked with its typed ledger separately.

Existing sigtimedwait copy failure consumes the selected pending signal. This
probe does not change or contradict that behavior. Native lineage/thread-group
edge cases, pressure/rollback and production enablement require further probes.
This private slice does not complete M3, POSIX, M0--M12, SMP, physical M11 or
manual M12 desktop acceptance.
