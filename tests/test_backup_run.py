import subprocess
import tempfile
import unittest
from pathlib import Path

from backup import (
    APPROVAL_PHRASE,
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
        self.assertEqual({tuple(c[-2:]) if c[-1] != "--dry-run" else tuple(c[-3:-1]) for c in runner.calls},
                         {(f"{self.hot / 'backup'}/", f"{self.cold / 'backup'}/")})
        self.assertIn("192.168.1.249 is powered off, skipping primary hot -> colder", printed)
        self.assertIn("192.168.1.249 is powered off, skipping advocate cold -> colder", printed)

    def test_run_backups_stops_after_first_failure(self):
        runner = FakeRunner((1, ""))
        with self.assertRaises(RsyncFailed):
            run_backups(self.jobs, probe=probe_with(set()), runner=runner, ask=no_ask, out=quiet)
        self.assertEqual(len(runner.calls), 1)


if __name__ == "__main__":
    unittest.main()
