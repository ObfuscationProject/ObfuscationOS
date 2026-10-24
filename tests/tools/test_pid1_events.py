import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from pid1_events import validate


RECORDS = [
    b"PID1_EVENT kind=init pid=1 value=0",
    b"PID1_EVENT kind=launch pid=2 value=1",
    b"PID1_SERVICE_CRASH attempt=1 pid=2",
    b"PID1_EVENT kind=reap-service pid=2 value=10752",
    b"PID1_EVENT kind=launch pid=3 value=2",
    b"PID1_SERVICE_CRASH attempt=2 pid=3",
    b"PID1_EVENT kind=reap-service pid=3 value=10752",
    b"PID1_EVENT kind=launch pid=4 value=3",
    b"PID1_ORPHAN_PASS pid=6 ppid=1",
    b"PID1_EVENT kind=reap-other pid=6 value=4352",
    b"PID1_EVENT kind=shutdown pid=4 value=0",
    b"PID1_SERVICE_STOP attempt=3 pid=4",
    b"PID1_EVENT kind=reap-service pid=4 value=0",
    b"PID1_EVENT kind=stopped pid=1 value=0",
    b"PID1_NATIVE_PASS pid=1 restarts=2 other=1 shutdown=clean",
]


def serial(lines=RECORDS):
    return b"boot text\n" + b"\n".join(lines) + b"\nother boot text\n"


class Pid1EventsTest(unittest.TestCase):
    def test_complete_native_receipt(self):
        result = validate(serial())
        self.assertEqual(result["service_pids"], [2, 3, 4])
        self.assertEqual(result["orphan_pid"], 6)
        self.assertEqual(validate(serial().replace(b"\n", b"\r\n")), result)

    def test_rejects_forged_or_incomplete_receipts(self):
        mutations = [
            RECORDS[:-1],
            [*RECORDS, RECORDS[-1]],
            [*RECORDS[:9], b"PID1_EVENT kind=reap-other pid=7 value=4352", *RECORDS[10:]],
            [*RECORDS[:3], b"PID1_EVENT kind=reap-service pid=2 value=0", *RECORDS[4:]],
            [*RECORDS[:11], b"PID1_SERVICE_STOP attempt=3 pid=3", *RECORDS[12:]],
            [*RECORDS[:13], b"PID1_EVENT kind=stopped pid=1 value=1", *RECORDS[14:]],
            [*RECORDS[:8], b"shell> " + RECORDS[8], *RECORDS[9:]],
            [*RECORDS[:10], RECORDS[10], b"PID1_EVENT kind=force-stop pid=4 value=0", *RECORDS[11:]],
            [*RECORDS[:4], RECORDS[4], RECORDS[6], RECORDS[5], *RECORDS[7:]],
        ]
        for lines in mutations:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                validate(serial(lines))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate(serial() + b"PID1_EVENT kind=launch")


if __name__ == "__main__":
    unittest.main()
