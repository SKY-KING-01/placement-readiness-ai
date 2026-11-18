import os
import secrets
from pathlib import Path

import pytest
from alembic.config import Config
from scripts.import_source_data import import_source
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import settings
from app.core.database import engine

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def postgres():
    uri = os.getenv("PLACEMENT_TEST_DATABASE_URL")
    if not uri:
        pytest.skip("Set PLACEMENT_TEST_DATABASE_URL to a native PostgreSQL test server")
    parent = create_engine(uri, isolation_level="AUTOCOMMIT")
    schema = "placement_test_" + secrets.token_hex(7)
    with parent.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    patch = pytest.MonkeyPatch()
    url = make_url(uri).update_query_dict({"options": "-csearch_path=" + schema})
    patch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    patch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(48))
    patch.setenv("OPENAI_API_KEY", "")
    patch.setenv("PYTHON_EXECUTION_ENABLED", "false")
    patch.setenv("SYNTHETIC_DEMO_PREDICTIONS", "true")
    settings.cache_clear()
    engine.cache_clear()
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
        with Session(engine()) as session, session.begin():
            first = import_source(session)
        with Session(engine()) as session, session.begin():
            second = import_source(session)
        yield engine(), first, second
    finally:
        engine().dispose()
        engine.cache_clear()
        settings.cache_clear()
        patch.undo()
        with parent.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        parent.dispose()


@pytest.fixture
def client(postgres):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
