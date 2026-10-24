"""Join the pressure journal to typed child exits, blocked reads and safe reaps."""
from native_child_exit_events import explicit_reap_batches
from native_child_exit_pressure_guest import require


def validate_joins(guest, lifecycle, pipes, native_parent):
    exits = {row['child']: row for row in lifecycle if row['tag'] == 'OK_NATIVE_CHILD_EXIT'}
    require(len(exits) == sum(row['tag'] == 'OK_NATIVE_CHILD_EXIT' for row in lifecycle),
            'duplicate process completion')
    main, uid = guest['pid'], guest['uid']
    assigned, successful, epochs, pipe_positions = set(), set(), set(), set()
    rollbacks, results = [], []

    def completion(pid, status, release, observed, automatic, notify):
        require(pid in exits and pid not in assigned, 'missing or reused child completion')
        row = exits[pid]
        expected = dict(parent=main, parent_tid=main, uid=uid, code=1, status=status,
                        wait_code=1, wait_status=status, published=1,
                        autoreap=int(automatic), notify=int(notify))
        require(all(row[k] == value for k, value in expected.items()) and row['parent_epoch'] > 0,
                'child owner, cause or completion policy')
        require(release < row['position'] < observed, 'child completion outside release/wait window')
        assigned.add(pid)
        successful.add(pid)
        epochs.add(row['parent_epoch'])
        return row

    def read_gate(pid, opening, release, exit_position, must_block):
        rows = [row for row in pipes if row['pid'] == pid]
        require(all(row['tid'] == pid and row['direction'] == 0 and not row['vector'] and
                    not row.get('large', False) and row['bytes'] == 1 for row in rows),
                'gate read changed owner or operation')
        if not rows:
            require(not must_block, 'pressure child lacks actual blocked read')
            return False
        arms = [row for row in rows if row['event'] == 'WAIT']
        ends = [row for row in rows if row['event'] == 'COMPLETE']
        origins = [row for row in rows if row['event'] == 'ORIGIN']
        require(len(arms) >= 1 and len(ends) == 1 and len(origins) <= 1 and
                len(rows) == len(arms) + len(ends) + len(origins),
                'gate read has extra completion or publication')
        arm, end = arms[0], ends[0]
        require(arm['stage'] == 'arm' and all(row['stage'] == 'rearm' for row in arms[1:]) and
                all(arm['position'] < row['position'] < end['position'] for row in arms[1:]) and
                end['outcome'] == 'ready' and
                end['result'] == 1 and end['pinned'] == 0,
                'gate did not complete exactly one byte')
        require(opening < arm['position'] < end['position'] < exit_position and
                release < end['position'], 'gate lifetime ordering')
        if must_block:
            require(arm['position'] < release, 'pressure read was not armed before release')
        pipe_positions.update(row['position'] for row in rows)
        return True

    for wave in guest['waves']:
        index = wave['wave']
        records = []
        opening = {attempt['end']['a']: attempt['begin']['position']
                   for attempt in wave['attempts'] if attempt['end']['op'] == 'SPAWN'}
        for pid, observed in zip(wave['children'], wave['waits']):
            row = completion(pid, 37, wave['release']['position'], observed['position'],
                             automatic=index != 0, notify=index != 1)
            read_gate(pid, opening[pid], wave['release']['position'], row['position'], True)
            records.append(row)
        records.sort(key=lambda row: row['position'])
        if index == 1:
            require(all(not row['queued'] and not row['coalesced'] for row in records),
                    'explicit ignore generated a notification')
        else:
            require(records[0]['queued'] == 1 and records[0]['coalesced'] == 0 and
                    all(row['queued'] == 0 and row['coalesced'] == 1 for row in records[1:]),
                    'notification did not retain the first completion')
            require(wave['notification']['child'] == records[0]['child'] and
                    records[-1]['position'] < wave['notification']['position'],
                    'coalesced payload differs from the actual queued child')
        # Created-but-unpublished rollback is internal cleanup, not a child
        # returned by fork. Only a bounded ENOMEM call can account for it.
        wave_rollbacks = []
        for failed in wave['failures']:
            inner = [row for row in exits.values()
                     if failed['begin']['position'] < row['position'] < failed['end']['position']]
            require(len(inner) <= 1, 'multiple completions inside failed fork')
            if not inner:
                continue
            row = inner[0]
            expected = dict(parent=main, parent_tid=0, parent_epoch=0, uid=uid,
                            code=1, status=127, wait_code=1, wait_status=127,
                            published=0, notify=0, queued=0, coalesced=0, autoreap=0)
            require(failed['errno'] == 12 and row['child'] not in assigned and
                    row['child'] != main and all(row[k] == value for k, value in expected.items()),
                    'failed fork contains an unqualified rollback completion')
            assigned.add(row['child'])
            wave_rollbacks.append(row['child'])
            rollbacks.append(row['child'])
        recovery = wave['recovery']
        row = completion(recovery['pid'], 39, recovery['release']['position'],
                         recovery['wait']['position'], False, True)
        require(row['queued'] == 1 and row['coalesced'] == 0 and
                recovery['info']['child'] == row['child'] and row['position'] < recovery['info']['position'],
                'recovery notification differs from its completion')
        read_gate(row['child'], recovery['begin']['position'], recovery['release']['position'],
                  row['position'], False)
        results.append(dict(wave=index, successful_children=len(records),
                            failed_forks=len(wave['failures']), rollback_pids=wave_rollbacks,
                            queued_sender=records[0]['child'] if index != 1 else None,
                            recovery_pid=recovery['pid'], automatic_reaps=len(records) if index else 0))
    require(len(epochs) == 1, 'parent owner epoch changed within the single-threaded controller')
    require(set(row['position'] for row in pipes) == pipe_positions,
            'unassigned pipe activity in pressure command')
    require(main in exits and main not in assigned, 'missing controller completion')
    final = exits[main]
    expected = dict(parent=native_parent, parent_tid=0, parent_epoch=0, uid=uid,
                    code=1, status=0, wait_code=1, wait_status=0, published=1,
                    notify=0, queued=0, coalesced=0, autoreap=0)
    require(native_parent > 0 and all(final[k] == value for k, value in expected.items()) and
            guest['success']['position'] < final['position'], 'controller lost native shell ownership')
    assigned.add(main)
    require(assigned == set(exits), 'unobserved or unassigned process completion')
    require(len(successful) + 1 == guest['expected_published_completions'],
            'published completion count differs from successful fork journal')
    batches = explicit_reap_batches(lifecycle)
    expected_reaps = {pid for wave in guest['waves'] if wave['wave'] != 0 for pid in wave['children']}
    reaped = [pid for batch in batches for pid in batch['completed_pids']]
    require(len(reaped) == len(expected_reaps) and set(reaped) == expected_reaps,
            'automatic detach and physical reclaim identities differ')
    return dict(waves=results, process_completions=len(exits),
                published_completions=len(successful) + 1, rollback_completions=len(rollbacks),
                successful_pressure_children=guest['pressure_children'],
                failed_forks=guest['failed_forks'], recovery_children=3,
                blocked_pressure_reads=guest['pressure_children'], automatic_physical_reaps=len(reaped),
                parent_epoch=next(iter(epochs)), main_pid=main, main_parent=native_parent,
                minimum_entry_leases=guest['minimum_entry_leases'],
                full_reap_accounting=True, natural_fork_exhaustion=True,
                global_process_exhaustion=False, vm_exhaustion=False, stack_exhaustion=False)
