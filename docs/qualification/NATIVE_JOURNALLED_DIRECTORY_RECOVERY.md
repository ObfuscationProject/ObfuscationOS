# Ordinary-directory chmod cuts and native recovery

These private fixtures qualify the bounded maintained ext4 side mount. They do
not select it as the distribution root or provide general namespace/allocation
mutation. The normal directory probe's first chmod changes existing directory
inode14 (`/child`) from0755 to02750 as UID1000, preserving its type and namespace.

`tools/test_journalled_directory_mode_cut.py` builds a separate SDK30 fixture with
an explicit `--cut-after` value from1 through20. Its user program is the normal
`tests/musl/journalled_directory_mode.c`; its cut instrumentation is separate from
the normal native fixture. It stops immediately after the selected real completed
write/flush and never returns to userland. It issues no additional device I/O.

`tools/jbd2/journalled_directory_mode_cut_protocol.py` checks bounded protocol
framing, exact first-operation ordering, Linux loader identity, transport ordinals,
and the unique terminal cut. `journalled_directory_mode_cut_evidence.py` also
checks the complete guarded disk against the independent libext2fs CRC transaction
oracle. Before the inode payload write, its timestamp-dependent descriptor CRC is
not yet observable; the oracle checks the descriptor checksum and every other
field rather than inventing that timestamp. Journal publication occurs at completed
call11: cuts1-10 retain the old child inode; cuts11-20 recover the new child inode.

`tools/test_journalled_directory_mode_recovery.py` builds a separate SDK-only
recovery fixture. Before constructing a mount, it acquires a bounded exclusive
BlockSessions session, excludes aliases/detach, runs exported
`Ext4RecoveryCompletion`, retires the session, and verifies stale access rejection.
Only successful durable completion permits mount and Linux user-program entry.
The mount API itself still requires a clean journal.

The recovery musl program checks child directory metadata/fd/alias identities,
complete root and child namespace entries, parent traversal through the child fd,
all4096 seed bytes, the other-owner payload, the symlink target and following,
full statx snapshots for child/root/seed/other/link/leaf, two fsync calls, and exit/reap.
The collector validates the exact old/new snapshots for the chosen cut, full
loader grammar and framing, recovery/public-call order, counters, and complete
guarded final bytes. Each recovery requires a further clean successor boot.

Builders require explicit architecture/mode/compiler-matched SDK30 manifests,
musl ELF/source build receipts, and fixture facts/disk hashes. They snapshot and
revalidate those inputs and do not compile Kernel source. Build-only output and
synthetic collector tests are not execution evidence. Native campaign qualification
must separately bind QEMU invocations, every failure, logs and whole disk hashes.
The bounded cut/recovery matrix uses x86_64/i386/MIPS; it does not narrow the ten
Kernel profiles or change the four supported distribution architectures.

These are software completed-call boundaries, not physical power cuts. No volatile
cache loss, torn/reordered writes or SMP behavior is established. Checksummed
whole-superblock CRCs may have a common residue; their ledger alone cannot uniquely
identify intermediate bytes. Full disk checks and pinned source provide additional
evidence. A successful guest FLUSH after restarting QEMU does not itself establish
that a fresh host fdatasync occurred or prove physical durability. A timeout can
leave writes that completed later and must remain a retained failure.

The integrated nonempty fixture also binds inode16 `/child/leaf`, its full statx,
namespace entry and24-byte payload through path, alias and retained directory.
The recovery validator inspects six allocated ordinary inodes; the root inode
is validated separately. Older empty-directory source/model receipts do not
qualify this added payload automatically.

## Automated qualification

The nonempty-directory campaign uses the repaired 869-file Kernel source and
the matching SDK30 exports. All twenty first-transaction completion boundaries
pass on x86_64, i386 and big-endian MIPS. Each saved disk passes the full cut
oracle, then a native recovery boot and a separate clean successor. These 120
native boots each execute 4,233 public checks, including the nested leaf payload.
Sixty independent Linux recovery guests validate the expected home metadata and
data, allowing only the documented Linux superblock/journal bookkeeping fields;
readonly e2fsck checks pass afterward. One representative sequence is included
once in these totals. No physical or human desktop validation is counted.

Retained preparation failures include an overlong private archive basename
(fixed as `musl-jdir-recovery`) and a recovery-image build launched before its
MIPS SDK existed. Neither reached an affected guest. The predecessor regular-file
campaign's three MIPS flush timeouts remain unresolved historical failures; this
directory campaign does not establish that their transport cause was repaired.
