import csv
import io
import secrets
from datetime import UTC, datetime, timedelta

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import PASSWORDS
from app.models import (
    AssessmentQuestion,
    Question,
    ReadinessScore,
    RoleSkillWeight,
    Student,
    SubtopicScore,
    TopicScore,
    Trainer,
    User,
)
from app.services.catalog import stable_id

P = "/api/v1"
PASSWORD = "testing-a-unique-password"


def auth_header(response):
    assert response.is_success, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def student(client, name="Tara Test"):
    email = f"test-{secrets.token_hex(4)}@example.org"
    response = client.post(
        P + "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": name, "department": "Computer Science"},
    )
    return email, auth_header(response), response.json()


def staff(client, postgres, role):
    email = f"{role}-{secrets.token_hex(4)}@example.org"
    with Session(postgres[0]) as db, db.begin():
        user = User(email=email, role=role, display_name=role, password_hash=PASSWORDS.hash(PASSWORD))
        db.add(user)
        db.flush()
        key = user.id
        if role == "trainer":
            db.add(Trainer(user_id=key))
    return key, auth_header(client.post(P + "/auth/login", json={"email": email, "password": PASSWORD}))


def choose(client, headers):
    response = client.get(P + "/roles", headers=headers)
    role = next(item for item in response.json() if item["name"] == "Data Analyst")
    result = client.put(P + "/students/me/role", headers=headers, json={"role_id": role["id"]})
    assert result.json()["career_role"] == role
    return role


def complete(client, headers, postgres):
    response = client.post(P + "/assessments", headers=headers, json={})
    assert response.status_code == 201, response.text
    item = response.json()
    assert len(item["questions"]) == 8
    assert "answer" not in item["questions"][0]
    q = item["questions"][0]
    with Session(postgres[0]) as db:
        label = db.get(AssessmentQuestion, q["id"]).snapshot["answer"]
    path = P + "/assessments/" + item["id"]
    assert client.post(
        path + "/responses", headers=headers, json={"question_id": q["id"], "option": label}
    ).is_success
    result = client.post(path + "/submit", headers=headers)
    assert result.is_success, result.text
    assert 0 < result.json()["readiness"] < 100
    assert result.json()["coverage"]["assigned_questions"] == 8
    assert client.post(path + "/submit", headers=headers).json() == result.json()
    return item, result.json()


def test_migrations_import_and_foreign_keys(postgres):
    engine, first, repeated = postgres
    assert first["source_question_eligible"] == 1348
    assert len(first["flagged_question_ids"]) == 252
    assert all(value == 0 for value in repeated["inserted"].values())
    with Session(engine) as db:
        assert db.scalar(select(func.count(Student.id)).where(Student.synthetic)) == 100
        assert db.scalar(select(func.count(ReadinessScore.id))) >= 100
        assert db.scalar(select(func.count(TopicScore.id))) >= 700
        assert db.scalar(select(func.count(SubtopicScore.id))) >= 2100
        assert db.scalar(select(func.count(RoleSkillWeight.id))) >= 435
        assert db.scalar(select(func.count(Question.id)).where(Question.status == "quarantined")) == 252
        db.add(Student(user_id="no-such-user", department="Test"))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("Database accepted an orphan student")


def test_auth_rotation_and_role_guard(client):
    assert client.get(P + "/health").json()["status"] == "ok"
    email, headers, tokens = student(client)
    assert client.get(P + "/auth/me", headers=headers).json()["role"] == "student"
    assert client.get(P + "/admin/users", headers=headers).status_code == 403
    assert client.get(P + "/placement/overview", headers=headers).status_code == 403
    assert client.get(P + "/auth/me").status_code == 401
    refresh = {"refresh_token": tokens["refresh_token"]}
    assert client.post(P + "/auth/refresh", json=refresh).status_code == 200
    assert client.post(P + "/auth/refresh", json=refresh).status_code == 401
    assert client.post(P + "/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
    malicious = {
        "email": "new@example.org",
        "password": PASSWORD,
        "display_name": "A",
        "department": "B",
        "role": "admin",
    }
    rejected = client.post(P + "/auth/register", json=malicious)
    assert rejected.status_code == 422 and PASSWORD not in rejected.text


def test_student_journey_roadmap_and_reassessment(client, postgres):
    _, headers, _ = student(client)
    _, other, _ = student(client)
    assert (
        client.get(P + "/students/me/predictions", headers=headers).json()["status"] == "insufficient_history"
    )
    choose(client, headers)
    initial, _ = complete(client, headers, postgres)
    path = P + "/assessments/" + initial["id"]
    assert client.get(path, headers=other).status_code == 404
    assert (
        client.post(
            path + "/responses",
            headers=headers,
            json={"question_id": initial["questions"][0]["id"], "option": "A"},
        ).status_code
        == 409
    )
    assert (
        client.get(P + "/students/me/predictions", headers=headers).json()["status"]
        == "synthetic_validation_only"
    )
    fallback = client.get(P + "/students/me/roadmap", headers=headers).json()
    assert fallback["status"] == "fallback"
    task_id = fallback["roadmap"]["tasks"][0]["id"]
    task_path = P + "/students/me/roadmap/tasks/" + task_id
    assert client.patch(task_path, headers=other, json={"completed": True}).status_code == 404
    assert client.patch(task_path, headers=headers, json={"completed": True}).json()["completed"]
    scheduled = client.post(
        P + "/assessments",
        headers=headers,
        json={"scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    ).json()
    assert scheduled["status"] == "scheduled"
    assert (
        client.post(P + "/assessments/" + scheduled["id"] + "/activate", headers=headers).status_code == 409
    )
    second, _ = complete(client, headers, postgres)
    assert second["id"] != initial["id"]
    assert len(client.get(P + "/students/me/progress", headers=headers).json()["history"]) == 2
    assert (
        client.get(P + "/students/me/roadmap", headers=headers).json()["roadmap"]["assessment_id"]
        == second["id"]
    )


def test_adaptive_and_coding_storage(client, postgres, monkeypatch):
    _, headers, _ = student(client)
    _, other, _ = student(client)
    choose(client, headers)
    item = client.post(P + "/practice/start", headers=headers, json={"max_questions": 2}).json()
    url = P + "/practice/" + item["id"]
    first = client.get(url + "/next-question", headers=headers).json()["question"]
    assert client.get(url + "/next-question", headers=headers).json()["question"]["id"] == first["id"]
    assert client.post(
        url + "/responses",
        headers=headers,
        json={"question_id": first["id"], "option": first["options"][0]["label"]},
    ).is_success
    second = client.get(url + "/next-question", headers=headers).json()["question"]
    assert first["id"] != second["id"]
    assert (
        client.post(
            url + "/responses",
            headers=headers,
            json={"question_id": second["id"], "option": second["options"][0]["label"]},
        ).json()["status"]
        == "complete"
    )
    assert client.get(P + "/students/me/progress", headers=headers).json()["history"] == []
    with Session(postgres[0]) as db:
        snapshot = db.get(AssessmentQuestion, second["id"])
        assert snapshot.selection["version"] == "heuristic-v1"
    public = client.get(P + "/coding/questions", headers=headers)
    assert len(public.json()) == 2 and "hidden" not in public.text
    code = "  # Preserve submitted bytes\nprint('sample')\n"
    response = client.post(
        P + "/coding/submissions",
        headers=headers,
        json={"question_id": "practice-sum", "code": code, "language": "python3"},
    )
    assert response.status_code == 201 and response.json()["status"] == "execution_disabled"
    endpoint = P + "/coding/submissions/" + response.json()["id"]
    assert client.get(endpoint, headers=headers).json()["code"] == code
    assert client.get(endpoint, headers=other).status_code == 404
    assert client.post(endpoint + "/run-samples", headers=headers).status_code == 503
    from app.core.config import settings

    monkeypatch.setattr(settings(), "python_execution_enabled", True)
    run = client.post(endpoint + "/run-samples", headers=headers)
    assert run.status_code == 503 and run.json()["detail"]["code"] == "no_verified_worker"


def test_staff_assignment_privacy_and_question_import(client, postgres):
    _, admin = staff(client, postgres, "admin")
    trainer_key, trainer = staff(client, postgres, "trainer")
    _, placement = staff(client, postgres, "placement")
    _, learner, _ = student(client)
    sid = client.get(P + "/students/me", headers=learner).json()["id"]
    response = client.get(P + "/trainers/students/" + sid + "/analytics", headers=trainer)
    assert response.status_code == 404
    assign = client.post(
        P + "/admin/trainer-assignments", headers=admin, json={"user_id": trainer_key, "student_id": sid}
    )
    assert assign.status_code == 201, assign.text
    assert client.get(P + "/trainers/students/" + sid + "/analytics", headers=trainer).is_success
    assert client.get(P + "/placement/overview", headers=placement).json()["status"] == "cohort_suppressed"
    report = client.get(P + "/placement/overview?synthetic=true", headers=placement)
    assert report.is_success and report.json()["students"] == 100
    workshop = client.get(P + "/placement/workshop-recommendations?synthetic=true", headers=placement)
    assert workshop.is_success and all(row["students"] >= 5 for row in workshop.json())
    topic = stable_id("topic", "Communication")
    subtopic = stable_id("sub", "Communication", "Professional Communication")
    header = [
        "text",
        "category",
        "difficulty",
        "topic_id",
        "subtopic_id",
        "option_a",
        "option_b",
        "correct_option",
    ]
    title = "Which option makes a polite request? " + secrets.token_hex(3)
    valid = [title, "soft skills", "easy", topic, subtopic, "Please help.", "No.", "A"]
    invalid = ["Invalid workbook question", "soft skills", "easy", topic, subtopic, "2026-10-01", "No.", "A"]
    stream = io.StringIO()
    csv.writer(stream).writerows([header, valid, valid, invalid])
    path = P + "/admin/questions/import"
    files = {"file": ("questions.csv", stream.getvalue().encode(), "text/csv")}
    preview = client.post(path, headers=admin, files=files)
    assert preview.is_success and (preview.json()["valid"], preview.json()["invalid"]) == (1, 2), preview.text
    result = client.post(path + "?preview=false", headers=admin, files=files)
    assert result.is_success and result.json()["status"] == "pending_approval", result.text
    item = client.get(P + "/admin/questions", headers=admin, params={"q": title}).json()[0]
    assert item["status"] == "pending"
    assert client.post(
        P + "/trainers/questions/" + item["id"] + "/reviews",
        headers=trainer,
        json={"detail": "Options are clear."},
    ).is_success
    assert client.post(P + "/admin/questions/" + item["id"] + "/approve", headers=admin).is_success
    change = {k: v for k, v in item.items() if k not in {"id", "status"}}
    change["text"] = title + " Reviewed revision."
    edited = client.patch(P + "/admin/questions/" + item["id"], headers=admin, json=change)
    assert edited.is_success and edited.json()["status"] == "pending", edited.text
    assert client.post(P + "/admin/questions/" + item["id"] + "/deactivate", headers=admin).is_success
    assert client.post(P + "/admin/questions/" + item["id"] + "/approve", headers=admin).status_code == 409
    new_book = Workbook()
    new_book.active.append(header)
    new_book.active.append(["Workbook import sample", *valid[1:]])
    new_book.active.append(["Formula option", *valid[1:5], "=1+2", "No.", "A"])
    content = io.BytesIO()
    new_book.save(content)
    workbook = client.post(path, headers=admin, files={"file": ("questions.xlsx", content.getvalue())})
    assert workbook.is_success and workbook.json()["valid"] == 1, workbook.text
    assert workbook.json()["invalid"] == 1 and "Formula" in workbook.json()["issues"][0]["issues"][0]
    company = client.post(P + "/admin/companies", headers=admin, json={"name": "Demo Company"}).json()
    renamed = client.patch(
        P + "/admin/companies/" + company["id"], headers=admin, json={"name": "Renamed Company"}
    )
    assert renamed.json()["name"] == "Renamed Company"
    extra = client.post(P + "/admin/roles", headers=admin, json={"name": "Demo Engineer"}).json()
    removed = client.patch(P + "/admin/roles/" + extra["id"], headers=admin, json={"active": False})
    assert removed.is_success
    assert not any(item["id"] == extra["id"] for item in client.get(P + "/roles", headers=learner).json())
    role = choose(client, learner)
    skill = client.get(P + "/roles/" + role["id"] + "/skills", headers=admin).json()[0]
    weight = 0.3 if skill["weight"] != 0.3 else 1.0
    changed = client.patch(
        P + "/admin/roles/" + role["id"] + "/weights",
        headers=admin,
        json={"skill_id": skill["id"], "weight": weight},
    )
    assert changed.is_success, changed.text
    skills = client.get(P + "/roles/" + role["id"] + "/skills", headers=admin).json()
    assert next(e for e in skills if e["id"] == skill["id"])["weight"] == weight


def test_synthetic_prediction_history(client, postgres):
    _, headers, _ = student(client)
    choose(client, headers)
    sid = client.get(P + "/students/me", headers=headers).json()["id"]
    with Session(postgres[0]) as db, db.begin():
        db.get(Student, sid).synthetic = True
    complete(client, headers, postgres)
    result = client.get(P + "/students/me/predictions", headers=headers).json()
    assert result["status"] == "synthetic_demo", result
    assert 0 <= result["classification"]["value"] <= 1
    assert 0 <= result["regression"]["value"] <= 100
    history = client.get(P + "/students/me/prediction-history", headers=headers)
    assert history.is_success and len(history.json()) == 2
