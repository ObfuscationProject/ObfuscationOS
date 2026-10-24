"""Strict pressure journal only; native lifetimes and safe reclaim need a collector."""
import re
from native_child_exit_guest import ARCHES, expected_info

PREFIX=b'CHILD_PRESSURE_'
MARKER=b'CHILD_PRESSURE_PASS {arch} waves=3 exhaustion=3 failed_attempts=9 recoveries=3 bytes=128'
BEGIN=re.compile(rb'CHILD_PRESSURE_BEGIN arch=([a-z0-9_]+) pid=([0-9]+) uid=([0-9]+) cap=128 waves=3 failures=3')
KEY=rb' arch=([a-z0-9_]+) wave=([0-9]+) seq=([0-9]+)'
EVENT=re.compile(rb'CHILD_PRESSURE_EVENT'+KEY+rb' op=([A-Z_]+) a=(-?[0-9]+) b=(-?[0-9]+) c=(-?[0-9]+)')
INFO=re.compile(rb'CHILD_PRESSURE_INFO'+KEY+rb' via=(coalesced|recovery) signal=([0-9]+) code=1 child=([0-9]+) uid=([0-9]+) status=([0-9]+) bytes=128 hex=([0-9a-f]{256})')
PATTERNS=(BEGIN,EVENT,INFO)


def require(value,message):
    if not value:raise ValueError('child pressure '+message)


def probe_spec(arch,kind='child-exit-pressure'):
    require(arch in ARCHES and kind=='child-exit-pressure','unsupported profile')
    suffix='la64' if arch=='loongarch64' else arch.replace('_','-')
    # Dynamic successful forks are counted by guest_events; this is only the
    # minimum journal admission bound, never a fixed capacity expectation.
    return MARKER.replace(b'{arch}',arch.encode()),b'CHILD_PRESSURE_PASS',('/bin/native-child-pressure-'+suffix).encode(),10


def failure_line(serial):
    if b'CHILD_PRESSURE_FAIL' in serial:
        return 'child-pressure guest assertion failed: '+serial[serial.index(b'CHILD_PRESSURE_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
    return None


def incomplete_failure_line(serial):
    return b'CHILD_PRESSURE_FAIL' in serial and b'\n' not in serial[serial.index(b'CHILD_PRESSURE_FAIL'):]


def guest_events(span,arch):
    marker=probe_spec(arch)[0]
    if error:=failure_line(span):raise ValueError(error)
    rows=[]
    for position,raw in enumerate(span.splitlines(keepends=True)):
        if PREFIX not in raw:continue
        require(raw.endswith(b'\n'),'unterminated marker');line=raw[:-1].removesuffix(b'\r')
        if line==marker:rows.append(('PASS',dict(position=position,line=line)));continue
        pattern=next((p for p in PATTERNS if p.fullmatch(line)),None)
        require(pattern is not None,'malformed or unknown marker')
        row=dict(word.decode().split('=',1) for word in line.split()[1:])
        for key in row.keys()-{'arch','op','via','hex'}:row[key]=int(row[key])
        require(row['arch']==arch,'architecture mismatch')
        row.update(line=line,position=position);rows.append((pattern,row))
    require(rows and rows[0][0] is BEGIN,'missing begin')
    begin=rows[0][1];pid,uid=begin['pid'],begin['uid']
    require(0<pid<=0x3fffffff and 0<=uid<=0xffffffff,'controller identity domain')
    cursor=1;sequence=0;identities={pid};waves=[]

    def take(pattern,wave):
        nonlocal cursor,sequence
        require(cursor<len(rows) and rows[cursor][0] is pattern,'missing, duplicate or reordered record')
        row=rows[cursor][1];cursor+=1
        require(row['wave']==wave and row['seq']==sequence,'wave or global sequence')
        sequence+=1;return row

    def event(wave,op,a,b,c):
        row=take(EVENT,wave)
        require((row['op'],row['a'],row['b'],row['c'])==(op,a,b,c),'operation observation '+op)
        return row

    def identity(value):
        require(0<value<=0x3fffffff and value not in identities,'invalid or reused successful PID')
        identities.add(value)

    def info(wave,via,pids,status):
        row=take(INFO,wave)
        require(row['via']==via and row['child'] in pids and row['uid']==uid and row['status']==status,
                'notification owner/cause')
        require(row['signal']==(18 if arch.startswith('mips') else 17),'target SIGCHLD')
        require(bytes.fromhex(row['hex'])==expected_info(arch,1,row['child'],uid,status),'complete target128 payload')
        return row

    for wave in range(3):
        config=event(wave,'CONFIG',wave,1,0);initial=event(wave,'INITIAL_ABSENT',11,1,0)
        spawns=[];failures=[];attempts=[];attempt=0;failed=0
        while failed<3:
            require(attempt<128,'safety cap reached without complete failure proof')
            opening=event(wave,'FORK_BEGIN',attempt,len(spawns),failed)
            closing=take(EVENT,wave)
            if closing['op']=='SPAWN':
                require(failed==0 and (closing['b'],closing['c'])==(len(spawns),37),'success after failure or wrong spawn')
                identity(closing['a']);spawns.append(closing)
            else:
                failed+=1
                require(closing['op']=='FORK_FAIL' and closing['a']==attempt and closing['b'] in (11,12) and closing['c']==failed,'fallible fork result')
                failures.append(dict(begin=opening,end=closing,errno=closing['b']))
            attempts.append(dict(begin=opening,end=closing));attempt+=1
        pids=[r['a'] for r in spawns];count=len(pids)
        require(count>=2,'insufficient live children for coalescing')
        exhausted=event(wave,'EXHAUSTED',count,3,128)
        live=[event(wave,'LIVE',child,0,0) for child in pids]
        no_extra=event(wave,'NO_EXTRA',0,0,0);absent=event(wave,'FAILURE_ABSENT',11,1,0)
        release=event(wave,'RELEASE',count,count,37)
        waits=[event(wave,'ECHILD' if wave else 'WAIT',child,10 if wave else 37<<8,0 if wave else 1) for child in pids]
        empty=event(wave,'EMPTY',10,0,0)
        notification=info(wave,'coalesced',pids,37) if wave!=1 else None
        drained=event(wave,'DRAINED',11,1,0)
        recovery_config=event(wave,'RECOVERY_CONFIG',0,1,0)
        recovery_begin=event(wave,'RECOVERY_BEGIN',0,0,39)
        recovery_spawn=take(EVENT,wave)
        require((recovery_spawn['op'],recovery_spawn['b'],recovery_spawn['c'])==('RECOVERY_SPAWN',0,39),'recovery spawn')
        recovery_pid=recovery_spawn['a'];identity(recovery_pid)
        recovery_release=event(wave,'RECOVERY_RELEASE',recovery_pid,1,39)
        recovery_wait=event(wave,'RECOVERY_WAIT',recovery_pid,39<<8,1)
        recovery_info=info(wave,'recovery',[recovery_pid],39)
        recovery_absent=event(wave,'RECOVERY_ABSENT',11,1,0)
        done=event(wave,'WAVE_DONE',count,3,1)
        waves.append(dict(wave=wave,policy=('wait','ignore','nocldwait')[wave],config=config,
            initial=initial,attempts=attempts,spawns=spawns,children=pids,failures=failures,
            exhausted=exhausted,live=live,no_extra=no_extra,failure_absent=absent,release=release,
            waits=waits,empty=empty,notification=notification,drained=drained,
            recovery=dict(pid=recovery_pid,config=recovery_config,begin=recovery_begin,
                          spawn=recovery_spawn,release=recovery_release,wait=recovery_wait,
                          info=recovery_info,absent=recovery_absent),done=done))
    require(cursor+1==len(rows) and rows[cursor][0]=='PASS','missing or duplicate aggregate completion')
    count=sum(len(w['children']) for w in waves)
    return dict(architecture=arch,pid=pid,uid=uid,begin=begin,waves=waves,
                success=rows[cursor][1],lines=[row['line'] for _,row in rows],
                pressure_children=count,recovery_children=3,failed_forks=9,
                expected_published_completions=count+4,minimum_entry_leases=count+4,
                native_execution=False,requires_kernel_lifetime_join=True,
                fixed_capacity_claim=False,global_process_exhaustion_claim=False)
