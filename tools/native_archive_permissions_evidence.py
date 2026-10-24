"""Admit native archive permission execution records, separate from model tests."""
import re

PASS = (b'NATIVE_ARCHIVE_PERMISSIONS_PASS archive=1 exact_modes=pass root_ownership=pass '
        b'sticky=pass sgid_create=pass imported_no_inherit=pass actual_child_reap=pass')
EVENT = re.compile(rb'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event=([a-z-]+) '
    rb'service=([A-Za-z0-9_-]+) pid=([0-9]+) generation=([0-9]+) time_ms=([0-9]+) '
    rb'next_ms=([0-9]+) errno=([0-9]+) status=([0-9]+)')


def validate_archive_permissions(serial):
    lines = serial.replace(b'\r\n', b'\n').splitlines()

    def need(value, message):
        if not value:
            raise ValueError(message)

    for marker in (b'NATIVE_ARCHIVE_PERMISSIONS_FAIL', b'event=fatal-hold', b'OK_TEST_FAIL', b'Kernel panic'):
        need(marker not in serial, 'archive permissions execution failure')
    need(sum(line == b'OK_STORAGE source=archive reason=no-supported-device' for line in lines) == 1 and
         b'OK_STORAGE source=ext4' not in serial, 'guest did not use the boot archive root')

    def one(prefix, pattern):
        rows = [(i, re.fullmatch(pattern, line)) for i, line in enumerate(lines) if prefix in line]
        need(len(rows) == 1 and rows[0][1] is not None, 'missing/duplicate/malformed ' + prefix.decode())
        return rows[0]

    metadata, identity = one(b'NATIVE_ARCHIVE_METADATA', rb'NATIVE_ARCHIVE_METADATA pid=([1-9][0-9]*) '
        rb'parent=1 tmp=01777 sticky=01777 sgid=02777 imported=0755 regular=0444 uid=0 gid=0')
    owner = int(identity[1])
    creator, _ = one(b'NATIVE_ARCHIVE_CREATOR', rb'NATIVE_ARCHIVE_CREATOR uid=1000 gid=1000 '
        rb'sticky_file_gid=1000 sgid_file_gid=0 sgid_directory_mode=02700')
    attacker, _ = one(b'NATIVE_ARCHIVE_ATTACKER', rb'NATIVE_ARCHIVE_ATTACKER uid=1001 gid=1001 '
        rb'foreign_unlink=EPERM tmp_unlink=EPERM own_unlink=pass')
    completed, _ = one(b'NATIVE_ARCHIVE_PERMISSIONS_PASS', re.escape(PASS))
    reaps = []
    for i, line in enumerate(lines):
        if b'NATIVE_ARCHIVE_REAP' in line:
            match = re.fullmatch(rb'NATIVE_ARCHIVE_REAP child=([1-9][0-9]*) uid=(1000|1001) raw_status=0', line)
            need(match is not None, 'malformed native child reap')
            reaps.append((i, int(match[1]), int(match[2])))
    need(len(reaps) == 2 and [row[2] for row in reaps] == [1000, 1001] and
         len({1, owner, reaps[0][1], reaps[1][1]}) == 4,
         'archive fixture child identity/reap differs')
    need(metadata < creator < reaps[0][0] < attacker < reaps[1][0] < completed,
         'archive permission child execution order differs')
    events = []
    for i, line in enumerate(lines):
        if b'NATIVE_PID1 ' in line:
            match = EVENT.fullmatch(line[line.find(b'NATIVE_PID1 '):])
            need(match is not None, 'malformed PID1 event')
            events.append((i, match))

    def event(kind, service, pid=None):
        rows = [(i, row) for i, row in events if row[1] == kind and row[2] == service]
        need(len(rows) == 1 and rows[0][1][4] == b'1' and rows[0][1][7] == rows[0][1][8] == b'0' and
             (pid is None or int(rows[0][1][3]) == pid), 'missing/contradictory supervised archive lifecycle')
        return rows[0]

    launched, _ = event(b'launch', b'archive', owner)
    reaped, _ = event(b'reap', b'archive', owner)
    ready, _ = event(b'oneshot-ready', b'archive', owner)
    console, shell = event(b'launch', b'console')
    need(launched < metadata < completed < reaped < ready < console and int(shell[3]) > 1 and
         int(shell[3]) not in {owner, reaps[0][1], reaps[1][1]}, 'archive oneshot causal order differs')
    return dict(archive_root=True, fixture_pid=owner, child_pids=[row[1] for row in reaps],
                child_ids=[1000, 1001], exact_modes=True, root_ownership=True,
                imported_no_sgid_inheritance=True, sticky_foreign_unlink_denied=True,
                sticky_own_unlink=True, sgid_runtime_inheritance=True, actual_child_reaps=True,
                model_test=False, filesystem_sync=False, platform_power=False)
