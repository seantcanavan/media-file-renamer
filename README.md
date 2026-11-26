# media-file-renamer
ios is bad at filenames so i'm automating it

`just backup` runs `media_backup.py`:

1. **Preflight.** Checks that each NAS answers on the SMB port and that every share
   it will touch is mounted and non-empty. A missing/empty share or an unreachable
   .248 stops everything before any rename or rsync.
2. **Rename** new media under `smb/backup/pictures` and
   `smb/backup/people/magnus/pictures` to `YYYY-MM-DD_HH-MM-SS_<name>.<ext>`.
   A photo dumped from the phone twice is deleted only if an already-renamed file
   in the same folder has the same original name, size and SHA-256. Anything else
   is kept and listed for review. No prompts.
3. **Backups**, each a dry run first; any deletion needs the typed approval phrase:

| Job                     | From                          | To                              |
|-------------------------|-------------------------------|---------------------------------|
| primary hot -> cold     | `smb/backup/` (.248)          | `cold_smb/backup/` (.248)       |
| primary hot -> colder   | `smb/backup/` (.248)          | `colder_smb/backup/` (.249)     |
| advocate cold -> colder | `cold_smb/advocate/` (.248)   | `colder_smb/advocate/` (.249)   |

.249 is usually powered off; jobs writing to it are skipped with a message and the
run still succeeds. `advocate` lives only on cold and colder, not on hot.

`just test` runs the unit tests (temp dirs only).
