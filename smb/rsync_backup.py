import subprocess
import sys

del_string = "deleting "

destinations = ["/media/userhome/files/backup/", "/media/userhome/cold_smb/backup/"]


def run_rsync(destination: str, dry_run=True):
    command = [
        "rsync",
        "-Prv",
        "--size-only",
        "--delete-during",
        "--bwlimit=20480",
        "/media/userhome/smb/backup/",
        destination
    ]
    if dry_run:
        command.append("--dry-run")
    print(f"command is {command}")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout, result.stderr


def main():
    for destination in destinations:
        print(f"performing dry-run. destination is {destination}")
        stdout, stderr = run_rsync(destination=destination, dry_run=True)
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        if del_string in stdout:
            print(f"{del_string} located in stdout - verifying you actually want to delete")
            while True:
                user_input = input("Type 'I approve THESE files TO be DELETED' to proceed with deletion: ")
                if user_input == "I approve THESE files TO be DELETED":
                    print("Executing actual deletion...")
                    stdout, stderr = run_rsync(destination=destination, dry_run=False)
                    print(stdout)
                    break
                else:
                    print("Input did not match. Please type the approval text exactly as shown, or press CTRL+C to exit.")
        else:
            print("No files to delete. Running rsync without --dry-run.")
            stdout, stderr = run_rsync(destination=destination, dry_run=False)
            print(stdout)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        sys.exit()
