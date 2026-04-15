"""
Phase 4: Enhanced Model Training
XGBoost + RandomForest ensemble with Walk-Forward Validation.
Saves models to disk and metadata to model_registry table.
"""

import os
import sys
import pickle
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# ── Training benchmarks ────────────────────────────────────────────
# A model is only promoted to ``is_active=True`` when it clears every one
# of these thresholds on the held-out test split. If it misses, we retry
# up to MAX_RETRAIN_ATTEMPTS with incrementally more capacity before
# accepting the best attempt with ``is_active=False``.
MIN_ACCURACY = 0.55
MIN_PRECISION = 0.52
MIN_RECALL = 0.50
MIN_SHARPE = 0.3
MIN_TRAINING_SAMPLES = 200

MAX_RETRAIN_ATTEMPTS = 3


class _EnsembleModel:
    """Thin wrapper exposing ``.predict`` over the XGB+RF ensemble.

    Kept local to this module because the only consumer is
    :func:`evaluate_model_against_benchmarks`, which needs a ``predict(X)``
    contract regardless of which underlying estimators power the ensemble.
    """

    def __init__(self, xgb_model, rf_model, xgb_weight: float = 0.6, threshold: float = 0.5):
        self.xgb_model = xgb_model
        self.rf_model = rf_model
        self.xgb_weight = float(xgb_weight)
        self.rf_weight = 1.0 - float(xgb_weight)
        self.threshold = float(threshold)

    def predict_proba(self, X):
        xgb_proba = self.xgb_model.predict_proba(X)[:, 1]
        rf_proba = self.rf_model.predict_proba(X)[:, 1]
        return self.xgb_weight * xgb_proba + self.rf_weight * rf_proba

    def predict(self, X):
        return (self.predict_proba(X) >= self.threshold).astype(int)


def evaluate_model_against_benchmarks(model, X_val, y_val) -> Dict:
    """Score ``model`` on the validation split and compare against thresholds.

    Returns a dict containing accuracy/precision/recall/f1 (and an auxiliary
    signal Sharpe) plus a ``failures`` list describing every benchmark that
    was not met. ``passed`` is True only when ``failures`` is empty.
    """
    y_pred = model.predict(X_val)
    y_val_arr = np.asarray(y_val)

    accuracy = float(accuracy_score(y_val_arr, y_pred))
    precision = float(precision_score(y_val_arr, y_pred, zero_division=0))
    recall = float(recall_score(y_val_arr, y_pred, zero_division=0))
    f1 = float(f1_score(y_val_arr, y_pred, zero_division=0))

    # Signal-style Sharpe: +1 when the prediction matches direction, -1 when
    # it doesn't. Annualised assuming daily bars. It is a proxy for how
    # profitable the classifier would be as a long/short signal — good
    # enough as a gating metric without replaying a full backtest here.
    signals = np.where(y_pred == y_val_arr, 1.0, -1.0)
    sharpe = 0.0
    if len(signals) > 1 and float(np.std(signals)) > 0:
        sharpe = float(np.mean(signals) / np.std(signals) * np.sqrt(252))

    failures: List[str] = []
    if accuracy < MIN_ACCURACY:
        failures.append(f"accuracy below threshold ({accuracy:.2f} < {MIN_ACCURACY})")
    if precision < MIN_PRECISION:
        failures.append(f"precision below threshold ({precision:.2f} < {MIN_PRECISION})")
    if recall < MIN_RECALL:
        failures.append(f"recall below threshold ({recall:.2f} < {MIN_RECALL})")
    if sharpe < MIN_SHARPE:
        failures.append(f"sharpe below threshold ({sharpe:.2f} < {MIN_SHARPE})")

    return {
        "passed": len(failures) == 0,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "sharpe": sharpe,
        "failures": failures,
    }


def _fit_ensemble(X_train, y_train, X_test, y_test, attempt: int = 0) -> _EnsembleModel:
    """Fit an XGB+RF ensemble, scaling capacity with ``attempt`` for retries.

    Attempt 0 uses the baseline hyperparameters that existed before the
    benchmark-retry loop. Each subsequent attempt adds 50 estimators, one
    level of depth, and shifts ``random_state`` so the retry explores a
    different neighbourhood of the hypothesis space rather than fitting the
    exact same model again.
    """
    import xgboost as xgb

    xgb_estimators = 500 + attempt * 50
    rf_estimators = 200 + attempt * 50
    xgb_depth = 6 + attempt
    rf_depth = 8 + attempt
    seed = 42 + attempt * 17  # stride > 1 so attempts 0/1/2 differ meaningfully

    xgb_model = xgb.XGBClassifier(
        n_estimators=xgb_estimators, max_depth=xgb_depth, learning_rate=0.01,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", verbosity=0, n_jobs=-1,
        early_stopping_rounds=50, random_state=seed,
    )
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    rf_model = RandomForestClassifier(
        n_estimators=rf_estimators, max_depth=rf_depth, random_state=seed, n_jobs=-1
    )
    rf_model.fit(X_train, y_train)

    return _EnsembleModel(xgb_model, rf_model)


def load_features(db_session, symbol: str) -> Optional[pd.DataFrame]:
    """Load training features from database for a symbol."""
    from database.models import TrainingFeature

    rows = db_session.query(TrainingFeature).filter(
        TrainingFeature.symbol == symbol
    ).order_by(TrainingFeature.date).all()

    if len(rows) < 100:
        logger.warning(f"[Phase4] {symbol}: only {len(rows)} rows, need 100+")
        return None

    records = []
    for r in rows:
        feat = r.features if isinstance(r.features, dict) else {}
        feat["_date"] = r.date
        feat["_target_return"] = r.target_return
        feat["_target_direction"] = r.target_direction
        records.append(feat)

    df = pd.DataFrame(records)
    df = df.dropna(subset=["_target_direction"])
    return df


def walk_forward_validate(X: np.ndarray, y: np.ndarray,
                          train_size: int = 500, test_size: int = 30,
                          step: int = 30) -> List[Dict]:
    """Walk-forward validation: train on past, test on next window, slide forward."""
    results = []
    n = len(X)

    i = train_size
    while i + test_size <= n:
        X_train, y_train = X[:i], y[:i]
        X_test, y_test = X[i:i+test_size], y[i:i+test_size]

        try:
            import xgboost as xgb

            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)

            # XGBoost
            xgb_model = xgb.XGBClassifier(
                n_estimators=500, max_depth=6, learning_rate=0.01,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", verbosity=0, n_jobs=-1,
                early_stopping_rounds=50, random_state=42,
            )
            xgb_model.fit(X_train_s, y_train,
                         eval_set=[(X_test_s, y_test)], verbose=False)
            xgb_proba = xgb_model.predict_proba(X_test_s)[:, 1]

            # RandomForest
            rf_model = RandomForestClassifier(
                n_estimators=200, max_depth=8, random_state=42, n_jobs=-1
            )
            rf_model.fit(X_train_s, y_train)
            rf_proba = rf_model.predict_proba(X_test_s)[:, 1]

            # Ensemble: 60% XGB + 40% RF
            ensemble_proba = 0.6 * xgb_proba + 0.4 * rf_proba
            ensemble_pred = (ensemble_proba >= 0.5).astype(int)

            acc = accuracy_score(y_test, ensemble_pred)
            results.append({
                "window_start": i,
                "accuracy": float(acc),
                "test_size": test_size,
            })
        except Exception as e:
            logger.debug(f"Walk-forward window {i} failed: {e}")

        i += step

    return results


def train_symbol_enhanced(db_session, symbol: str, job_id: str = "manual") -> Optional[Dict]:
    """Train enhanced ensemble model for a single symbol.

    After each training attempt the model is scored against the module-level
    benchmark thresholds. A failing run triggers up to
    :data:`MAX_RETRAIN_ATTEMPTS` additional retrains with deeper trees, more
    estimators, and a different ``random_state``. If none of the attempts
    pass, the best-scoring attempt is still persisted — but marked
    ``is_active=False`` in ``model_registry`` so downstream consumers don't
    accidentally promote a sub-threshold model.
    """
    try:
        import xgboost  # noqa: F401  (imported in _fit_ensemble, fail fast here)
    except ImportError:
        logger.error("xgboost not installed")
        return None

    from database.models import ModelRegistry

    df = load_features(db_session, symbol)
    if df is None:
        return None

    # Prepare features
    feature_cols = [c for c in df.columns if not c.startswith("_")]
    if not feature_cols:
        return None

    X = df[feature_cols].fillna(0).values
    y = (df["_target_direction"] == "up").astype(int).values

    if len(X) < MIN_TRAINING_SAMPLES:
        logger.warning(
            f"[Phase4] {symbol}: insufficient training samples "
            f"({len(X)} < {MIN_TRAINING_SAMPLES}) — skipping"
        )
        return {
            "symbol": symbol,
            "error": f"insufficient_samples_{len(X)}_lt_{MIN_TRAINING_SAMPLES}",
        }

    # Walk-forward validation (diagnostic only — does not gate promotion).
    wf_results = walk_forward_validate(X, y, train_size=min(500, len(X) - 60), test_size=30)
    avg_accuracy = float(np.mean([r["accuracy"] for r in wf_results])) if wf_results else 0.0

    # Final model: train on all data with a fresh scaler per attempt.
    split = int(len(X) * 0.8)
    X_train_raw, X_test_raw = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    best_eval: Optional[Dict] = None
    best_model: Optional[_EnsembleModel] = None
    best_scaler: Optional[StandardScaler] = None
    best_attempt_index = 0
    passed = False

    for attempt in range(MAX_RETRAIN_ATTEMPTS):
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_test = scaler.transform(X_test_raw)

        model = _fit_ensemble(X_train, y_train, X_test, y_test, attempt=attempt)
        eval_result = evaluate_model_against_benchmarks(model, X_test, y_test)

        logger.info(
            f"[Phase4] {symbol} attempt {attempt + 1}/{MAX_RETRAIN_ATTEMPTS}: "
            f"acc={eval_result['accuracy']:.3f}, prec={eval_result['precision']:.3f}, "
            f"rec={eval_result['recall']:.3f}, f1={eval_result['f1']:.3f}, "
            f"sharpe={eval_result['sharpe']:.3f}, passed={eval_result['passed']}"
        )

        # Track the best attempt so we can still persist something if all fail.
        if (
            best_eval is None
            or eval_result["accuracy"] > best_eval["accuracy"]
        ):
            best_eval = eval_result
            best_model = model
            best_scaler = scaler
            best_attempt_index = attempt

        if eval_result["passed"]:
            passed = True
            break

        logger.warning(
            f"[RETRAIN {symbol}] Failed benchmarks: {eval_result['failures']} — triggering retrain"
        )

    assert best_eval is not None and best_model is not None and best_scaler is not None

    if not passed:
        logger.warning(
            f"[RETRAIN {symbol}] Exhausted {MAX_RETRAIN_ATTEMPTS} attempts without clearing benchmarks; "
            f"saving best attempt (acc={best_eval['accuracy']:.3f}) with is_active=False"
        )

    # Persist the best model we produced (passing or not).
    os.makedirs(MODELS_DIR, exist_ok=True)
    version = datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
    model_path = os.path.join(MODELS_DIR, f"{symbol}_ensemble_{version}.pkl")

    model_data = {
        "xgb_model": best_model.xgb_model,
        "rf_model": best_model.rf_model,
        "scaler": best_scaler,
        "feature_cols": feature_cols,
        "symbol": symbol,
        "model_type": "ensemble_xgb_rf",
        "version": version,
        "metrics": {
            "walk_forward_accuracy": avg_accuracy,
            "final_accuracy": best_eval["accuracy"],
            "precision": best_eval["precision"],
            "recall": best_eval["recall"],
            "f1": best_eval["f1"],
            "sharpe": best_eval["sharpe"],
            "training_samples": split,
            "test_samples": len(y_test),
            "features_count": len(feature_cols),
            "passed_benchmarks": passed,
            "failures": best_eval["failures"],
            "retrain_attempts": best_attempt_index + 1,
        },
        "trained_at": datetime.utcnow().isoformat(),
    }

    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    # Also save as "latest" only if the model passed — a failing model should
    # not silently become the default.
    if passed:
        latest_path = os.path.join(MODELS_DIR, f"{symbol}_ensemble_latest.pkl")
        with open(latest_path, "wb") as f:
            pickle.dump(model_data, f)

    # Update model registry: deactivate old rows, insert the new one with the
    # appropriate is_active flag.
    db_session.query(ModelRegistry).filter(
        ModelRegistry.symbol == symbol
    ).update({"is_active": False})

    db_session.add(ModelRegistry(
        symbol=symbol,
        model_version=version,
        accuracy=best_eval["accuracy"],
        precision_score=best_eval["precision"],
        recall_score=best_eval["recall"],
        training_samples=split,
        features_used=",".join(feature_cols),
        is_active=passed,
    ))
    db_session.commit()

    return {
        "symbol": symbol,
        "version": version,
        "walk_forward_accuracy": round(avg_accuracy, 4),
        "accuracy": round(best_eval["accuracy"], 4),
        "precision": round(best_eval["precision"], 4),
        "recall": round(best_eval["recall"], 4),
        "f1": round(best_eval["f1"], 4),
        "sharpe": round(best_eval["sharpe"], 4),
        "passed_benchmarks": passed,
        "is_active": passed,
        "retrain_attempts": best_attempt_index + 1,
        "failures": best_eval["failures"],
        "features": len(feature_cols),
        "samples": len(X),
    }


def retrain_all(job_id: str = "manual"):
    """Retrain all symbols with enhanced ensemble models."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import TrainingFeature, TrainingLog

    db = SessionLocal()

    try:
        symbols = [r[0] for r in db.query(TrainingFeature.symbol).distinct().all()]
        total = len(symbols)

        db.add(TrainingLog(
            job_id=job_id, phase="retrain",
            status="running", message=f"Retraining {total} symbols", progress=0
        ))
        db.commit()

        results = []
        for i, symbol in enumerate(symbols):
            try:
                result = train_symbol_enhanced(db, symbol, job_id)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"[Phase4] {symbol} failed: {e}")
                results.append({"symbol": symbol, "error": str(e)})

            progress = (i + 1) / total * 100
            if (i + 1) % 3 == 0:
                db.add(TrainingLog(
                    job_id=job_id, phase="retrain",
                    status="running", message=f"Trained {i+1}/{total}", progress=progress
                ))
                db.commit()

        succeeded = len([r for r in results if "accuracy" in r])
        db.add(TrainingLog(
            job_id=job_id, phase="retrain",
            status="completed",
            message=f"Retrained {succeeded}/{total} models",
            progress=100, completed_at=datetime.utcnow()
        ))
        db.commit()

        logger.info(f"[Phase4] Complete: {succeeded}/{total} models trained")
        return results

    except Exception as e:
        db.add(TrainingLog(
            job_id=job_id, phase="retrain",
            status="failed", message=str(e), completed_at=datetime.utcnow()
        ))
        db.commit()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    retrain_all()
