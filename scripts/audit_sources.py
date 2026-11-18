"""Rebuild the source inventory and quality notes without editing originals."""

import argparse
import hashlib
import importlib.util
import re
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source"
OPTIONS = ("Option A", "Option B", "Option C", "Option D")


def table(book, name):
    rows = iter(book[name].values)
    headers = next(rows, ())
    return [dict(zip(headers, row, strict=True)) for row in rows if any(x is not None for x in row)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation", type=Path, default=SOURCE / "AI_ML.pptx")
    args = parser.parse_args()
    script = next(SOURCE.glob("*.py"))
    spec = importlib.util.spec_from_file_location("original_preprocessing", script)
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    raw = next(SOURCE.glob("unprocessed*.xlsx"))
    clean = next(SOURCE.glob("cleaned*.xlsx"))
    paths = [raw, clean, script, args.presentation]
    inventory = ["# Source audit", "", "| File | Bytes | SHA-256 |", "| --- | ---: | --- |"]
    dictionary = ["# Source data dictionary"]
    summaries = []
    for path in paths:
        if not path.is_file():
            inventory.append(f"| {path.name} | unavailable | — |")
            continue
        inventory.append(
            f"| {path.name} | {path.stat().st_size:,} | `{hashlib.sha256(path.read_bytes()).hexdigest()}` |"
        )
        if path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")
            continue
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Invalid office archive {path.name}")
        if path.suffix == ".pptx":
            deck = Presentation(path)
            summaries.append(
                f"The {len(deck.slides)}-slide deck describes assessment, role-aware diagnosis, "
                "a personalized roadmap, mentorship and placement analytics. It proposes "
                "a 12-role × 39-skill matrix from high/medium/low relevance. The two workbooks "
                "lack that matrix. Use versioned prototype weights and record their provenance."
            )
            continue
        dictionary.extend(
            [
                "",
                f"## {path.name}",
                "",
                "Dimensions exclude the header. Types describe nonempty Excel cells as read by openpyxl.",
            ]
        )
        with closing(load_workbook(path, read_only=True)) as book:
            for sheet in book:
                rows = table(book, sheet.title)
                dictionary.extend(
                    [
                        "",
                        f"### {sheet.title}",
                        "",
                        f"{len(rows):,} records × {sheet.max_column} columns.",
                        "",
                        "| Column | Observed types | Missing |",
                        "| --- | --- | ---: |",
                    ]
                )
                if not rows:
                    dictionary.append("| — | Chart or empty sheet | — |")
                    continue
                for column in rows[0]:
                    counts = Counter(type(r[column]).__name__ for r in rows)
                    missing = counts.pop("NoneType", 0)
                    dictionary.append(f"| {column} | {', '.join(sorted(counts)) or '—'} | {missing:,} |")
    original_raw = pipeline.read_tables(raw)
    recovered = pipeline.preprocess(original_raw)
    supplied = pipeline.read_tables(clean)
    pipeline.validate_tables(pipeline.preprocess(supplied))
    pipeline.compare_to_source(supplied, recovered)
    recovered_lines = [
        "| Core sheet | Raw records | Distinct keys | Exact duplicate rows | Missing cells | Recovered records |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, frame in original_raw.items():
        recovered_lines.append(
            f"| {name} | {len(frame):,} | {len(frame.drop_duplicates(pipeline.KEYS[name])):,} | "
            f"{frame.duplicated().sum():,} | {frame.isna().sum().sum():,} | {len(recovered[name]):,} |"
        )
    with closing(load_workbook(clean, read_only=True)) as book:
        questions = table(book, "Question_Bank")
        usable = table(book, "Usable_Questions")
        date_options = Counter(
            str(q["Question id"])
            for q in questions
            for column in OPTIONS
            if isinstance(q[column], date) or re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$", str(q[column]))
        )
        if set(date_options) != {q["Question id"] for q in questions} - {q["Question id"] for q in usable}:
            raise ValueError("Question review and usable question IDs disagree")
        assessments = table(book, "Assessments")
        role_names = {r["Target_Role"] for r in assessments + table(book, "Career_Profile")}
        readiness = Counter(r["Readiness_Level"] for r in assessments)
        topics = table(book, "Topic_Scores")
        subtopics = table(book, "Subtopic_Scores")
        families = Counter((r["Topic_ID"][:5], r["Topic_Name"]) for r in topics)
        examples = [
            f"Baseline assessment example: `{assessments[0]['Assessment_ID']}` is a {assessments[0]['Assessment_Type']}.",
            f"Topic example: `{topics[0]['Topic_ID']}` represents {topics[0]['Topic_Name']}. "
            f"Its first subtopic is `{subtopics[0]['Subtopic_ID']}` ({subtopics[0]['Subtopic_Name']}).",
            f"Question example: `{questions[0]['Question id']}` has category {questions[0]['Category']} "
            f"and difficulty {questions[0]['Difficulty']}.",
        ]
    for name, lines in {
        "source_audit": inventory
        + [
            "",
            *summaries,
            "",
            *examples,
            "",
            "The deck is available separately and contains student names and roll numbers. Keep it out of Git.",
            "",
            "The Python pipeline validates the nine source schemas, parses typed fields, collapses exact and consistent "
            "same-key records, verifies scores and foreign keys, and fits demonstration transforms on training students only. "
            "Its reports and feature sheets are outputs. The import uses its validation and keeps the original values separately.",
        ],
        "data_dictionary": dictionary
        + ["", "See `migration_mapping.md` for primary keys, destinations, and validation rules."],
        "data_quality_report": [
            "# Data quality report",
            "",
            *recovered_lines,
            "",
            "The original pipeline recovered the raw workbook and matched normalized values and keys in the cleaned workbook. "
            "Student/assessment ownership, topic parents, score bounds and rollups passed the pipeline’s validation.",
            "",
            "Blank first-login dates are permitted. Injected defects include missing values, out-of-range scores, invalid "
            "dates, whitespace and repeated rows. No restoration of ambiguous question fractions was attempted.",
            "",
            f"{sum(date_options.values())} date-like answer options affect {len(date_options)} of {len(questions)} questions. "
            f"The source marks {len(usable)} as structurally usable. This check cannot establish factual correctness or company provenance.",
            "",
            f"The workbook has {len(role_names)} distinct role names across profiles and assessments, {len(families)} "
            "student-scoped topic records and repeated positional subtopic IDs. Normalize taxonomy by topic name and "
            "parent-plus-subtopic name while retaining the original scoped IDs.",
            "",
            f"Observed source readiness labels: {dict(sorted(readiness.items()))}. Every student has one baseline "
            "and no reassessment or item-level response records. Exclude future profiles, roadmaps, mentorship, identities, "
            "source readiness labels and held-out records from model fitting.",
        ],
    }.items():
        (ROOT / "docs" / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
