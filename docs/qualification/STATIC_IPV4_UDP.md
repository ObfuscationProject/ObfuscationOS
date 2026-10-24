# Static ARP/IPv4/UDP service

`drivers/net/static_udp.hpp` exposes one fixed-peer UDP request/reply endpoint
and a serialized boot-CPU polling service over the OS-owned modern Virtio NIC.
Packet parsing and checksums use the explicitly exported SDK33
`ok/net/wire.hpp`; this OS build does not include or compile Kernel source.

The endpoint replies to the configured peer's Ethernet/IPv4 ARP requests and
checks the source MAC, source/destination IP, UDP ports, checksum and length
before returning `OK:` followed by the request payload. Input is borrowed for
the call; input and output buffers must be disjoint. Request payload is bounded
to 1,469 bytes so the three-byte reply prefix stays within an Ethernet MTU of
1,500. Replies use TTL 64, DF and checked IP/UDP checksums. The single service
requires a present UDP checksum. This policy does not change the Kernel byte
parser's support for valid omitted IPv4 UDP checksums.

Foreign and malformed packets, fragments, options and VLANs are dropped without
a response. No ARP learning, route discovery, socket objects or process syscall
path exists in this static service. The separate SDK33 native UDP socket path
exercises two user processes over the OS-owned Virtio NIC. `StaticUdpService::poll_once` consumes at most one
received frame; a failed transmit is reported to its caller and is not queued
for retransmission. Service and NIC lifetimes are managed by the boot caller;
calls require one serialized context. There is no IRQ, SMP, noncoherent DMA,
runtime unload or physical hardware qualification.

The SDK-only probe uses an external local Ethernet peer in QEMU. Both modes on
all ten Kernel profiles passed exchange, hostile-input, no-NIC and legacy-mode
scenarios. Both directions are captured and checked byte for byte, including
IP and UDP pseudo-header checksums. These are privileged diagnostic images,
not ordinary user socket or desktop networking acceptance. The existing four
ordinary distribution profiles are preserved.

Run with explicit artifacts and a new output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 xmake static-udp-test --arch=x86_64 --mode=debug --kernel-sdk=/path/to/x86_64/debug/sdk --toolchain=/path/to/x86_64-elf --output=/tmp/static-udp-native-v1
```

The generated AF_UNIX peer is local to the test. It does not contact an external
network. Hosted endpoint assertions and image reconstruction remain separate
from the original QEMU execution receipts. General IPv4/IPv6, TCP, a broad
socket API, configuration, services and a usable desktop network remain
implementation work.
