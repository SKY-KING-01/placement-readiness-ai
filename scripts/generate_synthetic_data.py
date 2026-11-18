"""Generate longitudinal CSVs and optionally import five synthetic reassessments per student."""

import argparse
import json
from pathlib import Path

import pandas as pd
from app.core.config import ROOT
from app.core.database import engine
from app.models import (
    Assessment,
    CareerRole,
    ReadinessScore,
    Student,
    Subtopic,
    SubtopicScore,
    Topic,
    TopicScore,
)
from app.services.catalog import stable_id
from app.services.scoring import SCORING_VERSION, WEIGHT_VERSION
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ml.simulation.generate import Simulation, export
from scripts.import_source_data import CLEAN, insert_rows


def persist(db, folder):
    history = pd.read_csv(folder / "assessments.csv", parse_dates=["date"])
    history = history.loc[~history.baseline]
    topic_data = pd.read_csv(folder / "topic_scores.csv")
    subtopic_data = pd.read_csv(folder / "subtopic_scores.csv")
    db.execute(text("SELECT pg_advisory_xact_lock(820374)"))
    if not set(history.student_id) <= set(db.scalars(select(Student.id).where(Student.synthetic))):
        raise ValueError("Import the baseline synthetic students before adding reassessments")
    roles = dict(db.execute(select(CareerRole.name, CareerRole.id)).all())
    topics = dict(db.execute(select(Topic.name, Topic.id)).all())
    subs = {
        (parent, name): key
        for parent, name, key in db.execute(select(Subtopic.topic_id, Subtopic.name, Subtopic.id))
    }
    keys = set(history.assessment_id)
    counts = {}
    counts["assessments"] = insert_rows(
        db,
        Assessment,
        [
            dict(
                id=r.assessment_id,
                student_id=r.student_id,
                role_id=roles[r.role],
                attempt=r.attempt,
                mode="standardized",
                status="submitted",
                taken_at=r.date.to_pydatetime(),
                synthetic=True,
                source={"practice": r.practice, "seed": r.seed, "generator": "latent-mastery-v1"},
            )
            for r in history.itertuples()
        ],
    )
    counts["topic_scores"] = insert_rows(
        db,
        TopicScore,
        [
            dict(
                id=stable_id("ts", r.assessment_id, r.topic),
                assessment_id=r.assessment_id,
                topic_id=topics[r.topic],
                score=r.score,
            )
            for r in topic_data.itertuples()
            if r.assessment_id in keys
        ],
    )
    counts["subtopic_scores"] = insert_rows(
        db,
        SubtopicScore,
        [
            dict(
                id=stable_id("ss", r.assessment_id, r.topic, r.subtopic),
                assessment_id=r.assessment_id,
                topic_id=topics[r.topic],
                subtopic_id=subs[topics[r.topic], r.subtopic],
                score=r.score,
            )
            for r in subtopic_data.itertuples()
            if r.assessment_id in keys
        ],
    )
    counts["readiness_scores"] = insert_rows(
        db,
        ReadinessScore,
        [
            dict(
                id=r.assessment_id,
                assessment_id=r.assessment_id,
                score=r.readiness,
                version=SCORING_VERSION,
                coverage={"historical_blueprint": "source", "weights": WEIGHT_VERSION},
            )
            for r in history.itertuples()
        ],
    )
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/synthetic/reassessments")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    metadata = export(args.output, CLEAN, Simulation())
    if args.persist:
        with Session(engine()) as db, db.begin():
            metadata["inserted"] = persist(db, args.output)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
