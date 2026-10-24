# Architecture, resources, SDK and extension design

Status: proposed implementation design. Parent: [workstation plan](README.md).

## A01. Ownership and language boundaries

| ObfuscationKernel | ObfuscationOS |
| --- | --- |
| CPU entry, traps, page tables, allocator, scheduler, credentials and user copies | Toolchain/sysroot assembly, musl and other user libraries, application ports |
| VFS/cache/filesystem implementations, socket/protocol mechanisms, IPC and time | Mount/storage/network policy, filesystem utilities, system daemons |
| Native module loader, resource/IRQ/DMA contracts and essential boot devices | External block/NIC/display/input/audio drivers, external native modules |
| Minimal display/input mechanism, rescue GUI and diagnostics | Compositor, session/desktop, toolkit, system apps, fonts and themes |
| Process/VM/resource mechanisms enforcing isolation | Authentication/account policy, packages, installer, update/recovery images |
| Stable UAPI and explicit same-build native extension interface | Linux driver adaptation and version-qualified upstream driver ports |

Keep freestanding C++23, xmake, RTTI and explicit `Status`/`Result` errors in
Kernel/native extensions. No exceptions, hosted STL allocation or implicit
external C++ runtime dependency. A userspace C/C++ library port is a different
execution environment: musl and a separately ported C++ runtime may provide its
hosted facilities. Do not force all third-party user code into freestanding C++.

Current [Kernel development rules](../../../ObfuscationKernel/docs/DEVELOPMENT.md)
forbid heap allocation. M1 therefore requires an explicit contract change to
allow **Kernel-owned, fallible physical/page/object allocators**, with context
and quota rules, while continuing to forbid hosted allocation and exceptions.
This plan does not silently change that rule or treat the existing model slab
allocator as a production memory manager.

## A02. Compile-time and runtime design

Architecture selection, page-table encoding, IRQ state operations, atomic
primitives, scheduler policy and measured hot algorithms use constrained
templates/static dispatch. Generic code names the required operation, not an
architecture-specific conditional scattered through VFS, networking or GUI.

Example *design shape*, not a committed public header:

```cpp
template <PageTableBackend Tables, PhysicalPageProvider Frames>
class AddressSpace;

template <RunQueuePolicy Policy, CpuOperations Cpu>
class SchedulerCore;

template <ChecksumImplementation Checksum>
class PacketValidation;
```

Use runtime OOP for dynamically selected `BlockDevice`, network/display device,
filesystem and module-service boundaries. Bind once at a device/queue boundary,
then batch requests; do not introduce a virtual call per byte, PTE or pixel.
Do not template entire subsystems over every configuration knob: excessive
instantiation increases image size and cross-architecture maintenance. Measure
the path before replacing a clear implementation purely for presumed speed.

## A03. Resource and concurrency contract

Canonical objects and owners:

| Object | Ownership and destruction condition |
| --- | --- |
| Physical page | Allocator owns accounting; mappings, I/O pins and shared objects hold references; reuse only after all references and translations are retired |
| Address space | Process/thread group owns it; map modifications serialize; teardown waits for remote TLB invalidation and outstanding safe user access |
| Thread / process | Scheduler owns executable state; process object survives exit until wait/reaping and external references complete |
| Open file description | Shared offsets/status flags, independent of FD slots; dup/fork/SCM_RIGHTS reference it; last release closes backing object |
| Inode/dentry/mount | Separate identity, naming and mount traversal objects; open/mapped/unlinked files and cwd pin references without requiring a live pathname |
| Device request | Submitter owns request until accepted; queue owns it until one completion/cancellation; pages remain pinned until DMA is stopped |
| Module | Loader owns code/data and dependency references; active objects/callbacks/timers/work/IRQs prevent unload |
| User buffer | VM object owns pages; handles/mappings/presentation references are distinct; no lifetime derived only from an integer slot |

Use generation-bearing handles where IDs can be reused. Validate references
when looking up handles and hold them through the operation. Never dereference
an unpinned user pointer after sleeping or switching address spaces.

Synchronization requirements:

- IRQ-safe spinlocks protect short runqueue/queue operations; no sleeping,
  faulting user copies or device waits while held. Save/restore interrupt state
  correctly rather than unconditionally enabling interrupts on unlock.
- Sleepable mutexes and read/write locks protect longer metadata operations.
  Define lock ranks and owner assertions; record per-subsystem acquisition order
  in its design. Cross-directory rename requires a stable global ordering.
- Atomically register a waiter and recheck the condition under the appropriate
  object lock. Publish state before wakeup with defined memory ordering. Timeouts,
  signals, peer exit and device removal race to exactly one wake outcome.
- Keep interrupt top halves bounded. Defer allocation, protocol parsing and
  callbacks to worker context. Work queues run real threads and drain on stop.
- Start with explicit reference counting and locks. Introduce RCU or lock-free
  structures only with a documented reclamation proof and a measured reason.
- Boot on one CPU first, but do not equate interrupt exclusion with SMP safety.
  Add debug lock checking, native two-CPU race tests and weak-memory stress.

Define memory pressure policy: per-process limits and charges, cache reclaim,
I/O reserves, allocation contexts, failure propagation and a bounded final OOM
policy. Do not deadlock journal/writeback/network recovery by consuming its last
reserved pages. Allocation failure must not leave half-published kernel objects.

## A04. Ten-architecture execution contract

Preserve `i386`, `x86_64`, `aarch64`, `arm32`, `rv64`, `rv32`, `loongarch64`,
`mips`, `mips64`, `ppc`. Existing native ELF execution is the baseline, not a
reason to defer less common profiles indefinitely. The root constraint file's
historical four-userland sentence is superseded by the present ten-profile OS
implementation and [OS development contract](../../AGENTS.md).

Each profile must implement/qualify:

1. Boot RAM/reserved regions, exception vectors, kernel/user privilege and
   checked return-state handling, stack alignment and guard pages.
2. Real page table/map/unmap/protection operations, page faults, ASID/PCID where
   available, local and remote TLB invalidation, instruction/data cache ordering.
3. Architecture atomic widths, alignment, memory ordering, interrupt nesting,
   per-CPU storage, timers, IPIs and secondary-CPU startup where supported by
   the selected platform. A UP-only platform reports that capability honestly.
4. General register, floating-point/SIMD, TLS and signal context preservation.
   Eager FPU save/restore is the initial correctness baseline; do not use lazy
   state as an untested optimization. Qualify soft-float profiles explicitly.
5. DMA addressing mask, coherent allocation vs streaming map/unmap,
   `sync_for_cpu`/`sync_for_device`, endian MMIO and posted-write barriers.
6. ELF class/endian/machine/ABI flags and compiler multilib, Linux syscall
   calling convention, auxv, signal frame, TLS model and time64/off64/stat
   layouts described in [POSIX/musl](POSIX_MUSL.md).
7. External interrupt delivery and actual device completion, reset and timeout;
   full SDK, standalone boot and OS-consumer integration in debug/release.

MIPS/PPC/32-bit special cases are acceptance inputs, not exceptions hidden in
generic code. Where selected CPUs lack NX or another protection, publish the
hardware limitation and enforce all available protections; never claim identical
W^X guarantees. New Linux ABI code must preserve old native ABI tests until their
apps are explicitly migrated. FPU/ABI changes may require an SDK generation and
toolchain rebuild, not merely a syscall wrapper change.

Generalize platform enumeration from current QEMU fixed resources to FDT/ACPI
or board-description inputs. Essential boot parser/controller code belongs in
Kernel; optional PCI/USB device policy and external functional drivers belong
in OS. Enumerate bridges/BARs/interrupt routing and allocation rather than assume
PCI bus 0 and fixed windows forever. An IOMMU backend is a separate capability;
without it, trusted kernel drivers still have unrestricted DMA risk.

## A05. Runtime native modules

Current [module implementation contract](../../../ObfuscationKernel/docs/modules/modules.md)
and [`KernelExtension`](../../../ObfuscationKernel/include/ok/core/extension.hpp)
cover metadata and prelinked objects. The implementation goal is actual
relocation, executable page mapping, initialization and lifecycle control.

Proposed Kernel layout: `src/module/{loader,elf,relocations,symbols,lifecycle}.cpp`
with per-architecture relocation policies under `src/arch/<arch>/`. OS packages
and drivers remain under OS `modules/` and `drivers/`; OS provides `kmodload`
and service-manager policy. SDK consumers cannot include Kernel private source.

Load pipeline:

1. Open a package through a privileged loader request; capture one immutable,
   size-bounded image and verify it before relocation. A pinned inode alone does
   not prevent concurrent content changes. Verify hashes/signatures and perform
   all later parsing/copying from the same captured bytes. Validate manifest
   architecture/mode/endianness, compiler ABI, SDK generation, required services
   and relocation capabilities.
2. Validate ELF sections, alignment, overflow, symbol/relocation bounds and
   allowed relocation types. Reject unsupported TLS/text relocations or dynamic
   linker assumptions explicitly. Start with documented `ET_REL` module output.
3. Allocate unpublished pages with writable/non-executable permissions where
   hardware supports it; copy sections, zero BSS, resolve only exported symbols
   and perform checked relocations. No import of arbitrary Kernel addresses.
4. Finalize RX/R/RW sections, flush caches and perform the required TLB/cache
   synchronization. Execute validated initialization arrays/factory under the
   loader's failure-unwind contract; publish services only after start succeeds.
5. Pin imports/dependencies while objects or callbacks use them. Roll back
   partial initialization in reverse order without publishing half-ready devices.

At first support direct C++ OOP use only with the exact SDK/compiler/flags/layout
contract. All module allocation/deallocation uses the Kernel allocator API; no
private hosted heap. Keep RTTI consistent across the module set, bound accepted
static initialization and prohibit exceptions/unwinding across this boundary.
For interfaces intended to evolve independently, add versioned C service records
with size/capabilities and opaque handles, plus C++ wrappers within each module.
This keeps OOP ergonomics without claiming arbitrary C++ ABI stability.

Unload protocol: reject new opens/submissions, withdraw published services,
stop device DMA/IRQs, cancel and drain timers/work, join workers, wait for client
object and callback references, run stop/destruction, then unmap executable
pages and release dependencies. Return `EBUSY` if quiescence is not provable.
Do not force-unload code executing on another CPU. Kernel-mode modules are
trusted code; a crash is not an isolated process restart, and a manifest
capability bit is not a memory-protection sandbox.

Tests: architecture relocation golden vectors and overflow rejection; a newly
compiled module executes a unique function in a guest, registers a service and
performs a real request; failed init leaks nothing; wrong SDK fails; unload with
open handles/timers/IRQ work is refused or drains safely; repeated load/unload
under SMP and I/O does not execute freed text. Metadata markers cannot pass this
gate.

Linux driver adaptation is a later, version-pinned OS layer. Start with one
selected driver's source dependencies, map locking/DMA/work/IRQ semantics onto
native contracts and port that driver with real-device tests. Track license and
source obligations. Do not promise arbitrary Linux `.ko` binary loading or
emulate an entire Linux kernel to satisfy an unexplored dependency graph.

## A06. SDK, sysroots, packages and upgrades

Maintain three separately versioned contracts:

- **Kernel SDK:** architecture, mode, CPU/ABI flags, compiler identity, native
  extension ABI, exported headers/libraries/linker artifacts and hashes.
- **User ABI/sysroot:** Linux personality revision, libc/loader version, target
  triple, feature/options manifest, user headers/libraries/crt and loader path.
- **Service/protocol ABI:** message/protocol versions, capability negotiation,
  supported semantic contracts and deprecation policy.

Existing [SDK validation](../../tools/kernel_sdk.py) remains mandatory. Extend
its manifest schema explicitly; never pick a convenient matching glob or fall
back to Kernel source headers. Build Kernel and export its SDK separately. OS
builds consume it read-only and fail before linking on mismatch. Generate user
UAPI headers from their public definitions, not internal C++ object layout.

Proposed `ports/<name>/` recipes record upstream URL/version/hash, license,
patches, build/host/target tools, dependencies and feature choices. xmake
orchestrates isolated out-of-tree upstream builds and staging; native build
tools are not target binaries. Generate one sysroot per arch/ABI/mode and forbid
host `/usr/include` or host libc leakage. Separate compiler bootstrap musl
sysroots from the complete distribution image to break toolchain cycles.

Reproducible package metadata records content hashes, dependencies, architecture,
required UAPI/SDK versions, installed paths, permissions, config merge policy and
license notices. Sign repository metadata with a pinned trust root and verify
before installation. Changes requiring new Kernel/native drivers must install
matching sets; never update an SDK-locked driver against an arbitrary Kernel.

Updates use a durable staged transaction or alternate boot/root deployment,
with manifest commit and rollback. ext4 is not a snapshot filesystem; do not
promise snapshot rollback without a separate storage/deployment mechanism.
Keep a known-good Kernel/root and immutable rescue image. Power interruption
must leave either a selected previous deployment or a complete new deployment,
not a partially overwritten boot path. First boot validates health before
discarding the previous generation.

## A07. Supporting mechanisms and release gates

- Entropy: initialize a cryptographic RNG from actual platform entropy and
  securely mixed sources; expose correctly blocking/nonblocking `getrandom`
  behavior. Unseeded counters are not adequate for TCP secrets, TLS or login.
  Test low-entropy boot and error paths before deploying network authentication.
- Time/power: monotonic, realtime and CPU accounting clocks with actual timer
  calibration; time adjustments cannot reverse monotonic time. Clean reboot and
  poweroff follow service termination, filesystem sync/unmount and device drain.
  Suspend/resume requires a separate per-driver gate and is advertised only then.
- Observability: bounded trace buffers, crash records, symbol/build IDs,
  resource counters and permission-checked inspection APIs; no secret-bearing
  kernel pointers in ordinary user diagnostics.
- Security foundation: credentials, supplementary groups, umask, executable
  privilege transitions, resource limits, randomization where supported, clear
  device access policy and safe parser failure. Do not substitute hidden APIs
  for authorization checks.

Acceptance spans M0/M1/M11/M12: ten-profile manifests; allocation failure and
lifetime tests; real two-CPU execution/TLB/IRQ tests on capable reference
platforms; module code execution; artifact mismatch tests; reproducible isolated
sysroots; interrupted update recovery; and named physical-platform evidence.
Source restructuring must preserve standalone Kernel diagnostics and useful
existing model tests alongside the new native tests.
