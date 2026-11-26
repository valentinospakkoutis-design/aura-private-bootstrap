"""
variant_harness.py — Αποτύπωση υποθέσεων ΠΡΙΝ από εκτέλεση. Χωρίς post-hoc fitting.

Χρήση:
    # Conformance check (BASE vs γνωστά αποτελέσματα)
    python3 -m backend.scripts.variant_harness --corner conformance --check

    # Όλες οι variants στο worst corner
    python3 -m backend.scripts.variant_harness --all --corner worst

    # Μία variant
    python3 -m backend.scripts.variant_harness --variant V1 --corner worst

Corners:
    conformance : fill=1.0, maker=30bp, taker=30bp, slip=0, churn=0
    worst       : fill=0.40, maker=30bp, taker=30bp
    base        : fill=0.60, maker=10bp, taker=15bp
    best        : fill=0.80, maker=5bp, taker=7.5bp

Promotion criteria (δηλώθηκαν ΠΡΙΝ από εκτέλεση):
    - excess_btc > 0  (beats BTC vol-targeted)
    - t_btc >= 2.0    (στατιστικά σημαντικό)
    - sharpe_h1 > 0 AND sharpe_h2 > 0  (consistency)
    - annual > BASE annual
    - max_dd > BASE max_dd (λιγότερο drawdown)

DSR: Bailey & López de Prado (2014) — sigma από std των trial Sharpes
"""

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.survivorship_backtest import (  # noqa: E402
    masked_portfolio,
    split_on_gaps,
    build_membership,
    synthetic_frames,
)
from scripts.aura_store import load_data, build_btc_benchmark, metrics
from scripts.trend_backtest import strategy_returns, symbol_returns, RULES  # noqa: E402

# ── Declared expectations (ΠΡΙΝ εκτελεστεί) ────────────────────────────────────
# Format: (min_annual, min_sharpe, max_dd_floor, comment)
DECLARED = {
    "BASE": (0.06, 0.65, -0.20, "τιμές ± tolerances από survivorship run 2026-11-24"),
    "V1":   (0.07, 0.70, -0.18, "hysteresis μειώνει false exits, +return +dd protection"),
    "V2":   (0.06, 0.68, -0.17, "min hold 5d μειώνει churn, λίγο καλύτερο sharpe"),
    "V3":   (0.07, 0.72, -0.19, "strength weight: περισσότερο σε coins με ισχυρή τάση"),
    "V4":   (0.07, 0.68, -0.17, "runner: asymmetric upside, ελαφρώς χειρότερο worst-case"),
    "V5":   (0.08, 0.75, -0.17, "combined: best case αν τα components συνεργάζονται"),
}

# ── Conformance tolerances (BASE πρέπει να περάσει πριν τρέξουν variants) ───────
CONFORM_TOL = {
    "annual": (0.069, 0.007),    # target ± tolerance
    "sharpe": (0.75,  0.080),
    "max_dd": (-0.159, 0.020),   # max_dd είναι αρνητικό
    "vol":    (0.093, 0.010),
}


@dataclass
class Costs:
    fill_prob: float = 0.40     # worst
    maker_bp:  float = 30.0
    taker_bp:  float = 30.0
    exit_slip_bp: float = 5.0
    churn_bp:  float = 2.0


@dataclass
class Variant:
    name: str
    hysteresis:     float = 0.0    # exit only when price <= MA * (1 - hysteresis)
    min_hold:       int   = 0      # minimum days to hold after entry
    strength_weight: bool = False  # weight position by (price-MA)/ATR, cap 3×
    runner:         bool  = False  # keep 20% with 2.5×ATR trailing, max 5 days


CORNERS: Dict[str, Costs] = {
    "conformance": Costs(fill_prob=1.0, maker_bp=30, taker_bp=30, exit_slip_bp=0, churn_bp=0),
    "worst":       Costs(fill_prob=0.40, maker_bp=30, taker_bp=30),
    "base":        Costs(fill_prob=0.60, maker_bp=10, taker_bp=15),
    "best":        Costs(fill_prob=0.80, maker_bp=5, taker_bp=7.5),
}

VARIANTS: Dict[str, Variant] = {
    "BASE": Variant("BASE"),
    "V1":   Variant("V1",  hysteresis=0.02),
    "V2":   Variant("V2",  min_hold=5),
    "V3":   Variant("V3",  strength_weight=True),
    "V4":   Variant("V4",  runner=True),
    "V5":   Variant("V5",  hysteresis=0.02, min_hold=5, strength_weight=True, runner=True),
}

PERIODS_PER_YEAR = 365


# ── Signal generation με variant modifiers ──────────────────────────────────────

def sma_signal_base(df: pd.DataFrame) -> pd.Series:
    """Βασικό SMA-50 signal (1=long, 0=flat) από trend_backtest."""
    return RULES["sma_50"](df)


def apply_hysteresis(signal: pd.Series, close: pd.Series, ma: pd.Series,
                     hysteresis: float) -> pd.Series:
    """Exit μόνο όταν close <= MA * (1 - hysteresis)."""
    if hysteresis <= 0:
        return signal
    out = signal.copy()
    # Re-implement: entry when close > MA, exit when close <= MA*(1-h)
    entry_mask = close > ma
    exit_mask  = close <= ma * (1 - hysteresis)
    pos = 0
    vals = []
    for e, x in zip(entry_mask, exit_mask):
        if e and pos == 0:
            pos = 1
        elif x and pos == 1:
            pos = 0
        vals.append(pos)
    return pd.Series(vals, index=signal.index).shift(1).fillna(0)


def apply_min_hold(signal: pd.Series, min_hold: int) -> pd.Series:
    """Κράτα θέση τουλάχιστον min_hold ημέρες μετά την είσοδο."""
    if min_hold <= 0:
        return signal
    out = signal.copy().astype(float)
    hold_count = 0
    for i in range(len(out)):
        if i == 0:
            hold_count = min_hold if out.iloc[i] > 0 else 0
            continue
        prev = out.iloc[i - 1]
        curr = out.iloc[i]
        if prev == 0 and curr > 0:
            hold_count = min_hold
        if hold_count > 0:
            out.iloc[i] = 1.0
            hold_count -= 1
    return out


def apply_strength_weight(signal: pd.Series, close: pd.Series, ma: pd.Series,
                           high: pd.Series, low: pd.Series) -> pd.Series:
    """Weight position by (close-MA)/ATR, cap at 3×."""
    atr = (high - low).rolling(14).mean().replace(0, np.nan)
    strength = ((close - ma) / atr).clip(0, 3)
    # Normalize: average strength → 1× position
    avg_s = strength[signal > 0].mean()
    avg_s = avg_s if pd.notna(avg_s) and avg_s > 0 else 1.0
    weight = (strength / avg_s).clip(0.1, 3.0)
    return (signal * weight).clip(0, 3)


def compute_signal(df: pd.DataFrame, variant: Variant) -> pd.Series:
    """Υπολογίζει το signal για μια variant."""
    close = df["close"]
    ma = close.rolling(50, min_periods=50).mean()

    # Base signal
    sig = sma_signal_base(df)

    # Hysteresis
    if variant.hysteresis > 0:
        sig = apply_hysteresis(sig, close, ma, variant.hysteresis)

    # Min hold
    if variant.min_hold > 0:
        sig = apply_min_hold(sig, variant.min_hold)

    # Strength weighting
    if variant.strength_weight:
        sig = apply_strength_weight(sig, close, ma, df["high"], df["low"])

    # Runner: add 20% extra position held with 2.5×ATR trailing, max 5 days
    # Simplified: runner adds 0.20 to signal when in trend, max 5 consecutive days
    if variant.runner:
        atr = (df["high"] - df["low"]).rolling(14).mean()
        trailing_stop = close - 2.5 * atr
        runner_on = pd.Series(0.0, index=sig.index)
        days_in = 0
        for i in range(1, len(sig)):
            if sig.iloc[i] > 0 and days_in < 5:
                # Still above trailing stop?
                if close.iloc[i] > trailing_stop.iloc[i]:
                    runner_on.iloc[i] = 0.20
                    days_in += 1
                else:
                    days_in = 0
            else:
                days_in = 0
        sig = sig + runner_on

    return sig


# ── DSR (Deflated Sharpe Ratio) ──────────────────────────────────────────────────

def dsr(r: pd.Series, trial_srs: list) -> float:
    """
    Bailey & López de Prado (2014) — Deflated Sharpe Ratio.

    Παράμετροι:
        r          : ημερήσια net returns της στρατηγικής
        trial_srs  : list[float] — Sharpe ratios ΟΛΩΝ των variants που δοκιμάστηκαν
                     (ίδια κλίμακα με r.mean()/r.std(), δηλ. ημερήσιο SR)
                     Χρειάζεται ≥2 τιμές για υπολογισμό sigma.

    Επιστρέφει:
        DSR ∈ [0,1]. DSR > 0.95 → αξιόπιστο (στατιστικά σημαντικό μετά correction)
    """
    from statistics import NormalDist
    import math

    if len(r) < 30:
        return 0.0

    # Sharpe σε ημερήσια κλίμακα (ίδια κλίμακα με trial_srs)
    sr = float(r.mean() / r.std()) if r.std() > 0 else 0.0

    # Sigma: τυπική απόκλιση των trial Sharpes — η κρίσιμη παράμετρος
    # Αν έχουμε μόνο 1 trial, χρησιμοποιούμε θεωρητικό SE
    if len(trial_srs) >= 2:
        sigma = float(np.std(trial_srs, ddof=1))
    else:
        sigma = abs(sr) * 0.1 if sr != 0 else 0.1  # fallback

    if sigma <= 0:
        sigma = 1e-6

    n = max(len(trial_srs), 2)
    t = len(r)  # αριθμός παρατηρήσεων

    # SR* = αναμενόμενο μέγιστο SR από n trials
    # (Bailey & LP eq. 10)
    e = 0.5772156649  # Euler-Mascheroni constant
    nd = NormalDist()
    sr0 = sigma * (
        (1 - e) * nd.inv_cdf(1 - 1 / n)
        + e * nd.inv_cdf(1 - 1 / (n * math.e))
    )

    # Skewness και excess kurtosis για correction
    if t >= 4:
        g3 = float(r.skew())
        g4 = float(r.kurt() + 3.0)  # excess kurtosis → kurtosis
    else:
        g3, g4 = 0.0, 3.0

    denom = np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))

    z = (sr - sr0) * np.sqrt(t - 1) / denom
    return float(nd.cdf(z))


# ── Backtest engine ──────────────────────────────────────────────────────────────

def run_variant(
    frames: Dict[str, pd.DataFrame],
    member: pd.DataFrame,
    variant: Variant,
    costs: Costs,
) -> pd.Series:
    """
    Τρέχει τη variant σε όλα τα coins του universe.
    Επιστρέφει ημερήσια net portfolio returns (equal-weight, masked).
    """
    cost_bp = costs.taker_bp  # simplified: χρησιμοποιούμε taker για όλες τις συναλλαγές

    nets = {}
    for sym, df in frames.items():
        try:
            sig = compute_signal(df, variant)
            ret = strategy_returns(df, sig, cost_bp)
            nets[sym] = ret["net"]
        except Exception as e:
            print(f"  WARN: {sym} error: {e}", file=sys.stderr)
            continue

    if not nets:
        return pd.Series(dtype=float)

    return masked_portfolio(nets, member)


# ── Conformance check ────────────────────────────────────────────────────────────

def conformance_check(
    frames: Dict[str, pd.DataFrame],
    member: pd.DataFrame,
    costs: Costs,
) -> bool:
    """
    BASE πρέπει να αναπαράγει τα γνωστά αποτελέσματα (survivorship run 2026-11-24)
    εντός tolerances. Αν αποτύχει, καμία variant δεν τρέχει.
    """
    print("\n── Conformance check (BASE @ conformance corner) ──")
    print(f"Tolerances: {CONFORM_TOL}")

    base_returns = run_variant(frames, member, VARIANTS["BASE"], costs)
    if len(base_returns) < 100:
        print("FAIL — ανεπαρκή δεδομένα")
        return False

    m = metrics(base_returns)
    print(f"\nΑποτελέσματα BASE:")
    for k, v in m.items():
        print(f"  {k}: {v}")

    ok = True
    for key, (target, tol) in CONFORM_TOL.items():
        val = m.get(key, float("nan"))
        passed = abs(val - target) <= tol
        status = "✓" if passed else "✗ FAIL"
        print(f"  {status}  {key}: {val:.4f}  (target {target} ± {tol})")
        if not passed:
            ok = False

    if ok:
        print("\n✓ CONFORMANCE PASS — τα variants θα τρέξουν")
    else:
        print("\n✗ CONFORMANCE FAIL — διερεύνησε πριν προχωρήσεις")
    return ok


# ── Excess return t-stat ─────────────────────────────────────────────────────────

def t_stat_excess(strategy: pd.Series, benchmark: pd.Series) -> float:
    """t-statistic του excess return στρατηγικής - benchmark."""
    excess = strategy.reindex(benchmark.index).fillna(0) - benchmark.fillna(0)
    n = len(excess.dropna())
    if n < 30:
        return 0.0
    mean = excess.mean()
    se = excess.std() / np.sqrt(n)
    return float(mean / se) if se > 0 else 0.0


# ── Promotion decision ───────────────────────────────────────────────────────────

def evaluate_variants(
    frames: Dict[str, pd.DataFrame],
    member: pd.DataFrame,
    costs: Costs,
    variants_to_run: List[str],
) -> pd.DataFrame:
    """
    Τρέχει τις δηλωμένες variants και επιστρέφει DataFrame αποτελεσμάτων.
    Δεν αλλάζει κριτήρια ΜΕΤΑ από εκτέλεση.
    """
    # BTC benchmark
    print("\nΥπολογισμός BTC benchmark...", file=sys.stderr)
    btc = build_btc_benchmark(frames, member, costs)
    btc_m = metrics(btc)
    print(f"BTC benchmark: annual={btc_m['annual']:.3f}, sharpe={btc_m['sharpe']:.3f}", file=sys.stderr)

    # BASE πρώτα (χρειάζεται για σύγκριση)
    print("Τρέχω BASE...", file=sys.stderr)
    base_ret = run_variant(frames, member, VARIANTS["BASE"], costs)
    base_m = metrics(base_ret)

    # Πρώτο πέρασμα: τρέχουμε ΟΛΕΣ τις variants για να μαζέψουμε τα Sharpe
    # (χρειάζονται για το DSR — sigma = std των trial SR)
    # BASE αποκλείεται από variants_to_run αν υπάρχει ήδη
    non_base = [v for v in variants_to_run if v != "BASE"]
    all_returns = {"BASE": base_ret}
    all_metrics = {"BASE": base_m}

    for vname in non_base:
        v = VARIANTS[vname]
        print(f"Τρέχω {vname}...", file=sys.stderr)
        ret = run_variant(frames, member, v, costs)
        all_returns[vname] = ret
        all_metrics[vname] = metrics(ret)

    # Trial Sharpes σε ημερήσια κλίμακα (για DSR)
    # Χρησιμοποιούμε ΜΟΝΟ τις non-BASE variants (αυτές που "δοκιμάζουμε")
    trial_daily_srs = []
    for vname in non_base:
        r = all_returns[vname]
        if r.std() > 0:
            trial_daily_srs.append(float(r.mean() / r.std()))
    # Αν δεν έχουμε αρκετά (πρώτη εκτέλεση), χρησιμοποιούμε θεωρητικό fallback
    if len(trial_daily_srs) < 2:
        trial_daily_srs = trial_daily_srs + [0.0] * (2 - len(trial_daily_srs))

    rows = []

    # Εμφάνιση BASE πρώτα (αλλά μόνο μία φορά)
    ordered = ["BASE"] + non_base

    for vname in ordered:
        m = all_metrics[vname]
        ret = all_returns[vname]

        # Declared expectations
        decl = DECLARED.get(vname, (0, 0, -1, ""))
        decl_min_ann, decl_min_sh, decl_max_dd_floor, decl_comment = decl

        # Excess over BTC
        t_btc = t_stat_excess(ret, btc)
        excess_btc = m["annual"] - btc_m["annual"]

        # DSR — τώρα με σωστή κλίμακα
        dsr_val = dsr(ret, trial_daily_srs)

        # Promotion (κριτήρια ΠΡΙΝ από εκτέλεση)
        promote = (
            excess_btc > 0
            and t_btc >= 2.0
            and m["sharpe_h1"] > 0
            and m["sharpe_h2"] > 0
            and m["annual"] > base_m["annual"]
            and m["max_dd"] > base_m["max_dd"]
        ) if vname != "BASE" else None

        # Declared check
        decl_pass = (
            m["annual"] >= decl_min_ann
            and m["sharpe"] >= decl_min_sh
            and m["max_dd"] >= decl_max_dd_floor
        )

        rows.append({
            "variant":    vname,
            "annual":     m["annual"],
            "vol":        m["vol"],
            "sharpe":     m["sharpe"],
            "max_dd":     m["max_dd"],
            "h1":         m["sharpe_h1"],
            "h2":         m["sharpe_h2"],
            "excess_btc": round(excess_btc, 4),
            "t_btc":      round(t_btc, 2),
            "dsr":        round(dsr_val, 3),
            "promote":    promote,
            "decl_pass":  decl_pass,
            "decl_ann":   decl_min_ann,
            "decl_sh":    decl_min_sh,
            "decl_dd":    decl_max_dd_floor,
            "note":       decl_comment,
        })

    return pd.DataFrame(rows).set_index("variant")


def print_results(df: pd.DataFrame) -> None:
    """Εκτυπώνει αποτελέσματα με promotion verdict."""
    print("\n" + "=" * 100)
    print(f"{'VARIANT':<8} {'ANN%':>7} {'VOL%':>7} {'SHARPE':>8} {'MAXDD%':>8} "
          f"{'H1':>6} {'H2':>6} {'XS_BTC%':>9} {'t_BTC':>7} {'DSR':>6} "
          f"{'PROMOTE':>8} {'DECL':>6}")
    print("-" * 100)

    for vname, row in df.iterrows():
        promote = ("YES" if row["promote"] else "no") if row["promote"] is not None else "BASE"
        decl = "✓" if row["decl_pass"] else "✗"
        print(
            f"{vname:<8} "
            f"{row['annual']*100:>7.2f} "
            f"{row['vol']*100:>7.2f} "
            f"{row['sharpe']:>8.3f} "
            f"{row['max_dd']*100:>8.2f} "
            f"{row['h1']:>6.3f} "
            f"{row['h2']:>6.3f} "
            f"{row['excess_btc']*100:>9.2f} "
            f"{row['t_btc']:>7.2f} "
            f"{row['dsr']:>6.3f} "
            f"{promote:>8} "
            f"{decl:>6}"
        )
    print("=" * 100)

    promoted = [v for v, r in df.iterrows() if r["promote"] is True]
    if promoted:
        print(f"\n✓ Promoted variants: {', '.join(promoted)}")
    else:
        print("\n✗ Καμία variant δεν πληροί τα κριτήρια promotion")


# ── CLI ──────────────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corner", choices=list(CORNERS), default="worst")
    ap.add_argument("--variant", choices=list(VARIANTS), help="μόνο μία variant")
    ap.add_argument("--all", dest="all_variants", action="store_true")
    ap.add_argument("--check", action="store_true", help="conformance check μόνο")
    ap.add_argument("--self-test", action="store_true", help="synthetic data, χωρίς network")
    ap.add_argument("--cache", default="/tmp/binance_archive")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--store", default=None, help="(αγνοείται — χρησιμοποιείται cache)")
    args = ap.parse_args(argv)

    costs = CORNERS[args.corner]
    print(f"\nCorner: {args.corner} | fill={costs.fill_prob} maker={costs.maker_bp}bp taker={costs.taker_bp}bp")
    print("\n── Δηλωμένες υποθέσεις (ΠΡΙΝ εκτέλεση) ──")
    for vname, (ma, ms, md, comment) in DECLARED.items():
        print(f"  {vname}: annual>={ma*100:.1f}% sharpe>={ms:.2f} max_dd>={md*100:.1f}% | {comment}")

    # Φόρτωση δεδομένων
    if args.self_test:
        print("\nSelf-test mode: synthetic data", file=sys.stderr)
        raw = synthetic_frames()
        frames = split_on_gaps(raw)
        frames = {s: df for s, df in frames.items() if len(df) > 201 + 30}
        member = build_membership(frames)
        used = [s for s in frames if member[s].any()]
        frames = {s: frames[s] for s in used}
        member = member[used]
        member = member.loc[member.any(axis=1)]
    else:
        print(f"\nΦόρτωση δεδομένων από Binance archive (cache: {args.cache})...")
        frames, member = load_data(cache_dir=args.cache, workers=args.workers)

    print(f"Universe: {len(frames)} coins, {len(member)} ημέρες "
          f"({str(member.index[0])[:10]} → {str(member.index[-1])[:10]})")

    # Conformance check
    conform_costs = CORNERS["conformance"]
    if args.check:
        passed = conformance_check(frames, member, conform_costs)
        return 0 if passed else 1

    # Conformance πριν variants
    if not args.self_test:
        passed = conformance_check(frames, member, conform_costs)
        if not passed:
            print("\nABORT — conformance fail. Διόρθωσε πριν τρέξεις variants.", file=sys.stderr)
            return 2

    # Επιλογή variants
    if args.all_variants:
        to_run = list(VARIANTS.keys())
    elif args.variant:
        to_run = ["BASE", args.variant] if args.variant != "BASE" else ["BASE"]
    else:
        to_run = ["BASE"]

    # Εκτέλεση
    results = evaluate_variants(frames, member, costs, to_run)
    print_results(results)

    # Αποθήκευση CSV
    out_path = f"/tmp/aura_harness_{args.corner}.csv"
    results.to_csv(out_path)
    print(f"\nΑποτελέσματα: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
