"""Ensure an audit cannot mistake missing, mixed or foreign files for an install."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_installation import file_state, installation_state


class AuditTests(unittest.TestCase):
    def test_file_state_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "resource.bin"
            original = hashlib.sha256(b"original").hexdigest()
            patched = hashlib.sha256(b"patched").hexdigest()
            self.assertEqual(file_state(path, original, patched)["state"], "missing")
            self.assertFalse(path.exists())
            for data, state in [(b"original", "original"), (b"patched", "patched"), (b"another mod", "different")]:
                path.write_bytes(data)
                self.assertEqual(file_state(path, original, patched)["state"], state)
                self.assertEqual(path.read_bytes(), data)

    def test_installed_original_and_mixed_are_distinct(self):
        guard = {"patch_target": False, "state": "original"}
        a = {"patch_target": True, "state": "patched"}
        b = {"patch_target": True, "state": "original"}
        self.assertEqual(installation_state([guard, a, a]), "installed")
        self.assertEqual(installation_state([guard, b, b]), "original")
        self.assertEqual(installation_state([guard, a, b]), "mixed")

    def test_changed_executable_or_missing_target_is_not_verified(self):
        target = {"patch_target": True, "state": "patched"}
        self.assertEqual(installation_state([{"patch_target": False, "state": "different"}, target]), "unsupported_or_incomplete")
        self.assertEqual(installation_state([{"patch_target": False, "state": "original"},
                                             {"patch_target": True, "state": "missing"}]), "unsupported_or_incomplete")
        self.assertEqual(installation_state([]), "unsupported_or_incomplete")
        self.assertEqual(installation_state([target]), "unsupported_or_incomplete")


if __name__ == "__main__":
    unittest.main()
