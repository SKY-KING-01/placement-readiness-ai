from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.models import RefreshSession, User, new_id

PASSWORDS = PasswordHash.recommended()
ISSUER = "placement-readiness"
ACCESS_LIFETIME = timedelta(minutes=20)
REFRESH_LIFETIME = timedelta(days=7)


@lru_cache
def dummy_hash():
    return PASSWORDS.hash(new_id())


def secret():
    key = settings().jwt_secret_key.get_secret_value()
    if len(key.encode()) < 32:
        raise RuntimeError("Set JWT_SECRET_KEY to a random secret of at least 32 bytes.")
    return key


def encode(subject, purpose, life, identifier):
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": subject, "typ": purpose, "iss": ISSUER, "iat": now, "exp": now + life, "jti": identifier},
        secret(),
        algorithm="HS256",
    )


def decode(token, purpose):
    payload = jwt.decode(
        token,
        secret(),
        algorithms=["HS256"],
        issuer=ISSUER,
        options={"require": ["exp", "iat", "sub", "iss", "jti", "typ"]},
    )
    if payload["typ"] != purpose or not isinstance(payload["jti"], str):
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def create_session(db, user: User):
    identifier = new_id()
    db.add(RefreshSession(id=identifier, user_id=user.id, expires_at=datetime.now(UTC) + REFRESH_LIFETIME))
    return {
        "access_token": encode(user.id, "access", ACCESS_LIFETIME, new_id()),
        "refresh_token": encode(user.id, "refresh", REFRESH_LIFETIME, identifier),
        "token_type": "bearer",
    }
