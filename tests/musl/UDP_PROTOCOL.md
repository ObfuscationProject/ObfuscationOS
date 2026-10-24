# Explicit musl UDP fixture protocol

`xmake musl-udp-probe --arch=ARCH --musl-build=DIR --toolchain=DIR --out=NEW_DIR`
builds the public-libc probe for x86_64, aarch64, rv64 or loongarch64. Add
`--capture-compile-dependencies` to record system headers from the same `-MD`
invocation that produces its object. Without that option the existing builder
commands and manifest shape are retained. Both paths compile only; neither
packages nor executes a guest. The ten-native architecture tables are unchanged.

The nondefault `app-musl-udp-runner` target builds a native parent against an
explicit validated Kernel SDK. Future explicit fixture packaging must install
its child at `/bin/musl-udp-probe`. The native parent forks once, execs the musl
image and checks the actual child PID and exit status. Normal init, apps and
rootfs policy do not select either fixture.

Guest execution requires composition with the independently admitted bind-zero
runtime successor and a matching, explicitly exported SDK. The runtime parent
used to author this source rejects bind(port=0); compilation is not evidence
that this phase executes. A historical SDK used only to compile the unchanged
native runner UAPI is separate from final product links.

The guest uses IPv4 local `192.0.2.2:54322` and peer `192.0.2.1:12345`, matching
the existing static link's MAC/IP policy. Every serial record is a complete
newline-terminated line. An external ARP/Ethernet/IPv4/UDP peer waits for the
exact ready marker before injecting the next datagram. Receive retries are
bounded to 5000 one-millisecond sleeps and accept only EAGAIN/EWOULDBLOCK while
waiting. Source address, source port, sockaddr length and expected bytes are
checked by the guest. It never uses connect, getsockname, poll or blocking UDP.

| Exact ready record | Peer action and guest expectation |
| --- | --- |
| `MUSL_UDP stage=basic-ready port=54322` | Request ARP and verify the reply; send `GO:BASIC` to 54322, observe outbound `MUSL:BASIC`, reply `ACK:BASIC`. |
| `MUSL_UDP stage=peek-ready` | Send `PEEK-DATA` (9 bytes). Guest checks 3-byte PEEK, PEEK\|TRUNC returning 9, then TRUNC returning 9 and consuming. |
| `MUSL_UDP stage=short-ready` | Send `SHORT-DATA` (10 bytes). Ordinary 3-byte receive returns `SHO`, consumes and leaves EAGAIN. |
| `MUSL_UDP stage=zero-ready` | Send an empty datagram; observe one outbound empty datagram. Guest checks receive/send return 0 and receive consumption. |
| `MUSL_UDP stage=fault-ready` | Send `F`. Valid payload output is copied before bad source output returns EFAULT; the packet is consumed. |
| `MUSL_UDP stage=peekfault-ready` | Send `P`. Bad source output with PEEK returns EFAULT; a later valid receive obtains P. |
| `MUSL_UDP stage=bind-zero-ready` | Observe `MUSL:BIND0:1`, reply `ACK:BIND0:1` to its source port; observe `MUSL:BIND0:2`, require the same nonzero ephemeral source port and reply `ACK:BIND0:2`. |
| `MUSL_UDP stage=implicit-ready` | Observe `MUSL:AUTO:1`, reply `ACK:AUTO:1` to its source port; observe `MUSL:AUTO:2`, require the same nonzero ephemeral source port and reply `ACK:AUTO:2`. |

Each phase has a corresponding `MUSL_UDP stage=...-pass` line. The final guest
line is `MUSL_UDP stage=pass`, after all descriptors close. The later native
parent line is `MUSL_UDP_RUNNER stage=pass child_status=0`. A fail marker,
unexpected record, extra/missing datagram, incomplete line or nonzero exit must
fail external acceptance. Observing these strings alone does not qualify a NIC,
guest execution, syscall stack or complete milestone. The external observer must
validate full Ethernet/IP/UDP identities, checksums, lengths, bytes and ordering.
Only that observer can qualify the guest's own source-port stability; the guest
does not print a source-port acceptance claim.

The deliberate EFAULT is a source-output failure with valid payload storage.
It occurs after packet selection in the bounded Linux adapter. An invalid
payload interval can fail its preflight before selecting a packet and is not
substituted for this consumption test. PEEK explicitly keeps its selected packet.

Host reference execution may compile this same C source with only
`MUSL_UDP_LOCAL_IPV4=0x7f000001UL` and `MUSL_UDP_PEER_IPV4=0x7f000001UL`, using
host Linux loopback and the host libc. That reference checks the fixture's Linux
expectations; it is neither musl guest execution nor ARP/NIC qualification.

## Explicit external NIC runner

`xmake musl-udp-nic-test --arch=x86_64 --mode=MODE --kernel-sdk=SDK
--image=IMAGE --packaged-child=STAGED_ELF --output=NEW_DIR` runs only an explicit
fixture image. `scripts/test_musl_udp_socket.py` supplies a socket netdev to modern
Virtio PCI and drives the exact protocol above. The existing public-libc app and
native parent remain unchanged; default rootfs policy does not select them.

The observer checks the complete ordered serial chain and seven exact outgoing
wire events: ARP, basic, empty UDP, two bind-zero and two implicit sends. It
checks identifiers 0x9000 through 0x9005, MAC/IP/port identities, lengths,
checksums, payloads and padding. Each dynamic source port must remain nonzero
and stable within its socket lifetime. There is no exact allocator-value or
cross-lifetime source-port distinction requirement. Malformed, missing, extra
or partial Ethernet transport records refuse acceptance.

Success and failure write receipts, serial logs and raw bidirectional captures,
including received partial frame bytes. The runner validates every SDK member
before and after execution and pins the SDK manifest, linked image, staged child,
QEMU, peer, observer and harness at both endpoints. A separate admitted packaging
capsule must establish source/probe manifest to staged child to rootfs archive
to linked image provenance; the runner does not infer that chain from file hashes
or from a Kernel SDK boot-archive receipt. Endpoint equality is not immutable
input history. The final quiet interval is 0.1 seconds, followed by final capture
and serial validation after owned QEMU cleanup; it does not qualify later traffic
or guest shutdown.

`tests/tools/test_musl_udp_observer.py` contains hosted protocol negative controls.
Those controls do not qualify guest instructions or NIC transactions. Actual
execution acceptance is limited to x86_64 static-peer IPv4 nonblocking UDP with
boot-CPU polling. The four supplied musl and ten native source matrices remain
intact. Blocking EINTR/restart, IRQ/SMP, TCP/IPv6, ordinary network services,
physical hardware and complete M0-M12 remain separate gates.

## Nondefault embedded fixture image

Build the existing probe with same-command dependency capture, then configure
the OS with `--musl_udp_child_build=BUILD`, its exact
`--musl_udp_child_manifest_sha256=HASH`, the explicit
`--musl_udp_musl_build=SYSROOT_BUILD` and exact
`--musl_udp_musl_manifest_sha256=HASH`. Building `musl-udp-fixture-image` compiles
the native parent normally against the selected SDK, copies normal staging into
a fresh dedicated fixture root, installs that parent as `/init` and the pinned
public-libc child as `/bin/musl-udp-probe`, then embeds the independently parsed
archive. Default rootfs staging and `distro_image` policy stay unchanged.

`tools/package_musl_udp_fixture.py` compares every archive record, metadata field,
payload and zero padding against the full fixture root. Its receipt binds the
probe/musl manifests and producing command, source, parent/child, root and archive
bytes. The separate image campaign must compare the linked archive symbol bytes
with that archive and pin the ELF and assembled image. Packaging is not code
loading or guest execution; stack and immutable construction closure remain
separate gates. Package outputs must be fresh; previously built attempts are
never overwritten or silently reused.

The observer drains final Ethernet evidence only after successful owned QEMU
reaping, with a 0.25-second and 1-MiB bound. A cleanup failure retains the first
protocol error, cleanup diagnostic and already observed raw/partial captures,
then publishes a failed receipt. It does not continue draining a live producer.

## Actual Linux exec entropy prerequisite

The socket NIC coordinator explicitly supplies the same modern Virtio PCI RNG
backend as the normal distribution QEMU launcher: `rng-random` reading host
`/dev/urandom` and `virtio-rng-pci-non-transitional`. Linux exec must acquire all
16 AT_RANDOM bytes before publishing its image. Without the device, the native
parent correctly observes exec failure; an archive-only native UDP fixture does
not have this Linux-personality requirement.

The observer requires one complete `OK_ENTROPY source=virtio-rng-pci state=ready`
record before fixture start and refuses missing, unavailable, failed, duplicate,
wrapped or unterminated entropy diagnostics. Captures qualify actual device
availability for this exec path, not cryptographic entropy quality. This changes
only external QEMU configuration and observation; the compiled image, static
Linux probe, native parent and Kernel SDK are unchanged.
