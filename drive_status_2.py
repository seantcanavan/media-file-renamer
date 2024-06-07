import subprocess
import time
import re
from datetime import datetime


def get_smart_test_progress(drive):
    try:
        # Execute the smartctl command
        print(f"drive is {drive}")
        result = subprocess.run(['smartctl', '-c', drive], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Check if the command was successful
        if result.returncode != 0:
            print(f"result is {result}")
            print(f"Error: {result.stderr.strip()}")
            return None
        
        # Parse the output for the remaining percentage
        output = result.stdout
        match = re.search(r'Self-test execution status:\s+\(\s*\d+\)\s+Self-test routine in progress\.\.\.\s+(\d+)% of test remaining\.', output)
        if match:
            return int(match.group(1))
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def main():
#    letters = ['b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p']
    letters = ['a']
    while len(letters) > 0:
        to_remove = []
        for letter in letters:
            drive = "/dev/sd" + letter
            remaining_percentage = get_smart_test_progress(drive)
            if remaining_percentage is None:
                to_remove.append(letter)

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if remaining_percentage is not None:
                print(f"{current_time} - {remaining_percentage}% of test remaining of drive {drive}.")
            time.sleep(1)
        for remove in to_remove:
            letters.remove(remove)
        print("-------------------------------------------------------------")

if __name__ == "__main__":
    main()
