import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.integrations import openai_client
from app.models import LearningRoadmap, RoadmapTask, Student
from app.schemas.roadmap import Roadmap, Week
from app.services.history import detailed_scores, standardized, topic_weights
from app.services.prediction import predict

RESOURCES = {
    "python-tutorial": ("Python tutorial", "https://docs.python.org/3/tutorial/"),
    "postgresql-tutorial": ("PostgreSQL tutorial", "https://www.postgresql.org/docs/current/tutorial.html"),
    "khan-statistics": (
        "Statistics and probability",
        "https://www.khanacademy.org/math/statistics-probability",
    ),
    "openstax-math": ("OpenStax math", "https://openstax.org/subjects/math"),
}
PROMPT_VERSION = openai_client.PROMPT_VERSION


def catalog(skills):
    topics = " ".join(skills).lower()
    result = ["openstax-math"]
    if "statistic" in topics or "quantitative" in topics:
        result.append("khan-statistics")
    if "python" in topics or "program" in topics or "machine learning" in topics:
        result.append("python-tutorial")
    if "sql" in topics or "database" in topics or "dbms" in topics:
        result.append("postgresql-tutorial")
    return result


def fallback(evidence):
    skills = evidence["skills"]
    plan = [
        Week(
            week=i,
            focus=skills[(i - 1) % len(skills)],
            hours=evidence["weekly_hours"],
            tasks=[
                f"Review {skills[(i - 1) % len(skills)]} concepts",
                f"Complete a focused practice set and log mistakes for week {i}",
            ],
        )
        for i in range(1, 5)
    ]
    return Roadmap(
        target_role=evidence["target_role"],
        current_readiness=evidence["current_readiness"],
        duration_weeks=4,
        priority_skills=skills,
        weekly_plan=plan,
        practice_tasks=["Rework missed questions and explain each correction."],
        recommended_resources=evidence["resource_ids"],
        reassessment_milestones=["Take a standardized reassessment after week 4."],
        explanation="Priorities come from measured gaps and the selected role’s skill weights.",
    )


def is_grounded(proposal, evidence):
    if proposal is None:
        return False
    if (
        proposal.target_role != evidence["target_role"]
        or proposal.current_readiness != evidence["current_readiness"]
        or not set(proposal.priority_skills) <= set(evidence["skills"])
        or not set(proposal.recommended_resources) <= set(evidence["resource_ids"])
    ):
        return False
    weeks = proposal.weekly_plan
    if [week.week for week in weeks] != list(range(1, proposal.duration_weeks + 1)) or any(
        week.hours > evidence["weekly_hours"] or week.focus not in evidence["skills"] for week in weeks
    ):
        return False
    output = [
        proposal.explanation,
        *proposal.practice_tasks,
        *proposal.reassessment_milestones,
        *(task for week in weeks for task in week.tasks),
    ]
    return all(
        1 <= len(text.strip()) <= 1200
        and not re.search(
            r"(?i)(?:https?\s*:|www\.|\b[a-z][a-z0-9-]*\.(?:com|org|net|edu|io|gov|in)\b)",
            unicodedata.normalize("NFKC", text),
        )
        for text in output
    )


def latest(db, student_id):
    return db.scalar(
        select(LearningRoadmap)
        .where(LearningRoadmap.student_id == student_id, LearningRoadmap.provider != "source")
        .order_by(LearningRoadmap.created_at.desc(), LearningRoadmap.id.desc())
        .limit(1)
    )


def evidence_for(db, student, weekly_hours):
    rows = standardized(db, student.id)
    if not rows:
        return None, None
    assessment, score, role = rows[-1]
    topics = detailed_scores(db, assessment.id)
    weights = topic_weights(db, assessment.role_id, score.coverage.get("weights"))
    for topic in topics:
        topic["gap"] = round(max(0.0, 75 - topic["score"]) * weights.get(topic["id"], 0.3), 2)
    priorities = sorted(topics, key=lambda item: (-item["gap"], item["score"], item["name"]))[:4]
    names = [item["name"] for item in priorities]
    # OpenAI receives bounded evidence without email, name, IDs or raw answer text.
    outcome = predict(db, student, persist=False)
    return assessment, {
        "target_role": role,
        "current_readiness": score.score,
        "skills": names,
        "weekly_hours": weekly_hours,
        "resource_ids": catalog(names),
        "scores": [{k: v for k, v in item.items() if k != "id"} for item in topics],
        "history": [
            {"date": item.taken_at.date().isoformat(), "score": value.score} for item, value, _ in rows[-6:]
        ],
        "predicted_next_score": (outcome["regression"] or {}).get("value"),
        "readiness_probability": (outcome["classification"] or {}).get("value"),
        "synthetic_prediction": outcome["status"] == "synthetic_demo",
    }


def create(db, student, weekly_hours, use_openai=True):
    assessment, evidence = evidence_for(db, student, weekly_hours)
    if evidence is None or not evidence["skills"]:
        return None
    config = settings()
    proposal = openai_client.generate(config, evidence) if use_openai else None
    use_proposal = is_grounded(proposal, evidence)
    chosen = proposal if use_proposal else fallback(evidence)
    db.get(Student, student.id, with_for_update=True)
    existing = latest(db, student.id)
    recent = standardized(db, student.id)
    if not recent or recent[-1][0].id != assessment.id:
        return existing
    provider = "openai" if use_proposal else "deterministic"
    content = {
        **chosen.model_dump(),
        "weekly_hours": weekly_hours,
        "model": config.openai_model if use_proposal else None,
    }
    if (
        existing
        and existing.assessment_id == assessment.id
        and existing.provider == provider
        and existing.content == content
    ):
        return existing
    roadmap = LearningRoadmap(
        student_id=student.id,
        assessment_id=assessment.id,
        provider=provider,
        version=PROMPT_VERSION,
        created_at=datetime.now(UTC),
        content=content,
    )
    db.add(roadmap)
    db.flush()
    db.add_all(
        RoadmapTask(roadmap_id=roadmap.id, title=task[:300], week=week.week)
        for week in chosen.weekly_plan
        for task in week.tasks
    )
    db.flush()
    return roadmap


def public(db, roadmap):
    if roadmap is None:
        return {"status": "insufficient_history", "roadmap": None}
    content = roadmap.content
    return {
        "status": "openai" if roadmap.provider == "openai" else "fallback",
        "roadmap": {
            "id": roadmap.id,
            "assessment_id": roadmap.assessment_id,
            "version": roadmap.version,
            **content,
            "resources": [
                {"id": key, "title": RESOURCES[key][0], "url": RESOURCES[key][1]}
                for key in content["recommended_resources"]
            ],
            "tasks": [
                {"id": task.id, "title": task.title, "week": task.week, "completed": task.completed}
                for task in db.scalars(
                    select(RoadmapTask)
                    .where(RoadmapTask.roadmap_id == roadmap.id)
                    .order_by(RoadmapTask.week, RoadmapTask.created_at, RoadmapTask.id)
                )
            ],
        },
    }
