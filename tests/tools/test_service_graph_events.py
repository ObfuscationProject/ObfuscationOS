"""Reject forged/missing service observations while permitting causal interleavings."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from service_graph_events import PASS, validate

FIXTURE = Path(__file__).with_name('service_graph_serial_fixture.txt').read_bytes()


class ServiceGraphEvidenceTests(unittest.TestCase):
    def test_observed_native_sequence_and_crlf(self):
        for serial in (FIXTURE, FIXTURE.replace(b'\n', b'\r\n')):
            result = validate(serial)
            self.assertEqual(result['orphan_pid'], 62)
            self.assertEqual(result['restarts'], 2)
            self.assertEqual(result['shutdown'], 'reverse-dependency')

    def test_every_record_is_required_once(self):
        rows = FIXTURE.splitlines(keepends=True)
        for index in range(len(rows)):
            with self.subTest(index=index, mutation='deleted'):
                with self.assertRaises(ValueError): validate(b''.join(rows[:index] + rows[index + 1:]))
            with self.subTest(index=index, mutation='duplicate'):
                with self.assertRaises(ValueError): validate(b''.join(rows[:index] + [rows[index]] + rows[index:]))

    def test_ownership_generation_and_status_mutations(self):
        rows = FIXTURE.splitlines(keepends=True)
        for index, row in enumerate(rows[:-1]):
            for field in (b'pid=', b'generation=', b'value='):
                start = row.index(field) + len(field)
                end = row.find(b' ', start)
                if end == -1: end = len(row) - 1
                value = int(row[start:end])
                replacement = row[:start] + str(value + 1).encode() + row[end:]
                with self.subTest(index=index, field=field):
                    with self.assertRaises(ValueError): validate(b''.join(rows[:index] + [replacement] + rows[index + 1:]))

    def test_reap_and_shutdown_causality(self):
        pairs = [(b'kind=ready name=setup', b'kind=launch name=upstream generation=1'),
                 (b'kind=ready name=upstream generation=1', b'kind=launch name=downstream generation=1'),
                 (b'kind=reap-service name=downstream generation=1', b'kind=launch name=downstream generation=2'),
                 (b'kind=reap-service name=downstream generation=2', b'kind=term name=upstream generation=2'),
                 (b'kind=term name=downstream generation=1', b'kind=orphan name=downstream'),
                 (b'kind=orphan name=downstream', b'kind=reap-other name=init'),
                 (b'kind=request-stop', b'kind=shutdown')]
        for first, second in pairs:
            rows = FIXTURE.splitlines(keepends=True)
            left = next(i for i, row in enumerate(rows) if first in row)
            right = next(i for i, row in enumerate(rows) if second in row)
            rows[left], rows[right] = rows[right], rows[left]
            with self.subTest(first=first):
                with self.assertRaises(ValueError): validate(b''.join(rows))
        rows = FIXTURE.splitlines(keepends=True)
        first_child = next(i for i, row in enumerate(rows) if b'SERVICE_CHILD' in row)
        rows.insert(0, rows.pop(first_child))
        with self.assertRaises(ValueError): validate(b''.join(rows))

    def test_permitted_child_and_parent_interleavings(self):
        rows = FIXTURE.splitlines(keepends=True)
        # A child can run before the parent's post-fork launch log.
        launch = next(i for i, row in enumerate(rows) if b'kind=launch name=setup' in row)
        start = next(i for i, row in enumerate(rows) if b'SERVICE_CHILD kind=start name=setup' in row)
        rows[launch], rows[start] = rows[start], rows[launch]
        validate(b''.join(rows))
        # A dedicated readiness ack can be inspected before exec-channel EOF.
        rows = FIXTURE.splitlines(keepends=True)
        execution = next(i for i, row in enumerate(rows) if b'SERVICE_EVENT kind=exec name=upstream generation=1' in row)
        acknowledgment = next(i for i, row in enumerate(rows) if b'SERVICE_EVENT kind=notify name=upstream generation=1' in row)
        child_notification = next(i for i, row in enumerate(rows) if b'SERVICE_CHILD kind=notify name=upstream generation=1' in row)
        rows[execution], rows[acknowledgment] = rows[acknowledgment], rows[execution]
        self.assertLess(execution, child_notification)
        validate(b''.join(rows))
        # An adopted child may be reaped after shutdown begins.
        rows = FIXTURE.splitlines(keepends=True)
        orphan = next(i for i, row in enumerate(rows) if b'kind=reap-other' in row)
        item = rows.pop(orphan)
        shutdown = next(i for i, row in enumerate(rows) if b'kind=shutdown' in row)
        rows.insert(shutdown + 1, item)
        validate(b''.join(rows))

    def test_malformed_failure_and_incomplete_evidence(self):
        for serial in (PASS + b'\n', FIXTURE[:-1], FIXTURE + PASS + b'\n',
                       FIXTURE + b'OK_TEST_FAIL after-completion\n',
                       FIXTURE + b'kernel-probe-failed name=disk\n',
                       FIXTURE + b'SERVICE_EVENT kind=failed name=init generation=0 pid=1 value=0\n',
                       FIXTURE.replace(b'pid=58', b'pid=2147483648', 1),
                       FIXTURE.replace(b'generation=1', b'generation=18446744073709551616', 1),
                       FIXTURE.replace(b'\n', b'\r', 1),
                       FIXTURE.replace(b'kind=exec name=setup', b'kind=notify name=setup')):
            with self.subTest(serial=serial[-100:]):
                with self.assertRaises(ValueError): validate(serial)


if __name__ == '__main__': unittest.main()
