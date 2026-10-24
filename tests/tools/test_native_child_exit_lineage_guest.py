"""Hosted synthetic lineage journals and adversarial kernel joins, never execution."""
from pathlib import Path
import copy
import re
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import native_child_exit_lineage_guest as g
from signal_wait_guest_protocol import TIMED


def wire(arch,pid,status):
    big=arch in ('mips','mips64','ppc');wide=arch in ('x86_64','aarch64','rv64','loongarch64','mips64')
    words=[18,1,0] if arch.startswith('mips') else [17,0,1]
    if wide:words+=[0]
    words += [pid,1000,status]
    return (b''.join(n.to_bytes(4,'big' if big else 'little') for n in words)+bytes(128))[:128]


def fixture(arch='x86_64'):
    lines=[];exits=[];signals=[];polls=[];chld=18 if arch.startswith('mips') else 17
    base=0x10000000 if arch in ('aarch64','arm32') else 0x40000000
    def kernel(prefix,fields,target,metadata):
        line=(prefix+' '+' '.join(f'{k}={v}' for k,v in fields.items())).encode()
        row=dict(fields,**metadata,line=line,position=len(lines));lines.append(line);target.append(row)
    for case in range(7):
        pid=100+case*10;child=pid+(2 if case<2 else 1);peer=pid+(1 if case<2 else 2);seq=0;completed=False
        lines += [f'CHILD_LINEAGE_BEGIN arch={arch} case={case} parent=5'.encode(),
                  f'CHILD_LINEAGE_CASE arch={arch} case={case} pid={pid} uid=1000'.encode()]
        def completion(subject=True):
            nonlocal completed
            if subject:completed=True
            notify=int(subject and case not in (0,6));status=17 if case in (2,3,4) else 37
            fields=dict(child=child if subject else pid,parent=pid if subject else 5,
                        parent_tid=(peer if case==0 else pid) if subject else 5,parent_epoch=case+2 if subject else 1,
                        uid=1000,code=1,status=status if subject else 0,wait_code=2 if subject and case==4 else 1,
                        wait_status=(15 if case==4 else 23 if case in (2,3) else 37) if subject else 0,
                        published=1,notify=notify,queued=notify,coalesced=0,autoreap=0)
            kernel('OK_NATIVE_CHILD_EXIT',fields,exits,dict(tag='OK_NATIVE_CHILD_EXIT'))
        def window(poll=False):
            if poll:
                kernel('OK_NATIVE_POLL_ARM',dict(pid=pid,tid=pid,wait=9,pc=base+1024,syscall=g.PPOLL[arch][0],
                       kind='poll',count=1,deadline=1000000000,live=1),polls,dict(tag='OK_NATIVE_POLL_ARM'))
                completion()
                kernel('OK_NATIVE_POLL_RETIRE',dict(pid=pid,tid=pid,wait=9,reason='ready',result=1,live=0),polls,dict(tag='OK_NATIVE_POLL_RETIRE'))
            else:
                bit=1<<(chld-1);arm=dict(pid=pid,tid=pid,epoch=1,wait=9,kind='timed',syscall=TIMED[arch],
                        pc=base+1024,set=base+2048,info=base+3072,timeout=base+4096,sigsetsize=16 if arch.startswith('mips') else 8,
                        wanted0=bit,wanted1=0,original0=bit,original1=0,deadline=1000000000,active0=0,active1=0,live=1)
                kernel('OK_NATIVE_SIGNAL_WAIT_ARM',arm,signals,dict(event='ARM'))
                completion()
                end=dict(pid=pid,tid=pid,epoch=1,wait=9,kind='timed',outcome='received',signal=chld,code=1,
                         sender_pid=child,sender_uid=1000,info=base+3072,result=chld,published=1,staged=0,consumed=1,
                         live=0,deadline=1000000000,now=500000000)
                kernel('OK_NATIVE_SIGNAL_WAIT_COMPLETE',end,signals,dict(event='COMPLETE'))
        def event(op,a,b,c):
            nonlocal seq
            if op=='WAIT' and not completed:completion()
            lines.append(f'CHILD_LINEAGE_EVENT arch={arch} case={case} seq={seq} op={op} a={a} b={b} c={c}'.encode());seq+=1
            if op=='WAIT_BEGIN':window()
            if op=='POLL_BEGIN':window(True)
        def info(status,via='wait'):
            nonlocal seq
            if not completed:completion()
            lines.append(f'CHILD_LINEAGE_INFO arch={arch} case={case} seq={seq} via={via} signal={chld} code=1 child={child} uid=1000 status={status} bytes=128 hex={wire(arch,child,status).hex()}'.encode());seq+=1
        event('CONFIG',0,1,0)
        if case<2:
            event('THREAD',peer,0,1);event('SPAWN',child,peer,37)
            if case==1:event('CREATOR_EXIT',peer,11,0)
            event('RELEASE',child,0,0)
            if case==1:info(37)
            event('WAIT',child,9472,1);event('PENDING',0,1,0);event('ABSENT',11,1,0)
            if case==0:event('THREAD_RETIRED',peer,0,0)
        elif case<5:
            event('SPAWN',child,pid,0);event('GROUP',child,child,peer);event('LEADER_EXIT',child,17,0)
            event('LIVE',child,0,0);event('RELEASE',child,peer,case-2);info(17)
            event('WAIT',child,15 if case==4 else 5888,1);event('PENDING',0,1,0);event('ABSENT',11,1,0)
        else:
            event('SPAWN',child,pid,37);event('THREAD',peer,1,1)
            if case==5:
                event('WAIT_BEGIN',pid,1,1);event('WAIT_RETURN',chld,0,1);info(37,'active-wait')
                event('THREAD_RETIRED',peer,0,0);event('WAIT',child,9472,1)
            else:
                event('POLL_BEGIN',pid,1,0);event('POLL_RETURN',1,1,1);event('READ_REAP',child,9472,peer)
                event('ECHILD',child,10,0);event('THREAD_RETIRED',peer,0,0)
            event('PENDING',0,1,0);event('ABSENT',11,1,0)
        lines.append(f'CHILD_LINEAGE_DONE arch={arch} case={case} pid={pid} events={seq}'.encode());completion(False)
        lines.append(f'CHILD_LINEAGE_REAP arch={arch} case={case} parent=5 child={pid} status=0'.encode())
    lines.append(f'CHILD_LINEAGE_PASS {arch} cases=7 creator=1 replacement=1 leader_causes=3 real_blocked=1 ppoll_mask=1 bytes=128'.encode())
    return b'\n'.join(lines)+b'\n',exits,signals,polls


def validate(data,arch='x86_64'):
    span,exits,signals,polls=data
    return g.validate_joins(span,g.guest_events(span,arch),exits,signals,polls)


def change_field(data,which,index,key,value):
    span,exits,signals,polls=copy.deepcopy(data);rows=(exits,signals,polls)[which];row=rows[index]
    original=row['line'];row[key]=value
    replacement=re.sub(rb'\b'+key.encode()+rb'=[^ ]+',key.encode()+b'='+str(value).encode(),original)
    assert replacement!=original;row['line']=replacement
    return span.replace(original,replacement,1),exits,signals,polls


class ChildLineageJournal(unittest.TestCase):
    def test_all_profiles_actual_window_models(self):
        for arch in g.ARCHES:
            data=fixture(arch)
            with self.subTest(arch=arch):
                result=validate(data,arch);self.assertEqual(result['subject_completions'],7)
                self.assertEqual(len(result['wait_windows']),2);self.assertFalse(result['native_execution'])
                self.assertEqual(g.probe_spec(arch)[3],22)
                crlf=(data[0].replace(b'\n',b'\r\n'),*data[1:]);self.assertEqual(validate(crlf,arch),result)

    def test_every_guest_marker_required_once_and_owned(self):
        raw=fixture()[0].splitlines(keepends=True)
        for index,line in enumerate(raw):
            if not line.startswith(g.PREFIX):continue
            for new in (b'',line*2,b'bad '+line):
                with self.subTest(index=index),self.assertRaises(ValueError):
                    g.guest_events(b''.join(raw[:index])+new+b''.join(raw[index+1:]),'x86_64')
            for key in (b'case',b'pid',b'parent',b'child',b'seq',b'a',b'b',b'c',b'events',b'status',b'uid'):
                match=re.search(rb'\b'+key+rb'=([0-9]+)',line)
                if not match:continue
                new=re.sub(rb'\b'+key+rb'=[0-9]+',key+b'='+str(int(match[1])+1).encode(),line)
                with self.subTest(index=index,key=key),self.assertRaises(ValueError):
                    g.guest_events(b''.join(raw[:index])+new+b''.join(raw[index+1:]),'x86_64')

    def test_full_info_layout_all_profiles(self):
        for arch in g.ARCHES:
            raw=fixture(arch)[0]
            for line in raw.splitlines(keepends=True):
                if not line.startswith(b'CHILD_LINEAGE_INFO '):continue
                old=re.search(rb'hex=([0-9a-f]+)',line)[1]
                for offset in (0,4,8,12,16,20,24,28,32,48,64,127):
                    value=bytearray.fromhex(old.decode());value[offset]^=1
                    with self.subTest(arch=arch,offset=offset),self.assertRaises(ValueError):
                        g.guest_events(raw.replace(line,line.replace(old,value.hex().encode()),1),arch)

    def test_exact_creator_replacement_and_distinct_exit_causes(self):
        for arch in g.ARCHES:
            data=fixture(arch)
            for index,row in enumerate(data[1]):
                for key in ('parent','parent_tid','uid','code','status','wait_code','wait_status','published','notify','queued','coalesced','autoreap'):
                    with self.subTest(arch=arch,index=index,key=key),self.assertRaises(ValueError):
                        validate(change_field(data,0,index,key,row[key]+1),arch)
                with self.subTest(arch=arch,index=index,key='epoch-zero'),self.assertRaises(ValueError):
                    validate(change_field(data,0,index,'parent_epoch',0),arch)
            for index in range(14):
                changed=copy.deepcopy(data);del changed[1][index]
                with self.subTest(arch=arch,index=index,missing=True),self.assertRaises(ValueError):validate(changed,arch)
                changed=copy.deepcopy(data);changed[1].append(changed[1][index])
                with self.subTest(arch=arch,index=index,duplicate=True),self.assertRaises(ValueError):validate(changed,arch)

    def test_wait_masks_and_owned_completions(self):
        for arch in g.ARCHES:
            data=fixture(arch)
            for which,index,keys in (
                (1,0,('pid','tid','wanted0','wanted1','original0','original1','active0','active1','live')),
                (1,1,('pid','tid','signal','code','sender_pid','sender_uid','result','published','staged','consumed','live','epoch','wait','info','deadline')),
                (2,0,('pid','tid','count','live')),
                (2,1,('pid','tid','wait','result','live'))):
                for key in keys:
                    value=data[which+1][index][key]
                    with self.subTest(arch=arch,which=which,index=index,key=key),self.assertRaises(ValueError):
                        validate(change_field(data,which,index,key,value+1),arch)
            for which in (2,3):
                changed=list(copy.deepcopy(data));changed[which]=[]
                with self.subTest(arch=arch,missing=which),self.assertRaises(ValueError):validate(changed,arch)

    def test_delay_or_entered_marker_cannot_substitute_for_arm_order(self):
        original=fixture()
        for which in (2,3):
            for move in ('arm-after-exit','terminal-before-exit'):
                span,exits,signals,polls=copy.deepcopy(original);rows=signals if which==2 else polls
                child=151 if which==2 else 161
                complete=next(r for r in exits if r['child']==child);lines=span.splitlines()
                target=rows[0] if move=='arm-after-exit' else rows[1]
                at,other=target['position'],complete['position'];lines[at],lines[other]=lines[other],lines[at]
                for row in exits+signals+polls:row['position']=lines.index(row['line'])
                changed=(b'\n'.join(lines)+b'\n',exits,signals,polls)
                with self.subTest(which=which,move=move),self.assertRaises(ValueError):validate(changed)

    def test_foreign_extra_children_and_source_positions(self):
        data=fixture();changed=copy.deepcopy(data);rogue=dict(changed[1][0]);rogue['child']=9999;changed[1].append(rogue)
        with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(data);changed[1][0]['position']+=1
        with self.assertRaises(ValueError):validate(changed)
        with self.assertRaises(ValueError):g.guest_events(data[0][:-1],'x86_64')
        with self.assertRaises(ValueError):g.guest_events(b'CHILD_LINEAGE_FAIL line=1\n'+data[0],'x86_64')
        with self.assertRaises(ValueError):g.guest_events(data[0]+b'CHILD_LINEAGE_EVENT invalid\n','x86_64')


if __name__=='__main__':unittest.main()
