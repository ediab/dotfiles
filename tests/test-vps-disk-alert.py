"""Run with python3 tests/test-vps-disk-alert.py."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("disk_alert", Path(__file__).resolve().parents[1] / "config/vps/vps-disk-alert.py")
alert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alert)


class DiskAlertTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(alert.severity(79, 10 * alert.GIB), 0)
        self.assertEqual(alert.severity(80, 10 * alert.GIB), 1)
        self.assertEqual(alert.severity(90, 10 * alert.GIB), 2)
        self.assertEqual(alert.severity(70, 4 * alert.GIB), 2)
        self.assertEqual(alert.severity(70, 5 * alert.GIB), 0)

    def test_transitions_reminders_and_recovery(self):
        self.assertTrue(alert.notification(1, {}, 100))
        state = {"level": 1, "sent_at": 100}
        self.assertFalse(alert.notification(1, state, 200))
        self.assertTrue(alert.notification(1, state, 86500))
        self.assertTrue(alert.notification(2, state, 200))
        self.assertTrue(alert.notification(0, state, 200))
        self.assertFalse(alert.notification(0, {"level": 0}, 200))


if __name__ == "__main__":
    unittest.main()
