"""Exact native copied poll/select wait ledger. Diagnostics alone are not execution."""
import re
from native_futex_events import instruction
NUMBERS={
    'x86_64':((7,271),(23,270)), 'i386':((168,309,414),(82,142,308,413)),
    'aarch64':((73,),(72,)), 'arm32':((168,336,414),(142,335,413)),
    'rv32':((414,),(413,)), 'rv64':((73,),(72,)), 'loongarch64':((73,),(72,)),
    'mips':((4188,4302,4414),(4142,4301,4413)), 'mips64':((5007,5261),(5022,5260)),
    'ppc':((167,281,414),(82,142,280,413))}
PREFIX=b'OK_NATIVE_POLL_'
OWNER=rb'pid=([0-9]+) tid=([0-9]+) wait=([0-9]+)'
ARM=re.compile(PREFIX+rb'ARM '+OWNER+rb' pc=([0-9]+) syscall=([0-9]+) kind=(poll|select) count=([0-9]+) deadline=([0-9]+) live=([0-9]+)')
RETIRE=re.compile(PREFIX+rb'RETIRE '+OWNER+rb' reason=(ready|timeout|interrupted|cancelled) result=(-?[0-9]+) live=([0-9]+)')
SIGNAL=re.compile(PREFIX+rb'SIGNAL '+OWNER+rb' signal=([0-9]+) kind=(poll|select) result=(eintr|efault) deadline=([0-9]+) now=([0-9]+) live=([0-9]+)')
PATTERNS=(ARM,RETIRE,SIGNAL)
def parse(pattern,line):
    if not pattern.fullmatch(line):raise ValueError('malformed poll evidence event: '+line[:160].decode(errors='replace'))
    row={'tag':line.split()[0].decode(),'line':line}
    for field in line.split()[1:]:
        name,value=field.decode().split('=',1)
        row[name]=value if name in ('arch','kind','reason','source','target') or value in ('eintr','efault') else int(value)
    return row
def native_events(span,arch,allow_signal=True,signal_numbers=None):
    if arch not in NUMBERS:raise ValueError('unsupported poll event architecture')
    active={};generations={};events=[];pending=None
    for line in span.splitlines():
        if PREFIX not in line:
            if line and pending is not None:raise ValueError('poll retirement lacks immediate signal publication')
            continue
        pattern=next((p for p in PATTERNS if p.fullmatch(line)),None)
        if pattern is None:raise ValueError('malformed native poll diagnostic')
        row=parse(pattern,line);owner=(row['pid'],row['tid'])
        if not all(0<v<=0xffffffff for v in owner) or not 0<row['wait']<=0xffffffffffffffff:
            raise ValueError('invalid native poll identity')
        if pending is not None and pattern is not SIGNAL:raise ValueError('missing native poll signal publication')
        if pattern is ARM:
            if (owner in active or row['wait']<=generations.get(owner,0) or not instruction(arch,row['pc']) or
                    row['syscall'] not in NUMBERS[arch][row['kind']=='select'] or not 0<=row['count']<=32 or
                    not 0<=row['deadline']<=0xffffffffffffffff):raise ValueError('invalid or stale copied poll arm')
            active[owner]=row;generations[owner]=row['wait']
        elif pattern is RETIRE:
            arm=active.get(owner)
            if arm is None or row['wait']!=arm['wait']:raise ValueError('poll retirement lost owned generation')
            reason,result=row['reason'],row['result']
            if (reason=='interrupted' and result not in (-4,-14) or reason=='cancelled' and result!=-4 or
                    reason=='timeout' and (not arm['deadline'] or result not in (0,-14)) or
                    reason=='ready' and not (result in (-9,-14) or 0<result<=arm['count']*3)):
                raise ValueError('poll retirement result differs from exact completion cause')
            row['arm']=arm;del active[owner]
            if reason=='interrupted':pending=row
        else:
            if not allow_signal or pending is None:raise ValueError('unowned poll signal publication')
            arm=pending['arm']
            if (any(row[k]!=pending[k] for k in ('pid','tid','wait','live')) or
                    any(row[k]!=arm[k] for k in ('kind','deadline')) or row['signal'] not in (signal_numbers if signal_numbers is not None else (16 if arch.startswith('mips') else 10,)) or
                    pending['result']!=(-14 if row['result']=='efault' else -4) or
                    row['result']=='efault' and row['kind']!='poll' or
                    not 0<row['now']<=0xffffffffffffffff or row['deadline'] and row['now']>=row['deadline']):
                raise ValueError('poll signal disagrees with claimed completion or copied deadline')
            row['arm']=arm;row['terminal']=pending;pending=None
        if row['live']!=len(active):raise ValueError('poll live count differs from exact object ledger')
        events.append(row)
    if active or pending is not None:raise ValueError('live poll object at command boundary')
    return events
