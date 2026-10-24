# Native mount inventory

`mountctl status` reads the Kernel's current global VFS namespace directly. It
needs no daemon, service manifest entry or administrator privilege. The tool is
an ordinary native executable installed in `/bin/mountctl` in maintenance and
console-login images. The console product profile is
`ordinary-native-console-login-logging-time-mount-v1`; its admission binds the
persisted executable bytes, root ownership, mode 0755 and single-link identity.
Earlier product sidecars are refused without changing enrolled disks.

The UAPI0.11.0 SDK declares `ok_mount_info(slot, output)` with nine boot-local
slots. Every result has version, wire size, generation, slot, capacity, state,
parent ID and path length in eight native-endian 32-bit fields, followed by a
zero-padded 256-byte path. The wrapper passes the exact 288-byte size and clears
all three reserved syscall arguments. The Kernel alone creates these records.
Linux personality calls remain unsupported.

Slot 0 represents the underlying RAM namespace, including when a provider covers
its `/` path. `covered=1` reports that case explicitly. Slots 1 through 8 report
unused capacity, borrowed provider attachments, owned provider attachments,
owned RAM attachments or detached history. A detached slot cannot be reused;
its path and parent describe history. Provider ownership states do not identify
a concrete filesystem type, device, mount options or durability capability.

The generation is `1 + used slots + detached slots`, between 1 and 17. One
syscall observes one row; it does not return a whole-table atomic snapshot. The
tool stages all nine rows with equal generations and then rereads slot 0. It
validates the complete wire rows and inventory before printing anything. Busy
or changed observations restart the pass at most eight times; exhaustion and
other errors fail with a diagnostic and no inventory output. Path output uses
quotes and escapes quote, backslash and every control or non-ASCII byte, so a
recorded name cannot inject terminal control sequences or extra output lines.

The interface grants no ownership reference, mutation authority, mount/umount
operation, service drain, persistence guarantee or shutdown admission. HALT
continues to require the original owned journalled root and owned `/run`, a
closed producer boundary, drained owners and the original storage seal.

Hosted controls run the actual CLI with deterministic inventory and output
seams, including every-call busy/error faults, bounded instability, malformed
wire fields, zero padding, escaping and maximum-length paths. Set
`OK_TEST_KERNEL_SDK` to an explicit exported inventory SDK and run
`python3 -B -m unittest discover -s tests/tools -p test_mountctl.py`. These are
hosted controls, separate from all-profile native compilation and actual guest
execution. They establish no SMP, physical-machine or general mount-mutation
acceptance.
