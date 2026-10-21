"""macOS first-run boundaries, using synthetic archives and no account."""
import io
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

from core import ControlError
from connection_setup_macos import prepare_macos, unpack_reader


class MacSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, name="7zz", kind=tarfile.REGTYPE, size=5):
        path = self.root / "reader.tar.xz"
        with tarfile.open(path, "w:xz") as tar:
            entry = tarfile.TarInfo(name)
            entry.type = kind
            entry.size = size if kind == tarfile.REGTYPE else 0
            entry.linkname = "/outside"
            tar.addfile(entry, io.BytesIO(b"hello") if size == 5 and kind == tarfile.REGTYPE else None)
        return path

    def test_only_regular_reader_is_written_to_caller_selected_path(self):
        output = self.root / "reader"
        unpack_reader(self.archive(), output)
        self.assertEqual(output.read_bytes(), b"hello")

    def test_reader_links_and_traversal_are_rejected_without_extraction(self):
        for name, kind in (("../7zz", tarfile.REGTYPE), ("7zz", tarfile.SYMTYPE), ("7zz", tarfile.LNKTYPE)):
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                unpack_reader(self.archive(name, kind), self.root / "reader")
        self.assertFalse((self.root / "reader").exists())

    def test_cancel_before_download_leaves_no_identity_or_staging(self):
        cancelled = threading.Event()
        cancelled.set()
        with patch("connection_setup_macos.download") as transfer, patch("connection_setup_macos.subprocess.run") as execute:
            with self.assertRaisesRegex(ControlError, "annulée"):
                prepare_macos(self.root / "profile", cancel=cancelled)
        transfer.assert_not_called()
        execute.assert_not_called()
        self.assertFalse((self.root / "profile/private").exists())
        self.assertEqual(list((self.root / "profile/connection").iterdir()), [])

    def test_tampered_client_cannot_trigger_reader_execution(self):
        installer = self.root / "client.exe"
        installer.write_bytes(b"wrong")
        with patch("connection_setup_macos.download") as transfer, patch("connection_setup_macos.subprocess.run") as execute:
            with self.assertRaises(ControlError):
                prepare_macos(self.root / "profile", installer=installer)
        transfer.assert_not_called()
        execute.assert_not_called()
        self.assertFalse((self.root / "profile/private").exists())


if __name__ == "__main__":
    unittest.main()
