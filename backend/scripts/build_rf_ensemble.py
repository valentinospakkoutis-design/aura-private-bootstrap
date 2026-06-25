"""Build RandomForest ensemble sidecar models for the 8 signal-quality symbols.
Bypasses the TrainingFeature DB table (which has legacy Yahoo ticker format) by
pulling features directly via asset_predictor._ensure_features. Idempotent —
safe to run on every startup; only builds models that are missing.
"""
import os
import sys
import pickle
import logging

import numpy as np

logger = logging.getLogger(__name__)

# Resolve paths relative to this file so it works both in-container and in-repo.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

MODELS_DIR = os.environ.get("AURA_MODELS_DIR", os.path.join(_BACKEND_DIR, "models"))
SYMS = ['FTSE1!', 'SI1!', 'BAC', 'HG1!', 'JPM', 'YM1!', 'ES1!', 'DAX1!']


def build_missing(force: bool = False) -> list:
    """Build RF ensemble sidecars for any of the 8 symbols whose pkl is missing.
    Returns a list of symbols that were (re)built. Set force=True to rebuild all."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from ai.asset_predictor import _ensure_features

    os.makedirs(MODELS_DIR, exist_ok=True)
    built = []

    for sym in SYMS:
        path = os.path.join(MODELS_DIR, f"{sym}_ensemble_latest.pkl")
        if os.path.exists(path) and not force:
            continue
        try:
            feat = _ensure_features(sym, None)
            if feat is None or len(feat) < 100:
                logger.warning("[rf_ensemble] %s: not enough data (%s rows)",
                               sym, len(feat) if feat is not None else 0)
                continue

            close_col = [c for c in feat.columns if 'close' in c.lower()]
            if not close_col:
                logger.warning("[rf_ensemble] %s: no close column", sym)
                continue

            feature_cols = [c for c in feat.columns if c not in ['date', 'symbol']]
            X = feat[feature_cols].fillna(0).values
            closes = feat[close_col[0]].values
            y = (np.roll(closes, -3) > closes).astype(int)
            y[-3:] = 0  # remove lookahead

            split = int(len(X) * 0.8)
            X_train, y_train = X[:split], y[:split]

            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)

            rf = RandomForestClassifier(
                n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
            )
            rf.fit(X_train_s, y_train)

            bundle = {"rf_model": rf, "scaler": scaler, "feature_cols": feature_cols}
            with open(path, 'wb') as f:
                pickle.dump(bundle, f)
            built.append(sym)
            logger.info("[rf_ensemble] %s: built -> %s", sym, path)
        except Exception as e:
            logger.warning("[rf_ensemble] %s: ERROR - %s", sym, e)

    return built


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = build_missing(force="--force" in sys.argv)
    print(f"Built {len(result)} RF ensemble models: {result}")
