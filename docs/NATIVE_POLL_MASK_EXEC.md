# Temporary signal masks across exec

`tools/qualify_native_poll_mask_exec.py` consumes an explicit architecture/mode
SDK29 artifact and pinned musl sysroot. It never compiles kernel source. The
private Debug signal fixture is required; production signal behavior is not
enabled by this probe. All ten architecture profiles remain in the runner.

Each command performs eight complete ELF replacements: ppoll/pselect combined
with exec from a leader handler, nonleader handler, a nonleader while the leader
waits, and a leader while a nonleader waits. Each attempt first fails exec and
checks that the current mask remains intact. Successful replacement checks
inherited handler/current masks, reset image state, leader identity, reset caught
actions, and two further temporary-mask restoration cycles. These are executed
guest assertions, not metadata-only process checks.

The collector joins each wait to its exact process/thread/ticket, requires
mask-capable syscall numbers, and verifies sibling wait retirement precedes new
image publication. Two complete commands must return stack/page accounting to
the shell baseline. Exec reuses its calling entry-stack lease: nine new leases
and nine image publications per command are distinct observations.

Hosted synthetic parser tests are under `tests/tools/test_native_poll_mask_exec.py`.
They are separate from QEMU execution and Linux reference behavior. Raw logs,
SDK manifests, initial/final scratch disks and command records remain in the
selected output directory, including failures. This does not establish SMP,
physical hardware support, production signals or complete POSIX conformance.
