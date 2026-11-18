import re
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from app.services.catalog import normalized

from .common import Input


class CaseInput(Input):
    public: bool = False
    inputs: dict
    expected: dict
    weight: float = Field(default=1, gt=0, le=100)


class QuestionInput(Input):
    text: str = Field(min_length=4, max_length=10000)
    kind: Literal["mcq", "python_io", "python_function"] = "mcq"
    category: Literal["aptitude", "sql", "technical", "python", "reasoning", "soft skills"]
    difficulty: Literal["easy", "medium", "hard"]
    topic_id: str = Field(min_length=1, max_length=80)
    subtopic_id: str | None = Field(default=None, max_length=80)
    skill_id: str | None = Field(default=None, max_length=80)
    role_id: str | None = Field(default=None, max_length=80)
    company_ids: list[str] = Field(default_factory=list, max_length=20)
    year: int | None = Field(default=None, ge=1900, le=2100)
    placement_round: str | None = Field(default=None, max_length=100)
    source_url: AnyHttpUrl | None = None
    verification: Literal["practice", "verified"] = "practice"
    explanation: str | None = Field(default=None, max_length=10000)
    options: list[str] = Field(default_factory=list, max_length=8)
    answer: int | None = Field(default=None, ge=0, le=7)
    cases: list[CaseInput] = Field(default_factory=list, max_length=40)
    function: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z_0-9]{0,63}$")
    seconds: int = Field(default=2, ge=1, le=10)
    memory_mb: int = Field(default=128, ge=32, le=512)
    partial: bool = False
    active: bool = True

    @field_validator("options")
    @classmethod
    def valid_options(cls, values):
        if any(
            not normalized(v) or len(v) > 3000 or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T].*)?", v.strip())
            for v in values
        ):
            raise ValueError(
                "Options must be nonempty reviewed text. Excel date conversions need source review."
            )
        if len(set(map(normalized, values))) != len(values):
            raise ValueError("Answer options must be distinct")
        return values

    @model_validator(mode="after")
    def validate_question(self):
        if self.verification == "verified" and (self.source_url is None or not self.company_ids):
            raise ValueError("Verified previous questions require a source URL and a company")
        if self.kind == "mcq":
            if (
                not self.subtopic_id
                or len(self.options) < 2
                or self.answer is None
                or self.answer >= len(self.options)
            ):
                raise ValueError("MCQs require a subtopic, two or more options and one valid correct index")
            if self.cases or self.function:
                raise ValueError("MCQs cannot include coding test cases")
        else:
            if self.options or self.answer is not None:
                raise ValueError("Coding questions use test cases for grading")
            if not any(c.public for c in self.cases) or not any(not c.public for c in self.cases):
                raise ValueError("Coding requires a sample and a hidden case")
            if self.kind == "python_function" and self.function is None:
                raise ValueError("Function-based questions require a function name")
            for case in self.cases:
                if self.kind == "python_io":
                    if (
                        set(case.inputs) != {"stdin"}
                        or set(case.expected) != {"stdout"}
                        or not all(
                            isinstance(x, str) for x in [case.inputs["stdin"], case.expected["stdout"]]
                        )
                    ):
                        raise ValueError("Input/output cases require stdin and stdout strings")
                elif (
                    not set(case.inputs) <= {"args", "kwargs"}
                    or set(case.expected) != {"return"}
                    or not isinstance(case.inputs.get("args", []), list)
                    or not isinstance(case.inputs.get("kwargs", {}), dict)
                ):
                    raise ValueError(
                        "Function cases require an args list or kwargs object and expected return"
                    )
        return self
