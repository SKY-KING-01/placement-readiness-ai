"""Create a local staff account. Enter the initial password at the terminal prompt."""

import argparse
import getpass

from app.core.database import engine
from app.core.security import PASSWORDS
from app.models import Trainer, User
from sqlalchemy import select
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True, choices=("admin", "trainer", "placement"))
    args = parser.parse_args()
    password = getpass.getpass("Initial password (12 characters or more): ")
    if not 12 <= len(password) <= 256 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Password confirmation or length is invalid.")
    with Session(engine()) as db, db.begin():
        email = args.email.strip().lower()
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("An account with this email already exists.")
        user = User(
            email=email, display_name=args.name, password_hash=PASSWORDS.hash(password), role=args.role
        )
        db.add(user)
        db.flush()
        if args.role == "trainer":
            db.add(Trainer(user_id=user.id))
    print(f"Created {args.role} account.")


if __name__ == "__main__":
    main()
