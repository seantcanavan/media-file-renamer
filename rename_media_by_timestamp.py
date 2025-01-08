import datetime
import os
import re  # Import the regular expressions library
from pathlib import Path

# Define the directory to start from
start_directories = [Path('/media/userhome/smb/backup/pictures'), Path('/media/userhome/smb/backup/people/magnus/pictures')]

# Define common multimedia file extensions in lower case
MEDIA_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.avi', '.mov', '.mkv', '.heic', '.mov', '.bmp', '.tif', '.tiff', '.bmp2', '.tiff2', '.aae']


def format_timestamp(timestamp):
    """Format the timestamp to a lexicographically sortable string."""
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d_%H-%M-%S')


def timestamp_prefix_exists(filename):
    """Check if the filename already starts with a timestamp."""
    pattern = r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}'  # Pattern for matching the timestamp
    return re.match(pattern, filename) is not None


def rename_files(directory):
    """Recursively rename files with a timestamp prefix, ensure lower-cased extension, and skip if the new filename exists."""
    for existing_path in directory.rglob('*'):  # rglob method for recursive globbing
        if existing_path.is_file() and existing_path.suffix.lower() in MEDIA_EXTENSIONS:
            if not timestamp_prefix_exists(existing_path.name):  # Check if filename starts with timestamp
                existing_created_time = existing_path.stat().st_ctime
                formatted_timestamp = format_timestamp(existing_created_time)
                name_without_extension, extension = os.path.splitext(existing_path.name)
                renamed_name = f"{formatted_timestamp}_{name_without_extension}{extension.lower()}"
                renamed_path = existing_path.parent / renamed_name
                if renamed_path.exists():
                    existing_size = os.path.getsize(existing_path)
                    renamed_size = os.path.getsize(renamed_path)
                    print(f"existing_path {existing_path} has duplicate target for renamed_path: {renamed_path}.")
                    print(f"existing size: {existing_size} - renamed size: {renamed_size}.")
                    if existing_size == renamed_size:
                        print(f"Sizes are identical: existing: {existing_size} and renamed: {renamed_size}. Deleting existing: {existing_path}.")
                        os.remove(existing_path)
                    else:
                        delete_existing_input = "eXiStInG"
                        delete_renamed_input = "rEnAmEd"
                        delete_duplicate_input = input(f"Enter {delete_existing_input} to delete existing. Enter {delete_renamed_input} to delete renamed.")
                        if delete_duplicate_input == delete_existing_input:
                            print(f"Deleting existing: {existing_path}.")
                            os.remove(existing_path)
                        elif delete_renamed_input == delete_renamed_input:
                            print(f"Deleting renamed: {renamed_path}.")
                            os.remove(renamed_path)
                            print(f"Renaming {existing_path} to {renamed_path}")
                            os.rename(existing_path, renamed_path)
                        else:
                            raise ValueError("Deletion of renamed file failed.")
                else:
                    print(f"Renaming {existing_path} to {renamed_path}")
                    os.rename(existing_path, renamed_path)


# Run the script
if __name__ == '__main__':
    rename_files(start_directories[0])  # rename my photos
    rename_files(start_directories[1])  # rename magnus photos
