"""Independent ordinary signal observer audit; replay does not execute a guest.

This file may be retained at tests/tools/audit_native_signal_production.py.
Use OBSERVER_REVIEW_SOURCE to audit an explicit frozen OS source instead.
"""
import os,re,sys,unittest
from pathlib import Path
SOURCE=Path(os.environ.get('OBSERVER_REVIEW_SOURCE',Path(__file__).resolve().parents[2])).resolve()
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE/'tests/tools')]
import native_signal_production_evidence as evidence
from test_native_signal_production import transcript,change_part,profile
from native_child_exit_guest import ARCHES

COUNT={'positive':0,'negative':0,'observer':0}
PLATFORM=b'N64_SIGNAL_PLATFORM_PASS before-cxx=1 fp=fr1\n'

def fixture(arch,kind,mode):
    serial,bounds=transcript(arch,kind,mode=mode,echo=False)
    if arch=='mips64' and PLATFORM not in serial:
        serial,bounds=change_part(serial,bounds,0,lambda p:PLATFORM+p)
    return serial,bounds

class IndependentOrdinaryReview(unittest.TestCase):
    def accept(self,serial,bounds,arch,kind,mode):
        COUNT['positive']+=1
        result=evidence.validate_execution(serial,*bounds,arch,kind,mode)
        self.assertEqual(result['runs'],2)
        self.assertEqual(len(result['observations']),2)
        self.assertTrue(result['parser_replay_only'])
        for key in ('native_execution','private_diagnostics','internal_blocked_waits_verified',
                    'internal_reclaim_ledger_verified','fault_injection_verified','physical','smp',
                    'full_posix_claim','private_signal_lifetime_join','actual_first_queued_sender_verified',
                    'unpublished_rollback_identity_verified'):
            self.assertFalse(result[key],key)
        return result
    def reject(self,serial,bounds,arch,kind,mode,reason=None):
        COUNT['negative']+=1
        if reason:
            with self.assertRaisesRegex(ValueError,reason):evidence.validate_execution(serial,*bounds,arch,kind,mode)
        else:
            with self.assertRaises(ValueError):evidence.validate_execution(serial,*bounds,arch,kind,mode)
    def rows(self):
        for arch in ARCHES:
            for kind in evidence.KINDS:
                for mode in ('debug','release'):
                    yield arch,kind,mode
    def test_four_commands_and_two_actual_observation_counts(self):
        for arch,kind,mode in self.rows():
            with self.subTest(arch=arch,kind=kind,mode=mode):
                data,bounds=fixture(arch,kind,mode);self.accept(data,bounds,arch,kind,mode)
                got=evidence.observe_guest_execution(data,arch,kind);COUNT['observer']+=1
                self.assertEqual(got['guest_invocation_starts_observed'],2)
                self.assertEqual(got['observed_pass_markers'],2)
                self.assertEqual(got['guest_failure_markers_observed'],0)
                self.assertEqual(got['guest_begin_markers_observed'],36 if kind=='child-exit-policy' else 2)
                self.assertTrue(got['executed']);self.assertNotIn('native_execution_accepted',got)
    def test_failures_rejected_in_every_command_and_boot(self):
        failures=(b'OK_TEST_FAIL injected\n',b'POSIX_CHECK failed: injected\n',
                  b'CHILD_EXIT_FAIL line=0001 case=99\n',b'CHILD_PRESSURE_FAIL line=0001 wave=9\n',
                  b'N64_SIGNAL_PLATFORM_REJECT reason=no-fpu before-cp1=1\n',
                  b'N64_PRIVATE_EARLY_PASS before-cxx=1 fp=fr1\n',
                  b'N64_PRIVATE_EARLY_REJECT reason=no-fpu before-cp1=1\n')
        for arch,kind,mode in self.rows():
            data,bounds=fixture(arch,kind,mode)
            for part in range(5):
                for fail in failures:
                    with self.subTest(arch=arch,kind=kind,mode=mode,part=part,fail=fail):
                        changed=change_part(data,bounds,part,lambda p:fail+p)
                        self.reject(*changed,arch,kind,mode)
    def test_n64_platform_admission_complete_unique_and_boot_only(self):
        for arch,kind,mode in self.rows():
            data,bounds=fixture(arch,kind,mode)
            if arch=='mips64':
                stripped=change_part(data,bounds,0,lambda p:p.replace(PLATFORM,b''))
                self.reject(*stripped,arch,kind,mode)
                late=change_part(data,bounds,0,lambda p:p.replace(PLATFORM,b'',1).replace(
                    b'OK_SYSTEM_GUI boot=complete\n',b'OK_SYSTEM_GUI boot=complete\n'+PLATFORM,1))
                self.reject(*late,arch,kind,mode)
                # A second, prefixed platform record is still suspicious even
                # though the exact assembly line remains present and valid.
                self.reject(*change_part(data,bounds,0,lambda p:b'prefix '+PLATFORM+p),arch,kind,mode)
                for altered in (PLATFORM*2,PLATFORM.replace(b'before-cxx=1',b'before-cxx=0'),
                                PLATFORM.replace(b'fp=fr1',b'fp=fr0'),PLATFORM[:-1],b'prefix '+PLATFORM,
                                PLATFORM.replace(b' fp=fr1',b' fp=fr1 unknown=1')):
                    with self.subTest(kind=kind,mode=mode,altered=altered):
                        self.reject(*change_part(data,bounds,0,lambda p:p.replace(PLATFORM,altered)),arch,kind,mode)
                for part in range(1,5):
                    changed=change_part(*stripped,part,lambda p:PLATFORM+p)
                    self.reject(*changed,arch,kind,mode)
            else:
                self.reject(*change_part(data,bounds,0,lambda p:PLATFORM+p),arch,kind,mode)
                self.reject(*change_part(data,bounds,0,lambda p:b'prefix '+PLATFORM+p),arch,kind,mode)
    def test_resource_counter_replay_and_retirement_order(self):
        for arch,kind,mode in self.rows():
            data,bounds=fixture(arch,kind,mode)
            previous=data[bounds[0]:bounds[1]]
            oldrows={prefix:next(row for row in previous.splitlines(True) if row.startswith(prefix))
                     for prefix in (b'OK_NATIVE_FRAMES ',b'OK_ENTRY_STACKS ')}
            for prefix,old in oldrows.items():
                with self.subTest(arch=arch,kind=kind,mode=mode,prefix=prefix):
                    def replay(p):return b''.join(old if row.startswith(prefix) else row for row in p.splitlines(True))
                    self.reject(*change_part(data,bounds,2,replay),arch,kind,mode)
            marker=evidence.probe_spec(arch,kind)[0]+b'\n'
            def before_pass(p):
                resources=b''.join(row for row in p.splitlines(True) if row.startswith((b'OK_NATIVE_FRAMES ',b'OK_ENTRY_STACKS ')))
                body=b''.join(row for row in p.splitlines(True) if not row.startswith((b'OK_NATIVE_FRAMES ',b'OK_ENTRY_STACKS ')))
                return body.replace(marker,resources+marker)
            self.reject(*change_part(data,bounds,2,before_pass),arch,kind,mode)
            ends=[0,*bounds[:4],len(data)];parts=[data[a:b] for a,b in zip(ends,ends[1:])]
            parts[2],parts[3]=parts[3],parts[2]
            swapped=b''.join(parts);new=[sum(map(len,parts[:i])) for i in range(1,5)]
            self.reject(swapped,(*new,new[-1]),arch,kind,mode)
    def test_modes_private_diagnostics_and_failure_execution_flags(self):
        for arch,kind,mode in self.rows():
            data,bounds=fixture(arch,kind,mode)
            self.reject(data,bounds,arch,kind,'release' if mode=='debug' else 'debug')
            for noise in (b'OK_NATIVE_CHILD_EXIT child=123\n',b'OK_NATIVE_SIGNAL_WAIT_ARM forged\n',
                          b'OK_NATIVE_PIPE_ORIGIN forged\n',b'OK_NATIVE_POLL_SIGNAL forged\n'):
                self.reject(*change_part(data,bounds,2,lambda p:noise+p),arch,kind,mode)
            failure=b'CHILD_EXIT_FAIL line=0001 case=99' if kind=='child-exit-policy' else b'CHILD_PRESSURE_FAIL line=0001 wave=9'
            for n in range(len(failure)+1):
                got=evidence.observe_guest_execution(failure[:n],arch,kind);COUNT['observer']+=1
                self.assertFalse(got['executed']);self.assertNotIn('native_execution_accepted',got)
            got=evidence.observe_guest_execution(failure+b'\n',arch,kind);COUNT['observer']+=1
            self.assertTrue(got['executed']);self.assertEqual(got['guest_failure_markers_observed'],1)
            self.assertEqual(got['observed_pass_markers'],0);self.assertEqual(got['guest_invocation_starts_observed'],0)
            self.assertIsNotNone(evidence.failure_line(failure))
    def test_sdk_and_libc_mode_binding_and_no_implicit_signal_admission(self):
        from copy import deepcopy
        for arch,kind,mode in self.rows():
            baseline=profile(arch,mode)
            self.assertIs(evidence.admit_profile(baseline,arch,mode),baseline)
            libc=dict(mode='debug',compiler=dict(triple=baseline['triple'],version=baseline['compiler']['version']))
            bound=evidence.admit_libc_mode(libc,'debug',baseline)
            self.assertEqual(bound['kernel_mode'],mode);self.assertEqual(bound['musl_mode'],'debug')
            self.assertEqual(bound['distribution_mode'],mode)
            for field,value in (('mode','release'),('compiler',dict(triple='wrong',version='14.2.0')),
                                ('compiler',dict(triple=baseline['triple'],version='0'))):
                wrong=deepcopy(libc);wrong[field]=value
                with self.assertRaises(ValueError):evidence.admit_libc_mode(wrong,'debug',baseline)
            for flags in (['-UOK_NATIVE_SIGNAL_RUNTIME'],['-Wp,-U,OK_NATIVE_SIGNAL_RUNTIME'],
                          ['-D','OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE']):
                for field in ('cxxflags','asflags'):
                    invalid=deepcopy(baseline);invalid[field]+=flags
                    with self.assertRaises(ValueError):evidence.admit_profile(invalid,arch,mode)

if __name__=='__main__':
    try:unittest.main()
    finally:print('INDEPENDENT_OBSERVER_COUNTS',COUNT,flush=True)
