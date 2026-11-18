from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from sqlalchemy import select, text

from app.models import (
    AuditLog,
    CodingSubmission,
    CodingTestCase,
    Company,
    Question,
    QuestionCompanyTag,
    QuestionImportBatch,
    QuestionOption,
    QuestionReview,
    Skill,
    Subtopic,
    Topic,
)
from app.routers.dependencies import DB, Admin, CurrentUser, Limit, Offset
from app.schemas.questions import QuestionInput
from app.services.questions import MAX_UPLOAD_BYTES, inspect_import, save_question

router = APIRouter(tags=["Question bank"])


def question_details(db, row):
    options = db.scalars(
        select(QuestionOption).where(QuestionOption.question_id == row.id).order_by(QuestionOption.label)
    ).all()
    companies = list(
        db.scalars(select(QuestionCompanyTag.company_id).where(QuestionCompanyTag.question_id == row.id))
    )
    cases = db.scalars(select(CodingTestCase).where(CodingTestCase.question_id == row.id)).all()
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "text",
            "kind",
            "category",
            "difficulty",
            "topic_id",
            "subtopic_id",
            "skill_id",
            "role_id",
            "year",
            "placement_round",
            "source_url",
            "verification",
            "explanation",
            "status",
            "active",
        )
    } | {
        "company_ids": companies,
        "options": [opt.text for opt in options],
        "answer": next((i for i, opt in enumerate(options) if opt.correct), None),
        "cases": [
            {"public": c.public, "inputs": c.inputs, "expected": c.expected, "weight": c.weight}
            for c in cases
        ],
        **row.settings,
    }


@router.get("/companies")
def companies(db: DB, user: CurrentUser):
    return [
        {"id": row.id, "name": row.name}
        for row in db.scalars(select(Company).order_by(Company.name).limit(100))
    ]


@router.get("/admin/catalog")
def catalog(db: DB, user: Admin):
    return {
        "topics": [{"id": t.id, "name": t.name} for t in db.scalars(select(Topic).order_by(Topic.name))],
        "subtopics": [
            {"id": s.id, "name": s.name, "topic_id": s.topic_id}
            for s in db.scalars(select(Subtopic).order_by(Subtopic.name))
        ],
        "skills": [{"id": s.id, "name": s.name, "topic_id": s.topic_id} for s in db.scalars(select(Skill))],
    }


@router.get("/admin/questions")
def list_questions(
    db: DB,
    user: Admin,
    limit: Limit = 30,
    offset: Offset = 0,
    q: str = Query(default="", max_length=120),
    status: str | None = None,
):
    statement = select(Question)
    if q:
        statement = statement.where(Question.text.icontains(q, autoescape=True))
    if status:
        statement = statement.where(Question.status == status)
    return [
        question_details(db, item)
        for item in db.scalars(
            statement.order_by(Question.created_at.desc(), Question.id).offset(offset).limit(limit)
        )
    ]


@router.post("/admin/questions", status_code=201)
def create(data: QuestionInput, db: DB, user: Admin):
    db.execute(text("SELECT pg_advisory_xact_lock(820374)"))
    try:
        item = save_question(db, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.add(AuditLog(actor_id=user.id, action="question.created", subject=item.id))
    result = question_details(db, item)
    db.commit()
    return result


@router.patch("/admin/questions/{key}")
def edit(key: str, data: QuestionInput, db: DB, user: Admin):
    db.execute(text("SELECT pg_advisory_xact_lock(820374)"))
    item = db.get(Question, key, with_for_update=True)
    if item is None:
        raise HTTPException(404, "Question not found")
    if db.scalar(select(CodingSubmission.id).where(CodingSubmission.question_id == key).limit(1)):
        raise HTTPException(409, "Create a new version of this coding question to preserve submissions")
    try:
        save_question(db, data, item)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    db.add(AuditLog(actor_id=user.id, action="question.edited", subject=item.id))
    result = question_details(db, item)
    db.commit()
    return result


@router.post("/admin/questions/{key}/deactivate")
def deactivate(key: str, db: DB, user: Admin):
    item = db.get(Question, key, with_for_update=True)
    if item is None:
        raise HTTPException(404, "Question not found")
    item.active = False
    db.add(AuditLog(actor_id=user.id, action="question.deactivated", subject=key))
    db.commit()
    return {"active": False}


@router.post("/admin/questions/{key}/approve")
def approve(key: str, db: DB, user: Admin):
    item = db.get(Question, key, with_for_update=True)
    if item is None:
        raise HTTPException(404, "Question not found")
    if item.status == "quarantined" or not item.active:
        raise HTTPException(409, "Correct quarantined content and activate the question before approval")
    if item.status != "approved":
        item.status = "approved"
        db.add(
            QuestionReview(
                question_id=key,
                reviewer_id=user.id,
                action="approved",
                detail="Administrator recorded approval",
            )
        )
        db.add(AuditLog(actor_id=user.id, action="question.approved", subject=key))
        db.commit()
    return {"status": "approved"}


@router.post("/admin/questions/import")
def import_questions(file: UploadFile, db: DB, user: Admin, preview: bool = True):
    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    filename = Path(file.filename or "questions.csv").name[:255]
    if not preview:
        db.execute(text("SELECT pg_advisory_xact_lock(820374)"))
    records, report = inspect_import(db, filename, contents)
    if preview:
        return {**report, "preview": True, "examples": [q.text for q in records[:10]]}
    batch = QuestionImportBatch(filename=filename, digest=report["digest"], user_id=user.id, report=report)
    db.add(batch)
    db.flush()
    for item in records:
        save_question(db, item, batch_id=batch.id)
    db.add(
        AuditLog(
            actor_id=user.id,
            action="question.import",
            subject=batch.id,
            details={"valid": report["valid"], "invalid": report["invalid"]},
        )
    )
    key = batch.id
    db.commit()
    return {**report, "batch_id": key, "status": "pending_approval"}
