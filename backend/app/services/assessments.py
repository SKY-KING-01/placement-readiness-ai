import hashlib
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentTemplate,
    Question,
    QuestionOption,
    ReadinessScore,
    Student,
    StudentResponse,
    SubtopicScore,
    TopicScore,
)
from app.services.history import detailed_scores, topic_weights
from app.services.scoring import READINESS_THRESHOLD, SCORING_VERSION, response_scores


def get_owned(db, student, key, mode, lock=False):
    stmt = select(Assessment).where(
        Assessment.id == key, Assessment.student_id == student.id, Assessment.mode == mode
    )
    item = db.scalar(stmt.with_for_update() if lock else stmt)
    if item is None:
        raise HTTPException(404, "Assessment not found")
    return item


def next_assessment(db, student, role_id, mode, **values):
    db.get(Student, student.id, with_for_update=True)
    attempt = (
        db.scalar(
            select(func.max(Assessment.attempt)).where(
                Assessment.student_id == student.id, Assessment.mode == mode
            )
        )
        or 0
    )
    item = Assessment(
        student_id=student.id,
        role_id=role_id,
        mode=mode,
        attempt=attempt + 1,
        synthetic=student.synthetic,
        **values,
    )
    db.add(item)
    db.flush()
    return item


def snapshot_question(db, question, position, assessment, selection=None):
    options = db.scalars(
        select(QuestionOption).where(QuestionOption.question_id == question.id).order_by(QuestionOption.label)
    ).all()
    if not options or sum(item.correct for item in options) != 1:
        raise HTTPException(409, "Question must have exactly one reviewed answer")
    item = AssessmentQuestion(
        assessment_id=assessment.id,
        question_id=question.id,
        position=position,
        snapshot={
            "text": question.text,
            "topic_id": question.topic_id,
            "subtopic_id": question.subtopic_id,
            "difficulty": question.difficulty,
            "options": [{"label": opt.label, "text": opt.text} for opt in options],
            "answer": next(opt.label for opt in options if opt.correct),
        },
        selection=selection or {},
    )
    db.add(item)
    db.flush()
    return item


def public_question(item):
    snap = item.snapshot
    return {
        "id": item.id,
        "position": item.position,
        "text": snap["text"],
        "difficulty": snap["difficulty"],
        "options": snap["options"],
    }


def assessment_data(db, item):
    joins = db.execute(
        select(AssessmentQuestion, StudentResponse.option)
        .outerjoin(StudentResponse, StudentResponse.assessment_question_id == AssessmentQuestion.id)
        .where(AssessmentQuestion.assessment_id == item.id)
        .order_by(AssessmentQuestion.position)
    )
    return {
        "id": item.id,
        "mode": item.mode,
        "attempt": item.attempt,
        "status": item.status,
        "scheduled_at": item.scheduled_at,
        "questions": [{**public_question(q), "selected": option} for q, option in joins],
    }


def select_standard(db, item, template):
    if template is None or not template.blueprint.get("sections"):
        raise HTTPException(409, "This role has no active assessment blueprint")
    previous = set(
        db.scalars(
            select(AssessmentQuestion.question_id)
            .join(Assessment, Assessment.id == AssessmentQuestion.assessment_id)
            .where(Assessment.student_id == item.student_id, Assessment.mode == "standardized")
        )
    )
    chosen = []
    for section in template.blueprint["sections"]:
        for level in section["levels"]:
            candidates = db.scalars(
                select(Question).where(
                    Question.topic_id == section["topic_id"],
                    Question.kind == "mcq",
                    Question.difficulty == level,
                    Question.status == "approved",
                    Question.active,
                    Question.subtopic_id.is_not(None),
                    ((Question.role_id.is_(None)) | (Question.role_id == item.role_id)),
                )
            ).all()
            available = [q for q in candidates if q.id not in {selected.id for selected in chosen}]
            if not available:
                raise HTTPException(409, "The question bank cannot satisfy this blueprint")
            selected = min(
                available,
                key=lambda q: (
                    q.id in previous,
                    hashlib.sha256(f"{item.student_id}:{item.attempt}:{q.id}".encode()).hexdigest(),
                ),
            )
            chosen.append(selected)
    for position, question in enumerate(chosen, 1):
        snapshot_question(db, question, position, item, {"blueprint": template.version})


def activate(db, item):
    if item.status == "scheduled":
        if item.scheduled_at is not None and item.scheduled_at > datetime.now(UTC):
            raise HTTPException(409, "This reassessment is not due yet")
        template = db.get(AssessmentTemplate, item.template_id)
        select_standard(db, item, template)
        item.status = "open"


def record_answer(db, item, question_key, option):
    if item.status != "open":
        raise HTTPException(409, "This assessment is closed")
    question = db.scalar(
        select(AssessmentQuestion).where(
            AssessmentQuestion.id == question_key, AssessmentQuestion.assessment_id == item.id
        )
    )
    if question is None:
        raise HTTPException(404, "Question not found in this assessment")
    if option not in {row["label"] for row in question.snapshot["options"]}:
        raise HTTPException(422, "Select one of the displayed options")
    earned = float(option == question.snapshot["answer"])
    response = db.scalar(select(StudentResponse).where(StudentResponse.assessment_question_id == question.id))
    if response:
        if item.mode == "practice":
            raise HTTPException(409, "Practice answers cannot be changed after feedback")
        response.option = option
        response.earned = earned
    else:
        db.add(StudentResponse(assessment_question_id=question.id, option=option, earned=earned))
    db.flush()
    return earned


def finalize(db, item):
    if item.status == "submitted":
        return
    if item.status != "open":
        raise HTTPException(409, "This assessment has not started")
    rows = db.execute(
        select(AssessmentQuestion, StudentResponse.earned)
        .outerjoin(StudentResponse, StudentResponse.assessment_question_id == AssessmentQuestion.id)
        .where(AssessmentQuestion.assessment_id == item.id)
    ).all()
    if not rows or all(earned is None for _, earned in rows):
        raise HTTPException(409, "Answer at least one question before submitting")
    version = item.source["weight_version"]
    weights = topic_weights(db, item.role_id, version)
    missing = {row.snapshot["topic_id"] for row, _ in rows} - weights.keys()
    if missing:
        # New practice topics are identifiable as low relevance. A standardized
        # blueprint cannot silently change the configured weights.
        if item.mode != "practice":
            raise HTTPException(409, "The assessment blueprint lacks a required topic weight")
        weights.update(dict.fromkeys(missing, 0.3))
    subtopics, topics, score = response_scores(
        [(q.snapshot["topic_id"], q.snapshot["subtopic_id"], earned or 0.0, 1.0) for q, earned in rows],
        weights,
    )
    db.add_all(TopicScore(assessment_id=item.id, topic_id=key, score=value) for key, value in topics.items())
    db.flush()
    db.add_all(
        SubtopicScore(assessment_id=item.id, topic_id=topic, subtopic_id=sub, score=value)
        for (topic, sub), value in subtopics.items()
    )
    if item.mode == "standardized":
        db.add(
            ReadinessScore(
                assessment_id=item.id,
                score=score,
                version=SCORING_VERSION,
                coverage={
                    "assessed": sorted(topics),
                    "unassessed": sorted(set(weights) - topics.keys()),
                    "answered_questions": sum(earned is not None for _, earned in rows),
                    "assigned_questions": len(rows),
                    "weights": version,
                },
            )
        )
    item.status, item.taken_at = "submitted", datetime.now(UTC)
    db.flush()


def results(db, item):
    if item.status != "submitted":
        raise HTTPException(409, "Submit the assessment to see results")
    record = db.scalar(select(ReadinessScore).where(ReadinessScore.assessment_id == item.id))
    return {
        "assessment_id": item.id,
        "mode": item.mode,
        "taken_at": item.taken_at,
        "readiness": record.score if record else None,
        "coverage": record.coverage if record else None,
        "threshold": READINESS_THRESHOLD,
        "scoring_version": record.version if record else None,
        "topics": detailed_scores(db, item.id),
    }


def topic_earned(db, assessment_id):
    result = defaultdict(list)
    for q, earned in db.execute(
        select(AssessmentQuestion, StudentResponse.earned)
        .join(StudentResponse, StudentResponse.assessment_question_id == AssessmentQuestion.id)
        .where(AssessmentQuestion.assessment_id == assessment_id)
    ):
        result[q.snapshot["topic_id"]].append(earned)
    return result
