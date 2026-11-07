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

    def test_hotplug_cycles_judge_the_probe_report(self):
        early = b'OK_SMP_HOTPLUG scope=hardware cycles=0 failures=0 cpu=3\r\n'
        middle = b'OK_SMP_HOTPLUG scope=hardware cycles=4 failures=0 cpu=3\r\n'
        final = b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=0 cpu=3\r\n'
        serial = early + middle + final
        reports = list(runner.HOTPLUG.finditer(serial))
        match = reports[-1]
        self.assertEqual(runner.hotplug_cycles(serial, match, 4),
                         {'cycles': 9, 'failures': 0, 'cpu': 3, 'probe_cycles': 9})
        # Against the last line before the probe: only later cycles count.
        self.assertEqual(runner.hotplug_cycles(serial, match, 4, reports[1])['probe_cycles'], 5)
        # Cycles that all happened before the probe started do not pass.
        with self.assertRaisesRegex(RuntimeError, 'during the probe'):
            runner.hotplug_cycles(early + middle, reports[1], 4, reports[1])
        stalled = early + middle + final + final
        stalled_reports = list(runner.HOTPLUG.finditer(stalled))
        with self.assertRaisesRegex(RuntimeError, 'during the probe'):
            runner.hotplug_cycles(stalled, stalled_reports[-1], 4, stalled_reports[2])
        rejected = (
            (early, early),
            (b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=1 cpu=3\n',) * 2,
            (b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=0 cpu=0\n',) * 2,
            (b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=0 cpu=4\n',) * 2,
            (final + middle, middle),
            (middle + b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=0 cpu=2\n',
             b'OK_SMP_HOTPLUG scope=hardware cycles=9 failures=0 cpu=2\n'),
        )
        for serial, last in rejected:
            with self.subTest(serial=serial):
                with self.assertRaises(RuntimeError):
                    runner.hotplug_cycles(serial, runner.HOTPLUG.fullmatch(last.rstrip(b'\r\n') + b'\n'), 4)

    def test_section_assertions_by_mode(self):
        def kernel(debug, shadow=0, **counters):
            values = dict.fromkeys(runner.KERNEL_FIELDS[:-1], 0)
            values.update(sections=40, completed=40, concurrent=3, witnessed=3, max_parallel=2)
            values.update(counters)
            fields = ' '.join('%s=%d' % item for item in values.items())
            line = ('OK_SMP_KERNEL scope=hardware debug=%d online=2 %s shadow=5/%d '
                    'cpu0=20:1:1:9:0 cpu1=20:2:2:9:0\n' % (debug, fields, shadow))
            return runner.kernel_sections(line.encode())
        families = dict.fromkeys(runner.FAMILY_NAMES, 100)
        runner.check_sections({}, kernel(1), families, 2, 10, 'debug')
        runner.check_sections({}, kernel(0), families, 2, 10, 'release')
        # A release kernel still counts these; each must be 0 there too.
        for name in runner.RELEASE_ASSERTS:
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, name):
                    runner.check_sections({}, kernel(0, **{name: 1}), families, 2, 10, 'release')
        with self.assertRaisesRegex(RuntimeError, 'shadow mismatches'):
            runner.check_sections({}, kernel(0, shadow=1), families, 2, 10, 'release')
        # Debug-only counters are checked in a debug kernel.
        with self.assertRaisesRegex(RuntimeError, 'purity_faults'):
            runner.check_sections({}, kernel(1, purity_faults=1), families, 2, 10, 'debug')
        # The kernel line's mode must be the requested one.
        with self.assertRaisesRegex(RuntimeError, 'debug=0 for a debug kernel'):
            runner.check_sections({}, kernel(0), families, 2, 10, 'debug')

    def test_hotplug_boot_line_must_pass(self):
        self.assertIsNone(runner.hotplug_boot(b'OK_SMP scope=hardware cpus=2 online=2\n'))
        good = b'OK_SMP_HOTPLUG_BOOT scope=hardware cpu=1 stop=pass parked_ipi=pass restart=pass ipi=pass\r\n'
        self.assertEqual(runner.hotplug_boot(b'x\n' + good),
                         'OK_SMP_HOTPLUG_BOOT scope=hardware cpu=1 stop=pass parked_ipi=pass restart=pass ipi=pass')
        for bad in (good.replace(b'restart=pass', b'restart=fail'), good.replace(b'ipi=pass\r', b'ipi=fail\r'),
                    good + good, good.replace(b' ipi=pass', b''), good.replace(b'cpu=1', b'cpu=2')):
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeError):
                    runner.hotplug_boot(bad)

    def test_result_line_must_be_complete(self):
        self.assertIsNone(runner.RESULT.search(b'SMP_STRESS_PASS arch=x86_64 workers=6'))
        match = runner.RESULT.search(b'SMP_STRESS_PASS arch=rv64 workers=6 rounds=40\r\n')
        self.assertEqual((match.group(1), match.group(2)), (b'PASS', b'rv64'))


if __name__ == '__main__':
    unittest.main()
