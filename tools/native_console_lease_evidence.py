"""Strict causal console lease guest records; synthetic reader tests are separate."""
import hashlib
import re

PASS_PREFIX = b'NATIVE_CONSOLE_PASS '
REJECTIONS = rb'read=EACCES readv=EACCES dup=EACCES poll=ERR_HUP controls=EACCES'
EVENT = re.compile(rb'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event=([a-z-]+) '
    rb'service=([A-Za-z0-9_-]+) pid=([0-9]+) generation=([0-9]+) time_ms=([0-9]+) '
    rb'next_ms=([0-9]+) errno=([0-9]+) status=([0-9]+)')


def key_hash(key):
    result = 14695981039346656037
    for byte in key:
        result = ((result ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return result


def validate_console_lease(serial, key):
    def need(value, message):
        if not value:
            raise ValueError(message)

    need(re.fullmatch(rb'[0-9a-f]{32}', key), 'input key must be exactly 32 lowercase hex bytes')
    # Short fragments also catch partial terminal echo. The qualifier chooses a
    # key whose every fragment contains a hex letter, avoiding decimal PID/hash text.
    need(all(key[i:i + 8] not in serial for i in range(len(key) - 7)), 'injected input echoed in serial')
    lines = serial.replace(b'\r\n', b'\n').splitlines()
    for marker in (b'NATIVE_CONSOLE_FAIL', b'event=fatal-hold', b'OK_TEST_FAIL', b'Kernel panic'):
        need(marker not in serial, 'console lease guest failure')
    need(sum(line == b'OK_STORAGE source=archive reason=no-supported-device' for line in lines) == 1 and
         b'OK_STORAGE source=ext4' not in serial, 'console guest must boot from archive without distribution disk')
    accepted = set()

    def rows(prefix, pattern, count):
        found = [(i, re.fullmatch(pattern, line)) for i, line in enumerate(lines) if prefix in line]
        need(len(found) == count and all(row is not None for _, row in found),
             'missing/duplicate/malformed ' + prefix.decode())
        accepted.update(i for i, _ in found)
        return found

    def one(prefix, pattern):
        return rows(prefix, pattern, 1)[0]

    guard_start, guard = one(b'NATIVE_CONSOLE_GUARD_START', rb'NATIVE_CONSOLE_GUARD_START pid=([1-9][0-9]*) '
        rb'parent=1 uid=0 gid=0 epoch=0')
    guard_pid = int(guard[1])
    leaders = rows(b'NATIVE_CONSOLE_LEADER', rb'NATIVE_CONSOLE_LEADER generation=([12]) '
        rb'pid=([1-9][0-9]*) parent=1 epoch=([1-9][0-9]*)', 2)
    need([row[1][1] for row in leaders] == [b'1', b'2'], 'leader generations differ')
    first_pid, next_pid = (int(row[1][2]) for row in leaders)
    first_epoch, next_epoch = (int(row[1][3]) for row in leaders)
    need(0 < first_epoch < next_epoch <= 0x3fffffff, 'console restart did not issue a fresh bounded epoch')
    departing, departure = one(b'NATIVE_CONSOLE_FIRST_EXIT', rb'NATIVE_CONSOLE_FIRST_EXIT pid=([1-9][0-9]*) '
        rb'epoch=([1-9][0-9]*) read_pid=([1-9][0-9]*) readv_pid=([1-9][0-9]*) '
        rb'poll_pid=([1-9][0-9]*) status=37')
    need(int(departure[1]) == first_pid and int(departure[2]) == first_epoch, 'first leader identity differs')
    roles = (b'read', b'readv', b'poll')
    children = dict(zip(roles, (int(departure[i]) for i in (3, 4, 5))))
    need(len({1, guard_pid, first_pid, next_pid, *children.values()}) == 7, 'console process identities alias')

    waits = rows(b'NATIVE_CONSOLE_WAIT', rb'NATIVE_CONSOLE_WAIT kind=(read|readv|poll) '
        rb'pid=([1-9][0-9]*) parent=([1-9][0-9]*) epoch=([1-9][0-9]*)', 3)
    revoked = rows(b'NATIVE_CONSOLE_REVOKED', rb'NATIVE_CONSOLE_REVOKED kind=(read|readv|poll) '
        rb'pid=([1-9][0-9]*) parent=1 epoch=([1-9][0-9]*) initial=(EACCES|ERR_HUP)', 3)
    old_passes = rows(b'NATIVE_CONSOLE_OLD_PASS', rb'NATIVE_CONSOLE_OLD_PASS kind=(read|readv|poll) '
        rb'pid=([1-9][0-9]*) parent=1 epoch=([1-9][0-9]*) attempts=([1-9][0-9]*) ' + REJECTIONS, 3)
    windows = rows(b'NATIVE_CONSOLE_WINDOW', rb'NATIVE_CONSOLE_WINDOW role=(guard|read|readv|poll) '
        rb'pid=([1-9][0-9]*) epoch=([0-9]+) control_epoch=([1-9][0-9]*) ' + REJECTIONS, 4)
    prompt, prompted = one(b'NATIVE_CONSOLE_PROMPT', rb'NATIVE_CONSOLE_PROMPT generation=2 '
        rb'pid=([1-9][0-9]*) epoch=([1-9][0-9]*) bytes=32')
    buffered, buffer = one(b'NATIVE_CONSOLE_BUFFERED', rb'NATIVE_CONSOLE_BUFFERED pid=([1-9][0-9]*) '
        rb'epoch=([1-9][0-9]*) ready=POLLIN')
    read_at, read = one(b'NATIVE_CONSOLE_READ_PASS', rb'NATIVE_CONSOLE_READ_PASS pid=([1-9][0-9]*) '
        rb'epoch=([1-9][0-9]*) bytes=32 readv=8 read=24 hash=([0-9]+)')
    guard_at, guard_pass = one(b'NATIVE_CONSOLE_GUARD_PASS', rb'NATIVE_CONSOLE_GUARD_PASS pid=([1-9][0-9]*) '
        rb'attempts=([1-9][0-9]*) ' + REJECTIONS)
    completed, final = one(b'NATIVE_CONSOLE_PASS', rb'NATIVE_CONSOLE_PASS pid=([1-9][0-9]*) '
        rb'epoch=([1-9][0-9]*) guard=live old_children=3 key=exact')
    for row in (prompted, buffer, read, final):
        need(int(row[1]) == next_pid and int(row[2]) == next_epoch, 'new console identity differs')
    need(int(read[3]) == key_hash(key), 'authorized console did not consume the exact injected key')
    need(int(guard_pass[1]) == guard_pid and int(guard_pass[2]) >= 5, 'root guard rejection rounds differ')
    need(leaders[0][0] < departing < leaders[1][0] < prompt < buffered < read_at < completed and
         read_at < guard_at < completed, 'console generation/input causal order differs')

    def keyed(records):
        need(len({row[1][1] for row in records}) == len(records), 'duplicate console role')
        return {row[1][1]: row for row in records}

    wait_by_role, revoked_by_role, pass_by_role, window_by_role = map(keyed, (waits, revoked, old_passes, windows))
    need(set(wait_by_role) == set(revoked_by_role) == set(pass_by_role) == set(roles) and
         set(window_by_role) == {b'guard', *roles}, 'missing console role')
    for role in roles:
        waiting, wait = wait_by_role[role]
        retired, revoke = revoked_by_role[role]
        passed, old = pass_by_role[role]
        window_at, window = window_by_role[role]
        pid = children[role]
        need(int(wait[2]) == int(revoke[2]) == int(old[2]) == int(window[2]) == pid and
             int(wait[3]) == first_pid and int(wait[4]) == int(revoke[3]) == int(old[3]) == int(window[3]) == first_epoch and
             int(window[4]) == next_epoch,
             'old descendant membership/parent identity differs')
        need(revoke[4] == (b'ERR_HUP' if role == b'poll' else b'EACCES') and int(old[4]) >= 5,
             'old descendant did not reject its original request')
        need(leaders[0][0] < waiting < departing < retired < prompt and
             buffered < window_at < read_at < passed < completed, 'old descendant causal order differs')
    guard_window_at, guard_window = window_by_role[b'guard']
    need(int(guard_window[2]) == guard_pid and int(guard_window[3]) == 0 and int(guard_window[4]) == next_epoch and
         buffered < guard_window_at < read_at, 'root guard did not reject access while input was buffered')
    need(all(i in accepted for i, line in enumerate(lines) if b'NATIVE_CONSOLE_' in line), 'unknown console record')

    events = []
    for i, line in enumerate(lines):
        if b'NATIVE_PID1 ' in line:
            match = EVENT.fullmatch(line)
            need(match is not None, 'malformed PID1 event')
            events.append((i, match))
    need(all(int(events[i - 1][1][5]) <= int(events[i][1][5]) for i in range(1, len(events))),
         'PID1 event time regressed')

    def event(kind, service, pid, generation, status=0):
        selected = [(i, row) for i, row in events if row[1] == kind and row[2] == service and
                    int(row[3]) == pid and int(row[4]) == generation]
        need(len(selected) == 1 and int(selected[0][1][7]) == 0 and int(selected[0][1][8]) == status,
             'missing/contradictory exact PID1 lifecycle')
        return selected[0][0]

    guard_launch = event(b'launch', b'guard', guard_pid, 1)
    guard_ready = event(b'notify-ready', b'guard', guard_pid, 1)
    first_launch = event(b'launch', b'console', first_pid, 1)
    first_ready = event(b'simple-ready', b'console', first_pid, 1)
    first_reap = event(b'reap', b'console', first_pid, 1, 37)
    restart = event(b'restart', b'console', 0, 1)
    next_launch = event(b'launch', b'console', next_pid, 2)
    next_ready = event(b'simple-ready', b'console', next_pid, 2)
    need(guard_launch < guard_start < guard_ready < first_launch < leaders[0][0] and
         first_launch < first_ready < departing < first_reap < restart < next_launch < leaders[1][0] and
         next_launch < next_ready < completed, 'PID1 supervision causal order differs')
    other = [(i, row) for i, row in events if row[1] == b'other-child']
    need(len(other) == 3, 'actual PID1 orphan reap count differs')
    for role, exit_value in zip(roles, (41, 42, 43)):
        at = event(b'other-child', b'none', children[role], 0, exit_value << 8)
        need(pass_by_role[role][0] < at, 'PID1 reaped an old child before its final denial record')
    for kind, service, count in ((b'launch', b'guard', 1), (b'launch', b'console', 2),
                                 (b'reap', b'console', 1), (b'reap', b'guard', 0),
                                 (b'restart', b'console', 1), (b'restart', b'guard', 0)):
        need(sum(row[1] == kind and row[2] == service for _, row in events) == count,
             'unexpected supervised process lifecycle')
    return dict(archive_root=True, guard_pid=guard_pid, leader_pids=[first_pid, next_pid],
                epochs=[first_epoch, next_epoch], old_child_pids=[children[role] for role in roles],
                actual_child_reaps=True, original_blocked_requests_revoked=True,
                unrelated_root_denied=True, buffered_input_attack_rounds=4,
                read_readv_poll=True, duplicate_descriptor_denied=True, native_controls_denied=True,
                key_sha256=hashlib.sha256(key).hexdigest(), key_hash=key_hash(key), input_echo=False,
                model_test=False, physical=False, smp=False, account_authentication=False,
                durable_password_storage=False, synchronized_shutdown=False)
