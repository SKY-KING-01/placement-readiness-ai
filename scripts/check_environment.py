"""Check installed runtimes, local PostgreSQL and project configuration without printing secrets."""

import shutil
import sys

from app.core.config import settings
from app.core.database import engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def main():
    config = settings()
    checks = {
        "Python 3.11+": sys.version_info >= (3, 11),
        "Node available": shutil.which("node") is not None,
        "JWT signing secret configured": len(config.jwt_secret_key.get_secret_value().encode()) >= 32,
    }
    try:
        with engine().connect() as connection:
            version = connection.execute(text("SHOW server_version")).scalar_one()
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            checks[f"PostgreSQL {version} migrated ({revision})"] = revision is not None
    except SQLAlchemyError:
        checks["Native PostgreSQL connection and migrated schema"] = False
    for label, ok in checks.items():
        print(("OK " if ok else "CHECK ") + label)
    print(
        "Roadmap: "
        + (
            "OpenAI configured"
            if config.openai_api_key.get_secret_value() and config.openai_model
            else "deterministic fallback"
        )
    )
    print("Python runner: no verified worker available")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
