"""
aura_store.py — φόρτωση δεδομένων για το variant harness.

Χρησιμοποιεί ακριβώς τον ίδιο μηχανισμό download/cache με το
survivorship_backtest.py:
  - κατεβάζει daily klines από https://data.binance.vision
  - αποθηκεύει ως pickle στο cache_dir (default: /tmp/binance_archive)
  - επιστρέφει frames: Dict[str, pd.DataFrame] με στήλες:
      open, high, low, close, quote_volume

Universe rule:
  - TOP_N=30 by 30-day volume, point-in-time
  - MIN_HISTORY=201 days
  - USDT pairs only, excludes stablecoins/leveraged tokens
  - split on gaps >7 days (ticker reuse)

BTC Benchmark:
  - vol-targeted to 10% annual
  - same cost structure, daily rebalance
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

# ── Import ίδιες συναρτήσεις με survivorship_backtest ──────────────────────────
# Το harness τρέχει ως: python3 -m backend.scripts.variant_harness
# οπότε sys.path έχει ήδη τον κατάλογο backend/

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.survivorship_backtest import (  # noqa: E402
    is_candidate,
    load_archive,
    split_on_gaps,
    build_membership,
    NOT_AN_ASSET,
    LEVERAGED,
    NOT_LEVERAGED,
    TOP_N,
    VOLUME_WINDOW,
)

MIN_HISTORY = 201      # ελάχιστες ημέρες ιστορικού
PERIODS_PER_YEAR = 365
BTC_VOL_TARGET = 0.10  # 10% ετήσια μεταβλητότητα


def load_data(
    cache_dir: str = "/tmp/binance_archive",
    workers: int = 12,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 0,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Φορτώνει δεδομένα από Binance archive (ίδια πηγή με survivorship_backtest).

    Επιστρέφει:
        frames  : Dict[symbol -> DataFrame(open,high,low,close,quote_volume)]
        member  : DataFrame(bool) — ποιο coin ανήκει στο universe κάθε μέρα
    """
    # 1. Download / cache (pickle)
    raw = load_archive(cache_dir, workers, limit=limit)
    if not raw:
        raise RuntimeError("Δεν φορτώθηκαν δεδομένα — έλεγξε σύνδεση στο internet")

    # 2. Split on gaps (ticker reuse — π.χ. LUNAUSDT)
    frames = split_on_gaps(raw)

    # 3. Αφαίρεσε frames με ανεπαρκή ιστορικό
    frames = {
        s: df
        for s, df in frames.items()
        if len(df) > MIN_HISTORY + VOLUME_WINDOW
    }

    # 4. Χτίσε point-in-time universe membership
    member = build_membership(frames, top_n=TOP_N)

    # 5. Κράτα μόνο coins που μπήκαν ποτέ στο universe
    used = [s for s in frames if member[s].any()]
    frames = {s: frames[s] for s in used}
    member = member[used]
    member = member.loc[member.any(axis=1)]

    # 6. Date filter (προαιρετικό)
    if start:
        member = member.loc[start:]
    if end:
        member = member.loc[:end]

    return frames, member


def build_btc_benchmark(
    frames: Dict[str, pd.DataFrame],
    member: pd.DataFrame,
    costs: "Costs",  # noqa: F821  # forward ref
    vol_target: float = BTC_VOL_TARGET,
    btc_fill: float = 0.8,
) -> pd.Series:
    """
    BTC vol-targeted benchmark: κρατά μόνο BTCUSDT, vol-scaled σε vol_target ετήσια.

    Fill 0.8 μοντελοποιείται ως ΑΠΟΤΥΧΙΑ εκτέλεσης, όχι ως έκπτωση κόστους (trial #14):
    κάθε 5η μηνιαία αναπροσαρμογή παραλείπεται (το βάρος μένει στο προηγούμενο) και το
    κόστος χρεώνεται πλήρες, μόνο στις αναπροσαρμογές που εκτελέστηκαν.
    Το παλιό (trial #13) πολλαπλασίαζε το κόστος × 0.8 — ανάποδο: λιγότερο fill → φθηνότερο benchmark.

    Επιστρέφει ημερήσιες net returns ευθυγραμμισμένες με το member index.
    """
    sym = "BTCUSDT"
    if sym not in frames:
        # Self-test fallback: χρησιμοποίησε το πρώτο διαθέσιμο coin ως proxy
        available = [s for s in frames if not s.endswith("#2")]
        if not available:
            raise ValueError("Κανένα coin στα frames")
        sym = available[0]
        import sys
        print(f"  WARN: BTCUSDT not found, using {sym} as benchmark proxy", file=sys.stderr)

    df = frames[sym]
    close = df["close"]

    # Daily returns
    ret = close.pct_change().reindex(member.index).fillna(0.0)

    # Rolling vol (63 days) — ετησιοποιημένη (σε ετήσιες μονάδες)
    # BTC ημερήσιο std ~0.035 → ετήσιο ~0.035 * sqrt(365) ≈ 0.67
    # Χρειαζόμαστε ετήσιο vol για να συγκρίνουμε με vol_target=0.10 (ετήσιο)
    vol_ann = ret.rolling(63, min_periods=21).std() * np.sqrt(PERIODS_PER_YEAR)
    vol_ann = vol_ann.replace(0, np.nan).ffill().fillna(vol_target)

    # Scale: πόσο BTC κρατάμε για να έχουμε vol_target ετήσια
    # Π.χ. vol_ann=0.67, vol_target=0.10 → scale=0.149 (όχι leverage)
    raw_scale = vol_target / vol_ann

    # Μηνιαία αναπροσαρμογή: κρατάμε το scale σταθερό εντός μήνα
    # για να αποφύγουμε καθημερινό κόστος αναπροσαρμογής
    # Reindex: παίρνουμε την τιμή στην αρχή κάθε μήνα και την κρατάμε για ολόκληρο τον μήνα
    monthly = raw_scale.resample("MS").first()
    skip_every = int(round(1.0 / (1.0 - btc_fill))) if btc_fill < 1.0 else 0   # 0.8 → 5
    if skip_every:
        # κάθε skip_every-οστή αναπροσαρμογή δεν εκτελείται → μένει το προηγούμενο βάρος
        skipped = (np.arange(len(monthly)) + 1) % skip_every == 0
        monthly = monthly.mask(skipped).ffill()
    monthly_scale = monthly.reindex(raw_scale.index, method="ffill")
    scale = monthly_scale.clip(0.05, 1.5).shift(1).fillna(raw_scale.iloc[0])

    # Gross returns, scaled
    gross = ret * scale

    # Κόστος αναπροσαρμογής: μόνο όταν αλλάζει το scale (μηνιαία)
    scale_chg = scale.diff().abs()
    is_rebalance = scale_chg > 1e-6  # αλλαγή scale → rebalance
    cost_rate = np.where(
        is_rebalance,
        costs.taker_bp / 10_000,  # πλήρες κόστος, μόνο στις εκτελεσμένες (οι παραλειφθείσες δεν αλλάζουν scale)
        0.0,  # καμία χρέωση τις μέρες χωρίς αναπροσαρμογή
    )
    daily_cost = pd.Series(cost_rate, index=gross.index)

    net = gross - daily_cost
    return net.reindex(member.index).fillna(0.0)


def metrics(returns: pd.Series) -> Dict:
    """Βασικά metrics για μια series ημερήσιων net returns."""
    ann = float(returns.mean() * PERIODS_PER_YEAR)
    vol = float(returns.std() * np.sqrt(PERIODS_PER_YEAR))
    sharpe = ann / vol if vol > 0 else 0.0
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    dd = (cum - running_max) / running_max
    max_dd = float(dd.min())

    n = len(returns)
    half = n // 2
    s1 = float(returns.iloc[:half].mean() / returns.iloc[:half].std() * np.sqrt(PERIODS_PER_YEAR)) \
        if returns.iloc[:half].std() > 0 else 0.0
    s2 = float(returns.iloc[half:].mean() / returns.iloc[half:].std() * np.sqrt(PERIODS_PER_YEAR)) \
        if returns.iloc[half:].std() > 0 else 0.0

    return {
        "annual": round(ann, 4),
        "vol": round(vol, 4),
        "sharpe": round(sharpe, 3),
        "max_dd": round(max_dd, 4),
        "sharpe_h1": round(s1, 3),
        "sharpe_h2": round(s2, 3),
    }
