from dataclasses import dataclass
from math import isfinite

WEIGHTS = {"gap": 0.4, "role": 0.25, "difficulty": 0.2, "company": 0.15}
DIFFICULTY = {"easy": 0.2, "medium": 0.55, "hard": 0.85}


@dataclass(frozen=True)
class Candidate:
    key: str
    topic_id: str
    level: str
    company_match: bool


def rank(candidate, mastery, relevance, previously_seen, current_seen):
    if candidate.key in current_seen:
        return None
    skill = mastery.get(candidate.topic_id, 0.5)
    relevance = relevance.get(candidate.topic_id, 0.3)
    if not all(isfinite(value) and 0 <= value <= 1 for value in (skill, relevance)):
        raise ValueError("Mastery and role relevance must lie between zero and one")
    challenge = min(0.92, skill + 0.12)
    components = {
        "gap": 1 - skill,
        "role": relevance,
        "difficulty": 1 - abs(DIFFICULTY[candidate.level] - challenge),
        "company": float(candidate.company_match),
    }
    total = sum(WEIGHTS[key] * value for key, value in components.items())
    return (candidate.key not in previously_seen, total), {
        "version": "heuristic-v1",
        "components": components,
        "score": total,
        "mastery": skill,
    }
