# Kernel link probe

Paired with kernel `feat/net-core` (WT2.3, module ABI 79).

## What runs

- `xmake f --net_probe=y` defines `OS_NET_PROBE` on the distribution image.
  `SystemGuiRuntime::network_interface` then returns the static link as a
  routed interface (192.0.2.2/24, gateway 192.0.2.1 without a known link
  address, IPv6 on), and `network_probe` asks the kernel for its link probe
  with a TCP echo at 192.0.2.100:7. Other builds return unsupported and keep
  the static peer link.
- `scripts/test_net_probe.py --arch A --qemu Q --kernel K --rootfs R --output D
  [--tcp-loss N]` boots the image on a QEMU socket netdev and serves the link
  with `tools/net_probe_peer.py`: ARP for the gateway and the echo host,
  ICMPv4/ICMPv6 echo, a router advertisement for 2001:db8:1::/64 on each
  router solicitation, neighbour advertisements, and a passive TCP echo that
  accepts in-order data, retransmits from SND.UNA and can drop N percent of
  the guest's TCP segments. It requires `OK_NET_LINK`, `OK_NET_ARP`, both
  `OK_NET_PING` families, `OK_NET_IPV6`, `OK_NET_TCP` and
  `OK_NET_PROBE result=pass`, and writes `result.json` with the markers, the
  peer's counts and the input hashes.
- The peer builds and checks every frame itself; it is an external peer,
  not a copy of the kernel's codecs. It is not a third-party stack either:
  the pinned QEMU 10.2 has no user-mode (slirp) netdev, and `passt` on this
  host cannot relay ICMP (ping sockets are disabled) or advertise IPv6 (no
  global IPv6 address).

## Results

On all ten profiles (i386, x86_64, aarch64, arm32, rv64, rv32, loongarch64,
mips, mips64, ppc), debug images against the kernel worktree's SDK: the guest
resolves the gateway through ARP, pings it, autoconfigures
2001:db8:1:0:11:22ff:fe33:4455 from the advertisement, pings the router's
link-local address and echoes 8192 TCP bytes in 10–53 ms. With ten percent
TCP loss the dropped segment is recovered by the guest's retransmission
timer (about one second). Receipts: ObfuscationEvidence
`receipts/ObfuscationKernel@956c7be/feat/net-core/device-probe-matrix`.

## Linux socketcall fixture

The explicit `net-socketcall` fixture applies to i386, mips and ppc, the
profiles whose Linux ABI has socketcall(2). It is the net_probe distribution
with `/bin/socketcall-probe` added to its rescue root.

- **Build**: `xmake net-socketcall-fixture-image`, with
  `tools/package_net_socketcall_fixture.py` and
  `xmake/net_socketcall_fixture.lua`. Default images are unchanged.
- **Program**: `tests/native/linux_tcp_socketcall_probe.c` is a freestanding
  Linux-personality program. It is built with the profile's SysToolchain
  compiler and the static-exec layout, and marked `EI_OSABI` Linux. It makes
  every socket call through socketcall, so no libc can choose the direct
  calls instead.
- **Run**: `scripts/test_net_socketcall.py` waits for the kernel link probe to
  pass, then types the program's path at the shell. The program:
  - creates a nonblocking TCP socket and connects it, unbound, to the peer's
    echo service;
  - checks `SO_ERROR`, `SO_TYPE` and both names;
  - echoes bytes with send/recv and sendto/recvfrom, then shuts down the write
    side;
  - checks `SO_TYPE` and `SO_ERROR` on a UDP socket.

  The run passes when the program prints
  `OK_NET_SOCKETCALL ... result=pass tcp=pass udp=pass`.
- **ppc**: the run uses the native e500v2 single-CPU QEMU profile, because
  the PPC kernel admits native userland only there. The plain net_probe run
  does not use that profile, so its PPC image reports
  `OK_NATIVE startup=private PPC ELF profile is not admitted`. The kernel link
  probe does not need userland and still passes.
- **Peer**: the scripted peer's echo service accepts a second client once the
  previous one has sent its FIN and acknowledged every echoed byte.
