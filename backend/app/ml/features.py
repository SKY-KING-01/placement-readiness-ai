from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from statistics import fmean, pstdev

from app.services.catalog import CORE_TOPICS, role_weight

FEATURE_VERSION = "longitudinal-v1"
TOPICS = (
    *CORE_TOPICS,
    "SQL & Database",
    "Python Programming",
    "Statistics",
    "Machine Learning",
    "Data Structures & Algorithms",
    "Healthcare Data Fundamentals",
    "Critical Thinking",
)
BASE = (
    "current",
    "previous",
    "recent_improvement",
    "mean_improvement",
    "volatility",
    "assessment_count",
    "days_since_baseline",
    "days_since_previous",
    "practice",
    "weighted_gap",
    "measured_topics",
    "role",
    "hard_share",
)
FEATURES = (*BASE, *(f"{topic}:{metric}" for topic in TOPICS for metric in ("current", "change")))


@dataclass(frozen=True)
class Observation:
    date: datetime
    score: float
    role: str
    topics: dict[str, float] = field(default_factory=dict)
    practice: int = 0
    hard_share: float | None = None


def features_for(history: list[Observation]) -> dict:
    """The caller supplies one student's standardized observations through the prediction cutoff."""
    if not history or any(a.date >= b.date for a, b in pairwise(history)):
        raise ValueError("Need strictly chronological standardized history")
    current = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    changes = [b.score - a.score for a, b in pairwise(history)]
    gaps = [
        (75 - score) * role_weight(current.role, topic)
        for topic, score in current.topics.items()
        if score < 75
    ]
    result = {
        "current": current.score,
        "previous": previous.score if previous else None,
        "recent_improvement": changes[-1] if changes else None,
        "mean_improvement": fmean(changes) if changes else None,
        "volatility": pstdev(item.score for item in history),
        "assessment_count": len(history),
        "days_since_baseline": (current.date - history[0].date).total_seconds() / 86400,
        "days_since_previous": (current.date - previous.date).total_seconds() / 86400 if previous else None,
        "practice": sum(item.practice for item in history),
        "weighted_gap": fmean(gaps) if gaps else 0.0,
        "measured_topics": len(current.topics),
        "role": current.role,
        "hard_share": current.hard_share,
    }
    for topic in TOPICS:
        score = current.topics.get(topic)
        before = previous.topics.get(topic) if previous else None
        result[f"{topic}:current"] = score
        result[f"{topic}:change"] = score - before if score is not None and before is not None else None
    return result
