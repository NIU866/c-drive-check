import os
import tempfile
import threading
import unittest
from pathlib import Path

from scanner import scan


class ScannerTest(unittest.TestCase):
    def test_rollup_and_rank(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            (root / "资料" / "内层").mkdir(parents=True)
            (root / "资料" / "内层" / "large.bin").write_bytes(b"x" * 20)
            (root / "资料" / "small.txt").write_bytes(b"hello")
            (root / "root.bin").write_bytes(b"x" * 10)
            result = scan(path, threading.Event(), limit=2)
            self.assertEqual((result.files, result.size), (3, 35))
            self.assertEqual(result.folders[0], (25, str(root / "资料")))
            self.assertEqual([size for size, _ in result.largest], [20, 10])

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require Developer Mode")
    def test_link_and_cancel(self):
        with tempfile.TemporaryDirectory() as path:
            (Path(path) / "loop").symlink_to(path, target_is_directory=True)
            cancelled = threading.Event()
            result = scan(path, cancelled)
            self.assertEqual((result.files, result.skipped), (0, 1))
            cancelled.set()
            self.assertIsNone(scan(path, cancelled))


if __name__ == "__main__":
    unittest.main()
