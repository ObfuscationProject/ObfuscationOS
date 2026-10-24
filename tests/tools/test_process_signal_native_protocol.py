"""Synthetic ownership/causality controls, explicitly separate from execution."""
import copy
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from native_pipe_vector_events import native_events,ARCHES
from native_pipe_signal_evidence import READ
from process_signal_native_protocol import validate_owned_waits


def fixture(arch,case=23,variant=0,form=0,restart=0,fd=3,description=2,pipe_object=1):
    low=0x10000000 if arch in ('arm32','aarch64') else 0x40000000
    width=2 if arch in ('x86_64','i386') or arch=='arm32' and form else 4
    site=low+0x1000;resume=site+width;pid=100;worker=101
    lines=[];guest=[];usr=16 if arch.startswith('mips') else 10
    def g(tag,**fields):
        guest.append(dict(tag=tag,position=len(lines),**fields))
        lines.append(('SYNTHETIC_GUEST '+tag).encode())
    def n(tag,**fields):lines.append((tag+' '+' '.join(f'{k}={v}' for k,v in fields.items())).encode())
    def identity(tid,request,buf,which):
        return dict(pid=pid,tid=tid,wait=request,request=request,output=buf,fd=fd+2*which,description=description+2*which,pipe=pipe_object+which,bytes=1)
    def pub(tid,request,buf,which):
        return dict(pid=pid,tid=tid,request=request,wait=request,origin=request,pc=resume,syscall=READ[arch],fd=fd+2*which,output=buf,bytes=1)
    def arm(tid,request,buf,which,live):
        n('OK_NATIVE_PIPE_READ_WAIT',**identity(tid,request,buf,which),stage='arm',live=live)
        n('OK_NATIVE_PIPE_ORIGIN',**pub(tid,request,buf,which))
    def terminal(tid,request,buf,which,live,result,outcome):
        n('OK_NATIVE_PIPE_READ_COMPLETE',**identity(tid,request,buf,which),result=result,outcome=outcome,pinned=0,live=live)
    buffer=low+0x5000;leader_buffer=low+0x6000
    g('CASE_BEGIN',case=case,pid=pid,variant=variant,form=form,restart=restart,read=READ[arch],usr1=usr,site=site,resume=resume)
    g('THREAD',actor=0,tid=worker);g('THREAD',actor=1,tid=102)
    g('PIPE',role=0,readfd=fd,writefd=fd+1)
    g('READ_BEGIN',actor=0,input=buffer,fd=fd,bytes=1)
    arm(worker,1,buffer,0,1)
    if case==23:
        g('EVENT',tag_value='READ_AWAIT',actor=9,value=0,extra=worker)
        g('KILL_BEGIN',actor=9,target=102,signal=usr)
        terminal(worker,1,buffer,0,0,0 if restart else -4,'interrupted')
        signal=pub(worker,1,buffer,0);signal['pc']=site if restart else resume
        n('OK_NATIVE_PIPE_SIGNAL',**dict(list(signal.items())[:5]),signal=usr,outcome='restart' if restart else 'eintr',**dict(list(signal.items())[5:]),pinned=0,live=0)
        g('HANDLE',pc=site if restart else resume)
        if not restart:
            g('READ_RETURN',value=-1 if variant else -4,ordinal=0)
            g('EVENT',tag_value='READ_RETRY',actor=0,value=fd,extra=1)
        arm(worker,2,buffer,0,1)
        g('EVENT',tag_value='READ_AWAIT',actor=9,value=1,extra=worker)
        g('EVENT',tag_value='READ_RELEASE',actor=9,value=fd+1,extra=81)
        terminal(worker,2,buffer,0,0,1,'ready')
        g('READ_RETURN',value=1,ordinal=0 if restart else 1)
    else:
        if case!=32:g('PIPE',role=1,readfd=fd+2,writefd=fd+3)
        g('LEADER_READ',actor=9,fd=0 if case==32 else fd+2,console=int(case==32),input=leader_buffer,bytes=1)
        if case!=32:arm(pid,1,leader_buffer,1,2)
        g('EVENT',tag_value='GROUP_AWAIT',actor=1,value=1 if case==32 else 2,extra=int(case==32))
        g('KILL_BEGIN',actor=1,target=worker if case==25 else pid,signal=9)
        terminal(worker,1,buffer,0,0 if case==32 else 1,-125,'cancelled')
        if case!=32:terminal(pid,1,leader_buffer,1,0,-125,'cancelled')
    g('PARENT_PASS',pid=pid,signal=0 if case==23 else 9)
    return b'\n'.join(lines)+b'\n',guest


def validate(raw,guest,arch):
    return validate_owned_waits(raw,arch,guest,native_events(raw,arch,allow_signal=True))


class NativeProcessSignalOwnership(unittest.TestCase):
    def test_all_ten_valid_profiles(self):
        for arch in ARCHES:
            for variant in (0,1):
                for form in range(2 if variant==0 and arch in ('arm32','ppc') else 1):
                    for restart in (0,1):
                        for case in (23,24,25,32):
                            with self.subTest(arch=arch,variant=variant,form=form,restart=restart,case=case):
                                raw,guest=fixture(arch,case,variant,form,restart)
                                result=validate(raw,guest,arch)
                                self.assertEqual(result['owned_requests'],1 if case==32 else 2)

    def test_native_object_domains(self):
        for arch in ARCHES:
            for field,values in [('fd',(0,28)),('description',(0,253)),('pipe_object',(0,14))]:
                for value in values:
                    with self.subTest(arch=arch,field=field,value=value):
                        raw,guest=fixture(arch,24,**{field:value});validate(raw,guest,arch)
            for field,values in [('fd',(30,32,99)),('description',(254,256,999)),('pipe_object',(15,16,999))]:
                for value in values:
                    with self.subTest(arch=arch,field=field,value=value):
                        raw,guest=fixture(arch,24,**{field:value})
                        with self.assertRaises(ValueError):validate(raw,guest,arch)

    def test_reject_timing_identity_and_terminal_mutations(self):
        for arch in ARCHES:
            for case in (23,24,25,32):
                raw,guest=fixture(arch,case)
                cases=[]
                for label,edit in [
                    ('foreign-process',lambda rows:rows[0].update(pid=200)),
                    ('foreign-thread',lambda rows:next(r for r in rows if r['tag']=='THREAD' and r['actor']==0).update(tid=201)),
                    ('copied-buffer',lambda rows:next(r for r in rows if r['tag']=='READ_BEGIN').update(input=0x400fffff)),
                    ('descriptor',lambda rows:next(r for r in rows if r['tag']=='PIPE').update(readfd=9)),
                    ('send-after-retirement',lambda rows:next(r for r in rows if r['tag']=='KILL_BEGIN').update(position=rows[-1]['position']-1)),
                    ('await-before-origin',lambda rows:next(r for r in rows if r['tag']=='EVENT' and r['tag_value'].endswith('AWAIT')).update(position=0)),
                ]:
                    changed=copy.deepcopy(guest);edit(changed);cases.append((label,raw,changed))
                if case==23:
                    changed=copy.deepcopy(guest);next(r for r in changed if r['tag']=='HANDLE')['pc']+=4;cases.append(('frame-pc',raw,changed))
                    cases.append(('not-interrupted',raw.replace(b'outcome=interrupted',b'outcome=ready'),guest))
                else:cases.append(('not-cancelled',raw.replace(b'result=-125 outcome=cancelled',b'result=1 outcome=ready'),guest))
                cases.append(('bad-fd',raw.replace(b'fd=3 ',b'fd=32 '),guest))
                cases.append(('bad-description',raw.replace(b'description=2 ',b'description=256 '),guest))
                cases.append(('bad-pipe',raw.replace(b'pipe=1 ',b'pipe=16 '),guest))
                for label,data,rows in cases:
                    with self.subTest(arch=arch,case=case,mutation=label):
                        with self.assertRaises(ValueError):validate(data,rows,arch)

    def test_duplicate_or_unscoped_event_is_rejected(self):
        raw,guest=fixture('x86_64')
        events=native_events(raw,'x86_64',allow_signal=True)
        extra=dict(events[-1]);extra['position']=guest[-1]['position']+1
        with self.assertRaises(ValueError):validate_owned_waits(raw,'x86_64',guest,events+[extra])


if __name__=='__main__':unittest.main()
