"""
Survivorship check for the crypto trend rules.

scripts.trend_backtest ran on the coins Aura trades today — coins that are
still alive. This script repeats the test on a universe that is chosen without
knowing the future, so coins that later collapsed or were delisted are in it
for as long as they actually traded.

Universe rule (point in time):
  * every USDT spot pair that ever appears in Binance's public archive
    (data.binance.vision keeps delisted pairs), minus stablecoins, fiat,
    wrapped duplicates and leveraged tokens;
  * on the first day of each month, the TOP_N pairs by traded value over the
    previous 30 days, among pairs with at least MIN_HISTORY_DAYS of history;
  * a pair stays in until the month ends or its data ends.

The rules, sizing and cost are imported from the same code the live paper
ledger uses. Nothing here is fitted.

The verdict follows the criteria written down on 23 Nov 2026 before this was
run (project doc aura_trend_paper_criteria.md, section E): judged only on
(a) excess return over holding scaled to the same volatility and
(b) the synchronized time-rotation placebo.

Known simplification: entering or leaving the universe at a month boundary is
not charged as a trade. It applies equally to the rules and to holding.

Read-only: downloads public data into a cache directory, writes nothing else.

    python -m scripts.survivorship_backtest                # full run
    python -m scripts.survivorship_backtest --self-test    # synthetic, no network
"""

import argparse
import io
import json
import math
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.trend_backtest import (  # noqa: E402
    BENCHMARK, RULES, _sharpe, metrics, same_vol_comparison, strategy_returns, symbol_returns,
)
from services.trend_signal import MIN_HISTORY_DAYS  # noqa: E402

LISTING_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FILE_URL = "https://data.binance.vision/"
PREFIX = "data/spot/monthly/klines/"
TOP_N = 30
VOLUME_WINDOW = 30
PERIODS_PER_YEAR = 365
JUDGED_RULES = ("sma_50", "majority")

NOT_AN_ASSET = {
    # stablecoins and fiat
    "USDC", "BUSD", "TUSD", "USDP", "PAX", "DAI", "FDUSD", "USDS", "USDSB", "SUSD", "UST",
    "USTC", "EUR", "GBP", "AUD", "EURI", "AEUR", "USD1", "XUSD", "BFUSD", "USDE", "BKRW",
    "IDRT", "BIDR", "BVND", "NGN", "RUB", "TRY", "UAH", "BRL", "ZAR", "PLN", "RON", "ARS",
    "JPY", "MXN", "COP", "CZK", "VAI",
    # commodity-backed and wrapped duplicates
    "PAXG", "WBTC", "WBETH", "BETH",
}
LEVERAGED = re.compile(r"^.+(UP|DOWN|BULL|BEAR)$")
# Real coins whose ticker merely ends like a leveraged token.
NOT_LEVERAGED = {"JUP", "SUPER", "SYRUP", "PUMP", "GROUP"}


def is_candidate(symbol: str) -> bool:
    if not symbol.endswith("USDT"):
        return False
    base = symbol[:-4]
    if not base or base in NOT_AN_ASSET:
        return False
    if LEVERAGED.match(base) and base not in NOT_LEVERAGED:
        return False
    return True


# ── Archive access ─────────────────────────────────────────────────────────────

def _list(session, prefix: str) -> Tuple[List[str], List[str]]:
    """(sub-prefixes, file keys) directly under `prefix`, following pagination."""
    prefixes: List[str] = []
    keys: List[str] = []
    marker = ""
    while True:
        params = {"delimiter": "/", "prefix": prefix}
        if marker:
            params["marker"] = marker
        r = session.get(LISTING_URL, params=params, timeout=60)
        r.raise_for_status()
        root = ElementTree.fromstring(r.content)
        ns = root.tag[: root.tag.index("}") + 1] if root.tag.startswith("{") else ""
        prefixes += [e.findtext(f"{ns}Prefix") for e in root.findall(f"{ns}CommonPrefixes")]
        keys += [e.findtext(f"{ns}Key") for e in root.findall(f"{ns}Contents")]
        if (root.findtext(f"{ns}IsTruncated") or "").lower() != "true":
            return prefixes, keys
        marker = root.findtext(f"{ns}NextMarker") or (keys[-1] if keys else prefixes[-1])


def parse_kline_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), header=None, usecols=[0, 1, 2, 3, 4, 7])
    df.columns = ["ts", "open", "high", "low", "close", "quote_volume"]
    df = df[pd.to_numeric(df["ts"], errors="coerce").notna()].astype(float)  # drop a header row
    # The archive switched from milliseconds to microseconds in 2025.
    ts = df["ts"].where(df["ts"] < 1e14, df["ts"] / 1000.0)
    df.index = pd.to_datetime(ts, unit="ms").dt.normalize()
    return df.drop(columns="ts")


def load_symbol(session, symbol: str, cache_dir: str) -> Optional[pd.DataFrame]:
    path = os.path.join(cache_dir, f"{symbol}.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    _, keys = _list(session, f"{PREFIX}{symbol}/1d/")
    parts = []
    for key in sorted(k for k in keys if k.endswith(".zip")):
        r = session.get(FILE_URL + key, timeout=60)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            parts.append(parse_kline_csv(z.read(z.namelist()[0])))
    if not parts:
        return None
    df = pd.concat(parts).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df[df["close"] > 0]
    df.to_pickle(path)
    return df


def load_archive(cache_dir: str, workers: int, limit: int = 0) -> Dict[str, pd.DataFrame]:
    import requests

    os.makedirs(cache_dir, exist_ok=True)
    session = requests.Session()
    prefixes, _ = _list(session, PREFIX)
    symbols = sorted(s for s in (p.rstrip("/").split("/")[-1] for p in prefixes) if is_candidate(s))
    if limit:
        symbols = symbols[:limit]
    print(f"archive: {len(prefixes)} spot pairs, {len(symbols)} USDT candidates", file=sys.stderr)

    frames: Dict[str, pd.DataFrame] = {}
    failed: Dict[str, str] = {}

    def fetch(sym: str):
        error = ""
        for attempt in range(4):
            try:
                return sym, load_symbol(session, sym, cache_dir), None
            except Exception as exc:  # one bad pair must not stop the run
                error = f"{type(exc).__name__}: {exc}"
                time.sleep(2 * (attempt + 1))
        return sym, None, error

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (sym, df, err) in enumerate(pool.map(fetch, symbols), 1):
            if err:
                failed[sym] = err
            elif df is not None and len(df) > 0:
                frames[sym] = df
            if i % 50 == 0:
                print(f"  {i}/{len(symbols)} loaded", file=sys.stderr, flush=True)
    if failed:
        print(f"failed to load {len(failed)} pairs: {sorted(failed)}", file=sys.stderr)
    return frames


# ── Data integrity ─────────────────────────────────────────────────────────────

MAX_GAP_DAYS = 7


def split_on_gaps(frames: Dict[str, pd.DataFrame], max_gap_days: int = MAX_GAP_DAYS) -> Dict[str, pd.DataFrame]:
    """Treat a ticker that stopped trading and later came back as a new instrument.

    Binance reuses tickers: LUNAUSDT is the coin that went to zero in May 2022
    and, from two weeks later, a different coin at a different price. Read as
    one series, that is a one-day gain of many thousand percent that nobody
    could have earned. Each stretch of continuous trading becomes its own
    instrument (LUNAUSDT, LUNAUSDT#2) and must build its own history again.
    """
    out: Dict[str, pd.DataFrame] = {}
    for symbol, df in frames.items():
        gaps = df.index.to_series().diff().dt.days.fillna(1) > max_gap_days
        part = gaps.cumsum()
        for n, (_, segment) in enumerate(df.groupby(part.values), 1):
            out[symbol if n == 1 else f"{symbol}#{n}"] = segment
    return out


def largest_moves(frames: Dict[str, pd.DataFrame], member: pd.DataFrame, top: int = 8) -> List[Dict]:
    """Biggest one-day price changes inside the universe — a check for bad data."""
    rows = []
    for symbol, df in frames.items():
        ret = df["close"].pct_change().reindex(member.index).where(member[symbol])
        for day, value in ret.abs().nlargest(3).dropna().items():
            rows.append({"symbol": symbol, "day": str(day)[:10], "return_pct": round(float(ret[day]) * 100, 1)})
    return sorted(rows, key=lambda r: -abs(r["return_pct"]))[:top]


# ── Point-in-time universe ─────────────────────────────────────────────────────

def build_membership(frames: Dict[str, pd.DataFrame], top_n: int = TOP_N) -> pd.DataFrame:
    """Boolean (day x symbol): is the symbol in the universe on that day?

    Decided on the first day of each month from data strictly before that day.
    """
    volume = pd.DataFrame({s: df["quote_volume"] for s, df in frames.items()}).sort_index()
    age = volume.notna().cumsum()
    trailing = volume.rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).sum()
    # Both shifted one day: the choice on day D sees nothing from day D onwards.
    known_volume = trailing.shift(1)
    known_age = age.shift(1)
    still_trading = volume.shift(1).notna()

    member = pd.DataFrame(False, index=volume.index, columns=volume.columns)
    month = volume.index.to_period("M")
    for period in month.unique():
        days = volume.index[month == period]
        first = days[0]
        eligible = (known_age.loc[first] >= MIN_HISTORY_DAYS) & still_trading.loc[first]
        ranked = known_volume.loc[first][eligible].dropna().sort_values(ascending=False)
        member.loc[days, list(ranked.index[:top_n])] = True
    return member


# ── Evaluation ─────────────────────────────────────────────────────────────────

def masked_portfolio(nets: Dict[str, pd.Series], member: pd.DataFrame) -> pd.Series:
    table = pd.DataFrame(nets).reindex(member.index)
    return table.where(member[table.columns]).mean(axis=1, skipna=True).dropna()


def placebo(frames: Dict[str, pd.DataFrame], member: pd.DataFrame, rule_name: str,
            cost_bps: float, runs: int, seed: int = 7) -> Dict:
    """Synchronized time-rotation placebo, same construction as trend_backtest."""
    rule = RULES[rule_name]
    signals = {s: rule(df) for s, df in frames.items()}
    actual = _sharpe(masked_portfolio(
        {s: strategy_returns(frames[s], signals[s], cost_bps)["net"] for s in frames}, member),
        PERIODS_PER_YEAR)
    rng = np.random.default_rng(seed)
    longest = max((int(sig.notna().sum()) for sig in signals.values()), default=0)
    results = []
    for _ in range(runs):
        common = int(rng.integers(250, max(251, longest - 250)))
        nets = {}
        for s, df in frames.items():
            valid = signals[s].dropna()
            if len(valid) < 2:
                continue
            rotated = pd.Series(np.roll(valid.values, common % len(valid)),
                                index=valid.index).reindex(signals[s].index)
            nets[s] = strategy_returns(df, rotated, cost_bps)["net"]
        results.append(_sharpe(masked_portfolio(nets, member), PERIODS_PER_YEAR))
    arr = np.array(results)
    return {
        "actual_sharpe": round(actual, 2),
        "placebo_sharpe_mean": round(float(arr.mean()), 2),
        "placebo_sharpe_95th": round(float(np.percentile(arr, 95)), 2),
        "runs": len(arr),
        "p_value": round(float((np.sum(arr >= actual) + 1) / (len(arr) + 1)), 4),
    }


def verdict(excess_pct: float, p_value: float) -> str:
    """Criteria fixed before the run (aura_trend_paper_criteria.md, section E)."""
    if excess_pct <= 0 or p_value > 0.10:
        return "REJECTED"
    if p_value < 0.05:
        return "HOLDS"
    return "UNCERTAIN"


def evaluate(frames: Dict[str, pd.DataFrame], cost_bps: float, placebo_runs: int,
             top_n: int = TOP_N) -> Dict:
    frames = split_on_gaps(frames)
    frames = {s: df for s, df in frames.items() if len(df) > MIN_HISTORY_DAYS + VOLUME_WINDOW}
    member = build_membership(frames, top_n)
    used = [s for s in frames if member[s].any()]
    frames = {s: frames[s] for s in used}
    member = member[used]
    member = member.loc[member.any(axis=1)]

    per_symbol = {s: symbol_returns(df, cost_bps) for s, df in frames.items()}
    last_day = max(df.index[-1] for df in frames.values())
    dead = sorted(s for s, df in frames.items() if (last_day - df.index[-1]).days > 60)

    bench = masked_portfolio({s: r[BENCHMARK]["net"] for s, r in per_symbol.items()}, member)
    out: Dict = {
        "universe": {
            "symbols_ever_included": len(used),
            "no_longer_trading": len(dead),
            "no_longer_trading_names": dead,
            "from": str(member.index[0])[:10],
            "to": str(member.index[-1])[:10],
            "average_members_per_day": round(float(member.sum(axis=1).mean()), 1),
            "top_n": top_n,
            "reused_tickers": sorted(s for s in used if "#" in s),
            "largest_one_day_moves": largest_moves(frames, member),
        },
        "settings": {"cost_bps": cost_bps, "placebo_runs": placebo_runs},
        "strategies": {BENCHMARK: metrics(bench, PERIODS_PER_YEAR)},
    }
    for name in RULES:
        series = masked_portfolio({s: r[name]["net"] for s, r in per_symbol.items()}, member)
        row = metrics(series, PERIODS_PER_YEAR)
        row.update(same_vol_comparison(series, bench, PERIODS_PER_YEAR))
        if name in JUDGED_RULES and placebo_runs > 0:
            row["placebo"] = placebo(frames, member, name, cost_bps, placebo_runs)
            row["verdict"] = verdict(row.get("same_vol_excess_annual_pct", 0.0),
                                     row["placebo"]["p_value"])
        out["strategies"][name] = row
    return out


def print_report(title: str, report: Dict) -> None:
    u = report["universe"]
    print(f"\n=== {title} ===")
    print(f"{u['from']} to {u['to']} | {u['symbols_ever_included']} coins ever included, "
          f"{u['no_longer_trading']} no longer trading | "
          f"about {u['average_members_per_day']} held in the universe per day")
    if u.get("reused_tickers"):
        print("tickers reused after a trading halt (treated as new coins):", ", ".join(u["reused_tickers"]))
    print("largest one-day moves in the universe:",
          "; ".join(f"{r['symbol']} {r['day']} {r['return_pct']:+}%" for r in u["largest_one_day_moves"]))
    print(f"{'strategy':<16}{'ann%':>7}{'sharpe':>8}{'maxDD%':>8}{'S_1st':>7}{'S_2nd':>7}"
          f"{'xs%@vol':>9}{'t':>6}{'p':>8}  verdict")
    for name, m in report["strategies"].items():
        if "sharpe" not in m:
            print(f"{name:<16} insufficient data")
            continue
        p = m.get("placebo", {}).get("p_value")
        print(f"{name:<16}{m['annual_return_pct']:>7}{m['sharpe']:>8}{m['max_drawdown_pct']:>8}"
              f"{m['sharpe_first_half']:>7}{m['sharpe_second_half']:>7}"
              f"{m.get('same_vol_excess_annual_pct', ''):>9}{m.get('same_vol_excess_t_stat', ''):>6}"
              f"{'' if p is None else p:>8}  {m.get('verdict', '')}")


# ── Self-test data ─────────────────────────────────────────────────────────────

def synthetic_frames(seed: int = 3, days: int = 1500, coins: int = 12) -> Dict[str, pd.DataFrame]:
    """Random walks with no trend information; a third of them collapse and stop."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2020-01-01", periods=days, freq="D")
    frames = {}
    for i in range(coins):
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.04, days)))
        end = days
        if i % 3 == 0:  # dies: falls 95% over its last 40 days, then no more data
            end = int(days * (0.5 + 0.03 * i))
            close[end - 40:end] *= np.linspace(1.0, 0.05, 40)
        frames[f"C{i}USDT"] = pd.DataFrame({
            "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
            "quote_volume": rng.uniform(1e6, 1e7, days) * (1 + i),
        }, index=index).iloc[:end]
    return frames


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cost-bps", type=float, default=30.0)
    ap.add_argument("--placebo", type=int, default=300)
    ap.add_argument("--top-n", type=int, default=TOP_N)
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="only the first N pairs (quick connectivity check)")
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    frames = synthetic_frames() if args.self_test else load_archive(args.cache, args.workers, args.limit)
    if not frames:
        print("no data loaded", file=sys.stderr)
        return 1
    if args.limit:  # connectivity check only: show what arrived and stop
        for sym, df in frames.items():
            print(f"{sym:<16}{str(df.index[0])[:10]} to {str(df.index[-1])[:10]}  {len(df)} days  "
                  f"last close {df['close'].iloc[-1]:.6g}")
        return 0

    frames = split_on_gaps(frames)   # before deciding which coins are still alive
    full = evaluate(frames, args.cost_bps, args.placebo, args.top_n)
    print_report("All coins, including those that later died", full)
    if full["universe"]["no_longer_trading_names"]:
        print("no longer trading:", ", ".join(full["universe"]["no_longer_trading_names"]))

    last_day = max(df.index[-1] for df in frames.values())
    alive = {s: df for s, df in frames.items() if (last_day - df.index[-1]).days <= 60}
    survivors = evaluate(alive, args.cost_bps, 0, args.top_n)
    print_report("Same rule, only coins still trading today (survivorship-biased, for contrast)", survivors)

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"all": full, "survivors_only": survivors}, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
