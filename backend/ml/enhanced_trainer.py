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
from sklearn.metrics import accuracy_score, precision_score, recall_score

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


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
    """Train enhanced ensemble model for a single symbol."""
    try:
        import xgboost as xgb
    except ImportError:
        logger.error("xgboost not installed")
        return None

    from database.models import ModelRegistry

    df = load_features(db_session, symbol)
    if df is None:
        return None

    # Prepare features
    meta_cols = [c for c in df.columns if c.startswith("_")]
    feature_cols = [c for c in df.columns if not c.startswith("_")]
    if not feature_cols:
        return None

    X = df[feature_cols].fillna(0).values
    y = (df["_target_direction"] == "up").astype(int).values

    # Walk-forward validation
    wf_results = walk_forward_validate(X, y, train_size=min(500, len(X) - 60), test_size=30)
    avg_accuracy = np.mean([r["accuracy"] for r in wf_results]) if wf_results else 0

    # Final model: train on all data
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split for final metrics (80/20)
    split = int(len(X) * 0.8)
    X_train, X_test = X_scaled[:split], X_scaled[split:]
    y_train, y_test = y[:split], y[split:]

    # XGBoost
    xgb_model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.01,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", verbosity=0, n_jobs=-1,
        early_stopping_rounds=50, random_state=42,
    )
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # RandomForest
    rf_model = RandomForestClassifier(
        n_estimators=200, max_depth=8, random_state=42, n_jobs=-1
    )
    rf_model.fit(X_train, y_train)

    # Ensemble predictions
    xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
    rf_proba = rf_model.predict_proba(X_test)[:, 1]
    ensemble_proba = 0.6 * xgb_proba + 0.4 * rf_proba
    ensemble_pred = (ensemble_proba >= 0.5).astype(int)

    acc = float(accuracy_score(y_test, ensemble_pred))
    prec = float(precision_score(y_test, ensemble_pred, zero_division=0))
    rec = float(recall_score(y_test, ensemble_pred, zero_division=0))

    logger.info(f"[Phase4] {symbol}: WF-Acc={avg_accuracy:.3f}, Final-Acc={acc:.3f}, P={prec:.3f}, R={rec:.3f}")

    # Save model
    os.makedirs(MODELS_DIR, exist_ok=True)
    version = datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
    model_path = os.path.join(MODELS_DIR, f"{symbol}_ensemble_{version}.pkl")

    model_data = {
        "xgb_model": xgb_model,
        "rf_model": rf_model,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "symbol": symbol,
        "model_type": "ensemble_xgb_rf",
        "version": version,
        "metrics": {
            "walk_forward_accuracy": avg_accuracy,
            "final_accuracy": acc,
            "precision": prec,
            "recall": rec,
            "training_samples": split,
            "test_samples": len(y_test),
            "features_count": len(feature_cols),
        },
        "trained_at": datetime.utcnow().isoformat(),
    }

    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    # Also save as "latest"
    latest_path = os.path.join(MODELS_DIR, f"{symbol}_ensemble_latest.pkl")
    with open(latest_path, "wb") as f:
        pickle.dump(model_data, f)

    # Update model registry
    # Deactivate old models for this symbol
    db_session.query(ModelRegistry).filter(
        ModelRegistry.symbol == symbol
    ).update({"is_active": False})

    db_session.add(ModelRegistry(
        symbol=symbol,
        model_version=version,
        accuracy=acc,
        precision_score=prec,
        recall_score=rec,
        training_samples=split,
        features_used=",".join(feature_cols),
        is_active=True,
    ))
    db_session.commit()

    return {
        "symbol": symbol,
        "version": version,
        "walk_forward_accuracy": round(avg_accuracy, 4),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
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
