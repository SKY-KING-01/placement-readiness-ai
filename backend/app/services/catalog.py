import hashlib
import re

CORE_TOPICS = ("Quantitative Aptitude", "Logical & Analytical Reasoning", "Communication")
QUESTION_TOPICS = {
    "Quantitative Aptitude": CORE_TOPICS[0],
    "Logical and Critical Thinking": CORE_TOPICS[1],
    "Verbal Aptitude": CORE_TOPICS[2],
    "Communication": CORE_TOPICS[2],
    "Teamwork": CORE_TOPICS[2],
    "Work Planning": "Critical Thinking",
    "Professional Judgment": "Critical Thinking",
    "Python Programming": "Python Programming",
    "DBMS and SQL": "SQL & Database",
    "DSA": "Data Structures & Algorithms",
    "Mathematics and Statistics": "Statistics",
    "Deep Learning and AI": "Machine Learning",
    "Healthcare AI": "Healthcare Data Fundamentals",
    "Healthcare Data": "Healthcare Data Fundamentals",
}
ROLE_TOPICS = (
    (
        ("health", "clinical"),
        ("Healthcare Data Fundamentals", "Python & Data", "Statistics", "Machine Learning Basics"),
    ),
    (
        ("security", "soc"),
        ("Cybersecurity Fundamentals", "Networking", "Operating Systems", "Python & Scripting"),
    ),
    (
        ("backend", "software", "qa"),
        ("Programming", "Data Structures & Algorithms", "OOP & Software Engineering", "DBMS"),
    ),
    (("analyst",), ("SQL & Database", "Excel & BI", "Python & Statistics", "Critical Thinking")),
    (
        ("ai engineer", "ml engineer", "scientist"),
        ("Python Programming", "Statistics & Probability", "Machine Learning", "Data Preprocessing"),
    ),
)
LIVE_TOPICS = (
    (("health", "clinical"), "Healthcare Data Fundamentals"),
    (("security", "soc"), "Critical Thinking"),
    (("backend", "software", "qa"), "Data Structures & Algorithms"),
    (("analyst",), "SQL & Database"),
    (("engineer", "scientist"), "Python Programming"),
)


def stable_id(namespace: str, *parts: str) -> str:
    return namespace + "-" + hashlib.sha256(repr(tuple(parts)).encode()).hexdigest()[:24]


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def fingerprint(text: str, kind: str, options=()) -> str:
    signature = (kind, normalized(text), tuple(sorted(normalized(option) for option in options)))
    return hashlib.sha256(repr(signature).encode()).hexdigest()


def role_weight(role: str, topic: str) -> float:
    name = normalized(role)
    relevant = next((topics for keys, topics in ROLE_TOPICS if any(k in name for k in keys)), ())
    live = next((topic_name for keys, topic_name in LIVE_TOPICS if any(k in name for k in keys)), None)
    if topic in relevant or topic == live:
        return 1.0
    return 0.6 if topic in CORE_TOPICS else 0.3


def blueprint(role: str) -> dict:
    live = next(
        (topic for keys, topic in LIVE_TOPICS if any(k in normalized(role) for k in keys)),
        "Python Programming",
    )
    return {
        "sections": [
            {"topic_id": stable_id("topic", topic), "levels": ["easy", "medium"]}
            for topic in (*CORE_TOPICS, live)
        ],
        "weight_version": "prototype-v1",
    }
