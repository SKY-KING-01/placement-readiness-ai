"""Reproduce synthetic assessment histories from the original baseline evidence."""

import argparse
import hashlib
import json
from collections import defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from app.core.config import ROOT
from app.services.catalog import role_weight, stable_id
from app.services.scoring import READINESS_THRESHOLD, weighted_mean
from openpyxl import load_workbook

from scripts.import_source_data import CLEAN, rows, utc


@dataclass(frozen=True)
class Simulation:
    seed: int = 42
    attempts: int = 6
    interval_days: int = 14
    threshold: float = READINESS_THRESHOLD
    horizon_days: int = 60


PATTERNS = (
    "fast",
    "slow",
    "plateau",
    "temporary_regression",
    "irregular",
    "topic_specific",
    "practice_dependent",
)


def simulate(workbook: Path, config: Simulation):
    if config.attempts < 2 or config.interval_days < 1:
        raise ValueError("Simulation requires at least two attempts and a positive interval")
    with closing(load_workbook(workbook, read_only=True)) as book:
        baseline = rows(book, "Assessments")
        parent_topics = {
            (r["Assessment_ID"], r["Topic_ID"]): r["Topic_Name"] for r in rows(book, "Topic_Scores")
        }
        original_topic_scores = {
            (r["Assessment_ID"], r["Topic_Name"]): r["Percentage"] for r in rows(book, "Topic_Scores")
        }
        subtopics = defaultdict(list)
        for row in rows(book, "Subtopic_Scores"):
            name = parent_topics[row["Assessment_ID"], row["Topic_ID"]]
            subtopics[row["Assessment_ID"]].append((name, row["Subtopic_Name"], row["Percentage"]))
    rng = np.random.default_rng(config.seed)
    assessments, topic_rows, subtopic_rows = [], [], []
    for row in sorted(baseline, key=lambda r: r["Student_ID"]):
        original = row["Assessment_ID"]
        student = row["Student_ID"]
        role = row["Target_Role"]
        start = utc(row["Assessment_Date"])
        pattern = rng.choice(PATTERNS).item()
        rate = float(
            rng.normal(
                {
                    "fast": 0.24,
                    "slow": 0.085,
                    "plateau": 0.028,
                    "temporary_regression": 0.145,
                    "irregular": 0.14,
                    "topic_specific": 0.13,
                    "practice_dependent": 0.12,
                }[pattern],
                0.024,
            )
        )
        topics = sorted({item[0] for item in subtopics[original]})
        favored = rng.choice(topics).item()
        engagement = rng.uniform(0.45, 1.55)
        mastery = {
            (topic, sub): float(np.clip(score + rng.normal(0, 0.9), 10, 96))
            for topic, sub, score in subtopics[original]
        }
        for offset in range(config.attempts):
            assessment = (
                original if offset == 0 else stable_id("sim", student, str(config.seed), str(offset + 1))
            )
            date = start + timedelta(days=offset * config.interval_days)
            activity = int(rng.poisson(4.5 * engagement)) if offset else 0
            period_noise = rng.normal(0, 1.5)
            topic_values = defaultdict(list)
            for topic, sub, original_score in sorted(subtopics[original]):
                if not offset:
                    measured = original_score
                else:
                    effect = rate * (0.66 + 0.07 * activity)
                    if pattern == "topic_specific":
                        effect *= 1.8 if topic == favored else 0.60
                    if pattern == "practice_dependent":
                        effect *= activity / (2 + activity)
                    if pattern == "plateau" and offset >= 3:
                        effect *= 0.15
                    shock = period_noise + rng.normal(0, 0.9)
                    if pattern == "temporary_regression" and offset in {2, 3}:
                        shock -= 6
                    if pattern == "irregular":
                        shock += rng.normal(0, 4)
                    key = topic, sub
                    mastery[key] = float(np.clip(mastery[key] + effect * (91 - mastery[key]) + shock, 0, 100))
                    measured = round(float(np.clip(mastery[key] + rng.normal(0, 3.4), 0, 100)), 2)
                topic_values[topic].append(measured)
                subtopic_rows.append((assessment, student, topic, sub, measured))
            scores = {
                topic: (
                    original_topic_scores[original, topic] if not offset else round(float(np.mean(vals)), 2)
                )
                for topic, vals in sorted(topic_values.items())
            }
            readiness = weighted_mean(scores, {topic: role_weight(role, topic) for topic in scores})
            assessments.append(
                (
                    assessment,
                    student,
                    role,
                    offset + 1,
                    date,
                    readiness,
                    activity,
                    config.seed,
                    True,
                    offset == 0,
                    pattern,
                )
            )
            topic_rows.extend((assessment, student, topic, score) for topic, score in scores.items())
    return (
        pd.DataFrame(
            assessments,
            columns=(
                "assessment_id",
                "student_id",
                "role",
                "attempt",
                "date",
                "readiness",
                "practice",
                "seed",
                "synthetic",
                "baseline",
                "pattern",
            ),
        ),
        pd.DataFrame(topic_rows, columns=("assessment_id", "student_id", "topic", "score")),
        pd.DataFrame(subtopic_rows, columns=("assessment_id", "student_id", "topic", "subtopic", "score")),
    )


def export(destination: Path, workbook: Path, config: Simulation):
    destination.mkdir(parents=True, exist_ok=True)
    result = simulate(workbook, config)
    for name, frame in zip(("assessments", "topic_scores", "subtopic_scores"), result, strict=True):
        frame.to_csv(destination / f"{name}.csv", index=False)
    metadata = {
        "config": asdict(config),
        "source_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "students": int(result[0].student_id.nunique()),
        "rows": [len(frame) for frame in result],
        "synthetic": True,
        "generator": "latent-mastery-v1",
    }
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=CLEAN)
    parser.add_argument("--output", type=Path, default=ROOT / "data/synthetic/reassessments")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(export(args.output, args.workbook, Simulation(seed=args.seed)), indent=2))


if __name__ == "__main__":
    main()
