"""
Where did the trend rule's advantage go?

scripts.survivorship_backtest showed the 50-day rule holding up over 2018-2026
but much weaker in the second half. This script only describes — it fits
nothing and proposes nothing. It cuts the same point-in-time backtest by year
and by the state of the market, so a later test can be aimed at one specific,
pre-declared idea instead of a search.

Every market state is known the day before the return it is matched with.

    python -m scripts.trend_diagnosis               # uses the archive cache
    python -m scripts.trend_diagnosis --self-test   # synthetic, no network
"""

import argparse
import math
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.survivorship_backtest import (  # noqa: E402
    TOP_N, VOLUME_WINDOW, build_membership, load_archive, masked_portfolio,
    split_on_gaps, synthetic_frames,
)
from scripts.trend_backtest import BENCHMARK, RULES, strategy_returns  # noqa: E402
from services.trend_signal import MIN_HISTORY_DAYS, vol_weight  # noqa: E402

YEAR = 365


def _ann(x: pd.Series) -> float:
    return float(x.mean()) * YEAR * 100 if len(x) else float("nan")


def _t(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 30 or float(x.std(ddof=1)) == 0:
        return float("nan")
    return float(x.mean()) / (float(x.std(ddof=1)) / math.sqrt(len(x)))


def _sharpe(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 30 or float(x.std(ddof=1)) == 0:
        return float("nan")
    return float(x.mean()) / float(x.std(ddof=1)) * math.sqrt(YEAR)


def build(frames: Dict[str, pd.DataFrame], rule_name: str, cost_bps: float, top_n: int) -> Dict:
    frames = split_on_gaps(frames)
    frames = {s: df for s, df in frames.items() if len(df) > MIN_HISTORY_DAYS + VOLUME_WINDOW}
    member = build_membership(frames, top_n)
    used = [s for s in frames if member[s].any()]
    frames = {s: frames[s] for s in used}
    member = member[used].loc[member[used].any(axis=1)]

    rule = RULES[rule_name]
    nets, holds, gross, raw, sized, signal = {}, {}, {}, {}, {}, {}
    for s, df in frames.items():
        ret = df["close"].pct_change()
        sig = rule(df)
        traded = strategy_returns(df, sig, cost_bps)
        nets[s] = traded["net"]
        gross[s] = traded["position"] * ret.reindex(traded.index)
        holds[s] = strategy_returns(df, pd.Series(1.0, index=df.index), cost_bps)["net"]
        raw[s] = ret
        sized[s] = vol_weight(ret).shift(1) * ret          # what a volatility-sized holder earns
        signal[s] = sig.shift(1)                           # the signal the day's return was earned under

    table = lambda d: pd.DataFrame(d).reindex(member.index).where(member)  # noqa: E731
    rule_p = masked_portfolio(nets, member)
    hold_p = masked_portfolio(holds, member)
    both = pd.concat([rule_p, hold_p], axis=1, keys=["rule", "hold"]).dropna()
    k = float(both["rule"].std(ddof=1)) / float(both["hold"].std(ddof=1))
    both["hold_same_vol"] = both["hold"] * k
    both["excess"] = both["rule"] - both["hold_same_vol"]
    both["cost"] = (table(gross).mean(axis=1) - table(nets).mean(axis=1)).reindex(both.index)

    raw_t, sig_t, sized_t = table(raw), table(signal), table(sized)
    index_ret = raw_t.mean(axis=1)
    level = (1.0 + index_ret.fillna(0.0)).cumprod()
    vol30 = index_ret.rolling(30).std()
    own_var = pd.DataFrame(raw).reindex(member.index).rolling(60).var().where(member).mean(axis=1)
    comove = index_ret.rolling(60).var() / own_var
    breadth = sig_t.mean(axis=1)                           # already yesterday's signal

    states = pd.DataFrame({
        "market_trend": np.where(level > level.rolling(200).mean(), "market above 200d avg", "market below 200d avg"),
        "volatility": np.where(vol30 > vol30.expanding(YEAR).median(), "turbulent", "calm"),
        "co_movement": np.where(comove > comove.expanding(YEAR).median(), "coins move together", "coins move apart"),
    }, index=member.index)
    for col, src in (("market_trend", level.rolling(200).mean()), ("volatility", vol30.expanding(YEAR).median()),
                     ("co_movement", comove.expanding(YEAR).median())):
        states[col] = states[col].where(src.notna())
    states = states.shift(1)                               # known the day before
    states["breadth"] = pd.cut(breadth, [-0.01, 1 / 3, 2 / 3, 1.0],
                               labels=["under 1/3 of coins in uptrend", "1/3 to 2/3", "over 2/3"]).astype(object)

    on = sized_t.where(sig_t > 0).mean(axis=1)
    off = sized_t.where(sig_t == 0).mean(axis=1)
    return {"daily": both, "states": states.reindex(both.index), "k": k, "rule": rule_name,
            "on": on.reindex(both.index), "off": off.reindex(both.index),
            "in_market": (sig_t > 0).sum(axis=1).div(member.sum(axis=1)).reindex(both.index),
            "symbols": len(used)}


def report(d: Dict) -> None:
    daily, states = d["daily"], d["states"]
    mid = daily.index[len(daily) // 2]
    halves = {"1st half": daily.index < mid, "2nd half": daily.index >= mid}
    print(f"\nRule: {d['rule']} | {d['symbols']} coins | {str(daily.index[0])[:10]} to {str(daily.index[-1])[:10]} "
          f"| halves split at {str(mid)[:10]}")
    print(f"Holding is scaled by {d['k']:.2f} to match the rule's volatility (one factor for the whole period).")

    print("\n-- By year (% per year; 'excess' = rule minus holding at equal risk) --")
    print(f"{'year':<8}{'hold':>8}{'rule':>8}{'excess':>8}{'t':>7}{'ruleSharpe':>12}{'inMkt%':>8}{'cost%':>7}")
    for year, g in daily.groupby(daily.index.year):
        print(f"{year:<8}{_ann(g['hold_same_vol']):>8.1f}{_ann(g['rule']):>8.1f}{_ann(g['excess']):>8.1f}"
              f"{_t(g['excess']):>7.2f}{_sharpe(g['rule']):>12.2f}"
              f"{float(d['in_market'].loc[g.index].mean()) * 100:>8.0f}{_ann(g['cost']):>7.1f}")

    print("\n-- Does the signal separate good days from bad? (average daily return of a "
          "volatility-sized holding, in basis points) --")
    print(f"{'period':<10}{'signal ON':>11}{'signal OFF':>12}{'difference':>12}{'t':>7}")
    for name, mask in list(halves.items()) + [("all", np.ones(len(daily), dtype=bool))]:
        on, off = d["on"][mask], d["off"][mask]
        diff = (on - off).dropna()
        print(f"{name:<10}{float(on.mean()) * 1e4:>11.1f}{float(off.mean()) * 1e4:>12.1f}"
              f"{float(diff.mean()) * 1e4:>12.1f}{_t(diff):>7.2f}")

    print("\n-- By market state (state known the day before) --")
    print(f"{'state':<32}{'days%':>7}{'1st%':>6}{'2nd%':>6}{'hold':>8}{'rule':>8}{'excess':>8}{'t':>7}"
          f"{'xs 1st':>8}{'xs 2nd':>8}")
    for col in states.columns:
        print(f"[{col}]")
        for value in [v for v in pd.unique(states[col].dropna())]:
            m = (states[col] == value).values
            g = daily[m]
            if len(g) < 60:
                continue
            row = [float(m.mean()) * 100]
            row += [float(m[h].mean()) * 100 for h in halves.values()]
            xs = [_ann(daily[m & h]["excess"]) if (m & h).sum() >= 60 else float("nan") for h in halves.values()]
            print(f"  {str(value):<30}{row[0]:>7.0f}{row[1]:>6.0f}{row[2]:>6.0f}{_ann(g['hold_same_vol']):>8.1f}"
                  f"{_ann(g['rule']):>8.1f}{_ann(g['excess']):>8.1f}{_t(g['excess']):>7.2f}{xs[0]:>8.1f}{xs[1]:>8.1f}")

    print("\n-- Halves --")
    print(f"{'period':<10}{'hold':>8}{'rule':>8}{'excess':>8}{'t':>7}{'cost%':>7}{'inMkt%':>8}")
    for name, mask in halves.items():
        g = daily[mask]
        print(f"{name:<10}{_ann(g['hold_same_vol']):>8.1f}{_ann(g['rule']):>8.1f}{_ann(g['excess']):>8.1f}"
              f"{_t(g['excess']):>7.2f}{_ann(g['cost']):>7.1f}{float(d['in_market'][mask].mean()) * 100:>8.0f}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rule", default="sma_50", choices=sorted(RULES))
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    frames = synthetic_frames() if args.self_test else load_archive(args.cache, args.workers)
    if not frames:
        print("no data loaded", file=sys.stderr)
        return 1
    report(build(frames, args.rule, args.cost_bps, 8 if args.self_test else args.top_n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
