from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .config import settings


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True)


def database():
    with Session(engine()) as session:
        yield session
