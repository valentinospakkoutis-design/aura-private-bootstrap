import asyncio
import importlib
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import httpx
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from cache.connection import cache_set
from database.connection import SessionLocal
from ml.auto_trainer import (
    CRYPTO_SYMBOLS,
    MODELS_DIR,
    TRAINING_SYMBOLS,
    YFINANCE_SYMBOL_MAP,
    engineer_features,
    fetch_ohlcv,
)
from ml.rl_trader import train_rl_agent
from services.news_fetcher import news_fetcher

logger = logging.getLogger(__name__)

NEWS_SYMBOLS = TRAINING_SYMBOLS[:34]
RETRAIN_SYMBOLS = TRAINING_SYMBOLS[:34]


def _db_available() -> bool:
    return SessionLocal is not None


def _ensure_aux_tables() -> None:
    if not _db_available():
        return

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cron_runs (
                    id SERIAL PRIMARY KEY,
                    task_name VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    started_at TIMESTAMP DEFAULT NOW(),
                    finished_at TIMESTAMP,
                    details TEXT
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS sentiment_scores (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    score FLOAT,
                    label VARCHAR(20),
                    article_count INTEGER DEFAULT 0,
                    source_breakdown JSONB,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(symbol)
                )
                """
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _start_run(task_name: str) -> Optional[int]:
    if not _db_available():
        return None

    _ensure_aux_tables()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                INSERT INTO cron_runs (task_name, status, started_at)
                VALUES (:task_name, 'running', NOW())
                RETURNING id
                """
            ),
            {"task_name": task_name},
        ).fetchone()
        db.commit()
        return int(row[0]) if row else None
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def _finish_run(run_id: Optional[int], status: str, details: str) -> None:
    if not run_id or not _db_available():
        return

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                UPDATE cron_runs
                SET status = :status,
                    finished_at = NOW(),
                    details = :details
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "status": status, "details": details[:8000]},
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _asset_type_for_symbol(symbol: str) -> str:
    if symbol in CRYPTO_SYMBOLS:
        return "crypto"
    if symbol in YFINANCE_SYMBOL_MAP:
        yf_ticker = YFINANCE_SYMBOL_MAP.get(symbol, "")
        if yf_ticker.endswith("=X"):
            return "fx"
        if yf_ticker.startswith("^"):
            return "index"
        if yf_ticker.endswith("=F"):
            return "futures"
        return "stock"
    return "other"


def _upsert_sentiment_score(symbol: str, payload: Dict[str, Any]) -> None:
    if not _db_available():
        return

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO sentiment_scores (
                    symbol, score, label, article_count, source_breakdown, updated_at
                ) VALUES (
                    :symbol, :score, :label, :article_count, CAST(:source_breakdown AS JSONB), NOW()
                )
                ON CONFLICT (symbol)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    label = EXCLUDED.label,
                    article_count = EXCLUDED.article_count,
                    source_breakdown = EXCLUDED.source_breakdown,
                    updated_at = NOW()
                """
            ),
            {
                "symbol": symbol,
                "score": float(payload.get("score", 50.0) or 50.0),
                "label": str(payload.get("label", "neutral") or "neutral"),
                "article_count": int(payload.get("article_count", 0) or 0),
                "source_breakdown": json.dumps(payload.get("sources", {})),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _incremental_update_prices(symbol: str, max_days: int = 30) -> int:
    if not _db_available():
        return 0

    db = SessionLocal()
    try:
        max_date_row = db.execute(
            text("SELECT MAX(date) AS max_date FROM historical_prices WHERE symbol = :symbol"),
            {"symbol": symbol},
        ).mappings().first()
        max_date = max_date_row["max_date"] if max_date_row else None
    finally:
        db.close()

    if max_date:
        days_since_last = (datetime.utcnow().date() - max_date).days
        days_to_fetch = max(1, min(max_days, days_since_last + 1))
    else:
        days_to_fetch = max_days

    df = fetch_ohlcv(symbol, days=days_to_fetch, interval="1d")
    if df is None or df.empty:
        return 0

    if max_date:
        df = df[df.index.date > max_date]
    if df.empty:
        return 0

    rows = []
    asset_type = _asset_type_for_symbol(symbol)
    for ts, row in df.iterrows():
        rows.append(
            {
                "symbol": symbol,
                "asset_type": asset_type,
                "date": ts.date(),
                "open": float(row.get("open", row.get("close", 0.0)) or 0.0),
                "high": float(row.get("high", row.get("close", 0.0)) or 0.0),
                "low": float(row.get("low", row.get("close", 0.0)) or 0.0),
                "close": float(row.get("close", 0.0) or 0.0),
                "volume": float(row.get("volume", 0.0) or 0.0),
            }
        )

    db = SessionLocal()
    inserted = 0
    try:
        for r in rows:
            db.execute(
                text(
                    """
                    INSERT INTO historical_prices (symbol, asset_type, date, open, high, low, close, volume, created_at)
                    VALUES (:symbol, :asset_type, :date, :open, :high, :low, :close, :volume, NOW())
                    ON CONFLICT (symbol, date)
                    DO UPDATE SET
                        asset_type = EXCLUDED.asset_type,
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                    """
                ),
                r,
            )
            inserted += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return inserted


def _load_symbol_prices_from_db(symbol: str, lookback_days: int = 400) -> Optional[pd.DataFrame]:
    if not _db_available():
        return None

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT date, open, high, low, close, volume
                FROM historical_prices
                WHERE symbol = :symbol
                  AND date >= CURRENT_DATE - (:lookback_days || ' days')::INTERVAL
                ORDER BY date ASC
                """
            ),
            {"symbol": symbol, "lookback_days": lookback_days},
        ).mappings().all()
    finally:
        db.close()

    if not rows:
        return None

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["quote_volume"] = (df["close"].astype(float) * df["volume"].astype(float)).fillna(0.0)
    df["trades"] = 0
    return df


def _current_accuracy(symbol: str) -> Optional[float]:
    if not _db_available():
        return None

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT accuracy
                FROM model_registry
                WHERE symbol = :symbol
                ORDER BY is_active DESC, trained_at DESC
                LIMIT 1
                """
            ),
            {"symbol": symbol},
        ).mappings().first()
        if not row or row["accuracy"] is None:
            return None
        return float(row["accuracy"])
    finally:
        db.close()


def _record_model_registry(symbol: str, accuracy: float, training_samples: int, features: List[str]) -> None:
    if not _db_available():
        return

    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE model_registry SET is_active = FALSE WHERE symbol = :symbol"),
            {"symbol": symbol},
        )
        version_tag = datetime.utcnow().strftime("cron_ensemble_%Y%m%d_%H%M%S")
        db.execute(
            text(
                """
                INSERT INTO model_registry (
                    symbol, model_version, version, accuracy,
                    training_samples, features_used, trained_at, improved_at, is_active
                ) VALUES (
                    :symbol, :model_version, 1, :accuracy,
                    :training_samples, :features_used, NOW(), NOW(), TRUE
                )
                """
            ),
            {
                "symbol": symbol,
                "model_version": version_tag,
                "accuracy": float(accuracy),
                "training_samples": int(training_samples),
                "features_used": ",".join(features[:120]),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _train_incremental_ensemble(symbol: str) -> Dict[str, Any]:
    try:
        xgb = importlib.import_module("xgboost")
    except Exception:
        return {"symbol": symbol, "status": "skipped", "reason": "xgboost_missing"}

    df = _load_symbol_prices_from_db(symbol, lookback_days=400)
    if df is None or len(df) < 220:
        return {"symbol": symbol, "status": "skipped", "reason": "insufficient_history"}

    feat = engineer_features(df)
    if feat is None or feat.empty or len(feat) < 140:
        return {"symbol": symbol, "status": "skipped", "reason": "insufficient_features"}

    excluded = {"target", "open", "high", "low", "close", "volume", "quote_volume", "trades"}
    feature_cols = [c for c in feat.columns if c not in excluded]
    if len(feature_cols) < 10:
        return {"symbol": symbol, "status": "skipped", "reason": "feature_columns_missing"}

    X = feat[feature_cols].values
    y = feat["target"].values

    split_idx = int(len(X) * 0.8)
    if split_idx < 80 or split_idx >= len(X) - 5:
        return {"symbol": symbol, "status": "skipped", "reason": "split_too_small"}

    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    xgb_model = xgb.XGBRegressor(
        n_estimators=240,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    rf_model = RandomForestRegressor(
        n_estimators=220,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )

    xgb_model.fit(X_train_scaled, y_train)
    rf_model.fit(X_train_scaled, y_train)

    xgb_pred = xgb_model.predict(X_test_scaled)
    rf_pred = rf_model.predict(X_test_scaled)
    ensemble_pred = (xgb_pred + rf_pred) / 2.0

    pred_dir = np.sign(ensemble_pred[1:] - y_test[:-1])
    true_dir = np.sign(y_test[1:] - y_test[:-1])
    new_acc = float((pred_dir == true_dir).mean()) if len(true_dir) > 0 else 0.0

    current_acc = _current_accuracy(symbol)
    deploy_threshold = (current_acc - 0.02) if current_acc is not None else None
    should_deploy = current_acc is None or new_acc >= deploy_threshold

    status = "deployed" if should_deploy else "skipped"

    model_data = {
        "model": xgb_model,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "symbol": symbol,
        "model_type": "xgboost",
        "trained_at": datetime.utcnow().isoformat(),
        "metrics": {
            "test_direction_accuracy": new_acc,
            "ensemble_components": ["xgboost", "random_forest"],
            "rf_test_rows": len(y_test),
        },
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    version_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_cron_{ts}.pkl")
    latest_path = os.path.join(MODELS_DIR, f"{symbol}_xgboost_latest.pkl")

    with open(version_path, "wb") as f:
        pickle.dump(model_data, f)

    if should_deploy:
        with open(latest_path, "wb") as f:
            pickle.dump(model_data, f)
        _record_model_registry(symbol, new_acc, len(X_train), feature_cols)

    return {
        "symbol": symbol,
        "status": status,
        "old_acc": current_acc,
        "new_acc": new_acc,
        "training_samples": int(len(X_train)),
        "features": int(len(feature_cols)),
    }


async def task_fetch_news():
    """Fetch latest news and update sentiment scores for all training symbols."""
    run_id = _start_run("fetch_news")
    processed = 0
    failures = 0
    try:
        _ensure_aux_tables()
        for symbol in NEWS_SYMBOLS:
            try:
                sentiment = await asyncio.to_thread(news_fetcher.get_symbol_sentiment, symbol)
                await asyncio.to_thread(_upsert_sentiment_score, symbol, sentiment)
                processed += 1
            except Exception as e:
                failures += 1
                logger.warning("[CRON_NEWS] %s failed: %s", symbol, e)

        logger.info("[CRON_NEWS] Fetched news for %s symbols", processed)
        details = json.dumps({"processed": processed, "failures": failures})
        _finish_run(run_id, "success", details)
        return {"status": "success", "processed": processed, "failures": failures}
    except Exception as e:
        logger.exception("[CRON_NEWS] fatal error")
        _finish_run(run_id, "failed", str(e))
        return {"status": "failed", "error": str(e)}


async def task_weekly_retrain():
    """Run incremental weekly retraining with conservative deployment guardrails."""
    run_id = _start_run("weekly_retrain")
    deployed = 0
    skipped = 0
    errors = 0
    logs: List[str] = []

    try:
        _ensure_aux_tables()
        for symbol in RETRAIN_SYMBOLS:
            try:
                inserted = await asyncio.to_thread(_incremental_update_prices, symbol, 30)
                _ = inserted  # explicit for readability in logs below

                result = await asyncio.to_thread(_train_incremental_ensemble, symbol)
                old_acc = result.get("old_acc")
                new_acc = result.get("new_acc")
                status = result.get("status")

                if status == "deployed":
                    deployed += 1
                    line = (
                        f"[CRON_RETRAIN] Symbol {symbol}: old_acc={old_acc if old_acc is not None else 'n/a'} "
                        f"-> new_acc={new_acc:.4f} DEPLOYED"
                    )
                elif status == "skipped":
                    skipped += 1
                    if new_acc is not None:
                        line = f"[CRON_RETRAIN] Symbol {symbol}: new_acc={new_acc:.4f} SKIPPED"
                    else:
                        line = f"[CRON_RETRAIN] Symbol {symbol}: SKIPPED ({result.get('reason', 'unknown')})"
                else:
                    skipped += 1
                    line = f"[CRON_RETRAIN] Symbol {symbol}: SKIPPED"

                logger.info(line)
                logs.append(line)
            except Exception as e:
                errors += 1
                line = f"[CRON_RETRAIN] Symbol {symbol}: FAILED ({e})"
                logger.warning(line)
                logs.append(line)

        details = json.dumps({"deployed": deployed, "skipped": skipped, "errors": errors, "logs": logs[:60]})
        _finish_run(run_id, "success", details)
        return {"status": "success", "deployed": deployed, "skipped": skipped, "errors": errors}
    except Exception as e:
        logger.exception("[CRON_RETRAIN] fatal error")
        _finish_run(run_id, "failed", str(e))
        return {"status": "failed", "error": str(e)}


async def task_fear_greed_update():
    """Fetch Fear & Greed index and cache in Redis for one hour."""
    run_id = _start_run("fear_greed")
    try:
        from cache.connection import get_redis
        from ml.regime_detector import fetch_and_cache_vix

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            resp.raise_for_status()
            payload = resp.json()

        data = (payload.get("data") or [{}])[0]
        value = int(float(data.get("value", 50)))
        classification = str(data.get("value_classification") or "Neutral")

        cache_payload = {
            "value": value,
            "classification": classification,
            "timestamp": datetime.utcnow().isoformat(),
        }
        cache_set("fear_greed:latest", cache_payload, expire=3600)

        # Also update VIX-based market regime.
        redis_client = get_redis()
        regime = await fetch_and_cache_vix(redis_client)
        cache_payload["regime"] = regime

        logger.info("[CRON_FG] Fear & Greed = %s (%s)", value, classification)
        logger.info("[CRON_REGIME] regime=%s vix=%.2f", regime.get("regime", "unknown"), float(regime.get("vix", 20.0)))
        _finish_run(run_id, "success", json.dumps(cache_payload))
        return {"status": "success", **cache_payload}
    except Exception as e:
        logger.exception("[CRON_FG] failed")
        _finish_run(run_id, "failed", str(e))
        return {"status": "failed", "error": str(e)}


async def task_monthly_rl_retrain():
    """Retrain RL agents for existing symbols and deploy only if Sharpe improves."""
    run_id = _start_run("monthly_rl")
    deployed = 0
    skipped = 0
    errors = 0
    logs: List[str] = []

    if not _db_available():
        msg = "database_not_available"
        _finish_run(run_id, "failed", msg)
        return {"status": "failed", "error": msg}

    try:
        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT DISTINCT symbol FROM rl_models ORDER BY symbol ASC")).mappings().all()
            symbols = [str(r["symbol"]).upper() for r in rows if r.get("symbol")]
        finally:
            db.close()

        for symbol in symbols:
            try:
                db = SessionLocal()
                try:
                    old_row = db.execute(
                        text(
                            """
                            SELECT val_sharpe, episode
                            FROM rl_models
                            WHERE symbol = :symbol AND is_best = TRUE
                            ORDER BY trained_at DESC
                            LIMIT 1
                            """
                        ),
                        {"symbol": symbol},
                    ).mappings().first()
                    old_sharpe = float(old_row["val_sharpe"]) if old_row and old_row["val_sharpe"] is not None else 0.0
                    old_episode = int(old_row["episode"]) if old_row and old_row["episode"] is not None else 0
                finally:
                    db.close()

                await asyncio.to_thread(train_rl_agent, symbol, 500, "cron_monthly_rl")

                db = SessionLocal()
                try:
                    new_row = db.execute(
                        text(
                            """
                            SELECT val_sharpe, episode
                            FROM rl_models
                            WHERE symbol = :symbol AND is_best = TRUE
                            ORDER BY trained_at DESC
                            LIMIT 1
                            """
                        ),
                        {"symbol": symbol},
                    ).mappings().first()
                    new_sharpe = float(new_row["val_sharpe"]) if new_row and new_row["val_sharpe"] is not None else old_sharpe
                    new_episode = int(new_row["episode"]) if new_row and new_row["episode"] is not None else old_episode
                finally:
                    db.close()

                if new_sharpe > old_sharpe:
                    deployed += 1
                    line = (
                        f"[CRON_RL] Symbol {symbol}: old_sharpe={old_sharpe:.2f} "
                        f"-> new_sharpe={new_sharpe:.2f} DEPLOYED"
                    )
                else:
                    skipped += 1
                    line = (
                        f"[CRON_RL] Symbol {symbol}: old_sharpe={old_sharpe:.2f} "
                        f"-> new_sharpe={new_sharpe:.2f} SKIPPED"
                    )

                logger.info(line)
                logs.append(line)
                _ = new_episode  # documents that additional episodes were trained
            except Exception as e:
                errors += 1
                line = f"[CRON_RL] Symbol {symbol}: FAILED ({e})"
                logger.warning(line)
                logs.append(line)

        details = json.dumps({"deployed": deployed, "skipped": skipped, "errors": errors, "logs": logs[:80]})
        _finish_run(run_id, "success", details)
        return {"status": "success", "deployed": deployed, "skipped": skipped, "errors": errors}
    except Exception as e:
        logger.exception("[CRON_RL] fatal error")
        _finish_run(run_id, "failed", str(e))
        return {"status": "failed", "error": str(e)}


TASK_MAP = {
    "fetch_news": task_fetch_news,
    "weekly_retrain": task_weekly_retrain,
    "fear_greed": task_fear_greed_update,
    "monthly_rl": task_monthly_rl_retrain,
}


async def run_named_task(task_name: str) -> Dict[str, Any]:
    task = TASK_MAP.get(task_name)
    if task is None:
        return {"status": "failed", "error": f"Unknown task: {task_name}"}
    return await task()
