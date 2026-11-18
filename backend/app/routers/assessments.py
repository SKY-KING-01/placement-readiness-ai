from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import Assessment, AssessmentTemplate, Student
from app.routers.dependencies import DB, CurrentStudent, Limit, Offset, selected_role
from app.schemas.assessment import Answer, StartAssessment
from app.services import roadmap
from app.services.assessments import (
    activate,
    assessment_data,
    finalize,
    get_owned,
    next_assessment,
    record_answer,
    results,
    select_standard,
)

router = APIRouter(prefix="/assessments", tags=["Assessments"])


@router.get("")
def list_assessments(db: DB, student: CurrentStudent, limit: Limit = 20, offset: Offset = 0):
    rows = db.scalars(
        select(Assessment)
        .where(Assessment.student_id == student.id, Assessment.mode == "standardized")
        .order_by(Assessment.attempt.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        {
            "id": a.id,
            "attempt": a.attempt,
            "status": a.status,
            "scheduled_at": a.scheduled_at,
            "taken_at": a.taken_at,
        }
        for a in rows
    ]


@router.post("", status_code=201)
def start(data: StartAssessment, db: DB, student: CurrentStudent):
    db.get(Student, student.id, with_for_update=True)
    role_id = selected_role(db, student.id)
    template = db.scalar(
        select(AssessmentTemplate)
        .where(AssessmentTemplate.role_id == role_id, AssessmentTemplate.active)
        .order_by(AssessmentTemplate.created_at.desc(), AssessmentTemplate.id.desc())
        .limit(1)
    )
    if template is None:
        raise HTTPException(409, "This role has no active assessment blueprint")
    scheduled = data.scheduled_at is not None
    if scheduled and data.scheduled_at <= datetime.now(UTC):
        raise HTTPException(422, "Choose a future date for the reassessment")
    if not scheduled:
        existing = db.scalar(
            select(Assessment)
            .where(
                Assessment.student_id == student.id,
                Assessment.mode == "standardized",
                Assessment.status == "open",
            )
            .order_by(Assessment.attempt.desc())
            .limit(1)
        )
        if existing:
            return assessment_data(db, existing)
    item = next_assessment(
        db,
        student,
        role_id,
        "standardized",
        template_id=template.id,
        scheduled_at=data.scheduled_at,
        status="scheduled" if scheduled else "open",
        source={"weight_version": template.blueprint["weight_version"]},
    )
    if not scheduled:
        select_standard(db, item, template)
    data = assessment_data(db, item)
    db.commit()
    return data


@router.get("/{key}")
def get(key: str, db: DB, student: CurrentStudent):
    return assessment_data(db, get_owned(db, student, key, "standardized"))


@router.post("/{key}/activate")
def start_scheduled(key: str, db: DB, student: CurrentStudent):
    item = get_owned(db, student, key, "standardized", lock=True)
    activate(db, item)
    data = assessment_data(db, item)
    db.commit()
    return data


@router.post("/{key}/responses")
def answer(key: str, data: Answer, db: DB, student: CurrentStudent):
    item = get_owned(db, student, key, "standardized", lock=True)
    record_answer(db, item, data.question_id, data.option)
    db.commit()
    return {"saved": True}


@router.post("/{key}/submit")
def submit(key: str, db: DB, student: CurrentStudent):
    item = get_owned(db, student, key, "standardized", lock=True)
    was_open = item.status == "open"
    finalize(db, item)
    if was_open:
        previous = roadmap.latest(db, student.id)
        hours = previous.content.get("weekly_hours", 5) if previous else 5
        roadmap.create(db, student, hours, use_openai=False)
    data = results(db, item)
    db.commit()
    return data


@router.get("/{key}/results")
def get_results(key: str, db: DB, student: CurrentStudent):
    return results(db, get_owned(db, student, key, "standardized"))
