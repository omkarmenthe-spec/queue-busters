import json
import secrets
from getpass import getpass
from pathlib import Path

from werkzeug.security import generate_password_hash


def main():
    folder = Path(__file__).resolve().parent / "instance"
    folder.mkdir(exist_ok=True)
    config_file = folder / "staff_config.json"

    if config_file.exists():
        answer = input(
            "Replace the existing staff password and invalidate old logins? "
            "Type yes to continue: "
        ).strip().lower()

        if answer != "yes":
            print("No changes made.")
            return

    print("Create a demo-only staff password.")
    print("Use at least 12 characters. Do not reuse a personal password.")

    while True:
        password = getpass("New staff password: ")

        if len(password) < 12:
            print("Please use at least 12 characters.")
            continue

        confirmation = getpass("Confirm password: ")

        if password != confirmation:
            print("Passwords did not match. Try again.")
            continue

        break

    configuration = {
        "secret_key": secrets.token_hex(32),
        "password_hash": generate_password_hash(password),
    }

    config_file.write_text(
        json.dumps(configuration, indent=2),
        encoding="utf-8",
    )

    print("\nStaff password saved as a hash.")
    print("Restart the application before using the new password.")
    print("Keep instance/staff_config.json private and out of Git.")


if __name__ == "__main__":
    main()