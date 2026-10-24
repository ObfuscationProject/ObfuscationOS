"""Independent whole-completion cut oracle; this module does not execute a guest.

The outer campaign must bind the actual SDK, ELF, QEMU process and captured disk.
Cuts retain every completed write. They do not simulate a volatile device cache,
torn writes, write reordering, or physical loss of power.
"""
import re
import struct
from admit_linux_fixture import checksum
from journalled_directory_mode_evidence import records, require
from journalled_mode_image import extract_volume, inode_metadata
from journalled_directory_transaction import expected as transaction
from journalled_directory_mode_cut_protocol import validate_cut


def verify_cut(text, initial, guarded, facts, cut, arch):
    require(isinstance(text, str), 'cut transcript text required')
    validate_cut(text.encode('ascii'), cut, arch, facts)
    require(1 <= cut <= 20, 'cut outside first transaction')
    require(arch in ('x86_64', 'i386', 'mips'), 'cut architecture domain')
    require(not any(token in text for token in ('JMODE_', 'JREC_', 'JDREC_')),
            'foreign fixture protocol in directory cut')
    terminal = re.compile(r'JDMODE_CUT ordinal=([1-9][0-9]*) writes=(0|[1-9][0-9]*) flushes=(0|[1-9][0-9]*)\r?\n')
    matches = list(terminal.finditer(text))
    require(len(matches) == 1, 'missing/duplicate/truncated cut marker')
    marker = matches[0]
    require(marker.start() == 0 or text[marker.start() - 1] == '\n', 'cut marker line framing')
    require(not any(token in text[marker.end():] for token in ('JDMODE_', 'LINUX_CHMOD_SNAPSHOT')),
            'protocol activity after cut')
    rows = records(text[:marker.start()])
    require([r['kind'] for r in rows[:5]] == ['fixture_begin', 'storage', 'credentials', 'user_begin', 'begin'],
            'cut initial entry/operation ordering')
    require([r['values'] for r in rows[:5]] == [(1000, 'in-range'), (), (1000, 1000, 1000, 1000),
                                               (1000,), (1, 'chmod')], 'cut initial operation identity')
    native_lines = text.splitlines(keepends=True)
    image = []; loaded = []
    image_pattern = re.compile(r'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=([1-9][0-9]*) physical_first=(0x[0-9a-f]{16}) physical_last=(0x[0-9a-f]{16}) owner=retained\r?\n')
    for position, line in enumerate(native_lines):
        if 'OK_NATIVE_IMAGE' in line:
            match = image_pattern.fullmatch(line)
            require(match is not None, 'cut loader grammar/framing')
            source, pages, first, last = match.groups()
            first, last = int(first, 16), int(last, 16)
            require(source == ('linker' if arch == 'mips' else 'firmware') and int(pages) > 0 and
                    first % 4096 == last % 4096 == 0 and last >= first, 'cut loader identity')
            image.append(position)
        if 'OK_NATIVE scope=hardware init=' in line:
            require(re.fullmatch(r'OK_NATIVE scope=hardware init=loaded\r?\n', line) is not None,
                    'cut loaded grammar/framing')
            loaded.append(position)
    require(len(image) == len(loaded) == 1 and
            rows[1]['position'] < image[0] < loaded[0] < rows[2]['position'], 'cut native entry ordering')
    captured = extract_volume(guarded)
    require(len(initial) == len(captured) == 32 * 1024 * 1024, 'cut volume size')
    number = facts['nodes']['child']['inode']; old = inode_metadata(initial, number)
    require((number, old['mode'], old['uid'], old['gid'], old['links'], old['size'], old['blocks512']) ==
            (14, 0o40755, 1000, 1000, 2, 1024, 2), 'ordinary child directory fixture identity')
    j = facts['journal_first']; block = old['block']
    seconds, nanos = 1700000000, 123456789
    if cut >= 4:
        projected = bytearray(initial)
        projected[block * 1024:(block + 1) * 1024] = captured[(j + 3) * 1024:(j + 4) * 1024]
        new = inode_metadata(projected, number)
        seconds, nanos = new['ctime']['seconds'], new['ctime']['nanoseconds']
        require(1700000000 <= seconds < 1700003600 and 0 <= nanos < 1000000000, 'cut transaction time domain')
    published, complete = transaction(initial, facts, number, old['uid'], old['gid'], seconds, nanos, 0o2750)
    published = bytearray(published)
    # Before the inode payload write, the descriptor's payload checksum depends
    # on a ctime that is not yet observable. Validate the complete descriptor's
    # checksum and every other byte; do not invent that unobserved timestamp.
    if 2 <= cut < 4:
        at = (j + 1) * 1024
        actual = bytearray(captured[at:at + 1024]); wanted = published[at:at + 1024]
        seed = checksum(0xffffffff, bytes.fromhex(facts['uuid']))
        recorded = struct.unpack_from('>I', actual, 1020)[0]
        struct.pack_into('>I', actual, 1020, 0)
        require(checksum(seed, actual) == recorded, 'early descriptor checksum')
        require(all(a == b for i, (a, b) in enumerate(zip(actual, wanted))
                    if i not in set(range(56, 60)) | set(range(1020, 1024))), 'early descriptor fixed fields')
        published[at:at + 1024] = captured[at:at + 1024]
    recipe = [None, (j + 1, published), (j + 2, published), (j + 3, published), (j + 5, published),
              None, (j + 4, published), None, (1, published), None, (j, published), None, None,
              (1, published), (block, complete), None, (j, complete), None, (1, complete), None]
    expected = bytearray(initial); io = []; writes = flushes = 0
    for step in recipe[:cut]:
        if step is None:
            io.append(('flush',)); flushes += 1
        else:
            destination, data = step; payload = data[destination * 1024:(destination + 1) * 1024]
            expected[destination * 1024:(destination + 1) * 1024] = payload
            io.append(('write', facts['origin'] + destination * 2, 1024, checksum(0xffffffff, payload)))
            writes += 1
    observed = []; inodes = []
    for i, row in enumerate(rows[5:], 5):
        kind, values = row['kind'], row['values']
        require(kind in ('write', 'flush', 'inode'), 'unexpected event during first interrupted chmod')
        if kind == 'inode':
            require(i > 5 and rows[i - 1]['kind'] == 'write' and rows[i - 1]['position'] + 1 == row['position'],
                    'cut inode event adjacency')
            require(len(observed) == 15 and values[0] == 15, 'cut inode not at home write')
            inodes.append(values)
        else:
            require(values[0] == len(observed) + 1, 'cut I/O ordinal gap/reuse')
            observed.append((kind, *values[1:]))
    require(observed == io, 'cut write/flush prefix differs from independent transaction')
    require(tuple(map(int, marker.groups())) == (cut, writes, flushes), 'cut completion accounting')
    require(captured == expected, 'cut full disk differs from whole-completion prefix')
    if cut >= 15:
        changed = inode_metadata(complete, number)
        require(inodes == [(15, number, changed['mode'], old['uid'], old['gid'], seconds, nanos, changed['version'])],
                'cut home inode observation')
    else:
        require(not inodes, 'home inode observed before completed home write')
    recovered = bytearray(expected)
    # The journal becomes visible at its superblock publication (completion11).
    # Earlier cuts leave the old inode; later cuts recover the new inode.
    if cut >= 11:
        recovered[block * 1024:(block + 1) * 1024] = complete[block * 1024:(block + 1) * 1024]
        recovered[j * 1024:(j + 1) * 1024] = complete[j * 1024:(j + 1) * 1024]
    recovered[1024:2048] = initial[1024:2048]
    return dict(cut=cut, writes=writes, flushes=flushes, recovered_new_inode=cut >= 11,
                early_unobservable_payload_crc=2 <= cut < 4, expected_recovered=bytes(recovered),
                scope='independent whole-completion snapshot and recovery oracle; no execution')
