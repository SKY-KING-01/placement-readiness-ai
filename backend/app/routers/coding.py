from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.models import CodingSubmission, CodingTestCase, Question, Student
from app.routers.dependencies import DB, CurrentStudent, Limit, Offset
from app.schemas.assessment import CodingSubmissionInput
from app.services.python_runner import execution_status

router = APIRouter(prefix="/coding", tags=["Python coding"])


def owned(db, key, student):
    row = db.scalar(
        select(CodingSubmission).where(CodingSubmission.id == key, CodingSubmission.student_id == student.id)
    )
    if row is None:
        raise HTTPException(404, "Submission not found")
    return row


def submission(row):
    return {
        key: getattr(row, key) for key in ("id", "question_id", "language", "status", "score", "created_at")
    }


@router.get("/questions")
def questions(db: DB, student: CurrentStudent, limit: Limit = 30, offset: Offset = 0):
    rows = db.scalars(
        select(Question)
        .where(
            Question.kind.in_(("python_io", "python_function")),
            Question.active,
            Question.status == "approved",
        )
        .order_by(Question.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "text": row.text,
            "kind": row.kind,
            "settings": row.settings,
            "samples": [
                {"inputs": c.inputs, "expected": c.expected}
                for c in db.scalars(
                    select(CodingTestCase).where(CodingTestCase.question_id == row.id, CodingTestCase.public)
                )
            ],
        }
        for row in rows
    ]


@router.post("/submissions", status_code=201)
def create(data: CodingSubmissionInput, db: DB, student: CurrentStudent):
    if len(data.code.encode()) > 32000 or not data.code.strip() or "\x00" in data.code:
        raise HTTPException(422, "Submit nonempty Python source up to 32 KB without NUL bytes")
    question = db.get(Question, data.question_id, with_for_update=True)
    if (
        not question
        or not question.active
        or question.status != "approved"
        or not question.kind.startswith("python")
    ):
        raise HTTPException(404, "Approved Python question not found")
    db.get(Student, student.id, with_for_update=True)
    count = db.scalar(
        select(func.count(CodingSubmission.id)).where(
            CodingSubmission.student_id == student.id,
            CodingSubmission.created_at > datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    if count >= 12:
        raise HTTPException(429, "Submission limit reached. Try again in a few minutes")
    row = CodingSubmission(
        student_id=student.id,
        question_id=question.id,
        code=data.code,
        status=execution_status(settings().python_execution_enabled),
    )
    db.add(row)
    db.flush()
    result = submission(row)
    db.commit()
    return result


@router.get("/submissions")
def history(db: DB, student: CurrentStudent, limit: Limit = 25, offset: Offset = 0):
    return [
        submission(row)
        for row in db.scalars(
            select(CodingSubmission)
            .where(CodingSubmission.student_id == student.id)
            .order_by(CodingSubmission.created_at.desc(), CodingSubmission.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/submissions/{key}")
def get(key: str, db: DB, student: CurrentStudent):
    row = owned(db, key, student)
    return {**submission(row), "code": row.code}


@router.post("/submissions/{key}/run-samples")
def run_samples(key: str, db: DB, student: CurrentStudent):
    owned(db, key, student)
    raise HTTPException(
        503,
        {
            "code": execution_status(settings().python_execution_enabled),
            "message": "No verified isolated Python worker is available. Submission was saved.",
        },
    )
