from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from .common import Input


class StartAssessment(Input):
    scheduled_at: AwareDatetime | None = None


class Answer(Input):
    question_id: str = Field(min_length=1, max_length=80)
    option: str = Field(min_length=1, max_length=8)


class StartPractice(Input):
    company_id: str | None = Field(default=None, max_length=80)
    max_questions: int = Field(default=5, ge=1, le=20)


class CodingSubmissionInput(Input):
    question_id: str = Field(min_length=1, max_length=80)
    language: str = Field(default="python3", pattern="^python3$")
    code: Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=20000)]
