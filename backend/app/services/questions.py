import csv
import hashlib
import io
import re
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.models import (
    CareerRole,
    CodingTestCase,
    Company,
    Question,
    QuestionCompanyTag,
    QuestionOption,
    Skill,
    Subtopic,
    Topic,
)
from app.schemas.questions import QuestionInput
from app.services.catalog import fingerprint

MAX_UPLOAD_BYTES = 2_000_000
MAX_ROWS = 500
INVALID_CELL = object()
IMPORT_COLUMNS = {
    "text",
    "category",
    "difficulty",
    "topic_id",
    "subtopic_id",
    "skill_id",
    "role_id",
    "company_id",
    "year",
    "placement_round",
    "source_url",
    "verification",
    "explanation",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
}


def valid_refs(db, payload):
    topic = db.get(Topic, payload.topic_id)
    subtopic = db.get(Subtopic, payload.subtopic_id) if payload.subtopic_id else None
    skill = db.get(Skill, payload.skill_id) if payload.skill_id else None
    if (
        not topic
        or (payload.subtopic_id and (not subtopic or subtopic.topic_id != topic.id))
        or (payload.skill_id and (not skill or skill.topic_id != topic.id))
    ):
        raise ValueError("Unknown topic or incompatible subtopic or skill")
    if payload.role_id and not db.get(CareerRole, payload.role_id):
        raise ValueError("Career role does not exist")
    if any(not db.get(Company, identifier) for identifier in payload.company_ids):
        raise ValueError("Company does not exist")


def existing_duplicate(db, mark, existing=None):
    stmt = select(Question.id).where(Question.fingerprint == mark, Question.active)
    if existing:
        stmt = stmt.where(Question.id != existing)
    return db.scalar(stmt.limit(1)) is not None


def save_question(db, payload, question=None, batch_id=None):
    valid_refs(db, payload)
    mark = fingerprint(payload.text, payload.kind, payload.options)
    if existing_duplicate(db, mark, question.id if question else None):
        raise ValueError("A matching active question already exists")
    values = payload.model_dump(
        mode="json",
        exclude={"options", "answer", "cases", "company_ids", "function", "seconds", "memory_mb", "partial"},
    )
    values.update(
        fingerprint=mark,
        status="pending",
        settings={
            "function": payload.function,
            "seconds": payload.seconds,
            "memory_mb": payload.memory_mb,
            "partial": payload.partial,
        },
    )
    if question is None:
        question = Question(**values, batch_id=batch_id)
        db.add(question)
        db.flush()
    else:
        for key, value in values.items():
            setattr(question, key, value)
        # Historical assessment snapshots retain their original options. Existing
        # evaluated coding cases must be retained for audit, so reject changing a
        # coding item once it has been used.
        for model in (QuestionOption, QuestionCompanyTag, CodingTestCase):
            db.execute(delete(model).where(model.question_id == question.id))
    db.add_all(
        QuestionOption(question_id=question.id, label=chr(65 + i), text=value, correct=i == payload.answer)
        for i, value in enumerate(payload.options)
    )
    db.add_all(
        QuestionCompanyTag(question_id=question.id, company_id=value)
        for value in sorted(set(payload.company_ids))
    )
    db.add_all(CodingTestCase(question_id=question.id, **case.model_dump()) for case in payload.cases)
    db.flush()
    return question


def upload_grid(filename, data):
    suffix = Path(filename).suffix.lower()
    stream = io.BytesIO(data)
    if suffix == ".csv":
        yield from csv.reader(io.StringIO(data.decode("utf-8-sig")), strict=True)
    elif suffix == ".xlsx":
        with ZipFile(stream) as z:
            if len(z.infolist()) > 200 or sum(x.file_size for x in z.infolist()) > 20_000_000:
                raise ValueError("Workbook exceeds the uncompressed import limit")
        book = load_workbook(stream, read_only=True, keep_links=False)
        try:
            for row in book.active.iter_rows(max_col=len(IMPORT_COLUMNS) + 1):
                yield [cell.value if cell.data_type not in {"f", "e"} else INVALID_CELL for cell in row]
        finally:
            book.close()
    else:
        raise ValueError("Upload a UTF-8 CSV or an XLSX file")


def inspect_import(db, filename, data):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Upload a nonempty file up to 2 MB")
    records, problems, seen = [], [], set()
    try:
        stream = upload_grid(filename, data)
        header = [str(field).strip().lower() if field is not None else "" for field in next(stream, ())]
        while header and not header[-1]:
            header.pop()
        required = {
            "text",
            "category",
            "difficulty",
            "topic_id",
            "subtopic_id",
            "option_a",
            "option_b",
            "correct_option",
        }
        if (
            not required <= set(header)
            or not set(header) <= IMPORT_COLUMNS
            or len(set(header)) != len(header)
        ):
            raise ValueError("Use the documented CSV header with topic and subtopic IDs")
        for number, row in enumerate(stream, 2):
            if number > MAX_ROWS + 1:
                raise ValueError("Upload at most 500 data rows")
            if not any(value not in (None, "") for value in row):
                continue
            field = {
                key: str(value).strip()
                for key, value in zip(header, row)
                if value is not None and str(value).strip()
            }
            try:
                if any(value is INVALID_CELL for value in row):
                    raise ValueError("Formula or error cells require review")
                if any(value not in (None, "") for value in row[len(header) :]):
                    raise ValueError("Unexpected cells past the last defined header")
                options = [field.pop(f"option_{key}", "") for key in "abcd"]
                while options and not options[-1]:
                    options.pop()
                answer = field.pop("correct_option", "").upper()
                if not re.fullmatch(r"[A-D]", answer):
                    raise ValueError("Correct option must be A, B, C or D")
                company = field.pop("company_id", None)
                for key in ("category", "difficulty", "verification"):
                    if key in field:
                        field[key] = field[key].lower()
                payload = QuestionInput(
                    **field,
                    options=options,
                    answer=ord(answer) - ord("A"),
                    company_ids=[company] if company else [],
                )
                valid_refs(db, payload)
                mark = fingerprint(payload.text, payload.kind, payload.options)
                if mark in seen or existing_duplicate(db, mark):
                    raise ValueError("Duplicate question detected")
                seen.add(mark)
                records.append(payload)
            except ValidationError as error:
                problems.append({"row": number, "issues": [item["msg"] for item in error.errors()]})
            except ValueError as error:
                problems.append({"row": number, "issues": [str(error)]})
    except (ValueError, csv.Error, BadZipFile, KeyError, OSError, TypeError, ParseError) as error:
        raise HTTPException(422, str(error)) from error
    return records, {
        "valid": len(records),
        "invalid": len(problems),
        "issues": problems,
        "digest": hashlib.sha256(data).hexdigest(),
    }
