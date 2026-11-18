"""Set a new local password for an existing synthetic student; never use workbook hashes."""

import argparse
import getpass

from app.core.config import settings
from app.core.database import engine
from app.core.security import PASSWORDS
from app.models import Student, User
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id", help="An imported synthetic ID, e.g. STU0001")
    args = parser.parse_args()
    if settings().app_env != "development":
        raise SystemExit("This helper requires APP_ENV=development.")
    with Session(engine()) as db, db.begin():
        student = db.get(Student, args.student_id, with_for_update=True)
        if student is None or not student.synthetic:
            raise SystemExit("Synthetic student not found.")
        user = db.get(User, student.user_id, with_for_update=True)
        if user.active:
            raise SystemExit("That local demo account is already active.")
        password = getpass.getpass("New local demo password (at least 12 characters): ")
        if not 12 <= len(password) <= 256 or password != getpass.getpass("Confirm password: "):
            raise SystemExit("Password confirmation or length is invalid.")
        user.password_hash, user.active = PASSWORDS.hash(password), True
        email = user.email
    print(f"Local synthetic sign-in: {email}")


if __name__ == "__main__":
    main()
