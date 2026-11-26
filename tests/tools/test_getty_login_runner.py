"""Scripted serial transcripts for the checks in scripts/test_getty_login.py; no guest starts.

Each send() appends the guest's scripted answer, so offsets behave as they do
over a live serial line. The transcripts are synthetic: these tests show what
the lane's checks accept and refuse, not that the guest behaves that way.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.append(str(SCRIPTS))
spec = importlib.util.spec_from_file_location('getty_login_runner', SCRIPTS / 'test_getty_login.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

# The pts ends its lines with CR CR LF (ONLCR plus the serial CR).
HOLD_LINE = b'oksh-jobs hold 600 || echo hold-interrupted'


def pts(text: bytes) -> bytes:
    return text.replace(b'\n', b'\r\r\n')


class ScriptedGuest(runner.Guest):
    """Serial output that arrives in answer to each send, in order."""

    def __init__(self, log: Path, initial: bytes, answers: list):
        self.log, self.timeout = log, 0.5
        self.data = bytearray(initial)
        self.started = time.monotonic()
        self.answers = list(answers)
        self.sent: list[bytes] = []

    def read(self, deadline: float, what: str) -> None:
        if time.monotonic() > deadline:
            raise runner.Failure(f'no {what} after {len(self.data)} bytes')
        time.sleep(0.01)

    def send(self, line: bytes, newline: bool = True) -> int:
        offset = len(self.data)
        self.sent.append(line)
        if not self.answers:
            raise AssertionError(f'unscripted input {line!r}')
        self.data.extend(self.answers.pop(0))
        return offset

    def save(self) -> None:
        pass


class GettyLoginRunnerTests(unittest.TestCase):
    def session(self, answers: list, initial: bytes = b'oksh> ') -> runner.Session:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        guest = ScriptedGuest(Path(directory.name) / 'serial.log', initial, answers)
        return runner.Session(guest, [], 1, 1)

    def interrupt_answers(self, branch: bytes) -> list:
        return [
            pts(HOLD_LINE + b'\n')
            + b'OK_NATIVE_CHILD_WAIT pid=60 outcome=arm\r\n'
            + pts(b'OKSH_JOBS hold pid=71 pgrp=71 tty_pgrp=71 seconds=600\n'),
            b'^C' + pts(branch + b'\n') + b'oksh> ',
            pts(b'jobs\n\n') + b'oksh> ',
        ]

    def test_interrupt_accepts_the_branch_output_after_the_echo(self):
        session = self.session(self.interrupt_answers(b'hold-interrupted'))
        session.interrupt(0)
        self.assertEqual(session.steps[-1]['step'], 'interrupt')
        self.assertEqual(session.steps[-1]['job'], 71)

    def test_interrupt_refuses_a_skipped_branch_that_only_the_echo_names(self):
        # The echoed command line holds "hold-interrupted\n" by itself.
        session = self.session(self.interrupt_answers(b''))
        with self.assertRaisesRegex(runner.Failure, r'\^C did not end the foreground job'):
            session.interrupt(0)

    def test_interrupt_refuses_branch_output_before_the_interrupt(self):
        session = self.session(self.interrupt_answers(b''))
        session.guest.answers[1] = pts(b'hold-interrupted\n') + b'^C' + pts(b'\n') + b'oksh> '
        with self.assertRaisesRegex(runner.Failure, r'\^C did not end the foreground job'):
            session.interrupt(0)

    def job_control_answers(self, branch: bytes) -> list:
        stopped = b'[1]+ Stopped oksh-jobs hold 600\n'
        return [
            pts(HOLD_LINE.split(b' ||')[0] + b'\nOKSH_JOBS hold pid=72 pgrp=72 tty_pgrp=72 seconds=600\n'),
            b'^Z' + pts(stopped) + b'oksh> ',
            pts(b'jobs\n' + stopped) + b'oksh> ',
            pts(b'exit\noksh: there are stopped jobs\n') + b'oksh> ',
            pts(b'fg || echo fg-interrupted\noksh-jobs hold 600\n'),
            b'^C' + pts(branch + b'\n') + b'oksh> ',
            pts(b'jobs\n') + b'oksh> ',
        ]

    def test_resumed_job_accepts_the_branch_output_after_the_echo(self):
        session = self.session(self.job_control_answers(b'fg-interrupted'))
        session.job_control(0)
        self.assertEqual(session.steps[-1]['step'], 'stop-jobs-fg')

    def test_resumed_job_refuses_a_skipped_branch_that_only_the_echo_names(self):
        session = self.session(self.job_control_answers(b''))
        with self.assertRaisesRegex(runner.Failure, r'\^C did not end the resumed job'):
            session.job_control(0)

    def stopped_logout_answers(self, new_pts: int) -> list:
        stopped = b'[1]+ Stopped oksh-jobs hold 600\n'
        pid1 = b'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event=%s service=console pid=%d ' \
               b'generation=%d time_ms=1 next_ms=0 errno=0 status=0\r\n'
        return [
            pts(b'oksh-jobs hold 600\nOKSH_JOBS hold pid=73 pgrp=73 tty_pgrp=73 seconds=600\n'),
            b'^Z' + pts(stopped) + b'oksh> ',
            pts(b'jobs\n' + stopped) + b'oksh> ',
            pts(b'exit\noksh: there are stopped jobs\n') + b'oksh> ',
            pts(b'exit\n') + b'GETTY event=close pts=0 pid=60 status=256 reason=exit\r\n'
            + pid1 % (b'reap', 58, 1) + pid1 % (b'launch', 74, 2)
            + b'GETTY event=open pts=%d pid=75\r\n' % new_pts,
        ]

    def test_stopped_job_logout_reuses_the_released_pts(self):
        session = self.session(self.stopped_logout_answers(0))
        self.assertEqual(session.logout(0, 60, 0, stopped_job=True)[:2], (0, 75))
        self.assertEqual(session.hung_up, 73)

    def test_stopped_job_logout_refuses_a_session_on_another_pts(self):
        # The old pair is gone from /dev/pts once getty closes the master,
        # so only the new index shows a slave still held open.
        session = self.session(self.stopped_logout_answers(1))
        with self.assertRaisesRegex(runner.Failure, r'got pts 1, not the released pts 0'):
            session.logout(0, 60, 0, stopped_job=True)

    def alive_answers(self, shell: int, job: int) -> list:
        return [pts(b'oksh-jobs alive %d\nOKSH_JOBS alive pid=%d alive=%d\n' % (pid, pid, alive)) + b'oksh> '
                for pid, alive in ((74, shell), (73, job))]

    def test_hung_up_job_must_be_gone_in_the_next_session(self):
        session = self.session(self.alive_answers(1, 0))
        session.gone(73, 74, 0)
        self.assertEqual((session.steps[-1]['step'], session.steps[-1]['job']), ('stopped-job-gone', 73))
        with self.assertRaisesRegex(runner.Failure, r'job 73 stopped at logout survived'):
            self.session(self.alive_answers(1, 1)).gone(73, 74, 0)

    def test_alive_probe_must_see_the_session_shell(self):
        with self.assertRaisesRegex(runner.Failure, r'does not see the session'):
            self.session(self.alive_answers(0, 0)).gone(73, 74, 0)

if __name__ == '__main__':
    unittest.main()
