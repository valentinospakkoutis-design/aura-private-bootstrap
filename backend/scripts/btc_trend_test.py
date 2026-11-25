"""
Two questions about BTC, with criteria fixed in advance
(project doc aura_btc_benchmark_criteria.md, section C):

  1. Is the 50-day rule on BTC alone worth anything over BTC simply held at a
     10% volatility target?
  2. Do the 30 coins earn their keep — does the 50-day rule on the universe
     beat the same rule on BTC alone?

"Distinguishable" needs BOTH an excess return at equal risk with t >= 2 AND,
for question 1, a placebo p below 0.05 where the signal is shifted in time by
every possible offset. Anything else is "not distinguishable".

Also recorded, without bearing on the verdict: the Deflated Sharpe of the
universe rule's excess over volatility-targeted BTC, and the average pairwise
correlation of the universe by year (a co-movement measure that does not
depend on how many coins there are).

Read-only; uses the archive cache.

    python -m scripts.btc_trend_test
    python -m scripts.btc_trend_test --self-test
"""

import argparse
import json
import math
import os
import sys
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.method_audit import Tables, deflated_sharpe, sharpe_of  # noqa: E402
from scripts.survivorship_backtest import TOP_N, load_archive, synthetic_frames  # noqa: E402
from scripts.trend_backtest import RULES, metrics, same_vol_comparison  # noqa: E402
from services.trend_signal import annual_vol_weight  # noqa: E402

YEAR = 365
TARGET_ANNUAL_VOL = 0.10
T_THRESHOLD = 2.0
P_THRESHOLD = 0.05


def sized_returns(df: pd.DataFrame, signal: pd.Series, cost_bps: float) -> pd.DataFrame:
    """One asset: signal x volatility-target weight, decided at the close, earned the next day."""
    ret = df["close"].pct_change()
    position = (signal * annual_vol_weight(ret, TARGET_ANNUAL_VOL)).shift(1)
    turnover = position.fillna(0.0).diff().abs().fillna(0.0)
    cost = turnover * (cost_bps / 10000.0)
    return pd.DataFrame({"net": position * ret - cost, "position": position, "cost": cost}).dropna(subset=["net"])


def every_shift_placebo(df: pd.DataFrame, signal: pd.Series, window: pd.Index, cost_bps: float) -> Dict:
    """The rule's Sharpe against the same signal moved in time by every possible offset."""
    valid = signal.dropna()
    actual = sharpe_of(sized_returns(df, signal, cost_bps)["net"].reindex(window).values)
    shifted = np.empty(len(valid) - 1)
    for k in range(1, len(valid)):
        moved = pd.Series(np.roll(valid.values, k), index=valid.index).reindex(signal.index)
        shifted[k - 1] = sharpe_of(sized_returns(df, moved, cost_bps)["net"].reindex(window).values)
    return {
        "actual_sharpe": round(actual, 2), "shifts": int(len(shifted)),
        "shifted_mean": round(float(shifted.mean()), 2),
        "shifted_95th": round(float(np.percentile(shifted, 95)), 2),
        "p_value": round(float((np.sum(shifted >= actual) + 1) / (len(shifted) + 1)), 4),
    }


def decide(excess_pct: float, t_stat: float, p_value: Optional[float] = None) -> str:
    """Fixed before the run: both conditions, or it is not distinguishable."""
    ok = excess_pct > 0 and t_stat >= T_THRESHOLD and (p_value is None or p_value < P_THRESHOLD)
    return "DISTINGUISHABLE" if ok else "NOT DISTINGUISHABLE"


def pairwise_correlation_by_year(t: Tables) -> List[Dict]:
    """Mean correlation between pairs of universe members, month by month, averaged per year."""
    rows = []
    months = t.index.to_period("M")
    for period in months.unique():
        days = np.where(months == period)[0]
        members = np.where(t.member[days[0]])[0]
        block = pd.DataFrame(t.ret[np.ix_(days, members)]).dropna(axis=1, thresh=20)
        if block.shape[1] < 3:
            continue
        corr = block.corr().values
        off = corr[~np.eye(len(corr), dtype=bool)]
        rows.append({"year": period.year, "corr": float(np.nanmean(off)), "coins": block.shape[1]})
    frame = pd.DataFrame(rows)
    return [{"year": int(y), "average_pairwise_correlation": round(float(g["corr"].mean()), 2),
             "coins": round(float(g["coins"].mean()), 1)} for y, g in frame.groupby("year")]


def run(raw: Dict[str, pd.DataFrame], cost_bps: float, top_n: int, btc_symbol: str,
        placebo: Callable = every_shift_placebo) -> Dict:
    t = Tables(raw, top_n, cost_bps)
    window = t.index[t.lead:]
    btc = raw[btc_symbol]
    always = pd.Series(1.0, index=btc.index)
    trend = RULES["sma_50"](btc)

    held = sized_returns(btc, always, cost_bps).reindex(window).dropna(subset=["net"])
    ruled = sized_returns(btc, trend, cost_bps).reindex(window).dropna(subset=["net"])
    universe = t.series(t.signal["sma_50"]).reindex(window).dropna()

    def line(frame_or_series) -> Dict:
        s = frame_or_series["net"] if isinstance(frame_or_series, pd.DataFrame) else frame_or_series
        m = metrics(s, YEAR)
        if isinstance(frame_or_series, pd.DataFrame):
            m["time_in_market_pct"] = round(float((frame_or_series["position"] > 0).mean()) * 100)
            m["cost_pct_per_year"] = round(float(frame_or_series["cost"].mean()) * YEAR * 100, 2)
            m["average_weight_pct"] = round(float(frame_or_series["position"].mean()) * 100)
        return m

    q1 = same_vol_comparison(ruled["net"], held["net"], YEAR)
    q1_placebo = placebo(btc, trend, window, cost_bps)
    q2 = same_vol_comparison(universe, ruled["net"], YEAR)

    excess_vs_btc = {}
    for name in RULES:
        s = t.series(t.signal[name]).reindex(window).dropna()
        both = pd.concat([s, held["net"]], axis=1, keys=["s", "b"]).dropna()
        excess_vs_btc[name] = both["s"] - both["b"] * float(both["s"].std(ddof=1) / both["b"].std(ddof=1))

    return {
        "window": {"from": str(window[0])[:10], "to": str(window[-1])[:10], "btc_series": btc_symbol,
                   "target_annual_vol_pct": TARGET_ANNUAL_VOL * 100, "cost_bps": cost_bps},
        "lines": {"btc_voltarget": line(held), "btc_voltarget_trend50": line(ruled),
                  "sma_50 on the universe": line(universe)},
        "question_1": {"comparison": q1, "placebo": q1_placebo,
                       "verdict": decide(q1["same_vol_excess_annual_pct"], q1["same_vol_excess_t_stat"],
                                         q1_placebo["p_value"])},
        "question_2": {"comparison": q2,
                       "verdict": decide(q2["same_vol_excess_annual_pct"], q2["same_vol_excess_t_stat"])},
        "deflated_sharpe_universe_rule_vs_btc": deflated_sharpe(excess_vs_btc, "sma_50"),
        "pairwise_correlation_by_year": pairwise_correlation_by_year(t),
    }


def print_report(r: Dict) -> None:
    w = r["window"]
    print(f"\nBTC TREND TEST | {w['btc_series']} | {w['from']} to {w['to']} | target {w['target_annual_vol_pct']:.0f}% "
          f"yearly volatility, no leverage | {w['cost_bps']} bps per side")
    print(f"\n{'':<26}{'ann%':>7}{'vol%':>7}{'sharpe':>8}{'maxDD%':>8}{'S_1st':>7}{'S_2nd':>7}{'inMkt%':>8}{'cost%':>7}")
    for name, m in r["lines"].items():
        print(f"{name:<26}{m['annual_return_pct']:>7}{m['annual_vol_pct']:>7}{m['sharpe']:>8}{m['max_drawdown_pct']:>8}"
              f"{m['sharpe_first_half']:>7}{m['sharpe_second_half']:>7}"
              f"{str(m.get('time_in_market_pct', '')):>8}{str(m.get('cost_pct_per_year', '')):>7}")

    q, p = r["question_1"]["comparison"], r["question_1"]["placebo"]
    print("\nQUESTION 1 - does the 50-day rule on BTC beat BTC simply held at the same volatility target?")
    print(f"  at equal risk: benchmark {q['hold_same_vol_annual_pct']}% a year, excess {q['same_vol_excess_annual_pct']}% "
          f"a year, t = {q['same_vol_excess_t_stat']}")
    print(f"  placebo over all {p['shifts']} time shifts: rule Sharpe {p['actual_sharpe']} vs shifted mean "
          f"{p['shifted_mean']}, 95th {p['shifted_95th']} -> p = {p['p_value']}")
    print(f"  VERDICT: {r['question_1']['verdict']}  (needs t >= {T_THRESHOLD} and p < {P_THRESHOLD})")

    q = r["question_2"]["comparison"]
    print("\nQUESTION 2 - does the rule on 30 coins beat the same rule on BTC alone?")
    print(f"  at equal risk: BTC-only rule {q['hold_same_vol_annual_pct']}% a year, excess {q['same_vol_excess_annual_pct']}% "
          f"a year, t = {q['same_vol_excess_t_stat']}")
    print(f"  VERDICT: {r['question_2']['verdict']}  (needs t >= {T_THRESHOLD})")

    d = r["deflated_sharpe_universe_rule_vs_btc"]
    print(f"\nRecorded only: Deflated Sharpe of the universe rule's excess over volatility-targeted BTC: "
          f"Sharpe {d['sharpe_annual']} vs {d['luck_benchmark_sharpe_annual']} expected from the luckiest of "
          f"{d['trials']} -> probability {d['deflated_sharpe_probability']} "
          f"(without the correction: {d['probability_sharpe_above_zero']})")
    print("Recorded only: average pairwise correlation inside the universe, by year:")
    print("  " + "  ".join(f"{c['year']}: {c['average_pairwise_correlation']} ({c['coins']:.0f} coins)"
                           for c in r["pairwise_correlation_by_year"]))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    raw = synthetic_frames() if args.self_test else load_archive(args.cache, args.workers)
    symbol = "C1USDT" if args.self_test else "BTCUSDT"
    if not raw or symbol not in raw:
        print(f"{symbol} not loaded", file=sys.stderr)
        return 1
    report = run(raw, args.cost_bps, 9 if args.self_test else args.top_n, symbol)
    print_report(report)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
