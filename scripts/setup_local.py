"""Create an untracked local environment file and generate a JWT signing secret."""

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / ".env"
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    content = template.replace("JWT_SECRET_KEY=\n", f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}\n", 1)
    try:
        with os.fdopen(
            os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8"
        ) as file:
            file.write(content)
    except FileExistsError:
        print("A local .env already exists. Its settings were preserved.")
        return
    print("Created .env. Set DATABASE_URL to your local PostgreSQL connection.")


if __name__ == "__main__":
    main()
