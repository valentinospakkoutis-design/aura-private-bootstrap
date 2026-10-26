"""Atomic paper-mode order reservation, claim, settlement and accounting.

Every paper order — auto-trader, manual UI, API — must pass through:

    reserve_and_validate()  →  claim_reservation()  →  settle_reservation()

v8 fixes (over v7)
──────────────────
F21-active. Active reservations accumulated raw notional+fee instead of worst-case.

     Two $50 reservations with cash=$102.60 passed the check (raw total $100.10 <
     $102.60), but the second settlement failed because the actual worst-case total
     was $105.10.  Root cause: the SQL aggregation used SUM(notional_usd +
     fee_estimate_usd) on active rows.

     Fix: each reservation now stores worst_case_total_usd (notional×1.05 + fee on
     that) and worst_case_notional_usd (notional×1.05, used for symbol/portfolio
     exposure checks without fee) at write time.  The active-reservation SQL
     aggregation uses COALESCE(worst_case_total_usd, raw) so that legacy rows (pre-v8)
     contribute their raw cost while v8+ rows contribute worst-case.

     All three checks — cash, symbol exposure, portfolio exposure — now accumulate
     active reservations at worst-case cost.

F22-floor. _compute_min_filled_qty accepted fills far short of 97 %.

     For qty=0.3, step=0.1: floor(0.97×0.3/0.1)×0.1 = floor(2.91)×0.1 = 0.2.
     That is only 66.7 % of the reserved quantity, yet the remaining 0.1 is a whole
     executable step.  The formula rounded 97 % downward without bounding how far
     below the actual quantity the threshold could land.

     v8 fix: min_required = max(floor_threshold, qty − step).
     At most ONE step may be left unfilled.

     v9 fix: the v8 formula still allowed exactly one whole executable step to
     remain unfilled (boundary case: floor_threshold == qty − step).  Three-way
     formula patched the boundary, but failed for large integer ratios (qty=34,
     step=1): floor=32 < one_step_below=33, so clamped to 33, still leaving
     remainder=1 == step.

     v10 fix (definitive): the correct rule is remainder STRICTLY less than one
     step, i.e. (reserved_qty − filled_qty) < qty_step.  The unique step-aligned
     value that satisfies this is floor(reserved_qty / qty_step) × qty_step.

         For integer ratios (qty exact multiple of step):
             floor(qty/step) = qty/step  →  min = qty  (full fill required)
         For non-integer ratios (e.g. qty=1.5, step=0.2, ratio=7.5):
             floor(7.5) = 7  →  min = 1.4  (remainder=0.1 < step=0.2 ✓)

     Formula: min_filled_qty = floor(reserved_qty / qty_step) × qty_step

F22-persist. min_filled_qty not persisted to DB — rejected in new sessions.

     The reservation service stored the threshold only on the Python object
     (reservation._min_filled_qty), which was lost when a new session loaded
     the row from DB.  A fill accepted in the original session was rejected as
     filled_incomplete in any subsequent session.

     Fix: min_filled_qty is now a real DB column on execution_reservations
     (migration 025).  reserve_and_validate() writes it; settle_reservation()
     reads it from the row, never from a transient Python attribute.

v7 fixes (carried over)
───────────────────────
F20. Stale ORM cache on locked rows in reserve_and_validate() — the UserProfile
     query now includes .populate_existing() so that concurrent or sequential
     sessions always see the current paper_balance and paper_positions, never
     a cached copy from before the lock was acquired.

F21. Slippage headroom applied to ALL capacity checks, not just per-trade cap.

     worst_case_notional = notional_d × FILL_NOTIONAL_TOLERANCE

     Checks updated: cash, per-trade cap, symbol cap, portfolio cap.

F22. qty_step tolerance for FILL_COMPLETE_THRESHOLD (97 % completeness check).

     Optional qty_step parameter in reserve_and_validate(); threshold stored as
     min_filled_qty on the reservation row.

v6 fixes (carried over)
───────────────────────
F16b. populate_existing() on UserProfile in settle_reservation().
F17b. Effective per-trade cap = max_per_trade_usd / FILL_NOTIONAL_TOLERANCE.
F19.  Alembic fixture and env.py; _make_engine() SQLite-only create_all().

v5 fixes (carried over)
────────────────────────
F16. Stale ORM cache on locked reservation row in settle_reservation().
F17. Fill notional must not exceed reserved notional × 1.05.
F18. Premature 'filled' blocked — 97 % completeness threshold.
F12b. broker_order_id inside savepoint.

v4 fixes (carried over)
────────────────────────
F11. fill_price consistency check (±0.5 % tolerance).
F12. Settle atomicity via savepoint.
F13. Strict outcome/fill-data validation.
F14. TestPostgresConcurrency renamed; uses real Alembic migration.
F15. Decimal integrity — positions stored as str(Decimal).

v3 fixes (carried over)
────────────────────────
F6. RISK_PROFILES percentage division.
F7. Position quantity tracking (fill_price parameter).
F8. SELL validation in units from locked paper_positions.
F9. Overfill guard.
F10. Active BUY netting against locked cash.
L1. Lock order: UserProfile → reservation.
L2. No float re-cast; negative cash raises ReservationSettlementError.
L3. Fresh exposure inside lock (SELL unit check from locked profile).

v2 fixes (carried over)
────────────────────────
F1. Snapshot freshness — cash re-read from locked UserProfile row.
F2. SELL notional dedup.
F3. Fill dedup via reservation_fill_events UNIQUE constraint.
F4. unknown → terminal (reconciliation path).
F5. Atomic settlement accounting.
C1. Real RISK_PROFILES field names.
C2. cancelled_partial in status CHECK constraint.

Design guarantees
─────────────────
1.  Lock order: UserProfile → AutoSizingPaperRisk → execution_reservations.
    Never reversed.  settle_reservation() acquires UserProfile first (L1).

2.  Active statuses consume resources: reserved, claiming, partial, unknown.
    Expiry requires explicit reconciliation; never auto-releases.

3.  Idempotency: checked inside lock before capacity math.

4.  Atomic claim: UPDATE reserved→claiming (PG RETURNING / SQLite SFU).

5.  Fill dedup: UNIQUE(reservation_id, fill_id) on reservation_fill_events.

6.  Overfill guard: total filled quantity ≤ reserved quantity × 1.001.

7.  Caps from RISK_PROFILES (pct ÷ 100 × equity).

8.  SELL check in units from locked paper_positions.

9.  All monetary arithmetic uses Decimal; DB stores NUMERIC(20,8).

10. Position JSON stores Decimal values as strings; no float() cast.

11. settle_reservation() uses a savepoint; failure rolls back to savepoint.

12. fill_price × fill_qty ≈ fill_notional checked before any write (F11).

13. filled_notional ≤ reserved_notional × FILL_NOTIONAL_TOLERANCE (F17).

14. outcome='filled' requires accumulated qty ≥ min_required (F18/F22).

15. Reserved row re-read with populate_existing() under lock (F16).

16. broker_order_id set inside savepoint (F12b).

17. UserProfile re-read with populate_existing() in reserve_and_validate() (F20).

18. All capacity checks use worst_case_notional = notional × 1.05 (F21).

19. qty_step-aligned 97 % completeness threshold; at most one step may remain
    unfilled (F22-floor); threshold persisted in DB column min_filled_qty (F22-persist).

20. Active reservations accumulate worst_case_total_usd (not raw cost) for cash
    and portfolio cap checks; worst_case_notional_usd for symbol exposure (F21-active).

Operational constraints
───────────────────────
- No account resets, real orders, pushes, merges to remote branches,
  migrations on an external DB, or deployments.
- ALLOW_LIVE_TRADING unchanged.
- DCA safeguards and kill switch preserved.
- Scope: paper mode only, no real broker connections.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

# ── constants ───────────────────────────────────────────────────────────────
ACTIVE_STATUSES   = ('reserved', 'claiming', 'partial', 'unknown')
TERMINAL_STATUSES = ('filled', 'rejected', 'cancelled_partial')
FEE_RATE_TAKER    = Decimal('0.001')    # 0.10 % — conservative taker fee
RESERVATION_TTL_SECONDS = 30
OVERFILL_TOLERANCE = Decimal('1.001')   # 0.1 % rounding tolerance

# F11: fill_price × fill_qty must be within this fraction of fill_notional.
FILL_PRICE_NOTIONAL_TOLERANCE = Decimal('0.005')   # 0.5 %

# F17/F21: filled_notional may reach reserved_notional × this factor.
# 5 % slippage allowance — generous for market orders on liquid assets.
# ALL capacity checks at reservation time use worst_case = notional × this.
FILL_NOTIONAL_TOLERANCE = Decimal('1.05')          # 105 % of reserved

# F18/F22: outcome='filled' requires at least this fraction of reserved_quantity filled.
# 97 % threshold: allows tiny rounding residuals without false "partial" obligations.
FILL_COMPLETE_THRESHOLD = Decimal('0.97')

# F18: strict transition table — (source_status, outcome) → allowed
VALID_TRANSITIONS = {
    ('claiming', 'filled'),
    ('claiming', 'rejected'),
    ('claiming', 'partial'),
    ('claiming', 'unknown'),
    ('claiming', 'cancelled_partial'),
    ('partial',  'filled'),
    ('partial',  'cancelled_partial'),
    ('partial',  'unknown'),
    ('partial',  'partial'),
    ('unknown',  'filled'),
    ('unknown',  'rejected'),
    ('unknown',  'cancelled_partial'),
    # reserved → unknown (edge case: reservation was never claimed, e.g. broker rejected immediately)
    ('reserved', 'unknown'),
    ('reserved', 'rejected'),
}


# ── exceptions ──────────────────────────────────────────────────────────────

class ReservationError(Exception):
    """Base — always fail-closed."""

class ReservationRejected(ReservationError):
    """Capacity or validation check failed; no reservation written."""

class ReservationConflict(ReservationError):
    """Idempotency key reuse with different params, or claim race lost."""

class ReservationNotFound(ReservationError):
    """Reservation ID not found."""

class ReservationSettlementError(ReservationError):
    """Settlement data invalid or accounting update failed.

    When outcome='filled' is rejected because the fill is below the
    step-aligned threshold (filled_incomplete), the exception carries
    structured attributes so the caller can re-settle as 'partial'
    without losing the fill event:

        exc.fill_id           — the SAME fill_id that was rejected (re-use it)
        exc.filled_quantity   — the fill quantity that was rejected
        exc.filled_notional   — the fill notional that was rejected
        exc.actual_fee_usd    — the fill fee that was rejected
        exc.fill_price        — the fill price that was rejected
        exc.reservation_id    — the reservation being settled
        exc.min_required      — the step-aligned minimum for 'filled'

    Usage pattern:
        try:
            svc.settle_reservation(..., outcome='filled',
                                   fill_id=my_fill_id, ...)
        except ReservationSettlementError as exc:
            if 'filled_incomplete' in str(exc) and exc.filled_quantity:
                # Re-use exc.fill_id — same identity, just different outcome.
                svc.settle_reservation(..., outcome='partial',
                                       fill_id=exc.fill_id,
                                       filled_quantity=exc.filled_quantity,
                                       filled_notional=exc.filled_notional,
                                       actual_fee_usd=exc.actual_fee_usd,
                                       fill_price=exc.fill_price)
    """
    # Structured attributes populated only for filled_incomplete errors.
    fill_id:         Optional[str]     = None
    filled_quantity: Optional[Decimal] = None
    filled_notional: Optional[Decimal] = None
    actual_fee_usd:  Optional[Decimal] = None
    fill_price:      Optional[Decimal] = None
    reservation_id:  Optional[int]     = None
    min_required:    Optional[Decimal] = None


# ── helpers ─────────────────────────────────────────────────────────────────

def _d(value, name='value', positive=False) -> Decimal:
    """Convert to Decimal; reject bool, non-finite float, negative."""
    if isinstance(value, bool):
        raise ReservationRejected(f'invalid_{name}: bool not allowed')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ReservationRejected(f'invalid_{name}: not numeric')
    if not result.is_finite():
        raise ReservationRejected(f'invalid_{name}: not finite')
    if result < 0:
        raise ReservationRejected(f'invalid_{name}: negative')
    if positive and result <= 0:
        raise ReservationRejected(f'invalid_{name}: must be positive')
    return result


def _d_settle(value, name='value', positive=False) -> Decimal:
    """Like _d() but raises ReservationSettlementError instead of ReservationRejected.

    Used for fill data validation inside settle_reservation().
    """
    if isinstance(value, bool):
        raise ReservationSettlementError(f'invalid_{name}: bool not allowed')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ReservationSettlementError(f'invalid_{name}: not numeric')
    if not result.is_finite():
        raise ReservationSettlementError(f'invalid_{name}: not finite')
    if result < 0:
        raise ReservationSettlementError(f'invalid_{name}: negative')
    if positive and result <= 0:
        raise ReservationSettlementError(f'invalid_{name}: must be positive')
    return result


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _params_match(row, symbol, side, order_type, quantity_d, notional_d) -> bool:
    return (row.symbol == symbol
            and row.side == side
            and row.order_type == order_type
            and Decimal(str(row.quantity)) == quantity_d
            and Decimal(str(row.notional_usd)) == notional_d)


def _get_dialect(db: Session) -> str:
    try:
        return db.get_bind().dialect.name
    except Exception:
        return 'unknown'


def _pos_d(value) -> Decimal:
    """Read a position JSON value back as Decimal.

    Stored as str (e.g. "0.001") in v4; may be float in rows written by v3.
    Always returns a Decimal regardless of the stored type.
    """
    return Decimal(str(value))


def _compute_min_filled_qty(
    reserved_qty: Decimal,
    qty_step: Optional[Decimal],
) -> Decimal:
    """Compute the step-aligned completeness threshold for outcome='filled' (F22).

    v10 (definitive): The rule is that the unfilled remainder must be STRICTLY
    LESS than one step:

        (reserved_qty − filled_qty) < qty_step

    The unique step-aligned value that satisfies this is:

        min_filled_qty = floor(reserved_qty / qty_step) × qty_step

    Derivation:
        Let n = floor(reserved_qty / qty_step).
        Then n × qty_step ≤ reserved_qty < (n+1) × qty_step.
        Remainder at n×step: reserved_qty − n×step < step  ✓
        Remainder at (n−1)×step: reserved_qty − (n−1)×step ≥ step  ✗

        For INTEGER ratios (qty = k × step):
            floor(qty/step) = k  →  min = k×step = qty  (full fill required)
            Example: qty=34, step=1  → min=34
            Example: qty=0.3, step=0.1 → min=0.3

        For NON-INTEGER ratios (qty = k.f × step, f>0):
            floor(qty/step) = k  →  min = k×step < qty  (partial fill allowed)
            Example: qty=1.5, step=0.2 → floor(7.5)=7 → min=1.4, rem=0.1<0.2 ✓
            Example: qty=10.0, step=0.3 → floor(33.3)=33 → min=9.9, rem=0.1<0.3 ✓

    v8/v9 approaches were superseded:
        v8: max(floor(0.97×qty/step)×step, qty−step)
            Still allowed fill=33 for qty=34, step=1 (floor=32 < one_step_below=33
            → clamped to 33 → remainder=1 == step, not strictly less).
        v9: three-way formula patched integer-ratio cases where floor==one_step_below,
            but left the floor<one_step_below clamp branch broken for large integer
            ratios (e.g. qty=34, step=1: floor=32 < one_step_below=33 → returned 33,
            remainder=1 not < step).

    When qty_step is None: min_required = reserved_qty (full fill required).
    v11: the 97% fallback is removed. A caller that cannot supply qty_step must
    fill the entire reserved quantity to close as 'filled'. This eliminates the
    bypass where fill=33 for qty=34 was accepted (33/34 = 97.1% > 97%) without
    a step constraint.
    """
    if qty_step is None or qty_step <= 0:
        # No step info: require exactly the full reserved quantity.
        # floor(qty / qty) × qty = qty for any positive qty.
        return reserved_qty
    # floor(reserved_qty / qty_step) × qty_step — the largest step-aligned value
    # whose unfilled remainder is strictly less than one step.
    total_steps = (reserved_qty / qty_step).to_integral_value(rounding=ROUND_DOWN)
    return total_steps * qty_step


# ── reserve_and_validate ─────────────────────────────────────────────────────

def reserve_and_validate(
    db: Session,
    *,
    user_id: int,
    account_mode: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: object,
    notional_usd: object,
    idempotency_key: str,
    snapshot,
    risk_profile: str,
    qty_step: Optional[object] = None,   # F22: exchange minimum quantity increment
) -> object:
    """Validate capacity and write a reservation inside the caller's transaction.

    Lock order: UserProfile → AutoSizingPaperRisk → execution_reservations (read).

    F1:   Cash re-read from locked UserProfile row.
    F2:   Active SELL notional subtracted from SELL holding (USD).
    F6:   RISK_PROFILES percentages divided by 100 before multiplying by equity.
    F8:   SELL unit check uses locked paper_positions (L3) in units.
    F10:  Active BUY notional+fee subtracted from locked cash.
    F17b: Per-trade cap uses effective_cap = max_per_trade_usd / FILL_NOTIONAL_TOLERANCE.
    F20:  UserProfile loaded with .populate_existing() so stale sessions see fresh data.
    F21:  All capacity checks use worst_case_notional = notional_d × FILL_NOTIONAL_TOLERANCE.
    F22:  qty_step-aligned 97 % completeness threshold stored as min_filled_qty.

    Raises ReservationRejected on capacity failure.
    Raises ReservationConflict on idempotency key reuse with different params.
    """
    from database.models import UserProfile, AutoSizingPaperRisk, ExecutionReservation
    from services.position_sizing import RISK_PROFILES
    from services.sizing_snapshot import validate_snapshot

    # ── input validation ────────────────────────────────────────────────────
    if type(user_id) is not int or user_id <= 0:
        raise ReservationRejected('invalid_user_id')
    if account_mode != 'paper':
        raise ReservationRejected('live_reservation_not_supported')
    if not isinstance(symbol, str) or not symbol or symbol != symbol.upper():
        raise ReservationRejected('invalid_symbol')
    if side not in ('BUY', 'SELL'):
        raise ReservationRejected('invalid_side')
    if order_type not in ('market', 'limit'):
        raise ReservationRejected('invalid_order_type')
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise ReservationRejected('invalid_idempotency_key')
    if risk_profile not in RISK_PROFILES:
        raise ReservationRejected('unknown_risk_profile')

    quantity_d = _d(quantity,    'quantity',    positive=True)
    notional_d = _d(notional_usd, 'notional_usd', positive=True)
    fee_d      = (notional_d * FEE_RATE_TAKER).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    # F22: parse qty_step if provided
    qty_step_d: Optional[Decimal] = None
    if qty_step is not None:
        qty_step_d = _d(qty_step, 'qty_step', positive=True)

    # F21: worst-case notional = reserved notional × FILL_NOTIONAL_TOLERANCE.
    # Used in all capacity checks: cash, per-trade cap, symbol cap, portfolio cap.
    worst_case_notional = notional_d * FILL_NOTIONAL_TOLERANCE
    # Worst-case fee is proportional to worst-case notional.
    worst_case_fee = (worst_case_notional * FEE_RATE_TAKER).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN)
    worst_case_total = worst_case_notional + worst_case_fee

    # ── re-validate snapshot ────────────────────────────────────────────────
    paper_mode = account_mode == 'paper'
    broker     = snapshot.broker
    snapshot   = validate_snapshot(snapshot, user_id, broker, paper_mode)

    # ── acquire account locks (UserProfile first) ─────────────────────────────
    # F20: .populate_existing() forces re-read from DB even if this session
    # already holds a cached UserProfile.  Without this, a session that loaded
    # the profile before calling reserve_and_validate() would approve a
    # reservation against a stale (too-high) balance.
    profile_row = (db.query(UserProfile)
                     .filter(UserProfile.user_id == user_id)
                     .with_for_update()
                     .populate_existing()
                     .first())
    if profile_row is None:
        raise ReservationRejected('paper_profile_unavailable')

    epoch = (db.query(AutoSizingPaperRisk)
               .filter_by(user_id=user_id)
               .with_for_update()
               .first())
    if epoch is None:
        raise ReservationRejected('paper_risk_epoch_unavailable_reset_required')

    # ── F1: re-read cash from NOW-LOCKED profile row ─────────────────────────
    locked_cash_d = _d(profile_row.paper_balance, 'paper_balance')

    # ── F6: caps from RISK_PROFILES — divide percentages by 100 ─────────────
    # Real profiles store e.g. 10.0 for 10 %, not 0.10.
    caps               = RISK_PROFILES[risk_profile]
    equity_d           = _d(snapshot.equity_usd, 'equity_usd', positive=True)
    max_per_trade_usd  = equity_d * _d(caps['max_per_trade_pct'],  'max_per_trade_pct') / Decimal('100')
    max_portfolio_usd  = equity_d * _d(caps['max_portfolio_pct'],  'max_portfolio_pct') / Decimal('100')
    sym_pct_key        = 'max_symbol_pct' if 'max_symbol_pct' in caps else 'max_portfolio_pct'
    max_symbol_usd     = equity_d * _d(caps[sym_pct_key], sym_pct_key) / Decimal('100')

    # ── idempotency: check first, inside lock ───────────────────────────────
    existing = (db.query(ExecutionReservation)
                  .filter_by(idempotency_key=idempotency_key)
                  .with_for_update()
                  .first())
    if existing is not None:
        if (existing.user_id != user_id
                or existing.account_mode != account_mode
                or not _params_match(existing, symbol, side, order_type,
                                     quantity_d, notional_d)):
            raise ReservationConflict(
                f'idempotency_key_reuse: key={idempotency_key!r} '
                f'existing_status={existing.status}')
        logger.info('[reservation] idempotent replay key=%s status=%s',
                    idempotency_key, existing.status)
        return existing

    # ── active reservation totals (F21-active) ───────────────────────────────
    # All accumulations use worst_case_total_usd / worst_case_notional_usd so
    # that each active reservation contributes its worst-case cost rather than
    # the raw reserved notional + fee.  This closes the gap identified in F21:
    # two $50 reservations with $102.60 cash passed the raw check
    # (100.10 < 102.60) but the second settlement failed because the actual
    # worst-case total was $105.10.
    #
    # Legacy rows (pre-v8) lack worst_case_total_usd / worst_case_notional_usd.
    # COALESCE per-row falls back to a COMPUTED worst-case for these rows:
    #   worst_case_total     = notional * 1.05 + fee * 1.05
    #   worst_case_notional  = notional * 1.05
    # This is conservative but correct — it never understates the cost of an
    # active legacy reservation, so the cash/exposure checks remain safe.
    # Using the raw (notional + fee) as the fallback would reintroduce F21 for
    # any session that still has active legacy rows when the first v9 reservation
    # is attempted.
    active = db.execute(
        text("""
            SELECT
                COALESCE(SUM(
                    COALESCE(worst_case_total_usd,
                             notional_usd * 1.05 + fee_estimate_usd * 1.05)
                ), 0) AS total_cost,
                COALESCE(SUM(CASE WHEN side = 'BUY'
                                  THEN COALESCE(worst_case_total_usd,
                                                notional_usd * 1.05 + fee_estimate_usd * 1.05)
                                  ELSE 0 END), 0)
                    AS buy_total_cost,
                COALESCE(SUM(CASE WHEN symbol = :sym
                                  THEN COALESCE(worst_case_notional_usd,
                                                notional_usd * 1.05)
                                  ELSE 0 END), 0)
                    AS symbol_buy_cost,
                COALESCE(SUM(CASE WHEN symbol = :sym AND side = 'SELL'
                                  THEN notional_usd ELSE 0 END), 0)
                    AS symbol_sell_notional,
                COALESCE(SUM(CASE WHEN symbol = :sym AND side = 'SELL'
                                  THEN quantity ELSE 0 END), 0)
                    AS symbol_sell_qty
            FROM execution_reservations
            WHERE user_id = :uid
              AND status  IN :statuses
        """).bindparams(
            bindparam('statuses', value=list(ACTIVE_STATUSES), expanding=True)
        ), {
            'uid': user_id,
            'sym': symbol,
        }
    ).mappings().one()

    active_buy_total_cost    = _d(active['buy_total_cost'])
    active_symbol_buy_cost   = _d(active['symbol_buy_cost'])
    active_symbol_sell_notl  = _d(active['symbol_sell_notional'])
    active_symbol_sell_qty   = _d(active['symbol_sell_qty'])

    # ── F10 + F21: cash check uses worst-case notional ─────────────────────
    # available_cash must cover worst_case_notional + worst_case_fee even if
    # slippage pushes the fill 5 % above the reserved notional.
    if side == 'BUY':
        available_cash = locked_cash_d - active_buy_total_cost
        if available_cash < worst_case_total:
            raise ReservationRejected(
                f'insufficient_cash: available={available_cash} '
                f'required_worst_case={worst_case_total} '
                f'(notional={notional_d} × slippage_tolerance={FILL_NOTIONAL_TOLERANCE} '
                f'+ fee; locked_cash={locked_cash_d} '
                f'pending_buy_cost={active_buy_total_cost})')

    # ── per-trade cap — worst_case_notional must not exceed cap (F17b/F21) ──
    # worst_case_notional = notional_d × FILL_NOTIONAL_TOLERANCE
    # This is equivalent to: notional_d ≤ max_per_trade_usd / FILL_NOTIONAL_TOLERANCE
    if worst_case_notional > max_per_trade_usd:
        raise ReservationRejected(
            f'per_trade_cap_exceeded: notional={notional_d} '
            f'effective_cap={max_per_trade_usd / FILL_NOTIONAL_TOLERANCE} '
            f'(cap={max_per_trade_usd} / slippage_tolerance={FILL_NOTIONAL_TOLERANCE})')

    # ── symbol exposure cap (BUY) — worst-case (F21) ─────────────────────────
    if side == 'BUY':
        current_sym_exposure  = _d(snapshot.exposure_by_symbol.get(symbol, 0))
        # Existing active reservations used raw notional; new one uses worst-case.
        projected_sym_worst   = current_sym_exposure + active_symbol_buy_cost + worst_case_notional
        if projected_sym_worst > max_symbol_usd:
            raise ReservationRejected(
                f'symbol_exposure_exceeded: projected_worst_case={projected_sym_worst} '
                f'cap={max_symbol_usd} '
                f'(current_exposure={current_sym_exposure} '
                f'active_reservations={active_symbol_buy_cost} '
                f'worst_case_new={worst_case_notional})')

    # ── portfolio exposure cap (BUY) — worst-case (F21) ──────────────────────
    if side == 'BUY':
        total_exposure     = sum(_d(v) for v in snapshot.exposure_by_symbol.values())
        projected_port_worst = total_exposure + active_buy_total_cost + worst_case_notional
        if projected_port_worst > max_portfolio_usd:
            raise ReservationRejected(
                f'portfolio_exposure_exceeded: projected_worst_case={projected_port_worst} '
                f'cap={max_portfolio_usd} '
                f'(total_exposure={total_exposure} '
                f'active_buy_cost={active_buy_total_cost} '
                f'worst_case_new={worst_case_notional})')

    # ── F8 + L3: SELL — unit check from locked paper_positions ───────────────
    if side == 'SELL':
        locked_positions = list(profile_row.paper_positions or [])
        locked_holding_qty = Decimal('0')
        for pos in locked_positions:
            if pos.get('symbol') == symbol:
                locked_holding_qty = _pos_d(pos.get('quantity', 0))
                break

        available_qty = locked_holding_qty - active_symbol_sell_qty
        if available_qty < quantity_d:
            raise ReservationRejected(
                f'insufficient_units_for_sell: available={available_qty} '
                f'requested={quantity_d} symbol={symbol} '
                f'(held={locked_holding_qty} active_sells={active_symbol_sell_qty})')

        # F2: legacy USD holding guard.
        holding_usd       = _d(snapshot.exposure_by_symbol.get(symbol, 0))
        available_holding = holding_usd - active_symbol_sell_notl
        if available_holding < notional_d:
            raise ReservationRejected(
                f'insufficient_asset_for_sell: available_holding={available_holding} '
                f'notional={notional_d} (active_sells_usd={active_symbol_sell_notl})')

    # ── F22: compute qty_step-aligned 97 % threshold ─────────────────────────
    min_filled_qty = _compute_min_filled_qty(quantity_d, qty_step_d)

    # ── write reservation ────────────────────────────────────────────────────
    now = _now_utc()
    reservation = ExecutionReservation(
        idempotency_key         = idempotency_key,
        user_id                 = user_id,
        account_mode            = account_mode,
        symbol                  = symbol,
        side                    = side,
        order_type              = order_type,
        quantity                = quantity_d,
        notional_usd            = notional_d,
        fee_estimate_usd        = fee_d,
        # F21-active: store worst-case costs so active-reservation aggregation
        # uses consistent worst-case figures across sessions (not raw cost).
        worst_case_total_usd    = worst_case_total,      # notional×1.05 + fee_on_worst
        worst_case_notional_usd = worst_case_notional,   # notional×1.05 (exposure checks)
        # F22-persist: persist threshold to DB so settle_reservation() can load
        # it in a fresh session without needing the original qty_step parameter.
        min_filled_qty          = min_filled_qty,
        status                  = 'reserved',
        created_at              = now,
        expires_at              = now + timedelta(seconds=RESERVATION_TTL_SECONDS),
    )

    db.add(reservation)
    db.flush()

    logger.info('[reservation] reserved id=%s user=%s %s %s qty=%s notional=%s '
                'worst_case_notional=%s min_filled_qty=%s',
                reservation.id, user_id, side, symbol,
                quantity_d, notional_d, worst_case_notional, min_filled_qty)
    return reservation


# ── claim_reservation ────────────────────────────────────────────────────────

def claim_reservation(db: Session, reservation_id: int) -> dict:
    """Atomically transition reserved → claiming.

    PostgreSQL: UPDATE … RETURNING.
    SQLite (CI): SELECT FOR UPDATE + UPDATE.

    Returns a dict with row data.
    Raises ReservationConflict if the row is not in 'reserved' status.
    """
    from database.models import ExecutionReservation

    dialect = _get_dialect(db)

    if dialect == 'postgresql':
        result = db.execute(text("""
            UPDATE execution_reservations
               SET status     = 'claiming',
                   claimed_at = now()
             WHERE id     = :id
               AND status = 'reserved'
            RETURNING id, idempotency_key, symbol, side, order_type,
                      quantity, notional_usd, fee_estimate_usd, user_id
        """), {'id': reservation_id}).mappings().one_or_none()

        if result is None:
            raise ReservationConflict(
                f'claim_failed: reservation {reservation_id} not in reserved status '
                f'(already claimed, settled, or not found)')
        db.commit()
        logger.info('[reservation] claimed id=%s key=%s %s %s qty=%s',
                    result['id'], result['idempotency_key'],
                    result['side'], result['symbol'], result['quantity'])
        return dict(result)

    else:
        row = (db.query(ExecutionReservation)
                 .filter_by(id=reservation_id, status='reserved')
                 .with_for_update()
                 .first())
        if row is None:
            raise ReservationConflict(
                f'claim_failed: reservation {reservation_id} not in reserved status '
                f'(already claimed, settled, or not found)')
        row.status     = 'claiming'
        row.claimed_at = _now_utc()
        db.commit()
        logger.info('[reservation] claimed id=%s key=%s %s %s qty=%s',
                    row.id, row.idempotency_key, row.side, row.symbol, row.quantity)
        return {
            'id':               row.id,
            'idempotency_key':  row.idempotency_key,
            'symbol':           row.symbol,
            'side':             row.side,
            'order_type':       row.order_type,
            'quantity':         row.quantity,
            'notional_usd':     row.notional_usd,
            'fee_estimate_usd': row.fee_estimate_usd,
            'user_id':          row.user_id,
        }


# ── settle_reservation ───────────────────────────────────────────────────────

def settle_reservation(
    db: Session,
    reservation_id: int,
    *,
    outcome: str,
    fill_id: Optional[str]   = None,
    filled_quantity: object  = None,
    filled_notional: object  = None,
    actual_fee_usd: object   = None,
    fill_price: object       = None,   # F7: required for filled/partial (price per unit)
    broker_order_id: Optional[str] = None,
) -> None:
    """Update reservation status and record fill details atomically.

    L1 — Lock order: UserProfile acquired BEFORE reservation row.
         Matches reserve_and_validate lock order; prevents deadlock.

    F3 — Fill dedup via UNIQUE(reservation_id, fill_id).

    F4 — unknown → terminal (reconciliation path).

    F7 — fill_price required for filled/partial outcomes.
         _apply_paper_accounting updates position quantity and avg_price.

    F9 — Overfill guard: rejects fills exceeding reserved quantity × 1.001.

    F11 — fill_price consistency: fill_price × fill_qty ≈ fill_notional (±0.5 %).

    F12 — Savepoint atomicity: fill-event write + accounting wrapped in
          db.begin_nested(). Failure rolls back to savepoint without
          affecting the reservation row in the outer transaction.

    F13 — Strict outcome validation: non-accounting outcomes (unknown, rejected,
          cancelled_partial) must NOT carry fill data.

    L2 — No float re-cast; negative cash raises ReservationSettlementError.

    Status machine (source → outcome) — VALID_TRANSITIONS (F18):
        reserved   → unknown | rejected
        claiming   → filled | rejected | partial | unknown | cancelled_partial
        partial    → filled | partial | cancelled_partial | unknown
        unknown    → filled | rejected | cancelled_partial  (F4)

    F16b — UserProfile re-read with populate_existing() under lock.
    F16  — reservation row re-read with populate_existing() under lock.
    F17  — filled_notional ≤ reserved_notional × FILL_NOTIONAL_TOLERANCE.
    F18/F22 — outcome='filled' requires accumulated qty ≥ min_required.
    F12b — broker_order_id set inside savepoint.
    """
    from database.models import ExecutionReservation, ReservationFillEvent, UserProfile

    if outcome not in ('filled', 'rejected', 'partial', 'unknown', 'cancelled_partial'):
        raise ReservationError(f'invalid_outcome: {outcome!r}')

    needs_fill_data     = outcome in ('filled', 'partial')
    no_accounting       = outcome in ('rejected', 'unknown', 'cancelled_partial')
    has_fill_data       = any(x is not None for x in
                              (filled_quantity, filled_notional, actual_fee_usd, fill_price, fill_id))

    # ── F13: non-accounting outcomes must not carry fill data ─────────────────
    if no_accounting and has_fill_data:
        raise ReservationSettlementError(
            f'fill_data_not_allowed_for_outcome={outcome!r}: '
            f'pass only outcome for rejected/unknown/cancelled_partial')

    # ── validate required fill data for accounting outcomes ──────────────────
    if needs_fill_data and fill_id is None:
        raise ReservationSettlementError(
            f'fill_id required for outcome={outcome!r}')
    if needs_fill_data and (filled_quantity is None or filled_notional is None
                             or actual_fee_usd is None):
        raise ReservationSettlementError(
            f'fill data (filled_quantity, filled_notional, actual_fee_usd) '
            f'required for outcome={outcome!r}')
    # F7: fill_price required for outcomes that update positions.
    if needs_fill_data and fill_price is None:
        raise ReservationSettlementError(
            f'fill_price required for outcome={outcome!r}')

    # ── convert fill data (raise ReservationSettlementError on bad values) ────
    fq = _d_settle(filled_quantity, 'filled_quantity', positive=True) if filled_quantity is not None else None
    fn = _d_settle(filled_notional, 'filled_notional', positive=True) if filled_notional is not None else None
    fa = _d_settle(actual_fee_usd,  'actual_fee_usd')                 if actual_fee_usd  is not None else None
    fp = _d_settle(fill_price,      'fill_price',      positive=True) if fill_price       is not None else None

    # ── F11: fill_price consistency check ────────────────────────────────────
    if fq is not None and fn is not None and fp is not None:
        implied_notional = fp * fq
        if fn > 0:
            relative_error = abs(implied_notional - fn) / fn
        else:
            relative_error = abs(implied_notional - fn)
        if relative_error > FILL_PRICE_NOTIONAL_TOLERANCE:
            raise ReservationSettlementError(
                f'fill_price_inconsistent: fill_price={fp} × fill_qty={fq} = {implied_notional} '
                f'but fill_notional={fn} (relative_error={relative_error:.4%}; '
                f'tolerance={FILL_PRICE_NOTIONAL_TOLERANCE:.1%})')

    # ── L1: lock UserProfile FIRST (same order as reserve_and_validate) ──────
    reservation_peek = (db.query(ExecutionReservation)
                          .filter_by(id=reservation_id)
                          .first())
    if reservation_peek is None:
        raise ReservationNotFound(f'reservation {reservation_id} not found')

    # F16b: populate_existing() forces re-read of UserProfile from DB.
    profile = (db.query(UserProfile)
                 .filter(UserProfile.user_id == reservation_peek.user_id)
                 .with_for_update()
                 .populate_existing()
                 .first())
    if profile is None:
        raise ReservationSettlementError(
            f'paper_profile_not_found for user {reservation_peek.user_id}')

    # ── F16: lock reservation row with populate_existing() ───────────────────
    row = (db.query(ExecutionReservation)
             .filter_by(id=reservation_id)
             .with_for_update()
             .populate_existing()
             .first())
    if row is None:
        raise ReservationNotFound(f'reservation {reservation_id} not found')

    # ── F18: strict transition table ─────────────────────────────────────────
    if (row.status, outcome) not in VALID_TRANSITIONS:
        raise ReservationConflict(
            f'invalid_transition: id={reservation_id} '
            f'status={row.status!r} → outcome={outcome!r}; '
            f'allowed from {row.status!r}: '
            + str([o for (s, o) in VALID_TRANSITIONS if s == row.status]))

    # ── F9: overfill guard (quantity) ────────────────────────────────────────
    reserved_qty = _d(row.quantity, 'reserved_quantity', positive=True)
    if fq is not None:
        current_filled    = _d(row.filled_quantity or 0)
        total_after_fill  = current_filled + fq
        if total_after_fill > reserved_qty * OVERFILL_TOLERANCE:
            raise ReservationSettlementError(
                f'overfill: reservation {reservation_id} reserved={reserved_qty} '
                f'already_filled={current_filled} this_fill={fq} '
                f'total={total_after_fill} max={reserved_qty * OVERFILL_TOLERANCE}')

    # ── F17: fill notional cap ───────────────────────────────────────────────
    if fn is not None:
        reserved_notional = _d(row.notional_usd, 'reserved_notional', positive=True)
        already_filled_notional = _d(row.filled_notional or 0)
        total_notional_after = already_filled_notional + fn
        if total_notional_after > reserved_notional * FILL_NOTIONAL_TOLERANCE:
            raise ReservationSettlementError(
                f'fill_notional_exceeds_reservation: reservation {reservation_id} '
                f'reserved_notional={reserved_notional} '
                f'already_filled_notional={already_filled_notional} '
                f'this_fill_notional={fn} '
                f'total={total_notional_after} '
                f'max={reserved_notional * FILL_NOTIONAL_TOLERANCE}')

    # ── F18/F22: filled completeness check ───────────────────────────────────
    # outcome='filled' requires accumulated filled_quantity ≥ min_required.
    # min_required is stored on the row (qty_step-aligned) or computed from
    # the 97 % threshold.
    if outcome == 'filled' and fq is not None:
        current_filled   = _d(row.filled_quantity or 0)
        total_after_fill = current_filled + fq
        # F22-persist: always read threshold from DB column.
        # The column is written at reservation time so it survives across
        # sessions.  For legacy rows (pre-v8) where min_filled_qty IS NULL,
        # v12 requires the full reserved quantity rather than the 97% fallback.
        # Rationale: without a stored step-aligned threshold we cannot determine
        # the exchange's minimum increment; requiring 100% is the safe default
        # (same rule as new reservations with no qty_step).
        if row.min_filled_qty is not None:
            min_required = _d(row.min_filled_qty)
        else:
            min_required = reserved_qty   # v12: full fill for legacy NULL rows
        if total_after_fill < min_required:
            exc = ReservationSettlementError(
                f'filled_incomplete: reservation {reservation_id} '
                f'reserved_qty={reserved_qty} '
                f'filled_so_far={current_filled} this_fill={fq} '
                f'total={total_after_fill} '
                f'min_required={min_required} (step-aligned threshold)')
            # Populate structured attributes so the caller can re-settle
            # the fill as outcome='partial' without losing the fill event.
            # IMPORTANT: re-use exc.fill_id in the re-settle call — it is the
            # same fill event, just re-classified as partial, not a new fill.
            exc.fill_id         = fill_id
            exc.filled_quantity = fq
            exc.filled_notional = fn
            exc.actual_fee_usd  = fa
            exc.fill_price      = fp
            exc.reservation_id  = reservation_id
            exc.min_required    = min_required
            raise exc

    # ── F12: savepoint — fill event + accounting ─────────────────────────────
    if needs_fill_data and fill_id is not None:
        savepoint = db.begin_nested()
        try:
            if broker_order_id is not None and row.broker_order_id is None:
                row.broker_order_id = broker_order_id

            fill_event = ReservationFillEvent(
                reservation_id  = reservation_id,
                fill_id         = fill_id,
                filled_quantity = fq,
                filled_notional = fn,
                actual_fee_usd  = fa,
                recorded_at     = _now_utc(),
            )
            db.add(fill_event)
            db.flush()

            row.filled_quantity = _d(row.filled_quantity or 0) + fq
            row.filled_notional = _d(row.filled_notional or 0) + fn
            row.actual_fee_usd  = _d(row.actual_fee_usd  or 0) + fa

            _apply_paper_accounting(
                db, row, profile=profile,
                outcome=outcome,
                this_fill_notional=fn,
                this_fill_fee=fa,
                this_fill_qty=fq,
                fill_price=fp,
            )

            row.status = outcome
            if outcome in TERMINAL_STATUSES:
                row.released_at = _now_utc()

            savepoint.commit()

        except IntegrityError:
            savepoint.rollback()
            logger.warning('[reservation] duplicate fill_id=%s id=%s — ignored',
                           fill_id, reservation_id)
            raise ReservationSettlementError(
                f'duplicate_fill_id: fill_id={fill_id!r} already recorded for '
                f'reservation {reservation_id}')
        except Exception:
            savepoint.rollback()
            raise

    else:
        row.status = outcome
        if outcome in TERMINAL_STATUSES:
            row.released_at = _now_utc()

    db.commit()
    logger.info('[reservation] settled id=%s status=%s fill_id=%s qty=%s',
                reservation_id, outcome, fill_id, row.filled_quantity)


def _apply_paper_accounting(
    db: Session,
    row,
    *,
    profile,
    outcome: str,
    this_fill_notional: Decimal,
    this_fill_fee: Decimal,
    this_fill_qty: Decimal,
    fill_price: Decimal,
) -> None:
    """Update paper_balance and paper_positions atomically (F5, F7, L2, F15).

    profile is already locked by settle_reservation (L1 ensures correct lock order).

    BUY  fills: cash -= (notional + fee); position qty/avg_price updated.
    SELL fills: cash += (notional - fee); position qty reduced.
    """
    cash      = _d(profile.paper_balance, 'paper_balance')
    positions = list(profile.paper_positions or [])
    symbol    = row.symbol

    if row.side == 'BUY':
        cash_delta = -(this_fill_notional + this_fill_fee)
        new_cash   = cash + cash_delta
        if new_cash < 0:
            raise ReservationSettlementError(
                f'accounting_error: BUY settlement would make cash negative '
                f'id={row.id} user={row.user_id} '
                f'cash={cash} delta={cash_delta} — investigate reservation state')
        _position_apply_buy(positions, symbol, this_fill_notional, this_fill_fee,
                            this_fill_qty, fill_price)

    elif row.side == 'SELL':
        cash_delta = this_fill_notional - this_fill_fee
        new_cash   = cash + cash_delta
        if new_cash < 0:
            raise ReservationSettlementError(
                f'accounting_error: SELL settlement produced negative cash '
                f'id={row.id} user={row.user_id} '
                f'cash={cash} delta={cash_delta}')
        _position_apply_sell(positions, symbol, this_fill_qty, fill_price)

    else:
        raise ReservationSettlementError(f'unknown side {row.side!r}')

    profile.paper_balance   = new_cash
    profile.paper_positions = list(positions)
    flag_modified(profile, 'paper_positions')


def _position_apply_buy(
    positions: list,
    symbol: str,
    fill_notional: Decimal,
    fill_fee: Decimal,
    fill_qty: Decimal,
    fill_price: Decimal,
) -> None:
    """Update (or create) position entry for a BUY fill (F7, F15)."""
    cost_inc = fill_notional + fill_fee
    for pos in positions:
        if pos.get('symbol') == symbol:
            prev_cost = _pos_d(pos.get('total_cost', 0))
            prev_qty  = _pos_d(pos.get('quantity', 0))
            new_cost  = prev_cost + cost_inc
            new_qty   = prev_qty  + fill_qty
            avg_price = new_cost / new_qty if new_qty > 0 else fill_price
            pos['quantity']   = str(new_qty)
            pos['avg_price']  = str(avg_price)
            pos['total_cost'] = str(new_cost)
            return
    avg_price = cost_inc / fill_qty if fill_qty > 0 else fill_price
    positions.append({
        'symbol':     symbol,
        'quantity':   str(fill_qty),
        'avg_price':  str(avg_price),
        'total_cost': str(cost_inc),
    })


def _position_apply_sell(
    positions: list,
    symbol: str,
    fill_qty: Decimal,
    fill_price: Decimal,
) -> None:
    """Reduce position entry for a SELL fill (F7, F15)."""
    for i, pos in enumerate(positions):
        if pos.get('symbol') == symbol:
            prev_qty  = _pos_d(pos.get('quantity',   0))
            prev_cost = _pos_d(pos.get('total_cost', 0))
            removed   = min(fill_qty, prev_qty)
            new_qty   = max(Decimal('0'), prev_qty - removed)
            if prev_qty > 0:
                cost_fraction = removed / prev_qty
                new_cost = max(Decimal('0'), prev_cost * (1 - cost_fraction))
            else:
                new_cost = Decimal('0')

            if new_qty <= 0:
                positions.pop(i)
            else:
                pos['quantity']   = str(new_qty)
                pos['total_cost'] = str(new_cost)
            return


# ── active_reservation_totals ────────────────────────────────────────────────

def active_reservation_totals(db: Session, user_id: int, symbol: str) -> dict:
    """Return active totals for capacity checks outside reserve_and_validate."""
    row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(notional_usd + fee_estimate_usd), 0) AS total_cost,
                COALESCE(SUM(CASE WHEN symbol = :sym THEN notional_usd ELSE 0 END), 0)
                    AS symbol_cost,
                COALESCE(SUM(CASE WHEN expires_at < :now THEN 1 ELSE 0 END), 0)
                    AS expired_count
            FROM execution_reservations
            WHERE user_id = :uid
              AND status  IN :statuses
        """).bindparams(
            bindparam('statuses', value=list(ACTIVE_STATUSES), expanding=True)
        ), {
            'uid': user_id,
            'sym': symbol,
            'now': _now_utc(),
        }
    ).mappings().one()

    expired = int(row['expired_count'] or 0)
    if expired > 0:
        logger.warning('[reservation] %d expired active reservations for user %s '
                       '— reconciliation required', expired, user_id)

    return {
        'total_cost_usd':  _d(row['total_cost']),
        'symbol_cost_usd': _d(row['symbol_cost']),
        'expired_count':   expired,
    }


def generate_idempotency_key() -> str:
    return str(uuid.uuid4())
