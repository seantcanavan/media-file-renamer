default:
    @just --list

# run the unit tests (temp dirs only, never touches /media)
test:
    python -m unittest discover -s tests -t . -v

# rename new photos on hot, then back up hot -> cold -> colder and advocate cold -> colder
backup:
    python media_backup.py
