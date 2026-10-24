# Workstation contract and evidence ledger

This is the executable first M0 batch. It preserves ten native profiles and
records 95 seed requirements, 175 test definitions and eleven admitted historical
evidence entries with ownership, dependencies and explicit gaps. It is not a clause-level standards inventory or a completed M0 gate.

Run from ObfuscationOS:

```sh
xmake plan-check --evidence-root=..
xmake plan-report --evidence-root=.. --output=build/workstation-capabilities.md
python3 tools/plan_ledger.py gate-m0 --evidence-root=..
```

`plan-check` validates schema/relationships and runs the ledger/source-admission
regressions. `plan-report` generates the capability matrix from `ledger.json`.
`gate-m0` deliberately exits nonzero: the ledger is a seed inventory, and none
of the four source universes has a reviewed clause/unit index. The separate
`inventory_coverage.json` protocol now pins each reviewed index by SHA-256 and
requires an exact mapping from every indexed unit to owned requirements and
their planned tests. It rejects missing/extra units, unknown source references,
declared sources with no indexed unit, unrelated tests and omitted architectures.
For each linked requirement, correctly classified units must collectively cover
every architecture named by that requirement; units may divide the matrix by
source or architecture. The baseline contains four `null`
indexes, so this is admission machinery, not an M0 completion claim.

Source pins need an archive artifact and an expected SHA-256. `validate` checks
the actual archive bytes when `--source-root=DIR` is supplied; `gate-m0` requires
this explicit root before it can pass. A hash string in `ledger.json` alone is
not source admission. The current musl 1.2.5 archive can be checked from a local
archive directory, but other normative source selections and pins remain open.

To advance one domain, review its complete selected source universe and place a
unit index under `docs/plans/contracts/indexes/` using
`inventory_index.schema.json`. Each unit must identify a source, exact section,
obligation, classification and applicable architectures. Record the index path,
hash, reviewer/date and every unit mapping in `inventory_coverage.json`. Each
requirement link repeats the normative source ID/section, the existing ledger
source version/section, a reviewed relation and its reviewer/date. The validator
requires the link's plan section to belong to the inventory's plan document,
and checks matching requirement level and mapped test coverage separately for
every unit architecture. Hosted tests are architecture-independent; native and
physical tests must name the architecture. The validator can prove the index
bytes and mapping are internally complete, but it cannot decide whether the
reviewed relation is semantically correct or whether the source index omitted a
normative unit. Those remain human source-review duties.
Keep the ledger inventory `partial` until that review and all mapped requirements
are present. The existing unpinned source and ten Linux ABI qualification gaps
remain separate.

## Bounded console evidence integration

The first eleven execution-evidence entries bind the promoted ABI73 console
slice to available test definitions. Nine host/model/tool records remain
separate from two actual x86_64 Debug/Release guest records; the same guest
records support the explicitly x86_64 console-login subrequirement. The all-ten
parent retains its complete architecture matrix. No requirement becomes
`verified`, and all thirteen complete milestone gates remain open.

Before consuming these entries, use the read-only historical receipt admission
tool with the physical absolute project root and explicit completion trust root:

```sh
python3 tools/console_receipt_admission.py --project-root=/absolute/project/root \
    --completion-sha256=f5d216fe6bdcf81ee12361a720d7e7ce10c585c9229d3b6a43d2c5fe732d457e
```

It checks all 24,340 immutable qualification inputs, original and successor
validator provenance, canonical-validation products and publication/document
receipt relationships without importing receipt-supplied code or running old
baseline guards. It proposes mappings and never rewrites the ledger. This is
historical evidence admission, not revalidation of current installed sources,
SDK directory identities, inverse trees or protected disks. `plan_ledger.py`
subsequently checks the mapped artifact hashes and ledger relationships; it
does not itself interpret receipt semantics. The exact retained evidence tree
is required under `--evidence-root`; a plain source checkout has no replacement
for those artifacts. Tests use synthetic fixtures and do not need that tree.

The records preserve four UID0 logins, UID1000 fixture peers, guest
`armed=unproven`, x86_64-only musl execution and the absence of retained-group
native foreground coverage. They do not establish PTYs, termios, full jobs,
orderly shutdown, SMP, physical or manual desktop acceptance. Normative source
indexes and source-unit mappings remain incomplete; importing evidence does
not pass M0 or M12. Existing failures remain retained.

## Data and validation contract

- `ledger.json` is versioned source data; `ledger.schema.json` is a strict JSON
  Schema Draft 2020-12 contract. The executable validator uses the schema's small
  supported vocabulary with Python's standard library, so checks need no network
  or downloaded Python package.
- Unknown fields/states, duplicate JSON keys/IDs, missing architecture profiles,
  mismatched native compiler triples, dangling/cyclic dependencies, orphan tests,
  unavailable entrypoints and mislabeled evidence layers fail validation.
- Requirement paths name the owning repository. Validation does not require a
  Kernel checkout, compile Kernel sources, or treat a source reference as an SDK.
  Available OS test entrypoints must exist; planned tests have acceptance criteria
  and no executable entrypoint yet.
- Source inspection and historical test reports do not become passing execution
  evidence. `native-partial` can describe an audited existing native path with
  explicitly recorded limitations; it is not a newly verified result.
- Execution evidence must point to actual files under `--evidence-root` and match
  their SHA-256 hashes, test layer, execution kind, architecture and mode. A
  `verified` requirement needs passing evidence for every linked test, all its
  native architectures in both debug/release, no outstanding limitations, and
  verified dependencies. Waived or failed runs cannot satisfy that state.
- `model` includes host unit/tool checks. `native` means executed QEMU CPU/user
  paths; `physical` is separate. Interoperability/fault tests record their actual
  execution kind. None of those labels alone asserts conformance or certification.

The recorded POSIX target is IEEE 1003.1-2024 / Issue 8; exact corrigenda and
clauses/options remain unaudited. The Linux 6.13.4 archive is now pinned to
SHA-256 `b80e0bc8efbc31e9ce5a84d1084dcccfa40e01bea8cc25afd06648b93d61339e`.
`tools/check_linux_source.py` verifies its decompressed tar signature against
Greg Kroah-Hartman's fingerprint published by kernel.org and checks all eight
ledger files plus 44 Kernel model references (46 unique files) in that archive.
This establishes source provenance, not complete Linux ABI or ext4 coverage.
The official e2fsprogs 1.47.0 and 1.47.2 archives are pinned, with eight audited
format/checksum/journal/tool source files per release. Check their complete
archive hashes, member hashes and exact release headers without executing
upstream code:

```sh
python3 tools/check_e2fsprogs_source.py --ledger=docs/plans/contracts/ledger.json \
    --source-root=../build/sources --output=build/e2fsprogs-source-readback.json
```

The output must be a new file. Detached release signatures are retained in the
source-pin evidence lane but have not been verified. The installed host tools
remain 1.47.0. An isolated xmake task built unmodified 1.47.2 source, and both
tool versions passed read-only `e2fsck -fn` checks on seven pinned images, plus
one damaged-image rejection each. The
[build](../../../../build/prototypes/e2fsprogs-dual-tool-interop-v1/build-attempt-02/result.json),
[interop](../../../../build/prototypes/e2fsprogs-dual-tool-interop-v1/interop-attempt-01/result.json)
and [independent audit](../../../../build/prototypes/e2fsprogs-dual-tool-interop-v1/independent-audit-01/result.json)
retain exact receipts. Reproducible tool builds, general two-version ext4
read/write/replay qualification, the complete feature/combination index and RFC
clause/update/errata inventories remain open.

The network plan's section 12 contains 47 exact RFC Editor text references.
Their 4,320,930 source bytes were [acquired](../../../../build/prototypes/m0-rfc-source-acquisition-v1/attempt-01/ACQUISITION.json)
and [independently read back](../../../../build/prototypes/m0-rfc-source-independent-v1/review-01/result.json).
The [draft byte manifest](drafts/internet_rfc_reference_sources.json) and
`tools/check_rfc_sources.py` make that readback repeatable without network access.
An additional [direct readback](../../../../build/prototypes/m0-rfc-source-acquisition-v1/readback-02.json)
passed against the original source directory:

```sh
python3 tools/check_rfc_sources.py \
    --source-dir=../build/prototypes/m0-rfc-source-acquisition-v1/attempt-01 \
    --output=build/rfc-reference-readback.json
```

This pins only the references currently printed in the plan. The selected
normative universe, updates/obsoletes/errata, individual MUST/SHOULD clauses and
owner/test mappings have not been reviewed. It does not populate the
`internet-rfc-clauses` coverage index or pass M0. The acquisition and independent
receipts have SHA-256 values
`9cdc15e559ea492f6b36f74c1ced03580a53399309b1dc2e3b64394ecdf04d09`
and `cfb855cff4ef791548c9daf07c1c1ca623e041a9d5e5109ca0a8c5bbdaf0d114`.
xmake 3.1.1+HEAD.3ba37a0 remains an observed host version.

The [Linux ABI bootstrap draft](drafts/linux_abi_bootstrap.json) copies the
Kernel's exact model manifest into an OS-side, ten-profile inventory of selected
syscall numbers, errno values and calling conventions. Regenerate or check it
only with an explicitly named Kernel manifest using
`tools/build_linux_abi_draft.py --kernel-manifest=PATH [--check]`. This is an
offline documentation audit; the OS build does not read or compile Kernel
sources. Its per-profile qualification remains unqualified, and the draft lacks
the complete syscall, structure, flag, signal, TLS and ELF clause universe needed
for the reviewed M0 `linux-abi-layouts` index.

## Independent Kernel parser and Linux bootstrap foundations

The Kernel now has an independent `Codec<Profile>` foundation for all ten
profiles, with checked time32/time64 byte conversion, raw syscall arguments,
MIPS O32 stack slots, and MIPS/PPC return/error conventions. Its generated
manifest crosschecks selected syscall numbers against Linux 6.13.4 and pinned
musl 1.2.5. See the [codec interface and integration gates](../../../../ObfuscationKernel/docs/abi/linux-user-codecs.md).
`P01.bootstrap-codecs` is recorded as `model-only`; the complete Linux ABI
requirement remains planned. The OS does not compile this Kernel code: its host
tests and source generator belong to the standalone Kernel repository.

The ledger now separates three additional `model-only` foundations:

| Contract | Available model/build validation | Remaining native boundary |
| --- | --- | --- |
| `P01.native-frame-bridge` | `scripts/test_linux_native_bridge.py` checks all ten hosted frame mappings; `--cross` compiles and checks all ten target objects | Complete processor ABI and concurrent TLS/thread qualification |
| `P01.exec-metadata` | `scripts/test_linux_exec.py` checks static ELF PHDR/TLS and auxv byte layouts; `--cross` checks target objects; `--elf PROFILE PATH` admits an explicit artifact | General dynamic images, qualified entropy and unrestricted VM/TLS |
| `P01.bootstrap-adapter` | `scripts/test_native_poll.py` exercises checked adapter paths with hosted copy/clock backends; `scripts/test_linux_bootstrap.py` compiles all ten target adapters | Complete child-tid/futex lifetime and Linux process/thread semantics |

These script paths are relative to **ObfuscationKernel**. The frame bridge copies
only declared MIPS O32 stack words and preserves MIPS a3/PowerPC CR0.SO semantics.
The exec helper requires real readable PHDR and initialized TLS mappings; it
does not invent an auxiliary-vector address or entropy. The adapter delegates
bounded I/O/VM copies to native handlers, supports monotonic time and selected TLS
setup, and returns ENOSYS for operations outside its explicit subset. Hosted
adapter tests do not represent all-ten target execution.

ABI 6 now connects these helpers to per-image runtime selection, Linux auxv and
matching saved-frame returns. Child-tid clearing is best effort before mapping
teardown, with no futex wake/join contract. Bounded native startup/TLS/time and file/sync guests now execute; the fresh
ABI 8 all-ten Debug/Release matrix passed 20 production-equivalent rows and
290 commands, with the two retained QEMU reader revisions explicitly identified.
ABI 9 added mapped heap/fixed replacement, checked VFS operations and runtime
journal binding; its process/preview batch completed 20 rows and 310 commands.
ABI 10 integrated owned process frames, Linux pathname/descriptor operations
and bounded recovery completion; its combined qualification passed 20 rows and
330 commands. ABI 11 adds pipe/seek adaptation and the bounded journal writer;
its combined Debug/Release qualification passed 20 rows and 350 commands. The separate ABI 12 batch
adds bounded monotonic sleep and exclusive block sessions; its combined matrix
completed20 Debug/Release rows and370 commands. ABI13 adds poll/open, canonical
metadata buffers and ARM32 firmware-backed frames; its combined Debug/Release
matrix passed20 rows and390 commands, including40 cumulative musl executions. The ABI 7 run stopped on a
stale incremental object and cannot qualify its recorded source snapshot. The
completed ABI 5 clock/ext4 matrix is a separate source snapshot;
see the [implementation progress](../IMPLEMENTATION_PROGRESS.md).

`P02.fdt-parser` records the bounded FDT parser and
`scripts/test_fdt_memory.py` hosted/explicit-DTB checks. Six QEMU DTB audits and
isolated all-ten freestanding compilation were reported by the implementation
batch; the runner has no `--cross` option. ARM32 now consumes the real FDT through the validated raw Linux boot-image
contract; QEMU8.2.2 LoongArch still supplies malformed RAM cells. A rejected
firmware profile is never silently replaced with a guessed map. Raw capture now exists on all ten entry
paths. Typed owned discovery and its standalone probes are integrated; full RAM
qualification, capacity policy and allocator integration remain open; see the Kernel
[boot handoff audit](../../../../ObfuscationKernel/docs/qualification/BOOT_MEMORY_HANDOFF.md).

`S3.jbd2-plan` records the independent checksum-v3 codec and ordered, committed,
revoke-filtered replay plan. `scripts/test_jbd2.py` uses a synthetic fixture with
an e2fsprogs 1.47.0 CRC32C oracle and pinned Linux 6.13.4 source hashes. It covers
1/2/4 KiB blocks, optional revoke/64-bit tags, wrap and bounded failures. It
performs no replay writes or mount admission; see the Kernel
[JBD2 model contract](../../../../ObfuscationKernel/docs/fs/jbd2-model.md).

Normal and ASan/UBSan model runs were reported for the codecs, frame bridge, exec
helper, FDT and JBD2 parser. Their `available` tests name reproducible entrypoints;
the source ledger contains no execution receipts and does not turn those reports
into `verified` requirements. Native wait pin/teardown behavior is separately
registered as `T.P04.poll-lifecycle-model`.

## Pinned musl source and static build experiment

musl 1.2.5 was downloaded from its official HTTPS release URL. The exact archive
SHA-256 and inspected source-file digests are in the `musl` reference in
`ledger.json`. Detached signature verification has not been performed. All ten
corresponding `arch/` ports are present in this release. Their existence does not
qualify the retained CPUs, compiler ABI, Linux syscall personality or userland.

```sh
xmake musl-source-check --archive=/path/to/musl-1.2.5.tar.gz
xmake musl-static-spike --archive=/path/to/musl-1.2.5.tar.gz \
  --arch=x86_64 --toolchain=/path/to/x86_64-elf --mode=debug \
  --out=build/ports/musl/1.2.5/x86_64/debug-new --jobs=4
xmake musl-static-spike --archive=/path/to/musl-1.2.5.tar.gz \
  --arch=ppc --toolchain=/path/to/powerpc-eabi --mode=debug \
  --ppc-clang=/usr/lib/llvm-18/bin/clang \
  --out=build/ports/musl/1.2.5/ppc/debug-new --jobs=4
```

The build task accepts an explicit archive and compiler installation. It enforces
archive/file hashes, rejects unsafe archive members, copies admitted source into
an isolated directory, invokes unmodified upstream configure/make, and stages
headers/crt/libc plus its COPYRIGHT under a separate sysroot. It never installs
into the host or native okcrt sysroot, builds Kernel sources, fetches dependencies,
or executes a target program. Existing output directories are refused; choose a
new `--out` for another attempt. Failed builds preserve their source/logs and
partial staging with `status=build-failed`, never a successful sysroot claim.

Both modes compile musl with `-O2`; debug additionally retains `-g`. Optimization
is required by musl's inline atomic implementation: the previous LoongArch `-O0`
build separated LL/SC with stack stores and stalled during clock initialization,
including under Linux user emulation. Debug information does not require `-O0`.

For PowerPC, the optional explicit `--ppc-clang` selects only the ordinary C
probe frontend; libc compilation and the final link retain the GCC toolchain.
Without this option, the historical bare-metal GCC experiment still reports its
ordinary-main failure. The option is rejected on other architectures. The shared
frontend check pins the locally audited Ubuntu Clang 18.1.3 binary, verifies its
effective Linux target and 32-bit/big-endian/64-bit-long-double macros, and keeps
the e500v2 soft-float flags explicit. The manifest records both compiler identities
and assembler/linker/readelf hashes. See the [exact local pin](PPC_MUSL_BLOCKER.md).

The result includes a source/build manifest, exact compiler identity, flags,
tool/runtime hashes, commands and output hashes. It also links an ordinary
`write` probe and checks ET_EXEC, machine/class/endian, program-header bounds and
absence of PT_INTERP. Build paths are remapped in debug information and GNU
ar/ranlib use deterministic indexes. Two fresh x86_64 debug builds had identical
hashes for all 234 installed/probe files. This is a demonstrated reproducibility
check for that profile, not a claim about all upstream toolchains or artifacts.

The initial cross-build experiment used the existing GCC 14.2.0 native compiler
installations. Static libc and a probe ELF linked on i386, x86_64, aarch64,
arm32, rv64, rv32, loongarch64, MIPS O32 and MIPS n64. MIPS requires explicit
`-mabicalls`; the retained MIPS64 linker also requires an explicit ELF64 big-endian
output format. Its startup-object ABI warnings remain qualification inputs.
PowerPC libc compiled with e500v2/soft-float/64-bit-long-double flags, but an
ordinary `main` probe failed to link: this bare-metal compiler emits an `__eabi`
startup dependency requiring EABI linker symbols. The original GCC failure is
retained; a subsequent explicit Clang 18 Linux-targeted application frontend
links the bootstrap probe without a stub or CPU substitution. The
[PowerPC startup diagnosis](PPC_MUSL_BLOCKER.md) records the tested GCC options
and version-pinned compiler source explaining why `-mcall-linux` is insufficient.
Kernel/native extensions retain their exact exported GCC compiler identity.

The separate `tools/build_musl_probe.py` / `xmake musl-bootstrap-probe` recipe
verifies an explicit admitted musl sysroot and writes source, linker-script,
compiler, linker-driver and ELF hashes plus the exact commands. The ten explicit
`build/musl-bootstrap-v4/<arch>/manifest.json` artifacts are all
`built-not-executed`. Their `bootstrap.ld` maps PHDR in a readable load, preserves
the four-byte TLS initializer, supplies RW/non-executable GNU_STACK and marks
ELFOSABI_LINUX while retaining the MIPS ABI version. This corrects the unmapped
PHDR layout in the initial ARM/AArch64/MIPS probes. PowerPC compiles its C
application through explicitly selected `--ppc-clang`; this does not qualify the
whole mixed-toolchain ABI.

Current probe admission requires a source build with schema 1, musl version
1.2.5, an explicit debug/release mode, `status=built-not-executed` and
`native_execution=false`. It verifies required startup/libc/header hashes before
creating an output directory, and records `source_version`, `source_mode` and
`mode` in the probe manifest. A partial sysroot from `build-failed` is rejected,
even if its static library exists. Earlier PowerPC failed-build and v4 records
remain historical artifacts; they are never relabeled as successful source builds.

[The build artifact audit](MUSL_BOOTSTRAP_BUILD_AUDIT.json) records all ten exact
manifest/ELF hashes, verified source/tool identities, command-log hashes and
independently decoded ELF facts. It inspects existing local outputs and does not
claim to have replayed their build commands or executed target code. The outputs
remain local and unversioned; the audit is not a ledger execution receipt.

Every Linux ABI row remains **unqualified**. musl programs must not be packaged or
executed through the existing native syscall personality. Static libc compilation
is not static musl guest execution (M3/L01), shared linking (M5/L02), POSIX
conformance, or completion of any native thread/signal/VM gate.

## ABI 14 bounded integration contracts

The combined candidate adds bounded positional I/O, select/pselect, qualified
file identities and readonly ext4 timestamps, deterministic native-stat field
projection, and privately owned ext4 publication/checkpoint. Kernel SDK and native
module generation are14; native UAPI remains0.4.0. Individual candidate evidence
is retained separately from fresh combined producer/consumer qualification.
The ledger records native-partial paths with their actual limits and no fabricated
execution receipts. Linux stat-family success, writable epoch timestamps, signal
masks, full off64, production SMP and journalled mount admission remain open.

## Audited ABI 14 shared integration

The frozen all-ten Debug/Release generation passed20 complete rows,430
commands,40 cumulative musl runs and2680 storage-device cases. The first
MIPS64 Release partial attempt is retained as a timeout failure; two fresh
complete Release rows provide the final tail evidence. A forced shared
x86_64 Debug producer/consumer/musl rebuild and independent offline checks
also passed. Native UAPI0.4.0 is unchanged. This closes bounded integration
gates only; M0–M12, general POSIX, SMP and physical qualification remain open.

## Audited ABI 16 shared integration

The exact union passed20 Debug/Release rows,470 commands,40 cumulative musl
executions,2680 earlier storage cases,328 mounted cases and56 privileged RTC
cases, plus two actual Linux boots. A forced shared x86 producer/consumer/musl
rebuild passed14 commands and fresh persisted-mode/data checks. Source and
generation boundaries remain explicit: SDK/module16, native UAPI0.4.0; public
realtime remains disabled. Component receipts and earlier ABI14 history remain
separate. The83-requirement/143-test seed ledger is an incomplete candidate
inventory; dated pending labels in it are not the current matrix status, which
is recorded above and in IMPLEMENTATION_PROGRESS.md. No complete M0–M12 claim.

## Audited ABI 17 public realtime shared integration

SDK/module17 and native UAPI0.5.0 use checked epoch clocks and explicit source
capability, width and copyout errors. The frozen all-ten Debug/Release union
passed470 commands and40 cumulative musl executions, plus16 extra epoch0/2040
boots and32 more executions on the four positive source profiles. Storage/RTC
regressions, two Linux boots and a forced shared x86 rebuild also passed. The
R2 i386 NULL-wrapper probe error and interrupted matrix remain preserved; R3
correctly distinguishes raw NULL identity from legacy-musl temporary output.
The84-requirement/146-test seed ledger and all complete M0–M12 gates remain open.

## Audited ABI 18 directory creation shared integration

SDK/module18 retains native UAPI0.5.0. All-ten Debug/Release producer/consumer
qualification passed470 commands/40 cumulative musl executions;16 extra date
boots passed32 more. Every new musl boot includes19-node/four-file final-image
oracles, including high GID/setgid inheritance. Three actual Linux reference
boots cover the two retained metadata gates and new readonly mkdir image oracle.
The fresh shared x86 rebuild and hosted/storage regressions also passed. Initial
mutable guest disk bytes were not retained, and Linux source provenance is not
established by a binary hash. Nonjournalled namespace mutation, unsupported
readonly creation, bounded resources and unqualified SMP/physical behavior remain
explicit. The86-requirement/152-test seed ledger leaves every M0–M12 gate open.

## Audited ABI 19 administrative realtime integration

SDK/module 19 and native UAPI 0.6.0 passed all-ten Debug/Release qualification:
550 commands, 40 cumulative musl executions, 20 privileged clock diagnostics
and 40 actual root/UID1000 clock fixture boots. Retained serial arithmetic binds
240 held-wait changes, 120 waits, 80 brackets and 56 raw setter records. Sixteen
extra date boots add 32 cumulative musl executions; three fresh filesystem Linux
references and the separate clock Linux reference keep their bounded scopes.
Fresh shared x86 producer/consumer qualification adds 18 commands and rebuilds
both musl probes. Initial and final mutable disks are retained in this generation.
The clock uses a serialized boot-CPU context, effective UID0/trusted credentials,
and explicit software provenance with unknown UTC accuracy. RTC writes, NTP,
filesystem timestamp maintenance/stat, SMP and physical qualification remain
open. The 88-requirement/158-test ledger does not complete the normative inventory
or any M0–M12 gate. Earlier evidence and failures remain preserved separately.

## Audited ABI20 maintained ext4 integration

SDK/module20 keeps native UAPI0.6.0. All ten Debug/Release profiles pass the
610-command union, including120 six-layout maintained service boots and20
actual UID1000 native/musl boots. Six-layout normal/sanitized hosted faults,
16 extra public date boots, fresh Linux readonly references and a further
21-command shared x86 producer/consumer rebuild keep their distinct evidence
scopes. All144 OS tool tests pass. Initial parallel-run failures are
retained separately from the explicitly selected lower-concurrency retry lanes.
Maintained nonjournalled storage is opt-in; default roots remain unqualified.
No Linux stat, SMP, physical or complete POSIX/ext4 claim is made. The90-row
requirement/163-test ledger remains an incomplete normative inventory.
