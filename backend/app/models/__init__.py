from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def new_id() -> str:
    return uuid4().hex


class Record(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Record):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('student','trainer','placement','admin')", name="role"),)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="student")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshSession(Record):
    __tablename__ = "refresh_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(default=False)


class CareerRole(Record):
    __tablename__ = "career_roles"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    active: Mapped[bool] = mapped_column(default=True)


class Student(Record):
    __tablename__ = "students"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    roll_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    synthetic: Mapped[bool] = mapped_column(default=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class Trainer(Record):
    __tablename__ = "trainers"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)


class TrainerAssignment(Record):
    __tablename__ = "trainer_assignments"
    __table_args__ = (UniqueConstraint("trainer_id", "student_id"),)
    trainer_id: Mapped[str] = mapped_column(ForeignKey("trainers.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)


class CareerProfile(Record):
    __tablename__ = "career_profiles"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), unique=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("career_roles.id"), index=True)
    source_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class Topic(Record):
    __tablename__ = "topics"
    name: Mapped[str] = mapped_column(String(180), unique=True)


class Subtopic(Record):
    __tablename__ = "subtopics"
    __table_args__ = (UniqueConstraint("topic_id", "name"), UniqueConstraint("topic_id", "id"))
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))


class Skill(Record):
    __tablename__ = "skills"
    name: Mapped[str] = mapped_column(String(180), unique=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)


class RoleSkillWeight(Record):
    __tablename__ = "role_skill_weights"
    __table_args__ = (
        UniqueConstraint("role_id", "skill_id", "version"),
        CheckConstraint("weight > 0 AND weight <= 1", name="weight_range"),
    )
    role_id: Mapped[str] = mapped_column(ForeignKey("career_roles.id"), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    version: Mapped[str] = mapped_column(String(40))
    weight: Mapped[float] = mapped_column(Float)


class Company(Record):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(150), unique=True)


class QuestionImportBatch(Record):
    __tablename__ = "question_import_batches"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    digest: Mapped[str] = mapped_column(String(64), index=True)
    report: Mapped[dict] = mapped_column(JSON)


class Question(Record):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("kind IN ('mcq','python_io','python_function')", name="kind"),
        CheckConstraint("difficulty IN ('easy','medium','hard')", name="difficulty"),
        CheckConstraint("status IN ('pending','approved','quarantined')", name="status"),
        CheckConstraint("verification IN ('practice','verified')", name="verification"),
        CheckConstraint("verification <> 'verified' OR source_url IS NOT NULL", name="provenance"),
    )
    text: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(40))
    difficulty: Mapped[str] = mapped_column(String(10))
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    subtopic_id: Mapped[str | None] = mapped_column(ForeignKey("subtopics.id"))
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"))
    role_id: Mapped[str | None] = mapped_column(ForeignKey("career_roles.id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("question_import_batches.id"))
    year: Mapped[int | None] = mapped_column(Integer)
    placement_round: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    verification: Mapped[str] = mapped_column(String(12), default="practice")
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    active: Mapped[bool] = mapped_column(default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class QuestionOption(Record):
    __tablename__ = "question_options"
    __table_args__ = (UniqueConstraint("question_id", "label"),)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    label: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(default=False)


class QuestionCompanyTag(Record):
    __tablename__ = "question_company_tags"
    __table_args__ = (UniqueConstraint("question_id", "company_id"),)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)


class QuestionReview(Record):
    __tablename__ = "question_reviews"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text)


class CodingTestCase(Record):
    __tablename__ = "coding_test_cases"
    __table_args__ = (CheckConstraint("weight > 0", name="positive_weight"),)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    public: Mapped[bool] = mapped_column(default=False)
    inputs: Mapped[dict] = mapped_column(JSON)
    expected: Mapped[dict] = mapped_column(JSON)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class AssessmentTemplate(Record):
    __tablename__ = "assessment_templates"
    __table_args__ = (UniqueConstraint("role_id", "version"),)
    role_id: Mapped[str] = mapped_column(ForeignKey("career_roles.id"))
    version: Mapped[str] = mapped_column(String(40))
    blueprint: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(default=True)


class Assessment(Record):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("student_id", "mode", "attempt"),
        CheckConstraint("attempt > 0", name="attempt"),
        CheckConstraint("mode IN ('baseline','standardized','practice')", name="mode"),
        CheckConstraint("status IN ('scheduled','open','submitted')", name="status"),
        Index("ix_assessments_student_date", "student_id", "taken_at"),
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("career_roles.id"))
    template_id: Mapped[str | None] = mapped_column(ForeignKey("assessment_templates.id"))
    attempt: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synthetic: Mapped[bool] = mapped_column(default=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class AssessmentQuestion(Record):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_id"),
        UniqueConstraint("assessment_id", "position"),
    )
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    selection: Mapped[dict] = mapped_column(JSON, default=dict)


class StudentResponse(Record):
    __tablename__ = "student_responses"
    assessment_question_id: Mapped[str] = mapped_column(ForeignKey("assessment_questions.id"), unique=True)
    option: Mapped[str] = mapped_column(String(8))
    earned: Mapped[float] = mapped_column(Float)


class CodingSubmission(Record):
    __tablename__ = "coding_submissions"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    language: Mapped[str] = mapped_column(String(20), default="python3")
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="execution_disabled")
    score: Mapped[float | None] = mapped_column(Float)


class CodingEvaluationResult(Record):
    __tablename__ = "coding_evaluation_results"
    __table_args__ = (UniqueConstraint("submission_id", "test_case_id"),)
    submission_id: Mapped[str] = mapped_column(ForeignKey("coding_submissions.id"))
    test_case_id: Mapped[str] = mapped_column(ForeignKey("coding_test_cases.id"))
    passed: Mapped[bool] = mapped_column(Boolean)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)


class TopicScore(Record):
    __tablename__ = "topic_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "topic_id"),
        UniqueConstraint("assessment_id", "source_topic_id"),
        CheckConstraint("score BETWEEN 0 AND 100", name="percentage"),
    )
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"))
    score: Mapped[float] = mapped_column(Float)
    source_topic_id: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class SubtopicScore(Record):
    __tablename__ = "subtopic_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "subtopic_id"),
        UniqueConstraint("assessment_id", "source_topic_id", "source_subtopic_id"),
        ForeignKeyConstraint(
            ["assessment_id", "topic_id"],
            ["topic_scores.assessment_id", "topic_scores.topic_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["topic_id", "subtopic_id"], ["subtopics.topic_id", "subtopics.id"]),
        CheckConstraint("score BETWEEN 0 AND 100", name="percentage"),
    )
    assessment_id: Mapped[str] = mapped_column(String(80), index=True)
    topic_id: Mapped[str] = mapped_column(String(80))
    subtopic_id: Mapped[str] = mapped_column(String(80))
    score: Mapped[float] = mapped_column(Float)
    source_topic_id: Mapped[str | None] = mapped_column(String(80))
    source_subtopic_id: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[dict] = mapped_column(JSON, default=dict)


class ReadinessScore(Record):
    __tablename__ = "readiness_scores"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="percentage"),)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    version: Mapped[str] = mapped_column(String(40))
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)


class MLFeatureSnapshot(Record):
    __tablename__ = "ml_feature_snapshots"
    __table_args__ = (UniqueConstraint("assessment_id", "version"),)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    features: Mapped[dict] = mapped_column(JSON)


class MLModelVersion(Record):
    __tablename__ = "ml_model_versions"
    task: Mapped[str] = mapped_column(String(24), index=True)
    algorithm: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSON)


class MLPrediction(Record):
    __tablename__ = "ml_predictions"
    __table_args__ = (UniqueConstraint("snapshot_id", "model_id"),)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("ml_feature_snapshots.id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("ml_model_versions.id"))
    value: Mapped[float] = mapped_column(Float)


class LearningRoadmap(Record):
    __tablename__ = "learning_roadmaps"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    provider: Mapped[str] = mapped_column(String(24))
    version: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON)


class RoadmapTask(Record):
    __tablename__ = "roadmap_tasks"
    roadmap_id: Mapped[str] = mapped_column(ForeignKey("learning_roadmaps.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    week: Mapped[int] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(default=False)


class MentorshipSession(Record):
    __tablename__ = "mentorship_sessions"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    source: Mapped[dict] = mapped_column(JSON)


class WorkshopRecommendation(Record):
    __tablename__ = "workshop_recommendations"
    __table_args__ = (UniqueConstraint("topic_id", "method"),)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"))
    priority: Mapped[float] = mapped_column(Float)
    participants: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(40))


class AuditLog(Record):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
