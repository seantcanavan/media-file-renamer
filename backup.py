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
