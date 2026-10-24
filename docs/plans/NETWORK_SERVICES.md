# Network and system-service implementation plan

Status: proposal for review, based on a source audit on 2026-09-20.
Parent: [workstation plan](README.md). This document
adds no implementation or validation claim. No builds, tests, packet exchanges,
or external standards/library audits were run for this planning task. Existing
acceptance results are attributed to the repository's validation records.

## 1. Outcome and boundaries

Build a usable dual-stack Internet **end host** and a supervised native
user-space system on all ten profiles: i386, x86_64, aarch64, arm32, rv64, rv32,
loongarch64, mips, mips64 and ppc. Preserve freestanding C++23, xmake and the
artifact-only Kernel SDK boundary. A first milestone may be IPv4-only, polling,
or static-addressed, but must retain that label until later gates pass.

A completed core host milestone requires real Ethernet RX/TX, independently
verified IPv4/IPv6 parsing and transport behavior, working native sockets and
readiness, address/route configuration, name resolution, and recoverable service
lifecycle. An internal loopback counter, `established` enum, scheduler record,
or successful SDK build cannot establish any of these outcomes by itself.
“Complete” below means this documented host profile and its requirements matrix,
not every Internet RFC, every POSIX facility or Linux binary compatibility.

| Owner | Mechanisms and policy |
| --- | --- |
| ObfuscationKernel | Packet memory, protocol engine, interfaces/routes/neighbors, endpoint state, socket/IPC handles, guarded syscalls, readiness/wait queues, clocks/timers, entropy, credentials, process/session mechanisms, DMA/IRQ/platform primitives, basic diagnostics |
| ObfuscationOS | External NIC drivers, device discovery policy, interface naming and configuration, DHCP/DNS/time services, PID 1 program, service manifests/control CLI, account/login policy, user sessions/desktop, firewall policy, packaging/update/recovery |
| Exported SDK | Versioned native driver service contracts, C user UAPI, build/compiler ABI and artifact hashes; consumers never rebuild Kernel sources |

The overarching roadmap selects a per-architecture Linux user-space syscall
personality for musl. Keep this compatibility layer separate from the native
Obfuscation UAPI: both call the same kernel socket/process mechanisms after
their own checked marshaling. The planned system compositor is an isolated OS
Wayland process using libwayland, xdg-shell, wl_shm and a software pixman renderer
first; Kernel retains its basic rescue/diagnostic GUI. This document specifies
the network, supervisor and session/seat prerequisites of that direction, not
the compositor rendering design.

Runtime interfaces are justified where a device, module or open resource is
selected at runtime. Packet parsing, checksum algorithms, transport selection,
queue algorithms and scheduler policy use constrained templates/static dispatch
where measured work benefits. Do not put a virtual call on every byte or route
lookup merely to share code. Keep extensible boundaries coarse, for example one
batch submission call per device queue.

## 2. Source audit: what exists

Paths are relative to this document. Line numbers are inspection hints for the
working tree on the audit date; symbols are the durable references.

| Evidence | Observed behavior and implication |
| --- | --- |
| [net.hpp](../../../ObfuscationKernel/include/ok/net/net.hpp), `NetworkStack`, `SocketTable`, lines 14–225 | Fixed capacities: 1500-byte packet buffer, 16 datagrams/sockets, eight listeners/ARP entries; IPv4 addresses only. Socket numbers are a separate table starting at 3, not scheduler-owned descriptors. |
| [net.cpp](../../../ObfuscationKernel/src/net/net.cpp), `VirtioNetDevice::probe/transmit/receive`, lines 24–72 | Probe flips a boolean; transfer functions validate a span and increment counters. No PCI/MMIO negotiation, DMA ring or device completion exists here. The name does not indicate a hardware NIC driver. |
| Same file, `ArpCache`, `send_icmp_echo`, `send_udp`, lines 75–224 | ARP is an in-memory key/value table without wire messages or expiry. ICMP returns a synthesized local reply. UDP constructs temporary IPv4/UDP bytes but queues a copied `UdpDatagram` directly; the packet is not transmitted or reparsed from hardware. Nonlocal destinations return unsupported. |
| Same file, `connect_tcp`, `accept`, `recvfrom`, `poll`, `shutdown`, lines 245–502 | TCP checks a local listener and returns `established`; accept creates a connected record without a pending handshake queue. Stream read/write are unsupported. All UDP sockets consume the same stack queue, and readability tests that global queue; there is no destination demultiplexing. Shutdown changes a state field rather than reclaiming descriptor/transport resources. |
| [network_storage_tests.cpp](../../../ObfuscationKernel/tests/kernel/roadmap/network_storage_tests.cpp), `test_network_device_and_protocols`, `test_socket_table`, lines 116–286 | Useful model checks for the preceding contracts; they do not exchange packets with a peer or execute user socket syscalls. Preserve them with the model implementation. |
| [shell/network.cpp](../../../ObfuscationKernel/src/apps/shell/network.cpp), `execute_network`; [kernel.cpp](../../../ObfuscationKernel/src/core/kernel.cpp), `Kernel::boot`, line 356 | Debug commands call the loopback model; boot initializes 127.0.0.1. A successful debug `net tcp` command is not a TCP interoperability test. |
| [runtime.cpp](../../../ObfuscationKernel/src/user/runtime.cpp), `dispatch`, lines 287–686 | Checked native boundary implements a narrower syscall set than trusted-buffer handlers. Socket calls, select/poll/epoll, signals and general native sleep/VM operations are not implemented by this boundary. Its default returns ENOSYS. |
| [resources.hpp](../../../ObfuscationKernel/include/ok/sched/resources.hpp), `OpenFileDescription`, `ThreadWaitReason` | Files, console and pipes share canonical scheduler ownership; sockets do not. Native wait reasons currently cover children and pipe reads/writes, not a general pollable object. This ownership should be extended, not duplicated. |
| [abi.hpp](../../../ObfuscationKernel/include/ok/driver/abi.hpp), `OkNetworkOperations`, line 303; [abi.cpp](../../../ObfuscationKernel/src/driver/abi.cpp), `OkDmaMapper::map`, line 176 | A synchronous span-based native network service edge exists. Generic DMA returns a synthetic buffer-address-plus-slot value; MMIO uses an array, work queues count items, wait queues hold tokens and timers store deadlines. These helpers cannot be treated as real DMA, interrupt work, blocking or timer delivery. |
| [OS drivers](../../drivers/), [block.cpp](../../drivers/virtio/block.cpp), [VIRTIO_BLOCK.md](../VIRTIO_BLOCK.md) | The external real driver is Virtio block. Its MMIO/PCI and big-endian host bridge work provides useful platform experience on all ten profiles, but there is no OS NIC driver. Its single polling queue/coherent-QEMU assumptions do not prove NIC IRQ, noncoherent DMA or SMP correctness. |
| [qemu_distro.py](../../scripts/qemu_distro.py), `command_for` | Distribution runner explicitly attaches block/input/display devices; there is no controlled NIC/peer/network acceptance setup. Any machine default NIC is not evidence that the OS drives it. |
| [init/main.c](../../apps/init/main.c); [pid1.c](../../apps/init/pid1.c) | The legacy app launches one shell and exits with it. An explicit static-musl PID 1 candidate now keeps one foreground shell under bounded restart, wait-any reaping and TERM/KILL shutdown when its audited build is selected for rootfs staging. It has no service graph, readiness, accounts or full shutdown transaction. |
| [runtime.cpp](../../../ObfuscationKernel/src/user/runtime.cpp), `start/run_slice`, lines 692–803; [scheduler.cpp](../../../ObfuscationKernel/src/sched/scheduler.cpp), `finish_process`, `reap_orphans`, lines 866–971 | Native static ELF execution and boot-CPU preemption exist. Init is allocated from the existing process table; there is no explicit user PID 1 guarantee. Orphans are reparented to kernel parent zero and reaped there. A POSIX init/subreaper policy is future work. |
| [module.cpp](../../../ObfuscationKernel/src/core/module.cpp), `ServiceRegistry`, `start_all`, `supervise_kernel_processes`; [driver.cpp](../../../ObfuscationKernel/src/driver/driver.cpp), `ensure_kernel_process`; [kernel.cpp](../../../ObfuscationKernel/src/core/kernel.cpp), `supervise_daemons`, line 1620 | C++ objects have real lifecycle callbacks and service publication, but `mod:*`/`drv:*` supervision recreates scheduler records with synthetic entry/stack ranges. It is not exec, independent kernel-thread scheduling, process isolation or a native user service manager. Registry values are in-kernel pointers, not authenticated IPC. |
| [ipc.hpp](../../../ObfuscationKernel/include/ok/ipc/ipc.hpp), `IpcRouter`; [ipc.cpp](../../../ObfuscationKernel/src/ipc/ipc.cpp) | Fixed copied messages with caller-supplied sender/receiver fields; no checked user endpoint, ownership/authentication, peer-close wakeup or actual shared-ring mapping. `shared_ring` is a mode value, not mapped user IPC. |
| [user.cpp](../../../ObfuscationKernel/src/user/user.cpp), `reset_defaults`, line 11; [system_gui_runtime.cpp](../../modules/system-gui/system_gui_runtime.cpp), `bind_session_context`, `launch_system_gui_app`, lines 242 and 375 | Built-in kernel/root/user accounts and credential selection exist. GUI launch parses ELF and creates UI records, while app views remain prelinked extension code. Account selection is not password authentication or an isolated graphical login/session. |
| [posix/process.cpp](../../../ObfuscationKernel/src/posix/process.cpp), `clock_gettime`, `nanosleep`, `getrandom`, lines 17, 29, 201 | Clock reads accumulated ticks; model sleep increments them. Random output uses deterministic xorshift seeded from a constant/ticks. Neither calibrated deadlines while idle nor cryptographic entropy exists. Native runtime adds nominal 10 ms on user timer traps. Retransmission, leases, authentication and unpredictable TCP/DNS values must not rely on these semantics. |
| [VALIDATION.md](../../../ObfuscationKernel/docs/VALIDATION.md), [NATIVE_EXECUTION.md](../../../ObfuscationKernel/docs/NATIVE_EXECUTION.md) | Records ten-profile native process/file and real block/ext4 acceptance in QEMU. They do not claim physical networking, hardware SMP or socket interoperability. Current static executable/page/process/fd bounds also constrain future service/library ports. |

Retain current models in explicitly named model tests. Once a real stack exists,
route ordinary network diagnostics to its counters and sockets. Do not silently
keep a synthetic fallback that makes a disconnected NIC appear operational.

## 3. Implementation strategy and reuse decision

The existing language contract selects a freestanding C++23 kernel engine,
including compatible reusable components where qualified. The current TCP model
is not a production protocol implementation to complete by adding success
states. Budget adversarial state handling, retransmission, timers and
interoperability as their own protocol work; OOP alone does not reduce it. Own
the kernel resource model, driver contract, user ABI and OS policy.

Run a bounded comparison against a pinned lwIP release as a feasibility/reference
spike, not an adopted kernel dependency. Inspect its low-level packet/connection
API rather than introducing a second public socket table. Evaluate upstream
source, licenses, supported features and current advisories before choosing a
comparison version. Do not infer that all requirements, especially TCP
SACK/recovery, dual-stack behavior, concurrency and full BSD error semantics,
are supplied by a candidate. This planning task did not fetch or audit lwIP.
Its C implementation does not meet the present kernel C++23 contract by default.
Any alternative that introduces C kernel code requires an explicit architecture
and language-contract decision after the spike; this plan grants no exception
and does not treat compiling C as C++ as qualification.

The evaluation deliverable is a requirement-by-requirement gap table and a small
isolated harness: packet ingress/egress, bounded allocators, exact timer control,
no hidden host syscalls, all ten compiler profiles, little/big endian and ILP32,
license/provenance/SBOM, update path, fuzz integration, object/stack/pool footprint
and packet-rate/latency results. Unmet requirements must have a maintainable
upstream change or explicit milestone; no claim of completion based on library
name. Record any changed engine selection in an architectural decision using
those artifacts and an explicit language-contract update where required. This
is a technical qualification dependency, not a routine user-approval stop between
implementation milestones.

The default C++23 engine follows the contracts below, using the existing
checksum routine only after independent vectors pass. Its estimate must include
long-term TCP state-machine/interop maintenance, not only first packet exchange.
Importing large Linux/BSD network subsystems is a later option after a dependency
and license audit; their allocator, locking, timers and driver contracts must not
force Linux emulation into core kernel paths. The OS Linux-driver adaptation
layer is not an Internet stack port.

Reuse maintained user-space libraries/programs for DNS validation, DHCP, TLS,
NTP and password hashing where their dependencies fit. TLS, certificate parsing
and password KDFs should not be newly invented in the kernel. A tiny project-owned
PID 1/supervisor is reasonable while the syscall surface is small; its process
and IPC semantics must permit porting other supervisors later. libc wrappers
stay thin; they do not reimplement kernel transport state.

## 4. Kernel data model and interfaces

Names in this section are proposed contracts, not existing exported APIs.

### 4.1 Packet and interface ownership

- `InterfaceId {index, generation}` identifies an interface across hot-unplug and
  slot reuse. A registry owns the device reference, capabilities, addresses,
  link state, MTU, queues, statistics and removal state. Names are OS policy;
  generation-tagged IDs are authoritative in routes, sockets and completion work.
- `PacketBuffer` is a move-only owner of bounded pool storage with headroom,
  length, segment chain and metadata. Separate CPU virtual addresses, physical
  addresses and device DMA addresses with different types. Checked cursor reads
  decode network byte order without packed-struct casts or unaligned loads.
  The 1500-byte IP MTU is not the full Ethernet frame size: account separately
  for Ethernet/VLAN/Virtio headers, FCS handling and buffer alignment.
- `NetworkDevice` exposes capabilities, configure/start/quiesce, batched TX,
  RX refill/completion and link events. An accepted TX buffer belongs to the
  device until exactly one completion; a rejected buffer remains with its caller.
  `submit_batch` returns an accepted prefix plus a status, never ambiguous ownership.
  Copy from user memory initially; do not DMA arbitrary user pointers.
- RX ownership is device -> completion -> protocol worker -> socket queue or
  drop -> pool. TX is socket/kernel packet -> device -> completion -> pool.
  TCP keeps its own retransmittable bytes/reference until acknowledged;
  a DMA completion means the NIC consumed a buffer, not that the peer ACKed data.
- Shared payload clones require explicit reference counting and immutable data.
  Mutable header views require unique ownership. DMA mappings are move-only
  tokens tied to device generation/direction/range; unmapping twice is an error.
  Device timeout/removal quarantines outstanding memory until DMA is stopped.
- Pool limits are configuration values, not unexplained global constants. Account
  per interface, socket, process and protocol, with global caps and reserved
  control capacity for ARP/ND/ICMP/TCP ACK and close paths. Report pressure/drop
  reasons; avoid a receive flood starving the supervisor's local IPC or kernel.

`NetworkDevice` replaces or versions the current ambiguous `OkNetworkOperations`
span lifetime contract. Export native ABI changes through matching SDK/module
versions and rejection fixtures. Drivers are statically composed first; no design
step assumes arbitrary runtime ELF module loading is already available.

### 4.2 Execution, timing and locking

Start with one network executor on the boot CPU and explicit bounded ingress,
command and completion queues. Polling can prove first RX/TX, but cannot close
the final interrupt-delivery gate. IRQ handlers acknowledge/mask, publish small
work items and return; they do not parse arbitrary packets, wait for sockets or
invoke OS services. A budgeted deferred poll drains RX/TX and reschedules fairly,
then unmasks interrupts with a recheck to avoid a lost interrupt. Never disable
interrupts around unbounded packet processing.

First correct concurrent contract: one executor owns protocol control blocks;
submitters enqueue commands and receive completions. Device-ring locks are
separate from protocol and fd-table locks. Lookup retains a socket under the
fd-table lock and releases that lock before touching queues. Do not call drivers,
copy user memory, run callbacks or sleep while holding protocol/ring spinlocks.
A condition check, waiter registration and readiness-generation recheck must be
atomic with respect to producer wakeup. Every wait has cancellation for close,
exit, signal, timeout and device disappearance.

A calibrated monotonic clock must advance during idle and kernel-only work.
Use absolute deadlines, overflow-safe arithmetic, an ordered bounded timer
queue/wheel and generation-tagged cancellation. TCP RTO, neighbor expiry,
DHCP leases and supervisor backoff use monotonic time; UTC adjustments must not
restart or skip them. Hardware/virtual clock frequency, rollover, suspend and
cross-CPU consistency require per-architecture contracts. A model `OkTimer`
record is not sufficient. A central work/timer mechanism should also serve disk,
IPC and process waits rather than adding a private network scheduler.

Only after boot-CPU correctness and measured contention, add per-queue/CPU
executors and flow affinity. Preserve one owner for each TCP control block;
route/config updates publish immutable generations and retire old snapshots
safely. Define teardown and cross-CPU wakeup before claiming SMP. Use actual
SMP execution tests, not the current topology/dispatch counters.

### 4.3 Routing and control plane

Kernel owns IPv4/IPv6 prefix tables, interface addresses/lifetimes, neighbor
state, multicast membership, local delivery and source/route selection. Begin
with static routes and a deterministic longest-prefix match with metrics and
explicit interface scope. Separate local/broadcast/multicast routes from unicast.
IPv6 link-local addresses require an interface index; route/source selection
must handle deprecated/tentative addresses and multiple interfaces. Route
updates are validated transactions with generation numbers; removing a route
invalidates cached destinations/PMTU safely. Forwarding defaults off.

Provide a versioned, length-checked privileged control endpoint for enumerate,
set link/MTU, add/remove address/route, subscribe to events and query statistics.
An AF_UNIX-like transport does not make privileged changes safe by itself: bind
authority to kernel credentials/capabilities and fixed operations, never an
unrestricted kernel pointer/ioctl. Event overflow reports a sequence gap and
requires snapshot resynchronization. OS `netd` owns desired configuration and
reconciles hotplug; kernel enforces resource/permission validity. Do not expose
mutable protocol tables directly to desktop or service code.

## 5. Ten-architecture device bring-up

Extract reusable bus/queue support from OS Virtio block work with its existing
tests, not by duplicating the whole block driver. Generic PCI resource allocation
and essential host bridge mappings belong in Kernel platform support; OS Virtio
transport/device code consumes those services. Coordinated BAR/IRQ ownership is
required when block, net and input coexist. A network probe must never rewrite
another driver's BARs or reset its shared bridge.

| Profiles | First QEMU transport | Additional acceptance |
| --- | --- | --- |
| i386, x86_64 | Modern Virtio PCI, initially one RX/TX pair | DMA mask/bounce behavior on ILP32; BAR lifetime; platform IRQ routing and MSI/MSI-X or explicitly supported INTx; no inference from PIT preemption |
| aarch64, arm32 | Virtio MMIO v2, optionally tested v1 | GIC device interrupt acknowledgment, cache-maintenance hooks, MMIO ordering; 32-bit address limits on ARM32 |
| rv64, rv32 | Virtio MMIO v2, optionally tested v1 | External device IRQ controller/PLIC path, distinct from CLINT timer interrupts; I/O fences and 32-bit DMA bounds |
| loongarch64 | Modern Virtio PCI | Bridge/config endian correctness, device IRQ controller routing, address translation and barriers |
| mips, mips64 | Malta modern Virtio PCI | GT64120 native/config/device endian distinctions, KSEG CPU-to-DMA translation, MIPS64 sign extension, uncached mappings and external IRQ path |
| ppc | ppce500 modern Virtio PCI | BookE protected PCI TLB/ATMU windows, inbound DMA aperture, big-endian config index/little-endian Virtio ring fields, MPIC/device IRQ path distinct from DEC |

Use the documented current block apertures only as bring-up evidence, not a
universal board address map. Discover devices/resources through the platform's
actual description (firmware/DT/PCI); add real cache clean/invalidate and IOMMU
contracts before physical-machine support. Acquire/release device barriers are
not substitutes for cache maintenance. Virtio descriptors use specified endian
formats independent of CPU endian; handle legacy formats only when explicitly
negotiated and tested.

Initial NIC feature negotiation: MAC/status/MTU where supported, split queues,
no checksum/GSO/TSO/RSS/multiqueue offload until software paths are correct. Validate
used IDs, lengths, chained/indirect descriptors, ring wrap and device feature
changes. Later offloads must have independent software equivalence tests and
fall back when negotiation rejects them. Minimum one hardware-free host adapter
and one real QEMU Virtio NIC adapter share the same protocol ingress. Physical
NIC families, Wi-Fi and Linux-adapted drivers are separate OS work packages.

## 6. Required Internet end-host protocol profile

Maintain a requirements matrix with RFC section, MUST/SHOULD decision, code owner,
test and known deviation. The following is engineering scope, not a substitute
for that matrix. References below are reading targets, not externally verified
conformance assertions.

| Layer | Required behavior before the core host gate |
| --- | --- |
| Ethernet | Validate minimum/maximum frame lengths, destination filtering, broadcast/multicast and EtherType; software bounds before header reads; explicit FCS/offload ownership. VLAN configuration is optional, but tagged traffic must be safely accepted under configured support or rejected. |
| ARP / IPv4 addressing | Wire ARP request/reply and neighbor resolution with incomplete/reachable/stale/probe/failure state, retries and bounded pending packets; validate sender/address context; expire entries; address-conflict detection and gratuitous announcements with rate limits. Avoid infinite queues or trusting arbitrary unsolicited claims as permanent routes. |
| IPv4 | Checked version/IHL/total length/checksum/options, TTL and local-address semantics; routing/source selection; broadcast/multicast delivery restrictions; bounded fragment reassembly, IDs, expiry, duplicate/overlap policy; DF/MTU errors and ICMP feedback. Generate fragments for supported local datagram sends when policy permits, never silently slice one datagram into independent messages. |
| IPv6 | Base/extension-header parsing with bounded chain/work budget, hop limit, scope/source selection, link-local and global addresses, ND/NUD, router discovery, DAD, SLAAC lifetimes and MLD membership needed by host multicast. RA/redirect policy is per interface; validate ND hop limit and options, reject malformed/overlapping fragments and honor source-only fragmentation rules. Extension-header limits and unsupported features need explicit deviations. |
| ICMPv4 / ICMPv6 | Echo and required destination-unreachable, time-exceeded, parameter-problem and Packet Too Big/fragmentation-needed handling. Validate quoted transport context before applying errors/PMTU; rate-limit generated errors and never create error loops. Do not blanket-drop ICMPv6 or break ND/PMTUD. |
| MTU / fragmentation | Per-destination PMTU with floor/ceiling/expiry, route-change invalidation, validated ICMP updates and black-hole recovery; TCP segmentation by effective MSS. Bounded reassembly per peer/interface and globally, monotonic expiry and overlap rejection. Distinguish IPv4 DF behavior and IPv6 PMTUD; test tunneled/small-MTU paths and source fragment/reassembly limits. |
| UDP | Correct port/address/interface demultiplexing, wildcard and connected sockets, ephemeral allocation/collision handling, broadcast/multicast permission/membership, length and pseudo-header checksums. IPv6 mandatory UDP checksum rules are separate from allowed IPv4 zero checksums. Preserve datagram boundaries, zero-length messages, truncation metadata and asynchronous ICMP errors. |
| TCP connection state | Real active/passive three-way handshake, SYN/backlog limits, simultaneous open where required, sequence arithmetic across wrap, validation of ACK/RST/SYN, retransmitted/duplicate segments, established data, half-close, FIN/retransmission, reset, TIME_WAIT and abort. Accept only completed queued connections; no synthetic success. |
| TCP data/recovery | Reassembly/out-of-order and duplicate handling, cumulative ACK, delayed ACK, MSS, peer receive window, zero-window probes/persist, receive-buffer flow control, retransmission timer/backoff, RTT estimation, slow start/congestion avoidance/fast retransmit/recovery, SACK negotiation and bounded scoreboard/recovery, window scaling and timestamps/PAWS. Keep congestion window distinct from flow-control window. Test Nagle/NO_DELAY and application-limited traffic. |
| TCP urgent data | Implement and document the urgent-pointer interpretation, `MSG_OOB`, `SO_OOBINLINE`, `sockatmark`, exceptional readiness and applicable `SIGURG` ownership/delivery. Qualify RFC 6093 and selected Linux-personality compatibility, including mark movement and overwritten urgent data; do not confuse TCP urgent data with an independent reliable message channel. |
| TCP robustness | Unpredictable initial sequence numbers/ephemeral choices from a real CSPRNG, challenge/validation behavior against blind injection, SYN-flood and reassembly budget controls, bounded retransmission/dead peer policy, optional keepalive with explicit defaults. ECN and newer congestion algorithms may follow the conservative baseline, with accurate capability negotiation. |

For IPv6 source fragments and unusual IPv4 options, define exact supported
behavior against host requirements rather than declaring them irrelevant after
a simple HTTP success. IGMP/MLD host membership needed by configured multicast
is distinct from optional multicast routing. Jumbograms, raw packet injection,
advanced TCP algorithms, MPTCP and accelerated zero-copy can be deferred with
explicit unsupported behavior. An RFC-complete claim requires review beyond this
list, including current updates and errata.

Kernel ingress filters run before costly allocation. Keep parser bounds,
anti-spoof policy, fragment quotas, transport state validation and rate limiting
separate. A privileged OS policy service installs rules atomically; default
policy permits configured outgoing traffic and required discovery/error control,
while services expose listeners deliberately. Start with stateless host rules
and a bounded state tracker if needed; NAT, forwarding and firewall-as-router
features are optional and do not block an end host. Filters and debug logs must
not reveal payloads or secrets by default.

## 7. Native socket and readiness contract

Extend the canonical open-file description with a typed socket endpoint
reference (or a common pollable open-resource abstraction). Never allocate a
second unrelated fd namespace. Descriptor references survive dup/fork, respect
per-fd CLOEXEC, and close on process exit. Shared O_NONBLOCK belongs to the open
file description; fd-number reuse must not deliver old completion events to a
new endpoint. Keep protocol objects alive for retransmission/TIME_WAIT without
keeping a dead process/fd alive.

Initial ABI: socket/socketpair, bind, connect, listen(backlog), accept/accept4,
getsockname/getpeername, send/recv/sendto/recvfrom/sendmsg/recvmsg, shutdown,
getsockopt/setsockopt, plus existing read/write/readv/writev/close/dup/fcntl.
Use project C UAPI numbers/layouts deliberately, not another architecture's Linux
socketcall convention. Define `socklen_t`, sockaddr families, IPv6 scope IDs,
ancillary alignment and fixed-width 64-bit times explicitly for ILP32/LP64 and
both endian families. Copy and validate complete control structures before
side effects; handle length addition overflow and bounds for every iovec/cmsg.
Never DMA or retain raw user addresses after a syscall returns.

The Linux personality must translate each supported architecture's actual
syscall numbering, argument/return/error registers, direct versus multiplexed
socket entry, structure padding, cmsg alignment, time64 calls and ioctl constants.
Do not feed x86_64 numbers unchanged to musl on another CPU. Pin the musl version
and its target ABI for every profile, including MIPS O32/n64 and PPC's selected
C ABI, then inspect emitted calls. Mixed native/personality processes share
kernel endpoint state through explicit translations, never reinterpret-cast
foreign sockaddr/msghdr layouts. Static musl precedes shared musl/dynamic loading;
native API smoke and musl socket/resolver suites remain distinct acceptance.

The current 4096-byte user copy buffer cannot silently shorten a UDP send into
a different datagram. Either admit the complete datagram using bounded chained
buffers or return EMSGSIZE before enqueue. Streams can return a short byte count;
that success means queued bytes, not acknowledged delivery. A received datagram
is consumed once; truncation/MSG_TRUNC, MSG_PEEK, source-address length and EFAULT
behavior must be specified and tested. Allocate/copy destination metadata before
irreversibly dequeuing when possible. EOF on a stream differs from a valid
zero-length UDP/AF_UNIX datagram.

| Condition | Required observable behavior |
| --- | --- |
| No readable data / full send queue | Block on a cancellable wait or EAGAIN for nonblocking; never busy-spin or pretend success |
| Nonblocking connect | EINPROGRESS; readiness on completion/failure, then SO_ERROR reports the result; handle repeated connect/EALREADY and timeout |
| Accepted queue empty | Blocking accept waits; nonblocking returns EAGAIN; accepted descriptor flags follow documented accept/accept4 semantics |
| Peer orderly stream close | Drain queued bytes then read returns zero; half-close retains the other direction |
| Write after shutdown/peer close | EPIPE and SIGPIPE unless suppressed; do not claim POSIX behavior until real signal delivery exists |
| Resource exhaustion | ENOBUFS/ENOMEM for packet/object pressure, EMFILE/ENFILE for fd/global limits; queue pressure is not permission failure |
| Route/interface/peer failures | Distinguish ENETUNREACH, EHOSTUNREACH, ENETDOWN, ECONNREFUSED, ECONNRESET, ETIMEDOUT; retain pending asynchronous error and report via SO_ERROR/readiness consistently |
| Incorrect fd/type/address | EBADF, ENOTSOCK, EAFNOSUPPORT/EPROTONOSUPPORT, EADDRINUSE/EADDRNOTAVAIL, EINVAL, EMSGSIZE; never map all failures to ENOSYS |
| Signal/cancel/timeout races | Partial bytes already transferred win over EINTR as specified; no duplicate send on syscall restart; wakeup after close cannot use freed state |
| TCP urgent mark / data | `MSG_OOB`, `SO_OOBINLINE` and `sockatmark` agree on urgent-byte placement; `select` exceptional conditions / `POLLPRI` and configured `SIGURG` delivery track the defined state without consuming ordinary stream bytes incorrectly |

Implement `poll` and `select` from the same readiness provider used by files,
pipes, sockets and future device events. `select` has explicit FD_SETSIZE bounds;
`poll` reports invalid fds and hangup/error independently of requested bits.
Use check-register-recheck and deadline-based blocking to prevent missed events.
Add pselect/ppoll when atomic signal-mask semantics exist. Epoll is a useful Linux
extension, not a POSIX requirement: implement level-triggered first, then
edge-triggered and one-shot with documented rearm/dup/close semantics. AF_UNIX
is the service-plane milestone, not a dependency on Ethernet: pathname-bound
stream/datagram/socketpair first, then seqpacket, peer credentials and SCM_RIGHTS.
Rights transfer retains validated resource references, limits queued descriptors
and accounts cycles; never serialize a process's fd integer as authority.

Pathname AF_UNIX sockets require VFS socket nodes, parent search/write access,
owner/mode checks, unlink-vs-open lifetime and stale-endpoint recovery. Peer
credentials come from the kernel at the specified connection/message boundary;
user-provided sender fields are not authentication. Abstract namespace support
is optional. Granting access to a socket does not grant arbitrary service
operations: versioned service protocols still authorize requests.

## 8. Native PID 1 and system services

### 8.1 Kernel prerequisites and migration

Introduce an explicit designated user init/reaper with user-visible PID 1.
Choose and document a stable namespace solution rather than relying on boot
allocation order; preferably separate internal kernel task IDs from user PID
allocation while keeping one authoritative process owner. Define reparenting,
subreaper behavior, wait-any, zombies and init death. Replace parent-zero auto
reaping for user descendants only after native init handles them. Kernel-owned
workers retain their own lifecycle. Tests for previous orphan collection must
be migrated to the new intended policy, not deleted.

Required native mechanisms: real process signals and masks/default actions,
SIGCHLD and waitpid/waitid/WNOHANG, sessions/process groups, kill permission,
setsid/setpgid, credential/group changes, controlling TTY/job-control policy,
O_NONBLOCK/CLOEXEC/pipe2, AF_UNIX/socketpair, poll and real sleeps/deadlines.
Provide a generation-safe process handle for supervisor control before allowing
PID reuse; a delayed stop must not kill an unrelated new process. General VM,
reliable allocation and larger/configurable process/fd/image bounds precede
large library/daemon ports. None is implemented by storing a signal bitset or
thread record alone.

Keep `/init` small and continuously alive. It owns service children, reaps all
exits, and runs a pollable event loop. Services remain in the foreground, without
double-fork or pidfile discovery. Launch is fork/exec with explicit argv/env,
working directory, stdio, credentials and inherited-fd allowlist; report exec
failure through a CLOEXEC error pipe. A child PID alone does not mean ready.
If init fails, the kernel enters a documented recovery/reboot path rather than
silently returning to the debug shell as a healthy system.

### 8.2 Service state and policy

Use a bounded declarative manifest with `Exec`, `User/Group`, dependency names,
ordering, readiness mode, restart policy, limits, stop deadline and required
resources. Parse no shell by default; command lines are explicit argument
arrays. Validate the graph and duplicate names before changing the running
system. `Requires`, `Wants`, `After` and readiness are distinct: order does not
prove availability, and optional network loss must not stop local login.

States: disabled -> queued -> starting -> ready -> stopping -> stopped; exits
can enter failed/backoff with a reason/generation. Readiness is an inherited
notify socket with peer credentials plus per-launch token, or a documented
one-shot successful exit. Add socket activation later where justified. Never
infer readiness from a log string, fixed sleep or a TCP port unrelated to the
child. Bound startup time, restart burst/window and exponential backoff with
jitter; reset after a stable period. Track exit code/signal, last readiness and
resource use. Crash loops isolate the unit and preserve local recovery access.

Reload validates a new configuration and swaps it transactionally. Changes
requiring restart are explicit. Separate “configured,” “link up,” “address
usable,” “default route available” and “DNS responding” capabilities; there is
no single universal `network-online` truth. Dependents handle lost capabilities
at runtime, not only during boot.

Shutdown stops accepting new sessions/updates, notifies and stops units in
reverse dependency order, sends TERM then KILL after bounded deadlines, reaps
children, drains bounded logs, synchronizes filesystems and quiesces devices
before poweroff/reboot. Failures are recorded; critical sync failure must not be
reported as a clean shutdown. Keep a rescue console available until its final
phase. No network, DNS or logging dependency may make shutdown wait forever.

### 8.3 Service inventory

Names are proposed and can change without freezing a system ABI.

| Service | Responsibility, authority and readiness |
| --- | --- |
| init / svcctl | Supervisor and authenticated local control CLI; smallest privileged process; readiness after manifest validation/control endpoint, not after every optional service |
| logd | Per-service stdout/stderr collectors plus structured AF_UNIX input; kernel supplies trusted source identity/boot ID/monotonic timestamps; bounded queues, rate limits, lost-record counts and storage rotation; ready when sinks can accept bounded records |
| devd | Device event snapshot/reconciliation, stable OS naming and driver load policy; kernel validates device resource ownership; minimal privileged helper for operations, unprivileged policy where practical |
| netd | Interface/address/route policy and per-interface DHCPv4/DHCPv6/RA state; privileged control helper with narrow request schema; atomically publish validated resolver configuration; report local usable-address/route capabilities separately |
| resolverd | Local DNS cache on loopback UDP/TCP, reached by stock musl through `/etc/resolv.conf`; `/etc/hosts` remains a libc input; unprivileged network client after narrow bind setup; ready on the local endpoint even while upstream is unavailable; no private libc IPC hook |
| timed | Select/reach time sources, validate samples and request bounded clock corrections; parser/network client unprivileged, narrow clock-set helper; report unsynchronized/synchronized explicitly |
| storaged / mount / fsck | Root/volume discovery, mount policy, busy checks, offline filesystem repair and orderly unmount; pinned device identity and narrowly privileged operations; readiness distinguishes accessible root, writable volumes and rescue-only state |
| jobd / at / cron | Bounded periodic and one-shot jobs under submitter credentials; implement the selected POSIX batch/periodic scheduling option inventory; separate calendar policy from monotonic execution deadlines, with explicit missed-run and overlap rules |
| random-seed | Read/mix an OS-owned seed through the Kernel CSPRNG API, rotate and durably store the next seed; seed files are untrusted input and do not independently establish credited entropy or RNG readiness |
| accountd / login / getty | Protected account database, authentication/rate limits and per-console login; terminal setup independent of networking; credential-change helper creates an authenticated session |
| session manager | User session lifecycle, environment/runtime directory, desktop or shell and child cleanup; unprivileged per-user supervisor; graphical greeter is a client of authentication, not the authority |
| seatd / display lease broker | Minimal OS authority for authenticated seat membership and display/input device leases; kernel enforces generation-tagged handles and revocation; compositor receives only its seat's fds and no generic driver/configuration privilege |
| updated / recovery tool | Signed manifest/package validation, staging, compatibility check, health-gated activation and rollback; network fetching/parser unprivileged, narrow installation authority; never required for ordinary boot |
| ssh / sshd | Qualified secure remote administration client/server package in the core host target; server installed but disabled until configured; host keys, authentication policy and privilege separation are OS responsibilities, not kernel protocols |

Do not turn existing C++ `ServiceRegistry` pointers into a cross-process API.
Define versioned length-prefixed IPC, per-request bounds/cancellation, peer
credentials, explicit capability checks and stable error replies. Service restart
invalidates connection generations; clients reconnect and resynchronize rather
than holding a pointer to prior state. Async dependency notifications carry
sequence IDs and snapshot recovery for drops.

### 8.4 Accounts, sessions, logging and recovery details

Storage policy uses stable device identities and explicit mount dependencies.
Bring up a known-good initramfs/rescue root before writable-volume policy; do not
run mutating fsck on a mounted filesystem. Detect required repair, missing media,
wrong identity and unsupported format features before advertising a writable
mount. Root replacement and mount namespaces use kernel object mechanisms,
while OS chooses root and recovery policy. Shutdown stops writers, flushes and
unmounts in dependency order; a busy root or failed flush enters a documented
recovery path rather than a forced-success report. Port qualified filesystem
utilities instead of putting repair policy into the kernel driver.

The job scheduler inventories `at`, `batch`, `crontab` and any selected POSIX
options with [POSIX/musl](POSIX_MUSL.md). Persist accepted jobs and their owner
securely; use the same credential/fd/environment preparation as other services.
Bound queues, runtime, output and concurrent jobs. Specify timezone/DST and UTC
step behavior, missed runs after downtime, overlap and restart policy. A durable
dispatch record cannot make arbitrary external side effects exactly-once;
document replay/idempotency expectations instead of promising that property.

The entropy-seed service reads only an owner-checked regular file and supplies
bytes as untrusted mixing input unless the kernel's explicit entropy policy
allows a stronger credit. Only the kernel CSPRNG decides readiness. Generate
and rotate seed material after readiness, with restrictive permissions and a
durable replace protocol qualified at M4. A copied image, replayed file or
uncertain shutdown cannot be assumed to provide fresh independent entropy;
fresh platform sources remain necessary. Read-only/no-seed boot waits or fails
secure operations explicitly and preserves local recovery.

Port a maintained SSH client/server with its required cryptography and host-key
verification. The server remains disabled until host keys, authentication and
authorized access are configured; never ship shared image keys or a default
password. Keep parsing/session workers unprivileged, isolate the small privileged
authentication/session operations, rate-limit failures and log without secrets.
Installation is part of the connected managed-host target; enabling a public
listener is distribution/admin policy. SSH does not add a kernel SSH protocol.

Move user/account names, home directories and login policy to OS configuration;
keep numeric credentials, permission enforcement and credential transitions in
Kernel. Separate uid/gid from special internal kernel authority. Supply root-owned
account/shadow files, secure initialization, a reviewed password KDF library,
per-attempt timing/rate policy and safe secret input. No compiled default password
or username-toggle authentication. Set groups, gid and uid in a documented safe
order before exec, close all unintended fds, establish session/TTY, set umask,
validate home ownership and constrain environment. Native system calls must
prevent regaining dropped privilege. Use capabilities/least authority when
supported, not the current GUI credential selection as a security boundary.

The session manager owns a per-user runtime directory (0700, correct uid),
Wayland socket, compositor/app process groups and their inherited-fd allowlist.
The greeter authenticates through the login authority; the authority returns a
session handle bound to credentials and seat, not a forgeable username. `seatd`
mediates activation/switching and passes display/input fds through authenticated
SCM_RIGHTS. Kernel display/input UAPI enforces exclusive display ownership,
which seat owns each event stream, buffer bounds and generation-safe revocation.
Wayland clients receive compositor sockets/shared-buffer handles, never raw
input or privileged scanout access. `wl_shm` requires real shared mappings and
descriptor lifetime checks; a shared-ring enum is insufficient.

On compositor crash, logout, seat switch or device removal, revoke display/input
leases, cancel outstanding submissions and prevent a stale duplicate fd from
retaining authority. Keep buffers alive until device completion or quiescence.
Revoke first, then hand ownership to a replacement compositor or kernel rescue
GUI. The rescue GUI and OS compositor must not simultaneously draw into the
same scanout. Loss/recovery notifications are asynchronous and recoverable;
process death itself triggers kernel lease cleanup even if `seatd` is down.
Test two users/seats, unauthorized lease transfer, supervisor/broker restart,
compositor hang and disconnect during presentation. The display server stays
unprivileged; UID 0 or direct pointers into kernel GUI objects are not required
for normal composition.

Log records have monotonic and optional UTC timestamps with synchronization
state. Escape control characters, avoid secrets, keep per-source quotas and do
not block the network executor on log storage. Rotate with the filesystem's
actual durable semantics; a rename implementation without crash-atomic journal
recovery is not an atomic update guarantee. Handle ENOSPC, read-only disks,
slow sinks, logd restart and early-boot buffered loss visibly.

Persist configuration/leases with versioning and explicit fsync. Current bounded
non-journalled ext4 requires offline recovery after interrupted mutations; never
apply an update directly to the only bootable image assuming crash atomicity.
Prefer an inactive image/slot or staged generation plus validated activation
record and retained previous generation. Test interrupted download, metadata
validation failure, power loss at every durable step and incompatible Kernel SDK
or module ABI. Define trusted rollback policy and key rotation before claiming
secure updates. Rescue boot uses known-good immutable assets, offline fsck and
manual network configuration; it must work without DNS or remote authentication.

## 9. Network configuration, names and time services

- DHCPv4: discover/offer/request/ack/nak, transaction and server validation,
  option-length parser, address conflict checks, lease T1/T2/expiry, renew/rebind,
  reboot reuse and link-change invalidation. Persist remaining lease state
  conservatively when no trusted RTC exists; do not treat an expired address as
  permanent after restart. Renew failure should withdraw only expired state.
- IPv6: kernel processes validated ND/RA and maintains protocol lifetimes; OS
  policy selects allowed RA sources/modes, SLAAC privacy/stable address policy,
  DHCPv6 client behavior and DNS source precedence. DAD failure, prefix/router
  expiry, renumbering, multiple routers and link-local scope must reach netd.
  SLAAC alone does not provide every DNS/configuration option.
- Resolver: keep musl's resolver unchanged as far as possible. Applications use
  ordinary `getaddrinfo`/`freeaddrinfo`/`getnameinfo`, musl's numeric/hosts handling
  and `/etc/resolv.conf`; the default nameserver is resolverd on loopback DNS
  over UDP/TCP, not a custom libc IPC interface. Qualify the pinned musl version's
  search/options/error behavior. The daemon validates query/response IDs and
  sources, uses unpredictable ports/IDs, bounds decompression/CNAME traversal,
  supports EDNS size limits, UDP truncation -> TCP fallback, IPv4/IPv6 upstreams,
  positive/negative TTL caching and cancellation. Retry across upstreams with
  monotonic deadlines and bounds against poisoning/floods. DNSSEC and encrypted
  DNS are separate extensions without implied validation flags.
- Resolver configuration: netd selects static, DHCP and RA/RDNSS inputs through
  explicit precedence and interface/lease generations. Publish the loopback
  libc configuration and daemon upstream state without making resolverd query
  its own loopback address as an upstream. Stage and validate a complete new
  generation, then atomically replace root-owned configuration; reject unsafe
  symlinks/ownership and never expose partially written server/search lists.
  Keep the libc loopback setting stable across upstream changes; publish the
  daemon's upstream set as one generation. If a change also affects libc search
  settings, define activation and rollback explicitly rather than assuming two
  file renames form one transaction. Readers hold one version through a request.
  Runtime lease state may live in
  `/run`; persisted admin configuration needs file and parent-directory fsync
  plus M4 journal/crash-recovery qualification. Until that gate, retain a
  known-good immutable fallback and explicitly limit power-loss guarantees.
  Link/lease expiry withdraws only its own source generation; daemon restart
  reloads a validated snapshot. Offline upstreams do not prevent local login.
- Time: bootstrap from platform RTC/explicit administrator policy, then use a
  reviewed NTP client with sane offset/delay/outlier bounds and privilege
  separation. Never step monotonic time. Distinguish unsynchronized UTC from
  trusted certificate-validating time; handle NTS/TLS bootstrap deliberately,
  rather than disabling certificate validation when the clock is wrong.
- Security entropy: add a real kernel CSPRNG with readiness/error semantics,
  reseeding and audited entropy sources before network-facing authentication,
  DNS spoof resistance, TCP sequence security, password salts or TLS. Deterministic
  seeds remain test-only. Early services may wait or explicitly fail secure
  operations; they must not silently use the model xorshift.

## 10. Phased delivery and acceptance

Every phase produces code in the correct repository, artifact/ABI changes,
reproduction commands, resource limits and results labeled by scope. Preserve
the ten-profile build matrix throughout. Runtime coverage expands explicitly;
unsupported execution is reported as a gap, never hidden by dropping a profile.
A packet-capture host test cannot substitute for checked native user syscalls.

The N identifiers below subdivide the overall roadmap rather than replace it:

| Global milestone | Dependencies/deliverables relevant here |
| --- | --- |
| M0: specification baseline | This source audit, protocol requirements and language-compatible engine decision (N0) |
| M1: resource foundation | Owned allocation, real blocked waits, monotonic deadlines and entropy prerequisites for NIC/protocol execution |
| M2: common OS objects | Pollable resource identity, credentials, AF_UNIX, descriptor passing and authenticated service/TTY channels (part of N2) |
| M3: libc substrate | Process-control/reaping, threads/signals and per-architecture Linux personality; static musl acceptance needed by real services |
| M4: durable default root | Durable service configuration/log/update policy; retain current offline-recovery limitation until its gate passes |
| M5: useful POSIX userland | Shared-library/runtime compatibility and broad socket/client-library interfaces; do not make small static network probes depend on the dynamic loader |
| M6: connected host | N1 and N3–N5: real devices and complete documented end-host profile |
| M7: managed system | N2/N6: supervisor, accounts, net/DNS/time, storage/jobs/entropy/SSH policy, hotplug/session brokers and recovery |
| M8: isolated graphics | Seat/display lease authority and user-session lifecycle for the isolated Wayland desktop |
| M9: daily desktop | Authenticated service APIs, durable application policy and network access for isolated clients |
| M10: ext4 breadth | Additional storage capabilities follow their own requirements; service durability cannot wait on unrelated optional filesystem features |
| M11: execution breadth | N7: real concurrent execution, driver lifecycle/loading, physical DMA/IRQ validation |
| M12: full target | Protocol requirements closure, native and Linux-personality semantics, independent interop/adversarial evidence and documented deviations |

These are integration gates, not a serial work schedule. M2/M3 depend on M1 and
shared object contracts; M4 follows M2, and M6 integrates with the M3 user ABI.
M7 requires M4 durability plus M5 userland and M6 connectivity, although minimal
init/reaping and independent local services start earlier. M8 depends on M5,
and M9 joins M7/M8. M11 concurrency/lifetime design starts at M1 rather than
being retrofitted after networking. The master dependency graph is authoritative.

| Phase | Deliverable and dependency | Exit gate |
| --- | --- | --- |
| N0: contracts and engine decision | Requirements/gap matrix, CSPRNG/clock/allocator prerequisites, device/socket ownership, library evaluation, model naming | Reviewed design and pinned dependency decision; exact memory/stack/ABI budgets; no Internet-host completion claim |
| N1: executor and device path | Bounded packet pool, real timer/deferred work, OS Virtio NIC, separate controlled peer; polling first then real IRQ | RX/TX bytes verified by an external capture/peer, wrap/pressure/reset/teardown tests; all ten QEMU transports; no synthetic receive injection in device acceptance |
| N2: local IPC and supervisor base | Canonical pollable fd resources, AF_UNIX/socketpair, signals/process control and persistent init/reaper | Real native two-process transfer, peer authentication, fd lifetime/wakeup tests; init reaps descendants and restarts a crashed foreground service on all ten profiles |
| N3: static IPv4/UDP | Ethernet/ARP, IPv4/ICMP, routes, fragments/PMTU, native UDP/readiness | Two guests and independent Linux/BSD peer exchange bytes; demultiplexing, MTU, checksums, errors and loss tests; actual socket syscalls, not kernel-only probes |
| N4: reliable TCP | Handshake, queues, all close states, flow/congestion control, RTO/RTT, SACK/window scaling/timestamps | Byte-exact bidirectional transfers and state/packet traces under loss/reordering/duplication/zero window; no leaked sockets after stress; idle timers advance |
| N5: complete dual-stack core | IPv6/ND/RA/DAD/SLAAC/MLD, IPv6 transport/PMTU, DHCP/resolver/time, host filters | Requirements matrix has no unresolved mandatory host-profile gaps; IPv4-only/IPv6-only/dual-stack routed peers, reboot/renumbering and safe fallback pass; no physical claim yet |
| N6: supervised distribution | service graph/readiness, accounts/login, logging/hotplug/session/privilege separation, shutdown and recovery | Native service failure/privilege tests, no root-fd leaks, orderly and forced shutdown, offline/rescue boot, durable configuration/update interruption tests |
| N7: performance and hardware | Measured batching/offloads, multiple queues, hardware SMP, noncoherent DMA/IOMMU and selected physical NICs | Independent per-platform evidence for actual IRQ/DMA/SMP; compare correctness and latency under pressure before/after tuning |

N1 and N2 can progress independently after shared timer/resource contracts.
AF_UNIX and local login must work without N3–N5. Static-address network tests
precede DHCP/DNS; a failed DHCP server must not obscure a broken packet path.
A minimal supervisor starts early in N2; the complete service policy in N6 is
not a reason to defer real orphan handling until after networking.

### 10.1 Protocol and user-space acceptance

Use deterministic host packet/timer adapters for model testing, then QEMU with
explicit Virtio NIC and isolated TAP/bridge or a controlled socket backend.
No public network is required for correctness. Rootless QEMU user networking is
useful for smoke tests, but its NAT behavior cannot prove arbitrary incoming
connections, Ethernet/ND, multicast or path-MTU handling. Record topology,
addresses, MTUs, seeds, QEMU/library/toolchain versions and byte/pcap hashes.
Privilege-requiring host network setup is a separate explicit harness step.

Required suites:

1. **Byte/parser tests:** independent wire fixtures/checksums, odd lengths,
   alignment, endian/ILP32, truncated headers, impossible lengths, nested IPv6
   extensions, DNS compression cycles and malformed options. Fuzz parser and
   stateful engine separately with host sanitizers and bounded fake time.
2. **Isolation/demultiplexing:** many socket ports/processes/interfaces, wildcard
   conflicts, connected UDP filtering, privilege-denied raw/config operations,
   bad user pointers/lengths, fork/dup/exec/exit, close/reuse during poll/accept,
   ancillary fds and peer credentials. Prove process A cannot read B's datagram.
3. **Transport traces:** independently generated SYN/ACK/FIN/RST, seq wrap,
   reordered overlapping data, delayed/lost ACK, retransmission/Karn/RTO cases,
   SACK scoreboard limits, zero-window reopening, simultaneous close/TIME_WAIT,
   reset injection, listener overflow and app-not-reading pressure. Verify
   state/packet outcomes, not just a successful connection marker. Exercise
   urgent-pointer interoperability, `MSG_OOB`/`SO_OOBINLINE`, `sockatmark`,
   exceptional readiness and `SIGURG` with and without inline urgent bytes,
   including successive marks, retransmission and concurrent ordinary reads.
4. **Network failure:** cable/link loss, no route, ARP/ND timeout/poison attempts,
   duplicate addresses, bad RA, PMTU decrease/black hole, fragments timed out or
   overlapping, DHCP expiry/NAK, IPv6 prefix withdrawal, DNS truncation/TCP
   fallback and poisoned replies. Bound retries, memory and log generation.
5. **Device failure:** exhausted/short RX buffers, ring wrap, malformed used
   entries, IRQ storms/missed interrupts, reset/hot-unplug with DMA outstanding,
   bus errors, feature negotiation rejection and coexistence with block/input.
   Verify no memory reuse before DMA quiescence and no cross-device BAR damage.
6. **Interop:** independent Linux and BSD endpoints, UDP echo and large
   datagrams, TCP client/server transfers with independent hashes, concurrent
   connects, IPv6-only DNS/HTTP with a reviewed user TLS library when available,
   DHCP/RA from independent implementations and packetdrill-style scripted
   semantics. Packet capture and peer observations must agree with guest logs.
7. **Limits and performance:** zero/near/full pools, global/per-process limits,
   low memory, many idle connections, bounded CPU work under flood, queue fairness,
   latency percentiles and throughput with offloads disabled/enabled. State
   exact workload, memory and drop budgets; do not invent an unmeasured target.

All ten profiles require native socket/basic IPv4/IPv6/TCP/UDP/AF_UNIX and
supervisor smoke coverage before the core host release. Full adversarial suites
run on representative little-endian 64-bit, little-endian 32-bit and big-endian
32/64-bit targets, with targeted reruns on every affected architecture. Each
Virtio bus family requires real device IRQ tests. Physical hardware and SMP
remain separate columns, including explicitly not tested where appropriate.

### 10.2 Service and recovery acceptance

Boot without NIC, disk writes, DNS or correct UTC; local rescue/login must remain
usable. Kill each service before exec, before readiness and after readiness;
verify readiness generation, dependent reaction, restart backoff and no zombie/fd
leaks. Exercise dependency cycles, malicious manifests/IPC, blocked children,
service fork trees, reused PIDs, log floods, full disk, credential drop and
unauthorized control attempts. Disconnect DHCP/DNS/time during operation and
confirm bounded degradation without restarting unrelated services.

Test users with different credentials accessing service sockets/files and
passing descriptors. Authentication failure cannot launch a session or leak
secrets; changing GUI user selection alone confers no authority. A session's
termination closes its devices/IPC and descendants without killing other users.
Attempt to reuse revoked display/input handles from surviving dup/fork peers;
kernel must reject access even when a broker/compositor has restarted. Verify
seat switch isolates input, rescue display handoff is exclusive and ordinary
Wayland clients cannot acquire another session's devices or runtime socket.
Shutdown must interrupt blocked poll/connect/wait and bound a hung unit. Update
power-loss tests use scratch images at every persistence boundary, then boot
known-good recovery and verify rollback/offline repair. A clean-run fsync check
alone does not establish power-failure atomicity.

Exercise storage repair refusal on mounted/busy volumes, missing root media and
rescue selection; cron/at jobs across restart, DST/clock changes and privilege
denial; cloned/stale/unwritable random-seed files with no false RNG readiness;
and SSH disabled-by-default, key initialization, wrong-host-key rejection,
failed authentication and credential-isolated remote sessions. Resolver tests
use unmodified musl clients, hosts/numeric lookup, loopback UDP/TCP, daemon
restart, malformed replies and concurrent netd generation updates; readers must
never observe a partial configuration or query the daemon recursively.

Proposed result labels distinguish `scope=model`, `scope=native-qemu`,
`scope=device-qemu`, `scope=interop`, `scope=physical` and `scope=smp`. Include
architecture, transport, peer, engine/version and exercised feature list; never
reuse the old loopback-model marker as evidence for an Internet stack.

## 11. Deferred capabilities and completion reporting

Optional work after the core host: IP forwarding/router protocols, bridge/NAT,
VPN/IPsec, Wi-Fi association/authentication/regulatory policy, Bluetooth,
cellular, advanced firewall scripting/eBPF, multicast routing, containers/network
namespaces, broad NIC families, Linux-driver API coverage, advanced congestion
algorithms, MPTCP, RDMA and arbitrary application servers such as a web server.
Qualified secure remote tools and a configured-only SSH server are part of the
core managed-host target, with their policies described above.
Basic packet security, required ICMP/ND, resource limits and process isolation
are core requirements, not optional because the first deployment is QEMU.

At every release list: supported protocols/options and explicit deviations;
user calls and errors; architecture/device/IRQ/DMA limits; native vs modeled
services; tested peer/topology; measured resource limits; known recovery and
security gaps. “TCP connects,” “network online,” “PID 1,” “POSIX-compatible,”
“secure login” and “driver compatibility” each require their own evidence.

## 12. External reading and decision references

These are official specification or upstream-project URLs supplied as planning
references. They were **not fetched or independently verified in this task**.
No external conformance, current release, maintenance status or license claim is
being made. Before implementation, read the current documents, updates/errata and
candidate source, then record section-level requirements and decisions.

| Subject | References to review |
| --- | --- |
| IPv4 host requirements, IPv4/ARP | [RFC 1122](https://www.rfc-editor.org/rfc/rfc1122), [RFC 791](https://www.rfc-editor.org/rfc/rfc791), [RFC 826](https://www.rfc-editor.org/rfc/rfc826), [RFC 5227](https://www.rfc-editor.org/rfc/rfc5227) |
| IPv6 host and addressing | [RFC 8504](https://www.rfc-editor.org/rfc/rfc8504), [RFC 8200](https://www.rfc-editor.org/rfc/rfc8200), [RFC 4291](https://www.rfc-editor.org/rfc/rfc4291), [RFC 6724](https://www.rfc-editor.org/rfc/rfc6724) |
| ND, SLAAC, multicast | [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861), [RFC 4862](https://www.rfc-editor.org/rfc/rfc4862), [RFC 7217](https://www.rfc-editor.org/rfc/rfc7217), [RFC 8981](https://www.rfc-editor.org/rfc/rfc8981), [RFC 3376](https://www.rfc-editor.org/rfc/rfc3376), [RFC 3810](https://www.rfc-editor.org/rfc/rfc3810) |
| ICMP, MTU, fragments | [RFC 792](https://www.rfc-editor.org/rfc/rfc792), [RFC 4443](https://www.rfc-editor.org/rfc/rfc4443), [RFC 1191](https://www.rfc-editor.org/rfc/rfc1191), [RFC 8201](https://www.rfc-editor.org/rfc/rfc8201), [RFC 8899](https://www.rfc-editor.org/rfc/rfc8899), [RFC 5722](https://www.rfc-editor.org/rfc/rfc5722), [RFC 6946](https://www.rfc-editor.org/rfc/rfc6946) |
| UDP | [RFC 768](https://www.rfc-editor.org/rfc/rfc768), [RFC 8085](https://www.rfc-editor.org/rfc/rfc8085) |
| TCP base, congestion, timers | [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293), [RFC 5681](https://www.rfc-editor.org/rfc/rfc5681), [RFC 6298](https://www.rfc-editor.org/rfc/rfc6298) |
| TCP extensions and robustness | [RFC 2018](https://www.rfc-editor.org/rfc/rfc2018), [RFC 6675](https://www.rfc-editor.org/rfc/rfc6675), [RFC 7323](https://www.rfc-editor.org/rfc/rfc7323), [RFC 5961](https://www.rfc-editor.org/rfc/rfc5961), [RFC 6528](https://www.rfc-editor.org/rfc/rfc6528), [RFC 6093](https://www.rfc-editor.org/rfc/rfc6093) |
| DHCP and DNS configuration | [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131), [RFC 2132](https://www.rfc-editor.org/rfc/rfc2132), [RFC 8415](https://www.rfc-editor.org/rfc/rfc8415), [RFC 8106](https://www.rfc-editor.org/rfc/rfc8106) |
| DNS resolver behavior/security | [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034), [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035), [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308), [RFC 6891](https://www.rfc-editor.org/rfc/rfc6891), [RFC 7766](https://www.rfc-editor.org/rfc/rfc7766), [RFC 5452](https://www.rfc-editor.org/rfc/rfc5452); DNSSEC extension: [RFC 4033](https://www.rfc-editor.org/rfc/rfc4033) and its related documents |
| Time, entropy and TLS | [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905), [RFC 8915](https://www.rfc-editor.org/rfc/rfc8915), [RFC 4086](https://www.rfc-editor.org/rfc/rfc4086), [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446) |
| Native POSIX API behavior | [The Open Group POSIX specifications](https://pubs.opengroup.org/onlinepubs/9799919799/); Linux extensions require a separate compatibility decision |
| Virtio network/device contract | [OASIS Virtio 1.3 specification](https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html); pin the implemented transport/features and review normative endian/ordering requirements |
| Engine comparison/reference spike | [lwIP upstream documentation](https://www.nongnu.org/lwip/), [upstream source](https://git.savannah.nongnu.org/cgit/lwip.git/); evaluation does not select a C kernel dependency or waive the C++23 contract |
| User runtime and session integration | [musl upstream](https://musl.libc.org/), [Wayland upstream](https://wayland.freedesktop.org/), [Wayland protocol documentation](https://wayland.freedesktop.org/docs/html/), [seatd upstream](https://git.sr.ht/~kennylevinsen/seatd); references for interface/porting evaluation, not a claim these components already run here |
| Scripted transport testing | [packetdrill upstream](https://github.com/google/packetdrill); evaluate harness portability and licensing before reuse |
