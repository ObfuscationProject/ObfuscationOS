"""ABI draft admission from a pinned model fixture; no native ABI qualification."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

OS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(OS_ROOT / 'tools'))
from build_linux_abi_draft import build


class LinuxAbiDraftTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.ledger = json.loads((OS_ROOT / 'docs/plans/contracts/ledger.json').read_text())
        self.model = json.loads((OS_ROOT / 'tests/fixtures/linux_abi_model.json').read_text())

    def generate(self):
        ledger = self.directory / 'ledger.json'
        model = self.directory / 'model.json'
        ledger.write_text(json.dumps(self.ledger))
        # Preserve original bytes in the clean case to retain the source hash.
        original = OS_ROOT / 'tests/fixtures/linux_abi_model.json'
        if json.loads(original.read_text()) == self.model:
            model.write_bytes(original.read_bytes())
        else:
            model.write_text(json.dumps(self.model))
        return build(model, ledger)

    def test_clean_draft_preserves_exact_ten_profiles_and_output(self):
        result = self.generate()
        expected = json.loads((OS_ROOT / 'docs/plans/contracts/drafts/linux_abi_bootstrap.json').read_text())
        self.assertEqual(result, expected)
        self.assertEqual(len(result['architectures']), 10)

    def test_identical_os_duplicate_is_rejected_in_either_position(self):
        baseline = copy.deepcopy(self.ledger)
        for position in (0, len(baseline['architectures'])):
            with self.subTest(position=position):
                self.ledger = copy.deepcopy(baseline)
                self.ledger['architectures'].insert(position, copy.deepcopy(baseline['architectures'][0]))
                with self.assertRaisesRegex(ValueError, 'OS ledger repeats an architecture profile'):
                    self.generate()

    def test_conflicting_os_duplicate_cannot_change_selected_linux_target(self):
        baseline = copy.deepcopy(self.ledger)
        for position in (0, len(baseline['architectures'])):
            with self.subTest(position=position):
                self.ledger = copy.deepcopy(baseline)
                duplicate = copy.deepcopy(next(row for row in baseline['architectures'] if row['id'] == 'i386'))
                duplicate['linux_target'] = 'foreign-target-from-duplicate'
                self.ledger['architectures'].insert(position, duplicate)
                with self.assertRaisesRegex(ValueError, 'OS ledger repeats an architecture profile'):
                    self.generate()

    def test_kernel_duplicate_remains_rejected(self):
        self.model['profiles'].append(copy.deepcopy(self.model['profiles'][0]))
        with self.assertRaisesRegex(ValueError, 'bootstrap manifest repeats an architecture profile'):
            self.generate()

    def test_missing_os_profile_remains_rejected(self):
        self.ledger['architectures'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly all ten profiles'):
            self.generate()


if __name__ == '__main__':
    unittest.main()
