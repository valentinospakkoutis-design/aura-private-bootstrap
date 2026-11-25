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
from services.trend_paper import (
    BENCHMARKS, INITIAL_CAPITAL, PAPER_COST_BPS, SqlStore, run, spread_summary, summary,
)
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


def _fetch_quotes(symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """Best bid and ask from Binance's public ticker, for the USDC pairs Aura would
    trade and their USDT twins. Public data, no account involved."""
    import httpx
    from ml.auto_trainer import BINANCE_BASE

    wanted = set()
    for symbol in symbols:
        wanted.add(symbol.upper())
        if symbol.upper().endswith("USDC"):
            wanted.add(symbol.upper()[:-4] + "USDT")
    with httpx.Client(base_url=BINANCE_BASE, timeout=15.0) as client:
        response = client.get("/api/v3/ticker/bookTicker")
        response.raise_for_status()
    return {row["symbol"]: {"bid": float(row["bidPrice"]), "ask": float(row["askPrice"])}
            for row in response.json() if row.get("symbol") in wanted}


def _record_spreads(store: SqlStore, symbols: List[str], after_close: bool) -> None:
    try:
        quotes = _fetch_quotes(symbols)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        saved = store.save_spreads(stamp, quotes, after_close)
        print(f"spreads recorded for {saved} pairs")
    except Exception as exc:   # a measurement must never stop the ledger
        print(f"  spreads not recorded ({type(exc).__name__}: {exc})", file=sys.stderr)


def _print_report(store: SqlStore) -> None:
    rows = summary(store)
    print(f"\n{'strategy':<22}{'since':<12}{'as of':<12}{'days':>5}{'equity':>11}{'ret%':>8}"
          f"{'maxDD%':>8}{'expo%':>7}{'held':>9}{'trades':>8}{'costs':>9}")
    print("-" * 111)
    for r in rows:
        if not r.get("days"):
            print(f"{r['strategy']:<22}no data yet")
            continue
        print(f"{r['strategy']:<22}{r['start']:<12}{r['as_of']:<12}{r['days']:>5}{r['equity']:>11.2f}"
              f"{r['total_return_pct']:>8.2f}{r['max_drawdown_pct']:>8.2f}{r['exposure_pct']:>7.1f}"
              f"{str(r['held']) + '/' + str(r['universe']):>9}{r['trades']:>8}{r['costs_total']:>9.2f}")
    print(f"\nvirtual capital per strategy: {INITIAL_CAPITAL:,.0f} | cost per side: {PAPER_COST_BPS:.0f} bps"
          f" | benchmarks, not candidates: {', '.join(BENCHMARKS)}")
    print("each line is its own portfolio with its own start date; they are not meant to be added up")
    spreads = spread_summary(store)
    if spreads:
        print("\nmeasured half-spread just after the close (cost of a small order beyond the exchange fee):")
        for row in spreads:
            print(f"  {row['quote']} pairs: median {row['median_half_spread_bps']} bps over {row['symbols']} coins, "
                  f"{row['snapshots']} snapshots | BTC {row['btc_half_spread_bps']} bps | "
                  f"widest {row['worst_symbol']} {row['worst_symbol_half_spread_bps']} bps")
        print(f"  the ledger still charges its assumed {PAPER_COST_BPS:.0f} bps; the exchange fee is not measured here")


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
                print(f"recorded {step['strategy']:<22} {step['as_of']}  equity {step['equity']:.2f}  "
                      f"trades {step['trades']}  held {step['held']}/{step['universe']}")
        else:
            print("nothing new to record (already up to date)")
        _record_spreads(store, list(CRYPTO_SYMBOLS), after_close=bool(steps))
    _print_report(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
