"""Offline failure must prevent native acceptance, even with valid serial evidence."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from qualify_service_graph import require_offline_success


class ServiceGraphCompletionTests(unittest.TestCase):
    def test_requires_completed_guest_and_offline_success(self):
        require_offline_success(dict(status='guest-passed-awaiting-offline', offline_fsck_passed=True))
        for record in ({}, {'status': 'guest-passed-awaiting-offline'},
                       {'status': 'running-final-fsck', 'offline_fsck_passed': True},
                       {'status': 'failed', 'offline_fsck_passed': True},
                       {'status': 'guest-passed-awaiting-offline', 'offline_fsck_passed': False},
                       {'status': 'guest-passed-awaiting-offline', 'offline_fsck_passed': 1},
                       {'status': 'guest-passed-awaiting-offline', 'offline_fsck_passed': True,
                        'offline_error': 'e2fsck failed'}):
            with self.subTest(record=record), self.assertRaises(ValueError): require_offline_success(record)


if __name__ == '__main__': unittest.main()
