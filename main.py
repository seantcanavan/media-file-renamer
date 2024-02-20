import datetime
import os
import re  # Import the regular expressions library
from pathlib import Path

# Define the directory to start from
start_directory = Path('/media/userhome/media/test_pics_backup')

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
    """Recursively rename files with a timestamp prefix, if not already present, and ensure lower-cased extension."""
    for item in directory.rglob('*'):  # rglob method for recursive globbing
        if item.is_file() and item.suffix.lower() in MEDIA_EXTENSIONS:
            if not timestamp_prefix_exists(item.name):  # Check if filename starts with timestamp
                creation_time = item.stat().st_ctime
                formatted_timestamp = format_timestamp(creation_time)
                # Split the filename from its extension and convert the extension to lowercase
                name_without_extension, extension = os.path.splitext(item.name)
                new_name = f"{formatted_timestamp}_{name_without_extension}{extension.lower()}"
                new_path = item.parent / new_name
                print(f"Renaming {item} to {new_path}")
                os.rename(item, new_path)
            else:
                print(f"Skipping {item}, already has timestamp.")


# Run the script
if __name__ == '__main__':
    rename_files(start_directory)
