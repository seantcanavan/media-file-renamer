default:
    @just --list

# run the unit tests (temp dirs only, never touches /media)
test:
    python -m unittest discover -s tests -t . -v

# one-time migration proof: sha256 every advocate file on hot, cold and colder (read-only, hours)
verify-advocate:
    python verify_copies.py \
        --source /media/userhome/smb/backup/people/sean/advocate \
        --copy cold=/media/userhome/cold_smb/advocate \
        --copy colder=/media/userhome/colder_smb/advocate \
        --manifest-dir ~/advocate-manifests

# rename new photos on hot, then back up hot -> cold -> colder and advocate cold -> colder
backup:
    python media_backup.py
