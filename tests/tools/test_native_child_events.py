"""Hermetic checks of owned waits and strict, lossless transcript framing."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from native_child_events import native_events, scan, normalize_transcript, boot_baseline


def wait(pid=1, tid=1, request=4, ticket=None, selector=2, output=0x40001000,
         format='status', outcome='arm', result=-11, live=1):
    return (f'OK_NATIVE_CHILD_WAIT pid={pid} tid={tid} request={request} '
            f'wait={request if ticket is None else ticket} selector={selector} '
            f'output={output} format={format} outcome={outcome} '
            f'result={result} live={live}\n').encode()


class ChildLedgerTests(unittest.TestCase):
    def test_exact_baseline_and_rearm(self):
        baseline = boot_baseline(wait(), required=True)
        trace = (wait(pid=3, tid=4, selector=5, live=2) +
                 wait(pid=3, tid=4, selector=5, ticket=7, outcome='rearm', live=2) +
                 wait(pid=3, tid=4, selector=5, ticket=7, outcome='complete', result=5))
        rows = native_events(trace, baseline=baseline)
        self.assertIs(rows[-1]['arm'], rows[1])
        self.assertIs(rows[1]['previous'], rows[0])
        self.assertEqual(scan(trace, baseline=baseline)[1], baseline)
        for field, old, new in [('ticket', b'wait=7', b'wait=6'),
                                ('selector', b'selector=5', b'selector=6'),
                                ('output', b'output=1073745920', b'output=0'),
                                ('owner', b'tid=4', b'tid=5')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                native_events(trace[:-len(rows[-1]['line'])-1] +
                              rows[-1]['line'].replace(old, new) + b'\n', baseline=baseline)

    def test_baseline_cannot_be_lost_or_replaced(self):
        baseline = boot_baseline(wait(), required=True)
        retire = wait(outcome='complete', result=2, live=0)
        image = b'OK_NATIVE_IMAGE pid=9 replaced=1\n'
        for trace in (retire, retire + wait(), retire + wait(request=5),
                      retire + image + wait(), image + retire + image + wait()):
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                native_events(trace, baseline=baseline)

    def test_terminal_results_and_fresh_tickets(self):
        arm = wait()
        for result in (1, 3, 0, -4, -11, -125):
            with self.subTest(result=result), self.assertRaises(ValueError):
                native_events(arm + wait(outcome='complete', result=result, live=0))
        for result in (2, -3, -10, -14):
            self.assertEqual(len(native_events(arm + wait(outcome='complete', result=result, live=0))), 2)
        done = wait(outcome='complete', result=2, live=0)
        with self.assertRaises(ValueError):
            native_events(arm + done + arm + done)
        self.assertEqual(len(native_events(arm + done +
                            b'OK_NATIVE_IMAGE pid=1 replaced=1\n' + arm + done)), 4)
        self.assertEqual(len(native_events(wait(selector=0xffffffff) +
                            wait(selector=0xffffffff, outcome='complete', result=9, live=0))), 2)

    def test_exact_signal_publication_and_odd_x86_pc(self):
        for restart in (False, True):
            terminal = wait(outcome='interrupted', result=0 if restart else -4, live=0)
            signal = (b'OK_NATIVE_CHILD_SIGNAL pid=1 tid=1 request=4 wait=4 origin=9 '
                      b'signal=10 outcome=' + (b'restart' if restart else b'eintr') +
                      b' pc=1073742255 selector=2 output=1073745920 live=0\n')
            trace = wait() + terminal + signal
            self.assertEqual(len(native_events(trace, allow_signal=True)), 3)
            for bad in (trace.replace(b'origin=9', b'origin=0'),
                        trace.replace(b'pc=1073742255', b'pc=0'),
                        trace.replace(b'signal=10', b'signal=11'),
                        wait() + signal + terminal,
                        wait() + terminal,
                        trace.replace(terminal, terminal + b'unexpected\n')):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    native_events(bad, allow_signal=True)
            with self.assertRaises(ValueError):
                native_events(trace)

    def test_owned_cancellation_and_output_format(self):
        rows = native_events(wait(format='siginfo') +
                             wait(format='siginfo', outcome='cancelled', result=-125, live=0))
        self.assertEqual(rows[-1]['result'], -125)
        for trace in (wait(format='siginfo', output=0),
                      wait() + wait(outcome='cancelled', result=-4, live=0),
                      wait(live=2), b'junk' + wait(), wait()[:-1] + b' junk\n'):
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                native_events(trace)

    def test_explicit_boot_profiles(self):
        self.assertEqual(boot_baseline(b'legacy boot\n'), {})
        for boot in (b'', wait(selector=0xffffffff), wait(tid=3),
                     wait() + wait(pid=3, tid=3, selector=4, live=2)):
            with self.subTest(boot=boot), self.assertRaises(ValueError):
                boot_baseline(boot, required=True)

    def test_framing_preserves_records_and_recalculates_offsets(self):
        banner = b'hello from ObfuscationOS userland'
        parts = [banner + wait() + b'oksh> '] + [b'command\noksh> '] * 4
        raw = b''.join(parts)
        offsets = [sum(map(len, parts[:i])) for i in range(1, 5)]
        clean, bounds = normalize_transcript(raw, (*offsets, offsets[-1]))
        self.assertEqual(clean, raw.replace(banner, banner + b'\n', 1))
        self.assertEqual(bounds, tuple(x + 1 for x in (*offsets, offsets[-1])))
        self.assertEqual(scan(clean)[1], scan(wait())[1])
        for replacement in (wait().replace(b' live=1', b' live=bad'), wait().rstrip()):
            badparts = [banner + replacement + b'oksh> '] + parts[1:]
            bad = b''.join(badparts)
            offsets = [sum(map(len, badparts[:i])) for i in range(1, 5)]
            with self.assertRaises(ValueError):
                normalize_transcript(bad, (*offsets, offsets[-1]))


if __name__ == '__main__':
    unittest.main()
