# Merge renamer + backup, move advocate off hot storage

## Why

- Automate further: one script runs the timestamp rename, then the backups.
- `smb/backup/people/sean/advocate` (338 files, 2.15 TB of video) has outgrown the
  hot SSD share on .248. It must keep exactly two copies (cold .248, colder .249)
  and leave hot. The YouTube archive download that feeds it restarts afterwards,
  writing to the new location.
- .249 is powered off most of the time and only switched on for occasional
  tertiary backups. The script must treat that as normal.

## Hard rules

- No file on cold or colder is ever lost. Files may move.
- The only files ever deleted from hot are the advocate videos, and only after
  checksum-proven copies exist on both cold and colder.
- Nothing destructive runs against a share that is missing or not mounted.
- **Photos are off limits to Claude.** During this work Claude never renames,
  moves, deletes or writes any photo (listing names/sizes only). The rename step
  is tested only against fake temp dirs. Every real run of the merged script is
  started by Sean. The 27 existing duplicate pairs found in `smb/backup/pictures`
  are left alone; any cleanup later is Sean's, with a dedicated tool.

## Stores and data flow

| Store  | Mount                        | Host          |
|--------|------------------------------|---------------|
| hot    | `/media/userhome/smb`        | 192.168.1.248 |
| cold   | `/media/userhome/cold_smb`   | 192.168.1.248 |
| colder | `/media/userhome/colder_smb` | 192.168.1.249 |

- Primary chain: hot `backup/` -> cold `backup/` -> colder `backup/`
  (implemented, as today, as two rsyncs from hot: hot->cold, hot->colder).
- Advocate chain: cold `advocate/` -> colder `advocate/`. Cold is the master copy.

## Approaches considered

- **Chosen (Sean): move advocate to the root of cold and colder, add a second,
  similar rsync for it.** Keeps the primary `backup/` mirror a plain mirror of hot.
- Keep advocate inside `backup/` on cold and protect it with an rsync exclude:
  rejected. One wrong flag (`--delete-excluded`) or a typo wipes both copies.
- Leave advocate on hot: rejected, it no longer fits.

## One-time migration (manual, each step confirmed by Sean)

1. Freeze: backup script and downloader do not run.
2. `os.rename` `cold_smb/backup/people/sean/advocate` -> `cold_smb/advocate`, same on
   colder. `os.rename` never falls back to copying; if it fails (different dataset)
   nothing has moved and we stop to re-plan.
3. Copy the 7 colder-only files (yt-dlp `.f251/.f308.webm`, `.temp.mkv`, `.webp`;
   50.6 GB) colder -> cold, then copy cold -> colder (no delete) to fill the 218
   missing files (448 GB). Afterwards cold and colder advocate are identical sets.
4. Checksum (sha256) every advocate file on hot, cold and colder; all must match.
   Runs over the SMB mounts in the background (~6.5 TB read, hours).
5. Only then, with Sean's explicit go-ahead, delete `smb/backup/people/sean/advocate`.
6. Sean runs the new script (`just backup`); it includes the rename step, which
   touches photos, so Claude does not run it. The primary dry run must show no
   advocate deletions (cold and colder no longer have advocate under `backup/`).

## The merged script (`media_backup.py`, replaces both old scripts)

Order: preflight -> rename -> primary rsync -> advocate rsync. Any error stops the
run before the next step.

**Preflight / host availability** (before any rsync):
- For each host, a TCP connect to port 445 with a short timeout, so a powered-off
  .249 is detected without hanging on the autofs mount.
- For each reachable store, the share must actually be mounted and populated: the
  source dir (`smb/backup`, `cold_smb/advocate`) and destination root must exist and
  be non-empty. An empty or missing dir on a reachable host is a broken chain.
- Outcomes:
  - .248 unreachable, hot or cold missing/empty: **error, nothing runs.**
  - .249 unreachable: not an error. Primary hot->cold runs; the hot->colder stage
    prints ".249 is powered off, skipping colder"; the advocate rsync prints the
    same and is skipped; script exits 0.
  - .249 reachable but `colder_smb` not mounted/empty: **error** (broken chain).

**Rename step:** the existing timestamp renamer over the two picture dirs
(prefix from `st_ctime`, extension lower-cased, already-prefixed files skipped).
Its purpose includes de-duplicating photos that were dumped from the phone twice.

Today's dedupe is broken: the prefix is the time the copy landed on the NAS, so a
second dump gets a different prefix and never collides (27 such pairs exist today).
It also deletes on equal size alone, and line 49 (`elif x == x`) deletes the
renamed file on any typo at the prompt. New behaviour for each un-prefixed file:

- Look in the same dir for an already-prefixed file whose original-name part
  matches (case-insensitive extension).
- If one has the same size **and** the same SHA-256: it is a re-dump. Delete the
  new, un-prefixed copy; keep the older prefixed one. Print what was deleted.
- If the name matches but size or hash differs: keep both, rename the new one as
  usual, and list it under "same name, different content" in the summary.
- If the exact target name already exists (same-second collision): same rule,
  delete the new copy only on size + SHA-256 match, otherwise skip it and list it.
- No typed prompts: it runs unattended. Hashing only happens on a name + size
  match, so it stays fast.

**Primary rsync** (unchanged flags): `rsync -Prv --size-only --delete-during
smb/backup/ <dest>/backup/` for cold, then colder. Dry run first; if it would delete
anything, require the typed approval phrase, as today.

**Advocate rsync:** `rsync -Prv --size-only --delete-during cold_smb/advocate/
colder_smb/advocate/`, same dry run + approval guard.

**All rsyncs:** return code checked; non-zero stops the run and is reported with
stderr. The real run adds `--max-delete=N`, N = the number of `deleting` lines in
the dry run just approved (0 when none), so a source that changed in between
cannot delete more than was shown; rsync skips the excess and exits 25, which
stops the run (added after final review, approved by Sean). Each job re-probes
its hosts and re-checks its shares right before it runs.

## Builder's calls (Claude's, correctable)

- Script name `media_backup.py`; the two old scripts are removed (they stay in git
  history). A `justfile` with `just backup` and `just test`.
- Tests use stdlib `unittest`, with temp dirs and fake mount layouts; rsync and the
  port probe are injected so tests never touch the real shares.
- Every hard-coded path stays at the top of the script as a constant.

## Out of scope

- Cleaning up the 27 existing duplicate photo pairs (Sean, later, own tool).
- Switching timestamps to EXIF capture time.
- Repointing the YouTube downloader at `cold_smb/advocate` (Sean, after step 5).
