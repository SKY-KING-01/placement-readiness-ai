from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import PASSWORDS, create_session, decode, dummy_hash
from app.models import RefreshSession, Student, User
from app.routers.dependencies import DB, CurrentUser, unauthorized
from app.schemas.auth import Login, Refresh, Register

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=201)
def register(data: Register, db: DB):
    email = data.email.lower()
    user = User(
        email=email,
        display_name=data.display_name,
        password_hash=PASSWORDS.hash(data.password),
        role="student",
    )
    db.add(user)
    try:
        db.flush()
        db.add(Student(user_id=user.id, department=data.department))
        tokens = create_session(db, user)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from error
    return tokens


@router.post("/login")
def login(data: Login, db: DB):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    valid = PASSWORDS.verify(
        data.password, user.password_hash if user and user.password_hash else dummy_hash()
    )
    if user is None or not user.active or not user.password_hash or not valid:
        raise unauthorized()
    tokens = create_session(db, user)
    db.commit()
    return tokens


@router.post("/refresh")
def refresh(data: Refresh, db: DB):
    try:
        claims = decode(data.refresh_token, "refresh")
    except jwt.InvalidTokenError as error:
        raise unauthorized() from error
    record = db.get(RefreshSession, claims["jti"], with_for_update=True)
    if (
        record is None
        or record.user_id != claims["sub"]
        or record.revoked
        or record.expires_at <= datetime.now(UTC)
    ):
        raise unauthorized()
    user = db.get(User, record.user_id)
    if user is None or not user.active:
        raise unauthorized()
    record.revoked = True
    tokens = create_session(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=204)
def logout(data: Refresh, db: DB, user: CurrentUser):
    try:
        claims = decode(data.refresh_token, "refresh")
    except jwt.InvalidTokenError:
        return
    record = db.get(RefreshSession, claims["jti"], with_for_update=True)
    if record and record.user_id == user.id:
        record.revoked = True
        db.commit()


@router.get("/me")
def me(user: CurrentUser):
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}
