from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import CareerProfile, CareerRole, RoleSkillWeight, Skill, Student
from app.routers.dependencies import DB, CurrentStudent, CurrentUser, Limit, Offset
from app.schemas.common import Input
from app.services.history import active_weight_version, detailed_scores, standardized

router = APIRouter(tags=["Students and roles"])


class RoleInput(Input):
    role_id: str


@router.get("/roles")
def roles(db: DB, user: CurrentUser, limit: Limit = 50, offset: Offset = 0):
    return [
        {"id": row.id, "name": row.name}
        for row in db.scalars(
            select(CareerRole).where(CareerRole.active).order_by(CareerRole.name).offset(offset).limit(limit)
        )
    ]


@router.get("/roles/{role_id}/skills")
def skills(role_id: str, db: DB, user: CurrentUser):
    if db.get(CareerRole, role_id) is None:
        raise HTTPException(404, "Career role not found")
    version = active_weight_version(db, role_id)
    rows = db.execute(
        select(Skill.id, Skill.name, RoleSkillWeight.weight)
        .join(RoleSkillWeight, RoleSkillWeight.skill_id == Skill.id)
        .where(RoleSkillWeight.role_id == role_id, RoleSkillWeight.version == version)
        .order_by(RoleSkillWeight.weight.desc(), Skill.name)
    )
    return [{"id": key, "name": name, "weight": weight, "version": version} for key, name, weight in rows]


def student_data(db, student):
    role = db.execute(
        select(CareerRole.id, CareerRole.name)
        .join(CareerProfile, CareerProfile.role_id == CareerRole.id)
        .where(CareerProfile.student_id == student.id)
    ).first()
    return {
        "id": student.id,
        "department": student.department,
        "synthetic": student.synthetic,
        "career_role": {"id": role.id, "name": role.name} if role else None,
    }


@router.get("/students/me")
def profile(db: DB, student: CurrentStudent):
    return student_data(db, student)


@router.put("/students/me/role")
def change_role(data: RoleInput, db: DB, student: CurrentStudent):
    role = db.get(CareerRole, data.role_id)
    if role is None or not role.active:
        raise HTTPException(404, "Career role not found")
    db.get(Student, student.id, with_for_update=True)
    profile = db.scalar(select(CareerProfile).where(CareerProfile.student_id == student.id))
    if profile:
        profile.role_id = role.id
    else:
        db.add(CareerProfile(student_id=student.id, role_id=role.id))
    db.commit()
    return student_data(db, student)


def progress_data(db, student_id):
    rows = standardized(db, student_id)
    history = [
        {
            "assessment_id": item.id,
            "date": item.taken_at,
            "score": score.score,
            "role": role,
            "attempt": item.attempt,
            "synthetic": item.synthetic,
            "scoring_version": score.version,
        }
        for item, score, role in rows
    ]
    return {
        "history": history,
        "latest": history[-1] if history else None,
        "topics": detailed_scores(db, rows[-1][0].id) if rows else [],
    }


@router.get("/students/me/progress")
def progress(db: DB, student: CurrentStudent):
    return progress_data(db, student.id)
