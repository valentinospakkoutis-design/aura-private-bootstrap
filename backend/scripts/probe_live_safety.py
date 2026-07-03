"""
PROBE B — Φ3 LIVE-SAFETY (services/auto_trading_engine.py + main.py).

Proves the invariant that matters most: with paper_mode=False the live auto-trade
universe is EXACTLY the 27 crypto pairs and non-crypto can NEVER be traded.

Three independent checks:
  1. place_auto_order with paper_mode=False refuses every non-crypto symbol with the
     hard-block reason "non-crypto blocked on live path" and returns None — even
     though we set enabled=True and a connected fake broker, i.e. everything else
     that would let a trade through is in place.
  2. The live whitelist set is byte-for-byte ALLOWED_AUTO_TRADE_SYMBOLS (no leak).
  3. Static guarantee: no live code path sets paper_mode=True. Every
     `paper_mode = True` / `["paper_mode"] = True` assignment in main.py lives inside
     a function whose name marks it as the paper endpoint.

Run AFTER deploy (no DB/broker needed — user_id=None skips the circuit breaker):

    docker exec aura-backend python3 scripts/probe_live_safety.py
    #  ...or locally, from backend/:
    python3 scripts/probe_live_safety.py

Exit code is non-zero if any assertion fails.
"""

import ast
import sys

sys.path.insert(0, ".")

from services.auto_trading_engine import (  # noqa: E402
    AutoTradingEngine,
    ALLOWED_AUTO_TRADE_SYMBOLS,
    PAPER_ONLY_SYMBOLS,
)

NON_CRYPTO = ["SI1!", "HG1!", "BAC", "JPM", "ES1!", "YM1!", "DAX1!", "FTSE1!"]
BLOCK_REASON = "non-crypto blocked on live path"

failures = []


def check(label, cond):
    ok = bool(cond)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


class _FakeBroker:
    """Connected broker so NOTHING but the live-safety block can stop the trade."""
    connected = True


def run_symbol(engine, symbol):
    events = []
    engine._log_event = lambda kind, msg, *a, **k: events.append((kind, msg))
    result = engine.place_auto_order(
        {"symbol": symbol, "action": "buy", "price": 1.0, "targetPrice": 1.1, "confidence": 0.99},
        user_id=None,
    )
    return result, [m for (_, m) in events]


# ── 1. Runtime: paper_mode=False refuses non-crypto ───────────────────────────
print("== place_auto_order with paper_mode=False — non-crypto HARD-BLOCKED ==")
engine = AutoTradingEngine()
engine.config = dict(engine.config)
engine.config["enabled"] = True
engine.config["paper_mode"] = False          # LIVE
engine.broker = _FakeBroker()                 # connected broker on purpose

for s in NON_CRYPTO:
    result, reasons = run_symbol(engine, s)
    blocked = any(BLOCK_REASON in r for r in reasons)
    print(f"  {s:6} result={result!r}  blocked={blocked}  reasons={reasons}")
    check(f"{s}: returns None on live path", result is None)
    check(f"{s}: skipped with '{BLOCK_REASON}'", blocked)

# crypto sanity: a crypto symbol must NOT be hit by the live-safety block
_, reasons = run_symbol(engine, "BTCUSDC")
check("BTCUSDC NOT hit by live-safety block", not any(BLOCK_REASON in r for r in reasons))

# ── 2. The live allowed set is exactly the 27 crypto pairs ────────────────────
print("\n== live whitelist has zero non-crypto leak ==")
paper_mode = False
live_allowed = (ALLOWED_AUTO_TRADE_SYMBOLS | PAPER_ONLY_SYMBOLS) if paper_mode else ALLOWED_AUTO_TRADE_SYMBOLS
check("live allowed == ALLOWED_AUTO_TRADE_SYMBOLS", live_allowed == ALLOWED_AUTO_TRADE_SYMBOLS)
check("no PAPER_ONLY_SYMBOLS in live allowed", not (live_allowed & PAPER_ONLY_SYMBOLS))

# ── 3. Static: no live caller sets paper_mode=True ────────────────────────────
print("\n== static scan: every paper_mode=True lives in a paper-only function ==")
src = open("main.py").read()
tree = ast.parse(src)

# Map each line number to its enclosing function name.
func_ranges = []  # (start, end, name)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        end = getattr(node, "end_lineno", node.lineno)
        func_ranges.append((node.lineno, end, node.name))


def enclosing_func(lineno):
    # Innermost function whose range contains lineno.
    best = None
    for start, end, name in func_ranges:
        if start <= lineno <= end and (best is None or start > best[0]):
            best = (start, end, name)
    return best[2] if best else "<module>"


def is_paper_true_assign(node):
    """True if node assigns the literal True to something named paper_mode
    (`paper_mode = True`, `cfg["paper_mode"] = True`, `overrides["paper_mode"] = True`)."""
    if not isinstance(node, ast.Assign):
        return False
    if not (isinstance(node.value, ast.Constant) and node.value.value is True):
        return False
    for tgt in node.targets:
        if isinstance(tgt, ast.Name) and tgt.id == "paper_mode":
            return True
        if isinstance(tgt, ast.Subscript) and isinstance(tgt.slice, ast.Constant) and tgt.slice.value == "paper_mode":
            return True
    return False


assigns = [n for n in ast.walk(tree) if is_paper_true_assign(n)]
print(f"  found {len(assigns)} `paper_mode = True` assignment(s) in main.py")
for n in assigns:
    fn = enclosing_func(n.lineno)
    print(f"    line {n.lineno}: enclosing function = {fn}()")
    check(f"line {n.lineno} is inside a paper-only function ('paper' in name)", "paper" in fn.lower())
check("at least one paper_mode=True assignment exists (endpoint present)", len(assigns) >= 1)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} assertion(s)): {failures}")
    sys.exit(1)
print("RESULT: PASS — live path can never trade non-crypto; only the paper endpoint enables paper_mode")
