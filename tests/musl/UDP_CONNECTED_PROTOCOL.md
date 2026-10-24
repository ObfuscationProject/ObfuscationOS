# Explicit public-musl connected UDP fixture

This fixture uses public libc calls in a static Linux-musl child and an SDK-only
native fork/exec/wait runner. It is excluded from ordinary distribution defaults.
The supplied child build paths remain x86_64, aarch64, rv64 and loongarch64; the
actual NIC harness selects x86_64 Debug or Release only. Hosted observer/package
controls use synthetic bytes and do not establish execution of libc or a guest.

The bounded S6 profile uses local IPv4 192.0.2.2 and peer 192.0.2.1 with serialized
boot-CPU polling, static-peer routing and nonblocking UDP. It requires the exact
ABI55 bounded-static-peer-association-zero-destination-output-v2 SDK profile. Remote-port-zero
association permits a default send to destination port zero; getpeername still
returns ENOTCONN without changing its outputs. Supplying an explicit port-zero
address to sendto returns EINVAL. These distinct public operations are checked
within the bounded project profile; hosted byte controls are not libc execution.

## Ordered public operations

1. Query an unbound wildcard socket; bind 192.0.2.2:54324, connect the peer at
   12345, and report both names. Verify peer-query clipping, guards and padding.
   After the host's ARP request/reply and GO, use default send. The peer sends a
   valid source-12346 wrong payload immediately before the source-12345 ACK.
   Receive only the ACK, validate its source and require an empty receive queue.
2. Duplicate the descriptor, close the original and require EBADF without output
   changes on the original. Report the alias's unchanged local/peer names and
   exchange default-send/recv data. Close the alias and rebind the exact old
   address/port on a new endpoint, proving reservation release through the API.
3. Bind 192.0.2.2:54325 and connect the peer at port zero. Require unchanged-output
   ENOTCONN. Supply an explicit peer-port-zero address to sendto and require
   EINVAL before any outgoing frame. Report the unchanged local name as
   zero-before and zero-after-refusal, recheck ENOTCONN, then use default send
   for MUSL:S6:ZERO. Its observed destination port must be zero. Receive valid
   source-port-zero and source-12346 packets in order; recheck ENOTCONN.
4. Disconnect with a two-byte AF_UNSPEC address. Report the fixed binding intact,
   require EDESTADDRREQ on default send, then explicitly send and receive from
   source 12346 to exercise cleared filtering.
5. Bind the configured address with port zero and report the assigned port before
   and after connect to 12345. Disconnect retains the address and releases the
   unlocked port to zero. A refused unconnected default send reserves a nonzero
   port while retaining the address. Report it before and after explicit send,
   match both to wire source, and exchange data. Reconnect to 12346 with the same
   local name, use default send, and receive the valid 12346 ACK after an ordered
   wrong-source-12345 packet. Close and complete with normal child exit zero.

There are 16 located name records and 32 ordered fixture records. Record lines
must be complete ASCII with LF or CRLF, exact phase/kind/address/port/length and
kernel mode/entropy diagnostics before the runner's start. Fixed and zero ports
are exact; names in each retained lifetime agree, but a newly assigned port need
not differ from a released one. Peer query capacities are 0, 1, 2, 7, 15, 16, 17
and INT_MAX; guarded untouched suffixes and returned length 16 are checked.

## Closed Ethernet protocol

The outgoing event order is ARP, associated, duplicate, zero, disconnect,
retained, reconnect. UDP IPv4 identifiers are 0x9000 through 0x9005. Each accepted
frame must exactly match all Ethernet/IPv4/UDP bytes, lengths, checksums and
padding, its payload below, and the required located name reports. Fixed source
ports are 54324, 54324, 54325, 54325; the last two sources agree with the retained
binding. The zero event targets port zero, reconnect targets 12346, and the
associated, duplicate, disconnect and retained events target 12345.

| Outgoing phase | Outgoing payload | Ordered incoming payloads (source port) |
| --- | --- | --- |
| associated | MUSL:S6:ASSOC | GO:S6:ASSOC (12345) before send; BAD:S6:ASSOC (12346), ACK:S6:ASSOC (12345) after send |
| duplicate | MUSL:S6:DUP | ACK:S6:DUP (12345) |
| zero | MUSL:S6:ZERO | ACK:S6:ZERO0 (0), ACK:S6:ZEROOTHER (12346) |
| disconnect | MUSL:S6:DISC | ACK:S6:DISC (12346) |
| retained | MUSL:S6:RETAIN | ACK:S6:RETAIN (12345) |
| reconnect | MUSL:S6:RECONNECT | BAD:S6:RECONNECT (12345), ACK:S6:RECONNECT (12346) |

Every incoming event has a closed exact preceding serial/name/wire gate and
fixed payload/source. Arbitrary raw sends cannot advance the coordinator.
Wrong-source ingress remains valid in every other field and both checksums;
the source-port-zero frame is separately valid without modifying any production
codec. Framed transport bytes, ingress order, failure candidates and partial
frames are retained. No unexpected outgoing frame, including the refused explicit
port-zero sendto payload, may appear before, during or after the successful zero
default send. The previous explicit destination-12345 zero-phase output and a
checksum-valid wrong zero payload are both refused without advancing wire state. Final
verification checks complete serial order, all seven wire events, all 11 host
events, a recorded 0.1-second quiet interval and post-reap drainage.

The empty-queue checks establish bounded ordered-transport filtering only. They
do not establish general packet-loss behavior, concurrent sockets, IRQ, SMP,
blocking restart, general networking, desktop or hardware acceptance. The outer
artifact campaign must own and retire the complete execution process group and
establish image-to-child provenance; this harness's endpoint hashes alone do not
establish immutable artifact history.

## Explicit construction

Use `xmake musl-udp-connected-probe` with explicit architecture, audited musl build,
cross toolchain, new output and actual compile dependency capture. Configure the
native runner/archive/image with an explicit architecture/mode-matched exported
Kernel SDK and pinned child/musl manifests. The closed package selector is
`--fixture udp-connected`; it selects this child, its runner and
`/bin/musl-udp-connected-probe`. Only the explicit fixture copy's `/init` and child
payload change. Normal staging and the original/default selectors remain intact.
The OS build consumes SDK libraries and compiles no Kernel checkout source.

The explicit `musl-udp-connected-nic-test` task requires the selected SDK, image,
exact staged child and new output directory. Run Python tools with
`PYTHONDONTWRITEBYTECODE=1 python3 -B`. Host C compilation checks public headers and
warnings only; actual musl builds and guest NIC admission belong to separately
selected artifact and execution campaigns.
