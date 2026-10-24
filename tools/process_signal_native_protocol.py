"""Bind process-signal guest claims to owned native pipe continuations.

The shared pipe ledger validates every descriptor, retained description, object,
generation, origin and terminal. This layer adds guest identity and causality.
"""
from native_signal_delivery_x86_64_evidence import IMAGE


def only(rows, label):
    if len(rows) != 1:
        raise ValueError('process signal requires one ' + label)
    return rows[0]


def validate_owned_waits(raw, arch, guest, events):
    begins = [r for r in guest if r['tag'] == 'CASE_BEGIN']
    parents = [r for r in guest if r['tag'] == 'PARENT_PASS']
    if len(begins) != len(parents):
        raise ValueError('process signal native case boundaries differ')
    assigned = set()
    result = dict(owned_requests=0, interrupted_reads=0, cancelled_reads=0,
                  incidental_gate_requests=0, simultaneous_two_waits=0,
                  console_group_terminations=0, exec_images=0)
    image_positions = [i for i, line in enumerate(raw.splitlines()) if IMAGE.fullmatch(line)]
    for begin, parent in zip(begins, parents):
        low, high = begin['position'], parent['position']
        part = [r for r in guest if low < r['position'] < high]
        native = [r for r in events if low < r['position'] < high]
        assigned.update(r['position'] for r in native)
        case, pid = begin['case'], begin['pid']
        threads = {r['actor']: r['tid'] for r in part if r['tag'] == 'THREAD'}
        images = [i for i in image_positions if low < i < high]
        if len(images) != int(case in (20, 21)):
            raise ValueError('process signal exec image cardinality differs')
        if images:
            commit = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'EXEC_COMMIT'], 'exec commit')
            replaced = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'EXEC_REPLACED'], 'exec replacement')
            if not commit['position'] < images[0] < replaced['position']:
                raise ValueError('process signal exec publication outside committed replacement')
            result['exec_images'] += 1
        if any(r['direction'] or r['vector'] or r.get('large') or r['pid'] != pid or
               r['tid'] not in (pid, *threads.values()) for r in native):
            raise ValueError('process signal foreign native pipe owner or operation')
        if case == 0:
            gate = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'ZOMBIE_GATE'], 'zombie gate')
            eof = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'ZOMBIE_EOF'], 'zombie EOF')
            if any(r['tid'] != pid or r['fd'] != gate['value'] or r['bytes'] != 1 or
                   not gate['position'] < r['position'] < eof['position'] or r['event'] == 'SIGNAL' for r in native):
                raise ValueError('process signal incidental gate read escaped its exact owner/descriptor')
            terminals = [r for r in native if r['event'] == 'COMPLETE']
            if any(r['origin_record'] is None for r in terminals):
                raise ValueError('process signal incidental gate read lacks its qualified origin')
            if len(terminals) > 2 or any((r['outcome'], r['result']) not in (('ready', 1), ('eof', 0)) for r in terminals):
                raise ValueError('process signal incidental gate read has unexpected retirement')
            if len(terminals) == 2 and [(r['outcome'], r['result']) for r in terminals] != [('ready', 1), ('eof', 0)]:
                raise ValueError('process signal gate read completion order differs')
            result['incidental_gate_requests'] += len(terminals)
            continue
        if case not in (23, 24, 25, 32):
            if native:
                raise ValueError('unexpected pipe wait in process signal case')
            continue
        pipes = {r['role']: r for r in part if r['tag'] == 'PIPE'}
        read = only([r for r in part if r['tag'] == 'READ_BEGIN'], 'worker read')
        leader_read = [r for r in part if r['tag'] == 'LEADER_READ']
        owned = {0: [r for r in native if r['tid'] == threads[0]],
                 9: [r for r in native if r['tid'] == pid]}
        if any(r['tid'] not in (threads[0], pid) for r in native):
            raise ValueError('process signal unassigned native waiter')
        if case == 23 and owned[9] or case == 32 and owned[9]:
            raise ValueError('unexpected owned leader pipe read')
        if case != 23 and len(leader_read) != 1:
            raise ValueError('missing group fatal leader read')
        for role in (0, 9):
            if role == 9 and case in (23, 32):
                continue
            rows = owned[role]
            attempt = read if role == 0 else leader_read[0]
            pipe = pipes[0 if role == 0 else 1]
            arms = [r for r in rows if r['event'] == 'WAIT' and r['stage'] == 'arm']
            terms = [r for r in rows if r['event'] == 'COMPLETE']
            origins = [r for r in rows if r['event'] == 'ORIGIN']
            signals = [r for r in rows if r['event'] == 'SIGNAL']
            expected = 2 if case == 23 else 1
            if len(arms) != expected or len(terms) != expected or len(origins) != expected or len(signals) != int(case == 23):
                raise ValueError('process signal owned read cardinality differs')
            if any(r['fd'] != pipe['readfd'] or r['output'] != attempt['input'] or
                   r['bytes'] != 1 or r['event'] in ('ORIGIN', 'SIGNAL') and r['syscall'] != begin['read'] for r in rows):
                raise ValueError('process signal copied read identity differs')
            if not attempt['position'] < arms[0]['position']:
                raise ValueError('process signal owned read preceded its attempt')
            for arm, origin in zip(arms, origins):
                if arm['request'] != origin['request'] or not arm['position'] < origin['position']:
                    raise ValueError('process signal read lost its origin')
                if role == 0 and not begin['variant'] and origin['pc'] != begin['resume']:
                    raise ValueError('process signal read raw continuation differs')
            if case == 23:
                handler = only([r for r in part if r['tag'] == 'HANDLE'], 'read handler')
                sends = [r for r in part if r['tag'] == 'KILL_BEGIN']
                send = only(sends, 'read interrupt send')
                awaits = [r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'READ_AWAIT']
                release = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'READ_RELEASE'], 'read release')
                returns = [r for r in part if r['tag'] == 'READ_RETURN']
                if len(awaits) != 2 or [(r['outcome'], r['result']) for r in terms] != [('interrupted', 0 if begin['restart'] else -4), ('ready', 1)]:
                    raise ValueError('process signal read interrupt/ready terminal differs')
                if signals[0]['signal'] != begin['usr1'] or signals[0]['outcome'] != ('restart' if begin['restart'] else 'eintr') or handler['pc'] != signals[0]['pc']:
                    raise ValueError('process signal caught frame differs from native signal publication')
                if not origins[0]['position'] < awaits[0]['position'] < send['position'] < terms[0]['position'] < signals[0]['position'] < handler['position'] < arms[1]['position']:
                    raise ValueError('process signal read send/interruption/retry order differs')
                if not origins[1]['position'] < awaits[1]['position'] < release['position'] < terms[1]['position'] < returns[-1]['position']:
                    raise ValueError('process signal resumed read was not blocked before release')
                for awaited, arm in zip(awaits, arms):
                    latest = [r for r in rows if r['event'] in ('WAIT', 'COMPLETE') and r['position'] < awaited['position']]
                    if not latest or latest[-1]['event'] != 'WAIT' or latest[-1]['request'] != arm['request']:
                        raise ValueError('process signal await lacks a live owned request')
                if not begin['restart']:
                    retry = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'READ_RETRY'], 'explicit read retry')
                    if not handler['position'] < returns[0]['position'] < retry['position'] < arms[1]['position']:
                        raise ValueError('process signal explicit retry order differs')
                result['interrupted_reads'] += 1
            else:
                send = only([r for r in part if r['tag'] == 'KILL_BEGIN'], 'group fatal send')
                awaited = only([r for r in part if r['tag'] == 'EVENT' and r['tag_value'] == 'GROUP_AWAIT'], 'group await')
                if (terms[0]['outcome'], terms[0]['result']) != ('cancelled', -125) or not origins[0]['position'] < awaited['position'] < send['position'] < terms[0]['position'] < high:
                    raise ValueError('process signal group fatal cancellation differs')
                result['cancelled_reads'] += 1
            result['owned_requests'] += expected
        if case in (24, 25):
            if max((r.get('live', 0) for r in native), default=0) != 2:
                raise ValueError('process signal fatal case lacks simultaneous owned reads')
            result['simultaneous_two_waits'] += 1
        elif case == 32:
            result['console_group_terminations'] += 1
    if assigned != {r['position'] for r in events}:
        raise ValueError('process signal native events escaped case scope')
    return result
