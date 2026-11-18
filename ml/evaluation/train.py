"""Train and evaluate reproducible synthetic-readiness research models."""

import argparse
import hashlib
import json
import platform
from datetime import timedelta
from pathlib import Path

import catboost
import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn
from app.core.config import ROOT
from app.ml.features import FEATURE_VERSION, FEATURES
from app.services.scoring import SCORING_VERSION
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)

from ml.classification.models import classifiers
from ml.features.build import build
from ml.regression.models import regressors

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def partition(frame):
    return tuple(frame.loc[frame.split == name] for name in ("train", "validation", "test"))


def store_model(folder, task, pipeline, algorithm, metadata):
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f"{task}.joblib.tmp"
    joblib.dump(pipeline, temporary, compress=3)
    artifact = folder / f"{task}.joblib"
    temporary.replace(artifact)
    details = {
        "task": task,
        "algorithm": algorithm,
        "feature_version": FEATURE_VERSION,
        "scoring_version": SCORING_VERSION,
        "synthetic": True,
        "features": list(FEATURES),
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "versions": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "catboost": catboost.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        **metadata,
    }
    details["model_id"] = hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()
    target = folder / f"{task}.json"
    staging = target.with_suffix(".tmp")
    staging.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    staging.replace(target)


def classify(data, artifacts, research, seed):
    target = "ready_within_60_days"
    # Complete follow-up is required for every benchmark record, including positives,
    # to avoid making mere assessment age an artifact of label observability.
    known = data.loc[data.complete_followup & data[target].notna()]
    train, val, test = partition(known)
    if any(part[target].nunique() != 2 for part in (train, val, test)):
        raise ValueError("Classification needs two observed classes in each held-out cohort")
    models = classifiers(seed)
    metrics, candidates = [], {}
    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    for name, model in models.items():
        columns = list(FEATURES)
        model.fit(train[columns], train[target].astype(int))
        probability_val = model.predict_proba(val[columns])[:, 1]
        ap = average_precision_score(val[target], probability_val)
        threshold = max(
            np.linspace(0.20, 0.80, 25),
            key=lambda value: (
                f1_score(val[target], probability_val >= value, zero_division=0),
                -abs(value - 0.5),
            ),
        )
        probabilities = model.predict_proba(test[columns])[:, 1]
        change = probabilities >= threshold
        tn, fp, fn, tp = confusion_matrix(test[target], change, labels=[0, 1]).ravel()
        record = dict(
            model=name,
            validation_pr_auc=ap,
            threshold=threshold,
            n=len(test),
            precision=precision_score(test[target], change, zero_division=0),
            recall=recall_score(test[target], change, zero_division=0),
            f1=f1_score(test[target], change, zero_division=0),
            roc_auc=roc_auc_score(test[target], probabilities),
            pr_auc=average_precision_score(test[target], probabilities),
            brier=brier_score_loss(test[target], probabilities),
            tn=int(tn),
            fp=int(fp),
            fn=int(fn),
            tp=int(tp),
        )
        metrics.append(record)
        candidates[name] = (ap, -brier_score_loss(val[target], probability_val), threshold)
        p, r, _ = precision_recall_curve(test[target], probabilities)
        ax.step(r, p, where="post", label=name)
    ax.axhline(float(test[target].mean()), color="gray", linestyle=":", label="Test prevalence")
    ax.set(
        xlabel="Recall",
        ylabel="Precision",
        title="Synthetic follow-up classification",
        xlim=(0, 1),
        ylim=(0, 1.03),
    )
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(research / "figures/classification_precision_recall.png", dpi=160)
    plt.close(fig)
    winner = max(candidates, key=lambda name: candidates[name][:2])
    store_model(
        artifacts,
        "classification",
        models[winner],
        winner,
        {
            "cutoff": float(candidates[winner][2]),
            "landmark": "first_assessment_only",
            "held_out": len(test),
            "positive_cases": int(test[target].sum()),
            "negative_cases": int((test[target] == 0).sum()),
            "seed": seed,
        },
    )
    pd.DataFrame(metrics).to_csv(research / "classification_results.csv", index=False, float_format="%.6f")
    summary = ", ".join(
        f"{name} {len(part)} ({int(part[target].sum())} positive)"
        for name, part in zip(("train", "validation", "test"), (train, val, test), strict=True)
    )
    (research / "classification_comparison.md").write_text(
        f"# Readiness classification\n\nSelected **{winner}** by validation average precision, using validation "
        f"Brier score as the tie-breaker. The decision threshold was chosen by validation F1. Cohorts: {summary}. "
        "Metrics in the CSV are from held-out students. Probabilities were not recalibrated because the "
        "validation sample was small. Complete 60-day follow-up is available for first attempts only. "
        "The deployed demonstration therefore limits readiness probabilities to that landmark; "
        "it does not estimate real placement outcomes.\n",
        encoding="utf-8",
    )
    return winner


def regression(data, artifacts, research, seed):
    train, val, test = partition(data.loc[data.next_score.notna()])
    target = "next_score"
    columns = list(FEATURES)
    models = regressors(seed)
    scores, slices = [], []
    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    for name, model in models.items():
        used = ["current"] if name == "Last score" else columns
        model.fit(train[used], train[target])
        prediction = np.clip(model.predict(test[used]), 0, 100)
        validation = np.clip(model.predict(val[used]), 0, 100)
        scores.append(
            dict(
                model=name,
                n=len(test),
                validation_mae=mean_absolute_error(val[target], validation),
                mae=mean_absolute_error(test[target], prediction),
                rmse=root_mean_squared_error(test[target], prediction),
                r2=r2_score(test[target], prediction),
            )
        )
        per_row = test.assign(
            error=np.abs(test[target] - prediction),
            readiness_group=pd.cut(
                test.current, [-1, 60, 75, 101], labels=["developing", "near", "ready"], right=False
            ),
        )
        for group_type in ("readiness_group", "role"):
            for key, group in per_row.groupby(group_type, observed=True):
                if group.student_id.nunique() >= 5:
                    slices.append(
                        dict(
                            model=name,
                            group_type=group_type,
                            group=key,
                            n=len(group),
                            students=group.student_id.nunique(),
                            mae=group.error.mean(),
                        )
                    )
        if name != "Last score":
            ax.scatter(test[target], prediction, label=name, alpha=0.55, s=18)
    ax.plot([0, 100], [0, 100], linestyle=":", color="gray")
    ax.set(
        xlabel="Observed synthetic next score", ylabel="Predicted next score", xlim=(30, 100), ylim=(30, 100)
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(research / "figures/regression_observed_vs_predicted.png", dpi=160)
    plt.close(fig)
    winner = min(scores, key=lambda item: item["validation_mae"])["model"]
    store_model(
        artifacts,
        "regression",
        models[winner],
        winner,
        {"seed": seed, "held_out": len(test), "input": ["current"] if winner == "Last score" else columns},
    )
    pd.DataFrame(scores).to_csv(research / "regression_results.csv", index=False, float_format="%.6f")
    pd.DataFrame(slices).to_csv(research / "regression_subgroups.csv", index=False, float_format="%.6f")
    (research / "regression_comparison.md").write_text(
        f"# Next-score regression\n\nSelected **{winner}** by validation MAE. The test cohort has {len(test)} "
        f"outcomes from {test.student_id.nunique()} held-out students. The target is the next standardized "
        "assessment after the feature date. The subgroup CSV requires at least five distinct students per slice. "
        "Sample size and synthetic distributions do not support validated uncertainty intervals.\n",
        encoding="utf-8",
    )
    return winner


def chronological_regression(data, research, seed):
    """Fit before the first final-landmark test date using only observed training outcomes."""
    known = data.loc[data.next_score.notna()]
    test = known.loc[(known.split == "test") & (known.assessment_count >= 5)]
    if test.empty:
        return
    cutoff = test.date.min()
    train = known.loc[(known.split == "train") & (known.next_date < cutoff)]
    if train.empty:
        return
    results = []
    for name, model in regressors(seed).items():
        columns = ["current"] if name == "Last score" else list(FEATURES)
        model.fit(train[columns], train.next_score)
        predictions = np.clip(model.predict(test[columns]), 0, 100)
        results.append(
            {
                "model": name,
                "cutoff": cutoff.isoformat(),
                "train_rows": len(train),
                "test_rows": len(test),
                "mae": mean_absolute_error(test.next_score, predictions),
                "rmse": root_mean_squared_error(test.next_score, predictions),
            }
        )
    pd.DataFrame(results).to_csv(
        research / "regression_temporal_results.csv", index=False, float_format="%.6f"
    )


def record_split_checks(data, research, horizon):
    earliest_test = data.loc[data.split == "test", "date"].min()
    rows = data.loc[(data.split == "train") & data.complete_followup & data.ready_within_60_days.notna()]
    eligible = rows.loc[rows.date + timedelta(days=horizon) < earliest_test]
    (research / "temporal_validation.md").write_text(
        "# Calendar validation\n\n"
        f"The earliest held-out baseline is {earliest_test.date()}. Only {len(eligible)} training landmarks "
        "have completed the full classification horizon before that date. A strict calendar-forward "
        "classification benchmark is therefore unavailable in this cohort. The classification CSV uses "
        "disjoint student cohorts ordered by baseline date, with overlapping follow-up calendars. "
        "The secondary regression CSV restricts training to outcomes observed before the first held-out "
        "fifth-attempt landmark. It uses different students and a later calendar cutoff, so its errors "
        "should be interpreted separately from the main regression comparison.\n",
        encoding="utf-8",
    )


def run(folder, artifacts, research):
    research.mkdir(parents=True, exist_ok=True)
    (research / "figures").mkdir(exist_ok=True)
    config = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))["config"]
    data = build(folder, config["horizon_days"], config["threshold"])
    data[
        [
            "student_id",
            "assessment_id",
            "date",
            "split",
            "ready_within_60_days",
            "complete_followup",
            "label_status",
            "next_score",
        ]
    ].to_csv(research / "synthetic_labels.csv", index=False)
    outcomes = {}
    for name, operation in (("classification", classify), ("regression", regression)):
        try:
            outcomes[name] = operation(data, artifacts, research, config["seed"])
        except ValueError as error:
            outcomes[name] = f"unavailable: {error}"
            (research / f"{name}_comparison.md").write_text(
                f"# {name.title()}\n\n{outcomes[name]}\n", encoding="utf-8"
            )
            for file in (
                artifacts / f"{name}.json",
                artifacts / f"{name}.joblib",
                research / f"{name}_results.csv",
            ):
                file.unlink(missing_ok=True)
    record_split_checks(data, research, config["horizon_days"])
    chronological_regression(data, research, config["seed"])
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/synthetic/reassessments")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "ml/artifacts")
    parser.add_argument("--research", type=Path, default=ROOT / "research")
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.artifacts, args.research), indent=2))


if __name__ == "__main__":
    main()
