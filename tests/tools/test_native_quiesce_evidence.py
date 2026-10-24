"""Synthetic observer controls are models, not native execution evidence."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_quiesce_evidence import validate_quiesce


def event(kind, service='none', pid=1, generation=0, time=1200, status=0):
    return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} service={service} '
            f'pid={pid} generation={generation} time_ms={time} next_ms=0 errno=0 status={status}\n').encode()


def fixture():
    return b''.join((
        event('launch', 'provider', 20, 3), event('launch', 'dependent', 21, 3),
        b'NATIVE_QUIESCE_DENIED uid=1000 state=public mutation=unchanged\n',
        b'NATIVE_QUIESCE_BEGIN observer=100 parent=1\n',
        event('quiesce-started'),
        b'OK_INIT_CONTROL 1 QUIESCE accepted=1 started_ms=1200 deadline_ms=19200\nEND\n',
        event('term', 'dependent', 21, 3), event('reap', 'dependent', 21, 3, status=128),
        event('term', 'provider', 20, 3), event('reap', 'provider', 20, 3, status=128),
        event('graph-stopped'),
        b'NATIVE_QUIESCE_HELD observer=100 phase=quiescing graph=stopped children=live started_ms=1200 deadline_ms=19200\n',
        b'NATIVE_QUIESCE_RELEASE observer=100 graph=stopped children=live duplicate=pass restart=busy wait_exit=37\n',
        event('other-child', pid=100, status=37 << 8), event('quiesced')))


class QuiesceEvidenceTests(unittest.TestCase):
    def test_complete_causal_trace(self):
        result = validate_quiesce(fixture().replace(b'\n', b'\r\n'))
        self.assertTrue(result['live_adopted_child_blocked'])
        self.assertEqual(result['observer_pid'], 100)
        self.assertFalse(result['synchronized_shutdown'])

    def test_missing_duplicate_and_prefixed_records(self):
        rows = fixture().splitlines(keepends=True)
        for row in rows:
            if b'NATIVE_' not in row and b'QUIESCE accepted=' not in row:
                continue
            variants = [fixture().replace(row, b'', 1), fixture() + row]
            # PID1 records may follow an existing console prompt. Fixture and
            # control records require whole-line framing.
            if b'NATIVE_PID1 ' not in row:
                variants.append(fixture().replace(row, b'banner' + row, 1))
            for changed in variants:
                with self.subTest(row=row), self.assertRaises(ValueError):
                    validate_quiesce(changed)

    def test_wrong_identity_status_deadline_and_scope(self):
        for old, new in (
            (b'HELD observer=100', b'HELD observer=101'),
            (b'RELEASE observer=100', b'RELEASE observer=101'),
            (b'status=9472', b'status=37'),
            (b'deadline_ms=19200', b'deadline_ms=19300'),
            (b'graph=stopped children=live started', b'graph=stopped children=empty started'),
            (b'parent=1', b'parent=2'),
            (b'event=quiesced service=none pid=1', b'event=quiesced service=none pid=2'),
            (b'event=quiesced service=none pid=1 generation=0 time_ms=1200',
             b'event=quiesced service=none pid=1 generation=0 time_ms=19200')):
            with self.subTest(old=old), self.assertRaises(ValueError):
                validate_quiesce(fixture().replace(old, new))

    def test_premature_completion_and_dependency_order(self):
        serial = fixture()
        complete = event('quiesced')
        reap = event('other-child', pid=100, status=37 << 8)
        dependent = event('reap', 'dependent', 21, 3, status=128)
        provider = event('term', 'provider', 20, 3)
        for changed in (
            serial.replace(complete, b'').replace(reap, complete + reap),
            serial.replace(dependent, b'').replace(provider, provider + dependent),
            serial + event('launch', 'missing', 200, 4),
            serial + event('reap', 'console', 22, 1),
            serial + b'NATIVE_QUIESCE_FAIL code=1\n',
            serial + event('fatal-hold')):
            with self.assertRaises(ValueError):
                validate_quiesce(changed)

    def test_event_clock_and_final_process_identity_contradictions(self):
        serial = fixture()
        for changed in (
            serial.replace(event('other-child', pid=100, status=37 << 8),
                           event('other-child', pid=100, status=37 << 8, time=19000)),
            serial.replace(event('graph-stopped'), event('graph-stopped', time=1)),
            serial.replace(event('other-child', pid=100, status=37 << 8),
                           event('other-child', pid=100, status=37 << 8, time=19200)),
            serial.replace(b'service=provider pid=20', b'service=provider pid=100'),
            serial.replace(b'service=dependent pid=21', b'service=dependent pid=20'),
            serial.replace(b'service=provider pid=20', b'service=provider pid=1'),
            serial.replace(event('reap', 'provider', 20, 3, status=128),
                           event('reap', 'provider', 20, 3, status=0))):
            with self.assertRaises(ValueError):
                validate_quiesce(changed)

    def test_acknowledgment_frame_and_known_shell_prompt(self):
        ack = b'OK_INIT_CONTROL 1 QUIESCE accepted=1 started_ms=1200 deadline_ms=19200\n'
        self.assertTrue(validate_quiesce(fixture().replace(ack, b'oksh> ' + ack))['quiesced'])
        for replacement in (ack, ack + b'EN\n', ack + b'END\nEND\n',
                            b'oksh> oksh> ' + ack + b'END\n'):
            with self.assertRaises(ValueError):
                validate_quiesce(fixture().replace(ack + b'END\n', replacement))


if __name__ == '__main__':
    unittest.main()
