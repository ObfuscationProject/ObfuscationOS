"""Typed private completion diagnostics; user observations supply semantics evidence."""
import re

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv64', 'rv32',
          'loongarch64', 'mips', 'mips64', 'ppc')
EXIT_FIELDS = ('child', 'parent', 'parent_tid', 'parent_epoch', 'uid', 'code',
               'status', 'wait_code', 'wait_status', 'published', 'notify',
               'queued', 'coalesced', 'autoreap')
REAP_FIELDS = ('count', 'failed_pid', 'failed_after_erase', 'success')
EXIT_PREFIX = b'OK_NATIVE_CHILD_EXIT'
REAP_PREFIX = b'OK_NATIVE_CHILD_REAP'
EXIT = re.compile(EXIT_PREFIX + b' ' + b' '.join(n.encode() + rb'=([0-9]+)' for n in EXIT_FIELDS))
REAP = re.compile(REAP_PREFIX + b' ' + b' '.join(n.encode() + rb'=([0-9]+)' for n in REAP_FIELDS))


def parse(line, arch):
    if arch not in ARCHES:
        raise ValueError('unknown child-exit target profile')
    pattern, fields = (EXIT, EXIT_FIELDS) if EXIT_PREFIX in line else (REAP, REAP_FIELDS)
    match = pattern.fullmatch(line)
    if not match:
        raise ValueError('malformed native child-exit diagnostic')
    row = dict(zip(fields, map(int, match.groups())))
    row.update(tag=line.split()[0].decode(), line=line)
    if pattern is REAP:
        if (row['count'] > 0xffffffff or row['failed_pid'] > 0xffffffff or
                row['failed_after_erase'] not in (0, 1) or row['success'] not in (0, 1)):
            raise ValueError('invalid checked child-reap result')
        if not row['success']:
            # A checked reap failure stops native service; partial erases do
            # not make the command an accepted execution.
            raise ValueError('native checked child reaper failed')
        if not row['count'] or row['failed_pid'] or row['failed_after_erase']:
            raise ValueError('contradictory successful child reap')
        return row
    if (not 0 < row['child'] <= 0xffffffff or
            not 0 <= row['parent'] <= 0xffffffff or row['child'] == row['parent'] or
            not 0 <= row['parent_tid'] <= 0xffffffff or
            not 0 <= row['parent_epoch'] <= 0xffffffffffffffff or
            not 0 <= row['uid'] <= 0xffffffff):
        raise ValueError('invalid child completion identity')
    maximum = 128 if arch in ('mips', 'mips64') else 64
    for code, status in (('code', 'status'), ('wait_code', 'wait_status')):
        if not (row[code] == 1 and 0 <= row[status] <= 255 or
                row[code] == 2 and 0 < row[status] <= maximum):
            raise ValueError('invalid typed child completion cause')
    if any(row[name] not in (0, 1) for name in ('published', 'notify', 'queued', 'coalesced', 'autoreap')):
        raise ValueError('invalid child completion policy bit')
    if row['queued'] + row['coalesced'] != row['notify']:
        raise ValueError('child notification publication contradicts policy')
    if bool(row['parent_tid']) != bool(row['parent_epoch']):
        raise ValueError('incomplete named parent signal owner')
    # An unpublished child or a native-personality boundary bypasses Linux
    # child management. Parent0 is the service reaper, never a recipient.
    if not row['published'] or not row['parent'] or not row['parent_epoch']:
        if any(row[name] for name in ('parent_tid', 'parent_epoch', 'notify', 'queued', 'coalesced', 'autoreap')):
            raise ValueError('child policy escaped its qualified parent boundary')
    return row


def native_events(span, arch):
    events, completed = [], set()
    for position, line in enumerate(span.splitlines()):
        if EXIT_PREFIX not in line and REAP_PREFIX not in line:
            continue
        row = parse(line, arch)
        row['position'] = position
        if row['tag'] == EXIT_PREFIX.decode():
            if row['child'] in completed:
                raise ValueError('duplicate child group completion')
            completed.add(row['child'])
        events.append(row)
    return events


def wait_ledger_view(span, events):
    """Remove only already-validated lifecycle lines for the separate wait ledger.

    The original transcript remains the source for command/guest parsing. This
    view does not erase page or stack accounting, nor allow unknown CHILD tags.
    """
    exact = {row['position']: row['line'] for row in events}
    if len(exact) != len(events):
        raise ValueError('duplicate lifecycle positions')
    lines = span.splitlines(keepends=True)
    for position, value in exact.items():
        if not 0 <= position < len(lines) or lines[position].rstrip(b'\r\n') != value:
            raise ValueError('lifecycle view differs from validated original')
    return b''.join(line for position, line in enumerate(lines) if position not in exact)


def explicit_reap_batches(events):
    """Check a campaign with no unobserved orphaned waitable children.

    Each successful checked service reap scans the complete parent0 set. The
    policy guest explicitly waits all non-autoreaped children before its parent
    exits. Its integration collector must establish that restriction before
    using this ledger; these counts alone do not establish general PID lifetime.
    """
    eligible, batches = set(), []
    for row in events:
        if row['tag'] == EXIT_PREFIX.decode():
            if row['autoreap'] or row['parent'] == 0:
                eligible.add(row['child'])
        elif row['tag'] == REAP_PREFIX.decode():
            if row['count'] != len(eligible):
                raise ValueError('checked child reap differs from explicit completions')
            batches.append(dict(position=row['position'], count=row['count'],
                                completed_pids=sorted(eligible)))
            eligible.clear()
        else:
            raise ValueError('unknown event in child reap ledger')
    if eligible:
        raise ValueError('explicit child completions were not physically reaped')
    return batches
