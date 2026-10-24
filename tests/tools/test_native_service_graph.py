"""The serial reader is an evidence parser; these synthetic fixtures are models."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('native_graph_qualifier', ROOT / 'tools/qualify_native_service_graph.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def fixture():
    def event(kind, service, generation, pid, error=0, status=0):
        return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} service={service} '
                f'pid={pid} generation={generation} time_ms=1000 next_ms=0 errno={error} status={status}\n').encode()
    return b''.join((
        b'NATIVE_TERMINATION signal=15 child=12 wait_signal=15 retired=pass\n',
        b'NATIVE_TERMINATION signal=9 child=13 wait_signal=9 retired=pass\n',
        b'NATIVE_TERMINATION_PASS term_wait=15 kill_wait=9 self_kill=9\n',
        event('oneshot-ready', 'termination', 1, 9),
        b'NATIVE_SERVICE_SETUP complete=1\n',
        event('oneshot-ready', 'setup', 1, 2),
        event('launch', 'provider', 1, 3),
        b'NATIVE_SERVICE_CHILD service=provider generation=1 pid=3 event=start\n',
        event('notify-ready', 'provider', 1, 3),
        event('launch', 'dependent', 1, 4),
        b'NATIVE_SERVICE_CHILD service=dependent generation=1 pid=4 event=start\n',
        event('notify-ready', 'dependent', 1, 4),
        event('exec-failed', 'missing', 1, 5, 2),
        event('simple-ready', 'console', 1, 6),
        b'NATIVE_SERVICE_PROVIDER crash=42\n',
        event('reap', 'provider', 1, 3, status=42),
        event('term', 'dependent', 1, 4),
        event('reap', 'dependent', 1, 4, status=128),
        event('launch', 'provider', 2, 7),
        b'NATIVE_SERVICE_CHILD service=provider generation=2 pid=7 event=start\n',
        event('notify-ready', 'provider', 2, 7),
        event('launch', 'dependent', 2, 8),
        b'NATIVE_SERVICE_CHILD service=dependent generation=2 pid=8 event=start\n',
        event('notify-ready', 'dependent', 2, 8),
        b'NATIVE_SERVICE_GRAPH stable=2 dependency_restart=pass\n'))


class NativeShellListsEvidenceTests(unittest.TestCase):
    def test_complete_ordered_records(self):
        reader.validate_shell_lists(b'\n' + reader.OKSH_LISTS_MARKER + b'\r\n' + reader.OKSH_MARKER + b'\n')

    def test_old_or_malformed_or_reordered_trace_is_refused(self):
        lists, final = reader.OKSH_LISTS_MARKER + b'\n', reader.OKSH_MARKER + b'\n'
        for serial in (final, lists, lists + lists + final, final + lists,
                       b'banner' + lists + final, lists.replace(b'exit=pass', b'exit=fail') + final,
                       lists + final + b'OKSH_LISTS partial\n'):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                reader.validate_shell_lists(serial)


def control_fixture():
    def event(kind, service, generation, pid, status=0):
        return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} service={service} '
                f'pid={pid} generation={generation} time_ms=2000 next_ms=0 errno=0 status={status}\n').encode()
    prefix = event('control-enabled', 'none', 0, 1)
    continuation = b''.join((
        reader.CONTROL_CREDENTIALS_MARKER + b'\n',
        reader.CONTROL_DENIED_MARKER + b'\n',
        b'NATIVE_CONTROL_DEADLINE elapsed_ms=1010 activity_ms=610 bound_ms=1200\n',
        reader.CONTROL_TRANSPORT_MARKER + b'\n',
        b'OK_INIT_CONTROL 1 ACCEPTED service=provider pid=7 generation=2\nEND\n',
        event('term', 'dependent', 2, 8, status=1),
        event('reap', 'dependent', 2, 8, status=128),
        event('term', 'provider', 2, 7),
        event('reap', 'provider', 2, 7, status=128),
        event('launch', 'provider', 3, 20),
        b'NATIVE_CONTROL_FDS service=provider generation=3 pid=20 inherited=0\n',
        b'NATIVE_SERVICE_CHILD service=provider generation=3 pid=20 event=start\n',
        event('notify-ready', 'provider', 3, 20),
        event('launch', 'dependent', 3, 21),
        b'NATIVE_CONTROL_FDS service=dependent generation=3 pid=21 inherited=0\n',
        b'NATIVE_SERVICE_CHILD service=dependent generation=3 pid=21 event=start\n',
        event('notify-ready', 'dependent', 3, 21),
        b'NATIVE_CONTROL_GENERATION service=provider old_pid=7 new_pid=20 old_generation=2 new_generation=3\n',
        b'NATIVE_CONTROL_GENERATION service=dependent old_pid=8 new_pid=21 old_generation=2 new_generation=3\n',
        reader.NATIVE_CONTROL_MARKER + b'\n'))
    return prefix + fixture() + continuation


def credentials_fixture():
    def event(kind):
        return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} service=identity '
                f'pid=17 generation=1 time_ms=1000 next_ms=0 errno=0 status=0\n').encode()
    return b''.join((event('launch'),
        b'NATIVE_SERVICE_IDENTITY service=identity pid=17 uid=1000 gid=1000 saved=1000 regain=denied\n',
        event('reap'), event('oneshot-ready'), reader.NATIVE_DROP_MARKER + b'\n',
        b'NATIVE_CREDENTIALS_EXEC kind=permanent inherited=pass regain=denied\n',
        b'NATIVE_CREDENTIALS_EXEC kind=saved reset=pass regain=denied\n', reader.CREDENTIALS_MARKER + b'\n'))


class NativeCredentialsEvidenceTests(unittest.TestCase):
    def test_pid_bound_native_credential_execution(self):
        result = reader.validate_credentials(credentials_fixture())
        self.assertEqual(result['service_identity_pid'], 17)
        self.assertFalse(result['linux_bridge'])

    def test_each_completion_and_identity_is_required_once(self):
        original = credentials_fixture()
        for line in original.splitlines(keepends=True):
            for changed in (original.replace(line, b'', 1), original + line):
                with self.subTest(line=line), self.assertRaises(ValueError):
                    reader.validate_credentials(changed)

    def test_wrong_identity_causality_and_failed_service_are_rejected(self):
        original = credentials_fixture()
        for before, after in ((b'pid=17 uid=', b'pid=18 uid='), (b'uid=1000', b'uid=0'),
                              (b'gid=1000', b'gid=0'), (b'event=launch', b'event=reap'),
                              (b'status=0', b'status=1'), (b'permanent=pass', b'permanent=fail')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                reader.validate_credentials(original.replace(before, after, 1))
        lines = original.splitlines(keepends=True)
        lines[0], lines[1] = lines[1], lines[0]
        reader.validate_credentials(b''.join(lines))  # Child may run before parent logs launch.

    def test_exec_and_control_drop_records_have_actual_execution_order(self):
        original = credentials_fixture()
        lines = original.splitlines(keepends=True)
        permanent = next(i for i, line in enumerate(lines) if b'kind=permanent' in line)
        saved = next(i for i, line in enumerate(lines) if b'kind=saved' in line)
        reversed_exec = list(lines)
        reversed_exec[permanent], reversed_exec[saved] = reversed_exec[saved], reversed_exec[permanent]
        drop = reader.NATIVE_DROP_MARKER + b'\n'
        for serial in (b''.join(reversed_exec), original.replace(drop, b'') + drop,
                       original.replace(drop, b'').replace(reader.CREDENTIALS_MARKER, drop + reader.CREDENTIALS_MARKER)):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                reader.validate_credentials(serial)

    def test_contradictory_identity_failure_and_nonzero_reap_are_refused(self):
        original = credentials_fixture()
        reap = next(line for line in original.splitlines(keepends=True) if b'event=reap ' in line)
        launch = next(line for line in original.splitlines(keepends=True) if b'event=launch ' in line)
        for serial in (original.replace(reap, reap.replace(b'status=0', b'status=9')),
                       original.replace(reap, reap.replace(b'errno=0', b'errno=5')),
                       original.replace(reap, reap.replace(b'pid=17 ', b'pid=18 ')),
                       original.replace(reap, reap.replace(b'generation=1 ', b'generation=2 ')),
                       original.replace(reap, b'') + reap,
                       original.replace(launch, launch + launch.replace(b'event=launch ', b'event=exec-failed ')),
                       original.replace(launch, launch + launch.replace(b'event=launch ', b'event=launch-failed '))):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                reader.validate_credentials(serial)

    def test_other_native_failure_records_cannot_hide_behind_credentials_PASS(self):
        original = credentials_fixture()
        for failure in (b'NATIVE_CREDENTIALS_FAIL code=1\n',
                        b'NATIVE_CONTROL_FAIL code=native-credential-drop\n',
                        b'NATIVE_PID1 event=fatal-hold errno=5\n', b'OK_TEST_FAIL native-runtime=failed\n',
                        b'Kernel panic\n'):
            for serial in (failure + original, original + failure):
                with self.subTest(failure=failure, position=serial.startswith(failure)), self.assertRaises(ValueError):
                    reader.validate_credentials(serial)

    def test_unknown_or_malformed_extra_credential_exec_record_is_refused(self):
        original = credentials_fixture()
        for extra in (b'NATIVE_CREDENTIALS_EXEC kind=unexpected result=pass\n',
                      b'NATIVE_CREDENTIALS_EXEC partial\n',
                      b'prefix NATIVE_CREDENTIALS_EXEC kind=saved reset=pass regain=denied\n'):
            for serial in (extra + original, original + extra):
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    reader.validate_credentials(serial)


class NativeControlEvidenceTests(unittest.TestCase):
    def test_actual_control_generation_and_dependency_identity(self):
        result = reader.validate_control(control_fixture())
        self.assertEqual(result['generations']['provider'], {'old_pid': 7, 'new_pid': 20})
        self.assertTrue(result['dependency_replacement'])

    def test_each_required_control_record_cannot_be_removed_or_duplicated(self):
        original = control_fixture()
        required = [line for line in original.splitlines(keepends=True)
                    if (b'NATIVE_CONTROL_' in line or b'OK_INIT_CONTROL 1 ACCEPTED' in line or b'event=control-enabled' in line or
                        b'generation=3 ' in line or (b'event=term' in line or b'event=reap' in line)
                        and b'generation=2 ' in line)]
        for line in required:
            for changed in (original.replace(line, b'', 1), original + line):
                with self.subTest(line=line), self.assertRaises(ValueError):
                    reader.validate_control(changed)

    def test_wrong_pid_generation_status_or_transport_is_refused(self):
        original = control_fixture()
        for before, after in ((b'old_pid=7', b'old_pid=8'), (b'new_pid=20', b'new_pid=7'),
                              (b'new_generation=3', b'new_generation=4'),
                              (b'pid=20 event=start', b'pid=99 event=start'),
                              (b'elapsed_ms=1010', b'elapsed_ms=1600'),
                              (b'activity_ms=610', b'activity_ms=0'),
                              (b'bound_ms=1200', b'bound_ms=2000'),
                              (b'errno=0 status=128', b'errno=0 status=0'),
                              (b'control-enabled', b'control-unavailable')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                reader.validate_control(original.replace(before, after))
        with self.assertRaises(ValueError):
            reader.validate_control(original + b'NATIVE_CONTROL_GENERATION partial\n')

    def test_dependency_order_is_enforced(self):
        original = control_fixture().splitlines(keepends=True)
        for first, second in ((b'event=term service=dependent pid=8', b'event=term service=provider pid=7'),
                              (b'event=notify-ready service=provider pid=20', b'event=launch service=dependent pid=21')):
            lines = list(original)
            i = next(i for i, line in enumerate(lines) if first in line)
            j = next(i for i, line in enumerate(lines) if second in line)
            lines[i], lines[j] = lines[j], lines[i]
            with self.subTest(first=first), self.assertRaises(ValueError):
                reader.validate_control(b''.join(lines))


class NativeGraphEvidenceTests(unittest.TestCase):
    def test_exact_bounded_synthetic_fixture(self):
        result = reader.validate_serial(fixture())
        self.assertEqual(result['provider_pids'], [3, 7])
        self.assertTrue(result['dependency_retirement'])

    def test_required_events_are_not_optional(self):
        original = fixture()
        for line in original.splitlines(keepends=True):
            with self.subTest(line=line):
                with self.assertRaises(ValueError):
                    reader.validate_serial(original.replace(line, b'', 1))

    def test_duplicate_lifecycle_identity_is_refused(self):
        original = fixture()
        for line in original.splitlines(keepends=True):
            if b'event=launch' in line or b'event=reap' in line or b'event=start' in line:
                with self.subTest(line=line):
                    with self.assertRaises(ValueError):
                        reader.validate_serial(original + line)

    def test_wrong_child_or_status_is_refused(self):
        original = fixture()
        for before, after in (
            (b'pid=7 event=start', b'pid=99 event=start'),
            (b'event=reap service=provider pid=3', b'event=reap service=provider pid=99'),
            (b'errno=0 status=42', b'errno=0 status=0'),
            (b'errno=0 status=128', b'errno=0 status=0'),
            (b'profile=dependency-graph-v1', b'profile=direct-child-v1'),
        ):
            with self.subTest(before=before):
                with self.assertRaises(ValueError):
                    reader.validate_serial(original.replace(before, after, 1))

    def test_readiness_cannot_follow_a_dependent_launch(self):
        lines = fixture().splitlines(keepends=True)
        ready = next(i for i, line in enumerate(lines) if b'notify-ready service=provider pid=7' in line)
        launched = next(i for i, line in enumerate(lines) if b'launch service=dependent pid=8' in line)
        lines[ready], lines[launched] = lines[launched], lines[ready]
        with self.assertRaises(ValueError):
            reader.validate_serial(b''.join(lines))

    def test_diagnostic_hold_never_passes(self):
        with self.assertRaises(ValueError):
            reader.validate_serial(fixture() + b'event=fatal-hold\n')


def adoption_fixture():
    def event(kind, service, pid, generation=0, status=0):
        return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} service={service} '
                f'pid={pid} generation={generation} time_ms=1000 next_ms=0 errno=0 status={status}\n').encode()
    return b''.join((event('launch', 'adoption', 10, 1),
        b'NATIVE_ADOPTION_PARENT pid=10 live=11 zombie=12\n',
        event('reap', 'adoption', 10, 1), event('oneshot-ready', 'adoption', 10, 1),
        event('other-child', 'none', 12, status=31 << 8),
        b'NATIVE_ADOPTION_CHILD pid=11 old_parent=10 new_parent=1 exit=23\n',
        event('other-child', 'none', 11, status=23 << 8)))


class NativeAdoptionEvidenceTests(unittest.TestCase):
    def test_actual_identity_and_both_reaps_are_required(self):
        original = adoption_fixture()
        self.assertTrue(reader.adoption_complete(original))
        self.assertEqual(reader.validate_adoption(original)['live_child'], 11)
        for line in original.splitlines(keepends=True):
            with self.subTest(line=line), self.assertRaises(ValueError):
                reader.validate_adoption(original.replace(line, b'', 1))

    def test_duplicate_or_wrong_parent_child_status_is_refused(self):
        original = adoption_fixture()
        bad = [original + line for line in original.splitlines(keepends=True)]
        bad += [original.replace(before, after) for before, after in (
            (b'old_parent=10', b'old_parent=9'), (b'live=11', b'live=1'),
            (b'new_parent=1', b'new_parent=0'), (b'status=7936', b'status=0'),
            (b'status=5888', b'status=0'), (b'status=7936', b'status=31'),
            (b'status=5888', b'status=23'),
            (b'service=adoption pid=10', b'service=adoption pid=9'),
            (b'service=none pid=11', b'service=none pid=99'))]
        for serial in bad:
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                reader.validate_adoption(serial)

    def test_reap_before_parent_exit_cannot_prove_adoption(self):
        lines = adoption_fixture().splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if b'other-child' in line)
        reaped = lines.pop(index)
        lines.insert(1, reaped)
        with self.assertRaisesRegex(ValueError, 'adopted-child reap'):
            reader.validate_adoption(b''.join(lines))

    def test_partial_or_failed_identity_cannot_finish(self):
        original = adoption_fixture()
        self.assertFalse(reader.adoption_complete(original[:original.rfind(b'NATIVE_PID1')]))
        with self.assertRaises(ValueError):
            reader.validate_adoption(original + b'NATIVE_ADOPTION_FAIL live_parent\n')

    def test_additional_malformed_identity_is_refused(self):
        for line in (b'NATIVE_ADOPTION_CHILD pid=11 old_parent=10\n',
                     b'NATIVE_ADOPTION_PARENT pid=10 live=11 zombie=12 extra=1\n',
                     b'partial bannerNATIVE_ADOPTION_CHILD pid=11 old_parent=10 new_parent=1 exit=23\n'):
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, 'malformed'):
                reader.validate_adoption(adoption_fixture() + line)

    def test_identity_cannot_precede_launch_or_follow_reap(self):
        original = adoption_fixture().splitlines(keepends=True)
        for marker, position in ((b'NATIVE_ADOPTION_PARENT', 'last'),
                                 (b'NATIVE_ADOPTION_CHILD', 'first'),
                                 (b'NATIVE_ADOPTION_CHILD', 'last')):
            lines = list(original)
            index = next(i for i, line in enumerate(lines) if line.startswith(marker))
            moved = lines.pop(index)
            lines.insert(0 if position == 'first' else len(lines), moved)
            with self.subTest(marker=marker, position=position), self.assertRaises(ValueError):
                reader.validate_adoption(b''.join(lines))

    def test_child_can_observe_adoption_before_pid1_reaps_parent(self):
        lines = adoption_fixture().splitlines(keepends=True)
        child = lines.pop(next(i for i, line in enumerate(lines) if line.startswith(b'NATIVE_ADOPTION_CHILD')))
        lines.insert(2, child)
        self.assertTrue(reader.validate_adoption(b''.join(lines))['pid1_reaped'])


if __name__ == '__main__':
    unittest.main()
