"""Backup chains between the three stores.

primary : hot .248 backup/   -> cold .248 backup/  and  hot .248 backup/ -> colder .249 backup/
advocate: cold .248 advocate/ -> colder .249 advocate/

.249 is powered off most of the time: jobs that write to it are skipped with a
message. Anything else missing (a .248 outage, an unmounted or empty share on a
reachable host) is a broken chain and nothing runs, because an empty source or
destination plus --delete-during is how a mirror gets wiped.
"""
import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HOT_ROOT = Path("/media/userhome/smb")
COLD_ROOT = Path("/media/userhome/cold_smb")
COLDER_ROOT = Path("/media/userhome/colder_smb")
HOST_248 = "192.168.1.248"
HOST_249 = "192.168.1.249"
SMB_PORT = 445
PROBE_TIMEOUT_S = 3.0


@dataclass(frozen=True)
class Job:
    name: str
    source: Path
    dest: Path
    source_host: str
    dest_host: str


class BrokenChain(Exception):
    pass


def default_jobs(hot: Path = HOT_ROOT, cold: Path = COLD_ROOT, colder: Path = COLDER_ROOT) -> list[Job]:
    return [
        Job("primary hot -> cold", hot / "backup", cold / "backup", HOST_248, HOST_248),
        Job("primary hot -> colder", hot / "backup", colder / "backup", HOST_248, HOST_249),
        Job("advocate cold -> colder", cold / "advocate", colder / "advocate", HOST_248, HOST_249),
    ]


def host_is_up(host: str, port: int = SMB_PORT, timeout: float = PROBE_TIMEOUT_S) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def dir_is_populated(path: Path) -> bool:
    if not path.is_dir():
        return False
    with os.scandir(path) as it:
        return next(it, None) is not None


def preflight(
    jobs: list[Job],
    probe: Callable[[str], bool] = host_is_up,
    populated: Callable[[Path], bool] = dir_is_populated,
) -> tuple[list[Job], list[str]]:
    # Probe every host before touching any path: an autofs path on a dead host hangs.
    hosts = list(dict.fromkeys(h for j in jobs for h in (j.source_host, j.dest_host)))
    up = {h: probe(h) for h in hosts}

    runnable: list[Job] = []
    messages: list[str] = []
    for job in jobs:
        if not up[job.source_host]:
            raise BrokenChain(f"{job.source_host} is unreachable; it holds the source for {job.name}")
        # The source is on a reachable host, so it is always checked, even when the
        # destination is off: a missing cold/advocate is a broken chain either way.
        if not populated(job.source):
            raise BrokenChain(f"{job.source} is missing or empty (share not mounted?); refusing to run {job.name}")
        if not up[job.dest_host]:
            messages.append(f"{job.dest_host} is powered off, skipping {job.name}")
            continue
        if not populated(job.dest):
            raise BrokenChain(f"{job.dest} is missing or empty (share not mounted?); refusing to run {job.name}")
        runnable.append(job)
    return runnable, messages


APPROVAL_PHRASE = "I approve THESE files TO be DELETED"


class RsyncFailed(Exception):
    def __init__(self, job: Job, returncode: int, stderr: str):
        super().__init__(f"rsync for {job.name} exited {returncode}: {stderr.strip()}")
        self.job = job
        self.returncode = returncode
        self.stderr = stderr


class DeletionNotApproved(Exception):
    pass


def build_rsync_command(job: Job, dry_run: bool) -> list[str]:
    # Trailing slashes: copy the directory's contents, not the directory itself.
    cmd = ["rsync", "-Prv", "--size-only", "--delete-during", f"{job.source}/", f"{job.dest}/"]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def run_job(
    job: Job,
    runner: Callable = subprocess.run,
    ask: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> None:
    out(f"== {job.name}: dry run")
    dry = runner(build_rsync_command(job, dry_run=True), capture_output=True, text=True)
    if dry.returncode != 0:
        raise RsyncFailed(job, dry.returncode, dry.stderr or "")
    out(dry.stdout)
    deletions = [line for line in dry.stdout.splitlines() if line.startswith("deleting ")]
    if deletions:
        out(f"{len(deletions)} deletion(s) on {job.dest}:")
        for line in deletions:
            out(f"  {line}")
        try:
            while ask(f"Type '{APPROVAL_PHRASE}' to proceed with deletion: ") != APPROVAL_PHRASE:
                out("Input did not match. Type the phrase exactly, or press CTRL+C to stop.")
        except EOFError:
            raise DeletionNotApproved(f"{job.name}: deletions pending and no approval (stdin closed)") from None
    out(f"== {job.name}: real run")
    real = runner(build_rsync_command(job, dry_run=False))
    if real.returncode != 0:
        raise RsyncFailed(job, real.returncode, getattr(real, "stderr", None) or "")


def run_backups(
    jobs: list[Job] | None = None,
    probe: Callable[[str], bool] = host_is_up,
    populated: Callable[[Path], bool] = dir_is_populated,
    runner: Callable = subprocess.run,
    ask: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> None:
    runnable, messages = preflight(jobs if jobs is not None else default_jobs(), probe, populated)
    for message in messages:
        out(message)
    for job in runnable:
        run_job(job, runner=runner, ask=ask, out=out)
