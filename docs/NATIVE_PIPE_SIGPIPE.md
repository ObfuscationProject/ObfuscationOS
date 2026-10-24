# Private automatic SIGPIPE guest

The SDK-only `pipe-sigpipe-signals` probe exercises automatic caller-thread
SIGPIPE from scalar write and writev. Raw and musl calls, restart off/on and
immediate/resumed completion run on all ten native profiles. ARM and Thumb traps
and both PPC CR0.SO input forms are explicit. Each group has fourteen scenarios:
224 scenarios per normal-profile command and 336 per ARM/PPC command. Two commands
on all ten profiles contain 4,928 scenarios.

The guest checks default termination status 13; caught completed EPIPE frames;
ignored dispositions; blocked caught/default/ignored signals; ignored-to-caught
unmasking; two-write coalescence; retention of an earlier SI_TKILL payload; an
unrelated masked SIGUSR1; and an unblocked sibling's empty pending set. Automatic
payloads must be SI_USER, current PID and real UID. Handlers verify their actual
TID and TLS role. SA_RESTART cannot restart a completed EPIPE. A separate scenario
edits the completed saved result to 77 and verifies that exact return value.

Zero-byte success, EBADF, EFAULT and nonblocking EAGAIN must generate no SIGPIPE.
Both payload spans, guard bytes, all three vector descriptors and retained filler
bytes are checked. Each nonfatal process joins both threads and restores its
resources. Fatal children are checked through actual parent wait status.

For resumed writes, existing WAIT/ORIGIN/COMPLETE records must bind the exact
caller, copied vector or scalar payload, retained description and terminal EPIPE.
The unpinned COMPLETE must follow peer closure and precede handler/return/death.
Immediate writes own no blocked request. No new diagnostic is introduced.
The wrapper requires two fresh command images, native `hello | cat` before and
after, and exact child-wait, frame and owned-entry resource baselines.

The same C source has a separate host Linux reference mode. It requires a real
4096-byte pipe and observes blocked syscalls through `/proc/self/task/TID/syscall`.
Its x86_64 reference executes 224 scenarios, 240 explicit writes, 80 observed waits,
128 handlers, 32 signal terminations and 192 complete buffer checks. Those host
observations do not establish native OS execution. No native scenarios are skipped.

The implementation remains inside the existing private signal guard. Production
signal enablement, SMP, physical hardware and manual desktop acceptance are not
established by this probe. Existing scalar/vector EPIPE guests keep their explicit
SIG_IGN dispositions and their previously accepted source unchanged.
