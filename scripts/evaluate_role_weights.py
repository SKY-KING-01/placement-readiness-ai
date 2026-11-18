"""Quantify how prototype relevance alters the baseline top-three gap list."""

from statistics import fmean

import pandas as pd
from app.core.config import ROOT
from app.services.catalog import role_weight
from app.services.scoring import READINESS_THRESHOLD

SOURCE = ROOT / "data/synthetic/reassessments"


def main():
    assessments = pd.read_csv(SOURCE / "assessments.csv")
    roles = assessments.loc[assessments.baseline].set_index("assessment_id").role
    topics = pd.read_csv(SOURCE / "topic_scores.csv")
    topics = topics.loc[topics.assessment_id.isin(roles.index)]
    overlaps = []
    for key, frame in topics.groupby("assessment_id"):
        gaps = [(r.topic, max(0, READINESS_THRESHOLD - r.score)) for r in frame.itertuples()]
        unweighted = sorted(gaps, key=lambda row: (-row[1], row[0]))[:3]
        weighted = sorted(gaps, key=lambda row: (-row[1] * role_weight(roles[key], row[0]), row[0]))[:3]
        overlaps.append(len({a for a, _ in unweighted} & {a for a, _ in weighted}))
    changed = sum(value != 3 for value in overlaps)
    output = [
        "# Prototype role-priority sensitivity",
        "",
        f"Compared the three highest measured gaps under uniform and role-weighted ranking across {len(overlaps)}",
        "synthetic baselines. Ties were ordered by topic name. The weighted list uses",
        "`max(0, 75 - topic score) × role weight`.",
        "",
        f"- {changed} baselines changed at least one top-three topic.",
        f"- Mean overlap was {fmean(overlaps):.2f} of three topics.",
        "",
        "The comparison measures sensitivity to the selected weights. It provides no evidence",
        "about which ranking improves learning or agrees with independent role experts.",
    ]
    (ROOT / "research/role_prioritization.md").write_text("\n".join(output) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
