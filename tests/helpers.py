"""Fake store layouts for backup tests. Never points at /media."""
from pathlib import Path

HOST_248 = "192.168.1.248"
HOST_249 = "192.168.1.249"


def make_layout(base: Path, empty: tuple[str, ...] = (), missing: tuple[str, ...] = ()) -> tuple[Path, Path, Path]:
    """Create hot/backup, cold/backup, cold/advocate, colder/backup, colder/advocate,
    each holding one file, except dirs listed in `empty` (created, no entries) or
    `missing` (not created). Returns (hot, cold, colder) roots."""
    for rel in ("hot/backup", "cold/backup", "cold/advocate", "colder/backup", "colder/advocate"):
        if rel in missing:
            continue
        d = base / rel
        d.mkdir(parents=True, exist_ok=True)
        if rel not in empty:
            (d / "x").write_bytes(b"x")
    return base / "hot", base / "cold", base / "colder"


def probe_with(down: set[str]):
    calls: list[str] = []

    def probe(host: str) -> bool:
        calls.append(host)
        return host not in down

    probe.calls = calls
    return probe
