"""
Relative strength (cross-sectional momentum) on large crypto coins.

One rule, fixed before it was run (project doc aura_xs_momentum_criteria.md):
every 7 days, among the point-in-time top-30 USDT pairs by traded value, hold
the third with the best 14-day return. Long only, each position sized by
volatility exactly like the trend rule, 30 bps per side.

Judged on
  (a) excess return over holding the whole universe at equal risk, net of cost;
  (b) whether the ranking carries information: the rule's Sharpe against
      portfolios that pick the same number of coins at random each week,
      compared before costs on both sides.
If it holds, a second question: does a 50/50 mix with the 50-day trend rule
beat the trend rule alone, over the full period and over the second half?

Read-only. Uses the archive cache written by scripts.survivorship_backtest.

    python -m scripts.xs_momentum_backtest
    python -m scripts.xs_momentum_backtest --self-test
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.survivorship_backtest import (  # noqa: E402
    TOP_N, VOLUME_WINDOW, build_membership, load_archive, split_on_gaps, synthetic_frames, verdict,
)
from scripts.trend_backtest import RULES, metrics, same_vol_comparison  # noqa: E402
from services.trend_signal import MIN_HISTORY_DAYS, vol_weight  # noqa: E402

LOOKBACK_DAYS = 14
REBALANCE_DAYS = 7
HOLD_FRACTION = 1.0 / 3.0
YEAR = 365


def _sharpe(x: pd.Series) -> float:
    x = x.dropna()
    s = float(x.std(ddof=1)) if len(x) > 2 else 0.0
    return float(x.mean()) / s * math.sqrt(YEAR) if s > 0 else 0.0


class Universe:
    """Aligned (day x coin) tables for one point-in-time universe."""

    def __init__(self, frames: Dict[str, pd.DataFrame], top_n: int):
        frames = split_on_gaps(frames)
        frames = {s: df for s, df in frames.items() if len(df) > MIN_HISTORY_DAYS + VOLUME_WINDOW}
        member = build_membership(frames, top_n)
        used = [s for s in frames if member[s].any()]
        self.member = member[used].loc[member[used].any(axis=1)]
        index = self.member.index
        table = lambda d: pd.DataFrame(d).reindex(index)  # noqa: E731
        self.ret = table({s: frames[s]["close"].pct_change() for s in used})
        self.weight = table({s: vol_weight(frames[s]["close"].pct_change()) for s in used})
        self.momentum = table({s: frames[s]["close"].pct_change(LOOKBACK_DAYS) for s in used})
        self.trend = table({s: RULES["sma_50"](frames[s]) for s in used})
        self.rebalance_days = index[::REBALANCE_DAYS]
        self.symbols = used

    def portfolio(self, held: pd.DataFrame, cost_bps: float) -> pd.Series:
        """Daily return of holding `held` (1/0 per coin, as decided at each close)."""
        position = (held * self.weight).shift(1)                 # decided yesterday, earns today
        turnover = position.fillna(0.0).diff().abs().fillna(0.0)
        net = position * self.ret - turnover * (cost_bps / 10000.0)
        return net.where(self.member).mean(axis=1, skipna=True).dropna()

    def cost_drag(self, held: pd.DataFrame, cost_bps: float) -> pd.Series:
        position = (held * self.weight).shift(1)
        turnover = position.fillna(0.0).diff().abs().fillna(0.0)
        return (turnover * (cost_bps / 10000.0)).where(self.member).mean(axis=1, skipna=True)

    def select(self, rank_by: Optional[pd.DataFrame], rng: Optional[np.random.Generator] = None,
               bottom: bool = False) -> pd.DataFrame:
        """Weekly selection held until the next rebalance. rank_by=None picks at random."""
        held = pd.DataFrame(np.nan, index=self.member.index, columns=self.member.columns)
        for day in self.rebalance_days:
            eligible = self.member.loc[day] & self.momentum.loc[day].notna()
            names = list(eligible.index[eligible.values])
            held.loc[day] = 0.0
            if not names:
                continue
            count = max(1, int(round(len(names) * HOLD_FRACTION)))
            if rank_by is None:
                chosen = list(rng.choice(names, size=count, replace=False))
            else:
                ranked = rank_by.loc[day, names].sort_values(ascending=bottom)
                chosen = list(ranked.index[:count])
            held.loc[day, chosen] = 1.0
        return held.ffill().fillna(0.0)


def evaluate(frames: Dict[str, pd.DataFrame], cost_bps: float, runs: int, top_n: int = TOP_N,
             seed: int = 11) -> Dict:
    u = Universe(frames, top_n)
    everything = pd.DataFrame(1.0, index=u.member.index, columns=u.member.columns)
    top = u.select(u.momentum)
    bottom = u.select(u.momentum, bottom=True)

    hold = u.portfolio(everything, cost_bps)
    rule = u.portfolio(top, cost_bps)
    losers = u.portfolio(bottom, cost_bps)
    trend = u.portfolio(u.trend.fillna(0.0), cost_bps)

    row = metrics(rule, YEAR)
    row.update(same_vol_comparison(rule, hold, YEAR))

    actual_gross = _sharpe(u.portfolio(top, 0.0))
    rng = np.random.default_rng(seed)
    random_gross = np.array([_sharpe(u.portfolio(u.select(None, rng), 0.0)) for _ in range(runs)]) \
        if runs > 0 else np.array([])
    p_value = float((np.sum(random_gross >= actual_gross) + 1) / (len(random_gross) + 1)) if runs > 0 else float("nan")
    decision = verdict(row.get("same_vol_excess_annual_pct", 0.0), p_value) if runs > 0 else "not judged"

    both = pd.concat([rule, trend], axis=1, keys=["rule", "trend"]).dropna()
    mix = 0.5 * both["rule"] + 0.5 * both["trend"]
    half = len(both) // 2
    combo = {
        "correlation_with_trend": round(float(both["rule"].corr(both["trend"])), 2),
        "trend_sharpe": round(_sharpe(both["trend"]), 2),
        "mix_sharpe": round(_sharpe(mix), 2),
        "trend_sharpe_second_half": round(_sharpe(both["trend"].iloc[half:]), 2),
        "mix_sharpe_second_half": round(_sharpe(mix.iloc[half:]), 2),
    }
    combo["adds_to_trend"] = bool(decision == "HOLDS" and combo["mix_sharpe"] > combo["trend_sharpe"]
                                  and combo["mix_sharpe_second_half"] > combo["trend_sharpe_second_half"])

    spread = pd.concat([rule, losers], axis=1, keys=["top", "bottom"]).dropna()
    cost = u.cost_drag(top, cost_bps).reindex(rule.index)
    return {
        "universe": {"coins": len(u.symbols), "from": str(u.member.index[0])[:10], "to": str(u.member.index[-1])[:10],
                     "rebalances": int(len(u.rebalance_days))},
        "settings": {"lookback_days": LOOKBACK_DAYS, "rebalance_days": REBALANCE_DAYS,
                     "hold_fraction": round(HOLD_FRACTION, 3), "cost_bps": cost_bps, "random_runs": runs},
        "hold": metrics(hold, YEAR),
        "rule": row,
        "bottom_third": metrics(losers, YEAR),
        "top_minus_bottom": metrics(spread["top"] - spread["bottom"], YEAR),
        "trend_sma_50": metrics(trend, YEAR),
        "ranking_test": {
            "rule_sharpe_before_costs": round(actual_gross, 2),
            "random_sharpe_mean": round(float(random_gross.mean()), 2) if runs > 0 else None,
            "random_sharpe_95th": round(float(np.percentile(random_gross, 95)), 2) if runs > 0 else None,
            "p_value": round(p_value, 4) if runs > 0 else None,
        },
        "verdict": decision,
        "with_trend": combo,
        "cost_by_year_pct": {int(y): round(float(g.mean()) * YEAR * 100, 1) for y, g in cost.groupby(cost.index.year)},
    }


def print_report(r: Dict) -> None:
    u, s = r["universe"], r["settings"]
    print(f"\nRelative strength: best {s['lookback_days']}-day return, top third, rebalanced every "
          f"{s['rebalance_days']} days, {s['cost_bps']} bps per side")
    print(f"{u['coins']} coins | {u['from']} to {u['to']} | {u['rebalances']} rebalances")
    print(f"\n{'':<22}{'ann%':>7}{'sharpe':>8}{'maxDD%':>8}{'S_1st':>7}{'S_2nd':>7}")
    for label, key in (("hold everything", "hold"), ("top third (the rule)", "rule"), ("bottom third", "bottom_third"),
                       ("top minus bottom", "top_minus_bottom"), ("trend sma_50", "trend_sma_50")):
        m = r[key]
        if "sharpe" not in m:
            print(f"{label:<22} insufficient data")
            continue
        print(f"{label:<22}{m['annual_return_pct']:>7}{m['sharpe']:>8}{m['max_drawdown_pct']:>8}"
              f"{m['sharpe_first_half']:>7}{m['sharpe_second_half']:>7}")
    m, t = r["rule"], r["ranking_test"]
    print(f"\n(a) excess over holding at equal risk: {m.get('same_vol_excess_annual_pct')}% per year "
          f"(t = {m.get('same_vol_excess_t_stat')})")
    print(f"(b) ranking test before costs: rule Sharpe {t['rule_sharpe_before_costs']} vs random picks "
          f"mean {t['random_sharpe_mean']}, 95th percentile {t['random_sharpe_95th']} -> p = {t['p_value']}")
    print(f"\nVERDICT: {r['verdict']}")
    c = r["with_trend"]
    print(f"\nWith the trend rule: correlation {c['correlation_with_trend']} | Sharpe trend {c['trend_sharpe']} "
          f"vs 50/50 mix {c['mix_sharpe']} | second half: trend {c['trend_sharpe_second_half']} "
          f"vs mix {c['mix_sharpe_second_half']}")
    print(f"ADDS TO TREND: {'yes' if c['adds_to_trend'] else 'no'}"
          + ("" if r["verdict"] == "HOLDS" else " (only considered when the verdict is HOLDS)"))
    print("cost per year (%):", ", ".join(f"{y}: {v}" for y, v in r["cost_by_year_pct"].items()))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--random-runs", type=int, default=300)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    frames = synthetic_frames() if args.self_test else load_archive(args.cache, args.workers)
    if not frames:
        print("no data loaded", file=sys.stderr)
        return 1
    report = evaluate(frames, args.cost_bps, args.random_runs, 9 if args.self_test else args.top_n)
    print_report(report)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
