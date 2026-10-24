"""Join the validated18-case policy guest with typed kernel completion events.

The caller must also validate the complete user marker journal and command
grammar. This module checks the independent kernel side of those observations.
"""
import re
from native_child_exit_events import native_events, explicit_reap_batches
from native_child_exit_guest import INFO
from native_child_events import WAIT as NATIVE_WAIT, parsed

BEGIN = re.compile(rb'CHILD_EXIT_BEGIN arch=([a-z0-9_]+) case=([0-9]+) parent=([0-9]+)')
CASE = re.compile(rb'CHILD_EXIT_CASE arch=([a-z0-9_]+) case=([0-9]+) pid=([0-9]+) uid=([0-9]+)')
EVENT = re.compile(rb'CHILD_EXIT_EVENT arch=([a-z0-9_]+) case=([0-9]+) seq=([0-9]+) op=([A-Z_]+) a=(-?[0-9]+) b=(-?[0-9]+) c=(-?[0-9]+)')
DONE = re.compile(rb'CHILD_EXIT_DONE arch=([a-z0-9_]+) case=([0-9]+) pid=([0-9]+) events=([0-9]+) handlers=([0-9]+)')
WAIT = re.compile(rb'CHILD_EXIT_REAP arch=([a-z0-9_]+) case=([0-9]+) parent=([0-9]+) child=([0-9]+) status=0')


def join_native_waits(span, lifecycle):
    """Bind recorded successful waits to a unique preceding owned completion.

    Immediate WNOHANG observations have no blocking-wait record. They are
    joined separately through the exact user journal. The caller still checks
    the complete request/ticket ledger, including its inherited owner.
    """
    exits = {r['child']: r for r in lifecycle if r['tag'] == 'OK_NATIVE_CHILD_EXIT'}
    collected, waits = set(), []
    for position, line in enumerate(span.splitlines()):
        if not NATIVE_WAIT.fullmatch(line):
            continue
        row = parsed(NATIVE_WAIT, line)
        row['position'] = position
        waits.append(row)
        if row['outcome'] != 'complete' or row['result'] <= 0:
            continue
        child = exits.get(row['result'])
        if (child is None or child['child'] in collected or child['autoreap'] or
                child['parent'] != row['pid'] or child['position'] >= position):
            raise ValueError('owned wait lacks unique preceding child completion')
        collected.add(child['child'])
    return waits


def validate_native_pipeline(span, arch, native_parent, require_two_pairs=True):
    """Qualify this pinned shell's two successful blocking pipeline waits.

    The policy campaign requires two arm/complete pairs. The separate lineage
    campaign permits immediate-ready waits without blocking diagnostics. Both
    require two exact native completions and strict metadata/causality for every
    emitted wait; immediate-ready mode does not claim per-wait trace coverage.
    """
    lifecycle = native_events(span, arch)
    exits = {r['child']: r for r in lifecycle if r['tag'] == 'OK_NATIVE_CHILD_EXIT'}
    waits = join_native_waits(span, lifecycle)
    counts = (4,) if require_two_pairs else (0,2,4)
    if not native_parent or len(lifecycle) != 2 or len(exits) != 2 or len(waits) not in counts:
        raise ValueError('native pipeline lacks two exact child completions and wait pairs')
    expected = dict(parent=native_parent, parent_tid=0, parent_epoch=0, uid=0,
                    code=1, status=0, wait_code=1, wait_status=0, published=0,
                    notify=0, queued=0, coalesced=0, autoreap=0)
    if any(r[k] != v for r in exits.values() for k,v in expected.items()):
        raise ValueError('native pipeline completion changed shell ownership or exit cause')
    selected = set()
    for arm, complete in zip(waits[::2], waits[1::2]):
        child = exits.get(complete['result'])
        if (child is None or child['child'] in selected or
                any(r[k] != v for r in (arm, complete) for k,v in
                    dict(pid=native_parent, tid=native_parent, selector=child['child'], format='status').items()) or
                arm['outcome'] != 'arm' or arm['result'] != -11 or arm['live'] != 2 or
                complete['outcome'] != 'complete' or complete['live'] != 1 or
                not 0 < arm['request'] == arm['wait'] == complete['request'] == complete['wait'] or
                not 0 < arm['output'] == complete['output'] or
                not arm['position'] < child['position'] < complete['position']):
            raise ValueError('native pipeline lost its exact shell-owned child wait')
        selected.add(child['child'])
    if require_two_pairs and selected != set(exits):
        raise ValueError('native pipeline did not collect both completed children')


def validate_join(span, arch, marker, native_parent):
    lines = span.splitlines()
    lifecycle = native_events(span, arch)
    native_waits = join_native_waits(span, lifecycle)
    exits = {r['child']: r for r in lifecycle if r['tag'] == 'OK_NATIVE_CHILD_EXIT'}
    beginnings = [(i, BEGIN.fullmatch(line)) for i, line in enumerate(lines) if BEGIN.fullmatch(line)]
    cases = [(i, CASE.fullmatch(line)) for i, line in enumerate(lines) if CASE.fullmatch(line)]
    done = [(i, DONE.fullmatch(line)) for i, line in enumerate(lines) if DONE.fullmatch(line)]
    waits = [(i, WAIT.fullmatch(line)) for i, line in enumerate(lines) if WAIT.fullmatch(line)]
    if any(len(rows) != 18 for rows in (beginnings, cases, done, waits)) or lines.count(marker) != 1:
        raise ValueError('child lifecycle join needs all18 validated guest cases')
    main = int(beginnings[0][1][3])
    selected, epochs, uids = set(), {}, set()
    autoreap = notifications = coalesced = 0

    def expect(child, parent, tid, uid, status, notify, automatic, merged):
        row = exits.get(child)
        if row is None or child in selected:
            raise ValueError('missing or reused actual child completion')
        code, value = (2, 15) if status == 15 else (1, status >> 8)
        expected = dict(parent=parent, parent_tid=tid, uid=uid, code=code,
                        status=value, wait_code=code, wait_status=value,
                        published=1, notify=notify, queued=notify-merged,
                        coalesced=merged, autoreap=automatic)
        if any(row[k] != v for k, v in expected.items()) or not row['parent_epoch']:
            raise ValueError('kernel child completion differs from observed policy')
        if parent in epochs and epochs[parent] != row['parent_epoch']:
            raise ValueError('kernel child parent owner changed within its lifetime')
        epochs[parent] = row['parent_epoch']
        selected.add(child)
        return row

    for ordinal, ((start, begin), (case_at, case), (done_at, finish), (wait_at, wait)) in enumerate(zip(beginnings, cases, done, waits)):
        if any(m[1].decode() != arch or int(m[2]) != ordinal for m in (begin, case, finish, wait)):
            raise ValueError('kernel join has a reordered guest case')
        pid, uid = int(case[3]), int(case[4])
        uids.add(uid)
        if (int(begin[3]) != main or int(wait[3]) != main or int(finish[3]) != pid or int(wait[4]) != pid or
                not start < case_at < done_at < wait_at or ordinal and start <= waits[ordinal-1][0]):
            raise ValueError('kernel join has inconsistent user process identities')
        observations = []
        for position in range(case_at + 1, done_at):
            match = EVENT.fullmatch(lines[position])
            if match:
                observations.append(dict(position=position, op=match[4].decode(),
                                         a=int(match[5]), b=int(match[6]), c=int(match[7])))
        spawns = [r for r in observations if r['op'] == 'SPAWN']
        if len(spawns) != (2 if ordinal in (13, 15, 16) else 1):
            raise ValueError('kernel join has an incomplete subject list')
        for slot, spawn in enumerate(spawns):
            child = spawn['b']
            if spawn['a'] != slot:
                raise ValueError('kernel join reordered child slots')
            if ordinal < 12:
                kind, blocked, no_wait = ordinal // 4, ordinal // 2 % 2, ordinal % 2
                notify = int(kind != 1 and (kind == 2 or blocked))
                automatic = int(kind == 1 or no_wait)
                merged = 0
            else:
                notify, automatic = 1, 0
                merged = int(ordinal == 14 or ordinal in (13, 16) and slot == 1)
            row = expect(child, pid, pid, uid, spawn['c'], notify, automatic, merged)
            releases = [r for r in observations if r['op'] == 'RELEASE' and r['a'] == slot and r['b'] == child]
            collected = [r for r in observations if r['op'] in ('WAIT', 'ECHILD') and r['a'] == slot and r['b'] == child]
            if len(collected) != 1 or collected[0]['op'] != ('ECHILD' if automatic else 'WAIT'):
                raise ValueError('child observation does not match its autoreap policy')
            if not case_at < row['position'] < collected[0]['position'] < done_at:
                raise ValueError('child user collection precedes actual completion')
            # The fork inspector has no child gate and may complete before its
            # parent prints SPAWN. Every other subject is released explicitly.
            if not (ordinal == 16 and slot == 1):
                if len(releases) != 1 or not spawn['position'] < releases[0]['position'] < row['position']:
                    raise ValueError('child completed before its observed pipe release')
                pending = [r for r in observations if r['op'] == 'PENDING' and r['a'] == 1 and
                           releases[0]['position'] < r['position'] < collected[0]['position']]
                if notify and pending and row['position'] >= pending[0]['position']:
                    raise ValueError('user observed pending notification before child completion')
            elif releases:
                raise ValueError('fork inspector unexpectedly claimed a release gate')
            for at in range(case_at + 1, done_at):
                info = INFO.fullmatch(lines[at])
                if info and int(info[7]) == child and int(info[6]) in (1, 2) and at <= row['position']:
                    raise ValueError('user observed typed child siginfo before completion')
            autoreap += automatic
            notifications += notify
            coalesced += merged
        parent_exit = expect(pid, main, main, uid, 0, 0, 0, 0)
        if not done_at < parent_exit['position'] < wait_at:
            raise ValueError('scenario worker was collected before completing')
    initial = exits.get(main)
    if initial is None or main in selected or not lines.index(marker) < initial['position']:
        raise ValueError('probe process completion does not follow its final observation')
    if not native_parent or initial['parent'] != native_parent or initial['parent'] in selected or uids != {initial['uid']}:
        raise ValueError('probe does not retain its observed shell parent and credentials')
    # This campaign is launched by the continuously live native shell. A parent0
    # service launch is a different contract and cannot coexist with its wait.
    if any(initial[k] for k in ('parent_tid', 'parent_epoch', 'notify', 'queued', 'coalesced', 'autoreap')) or any(
            initial[k] != v for k, v in dict(code=1, status=0, wait_code=1, wait_status=0, published=1).items()):
        raise ValueError('probe exit escaped the native shell/service boundary')
    selected.add(main)
    # All guest-side waits use bounded WNOHANG. The only blocking waiter is the
    # shell waiting for the long-running main, and it must retain that exact
    # request through actual completion. Do not accept an unrelated PID ledger.
    if len(native_waits) != 2:
        raise ValueError('child-exit campaign lacks exact shell wait pair')
    arm, complete = native_waits
    if (any(r[k] != v for r in native_waits for k,v in
            dict(pid=native_parent, tid=native_parent, selector=main, format='status').items()) or
            arm['outcome'] != 'arm' or arm['result'] != -11 or arm['live'] != 2 or
            complete['outcome'] != 'complete' or complete['result'] != main or complete['live'] != 1 or
            not 0 < arm['request'] == arm['wait'] == complete['request'] == complete['wait'] or
            not 0 < arm['output'] == complete['output'] or
            not arm['position'] < beginnings[0][0] < initial['position'] < complete['position']):
        raise ValueError('shell wait differs from observed main process lifetime')
    if selected != set(exits) or len(exits) != 40 or autoreap != 8:
        raise ValueError('extra or missing child lifecycle completion')
    batches = explicit_reap_batches(lifecycle)
    count = sum(r['count'] for r in batches)
    if count != autoreap:
        raise ValueError('physical child reaps do not cover exact automatic completions')
    return dict(completions=len(exits), automatic_detaches=autoreap, notifications=notifications,
                coalesced=coalesced, physical_reaps=count, reap_batches=batches,
                main_pid=main, main_parent=initial['parent'])
