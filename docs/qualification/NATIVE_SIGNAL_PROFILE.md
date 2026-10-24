# Ordinary bounded signal SDK capability

The distribution requires SDK31 with `native_signal_profile` equal to
`bounded-bootcpu-v1`, the canonical `OK_NATIVE_SIGNAL_RUNTIME` definition, and
the existing exact architecture/mode/compiler/artifact checks. A layout ABI
number alone does not establish a running signal service: earlier SDK31 exports
disabled it outside private Debug experiments. Those exports are rejected by
this consumer. Their frozen qualification tools and receipts remain unchanged.

The Kernel owns the signal runtime and administrative process-completion
transaction. OS programs and extensions consume only exported artifacts. The
capability covers the existing serialized boot-CPU implementation, including
caught signals, synchronous waits, supported wait interruption and child-exit
policy. It does not describe SMP, full POSIX/Linux signals or a finished
workstation. General init/subreaper adoption, stop/continue events, process-group
sends, CPU-time siginfo accounting and full hardware-fault handlers remain open.

Runtime enablement is independent of the private diagnostic fixture. Ordinary
Debug and Release exports both carry the capability. Private traces additionally
require Debug test points. Release exports may not carry private/test-point
definitions in the canonical defines, C++ flags or assembly flags. MIPS64 must
also enable its integer-only assembly platform/FPU admission before entering
compiled hard-float C++. All ten Kernel profiles remain, while ordinary distro
userland stays x86_64, aarch64, rv64 and loongarch64.

The consumer rejects absent, unknown, disabled or contradictory capabilities;
duplicate/value-qualified owned macros; C++ flag definitions bypassing the
canonical defines; assembly/define contradictions; and direct, split or
preprocessor-forwarded undefines of runtime/diagnostic controls. Valid metadata
is still only artifact admission. Native execution is established separately
by a booted image and its pinned guest/serial evidence.

Ordinary signal qualification consumes pinned static musl programs. An
explicitly selected musl build mode may differ from the kernel/OS build mode;
the qualifier must report both and retain the compiler ABI and source/library
pins. Such a row tests the selected ordinary kernel, not a newly rebuilt libc
configuration. Ordinary user observations, general resource diagnostics and
private detailed lifecycle/reaper traces are distinct evidence levels.

Automated integration passed all ten target profiles: thirty Kernel exports,
twenty Debug standalone boots, forty ordinary Debug/Release OS qualifiers with
eighty native commands, and twenty private Debug qualifiers with forty commands.
The ordinary commands establish user observations; private diagnostics establish
the deeper blocked-wait/completion/reaping joins. All ten measured public layout
profiles agree, and the mandatory semantic capability remains explicit.

The final tool regression consists of 66 unchanged hosted suites with 608
methods plus the updated nine-method ordinary collector suite: 67 suites and
617 distinct methods. The retained independent observer audit runs separately.
M0-M12, physical hardware and manual desktop acceptance remain incomplete.
