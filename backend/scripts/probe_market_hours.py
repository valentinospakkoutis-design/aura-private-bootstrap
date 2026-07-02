"""
Verification probe for the Phase-2 market-hours gate (services/market_hours.py).

Run AFTER deploy (no DB / broker needed — pure calendar logic):

    docker exec aura-backend python3 scripts/probe_market_hours.py
    #  ...or locally, from backend/:
    python3 scripts/probe_market_hours.py

Section A prints is_tradeable_now for a representative basket at the *current*
time (informational — depends on when you run it). Sections B and C use a mocked
`now` so the weekend / US-session / July-4-holiday behaviour is deterministic and
asserted. Exit code is non-zero if any assertion fails.
"""

import sys
from datetime import datetime, timezone

# Allow running from backend/ directly.
sys.path.insert(0, ".")

from services.market_hours import is_tradeable_now  # noqa: E402

NON_CRYPTO = ["BAC", "JPM", "ES1!", "YM1!", "SI1!", "HG1!", "FTSE1!", "DAX1!"]
US_CASH = ["BAC", "JPM"]          # NYSE-priced → fully closed on US holidays
CME_FUTURES = ["ES1!", "YM1!", "SI1!", "HG1!"]  # near-24h Globex, shortened on holidays

failures = []


def check(label, got, expected):
    ok = got == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:46} got={got!s:5} expected={expected!s}")
    if not ok:
        failures.append(label)


# ── A. Live snapshot (informational) ─────────────────────────────────────────
print("== A. is_tradeable_now @ now (informational) ==")
print(f"  now(UTC) = {datetime.now(timezone.utc).isoformat()}")
for s in ["BTCUSDC", "BAC", "JPM", "ES1!", "SI1!", "FTSE1!", "DAX1!"]:
    print(f"  {s:9} -> {is_tradeable_now(s)}")

# ── B. Mocked 'now': weekend vs US session (deterministic asserts) ────────────
print("\n== B. Weekend vs US session (mocked now) ==")

# Saturday 2026-07-04 15:00 UTC — every non-crypto venue is shut for the weekend.
sat = datetime(2026, 7, 4, 15, 0, tzinfo=timezone.utc)
check("BTCUSDC weekend (crypto always on)", is_tradeable_now("BTCUSDC", now=sat), True)
for s in NON_CRYPTO:
    check(f"{s} Sat 2026-07-04 15:00Z closed", is_tradeable_now(s, now=sat), False)

# Tuesday 2026-06-30 15:00 UTC (11:00 ET) — regular US cash session.
us_open = datetime(2026, 6, 30, 15, 0, tzinfo=timezone.utc)
check("BAC US session open", is_tradeable_now("BAC", now=us_open), True)
check("JPM US session open", is_tradeable_now("JPM", now=us_open), True)
check("BTCUSDC US session (crypto)", is_tradeable_now("BTCUSDC", now=us_open), True)

# NYSE after-hours: Tuesday 22:30 UTC (18:30 ET) — cash market shut.
after = datetime(2026, 6, 30, 22, 30, tzinfo=timezone.utc)
check("BAC after-hours closed", is_tradeable_now("BAC", now=after), False)

# ── C. BONUS: July 4th (observed Fri 2026-07-03) holiday logic ────────────────
print("\n== C. July 4th holiday (observed Fri 2026-07-03 15:00Z) ==")
# July 4 2026 falls on a Saturday → NYSE observes it on Friday July 3.
jul4_obs = datetime(2026, 7, 3, 15, 0, tzinfo=timezone.utc)
for s in US_CASH:
    check(f"{s} NYSE closed on Jul-4 observed", is_tradeable_now(s, now=jul4_obs), False)

# Real-world nuance (informational, not asserted): CME futures run a *shortened*
# session on the US cash holiday, so they stay tradeable while stocks are shut.
print("  -- CME futures nuance on Jul-3 (shortened session, expected open) --")
for s in CME_FUTURES:
    print(f"     {s:6} -> {is_tradeable_now(s, now=jul4_obs)}  (informational)")

# ── Result ───────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} assertion(s) failed): {failures}")
    sys.exit(1)
print("RESULT: PASS — all market-hours assertions hold")
