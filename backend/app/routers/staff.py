from collections import defaultdict
from datetime import UTC, datetime
from statistics import fmean
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.models import (
    Assessment,
    AssessmentTemplate,
    AuditLog,
    CareerRole,
    Company,
    MLModelVersion,
    Question,
    QuestionOption,
    QuestionReview,
    ReadinessScore,
    RoleSkillWeight,
    Skill,
    Student,
    Topic,
    TopicScore,
    Trainer,
    TrainerAssignment,
    User,
    WorkshopRecommendation,
    new_id,
)
from app.routers.dependencies import DB, Admin, Limit, Offset, require
from app.routers.students import progress_data
from app.schemas.common import Input
from app.services.catalog import blueprint, role_weight, stable_id
from app.services.history import topic_weights
from app.services.prediction import model_bundle
from app.services.scoring import READINESS_THRESHOLD, WEIGHT_VERSION

router = APIRouter(tags=["Institution and staff"])
TrainerUser = Annotated[User, Depends(require("trainer"))]
PlacementUser = Annotated[User, Depends(require("placement", "admin"))]


class Named(Input):
    name: str = Field(min_length=2, max_length=120)


class RoleStatus(Input):
    active: bool


class Assignment(Input):
    user_id: str = Field(min_length=1, max_length=80)
    student_id: str = Field(min_length=1, max_length=80)


class AccountChange(Input):
    role: Literal["student", "trainer", "placement", "admin"]
    active: bool


class WeightChange(Input):
    skill_id: str
    weight: Literal[0.3, 0.6, 1.0]


class Review(Input):
    detail: str = Field(min_length=5, max_length=2500)


def assignments(db, user):
    return (
        select(Student, User.display_name)
        .join(User, User.id == Student.user_id)
        .join(TrainerAssignment, TrainerAssignment.student_id == Student.id)
        .join(Trainer, Trainer.id == TrainerAssignment.trainer_id)
        .where(Trainer.user_id == user.id)
    )


@router.get("/trainers/students")
def assigned(db: DB, user: TrainerUser, limit: Limit = 30, offset: Offset = 0):
    return [
        {"id": s.id, "display_name": name, "department": s.department, "synthetic": s.synthetic}
        for s, name in db.execute(
            assignments(db, user).order_by(User.display_name, Student.id).limit(limit).offset(offset)
        )
    ]


@router.get("/trainers/students/{key}/analytics")
def student_analytics(key: str, db: DB, user: TrainerUser):
    result = db.execute(assignments(db, user).where(Student.id == key)).first()
    if result is None:
        raise HTTPException(404, "Assigned student not found")
    student, name = result
    trend = progress_data(db, student.id)
    trend["display_name"] = name
    trend["support_priority"] = (
        "assessment_needed"
        if not trend["latest"]
        else "review_skill_gaps"
        if trend["latest"]["score"] < READINESS_THRESHOLD
        else "continue"
    )
    return trend


@router.get("/trainers/questions")
def pending(db: DB, user: TrainerUser, limit: Limit = 25, offset: Offset = 0):
    rows = db.scalars(
        select(Question)
        .where(Question.status == "pending", Question.active)
        .order_by(Question.created_at, Question.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": q.id,
            "text": q.text,
            "category": q.category,
            "difficulty": q.difficulty,
            "options": [
                {"text": e.text, "correct": e.correct}
                for e in db.scalars(
                    select(QuestionOption)
                    .where(QuestionOption.question_id == q.id)
                    .order_by(QuestionOption.label)
                )
            ],
        }
        for q in rows
    ]


@router.post("/trainers/questions/{key}/reviews")
def review_question(key: str, data: Review, db: DB, user: TrainerUser):
    q = db.get(Question, key)
    if q is None or not q.active or q.status != "pending":
        raise HTTPException(404, "Pending question not found")
    db.add(QuestionReview(question_id=key, reviewer_id=user.id, action="feedback", detail=data.detail))
    db.commit()
    return {"saved": True}


def cohort(db, synthetic):
    ranked = (
        select(
            Assessment.id.label("key"),
            Assessment.student_id,
            Assessment.role_id,
            Assessment.taken_at,
            Assessment.attempt,
            ReadinessScore.score,
            ReadinessScore.version,
            ReadinessScore.coverage,
            func.row_number()
            .over(
                partition_by=Assessment.student_id,
                order_by=(Assessment.taken_at.desc(), Assessment.id.desc()),
            )
            .label("rank"),
        )
        .join(ReadinessScore, ReadinessScore.assessment_id == Assessment.id)
        .join(Student, Student.id == Assessment.student_id)
        .where(
            Assessment.synthetic == synthetic,
            Student.synthetic == synthetic,
            Assessment.mode.in_(("baseline", "standardized")),
            Assessment.status == "submitted",
            Assessment.taken_at <= datetime.now(UTC),
        )
        .subquery()
    )
    present = (
        db.execute(
            select(ranked, Student.department, CareerRole.name.label("role"))
            .join(Student, Student.id == ranked.c.student_id)
            .join(CareerRole, CareerRole.id == ranked.c.role_id)
            .where(ranked.c.rank == 1)
        )
        .mappings()
        .all()
    )
    return present, ranked


def summaries(rows, field, minimum):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row["score"])
    return [
        {
            "name": name,
            "students": len(values),
            "mean_score": round(fmean(values), 2),
            "readiness_rate": round(sum(v >= READINESS_THRESHOLD for v in values) / len(values), 3),
        }
        for name, values in sorted(groups.items())
        if len(values) >= minimum
    ]


@router.get("/placement/overview")
def overview(db: DB, user: PlacementUser, synthetic: bool = False):
    rows, ranked = cohort(db, synthetic)
    minimum = settings().min_cohort
    if len(rows) < minimum:
        return {"status": "cohort_suppressed", "minimum": minimum, "synthetic": synthetic}
    prior = {r.student_id: r for r in db.execute(select(ranked).where(ranked.c.rank == 2))}
    gains = []
    for row in rows:
        comparison = prior.get(row["student_id"])
        if (
            comparison
            and comparison.role_id == row["role_id"]
            and comparison.version == row["version"]
            and comparison.coverage.get("weights") == row["coverage"].get("weights")
        ):
            gains.append(row["score"] - comparison.score)
    series = db.execute(
        select(ranked.c.attempt, func.count(ranked.c.student_id.distinct()), func.avg(ranked.c.score))
        .group_by(ranked.c.attempt)
        .having(func.count(ranked.c.student_id.distinct()) >= minimum)
        .order_by(ranked.c.attempt)
    ).all()
    return {
        "status": "available",
        "students": len(rows),
        "synthetic": synthetic,
        "mean_score": round(fmean(r["score"] for r in rows), 2),
        "support_candidates": sum(r["score"] < READINESS_THRESHOLD for r in rows),
        "mean_reassessment_change": round(fmean(gains), 2) if len(gains) >= minimum else None,
        "departments": summaries(rows, "department", minimum),
        "roles": summaries(rows, "role", minimum),
        "trend": [{"attempt": i, "students": n, "mean_score": round(mean, 2)} for i, n, mean in series],
    }


def gaps(db, synthetic):
    rows, _ = cohort(db, synthetic)
    minimum = settings().min_cohort
    if len(rows) < minimum:
        return []
    by_assessment = {row["key"]: row for row in rows}
    known = {(row["role_id"], row["coverage"].get("weights", WEIGHT_VERSION)) for row in rows}
    weights = {key: topic_weights(db, *key) for key in known}
    topics = defaultdict(list)
    for a, key, name, score in db.execute(
        select(TopicScore.assessment_id, Topic.id, Topic.name, TopicScore.score)
        .join(Topic, Topic.id == TopicScore.topic_id)
        .where(TopicScore.assessment_id.in_(by_assessment))
    ):
        item = by_assessment[a]
        weight = weights[item["role_id"], item["coverage"].get("weights", WEIGHT_VERSION)].get(key, 0.3)
        topics[key, name].append((score, weight))
    result = [
        {
            "topic_id": key,
            "topic": name,
            "students": len(data),
            "weak_percent": round(100 * sum(score < READINESS_THRESHOLD for score, _ in data) / len(data), 2),
            "priority": round(
                fmean(max(0.0, READINESS_THRESHOLD - score) * weight for score, weight in data), 2
            ),
        }
        for (key, name), data in topics.items()
        if len(data) >= minimum
    ]
    return sorted(result, key=lambda item: (-item["priority"], item["topic"]))


@router.get("/placement/skill-gaps")
def skill_gaps(db: DB, user: PlacementUser, synthetic: bool = False):
    return gaps(db, synthetic)


@router.get("/placement/workshop-recommendations")
def workshops(db: DB, user: PlacementUser, synthetic: bool = False):
    recommendations = [item for item in gaps(db, synthetic) if item["priority"] > 0][:8]
    method = "synthetic-v1" if synthetic else "standardized-v1"
    for item in recommendations:
        statement = insert(WorkshopRecommendation).values(
            id=stable_id("workshop", item["topic_id"], method),
            topic_id=item["topic_id"],
            priority=item["priority"],
            participants=item["students"],
            method=method,
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["topic_id", "method"],
                set_={"priority": item["priority"], "participants": item["students"]},
            )
        )
    db.commit()
    return [
        {**item, "title": f"{item['topic']} practice workshop", "method": method} for item in recommendations
    ]


@router.get("/admin/users")
def users(db: DB, user: Admin, limit: Limit = 30, offset: Offset = 0):
    rows = db.execute(
        select(User, Student.id)
        .outerjoin(Student, Student.user_id == User.id)
        .order_by(User.created_at.desc(), User.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": account.id,
            "display_name": account.display_name,
            "email": account.email,
            "role": account.role,
            "active": account.active,
            "student_id": student_id,
        }
        for account, student_id in rows
    ]


@router.patch("/admin/users/{key}")
def account(key: str, data: AccountChange, db: DB, user: Admin):
    row = db.get(User, key, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Account not found")
    if key == user.id and (data.role != "admin" or not data.active):
        raise HTTPException(409, "Administrators cannot remove their own active access")
    if data.active and not row.password_hash:
        raise HTTPException(409, "An imported account needs a new credential before activation")
    if data.role == "student" and not db.scalar(select(Student.id).where(Student.user_id == key)):
        raise HTTPException(409, "This account has no student profile")
    row.role, row.active = data.role, data.active
    if data.role == "trainer" and not db.scalar(select(Trainer.id).where(Trainer.user_id == key)):
        db.add(Trainer(user_id=key))
    db.add(AuditLog(actor_id=user.id, action="account.changed", subject=key, details=data.model_dump()))
    db.commit()
    return {"saved": True}


@router.post("/admin/trainer-assignments", status_code=201)
def assign(data: Assignment, db: DB, user: Admin):
    trainer = db.scalar(
        select(Trainer)
        .join(User, Trainer.user_id == User.id)
        .where(Trainer.user_id == data.user_id, User.role == "trainer", User.active)
    )
    if trainer is None or not db.get(Student, data.student_id):
        raise HTTPException(404, "Active trainer or student not found")
    db.execute(
        insert(TrainerAssignment)
        .values(trainer_id=trainer.id, student_id=data.student_id)
        .on_conflict_do_nothing()
    )
    db.commit()
    return {"assigned": True}


@router.post("/admin/companies", status_code=201)
def company(data: Named, db: DB, user: Admin):
    db.execute(text("SELECT pg_advisory_xact_lock(820375)"))
    existing = db.scalar(select(Company.id).where(func.lower(Company.name) == data.name.lower()))
    if existing:
        return {"id": existing}
    row = Company(name=data.name)
    db.add(row)
    db.flush()
    identifier = row.id
    db.add(AuditLog(actor_id=user.id, action="company.created", subject=identifier))
    db.commit()
    return {"id": identifier}


@router.patch("/admin/companies/{key}")
def rename_company(key: str, data: Named, db: DB, user: Admin):
    db.execute(text("SELECT pg_advisory_xact_lock(820375)"))
    row = db.get(Company, key, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Company not found")
    duplicate = db.scalar(
        select(Company.id).where(Company.id != key, func.lower(Company.name) == data.name.lower())
    )
    if duplicate:
        raise HTTPException(409, "A company with this name already exists")
    row.name = data.name
    db.add(AuditLog(actor_id=user.id, action="company.renamed", subject=key))
    db.commit()
    return {"id": key, "name": data.name}


@router.get("/admin/roles")
def managed_roles(db: DB, user: Admin, limit: Limit = 50, offset: Offset = 0):
    return [
        {"id": row.id, "name": row.name, "active": row.active}
        for row in db.scalars(select(CareerRole).order_by(CareerRole.name).offset(offset).limit(limit))
    ]


@router.patch("/admin/roles/{key}")
def set_role_status(key: str, data: RoleStatus, db: DB, user: Admin):
    row = db.get(CareerRole, key, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Career role not found")
    row.active = data.active
    db.add(AuditLog(actor_id=user.id, action="role.status.changed", subject=key, details=data.model_dump()))
    db.commit()
    return {"id": key, "active": data.active}


@router.post("/admin/roles", status_code=201)
def add_role(data: Named, db: DB, user: Admin):
    db.execute(text("SELECT pg_advisory_xact_lock(820375)"))
    key = stable_id("role", data.name)
    if db.scalar(select(CareerRole.id).where(func.lower(CareerRole.name) == data.name.lower())):
        raise HTTPException(409, "Role already exists")
    db.add(CareerRole(id=key, name=data.name))
    db.flush()
    db.add(AssessmentTemplate(role_id=key, version="v1", blueprint=blueprint(data.name)))
    db.add_all(
        RoleSkillWeight(
            role_id=key, skill_id=skill.id, version=WEIGHT_VERSION, weight=role_weight(data.name, skill.name)
        )
        for skill in db.scalars(select(Skill))
    )
    db.commit()
    return {"id": key}


@router.patch("/admin/roles/{key}/weights")
def update_weight(key: str, data: WeightChange, db: DB, user: Admin):
    role = db.get(CareerRole, key, with_for_update=True)
    if role is None or db.get(Skill, data.skill_id) is None:
        raise HTTPException(404, "Role or skill not found")
    template = db.scalar(
        select(AssessmentTemplate)
        .where(AssessmentTemplate.role_id == key, AssessmentTemplate.active)
        .order_by(AssessmentTemplate.created_at.desc(), AssessmentTemplate.id.desc())
        .limit(1)
    )
    if template is None:
        raise HTTPException(409, "Role needs a baseline blueprint")
    old_version = template.blueprint["weight_version"]
    old = db.scalars(
        select(RoleSkillWeight).where(RoleSkillWeight.role_id == key, RoleSkillWeight.version == old_version)
    ).all()
    version = "weights-" + new_id()[:16]
    values = {row.skill_id: row.weight for row in old} | {data.skill_id: float(data.weight)}
    db.add_all(
        RoleSkillWeight(role_id=key, skill_id=skill_id, version=version, weight=weight)
        for skill_id, weight in values.items()
    )
    template.active = False
    db.add(
        AssessmentTemplate(
            role_id=key, version=version, blueprint=dict(template.blueprint, weight_version=version)
        )
    )
    db.add(
        AuditLog(actor_id=user.id, action="role.weights.changed", subject=key, details={"version": version})
    )
    db.commit()
    return {"version": version}


@router.get("/admin/model-versions")
def models(db: DB, user: Admin, limit: Limit = 30, offset: Offset = 0):
    local = {}
    for task in ("classification", "regression"):
        model = model_bundle(task)
        if model:
            local[model[0]["model_id"]] = model[0]
    rows = db.scalars(
        select(MLModelVersion).order_by(MLModelVersion.created_at.desc()).offset(offset).limit(limit)
    )
    return list((local | {r.id: r.metadata_json for r in rows}).values())
