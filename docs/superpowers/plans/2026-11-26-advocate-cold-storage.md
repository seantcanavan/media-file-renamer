# Merge renamer + backup, move advocate off hot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One script (`media_backup.py`) that renames/dedupes new photos on hot, then runs the hot->cold->colder backup and the cold->colder advocate backup, tolerating a powered-off .249; plus a one-time, checksum-verified move of `advocate` off hot.

**Architecture:** Three focused modules (`renamer.py`, `backup.py`, `verify_copies.py`) sharing `hashing.py`, driven by a thin entry point `media_backup.py`. All filesystem roots, hosts, rsync and the network probe are parameters with production defaults, so tests run entirely in temp dirs with fakes. The data migration (Task 6) is not code: Claude runs it step by step with Sean's explicit OK before each step.

**Tech Stack:** Python 3.14 stdlib only (`unittest`, `socket`, `subprocess`, `hashlib`, `concurrent.futures`), rsync 3.5, `just`.

**Spec:** `docs/superpowers/specs/2026-11-26-advocate-cold-storage-design.md`

## Handoff status (2026-11-26) — READ FIRST when resuming on the new machine

Sean moved to a machine with faster network before any copying. **Progress (2026-11-27): M1–M5 done** on the new machine (M3.1 changed, see Task 6). Hot advocate deleted after `just verify-advocate` exit 0; cold and colder each hold the same 338 verified files at `<share>/advocate`, manifests in `~/advocate-manifests`. Next: **M6 (Sean runs `just backup`)**, then M7.

**Done:** Tasks 1–5 + final review (opus reviewer, "with fixes"; all Critical/Important fixed with RED→GREEN tests). Last code commit `5152af9`. `just test` → 51 tests OK. Nothing under `/media` has been modified by Claude; only names/sizes were listed.

**Rules Sean set for this work (apply to the new session):**
- Sean runs Claude Code in manual mode and wants each migration step shown as an exact command, then run only after Sean says go. One step at a time. Any surprise → stop.
- Photos are off limits: never rename/move/delete/write anything under `smb/backup/pictures` or `smb/backup/people/magnus/pictures`. Never run `just backup` / `media_backup.py`; Sean does (M6).
- Deleting hot advocate (M5) needs `just verify-advocate` exit 0 **and** Sean's explicit go.
- Sean kept the commits made so far; commit + push code/doc changes per `~/.claude/CLAUDE.md` (main only, no attribution lines).
- The YouTube archive downloader that writes into advocate is stopped (Sean cancelled it) and stays stopped until M7.

**New-machine prerequisites (check in M1 before anything else):** `/media/userhome/smb`, `/media/userhome/cold_smb`, `/media/userhome/colder_smb` mounted at those exact paths (they were autofs CIFS mounts of `//192.168.1.248/smb`, `//192.168.1.248/cold_smb`, `//192.168.1.249/colder_smb`); .249 powered on for M2–M4; `python` ≥ 3.10, `rsync` ≥ 3.0, `just`, `sha256sum`; `just test` passes on that machine.

**Facts measured on 2026-11-26 (name + size only; M1 re-measures):**
- hot `smb/backup/people/sean/advocate`: 338 files, 2,150,335,502,503 bytes. cold `cold_smb/backup/people/sean/advocate`: identical names + sizes.
- colder `colder_smb/backup/people/sean/advocate`: 127 files = 120 matching hot + 7 colder-only (50.6 GB yt-dlp leftovers: `2020 08 13 - Stun Resist Diesel - Blackwing Lair & Molten Core & Zul'Gurub & Scholomance.{f251.webm,f308.webm,temp.mkv,webp}` and `2021 04 14 - Stun Resist Diesel - Naxxramas.{f251.webm,f308.webm,webp}`; the finished `.mkv` of both exists on all three). 218 hot files (448.3 GB) missing on colder. No same-name size mismatches.
- After M3 both cold and colder advocate should hold 338 files, the same as hot (the 7 partials were dropped from colder in M3.1; see Task 6).
- Free space then: hot 2.3T of 5.6T, cold 19T of 22T, colder 39T of 42T.

**Rulings made during execution (the ledger is git-ignored and did not travel):**
- T2: preflight checks a job's source even when its destination host is off (a missing `cold/advocate` is a broken chain with .249 off too). Cost if wrong: none, only stricter.
- Final: `verify_copies` fails on unreadable dirs, symlinks/special files, an empty source, and a source count ≠ `--expect-source-count` (338 in `just verify-advocate`).
- Final: each job re-probes hosts and re-checks shares right before it runs.
- Final: renamer never treats a symlink or the same file as a duplicate (raised from minor: effect would be losing the only copy of a photo).
- Final (Sean approved): real rsync run gets `--max-delete=N`, N = approved dry-run deletions.

**Deferred minors (not fixed; none can lose data):** a destination file replaced by a source dir of the same name is deleted with no `deleting` line (pre-existing rsync behaviour); renamer stats the whole folder per new file over SMB (slow for huge dumps); dry-run stderr not shown when rc 0, and real-run failure text has empty stderr (it streams live); OSError/UnicodeDecodeError show a traceback rather than `STOPPED:` (fails safe).

## Global Constraints

- Work on `main`; no branches/worktrees/PRs. Commits: explicit paths, no `-s`, no `Co-Authored-By` or any AI attribution. **Commit hold:** Sean asked Claude to hold all commits and pushes; commit steps run only once Sean lifts the hold.
- **Never touch real photos.** No test, command or subagent may read-write anything under `/media/userhome/smb/backup/pictures` or `/media/userhome/smb/backup/people/magnus/pictures`. Tests use `tempfile.TemporaryDirectory()` only. Never run `media_backup.py` or `just backup` against real shares; Sean does that.
- Never touch `/media/userhome/*` at all from Tasks 1–5 (code + tests only).
- Hosts by IP: hot/cold `192.168.1.248`, colder `192.168.1.249`. SMB port `445`. Probe timeout `3.0` s.
- Mount roots: hot `/media/userhome/smb`, cold `/media/userhome/cold_smb`, colder `/media/userhome/colder_smb`.
- rsync flags for every job, verbatim: `rsync -Prv --size-only --delete-during SRC/ DEST/` (+ `--dry-run` for the dry pass; + `--max-delete=N` on the real pass, N = approved `deleting` lines, added after final review with Sean's OK). Commands are argv lists, never a shell string.
- Approval phrase, verbatim: `I approve THESE files TO be DELETED`.
- Media extensions, verbatim from today's script: `.jpg .jpeg .png .gif .mp4 .mp3 .avi .mov .mkv .heic .bmp .tif .tiff .bmp2 .tiff2 .aae` (matched case-insensitively).
- Timestamp prefix format `%Y-%m-%d_%H-%M-%S` from `st_ctime`, followed by `_`; extension lower-cased.
- Tests: `just test` == `python -m unittest discover -s tests -t . -v`.

## Review Focus

1. **Share not mounted shows up as an empty dir** (autofs) — must raise `BrokenChain`, never rsync with `--delete-during` from/to it. Test: `test_preflight_empty_source_is_broken_chain`, `test_preflight_empty_dest_on_up_host_is_broken_chain` (Task 2).
2. **.249 powered off** — its paths must not be touched at all (touching autofs for a dead host hangs). Test: `test_preflight_colder_down_never_touches_colder_paths` (Task 2).
3. **Unattended run / stdin closed when deletions are pending** — `EOFError` from the prompt must abort with no real rsync. Test: `test_run_job_eof_at_prompt_aborts_without_real_run` (Task 3).
4. **Filenames with spaces, quotes, `&`, unicode (`⧸`, `＂`)** — argv list with trailing-slash dirs, no shell. Test: `test_build_command_is_argv_with_trailing_slashes` (Task 3); `test_rename_handles_unicode_and_spaces` (Task 1).
5. **Same name + same size but different bytes** (e.g. small `.aae` files) — never deleted. Test: `test_same_name_same_size_different_content_keeps_both` (Task 1).

---

### Task 1: `hashing.py` + `renamer.py` (rename and checksum dedupe)

**Files:**
- Create: `hashing.py`, `renamer.py`, `tests/__init__.py` (empty), `tests/test_renamer.py`

**Interfaces:**
- Produces:
  - `hashing.sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str` (hex digest).
  - `renamer.MEDIA_EXTENSIONS: frozenset[str]`
  - `renamer.has_timestamp_prefix(name: str) -> bool` — regex `^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}` (unchanged from today).
  - `renamer.format_timestamp(ts: float) -> str`
  - `@dataclass renamer.RenameReport`: `renamed: list[tuple[Path, Path]]`, `deleted_redumps: list[tuple[Path, Path]]` (deleted, kept), `same_name_different_content: list[Path]` (the new file, after rename), `skipped_collisions: list[tuple[Path, Path]]` (new file, existing target). Method `summary_lines() -> list[str]`.
  - `renamer.rename_files(directory: Path, timestamp_of: Callable[[Path], float] = lambda p: p.stat().st_ctime) -> RenameReport`

**Algorithm (the spec's rules; not determined by signatures):**
```
snapshot = sorted(all files under directory, recursive)   # list first, never mutate while globbing
for f in snapshot where suffix.lower() in MEDIA_EXTENSIONS and not has_timestamp_prefix(f.name):
    original = f.stem + f.suffix.lower()
    matches = [p in f.parent (non-recursive) with prefixed name whose part after the 20-char "YYYY-MM-DD_HH-MM-SS_" == original]
    twin = first m in matches with size == f.size and sha256(m) == sha256(f)
    if twin: delete f; record deleted_redumps (f, twin); continue
    target = f.parent / f"{format_timestamp(timestamp_of(f))}_{original}"
    if target exists:
        if same size and same sha256: delete f; record deleted_redumps (f, target)
        else: record skipped_collisions (f, target)          # f left untouched
        continue
    os.rename(f, target); record renamed
    if matches: record same_name_different_content (target)
```
Hash only when sizes match. No `input()` anywhere.

- [ ] **Step 1: Write failing tests** in `tests/test_renamer.py` (each in its own `TemporaryDirectory`, `timestamp_of` injected as a constant so names are deterministic, e.g. `lambda p: 1_700_000_000.0` → prefix `format_timestamp(1_700_000_000.0)`):
  - `test_renames_media_with_prefix_and_lowercase_ext`: `IMG_1.HEIC` → `<prefix>_IMG_1.heic`; report.renamed has 1 entry.
  - `test_ignores_non_media_and_already_prefixed`: `notes.txt` and `2020-01-01_00-00-00_IMG_2.jpg` unchanged; report empty.
  - `test_redump_identical_is_deleted_and_original_kept`: existing `2020-01-01_00-00-00_IMG_3.jpg` (bytes `b"A"*100`), new `IMG_3.JPG` same bytes → new file gone, old file still has `b"A"*100`, `deleted_redumps == [(new, old)]`.
  - `test_same_name_same_size_different_content_keeps_both`: existing prefixed `IMG_4.aae` = `b"A"*100`, new `IMG_4.aae` = `b"B"*100` → both exist afterwards (new one renamed), new path in `same_name_different_content`, `deleted_redumps == []`.
  - `test_same_name_different_size_keeps_both`: as above with `b"B"*50`.
  - `test_target_exists_identical_deletes_new_only`: pre-create `<prefix>_IMG_5.jpg` with bytes X, new `IMG_5.jpg` with X → new deleted, target intact.
  - `test_target_exists_different_skips_and_leaves_both`: target bytes X, new bytes Y (same size) → both untouched, `skipped_collisions == [(new, target)]`.
  - `test_match_is_same_directory_only`: identical prefixed twin in `sub_a/`, new file in `sub_b/` → new file renamed, not deleted.
  - `test_rename_handles_unicode_and_spaces`: `It＂s ⧸ a & b.mov` → renamed with prefix, content intact.
  - `test_sha256_file_matches_hashlib`: `hashing.sha256_file` equals `hashlib.sha256(data).hexdigest()` for a 20 MB file (crosses chunk boundary).
- [ ] **Step 2: Run** `python -m unittest tests.test_renamer -v` → FAIL (`ModuleNotFoundError: renamer`).
- [ ] **Step 3: Implement** `hashing.py` and `renamer.py` per Interfaces + Algorithm. `summary_lines()` prints one line per renamed/deleted/flagged/skipped file plus counts.
- [ ] **Step 4: Run** `python -m unittest tests.test_renamer -v` → all PASS.
- [ ] **Step 5: Commit** (when hold lifted): `git add hashing.py renamer.py tests/__init__.py tests/test_renamer.py && git commit -m "renamer: checksum dedupe for re-dumped photos, no prompts"`

---

### Task 2: `backup.py` — stores, jobs, host probe, preflight

**Files:**
- Create: `backup.py`, `tests/test_backup_preflight.py`

**Interfaces:**
- Produces:
  - Constants: `HOT_ROOT`, `COLD_ROOT`, `COLDER_ROOT` (`Path`s from Global Constraints), `HOST_248 = "192.168.1.248"`, `HOST_249 = "192.168.1.249"`, `SMB_PORT = 445`, `PROBE_TIMEOUT_S = 3.0`.
  - `@dataclass(frozen=True) Job`: `name: str`, `source: Path`, `dest: Path`, `source_host: str`, `dest_host: str`.
  - `default_jobs(hot: Path = HOT_ROOT, cold: Path = COLD_ROOT, colder: Path = COLDER_ROOT) -> list[Job]`, in this order:
    1. `"primary hot -> cold"`: `hot/backup` → `cold/backup`, 248 → 248
    2. `"primary hot -> colder"`: `hot/backup` → `colder/backup`, 248 → 249
    3. `"advocate cold -> colder"`: `cold/advocate` → `colder/advocate`, 248 → 249
  - `class BrokenChain(Exception)`
  - `host_is_up(host: str, port: int = SMB_PORT, timeout: float = PROBE_TIMEOUT_S) -> bool` — `socket.create_connection`; any `OSError` → `False`.
  - `dir_is_populated(path: Path) -> bool` — is a dir and has at least one entry.
  - `preflight(jobs: list[Job], probe: Callable[[str], bool] = host_is_up, populated: Callable[[Path], bool] = dir_is_populated) -> tuple[list[Job], list[str]]` — returns (runnable jobs in input order, skip messages).

**Rules:** probe each distinct host once, before touching any path. If any job's `source_host` is down → `BrokenChain` (".248 must be up"). For a job whose `dest_host` is down → skip it with message `f"{dest_host} is powered off, skipping {job.name}"`, and never call `populated` on its paths. For every job not skipped: `populated(source)` and `populated(dest)` must both be true, else `BrokenChain` naming the path.

- [ ] **Step 1: Write failing tests** in `tests/test_backup_preflight.py` (temp dirs laid out as `hot/backup/x`, `cold/backup/x`, `cold/advocate/x`, `colder/backup/x`, `colder/advocate/x`; jobs from `default_jobs(hot, cold, colder)`):
  - `test_preflight_all_up_runs_all_three_jobs`: probe always True → 3 jobs, no messages.
  - `test_preflight_colder_down_runs_only_hot_to_cold`: probe False for 249 → jobs == [job 1]; messages == `["192.168.1.249 is powered off, skipping primary hot -> colder", "192.168.1.249 is powered off, skipping advocate cold -> colder"]`.
  - `test_preflight_colder_down_never_touches_colder_paths`: recording `populated` fake; assert no recorded path is under `colder`.
  - `test_preflight_248_down_is_broken_chain`: probe False for 248 → `assertRaises(BrokenChain)`.
  - `test_preflight_empty_source_is_broken_chain`: empty `hot/backup` → `BrokenChain`.
  - `test_preflight_missing_cold_advocate_is_broken_chain`: no `cold/advocate` dir → `BrokenChain`.
  - `test_preflight_empty_dest_on_up_host_is_broken_chain`: 249 up, `colder/backup` empty → `BrokenChain`.
  - `test_preflight_probes_each_host_once`: counting probe → called exactly once for each of the two hosts.
  - `test_host_is_up_false_on_refused_port`: `host_is_up("127.0.0.1", port=<free port from a bound-then-closed socket>, timeout=0.5)` → False.
- [ ] **Step 2: Run** `python -m unittest tests.test_backup_preflight -v` → FAIL (module missing).
- [ ] **Step 3: Implement** the Interfaces above in `backup.py`.
- [ ] **Step 4: Run** `python -m unittest tests.test_backup_preflight -v` → all PASS.
- [ ] **Step 5: Commit** (when hold lifted): `git add backup.py tests/test_backup_preflight.py && git commit -m "backup: preflight that tolerates .249 off but stops on a broken chain"`

---

### Task 3: `backup.py` — running a job (dry run, approval, return codes)

**Files:**
- Modify: `backup.py`
- Create: `tests/test_backup_run.py`

**Interfaces:**
- Consumes: `Job`, `default_jobs`, `preflight`, `BrokenChain` (Task 2).
- Produces:
  - `APPROVAL_PHRASE = "I approve THESE files TO be DELETED"`
  - `class RsyncFailed(Exception)` — attrs `job: Job`, `returncode: int`, `stderr: str`.
  - `class DeletionNotApproved(Exception)`
  - `build_rsync_command(job: Job, dry_run: bool) -> list[str]` → `["rsync", "-Prv", "--size-only", "--delete-during", f"{job.source}/", f"{job.dest}/"]` + `["--dry-run"]` when `dry_run`.
  - `run_job(job: Job, runner: Callable = subprocess.run, ask: Callable[[str], str] = input, out: Callable[[str], None] = print) -> None`
  - `run_backups(jobs: list[Job] | None = None, probe=host_is_up, populated=dir_is_populated, runner=subprocess.run, ask=input, out=print) -> None` — preflight, print each skip message, then `run_job` for each runnable job in order. Exceptions propagate.

**`run_job` behaviour:** dry pass with `runner(cmd, capture_output=True, text=True)`; non-zero → `RsyncFailed`. Print dry-run stdout. If any stdout line starts with `"deleting "`: print those lines, then loop `ask(f"Type '{APPROVAL_PHRASE}' to proceed with deletion: ")` until exact match; `EOFError` → raise `DeletionNotApproved` (no real run). Real pass with `runner(cmd)` (output streams to the terminal, no capture); non-zero → `RsyncFailed`.

- [ ] **Step 1: Write failing tests** in `tests/test_backup_run.py` using a fake runner that records argv lists and returns `subprocess.CompletedProcess(args, rc, stdout, stderr)` from a script of responses:
  - `test_build_command_is_argv_with_trailing_slashes`: source `Path("/a/b c & d⧸e")` → element 4 == `"/a/b c & d⧸e/"`; dry_run adds `--dry-run` last; flags exactly as in Global Constraints.
  - `test_run_job_no_deletions_runs_dry_then_real`: dry stdout without `deleting ` → two calls, second without `--dry-run`, `ask` never called.
  - `test_run_job_deletions_require_exact_phrase`: dry stdout has `deleting old.jpg`; `ask` returns `"yes"`, then the phrase → real run happens once, `ask` called twice.
  - `test_run_job_eof_at_prompt_aborts_without_real_run`: `ask` raises `EOFError` → `DeletionNotApproved`; runner called once (dry only).
  - `test_run_job_dry_run_failure_raises_and_skips_real`: dry rc 23 → `RsyncFailed` with `returncode == 23`; one call.
  - `test_run_job_real_run_failure_raises`: dry rc 0, real rc 12 → `RsyncFailed`.
  - `test_run_backups_prints_skips_and_runs_only_runnable`: temp layout from Task 2, probe False for 249 → runner only ever sees `hot/backup/` → `cold/backup/`; both skip messages printed.
  - `test_run_backups_stops_after_first_failure`: all up, job 1 dry rc 1 → `RsyncFailed`, no command for jobs 2–3.
- [ ] **Step 2: Run** `python -m unittest tests.test_backup_run -v` → FAIL (names missing).
- [ ] **Step 3: Implement** the Interfaces above in `backup.py`.
- [ ] **Step 4: Run** `python -m unittest discover -s tests -t . -v` → all PASS.
- [ ] **Step 5: Commit** (when hold lifted): `git add backup.py tests/test_backup_run.py && git commit -m "backup: dry-run + approval per job, fail on rsync errors, advocate job"`

---

### Task 4: `media_backup.py` entry point, `justfile`, README, remove old scripts

**Files:**
- Create: `media_backup.py`, `justfile`, `tests/test_media_backup.py`
- Modify: `README.md`
- Delete: `rename_media_by_timestamp.py`, `rsync_backup.py` (`git rm`; history keeps them)

**Interfaces:**
- Consumes: `rename_files`, `RenameReport` (Task 1); `default_jobs`, `preflight`, `run_backups`, `BrokenChain`, `RsyncFailed`, `DeletionNotApproved`, `HOT_ROOT` (Tasks 2–3).
- Produces:
  - `PICTURE_DIRS = [HOT_ROOT / "backup/pictures", HOT_ROOT / "backup/people/magnus/pictures"]`
  - `main(picture_dirs: list[Path] = PICTURE_DIRS, jobs: list[Job] | None = None, probe=host_is_up, populated=dir_is_populated, runner=subprocess.run, ask=input, out=print, rename=rename_files) -> int`

**Order inside `main`:** `preflight(jobs, probe, populated)` first (so nothing — not even the rename — runs on a broken chain); then `rename` each picture dir and print `summary_lines()`; then `run_backups(...)` (it re-runs preflight; cheap and catches a host that dropped during the rename). Return `0` on success (skips included), `1` on `BrokenChain` / `RsyncFailed` / `DeletionNotApproved` with the error printed, `130` on `KeyboardInterrupt`. `if __name__ == "__main__": sys.exit(main())`.

`justfile` recipes: `default` (`just --list`), `test` (`python -m unittest discover -s tests -t . -v`), `backup` (`python media_backup.py`), `verify-advocate` (added in Task 5). README: what the script does, the three stores and chains, that .249 may be off, `just backup` / `just test`.

- [ ] **Step 1: Write failing tests** in `tests/test_media_backup.py` (fake `rename` recording calls; temp layout from Task 2):
  - `test_broken_chain_returns_1_and_never_renames`: empty `hot/backup` → `main(...) == 1`, rename fake never called, runner never called.
  - `test_rename_runs_before_any_rsync`: shared event list shows both renames before the first runner call.
  - `test_colder_down_returns_0`: probe False for 249 → returns 0, output contains both "powered off" messages.
  - `test_rsync_failure_returns_1`: runner rc 23 → returns 1.
- [ ] **Step 2: Run** `python -m unittest tests.test_media_backup -v` → FAIL.
- [ ] **Step 3: Implement** `media_backup.py`; write `justfile` and README; `git rm rename_media_by_timestamp.py rsync_backup.py`.
- [ ] **Step 4: Run** `just test` → all PASS; `just --list` shows `backup`, `test`.
- [ ] **Step 5: Commit** (when hold lifted): `git add media_backup.py justfile README.md tests/test_media_backup.py && git commit -m "merge renamer + backup into media_backup.py, add justfile"` (the `git rm` deletions are already staged).

---

### Task 5: `verify_copies.py` (checksum proof for the migration)

**Files:**
- Create: `verify_copies.py`, `tests/test_verify_copies.py`
- Modify: `justfile` (add `verify-advocate`)

**Interfaces:**
- Consumes: `hashing.sha256_file` (Task 1).
- Produces:
  - `hash_tree(root: Path, out: Callable[[str], None] = print) -> dict[str, tuple[int, str]]` — relative posix path → (size, sha256) for every regular file; progress line per file.
  - `compare(source: dict, copies: dict[str, dict]) -> list[str]` — problems, empty means verified. Rules: every source file exists in every copy with equal size and hash; all copies have identical maps to each other (files only in copies are fine relative to source, but must be on all copies).
  - `write_manifest(tree: dict, path: Path) -> None` — `sha256sum` format (`<hex>  <relpath>`), sorted.
  - CLI: `python verify_copies.py --source DIR --copy LABEL=DIR [--copy LABEL=DIR ...] --manifest-dir DIR` — hashes all roots in parallel (`ThreadPoolExecutor`, one thread per root), writes `<label>.sha256` per root (`source` label for the source), prints problems, exit 0 iff none. Read-only on every root.

`justfile`: `verify-advocate` runs it with `--source /media/userhome/smb/backup/people/sean/advocate --copy cold=/media/userhome/cold_smb/advocate --copy colder=/media/userhome/colder_smb/advocate --manifest-dir ~/advocate-manifests`.

- [ ] **Step 1: Write failing tests** in `tests/test_verify_copies.py`:
  - `test_identical_trees_no_problems`
  - `test_missing_on_one_copy_reported`: problem string names the path and the copy label.
  - `test_hash_mismatch_same_size_reported`
  - `test_extra_file_on_both_copies_is_ok` (the 7 leftovers case)
  - `test_extra_file_on_only_one_copy_reported`
  - `test_manifest_is_sha256sum_compatible`: `sha256sum -c` run in the tree dir against the written manifest exits 0.
- [ ] **Step 2: Run** `python -m unittest tests.test_verify_copies -v` → FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** `just test` → all PASS.
- [ ] **Step 5: Commit** (when hold lifted): `git add verify_copies.py tests/test_verify_copies.py justfile && git commit -m "verify_copies: parallel sha256 proof across hot/cold/colder"`

---

### Task 6: One-time advocate migration (Claude inline, never a subagent)

Each step: Claude shows the exact command, Sean says go, Claude runs it and shows the result. Any surprise → stop. All paths are fixed; nothing under `pictures` is touched.

- [x] **M1 Freeze.** Sean confirms the downloader is stopped and no backup will run until M6. Claude re-runs the name+size comparison from brainstorming; expected: hot 338 files / 2,150,335,502,503 bytes, cold identical, colder 127 files.
- [x] **M2 Rename on cold and colder.** Precheck: `cold_smb/advocate` and `colder_smb/advocate` do not exist. Run `python -I -c "import os; os.rename('/media/userhome/cold_smb/backup/people/sean/advocate', '/media/userhome/cold_smb/advocate')"`, then the same for colder. A failure (e.g. `EXDEV`) means nothing moved → stop and re-plan. Check: file counts at the new paths match M1.
- [x] **M3 Make cold and colder identical, without deleting.**
  1. ~~`rsync -Prv --ignore-existing --dry-run /media/userhome/colder_smb/advocate/ /media/userhome/cold_smb/advocate/` → must list exactly the 7 colder-only files; then the same without `--dry-run`.~~ **Changed 2026-11-26 (Sean's call):** the 7 colder-only files were 2024-10-31 yt-dlp partials of `.mkv` files present on all three shares, so they were deleted from colder (explicit 7-path `rm -v`, after checking both `.mkv` sizes on cold and colder) instead of being copied to cold. Colder then held 120 files.
  2. `rsync -Prv --size-only --dry-run /media/userhome/cold_smb/advocate/ /media/userhome/colder_smb/advocate/` → must list exactly the 218 missing files and **no** `deleting` lines; then the real run in the background (~448 GB).
  3. Check: cold and colder both 338 files (was 345 before the change in step 1), same names and sizes, both equal to hot.
- [x] **M4 Checksum proof.** `just verify-advocate` in the background (~6.5 TB read). Must exit 0 with no problems. Manifests stay in `~/advocate-manifests`.
- [x] **M5 Delete advocate from hot** — only with exit 0 from M4 **and** Sean's explicit go. Recheck that hot advocate still has exactly the 338 files of M1 (nothing new since hashing). Then `rm -rv -- /media/userhome/smb/backup/people/sean/advocate`. Check: path gone; `df -h /media/userhome/smb` shows ~2.15 TB freed.
- [ ] **M6 First real run — Sean runs `just backup`.** Claude does not run it (it includes the rename step). Expected: the primary dry runs show **no** `deleting` lines (M2 already moved advocate out of `backup/` on cold and colder), and the advocate dry run shows none either (M3 made the two identical). Any `deleting` line at all on this first run → don't type the phrase; stop and look together.
- [ ] **M7 Wrap up.** Sean repoints the downloader at `/media/userhome/cold_smb/advocate`. Claude deletes any scratch files it made on the new machine. (The brainstorming scratch files on the old machine were already deleted at handoff.)
