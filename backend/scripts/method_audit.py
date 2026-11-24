"""
Measurement audit of the trend and relative-strength results.

Nothing here changes a rule, a parameter or a position. It re-measures what was
already tested, with a better instrument, after an outside review pointed out
six weaknesses:

  1. 300 placebo runs put a floor of 0.0033 under every p-value -> many more runs.
  2. No correction for having tried eight rules -> a max-statistic test across
     all eight (each rule against the best of the eight placebos), Bonferroni
     for the two rules that were judged, and the Deflated Sharpe Ratio.
  3. Tables mixed raw holding with a risk-matched comparison -> volatility
     shown and every row labelled.
  4. Splitting a ticker at a trading halt might hide the worst of a collapse
     -> what happened around every ending and every halt, measured.
  5. "The market gave less" had an untested rival: the universe itself changed
     -> composition of the universe by year.
  6. Holding the universe is a soft benchmark -> volatility-targeted BTC.

Read-only; uses the archive cache.

    python -m scripts.method_audit                 # full (about an hour)
    python -m scripts.method_audit --runs 200      # quick
    python -m scripts.method_audit --self-test
"""

import argparse
import json
import math
import os
import sys
from statistics import NormalDist
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.survivorship_backtest import (  # noqa: E402
    MAX_GAP_DAYS, TOP_N, VOLUME_WINDOW, build_membership, load_archive, split_on_gaps, synthetic_frames,
)
from scripts.trend_backtest import RULES, metrics, same_vol_comparison, strategy_returns  # noqa: E402
from scripts.xs_momentum_backtest import HOLD_FRACTION, LOOKBACK_DAYS, REBALANCE_DAYS  # noqa: E402
from services.trend_signal import MIN_HISTORY_DAYS, vol_weight  # noqa: E402

YEAR = 365
JUDGED = ("sma_50", "majority")
NORMAL = NormalDist()


def sharpe_of(daily: np.ndarray) -> float:
    daily = daily[~np.isnan(daily)]
    if len(daily) < 3:
        return 0.0
    s = daily.std(ddof=1)
    return float(daily.mean() / s * math.sqrt(YEAR)) if s > 0 else 0.0


class Tables:
    """Everything as aligned numpy arrays (day x coin)."""

    def __init__(self, raw: Dict[str, pd.DataFrame], top_n: int, cost_bps: float):
        self.raw = raw
        segments = split_on_gaps(raw)
        self.segments = segments
        frames = {s: df for s, df in segments.items() if len(df) > MIN_HISTORY_DAYS + VOLUME_WINDOW}
        member = build_membership(frames, top_n)
        used = [s for s in frames if member[s].any()]
        member = member[used].loc[member[used].any(axis=1)]
        # Three extra leading days (nobody a member yet) so that the first real day
        # has yesterday's positions, exactly as in the per-coin backtest.
        lead = pd.date_range(end=member.index[0] - pd.Timedelta(days=1), periods=3, freq="D")
        member = member.reindex(lead.append(member.index), fill_value=False)
        self.lead = len(lead)
        self.frames = {s: frames[s] for s in used}
        self.index, self.symbols = member.index, used
        self.member_df = member
        self.member = member.values.astype(bool)
        tab = lambda d: pd.DataFrame(d).reindex(self.index)[used]  # noqa: E731
        self.ret_df = tab({s: self.frames[s]["close"].pct_change() for s in used})
        self.ret = self.ret_df.values
        self.weight = tab({s: vol_weight(self.frames[s]["close"].pct_change()) for s in used}).values
        self.momentum = tab({s: self.frames[s]["close"].pct_change(LOOKBACK_DAYS) for s in used}).values
        self.signal = {name: tab({s: rule(self.frames[s]) for s in used}).values for name, rule in RULES.items()}
        self.cost = cost_bps / 10000.0
        # Same weekly schedule as scripts.xs_momentum_backtest: every 7th day from the first real day.
        self.rebalance_rows = np.arange(self.lead, len(self.index), REBALANCE_DAYS)
        # Where each coin's signal is defined: one contiguous block per column.
        self.blocks = {}
        for name, sig in self.signal.items():
            ok = ~np.isnan(sig)
            first = np.where(ok.any(axis=0), ok.argmax(axis=0), 0)
            last = np.where(ok.any(axis=0), len(sig) - ok[::-1].argmax(axis=0), 0)
            self.blocks[name] = (first, last)

    def daily(self, held: np.ndarray, cost: Optional[float] = None) -> np.ndarray:
        """Portfolio return per day for a (day x coin) holding decided at each close."""
        cost = self.cost if cost is None else cost
        position = np.full_like(held, np.nan)
        position[1:] = (held * self.weight)[:-1]
        filled = np.nan_to_num(position)
        turnover = np.abs(np.diff(filled, axis=0, prepend=filled[:1]))
        net = position * self.ret - turnover * cost
        net[~self.member] = np.nan
        with np.errstate(invalid="ignore"):
            count = (~np.isnan(net)).sum(axis=1)
            return np.where(count > 0, np.nansum(net, axis=1) / np.maximum(count, 1), np.nan)

    def series(self, held: np.ndarray, cost: Optional[float] = None) -> pd.Series:
        return pd.Series(self.daily(held, cost), index=self.index).dropna()

    def rotated(self, name: str, common: int) -> np.ndarray:
        sig = self.signal[name]
        out = np.full_like(sig, np.nan)
        first, last = self.blocks[name]
        for j in range(sig.shape[1]):
            a, b = int(first[j]), int(last[j])
            if b - a >= 2:
                out[a:b, j] = np.roll(sig[a:b, j], common % (b - a))
        return out

    # relative strength -------------------------------------------------------
    def weekly_pick(self, scores: np.ndarray, phase: int = 0) -> np.ndarray:
        """phase shifts the weekly rebalance day; 0 is the schedule that was tested."""
        rows = self.rebalance_rows + phase
        rows = rows[rows < len(self.index)]
        scores = scores[: len(rows)]
        eligible = self.member[rows] & ~np.isnan(self.momentum[rows])
        s = np.where(eligible, scores, -np.inf)
        order = np.argsort(-s, axis=1, kind="stable")
        held = np.zeros_like(s)
        for i, n in enumerate(eligible.sum(axis=1)):
            if n:
                held[i, order[i, :max(1, int(round(n * HOLD_FRACTION)))]] = 1.0
        daily = np.zeros((len(self.index), held.shape[1]))
        start = self.lead + phase
        daily[start:] = np.repeat(held, REBALANCE_DAYS, axis=0)[: len(self.index) - start]
        return daily


# ── 1 + 2: placebo with many runs, corrected for the eight rules ───────────────

def placebo_all_rules(t: Tables, runs: int, seed: int = 7) -> Dict:
    actual = {name: sharpe_of(t.daily(t.signal[name])) for name in RULES}
    longest = max(int((b - a).max()) for a, b in t.blocks.values())
    rng = np.random.default_rng(seed)
    table = np.empty((runs, len(RULES)))
    for r in range(runs):
        common = int(rng.integers(250, max(251, longest - 250)))
        for k, name in enumerate(RULES):
            table[r, k] = sharpe_of(t.daily(t.rotated(name, common)))
        if (r + 1) % 500 == 0:
            print(f"  placebo {r + 1}/{runs}", file=sys.stderr, flush=True)
    best = table.max(axis=1)
    out = {}
    for k, name in enumerate(RULES):
        own = float((np.sum(table[:, k] >= actual[name]) + 1) / (runs + 1))
        family = float((np.sum(best >= actual[name]) + 1) / (runs + 1))
        out[name] = {
            "actual_sharpe": round(actual[name], 2),
            "placebo_mean": round(float(table[:, k].mean()), 2),
            "placebo_95th": round(float(np.percentile(table[:, k], 95)), 2),
            "p_own_placebo": round(own, 4),
            "p_best_of_eight": round(family, 4),
        }
    out["_best_of_eight_placebo_95th"] = round(float(np.percentile(best, 95)), 2)
    out["_runs"] = runs
    return out


def deflated_sharpe(series: Dict[str, pd.Series], chosen: str) -> Dict:
    """Bailey & Lopez de Prado: is the best Sharpe more than the best of N would be by luck?"""
    per_day = {n: float(s.mean() / s.std(ddof=1)) for n, s in series.items() if s.std(ddof=1) > 0}
    n = len(per_day)
    variance = float(np.var(list(per_day.values()), ddof=1))
    euler = 0.5772156649
    expected_best = math.sqrt(variance) * ((1 - euler) * NORMAL.inv_cdf(1 - 1 / n)
                                           + euler * NORMAL.inv_cdf(1 - 1 / (n * math.e)))
    x = series[chosen]
    sr, length = per_day[chosen], len(x)
    skew = float(((x - x.mean()) ** 3).mean() / x.std(ddof=0) ** 3)
    kurt = float(((x - x.mean()) ** 4).mean() / x.std(ddof=0) ** 4)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr * sr))
    psr = lambda benchmark: NORMAL.cdf((sr - benchmark) * math.sqrt(length - 1) / denom)  # noqa: E731
    return {
        "trials": n,
        "sharpe_annual": round(sr * math.sqrt(YEAR), 2),
        "luck_benchmark_sharpe_annual": round(expected_best * math.sqrt(YEAR), 2),
        "skew": round(skew, 2), "kurtosis": round(kurt, 1), "days": length,
        "probability_sharpe_above_zero": round(psr(0.0), 3),
        "deflated_sharpe_probability": round(psr(expected_best), 3),
    }


# ── 4: endings and halts ──────────────────────────────────────────────────────

def endings_and_halts(t: Tables) -> Dict:
    archive_end = max(df.index[-1] for df in t.raw.values())
    sma = t.signal["sma_50"]
    col = {s: j for j, s in enumerate(t.symbols)}
    rows = []
    for s in t.symbols:
        df = t.frames[s]
        end = df.index[-1]
        if (archive_end - end).days <= 60 or end not in t.index:
            continue
        i = t.index.get_loc(end)
        tail = df["close"].iloc[-30:]
        base, n = (s.split("#") + ["1"])[:2]
        nxt = t.segments.get(f"{base}#{int(n) + 1}")
        rows.append({
            "symbol": s, "ended": str(end)[:10],
            "in_universe_at_end": bool(t.member[i, col[s]]),
            "rule_held_at_end": bool(sma[i, col[s]] > 0),
            "drop_last_30d_pct": round(float(tail.iloc[-1] / tail.max() - 1) * 100, 1),
            "resumed_after_days": int((nxt.index[0] - end).days) if nxt is not None else None,
            "price_change_across_halt_pct": round(float(nxt["close"].iloc[0] / df["close"].iloc[-1] - 1) * 100, 1)
            if nxt is not None else None,
        })
    inside = [r for r in rows if r["in_universe_at_end"]]
    short = []
    for s in t.symbols:
        df = t.frames[s]
        gap = df.index.to_series().diff().dt.days
        for day in gap[(gap > 1) & (gap <= MAX_GAP_DAYS)].index:
            if day in t.index and t.member[t.index.get_loc(day), col[s]]:
                prev = df["close"].shift(1).loc[day]
                short.append({"symbol": s, "day": str(day)[:10], "missing_days": int(gap.loc[day]) - 1,
                              "return_across_pct": round(float(df["close"].loc[day] / prev - 1) * 100, 1)})
    return {
        "instruments_that_stopped_trading": len(rows),
        "of_which_in_universe_on_last_day": len(inside),
        "of_those_rule_still_held": sum(r["rule_held_at_end"] for r in inside),
        "of_those_fell_over_30pct_in_last_30d": sum(r["drop_last_30d_pct"] <= -30 for r in inside),
        "median_drop_last_30d_pct_in_universe": round(float(np.median([r["drop_last_30d_pct"] for r in inside])), 1)
        if inside else None,
        "in_universe_at_end": sorted(inside, key=lambda r: r["drop_last_30d_pct"]),
        "resumed_tickers": [r for r in rows if r["resumed_after_days"] is not None],
        "short_halts_inside_universe": len(short),
        "worst_short_halts": sorted(short, key=lambda r: r["return_across_pct"])[:8],
    }


# ── 5: did the universe change? ───────────────────────────────────────────────

def composition_by_year(t: Tables) -> List[Dict]:
    member = t.member_df
    ret = t.ret_df.where(member)
    full_ret = t.ret_df
    index_ret = ret.mean(axis=1)
    age = pd.DataFrame({s: pd.Series(np.arange(len(df)), index=df.index) for s, df in t.frames.items()}) \
        .reindex(t.index)[t.symbols].where(member)
    vol = (full_ret.rolling(30).std() * math.sqrt(YEAR)).where(member)
    comove = index_ret.rolling(60).var() / full_ret.rolling(60).var().where(member).mean(axis=1)
    month_ret = pd.DataFrame({s: df["close"].pct_change(30) for s, df in t.frames.items()}) \
        .reindex(t.index)[t.symbols].where(member)
    volume = pd.DataFrame({s: df["quote_volume"].rolling(30).sum() for s, df in t.frames.items()}) \
        .reindex(t.index)[t.symbols].where(member)
    top5 = volume.apply(lambda r: r.nlargest(5).sum() / r.sum() if r.sum() > 0 else np.nan, axis=1)
    breadth = pd.DataFrame(t.signal["sma_50"], index=t.index, columns=t.symbols).where(member).mean(axis=1)
    firsts = member[member.index.is_month_start]
    sets = [set(firsts.columns[row.values]) for _, row in firsts.iterrows()]
    churn = pd.Series([1 - len(a & b) / len(a) if a else np.nan for a, b in zip(sets[:-1], sets[1:])],
                      index=firsts.index[1:])
    out = []
    for year in sorted(set(t.index.year)):
        m = t.index.year == year
        out.append({
            "year": int(year),
            "coins_in_universe": round(float(member[m].sum(axis=1).mean()), 1),
            "median_age_days": int(np.nanmedian(age[m].values)),
            "median_coin_vol_pct": round(float(np.nanmedian(vol[m].values)) * 100),
            "co_movement": round(float(comove[m].mean()), 2),
            "dispersion_30d_returns_pct": round(float(month_ret[m].std(axis=1).mean()) * 100, 1),
            "top5_share_of_volume_pct": round(float(top5[m].mean()) * 100),
            "monthly_replacement_pct": round(float(churn[churn.index.year == year].mean()) * 100)
            if (churn.index.year == year).any() else None,
            "share_in_uptrend_pct": round(float(breadth[m].mean()) * 100),
        })
    return out


# ── report ────────────────────────────────────────────────────────────────────

def run(raw: Dict[str, pd.DataFrame], runs: int, top_n: int, cost_bps: float, seed: int = 7) -> Dict:
    t = Tables(raw, top_n, cost_bps)
    everything = np.ones_like(t.ret)
    hold = t.series(everything)
    rule_series = {name: t.series(t.signal[name]) for name in RULES}

    # 3 + 6: labelled table, with volatility, against two benchmarks
    btc_name = next((s for s in ("BTCUSDT", "C1USDT") if s in t.raw), None)
    btc = strategy_returns(t.raw[btc_name], pd.Series(1.0, index=t.raw[btc_name].index), cost_bps)["net"] \
        .reindex(hold.index).dropna() if btc_name else pd.Series(dtype=float)
    btc_raw = t.raw[btc_name]["close"].pct_change().reindex(hold.index).dropna() if btc_name else btc
    table = {"hold universe (raw, not risk-matched)": metrics(hold, YEAR),
             "BTC buy and hold (raw)": metrics(btc_raw, YEAR),
             "BTC volatility-targeted (raw)": metrics(btc, YEAR)}
    comparisons = {}
    for name in JUDGED:
        s = rule_series[name]
        table[f"{name} (the rule)"] = metrics(s, YEAR)
        comparisons[name] = {"vs_hold_universe": same_vol_comparison(s, hold, YEAR),
                             "vs_btc_vol_target": same_vol_comparison(s, btc, YEAR) if len(btc) else {}}

    excess = {}
    for name, s in rule_series.items():
        both = pd.concat([s, hold], axis=1, keys=["s", "h"]).dropna()
        excess[name] = both["s"] - both["h"] * float(both["s"].std(ddof=1) / both["h"].std(ddof=1))

    # relative strength, same sizing and same weekly schedule on both sides
    xs_actual = sharpe_of(t.daily(t.weekly_pick(np.nan_to_num(t.momentum[t.rebalance_rows], nan=-np.inf)), cost=0.0))
    rng = np.random.default_rng(seed + 4)
    xs_random = np.array([sharpe_of(t.daily(t.weekly_pick(rng.random((len(t.rebalance_rows), len(t.symbols)))), cost=0.0))
                          for _ in range(runs)])

    phases = [round(sharpe_of(t.daily(t.weekly_pick(
        np.nan_to_num(t.momentum[np.minimum(t.rebalance_rows + k, len(t.index) - 1)], nan=-np.inf), phase=k),
        cost=0.0)), 2) for k in range(REBALANCE_DAYS)]

    return {
        "universe": {"coins": len(t.symbols), "from": str(t.index[t.lead])[:10], "to": str(t.index[-1])[:10],
                     "btc_series": btc_name},
        "table": table,
        "at_equal_risk": comparisons,
        "placebo": placebo_all_rules(t, runs, seed),
        "deflated_sharpe_raw_returns": deflated_sharpe(rule_series, "sma_50"),
        "deflated_sharpe_excess_over_hold": deflated_sharpe(excess, "sma_50"),
        "relative_strength_ranking": {
            "rule_sharpe_before_costs": round(xs_actual, 2),
            "random_mean": round(float(xs_random.mean()), 2),
            "random_95th": round(float(np.percentile(xs_random, 95)), 2),
            "random_max": round(float(xs_random.max()), 2),
            "p_value": round(float((np.sum(xs_random >= xs_actual) + 1) / (runs + 1)), 4), "runs": runs,
            "rule_sharpe_by_rebalance_weekday": phases,
        },
        "endings_and_halts": endings_and_halts(t),
        "composition_by_year": composition_by_year(t),
    }


def print_report(r: Dict) -> None:
    u = r["universe"]
    print(f"\nMEASUREMENT AUDIT | {u['coins']} coins | {u['from']} to {u['to']}")

    print("\n== 3+6. What each line earned, with its volatility ==")
    print(f"{'':<40}{'ann%':>7}{'vol%':>7}{'sharpe':>8}{'maxDD%':>8}")
    for label, m in r["table"].items():
        if "sharpe" in m:
            print(f"{label:<40}{m['annual_return_pct']:>7}{m['annual_vol_pct']:>7}{m['sharpe']:>8}{m['max_drawdown_pct']:>8}")
    print("\nAt equal risk (benchmark scaled down to the rule's volatility):")
    print(f"{'':<12}{'benchmark':<22}{'bench ann%':>11}{'excess%/yr':>12}{'t':>7}{'bench maxDD%':>14}")
    for name, c in r["at_equal_risk"].items():
        for bench, m in c.items():
            if m:
                print(f"{name:<12}{bench:<22}{m['hold_same_vol_annual_pct']:>11}{m['same_vol_excess_annual_pct']:>12}"
                      f"{m['same_vol_excess_t_stat']:>7}{m['hold_same_vol_max_drawdown_pct']:>14}")

    p = r["placebo"]
    print(f"\n== 1+2. Placebo with {p['_runs']} runs, corrected for having tried eight rules ==")
    print(f"{'rule':<16}{'sharpe':>8}{'placebo mean':>14}{'95th':>7}{'p (own)':>10}{'p (best of 8)':>15}")
    for name in RULES:
        m = p[name]
        mark = "  <- judged" if name in JUDGED else ""
        print(f"{name:<16}{m['actual_sharpe']:>8}{m['placebo_mean']:>14}{m['placebo_95th']:>7}"
              f"{m['p_own_placebo']:>10}{m['p_best_of_eight']:>15}{mark}")
    print(f"95th percentile of the BEST placebo among the eight: {p['_best_of_eight_placebo_95th']}")
    print(f"Bonferroni for the two judged rules: p (own) must be under {0.05 / len(JUDGED)}")
    for label, key in (("raw returns", "deflated_sharpe_raw_returns"), ("excess over holding", "deflated_sharpe_excess_over_hold")):
        d = r[key]
        print(f"Deflated Sharpe, sma_50, {label}: Sharpe {d['sharpe_annual']} vs {d['luck_benchmark_sharpe_annual']} "
              f"expected from the luckiest of {d['trials']} -> probability {d['deflated_sharpe_probability']} "
              f"(without the correction: {d['probability_sharpe_above_zero']})")

    x = r["relative_strength_ranking"]
    print(f"\nRelative strength ranking test, {x['runs']} random portfolios (same sizing, same weekly schedule, "
          f"before costs): rule {x['rule_sharpe_before_costs']} vs random mean {x['random_mean']}, "
          f"95th {x['random_95th']}, best {x['random_max']} -> p = {x['p_value']}")
    print(f"Same rule started on each of the 7 possible weekdays (the first is the one that was tested): "
          f"{x['rule_sharpe_by_rebalance_weekday']}")

    e = r["endings_and_halts"]
    print("\n== 4. Coins that stopped trading, and halts ==")
    print(f"{e['instruments_that_stopped_trading']} stopped trading; {e['of_which_in_universe_on_last_day']} were in the "
          f"universe on their last day; the 50-day rule still held {e['of_those_rule_still_held']} of those; "
          f"{e['of_those_fell_over_30pct_in_last_30d']} had fallen over 30% in their last 30 days "
          f"(median {e['median_drop_last_30d_pct_in_universe']}%).")
    for row in e["in_universe_at_end"][:12]:
        print(f"  {row['symbol']:<14}{row['ended']}  last 30d {row['drop_last_30d_pct']:>7}%  "
              f"rule held: {'yes' if row['rule_held_at_end'] else 'no'}")
    for row in e["resumed_tickers"]:
        print(f"  resumed: {row['symbol']} after {row['resumed_after_days']} days, price change across the halt "
              f"{row['price_change_across_halt_pct']}% (in universe at halt: {'yes' if row['in_universe_at_end'] else 'no'})")
    print(f"Short halts (2-{MAX_GAP_DAYS} days) inside the universe: {e['short_halts_inside_universe']}; worst:",
          "; ".join(f"{h['symbol']} {h['day']} {h['return_across_pct']:+}%" for h in e["worst_short_halts"][:5]))

    print("\n== 5. Did the universe itself change? ==")
    print(f"{'year':<6}{'coins':>6}{'age(d)':>8}{'coinVol%':>9}{'coMove':>8}{'disp30d%':>10}{'top5vol%':>10}"
          f"{'replaced%/mo':>14}{'inUptrend%':>12}")
    for c in r["composition_by_year"]:
        print(f"{c['year']:<6}{c['coins_in_universe']:>6}{c['median_age_days']:>8}{c['median_coin_vol_pct']:>9}"
              f"{c['co_movement']:>8}{c['dispersion_30d_returns_pct']:>10}{c['top5_share_of_volume_pct']:>10}"
              f"{str(c['monthly_replacement_pct']):>14}{c['share_in_uptrend_pct']:>12}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=5000)
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    raw = synthetic_frames() if args.self_test else load_archive(args.cache, args.workers)
    if not raw:
        print("no data loaded", file=sys.stderr)
        return 1
    report = run(raw, args.runs, 9 if args.self_test else args.top_n, args.cost_bps)
    print_report(report)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
