"""Exact native FUTEX_WAIT diagnostic ledger, including incidental libc waits.

This parser never treats diagnostic text as proof of native execution by itself.
The dedicated collector supplies immutable SDK, image and serial provenance.
"""
import re
from kernel_sdk import ARCH_TRIPLES

WORD32 = ('i386', 'arm32', 'rv32', 'mips', 'ppc')
NUMBERS = dict(zip(('x86_64','i386','aarch64','arm32','rv32','rv64','loongarch64','mips','mips64','ppc'),
                   ((202,),(240,422),(98,),(240,422),(422,),(98,),(98,),(4238,4422),(5194,),(221,422))))
PREFIX = b'OK_NATIVE_FUTEX_'
OWNER = rb'pid=([0-9]+) tid=([0-9]+) wait=([0-9]+) origin=([0-9]+)'
INPUTS = rb' pc=([0-9]+) syscall=([0-9]+) address=([0-9]+) operation=([0-9]+) expected=([0-9]+) timeout=([0-9]+) deadline=([0-9]+)'
ARM = re.compile(PREFIX + rb'ARM ' + OWNER + INPUTS + rb' format=(time32|time64) live=([0-9]+)')
RETIRE = re.compile(PREFIX + rb'RETIRE ' + OWNER + rb' reason=(ready|timeout|interrupted|cancelled) result=(-?[0-9]+) live=([0-9]+)')
SIGNAL = re.compile(PREFIX + rb'SIGNAL ' + OWNER + rb' signal=([0-9]+) outcome=(eintr|restart)' + INPUTS + rb' live=([0-9]+)')
PATTERNS = (ARM, RETIRE, SIGNAL)

def parse(pattern, line):
    if not pattern.fullmatch(line):
        raise ValueError('malformed futex evidence event: ' + line[:100].decode(errors='replace'))
    row = {'tag': line.split()[0].decode(), 'line': line}
    for field in line.split()[1:]:
        name,value = field.decode().split('=',1)
        row[name] = value if name in ('arch','format','reason','outcome') else int(value)
    return row

def instruction(arch, pc, thumb=None):
    maximum = (1 << (32 if arch in WORD32 else 64))-1
    alignment = 1 if arch in ('i386','x86_64') else 2 if arch in ('arm32','rv32','rv64') else 4
    if arch == 'arm32' and thumb is not None:
        alignment = 2 if thumb else 4
    return 0 < pc <= maximum and pc % alignment == 0

def native_events(span, arch, allow_signal=True):
    """Require one exact terminal per arm and monotonically fresh owner tickets."""
    if arch not in ARCH_TRIPLES:
        raise ValueError('unsupported futex diagnostic architecture')
    maximum=(1 << (32 if arch in WORD32 else 64))-1
    active, waits, origins, events = {}, {}, {}, []
    pending = None
    previous = b''
    for line in span.splitlines():
        if PREFIX not in line:
            if pending is not None and line:
                raise ValueError('futex interrupted retirement lacks immediate signal publication')
            continue
        pattern=next((p for p in PATTERNS if p.fullmatch(line)),None)
        if pattern is None:
            raise ValueError('malformed native futex diagnostic')
        row=parse(pattern,line); owner=(row['pid'],row['tid'])
        if (not all(0 < value <= 0xffffffff for value in owner) or
                not 0 < row['wait'] <= 0xffffffffffffffff or not 0 < row['origin'] <= 0xffffffffffffffff):
            raise ValueError('invalid native futex identity or generation')
        if pending is not None and pattern is not SIGNAL:
            raise ValueError('futex interrupted retirement lacks signal publication')
        if pattern is ARM:
            wide=arch not in WORD32 or row['syscall'] in (422,4422)
            if (owner in active or row['wait']<=waits.get(owner,0) or row['origin']<=origins.get(owner,0) or
                    row['syscall'] not in NUMBERS[arch] or not instruction(arch,row['pc']) or
                    not 0 < row['address'] <= maximum-3 or row['address']%4 or row['operation'] not in (0,128) or
                    not 0 <= row['expected'] <= 0xffffffff or not 0 <= row['timeout'] <= maximum or
                    (row['timeout'] and row['timeout'] > maximum-(15 if wide else 7)) or
                    not 0 <= row['deadline'] <= 0xffffffffffffffff or bool(row['deadline']) != bool(row['timeout']) or
                    row['format'] != ('time64' if wide else 'time32')):
                raise ValueError('invalid or stale native futex arm')
            active[owner]=row; waits[owner]=row['wait'];origins[owner]=row['origin']
        elif pattern is RETIRE:
            arm=active.get(owner)
            if arm is None or any(row[k]!=arm[k] for k in ('wait','origin')):
                raise ValueError('futex retirement lost exact live owner/wait/origin')
            if (row['reason']=='ready' and row['result']!=0 or
                    row['reason']=='timeout' and (row['result']!=-110 or not arm['timeout']) or
                    row['reason']=='interrupted' and row['result'] not in (-4,0) or
                    row['reason']=='cancelled' and row['result']!=-4):
                raise ValueError('futex retirement reason/result disagree')
            row['arm']=arm
            del active[owner]
            if row['reason']=='interrupted':pending=row
        else:
            if not allow_signal or pending is None or previous!=pending['line']:
                raise ValueError('unexpected native futex signal publication')
            arm=pending['arm'];widths=(2,) if arch in ('x86_64','i386') else (2,4) if arch=='arm32' else (4,)
            if (any(row[k]!=pending[k] for k in ('pid','tid','wait','origin','live')) or
                    any(row[k]!=arm[k] for k in ('syscall','address','operation','expected','timeout','deadline')) or
                    row['signal']!=(16 if arch.startswith('mips') else 10) or not instruction(arch,row['pc']) or
                    pending['result']!=(-4 if row['outcome']=='eintr' else 0) or
                    (row['outcome']=='restart' and (arm['timeout'] or arm['pc']-row['pc'] not in widths)) or
                    (row['outcome']=='eintr' and row['pc']!=arm['pc'])):
                raise ValueError('futex signal changed retired original request or result')
            row['arm']=arm;row['terminal']=pending;pending=None
        if row['live']!=len(active):
            raise ValueError('futex live count differs from exact publication/retirement ledger')
        events.append(row);previous=line
    if active or pending is not None:
        raise ValueError('live futex wait or incomplete signal at command boundary')
    return events

def final_snapshots(span):
    """Children and shell may publish; each frame/entry pair must be fresh."""
    prefixes=(b'OK_NATIVE_FRAMES ',b'OK_ENTRY_STACKS ')
    rows=[line for line in span.splitlines() if any(p in line for p in prefixes)]
    if not rows or len(rows)%2:
        raise ValueError('missing paired final command resource snapshot')
    for index,line in enumerate(rows):
        if not line.startswith(prefixes[index%2]) or line in rows[:index]:
            raise ValueError('duplicate or reordered final command resource snapshot')
        if index>=2:
            previous=int(re.search(rb' releases=([0-9]+)',rows[index-2])[1])
            current=int(re.search(rb' releases=([0-9]+)',line)[1])
            if current<=previous:
                raise ValueError('stale final command resource snapshot')
