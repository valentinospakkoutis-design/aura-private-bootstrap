"""
Walk-forward evaluation: does a model have a real, tradeable edge?

Answers one question per symbol with data the model never saw:

    If we had retrained on everything up to a date and traded the next block,
    over and over, would we have beaten a coin flip and paid our costs?

Unlike the single 80/20 split in ml.auto_trainer this
  * predicts a stationary target (next-day return) for every symbol,
  * drops price-level features that let trees memorise the training range,
  * tests several consecutive out-of-sample blocks (expanding window),
  * compares against the base rate (how often the asset simply went up),
  * charges trading costs, and
  * reports how surprising the result would be if the model had no skill.

It is read-only: it trains throwaway models in memory and never touches the
models directory, the database or the trading engine.

Usage (inside the backend container):
    python -m scripts.walk_forward_eval --symbols BTCUSDC,ETHUSDC,SI1!
    python -m scripts.walk_forward_eval --all --out /tmp/walk_forward.json
"""

import argparse
import json
import math
import sys
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

EXCLUDE_COLS = ["target", "label_threshold", "open", "high", "low", "close", "volume",
                "quote_volume", "trades"]

# Model settings to compare. "current" mirrors ml.auto_trainer.train_symbol;
# "regularized" is deliberately small so it cannot memorise a few hundred rows.
MODEL_CONFIGS: Dict[str, Dict] = {
    "current": dict(n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8,
                    colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0),
    "regularized": dict(n_estimators=150, max_depth=3, learning_rate=0.03, subsample=0.7,
                        colsample_bytree=0.7, min_child_weight=5, reg_alpha=0.5, reg_lambda=5.0),
}


def _make_model(config: Dict):
    import xgboost as xgb
    return xgb.XGBRegressor(random_state=42, n_jobs=-1, verbosity=0, **config)


def build_dataset(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Features + next-day-return target, stationary columns only."""
    from ml.auto_trainer import engineer_features, _absolute_magnitude_cols

    feat = engineer_features(df, target_type="return")
    if feat is None or feat.empty:
        return None
    drop = set(EXCLUDE_COLS) | set(_absolute_magnitude_cols(feat.columns))
    cols = [c for c in feat.columns if c not in drop]
    out = feat[cols].copy()
    out["target"] = feat["target"]
    return out.replace([np.inf, -np.inf], np.nan).dropna()


def walk_forward_predict(data: pd.DataFrame, config: Dict, folds: int = 6,
                         min_train_frac: float = 0.5, embargo: int = 1,
                         model_factory: Callable = _make_model) -> pd.DataFrame:
    """Expanding-window out-of-sample predictions.

    The first `min_train_frac` of rows is training only. The remainder is cut
    into `folds` consecutive blocks; each block is predicted by a model fitted
    on every row before it, minus `embargo` rows so no training target overlaps
    the test block. Returns one row per out-of-sample day: pred, actual, fold.
    """
    from sklearn.preprocessing import StandardScaler

    feature_cols = [c for c in data.columns if c != "target"]
    X = data[feature_cols].values
    y = data["target"].values
    n = len(data)
    start = int(n * min_train_frac)
    edges = np.linspace(start, n, folds + 1).astype(int)

    rows = []
    for k in range(folds):
        lo, hi = edges[k], edges[k + 1]
        train_end = lo - embargo
        if hi <= lo or train_end < 50:
            continue
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[:train_end])
        model = model_factory(config)
        model.fit(X_train, y[:train_end])
        pred = model.predict(scaler.transform(X[lo:hi]))
        train_pred = model.predict(X_train)
        train_acc = float(np.mean(np.sign(train_pred) == np.sign(y[:train_end])))
        for i, p in zip(range(lo, hi), pred):
            rows.append({"date": data.index[i], "pred": float(p), "actual": float(y[i]),
                         "fold": k, "train_acc": train_acc})
    return pd.DataFrame(rows)


def score(oos: pd.DataFrame, cost_bps: float = 10.0) -> Dict:
    """Skill and after-cost profitability of out-of-sample predictions.

    Strategy scored: hold the asset on days the model predicts a positive
    return, otherwise stay flat; pay `cost_bps` per side whenever the position
    changes. Long-only, matching what the paper broker can execute.
    """
    if oos is None or len(oos) < 30:
        return {"n": 0 if oos is None else int(len(oos)), "verdict": "insufficient data"}

    pred = oos["pred"].values
    actual = oos["actual"].values
    moved = actual != 0
    n = int(moved.sum())
    hits = int(np.sum(np.sign(pred[moved]) == np.sign(actual[moved])))
    acc = hits / n if n else 0.0
    base_up = float(np.mean(actual[moved] > 0)) if n else 0.5
    baseline = max(base_up, 1.0 - base_up)  # accuracy of always guessing the common side
    # How many standard errors above the base rate. Against the base rate, not 50%,
    # so a model that just says "up" in a rising market earns no credit.
    se = math.sqrt(baseline * (1.0 - baseline) / n) if n else float("inf")
    z_acc = (acc - baseline) / se if se > 0 else 0.0

    position = (pred > 0).astype(float)
    prev = np.concatenate([[0.0], position[:-1]])
    cost = cost_bps / 10000.0
    net = position * actual - np.abs(position - prev) * cost
    mean_net, std_net = float(np.mean(net)), float(np.std(net, ddof=1))
    t_net = mean_net / (std_net / math.sqrt(len(net))) if std_net > 0 else 0.0
    entries = int(np.sum((position - prev) > 0))

    has_edge = z_acc >= 2.0 and t_net >= 2.0 and float(np.sum(net)) > float(np.sum(actual))
    return {
        "n": n,
        "direction_accuracy_pct": round(acc * 100, 1),
        "base_rate_pct": round(baseline * 100, 1),
        "accuracy_z_vs_base_rate": round(z_acc, 2),
        "train_accuracy_pct": round(float(oos["train_acc"].mean()) * 100, 1),
        "entries": entries,
        "days_in_market_pct": round(float(position.mean()) * 100, 1),
        "strategy_net_return_pct": round(float(np.sum(net)) * 100, 1),
        "buy_hold_return_pct": round(float(np.sum(actual)) * 100, 1),
        "net_t_stat": round(t_net, 2),
        "verdict": "EDGE" if has_edge else "no evidence of edge",
    }


def evaluate_symbol(symbol: str, days: int, folds: int, cost_bps: float) -> Dict:
    from ml.auto_trainer import fetch_ohlcv

    df = fetch_ohlcv(symbol, days=days)
    if df is None or len(df) < 300:
        return {"symbol": symbol, "error": f"not enough history ({0 if df is None else len(df)} rows)"}
    data = build_dataset(df)
    if data is None or len(data) < 250:
        return {"symbol": symbol, "error": "not enough feature rows"}
    result = {"symbol": symbol, "rows": int(len(data)),
              "features": int(data.shape[1] - 1), "models": {}}
    for name, config in MODEL_CONFIGS.items():
        result["models"][name] = score(walk_forward_predict(data, config, folds=folds), cost_bps)
    return result


def _print_table(results: List[Dict]) -> None:
    header = f"{'symbol':<11}{'model':<12}{'n':>5}{'acc%':>7}{'base%':>7}{'z':>7}{'train%':>8}{'net%':>8}{'b&h%':>8}{'t':>7}  verdict"
    print(header)
    print("-" * len(header))
    for r in results:
        if r.get("error"):
            print(f"{r['symbol']:<11}{r['error']}")
            continue
        for name, m in r["models"].items():
            if not m.get("n") or "direction_accuracy_pct" not in m:
                print(f"{r['symbol']:<11}{name:<12}{m.get('verdict', '')}")
                continue
            print(f"{r['symbol']:<11}{name:<12}{m['n']:>5}{m['direction_accuracy_pct']:>7}"
                  f"{m['base_rate_pct']:>7}{m['accuracy_z_vs_base_rate']:>7}{m['train_accuracy_pct']:>8}"
                  f"{m['strategy_net_return_pct']:>8}{m['buy_hold_return_pct']:>8}{m['net_t_stat']:>7}  {m['verdict']}")


def _print_summary(results: List[Dict]) -> None:
    for name in MODEL_CONFIGS:
        scored = [r["models"][name] for r in results
                  if not r.get("error") and "direction_accuracy_pct" in r["models"].get(name, {})]
        if not scored:
            continue
        edges = sum(1 for m in scored if m["verdict"] == "EDGE")
        # Each symbol is its own test; at z>=2 and t>=2 roughly 1 in 40 passes by luck alone.
        print(f"[{name}] symbols={len(scored)}  "
              f"mean acc={np.mean([m['direction_accuracy_pct'] for m in scored]):.1f}%  "
              f"mean base rate={np.mean([m['base_rate_pct'] for m in scored]):.1f}%  "
              f"mean train acc={np.mean([m['train_accuracy_pct'] for m in scored]):.1f}%  "
              f"EDGE={edges} (expected by luck alone: ~{len(scored) / 40:.1f})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Walk-forward edge evaluation (read-only).")
    parser.add_argument("--symbols", help="Comma-separated symbols, e.g. BTCUSDC,SI1!")
    parser.add_argument("--all", action="store_true", help="Evaluate every training symbol")
    parser.add_argument("--days", type=int, default=1500, help="History to fetch per symbol")
    parser.add_argument("--folds", type=int, default=6, help="Consecutive out-of-sample blocks")
    parser.add_argument("--cost-bps", type=float, default=10.0, help="Cost per side in basis points")
    parser.add_argument("--out", help="Write full results as JSON to this path")
    args = parser.parse_args(argv)

    if args.all:
        from ml.auto_trainer import TRAINING_SYMBOLS
        symbols = list(TRAINING_SYMBOLS)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        parser.error("pass --symbols or --all")

    results = []
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol} ...", file=sys.stderr, flush=True)
        try:
            results.append(evaluate_symbol(symbol, args.days, args.folds, args.cost_bps))
        except Exception as exc:  # one bad symbol must not stop the run
            results.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})

    _print_table(results)
    print()
    _print_summary(results)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(results, fh, indent=2, default=str)
        print(f"\nfull results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
