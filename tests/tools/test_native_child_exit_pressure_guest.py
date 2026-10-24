"""Synthetic pressure journals; these tests execute neither target code nor QEMU."""
from pathlib import Path
import re
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from native_child_exit_pressure_guest import guest_events,probe_spec,failure_line,incomplete_failure_line
from native_child_exit_guest import ARCHES,expected_info

COUNTS=dict(positive=0,negative=0)


def fixture(arch='x86_64',counts=(3,4,5),selected='last',uid=1000,errors=(11,12,11)):
    lines=[f'CHILD_PRESSURE_BEGIN arch={arch} pid=100 uid={uid} cap=128 waves=3 failures=3']
    seq=0;next_pid=101
    def event(w,op,a,b,c):
        nonlocal seq
        lines.append(f'CHILD_PRESSURE_EVENT arch={arch} wave={w} seq={seq} op={op} a={a} b={b} c={c}');seq+=1
    def info(w,via,pid,status):
        nonlocal seq
        chld=18 if arch.startswith('mips') else 17
        hexdata=expected_info(arch,1,pid,uid,status).hex()
        lines.append(f'CHILD_PRESSURE_INFO arch={arch} wave={w} seq={seq} via={via} signal={chld} code=1 child={pid} uid={uid} status={status} bytes=128 hex={hexdata}');seq+=1
    for wave,count in enumerate(counts):
        event(wave,'CONFIG',wave,1,0);event(wave,'INITIAL_ABSENT',11,1,0);pids=[]
        for i in range(count):
            event(wave,'FORK_BEGIN',i,len(pids),0);pids.append(next_pid);next_pid+=1
            event(wave,'SPAWN',pids[-1],i,37)
        for i in range(3):event(wave,'FORK_BEGIN',count+i,count,i);event(wave,'FORK_FAIL',count+i,errors[i],i+1)
        event(wave,'EXHAUSTED',count,3,128)
        for pid in pids:event(wave,'LIVE',pid,0,0)
        event(wave,'NO_EXTRA',0,0,0);event(wave,'FAILURE_ABSENT',11,1,0);event(wave,'RELEASE',count,count,37)
        for pid in pids:event(wave,'ECHILD' if wave else 'WAIT',pid,10 if wave else 9472,0 if wave else 1)
        event(wave,'EMPTY',10,0,0)
        if wave!=1:info(wave,'coalesced',(pids[0] if selected=='first' else pids[-1]) if pids else 99999,37)
        event(wave,'DRAINED',11,1,0);event(wave,'RECOVERY_CONFIG',0,1,0);event(wave,'RECOVERY_BEGIN',0,0,39)
        pid=next_pid;next_pid+=1;event(wave,'RECOVERY_SPAWN',pid,0,39);event(wave,'RECOVERY_RELEASE',pid,1,39)
        event(wave,'RECOVERY_WAIT',pid,9984,1);info(wave,'recovery',pid,39)
        event(wave,'RECOVERY_ABSENT',11,1,0);event(wave,'WAVE_DONE',count,3,1)
    lines.append(probe_spec(arch)[0].decode())
    return ('\n'.join(lines)+'\n').encode()


def replace_field(line,key,value):
    changed,n=re.subn(rb'(?<![a-z_])'+key.encode()+rb'=[^ \r\n]+',(key+'='+str(value)).encode(),line)
    assert n==1
    return changed


class PressureGuestTests(unittest.TestCase):
    def positive(self,data,arch):
        COUNTS['positive']+=1
        return guest_events(data,arch)
    def negative(self,data,arch):
        COUNTS['negative']+=1
        with self.assertRaises(ValueError):guest_events(data,arch)

    def test_all_architectures_variable_capacity_and_arbitrary_first_sender(self):
        for arch in ARCHES:
            for counts in ((2,2,2),(3,4,5),(16,16,16),(4,2,3)):
                for chosen in ('first','last'):
                    data=fixture(arch,counts,chosen)
                    got=self.positive(data,arch)
                    self.assertEqual(got['pressure_children'],sum(counts))
                    self.assertEqual(got['minimum_entry_leases'],sum(counts)+4)
                    self.assertEqual(got['failed_forks'],9)
                    self.assertFalse(got['native_execution'])
                    self.assertTrue(got['requires_kernel_lifetime_join'])
                    self.assertEqual(len(got['waves']),3)
                    self.positive(data.replace(b'\n',b'\r\n'),arch)

    def test_every_record_is_required_unique_and_ordered(self):
        for arch in ARCHES:
            rows=fixture(arch).splitlines(True)
            for i,row in enumerate(rows):
                self.negative(b''.join(rows[:i]+rows[i+1:]),arch)
                self.negative(b''.join(rows[:i]+[row,row]+rows[i+1:]),arch)
                self.negative(b''.join(rows[:i]+[row.replace(b'CHILD_PRESSURE_',b'CHILD_PRESSURE_UNKNOWN_',1)]+rows[i+1:]),arch)
                if i+1<len(rows):self.negative(b''.join(rows[:i]+[rows[i+1],row]+rows[i+2:]),arch)

    def test_each_event_sequence_wave_and_observation_are_bound(self):
        for arch in ARCHES:
            rows=fixture(arch).splitlines(True)
            for i,row in enumerate(rows):
                if b'CHILD_PRESSURE_EVENT ' not in row:continue
                for key,value in [('seq',9999),('wave',9),('a',-999),('b',-999),('c',-999)]:
                    self.negative(b''.join(rows[:i]+[replace_field(row,key,value)]+rows[i+1:]),arch)

    def test_siginfo_is_complete_target_layout_and_member_sender(self):
        for arch in ARCHES:
            rows=fixture(arch).splitlines(True)
            for i,row in enumerate(rows):
                if b'CHILD_PRESSURE_INFO ' not in row:continue
                for key,value in [('child',99999),('uid',1001),('status',23),('code',2),('signal',10),('bytes',127),('via','invented')]:
                    self.negative(b''.join(rows[:i]+[replace_field(row,key,value)]+rows[i+1:]),arch)
                original=re.search(rb' hex=([0-9a-f]+)',row)[1];payload=bytes.fromhex(original.decode())
                for offset in range(128):
                    changed=bytearray(payload);changed[offset]^=1
                    new=row.replace(original,changed.hex().encode())
                    self.negative(b''.join(rows[:i]+[new]+rows[i+1:]),arch)

    def test_failure_and_capacity_domains(self):
        for arch in ARCHES:
            for counts in ((0,2,2),(1,2,2),(2,0,2),(2,2,1),(126,2,2)):
                self.negative(fixture(arch,counts),arch)
            for errors in ((0,11,11),(4,11,11),(11,13,11),(11,12,999)):
                self.negative(fixture(arch,errors=errors),arch)
            data=fixture(arch)
            for before,after in ((b'pid=100 ',b'pid=0 '),(b'pid=100 ',b'pid=1073741824 '),
                (b'uid=1000 ',b'uid=4294967296 '),(b'cap=128 ',b'cap=16 '),
                (b'op=SPAWN a=101 ',b'op=SPAWN a=100 '),(b'op=SPAWN a=102 ',b'op=SPAWN a=101 '),
                (b'exhaustion=3',b'exhaustion=2'),(b'failed_attempts=9',b'failed_attempts=8')):
                self.negative(data.replace(before,after,1),arch)

    def test_framing_failure_markers_and_native_scope(self):
        for arch in ARCHES:
            data=fixture(arch);rows=data.splitlines(True)
            self.negative(data[:-1],arch)
            self.negative(data+b'CHILD_PRESSURE_FAIL line=0123 wave=1\n',arch)
            self.negative(data+b'CHILD_PRESSURE_FAIL line=0123 wave=1',arch)
            self.negative(data+b'noise CHILD_PRESSURE_',arch)
            interleaved=b''.join(b'kernel record is validated by root collector\n'+row for row in rows)
            observed=self.positive(interleaved,arch)
            self.assertEqual(observed['begin']['position'],1)
            self.assertFalse(observed['native_execution'])
        self.assertIsNotNone(failure_line(b'CHILD_PRESSURE_FAIL'))
        self.assertTrue(incomplete_failure_line(b'CHILD_PRESSURE_FAIL'))
        self.assertFalse(incomplete_failure_line(b'CHILD_PRESSURE_FAIL\n'))
        with self.assertRaises(ValueError):probe_spec('unsupported')


if __name__=='__main__':
    try:unittest.main()
    finally:print('HOSTED_PRESSURE_CONTROLS',COUNTS,flush=True)
