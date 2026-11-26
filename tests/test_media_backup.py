import subprocess
import tempfile
import unittest
from pathlib import Path

from backup import default_jobs
from media_backup import main
from renamer import RenameReport
from tests.helpers import HOST_249, make_layout, probe_with


class MainTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.events: list[str] = []
        self.printed: list[str] = []
        self.pictures = [self.base / "fake_pics_a", self.base / "fake_pics_b"]

    def tearDown(self):
        self._tmp.cleanup()

    def rename(self, directory):
        self.events.append(f"rename {directory.name}")
        return RenameReport()

    def runner(self, rc=0):
        def run(cmd, **kw):
            self.events.append("rsync")
            return subprocess.CompletedProcess(cmd, rc, "", "boom" if rc else "")
        return run

    def call(self, layout=None, down=frozenset(), rc=0):
        jobs = default_jobs(*make_layout(self.base, **(layout or {})))
        return main(picture_dirs=self.pictures, jobs=jobs, probe=probe_with(set(down)),
                    runner=self.runner(rc), ask=lambda p: self.fail("unexpected prompt"),
                    out=self.printed.append, rename=self.rename)

    def test_broken_chain_returns_1_and_never_renames(self):
        self.assertEqual(self.call(layout={"empty": ("hot/backup",)}), 1)
        self.assertEqual(self.events, [])

    def test_rename_runs_before_any_rsync(self):
        self.assertEqual(self.call(), 0)
        self.assertEqual(self.events[:2], ["rename fake_pics_a", "rename fake_pics_b"])
        self.assertEqual(set(self.events[2:]), {"rsync"})

    def test_colder_down_returns_0(self):
        self.assertEqual(self.call(down={HOST_249}), 0)
        text = "\n".join(self.printed)
        self.assertIn("192.168.1.249 is powered off, skipping primary hot -> colder", text)
        self.assertIn("192.168.1.249 is powered off, skipping advocate cold -> colder", text)

    def test_rsync_failure_returns_1(self):
        self.assertEqual(self.call(rc=23), 1)


if __name__ == "__main__":
    unittest.main()
