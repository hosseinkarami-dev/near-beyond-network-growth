"""Tests for safe replacement of Raw and Normalized data files."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from atomic_io import atomic_write_bytes, atomic_write_text


class AtomicWriteTests(unittest.TestCase):
    def test_writes_bytes_and_text_to_nested_destinations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary_path = root / "raw" / "response.json"
            text_path = root / "normalized" / "summary.json"

            atomic_write_bytes(binary_path, b'{"raw":true}\n')
            atomic_write_text(text_path, '{"normalized":true}\n')

            self.assertEqual(binary_path.read_bytes(), b'{"raw":true}\n')
            self.assertEqual(text_path.read_text(encoding="utf-8"), '{"normalized":true}\n')

    def test_replace_failure_keeps_previous_file_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "daily.json"
            destination.write_bytes(b"previous complete data")

            with patch("atomic_io.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    atomic_write_bytes(destination, b"new data")

            self.assertEqual(destination.read_bytes(), b"previous complete data")
            self.assertEqual(list(root.glob(".daily.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
