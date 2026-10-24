"""Replay retained pressure execution and targeted full-collector mutations.

No guest is executed. Source, serial, original receipt and output are explicit.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('--source',type=Path,required=True)
cli.add_argument('--source-inventory',type=Path,required=True)
cli.add_argument('--source-inventory-sha256',required=True)
cli.add_argument('--result',type=Path,required=True)
cli.add_argument('--serial',type=Path,required=True)
cli.add_argument('--output',type=Path,required=True)
a=cli.parse_args()
sys.path.insert(0,str(a.source/'tools'))
from native_child_events import normalize_transcript
from native_child_exit_pressure_evidence import validate_execution
from native_child_exit_pressure_guest import guest_events
from native_child_exit_guest import expected_info,ARCHES
from qualify_native_child_exit_pressure import observe_guest_execution
from signal_wait_guest_protocol import TIMED


def signal_fixture(arch,code,child,uid,signal):
    low=0x10000000 if arch in ('arm32','aarch64') else 0x40000000
    bits=1<<(signal-1);size=16 if arch.startswith('mips') else 8
    identity='pid=123 tid=123 epoch=11 wait=7 kind=timed'
    return (f'OK_NATIVE_SIGNAL_WAIT_ARM {identity} syscall={TIMED[arch]} pc={low+4096} '
            f'set={low+8192} info={low+8448} timeout={low+8704} sigsetsize={size} '
            f'wanted0={bits} wanted1=0 original0={bits} original1=0 deadline=1000 '
            'active0=0 active1=0 live=1\n'
            f'OK_NATIVE_SIGNAL_WAIT_COMPLETE {identity} outcome=received signal={signal} code={code} '
            f'sender_pid={child} sender_uid={uid} info={low+8448} result={signal} '
            'published=1 staged=0 consumed=1 live=0 deadline=1000 now=50\n').encode()


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sys.dont_write_bytecode
inventory=a.source_inventory
assert sha(inventory)==a.source_inventory_sha256
assert {str(p.relative_to(a.source)):sha(p) for p in a.source.rglob('*') if p.is_file()}==json.loads(inventory.read_text())['files']
receipt=json.loads(a.result.read_text());arch=receipt['architecture'];raw=a.serial.read_bytes()
assert sha(a.serial)==receipt['serial_sha256']
keys=('baseline_begin','probe_begin','probe_mid','probe_end','native_begin')
bounds=tuple(receipt['command_boundaries'][k] for k in keys)
normal,b=normalize_transcript(raw,bounds);assert b[3]==b[4]
parts=[normal[:b[0]],normal[b[0]:b[1]],normal[b[1]:b[2]],normal[b[2]:b[3]],normal[b[4]:]]
controls=[]


def replay(chunks):
    ends=[sum(map(len,chunks[:i])) for i in range(1,5)]
    return validate_execution(b''.join(chunks),*ends,ends[-1],arch)


def check(name,call,want='reject',gate=None):
    try:
        result=call();observed='accept';error=None
    except ValueError as exc:
        result=None;observed='reject';error=str(exc)
    passed=observed==want and (gate is None or error and gate in error)
    controls.append(dict(name=name,expected=want,observed=observed,intended_gate=gate,error=error,passed=bool(passed)))
    if not passed:print('UNEXPECTED',controls[-1],flush=True)
    return result


def mutated(name,index,span,want='reject',gate=None):
    chunks=parts.copy();chunks[index]=span
    return check(name,lambda:replay(chunks),want,gate)


def field(line,key,value):
    changed,n=re.subn(rb'(?<![a-z_])'+key.encode()+rb'=[^ \r\n]+',(key+'='+str(value)).encode(),line)
    assert n==1,(key,line)
    return changed


def number(line,key):return int(re.search(rb'(?<![a-z_])'+key.encode()+rb'=([0-9]+)',line)[1])


def live_counts(span):
    """Maintain valid generic pipe accounting while attacking a campaign join."""
    active=set();rows=[]
    for line in span.splitlines(True):
        if line.startswith((b'OK_NATIVE_PIPE_READ_WAIT ',b'OK_NATIVE_PIPE_READ_COMPLETE ')):
            owner=(number(line,'pid'),number(line,'tid'))
            if b'stage=arm ' in line:
                assert owner not in active;active.add(owner)
            elif b'stage=rearm ' in line:assert owner in active
            else:assert owner in active;active.remove(owner)
            line=field(line,'live',len(active))
        rows.append(line)
    assert not active
    return b''.join(rows)


def entry_threshold(chunks,index,reservations):
    """Create structurally valid synthetic snapshots at a selected lease bound.

    This is a model corruption control, not accounting from another execution.
    All capture and following counter deltas remain valid, so only the campaign
    minimum can reject a below-bound trace.
    """
    names=('reservations','releases','activations','syscalls','timers','faults','rejected')
    prior=next(line for line in reversed(chunks[index-1].splitlines(True)) if line.startswith(b'OK_ENTRY_STACKS '))
    oldrows=[line for line in chunks[index].splitlines(True) if line.startswith(b'OK_ENTRY_STACKS ')]
    # Multiple intermediate retirement snapshots impose their own minimum
    # number of releases. Retain the final paired snapshot only to isolate the
    # workload's dynamic lower bound instead of that generic freshness gate.
    last_frame=next(line for line in reversed(chunks[index].splitlines(True)) if line.startswith(b'OK_NATIVE_FRAMES '))
    local=[line for line in chunks[index].splitlines(True)
           if not line.startswith((b'OK_ENTRY_STACKS ',b'OK_NATIVE_FRAMES ')) or line in (last_frame,oldrows[-1])]
    base={key:number(prior,key) for key in names};leased=number(prior,'leased')
    peak=max(number(line,'peak') for line in oldrows)
    changed=[];step=0;final=None
    for line in local:
        if line.startswith(b'OK_ENTRY_STACKS '):
            step+=1
            values=dict(base,reservations=base['reservations']+reservations,
                        releases=base['releases']+reservations,
                        activations=base['activations']+step,syscalls=base['syscalls']+step)
            for key,value in dict(values,leased=leased,peak=peak).items():line=field(line,key,value)
            final=values
        changed.append(line)
    result=chunks.copy();result[index]=b''.join(changed)
    offset={key:final[key]-number(oldrows[-1],key) for key in names}
    for later in range(index+1,len(result)):
        changed=[]
        for line in result[later].splitlines(True):
            if line.startswith(b'OK_ENTRY_STACKS '):
                for key,value in offset.items():line=field(line,key,number(line,key)+value)
            changed.append(line)
        result[later]=b''.join(changed)
    return result


baseline=check('original-raw-v3-replay',lambda:validate_execution(raw,*bounds,arch),'accept')
assert baseline
check('normalized-v3-replay',lambda:replay(parts),'accept')
for index in (2,3):
    span=parts[index];lines=span.splitlines(True);guest=guest_events(span,arch)
    def wire(row):
        return next(line for line in lines if line.rstrip(b'\r\n')==row['line'])
    exits=[line for line in lines if line.startswith(b'OK_NATIVE_CHILD_EXIT ')]
    assert len(exits)==baseline['observations'][index-2]['process_completions']
    by_pid={number(line,'child'):line for line in exits}
    for j,line in enumerate(exits):
        # An ENOMEM can fail before PCB creation; zero rollback records are a
        # valid launch contract. This positive control makes that limit explicit.
        mutated(f'run{index}-exit{j}-missing',index,span.replace(line,b'',1),
                want='accept' if number(line,'published')==0 else 'reject')
        mutated(f'run{index}-exit{j}-duplicate',index,span.replace(line,line+line,1))
    for wave in guest['waves']:
        w=wave['wave'];pid=wave['children'][0];exitline=by_pid[pid];release=wire(wave['release'])
        child_rows=[line for line in lines if line.startswith(b'OK_NATIVE_PIPE_') and number(line,'pid')==pid]
        end=next(line for line in child_rows if line.startswith(b'OK_NATIVE_PIPE_READ_COMPLETE '))
        arm=next(line for line in child_rows if b'stage=arm ' in line)
        rearm=next(line for line in child_rows if b'stage=rearm ' in line)
        for key,value in dict(parent=999999,parent_tid=999999,uid=123456,status=38,wait_status=38).items():
            mutated(f'run{index}-wave{w}-child-{key}',index,span.replace(exitline,field(exitline,key,value),1),gate='child owner, cause or completion policy')
        mutated(f'run{index}-wave{w}-parent-epoch',index,span.replace(exitline,field(exitline,'parent_epoch',number(exitline,'parent_epoch')+1),1),gate='parent owner epoch changed')
        # Drop complete owned lifetime and repair other owners' live counters.
        removed=span
        for row in child_rows:removed=removed.replace(row,b'',1)
        mutated(f'run{index}-wave{w}-missing-owned-gate',index,live_counts(removed),gate='pressure child lacks actual blocked read')
        # Move arm/origin/rearms as a valid lifetime prefix after release.
        moved=span
        prefix=[row for row in child_rows if row!=end]
        for row in prefix:moved=moved.replace(row,b'',1)
        moved=moved.replace(release,release+b''.join(prefix),1)
        mutated(f'run{index}-wave{w}-arm-after-release',index,live_counts(moved),gate='pressure read was not armed before release')
        moved=span.replace(end,b'',1).replace(exitline,exitline+end,1)
        mutated(f'run{index}-wave{w}-read-completion-after-exit',index,live_counts(moved),gate='gate lifetime ordering')
        # Complete with a generically valid EOF, but never deliver the gate byte.
        eof=field(field(end,'outcome','eof'),'result',0)
        mutated(f'run{index}-wave{w}-valid-eof-not-gate-byte',index,span.replace(end,eof,1),gate='gate did not complete exactly one byte')
        for key,value,gate in [('wait',number(rearm,'wait')-1,'stale pipe wait ticket'),
                             ('request',99999,'invalid pipe request identity/range'),
                             ('output',number(rearm,'output')+1,'pipe rearm changed copied vectors or retained description'),
                             ('description',number(rearm,'description')+1,'pipe rearm changed copied vectors or retained description'),
                             ('tid',999999,'pipe rearm changed copied vectors or retained description')]:
            mutated(f'run{index}-wave{w}-rearm-{key}',index,span.replace(rearm,field(rearm,key,value),1),gate=gate)
        # Matching published fields remain valid, while the actual queued sender differs.
        if w!=1:
            info=wave['notification'];other=wave['children'][1];line=wire(info)
            new=field(line,'child',other)
            new=field(new,'hex',expected_info(arch,1,other,guest['uid'],37).hex())
            mutated(f'run{index}-wave{w}-wrong-valid-member-siginfo',index,span.replace(line,new,1),gate='coalesced payload differs from the actual queued child')
            second=by_pid[other]
            new_first=field(field(exitline,'queued',0),'coalesced',1)
            new_second=field(field(second,'queued',1),'coalesced',0)
            changed=span.replace(exitline,new_first,1).replace(second,new_second,1)
            mutated(f'run{index}-wave{w}-queued-not-first-completion',index,changed,gate='notification did not retain the first completion')
        for j,failed in enumerate(wave['failures']):
            inner=[line for line in exits if failed['begin']['position']<lines.index(line)<failed['end']['position']]
            assert len(inner)==1
            rollback=inner[0]
            for key,value in dict(parent=999999,parent_tid=guest['pid'],status=126,wait_status=126,published=1).items():
                # parent_tid also needs nonzero epoch to remain structurally valid.
                new=field(rollback,key,value)
                if key=='parent_tid':new=field(new,'parent_epoch',1)
                gate='child policy escaped its qualified parent boundary' if key=='parent_tid' else 'failed fork contains an unqualified rollback completion'
                mutated(f'run{index}-wave{w}-rollback{j}-{key}',index,span.replace(rollback,new,1),gate=gate)
            close=wire(failed['end'])
            moved=span.replace(rollback,b'',1).replace(close,close+rollback,1)
            mutated(f'run{index}-wave{w}-rollback{j}-outside-window',index,moved,gate='unobserved or unassigned process completion')
            mutated(f'run{index}-wave{w}-rollback{j}-eagain',index,span.replace(close,field(close,'b',11),1),gate='failed fork contains an unqualified rollback completion')
        if w!=0:
            reap=next(line for line in lines[wave['release']['position']:wave['done']['position']] if line.startswith(b'OK_NATIVE_CHILD_REAP '))
            mutated(f'run{index}-wave{w}-reap-count',index,span.replace(reap,field(reap,'count',number(reap,'count')+1),1),gate='checked child reap differs from explicit completions')
            mutated(f'run{index}-wave{w}-reap-missing',index,span.replace(reap,b'',1))
        recovery=by_pid[wave['recovery']['pid']]
        mutated(f'run{index}-wave{w}-recovery-cause',index,span.replace(recovery,field(recovery,'wait_status',37),1),gate='child owner, cause or completion policy')
    # Extra balanced owners are valid generic ledgers, but not this workload.
    exemplar=guest['waves'][0]['children'][0]
    owned=[line for line in lines if line.startswith(b'OK_NATIVE_PIPE_') and number(line,'pid')==exemplar]
    first=next(line for line in owned if b'stage=arm ' in line)
    origin=next(line for line in owned if line.startswith(b'OK_NATIVE_PIPE_ORIGIN '))
    end=next(line for line in owned if line.startswith(b'OK_NATIVE_PIPE_READ_COMPLETE '))
    extra=b''.join(field(field(field(line,'pid',999999),'tid',999999),'wait',1) for line in (first,origin,end))
    marker=wire(guest['success'])
    mutated(f'run{index}-extra-balanced-pipe-owner',index,live_counts(span.replace(marker,extra+marker,1)),gate='unassigned pipe activity')
    extra=signal_fixture(arch,code=0,child=123,uid=0,signal=10)
    mutated(f'run{index}-extra-balanced-signal-wait',index,span.replace(marker,extra+marker,1),gate='pressure guest unexpectedly entered signal/poll/futex wait')
    waits=[line for line in lines if line.startswith(b'OK_NATIVE_CHILD_WAIT ')]
    assert len(waits)==2
    for j,line in enumerate(waits):
        for key,value in dict(tid=999999,selector=999999,output=0,result=0).items():
            mutated(f'run{index}-shell-wait{j}-{key}',index,span.replace(line,field(line,key,value),1))
    main=by_pid[guest['pid']]
    mutated(f'run{index}-main-owner',index,span.replace(main,field(main,'parent',999999),1),gate='controller lost native shell ownership')
    moved=span.replace(main,b'',1).replace(marker,main+marker,1)
    mutated(f'run{index}-main-before-aggregate',index,moved,gate='controller lost native shell ownership')
    for prefix in (b'OK_ENTRY_STACKS ',b'OK_NATIVE_FRAMES '):
        row=next(line for line in reversed(lines) if line.startswith(prefix))
        mutated(f'run{index}-{prefix.decode().strip()}-duplicate-final',index,span.replace(row,row+row,1))
    stacks=next(line for line in reversed(lines) if line.startswith(b'OK_ENTRY_STACKS '))
    for key in ('faults','rejected','quarantine','leased'):
        mutated(f'run{index}-final-stack-{key}',index,span.replace(stacks,field(stacks,key,number(stacks,key)+1),1))
    minimum=guest['minimum_entry_leases']
    check(f'run{index}-synthetic-entry-minimum',lambda:replay(entry_threshold(parts,index,minimum)),'accept')
    check(f'run{index}-synthetic-below-entry-minimum',lambda:replay(entry_threshold(parts,index,minimum-1)),
          gate='pressure command lacks fresh owned entries')

# Observation helpers are metadata and must never claim acceptance.
for target in ARCHES:
    begin=f'CHILD_PRESSURE_BEGIN arch={target} pid=100 uid=0 cap=128 waves=3 failures=3\n'.encode()
    failed=b'CHILD_PRESSURE_FAIL line=0123 wave=2\n'
    for label,data,executed in [('none',b'',False),('begin',begin,True),('failure',failed,True),
                               ('begin-failure',begin+failed,True),('partial',begin[:-1],False),
                               ('invalid-failure',b'CHILD_PRESSURE_FAIL line=0123 wave=8\n',False)]:
        def observed(data=data,target=target,executed=executed):
            got=observe_guest_execution(data,target)
            if got['executed']!=executed or 'native_execution_accepted' in got:raise ValueError('wrong observation classification')
            return got
        check(f'{target}-observation-{label}',observed,'accept')

summary=dict(status='passed' if all(r['passed'] for r in controls) else 'failed',
             source=str(a.source.resolve()),source_inventory_sha256=sha(inventory),
             original_result_sha256=sha(a.result),original_serial_sha256=sha(a.serial),
             original_native_status=receipt['status'],original_native_accepted=receipt['native_execution_accepted'],
             original_native_executed=receipt['executed'],new_guest_execution=False,
             replay=baseline,positive_controls=sum(r['expected']=='accept' for r in controls),
             negative_controls=sum(r['expected']=='reject' for r in controls),
             targeted_gate_controls=sum(r['intended_gate'] is not None for r in controls),
             unexpected=[r for r in controls if not r['passed']],controls=controls)
a.output.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('replay','controls')},indent=2,sort_keys=True))
sys.exit(summary['status']!='passed')
