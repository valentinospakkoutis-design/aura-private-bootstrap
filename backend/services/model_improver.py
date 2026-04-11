"""Self-improvement layer for XGBoost models using real trade feedback."""

import os
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from database.connection import SessionLocal
from ml.auto_trainer import (
    MODELS_DIR,
    TRAINING_SYMBOLS,
    YFINANCE_SYMBOL_MAP,
    engineer_features,
    fetch_binance_ohlcv,
    fetch_yfinance_ohlcv,
)


def _ensure_schema() -> None:
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS trade_feedback (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                confidence_at_entry FLOAT,
                entry_price FLOAT,
                exit_price FLOAT,
                pnl_pct FLOAT,
                outcome VARCHAR,
                features_snapshot JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_trade_feedback_symbol_created ON trade_feedback (symbol, created_at DESC)"))
        db.execute(text("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1"))
        db.execute(text("ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS improved_at TIMESTAMP"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def save_trade_feedback(
    symbol: str,
    action: str,
    entry_price: float,
    exit_price: float,
    confidence: float,
    features_snapshot: Optional[dict],
) -> None:
    _ensure_schema()
    entry = float(entry_price or 0.0)
    exit_px = float(exit_price or 0.0)
    if entry <= 0 or exit_px <= 0:
        return

    pnl_pct = ((exit_px - entry) / entry) * 100.0
    if str(action).upper() == "SELL":
        pnl_pct = -pnl_pct
    outcome = "win" if pnl_pct > 0 else "loss"

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO trade_feedback (
                    symbol, action, confidence_at_entry,
                    entry_price, exit_price, pnl_pct,
                    outcome, features_snapshot
                ) VALUES (
                    :symbol, :action, :confidence_at_entry,
                    :entry_price, :exit_price, :pnl_pct,
                    :outcome, CAST(:features_snapshot AS JSONB)
                )
                """
            ),
            {
                "symbol": str(symbol or "").upper(),
                "action": str(action or "HOLD").upper(),
                "confidence_at_entry": float(confidence or 0.0),
                "entry_price": entry,
                "exit_price": exit_px,
                "pnl_pct": float(round(pnl_pct, 6)),
                "outcome": outcome,
                "features_snapshot": json.dumps(features_snapshot or {}),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _fetch_training_data(symbol: str):
    if symbol in YFINANCE_SYMBOL_MAP:
        df = fetch_yfinance_ohlcv(symbol, days=730)
    else:
        df = fetch_binance_ohlcv(symbol, interval="1d", days=730)
    if df is None or len(df) < 200:
        return None
    feat = engineer_features(df)
    if feat is None or feat.empty:
        return None
    return feat


def _feedback_rows(symbol: str, days: int = 90) -> List[dict]:
    _ensure_schema()
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = db.execute(
            text(
                """
                SELECT action, confidence_at_entry, entry_price, exit_price, pnl_pct, features_snapshot
                FROM trade_feedback
                WHERE symbol = :symbol
                  AND created_at >= :cutoff
                ORDER BY created_at DESC
                """
            ),
            {"symbol": symbol.upper(), "cutoff": cutoff},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        db.close()


def _evaluate_directional_accuracy(model, scaler, feature_cols: List[str], feat_df) -> float:
    if feat_df is None or len(feat_df) < 120:
        return 0.0

    exclude_cols = ["target", "open", "high", "low", "close", "volume", "quote_volume", "trades"]
    available_cols = [c for c in feature_cols if c in feat_df.columns and c not in exclude_cols]
    if not available_cols:
        return 0.0

    X = feat_df[available_cols].values
    y = feat_df["target"].values
    split_idx = int(len(X) * 0.8)
    if split_idx <= 2 or split_idx >= len(X):
        return 0.0

    X_test = X[split_idx:]
    y_test = y[split_idx:]

    if len(available_cols) < len(feature_cols):
        full = np.zeros((len(X_test), len(feature_cols)))
        for i, col in enumerate(feature_cols):
            if col in available_cols:
                full[:, i] = X_test[:, available_cols.index(col)]
        X_test = full

    X_test_scaled = scaler.transform(X_test)
    y_pred = model.predict(X_test_scaled)

    if len(y_pred) < 2:
        return 0.0

    pred_dir = np.sign(y_pred[1:] - y_test[:-1])
    true_dir = np.sign(y_test[1:] - y_test[:-1])
    return float((pred_dir == true_dir).mean())


def retrain_with_feedback(symbol: str) -> Dict:
    symbol = str(symbol or "").upper()
    _ensure_schema()

    feat_df = _fetch_training_data(symbol)
    if feat_df is None:
        return {"symbol": symbol, "status": "skipped", "reason": "no_historical_data"}

    feedback = _feedback_rows(symbol, days=90)
    if len(feedback) < 5:
        return {"symbol": symbol, "status": "skipped", "reason": "insufficient_feedback", "feedback_trades": len(feedback)}

    latest_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_latest.pkl")
    if not os.path.exists(latest_path):
        return {"symbol": symbol, "status": "skipped", "reason": "missing_base_model"}

    with open(latest_path, "rb") as f:
        model_data = pickle.load(f)

    old_model = model_data.get("model")
    old_scaler = model_data.get("scaler")
    feature_cols = model_data.get("feature_cols") or []
    if old_model is None or old_scaler is None or not feature_cols:
        return {"symbol": symbol, "status": "skipped", "reason": "invalid_base_model"}

    try:
        import xgboost as xgb
    except ImportError:
        return {"symbol": symbol, "status": "skipped", "reason": "xgboost_missing"}

    exclude_cols = ["target", "open", "high", "low", "close", "volume", "quote_volume", "trades"]
    hist_cols = [c for c in feature_cols if c in feat_df.columns and c not in exclude_cols]
    if len(hist_cols) < max(5, int(0.7 * len(feature_cols))):
        return {"symbol": symbol, "status": "skipped", "reason": "feature_mismatch"}

    X_hist = feat_df[hist_cols].values
    y_hist = feat_df["target"].values

    feedback_vectors = []
    feedback_targets = []
    for row in feedback:
        snap = row.get("features_snapshot") if isinstance(row.get("features_snapshot"), dict) else {}
        vec = np.zeros(len(feature_cols))
        for i, col in enumerate(feature_cols):
            val = snap.get(col)
            if isinstance(val, (int, float)):
                vec[i] = float(val)
        feedback_vectors.append(vec)

        exit_price = float(row.get("exit_price") or 0.0)
        entry_price = float(row.get("entry_price") or 0.0)
        pnl_pct = float(row.get("pnl_pct") or 0.0)
        if exit_price > 0:
            feedback_targets.append(exit_price)
        elif entry_price > 0:
            feedback_targets.append(entry_price * (1.0 + pnl_pct / 100.0))
        else:
            feedback_targets.append(0.0)

    if not feedback_vectors:
        return {"symbol": symbol, "status": "skipped", "reason": "empty_feedback_vectors"}

    X_fb = np.array(feedback_vectors)
    y_fb = np.array(feedback_targets)

    # Align historical columns to full model feature vector.
    X_hist_full = np.zeros((len(X_hist), len(feature_cols)))
    for i, col in enumerate(feature_cols):
        if col in hist_cols:
            X_hist_full[:, i] = X_hist[:, hist_cols.index(col)]

    X_fb_w = np.repeat(X_fb, 3, axis=0)
    y_fb_w = np.repeat(y_fb, 3, axis=0)

    X_train = np.vstack([X_hist_full, X_fb_w])
    y_train = np.concatenate([y_hist, y_fb_w])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_scaled, y_train, verbose=False)

    old_acc = _evaluate_directional_accuracy(old_model, old_scaler, feature_cols, feat_df)
    new_acc = _evaluate_directional_accuracy(model, scaler, feature_cols, feat_df)

    db = SessionLocal()
    try:
        latest_registry = db.execute(
            text(
                """
                SELECT id, COALESCE(version, 1) AS version, model_version
                FROM model_registry
                WHERE symbol = :symbol
                ORDER BY trained_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"symbol": symbol},
        ).mappings().first()

        old_version = int(latest_registry["version"]) if latest_registry else 1
        next_version = old_version + 1

        if new_acc > old_acc:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            model_filename = f"{symbol}_xgboost_fb_v{timestamp}.pkl"
            model_path = os.path.join(MODELS_DIR, model_filename)
            os.makedirs(MODELS_DIR, exist_ok=True)

            new_model_data = dict(model_data)
            new_model_data["model"] = model
            new_model_data["scaler"] = scaler
            new_model_data["trained_at"] = datetime.utcnow().isoformat()
            new_model_data["feedback_trades"] = len(feedback)
            new_model_data["metrics"] = {
                **(new_model_data.get("metrics") or {}),
                "feedback_old_direction_accuracy": round(old_acc * 100.0, 4),
                "feedback_new_direction_accuracy": round(new_acc * 100.0, 4),
                "feedback_trades": len(feedback),
            }

            with open(model_path, "wb") as f:
                pickle.dump(new_model_data, f)

            latest_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_latest.pkl")
            with open(latest_path, "wb") as f:
                pickle.dump(new_model_data, f)

            db.execute(
                text("UPDATE model_registry SET is_active = FALSE WHERE symbol = :symbol"),
                {"symbol": symbol},
            )
            db.execute(
                text(
                    """
                    INSERT INTO model_registry (
                        symbol, model_version, version, accuracy,
                        training_samples, features_used, trained_at,
                        improved_at, is_active
                    ) VALUES (
                        :symbol, :model_version, :version, :accuracy,
                        :training_samples, :features_used, NOW(),
                        NOW(), TRUE
                    )
                    """
                ),
                {
                    "symbol": symbol,
                    "model_version": f"feedback_v{next_version}",
                    "version": next_version,
                    "accuracy": float(round(new_acc, 6)),
                    "training_samples": int(len(X_train)),
                    "features_used": ",".join(feature_cols),
                },
            )

            old_ids = db.execute(
                text(
                    """
                    SELECT id FROM model_registry
                    WHERE symbol = :symbol
                    ORDER BY trained_at DESC, id DESC
                    OFFSET 3
                    """
                ),
                {"symbol": symbol},
            ).mappings().all()
            for row in old_ids:
                db.execute(text("DELETE FROM model_registry WHERE id = :id"), {"id": int(row["id"])})

            db.commit()
            print(f"[IMPROVED] {symbol}: {old_acc:.1%}->{new_acc:.1%}")
            return {
                "symbol": symbol,
                "status": "improved",
                "old_accuracy": old_acc,
                "new_accuracy": new_acc,
                "version": next_version,
                "feedback_trades": len(feedback),
            }

        db.rollback()
        print(f"[NO_IMPROVEMENT] {symbol}: keeping v{old_version}")
        return {
            "symbol": symbol,
            "status": "no_improvement",
            "old_accuracy": old_acc,
            "new_accuracy": new_acc,
            "version": old_version,
            "feedback_trades": len(feedback),
        }
    except Exception as e:
        db.rollback()
        return {"symbol": symbol, "status": "error", "error": str(e)}
    finally:
        db.close()


def retrain_all_with_feedback(symbols: Optional[List[str]] = None) -> List[Dict]:
    items = symbols or list(TRAINING_SYMBOLS)
    results: List[Dict] = []
    for symbol in items:
        try:
            results.append(retrain_with_feedback(symbol))
        except Exception as e:
            results.append({"symbol": symbol, "status": "error", "error": str(e)})
    return results


def get_model_health() -> Dict:
    _ensure_schema()
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT symbol, model_version, COALESCE(version, 1) AS version,
                       COALESCE(accuracy, 0) AS accuracy,
                       improved_at, trained_at
                FROM model_registry
                WHERE is_active = TRUE
                ORDER BY symbol ASC
                """
            )
        ).mappings().all()

        models = []
        now = datetime.utcnow()
        for row in rows:
            symbol = str(row["symbol"])
            current_acc = float(row.get("accuracy") or 0.0)

            prev = db.execute(
                text(
                    """
                    SELECT accuracy
                    FROM model_registry
                    WHERE symbol = :symbol AND id <> (
                        SELECT id FROM model_registry
                        WHERE symbol = :symbol
                        ORDER BY trained_at DESC, id DESC
                        LIMIT 1
                    )
                    ORDER BY trained_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"symbol": symbol},
            ).mappings().first()
            prev_acc = float(prev.get("accuracy") or 0.0) if prev else current_acc

            if current_acc > prev_acc + 1e-9:
                trend = "improving"
            elif current_acc < prev_acc - 1e-9:
                trend = "declining"
            else:
                trend = "stable"

            improved_at = row.get("improved_at")
            age_days = None
            last_improved = None
            if improved_at:
                if isinstance(improved_at, datetime):
                    age_days = max(0, (now - improved_at).days)
                    last_improved = improved_at.date().isoformat()
                else:
                    last_improved = str(improved_at)

            feedback_count_row = db.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM trade_feedback
                    WHERE symbol = :symbol
                      AND created_at >= :cutoff
                    """
                ),
                {"symbol": symbol, "cutoff": now - timedelta(days=90)},
            ).mappings().first()

            models.append(
                {
                    "symbol": symbol,
                    "version": int(row.get("version") or 1),
                    "accuracy": round(current_acc, 4),
                    "trend": trend,
                    "last_improved": last_improved,
                    "last_improved_days": age_days,
                    "feedback_trades": int((feedback_count_row or {}).get("cnt") or 0),
                }
            )

        return {"models": models}
    except Exception:
        return {"models": []}
    finally:
        db.close()
