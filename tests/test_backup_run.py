import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backup import (
    APPROVAL_PHRASE,
    BrokenChain,
    DeletionNotApproved,
    Job,
    RsyncFailed,
    build_rsync_command,
    default_jobs,
    run_backups,
    run_job,
)
from tests.helpers import HOST_248, HOST_249, make_layout, probe_with

JOB = Job("t", Path("/src"), Path("/dst"), HOST_248, HOST_248)


class FakeRunner:
    """Records argv lists; replies from a script of (returncode, stdout) tuples."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        rc, out = self.replies.pop(0) if self.replies else (0, "")
        return subprocess.CompletedProcess(cmd, rc, out, "boom" if rc else "")


def asker(*answers):
    answers = list(answers)
    calls = []

    def ask(prompt):
        calls.append(prompt)
        a = answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a

    ask.calls = calls
    return ask


def no_ask(prompt):
    raise AssertionError("ask() must not be called")


quiet = lambda *a: None


class BuildCommandTest(unittest.TestCase):
    def test_build_command_is_argv_with_trailing_slashes(self):
        job = Job("t", Path("/a/b c & d⧸e"), Path("/x/it's"), HOST_248, HOST_249)
        self.assertEqual(build_rsync_command(job, dry_run=False),
                         ["rsync", "-Prv", "--size-only", "--delete-during", "/a/b c & d⧸e/", "/x/it's/"])
        dry = build_rsync_command(job, dry_run=True)
        self.assertEqual(dry[-1], "--dry-run")
        self.assertEqual(dry[:-1], build_rsync_command(job, dry_run=False))


class MaxDeleteTest(unittest.TestCase):
    def test_real_run_capped_at_zero_when_dry_run_shows_no_deletions(self):
        runner = FakeRunner((0, "new.jpg\n"), (0, ""))
        run_job(JOB, runner=runner, ask=no_ask, out=quiet)
        self.assertNotIn("--max-delete=0", runner.calls[0])
        self.assertEqual(runner.calls[1], build_rsync_command(JOB, dry_run=False, max_delete=0))
        self.assertIn("--max-delete=0", runner.calls[1])

    def test_real_run_capped_at_approved_deletion_count(self):
        runner = FakeRunner((0, "deleting a.jpg\ndeleting old/b.jpg\ndeleting old/\nkept.jpg\n"), (0, ""))
        run_job(JOB, runner=runner, ask=asker(APPROVAL_PHRASE), out=quiet)
        self.assertIn("--max-delete=3", runner.calls[1])
        self.assertFalse([a for a in runner.calls[0] if a.startswith("--max-delete")])

    def test_exceeding_max_delete_rc25_raises(self):
        runner = FakeRunner((0, ""), (25, ""))
        with self.assertRaises(RsyncFailed) as ctx:
            run_job(JOB, runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(ctx.exception.returncode, 25)


@unittest.skipUnless(shutil.which("rsync"), "rsync not installed")
class RealRsyncMaxDeleteTest(unittest.TestCase):
    """Real rsync on temp dirs: the dry run's 'deleting' count must be exactly
    what --max-delete counts, including nested directories."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.src, self.dst = base / "src", base / "dst"
        self.src.mkdir()
        (self.src / "keep.jpg").write_bytes(b"k")
        self.dst.mkdir()
        (self.dst / "keep.jpg").write_bytes(b"k")
        (self.dst / "gone.jpg").write_bytes(b"g")
        (self.dst / "old" / "sub").mkdir(parents=True)
        (self.dst / "old" / "a.jpg").write_bytes(b"a")
        (self.dst / "old" / "sub" / "b.jpg").write_bytes(b"b")
        self.job = Job("real", self.src, self.dst, HOST_248, HOST_248)

    def tearDown(self):
        self._tmp.cleanup()

    def silent_runner(self, cmd, **kw):
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        return subprocess.run(cmd, **kw)

    def test_approved_count_deletes_everything_shown(self):
        run_job(self.job, runner=self.silent_runner, ask=asker(APPROVAL_PHRASE), out=quiet)
        self.assertEqual(sorted(p.name for p in self.dst.rglob("*")), ["keep.jpg"])

    def test_one_extra_deletion_is_refused_with_rc25(self):
        # Approve the dry run, then a new extraneous file appears before the real run.
        def ask(prompt):
            (self.dst / "appeared_later.jpg").write_bytes(b"x")
            return APPROVAL_PHRASE

        with self.assertRaises(RsyncFailed) as ctx:
            run_job(self.job, runner=self.silent_runner, ask=ask, out=quiet)
        self.assertEqual(ctx.exception.returncode, 25)
        remaining = sorted(p.relative_to(self.dst).as_posix() for p in self.dst.rglob("*"))
        self.assertEqual(len(remaining), 2)  # keep.jpg + exactly one survivor


class RunJobTest(unittest.TestCase):
    def test_run_job_no_deletions_runs_dry_then_real(self):
        runner = FakeRunner((0, "sending incremental file list\nnew.jpg\n"), (0, ""))
        run_job(JOB, runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(len(runner.calls), 2)
        self.assertIn("--dry-run", runner.calls[0])
        self.assertNotIn("--dry-run", runner.calls[1])

    def test_run_job_deletions_require_exact_phrase(self):
        runner = FakeRunner((0, "deleting old.jpg\n"), (0, ""))
        ask = asker("yes", APPROVAL_PHRASE)
        run_job(JOB, runner=runner, ask=ask, out=quiet)
        self.assertEqual(len(ask.calls), 2)
        self.assertEqual(len(runner.calls), 2)
        self.assertNotIn("--dry-run", runner.calls[1])

    def test_run_job_eof_at_prompt_aborts_without_real_run(self):
        runner = FakeRunner((0, "deleting old.jpg\n"))
        with self.assertRaises(DeletionNotApproved):
            run_job(JOB, runner=runner, ask=asker(EOFError()), out=quiet)
        self.assertEqual(len(runner.calls), 1)

    def test_run_job_dry_run_failure_raises_and_skips_real(self):
        runner = FakeRunner((23, ""))
        with self.assertRaises(RsyncFailed) as ctx:
            run_job(JOB, runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(ctx.exception.returncode, 23)
        self.assertEqual(len(runner.calls), 1)

    def test_run_job_real_run_failure_raises(self):
        runner = FakeRunner((0, ""), (12, ""))
        with self.assertRaises(RsyncFailed) as ctx:
            run_job(JOB, runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(ctx.exception.returncode, 12)


class RunBackupsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hot, self.cold, self.colder = make_layout(Path(self._tmp.name))
        self.jobs = default_jobs(self.hot, self.cold, self.colder)

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_backups_prints_skips_and_runs_only_runnable(self):
        runner = FakeRunner()
        printed = []
        run_backups(self.jobs, probe=probe_with({HOST_249}), runner=runner, ask=no_ask, out=printed.append)
        self.assertEqual({tuple(a for a in c if a.endswith("/")) for c in runner.calls},
                         {(f"{self.hot / 'backup'}/", f"{self.cold / 'backup'}/")})
        self.assertIn("192.168.1.249 is powered off, skipping primary hot -> colder", printed)
        self.assertIn("192.168.1.249 is powered off, skipping advocate cold -> colder", printed)

    def test_run_backups_rechecks_shares_before_each_job(self):
        # cold/advocate vanishes (share drops) while job 1 is running.
        runner = FakeRunner()
        advocate = self.cold / "advocate"

        def populated(p):
            if p == advocate and runner.calls:
                return False
            return True

        with self.assertRaises(BrokenChain):
            run_backups(self.jobs, probe=probe_with(set()), populated=populated,
                        runner=runner, ask=no_ask, out=quiet)
        self.assertFalse([c for c in runner.calls if f"{advocate}/" in c])

    def test_run_backups_skips_job_if_colder_goes_off_mid_run(self):
        runner = FakeRunner()
        probe_calls = []

        def probe(host):
            probe_calls.append(host)
            return not (host == HOST_249 and runner.calls)

        printed = []
        run_backups(self.jobs, probe=probe, runner=runner, ask=no_ask, out=printed.append)
        self.assertFalse([c for c in runner.calls if any(str(self.colder) in a for a in c)])
        self.assertIn("192.168.1.249 is powered off, skipping advocate cold -> colder", printed)

    def test_run_backups_stops_after_first_failure(self):
        runner = FakeRunner((1, ""))
        with self.assertRaises(RsyncFailed):
            run_backups(self.jobs, probe=probe_with(set()), runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(len(runner.calls), 1)


if __name__ == "__main__":
    unittest.main()
