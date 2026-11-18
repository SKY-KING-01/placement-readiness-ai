from pydantic import BaseModel, ConfigDict, Field

from .common import Input


class RoadmapRequest(Input):
    weekly_hours: int = Field(default=5, ge=1, le=40)


class TaskChange(Input):
    completed: bool


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Week(StrictOutput):
    week: int = Field(ge=1, le=12)
    focus: str = Field(min_length=1, max_length=160)
    hours: int = Field(ge=1, le=40)
    tasks: list[str] = Field(min_length=1, max_length=5)


class Roadmap(StrictOutput):
    target_role: str = Field(min_length=1, max_length=120)
    current_readiness: float = Field(ge=0, le=100)
    duration_weeks: int = Field(ge=1, le=12)
    priority_skills: list[str] = Field(min_length=1, max_length=8)
    weekly_plan: list[Week] = Field(min_length=1, max_length=12)
    practice_tasks: list[str] = Field(max_length=16)
    recommended_resources: list[str] = Field(max_length=12)
    reassessment_milestones: list[str] = Field(max_length=8)
    explanation: str = Field(min_length=1, max_length=1200)
