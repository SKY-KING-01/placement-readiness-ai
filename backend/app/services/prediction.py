import hashlib
import io
import json
import logging
from functools import lru_cache

import catboost
import joblib
import pandas as pd
import sklearn
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.ml.features import FEATURE_VERSION, FEATURES, features_for
from app.models import MLFeatureSnapshot, MLModelVersion, MLPrediction
from app.services.catalog import stable_id
from app.services.history import observations, standardized
from app.services.scoring import READINESS_THRESHOLD, SCORING_VERSION

log = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def validated_model(artifact_path, expected_hash, modified_at):
    # Only load artifacts produced locally by the trusted training script.
    blob = artifact_path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != expected_hash:
        raise ValueError("Model artifact digest mismatch")
    return joblib.load(io.BytesIO(blob))


def model_bundle(task):
    folder = settings().model_artifact_dir
    try:
        metadata = json.loads((folder / f"{task}.json").read_text(encoding="utf-8"))
        if (
            metadata["task"] != task
            or metadata["feature_version"] != FEATURE_VERSION
            or metadata["scoring_version"] != SCORING_VERSION
            or metadata["features"] != list(FEATURES)
            or metadata["versions"]["sklearn"] != sklearn.__version__
            or metadata["versions"]["catboost"] != catboost.__version__
            or not metadata["synthetic"]
            or metadata["held_out"] < 10
        ):
            return None
        artifact = folder / f"{task}.joblib"
        if not artifact.is_file():
            return None
        # Include file modification time to invalidate a warm-process cache.
        return metadata, validated_model(artifact, metadata["sha256"], artifact.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError, EOFError, ImportError, TypeError):
        log.warning("Local %s model artifact is unavailable or invalid", task)
        return None


def upsert(db, model, **values):
    db.execute(insert(model).values(**values).on_conflict_do_nothing())


def predict(db, student, persist=True):
    rows = standardized(db, student.id)
    if not rows:
        return {"status": "insufficient_history", "classification": None, "regression": None}
    if not all(item.synthetic for item, _, _ in rows) or not settings().synthetic_demo_predictions:
        return {"status": "synthetic_validation_only", "classification": None, "regression": None}
    attempt, readiness, _ = rows[-1]
    features = features_for(observations(db, rows))
    frame = pd.DataFrame([features], columns=FEATURES)
    for col in FEATURES:
        if col != "role":
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype(float)
    response = {
        "status": "model_unavailable",
        "classification": None,
        "regression": None,
        "assessment_id": attempt.id,
        "synthetic": True,
    }
    for task in ("classification", "regression"):
        if task == "classification" and (len(rows) != 1 or readiness.score >= READINESS_THRESHOLD):
            response["classification_status"] = (
                "already_ready" if readiness.score >= READINESS_THRESHOLD else "outside_validated_landmark"
            )
            continue
        loaded = model_bundle(task)
        if loaded is None:
            continue
        metadata, model = loaded
        if task == "classification":
            value = float(model.predict_proba(frame)[0, 1])
        else:
            value = min(100.0, max(0.0, float(model.predict(frame[metadata["input"]])[0])))
        response[task] = {
            "value": value,
            "algorithm": metadata["algorithm"],
            "model_id": metadata["model_id"],
        }
        response["status"] = "synthetic_demo"
        if persist:
            snapshot = stable_id("feature", attempt.id, FEATURE_VERSION)
            upsert(
                db,
                MLFeatureSnapshot,
                id=snapshot,
                assessment_id=attempt.id,
                version=FEATURE_VERSION,
                features=features,
            )
            upsert(
                db,
                MLModelVersion,
                id=metadata["model_id"],
                task=task,
                algorithm=metadata["algorithm"],
                metadata_json=metadata,
            )
            upsert(
                db,
                MLPrediction,
                id=stable_id("prediction", snapshot, metadata["model_id"]),
                snapshot_id=snapshot,
                model_id=metadata["model_id"],
                value=value,
            )
    return response


def prediction_history(db, student_id, limit, offset):
    assessment_ids = [item.id for item, _, _ in standardized(db, student_id)]
    rows = db.execute(
        select(MLPrediction, MLModelVersion)
        .join(MLModelVersion, MLModelVersion.id == MLPrediction.model_id)
        .join(MLFeatureSnapshot, MLFeatureSnapshot.id == MLPrediction.snapshot_id)
        .where(MLFeatureSnapshot.assessment_id.in_(assessment_ids))
        .order_by(MLPrediction.created_at.desc(), MLPrediction.id)
        .limit(limit)
        .offset(offset)
    )
    return [
        {
            "value": pred.value,
            "task": model.task,
            "algorithm": model.algorithm,
            "model_id": model.id,
            "date": pred.created_at,
            "synthetic": True,
        }
        for pred, model in rows
    ]
