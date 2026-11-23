"""
What the trend signal says right now, per crypto symbol. Read-only.

Shows which symbols the majority-vote trend signal would hold as of the last
completed daily bar and at what volatility-sized weight. Places no orders and
touches no models, database or engine state.

Usage (inside the backend container):
    python -m scripts.trend_today
    python -m scripts.trend_today --symbols BTCUSDC,ETHUSDC
"""

import argparse
import sys
from typing import List, Optional

from scripts.trend_backtest import load_prices
from services.trend_signal import MIN_HISTORY_DAYS, current_view


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Current trend signal per symbol (read-only).")
    parser.add_argument("--symbols", help="Comma-separated symbols (default: all crypto)")
    args = parser.parse_args(argv)

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        from ml.auto_trainer import CRYPTO_SYMBOLS
        symbols = list(CRYPTO_SYMBOLS)

    print(f"{'symbol':<11}{'as of':<12}{'close':>12}{'votes':>7}{'hold':>6}{'weight':>8}")
    print("-" * 56)
    held, weight_sum, ready = 0, 0.0, 0
    for symbol in symbols:
        try:
            # The last daily bar from the exchange is still forming; drop it so the
            # signal is only ever computed on completed days.
            df = load_prices(symbol, days=MIN_HISTORY_DAYS + 120)
            view = current_view(df.iloc[:-1] if df is not None else None)
        except Exception as exc:
            print(f"{symbol:<11}error: {type(exc).__name__}: {exc}")
            continue
        if not view.get("ready"):
            print(f"{symbol:<11}not ready: {view.get('reason')}")
            continue
        ready += 1
        held += int(view["hold"])
        weight_sum += view["target_weight"]
        print(f"{symbol:<11}{view['as_of']:<12}{view['close']:>12.6g}"
              f"{str(view['votes_for']) + '/' + str(view['votes_total']):>7}"
              f"{'YES' if view['hold'] else '-':>6}{view['target_weight']:>8.2f}")
    if ready:
        print("-" * 56)
        print(f"held: {held} of {ready} symbols | average exposure per symbol: {weight_sum / ready:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
