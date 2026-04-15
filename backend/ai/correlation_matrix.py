"""Correlation matrix utilities for cross-asset exposure control."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ml.auto_trainer import TRAINING_SYMBOLS, YFINANCE_SYMBOL_MAP

# Keep default scope to 34 symbols as requested.
DEFAULT_SYMBOLS = list(TRAINING_SYMBOLS[:34])


def _to_yfinance_symbol(symbol: str) -> str:
    sym = str(symbol or "").upper()
    if not sym:
        return ""

    # Direct map for non-crypto assets handled in trainer.
    if sym in YFINANCE_SYMBOL_MAP:
        return str(YFINANCE_SYMBOL_MAP[sym])

    # Normalize crypto pairs to yfinance spot tickers.
    if sym.endswith("USDC") or sym.endswith("USDT"):
        base = sym[:-4]
        if base:
            return f"{base}-USD"

    return sym


def _load_returns(symbols: List[str], lookback_days: int = 90) -> pd.DataFrame:
    import yfinance as yf

    series_map: Dict[str, pd.Series] = {}
    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").upper().strip()
        ticker = _to_yfinance_symbol(symbol)
        if not symbol or not ticker:
            continue
        try:
            df = yf.download(
                ticker,
                period=f"{int(max(lookback_days + 14, 100))}d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if df is None or df.empty or "Close" not in df.columns:
                continue

            returns = df["Close"].astype(float).pct_change().dropna().tail(int(lookback_days))
            if returns.empty:
                continue
            series_map[symbol] = returns
        except Exception:
            continue

    if not series_map:
        return pd.DataFrame()
    returns_df = pd.DataFrame(series_map).dropna(how="all")
    if returns_df.empty:
        return pd.DataFrame()
    # Require at least 20 common observations to avoid unstable estimates.
    return returns_df.dropna(axis=1, thresh=20)


def compute_correlation_matrix(symbols: Optional[list] = None) -> dict:
    """Compute Pearson correlation matrix from last 90d daily returns."""
    target_symbols = [str(s).upper() for s in (symbols or DEFAULT_SYMBOLS)]
    target_symbols = [s for s in target_symbols if s]

    returns_df = _load_returns(target_symbols, lookback_days=90)
    computed_at = datetime.utcnow().isoformat()

    if returns_df.empty:
        return {
            "matrix": {},
            "computed_at": computed_at,
            "symbols": [],
        }

    corr_df = returns_df.corr(method="pearson").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    matrix = {
        str(row_sym): {
            str(col_sym): float(round(corr_df.loc[row_sym, col_sym], 6))
            for col_sym in corr_df.columns
        }
        for row_sym in corr_df.index
    }

    return {
        "matrix": matrix,
        "computed_at": computed_at,
        "symbols": list(corr_df.columns),
    }


def get_correlated_pairs(threshold: float = 0.8) -> list:
    """Return symbol pairs with absolute correlation above threshold."""
    th = float(abs(threshold))
    payload = compute_correlation_matrix(symbols=None)
    matrix = payload.get("matrix", {})

    pairs = []
    symbols = sorted(matrix.keys())
    for i, symbol_a in enumerate(symbols):
        row = matrix.get(symbol_a, {})
        for symbol_b in symbols[i + 1:]:
            corr = float(row.get(symbol_b, 0.0) or 0.0)
            if abs(corr) > th:
                pairs.append(
                    {
                        "symbol_a": symbol_a,
                        "symbol_b": symbol_b,
                        "correlation": round(corr, 4),
                    }
                )

    pairs.sort(key=lambda item: abs(float(item.get("correlation", 0.0))), reverse=True)
    return pairs


def check_portfolio_correlation(symbols_in_portfolio: list) -> dict:
    """Check whether the given portfolio contains highly correlated pairs."""
    symbols = [str(s).upper() for s in (symbols_in_portfolio or []) if str(s).strip()]
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) < 2:
        return {"safe": True, "warnings": []}

    payload = compute_correlation_matrix(symbols=symbols)
    matrix = payload.get("matrix", {})

    warnings: List[str] = []
    pairs: List[Dict[str, float]] = []
    for idx, symbol_a in enumerate(symbols):
        row = matrix.get(symbol_a, {})
        for symbol_b in symbols[idx + 1:]:
            corr = float(row.get(symbol_b, 0.0) or 0.0)
            if abs(corr) > 0.85:
                pct = round(abs(corr) * 100.0)
                warnings.append(
                    f"{symbol_a} and {symbol_b} are {pct:.0f}% correlated - consider reducing exposure"
                )
                pairs.append({"symbol_a": symbol_a, "symbol_b": symbol_b, "correlation": round(corr, 4)})

    return {
        "safe": len(warnings) == 0,
        "warnings": warnings,
        "pairs": pairs,
        "computed_at": payload.get("computed_at"),
    }
