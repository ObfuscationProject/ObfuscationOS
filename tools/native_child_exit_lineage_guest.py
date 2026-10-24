"""Owned lineage guest journals and joins to separately validated kernel ledgers."""
import re
from native_child_exit_guest import ARCHES, expected_info

PREFIX=b'CHILD_LINEAGE_'
MARKER=b'CHILD_LINEAGE_PASS {arch} cases=7 creator=1 replacement=1 leader_causes=3 real_blocked=1 ppoll_mask=1 bytes=128'
KEY=rb' arch=([a-z0-9_]+) case=([0-9]+)'
BEGIN=re.compile(rb'CHILD_LINEAGE_BEGIN'+KEY+rb' parent=([0-9]+)')
CASE=re.compile(rb'CHILD_LINEAGE_CASE'+KEY+rb' pid=([0-9]+) uid=([0-9]+)')
EVENT=re.compile(rb'CHILD_LINEAGE_EVENT'+KEY+rb' seq=([0-9]+) op=([A-Z_]+) a=(-?[0-9]+) b=(-?[0-9]+) c=(-?[0-9]+)')
INFO=re.compile(rb'CHILD_LINEAGE_INFO'+KEY+rb' seq=([0-9]+) via=(wait|active-wait) signal=([0-9]+) code=1 child=([0-9]+) uid=([0-9]+) status=([0-9]+) bytes=128 hex=([0-9a-f]{256})')
DONE=re.compile(rb'CHILD_LINEAGE_DONE'+KEY+rb' pid=([0-9]+) events=([0-9]+)')
REAP=re.compile(rb'CHILD_LINEAGE_REAP'+KEY+rb' parent=([0-9]+) child=([0-9]+) status=0')
PATTERNS=(BEGIN,CASE,EVENT,INFO,DONE,REAP)
PPOLL={'x86_64':(271,),'i386':(309,414),'aarch64':(73,),'arm32':(336,414),
       'rv32':(414,),'rv64':(73,),'loongarch64':(73,),'mips':(4302,4414),
       'mips64':(5261,),'ppc':(281,414)}


def require(value,message):
    if not value:raise ValueError('child lineage '+message)


def probe_spec(arch,kind='child-exit-lineage'):
    require(arch in ARCHES and kind=='child-exit-lineage','unsupported profile')
    suffix='la64' if arch=='loongarch64' else arch.replace('_','-')
    # Main + seven scenario processes + seven subjects + seven pthreads; no exec.
    return MARKER.replace(b'{arch}',arch.encode()),b'CHILD_LINEAGE_PASS',('/bin/native-child-lineage-'+suffix).encode(),22


def failure_line(serial):
    if b'CHILD_LINEAGE_FAIL' in serial:
        return 'child-lineage guest assertion failed: '+serial[serial.index(b'CHILD_LINEAGE_FAIL'):].split(b'\n',1)[0].decode(errors='replace')
    return None


def incomplete_failure_line(serial):
    return b'CHILD_LINEAGE_FAIL' in serial and b'\n' not in serial[serial.index(b'CHILD_LINEAGE_FAIL'):]


def scenario(case):
    rows=[('CONFIG',0,1,0)]
    if case in (0,1):
        rows += [('THREAD','$peer',0,1),('SPAWN','$child','$peer',37)]
        if case==1:rows += [('CREATOR_EXIT','$peer',11,0)]
        rows += [('RELEASE','$child',0,0)]
        if case==1:rows += [('INFO','wait',37)]
        rows += [('WAIT','$child',9472,1),('PENDING',0,1,0),('ABSENT',11,1,0)]
        if case==0:rows += [('THREAD_RETIRED','$peer',0,0)]
    elif case in (2,3,4):
        rows += [('SPAWN','$child','$owner',0),('GROUP','$child','$child','$peer'),
                 ('LEADER_EXIT','$child',17,0),('LIVE','$child',0,0),('RELEASE','$child','$peer',case-2),
                 ('INFO','wait',17),('WAIT','$child',15 if case==4 else 5888,1),('PENDING',0,1,0),('ABSENT',11,1,0)]
    elif case==5:
        rows += [('SPAWN','$child','$owner',37),('THREAD','$peer',1,1),('WAIT_BEGIN','$owner',1,1),
                 ('WAIT_RETURN','$chld',0,1),('INFO','active-wait',37),('THREAD_RETIRED','$peer',0,0),
                 ('WAIT','$child',9472,1),('PENDING',0,1,0),('ABSENT',11,1,0)]
    elif case==6:
        rows += [('SPAWN','$child','$owner',37),('THREAD','$peer',1,1),('POLL_BEGIN','$owner',1,0),
                 ('POLL_RETURN',1,1,1),('READ_REAP','$child',9472,'$peer'),('ECHILD','$child',10,0),
                 ('THREAD_RETIRED','$peer',0,0),('PENDING',0,1,0),('ABSENT',11,1,0)]
    else:raise ValueError('invalid lineage scenario')
    return rows


def guest_events(span,arch):
    marker=probe_spec(arch)[0]
    if error:=failure_line(span):raise ValueError(error)
    lines=[]
    for position,raw in enumerate(span.splitlines(keepends=True)):
        if PREFIX not in raw:continue
        require(raw.endswith(b'\n'),'unterminated guest marker');line=raw[:-1].removesuffix(b'\r')
        if line==marker:lines.append(('PASS',dict(line=line,position=position)));continue
        pattern=next((p for p in PATTERNS if p.fullmatch(line)),None)
        require(pattern is not None,'malformed guest marker')
        row=dict(field.decode().split('=',1) for field in line.split()[1:])
        for key in row.keys()-{'arch','op','via','hex'}:row[key]=int(row[key])
        require(row['arch']==arch,'architecture mismatch');row.update(line=line,position=position);lines.append((pattern,row))
    cursor=0
    def take(pattern,case):
        nonlocal cursor
        require(cursor<len(lines) and lines[cursor][0] is pattern,'missing or reordered marker')
        row=lines[cursor][1];cursor+=1;require(row['case']==case,'missing, duplicate or reordered case');return row
    controller=None;controller_uid=None;cases=[];identities=set();exact=[]
    for case in range(7):
        begin=take(BEGIN,case);owner=take(CASE,case)
        require(0<begin['parent']<=0xffffffff and 0<owner['pid']<=0xffffffff and 0<=owner['uid']<=0xffffffff,'process identity domain')
        if controller is None:controller=begin['parent'];controller_uid=owner['uid']
        require(begin['parent']==controller and owner['pid']!=controller and owner['pid'] not in identities,'controller or duplicate scenario identity')
        require(owner['uid']==controller_uid,'scenario changed inherited real UID')
        identities.add(owner['pid']);env={'$owner':owner['pid'],'$chld':18 if arch.startswith('mips') else 17}
        observed=[];script=scenario(case)
        def capture(symbol,value):
            require(0<value<=0xffffffff and value not in (controller,owner['pid']) and value not in identities,'invalid or reused thread/child identity')
            identities.add(value);env[symbol]=value
        for seq,step in enumerate(script):
            row=take(INFO if step[0]=='INFO' else EVENT,case);require(row['seq']==seq,'operation sequence')
            if step[0]=='THREAD':capture('$peer',row['a'])
            if step[0]=='SPAWN':capture('$child',row['a'])
            if step[0]=='GROUP':capture('$peer',row['c'])
            resolve=lambda value:env[value] if isinstance(value,str) and value.startswith('$') else value
            if step[0]=='INFO':
                require((row['via'],row['signal'],row['code'],row['child'],row['uid'],row['status'])==
                        (step[1],env['$chld'],1,env['$child'],owner['uid'],step[2]),'notification identity/cause')
                require(bytes.fromhex(row['hex'])==expected_info(arch,1,env['$child'],owner['uid'],step[2]),'complete target128 payload')
            else:require((row['op'],row['a'],row['b'],row['c'])==tuple(resolve(v) for v in step),'scenario operation/observation')
            observed.append(row)
        done=take(DONE,case);reap=take(REAP,case)
        require((done['pid'],done['events'])==(owner['pid'],len(script)),'completion count/owner')
        require((reap['parent'],reap['child'])==(controller,owner['pid']),'controller reap owner')
        cases.append(dict(case=case,pid=owner['pid'],uid=owner['uid'],parent=controller,child=env['$child'],peer=env['$peer'],
                          begin=begin,owner=owner,events=observed,done=done,reap=reap))
        exact += [begin['line'],owner['line'],*(r['line'] for r in observed),done['line'],reap['line']]
    require(cursor+1==len(lines) and lines[cursor][0]=='PASS','aggregate completion')
    return dict(count=7,architecture=arch,cases=cases,lines=exact+[marker],native_execution=False,
                required_native_wait_windows=2)


def validate_joins(span,guest,exits,signal_waits=(),poll_waits=()):
    """Require lineage and actual wait windows, using root-validated typed rows.

    The root must run its complete lifetime parsers before this join. This helper
    does not admit raw EXIT, signal-wait or poll lines and never drops unknown
    diagnostics. Positions always refer to the same original span as guest.
    """
    raw=span.splitlines();arch=guest['architecture'];chld=18 if arch.startswith('mips') else 17
    def position(row):
        if 'position' in row:
            p=row['position'];require(type(p) is int and 0<=p<len(raw) and raw[p]==row['line'],'typed row position/bytes');return p
        matches=[i for i,line in enumerate(raw) if line==row['line']]
        require(len(matches)==1,'typed row needs unique original position');return matches[0]
    def only(rows,what):
        require(len(rows)==1,'missing or duplicate '+what);return rows[0]
    def op(case,name):return only([r for r in case['events'] if r.get('op')==name],name)
    def compare(row,wanted,what):require(all(row.get(k)==v for k,v in wanted.items()),what)
    for rows in (exits,signal_waits,poll_waits):
        for row in rows:position(row)
    assigned=[];wait_windows=[];controller_epoch=None
    for case in guest['cases']:
        number=case['case'];pid=case['pid'];child=case['child']
        native=only([r for r in exits if r.get('tag')=='OK_NATIVE_CHILD_EXIT' and r['child']==child],'subject completion')
        final=15 if number==4 else 23 if number in (2,3) else 37
        notify=int(number not in (0,6));notification=17 if number in (2,3,4) else 37
        compare(native,dict(parent=pid,parent_tid=case['peer'] if number==0 else pid,uid=case['uid'],
                code=1,status=notification,wait_code=2 if number==4 else 1,wait_status=final,
                published=1,notify=notify,queued=notify,coalesced=0,autoreap=0),'subject lineage/notification/wait policy')
        require(native.get('parent_epoch',0)>0,'missing subject parent epoch')
        at=position(native);require(case['owner']['position']<at<case['done']['position'],'subject completion case boundary')
        own=[r for r in exits if r.get('tag')=='OK_NATIVE_CHILD_EXIT' and r.get('parent')==pid]
        require(len(own)==1 and own[0] is native,'unobserved child completion in scenario')
        if number<5:require(op(case,'RELEASE')['position']<at,'subject completed before final release')
        if number==0:require(at<op(case,'THREAD_RETIRED')['position'],'creator was not retained through child completion')
        if number==1:require(op(case,'CREATOR_EXIT')['position']<op(case,'RELEASE')['position'],'replacement before child release')
        if number in (2,3,4):require(op(case,'LEADER_EXIT')['position']<op(case,'LIVE')['position']<op(case,'RELEASE')['position'],'leader-first live-group observation')
        infos=[r for r in case['events'] if 'hex' in r]
        for row in infos:require(at<row['position'],'user notification preceded kernel completion')
        terminal=op(case,'READ_REAP' if number==6 else 'WAIT')
        require(at<terminal['position'],'user wait preceded group completion')
        parent=only([r for r in exits if r.get('tag')=='OK_NATIVE_CHILD_EXIT' and r['child']==pid],'scenario completion')
        compare(parent,dict(parent=case['parent'],parent_tid=case['parent'],uid=case['uid'],code=1,status=0,
                wait_code=1,wait_status=0,published=1,notify=0,queued=0,coalesced=0,autoreap=0),'scenario completion policy')
        require(parent.get('parent_epoch',0)>0,'missing controller epoch')
        if controller_epoch is None:controller_epoch=parent['parent_epoch']
        require(parent['parent_epoch']==controller_epoch,'controller epoch changed')
        require(case['done']['position']<position(parent)<case['reap']['position'],'scenario physical completion ordering')
        assigned += [native,parent]
        if number==5:
            selected=[r for r in signal_waits if r.get('pid')==pid]
            require(len(selected)==2,'active signal wait needs exactly one arm and completion')
            arm=only([r for r in selected if r.get('event')=='ARM'],'signal-wait arm')
            end=only([r for r in selected if r.get('event')=='COMPLETE'],'signal-wait completion')
            bits=1<<(chld-1)
            compare(arm,dict(pid=pid,tid=pid,kind='timed',wanted0=bits,wanted1=0,original0=bits,original1=0,
                    active0=0,active1=0,live=1),'real_blocked signal wait masks/owner')
            require(arm.get('deadline',0)>0 and arm.get('timeout',0)>0,'bounded active signal wait')
            compare(end,dict(pid=pid,tid=pid,kind='timed',outcome='received',signal=chld,code=1,sender_pid=child,
                    sender_uid=case['uid'],result=chld,published=1,staged=0,consumed=1,live=0,
                    epoch=arm['epoch'],wait=arm['wait'],info=arm['info'],deadline=arm['deadline']),'active wait source/copy completion')
            require(op(case,'WAIT_BEGIN')['position']<position(arm)<at<position(end)<op(case,'WAIT_RETURN')['position'],
                    'active signal wait did not own completion interval')
            wait_windows.append(dict(case=number,arm=position(arm),exit=at,terminal=position(end)))
        if number==6:
            selected=[r for r in poll_waits if r.get('pid')==pid]
            require(len(selected)==2,'temporary poll needs exactly one arm and retirement')
            arm=only([r for r in selected if r.get('tag')=='OK_NATIVE_POLL_ARM'],'poll arm')
            end=only([r for r in selected if r.get('tag')=='OK_NATIVE_POLL_RETIRE'],'poll retirement')
            compare(arm,dict(pid=pid,tid=pid,kind='poll',count=1,live=1),'temporary ppoll owner/count')
            require(arm['syscall'] in PPOLL[arch] and arm['deadline']>0,'bounded actual ppoll syscall')
            compare(end,dict(pid=pid,tid=pid,wait=arm['wait'],reason='ready',result=1,live=0),'ppoll ready retirement')
            require(op(case,'POLL_BEGIN')['position']<position(arm)<at<position(end)<op(case,'POLL_RETURN')['position'],
                    'temporary ppoll did not own completion interval')
            wait_windows.append(dict(case=number,arm=position(arm),exit=at,terminal=position(end)))
    require(len(wait_windows)==2,'both actual native wait windows are required')
    return dict(subject_completions=7,scenario_completions=7,creator_parent_checks=1,replacement_parent_checks=1,
                leader_notification_final_wait_checks=3,wait_windows=wait_windows,
                assigned_exit_positions=[position(r) for r in assigned],native_execution=False)
