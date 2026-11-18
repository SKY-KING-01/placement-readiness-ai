from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.integrations import openai_client
from app.services import roadmap
from app.services.adaptive import Candidate, rank
from app.services.python_runner import EvaluationRequest, score_results
from app.services.python_runner import TestCase as Case
from app.services.python_runner import TestResult as Result
from app.services.scoring import percentage, response_scores, weighted_mean


def test_scoring_includes_only_measured_topics():
    rows, topics, total = response_scores(
        [
            ("a", "x", 2, 2),
            ("a", "y", 0, 1),
            ("b", "z", 1, 2),
        ],
        {"a": 1, "b": 0.6, "outside": 0.3},
    )
    assert rows == {("a", "x"): 100, ("a", "y"): 0, ("b", "z"): 50}
    assert topics == {"a": 66.6667, "b": 50}
    assert total == pytest.approx(60.4167)
    assert weighted_mean({}, {}) is None
    with pytest.raises(ValueError):
        percentage(11, 10)
    with pytest.raises(ValueError):
        weighted_mean({"x": 65}, {"y": 0.3})


def test_adaptive_rank_and_weighted_mock_scores():
    question = Candidate("Q1", "Topic", "easy", True)
    rank1, trace = rank(question, {"Topic": 0.2}, {"Topic": 1}, set(), set())
    rank2, _ = rank(question, {"Topic": 0.8}, {"Topic": 1}, set(), set())
    assert rank1 > rank2 and trace["components"]["company"] == 1
    assert rank(question, {}, {}, set(), {"Q1"}) is None
    cases = [
        Case("sample", {"stdin": "1"}, {"stdout": "1"}, 1, True),
        Case("hidden", {"stdin": "2"}, {"stdout": "2"}, 3, False),
    ]

    # This grader only returns predetermined test results. It never interprets source.
    class MockEvaluator:
        def evaluate(self, request: EvaluationRequest):
            return tuple(Result(case.id, case.public) for case in request.cases)

    results = MockEvaluator().evaluate(EvaluationRequest("python3", "placeholder", tuple(cases), 2, 128))
    assert score_results(cases, results, True) == 25
    assert score_results(cases, results, False) == 0
    with pytest.raises(ValueError):
        score_results(cases, results[:1], True)


def test_openai_structured_mock_and_fallback(monkeypatch):
    evidence = {
        "target_role": "Data Analyst",
        "current_readiness": 61.0,
        "weekly_hours": 3,
        "skills": ["SQL & Database"],
        "resource_ids": ["postgresql-tutorial"],
    }
    proposal = roadmap.fallback(evidence)
    config = SimpleNamespace(
        openai_api_key=SecretStr("mock"),
        openai_model="mock-model",
        openai_timeout_seconds=4,
        openai_max_retries=1,
        openai_input_price_per_million=0.1,
        openai_output_price_per_million=0.2,
    )

    class Mock:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 4 and kwargs["max_retries"] == 1
            self.responses = self

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def parse(self, **kwargs):
            assert kwargs["model"] == "mock-model" and not kwargs["store"]
            assert "email" not in kwargs["input"][1]["content"]
            assert kwargs["text_format"] is type(proposal)
            return SimpleNamespace(
                output_parsed=proposal, usage=SimpleNamespace(input_tokens=30, output_tokens=50)
            )

    monkeypatch.setattr(openai_client, "OpenAI", Mock)
    assert roadmap.is_grounded(openai_client.generate(config, evidence), evidence)
    assert not roadmap.is_grounded(
        proposal.model_copy(update={"recommended_resources": ["unknown"]}), evidence
    )
    assert not roadmap.is_grounded(
        proposal.model_copy(update={"explanation": "Try https://unverified.org"}), evidence
    )
    blank = SimpleNamespace(openai_api_key=SecretStr(""), openai_model="")
    assert openai_client.generate(blank, evidence) is None
    assert roadmap.fallback(evidence) == roadmap.fallback(evidence)
