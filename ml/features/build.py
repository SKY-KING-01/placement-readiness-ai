"""Build landmark features, future-only labels, and group-separated chronological cohorts."""

from datetime import timedelta
from pathlib import Path

import pandas as pd
from app.ml.features import Observation, features_for
from app.services.scoring import READINESS_THRESHOLD


def label_future(history, index, horizon=60, threshold=READINESS_THRESHOLD):
    cutoff = history[index].date + timedelta(days=horizon)
    full_followup = history[-1].date >= cutoff
    if history[index].score >= threshold:
        return None, full_followup, "already_ready"
    for row in history[index + 1 :]:
        if row.date > cutoff:
            break
        if row.score >= threshold:
            return 1, full_followup, "observed_positive"
    return (0, True, "observed_negative") if full_followup else (None, False, "censored")


def build(folder: Path, horizon=60, threshold=READINESS_THRESHOLD):
    assessments = pd.read_csv(folder / "assessments.csv", parse_dates=["date"])
    topics = pd.read_csv(folder / "topic_scores.csv")
    scores = {
        key: dict(zip(group.topic, group.score, strict=True))
        for key, group in topics.groupby("assessment_id")
    }
    records = []
    start = assessments.groupby("student_id").date.min().reset_index().sort_values(["date", "student_id"])
    students = start.student_id.tolist()
    boundary, validation_boundary = int(0.70 * len(students)), int(0.85 * len(students))
    groups = {
        key: "train" if n < boundary else "validation" if n < validation_boundary else "test"
        for n, key in enumerate(students)
    }
    for key, part in assessments.groupby("student_id"):
        ordered = list(part.sort_values("date").itertuples())
        history = [
            Observation(r.date.to_pydatetime(), r.readiness, r.role, scores[r.assessment_id], r.practice)
            for r in ordered
        ]
        for index, (row, observation) in enumerate(zip(ordered, history, strict=True)):
            target, full, status = label_future(history, index, horizon, threshold)
            future = history[index + 1] if index + 1 < len(history) else None
            records.append(
                dict(
                    student_id=key,
                    assessment_id=row.assessment_id,
                    date=observation.date,
                    split=groups[key],
                    ready_within_60_days=target,
                    complete_followup=full,
                    label_status=status,
                    next_score=future.score if future else None,
                    next_date=future.date if future else None,
                    **features_for(history[: index + 1]),
                )
            )
    return pd.DataFrame(records)
