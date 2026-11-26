"""Rename new photos on hot, then run the backup chains.

    just backup

Order: preflight (nothing runs on a broken chain) -> rename/dedupe the picture
dirs on hot -> primary rsync hot->cold, hot->colder -> advocate rsync cold->colder.
Jobs writing to .249 are skipped with a message when it is powered off.
"""
import subprocess
import sys
from pathlib import Path
from typing import Callable

from backup import (
    HOT_ROOT,
    BrokenChain,
    DeletionNotApproved,
    Job,
    RsyncFailed,
    default_jobs,
    dir_is_populated,
    host_is_up,
    preflight,
    run_backups,
)
from renamer import RenameReport, rename_files

PICTURE_DIRS = [HOT_ROOT / "backup/pictures", HOT_ROOT / "backup/people/magnus/pictures"]


def main(
    picture_dirs: list[Path] = PICTURE_DIRS,
    jobs: list[Job] | None = None,
    probe: Callable[[str], bool] = host_is_up,
    populated: Callable[[Path], bool] = dir_is_populated,
    runner: Callable = subprocess.run,
    ask: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
    rename: Callable[[Path], RenameReport] = rename_files,
) -> int:
    jobs = jobs if jobs is not None else default_jobs()
    try:
        preflight(jobs, probe, populated)
        for directory in picture_dirs:
            out(f"== renaming {directory}")
            for line in rename(directory).summary_lines():
                out(line)
        run_backups(jobs, probe=probe, populated=populated, runner=runner, ask=ask, out=out)
    except (BrokenChain, RsyncFailed, DeletionNotApproved) as e:
        out(f"STOPPED: {e}")
        return 1
    except KeyboardInterrupt:
        out("\nOperation canceled by user.")
        return 130
    out("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
