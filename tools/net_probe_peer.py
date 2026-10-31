"""Scripted Ethernet peer for the kernel link probe (scripts/test_net_probe.py).

It plays the distribution's gateway on 192.0.2.0/24 and fe80::/2001:db8:1::/64:
ARP for the gateway and the echo host, ICMPv4/ICMPv6 echo, router
advertisements, neighbour advertisements, and a TCP echo service at
192.0.2.100:7 with its own retransmission. Every frame is built and checked
here, independently of the kernel's codecs; this is an external peer, not a
second copy of the guest stack.
"""
from __future__ import annotations

import ipaddress
import random
import struct

GATEWAY_MAC = bytes.fromhex("025255000201")
GATEWAY4 = ipaddress.IPv4Address("192.0.2.1").packed
ECHO4 = ipaddress.IPv4Address("192.0.2.100").packed
PREFIX6 = ipaddress.IPv6Address("2001:db8:1::").packed
ALL_NODES = ipaddress.IPv6Address("ff02::1").packed
ECHO_PORT = 7


def link_local(mac: bytes) -> bytes:
    return bytes.fromhex("fe80000000000000") + bytes([mac[0] ^ 2]) + mac[1:3] + b"\xff\xfe" + mac[3:6]


GATEWAY6 = link_local(GATEWAY_MAC)


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def ethernet(destination: bytes, ethertype: int, payload: bytes) -> bytes:
    frame = destination + GATEWAY_MAC + struct.pack("!H", ethertype) + payload
    return frame + b"\0" * max(0, 60 - len(frame))


def ipv4(source: bytes, destination: bytes, protocol: int, payload: bytes, identification: int) -> bytes:
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), identification, 0x4000, 64, protocol, 0,
                         source, destination)
    return header[:10] + struct.pack("!H", checksum(header)) + header[12:] + payload


def ipv6(source: bytes, destination: bytes, next_header: int, payload: bytes, hop_limit: int = 64) -> bytes:
    return struct.pack("!IHBB", 6 << 28, len(payload), next_header, hop_limit) + source + destination + payload


def transport_checksum4(source: bytes, destination: bytes, protocol: int, segment: bytes) -> int:
    return checksum(source + destination + struct.pack("!BBH", 0, protocol, len(segment)) + segment)


def transport_checksum6(source: bytes, destination: bytes, next_header: int, segment: bytes) -> int:
    return checksum(source + destination + struct.pack("!I3xB", len(segment), next_header) + segment)


def icmp6(source: bytes, destination: bytes, body: bytes, hop_limit: int = 64) -> bytes:
    value = transport_checksum6(source, destination, 58, body)
    return ipv6(source, destination, 58, body[:2] + struct.pack("!H", value) + body[4:], hop_limit)


class TcpEcho:
    """One passive TCP connection that echoes every byte back.

    Data is accepted in order only; anything else draws a duplicate ACK.
    Unacknowledged echo data is resent from SND.UNA after `rto` seconds.
    """

    def __init__(self, rng: random.Random, rto: float = 0.4) -> None:
        self.rng = rng
        self.rto = rto
        self.reset()

    def reset(self) -> None:
        self.state = "listen"
        self.peer = None
        self.iss = self.rng.randrange(1 << 32)
        self.snd_una = self.snd_nxt = self.iss
        self.rcv_nxt = 0
        self.peer_window = 0
        self.peer_mss = 536
        self.pending = bytearray()  # echoed bytes from SND.UNA on
        self.sent_at = 0.0
        self.fin_received = self.fin_sent = False
        self.received = self.echoed_acked = self.retransmissions = self.duplicate_acks_sent = 0

    def segment(self, flags: int, payload: bytes = b"", sequence: int | None = None, options: bytes = b"") -> bytes:
        guest_ip, guest_port = self.peer
        sequence = self.snd_nxt if sequence is None else sequence
        offset = (20 + len(options)) // 4
        header = struct.pack("!HHIIBBHHH", ECHO_PORT, guest_port, sequence & 0xFFFFFFFF, self.rcv_nxt & 0xFFFFFFFF,
                             offset << 4, flags, 8192, 0, 0) + options
        body = header + payload
        value = transport_checksum4(ECHO4, guest_ip, 6, body)
        return body[:16] + struct.pack("!H", value) + body[18:]

    def receive(self, source: bytes, segment: bytes, now: float) -> list[bytes]:
        if len(segment) < 20 or transport_checksum4(source, ECHO4, 6, segment):
            return []
        sport, dport, sequence, ack, offset_byte, flags, window = struct.unpack("!HHIIBBH", segment[:16])
        if dport != ECHO_PORT:
            return []
        header = (offset_byte >> 4) * 4
        payload = segment[header:]
        out: list[bytes] = []
        if flags & 0x02:  # SYN
            if self.state in ("listen", "closed"):
                self.reset()
                self.peer = (source, sport)
                self.rcv_nxt = (sequence + 1) & 0xFFFFFFFF
                options = segment[20:header]
                at = 0
                while at < len(options):
                    kind = options[at]
                    if kind == 0:
                        break
                    if kind == 1:
                        at += 1
                        continue
                    length = options[at + 1]
                    if kind == 2 and length == 4:
                        self.peer_mss = struct.unpack("!H", options[at + 2:at + 4])[0]
                    at += max(length, 2)
                self.peer_window = window
                self.state = "syn_received"
            if self.state == "syn_received" and self.peer == (source, sport):
                self.snd_nxt = (self.iss + 1) & 0xFFFFFFFF
                out.append(self.segment(0x12, sequence=self.iss, options=b"\x02\x04\x05\xb4"))
            return out
        if self.peer != (source, sport) or self.state == "listen":
            return []
        if flags & 0x04:  # RST
            self.state = "closed"
            return []
        if flags & 0x10:  # ACK
            if self.state == "syn_received" and ack == (self.iss + 1) & 0xFFFFFFFF:
                self.state = "established"
                self.snd_una = ack
            elif self.state != "syn_received":
                advance = (ack - self.snd_una) & 0xFFFFFFFF
                in_flight = (self.snd_nxt - self.snd_una) & 0xFFFFFFFF
                if 0 < advance <= in_flight:
                    data = min(advance, len(self.pending))
                    del self.pending[:data]
                    self.echoed_acked += data
                    self.snd_una = ack
                    self.sent_at = now
            self.peer_window = window
        if payload or flags & 0x01:
            if sequence == self.rcv_nxt:
                room = 8192 - len(self.pending)
                accepted = payload[:room]
                self.pending += accepted
                self.received += len(accepted)
                self.rcv_nxt = (self.rcv_nxt + len(accepted)) & 0xFFFFFFFF
                if flags & 0x01 and len(accepted) == len(payload):
                    self.rcv_nxt = (self.rcv_nxt + 1) & 0xFFFFFFFF
                    self.fin_received = True
            else:
                self.duplicate_acks_sent += 1
            out.append(self.segment(0x10))
        out += self.send(now)
        return out

    def send(self, now: float, retransmit: bool = False) -> list[bytes]:
        if self.state != "established":
            return []
        out = []
        if retransmit:
            self.snd_nxt = self.snd_una
            self.retransmissions += 1
        while True:
            offset = (self.snd_nxt - self.snd_una) & 0xFFFFFFFF
            unsent = len(self.pending) - offset
            window = self.peer_window - offset
            if unsent <= 0 or window <= 0:
                break
            count = min(unsent, self.peer_mss, window)
            out.append(self.segment(0x18, bytes(self.pending[offset:offset + count])))
            self.snd_nxt = (self.snd_nxt + count) & 0xFFFFFFFF
            self.sent_at = now
        if self.fin_received and not self.pending and not self.fin_sent:
            out.append(self.segment(0x11))
            self.snd_nxt = (self.snd_nxt + 1) & 0xFFFFFFFF
            self.fin_sent = True
        return out

    def tick(self, now: float) -> list[bytes]:
        if self.state == "established" and self.pending and now - self.sent_at >= self.rto and \
                self.snd_nxt != self.snd_una:
            return self.send(now, retransmit=True)
        return []


class Peer:
    def __init__(self, seed: int = 1, tcp_loss_percent: int = 0) -> None:
        self.rng = random.Random(seed)
        self.tcp_loss_percent = tcp_loss_percent
        self.guest_mac: bytes | None = None
        self.identification = 0x2000
        self.tcp = TcpEcho(self.rng)
        self.stats = {"frames_in": 0, "frames_out": 0, "arp_replies": 0, "echo4_replies": 0, "echo6_replies": 0,
                      "router_advertisements": 0, "neighbour_advertisements": 0, "tcp_segments_in": 0,
                      "tcp_segments_dropped": 0, "ignored": 0}

    def out(self, frames: list[bytes]) -> list[bytes]:
        self.stats["frames_out"] += len(frames)
        return frames

    def receive(self, frame: bytes, now: float) -> list[bytes]:
        self.stats["frames_in"] += 1
        if len(frame) < 14:
            return []
        destination, source, ethertype = frame[:6], frame[6:12], struct.unpack("!H", frame[12:14])[0]
        payload = frame[14:]
        self.guest_mac = source
        if ethertype == 0x0806:
            return self.out(self.arp(payload))
        if ethertype == 0x0800:
            return self.out(self.ipv4(payload, now))
        if ethertype == 0x86DD:
            return self.out(self.ipv6(payload))
        self.stats["ignored"] += 1
        return []

    def arp(self, packet: bytes) -> list[bytes]:
        if len(packet) < 28:
            return []
        operation = struct.unpack("!H", packet[6:8])[0]
        sender_mac, sender_ip, target_ip = packet[8:14], packet[14:18], packet[24:28]
        if operation != 1 or target_ip not in (GATEWAY4, ECHO4):
            return []
        self.stats["arp_replies"] += 1
        reply = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 2) + GATEWAY_MAC + target_ip + sender_mac + sender_ip
        return [ethernet(sender_mac, 0x0806, reply)]

    def ipv4(self, packet: bytes, now: float) -> list[bytes]:
        if len(packet) < 20 or packet[0] != 0x45 or checksum(packet[:20]):
            return []
        total = struct.unpack("!H", packet[2:4])[0]
        protocol, source, destination = packet[9], packet[12:16], packet[16:20]
        body = packet[20:total]
        if protocol == 1 and destination == GATEWAY4 and len(body) >= 8 and body[0] == 8 and not checksum(body):
            self.stats["echo4_replies"] += 1
            reply = b"\0\0\0\0" + body[4:]
            reply = reply[:2] + struct.pack("!H", checksum(reply)) + reply[4:]
            self.identification += 1
            return [ethernet(self.guest_mac, 0x0800, ipv4(GATEWAY4, source, 1, reply, self.identification))]
        if protocol == 6 and destination == ECHO4:
            self.stats["tcp_segments_in"] += 1
            if self.tcp_loss_percent and self.rng.randrange(100) < self.tcp_loss_percent:
                self.stats["tcp_segments_dropped"] += 1
                return []
            frames = []
            for segment in self.tcp.receive(source, body, now):
                self.identification += 1
                frames.append(ethernet(self.guest_mac, 0x0800, ipv4(ECHO4, source, 6, segment, self.identification)))
            return frames
        self.stats["ignored"] += 1
        return []

    def router_advertisement(self, destination: bytes) -> bytes:
        options = (b"\x01\x01" + GATEWAY_MAC +
                   struct.pack("!BBBBIII", 3, 4, 64, 0xC0, 86400, 14400, 0) + PREFIX6 +
                   struct.pack("!BBHI", 5, 1, 0, 1500))
        body = struct.pack("!BBHBBHII", 134, 0, 0, 64, 0, 1800, 0, 0) + options
        return icmp6(GATEWAY6, destination, body, 255)

    def ipv6(self, packet: bytes) -> list[bytes]:
        if len(packet) < 40 or packet[0] >> 4 != 6:
            return []
        length, next_header, hop_limit = struct.unpack("!HBB", packet[4:8])
        source, destination = packet[8:24], packet[24:40]
        body = packet[40:40 + length]
        if next_header != 58 or len(body) < 4 or transport_checksum6(source, destination, 58, body):
            self.stats["ignored"] += 1
            return []
        kind = body[0]
        if kind == 133 and hop_limit == 255:
            self.stats["router_advertisements"] += 1
            return [ethernet(bytes.fromhex("333300000001"), 0x86DD, self.router_advertisement(ALL_NODES))]
        if kind == 135 and hop_limit == 255 and len(body) >= 24 and body[8:24] == GATEWAY6:
            if source == bytes(16):
                return []
            self.stats["neighbour_advertisements"] += 1
            advert = struct.pack("!BBHI", 136, 0, 0, 0xE0000000) + GATEWAY6 + b"\x02\x01" + GATEWAY_MAC
            return [ethernet(self.guest_mac, 0x86DD, icmp6(GATEWAY6, source, advert, 255))]
        if kind == 128 and destination == GATEWAY6:
            self.stats["echo6_replies"] += 1
            return [ethernet(self.guest_mac, 0x86DD, icmp6(GATEWAY6, source, bytes([129, 0, 0, 0]) + body[4:]))]
        self.stats["ignored"] += 1
        return []

    def tick(self, now: float) -> list[bytes]:
        if self.guest_mac is None or not self.tcp.peer:
            return []
        frames = []
        for segment in self.tcp.tick(now):
            self.identification += 1
            frames.append(ethernet(self.guest_mac, 0x0800, ipv4(ECHO4, self.tcp.peer[0], 6, segment, self.identification)))
        return self.out(frames)
