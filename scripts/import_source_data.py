"""Validate and import the supplied synthetic workbook as one PostgreSQL transaction."""

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import ROOT
from app.core.database import engine
from app.models import (
    Assessment,
    AssessmentTemplate,
    CareerProfile,
    CareerRole,
    CodingTestCase,
    LearningRoadmap,
    MentorshipSession,
    Question,
    QuestionImportBatch,
    QuestionOption,
    QuestionReview,
    ReadinessScore,
    RoleSkillWeight,
    Skill,
    Student,
    Subtopic,
    SubtopicScore,
    Topic,
    TopicScore,
    User,
)
from app.services.catalog import QUESTION_TOPICS, blueprint, fingerprint, role_weight, stable_id
from app.services.scoring import SCORING_VERSION, WEIGHT_VERSION, weighted_mean
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

SOURCE = ROOT / "data/source"
CLEAN = SOURCE / "cleaned_pseudo_dataset (1).xlsx"
OPTIONS = ("Option A", "Option B", "Option C", "Option D")


def rows(book, name):
    stream = iter(book[name].values)
    header = next(stream)
    return [dict(zip(header, row, strict=True)) for row in stream if any(value is not None for value in row)]


def serialized(row):
    return {key: value.isoformat() if isinstance(value, date) else value for key, value in row.items()}


def utc(value):
    return (
        value.replace(tzinfo=UTC)
        if isinstance(value, datetime)
        else datetime.fromisoformat(value).replace(tzinfo=UTC)
    )


def insert_rows(db, model, values):
    if not values:
        return 0
    count = 0
    for start in range(0, len(values), 350):
        statement = (
            insert(model).values(values[start : start + 350]).on_conflict_do_nothing().returning(model.id)
        )
        count += len(db.scalars(statement).all())
    return count


def load_validated(path):
    spec = importlib.util.spec_from_file_location(
        "source_pipeline", SOURCE / "placement_preprocessing_pipeline (1).py"
    )
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    # The importer requires a cleaned workbook. A normalization pass validates
    # types and all source relationships without consuming or changing reports.
    tables = pipeline.read_tables(path)
    normalized_tables = pipeline.preprocess(tables)
    if any(len(table) != len(normalized_tables[name]) for name, table in tables.items()):
        raise ValueError("Expected unique cleaned source records")
    with closing(load_workbook(path, read_only=True)) as book:
        return {name: rows(book, name) for name in (*tables, "Question_Review", "Usable_Questions")}


def import_source(db, path=CLEAN):
    data = load_validated(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    db.execute(text("SELECT pg_advisory_xact_lock(820374)"))
    counts = Counter()

    def save(model, values):
        counts[model.__tablename__] += insert_rows(db, model, list(values))

    source_topics = data["Topic_Scores"]
    role_names = sorted({r["Target_Role"] for r in data["Career_Profile"] + data["Assessments"]})
    roles = {name: stable_id("role", name) for name in role_names}
    source_topic_names = {(r["Assessment_ID"], r["Topic_ID"]): r["Topic_Name"] for r in source_topics}
    questions = data["Question_Bank"]
    normalized_topics = set(source_topic_names.values()) | {
        QUESTION_TOPICS.get(q["Skill area"], q["Skill area"]) for q in questions
    }
    topics = {name: stable_id("topic", name) for name in sorted(normalized_topics)}
    source_subtopics = {
        (r["Assessment_ID"], r["Topic_ID"], r["Subtopic_ID"]): (
            source_topic_names[r["Assessment_ID"], r["Topic_ID"]],
            r["Subtopic_Name"],
        )
        for r in data["Subtopic_Scores"]
    }
    question_subtopics = {
        q["Question id"]: (QUESTION_TOPICS.get(q["Skill area"], q["Skill area"]), q["Sub skill area"])
        for q in questions
    }
    subtopics = {
        key: stable_id("sub", *key)
        for key in sorted(set(source_subtopics.values()) | set(question_subtopics.values()))
    }
    skills = {topic: stable_id("skill", topic) for topic in topics}
    save(CareerRole, (dict(id=key, name=name) for name, key in roles.items()))
    save(Topic, (dict(id=key, name=name) for name, key in topics.items()))
    save(
        Subtopic,
        (dict(id=key, topic_id=topics[topic], name=name) for (topic, name), key in subtopics.items()),
    )
    save(Skill, (dict(id=key, topic_id=topics[topic], name=topic) for topic, key in skills.items()))
    save(
        RoleSkillWeight,
        (
            dict(
                id=stable_id("weight", role, topic, WEIGHT_VERSION),
                role_id=role_id,
                skill_id=skill_id,
                version=WEIGHT_VERSION,
                weight=role_weight(role, topic),
            )
            for role, role_id in roles.items()
            for topic, skill_id in skills.items()
        ),
    )
    save(
        AssessmentTemplate,
        (
            dict(id=stable_id("blueprint", role, "v1"), role_id=key, version="v1", blueprint=blueprint(role))
            for role, key in roles.items()
        ),
    )
    students = data["Students"]
    if any(not str(r["College_Email"]).endswith("@demo.college") for r in students):
        raise ValueError("Source import accepts the supplied synthetic student cohort only")
    save(
        User,
        (
            dict(
                id=r["Student_ID"],
                email=r["College_Email"].lower(),
                display_name=r["Full_Name"],
                active=False,
            )
            for r in students
        ),
    )
    save(
        Student,
        (
            dict(
                id=r["Student_ID"],
                user_id=r["Student_ID"],
                roll_number=r["Roll_No"],
                department=r["Department"],
                synthetic=True,
                source=serialized({k: v for k, v in r.items() if k not in {"Phone_Number", "College_Email"}}),
            )
            for r in students
        ),
    )
    save(
        CareerProfile,
        (
            dict(
                id=r["Career_Profile_ID"],
                source_id=r["Career_Profile_ID"],
                student_id=r["Student_ID"],
                role_id=roles[r["Target_Role"]],
                source=serialized(r),
            )
            for r in data["Career_Profile"]
        ),
    )
    assessments = data["Assessments"]
    save(
        Assessment,
        (
            dict(
                id=r["Assessment_ID"],
                student_id=r["Student_ID"],
                role_id=roles[r["Target_Role"]],
                mode="baseline",
                attempt=1,
                status="submitted",
                taken_at=utc(r["Assessment_Date"]),
                synthetic=True,
                source=serialized(r),
            )
            for r in assessments
        ),
    )
    save(
        TopicScore,
        (
            dict(
                id=stable_id("ts", r["Assessment_ID"], r["Topic_ID"]),
                assessment_id=r["Assessment_ID"],
                topic_id=topics[r["Topic_Name"]],
                score=r["Percentage"],
                source_topic_id=r["Topic_ID"],
                source=serialized(r),
            )
            for r in source_topics
        ),
    )
    save(
        SubtopicScore,
        (
            dict(
                id=stable_id("ss", r["Assessment_ID"], r["Topic_ID"], r["Subtopic_ID"]),
                assessment_id=r["Assessment_ID"],
                topic_id=topics[source_topic_names[r["Assessment_ID"], r["Topic_ID"]]],
                score=r["Percentage"],
                subtopic_id=subtopics[source_subtopics[r["Assessment_ID"], r["Topic_ID"], r["Subtopic_ID"]]],
                source_topic_id=r["Topic_ID"],
                source_subtopic_id=r["Subtopic_ID"],
                source=serialized(r),
            )
            for r in data["Subtopic_Scores"]
        ),
    )
    scores = {}
    for r in source_topics:
        scores.setdefault(r["Assessment_ID"], {})[r["Topic_Name"]] = r["Percentage"]
    save(
        ReadinessScore,
        (
            dict(
                id=r["Assessment_ID"],
                assessment_id=r["Assessment_ID"],
                version=SCORING_VERSION,
                score=weighted_mean(
                    scores[r["Assessment_ID"]],
                    {topic: role_weight(r["Target_Role"], topic) for topic in scores[r["Assessment_ID"]]},
                ),
                coverage={"historical_blueprint": "source", "weights": WEIGHT_VERSION},
            )
            for r in assessments
        ),
    )
    save(
        LearningRoadmap,
        (
            dict(
                id=r["Roadmap_ID"],
                student_id=r["Student_ID"],
                assessment_id=r["Assessment_ID"],
                provider="source",
                version="workbook",
                content=serialized(r),
            )
            for r in data["AI_Roadmaps"]
        ),
    )
    save(
        MentorshipSession,
        (
            dict(
                id=r["Mentorship_ID"],
                student_id=r["Student_ID"],
                assessment_id=r["Assessment_ID"],
                source=serialized(r),
            )
            for r in data["Mentorship"]
        ),
    )
    valid = {r["Question id"] for r in data["Usable_Questions"]}
    bad = {
        q["Question id"]
        for q in questions
        if any(
            isinstance(q[c], date) or re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", str(q[c])) for c in OPTIONS
        )
    }
    if valid != {q["Question id"] for q in questions} - bad:
        raise ValueError("Question eligibility report disagrees with observed date-like options")
    batch = stable_id("batch", digest)
    save(
        QuestionImportBatch,
        [
            dict(
                id=batch,
                filename=path.name,
                digest=digest,
                report={"questions": len(questions), "flagged": len(bad)},
            )
        ],
    )
    question_values = []
    seen = set()
    duplicates = []
    for question in questions:
        key = question["Question id"]
        options = [str(question[col]) for col in OPTIONS]
        mark = fingerprint(question["Question text"], "mcq", options)
        status = "approved" if key in valid and mark not in seen else "quarantined"
        if key in valid:
            if mark in seen:
                duplicates.append(key)
            seen.add(mark)
        topic, name = question_subtopics[key]
        question_values.append(
            dict(
                id=key,
                text=question["Question text"],
                kind="mcq",
                fingerprint=mark,
                category=question["Category"].lower(),
                difficulty=question["Difficulty"].lower(),
                topic_id=topics[topic],
                subtopic_id=subtopics[topic, name],
                skill_id=skills[topic],
                batch_id=batch,
                status=status,
                source=serialized(question),
            )
        )
    save(Question, question_values)
    save(
        QuestionOption,
        (
            dict(
                id=stable_id("op", q["Question id"], col),
                question_id=q["Question id"],
                label=col[-1],
                text=str(q[col]),
                correct=col[-1] == q["Correct option"],
            )
            for q in questions
            for col in OPTIONS
        ),
    )
    reviews = [
        dict(
            id=stable_id("review", r["Question id"], r["Column"]),
            question_id=r["Question id"],
            action="quarantined",
            detail=f"{r['Column']}: {r['Issue']}",
        )
        for r in data["Question_Review"]
    ]
    save(
        QuestionReview,
        reviews
        + [
            dict(
                id=stable_id("review", key, "duplicate"),
                question_id=key,
                action="quarantined",
                detail="Duplicate question and option content",
            )
            for key in duplicates
        ],
    )
    seed_coding(db, topics)
    return {
        "inserted": dict(counts),
        "source_question_eligible": len(valid) - len(duplicates),
        "flagged_question_ids": sorted(bad),
        "duplicate_question_ids": duplicates,
    }


def seed_coding(db, topics):
    examples = [
        (
            "practice-sum",
            "python_io",
            "Read two space-separated integers and print their sum.",
            {"stdin": "3 5\n"},
            {"stdout": "8\n"},
            {"stdin": "-13 9\n"},
            {"stdout": "-4\n"},
            {},
        ),
        (
            "practice-product",
            "python_function",
            "Implement multiply(a, b) and return their product.",
            {"args": [3, 5]},
            {"return": 15},
            {"args": [-13, 9]},
            {"return": -117},
            {"function": "multiply"},
        ),
    ]
    for key, kind, prompt, example, sample, secret, expected, extra in examples:
        insert_rows(
            db,
            Question,
            [
                dict(
                    id=key,
                    text=prompt,
                    kind=kind,
                    fingerprint=fingerprint(prompt, kind),
                    category="python",
                    difficulty="easy",
                    topic_id=topics["Python Programming"],
                    status="approved",
                    settings={"seconds": 2, "memory_mb": 128, "partial": True, **extra},
                )
            ],
        )
        insert_rows(
            db,
            CodingTestCase,
            [
                dict(id=f"{key}-sample", question_id=key, public=True, inputs=example, expected=sample),
                dict(id=f"{key}-hidden", question_id=key, public=False, inputs=secret, expected=expected),
            ],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=CLEAN)
    args = parser.parse_args()
    with Session(engine()) as db, db.begin():
        report = import_source(db, args.workbook)
        report["total_students"] = len(db.scalars(select(Student.id)).all())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
