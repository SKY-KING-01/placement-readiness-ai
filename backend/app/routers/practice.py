from statistics import fmean

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import (
    Assessment,
    AssessmentQuestion,
    Company,
    Question,
    QuestionCompanyTag,
    StudentResponse,
    TopicScore,
)
from app.routers.dependencies import DB, CurrentStudent, selected_role
from app.schemas.assessment import Answer, StartPractice
from app.services.adaptive import Candidate, rank
from app.services.assessments import (
    assessment_data,
    finalize,
    get_owned,
    next_assessment,
    public_question,
    record_answer,
    snapshot_question,
    topic_earned,
)
from app.services.history import active_weight_version, standardized, topic_weights

router = APIRouter(prefix="/practice", tags=["Adaptive practice"])


@router.post("/start", status_code=201)
def start(data: StartPractice, db: DB, student: CurrentStudent):
    if data.company_id and db.get(Company, data.company_id) is None:
        raise HTTPException(404, "Company not found")
    role_id = selected_role(db, student.id)
    item = next_assessment(
        db,
        student,
        role_id,
        "practice",
        status="open",
        source={
            "company_id": data.company_id,
            "max_questions": data.max_questions,
            "weight_version": active_weight_version(db, role_id),
        },
    )
    result = assessment_data(db, item)
    db.commit()
    return result


@router.get("/{key}/next-question")
def next_question(key: str, db: DB, student: CurrentStudent):
    item = get_owned(db, student, key, "practice", lock=True)
    if item.status != "open":
        return {"status": "complete", "question": None}
    assigned = db.execute(
        select(AssessmentQuestion, StudentResponse.option)
        .outerjoin(StudentResponse, StudentResponse.assessment_question_id == AssessmentQuestion.id)
        .where(AssessmentQuestion.assessment_id == key)
        .order_by(AssessmentQuestion.position)
    ).all()
    unanswered = next((q for q, option in assigned if option is None), None)
    if unanswered:
        return {"status": "open", "question": public_question(unanswered)}
    company = item.source["company_id"]
    tagged = (
        set(
            db.scalars(select(QuestionCompanyTag.question_id).where(QuestionCompanyTag.company_id == company))
        )
        if company
        else set()
    )
    prior = set(
        db.scalars(
            select(AssessmentQuestion.question_id)
            .join(Assessment, Assessment.id == AssessmentQuestion.assessment_id)
            .where(Assessment.student_id == student.id, Assessment.id != key)
        )
    )
    seen = {q.question_id for q, _ in assigned}
    history = standardized(db, student.id)
    readiness = (
        dict(
            db.execute(
                select(TopicScore.topic_id, TopicScore.score).where(
                    TopicScore.assessment_id == history[-1][0].id
                )
            ).all()
        )
        if history
        else {}
    )
    mastery = {topic: score / 100 for topic, score in readiness.items()}
    for topic, values in topic_earned(db, key).items():
        mastery[topic] = 0.7 * fmean(values) + 0.3 * mastery.get(topic, 0.5)
    weights = topic_weights(db, item.role_id, item.source["weight_version"])
    options = []
    for q in db.scalars(
        select(Question).where(
            Question.kind == "mcq",
            Question.status == "approved",
            Question.active,
            Question.subtopic_id.is_not(None),
            ((Question.role_id.is_(None)) | (Question.role_id == item.role_id)),
        )
    ).all():
        result = rank(
            Candidate(q.id, q.topic_id, q.difficulty, q.id in tagged), mastery, weights, prior, seen
        )
        if result:
            options.append((*result, q))
    if not options:
        if assigned:
            finalize(db, item)
            db.commit()
            return {"status": "complete", "question": None}
        raise HTTPException(409, "There are no approved practice questions")
    _, trace, best = min(options, key=lambda row: (not row[0][0], -row[0][1], row[2].id))
    question = snapshot_question(db, best, len(assigned) + 1, item, trace)
    result = public_question(question)
    db.commit()
    return {"status": "open", "question": result}


@router.post("/{key}/responses")
def answer(key: str, data: Answer, db: DB, student: CurrentStudent):
    item = get_owned(db, student, key, "practice", lock=True)
    earned = record_answer(db, item, data.question_id, data.option)
    assigned = len(
        db.scalars(select(AssessmentQuestion.id).where(AssessmentQuestion.assessment_id == key)).all()
    )
    if assigned >= item.source["max_questions"]:
        finalize(db, item)
    status = item.status
    db.commit()
    return {"correct": bool(earned), "status": "complete" if status == "submitted" else "open"}
