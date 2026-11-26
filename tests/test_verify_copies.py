import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_copies import UnsupportedEntry, compare, hash_tree, write_manifest

quiet = lambda *a: None


class VerifyCopiesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def tree(self, name, files):
        root = self.base / name
        for rel, data in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        root.mkdir(exist_ok=True)
        return hash_tree(root, out=quiet)

    FILES = {"a.mkv": b"A" * 10, "_metadata/a.info.json": b"{}", "it's ⧸ b & c.mkv": b"B"}

    def test_identical_trees_no_problems(self):
        src = self.tree("hot", self.FILES)
        copies = {"cold": self.tree("cold", self.FILES), "colder": self.tree("colder", self.FILES)}
        self.assertEqual(compare(src, copies), [])

    def test_missing_on_one_copy_reported(self):
        src = self.tree("hot", self.FILES)
        partial = {k: v for k, v in self.FILES.items() if k != "a.mkv"}
        problems = compare(src, {"cold": self.tree("cold", self.FILES), "colder": self.tree("colder", partial)})
        self.assertTrue(problems)
        self.assertTrue(any("a.mkv" in p and "colder" in p for p in problems))

    def test_hash_mismatch_same_size_reported(self):
        src = self.tree("hot", self.FILES)
        bad = dict(self.FILES, **{"a.mkv": b"Z" * 10})
        problems = compare(src, {"cold": self.tree("cold", bad), "colder": self.tree("colder", self.FILES)})
        self.assertTrue(any("a.mkv" in p and "cold" in p for p in problems))

    def test_extra_file_on_both_copies_is_ok(self):
        src = self.tree("hot", self.FILES)
        extra = dict(self.FILES, **{"x.f251.webm": b"leftover"})
        self.assertEqual(compare(src, {"cold": self.tree("cold", extra), "colder": self.tree("colder", extra)}), [])

    def test_extra_file_on_only_one_copy_reported(self):
        src = self.tree("hot", self.FILES)
        extra = dict(self.FILES, **{"x.f251.webm": b"leftover"})
        problems = compare(src, {"cold": self.tree("cold", self.FILES), "colder": self.tree("colder", extra)})
        self.assertTrue(any("x.f251.webm" in p for p in problems))

    def test_manifest_is_sha256sum_compatible(self):
        tree = self.tree("hot", self.FILES)
        manifest = self.base / "hot.sha256"
        write_manifest(tree, manifest)
        result = subprocess.run(["sha256sum", "--strict", "-c", str(manifest)], cwd=self.base / "hot",
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unreadable_subdir_fails_instead_of_skipping(self):
        root = self.base / "hot"
        locked = root / "locked"
        locked.mkdir(parents=True)
        (locked / "only_on_hot.mkv").write_bytes(b"x")
        locked.chmod(0)
        try:
            with self.assertRaises(OSError):
                hash_tree(root, out=quiet)
        finally:
            locked.chmod(0o755)

    def test_symlink_in_tree_fails(self):
        root = self.base / "hot"
        root.mkdir()
        (root / "real.mkv").write_bytes(b"x")
        (root / "link.mkv").symlink_to(root / "real.mkv")
        with self.assertRaises(UnsupportedEntry):
            hash_tree(root, out=quiet)

    def test_empty_source_is_a_problem(self):
        self.assertTrue(compare({}, {"cold": {}, "colder": {}}))

    def test_expected_count_mismatch_is_a_problem(self):
        src = self.tree("hot", self.FILES)
        copies = {"cold": self.tree("cold", self.FILES)}
        self.assertEqual(compare(src, copies, expect_source_count=3), [])
        self.assertTrue(any("expected 338" in p for p in compare(src, copies, expect_source_count=338)))

    def test_cli_exit_codes(self):
        self.tree("hot", self.FILES)
        self.tree("cold", self.FILES)
        self.tree("colder", {"a.mkv": b"A" * 10})
        def run(*copies):
            return subprocess.run(
                [sys.executable, "verify_copies.py", "--source", str(self.base / "hot"),
                 *[a for c in copies for a in ("--copy", f"{c}={self.base / c}")],
                 "--manifest-dir", str(self.base / "manifests")],
                capture_output=True, text=True).returncode
        self.assertEqual(run("cold"), 0)
        self.assertEqual(run("cold", "colder"), 1)
        self.assertTrue((self.base / "manifests" / "source.sha256").exists())


if __name__ == "__main__":
    unittest.main()
