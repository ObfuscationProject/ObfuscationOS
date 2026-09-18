"""QMP framing, timeout and termination checks without launching a VM."""
import importlib.util
import io
import os
from pathlib import Path
import sys
import time
import unittest

gui_tests = Path(__file__).resolve().parents[1] / "gui"
sys.path.insert(0, str(gui_tests))
spec = importlib.util.spec_from_file_location("capture_qemu", gui_tests / "capture_qemu.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class QmpConnectionTests(unittest.TestCase):
    def setUp(self):
        read_fd, self.write_fd = os.pipe()
        self.reader = os.fdopen(read_fd, "rb", buffering=0)
        self.requests = io.BytesIO()
        self.qmp = capture.QmpConnection(self.reader, self.requests, timeout=0.05)

    def tearDown(self):
        self.reader.close()
        if self.write_fd is not None:
            os.close(self.write_fd)

    def test_greeting_and_event_and_reply_in_one_chunk(self):
        os.write(self.write_fd, b'{"QMP": {}}\r\n{"event": "STOP"}\r\n{"return": {}}\r\n')
        self.qmp.greeting()
        self.assertEqual(self.qmp.execute("qmp_capabilities"), {"return": {}})
        self.assertIn(b'"execute": "qmp_capabilities"', self.requests.getvalue())

    def test_partial_json_without_newline_times_out(self):
        os.write(self.write_fd, b'{"return":')
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "QMP response timed out"):
            self.qmp.execute("query-status")
        self.assertLess(time.monotonic() - started, 1.0)

    def test_greeting_without_data_times_out(self):
        with self.assertRaisesRegex(TimeoutError, "QMP response timed out"):
            self.qmp.greeting()

    def test_eof_reports_incomplete_reply(self):
        os.write(self.write_fd, b'{"return":')
        os.close(self.write_fd)
        self.write_fd = None
        with self.assertRaisesRegex(RuntimeError, "closed before a complete response"):
            self.qmp.execute("query-status")

    def test_qmp_error_is_reported(self):
        os.write(self.write_fd, b'{"error": {"class": "CommandNotFound"}}\n')
        with self.assertRaisesRegex(RuntimeError, "CommandNotFound"):
            self.qmp.execute("missing-command")

    def test_events_do_not_extend_command_deadline(self):
        deadlines = []

        def events(deadline):
            deadlines.append(deadline)
            if len(deadlines) == 3:
                raise TimeoutError("QMP response timed out")
            return {"event": "STOP"}

        self.qmp.receive = events
        with self.assertRaises(TimeoutError):
            self.qmp.execute("query-status")
        self.assertEqual(len(set(deadlines)), 1)


if __name__ == "__main__":
    unittest.main()
