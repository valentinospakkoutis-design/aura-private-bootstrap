"""
cost_report.py — αναφορά μετρημένου κόστους από τα spread snapshots.

Συνδέει:
  1. trend_paper_spreads (DB) — half-spread ανά σύμβολο/στιγμιότυπο
  2. trend_paper_trades (DB) — ποιες συναλλαγές έγιναν και πότε
  3. data/costs/book.jsonl (προαιρετικό) — depth-5 data αν υπάρχει

Βγάζει:
  - πραγματοποιημένο half-spread (εκτιμώμενο): p50 / p90 ανά sleeve
  - σύγκριση με υπόθεση 20bps του ledger
  - ανά σύμβολο breakdown
  - αναμενόμενο ετήσιο κόστος σε μονάδες/έτος

Χρειάζονται ≥100 συναλλαγές για αξιόπιστη ερμηνεία.

Χρήση:
    python -m scripts.cost_report
    python -m scripts.cost_report --out /tmp/cost_report.md
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

LEDGER_COST_BPS = 20.0   # αυτό χρεώνει το κύριο ledger ανά πλευρά
THRESHOLD_BPS = 13.0     # αν p90 < αυτό → το +1.1% vs BTC ήταν κόστος, όχι σήμα
MIN_TRADES_FOR_INTERPRETATION = 100

# ── Data loading ─────────────────────────────────────────────────────────────────

def _load_spreads_from_db() -> pd.DataFrame:
    """Φορτώνει trend_paper_spreads από τη βάση."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        if SessionLocal is None:
            return pd.DataFrame()
        with SessionLocal() as db:
            rows = db.execute(text(
                "SELECT recorded_at, symbol, bid, ask, half_spread_bps, after_close "
                "FROM trend_paper_spreads ORDER BY recorded_at"
            )).all()
        df = pd.DataFrame(rows, columns=["recorded_at", "symbol", "bid", "ask",
                                         "half_spread_bps", "after_close"])
        df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)
        return df
    except Exception as exc:
        print(f"  WARN: DB spreads load failed: {exc}", file=sys.stderr)
        return pd.DataFrame()


def _load_trades_from_db() -> pd.DataFrame:
    """Φορτώνει trend_paper_trades για correlation με spreads."""
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        if SessionLocal is None:
            return pd.DataFrame()
        with SessionLocal() as db:
            rows = db.execute(text(
                "SELECT strategy, as_of, symbol, side, notional, cost "
                "FROM trend_paper_trades ORDER BY as_of"
            )).all()
        df = pd.DataFrame(rows, columns=["strategy", "as_of", "symbol", "side", "notional", "cost"])
        df["as_of"] = pd.to_datetime(df["as_of"], utc=True, errors="coerce")
        return df
    except Exception as exc:
        print(f"  WARN: DB trades load failed: {exc}", file=sys.stderr)
        return pd.DataFrame()


def _load_book_jsonl() -> pd.DataFrame:
    """Φορτώνει depth-5 data αν υπάρχει."""
    try:
        from services.cost_telemetry import load_book_jsonl
        return load_book_jsonl()
    except Exception:
        return pd.DataFrame()


# ── Analysis ─────────────────────────────────────────────────────────────────────

def _sleeve_from_symbol(symbol: str) -> str:
    if symbol.endswith("USDC"):
        return "USDC"
    if symbol.endswith("USDT"):
        return "USDT"
    return "OTHER"


def spread_distribution(spreads: pd.DataFrame) -> pd.DataFrame:
    """
    Κατανομή half-spread ανά sleeve.
    Μόνο after_close=1 snapshots (πιο κοντά στην απόφαση).
    """
    if spreads.empty:
        return pd.DataFrame()

    spreads = spreads.copy()
    spreads["sleeve"] = spreads["symbol"].apply(_sleeve_from_symbol)

    # After-close only (πιο αντιπροσωπευτικό)
    ac = spreads[spreads["after_close"] == 1]
    if ac.empty:
        ac = spreads  # fallback

    rows = []
    for sleeve, g in ac.groupby("sleeve"):
        rows.append({
            "sleeve":    sleeve,
            "n_records": len(g),
            "n_symbols": g["symbol"].nunique(),
            "n_snapshots": g["recorded_at"].nunique(),
            "p50_bps":   round(float(g["half_spread_bps"].median()), 2),
            "p90_bps":   round(float(g["half_spread_bps"].quantile(0.90)), 2),
            "p99_bps":   round(float(g["half_spread_bps"].quantile(0.99)), 2),
            "mean_bps":  round(float(g["half_spread_bps"].mean()), 2),
            "btc_bps":   round(float(g[g["symbol"].isin(["BTCUSDT", "BTCUSDC"])]["half_spread_bps"].median()), 2)
                         if any(g["symbol"].isin(["BTCUSDT", "BTCUSDC"])) else None,
            "worst_symbol": g.groupby("symbol")["half_spread_bps"].median().idxmax()
                             if not g.empty else None,
            "worst_bps": round(float(g.groupby("symbol")["half_spread_bps"].median().max()), 2)
                         if not g.empty else None,
        })
    return pd.DataFrame(rows).set_index("sleeve")


def per_symbol_spread(spreads: pd.DataFrame, sleeve: str = "USDC") -> pd.DataFrame:
    """Median half-spread ανά σύμβολο για το δεδομένο sleeve."""
    if spreads.empty:
        return pd.DataFrame()
    spreads = spreads.copy()
    spreads["sleeve"] = spreads["symbol"].apply(_sleeve_from_symbol)
    sub = spreads[(spreads["sleeve"] == sleeve) & (spreads["after_close"] == 1)]
    if sub.empty:
        sub = spreads[spreads["sleeve"] == sleeve]
    return (
        sub.groupby("symbol")["half_spread_bps"]
        .agg(["median", "count"])
        .rename(columns={"median": "half_spread_bps", "count": "n"})
        .sort_values("half_spread_bps", ascending=False)
        .round(2)
    )


PAPER_CAPITAL = 10_000.0      # εικονικό κεφάλαιο ανά στρατηγική στο λογιστικό
MIN_DAYS_FOR_TURNOVER = 30    # κάτω από αυτό ο τζίρος κυριαρχείται από την αρχική είσοδο
FALLBACK_TURNOVER = 7.7       # πλευρές/έτος σε πλήρες κεφάλαιο, από btc_trend_test
TURNOVER_STRATEGY = "sma_50"  # η στρατηγική που κρίνεται τον Ιανουάριο


def turnover_per_year(trades: pd.DataFrame, strategy: str = TURNOVER_STRATEGY) -> Dict:
    """
    Ετήσιος τζίρος ως πολλαπλάσιο του κεφαλαίου, για μία στρατηγική.

    Κάθε γραμμή του trend_paper_trades είναι ΜΙΑ πλευρά (αγορά ή πώληση) με δικό της notional.
    τζίρος = Σ notional / κεφάλαιο, ανά έτος. Το κόστος σε % = τζίρος × κόστος ανά πλευρά.

    Το παλιό υπολόγιζε len(trades)×2 από ΟΛΕΣ τις στρατηγικές και κάθε πλευρά ως πλήρες
    κεφάλαιο, σε 3 μέρες ιστορικού → ~27.000 «πλευρές»/έτος → 3.222%/έτος. Λάθος.
    """
    fallback = {"turnover": FALLBACK_TURNOVER, "source": "fallback btc_trend_test", "days": 0}
    if trades.empty or "strategy" not in trades:
        return fallback
    t = trades[trades["strategy"] == strategy].dropna(subset=["as_of"])
    if t.empty:
        return fallback
    days = (t["as_of"].max() - t["as_of"].min()).days
    if days < MIN_DAYS_FOR_TURNOVER:
        fallback["source"] = f"fallback (μόνο {days} ημέρες {strategy}, χρειάζονται ≥{MIN_DAYS_FOR_TURNOVER})"
        fallback["days"] = days
        return fallback
    notional = pd.to_numeric(t["notional"], errors="coerce").abs().sum()
    return {"turnover": notional / PAPER_CAPITAL / days * 365,
            "source": f"μετρημένο {strategy}, {days} ημέρες", "days": days}


def annual_cost_estimate(dist: pd.DataFrame, trades: pd.DataFrame) -> Dict:
    """
    Εκτιμά ετήσιο κόστος σε % του κεφαλαίου: τζίρος/έτος × (half-spread + fee) ανά πλευρά.
    """
    to = turnover_per_year(trades)
    trades_per_year = to["turnover"]

    result = {}
    for sleeve in dist.index:
        p50 = dist.loc[sleeve, "p50_bps"]
        p90 = dist.loc[sleeve, "p90_bps"]
        # + fee assumption: exchange fee η επόμενη μεγάλη άγνωστη
        # Με BNB discount: ~7.5bp maker, ~10bp taker
        fee_estimate_bps = fee_for(sleeve)
        total_p50 = p50 + fee_estimate_bps
        total_p90 = p90 + fee_estimate_bps

        result[sleeve] = {
            "trades_per_year":          round(trades_per_year, 1),
            "turnover_source":          to["source"],
            "half_spread_p50_bps":      p50,
            "half_spread_p90_bps":      p90,
            "fee_estimate_bps":         fee_estimate_bps,
            "total_cost_p50_bps":       round(total_p50, 1),
            "total_cost_p90_bps":       round(total_p90, 1),
            "annual_cost_p50_pct":      round(total_p50 / 10_000 * trades_per_year * 100, 2),
            "annual_cost_p90_pct":      round(total_p90 / 10_000 * trades_per_year * 100, 2),
            "ledger_assumption_bps":    LEDGER_COST_BPS,
            "ledger_annual_pct":        round(LEDGER_COST_BPS / 10_000 * trades_per_year * 100, 2),
            "gap_vs_ledger_bps":        round(LEDGER_COST_BPS - total_p50, 1),
            "gap_annual_pct":           round((LEDGER_COST_BPS - total_p50) / 10_000 * trades_per_year * 100, 2),
        }
    return result


# ΜΕΤΡΗΜΕΝΟ 27/11/2026 (probe_fees.py, /sapi/v1/asset/tradeFee + bnbBurn): Regular, spotBNBBurn=true.
# Effective (×0,75): USDC maker 7,50 / taker 7,125· USDT 7,50 / 7,50. Χρεώνεται taker (εντολές αγοράς).
# Προϋπόθεση της έκπτωσης: υπόλοιπο BNB στο spot wallet.
FEE_BPS = {"USDC": 7.125, "USDT": 7.5}
FEE_ASSUMED_BPS = 7.5  # fallback για άγνωστο sleeve


def fee_for(sleeve: str) -> float:
    return FEE_BPS.get(sleeve, FEE_ASSUMED_BPS)
CONFIRM_P50_TOTAL_BPS = 13.0
REFUTE_P90_TOTAL_BPS = 8.0


def caveats(dist: pd.DataFrame) -> List[str]:
    """Τι από το «ολικό κόστος» είναι μέτρηση και τι υπόθεση. Τυπώνεται ΔΙΠΛΑ σε κάθε νούμερο."""
    out = []
    for sleeve, r in dist.iterrows():
        f = fee_for(sleeve)
        total = r["p50_bps"] + f
        out.append(f"{sleeve}: ολικό p50 {total:.1f} bp = {r['p50_bps']} half-spread + {f} fee — και τα δύο μετρημένα")
    out += [
        "Fee: μετρημένη 27/11 από λογαριασμό (Regular, BNB burn ενεργό)· ισχύει όσο υπάρχει υπόλοιπο BNB. Χωρίς BNB: USDC 9,5, USDT 10.",
        "Spread: ένα στιγμιότυπο αμέσως μετά το κλείσιμο — ευνοϊκή ώρα· σε αναταραχή είναι ευρύτερο.",
        "Τζίρος: δανεισμένος από backtest μέχρι να υπάρξουν ≥30 ημέρες sma_50 στο λογιστικό.",
    ]
    return out


def verdict(dist: pd.DataFrame) -> str:
    """
    Δίπλευρο κριτήριο σε ΟΛΙΚΟ κόστος (half-spread + fee), ανά sleeve:
      ολικό p50 > 13 bp → επιβεβαιώνεται
      ολικό p90 < 8 bp  → διαψεύδεται
      αλλιώς            → ανάμεσα (καμία απόφαση)
    Προσοχή: με fee υποθετικό 8,75 bp το ολικό είναι πάντα ≥ 8,75, άρα το «διαψεύδεται»
    δεν μπορεί να πυροδοτήσει μέχρι να μετρηθεί πραγματική fee κάτω από 8 bp.
    """
    if dist.empty:
        return "PENDING — ανεπαρκή δεδομένα"
    n = int(dist["n_records"].min())
    if n < MIN_TRADES_FOR_INTERPRETATION:
        return f"PENDING — {n}/{MIN_TRADES_FOR_INTERPRETATION} records (χρειάζονται ≥{MIN_TRADES_FOR_INTERPRETATION})"
    lines = []
    for sleeve, r in dist.iterrows():
        p50 = r["p50_bps"] + fee_for(sleeve)
        p90 = r["p90_bps"] + fee_for(sleeve)
        if p50 > CONFIRM_P50_TOTAL_BPS:
            v = "ΕΠΙΒΕΒΑΙΩΝΕΤΑΙ"
        elif p90 < REFUTE_P90_TOTAL_BPS:
            v = "ΔΙΑΨΕΥΔΕΤΑΙ"
        else:
            v = "ΑΝΑΜΕΣΑ — κανένα άκρο δεν πυροδοτεί"
        lines.append(f"{sleeve}: {v} (ολικό p50 {p50:.1f} bp vs >{CONFIRM_P50_TOTAL_BPS}, "
                     f"p90 {p90:.1f} bp vs <{REFUTE_P90_TOTAL_BPS})")
    if min(FEE_BPS.values()) >= REFUTE_P90_TOTAL_BPS:
        lines.append(f"Το «διαψεύδεται» είναι απρόσιτο: η μετρημένη fee ({min(FEE_BPS.values())} bp) ήδη ≥ {REFUTE_P90_TOTAL_BPS} bp.")
    return "\n".join(lines)


# ── Report generation ─────────────────────────────────────────────────────────────

def build_report(spreads: pd.DataFrame, trades: pd.DataFrame,
                 book: pd.DataFrame) -> str:
    """Χτίζει το αρχείο Markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Aura — μετρημένο κόστος ({now})",
        "",
        f"Δημιουργήθηκε από `scripts/cost_report.py`. Χρειάζονται ≥{MIN_TRADES_FOR_INTERPRETATION} "
        f"συναλλαγές για αξιόπιστη ερμηνεία.",
        "",
    ]

    # Spread distribution
    dist = spread_distribution(spreads)
    if dist.empty:
        lines += ["## Spread data", "", "Κανένα δεδομένο ακόμα.", ""]
    else:
        lines += [
            "## Half-spread ανά sleeve (after-close snapshots)",
            "",
            "| Sleeve | Records | Symbols | Snapshots | p50 bps | p90 bps | p99 bps | BTC bps | Worst |",
            "|--------|---------|---------|-----------|---------|---------|---------|---------|-------|",
        ]
        for sleeve, r in dist.iterrows():
            worst = f"{r['worst_symbol']} ({r['worst_bps']})" if r.get("worst_symbol") else "—"
            btc = f"{r['btc_bps']}" if r.get("btc_bps") is not None else "—"
            lines.append(
                f"| {sleeve} | {int(r['n_records'])} | {int(r['n_symbols'])} | "
                f"{int(r['n_snapshots'])} | {r['p50_bps']} | {r['p90_bps']} | "
                f"{r['p99_bps']} | {btc} | {worst} |"
            )
        lines += ["", f"> Ledger assumption: **{LEDGER_COST_BPS:.0f} bps** ανά πλευρά.", ""]

    # Annual cost estimate
    if not dist.empty:
        annual = annual_cost_estimate(dist, trades)
        lines += ["## Εκτιμώμενο ετήσιο κόστος", ""]
        for sleeve, r in annual.items():
            lines += [
                f"### {sleeve}",
                "",
                f"- Τζίρος/έτος (× κεφάλαιο): **{r['trades_per_year']}** ({r['turnover_source']})",
                f"- Half-spread p50: {r['half_spread_p50_bps']} bp  |  p90: {r['half_spread_p90_bps']} bp",
                f"- Exchange fee (μετρημένη, BNB): {r['fee_estimate_bps']} bp",
                f"- Συνολικό p50: **{r['total_cost_p50_bps']} bp**  |  p90: **{r['total_cost_p90_bps']} bp**",
                f"- Ετήσιο κόστος p50: {r['annual_cost_p50_pct']}%  |  p90: {r['annual_cost_p90_pct']}%",
                f"- Ledger υπόθεση: {r['ledger_assumption_bps']} bp × {r['trades_per_year']} = **{r['ledger_annual_pct']}%/έτος**",
                f"- Κενό ledger - πραγματικό (p50): **{r['gap_vs_ledger_bps']} bp ≈ {r['gap_annual_pct']}%/έτος**",
                "",
            ]

        # Verdict
        v = verdict(dist)
        lines += [
            "## Verdict",
            "",
            f"Κριτήριο (ολικό = half-spread + fee): p50 > {CONFIRM_P50_TOTAL_BPS} bp → επιβεβαιώνεται· "
            f"p90 < {REFUTE_P90_TOTAL_BPS} bp → διαψεύδεται· αλλιώς ανάμεσα.",
            "",
            *[f"- **{line}**" for line in v.split("\n")],
            "",
            "### Τι είναι μέτρηση και τι υπόθεση",
            "",
            *[f"- {c}" for c in caveats(dist)],
            "",
        ]

    # Per-symbol breakdown (USDC)
    if not dist.empty and spreads is not None:
        sym_df = per_symbol_spread(spreads, "USDC")
        if not sym_df.empty:
            lines += [
                "## Ανά σύμβολο (USDC, median half-spread)",
                "",
                "| Symbol | half_spread_bps | n |",
                "|--------|-----------------|---|",
            ]
            for sym, row in sym_df.head(30).iterrows():
                lines.append(f"| {sym} | {row['half_spread_bps']} | {int(row['n'])} |")
            lines += [""]

    # Depth-5 summary (book.jsonl)
    if not book.empty and "bid_depth5" in book.columns:
        lines += [
            "## Depth-5 (book.jsonl)",
            "",
            f"Records: {len(book)} | Symbols: {book['symbol'].nunique()}",
            "",
        ]
        if "half_spread_bps" in book.columns:
            for sleeve in ["USDC", "USDT"]:
                g = book[book["symbol"].str.endswith(sleeve[-4:])]
                if g.empty:
                    continue
                avg_depth = g["ask_depth5"].median() * g["mid"].median()
                lines.append(
                    f"- {sleeve}: median ask depth-5 ≈ ${avg_depth:,.0f} | "
                    f"half-spread median {g['half_spread_bps'].median():.2f} bp"
                )
        lines += [""]

    # Notes
    lines += [
        "## Σημειώσεις",
        "",
        "- Η προμήθεια exchange (~7.5–10 bp με BNB) **δεν μετριέται** εδώ — είναι δημόσια.",
        "- Η ολίσθηση μεγάλων εντολών δεν μετριέται ακόμα (χρειάζεται aggTrades matching).",
        "- Τα snapshots γίνονται λίγα λεπτά μετά το κλείσιμο, όχι ακριβώς στην απόφαση.",
        "- Το κύριο ledger μένει στα 20 bp μέχρι 17/1/2027.",
        f"- Δημιουργήθηκε: {datetime.now(timezone.utc).isoformat()}",
    ]

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="", help="Αποθήκευση σε αρχείο Markdown")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).parent.parent))

    print("Φόρτωση spread data από DB...", file=sys.stderr)
    spreads = _load_spreads_from_db()
    print(f"  {len(spreads)} records", file=sys.stderr)

    print("Φόρτωση trades από DB...", file=sys.stderr)
    trades = _load_trades_from_db()
    print(f"  {len(trades)} trades", file=sys.stderr)

    print("Φόρτωση book.jsonl...", file=sys.stderr)
    book = _load_book_jsonl()
    print(f"  {len(book)} records", file=sys.stderr)

    # Σύντομη σύνοψη στο terminal
    dist = spread_distribution(spreads)
    if not dist.empty:
        print("\n── Half-spread ──")
        for sleeve, r in dist.iterrows():
            print(f"  {sleeve}: p50 {r['p50_bps']} bps  p90 {r['p90_bps']} bps  "
                  f"({int(r['n_records'])} records, {int(r['n_symbols'])} symbols)")

        annual = annual_cost_estimate(dist, trades)
        for sleeve, r in annual.items():
            print(f"  {sleeve} ετήσιο κόστος (p50): {r['annual_cost_p50_pct']}%  "
                  f"gap vs ledger: {r['gap_annual_pct']}%  "
                  f"[τζίρος {r['trades_per_year']}×/έτος, {r['turnover_source']}]")

        print("\n── Τι είναι μέτρηση και τι υπόθεση ──")
        for c in caveats(dist):
            print(f"  {c}")
        print(f"\n{verdict(dist)}")
    else:
        print("Κανένα spread data ακόμα.")

    # Αποθήκευση Markdown
    if args.out:
        report = build_report(spreads, trades, book)
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nΑποτέλεσμα: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
