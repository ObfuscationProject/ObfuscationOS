"""Independent host Ethernet peer for the static IPv4/ARP/UDP native probe."""
from __future__ import annotations

import struct

LOCAL_MAC = bytes.fromhex("021122334455")
PEER_MAC = bytes.fromhex("02aabbccddee")
LOCAL_IP = bytes((192, 0, 2, 2))
PEER_IP = bytes((192, 0, 2, 1))


def checksum(data: bytes) -> int:
    if len(data) & 1:
        data += b"\0"
    total = sum(int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def arp_request() -> bytes:
    frame = (b"\xff" * 6 + PEER_MAC + bytes.fromhex("08060001080006040001") +
             PEER_MAC + PEER_IP + bytes(6) + LOCAL_IP)
    return frame.ljust(60, b"\0")


def arp_reply() -> bytes:
    frame = (PEER_MAC + LOCAL_MAC + bytes.fromhex("08060001080006040002") +
             LOCAL_MAC + LOCAL_IP + PEER_MAC + PEER_IP)
    return frame.ljust(60, b"\0")


def payload(sequence: int) -> bytes:
    length = 1469 if sequence % 3 == 0 else 2 + sequence
    return struct.pack("!H", sequence) + bytes(((index * 37) ^ sequence ^ 0x5a) & 255
                                               for index in range(2, length))


def datagram(src_mac: bytes, dst_mac: bytes, src_ip: bytes, dst_ip: bytes,
             src_port: int, dst_port: int, ident: int, data: bytes,
             *, ttl: int = 64, flags: int = 0x4000, ihl: int = 5) -> bytes:
    udp_length = 8 + len(data)
    udp = struct.pack("!HHHH", src_port, dst_port, udp_length, 0) + data
    pseudo = src_ip + dst_ip + b"\0\x11" + struct.pack("!H", udp_length)
    transport_checksum = checksum(pseudo + udp) or 0xffff
    udp = udp[:6] + struct.pack("!H", transport_checksum) + udp[8:]
    options = bytes(4 * (ihl - 5))
    ip = (bytes(((4 << 4) | ihl, 0)) + struct.pack("!HHHBBH", 4 * ihl + udp_length,
          ident, flags, ttl, 17, 0) + src_ip + dst_ip + options)
    ip = ip[:10] + struct.pack("!H", checksum(ip)) + ip[12:]
    frame = dst_mac + src_mac + b"\x08\x00" + ip + udp
    return frame.ljust(60, b"\0")


def request(sequence: int) -> bytes:
    return datagram(PEER_MAC, LOCAL_MAC, PEER_IP, LOCAL_IP, 12345, 54321,
                    0x1234 + sequence, payload(sequence))


def reply(sequence: int) -> bytes:
    return datagram(LOCAL_MAC, PEER_MAC, LOCAL_IP, PEER_IP, 54321, 12345,
                    0x9000 + sequence, b"OK:" + payload(sequence))


def verify_reply(frame: bytes, sequence: int) -> None:
    expected = reply(sequence)
    if frame != expected:
        raise ValueError(f"UDP reply differs byte for byte at sequence {sequence}")
    if frame[0:6] != PEER_MAC or frame[6:12] != LOCAL_MAC or frame[12:14] != b"\x08\x00":
        raise ValueError("reply Ethernet addresses or type differ")
    total = struct.unpack_from("!H", frame, 16)[0]
    if total != 20 + 8 + 3 + len(payload(sequence)) or checksum(frame[14:34]):
        raise ValueError("reply IPv4 length or checksum differs")
    udp = frame[34:14 + total]
    if struct.unpack_from("!H", udp, 4)[0] != len(udp):
        raise ValueError("reply UDP length differs")
    if checksum(LOCAL_IP + PEER_IP + b"\0\x11" + struct.pack("!H", len(udp)) + udp):
        raise ValueError("reply UDP pseudo-header checksum differs")
    if any(frame[14 + total:]):
        raise ValueError("reply Ethernet padding is nonzero")


def hostile() -> list[tuple[str, bytes]]:
    clean = request(1)
    rows: list[tuple[str, bytes]] = []
    changed = bytearray(clean); changed[0] = 0
    rows.append(("foreign-ethernet-destination", bytes(changed)))
    changed = bytearray(clean); changed[24] ^= 1
    rows.append(("ip-checksum", bytes(changed)))
    changed = bytearray(clean); changed[43] ^= 1
    rows.append(("udp-checksum", bytes(changed)))
    changed = bytearray(clean); changed[26] ^= 1
    changed[24:26] = b"\0\0"; changed[24:26] = struct.pack("!H", checksum(changed[14:34]))
    rows.append(("pseudoheader-source", bytes(changed)))
    changed = bytearray(clean); changed[20:22] = b"\x20\x00"
    changed[24:26] = b"\0\0"; changed[24:26] = struct.pack("!H", checksum(changed[14:34]))
    rows.append(("fragment", bytes(changed)))
    changed = bytearray(clean); changed[40:42] = b"\0\0"
    rows.append(("zero-udp-checksum-policy", bytes(changed)))
    changed = bytearray(clean); changed[38:40] = b"\xff\xff"
    rows.append(("forged-udp-length", bytes(changed)))
    changed = bytearray(arp_request()); changed[22] ^= 1
    rows.append(("forged-arp-sender", bytes(changed)))
    rows.append(("ipv4-options", datagram(PEER_MAC, LOCAL_MAC, PEER_IP, LOCAL_IP,
               12345, 54321, 0x1234, payload(1), ihl=6)))
    changed = bytearray(clean); changed[16:18] = b"\xff\xff"
    changed[24:26] = b"\0\0"; changed[24:26] = struct.pack("!H", checksum(changed[14:34]))
    rows.append(("forged-ip-length", bytes(changed)))
    rows.append(("foreign-udp-port", datagram(PEER_MAC, LOCAL_MAC, PEER_IP, LOCAL_IP,
               12345, 54320, 0x1234, payload(1))))
    changed = bytearray(clean); changed[12:14] = b"\x81\x00"
    rows.append(("vlan-unsupported", bytes(changed)))
    assert len(rows) == 12 and all(60 <= len(frame) <= 1514 for _, frame in rows)
    return rows


if __name__ == "__main__":
    assert arp_request().hex() == ("ffffffffffff02aabbccddee0806000108000604000102aabbccddeec0000201"
                                   "000000000000c0000202000000000000000000000000000000000000")
    assert arp_reply().hex() == ("02aabbccddee02112233445508060001080006040002021122334455c0000202"
                                 "02aabbccddeec0000201000000000000000000000000000000000000")
    assert len(request(0)) == 1511 and len(reply(0)) == 1514
    assert len(hostile()) == 12
    for number in range(96):
        verify_reply(reply(number), number)
    print("STATIC_UDP_PEER_PASS arp=exact udp=96 hostile=12")
