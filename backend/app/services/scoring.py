from collections import defaultdict
from collections.abc import Iterable, Mapping
from math import isfinite

WEIGHT_VERSION = "prototype-v1"
SCORING_VERSION = "readiness-v1"
READINESS_THRESHOLD = 75.0


def percentage(earned: float, possible: float) -> float:
    if not all(map(isfinite, (earned, possible))) or possible <= 0 or not 0 <= earned <= possible:
        raise ValueError("Expected finite points between zero and the positive maximum")
    return 100 * earned / possible


def weighted_mean(scores: Mapping[str, float], weights: Mapping[str, float]) -> float | None:
    if not scores:
        return None
    selected = [(score, weights[key]) for key, score in scores.items() if key in weights]
    if len(selected) != len(scores):
        raise ValueError("Each assessed area must have a versioned weight")
    if any(not 0 <= score <= 100 or not isfinite(weight) or weight <= 0 for score, weight in selected):
        raise ValueError("Score or weight is invalid")
    return round(sum(score * weight for score, weight in selected) / sum(weight for _, weight in selected), 4)


def response_scores(rows: Iterable[tuple[str, str, float, float]], topic_weights: Mapping[str, float]):
    """Pool question points by subtopic, then average subtopics with their available points as weights."""
    totals = defaultdict(lambda: [0.0, 0.0])
    for topic, subtopic, earned, possible in rows:
        percentage(earned, possible)
        totals[topic, subtopic][0] += earned
        totals[topic, subtopic][1] += possible
    subtopics = {key: percentage(*pair) for key, pair in totals.items()}
    groups = defaultdict(dict)
    for (topic, subtopic), score in subtopics.items():
        groups[topic][subtopic] = score
    topics = {
        topic: weighted_mean(scores, {sub: totals[topic, sub][1] for sub in scores})
        for topic, scores in groups.items()
    }
    return subtopics, topics, weighted_mean(topics, topic_weights)
