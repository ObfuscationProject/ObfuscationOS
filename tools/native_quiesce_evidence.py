"""Admit causal service-quiesce serial records, independently of build success."""
import re

EVENT = re.compile(rb'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event=([a-z-]+) '
    rb'service=([A-Za-z0-9_-]+) pid=([0-9]+) generation=([0-9]+) time_ms=([0-9]+) '
    rb'next_ms=([0-9]+) errno=([0-9]+) status=([0-9]+)')


def validate_quiesce(serial):
    """A live observer blocks ECHILD; its actual reap must precede completion."""
    lines = serial.replace(b'\r\n', b'\n').splitlines()

    def need(value, message):
        if not value:
            raise ValueError(message)

    for marker in (b'NATIVE_QUIESCE_FAIL', b'event=fatal-hold', b'OK_TEST_FAIL', b'Kernel panic'):
        need(marker not in serial, 'quiesce lane failure: ' + marker.decode())

    def one(prefix, pattern):
        found = [(i, re.fullmatch(pattern, line)) for i, line in enumerate(lines) if prefix in line]
        need(len(found) == 1 and found[0][1] is not None, 'missing, malformed or duplicate ' + prefix.decode())
        return found[0]

    denied, _ = one(b'NATIVE_QUIESCE_DENIED',
        rb'NATIVE_QUIESCE_DENIED uid=1000 state=public mutation=unchanged')
    begin, identity = one(b'NATIVE_QUIESCE_BEGIN', rb'NATIVE_QUIESCE_BEGIN observer=([1-9][0-9]*) parent=1')
    pid = int(identity[1])
    need(pid > 1, 'invalid adopted observer identity')
    held, state = one(b'NATIVE_QUIESCE_HELD', rb'NATIVE_QUIESCE_HELD observer=([1-9][0-9]*) '
        rb'phase=quiescing graph=stopped children=live started_ms=([0-9]+) deadline_ms=([0-9]+)')
    released, retired = one(b'NATIVE_QUIESCE_RELEASE', rb'NATIVE_QUIESCE_RELEASE observer=([1-9][0-9]*) '
        rb'graph=stopped children=live duplicate=pass restart=busy wait_exit=37')
    accepted, budget = one(b'OK_INIT_CONTROL 1 QUIESCE accepted=',
        rb'(?:oksh> )?OK_INIT_CONTROL 1 QUIESCE accepted=1 started_ms=([0-9]+) deadline_ms=([0-9]+)')
    need(accepted + 1 < len(lines) and lines[accepted + 1] == b'END' and
         (accepted + 2 == len(lines) or lines[accepted + 2] != b'END'),
         'missing, malformed or duplicate quiesce acknowledgment terminator')
    started, deadline = int(state[2]), int(state[3])
    need(int(state[1]) == int(retired[1]) == pid and tuple(map(int, budget.groups())) == (started, deadline),
         'quiesce observer/deadline identity differs')
    need(deadline - started == 18000, 'quiesce absolute budget differs')
    events = []
    previous_time = 0
    for i, line in enumerate(lines):
        if b'NATIVE_PID1 ' in line:
            match = EVENT.fullmatch(line[line.find(b'NATIVE_PID1 '):])
            need(match is not None, 'malformed PID1 record')
            need(int(match[5]) >= previous_time, 'PID1 event time moved backwards')
            previous_time = int(match[5])
            events.append((i, match))

    def event(kind, service=b'none', process=1, generation=0):
        found = [(i, row) for i, row in events if row[1] == kind and row[2] == service and
                 int(row[3]) == process and int(row[4]) == generation]
        need(len(found) == 1 and found[0][1][7] == b'0', 'missing/duplicate/error quiesce event ' + kind.decode())
        return found[0]

    stop, stop_event = event(b'quiesce-started')
    graph, _ = event(b'graph-stopped')
    reap, reap_event = event(b'other-child', process=pid)
    complete, complete_event = event(b'quiesced')
    need(denied < begin < stop < graph < held < released < reap < complete and begin < accepted < held,
         'quiesce completion precedes actual child retirement')
    need(int(reap_event[8]) == 37 << 8 and complete_event[8] == b'0', 'observer raw wait status differs')
    need(started <= int(stop_event[5]) <= int(complete_event[5]) < deadline,
         'quiesce completion is outside its original deadline')
    for i, row in events:
        if row[1] in (b'quiesce-started', b'graph-stopped', b'quiesced'):
            need(row[2] == b'none' and row[3] == b'1' and row[4] == b'0' and row[7] == row[8] == b'0',
                 'contradictory quiesce lifecycle event')
        if i >= stop:
            need(started <= int(row[5]) < deadline, 'quiesce event is outside its original deadline')
            need(row[1] not in (b'launch', b'simple-ready', b'notify-ready', b'oneshot-ready'),
                 'service relaunched or became ready during quiesce')
        if i >= graph:
            need(row[2] == b'none', 'service action follows stopped graph')
    owners = {pid}
    for service in (b'provider', b'dependent'):
        generation_rows = [row for _, row in events if row[1] == b'launch' and row[2] == service and row[4] == b'3']
        need(len(generation_rows) == 1, 'missing final service generation')
        owner = int(generation_rows[0][3])
        need(owner > 1 and owner not in owners, 'final service/observer process identities overlap')
        owners.add(owner)
        term, _ = event(b'term', service, owner, 3)
        gone, final_status = event(b'reap', service, owner, 3)
        need(final_status[8] == b'128', 'infinite service did not retire by signal')
        need(stop < term < gone < graph, 'service shutdown retirement is incomplete')
        if service == b'dependent':
            dependent_reap = gone
        else:
            provider_term = term
    need(dependent_reap < provider_term, 'provider stopped before dependent reap')
    return dict(observer_pid=pid, observer_wait_exit=37, graph_stopped=True,
                live_adopted_child_blocked=True, actual_reap_before_completion=True,
                started_ms=started, deadline_ms=deadline, quiesced=True,
                synchronized_shutdown=False, platform_power=False)
