# M0 source-index gap audit

Status: partial source audit on 2026-10-04. This document and the
[ext4/JBD2 bit catalog](ext4_feature_bits_linux_6_13_4.json) are drafts outside
admitted coverage. They do not replace a complete reviewed normative universe,
change an implementation state or source pin, or close M0.

The [coverage manifest](../inventory_coverage.json) retains four null source
indexes and empty mapping arrays. The directory `contracts/indexes/` is absent.
The protocol requires a reviewed JSON artifact beneath that directory, but does
not prescribe its basename. The eventual paths below are suggestions, not
previously mandated missing filenames.

| Inventory and eventual artifact | Exact source/content still required | Available source evidence |
| --- | --- | --- |
| `posix-clauses-options`; `indexes/posix-clauses-options.json` | Exact Issue 8 publication/corrigenda, admitted archive bytes, every Base Definitions, System Interfaces and Shell/Utilities obligation, elected XSI/realtime options, declarations, limits, errors/signals and per-architecture owner/test links | Ledger `posix-issue8` selects IEEE Std 1003.1-2024 / Issue 8 only; no archive hash. [P00/profile rules](../../POSIX_MUSL.md#31-target-declarations-and-certification) specify required inventory detail. Existing bounded syscalls or musl fixtures do not enumerate the standard. |
| `linux-abi-layouts`; `indexes/linux-abi-layouts.json` | Complete selected syscall/error/flag, structure, ELF/auxv, TLS, signal/context, time32/time64 and off64 units for every retained tuple, checked against Linux and musl sources, with golden vectors and explicit gaps | Pinned Linux 6.13.4 and musl 1.2.5 archives exist. [ABI bootstrap draft](linux_abi_bootstrap.json) contains selected model-manifest data; [Kernel codec manifest](../../../../../ObfuscationKernel/docs/abi/linux-profiles.json) and [codec contract](../../../../../ObfuscationKernel/docs/abi/linux-user-codecs.md) are bounded foundations. No full Linux ABI row is qualified. |
| `ext4-feature-combinations`; `indexes/ext4-feature-combinations.json` | Linux format fields and feature bits, dependencies and legal/rejected combinations; read/write/replay/tooling support and fixtures for each advertised profile; authenticated primary and separately selected secondary e2fsprogs source releases | Pinned Linux archive supplies exact ext4/JBD2 definitions. The new draft enumerates 40 ext4 and 7 JBD2 literal feature macros only. e2fsprogs 1.47.0 and 1.47.2 archive bytes are now pinned, with eight audited members per release. Detached signature verification and complete format/tool coverage remain open. |
| `internet-rfc-clauses`; `indexes/internet-rfc-clauses.json` | Selected RFC editions, updates/obsoletions and errata with archive hashes; every applicable MUST/SHOULD and explicitly reasoned option; protocol/socket/service owners and native/interop/fault tests | Ledger `internet-rfcs` has no selected normative universe or archive pin. The 47 exact [network-plan references](../../NETWORK_SERVICES.md#12-external-reading-and-decision-references) have an offline [byte manifest](internet_rfc_reference_sources.json) and independent source readback, but remain reading targets rather than a reviewed clause index. Existing native IPv4/UDP slices do not establish full TCP/IPv6/Internet-host coverage. |

## Source-root facts

Only the project's declared local source root, `build/sources/`, was inspected
for admitted upstream archives. This is not a claim about every file on the
host. Ledger revision `2026-10-04.01` has SHA-256
`1efc9d836ba6869424028667376d1c3c10bd9686b74600ede8c03cd8046f0bd8`.
The source root contains the following four ledger-pinned archives; their
current hashes match their ledger pins:

| Ledger source | Source-root-relative archive | SHA-256 |
| --- | --- | --- |
| `linux-uapi-ext4`, Linux 6.13.4 | `linux-6.13.4/linux-6.13.4.tar.xz` | `b80e0bc8efbc31e9ce5a84d1084dcccfa40e01bea8cc25afd06648b93d61339e` |
| `musl`, musl 1.2.5 | `musl-1.2.5.tar.gz` | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |
| `e2fsprogs-primary`, 1.47.0 | `e2fsprogs-1.47.0/e2fsprogs-1.47.0.tar.xz` | `144af53f2bbd921cef6f8bea88bb9faddca865da3fbc657cc9b4d2001097d5db` |
| `e2fsprogs-secondary`, 1.47.2 | `e2fsprogs-1.47.2/e2fsprogs-1.47.2.tar.xz` | `08242e64ca0e8194d9c1caad49762b19209a06318199b63ce74ae4ef2d74e63c` |

The Linux release signature/key files are present in the Linux directory. The
ledger records its earlier authenticated provenance; this draft rechecks archive
bytes and selected members, not a new signature campaign. musl's existing pin
records official HTTPS acquisition with no detached signature verification.
No admitted POSIX or RFC archive is present in this source root. The separately
retained 47 RFC reference files are outside source admission and do not change
the ledger's unpinned `internet-rfcs` source. `xmake` remains
an observed local tool without a reproducible upstream source pin. Both
e2fsprogs releases have selected source-byte pins, but detached signature
verification remains open. The installed primary tool version is 1.47.0;
the selected 1.47.2 source has since been built through an isolated xmake task.
Both tool versions passed bounded read-only checks on pinned images; reproducible
builds and general two-version read/write/replay interoperability remain open.

A separate bounded acquisition fetched e2fsprogs 1.47.0 and candidate 1.47.2
archives plus detached tar signatures from the official `www.kernel.org`
release directories. All four responses were HTTPS/HTTP 200 without a changed
effective URL. Its original files and acquisition receipts are retained under
`build/prototypes/m0-e2fsprogs-source-acquisition-v1/attempt-02/`, outside the
admitted source root. The first restricted-network attempt failed DNS resolution
and remains preserved. At acquisition time, 1.47.2 was a candidate and the ledger
still had a null secondary selection. A separate root-owned source review later
selected both releases and refreshed the ledger. That later byte-pin update does
not retroactively authenticate the acquisition receipt or qualify either tool.

| Archive retained in the acquisition lane | Computed SHA-256 |
| --- | --- |
| `e2fsprogs-1.47.0.tar.xz` | `144af53f2bbd921cef6f8bea88bb9faddca865da3fbc657cc9b4d2001097d5db` |
| `e2fsprogs-1.47.2.tar.xz` | `08242e64ca0e8194d9c1caad49762b19209a06318199b63ce74ae4ef2d74e63c` |

The acquisition receipt SHA-256 is
`94306a91953e664a5a21667885d886e7d594337539d10fca13fa874ce77f96df`.
Computed hashes and downloaded signatures establish retained bytes; they do not
establish trusted signature authentication. Independent maintainer-key provenance
and detached signature verification over each decompressed tar remain open,
as do complete normative/tool review, reproducible builds and interoperability.
No package source was compiled or executed by this audit or its acquisition.
The initial drafts under
`build/prototypes/m0-source-index-gap-audit-v1/attempt-01/` preserve the earlier
`2026-09-21.23` ledger baseline and its unselected-secondary observation.

## Bounded ext4/JBD2 work completed

The draft reads four unique ordinary members directly from the exact Linux
archive. It records their SHA-256, source locations, literal macro values,
all ten applicable architectures, Kernel mechanism and OS fixture owners,
existing seed requirement/test pointers, and raw feature-mask gate observations.
No upstream source is compiled or executed by this audit.

| Selected Linux member | SHA-256 |
| --- | --- |
| `fs/ext4/ext4.h` | `f41c8032e06ebc7de9b771cd745fca13650832121ffc2fbfcedd9d43b1d78d75` |
| `include/linux/jbd2.h` | `a166557488181a92abec73ac387023be029101bb2e7b3620a01a8130786b308d` |
| `Documentation/filesystems/ext4/super.rst` | `812f0ade6b1c91adf80e7e3442463cdf2fb610b9c73370d3755b7b5077afd3c4` |
| `Documentation/filesystems/ext4/journal.rst` | `ae23e8ec62ae06fac5a14226a1bdaa4d1b7276aaeefd1c25a1ce1d98739bbbf2` |

The inspected primary-tree routes have different bounded admission rules:

- The [legacy writer](../../../../../ObfuscationKernel/src/fs/ext4_fs.cpp)
  requires compat=0, incompat=0x42 and ro_compat limited to 0x3. Allowing a
  `large_file` bit at this gate does not implement unrestricted large files.
- The [read-only recovery binding](../../../../../ObfuscationKernel/src/fs/ext4_recovery.cpp)
  requires compat=0x4, incompat=0x42 or 0x46 and ro_compat=0x400, with additional
  geometry, checksum, inode, journal and ownership restrictions. An inspected
  mask is not a mounted writer capability.
- The [JBD2 codec](../../../../../ObfuscationKernel/include/ok/fs/jbd2.hpp)
  requires checksum-v3, optionally permits revoke/64-bit tags, and rejects other
  feature masks/layouts. Tag width does not imply a general 64-bit ext4 volume.

The private successor's mounted startup/history/reclaim routes have their own
evidence in [implementation progress](../../IMPLEMENTATION_PROGRESS.md). This
draft does not turn those slices into general modern-ext4 support. It also does
not invent classification or complete semantic coverage for reserved bits,
inode flags, mount modes, recovery cases or cross-feature combinations.

## Owners, profiles and completion work

ObfuscationKernel owns ABI codecs and adapters, filesystem/protocol mechanisms
and the related native/model tests. ObfuscationOS owns musl/user utilities,
rootfs/profile policy, external drivers/services, upstream tools and distribution
interoperability fixtures. POSIX and RFC source selection/mapping is joint;
ext4 source semantics are Kernel-owned and tool/profile admission is OS-owned.

Retain every tuple below. Current ledger Linux qualification is `unqualified`
for all ten; narrower historical native tests remain separate evidence.

| Profile | Native compiler tuple | Intended Linux/musl tuple | ELF/endian |
| --- | --- | --- | --- |
| i386 | i386-elf | i386-linux-musl | 32/little |
| x86_64 | x86_64-elf | x86_64-linux-musl | 64/little |
| aarch64 | aarch64-elf | aarch64-linux-musl | 64/little |
| arm32 | arm-none-eabi | arm-linux-musleabi | 32/little |
| rv64 | riscv64-elf | riscv64-linux-musl | 64/little |
| rv32 | riscv32-elf | riscv32-linux-musl | 32/little |
| loongarch64 | loongarch64-elf | loongarch64-linux-musl | 64/little |
| mips | mips-elf | mips-linux-musl | 32/big |
| mips64 | mips64-elf | mips64-linux-musl | 64/big |
| ppc | powerpc-eabi | powerpc-linux-musl | 32/big |

The supplied musl userland set remains x86_64, aarch64, rv64 and loongarch64;
the broader ten-profile source/build/ABI obligation remains intact.

For actual source-index admission, each complete selected universe still needs
the strict [index schema](../inventory_index.schema.json): source ID, exact
section, obligation, reviewed classification and architecture set per unit.
Every indexed unit then needs a matching-level owned requirement, correctly
related planned tests covering each architecture, normative-to-plan relation
review, and a SHA/reviewer/date binding in the coverage manifest. Source IDs
cannot be omitted, units cannot be duplicated or dropped, and passing hosted
checks cannot substitute for native/physical execution requirements.

Finally, the 90-requirement/163-test ledger remains `seed-inventory`; source
archives must be checked under explicit `--source-root` for M0 admission, all
four inventory states remain partial, and dependency source pins remain open.
Physical M11 and manual M12 are user-deferred; that does not waive M0 duties.
This audit leaves coverage, ledger, schemas, progress and acceptance unchanged.
