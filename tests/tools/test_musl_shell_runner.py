import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("musl_shell_runner", ROOT / "scripts/test_musl_shell.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class SuiteJudgementTests(unittest.TestCase):
    SERIAL = (b"PASS: cat-prints-a-file\r\nFAIL: touch-creates-file\nSKIPPED: tar (not built)\n"
              b"UNTESTED: cpio-extracts-zero-length-hardlinks\nPASS: sed s///g\n")

    def test_parses_runtest_lines(self):
        self.assertEqual(runner.suite_results(self.SERIAL), {
            "cat-prints-a-file": "PASS", "touch-creates-file": "FAIL", "tar (not built)": "SKIPPED",
            "cpio-extracts-zero-length-hardlinks": "UNTESTED", "sed s///g": "PASS"})

    def test_kernel_failure_line(self):
        serial = b"oksh> \r\nOK_TEST_FAIL native-runtime=private MIPS handler resume unverified\r\nmore\n"
        self.assertEqual(runner.kernel_failure(serial), "OK_TEST_FAIL native-runtime=private MIPS handler resume unverified")
        self.assertIsNone(runner.kernel_failure(b"OK_TEST_PASS arch=mips\n"))

    def test_unlisted_failure_fails_the_gate(self):
        verdict = runner.judge_suite(runner.suite_results(self.SERIAL), {})
        self.assertEqual(verdict["status"], "fail")
        self.assertEqual(verdict["unexpected_failures"], ["touch-creates-file"])
        self.assertEqual(verdict["passed"], 2)

    def test_reviewed_failures_pass_and_stale_entries_fail(self):
        results = runner.suite_results(self.SERIAL)
        self.assertEqual(runner.judge_suite(results, {"touch-creates-file": "utimensat"})["status"], "pass")
        stale = runner.judge_suite(results, {"touch-creates-file": "utimensat", "sed s///g": "old"})
        self.assertEqual((stale["status"], stale["expected_failures_now_passing"]), ("fail", ["sed s///g"]))
        self.assertEqual(runner.judge_suite({}, {})["status"], "fail")

    def test_suite_plan_needs_applets_and_causes(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "plan"
            path.write_text("# comment\napplets echo cut\ntouch-creates-file\tutimensat is not routed\n")
            self.assertEqual(runner.suite_plan(path), (["echo", "cut"], {"touch-creates-file": "utimensat is not routed"}))
            for bad in ("applets echo\ntouch-creates-file\n", "applets echo\na\tx\na\ty\n", "applets echo\n\treason\n",
                        "a\tx\n", "applets a\napplets b\n"):
                path.write_text(bad)
                with self.assertRaises(ValueError, msg=bad):
                    runner.suite_plan(path)

    def test_repository_gate_plan_is_well_formed(self):
        applets, expected = runner.suite_plan(ROOT / "ports/busybox/testsuite-gate.txt")
        selected = {line.split("=")[0][7:].lower() for line in (ROOT / "ports/busybox/busybox.config").read_text().splitlines()
                    if line.startswith("CONFIG_") and line.endswith("=y")}
        self.assertTrue(set(applets) <= selected, set(applets) - selected)
        self.assertTrue(all(expected.values()))

if __name__ == "__main__":
    unittest.main()
