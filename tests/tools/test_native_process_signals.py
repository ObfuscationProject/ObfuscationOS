"""Synthetic complete SDK command collectors; none of these fixtures execute."""
from functools import lru_cache
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/tools')]
import native_process_signals_evidence as evidence
from process_signal_guest_protocol import parse
from process_signal_fixtures import events as guest_events,ARCHES
from test_native_signal_delivery_x86_64 import frames,stacks,IMAGE
from test_native_pipe_vector import INIT


@lru_cache(None)
def events(arch):
    raw=guest_events(arch);rows=parse(raw,arch);out=[];current=None;part=[]
    def native_part(part):
        b=part[0];case=b['case'];pid=b['pid'];tids={r['actor']:r['tid'] for r in part if r['tag']=='THREAD'}
        pipes={r['role']:r for r in part if r['tag']=='PIPE'};read=next((r for r in part if r['tag']=='READ_BEGIN'),None)
        live=set();request={0:0,9:0};output=[]
        h=next((r for r in part if r['tag']=='HANDLE'),None)
        width=b['resume']-b['site'];pc=(h['pc']+width if b['restart'] else h['pc']) if case==23 else b['resume']
        def emit(tag,fields):output.append((tag+' '+' '.join(f'{k}={v}' for k,v in fields.items())).encode())
        def shape(role):
            row=read if role==0 else next(r for r in part if r['tag']=='LEADER_READ')
            p=pipes[0 if role==0 else 1]
            return row,p
        def identity(role):
            row,p=shape(role);q=request[role]
            return dict(pid=pid,tid=tids[0] if role==0 else pid,wait=q,request=q,output=row['input'],fd=p['readfd'],description=2 if role==0 else 4,pipe=1 if role==0 else 2,bytes=1)
        def publication(role,signal=False):
            row,p=shape(role);q=request[role]
            result=dict(pid=pid,tid=tids[0] if role==0 else pid,request=q,wait=q,origin=q)
            if signal:result.update(signal=b['usr1'],outcome='restart' if b['restart'] else 'eintr')
            result.update(pc=h['pc'] if signal else pc,syscall=b['read'],fd=p['readfd'],output=row['input'],bytes=1)
            if signal:result.update(pinned=0,live=len(live))
            return result
        def arm(role):
            request[role]+=1;live.add(role)
            emit('OK_NATIVE_PIPE_READ_WAIT',dict(identity(role),stage='arm',live=len(live)))
            emit('OK_NATIVE_PIPE_ORIGIN',publication(role))
        def complete(role,outcome,result):
            live.remove(role)
            emit('OK_NATIVE_PIPE_READ_COMPLETE',dict(identity(role),result=result,outcome=outcome,pinned=0,live=len(live)))
        for row in part:
            tag=row['tag'];ev=row.get('event')
            if case in (20,21) and ev=='EXEC_REPLACED':output.append(IMAGE.rstrip(b'\n'))
            if case==23 and tag=='HANDLE':
                complete(0,'interrupted',0 if b['restart'] else -4)
                emit('OK_NATIVE_PIPE_SIGNAL',publication(0,True))
            output.append(row['line'])
            if case==0 and ev=='ZOMBIE_GATE':
                for ticket,(outcome,result) in enumerate((('ready',1),('eof',0)),1):
                    identity=dict(pid=pid,tid=pid,wait=ticket,request=ticket,output=b['site']+0x9000,fd=row['value'],description=2,pipe=1,bytes=1)
                    emit('OK_NATIVE_PIPE_READ_WAIT',dict(identity,stage='arm',live=1))
                    emit('OK_NATIVE_PIPE_ORIGIN',dict(pid=pid,tid=pid,request=ticket,wait=ticket,origin=ticket,pc=b['resume'],syscall=b['read'],fd=row['value'],output=b['site']+0x9000,bytes=1))
                    emit('OK_NATIVE_PIPE_READ_COMPLETE',dict(identity,result=result,outcome=outcome,pinned=0,live=0))
            if case in (23,24,25,32):
                if tag=='READ_BEGIN':arm(0)
                if tag=='LEADER_READ' and case!=32:arm(9)
                if case==23:
                    if tag=='HANDLE' and b['restart'] or ev=='READ_RETRY':arm(0)
                    if ev=='READ_RELEASE':complete(0,'ready',1)
                elif tag=='KILL_BEGIN':
                    complete(0,'cancelled',-125)
                    if case!=32:complete(9,'cancelled',-125)
        return output
    for row in rows:
        if row['tag']=='CASE_BEGIN':part=[row]
        elif row['tag']=='PARENT_PASS':part.append(row);out.extend(native_part(part));part=[]
        elif row['tag']=='PASS':out.append(row['line'])
        else:part.append(row)
    return b'\n'.join(out)+b'\n'


def transcript(arch):
    _,_,command,leases=evidence.probe_spec(arch,'process-shared-signals')
    body=command+b'\n'+IMAGE+events(arch)
    def f(a,r,objects=1):return frames(a,r).replace(b'objects=0',f'objects={objects}'.encode()).replace(f'user={a-r}'.encode(),f'user={a-r-objects}'.encode())
    parts=[b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+f(0,0,0)+stacks(0,0,0,peak=0)+INIT+f(40,0)+stacks(7,5,100)+b'oksh> ',
           b'hello | cat\nhello from ObfuscationOS userland\n'+f(100,60)+stacks(10,8,200)+b'oksh> ',
           body+f(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
           body+f(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
           b'hello | cat\nhello from ObfuscationOS userland\n'+f(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ']
    if arch in ('loongarch64','mips','mips64'):parts=[p.replace(b'source=firmware',b'source=linker') for p in parts]
    return parts


def validate(parts,arch):
    bounds=[sum(map(len,parts[:i])) for i in range(1,5)]
    return evidence.validate_execution(b''.join(parts),*bounds,bounds[-1],arch)


class NativeProcessSignals(unittest.TestCase):
    def test_all_ten_complete_wrappers(self):
        for arch in ARCHES:
            with self.subTest(arch=arch):
                result=validate(transcript(arch),arch)
                self.assertEqual(result['runs'],2)
                self.assertTrue(result['process_directed_kill'])
                self.assertEqual(result['observations'][0]['cases'],198 if arch in ('arm32','ppc') else 132)
                self.assertEqual(result['observations'][0]['native_waits']['owned_requests'],42 if arch in ('arm32','ppc') else 28)

    def test_native_case_crlf(self):
        for arch in ARCHES:
            raw=events(arch)
            self.assertEqual(evidence.validate_cases(raw,arch),evidence.validate_cases(raw.replace(b'\n',b'\r\n'),arch))

    def test_complete_wrapper_record_domains(self):
        for arch in ARCHES:
            parts=transcript(arch)
            for before,after in [(b'fd=3 ',b'fd=32 '),(b'description=2 ',b'description=256 '),(b'pipe=1 ',b'pipe=16 '),
                                 (b'outcome=cancelled',b'outcome=ready'),(b'pinned=0',b'pinned=1'),
                                 (b'outcome=eintr',b'outcome=restart'),(b'format=status',b'format=invalid'),
                                 (b'PROCESS_SIGNAL_HANDLE ',b'PROCESS_SIGNAL_UNKNOWN '),
                                 (b'PROCESS_SIGNAL_PARENT_PASS ',b'PROCESS_SIGNAL_FAIL code=111 '),
                                 (b' uid=1101 ',b' uid=0 '),(b' sender=0 uid=0 ',b' sender=1 uid=0 ')]:
                index=next(i for i,p in enumerate(parts) if before in p)
                changed=parts.copy();changed[index]=changed[index].replace(before,after,1)
                with self.subTest(arch=arch,before=before),self.assertRaises(ValueError):validate(changed,arch)

    def test_full_wrapper_rejects_missing_and_duplicate_native_records(self):
        for arch in ARCHES:
            parts=transcript(arch)
            for prefix in (b'OK_NATIVE_PIPE_READ_WAIT ',b'OK_NATIVE_PIPE_ORIGIN ',b'OK_NATIVE_PIPE_READ_COMPLETE ',b'OK_NATIVE_PIPE_SIGNAL ',b'OK_NATIVE_IMAGE ',b'PROCESS_SIGNAL_CASE_BEGIN ',b'PROCESS_SIGNAL_PASS '):
                line=next(x for x in parts[2].splitlines(keepends=True) if x.startswith(prefix))
                for replacement in (b'',line+line):
                    changed=parts.copy();changed[2]=changed[2].replace(line,replacement,1)
                    with self.subTest(arch=arch,prefix=prefix,duplicate=bool(replacement)),self.assertRaises(ValueError):validate(changed,arch)

    def test_qualifier_layout(self):
        import qualify_native_process_signals as qualifier
        for arch in ARCHES:
            source,name,command=qualifier.probe_layout(arch,'process-shared-signals')
            self.assertEqual(source,'native_process_signals')
            self.assertEqual(command,'/bin/'+name)
            self.assertLessEqual(len(name),31)


if __name__=='__main__':unittest.main()
