"""Optional LSTM sidecar for top-10 crypto ensemble predictions."""

import json
import logging
import os
import importlib
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
LSTM_SEQUENCE_LENGTH = 60
LSTM_FEATURE_COUNT = 20

LSTM_SYMBOLS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "SOLUSDC",
    "ADAUSDC", "XRPUSDC", "DOGEUSDC", "DOTUSDC",
    "LINKUSDC", "LTCUSDC",
]

_LSTM_CACHE: Dict[str, object] = {}
_LSTM_METADATA_CACHE: Dict[str, Dict] = {}


def _bundle_paths(symbol: str) -> Tuple[str, str]:
    model_path = os.path.join(MODELS_DIR, f"{symbol}_lstm_latest.keras")
    meta_path = os.path.join(MODELS_DIR, f"{symbol}_lstm_latest.json")
    return model_path, meta_path


def build_lstm(sequence_length: int = LSTM_SEQUENCE_LENGTH, n_features: int = LSTM_FEATURE_COUNT):
    try:
        keras = importlib.import_module("tensorflow.keras")

        model = keras.Sequential([
            keras.layers.Input(shape=(sequence_length, n_features)),
            keras.layers.LSTM(128, return_sequences=True),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(64),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dense(1, activation="sigmoid"),
        ])
        model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
        return model
    except ImportError:
        print("[LSTM] TensorFlow not available, skipping")
        return None


def _select_feature_columns(features: pd.DataFrame, n_features: int = LSTM_FEATURE_COUNT) -> List[str]:
    excluded = {"target", "open", "high", "low", "close", "volume", "quote_volume", "trades"}
    numeric_cols = [
        col for col in features.columns
        if col not in excluded and pd.api.types.is_numeric_dtype(features[col])
    ]
    return numeric_cols[:n_features]


def _build_feature_matrix(ohlcv_data: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> Tuple[Optional[np.ndarray], List[str], Optional[np.ndarray]]:
    from ml.auto_trainer import engineer_features

    features = engineer_features(ohlcv_data)
    if features is None or features.empty:
        return None, [], None

    selected_cols = feature_cols or _select_feature_columns(features)
    if len(selected_cols) < LSTM_FEATURE_COUNT:
        return None, [], None

    selected_cols = selected_cols[:LSTM_FEATURE_COUNT]
    matrix = features[selected_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(np.float32)

    target_close = features["target"].astype(float).values
    current_close = features["close"].astype(float).values
    labels = (target_close > current_close).astype(np.float32)
    return matrix.values, selected_cols, labels


def prepare_sequences(data, seq_len: int = LSTM_SEQUENCE_LENGTH, labels=None):
    X, y = [], []
    if data is None or len(data) <= seq_len:
        return np.array(X), np.array(y)

    if labels is None:
        labels = np.zeros(len(data), dtype=np.float32)

    for i in range(seq_len, len(data)):
        X.append(data[i - seq_len:i])
        y.append(labels[i])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def save_lstm_model(symbol: str, model, feature_cols: List[str], sequence_length: int = LSTM_SEQUENCE_LENGTH) -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path, meta_path = _bundle_paths(symbol)
    model.save(model_path, overwrite=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"feature_cols": feature_cols, "sequence_length": sequence_length}, f)
    _LSTM_CACHE[symbol] = model
    _LSTM_METADATA_CACHE[symbol] = {"feature_cols": feature_cols, "sequence_length": sequence_length}


def _load_lstm_bundle(symbol: str) -> Tuple[Optional[object], Optional[Dict]]:
    if symbol in _LSTM_CACHE and symbol in _LSTM_METADATA_CACHE:
        return _LSTM_CACHE[symbol], _LSTM_METADATA_CACHE[symbol]

    model_path, meta_path = _bundle_paths(symbol)
    if not os.path.exists(model_path) or not os.path.exists(meta_path):
        return None, None

    try:
        keras = importlib.import_module("tensorflow.keras")
    except ImportError:
        print("[LSTM] TensorFlow not available, skipping")
        return None, None

    try:
        model = keras.models.load_model(model_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        _LSTM_CACHE[symbol] = model
        _LSTM_METADATA_CACHE[symbol] = metadata
        return model, metadata
    except Exception as exc:
        logger.warning("[LSTM] Failed loading %s: %s", symbol, exc)
        return None, None


def load_lstm_model(symbol: str):
    model, _ = _load_lstm_bundle(symbol)
    return model


def load_all_lstm_models() -> Dict[str, object]:
    loaded = {}
    for symbol in LSTM_SYMBOLS:
        model, _ = _load_lstm_bundle(symbol)
        if model is not None:
            loaded[symbol] = model
    if loaded:
        logger.info("[LSTM] Loaded %s pre-trained models", len(loaded))
    else:
        logger.info("[LSTM] No pre-trained LSTM models found")
    return loaded


def train_lstm(symbol: str, ohlcv_data: pd.DataFrame):
    model = build_lstm()
    if model is None:
        return None
    if ohlcv_data is None or ohlcv_data.empty:
        return None

    matrix, feature_cols, labels = _build_feature_matrix(ohlcv_data)
    if matrix is None or labels is None:
        logger.info("[LSTM] Feature preparation failed for %s", symbol)
        return None

    X, y = prepare_sequences(matrix, labels=labels)
    if len(X) < 100:
        print(f"[LSTM] Not enough data for {symbol}")
        return None

    model.fit(X, y, epochs=30, batch_size=32, validation_split=0.2, verbose=0)
    save_lstm_model(symbol, model, feature_cols)
    print(f"[LSTM] Trained {symbol}")
    return model


def predict_lstm(symbol: str, recent_data: pd.DataFrame):
    model, metadata = _load_lstm_bundle(symbol)
    if model is None or metadata is None or recent_data is None or recent_data.empty:
        return None

    matrix, feature_cols, _ = _build_feature_matrix(recent_data, metadata.get("feature_cols"))
    if matrix is None or feature_cols != metadata.get("feature_cols"):
        return None

    seq_len = int(metadata.get("sequence_length", LSTM_SEQUENCE_LENGTH))
    if len(matrix) < seq_len:
        return None

    X = np.array([matrix[-seq_len:]], dtype=np.float32)
    prob = float(model.predict(X, verbose=0)[0][0])
    return max(0.0, min(1.0, prob))
