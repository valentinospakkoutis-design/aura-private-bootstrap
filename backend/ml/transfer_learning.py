"""Transfer learning training flow for cross-asset model reuse."""

from __future__ import annotations

import glob
import os
import pickle
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from database.models import ModelRegistry
from ml.auto_trainer import engineer_features, fetch_ohlcv

MIN_ACCURACY = 0.55
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def _candidate_model_paths(symbol: str) -> List[str]:
    symbol_u = str(symbol or "").upper()
    return [
        os.path.join(MODELS_DIR, f"{symbol_u}_xgboost_latest.pkl"),
        os.path.join(MODELS_DIR, f"{symbol_u}_ensemble_latest.pkl"),
        os.path.join(MODELS_DIR, f"{symbol_u}_xgboost_threshold_latest.pkl"),
    ]


def _load_model_artifact(symbol: str) -> Dict:
    for path in _candidate_model_paths(symbol):
        if os.path.exists(path):
            with open(path, "rb") as f:
                obj = pickle.load(f)
            if isinstance(obj, dict):
                return obj

    # Fallback: newest versioned xgboost artifact for the symbol.
    pattern = os.path.join(MODELS_DIR, f"{symbol.upper()}_xgboost_v*.pkl")
    candidates = sorted(glob.glob(pattern), reverse=True)
    if candidates:
        with open(candidates[0], "rb") as f:
            obj = pickle.load(f)
        if isinstance(obj, dict):
            return obj

    return {}


def _extract_feature_importances(artifact: Dict) -> Dict[str, float]:
    feature_cols = artifact.get("feature_cols") or []
    model = artifact.get("model") or artifact.get("xgb_model")

    if feature_cols and model is not None and hasattr(model, "feature_importances_"):
        importances = getattr(model, "feature_importances_", None)
        if importances is not None and len(importances) == len(feature_cols):
            imp = np.asarray(importances, dtype=float)
            imp = np.nan_to_num(imp, nan=0.0)
            total = float(imp.sum())
            if total > 0:
                imp = imp / total
            return {str(col): float(val) for col, val in zip(feature_cols, imp)}

    if feature_cols:
        weight = 1.0 / float(len(feature_cols))
        return {str(col): weight for col in feature_cols}

    return {}


def get_base_model_features(db: Session) -> Tuple[Dict[str, float], str]:
    """Load best active model from registry and return feature-importance knowledge."""
    row = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.is_active == True, ModelRegistry.accuracy.isnot(None))
        .order_by(ModelRegistry.accuracy.desc(), ModelRegistry.trained_at.desc())
        .first()
    )
    if row is None:
        return {}, ""

    base_symbol = str(row.symbol or "").upper()
    artifact = _load_model_artifact(base_symbol)
    base_features = _extract_feature_importances(artifact)

    # Last resort if artifact did not expose importances.
    if not base_features and row.features_used:
        cols = [c.strip() for c in str(row.features_used).split(",") if c.strip()]
        if cols:
            weight = 1.0 / float(len(cols))
            base_features = {c: weight for c in cols}

    return base_features, base_symbol


def train_with_transfer(symbol: str, db: Session) -> Dict:
    """Train target symbol model using feature priors from best active source model."""
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is not installed") from exc

    symbol_u = str(symbol or "").upper()
    if not symbol_u:
        raise ValueError("symbol is required")

    base_features, base_model_symbol = get_base_model_features(db)
    if not base_model_symbol:
        raise ValueError("No active base model found in model_registry")

    df = fetch_ohlcv(symbol_u, days=730)
    if df is None or len(df) < 200:
        raise ValueError(f"Insufficient price history for {symbol_u}")

    feat = engineer_features(df)
    if feat is None or feat.empty or len(feat) < 120:
        raise ValueError(f"Insufficient engineered features for {symbol_u}")

    exclude_cols = {
        "target", "label_threshold", "open", "high", "low", "close", "volume", "quote_volume", "trades"
    }
    feature_cols = [c for c in feat.columns if c not in exclude_cols]
    if len(feature_cols) < 10:
        raise ValueError(f"Not enough feature columns for {symbol_u}")

    X = feat[feature_cols].fillna(0.0).values
    y = (feat["target"].values > feat["close"].values).astype(int)

    split_idx = int(len(X) * 0.8)
    if split_idx < 80 or split_idx >= len(X) - 5:
        raise ValueError("Train/test split too small for transfer training")

    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    feature_weights = np.array([float(base_features.get(c, 0.0)) for c in feature_cols], dtype=float)
    if float(feature_weights.sum()) <= 0.0:
        feature_weights = np.ones(len(feature_cols), dtype=float)
    feature_weights = feature_weights / float(feature_weights.sum())
    feature_weights = np.clip(feature_weights * len(feature_weights), 1e-6, None)

    non_zero_ratio = float(np.count_nonzero(feature_weights)) / float(len(feature_weights))
    base_score = float(min(0.7, max(0.3, non_zero_ratio)))

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.1,
        reg_lambda=1.0,
        base_score=base_score,
        random_state=42,
        n_jobs=-1,
        eval_metric="logloss",
        verbosity=0,
    )

    fit_kwargs = {
        "eval_set": [(X_test_scaled, y_test)],
        "verbose": False,
    }
    # xgboost versions differ; use feature weights when supported.
    try:
        model.fit(X_train_scaled, y_train, feature_weights=feature_weights, **fit_kwargs)
    except TypeError:
        model.fit(X_train_scaled, y_train, **fit_kwargs)

    y_pred = model.predict(X_test_scaled)
    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))

    previous_row = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.symbol == symbol_u, ModelRegistry.accuracy.isnot(None))
        .order_by(ModelRegistry.trained_at.desc())
        .first()
    )
    previous_accuracy = float(previous_row.accuracy) if previous_row and previous_row.accuracy is not None else 0.0
    improvement = float(accuracy - previous_accuracy)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_payload = {
        "model": model,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "symbol": symbol_u,
        "model_type": "xgboost_transfer",
        "trained_at": datetime.utcnow().isoformat(),
        "transfer_from": base_model_symbol,
        "metrics": {
            "test_accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "benchmark_min_accuracy": MIN_ACCURACY,
            "previous_accuracy": previous_accuracy,
            "improvement": improvement,
        },
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    version_path = os.path.join(MODELS_DIR, f"{symbol_u}_xgboost_transfer_v{timestamp}.pkl")
    latest_path = os.path.join(MODELS_DIR, f"{symbol_u}_xgboost_transfer_latest.pkl")
    with open(version_path, "wb") as f:
        pickle.dump(model_payload, f)
    with open(latest_path, "wb") as f:
        pickle.dump(model_payload, f)

    db.query(ModelRegistry).filter(ModelRegistry.symbol == symbol_u).update({"is_active": False})
    db.add(
        ModelRegistry(
            symbol=symbol_u,
            model_version="transfer_v1",
            accuracy=accuracy,
            precision_score=precision,
            recall_score=recall,
            training_samples=int(len(X_train)),
            features_used=",".join(feature_cols),
            is_active=bool(accuracy >= MIN_ACCURACY),
        )
    )
    db.commit()

    return {
        "symbol": symbol_u,
        "accuracy": round(accuracy, 4),
        "transfer_from": base_model_symbol,
        "improvement": round(improvement, 4),
        "passed_benchmark": bool(accuracy >= MIN_ACCURACY),
    }
