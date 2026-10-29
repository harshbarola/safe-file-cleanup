
import unittest
import tempfile
from pathlib import Path
from cleanup import scan_folder


class TestCleanup(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_duplicate_files(self):
        (self.folder / "photo.jpg").write_bytes(b"same content")
        (self.folder / "photo_copy.jpg").write_bytes(b"same content")

        proposed = scan_folder(self.folder, 100)

        self.assertEqual(len(proposed), 1)

    def test_unique_files(self):
        (self.folder / "one.txt").write_text("hello")
        (self.folder / "two.txt").write_text("world")

        proposed = scan_folder(self.folder, 100)

        self.assertEqual(len(proposed), 0)

    def test_large_file(self):
        large_file = self.folder / "large.bin"
        large_file.write_bytes(b"x" * (2 * 1024 * 1024))

        scan_folder(self.folder, 1)

        self.assertTrue(large_file.exists())

        
    def test_quarantine_and_restore(self):
        from cleanup import quarantine_files, restore_session
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from io import StringIO
        import json

        (self.folder / "photo.jpg").write_bytes(b"same photo")
        (self.folder / "photo_copy.jpg").write_bytes(b"same photo")

        proposed = scan_folder(self.folder, 100)

        with patch("builtins.input", return_value="QUARANTINE"):
            with redirect_stdout(StringIO()):
                quarantine_files(self.folder, proposed)

        quarantine_root = self.folder / ".cleanup_quarantine"
        sessions = list(quarantine_root.glob("session_*"))
        self.assertEqual(len(sessions), 1)

        session = sessions[0]
        manifest = json.loads(
            (session / "manifest.json").read_text()
        )

        moved = next(
            item for item in manifest["files"]
            if item["status"] == "moved"
        )

        quarantined_file = Path(moved["quarantine_path"])
        original_path = Path(moved["original_path"])

        self.assertTrue(quarantined_file.exists())
        self.assertFalse(original_path.exists())

        with redirect_stdout(StringIO()):
            restore_session(session.name, quarantine_root)

        self.assertTrue(original_path.exists())
        self.assertFalse(quarantined_file.exists())
        self.assertEqual(original_path.read_bytes(), b"same photo")

    def test_restore_conflict(self):
        from cleanup import quarantine_files, restore_session
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from io import StringIO
        import json

        (self.folder / "photo.jpg").write_bytes(b"same photo")
        (self.folder / "photo_copy.jpg").write_bytes(b"same photo")

        proposed = scan_folder(self.folder, 100)

        with patch("builtins.input", return_value="QUARANTINE"):
            with redirect_stdout(StringIO()):
                quarantine_files(self.folder, proposed)

        quarantine_root = self.folder / ".cleanup_quarantine"
        session = next(quarantine_root.glob("session_*"))

        manifest = json.loads(
            (session / "manifest.json").read_text()
        )
        moved = next(
            item for item in manifest["files"]
            if item["status"] == "moved"
        )

        original_path = Path(moved["original_path"])
        quarantined_file = Path(moved["quarantine_path"])

        # Simulate a newer file appearing at the original location.
        original_path.write_bytes(b"newer content")

        output = StringIO()
        with redirect_stdout(output):
            restore_session(session.name, quarantine_root)

        self.assertEqual(original_path.read_bytes(), b"newer content")
        self.assertTrue(quarantined_file.exists())
        self.assertIn("RESTORE CONFLICT", output.getvalue())

    def test_invalid_manifest(self):
        from cleanup import restore_session
        from contextlib import redirect_stdout
        from io import StringIO

        quarantine_root = self.folder / ".cleanup_quarantine"
        session = quarantine_root / "session_001"
        session.mkdir(parents=True)

        (session / "manifest.json").write_text("{invalid json")

        output = StringIO()
        with redirect_stdout(output):
            restore_session("session_001", quarantine_root)

        self.assertIn("Could not read manifest", output.getvalue())
        



if __name__ == "__main__":
    unittest.main()
