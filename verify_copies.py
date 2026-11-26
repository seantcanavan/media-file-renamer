"""Checksum proof that copies of a tree are complete before the source is deleted.

    python verify_copies.py --source DIR --copy cold=DIR --copy colder=DIR --manifest-dir DIR

Read-only on every root. Each root is hashed in its own thread (they are separate
disks/hosts). Passes (exit 0) only if every source file is on every copy with the
same size and SHA-256, and the copies are identical to each other (files that are
only on the copies are allowed, as long as every copy has them). Writes one
sha256sum-format manifest per root.
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from hashing import sha256_file

Tree = dict[str, tuple[int, str]]


class UnsupportedEntry(Exception):
    """A symlink, socket, device etc. in a tree being verified: refuse rather than skip."""


def _raise(error: OSError) -> None:
    raise error


def hash_tree(root: Path, out: Callable[[str], None] = print) -> Tree:
    tree: Tree = {}
    # onerror=_raise: a directory we cannot list must fail the run, never be skipped.
    for dirpath, dirnames, filenames in os.walk(root, onerror=_raise):
        for name in dirnames:
            if (Path(dirpath) / name).is_symlink():
                raise UnsupportedEntry(f"symlinked directory: {Path(dirpath) / name}")
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                raise UnsupportedEntry(f"not a regular file: {path}")
            rel = path.relative_to(root).as_posix()
            tree[rel] = (path.stat().st_size, sha256_file(path))
            out(f"[{root}] {len(tree)}: {rel}")
    return tree


def compare(source: Tree, copies: dict[str, Tree], expect_source_count: int | None = None) -> list[str]:
    problems: list[str] = []
    if not source:
        problems.append("source is empty (share not mounted?)")
    if expect_source_count is not None and len(source) != expect_source_count:
        problems.append(f"source has {len(source)} files, expected {expect_source_count}")
    for label, copy in copies.items():
        for rel, entry in sorted(source.items()):
            if rel not in copy:
                problems.append(f"missing on {label}: {rel}")
            elif copy[rel] != entry:
                problems.append(f"differs on {label}: {rel} (source {entry}, {label} {copy[rel]})")
    extras = sorted({rel for copy in copies.values() for rel in copy} - source.keys())
    for rel in extras:
        present = {label: copy[rel] for label, copy in copies.items() if rel in copy}
        if len(present) != len(copies):
            missing = sorted(set(copies) - set(present))
            problems.append(f"only on some copies: {rel} (missing on {', '.join(missing)})")
        elif len(set(present.values())) != 1:
            problems.append(f"differs between copies: {rel} {present}")
    return problems


def write_manifest(tree: Tree, path: Path) -> None:
    lines = []
    for rel, (_, digest) in sorted(tree.items()):
        if "\\" in rel or "\n" in rel:  # sha256sum's escaping for awkward names
            lines.append("\\" + digest + "  " + rel.replace("\\", "\\\\").replace("\n", "\\n"))
        else:
            lines.append(f"{digest}  {rel}")
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8", errors="surrogateescape")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--copy", action="append", required=True, metavar="LABEL=DIR")
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--expect-source-count", type=int, default=None,
                        help="fail unless the source holds exactly this many files")
    args = parser.parse_args(argv)

    roots = {"source": args.source}
    for spec in args.copy:
        label, _, directory = spec.partition("=")
        if not directory or label in roots:
            parser.error(f"bad --copy {spec!r}")
        roots[label] = Path(directory)
    for label, root in roots.items():
        if not root.is_dir():
            print(f"FAIL: {label} root {root} is not a directory")
            return 1

    with ThreadPoolExecutor(max_workers=len(roots)) as pool:
        futures = {label: pool.submit(hash_tree, root) for label, root in roots.items()}
        try:
            trees = {label: f.result() for label, f in futures.items()}
        except (OSError, UnsupportedEntry) as e:
            print(f"FAIL: could not read every file: {e}")
            return 1

    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    for label, tree in trees.items():
        write_manifest(tree, args.manifest_dir / f"{label}.sha256")

    source = trees.pop("source")
    problems = compare(source, trees, args.expect_source_count)
    for label, tree in [("source", source), *trees.items()]:
        print(f"{label}: {len(tree)} files, {sum(s for s, _ in tree.values()):,} bytes")
    if problems:
        print(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"OK: all {len(source)} source files verified on {', '.join(trees)}; copies identical to each other.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
