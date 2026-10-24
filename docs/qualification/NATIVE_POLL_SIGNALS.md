# Copied poll/select signal fixture

`tools/qualify_native_poll_signal.py --probe poll-signals` uses the same explicit
SDK29 Debug/source/toolchain/musl/QEMU arguments as the futex runner. It compiles
only the OS consumer and static guest, preserves transitive input hashes and
failed evidence, and runs a native pipeline, two complete guest commands and a
final native pipeline. Kernel source is never built by the OS.

All ten architecture profiles remain supported. Raw lanes include every admitted
poll, ppoll, ppoll_time64, packed old select, new select, pselect6 and pselect6_time64
number that exists for the target; absent syscalls are not invented. Four libc
interfaces run separately on every target. Raw ARM/Thumb and PPC initial CR0.SO
clear/set are separate forms. Libc uses its own actual syscall entry. The guest
passes six explicit arguments, including o32 stacked arguments, and uses null
temporary signal masks throughout. The BEGIN width field describes the raw lane
encoding, or native long width for libc lanes; the libc implementation owns its
local time representation, including RV32 time64 calls.

Each variant/form group runs nineteen cases: untimed and timed caught signals
with both SA_RESTART settings; copied input mutation; two descriptor reuse
controls; readonly output; readonly raw timeout when that syscall has a timeout
pointer; timeout memory mutation; readiness/timeout before signal; masked and
ignored signals; nesting; immediate timeout/readiness; fatal signal and exit with
an active wait. Libc timeout pointers are copied by musl and are therefore not
claimed as kernel readonly-timeout-copyout tests. Scalar poll has no timeout
pointer. Applicable variants remain explicit in the collector.

All caught poll/select calls complete without restart. Poll copies revents and
reports EFAULT when that output becomes readonly; select leaves the supplied
sets untouched on EINTR. Raw timeout output uses the original copied deadline,
and failed timeout copyout is ignored. Libc error returns and errno are checked
separately from raw negative results. Guards, unaffected fields, child statuses,
joins and cleanup are guest assertions. A cancelled wait after fatal/exit must
retire before the parent emits its verified child result.

The native collector requires an exact ARM after each ATTEMPT and before any
signal/readiness/mutation, exact owner/ticket retirement, immediate matching
SIGNAL publication, saved continuation/result encoding, all complete case records,
and final resources at the shell baseline with no newly captured faults. SIGNAL
labels cannot override contradictory numeric RETIRE results. Incidental poll,
futex and pipe events are separately paired; they cannot substitute for guest
waits. Diagnostic ARM records do not expose copied user pointers; immutable guest
source/assertions and the captured owner/syscall/count supply that part of the
evidence, rather than a claim that the diagnostic independently prints inputs.

Static compilation/ELF checks, Linux reference, synthetic parser tests and actual
SDK-native execution are separate evidence classes. The Linux reference explicitly
excludes concurrent close/reuse cases5/6: Linux may re-evaluate the replaced numeric
descriptor, while this admitted runtime retains the original description. The
initial Linux mismatch is retained. Both cases remain mandatory native guest
tests. Parent logs or scheduling delays are never accepted as native blocking
proof. Production signals, nonnull temporary masks, no-handler restart_syscall,
SMP, physical hardware, manual desktop and complete M0-M12 acceptance are excluded.
