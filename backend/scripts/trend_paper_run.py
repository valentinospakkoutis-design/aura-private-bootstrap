"""
Step the trend paper ledger to the last completed daily bar, or report on it.

Outside the trading engine: reads prices, computes the trend signals, and
records simulated positions for each strategy in the `trend_paper_*` tables.
Places no orders. Safe to run any number of times a day — a day that is
already recorded is never rewritten, and missed days are caught up in order.

Usage (inside the backend container):
    python -m scripts.trend_paper_run            # step, then print the report
    python -m scripts.trend_paper_run --report   # report only
"""

import argparse
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from scripts.trend_backtest import load_prices
from services.trend_paper import INITIAL_CAPITAL, PAPER_COST_BPS, SqlStore, run, summary
from services.trend_signal import MIN_HISTORY_DAYS


def _load_frames(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            df = load_prices(symbol, days=MIN_HISTORY_DAYS + 150)
        except Exception as exc:
            print(f"  {symbol}: price load failed ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue
        if df is not None and len(df) >= MIN_HISTORY_DAYS:
            frames[symbol] = df
    return frames


def _print_report(store: SqlStore) -> None:
    rows = summary(store)
    print(f"\n{'strategy':<13}{'since':<12}{'as of':<12}{'days':>5}{'equity':>11}{'ret%':>8}"
          f"{'maxDD%':>8}{'expo%':>7}{'held':>9}{'trades':>8}{'costs':>9}")
    print("-" * 102)
    for r in rows:
        if not r.get("days"):
            print(f"{r['strategy']:<13}no data yet")
            continue
        print(f"{r['strategy']:<13}{r['start']:<12}{r['as_of']:<12}{r['days']:>5}{r['equity']:>11.2f}"
              f"{r['total_return_pct']:>8.2f}{r['max_drawdown_pct']:>8.2f}{r['exposure_pct']:>7.1f}"
              f"{str(r['held']) + '/' + str(r['universe']):>9}{r['trades']:>8}{r['costs_total']:>9.2f}")
    print(f"\nvirtual capital per strategy: {INITIAL_CAPITAL:,.0f} | cost per side: {PAPER_COST_BPS:.0f} bps"
          " | always_long is the yardstick, not a candidate")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Trend paper ledger (no orders are placed).")
    parser.add_argument("--report", action="store_true", help="Only print the report")
    args = parser.parse_args(argv)

    from database.connection import SessionLocal
    if SessionLocal is None:
        print("DATABASE_URL is not configured; the ledger needs the database.", file=sys.stderr)
        return 2
    store = SqlStore(SessionLocal)

    if not args.report:
        from ml.auto_trainer import CRYPTO_SYMBOLS
        frames = _load_frames(list(CRYPTO_SYMBOLS))
        if not frames:
            print("no price data loaded; nothing recorded", file=sys.stderr)
            return 1
        steps = run(store, frames, datetime.now(timezone.utc).date())
        if steps:
            for step in steps:
                print(f"recorded {step['strategy']:<12} {step['as_of']}  equity {step['equity']:.2f}  "
                      f"trades {step['trades']}  held {step['held']}/{step['universe']}")
        else:
            print("nothing new to record (already up to date)")
    _print_report(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
