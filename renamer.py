"""Prefix new media files with a sortable timestamp and drop exact re-dumps.

A photo copied from the phone to the NAS twice lands with a new st_ctime, so
it would get a second, different prefix. Before renaming a new file we look for
an already-prefixed file in the same directory with the same original name;
if size and SHA-256 both match, the new copy is a re-dump and is deleted.
Anything less than an exact match keeps both files. Never prompts.
"""
import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from hashing import sha256_file

MEDIA_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".avi", ".mov", ".mkv",
    ".heic", ".bmp", ".tif", ".tiff", ".bmp2", ".tiff2", ".aae",
})

_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}")
_PREFIX_WITH_SEP_LEN = len("YYYY-MM-DD_HH-MM-SS_")


def has_timestamp_prefix(name: str) -> bool:
    return _PREFIX_RE.match(name) is not None


def format_timestamp(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M-%S")


@dataclass
class RenameReport:
    renamed: list[tuple[Path, Path]] = field(default_factory=list)
    deleted_redumps: list[tuple[Path, Path]] = field(default_factory=list)  # (deleted, kept)
    same_name_different_content: list[Path] = field(default_factory=list)
    skipped_collisions: list[tuple[Path, Path]] = field(default_factory=list)  # (new, existing)

    def summary_lines(self) -> list[str]:
        lines = [f"renamed: {src} -> {dst.name}" for src, dst in self.renamed]
        lines += [f"deleted re-dump: {gone} (identical to {kept.name})" for gone, kept in self.deleted_redumps]
        lines += [f"REVIEW same name, different content: {p}" for p in self.same_name_different_content]
        lines += [f"REVIEW skipped, target exists with different content: {new} vs {old.name}"
                  for new, old in self.skipped_collisions]
        lines.append(
            f"rename summary: {len(self.renamed)} renamed, {len(self.deleted_redumps)} re-dumps deleted, "
            f"{len(self.same_name_different_content)} same-name/different-content, "
            f"{len(self.skipped_collisions)} skipped collisions"
        )
        return lines


def _identical(a: Path, b: Path) -> bool:
    return a.stat().st_size == b.stat().st_size and sha256_file(a) == sha256_file(b)


def _prefixed_twins_by_name(directory: Path, original: str) -> list[Path]:
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and has_timestamp_prefix(p.name) and p.name[_PREFIX_WITH_SEP_LEN:] == original
    )


def rename_files(
    directory: Path,
    timestamp_of: Callable[[Path], float] = lambda p: p.stat().st_ctime,
) -> RenameReport:
    report = RenameReport()
    # Snapshot first: never mutate the tree while walking it.
    candidates = sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS and not has_timestamp_prefix(p.name)
    )
    for new in candidates:
        original = new.stem + new.suffix.lower()
        matches = _prefixed_twins_by_name(new.parent, original)
        twin = next((m for m in matches if _identical(new, m)), None)
        if twin is not None:
            os.remove(new)
            report.deleted_redumps.append((new, twin))
            continue
        target = new.parent / f"{format_timestamp(timestamp_of(new))}_{original}"
        if target.exists():
            if _identical(new, target):
                os.remove(new)
                report.deleted_redumps.append((new, target))
            else:
                report.skipped_collisions.append((new, target))
            continue
        os.rename(new, target)
        report.renamed.append((new, target))
        if matches:
            report.same_name_different_content.append(target)
    return report
