"""Synthetic OK_SMP_CPUS controls for scripts/test_smp_stress.py; no guest starts."""
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.append(str(SCRIPTS))
spec = importlib.util.spec_from_file_location('smp_stress_runner', SCRIPTS / 'test_smp_stress.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class SmpStressRunnerTests(unittest.TestCase):
    def test_counters_are_read_per_cpu(self):
        line = b'OK_SMP_CPUS scope=hardware online=2 cpu0=10:20:3:4:5 cpu1=7:8:9:1:0\r\n'
        self.assertEqual(runner.cpu_counters(line), {0: (10, 20, 3, 4, 5), 1: (7, 8, 9, 1, 0)})
        with self.assertRaises(RuntimeError):
            runner.cpu_counters(b'OK_SMP_CPUS scope=hardware online=3 cpu0=1:0:0:0:0 cpu1=1:0:0:0:0\n')

    def test_every_online_cpu_must_enter_user_code_during_the_probe(self):
        line = b'OK_SMP_CPUS scope=hardware online=2 cpu0=10:0:0:0:0 cpu1=4:0:0:0:0\n'
        self.assertEqual(runner.probe_entries(line, None, 2)[1], {0: 10, 1: 4})
        self.assertEqual(runner.probe_entries(line, {0: (6, 0, 0, 0, 0), 1: (1, 0, 0, 0, 0)}, 2)[1], {0: 4, 1: 3})
        # A CPU that entered user code only before the probe does not count.
        with self.assertRaisesRegex(RuntimeError, 'CPU 1'):
            runner.probe_entries(line, {0: (6, 0, 0, 0, 0), 1: (4, 0, 0, 0, 0)}, 2)
        with self.assertRaisesRegex(RuntimeError, 'CPU 1'):
            runner.probe_entries(b'OK_SMP_CPUS scope=hardware online=2 cpu0=3:0:0:0:0 cpu1=0:9:9:9:0\n', None, 2)
        # The report must name exactly CPUs 0..online-1.
        with self.assertRaisesRegex(RuntimeError, 'name CPUs'):
            runner.probe_entries(line, None, 3)
        with self.assertRaisesRegex(RuntimeError, 'name CPUs'):
            runner.probe_entries(b'OK_SMP_CPUS scope=hardware online=2 cpu0=3:0:0:0:0 cpu2=3:0:0:0:0\n', None, 2)

    def test_result_line_must_be_complete(self):
        self.assertIsNone(runner.RESULT.search(b'SMP_STRESS_PASS arch=x86_64 workers=6'))
        match = runner.RESULT.search(b'SMP_STRESS_PASS arch=rv64 workers=6 rounds=40\r\n')
        self.assertEqual((match.group(1), match.group(2)), (b'PASS', b'rv64'))


if __name__ == '__main__':
    unittest.main()
