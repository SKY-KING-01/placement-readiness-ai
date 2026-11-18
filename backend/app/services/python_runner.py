"""Interface for a separately verified grading worker. The HTTP process never executes submissions."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TestCase:
    id: str
    inputs: dict
    expected: dict
    weight: float
    public: bool


@dataclass(frozen=True)
class EvaluationRequest:
    language: str
    code: str
    cases: tuple[TestCase, ...]
    seconds: int
    memory_mb: int
    max_output_bytes: int = 8192
    function: str | None = None


@dataclass(frozen=True)
class TestResult:
    case_id: str
    passed: bool
    runtime_ms: int | None = None


class IsolatedEvaluator(Protocol):
    def evaluate(self, request: EvaluationRequest) -> tuple[TestResult, ...]: ...


def execution_status(configured: bool):
    if configured:
        return "no_verified_worker"
    return "execution_disabled"


def score_results(cases, results, partial):
    expected = {case.id: case.weight for case in cases}
    weights = {row.case_id: row.passed for row in results}
    if not expected or len(results) != len(expected) or set(weights) != set(expected):
        raise ValueError("Worker result must cover each assigned case exactly once")
    if not partial:
        return float(all(weights.values())) * 100
    return 100 * sum(value for key, value in expected.items() if weights[key]) / sum(expected.values())
