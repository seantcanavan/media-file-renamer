import os
import re

# Function to increment the episode number
def increment_episode(filename, increment=-1):
    pattern = r"(Dragon Ball Kai - S\d{2}E)(\d{2})( - .+\.mkv)"
    match = re.match(pattern, filename)
    if match:
        prefix, episode, suffix = match.groups()
        new_episode_number = int(episode) + increment
        new_filename = f"{prefix}{str(new_episode_number).zfill(2)}{suffix}"
        return new_filename
    return filename

# Scan the current directory and rename files
def main():
    for filename in os.listdir('.'):
        new_filename = increment_episode(filename)
        if new_filename != filename:
            os.rename(filename, new_filename)
            print(f"Renamed '{filename}' to '{new_filename}'")

if __name__ == "__main__":
    main()
