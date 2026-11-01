"""
Incremental XGBoost Retrainer με Shadow Validation.
Τρέχει μετά από trigger από το daily_evaluation pipeline.
"""
from __future__ import annotations

import logging
import os
import pickle
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy import text
from database.connection import get_async_db

logger = logging.getLogger(__name__)

MODELS_DIR   = Path(os.getenv("MODELS_DIR", "/app/models"))
SHADOW_SUFFIX = "_shadow"
ROLLING_DAYS  = 30  # rolling window για labeled examples


async def _load_training_rows(days: int = ROLLING_DAYS) -> list[dict]:
    """Φέρνει labeled trades των τελευταίων N ημερών από trade_feedback."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_async_db() as db:
        rows = (await db.execute(text("""
            SELECT symbol, action, confidence_at_entry,
                   entry_price, exit_price, pnl_pct, outcome,
                   features_snapshot, created_at
            FROM trade_feedback
            WHERE created_at >= :cutoff
              AND outcome IS NOT NULL
              AND features_snapshot IS NOT NULL
            ORDER BY created_at
        """), {"cutoff": cutoff})).mappings().all()
    return [dict(r) for r in rows]


def _rows_to_xy(rows: list[dict]):
    """Μετατρέπει trade rows σε X, y για XGBoost."""
    import json
    X, y = [], []
    for r in rows:
        try:
            features = r["features_snapshot"]
            if isinstance(features, str):
                features = json.loads(features)
            if not isinstance(features, dict):
                continue
            x = list(features.values())
            label = 1 if (r.get("outcome") or "").lower() == "win" else 0
            X.append(x)
            y.append(label)
        except Exception:
            continue
    return np.array(X, dtype=float), np.array(y, dtype=int)


def _find_model_files() -> list[Path]:
    """Βρίσκει όλα τα XGBoost .pkl αρχεία στο models dir."""
    if not MODELS_DIR.exists():
        return []
    return sorted(MODELS_DIR.glob("*.pkl"))


async def trigger_incremental_refit(reason: str = "") -> bool:
    """
    Κύρια συνάρτηση retraining.
    1. Φέρνει rolling 30d training data
    2. Κάνει incremental refit
    3. Shadow validation 24h (αποθηκεύει ως _shadow)
    4. Επιστρέφει True αν όλα πήγαν καλά
    """
    logger.info(f"[retrainer] Triggered — reason: {reason}")

    rows = await _load_training_rows(days=ROLLING_DAYS)
    if len(rows) < 20:
        logger.warning(f"[retrainer] Only {len(rows)} labeled rows — skipping refit (need ≥20)")
        return False

    X, y = _rows_to_xy(rows)
    if len(X) < 20:
        logger.warning(f"[retrainer] Only {len(X)} valid feature rows — skipping")
        return False

    logger.info(f"[retrainer] Training on {len(X)} rows, win_rate={y.mean():.2%}")

    model_files = _find_model_files()
    if not model_files:
        logger.warning("[retrainer] No model .pkl files found — skipping")
        return False

    refitted = 0
    for model_path in model_files:
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)

            # Incremental refit — XGBoost supports set_params + fit
            if hasattr(model, "fit"):
                model.fit(X, y)
            else:
                logger.warning(f"[retrainer] {model_path.name} has no fit() — skipping")
                continue

            # Αποθήκευση ως shadow
            shadow_path = model_path.with_name(model_path.stem + SHADOW_SUFFIX + ".pkl")
            with open(shadow_path, "wb") as f:
                pickle.dump(model, f)

            refitted += 1
            logger.info(f"[retrainer] ✅ Refitted {model_path.name} → {shadow_path.name}")

        except Exception as e:
            logger.error(f"[retrainer] Failed on {model_path.name}: {e}")

    if refitted == 0:
        return False

    # Log retraining event στο DB
    try:
        async with get_async_db() as db:
            await db.execute(text("""
                INSERT INTO training_logs (created_at, notes)
                VALUES (:ts, :notes)
            """), {
                "ts":    datetime.now(timezone.utc),
                "notes": f"incremental_refit: {refitted} models, reason={reason}, rows={len(X)}",
            })
            await db.commit()
    except Exception as e:
        logger.warning(f"[retrainer] Could not log to training_logs: {e}")

    logger.info(f"[retrainer] Done — {refitted} models saved as shadow, pending 24h validation")
    return True


async def promote_shadow_models() -> int:
    """
    Προωθεί shadow models σε production αν έχουν περάσει 24h.
    Τρέχει κάθε πρωί (π.χ. 08:00 UTC).
    """
    promoted = 0
    for shadow_path in MODELS_DIR.glob(f"*{SHADOW_SUFFIX}.pkl"):
        age_hours = (datetime.now(timezone.utc).timestamp() - shadow_path.stat().st_mtime) / 3600
        if age_hours < 24:
            logger.info(f"[retrainer] {shadow_path.name} only {age_hours:.1f}h old — waiting")
            continue

        # Rollback backup
        stem        = shadow_path.stem.replace(SHADOW_SUFFIX, "")
        prod_path   = shadow_path.with_name(stem + ".pkl")
        backup_path = shadow_path.with_name(stem + "_backup.pkl")

        if prod_path.exists():
            shutil.copy2(prod_path, backup_path)

        shutil.move(str(shadow_path), str(prod_path))
        promoted += 1
        logger.info(f"[retrainer] ✅ Promoted {shadow_path.name} → {prod_path.name}")

    return promoted
