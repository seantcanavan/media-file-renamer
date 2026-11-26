import hashlib
import tempfile
import unittest
from pathlib import Path

from hashing import sha256_file
from renamer import format_timestamp, rename_files

TS = 1_700_000_000.0
PREFIX = format_timestamp(TS)
OLD = "2020-01-01_00-00-00"


def fixed_ts(_path):
    return TS


class RenamerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def names(self, rel="."):
        return sorted(p.name for p in (self.root / rel).iterdir())

    def test_renames_media_with_prefix_and_lowercase_ext(self):
        self.write("IMG_1.HEIC", b"x")
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertEqual(self.names(), [f"{PREFIX}_IMG_1.heic"])
        self.assertEqual(len(report.renamed), 1)

    def test_ignores_non_media_and_already_prefixed(self):
        self.write("notes.txt", b"x")
        self.write(f"{OLD}_IMG_2.jpg", b"y")
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertEqual(self.names(), [f"{OLD}_IMG_2.jpg", "notes.txt"])
        self.assertEqual(report.renamed, [])
        self.assertEqual(report.deleted_redumps, [])

    def test_redump_identical_is_deleted_and_original_kept(self):
        old = self.write(f"{OLD}_IMG_3.jpg", b"A" * 100)
        new = self.write("IMG_3.JPG", b"A" * 100)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertFalse(new.exists())
        self.assertEqual(old.read_bytes(), b"A" * 100)
        self.assertEqual(self.names(), [f"{OLD}_IMG_3.jpg"])
        self.assertEqual(report.deleted_redumps, [(new, old)])

    def test_same_name_same_size_different_content_keeps_both(self):
        old = self.write(f"{OLD}_IMG_4.aae", b"A" * 100)
        self.write("IMG_4.aae", b"B" * 100)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        renamed = self.root / f"{PREFIX}_IMG_4.aae"
        self.assertEqual(old.read_bytes(), b"A" * 100)
        self.assertEqual(renamed.read_bytes(), b"B" * 100)
        self.assertEqual(report.same_name_different_content, [renamed])
        self.assertEqual(report.deleted_redumps, [])

    def test_same_name_different_size_keeps_both(self):
        old = self.write(f"{OLD}_IMG_4.aae", b"A" * 100)
        self.write("IMG_4.aae", b"B" * 50)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        renamed = self.root / f"{PREFIX}_IMG_4.aae"
        self.assertEqual(old.read_bytes(), b"A" * 100)
        self.assertEqual(renamed.read_bytes(), b"B" * 50)
        self.assertEqual(report.same_name_different_content, [renamed])
        self.assertEqual(report.deleted_redumps, [])

    def test_target_exists_identical_deletes_new_only(self):
        target = self.write(f"{PREFIX}_IMG_5.jpg", b"X" * 10)
        new = self.write("IMG_5.jpg", b"X" * 10)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertFalse(new.exists())
        self.assertEqual(target.read_bytes(), b"X" * 10)
        self.assertEqual(report.deleted_redumps, [(new, target)])

    def test_target_exists_different_skips_and_leaves_both(self):
        # Target has a different original-name match too (it *is* that match),
        # so make it differ in content but not size.
        target = self.write(f"{PREFIX}_IMG_6.jpg", b"X" * 10)
        new = self.write("IMG_6.jpg", b"Y" * 10)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertEqual(target.read_bytes(), b"X" * 10)
        self.assertEqual(new.read_bytes(), b"Y" * 10)
        self.assertEqual(report.skipped_collisions, [(new, target)])
        self.assertEqual(report.deleted_redumps, [])

    def test_match_is_same_directory_only(self):
        self.write(f"sub_a/{OLD}_IMG_7.jpg", b"Z" * 10)
        self.write("sub_b/IMG_7.jpg", b"Z" * 10)
        report = rename_files(self.root, timestamp_of=fixed_ts)
        self.assertEqual(self.names("sub_b"), [f"{PREFIX}_IMG_7.jpg"])
        self.assertEqual(self.names("sub_a"), [f"{OLD}_IMG_7.jpg"])
        self.assertEqual(report.deleted_redumps, [])

    def test_rename_handles_unicode_and_spaces(self):
        name = "It＂s ⧸ a & b's.MOV"
        self.write(name, b"video")
        rename_files(self.root, timestamp_of=fixed_ts)
        renamed = self.root / f"{PREFIX}_It＂s ⧸ a & b's.mov"
        self.assertEqual(renamed.read_bytes(), b"video")

    def test_never_prompts(self):
        import builtins
        orig = builtins.input
        builtins.input = lambda *a: self.fail("input() called")
        try:
            self.write(f"{PREFIX}_IMG_8.jpg", b"X" * 10)
            self.write("IMG_8.jpg", b"Y" * 10)
            rename_files(self.root, timestamp_of=fixed_ts)
        finally:
            builtins.input = orig

    def test_sha256_file_matches_hashlib(self):
        data = bytes(range(256)) * (20 * 1024 * 1024 // 256 + 3)
        p = self.write("big.bin", data)
        self.assertEqual(sha256_file(p), hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
