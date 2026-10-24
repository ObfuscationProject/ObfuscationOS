# Storage and ext4 implementation plan

Parent: [complete workstation implementation plan](README.md).

Status: planning only. Source audit date: 2026-09-20. This document proposes work;
its acceptance gates are not statements that the work has already passed. No
implementation, build, or test was performed while preparing this plan.

## 1. Objective and completion criteria

Provide a dependable, interoperable ext4 filesystem through the Kernel's VFS,
backed by OS-owned storage drivers, while preserving freestanding C++23, xmake,
the exported Kernel SDK boundary, and all ten architecture profiles:
`i386`, `x86_64`, `aarch64`, `arm32`, `rv64`, `rv32`, `loongarch64`, `mips`,
`mips64`, and `ppc`.

"Complete ext4" must refer to a published, versioned feature and behavior matrix,
not merely the ability to mount an image bearing the ext4 magic number. Track
three distinct milestones:

1. **Existing supported subset:** preserve today's working formats, syscall
   semantics, SDK consumption, and QEMU persistence evidence throughout refactoring.
2. **Modern ext4 interoperability:** read, modify, recover, and exchange ordinary
   Linux/e2fsprogs-created ext4 volumes, including common default features,
   checksums, indexed directories, large files, full extent mutation, internal
   JBD2 journaling, and persistent orphan recovery. The exact feature list and
   tool versions must be explicit; distro `mke2fs` defaults are not universal.
3. **Full declared ext4 scope:** complete the separately staged capabilities in
   the matrix, including quotas, external journals, encryption, verity, casefold,
   bigalloc, MMP, fast commit, and supported maintenance operations. These are
   optional deployment features, not quietly removed project requirements.
   Milestone 2 must never be relabeled as milestone 3 while these remain pending.

A feature needs more than decoding: negotiate it safely; enforce its VFS and
permission semantics; preserve it during unrelated writes; update all associated
metadata and checksums; recover interrupted changes; reject malformed inputs;
and demonstrate two-way interoperability. A read-only implementation and a
read/write implementation receive separate matrix entries. Runtime limits must
be reported as resource limits rather than disguised as unsupported disk formats.

Freeze the initial specification against named Linux ext4/JBD2 format revisions
and at least two supported e2fsprogs releases during gate S0. Record any historical
or experimental bits outside that edition explicitly. Future unknown features
remain subject to safe negotiation; no implementation can promise future formats.

## 2. Audited baseline and evidence boundaries

The implementation and tests below were inspected. Previously recorded execution
results come from the Kernel's `docs/VALIDATION.md` dated 2026-09-19; they were not
rerun for this plan.

| Area | Current implementation/evidence | Limit relevant to this plan |
| --- | --- | --- |
| Mounted ext4 | Kernel `include/ok/fs/ext4_fs.hpp`, `src/fs/ext4_fs.cpp`; `Ext4Node` implements VFS operations | Bounded non-journalled writer, not modern-default ext4 support |
| Format admission | Requires clean state; exact incompatibility mask `0x42` (`filetype`, `extents`), zero compatible bits, read-only-compatible bits limited to `sparse_super` and `large_file` | Even read-only mounts use this narrow gate; `has_journal`, `metadata_csum`, `64bit`, `dir_index`, and other modern combinations are rejected |
| Geometry | 512-byte device sectors; 1/2/4 KiB filesystem blocks; 128/256-byte Linux-layout inodes; at most 32 groups | No general 4Kn path, large descriptor layouts, larger blocks/inodes, or arbitrary-size group table |
| Mapping/allocation | Extent-tree reads through depth three; inline extent mutation with at most four physical runs; low 32-bit file size/block accounting | No general tree split/merge, unwritten-extent mutation, or complete large-file behavior; accepting `large_file` does not establish large-file support |
| Namespace | Create/remove, ordinary directories, rename/replacement, hard links, uid/gid/modes, zero-filled holes, truncate | 31-byte names, 64-entry materialized listings, 128 ext4 node slots; no symlink traversal, htree update, xattr/ACL or timestamps contract |
| Lifetime/path | Retained open nodes and cwd; mount IDs in cwd/open descriptions; alias mounts remain distinct; fork/close/exit tests | Path reconstruction is limited to 95 bytes; removed/replaced/covered cwd/dirfds are unreachable and relative operations return ENOENT; mount-point/ancestor moves return busy; no unmount syscall |
| Node cache | Existing inode number reuses a cached `Ext4Node`; destroyed nodes release slots | Linked, unreferenced inode slots are not a general reclaimable cache; walking many distinct live inodes can exhaust 128 slots |
| Durability | Dirty marker flushed before mutation; successful sync flushes and may mark clean when no retained orphan exists | No transactions or replay; interrupted writes need offline fsck. `NamespaceMutation` quarantines incomplete rename/link writes; it is not rollback or power-loss atomicity |
| Synchronization | `Ext4Node::sync()` synchronizes the filesystem; POSIX fsync/fdatasync use the same path | No per-inode transaction tracking, writeback error cursor, or directory-durability contract |
| Cache/locking | Separate `BlockCache` in `fs/storage.*`: eight 512-byte entries with write-through behavior; VFS holds its spinlock during several filesystem calls | Not a unified page cache and not wired in as the ext4 transaction cache; blocking device I/O beneath this lock cannot become the SMP/IRQ design |
| Device path | OS `drivers/virtio/block.cpp`: statically selected MMIO/PCI transport behind runtime `BlockDevice`; 4 KiB request chunks, read/write/FLUSH, static queue/bounce storage | One polling queue on the boot CPU, coherent/direct-mapped QEMU assumptions; no hardware SMP, noncoherent DMA, IOMMU or hot-unplug claim |
| Root policy | OS `modules/boot/storage.cpp`, `tools/mkext4.py` | Explicit small non-journalled image format; missing/non-ext4 media selects archive rescue root; invalid ext4 never triggers formatting |
| Earlier models | Kernel `Ext4Volume`, `UnixVfsModel`, `BlockCache`, driver ABI resource/DMA/wait/work objects | Preserve useful diagnostics/tests, but their existence does not establish mounted-filesystem recovery, real worker scheduling, or physical DMA support |

Recorded evidence includes all-ten-profile QEMU block-driver and ext4 two-boot
persistence acceptance, standalone debug kernels, native POSIX naming and cwd
semantics, and isolated x86_64/PPC release SDK consumers. The hosted ext4 suite
uses 1/2/4 KiB images and reports 1,776 injected read/partial-write/flush failures
across those sizes, logical extent-capacity quarantine, and clean ordinary fsck.
Those are error models and orderly synchronized restart tests, not power-cut
recovery evidence. A host executable built with a PPC/MIPS profile macro does
not execute a big-endian CPU; native QEMU probes remain necessary.

Source entry points for preserving evidence:

- Kernel: `scripts/test_ext4_fs.py`, `tests/host/ext4_fs_tests.cpp`,
  `tests/host/ext4_failure_tests.cpp`, `scripts/test_vfs_namespace.py`,
  `tests/host/vfs_namespace_tests.cpp`, `scripts/test_process_resources.py`,
  `tests/host/process_resource_tests.cpp`, and kernel roadmap VFS/storage tests.
- OS: `scripts/test_virtio_block.py`, `tests/drivers/virtio_block_probe.cpp`,
  `scripts/test_persistent_ext4.py`, `tests/tools/test_mkext4.py`, native POSIX
  acceptance, SDK artifact tests, and rootfs/distribution runners.
- Explanations: [current storage](../STORAGE.md), [Virtio block](../VIRTIO_BLOCK.md),
  Kernel `docs/modules/ext4-storage.md`, `docs/modules/filesystem.md`, and
  `docs/VALIDATION.md`.

There is documentation drift to repair during S0: OS `docs/CI.md` still describes
MIPS/MIPS64/PPC storage skips, while current driver sources and validation records
cover them. The parent workspace contract's introductory four-userland-profile
sentence is also older than the OS contract's explicit ten-profile requirement.
The implementation plan preserves all ten; historical prose must not narrow it.

## 3. Ownership, resource policy, and prerequisites

### Repository and dispatch boundaries

**Kernel owns:** VFS/path and mount objects, inode/file lifetime, page/buffer cache,
block request and durability contracts, extent/allocator algorithms, ext4/JBD2
mechanisms, generic synchronization, IRQ/DMA services, and essential CPU/platform
mappings. Keep the ext4 implementation here because it is a kernel filesystem
mechanism. OS policy must not be called from filesystem algorithms.

**OS owns:** Virtio and other external block drivers, Linux driver adaptation,
storage discovery policy, partition/root selection, image tooling, installer and
recovery UI, mount policy, e2fsprogs packaging, rootfs fixtures, and end-to-end
application acceptance. ATA/AHCI, NVMe, USB storage and future drivers consume
the same Kernel request contract; no Linux driver compatibility layer belongs
inside the ext4 implementation.

Concepts/templates and static dispatch should select architecture barriers,
byte-order codecs, checksum implementations and measured hot algorithms. Runtime
polymorphism is appropriate at actual filesystem, mounted-device and module
service boundaries. Do not build inheritance hierarchies merely to share extent,
bitmap, transaction or cache code. Do not encode filesystem on-disk widths in
`uptr`, or equate a host pointer with a device address.

Export changed interfaces with an explicit SDK ABI generation and artifact
manifest. Validate architecture, mode, compiler ABI and hashes; migrate OS
consumers and probes together. The OS must continue building without a Kernel
checkout or source-header fallback. Generic storage remains architecture-neutral.

### Explicit no-heap prerequisite

Kernel `docs/DEVELOPMENT.md` requires: "Keep `okernel` freestanding: no hosted STL
containers, heap allocation, exceptions, libc calls, or external C++ runtime
dependencies." `FrameAllocator` has bounded frame bookkeeping; driver
`OkSlabAllocator` is sixteen fixed 256-byte slots. Neither demonstrates a general
reclaimable production cache allocator or a sleepable allocation subsystem.

The master plan's **M1 selects Kernel-owned, fallible physical/page/object
allocators as a prerequisite**, including reclaimable backing for production
inode, dentry, page and transaction caches. This is not a choice deferred until
after the storage implementation. Before introducing those allocators, the
implementation must deliberately revise `docs/DEVELOPMENT.md` to permit controlled
Kernel allocation, with ownership, allocation-context, accounting/quota and
failure rules. The planning document itself does not change that contract.
Hosted allocation, exceptions and implicit external runtime dependencies remain
forbidden; freestanding C++23 is unchanged.

S0 specifies the storage resource budgets and dependencies on M1. Production
allocation requests use the Kernel's fallible APIs, not unrestricted `new` or a
private filesystem heap. Define reclaim and pinning rules, sleepable versus IRQ
contexts, resource limits, failure injection and per-profile validation before
using them in filesystem code. A cache's ENOMEM must not be reported as on-disk
ENOSPC.

Retain caller/boot-provisioned arenas, typed pools and emergency journal/recovery
reserves for early boot, panic and forward progress under pressure. These bounded
paths coexist with the selected production allocators; placement construction
into owned storage is distinct from hosted allocation. Scan arbitrarily large
disk structures incrementally rather than loading them all into RAM. Publish
capacities and expose configuration without imposing today's tiny fixed pools as
workstation limits. Do not let general reclaim consume the buffers needed by
the only commit/recovery worker capable of freeing memory.

Before concurrent writeback, provide real sleep/wakeup and worker execution,
reclaim-safe memory reservations, lock-order checking, and request completion
lifetimes. Existing state-only mutex/wait/work models are not sufficient. An
initial bounded synchronous journal can precede IRQ-driven I/O; an asynchronous
writeback implementation cannot precede these guarantees.

## 4. Versioned ext4 feature matrix

Tags: **M** belongs to modern interoperability; **X** is a separately staged
extension that remains required for full declared scope. **R** is recovery and
cross-cutting infrastructure. Every row needs fixtures for absent, present,
malformed and relevant combined states. "Pending" does not permit unsafe
read/write mounting in the interim.

| Feature/family | Current state | Planned semantics, dependencies and acceptance |
| --- | --- | --- |
| Superblock/groups, `sparse_super`, `sparse_super2`, `resize_inode`, `meta_bg`, `flex_bg` | Small classic layout only | **M:** checked descriptor placement/size, backup superblocks, reserved GDT space, flex/meta group placement, free counters, initialization flags and lazy inode tables; read/write images with multiple descriptor blocks and non-local metadata placement |
| `64bit`, `large_file`, `huge_file`, `extra_isize`, timestamps | Low 32-bit file/block path; only 128/256-byte inode handling | **M:** descriptor high fields, correct on-disk address limits, 64-bit size/sector counts, extra inode fields, nanosecond/epoch timestamps and preservation of unknown reserved fields; files above 4 GiB on 32-bit CPUs, sparse huge-volume fixtures and overflow rejection |
| 1/2/4 KiB and larger filesystem blocks; 512e/4Kn | First three block sizes over 512-byte sectors | **M:** common sizes over independently described device sectors. **X:** supported 8/16/32/64 KiB block formats, correct large-directory record-length encoding, buffers spanning multiple CPU pages; no silent dropping on 4 KiB-page architectures |
| Extents, unwritten extents, sparse files, `fallocate` | Shallow read; four inline runs for mutation | **M:** validated full tree traversal, split/grow/shrink/merge, initialized/unwritten transitions and zero-before-exposure; sparse truncate/grow, allocation beyond EOF, preallocation and hole punching. **X:** collapse/insert/zero-range APIs and online defragmentation; journal mapping changes and recover interrupted conversions |
| Legacy direct/indirect mappings | Not a writable mounted format | **X:** files without extent flag, indirect tree validation/mutation, Linux-created ext2/ext3-style inode layouts inside admitted ext4; never reinterpret block pointers as extent headers |
| Linear directories, names, types, `dir_nlink`, `large_dir` | Linear directories with 31-byte names and 64-entry output | **M:** 255-byte byte-string components, streaming iteration/cookies, complete file type handling and link-count overflow convention. **X:** large-directory limits and growth; disk capacity is independent of one syscall buffer |
| `dir_index` / htree | Rejected | **M:** supported hash versions, UUID/hash seed and signedness, collision chains, indexed lookup/readdir, split/grow and transactionally consistent index/leaf updates; Linux/e2fsck must accept results without rebuilding indexes |
| Symlinks, special inodes | No symlink traversal; regular/dir writer | **M:** fast/in-inode and block-backed symlinks, bounded iterative resolution, correct final-component flags, device-number encoding, FIFO/socket metadata and safe unsupported open behavior; ACL/permission checks during traversal |
| `ext_attr`, `ea_inode`, xattrs and POSIX ACLs | Absent/rejected | **M:** in-inode/external-block xattrs, sharing/refcounts/checksums, ACL masks/default inheritance/chmod integration, namespace authorization, security-label preservation. **X:** external xattr-value inodes (`ea_inode`) and large values; namespace/label storage is not an implementation of an LSM policy |
| `metadata_csum`, `metadata_csum_seed`, `gdt_csum` / `uninit_bg` | Rejected | **M:** CRC32C and legacy checksum variants where applicable; precise UUID/seed/inode-generation context; superblock, descriptors, bitmaps, inodes, extent nodes, directory tails and xattrs; validate before use and regenerate within the transaction |
| `has_journal`, `needs_recovery`, JBD2 formats | Rejected; dirty-marker-only writer | **R/M:** internal journal, descriptor/tag/commit/revoke parsing, escape handling, sequence wrap, checksums v1/v2/v3 as admitted, 64-bit tags, replay/checkpoint and abort. **X:** external journal binding, supported async-commit format and every remaining admitted JBD2 feature combination |
| `data=ordered`, `data=journal`, `data=writeback` | No journaling mode | **M:** ordered-data journal first. **X:** data journaling and explicitly selectable writeback mode with documented weaker data ordering; no mode may expose uninitialized allocation contents or invalidate metadata recovery |
| Traditional orphan chain, `orphan_file`, `orphan_present` | Open unlinked nodes remain allocated; clean marking waits for their release | **R/M:** restartable cleanup of unlink/truncate orphans, journal-coupled registration/removal. Include modern orphan-file format/checksums where emitted by selected tool versions; crash while recovering and zero-link open inode persistence |
| Quotas, `quota`, `project` | Absent | **X:** user/group/project quota formats, accounting, reservation, enforcement and administration; all allocate/free/chown/project transitions participate in transactions. Tests must distinguish EDQUOT, ENOSPC and ENOMEM and survive crash recovery |
| `encrypt` / fscrypt | Rejected | **X:** interoperable policy versions and formats, key identifiers/lifecycle, filename and data encryption, permitted no-key enumeration semantics, ENOKEY access behavior, secure key handling; keys/services are prerequisites, not a bit that can be ignored |
| `verity` / fs-verity | Rejected | **X:** descriptor/Merkle tree validation, enable operation, immutable verified data, digest/signature-policy integration and cache poisoning resistance. Corrupt data must fail verification; verity is integrity, not encryption |
| `casefold` | Rejected | **X:** versioned Unicode encoding/normalization tables, invalid-name policy, lookup/hash collision semantics and allowed encryption combinations; preserve ordinary case-sensitive directories and original names |
| `bigalloc` | Rejected | **X:** cluster allocation/refcounts/accounting, partial-cluster ownership at truncate/punch, extent interactions and journal/bitmap checksums; test multiple block-to-cluster ratios and ENOSPC without leaking clusters |
| MMP (`mmp`) | Rejected | **X:** exclusive-mount protocol, sequence/checksum validation, heartbeat timing, read/write transitions and failure fencing; needs dependable clocks/workers and shared-device tests. Do not claim to implement a distributed cluster filesystem |
| `fast_commit` | Rejected | **X:** independently validate/replay fast-commit areas before admission, track eligible metadata changes, durable head/tail/invalidation and full-commit fallback; require crash/replay interoperability with Linux, including mixed full/fast commits |
| `inline_data`, `stable_inodes`, read-only format state and other declared bits | Not generally supported | **X:** inline file/directory data and conversion to extents; stable inode-number/UUID constraints; honor format-mandated read-only state. S0 inventory must enumerate all remaining bits individually, with no catch-all write permission |
| Maintenance and lifecycle | No online resize/unmount protocol | **M:** safe sync, remount-read-only and unmount/freeze primitives. **X:** online grow, trim/discard, administrative label/UUID/feature changes where valid, fragmentation tools; keep shrink/offline repair in OS tools and never promise unsupported online shrink |

### Historical and separately encoded feature bits

These rows give individual dispositions to bits that the family matrix does
not cover. They are planned requirements, not new mount capabilities. Sources
are Linux 6.13.4 `Documentation/filesystems/ext4/super.rst` and `fs/ext4/ext4.h`,
and e2fsprogs 1.47.0/1.47.2 `lib/ext2fs/ext2_fs.h`. The pinned literal-bit
crosswalk is narrower than the format documentation: `EXCLUDE_INODE`, for
example, is documented even though none of those three headers defines it.
The complete S0 index must include documented fields and historical bits as
well as literal macros.

| Mask and bit | Individual disposition and acceptance |
| --- | --- |
| `COMPAT:0x0001` `DIR_PREALLOC` | **X:** directory allocation hints in `s_prealloc_dir_blocks`, distinct from file `fallocate`. Preserve hints; prove allocation, release and interrupted recovery accounting before write admission. Pending profiles reject this bit. |
| `COMPAT:0x0002` `IMAGIC_INODES` | Historical format requiring further specification; the pinned format document explicitly says its meaning is unclear. Reject pending a source-reviewed inode/directory contract and fixtures; do not infer support from the similarly named inode flag. |
| `COMPAT:0x0040` `LAZY_BG` | Historical bit absent from the selected Linux header; distinct from supported group initialization flags and `GDT_CSUM`. Reject pending a reviewed historical format, bitmap/inode-table rules and interoperability fixtures. |
| `COMPAT:0x0080` `EXCLUDE_INODE` | Documented unused historical bit, absent from the selected headers. Reject; record the documentation-only source unit and a negative fixture rather than silently omitting it from S0. |
| `COMPAT:0x0100` `EXCLUDE_BITMAP` | Snapshot-related historical bit defined by e2fsprogs. Reject pending ownership, descriptor/bitmap validation, preservation and snapshot recovery rules; never interpret its bitmap as the ordinary free-block bitmap. |
| `RO_COMPAT:0x0004` `BTREE_DIR` | The selected format document describes this bit as unused. It is distinct from `COMPAT:DIR_INDEX` htree support. Reject in the declared profiles pending a separately specified format and fixtures. |
| `RO_COMPAT:0x0080` `HAS_SNAPSHOT` | Historical snapshot format, not ordinary copy-on-write file support. Reject pending snapshot fields, inode/block ownership, reservation and recovery semantics; unknown sharing must not enter an allocator. |
| `RO_COMPAT:0x0800` `REPLICA` | Historical replication bit without an implementation in the selected Linux/e2fsprogs editions. Reject pending a format and replica-consistency contract; the bit alone supplies no replication semantics. |
| `RO_COMPAT:0x4000` `SHARED_BLOCKS` | e2fsprogs image sharing format. Reject pending a coherent read-only mapping contract and fixtures. Write admission additionally requires checked unsharing, complete ownership/accounting and recovery; ordinary extents must not authorize freeing shared blocks. |
| `INCOMPAT:0x0001` `COMPRESSION` | Historical compression format; reject both read-only and read/write pending an explicit codec, mapping/allocation and recovery profile. Reserved compression fields or flags are not an interoperable codec. |
| `INCOMPAT:0x0008` `JOURNAL_DEV` | **X:** identifies a journal-device filesystem; it is not a normal data-root volume. Reject as a data root. External-journal admission must separately validate journal UUID, user bindings, geometry, checksums and exclusive ownership before replaying a bound data volume. |
| `INCOMPAT:0x1000` `DIRDATA` | Historical directory-entry extension, distinct from `FILETYPE` and `INLINE_DATA`. Reject both mount modes pending exact record/length, lookup, iteration, checksum and mutation rules. |

For each rejection fixture, vary the named bit alone and with the nearest
related admitted feature. Check that rejection precedes root publication,
replay and every write/flush, including when `RECOVER` is set. Read-only
compatibility permits a future read-only profile where its full semantics are
safe; it does not require the current narrower profile to accept it. Changing
any disposition requires updating the reviewed source index, owner/test links
and advertised profile together.

For format testing, larger address fields do not authorize arbitrary values:
respect ext4's defined widths and limits, including extent physical addresses,
logical blocks and directory layouts. Incompatible feature combinations are
explicit rejection fixtures, not targets to force into working together.

### Feature and recovery admission policy

Decode all three ext4 feature masks and the journal masks before exposing the
root or changing a byte. Maintain separate capabilities for inspection, coherent
read-only mount, recovery, and read/write mount.

- Unknown `incompat`: reject both normal read-only and read/write mount.
- Unknown `ro_compat`: reject read/write; permit read-only only under the specified
  compatibility rules and after validating that the known reader can safely
  interpret the resulting layout. A known unsupported layout can still require
  complete rejection.
- Unknown `compat`: the format permits compatible readers to ignore it, but this
  implementation uses an explicit policy table. Only audited safe-to-ignore
  cases may mount; conservatively reject mutation until preservation is proved.
  Do not infer "safe to write" merely from the bit's class.
- Known features with unsupported required inode flags, hash/checksum versions,
  encodings or journal variants: reject the affected operation/mount safely;
  do not reinterpret data. Specify whether the unsupported inode blocks an
  otherwise safe read-only volume admission.
- A needs-recovery volume requires verified replay before coherent namespace
  access. Ordinary read-only mounting must not secretly write journal recovery
  to a read-only device. Offer an explicitly separate no-write inspection mode
  or a recovery-on-copy tool if needed; unreplayed data is not a coherent mount.
- Unsupported MMP, encryption, verity, quotas or casefold cannot be bypassed by
  clearing their flags. Probes do not format, fsck, repair or modify feature bits.

## 5. VFS objects, path resolution, and concurrency

Refactor around explicit ownership rather than storing all semantics in a path
string. Proposed objects are `Superblock`, `InodeRef`, `DentryRef`, `MountRef`,
`PathRef {mount, dentry}`, and `OpenFileDescription`. Names belong to dentries;
hard links share an inode. An open file has independent offset/flags, owns its
inode/path references, and remains valid across rename/unlink. Cwd and directory
FDs retain a mount as well as a directory. Mount IDs need generations before
slots can be recycled by unmount; stale IDs must never refer to a new mount.

Keep the current explicit-mount-ID fix and tests while introducing these objects.
A multiply mounted filesystem must preserve the selected alias for `..`, getcwd,
permission traversal and cross-mount EXDEV checks. Never choose the first mount
whose inode happens to match. Replace absolute-path-based mount attachment with
mountpoint objects before supporting mount-ancestor rename, nested unmount,
move-mount or namespace cloning. Root replacement must explicitly rebind the
boot service cwd; it must not rewrite every existing process's retained path.

Make path walking iterative and object based. Check search permission at each
actually traversed directory, including components before `..`; start relative
walks at their held cwd/dirfd, not by rechecking inaccessible ancestors. Apply this
consistently to open/create/stat/unlink/chmod/chdir/link/rename and *at variants,
not just the new naming operations. Define trailing slash, empty-path flags,
`.`/`..`, symlink loop limits, final symlink follow rules, root boundaries and
sticky directories. ACLs, effective versus real IDs, supplementary groups and
setgid-directory inheritance join the same authorization path.

A pathname reconstruction failure must not redirect operations to a replacement
inode. Complete detached-directory behavior later through object traversal:
getcwd can return ENOENT while valid operations on a retained detached directory
obey their own rules. Streaming directory iteration must expose a stable cookie
contract under mutation and never make 64 cached entries the filesystem limit.
Use fallible bounded path buffers with published PATH_MAX/NAME_MAX and explicit
ENAMETOOLONG; expand beyond today's 95/31-byte bounds.

Replace the global VFS spinlock around device work with short namespace/cache
locks and sleepable operation locks. Establish and document ordering among mount
namespace, rename serialization, ordered parent inode locks, inode mapping locks,
transaction handles, buffer locks and device queues. Reserve transaction credits
before taking locks that could block reclaim. Pin objects across lock release;
revalidate rename ancestry and name bindings before commit. IRQ completion only
publishes completion/wakes workers; it must not perform filesystem allocation,
replay, pathname walking or blocking cache reclamation.

Inode cache entries need reference counts distinct from link counts, generation
checks, dirty/writeback/transaction pins, bounded eviction of clean unreferenced
entries, and deferred reclamation after all I/O ends. Last-close orphan cleanup
may fail: preserve an on-disk recoverable orphan and record the error instead of
reusing its inode prematurely. Unmount must drain operations, file/mount refs,
writeback and journals or return busy; forced device removal enters a defined
failed state. SMP correctness is a separate gate from single-CPU behavior.

## 6. Cache, block I/O, and transaction ordering

### Canonical buffers and I/O contracts

Introduce a canonical metadata buffer cache keyed by device identity and block,
with one authoritative version, pins, dirty state, in-flight state, error state,
transaction ownership and generation. A generic dirty-buffer eviction path must
never write uncommitted journal metadata to its home location. Preserve or
explicitly replace the old sector-cache tests; do not layer an unaware writeback
cache under JBD2. Filesystem blocks can span multiple device sectors/CPU pages.

Add a page cache keyed by inode identity and logical page range for file data,
coherent across read/write, truncation, mapped pages and eventual direct I/O.
Zero-fill holes and unwritten regions; serialize dirty pages against truncate,
hole punch and inode reuse. File-backed mmap needs VM invalidation and writeback
integration before it is claimed. Delayed allocation/read-ahead/background
writeback are performance stages after correct ownership and durable ordering,
not prerequisites for the first synchronous journal implementation.

Evolve `BlockDevice` to expose explicit request/completion ownership, logical and
physical sector sizes, alignment, maximum segments/bytes, capacity, read-only
state and durability capabilities (FLUSH/FUA where available). Define completion
as transfer completion separately from persistence. A successful write or memory
barrier is not a device flush. Split/scatter requests without losing partial-byte
results or the first error. Flush ordering spans all queues of a device, including
queued requests not yet submitted when a flush fence is created. Reject writable
mounts when their required durability contract cannot be honored.

Keep transport/device virtual dispatch at this service boundary; select Virtio
transport/ring policies and architecture barriers statically. Introduce validated
partitions as bounded device views, GPT plus existing MBR discovery, multiple
stable device identities and OS root selection without arbitrary first-match
selection. Discovery must remain non-mutating.

### Required dependency order

Implement these as dependent milestones, not parallel enablement switches:

1. Fallible resource reservation, canonical buffer ownership, synchronous request
   completion and a truthful flush contract.
2. Checked modern read-only decoding/checksums and JBD2 recovery on scratch images.
3. A bounded synchronous transaction engine with metadata buffers protected from
   home writeback, restartable orphan handling and ordered-data dependencies.
4. Enable modern ext4 mutations only through that engine; prove crash consistency.
5. Add batching, delayed allocation and background/multi-queue writeback using the
   same transaction dependencies; then IRQ-driven and SMP scheduling paths.

Block/DMA/IRQ development may proceed on independent probes, but it must not
bypass the durability gate when integrated. Never enable a modern writable mount
just because replay alone works, or enable generic asynchronous writeback before
journal buffers have transaction ownership and checkpoint rules.

### Initial JBD2 transaction contract

A transaction handle reserves credits for every metadata buffer, journal record,
revoke entry, allocator/quota update and rollback scratch it may need. Bound and
calculate worst cases for rename/replacement, htree or extent splits, xattr
replacement and orphan creation. Operations that exceed a bounded transaction
must use explicitly recoverable multi-transaction protocols; do not expose half a
rename as an ordinary capacity error.

For the initial `data=ordered` implementation:

1. Pin dependencies and prepare private/owned metadata versions; no home-location
   metadata write can expose the uncommitted operation. Capture undo state or
   discardable private versions before mutation. Stage bitmap, count, inode,
   directory, orphan and checksum changes together.
2. Initialize and issue required file-data writes. In particular, newly allocated
   or newly initialized blocks must contain safe data before committed metadata
   can expose them. Wait for their ordered-data dependencies.
3. Write the journal descriptor/tags and metadata payload, escape records and
   revoke records with the specified checksums and transaction sequence. Make
   ordered data and journal payload durable before the commit record can become
   durable, using flush/barrier/FUA sequences supported by the actual device.
4. Write and durably complete the checksummed commit record. Only now may fsync
   report this transaction durable. A synchronous inode/namespace publication
   scheme is acceptable initially; specify the in-memory linearization point
   separately from disk durability.
5. Checkpoint committed metadata to home blocks, preserving ordering against
   later transactions modifying the same buffer. Flush home writes before
   persisting journal-tail advancement/reusing log space. Revoke/block-reuse
   rules must prevent old log contents from overwriting newly assigned blocks.

This is the conservative dependency contract, not a substitute for the precise
JBD2 format. Sequence-number wrap, tags, endianness, checksum variants, journal
superblock state, external-journal identity and commit/tail persistence must match
the frozen specification. ext4 fields are generally little-endian; JBD2 headers
and many journal fields are big-endian. Use distinct explicit codecs.

Recover by validating the journal, identifying complete committed transactions,
building revoke knowledge in the required order, replaying only valid committed
updates, then completing orphan cleanup. Recovery is idempotent and itself
interruptible. Reject corrupt/torn commits and never replay a block outside its
validated device/metadata domain. Do not publish the VFS root until recovery
and the mount state transition have reached a coherent state. Only clean
unmount/freeze transitions with drained work may claim the required clean state;
a mounted journaling filesystem is not marked clean after every file fsync.

For later modes, `data=journal` journals file data as well as metadata and tracks
mode-switch draining. `data=writeback` may relax user-data ordering but preserves
metadata consistency, allocation confidentiality and explicit durability calls.
Fast commit comes after full commit/replay: unhandled operations must force the
specified full-commit fallback, and no fast-commit tail may outlive the full
transaction state that invalidates it.

### Namespace and user-visible durability

Atomic rename means observers see the old or new namespace state; after recovery
there must be an allowed complete state, not half of the metadata update. This
is distinct from guaranteeing persistence merely because rename returned.
Document write/fsync/fdatasync/syncfs/sync and directory-fsync contracts. To make
an application replacement durable, support the conventional sequence: create a
temporary file, write, fsync it, rename, then fsync the affected directory; for
cross-directory changes define and test synchronization of both parents.
`fdatasync` must still persist metadata necessary to retrieve data, including
size and extent changes. It cannot skip allocation metadata.

Track writeback errors per inode/superblock and per open-description observation
cursor so fsync/close paths cannot accidentally erase a prior failure. Preserve
short-write progress and offsets if an error follows successful data transfer.
`Node::write` returning only `Status` and `FileBuffer` returning a whole fixed
array are candidates for a counted, streaming I/O interface. Define 64-bit file
offsets and overflow-safe libc/UAPI conversions on 32-bit profiles before large
files are enabled; do not widen only the internal ext4 field.

### Resource and media failures

| Failure point | Required behavior |
| --- | --- |
| Before mutation/credit reservation | ENOMEM, ENOSPC, EDQUOT, EFBIG, ENAMETOOLONG or unsupported as appropriate; namespace and persistent allocation unchanged |
| Journal space exhausted | Commit/checkpoint or wait using a progress reserve before taking blocking operation locks; bounded cancellation/timeout; no sleeping under spinlocks and no allocation-reclaim recursion into the transaction |
| Before a transaction's durable commit | Discard private changes or execute a proved abort protocol; no uncommitted metadata reaches home; do not return ordinary resource failure after irreversibly publishing a half-operation |
| Device I/O/checksum error during a transaction | Abort/quarantine the affected writable superblock, propagate EIO and preserve recoverable journal/orphan state; read-only continuation only under a documented integrity policy |
| Uncertain commit or failed flush | Do not claim durable success or retry as if nothing happened; expose the error and require recovery to determine durable state |
| Failure after commit during checkpoint | Keep committed journal records pinned, stop log reuse, propagate persistent errors; recovery can replay the committed transaction |
| Last close/unmount cleanup failure | Keep recovery records and dirty/failed state; do not reuse inode numbers or release I/O backing prematurely |
| DMA timeout/hot-unplug | Fence/quiesce/reset the device before reclaiming mappings; a timed-out request may still DMA. Preserve static/pinned storage until cancellation completion is proved |
| Memory pressure | Reclaim clean unpinned cache objects; throttle dirty producers and reserve emergency commit/recovery buffers; failure must not deadlock the only worker able to free resources |

Do not promise recovery from arbitrary media destruction. Dirty-marker restoration
is currently best effort on a failed device; the new journal likewise cannot make
an unwritable device persist a corrective record. Mount failure must remain
non-destructive and leave repair policy to explicit OS recovery tools.

## 7. IRQ, DMA, architecture and performance rollout

Preserve current polling drivers as a diagnostic/bootstrap path while adding real
completion IRQs, waitable requests and worker processing. Validate lost/spurious
interrupts, queue wrap, interrupt masking, error completion, reset and teardown.
Hard IRQ paths acknowledge and enqueue work using pre-reserved storage; blocking
transactions execute in a sleepable context. Define memory barriers separately
from DMA cache maintenance and storage persistence barriers.

Provide Kernel DMA mapping APIs with device masks, scatter/gather, bounce buffers,
map/unmap ownership, cache sync for CPU/device, alignment and eventual IOMMU
isolation. The current `OkDmaMapper` model and direct physical-address helpers do
not establish those guarantees. Keep PCI host-bridge/TLB/essential mapping support
in Kernel architecture/platform code and transport-specific queue code in OS.

| Profiles | Retained transport baseline | Required additional coverage |
| --- | --- | --- |
| i386 / x86_64 | PCI Virtio | 32-bit DMA/offset limits, high memory/bounce paths, INTx/MSI/MSI-X as implemented, actual device ordering |
| arm32 / aarch64 | Virtio MMIO v1/v2 | GIC delivery, weak ordering, noncoherent cache maintenance on physical targets, 32-bit address constraints |
| rv32 / rv64 | Virtio MMIO v1/v2 | Interrupt-controller routing, fences, platform coherence attributes, RV32 wide offsets/atomicity |
| loongarch64 | PCI Virtio | Interrupt routing, MMIO attributes, DMA mapping and platform barriers |
| mips / mips64 | Malta PCI via KSEG mappings | Big-endian format/ring access, uncached aliases, DMA physical conversion, 32-bit/n64 widths and cache ownership |
| ppc | ppce500 PCI through TLB/bridge windows | Big-endian CPU with little-endian Virtio and ext4, big-endian JBD2, guarded MMIO, DMA window bounds and IRQ routing |

Every stage keeps all ten compilable, SDK-exportable and covered by the current
QEMU storage baseline. New physical-board or SMP claims require separate evidence
per actual platform; unavailable physical tests remain explicit gaps. Do not
make advanced format support conditional on x86 alone. Large-buffer algorithms
must work with small page sizes and bounded kernel stacks.

Measure sequential and random throughput, latency distributions, metadata IOPS,
fsync latency, cache hit/miss rates, journal waits, dirty throttling and CPU cost
against named baseline workloads. Optimize after semantic and crash gates.
Use templates for measured policy/algorithm hot paths; evaluate code-size effects
on all ten images. No benchmark may disable checksums/barriers without labeling a
different durability configuration.

## 8. Candidate source refactoring

These are proposed locations, not requests to move files before dependencies are
ready. Keep each behavior-preserving extraction reviewable and move useful tests
with the implementation. Avoid a second filesystem implementation hidden in OS.

| Owner / current area | Candidate responsibility split |
| --- | --- |
| Kernel `include/ok/fs/vfs.hpp`, `src/fs/vfs.cpp` | `fs/vfs/{inode,dentry,mount,path,file,ramfs}`; one production namespace and object-lifetime contract; remove duplicated model semantics only after preserving distinct model tests |
| Kernel `src/fs/ext4_fs.cpp`, matching header | `fs/ext4/{format,features,superblock,group,inode,extent,allocator,directory,xattr,orphan,transaction,filesystem}`; pure checked codecs and algorithms separate from I/O/state |
| Kernel journaling | `fs/jbd2/{format,checksum,log,recovery,transaction,checkpoint,revoke}`; no dependency on OS root/image policy |
| Kernel `fs/storage.*`, `driver/driver.hpp` | `block/{device,request,queue,partition,buffer_cache}` and `fs/page_cache`; retain sector-cache model tests under their actual scope |
| Kernel `memory/*`, `driver/abi.*`, scheduler/IRQ support | Production pool/frame backing, cache reclamation, DMA and completion/worker mechanisms; keep existing bounded API models explicit until replaced by executed services |
| Kernel `posix/*`, `sched/resources.hpp`, UAPI | Mount/dentry handles, streaming/counting I/O, wide offsets, directory iteration, permissions/ACL integration, lifetime and durability APIs |
| OS `drivers/virtio/block.cpp` | `drivers/virtio/{transport,ring,block}` or equivalent static policy split; real device operation and DMA/IRQ SDK adapters remain here |
| OS `modules/boot/storage.cpp`, tools and runners | Named format profiles, explicit probe/mount/recovery policy, multiple-device selection, partition fixtures, safe upgrade/export tools and interoperability/crash harnesses |

Do not merge the older `Ext4Volume` metadata inspector into the writable mount
path by assuming its looser parsing is sufficient. Reuse checked codecs only
after their admission/error contracts match. Prefer stack-bounded iterators and
caller-owned scratch over large recursive frame allocations.

## 9. Interoperability and fault test program

All destructive tests use uniquely created disposable images or copies; never a
user's persistent disk. Record image hash, feature masks, UUID, block/inode size,
sector geometry, tool versions, compiler/SDK identity, architecture/mode, seed,
commands and logs. Keep mutation, crash and inspection copies distinct.

### Host e2fsprogs and Linux interoperability

- Generate a feature corpus with pinned `mke2fs -t ext4` releases and archived
  `mke2fs.conf`; include their defaults as well as explicit individual and pairwise
  combinations. Inspect masks with `dumpe2fs`/`tune2fs`; do not assume a command
  line enabled a feature without checking the image.
- Retain the present minimal format and all 1/2/4 KiB cases. Add block/inode sizes,
  4Kn adapters, multiple descriptor blocks/groups, flex/meta layouts, lazy tables,
  sparse large devices and files above 4 GiB without allocating entire host images.
- Create Linux fixtures through both e2fsprogs and a controlled Linux guest/loop
  mount: deep extent trees, fragmented/unwritten ranges, indexed directories with
  hash collisions and more than 64 entries, 255-byte names, symlinks, xattrs/ACLs,
  quota state and each staged feature. Read/write them through the Kernel host
  adapter, then verify with a fresh Linux mount and `debugfs`/`e2fsck -fn`.
- Reverse the direction: create/mutate with this filesystem, use Linux/e2fsprogs
  to modify it, then remount and verify here. Check bytes, inode identity, nlink,
  free-space counts, sizes/i_blocks, ownership, timestamps, flags and checksums.
- Use `filefrag`/`e4defrag` or equivalent mapping inspection, get/setfattr and
  get/setfacl, quota tools, fscrypt tools and fsverity tools as their stages land.
  A parser-only check is not feature interoperability. Record prerequisites and
  privileged Linux operations in the test harness.
- Keep ordinary successful-operation `e2fsck -fn` exit status clean. For deliberate
  crash images, first inspect the unrepaired copy, replay using the intended
  engine on a copy, then demand clean checking. A test that always runs repairing
  fsck before checking can hide incorrect writer/recovery behavior.
- Run selected xfstests generic/ext4 cases in a controlled Linux-like userland
  harness as syscall/tool support becomes available. Publish unsupported-case
  reasons; do not equate a small curated subset with the full suite.

### Deterministic crash and resource-failure testing

Extend the current cache/durable-device model with sector/subsector tearing,
write reordering, dropped writes, volatile caches, flush/FUA ordering, read errors,
corrupt checksums and failures of the clean/commit/tail records. Persist only the
modeled durable state, destroy all memory, and remount a fresh filesystem object.
Enumerate bounded traces at each record/block/flush boundary and supplement with
seeded randomized traces. Keep deterministic minimal reproductions.

Test create/write/extend/truncate/punch, rename/replacement across directories,
hard link/unlink/last close, extent/htree splits, xattr refcounts, quota updates,
orphan cleanup, journal wrap/checkpoint, and crash during recovery. Validate the
allowed old/new namespace states, data promises conditional on fsync completion,
no duplicate allocation, no stale-data exposure, no referenced freed blocks, no
lost committed transaction and no resurrected revoked block. Recovery must be
idempotent. Exercise journal-credit starvation and ENOMEM at every reservation,
including a full cache of dirty/pinned objects and the commit worker's reserves.

Use two independent recovery paths on copies: this engine and Linux/JBD2. Both
must reach equivalent allowed contents/accounting. Include corrupt/unrecognized
journal records and feature combinations; mount rejection must leave the image
byte-for-byte unchanged. A read-only inspection/rejection test must detect even
journal-superblock or MMP-heartbeat writes.

### Native QEMU, physical and concurrency evidence

Retain all existing Virtio request/FLUSH/error probes and two-boot POSIX persistence
tests on all ten profiles, in addition to standalone Kernel tests and OS SDK
consumption without source checkout. Add abrupt VM termination at explicit
transaction checkpoints with cache configurations whose persistence model is
recorded. Cross-endian tests write on one architecture, recover/read on another,
and verify offline; in particular PPC/MIPS must exercise JBD2 as well as ext4
codecs. Host profile macros alone cannot establish this.

Test real IRQ delivery/wakeup, CPU concurrency, cache coherence, lock contention,
rename/unlink/open races, write/truncate/fsync races, cancellation and hot-unplug
under the actual native execution path. Physical power cuts and noncoherent DMA
need separate hardware fixtures. QEMU `scope=hardware` markers continue to mean
executed guest instructions/device I/O, not physical-board certification.

## 10. Staged acceptance gates and delivery order

| Gate | Deliverable and dependencies | Exit evidence |
| --- | --- | --- |
| **S0 — Contract and fixtures** | Freeze format/tool editions and full feature inventory; specify the M1 allocator dependency/contract revision and 64-bit UAPI policy; document resource/error/durability contracts and repair doc drift | Reviewed feature/admission table, reproducible fixture manifests, memory/credit budgets and ownership diagram; all prior tests retain their scope and ten-profile entries |
| **S1 — Behavior-preserving foundations** | After M1 allocation/lifetime foundations: extract checked codecs; streaming buffers/iteration; mount/inode/dentry lifetime and ID generations; short-lock/request ownership; preserve existing subset | Existing host, standalone Kernel, native OS and isolated SDK consumer regressions pass; explicit cache/handle exhaustion and alias/covered-path tests; no format admission expansion yet |
| **S2 — Modern read-only reader** | Checksums, group layouts/64-bit fields, full extent reads, htree, inode metadata, symlinks/xattrs and feature negotiation; no recovery writes hidden in read-only mount | Linux/e2fsprogs corpus reads match; corrupted/unknown images rejected safely; true read-only mounts are byte-identical; large-file/large-directory cases run on 32-bit and big-endian profiles |
| **S3 — Recovery engine** | Canonical metadata buffers and reserves; internal JBD2 decode/replay/revoke/checkpoint rules; orphan recovery; synchronous block durability first | Interrupted Linux journals recover equivalently on copies; every recovery step is restartable; journal checksum/wrap/torn-write tests; no read/write claim based only on replay |
| **S4 — Transactional modern writer** | Route allocation/free, inode, directory, extent, xattr/ACL and namespace mutation through one transaction contract; ordered data and fsync semantics; classic/modern orphan paths | Two-way modern ext4 writes; enumerated commit/checkpoint fault points; Linux and native replay equivalence; fsck-clean normal and recovered images; per-operation atomicity/resource guarantees |
| **S5 — Primary modern interoperability** | Complete all M rows for the frozen common feature profiles; consistent permissions, wide offsets, remount/unmount, installation/root selection and OS tools | All-ten-profile modern ext4 native root/app/restart/recovery matrix, selected xfstests with explicit gaps, standalone Kernel regression and debug/release SDK isolation; publish exact matrix, not "full ext4" |
| **S6 — Cache/IRQ/SMP performance** | After S4 ordering is proved: coherent page cache/mmap integration, delayed allocation, background writeback, real IRQ workers, multiqueue, DMA mapping, reclaim and SMP | No durability/semantic regression; native concurrency/failure probes, cross-architecture performance baselines, pressure/deadlock tests; separate physical DMA evidence |
| **S7a — Extended format/administration** | Legacy mappings, larger blocks, inline data/ea_inode, large_dir, quotas/projects, external journals and remaining admitted journal/data modes; maintenance/freeze/online-grow tools | Dedicated mixed-feature corpus and two-way Linux operation/recovery; filesystem and journal on separate failed devices; quota/resource enforcement; online grow crash tests |
| **S7b — Specialized semantics** | fscrypt, fs-verity and casefold with their key/crypto/Unicode/security dependencies | Correct access/verification failures, Linux policy/data interoperability, allowed feature combinations, crash-safe metadata and no secret exposure through cache/reuse |
| **S7c — Cluster/log extensions** | Bigalloc after allocator/extent transactions; MMP after clocks/workers/fencing; fast commit after full journal and replay stability | Partial-cluster recovery, simultaneous-mount refusal/heartbeat failure, Linux fast-commit/full-commit crossover and crash corpus; safe fallback/rejection for unsupported combinations |
| **S8 — Full declared-scope audit** | All M/R/X commitments for the frozen edition complete; every residual limitation explicitly resolved or agreed as a scope change | Feature-by-feature read/write/recovery ledger with links to reproducible evidence, interoperability versions, resource/platform limits and complete ten-profile baseline; no unacknowledged pending feature under a "complete" label |

S7 tracks can overlap after their actual dependencies land; they are not required
to wait for every S6 performance optimization. MMP specifically needs real timing
and workers, while encryption/verity need cryptographic and key-management
services. S4's synchronous journal is the first crash-consistent write milestone;
S6 must extend it rather than replace it with an independent writeback mechanism.

Each delivered stage should be a small sequence of reviewable changes: preserve
behavior first, add negative/failure tests before widening format admission, then
publish the SDK consumer update and evidence together. Keep newly supported
features disabled for image creation until both the writer and recovery gates
for that feature pass. Retain a documented rescue format and never regenerate an
existing persistent user disk as a migration strategy.

## 11. First implementation tranche

1. Inventory exact ext4/JBD2 bits and tool-produced default images; turn admission
   decisions into test data. Record existing negative fixtures and all limits.
2. Specify pool/arena budgets, cache ownership, 64-bit offset/UAPI transition,
   block flush/completion semantics, and transaction credit accounting. Resolve
   the no-heap contract revision and M1 Kernel allocator prerequisite explicitly
   before allocating production caches.
3. Extract endian/checked-offset/checksum codecs and test malformed metadata
   without changing the admitted writable format or moving the external driver.
4. Replace bounded directory materialization and unreferenced-node cache exhaustion
   with streaming/reclaimable mechanisms, preserving alias mount/cwd/open-file
   regressions and making errors observable rather than silent null lookups.
5. Build read-only modern fixtures and JBD2 replay on disposable images; establish
   independent Linux recovery comparisons before enabling journalled mutation.

This document specifies the technical direction; it neither starts implementation
nor claims that the full filesystem exists. Implementation reports must distinguish
host models, QEMU native integration, crash simulation, and physical validation.

## 12. Upstream references to pin

- [Linux ext4 on-disk documentation](https://docs.kernel.org/filesystems/ext4/)
  and [journal format](https://docs.kernel.org/filesystems/ext4/journal.html).
- [e2fsprogs upstream](https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git/).
- [fscrypt documentation](https://docs.kernel.org/filesystems/fscrypt.html) and
  [fs-verity documentation](https://docs.kernel.org/filesystems/fsverity.html).
- [xfstests upstream](https://git.kernel.org/pub/scm/fs/xfs/xfstests-dev.git/).

These are implementation reference targets; no upstream source or current
release was downloaded or qualified by this planning change. S0 must record
exact commits/releases and the normative field/feature rules used by fixtures.
