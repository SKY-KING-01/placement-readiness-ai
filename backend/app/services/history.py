from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.ml.features import Observation
from app.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentTemplate,
    CareerRole,
    ReadinessScore,
    RoleSkillWeight,
    Skill,
    Subtopic,
    SubtopicScore,
    Topic,
    TopicScore,
)
from app.services.scoring import WEIGHT_VERSION


def active_weight_version(db, role_id):
    template = db.scalar(
        select(AssessmentTemplate)
        .where(AssessmentTemplate.role_id == role_id, AssessmentTemplate.active)
        .order_by(AssessmentTemplate.created_at.desc(), AssessmentTemplate.id.desc())
        .limit(1)
    )
    return template.blueprint["weight_version"] if template else WEIGHT_VERSION


def topic_weights(db, role_id, version=WEIGHT_VERSION):
    return dict(
        db.execute(
            select(Skill.topic_id, func.max(RoleSkillWeight.weight))
            .join(RoleSkillWeight, RoleSkillWeight.skill_id == Skill.id)
            .where(RoleSkillWeight.role_id == role_id, RoleSkillWeight.version == version)
            .group_by(Skill.topic_id)
        ).all()
    )


def standardized(db, student_id, cutoff=None):
    return db.execute(
        select(Assessment, ReadinessScore, CareerRole.name)
        .join(ReadinessScore, ReadinessScore.assessment_id == Assessment.id)
        .join(CareerRole, CareerRole.id == Assessment.role_id)
        .where(
            Assessment.student_id == student_id,
            Assessment.status == "submitted",
            Assessment.mode.in_(("standardized", "baseline")),
            Assessment.taken_at <= (cutoff or datetime.now(UTC)),
        )
        .order_by(Assessment.taken_at, Assessment.id)
    ).all()


def named_scores(db, assessment_ids):
    result = defaultdict(dict)
    if assessment_ids:
        values = db.execute(
            select(TopicScore.assessment_id, Topic.name, TopicScore.score)
            .join(Topic, Topic.id == TopicScore.topic_id)
            .where(TopicScore.assessment_id.in_(assessment_ids))
        )
        for key, name, score in values:
            result[key][name] = score
    return result


def observations(db, standardized_rows):
    ids = [item.id for item, _, _ in standardized_rows]
    topics = named_scores(db, ids)
    difficulty = defaultdict(list)
    if ids:
        for item in db.scalars(select(AssessmentQuestion).where(AssessmentQuestion.assessment_id.in_(ids))):
            difficulty[item.assessment_id].append(item.snapshot["difficulty"] == "hard")
    result = []
    for index, (assessment, score, role) in enumerate(standardized_rows):
        lower = standardized_rows[index - 1][0].taken_at if index else None
        # Practice enters a feature only after submission and only when its date
        # is at or before this landmark.
        statement = select(func.count(Assessment.id)).where(
            Assessment.student_id == assessment.student_id,
            Assessment.mode == "practice",
            Assessment.status == "submitted",
            Assessment.taken_at <= assessment.taken_at,
        )
        if lower is not None:
            statement = statement.where(Assessment.taken_at > lower)
        practice = assessment.source.get("practice", 0) if assessment.synthetic else db.scalar(statement)
        levels = difficulty[assessment.id]
        result.append(
            Observation(
                assessment.taken_at,
                score.score,
                role,
                topics[assessment.id],
                practice,
                sum(levels) / len(levels) if levels else None,
            )
        )
    return result


def detailed_scores(db, assessment_id):
    topics = db.execute(
        select(Topic.id, Topic.name, TopicScore.score)
        .join(TopicScore, TopicScore.topic_id == Topic.id)
        .where(TopicScore.assessment_id == assessment_id)
        .order_by(Topic.name)
    )
    subtopics = db.execute(
        select(SubtopicScore.topic_id, Subtopic.name, SubtopicScore.score)
        .join(Subtopic, Subtopic.id == SubtopicScore.subtopic_id)
        .where(SubtopicScore.assessment_id == assessment_id)
        .order_by(Subtopic.name)
    )
    grouped = defaultdict(list)
    for topic_id, name, score in subtopics:
        grouped[topic_id].append({"name": name, "score": score})
    return [
        {"id": key, "name": name, "score": score, "subtopics": grouped[key]} for key, name, score in topics
    ]
