# POSIX.1-2024 and musl implementation plan

Status: design for review, not an implementation or a conformance claim.
Audit date: 2026-09-20. Source baseline: ObfuscationKernel `c15dee2`,
ObfuscationOS `7bff2e9`. This audit read source and existing evidence; it did not
build, execute tests, download musl, or verify an upstream release archive.

The intended product is a POSIX operating system, including Shell and Utilities,
with a musl-based userland on **all ten existing architecture profiles**. A libc
that links, a program that boots, Linux syscall numbers, and a POSIX certificate
are four different outcomes. This plan tracks them separately.

This document expands the [main implementation plan](README.md). Its P/L work IDs
are stable subsystem requirements; the main plan's M0–M12 labels are integration
milestones. The crosswalk in Section 7 explains their relationship.

## 1. Ownership and contract decisions

The [Kernel contract](../../../ObfuscationKernel/AGENTS.md),
[OS contract](../../AGENTS.md), and
[Development Standard](../../../ObfuscationKernel/docs/DEVELOPMENT.md) apply.
Kernel mechanisms, VM, scheduling, trap handling, credentials, VFS, native module
interfaces and essential platform support remain in ObfuscationKernel. musl,
programs, shell, utilities, locale data, distribution services, external drivers
and Linux **kernel-driver** adaptation remain in ObfuscationOS. A Linux
**userspace syscall personality** is a Kernel ABI decoder over Kernel mechanisms;
it must not be implemented through the OS Linux-driver compatibility model.

**P00 includes a prerequisite allocator-contract revision during implementation.**
The current Development Standard explicitly prohibits "heap allocation" as well
as hosted STL containers, exceptions, libc calls and external C++ runtime
dependencies. General VM and scalable process objects require deliberate
Kernel-owned frame and object allocators. Before implementation, revise that
prohibition to permit audited, failure-reporting Kernel allocators with explicit
ownership, budgets and allocation contexts. Retain freestanding C++23, xmake,
no exceptions, no hosted libc or C++ runtime, and no hidden allocation in hot
paths. This documentation task leaves the contract unchanged. The planned revision
permits neither unrestricted `new`, hosted `std::vector`/`malloc`, nor general
allocation from interrupt context; it is implementation work, not a routine
permission checkpoint between milestones.

Architecture operations, ABI codecs, page-table operations and scheduler policies
should use concepts/templates and static dispatch. Runtime polymorphism belongs
at actual filesystem, device and module service boundaries. Kernel internal C++
interfaces are not user ABIs. Each OS build consumes an explicitly matched,
validated architecture/mode SDK; it never builds Kernel sources or chooses a
convenient artifact from a glob.

Preserve current profiles, CPUs and their rescue images while adding musl. A
blocked musl qualification on a profile remains a visible work item; replacing
PPC e500v2 with another PowerPC CPU, replacing MIPS CPUs to gain NX, or dropping
RV32 does not satisfy this plan.

## 2. Evidenced baseline and immediate implications

Source links are to the sibling repositories in the existing workspace layout.
Symbols and behavior, rather than a syscall enum entry, establish implementation.
Existing documents sometimes describe a broader trusted-buffer model than the
native entry point; the native whitelist is authoritative.

| Evidence | What exists | What it does not establish |
| --- | --- | --- |
| [Native execution](../../../ObfuscationKernel/docs/NATIVE_EXECUTION.md), [execution API](../../../ObfuscationKernel/include/ok/arch/execution.hpp), `src/arch/*/execution*` | Real user privilege, traps, user copies, timer interruption and saved integer/FP/TLS state on ten QEMU profiles | Physical-board validation, hardware SMP, general VM, Linux userspace ABI |
| [Native runtime](../../../ObfuscationKernel/src/user/runtime.cpp), `load`, `dispatch`, `step` | Native ET_EXEC execution with static test binaries, eager-copy fork, staged exec, wait/reap, pipe and checked scalar/vectored I/O; only first native thread of each process is selected | Native clone/pthreads, general mmap/brk/mprotect, signal delivery, futex, ioctl, sockets, poll/select |
| Same runtime, `physical_pages`, `Pages`, `elf_buffer`, `load` | 1,024 backing pages (4 MiB), at most 128 pages/process, 128 KiB input ELF, 64 KiB stack, 16 argv and 16 env strings; 4 KiB I/O and 16 iovecs | malloc-capable address-space growth, scalable ELF loading, demand paging or COW |
| [ELF parser](../../../ObfuscationKernel/src/sched/process.cpp), `ElfLoader::load` | Validates architecture/class/order/ranges and PT_LOAD metadata; parser accepts ET_DYN metadata but runtime rejects it; non-PT_LOAD headers are ignored | PT_INTERP execution or explicit rejection, PT_TLS setup, relocations, PIE, validated architecture `e_flags`; ET_EXEC alone does not establish static linkage |
| Runtime initial stack construction | argc/argv/envp plus AT_PAGESZ and AT_ENTRY | musl's complete startup/auxv and dynamic-loader contract |
| [UAPI](../../../ObfuscationKernel/include/ok/uapi/syscall.h), [syscall model](../../../ObfuscationKernel/src/core/kernel_syscalls.cpp), [ABI mapping](../../../ObfuscationKernel/src/syscall/linux.cpp) | Project common numbers based on x86_64 Linux, project structures/errors, trusted-buffer service dispatch | Architecture-specific Linux numbers, argument packing, errno tables or Linux structure layouts |
| [Process resources](../../../ObfuscationKernel/include/ok/sched/resources.hpp), [scheduler](../../../ObfuscationKernel/src/sched/scheduler.cpp) | Canonical process/thread records, shared open descriptions, retained cwd plus mount identity, close-on-exec, exit status, orphan reaping, bounded pipe waiters | Reference-safe concurrent SMP objects, signal-aware interruptible waits, full process groups/sessions |
| [POSIX process models](../../../ObfuscationKernel/src/posix/process.cpp) | mmap/mprotect/munmap modify records; futex WAIT returns would_block and WAKE returns zero; signal handler is a no-op; TLS/robust-list addresses are stored | Real mappings, atomic futex queues, signal frames, robust-owner death, native TLS installation |
| Same process models and native timer handling | Clock ticks advanced by user timer returns; model nanosleep advances a counter; deterministic getrandom seeded by ticks | Idle-progressing monotonic time, realtime clock, actual sleep, cryptographic entropy |
| [Memory API](../../../ObfuscationKernel/include/ok/memory/memory.hpp), [memory implementation](../../../ObfuscationKernel/src/memory/memory.cpp) | Fixed frame/page-table/user-copy models alongside the separate native backend | A unified allocator/VM whose allocations back every running process |
| [SMP](../../../ObfuscationKernel/src/smp/smp.cpp), [spinlock](../../../ObfuscationKernel/include/ok/smp/smp.hpp) | CPU topology/state bookkeeping and atomic-flag locks | AP bring-up, per-CPU native scheduling, remote TLB shootdown, IPI delivery |
| [Paths](../../../ObfuscationKernel/src/posix/path.cpp), [VFS](../../../ObfuscationKernel/src/fs/vfs.cpp), [ext4](../../../ObfuscationKernel/src/fs/ext4_fs.cpp) | RAM/ext4 rename/link, dirfds, sticky checks and search checks for naming; retained renamed directory identity and mount identity | Symlink traversal, detached-directory relative lookup, full permissions for every API, general mount namespaces, filesystem crash transactions |
| [Credentials](../../../ObfuscationKernel/include/ok/user/user.hpp) | Real/effective uid/gid and a kernel-space flag | Saved IDs, supplementary groups, complete set-ID exec/permission rules |
| [okcrt](../../lib/okcrt/src/syscalls.c), [errno](../../lib/okcrt/src/errno.c), [types](../../sdk/include/sys/types.h), [stat](../../sdk/include/sys/stat.h) | Small project wrappers, global errno, word-sized off_t/time_t, stat translation with overflow checks and missing inode/time information | musl ABI, per-thread errno, large-file/time64 support, libc completeness |
| [oksh](../../apps/oksh/main.c), [commands](../../apps/lib/commands.c) | Basic whitespace splitting, one two-command pipeline, fork/exec/wait, a few builtins and external tools | POSIX shell grammar, quoting/expansion/redirection, job control, complete utilities |
| [SDK validator](../../tools/kernel_sdk.py), [build profiles](../../xmake/arch.lua) | Ten explicit triples; SDK ABI 3, hashes, compiler identity and mode validation | A musl toolchain/sysroot qualification or a versioned Linux-personality contract |

The existing [native acceptance program](../../apps/posix-check/main.c),
[process-resource models](../../../ObfuscationKernel/tests/host/process_resource_tests.cpp),
[native architecture probes](../../../ObfuscationKernel/tests/native/),
[namespace tests](../../../ObfuscationKernel/tests/host/vfs_namespace_tests.cpp),
and [persistent ext4 runner](../../scripts/test_persistent_ext4.py) are useful
regressions to preserve. Their current pass results are not repeated or extended
by this planning audit. No musl execution has been established here.

## 3. Standards target and evidence ledger — P00, P16

### 3.1 Target, declarations and certification

Target the mandatory requirements of **POSIX.1-2024 / The Open Group Base
Specifications Issue 8**, including Base Definitions, System Interfaces, and
Shell and Utilities, plus an explicitly enumerated XSI and realtime option set.
The official specification entry point is
[Issue 8](https://pubs.opengroup.org/onlinepubs/9799919799/). It is a normative
reference for implementation work, not a claim that every clause was audited in
this session. Resolve corrigenda and the exact publication revision in P00.

Maintain separate labels for: implemented API, tested behavior, declared option,
profile-qualified release, and externally certified product/configuration. A
certificate requires the applicable certification program, licensed/accepted
suite, required submissions and permitted branding. The applicable Issue-8-era
certification program and suite availability were **not verified** in this audit.
Do not call the OS certified, UNIX-branded, or completely conformant on the basis
of musl, a self-authored test suite, or one QEMU configuration.

Do not import an Issue 7 optional/mandatory list unchanged. Some feature groups
and declarations have changed between editions. P00 must classify every
interface and option directly against the selected Issue 8 text. The planning
matrix below groups work; it is not a substitute for that clause-level inventory.

The planned workstation profile selects XSI facilities, including applicable
System V IPC interfaces, and these realtime/thread facilities: realtime
signals/timers, process/thread CPU clocks, priority scheduling, memory locking,
asynchronous I/O, message queues, semaphores, shared-memory objects, thread
process sharing, robust mutexes, priority inheritance and priority protection.
These are product requirements, whether Issue 8 classifies them as mandatory or
optional. P00 maps each facility to its exact Issue 8 option name, dependencies
and applicability; this list does not invent macro values. Other optional
facilities need an explicit include/exclude entry in the ledger. Removing a
selected facility requires a visible product-profile revision, not an
implementation-side ENOSYS exception. Hardware SMP is an engineering goal,
not a POSIX conformance requirement by itself.

### 3.2 Required inventory schema

Create a machine-readable ledger in later work with one row per interface or
normative utility/behavior, not just one row per syscall. Suggested fields:

```
requirement_id: P08.openat.search-components
edition: POSIX.1-2024
normative_clause: <verified section and URL>
classification: mandatory | selected-option | extension | out-of-profile
option_group: <exact normative name, if any>
interface: openat
kernel_mechanism: VFS path walk
libc_entry: musl openat wrapper
owner: Kernel | OS | joint
architecture_abi: <all ten qualified tuples or explicit blockers>
state: planned | model-only | native-partial | implemented | verified | not-applicable-with-rationale
feature_test_macro: <header visibility control>
compile_time_option_macro: <value or undefined, with normative rule>
runtime_query: <sysconf/pathconf/confstr selector and result rule>
limits: <minimum, configured value, runtime behavior>
error_and_signal_rules: <errno, EINTR/restart, cancellation>
tests: <model, hardware, userland, fault/concurrency, conformance evidence>
remaining_deviation: <reason, owner, closing gate; empty only when satisfied>
```

These fields extend the main plan's canonical requirement/evidence schema;
`state` uses the same values. Qualification is an additional release/profile
gate, not another implementation state. A ledger entry needs both the canonical
fields and the POSIX-specific fields above.

Separate feature-test selectors such as `_POSIX_C_SOURCE`, `_XOPEN_SOURCE` and
extension switches from capability macros such as `_POSIX_THREADS` and runtime
`sysconf` answers. Do not advertise `_POSIX_VERSION` or an option as complete
before its required behavior is qualified. Use the selected standard's exact
macro values and undefined/-1/0/positive rules; `sysconf` returning an indefinite
limit must leave errno as required. Avoid hard-coded success for unsupported
`rseq`, signals, futexes or model resource counts. Unknown Linux extensions should
return ENOSYS only where that is the defined unsupported syscall behavior;
recognized operations/flags need the documented EINVAL/ENOTSUP/other error.

### 3.3 API-family coverage matrix

Each row requires detailed ledger entries, exported headers and user-observable
semantics. "Absent" below means absent from the running native contract, even if
there is a model or enum. Standards classification remains subject to P00.

| Family and representative interfaces | Current native baseline | Planned owner/work | Required acceptance beyond linking |
| --- | --- | --- | --- |
| C/POSIX libc, stdio, allocation, math, errno, environment | Minimal shim; no general allocator; global errno | OS L00/L01; Kernel P02/P03 | locale-aware conversions, stream errors/locking, malloc overflow/OOM, floating ABI and thread-local errno |
| File/descriptor I/O: openat, read/write, preadv/pwritev variants, dup, fcntl locks, fsync | Bounded subset; shared offsets; no record-lock completeness | Kernel P08; OS L01 | partial transfer/EINTR, append atomicity, lock ownership/deadlock, close/exec races, durability |
| Names/metadata: stat variants, chmod/chown, symlink/readlink, link/rename, directories | RAM/ext4 subset; restricted paths/linkat flags; incomplete metadata | Kernel P08/P09 | all component permissions, symlink limits, timestamps/inodes, dirfd identity and detached directory behavior |
| VM: mmap/munmap/mprotect, brk, msync, mlock, shared/private mappings | Native absent; record models only | Kernel P02/P03/P13 | actual faults and protections, split/unmap races, shared visibility, COW and SIGBUS |
| Process lifecycle: fork/exec/wait, posix_spawn, exit/_Exit, atfork | Static single-thread fork/exec/wait | Kernel P09; OS L03/L05 | exec commit/rollback, multithread fork, inherited state, zombies and wait events |
| Threads: pthread create/join/detach, attributes, keys, once, rwlocks, barriers, spinlocks | No native clone/threads | Kernel P04/P05/P07; OS L03 | N:M identity not invented; genuine scheduled threads, TLS/destructors, stack guards and cancellation |
| Signals: sigaction/masks, sigwait, kill, pthread_kill, realtime queues, altstack | Terminal fault status only; model no-op handlers | Kernel P06/P09; OS L03 | architecture signal frame/return, targeting, masks, restart and async-signal-safe paths |
| Thread synchronization: mutex/condvar, robust/process-shared, priority protocols | No native futex | Kernel P07/P13; OS L03 | lost-wakeup stress, owner death, shared-address aliasing, priority inversion and recovery |
| Clocks/timers/sleeps: clock_gettime, nanosleep, timer_*, timed waits | Tick-derived clock reads only | Kernel P04/P06/P13; OS L01/L03 | idle advancement, time64 rollover, monotonic deadlines, clock adjustment, overrun accounting |
| Readiness: poll, select, pselect, ppoll; epoll as Linux extension if elected | Native absent | Kernel P04/P08; OS L01 | atomic mask-and-wait, close/reuse races, EOF/HUP/ERR and timeout accuracy |
| Terminal control: termios, tc*, ttyname, PTYs, controlling terminal | Serial byte stream; no native ioctl | Kernel P10; OS L05 | canonical/raw I/O, line discipline, foreground group, stop/continue, hangup and winsize |
| Identity/process control: set*id, groups, setsid/setpgid, getpgrp, rlimits, umask | Read IDs, umask and limited limits | Kernel P09/P15; OS L06 | saved/supplementary IDs, set-ID exec, groups, resource enforcement and secure loader policy |
| Pipes/FIFOs and IPC: shm_open, mmap sharing, sem_*, mq_* | Anonymous bounded pipes only | Kernel P08/P11; OS L03/L06 | FIFO open rules, unlink lifetime, process sharing, queue priority/notification and interruption |
| XSI/System V IPC: shm*, sem*, msg* families as required by elected profile | Absent | Kernel P11; OS L06 | IPC IDs/reuse, permission rules, SEM_UNDO, removal wakeups and accounting |
| Async I/O and realtime: aio_*, lio_listio, sched_*, priority ceilings/inheritance | Absent | Kernel P13; OS L03 | completion once, signal delivery, cancellation outcomes, bounded resources, scheduler behavior |
| Sockets/network: socket/connect/accept/send/recv, ancillary data, name resolution | Native absent; separate models are not a network stack | Kernel P12; OS L06 | AF_UNIX first, TCP/UDP, nonblocking readiness, credentials/SCM_RIGHTS, DNS and byte order |
| Locales/internationalization: setlocale/uselocale, wchar/multibyte, strcoll/strftime | Not supplied by shim | OS L04 | C and declared locales, concurrent locale state, encodings/collation and invalid sequences |
| Regex/glob/fnmatch/wordexp, catalogs | Not supplied by shim | OS L04/L05 | standard matching/escaping, locale rules, safe shell expansion; catgets where required |
| Dynamic loading: dlopen/dlsym/dlclose and ELF interpreter as required/elected | ET_EXEC gate with static fixtures; interpreter not implemented | Kernel P03/P05/P09; OS L02 | actual relocations/TLS, constructor order, unload/lifetime, secure path handling |
| Shell command language | One simple pipeline and whitespace parsing | OS L05 | complete Issue 8 grammar, expansions, redirections, traps, subshells, exit statuses and jobs |
| Utilities and execution environment | Small custom utilities | OS L05/L06 | every mandatory/elected utility, options/output/locale, shell scripts and filesystem environment |
| Administration/bootstrap/build interfaces selected by the standard | No complete distribution contract | OS L05/L06/L07 | paths, environment, getconf, tools and required development interfaces; explicit option decisions |

`gettext` is a separate GNU ecosystem API/data/tooling concern, not a replacement
for the normative locale or XSI message-catalog interfaces. Installing gettext
must not be counted as satisfying `setlocale`, collation, `catgets`, regex or
Shell and Utilities requirements.

## 4. ABI and architecture qualification — P01, L00

### 4.1 Recommended direction

Add a versioned, per-architecture **Linux userspace syscall personality** over
common Kernel semantic operations, and target musl's matching Linux ABI. Keep the
existing Obfuscation ABI for old okcrt binaries until a deliberate retirement
policy is adopted. Do not renumber the existing global enum and reinterpret
old executables. Numeric collision is real: other architectures assign the same
numbers to different calls. Matching an instruction such as `svc`, `ecall` or
`syscall` is not personality detection.

Select personality at exec from validated, build-controlled ELF metadata and
package policy. A proposed `OBFUSCATION` ELF note can name `legacy-ok-0.1` or a
qualified Linux ABI tuple/version. Reserve its format before use. Dynamic
interpreter names can corroborate selection but do not make an unmarked static
ELF unambiguous. Retain an explicit legacy default only for existing trusted
legacy packages; reject ambiguous foreign images with ENOEXEC. Fork inherits the
personality; successful exec atomically installs the new one; all threads sharing
an address space use one personality. Never probe several syscall tables until
one returns success. The current [linker script](../../lib/okcrt/user.ld)
discards `.note.*`; any note-based design therefore needs a new musl link path
and an explicit legacy policy, not a note that the build silently removes.

Use architecture-selected ABI codecs to decode raw arguments into width-stable
Kernel request types, marshal user structures, map internal errors, and encode
returns. Keep signal-frame and TLS codecs beside those architecture policies.
One semantic `rename`, `mmap` or `wait` implementation should serve both
personalities; layout translation must not leak into VFS/scheduler algorithms.
The Linux personality's numeric errno and flag values also need per-ABI audit,
particularly MIPS. A name such as EOVERFLOW must not imply a universal number.

The alternative, patching all of musl to the current common project ABI, creates
long-lived changes in syscall numbers, signal trampolines, clone, TLS, time64,
structure definitions and the loader. It reduces neither the required Kernel
semantics nor the conformance work. Keep it as a documented fallback for an
unqualified CPU ABI, not the default strategy. Linux userspace compatibility
still does not mean all Linux syscalls, Linux kernel modules, or arbitrary glibc
binaries will run.

### 4.2 Ten-profile qualification matrix

Current build policy is in [OS architecture definitions](../../xmake/arch.lua)
and [Kernel architecture definitions](../../../ObfuscationKernel/xmake/arch.lua).
The proposed Linux/musl ABI column is a **qualification target**, not a verified
upstream support claim. Pinning source and probing compiler defaults is L00.

| Existing profile / retained platform | Current form | Linux/musl qualification target and special work |
| --- | --- | --- |
| i386 / QEMU modern 32-bit CPU with PAE/NX/FXSR | ELF32 LE, i386-elf, `-m32`, project numbers | Linux i386 ABI; int80 arguments/results, set_thread_area/TLS descriptor rules, 64-bit syscall pairs and legacy/time64 calls; never call this original 80386 support |
| x86_64 / existing PC profile | ELF64 LE, x86_64-elf, no red zone | Linux x86_64 LP64, syscall clobbers and FS TLS; x32 is a separate ABI and not silently included |
| aarch64 / QEMU virt cortex-a57 | ELF64 LE, aarch64-elf; current general-regs-only build policy | Linux AArch64 LP64, x8/x0..x5, TPIDR_EL0, AArch64 signal context; ordinary musl FP/SIMD use must be qualified beyond current compiler restrictions |
| arm32 / QEMU virt cortex-a15 | ELF32 LE, arm-none-eabi, ARMv7 ARM mode; existing artifact EABI5 soft-float | Linux ARM EABI; explicitly select soft/softfp/hard-float and matching musl/toolchain, r7 syscall ABI, EABI 64-bit alignment, TLS setup syscall/helper conventions, ARM/Thumb interworking and signal restorer |
| rv64 / existing QEMU virt CPU | ELF64 LE, riscv64-elf, medany policy; existing artifact RVC/double-float | Linux RISC-V LP64 variant pinned explicitly instead of relying on compiler defaults, a7/a0..a5, tp, atomics/cache synchronization and ELF flags |
| rv32 / existing QEMU virt CPU | ELF32 LE, riscv32-elf, medany policy; existing artifact RVC/double-float | Linux RISC-V ILP32 variant; pinned musl RV32 port/time64 and 64-bit argument-pair requirements must be verified; retain profile if upstream qualification is blocked |
| loongarch64 / existing QEMU virt CPU | ELF64 LE, loongarch64-elf, SIMD disabled; existing artifact double-float OBJ-v1 | Linux LoongArch LP64 variant; pinned musl port, FP ABI, r2 TLS, relocation and signal-frame support must be verified; no LSX/LASX claim from disabled SIMD |
| mips / Malta 24Kf | ELF32 BE, O32 hard-float artifact, mips32r2; project six-register syscall ABI | Linux MIPS O32: architecture numbers, stack-carried later syscall arguments, a3 error flag, 64-bit pair/alignment and endian rules, FP ABI, MIPS ELF ABI flags; preserve RI-emulated rdhwr TLS on CPU without UserLocal |
| mips64 / Malta MIPS64R2-generic | ELF64 BE, n64 hard-float artifact, mips64r2 | Linux MIPS n64, not n32; architecture numbers/error flag, GP/GOT/PIC, ABI flags/FP/TLS and loader relocations; preserve CPU and KSEG/DMA policy |
| ppc / ppce500 e500v2 | ELF32 BE, powerpc-eabi, `-msoft-float -msdata=none`; SPE-capable CPU | Linux 32-bit PowerPC ABI plus verified soft-float toolchain fit; CR0.SO error convention, r2 TLS, signal/atomic behavior and ELF relocations. SPE CPU state does not imply an SPE floating-point ABI. Generic powerpc port existence does not prove this retained CPU works; no classic FPU or PPC64 substitution |

Artifact observations above come from read-only `readelf` inspection of existing
`hello.elf` outputs, not fresh builds or musl qualification. Several source
profiles rely on compiler defaults for their FP ABI. L00 must make those choices
explicit and verify rebuilt outputs, including C argument passing and long double.

For each tuple, record endianness, pointer/long/size_t/off_t/time_t widths,
long-double representation, stack alignment, argument registers, stack argument
locations, syscall restart PC, error flag/register, TLS convention, atomic ISA,
FP/SIMD register set, ELF class/machine/e_flags, interpreter pathname and relevant
hardware capabilities. Require byte-for-byte golden fixtures for stat/statx,
timespec/timeval, sigaction/sigset/siginfo/ucontext, iovec/msghdr, rlimit/rusage,
termios and IPC control structures. Packed casts to current C++ types are not
an ABI implementation; reserved bytes must be initialized and overflow rejected.

MIPS O32 currently places arguments five/six in t0/t1 and returns signed v0;
PPC currently returns signed r3 without Linux CR0.SO. See
[MIPS wrappers](../../lib/okcrt/arch/mips/syscall.S),
[PPC wrappers](../../lib/okcrt/arch/ppc/syscall.S), and
[MIPS execution notes](../../../ObfuscationKernel/docs/arch/mips-native.md).
These are concrete incompatibilities, not just different syscall numbers.

The read-only ABI audit also compared local Linux 6.13.4 UAPI/entry sources:
`arch/mips/kernel/scall32-o32.S`, `arch/mips/include/uapi/asm/{unistd,errno}.h`,
`arch/powerpc/include/asm/syscall.h` and `include/uapi/asm-generic/{unistd,fcntl}.h`.
For example, Linux MIPS O32/n64 number bases are 4000/5000, and its ENOSYS and
EOVERFLOW values are 89/79 rather than this project's 38/75. Even x86_64's matching
number/register scheme is insufficient: current `OK_O_APPEND` is 0x8, while the
generic Linux flag is 0x400. M0 must pin and archive the chosen Linux UAPI source
as reproducible evidence; the developer's local comparison tree is not a build
dependency.

MIPS's retained CPUs cannot enforce NX on readable data; LoongArch's existing
notes limit its emulator NX evidence. Record protection guarantees per CPU and
separate software W^X admission policy from hardware execute denial. Review any
policy that rejects a standards-required protection combination against P00;
do not silently label a security restriction POSIX-conformant or change the CPU
matrix to hide a limitation.

### 4.3 musl version and supply-chain qualification

No upstream musl source was present in the audited OS paths, and no release,
port table, patches or build was verified in this task. **The exact musl version
is an M0/L00 decision; this plan does not guess the current release or claim
support for a retained CPU from a generic architecture name.** L00 must choose
a maintained release after checking the official
[release site](https://musl.libc.org/) and
[source repository](https://git.musl-libc.org/cgit/musl/), record the exact
archive/commit, checksum/signature verification, license and patches, then
freeze it for the qualification matrix. If another version is selected, preserve
these requirements and rerun all affected evidence.

Inspect that exact tree's `arch/*`, syscall headers, `bits/alltypes.h.in`,
`pthread_arch.h`, `reloc.h`, crt, clone, cancellation and signal-return assembly,
and dynamic linker. Record required compiler/assembler/linker versions and
hardware instruction assumptions. The chosen release's 64-bit time behavior,
32-bit large-file policy, each port's availability, PowerPC e500v2 soft-float fit,
MIPS FP/TLS details, RV32 and LoongArch support, locale coverage and priority-mutex
support are **external facts to verify against the pin**, not assumptions
licensed by this document. Upstream support for Linux does not prove support for
our Linux personality or its implemented syscall subset.

Use separate sysroots keyed by architecture, ABI tuple, libc version and mode.
Do not mix current `sdk/include/sys/types.h`, okcrt startup objects, musl headers,
or host headers. Preserve SDK compiler identity requirements for **Kernel C++
extensions** separately from the userland C toolchain contract. A Linux-targeted
musl user compiler need not masquerade as the existing bare-metal SDK compiler.
Capture both identities in reproducible build manifests. xmake remains the
project entry point; an xmake-owned, pinned upstream-musl build step may invoke
upstream build machinery, with explicit inputs/outputs, isolated directories and
no network-dependent fallback. Decide and document this integration before
adding targets. Do not rewrite upstream libc build rules without a demonstrated
need.

## 5. Kernel foundations and detailed semantics

### P02 — physical and object allocation

Replace the runtime's static user-page pool with one ownership-accounted physical
allocator fed by validated boot memory maps. Reserve Kernel image, page tables,
boot objects, firmware/device apertures, DMA and modules before making frames
available. Track page order, reference/pin counts, use type, NUMA node if later
supported, and zeroing policy; do not equate a physical frame number with a
currently mapped C++ pointer on MIPS or high-memory platforms.

Provide an explicit `Result<OwnedPages>` interface and fallible Kernel object
allocation after P00. Separate nonblocking/IRQ-safe preallocated requests from
sleepable allocations. Define reclaim/OOM policy and per-process/global quotas;
allocation failure must roll back partially created VMAs, PTEs, threads and file
objects. No panic on an ordinary user-induced ENOMEM. Bootstrapping allocators
must have an explicit handoff and cannot free reserved pages into the main pool.
Use stable referenced objects/handles; the current compacting process arrays
must not invalidate references held by another CPU or a sleeping syscall.

Acceptance: exhaustion and allocation failure at every stage of fork/exec/map;
zero-fill across ownership changes; reference/pin underflow detection; reserve
region rejection; concurrent allocate/free; Kernel and OS images still fit their
boot loaders. Prove no double ownership or data exposure using physical pages,
not metadata-only frame models.

### P03 — one native VM and guarded user access

Unify semantic VMA state with native page tables through architecture-selected
map/unmap/protect/invalidate operations. VMAs own anonymous/file/shared objects,
permissions, offsets, inheritance and accounting. Process identity is distinct
from an address-space object; threads share the latter by reference. Replace
fixed 128-page lists with bounded-by-policy allocation and interval operations.

Implement anonymous private mappings first, then file-backed private/shared
mappings and COW. Validate size/address/offset arithmetic before alignment; honor
hint versus MAP_FIXED semantics, MAP_FIXED_NOREPLACE where supported, page/offset
alignment and collision rules. Split VMAs on partial munmap/mprotect; handle holes
and PROT_NONE correctly. Linux brk failure returns the unchanged break to musl,
not a generic negative errno; libc applies its public contract. File mapping
lifetimes must survive fd close/unlink, zero the last partial page, and deliver
SIGBUS for access beyond the valid file-backed range when required. Specify
truncate-versus-fault and msync/fsync writeback ordering before enabling shared
writable mappings. Avoid holding a spinlock across storage I/O.

A mapping update must publish or roll back metadata/PTE changes coherently.
Unmapping does not free frames until local/remote TLB invalidation and outstanding
user copies/DMA pins are complete. COW needs atomic page-reference decisions,
copy allocation failure behavior, permission restoration and TLB synchronization;
keep eager-copy fork as a correct initial implementation. Add stack guards and
bounded growth; define user VA layouts per existing platform without blindly
reusing the current AArch64/RISC-V/x86 ranges for a Linux-targeted toolchain.

Copy helpers must become fault-recoverable operations against a referenced
address space, not a validation-then-dereference race. Validate whole small
control arrays/strings into Kernel-owned buffers; stream large payloads with
precisely defined partial progress. Freeze scalar arguments and copied structures
across blocking waits. Distinguish a fault before any externally visible effect
from a later short transfer; do not replay a completed write after a signal.
Test simultaneous munmap/mprotect/exec, crossing page boundaries, integer wrap,
unaligned fields, readonly destinations and stale shared-memory addresses.

### P04 — wait protocol, readiness and real clocks

Create typed wait queues with a single state transition among runnable, waiting,
woken, timed-out, interrupted and exiting. Testing a condition and publishing a
waiter must be atomic under the condition's lock; wakeup rechecks predicates and
cannot be lost between those steps. Completion ownership is singular when timer,
signal, I/O and close race. Sleep without holding a spinlock; establish lock ranks
for process, file, inode, VM, futex and run queues, and separate IRQ-safe locks
from sleeping locks. Do not use repeatedly rerunning a syscall from scratch as
the general blocking protocol.

poll/select/ppoll/pselect need descriptor references held during registration,
readiness generation checks, subscribe-then-recheck, proper EOF/HUP/ERR behavior,
and no notification to a new object that reused a closed fd. The temporary
signal-mask change in ppoll/pselect and the wait must be atomic relative to signal
delivery. pipe2 flags are installed before descriptor publication. Preserve
PIPE_BUF atomic writes, nonblocking EAGAIN, EOF and SIGPIPE/EPIPE semantics; pipe
capacity is not itself a standards declaration of PIPE_BUF.

Use calibrated per-platform clocks that advance during idle and Kernel work.
Separate monotonic, realtime, process and thread CPU clocks. Define epoch source,
frequency conversion, overflow, settime privileges and realtime adjustment;
absolute monotonic deadlines must not move when realtime changes. Timer queues
must safely cancel on thread/process exit. nanosleep/clock_nanosleep need actual
blocking, EINTR and remaining-time/absolute-time behavior. rlimits/sysinfo must
report and enforce real accounting, not current model constants.

### P05 — runnable threads, TLS and clone

Make native dispatch select runnable **threads**, each with a Kernel stack,
complete register frame, TLS, signal mask, cancellation-related state and wait
record. Distinguish pid/tgid/tid and shared versus per-thread objects. Decode the
exact selected architecture's clone argument order/stack rules; implement a
specified supported flag set with consistent sharing of VM, files, cwd and signal
dispositions. Reject contradictory flags before publishing a child. Install TLS
and parent/child TID stores at the documented points, with complete rollback if
copies or allocation fail. Provide Linux set_tid_address and clear-child-tid
store plus futex wake on thread exit; do not let a freed TID address access
unmapped or another process's memory.

Wire native TLS syscalls/clone TLS to the **actual saved frame and hardware
thread pointer**, not only `ThreadLocalState`. x86_64 FS base, i386 descriptors,
ARM TLS conventions, AArch64 TPIDR_EL0, RISC-V tp, LoongArch r2, MIPS rdhwr and PPC
r2 require separate verified policies. TLS block layout, alignment, TCB bias,
DTV, `.tdata/.tbss`, static/dynamic TLS and errno storage must match the pinned
musl port. Preserve existing MIPS delay-slot/TLS emulation and PPC SPE context.
Block unsupported instruction extensions explicitly; do not rely on the current
512-byte generic FP storage to cover future vector state.

The current native whitelist has no TLS-install syscall case; unlisted calls
return ENOSYS, and the POSIX model's arch_prctl does not update `native_frame`.
Some architectures let userspace set its thread pointer directly, but that does
not remove their TCB/PT_TLS/clone/signal-restoration obligations. Qualify the
minimal single-thread TLS path early; full thread lifecycle follows separately.

A thread exit must release thread resources without closing shared process files
or destroying another thread's VM. exit_group kills the whole group and waits
for safe teardown. exec by a nonleader must quiesce siblings, install one new
thread image, and handle leader/TID rules consistently with the selected Linux
ABI. A successful exec never returns; failure preserves the caller's old image.

### P06 — signals, interruption and cancellation support

Implement process-wide dispositions, per-thread masks/pending queues, process
pending queues, targeting rules and realtime FIFO ordering with queue limits.
SIGKILL/SIGSTOP cannot be caught or blocked; job-control stop/continue and child
state changes must wake waiters. Define synchronous fault signals and siginfo
addresses/codes instead of translating every trap to an indistinguishable exit.
Deliver at safe user-return points; interrupted waits must resolve exactly once.

Build architecture-specific sigaction, sigset, siginfo, ucontext and signal-stack
frames including FP/TLS state and restorer requirements. sigreturn is an untrusted
input boundary: check user ranges, canonical addresses, privilege flags, segment
selectors, signal masks and reserved state before restoring execution. Support
sigaltstack, nested signals and guard-page failures. Preserve masks/ignored
signals and reset caught dispositions/alternate stacks on exec according to the
chosen contracts. Fork does not inherit pending signals as pending work.

Define internal restart results and the user ABI behavior of SA_RESTART,
nonrestartable calls, short I/O and timeout recomputation. musl cancellation uses
implementation-specific assembly and reserved signals; qualify those against
the pinned source rather than exposing Kernel-specific cancellation primitives.
Deferred cancellation must work at required cancellation points without leaking
locks, fd reservations or partially published objects. pthread cleanup handlers,
TSD destructors and cancellation-disabled regions belong in libc; the Kernel
must provide dependable signal/wait/exit semantics. Async cancellation is only
promised to the extent required and implemented by the selected libc contract.

### P07 — futexes, robust and process-shared synchronization

Start with correct WAIT/WAKE and PRIVATE/shared keys, then add WAIT_BITSET and
REQUEUE/CMP_REQUEUE or other operations demonstrated by the pinned musl paths.
A private key is address-space identity plus address; a shared key is backing
object/page/offset, so different VAs in different processes synchronize on the
same object. A reused VA, unmapped page or recycled object must not inherit a
previous waiter's key. Define pin/ref lifetime and unmap/exit interactions.

Check 32-bit alignment and atomically compare the user value while publishing the
waiter under the futex bucket protocol. Mismatch returns EAGAIN; timeout,
interruption and bad user memory have distinct outcomes. Return the actual number
woken. Acquire/release behavior must work on ARM, RISC-V, MIPS, PPC and LoongArch,
not merely x86; blocking locks must never busy-wait with interrupts disabled.

Implement the exact robust-list ABI, bounded/cycle-safe exit traversal, pending
operation handling, FUTEX_OWNER_DIED and wakeup. A bad robust-list pointer must
not prevent process teardown or damage another address space. Exercise a killed
owner while acquiring, holding and releasing a mutex. libc must expose
EOWNERDEAD/ENOTRECOVERABLE and `pthread_mutex_consistent` correctly. Process-shared
mutexes/condition variables and semaphores require real shared mappings, not
shared virtual addresses. Cancellation during condvar handoff must not consume
another waiter's notification or leave the associated mutex permanently locked.

If priority inheritance/protection is part of P00's declared profile, implement
and test it end to end: owner TID tracking, transitive donation, timeout/deboost,
owner death, deadlock detection, ceilings and scheduler enforcement. A normal
WAIT/WAKE futex is not a PI futex. If pinned musl lacks a required protocol,
L00/L03 must provide a reviewed implementation or record a release blocker;
returning ENOTSUP cannot satisfy a declared option.

### P08 — VFS and open-file semantics

Move path traversal to retained `(mount, dentry/inode)` references rather than
reconstructing strings for every relative operation. Keep parent traversal and
mount crossings explicit; handle symlinks with a bounded expansion count and
flags such as no-follow/empty-path only where the ABI specifies them. Search
permissions must apply to all required components for every syscall, without
rechecking ancestors above an already held cwd/dirfd. Retained detached
references must never resolve to replacement paths. Use per-directory/inode
locking and a documented cross-directory rename lock order; permission checks
and mutation must share a stable lookup result under concurrency.

Complete stable inode/device IDs, 64-bit sizes/offsets, timestamps and nanosecond
rounding, chmod/chown/setgid/sticky rules, supplementary-group checks, links,
FIFO/device/socket nodes and mount-aware errors. Add descriptor status versus
per-fd flags, O_APPEND atomicity, O_NONBLOCK, O_CLOEXEC publication, fcntl byte-range
locks, close semantics and cancellation interactions. Avoid silently translating
EINTR after close into a retry against a reused fd. Specify seek/pwrite behavior
for each personality where project semantics and Linux behavior differ.

The public POSIX `pwrite` contract honors the supplied offset even on an
O_APPEND descriptor and leaves the open-description offset unchanged. Linux's
append-on-pwrite behavior must not silently leak through the musl personality.
Use an explicitly documented POSIX-correct kernel operation or a reviewed libc
adapter; do not temporarily clear a shared O_APPEND flag around a write. Record
this as a deliberate Linux-compatibility difference and test shared descriptors,
concurrent append/pwrite and unchanged seek offsets. Define the project's pwritev
semantics consistently; Linux-specific pwritev2 flags need their own separately
documented contract.

The current ext4 writer is deliberately bounded/nonjournalled. POSIX name
operation atomic visibility under concurrency and crash persistence are distinct
requirements; build namespace transactions/rollback before advertising concurrent
atomic rename, and retain the existing sticky I/O-failure quarantine and offline
recovery rule until a separately validated persistence mechanism replaces it.
Tests need syscall observers, held descriptors, mount aliases, I/O faults and
reboot/fsck evidence, not merely a clean success path.

### P09 — processes, credentials and exec

Define reference-counted process/thread group objects, stable PID/TID generations,
parent/child relationships, process groups, sessions and wait-event consumption.
Support waitpid/waitid/selected Linux wait forms for exit, stop and continue;
prevent double reaping and PID-reuse signal delivery. Child reparenting and
subreaper/init policy must be explicit. Separate thread exit from process exit.

Fork duplicates process state and shared open descriptions while a multithreaded
parent yields a child with only the calling thread. Define which locks are
reinitialized in the child and the libc atfork protocol. Preserve or reset
credentials, masks, pending signals, timers, robust state, resource limits and
CPU accounting according to each operation, not by copying an entire mutable
C++ resource struct. vfork is not a required shortcut: keep it unsupported until
its parent-suspension/child restrictions are implemented; qualify musl/posix_spawn
fallbacks or provide a correct implementation if required by the pinned path.

Exec resolves relative paths through the held cwd and validates search/execute
permissions; the current runtime's direct VFS lookup must be replaced. Support
shebang scripts, argv/env limits and failure cleanup, with loop and interpreter
limits. Stage ELF, interpreter, stacks, TLS metadata, credentials and close-on-exec
changes before the commit point. Sibling teardown, signal reset, new ABI
personality and address space become visible together. Audit errors after commit
and do not return to a half-destroyed old image.

Add saved IDs, supplementary groups, set*id restrictions, effective/real access
checks, set-ID file transitions and group inheritance. Kernel-space credentials
must never be copied from a user-controlled structure. Provide resource limits
with defined units and enforcement. Establish secure-exec behavior and AT_SECURE
before allowing set-ID dynamic binaries; sanitize loader environment and defend
against interpreter/library pathname substitution. Prefer disabling set-ID
execution explicitly until this gate passes.

### P10 — terminal and job-control model

Turn serial/PTY endpoints into referenced TTY devices with input/output queues,
termios state, canonical editing, echo, signals, flow control, raw/noncanonical
VMIN/VTIME rules and drain/flush behavior. ioctl numbers/layouts belong to the
personality codec. A terminal owns a controlling session and foreground process
group; implement setsid, controlling-TTY acquisition/release, tcsetpgrp/tcgetpgrp,
SIGTTIN/SIGTTOU/SIGTSTP, SIGCONT, SIGWINCH and hangup behavior. Distinguish serial
console, desktop input and PTY sessions so GUI typing cannot execute shell input.

The OS supplies login/session policy, PTY clients and the shell job table. Test
multi-stage foreground/background pipelines, Ctrl-C/Z, resumed jobs, blocked
background reads, orphan groups, terminal exit/hangup and simultaneous sessions.
EOF on an input queue is a device/session state, not an empty polling result.

### P11 — shared memory, semaphores, queues and XSI IPC

POSIX shm objects require namespace, permissions, unlink lifetime, ftruncate and
shared mappings. Named semaphores and message queues need referenced objects,
O_CREAT/O_EXCL races, priorities/capacity limits, unlink-while-open semantics,
timeouts, signals and process exit cleanup. `mq_notify` registration/one-shot
notification must race correctly with receive and close. Unnamed process-shared
semaphores build on P03/P07; they are not implemented by a process-local counter.

For elected XSI/System V IPC, define ID generation/reuse, IPC_PRIVATE/key lookup,
permission/control layouts, attach/detach, IPC_RMID wakeup, queue accounting and
SEM_UNDO limits and exit behavior. Include 32/64-bit time fields and endian
translation. Shared pages survive the appropriate process and fd lifetimes;
reclamation occurs only after the final mapping/reference ends.

### P12 — socket and resolver boundary

Implement AF_UNIX stream/datagram semantics first to support local services,
including peer credentials, ancillary-data bounds and SCM_RIGHTS lifetime. Then
add actual IP sockets and platform-independent networking mechanisms; existing
network or Linux-driver models do not establish this. Implement nonblocking
connect/accept, poll readiness, shutdown/half-close, SO_ERROR, SIGPIPE suppression
where specified, timeouts and orderly process exit. Check accept/exec and
received-fd CLOEXEC races. Cross-endian network byte order is independent of the
host structure ABI.

DNS, `/etc/hosts`, passwd/group lookup, service databases and resolver policy are
OS/libc integration. Do not assume glibc NSS modules load in musl. Select and test
a configuration model, IPv4/IPv6 behavior, resolver concurrency, cancellation and
failure limits; keep packet I/O mechanisms in Kernel or authorized driver services.

### P13 — declared realtime facilities and AIO

Implement the elected scheduler policies/priorities and privilege/rlimit checks
with actual scheduling effects, not stored attributes. CPU affinity and topology
are Linux extensions to qualify separately. Provide priority inheritance/ceilings
as required by P07 and the option inventory. Memory-locking must pin real pages
and enforce quotas, including fork/exec rules; it is not a successful no-op.

POSIX AIO may use a qualified libc worker design if permitted by the selected
contracts; it need not imply a Linux-specific async syscall. Whichever layer
owns it, ensure each request has one completion, referenced fd/data lifetime,
correct aio_error/aio_return, list I/O, cancellation outcomes, signal/thread
notification and process exit cleanup. Test close/reuse, cancellation concurrent
with completion, queue exhaustion and short/error I/O. Realtime timers require
chosen notification modes, overrun accounting, clock selection and delivery
through P06/P04. Hard realtime latency guarantees require separate measured
budgets and hardware evidence; option support alone is not a latency guarantee.

### P14 — hardware SMP gate

Uniprocessor preemptive pthreads are a legitimate first stage, but must not be
reported as SMP. Add AP startup, per-CPU stacks/run queues/idle state, timer and
IPI delivery, cross-CPU rescheduling and TLB shootdown using architecture-specific
static backends. Start with coarse correct ownership rules; optimize only with
measurements. Define address-space active-CPU masks and shootdown acknowledgement
before freeing page tables or frames. Refcount zero and reclamation require a
specified grace/pin protocol, not a relaxed atomic decrement followed by free.

Audit global runtime buffers, current-PID/TID access, global errno replacements,
process table compaction, console queues, file offsets, VFS mutation, ext4 and the
single-queue polling driver before enabling parallel syscalls. Scope driver
serialization and DMA lifetimes explicitly. Test migration while using TLS,
signals, COW, futex and shared fd offsets. Every claimed SMP profile needs real
multiple-CPU execution markers, IPI/TLB evidence and stress logs; CPU topology
model state alone cannot pass this gate.

### P15 — accounting, entropy and observability

Replace fabricated sysinfo/clock/random data with accounted state and calibrated
sources. A cryptographic random service needs entropy collection, initialization
state, reseeding and blocking/nonblocking semantics; the current tick-seeded
xorshift must not supply AT_RANDOM, stack guards or security tokens. Return the
appropriate not-ready result until seeded. Define per-thread/process CPU time,
wall clocks, open-file/page/IPC limits and stable diagnostics without exposing
Kernel addresses or secrets. Add low-overhead trace IDs for blocked calls, wakes,
signals, page faults and allocation failures; keep instrumentation out of the
architecture hot path when disabled.

## 6. Userland/libc work and qualification

### L01 — static musl milestone

First run a static, single-threaded musl executable under the new personality,
using musl crt and headers exclusively. A useful gate includes constructors,
argv/envp/auxv, TLS-backed errno, stdio, malloc/realloc/free/alignment, directory
and file APIs, clock access, invalid pointers and clean exit. A puts-only program
that happens not to allocate is insufficient. Qualify stack alignment, FP ABI,
libgcc/compiler-builtins dependencies and multibyte/types even before threads.
Userland may use a full hosted libc; Kernel remains freestanding.

Supply the auxv fields actually required by the pin and chosen loader, including
correct program headers/count/entry sizes, entry/base addresses, page size,
real/effective IDs, secure mode, hardware capability masks and safely generated
random bytes. Do not advertise unsupported ISA features in HWCAP. Static TLS
initialization uses PT_TLS metadata and the architecture TLS contract. Account
for normal musl executable size and stack needs rather than simply enlarging the
current 128 KiB buffer and calling VM complete. ELF loading should use validated
segments through referenced files and VM, with bounded memory consumption.

### L02 — interpreter, PIE and shared libraries

Kernel maps the main ELF and validated PT_INTERP image with independent load
biases, sets the initial PC to the interpreter, and exposes the main program's
auxv correctly. The musl dynamic linker owns ELF symbol resolution, architecture
relocations, TLS modules, constructors/destructors and library policy. Add ET_DYN
and validated interpreter/ELF segment handling in Kernel. Kernel rejects
unsupported architecture/ELF ABI variants and invalid load ranges before transfer
of control; musl parses PT_DYNAMIC and validates/processes userspace DSO
relocations. Verify REL/RELA, GOT/PLT and MIPS/PPC special cases against the pinned
port rather than reimplementing them in generic Kernel code.

Implement mmap/mprotect and file semantics needed for RELRO, executable mappings
and shared libraries. Define W^X transitions and fail safely on malformed images;
never ignore an unsupported interpreter or PT_TLS. Audit library search paths,
rpath/runpath semantics, environment handling, secure-exec restrictions and
relative/renamed executable paths. Qualify dlopen/dlsym/dlclose, dependency cycles,
weak symbols, constructor failure/order, thread-local destructors, handle/lifetime
behavior, dynamic TLS with pre-existing threads, and mixed wrong-endian/ABI DSOs.
The pinned musl may retain loaded DSOs after dlclose where permitted; qualification
must follow its documented and standards-permitted semantics, not require a new
unloader or immediate unmapping. If actual unload is implemented, prove that no
live code/TLS references are invalidated.
Unsupported symbol-version or loader features must be stated rather than claimed
as arbitrary glibc-binary compatibility.

### L03 — threads and libc concurrency

Use the pinned musl pthread implementation, with its architecture clone/TLS,
futex, signal and cancellation paths audited end to end. Qualify pthread_create,
join/detach, stack/guard attributes, once, TSD destructors, mutex types, condition
variables, rwlocks, barriers, spinlocks, cancellation, atfork and posix_spawn.
Run process-shared and robust tests with separate processes mapping at different
VAs. Test priority protocols only after their Kernel and libc support is real.
Verify errno, strtok-like reentrant alternatives, stdio locks, allocator locks,
locale state and dlopen concurrency under timer preemption and later SMP.

A failed thread creation must not leave a joinable ghost, writable orphan stack,
incorrect parent TID or fd/VM leak. A canceled thread must not lose a condvar
notification, leave the malloc lock owned, or bypass required cleanup. libc exit
and `_Exit` differ; flushing streams, atexit/destructor execution and terminating
all threads must match their interfaces. Signals and fork need async-signal-safe
paths; do not use a general Kernel allocator or sleepable libc lock inside a
signal trampoline.

### L04 — libc standards gaps, locales and text APIs

musl is a candidate implementation, not a guarantee of every elected POSIX/XSI
option. Audit the pinned release for locales, collation, encodings, math/long
double, complex functions, floating environment, iconv, locale objects, message
catalogs and thread priority protocols. Record unsupported or deliberately
limited behavior in the P00 ledger. If mandatory/elected behavior is missing,
choose a maintainable patch, a supplementary library/service with the correct
ABI, or a revised optional declaration before release; never relabel a mandatory
requirement optional to fit libc.

Define shipped locale names/data and the C/POSIX locale baseline. Test LC_CTYPE,
LC_COLLATE, LC_NUMERIC, LC_TIME, LC_MONETARY and LC_MESSAGES with per-thread locale
objects, invalid byte sequences, restartable multibyte state and concurrent
setlocale/uselocale behavior as specified. UTF-8 input support alone does not
satisfy collation, case conversion, monetary formatting or utility locale rules.
Qualify regex bracket classes/collation/backreferences, fnmatch/glob escaping and
sorting, and wordexp's dependency on a conforming shell and command-execution
controls. Treat gettext catalogs/tools as an additional compatibility package;
track catopen/catgets/catclose separately wherever the selected XSI contract
requires them.

### L05 — Shell and Utilities completion

Keep oksh as a small rescue shell while qualifying a maintained shell candidate
or explicitly implementing the full grammar. Package selection is a later
license/size/portability decision, not a declaration that BusyBox, dash, bash,
Toybox or any named package automatically conforms. Use the Issue 8 utility list
and exact selected options as the inventory, including required development,
text-processing and environment interfaces. Do not substitute a count of
installed binaries for behavior coverage.

Required shell work includes quoting/escaping, parameter/command/arithmetic
expansion, field splitting and pathname expansion order, redirections and
here-documents, compound commands, functions, loops/conditionals, subshells,
AND/OR and multi-stage pipelines, environment/export/readonly/unset, traps,
wait/exit statuses, command lookup, PATH/ENOEXEC script handling, background jobs
and terminal job control. Cover each special builtin's error and environment
semantics. Test hostile filenames, empty fields, embedded newlines, interrupted
redirections and fd collisions; parser tests alone do not cover process and TTY
semantics.

Build an explicit row for every mandatory/elected utility and builtin. Early
integration groups include `sh`, `test`, `printf`, `getconf`, `env`, `command`,
`find`, `xargs`, `sed`, `awk`, `grep`, `sort`, `uniq`, `cut`, `tr`, `wc`, `od`,
`dd`, `cmp`, `diff`, `cp`, `mv`, `ln`, `rm`, `mkdir`, `rmdir`, `chmod`, `chown`,
`touch`, `ls`, `pax`, `tar` only if selected as an extension, and process/job
utilities. This example group is **not the complete normative list**; P00 owns
that list, including utilities whose required status depends on selected
options. Test exit codes, diagnostics channels, utility syntax guidelines,
locale/environment effects, large files, signals and pipeline behavior against
the standard and a qualified reference environment.

### L06 — distribution services and execution environment

Provide the declared filesystem hierarchy, temporary-file policy, device nodes,
accounts/groups, locale/timezone/resolver data and required system databases.
Implement login/session policy and startup/shutdown/reaping in OS-owned services.
Integrate sockets/PTYs/IPC without embedding distribution names into Kernel
mechanisms. Establish ownership/permissions at packaging time, avoid world-writable
loader paths, and verify persistent data migration across OS upgrades. Keep the
rescue archive, basic Kernel GUI and diagnostics available independently of a
failed musl or service startup.

### L07 — packaging, SDK and release gates

Keep legacy and musl artifacts distinguishable in package manifests, ELF metadata
and sysroot directories. Export ABI capability/schema versions and exact supported
personalities from Kernel SDKs; increment native C++ module ABI when its actual
interface changes independently of user ABI versioning. Validation must reject
wrong architecture, endianness, mode, compiler ABI, user personality, libc tuple
and missing/modified artifacts before linking or boot. Preserve the standalone
Kernel test path as well as OS SDK consumption.

Pin all upstream inputs and patches, preserve license notices, capture toolchain
versions and configuration, and demonstrate reproducible builds or explain each
unavoidable nondeterministic field. xmake targets should expose separate producer
and consumer phases and never compile a sibling Kernel checkout. Build all ten
legacy profiles throughout migration; additionally report musl qualification per
tuple instead of silently omitting unsupported rows.

## 7. Dependency backlog and completion gates

IDs are stable work/requirement-family identifiers for the main project plan.
Do not reuse an ID for a different requirement. Each gate requires code review,
ABI documentation, meaningful tests and explicit remaining deviations.

| ID | Deliverable | Dependencies | Completion evidence |
| --- | --- | --- | --- |
| P00 | Revised allocator contract; Issue 8 mandatory/options ledger; scope and certification vocabulary | None; contract revision precedes allocator implementation | Reviewed contract diff and complete interface/utility inventory with owners |
| P01 | Versioned legacy/Linux personalities and ten ABI codecs/specifications | P00, L00 ABI audit | Raw assembly syscall/error/structure fixtures on all ten; ambiguity and wrong-ABI rejection |
| P02 | Real frame/object allocators, stable references, quotas and contexts | P00 | Exhaustion/rollback/reuse and physical allocation tests |
| P03 | Native VMA/PTE/fault/user-copy system; anonymous then file/shared VM; COW later | P01, P02 | Real map/protect/unmap/fault tests; races and data isolation |
| P04 | Thread wait/wake/readiness protocol and actual clock/timer core | P02; P01 for user layouts | Lost-wakeup, mask-and-wait, idle-time and timeout evidence |
| P05 | Runnable native threads, clone sharing, TLS and clear-child-tid | P01–P04 | Multi-thread execution and independent TLS/errno on each profile |
| P06 | Signals, sigreturn, restart and cancellation substrate | P01, P03–P05 | All architecture frames, masks, nested/altstack delivery, interrupted syscalls |
| P07 | Private/shared futex, robust exit and declared mutex protocols | P03–P06 for P07.basic; P13.scheduler for P07.priority | Cross-process aliasing, race, owner-death and PI tests |
| P08 | Complete VFS/path/fd/metadata/readiness semantics | P01–P04; P06 for signals | Namespace/permission/short-I/O/locking/durability suites |
| P09 | Complete process/credential/exec/wait/session semantics | P01–P06, P08 | Thread-group exec/fork/exit rollback, set-ID and wait-event tests |
| P10 | TTY/PTY/termios and job-control mechanisms | P04, P06, P08, P09 | Interactive and scripted multi-session job-control suite |
| P11 | POSIX and elected XSI IPC | P03–P09 | Shared memory, semaphores, MQ and elected System V lifecycle tests |
| P12 | AF_UNIX then IP socket mechanisms | P04, P06, P08, P09 | Real endpoint/network tests, ancillary rights and readiness races |
| P13 | Elected realtime scheduler/timers/AIO/memory-locking behavior | P03–P06/P08/P09 and P07.basic; P13.scheduler precedes P07.priority | Policy, priority-inversion, AIO completion and timed IPC tests |
| P14 | Hardware SMP and concurrent Kernel services | P02–P09; P07/P13 readiness review | AP/IPI/TLB and parallel user execution per claimed platform |
| P15 | Honest accounting, entropy and diagnostics | P02, P04, platform entropy inputs | No fabricated success; entropy-ready/limits/usage tests |
| P16 | Clause-level conformance and declared-profile qualification | Required P00–P15/L00–L07 rows; SMP only if claimed | Reproducible results, deviations closed, optional certification process separate |
| L00 | Pinned musl/toolchain/port and ABI qualification | P00 | Exact version/source hashes/patches, ten tuple decisions, external facts verified |
| L01 | Static single-thread musl with real allocator/TLS | L00, P01–P04; single-thread TLS part of P05 and required P08/P09/P15 subsets | Actual musl stdio/malloc/TLS/auxv/errno smoke and negative tests on ten |
| L02 | PIE/interpreter/dynamic linker and dl* | L01, P03/P05/P06/P09/P15 | Relocations, TLS DSOs, constructors, RELRO and secure loader tests |
| L03 | pthread, synchronization, cancellation and spawn qualification | L01, P05–P09, selected P11/P13 | libc concurrency and process-shared/robust/cancellation suite |
| L04 | libc/locale/text standards-gap closure | L00/L01 for L04.core; L03 for thread locales, L05.shell for L04.wordexp | Per-interface and per-locale conformance evidence |
| L05 | Conforming shell and complete required utilities | L01/L04.core; P06/P09/P10; L03/L02 as packages need; L05.shell precedes L04.wordexp | Clause-level shell/utility matrix; real pipelines and job control |
| L06 | Accounts, resolver, services and execution environment | L01/L04/L05, P09–P12 | Real service/session/data/permissions integration |
| L07 | Reproducible sysroots, packaging and SDK/ABI release pipeline | Starts with L00; expands at each gate | Ten-profile producer/consumer acceptance and upgrade/recovery evidence |

These are dependency gates, not a calendar promise. P04 wait/clock foundations
can proceed with P03, and OS source/ABI audit can proceed before a libc can run.
Do not make basic single-CPU threads depend on completed SMP. Do not make static
musl depend on dynamic linking. Conversely, do not mark L01 complete while malloc
or TLS still succeeds only through fake metadata handlers. AIO implementation
choice and selected realtime option scope are explicit decisions at P00/L00.

Use these explicit subgates to keep the dependency graph acyclic:

- `P07.basic`: ordinary private/shared futexes and robust teardown, independent of
  priority policies. `P13.scheduler`: actual policy/priority enforcement, then
  `P07.priority`: donation/ceilings integrated with that scheduler. Full P07/P13
  completion requires their respective final tests; neither full work item is
  a prerequisite for starting the other.
- `L04.core`: libc locale/regex/glob/fnmatch behavior excluding wordexp's shell
  dependency. `L05.shell`: runnable shell grammar/expansion/process/TTY semantics
  over L04.core. `L04.wordexp` follows L05.shell; full L05 utilities qualification
  can then include it. A package may require later loader/thread work, which its
  package manifest must name explicitly.

| Main integration milestone | Principal requirements from this document |
| --- | --- |
| M0: specification baseline | P00, L00 and P01 ABI specifications; initial L07 manifests |
| M1: resource foundation | P02/P03/P04; P15 clock/accounting foundations and P14 locking design |
| M2: common OS objects | P08/P09, TTY foundations of P10 and AF_UNIX part of P12; signal-dependent completion follows M3 |
| M3: libc substrate | P01 execution, P05/P06/P07.basic, L01/L03 and startup entropy from P15 |
| M4: durable default root | P08 persistence contract integrated with the storage plan |
| M5: useful POSIX userland | L02/L04/L05, P10/P11/P13 and remaining file/time/process semantics |
| M6: connected host | IP socket part of P12 and resolver integration from L06 |
| M7–M9: services and desktop | L06; actual applications exercise P03/P08/P10/P12 and libc contracts |
| M10: ext4 breadth | P08 semantics across the storage plan's advanced profiles |
| M11: execution breadth | P14, concurrent P07/P08/P12/P13 qualification and L07 platform evidence |
| M12: full target | P16 and L07; all mandatory and selected requirements closed on all ten profiles |

Milestone names group integration evidence; they do not convert partial
foundations into completed semantics. These subgates continue during execution
without routine user approval stops, within the authorized implementation scope.

Recommended integration order: P00/L00/P01 specifications; P02/P03/P04; P05 and
minimal static L01 startup; P06/P07/L03 with P08/P09; L02 and P15 completion;
P10/L05, P11/P12/L06 and declared P13; P14 when concurrency invariants are ready;
then P16 for the entire declared product profile. Run regression gates during
each increment rather than accumulating ten untested ports at the end.

## 8. Concrete test design and evidence rules

No tests listed below were run for this planning task. Existing tests remain;
new suites should assert externally meaningful invariants and distinguish models,
QEMU CPU/device execution, full userland and physical-board runs.

| Gate | Required experiments and assertions |
| --- | --- |
| ABI | Tiny per-architecture assembly probes bypass libc; success/error flag checks, all six arguments including MIPS O32 stack slots, signed/unsigned extension, 64-bit pairs on ILP32, BE/LE structures, signal/TLS layouts, invalid flags and wrong-personality ELF |
| VM | Touch actual mapped pages, zero-fill, guard-page faults, PROT_NONE, partial unmap/protect, MAP_FIXED collision/rollback, file EOF/truncate SIGBUS, shared aliasing, COW parent/child independence, copy faults and allocation failure at each stage |
| Process/exec | Failed exec preserves all old state; successful exec closes only CLOEXEC descriptors, kills sibling threads safely and installs credentials/personality; fork from nonleader thread, wait stop/continue/exit once, orphan collection and PID reuse |
| Time64/large files | ILP32 and BE fixtures past 2038 and beyond signed 32-bit offsets; sparse files/mappings past 4 GiB where filesystem supports them; EOVERFLOW only at incompatible legacy interfaces; relative/absolute timeout rollover and clock adjustments |
| Threads/TLS | Hundreds of create/join/detach cycles bounded by declared limits; preemption/migration with unique TLS and errno; TSD destructors; TLS after dlopen; stack overflow/guard; FP state preservation and compiler-generated atomics |
| Futex/robust | Compare versus enqueue race, wake before/after sleep, timeout/signal/wake collision, shared object at different VAs, unmap/reuse, process killed during robust pending operation, owner-death recovery, condvar cancellation and PI chains |
| Signals | Every supported delivery/return path, nested handlers, alternate stacks, invalid sigreturn frames, reserved privilege bits, blocked pending signals, realtime ordering/limits, SA_RESTART and partial writes, cancellation cleanup |
| Files/namespace | Search permissions including dotdot, sticky/group rules, symlinks, held cwd/dirfds through rename/detach/mount aliases, concurrent rename observers, shared fd offsets, append and byte locks, close/reuse and crash persistence with offline inspection |
| TTY/shell | PTY-driven shell tests with quoting/expansions/redirections; multi-stage pipelines; Ctrl-C/Z and foreground/background groups; VMIN/VTIME; EOF/hangup; multiple sessions; fd and child leaks after errors |
| IPC/network | Shared-memory unlink and final-reference reclamation, named/unnamed semaphores, MQ priority/notify race, elected System V removal/SEM_UNDO, AF_UNIX rights/credentials, nonblocking socket and real IP traffic |
| musl/loader | Pin's own suitable tests plus independently selected libc/POSIX suites; static/dynamic PIE, RELRO, malformed DSOs, constructor/destructor ordering, dlopen TLS, locale/regex/glob/wordexp, malloc fragmentation and stdio concurrency |
| Realtime/AIO | Real policy scheduling, priority inversion and ceiling bounds, timer overruns, pinned-page accounting, AIO cancellation/completion exactly once and close/reuse; report measured platform/jitter separately |
| SMP | At least two real QEMU CPUs where claimed, simultaneous user execution, IPI receipt, remote stale-TLB rejection, lock/refcount races, TLS migration, CPU offline/exit protocol if supported |
| Product conformance | All mandatory/elected interface and utility rows, feature macro/query checks, limits and error behavior, installed environment, no unexplained skips; certification evidence only from the applicable external process |

Run the architecture matrix in both debug and release for standalone Kernel and
OS SDK consumer. Retain raw serial logs, compiler/libc/SDK manifests, generated
ABI fixtures, test versions, QEMU machine/CPU/device settings and failure seeds.
Do not treat a host test compiled with ten architecture defines as ten hardware
executions. Failure injection must cover allocator, copy, I/O, timeout and teardown
paths; concurrency tests need adversarial scheduling and weak-memory architectures.

Test package choices (for example libc-test, relevant LTP/POSIX subsets and shell
conformance suites) require version/license/environment review at P16. Passing a
Linux-oriented suite can supply useful evidence but does not redefine POSIX or
prove all selected options. Each waived test needs a normative reason, profile
impact and closing requirement ID; an ENOSYS skip is not a pass for a mandatory
or elected interface.

## 9. Decisions to resolve before implementation starts

1. Implement P00's narrow allocator contract revision and establish the exact
   Issue 8 option declaration, including realtime/XSI and utility obligations.
2. Specify P01's dual-personality transition and ELF selection rule; freeze ten
   ABI tuples without altering their existing CPU profiles.
3. Select and verify the musl release, Linux UAPI baseline and user toolchains;
   decide how to close any retained-PPC/MIPS/RV32/LoongArch qualification gaps.
4. Agree on frame/object ownership, VM/wait locking and rollback boundaries before
   exposing mmap/clone/signals/futex to untrusted native programs.
5. Choose the maintained shell/utility/locale packages or the explicitly funded
   implementation scope; audit musl standards gaps rather than assuming them away.
6. Define release evidence and certification intent separately. Keep incomplete
   profiles visible and preserve legacy rescue/userland and all ten Kernel builds.

This plan intentionally creates no implementation, build configuration change,
SDK export or new compatibility claim. Each implementation phase must update its
ledger and documentation with observed behavior and validation evidence.
