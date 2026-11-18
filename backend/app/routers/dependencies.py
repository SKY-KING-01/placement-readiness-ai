from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import database
from app.core.security import decode
from app.models import CareerProfile, CareerRole, Student, User

DB = Annotated[Session, Depends(database)]
Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]


def unauthorized():
    return HTTPException(
        401, "Invalid credentials or expired session", headers={"WWW-Authenticate": "Bearer"}
    )


def current_user(db: DB, credential: Bearer):
    if credential is None:
        raise unauthorized()
    try:
        claims = decode(credential.credentials, "access")
    except jwt.InvalidTokenError as error:
        raise unauthorized() from error
    user = db.get(User, claims["sub"])
    if user is None or not user.active:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require(*roles):
    def dependency(user: CurrentUser):
        if user.role not in roles:
            raise HTTPException(403, "This action requires a different account role")
        return user

    return dependency


def current_student(db: DB, user: Annotated[User, Depends(require("student"))]):
    student = db.scalar(select(Student).where(Student.user_id == user.id))
    if student is None:
        raise HTTPException(404, "Student profile unavailable")
    return student


CurrentStudent = Annotated[Student, Depends(current_student)]
Admin = Annotated[User, Depends(require("admin"))]


def selected_role(db, student_id):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.student_id == student_id))
    if profile is None:
        raise HTTPException(409, "Select a career role first")
    if not db.get(CareerRole, profile.role_id).active:
        raise HTTPException(409, "Select an active career role")
    return profile.role_id
