"""
Trend-following backtest: do simple, pre-specified trend rules pay after costs?

Next-day direction turned out to be unpredictable from daily price features
(see scripts.walk_forward_eval). This tests a different idea: do not predict,
follow. Hold an asset only while it is in an established uptrend, size the
position by its volatility, and spread the risk over many assets.

What keeps this honest:
  * the rules have no fitted parameters — they are fixed below and every
    variant is reported, not just the best one;
  * a signal formed at today's close earns tomorrow's return, never today's;
  * costs are charged on every change in position;
  * each rule is compared with a benchmark that holds the same assets with the
    same volatility sizing but never times them, so the number shown is the
    value of the timing itself;
  * results are also split into first and second half of the history.

Long-only (flat when out of trend), matching what the broker layer executes.
Read-only: touches no models, database or engine state.

Usage (inside the backend container):
    python -m scripts.trend_backtest --all --out /tmp/trend_backtest.json
    python -m scripts.trend_backtest --crypto --cost-bps 30
    python -m scripts.trend_backtest --symbols BTCUSDC,ETHUSDC,SI1! --per-symbol
"""

import argparse
import json
import math
import sys
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from services.trend_signal import (
    BASE_RULES,
    TARGET_DAILY_VOL,
    majority_signal,
    vol_weight,
)

# Every base rule is reported, plus the majority vote of all of them — the one
# signal that involves no after-the-fact choice of rule.
RULES: Dict[str, Callable[[pd.DataFrame], pd.Series]] = dict(BASE_RULES, majority=majority_signal)
BENCHMARK = "always_long"


# ── Per-symbol returns ─────────────────────────────────────────────────────────

def strategy_returns(df: pd.DataFrame, signal: pd.Series, cost_bps: float) -> pd.DataFrame:
    """Daily net return of holding `signal` (sized by volatility), plus bookkeeping."""
    ret = df["close"].pct_change()
    position = (signal * vol_weight(ret)).shift(1)   # decided yesterday, earns today
    turnover = position.fillna(0.0).diff().abs().fillna(0.0)
    net = position * ret - turnover * (cost_bps / 10000.0)
    entries = ((signal.shift(1) > 0) & ~(signal.shift(2) > 0)).astype(float)
    return pd.DataFrame({"net": net, "position": position, "entries": entries}).dropna(subset=["net"])


def symbol_returns(df: pd.DataFrame, cost_bps: float) -> Dict[str, pd.DataFrame]:
    out = {name: strategy_returns(df, rule(df), cost_bps) for name, rule in RULES.items()}
    always = pd.Series(1.0, index=df.index)
    out[BENCHMARK] = strategy_returns(df, always, cost_bps)
    return out


# ── Metrics ────────────────────────────────────────────────────────────────────

def metrics(daily: pd.Series, periods_per_year: int) -> Dict:
    daily = daily.dropna()
    n = len(daily)
    if n < 60:
        return {"days": n}
    mean, std = float(daily.mean()), float(daily.std(ddof=1))
    sharpe = mean / std * math.sqrt(periods_per_year) if std > 0 else 0.0
    equity = (1.0 + daily).cumprod()
    drawdown = float((equity / equity.cummax() - 1.0).min())
    half = n // 2

    def _sharpe(x: pd.Series) -> float:
        s = float(x.std(ddof=1))
        return float(x.mean()) / s * math.sqrt(periods_per_year) if s > 0 else 0.0

    return {
        "days": n,
        "annual_return_pct": round(mean * periods_per_year * 100, 1),
        "annual_vol_pct": round(std * math.sqrt(periods_per_year) * 100, 1),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(drawdown * 100, 1),
        "t_stat": round(mean / (std / math.sqrt(n)), 2) if std > 0 else 0.0,
        "sharpe_first_half": round(_sharpe(daily.iloc[:half]), 2),
        "sharpe_second_half": round(_sharpe(daily.iloc[half:]), 2),
    }


def portfolio(per_symbol: Dict[str, Dict[str, pd.DataFrame]], strategy: str) -> pd.Series:
    """Equal-weight average of the symbols that have data on each day."""
    cols = {s: r[strategy]["net"] for s, r in per_symbol.items() if strategy in r}
    if not cols:
        return pd.Series(dtype=float)
    return pd.DataFrame(cols).sort_index().mean(axis=1, skipna=True).dropna()


def timing_value(strategy: pd.Series, benchmark: pd.Series, periods_per_year: int) -> Dict:
    """Is the rule better than simply holding? Paired on the same days."""
    both = pd.concat([strategy, benchmark], axis=1, keys=["s", "b"], sort=True).dropna()
    if len(both) < 60:
        return {}
    diff = both["s"] - both["b"]
    std = float(diff.std(ddof=1))
    return {
        "excess_annual_return_pct": round(float(diff.mean()) * periods_per_year * 100, 1),
        "excess_t_stat": round(float(diff.mean()) / (std / math.sqrt(len(diff))), 2) if std > 0 else 0.0,
    }


def same_vol_comparison(strategy: pd.Series, benchmark: pd.Series, periods_per_year: int) -> Dict:
    """Compare with holding scaled down to the strategy's own volatility.

    A rule that is in the market 40% of the time has less risk than always
    holding, so a smaller drawdown proves nothing by itself. Here the benchmark
    is de-risked to the same volatility; what is left is the value of timing.
    """
    both = pd.concat([strategy, benchmark], axis=1, keys=["s", "b"], sort=True).dropna()
    if len(both) < 60 or float(both["b"].std(ddof=1)) == 0:
        return {}
    k = float(both["s"].std(ddof=1)) / float(both["b"].std(ddof=1))
    scaled = both["b"] * k
    diff = both["s"] - scaled
    std = float(diff.std(ddof=1))
    equity = (1.0 + scaled).cumprod()
    return {
        "hold_same_vol_annual_pct": round(float(scaled.mean()) * periods_per_year * 100, 1),
        "hold_same_vol_max_drawdown_pct": round(float((equity / equity.cummax() - 1.0).min()) * 100, 1),
        "same_vol_excess_annual_pct": round(float(diff.mean()) * periods_per_year * 100, 1),
        "same_vol_excess_t_stat": round(float(diff.mean()) / (std / math.sqrt(len(diff))), 2) if std > 0 else 0.0,
    }


def _sharpe(daily: pd.Series, periods_per_year: int) -> float:
    daily = daily.dropna()
    std = float(daily.std(ddof=1)) if len(daily) > 2 else 0.0
    return float(daily.mean()) / std * math.sqrt(periods_per_year) if std > 0 else 0.0


def placebo_test(frames: Dict[str, pd.DataFrame], rule_name: str, cost_bps: float,
                 periods_per_year: int, runs: int, seed: int = 7,
                 synchronized: bool = True) -> Dict:
    """Is the timing better than the same trading pattern applied at the wrong time?

    Each symbol's real signal is rotated in time. That keeps how often and how
    long the rule holds, but breaks its link to the prices. The share of rotated
    portfolios that match or beat the real Sharpe is the chance of seeing this
    result from timing that carries no information.

    synchronized=True rotates every symbol by the SAME number of days. Crypto
    assets move together, so the real signals switch on and off together; a
    fair placebo must keep that, otherwise each rotated portfolio is quietly
    diversified across time, the placebo results bunch tightly around the
    market's own Sharpe, and the real result looks far more surprising than it
    is. synchronized=False (independent offsets) is kept only to show that gap.
    """
    rule = RULES[rule_name]
    signals = {s: rule(df) for s, df in frames.items()}
    actual = _sharpe(pd.DataFrame(
        {s: strategy_returns(frames[s], signals[s], cost_bps)["net"] for s in frames}
    ).sort_index().mean(axis=1, skipna=True), periods_per_year)

    rng = np.random.default_rng(seed)
    placebo = []
    longest = max((int(sig.notna().sum()) for sig in signals.values()), default=0)
    for _ in range(runs):
        cols = {}
        common = int(rng.integers(250, max(251, longest - 250)))
        for s, df in frames.items():
            sig = signals[s]
            valid = sig.dropna()
            if len(valid) < 600:
                continue
            # Arrays share their end date, so an equal shift keeps symbols aligned.
            offset = common % len(valid) if synchronized else int(rng.integers(250, len(valid) - 250))
            rotated = pd.Series(np.roll(valid.values, offset), index=valid.index).reindex(sig.index)
            cols[s] = strategy_returns(df, rotated, cost_bps)["net"]
        if cols:
            placebo.append(_sharpe(pd.DataFrame(cols).sort_index().mean(axis=1, skipna=True), periods_per_year))
    if not placebo:
        return {}
    placebo_arr = np.array(placebo)
    return {
        "rule": rule_name,
        "synchronized": synchronized,
        "actual_sharpe": round(actual, 2),
        "placebo_sharpe_mean": round(float(placebo_arr.mean()), 2),
        "placebo_sharpe_95th": round(float(np.percentile(placebo_arr, 95)), 2),
        "runs": len(placebo),
        # +1 so the estimate is never exactly zero from a finite number of runs
        "p_value": round(float((np.sum(placebo_arr >= actual) + 1) / (len(placebo) + 1)), 4),
    }


def verdict(m: Dict, bench: Dict) -> str:
    if "sharpe" not in m or "sharpe" not in bench:
        return "insufficient data"
    robust = m["sharpe_first_half"] > 0 and m["sharpe_second_half"] > 0
    if m["t_stat"] >= 2.0 and robust and m["sharpe"] > bench["sharpe"]:
        return "PROMISING"
    if m["sharpe"] > bench["sharpe"] and m["max_drawdown_pct"] > bench["max_drawdown_pct"]:
        return "better than holding, not proven"
    return "no evidence"


# ── Data ───────────────────────────────────────────────────────────────────────

def load_prices(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Daily OHLC. For USDC crypto pairs the USDT twin is used when it has a longer
    history — the price path is the same and the extra years matter for the test."""
    from ml.auto_trainer import fetch_binance_ohlcv, fetch_yfinance_ohlcv, YFINANCE_SYMBOL_MAP

    if symbol in YFINANCE_SYMBOL_MAP:
        df = fetch_yfinance_ohlcv(symbol, days=days)
    else:
        df = fetch_binance_ohlcv(symbol, interval="1d", days=days)
        if symbol.upper().endswith("USDC"):
            twin = fetch_binance_ohlcv(symbol.upper()[:-4] + "USDT", interval="1d", days=days)
            if twin is not None and (df is None or len(twin) > len(df)):
                df = twin
    if df is None or df.empty:
        return None
    df = df[["open", "high", "low", "close"]].copy()
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[(df["close"] > 0)].dropna()


def group_of(symbol: str) -> str:
    from ml.auto_trainer import YFINANCE_SYMBOL_MAP
    return "non_crypto" if symbol in YFINANCE_SYMBOL_MAP else "crypto"


PERIODS = {"crypto": 365, "non_crypto": 252}


# ── Report ─────────────────────────────────────────────────────────────────────

def run(symbols: List[str], days: int, cost_bps: float, placebo_runs: int = 0) -> Dict:
    per_symbol: Dict[str, Dict[str, Dict[str, pd.DataFrame]]] = {"crypto": {}, "non_crypto": {}}
    frames: Dict[str, Dict[str, pd.DataFrame]] = {"crypto": {}, "non_crypto": {}}
    skipped: Dict[str, str] = {}
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol} ...", file=sys.stderr, flush=True)
        try:
            df = load_prices(symbol, days)
            if df is None or len(df) < 300:
                skipped[symbol] = f"not enough history ({0 if df is None else len(df)} days)"
                continue
            per_symbol[group_of(symbol)][symbol] = symbol_returns(df, cost_bps)
            frames[group_of(symbol)][symbol] = df
        except Exception as exc:  # one bad symbol must not stop the run
            skipped[symbol] = f"{type(exc).__name__}: {exc}"

    report: Dict = {"groups": {}, "symbols": {}, "skipped": skipped,
                    "settings": {"days": days, "cost_bps": cost_bps,
                                 "target_daily_vol": TARGET_DAILY_VOL}}
    for group, members in per_symbol.items():
        if not members:
            continue
        ppy = PERIODS[group]
        bench_series = portfolio(members, BENCHMARK)
        bench = metrics(bench_series, ppy)
        rows = {BENCHMARK: dict(bench, verdict="benchmark")}
        for name in RULES:
            series = portfolio(members, name)
            m = metrics(series, ppy)
            m.update(timing_value(series, bench_series, ppy))
            m.update(same_vol_comparison(series, bench_series, ppy))
            m["time_in_market_pct"] = round(float(np.mean(
                [(r[name]["position"] > 0).mean() for r in members.values()])) * 100, 1)
            m["trades_per_symbol_year"] = round(float(np.mean(
                [r[name]["entries"].sum() / max(len(r[name]) / ppy, 1e-9) for r in members.values()])), 1)
            m["verdict"] = verdict(m, bench)
            rows[name] = m
        report["groups"][group] = {"symbols": len(members), "strategies": rows}
        if placebo_runs > 0:
            report["groups"][group]["placebo"] = [
                placebo_test(frames[group], name, cost_bps, ppy, placebo_runs, synchronized=sync)
                for name in ("sma_50", "majority") if name in RULES
                for sync in (True, False)
            ]
        for symbol, r in members.items():
            report["symbols"][symbol] = {name: metrics(frame["net"], ppy) for name, frame in r.items()}
    return report


def print_report(report: Dict, per_symbol: bool) -> None:
    for group, block in report["groups"].items():
        print(f"\n=== {group}: equal-weight portfolio of {block['symbols']} symbols ===")
        header = (f"{'strategy':<16}{'ann%':>7}{'vol%':>7}{'sharpe':>8}{'maxDD%':>8}{'t':>6}"
                  f"{'S_1st':>7}{'S_2nd':>7}{'vsHold%':>9}{'t_vs':>6}{'inMkt%':>8}{'tr/yr':>7}  verdict")
        print(header)
        print("-" * len(header))
        for name, m in block["strategies"].items():
            if "sharpe" not in m:
                print(f"{name:<16}insufficient data")
                continue
            print(f"{name:<16}{m['annual_return_pct']:>7}{m['annual_vol_pct']:>7}{m['sharpe']:>8}"
                  f"{m['max_drawdown_pct']:>8}{m['t_stat']:>6}{m['sharpe_first_half']:>7}"
                  f"{m['sharpe_second_half']:>7}{str(m.get('excess_annual_return_pct', '')):>9}"
                  f"{str(m.get('excess_t_stat', '')):>6}{str(m.get('time_in_market_pct', '')):>8}"
                  f"{str(m.get('trades_per_symbol_year', '')):>7}  {m['verdict']}")
        print(f"\n--- {group}: against holding de-risked to the same volatility ---")
        print(f"{'strategy':<16}{'ann%':>7}{'hold%':>7}{'diff%':>7}{'t':>6}{'maxDD%':>8}{'holdDD%':>9}")
        for name, m in block["strategies"].items():
            if "same_vol_excess_annual_pct" not in m:
                continue
            print(f"{name:<16}{m['annual_return_pct']:>7}{m['hold_same_vol_annual_pct']:>7}"
                  f"{m['same_vol_excess_annual_pct']:>7}{m['same_vol_excess_t_stat']:>6}"
                  f"{m['max_drawdown_pct']:>8}{m['hold_same_vol_max_drawdown_pct']:>9}")
        for p in block.get("placebo", []):
            if p:
                kind = "same shift for all symbols" if p["synchronized"] else "independent shifts (too lenient)"
                print(f"placebo {p['rule']} [{kind}]: real sharpe {p['actual_sharpe']} | rotated: "
                      f"mean {p['placebo_sharpe_mean']}, 95th pct {p['placebo_sharpe_95th']} "
                      f"({p['runs']} runs) | p = {p['p_value']}")
    if per_symbol:
        print("\n=== per symbol: sharpe by strategy ===")
        names = [BENCHMARK] + list(RULES)
        print(f"{'symbol':<11}{'days':>6}" + "".join(f"{n[:9]:>10}" for n in names))
        for symbol, rows in report["symbols"].items():
            days = rows[BENCHMARK].get("days", 0)
            print(f"{symbol:<11}{days:>6}" + "".join(f"{str(rows[n].get('sharpe', '-')):>10}" for n in names))
    if report["skipped"]:
        print("\nskipped: " + "; ".join(f"{s} ({why})" for s, why in report["skipped"].items()))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Trend-following backtest (read-only).")
    parser.add_argument("--symbols", help="Comma-separated symbols, e.g. BTCUSDC,SI1!")
    parser.add_argument("--all", action="store_true", help="Every training symbol")
    parser.add_argument("--crypto", action="store_true", help="Every crypto symbol")
    parser.add_argument("--days", type=int, default=3000, help="History to fetch per symbol")
    parser.add_argument("--cost-bps", type=float, default=10.0, help="Cost per side in basis points")
    parser.add_argument("--per-symbol", action="store_true", help="Also print a per-symbol table")
    parser.add_argument("--placebo", type=int, default=0, metavar="RUNS",
                        help="Placebo test: rotate signals in time RUNS times (e.g. 300)")
    parser.add_argument("--out", help="Write full results as JSON to this path")
    args = parser.parse_args(argv)

    if args.all:
        from ml.auto_trainer import TRAINING_SYMBOLS
        symbols = list(TRAINING_SYMBOLS)
    elif args.crypto:
        from ml.auto_trainer import CRYPTO_SYMBOLS
        symbols = list(CRYPTO_SYMBOLS)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        parser.error("pass --symbols, --crypto or --all")

    report = run(symbols, args.days, args.cost_bps, placebo_runs=args.placebo)
    print_report(report, args.per_symbol)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
        print(f"\nfull results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
