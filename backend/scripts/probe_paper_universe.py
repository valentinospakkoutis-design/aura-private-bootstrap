"""
PROBE A — Φ3 paper universe (services/auto_trading_engine.py + main.py).

Proves that with paper_mode=True the 8 non-crypto paper-only symbols ENTER the
auto-trade evaluation path (they clear the whitelist gate and are NOT rejected as
"not in allowed" nor "blocked on live path"). They may still SKIP later for a real
reason (market closed / broker not connected / low confidence) — that is expected
and still proves the symbol was evaluated rather than filtered out up front.

Run AFTER deploy (no DB/broker needed — user_id=None short-circuits the circuit
breaker, and we deliberately leave the broker unset so evaluation bails at the
"broker not connected" gate, which sits AFTER the Φ3 whitelist we are testing):

    docker exec aura-backend python3 scripts/probe_paper_universe.py
    #  ...or locally, from backend/:
    python3 scripts/probe_paper_universe.py

Exit code is non-zero if any assertion fails.
"""

import sys

sys.path.insert(0, ".")

from services.auto_trading_engine import (  # noqa: E402
    AutoTradingEngine,
    ALLOWED_AUTO_TRADE_SYMBOLS,
    PAPER_ONLY_SYMBOLS,
)

NON_CRYPTO = ["SI1!", "HG1!", "BAC", "JPM", "ES1!", "YM1!", "DAX1!", "FTSE1!"]

# Reasons that mean the symbol was FILTERED OUT before evaluation (a failure for
# paper mode). Anything else (broker not connected, market closed, confidence, …)
# means it got past the Φ3 whitelist and was genuinely evaluated.
REJECT_MARKERS = ("not in allowed auto-trade symbols", "non-crypto blocked on live path")

failures = []


def run_symbol(engine, symbol):
    """Call place_auto_order once and return the list of SKIP/log reasons emitted."""
    events = []
    engine._log_event = lambda kind, msg, *a, **k: events.append((kind, msg))  # capture
    engine.place_auto_order(
        {"symbol": symbol, "action": "buy", "price": 1.0, "targetPrice": 1.1, "confidence": 0.10},
        user_id=None,  # None → skips the DB-backed circuit-breaker pre-check
    )
    return [m for (_, m) in events]


def check(label, cond):
    ok = bool(cond)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


print("== Universe composition ==")
paper_universe = set(ALLOWED_AUTO_TRADE_SYMBOLS) | set(PAPER_ONLY_SYMBOLS)
print(f"  live universe (crypto)     : {len(ALLOWED_AUTO_TRADE_SYMBOLS)} symbols")
print(f"  paper-only (non-crypto)    : {len(PAPER_ONLY_SYMBOLS)} symbols -> {sorted(PAPER_ONLY_SYMBOLS)}")
print(f"  paper universe (union)     : {len(paper_universe)} symbols")
check("paper universe = 27 crypto + 8 non-crypto = 35", len(paper_universe) == len(ALLOWED_AUTO_TRADE_SYMBOLS) + 8)
check("no overlap between crypto and paper-only", not (set(ALLOWED_AUTO_TRADE_SYMBOLS) & set(PAPER_ONLY_SYMBOLS)))

print("\n== place_auto_order with paper_mode=True — each non-crypto is EVALUATED ==")
engine = AutoTradingEngine()
engine.config = dict(engine.config)
engine.config["enabled"] = True
engine.config["paper_mode"] = True
# broker left unset → evaluation reaches the "broker not connected" gate, which is
# AFTER the whitelist — proving the symbol was admitted.

for s in NON_CRYPTO:
    reasons = run_symbol(engine, s)
    rejected = any(any(mk in r for mk in REJECT_MARKERS) for r in reasons)
    tail = reasons[-1] if reasons else "(no skip — proceeded)"
    print(f"  {s:6} evaluated={not rejected}  last_reason={tail!r}")
    check(f"{s}: admitted past whitelist (not filtered out)", not rejected)

print("\n== crypto path unchanged (sanity) ==")
reasons = run_symbol(engine, "BTCUSDC")
rejected = any(any(mk in r for mk in REJECT_MARKERS) for r in reasons)
check("BTCUSDC still admitted in paper mode", not rejected)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} assertion(s)): {failures}")
    sys.exit(1)
print("RESULT: PASS — paper_mode admits all 8 non-crypto into the auto-trade loop")
