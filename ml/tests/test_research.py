import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from app.ml.features import FEATURES, Observation, features_for
from app.services.prediction import model_bundle

from ml.evaluation.train import run
from ml.features.build import build, label_future
from ml.simulation.generate import Simulation, export, simulate
from scripts.import_source_data import CLEAN


@pytest.fixture(scope="module")
def research(tmp_path_factory):
    root = tmp_path_factory.mktemp("longitudinal")
    folder = root / "simulated"
    export(folder, CLEAN, Simulation())
    return root, folder


def test_reproducible_simulation_and_foreign_keys(research):
    _, folder = research
    first = pd.read_csv(folder / "assessments.csv", parse_dates=["date"])
    regenerated, topics, subs = simulate(CLEAN, Simulation())
    pd.testing.assert_frame_equal(first, regenerated, check_dtype=False)
    assert len(first) == 600 and first.student_id.nunique() == 100 and first.baseline.sum() == 100
    assert first.assessment_id.is_unique and first.groupby("student_id").size().eq(6).all()
    assert first.groupby("student_id").date.diff().dropna().dt.days.eq(14).all()
    assert set(topics.assessment_id) == set(first.assessment_id) == set(subs.assessment_id)
    assert len(topics) == 4200 and len(subs) == 12600
    assert all(
        frame[column].between(0, 100).all()
        for frame, column in [(first, "readiness"), (topics, "score"), (subs, "score")]
    )


def test_future_label_censoring_and_no_feature_leakage(research):
    t = datetime(2026, 1, 1, tzinfo=UTC)
    history = [Observation(t, 50, "A"), Observation(t + timedelta(days=14), 70, "A")]
    assert label_future(history, 0) == (None, False, "censored")
    assert label_future(history + [Observation(t + timedelta(days=70), 80, "A")], 0) == (
        0,
        True,
        "observed_negative",
    )
    assert label_future(history + [Observation(t + timedelta(days=50), 80, "A")], 0) == (
        1,
        False,
        "observed_positive",
    )
    assert features_for(history[:1])["previous"] is None and features_for(history)["previous"] == 50
    _, folder = research
    data = build(folder)
    assert data.groupby("student_id").split.nunique().eq(1).all()
    assert data.loc[data.ready_within_60_days == 0, "complete_followup"].all()
    assert data.loc[~data.complete_followup, "ready_within_60_days"].dropna().eq(1).all()
    assert data.sort_values("date").groupby("student_id").tail(1).next_score.isna().all()
    assert set(FEATURES).isdisjoint(
        {"student_id", "assessment_id", "next_score", "ready_within_60_days", "pattern"}
    )


def test_model_training_and_verified_artifacts(research, monkeypatch):
    root, folder = research
    artifacts = root / "artifacts"
    report = root / "research"
    selected = run(folder, artifacts, report)
    assert set(selected) == {"classification", "regression"}
    assert all("unavailable" not in value for value in selected.values())
    classification = pd.read_csv(report / "classification_results.csv")
    regression = pd.read_csv(report / "regression_results.csv")
    assert len(classification) == len(regression) == 3
    assert classification.roc_auc.between(0, 1).all()
    assert regression.mae.ge(0).all()
    from app.core.config import settings

    monkeypatch.setattr(settings(), "model_artifact_dir", artifacts)
    model, _ = model_bundle("regression")
    assert model["synthetic"] and model["held_out"] == 75
    path = artifacts / "regression.json"
    bad = json.loads(path.read_text()) | {"sha256": "0" * 64}
    path.write_text(json.dumps(bad))
    assert model_bundle("regression") is None
