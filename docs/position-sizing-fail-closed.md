# Verified automatic position sizing — draft, no deployment

Based on a2d8dd69dc6f076152ad48e3c16edea763a7589d. Branch: fix/verified-position-sizing.

Sizing exceptions, unknown profiles, invalid inputs/outputs, unavailable circuit-breaker prechecks, and failed primary exposure checks reject new orders. No fixed-amount fallback remains. Existing order caps and ALLOW_LIVE_TRADING remain in place.

## Connected paper path

The default engine now uses paper_sizing_snapshot. It reads the actual user profile and cash/holdings from the database, values every holding using a timestamped websocket quote no more than 60 seconds old, and includes pending DCA notional in both symbol and gross portfolio exposure. Reservations reduce available cash without increasing equity. Missing schema, stale prices, persistence failures, and a mismatch between the paper service cache and database all block.

A dedicated server-owned auto_sizing_paper_risk table persists the highest observed marked-to-market equity. It is not stored in editable profile notes. The epoch starts only when the paper service creates a new account or the user explicitly resets the virtual account. Migration 023 creates an empty table and never invents historical peaks for existing accounts. No account has been reset by this work.

The provider records observations every auto-trader scan and before sizing. Drawdown is computed from actual observed equity and this persisted peak. This is a sampled high-water mark, not a reconstruction of intra-scan or offline historical maxima. A restart retains the previously recorded peak. Paper funding changes are currently limited to the explicit virtual-account reset; future deposit/withdrawal features must adjust the risk epoch before being supported.

PaperBroker no longer executes at random/base-price fallbacks. Missing verified quotes reject an order. Paper-only symbols lacking this timestamped feed are consequently unavailable in this draft. The per-user portfolio total also uses that user's cash rather than the legacy global cash value.

## Deliberate blocks and remaining work

- Binance/Bybit live risk integration is unsupported: live new entries fail closed, even if ALLOW_LIVE_TRADING is set externally. Existing broker methods conceal some API failures and lack a complete cash-flow-adjusted historical equity ledger, so their data is not represented as verified.
- The auto-trader's DCA creation and pending execution are paused. They need atomic reservations and revalidation at execution time before resuming. Pending records are preserved and counted in sizing, not deleted or cancelled.
- Existing paper accounts without a recorded risk epoch remain blocked. An explicit reset erases virtual account holdings/history and must be a user's decision; this work does not perform it. Importing an independently verified historic peak is a separate alternative to design.
- SQLite tests do not establish PostgreSQL locking semantics, multi-process order atomicity, or end-to-end production readiness. Reconciliation and execution are separate transactions; concurrent manual/API writers or multiple workers still need an account-wide atomic execution/reservation design.
- Existing exit-management code remains, but paper executions require fresh verified prices. No fallback prices are used for exits either.

Do not merge or deploy this draft as a live-trading-ready change.

## Validation

Run from the repository root with SQLAlchemy, Alembic and pytest installed:

    ALLOW_LIVE_TRADING=false DATABASE_URL= python -m pytest \
      backend/tests/test_auto_sizing_fail_closed.py \
      backend/tests/test_verified_paper_sizing.py \
      backend/tests/test_position_sizing.py -q

Integration tests use actual project UserProfile/AutoSizingPaperRisk models, actual migration 023, a local in-memory SQLite database, the real paper service and PaperBroker. Prices are controlled test fixtures, and socket creation is forbidden during each new test. No broker account, Redis server, deployment, or real-money execution is used. Original tests are also executed as subtests by one regression test; do not add those nested executions again to the pytest total.

Evidence: docs/evidence/position-sizing/results.txt and results.xml. Only the targeted suite was run; full application CI and real PostgreSQL are not claimed.
