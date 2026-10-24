# Owned scalar pipe read qualification

The dedicated `qualify_native_pipe_read.py` runner consumes an explicit hashed
Debug SDK29, builds only distribution sources and a musl probe, and executes two
complete commands with native pipelines before and after them. It retains source,
tool, SDK, image, rootfs, serial and offline filesystem evidence. No Kernel source
is compiled by the OS consumer. Results, not this document, establish execution.

The guest uses musl read and a direct architecture syscall shim across all ten
profiles. Each form runs four rounds of descriptor replacement, last-reader
reference, short data, EOF, changed output protection, zero length, nonblocking
and blocked-peer group-exit cases. It verifies original A bytes versus replacement
B bytes, unchanged guards, error conventions, child outcomes and unused pipe data
after EFAULT. A ready flag or elapsed delay does not establish a blocked syscall.

The collector requires a real owned arm between each attempt and mutation. It
binds the PID, nonleader TID, original fd, output address, count, open description,
pipe, initial request generation and current wait ticket. Rearm may change only
the current ticket. Completion must occur after original readiness and retire
the same object's pin. Exit cancellation is -125 and is not a return-to-user
claim. The global live count must match all published objects and return to zero
at every command boundary. Incidental reads in native pipelines have separate
complete identity/accounting pairs; their records cannot satisfy guest cases.
Linux images in either native pipeline, malformed/reordered events, unexpected
faults, unretired objects and incomplete assertion diagnostics are rejected.

The canonical guest has 64 cases, 48 observed blocking operations, eight EFAULT
cases and eight group-exit cancellations per command. Source compilation, Linux
references and synthetic collector controls remain distinct from ObfuscationOS
user execution. This slice does not enable caught pipe signals, SA_RESTART,
readv/write continuations, production signals, SMP, physical hardware or complete
workstation milestones. Exec retirement has separate hosted lifecycle evidence.
