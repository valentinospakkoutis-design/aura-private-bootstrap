"""ExecutionReservation and ReservationFillEvent models — append to database/models.py.

These are stand-alone definitions for the v2 patch.
In the integration step, paste the two classes below the last existing model in
backend/database/models.py (currently: PaperStrategySnapshot).
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey,
    Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

# Assume Base is already imported from the existing models.py:
#   from database.models import Base
# For standalone use in tests this module defines its own declarative base.
try:
    from database.models import Base          # real codebase
except Exception:                             # test isolation fallback
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()


class ExecutionReservation(Base):
    """One row per in-flight paper order, from reservation through terminal status."""

    __tablename__ = 'execution_reservations'
    __table_args__ = (
        CheckConstraint("account_mode = 'paper'", name='ck_er_paper_only'),
        CheckConstraint("side IN ('BUY','SELL')", name='ck_er_side'),
        CheckConstraint(
            "status IN ('reserved','claiming','partial','filled',"
            "'rejected','unknown','cancelled_partial')",
            name='ck_er_status'),
    )

    id               = Column(Integer,       primary_key=True, autoincrement=True)
    idempotency_key  = Column(String(64),    nullable=False, unique=True)
    user_id          = Column(Integer,       nullable=False, index=True)
    account_mode     = Column(String(16),    nullable=False)
    symbol           = Column(String(32),    nullable=False)
    side             = Column(String(8),     nullable=False)
    order_type       = Column(String(16),    nullable=False)
    quantity         = Column(Numeric(20, 8), nullable=False)
    notional_usd     = Column(Numeric(20, 8), nullable=False)
    fee_estimate_usd = Column(Numeric(20, 8), nullable=False)
    status           = Column(String(24),    nullable=False, default='reserved')
    created_at       = Column(DateTime,      nullable=False, default=datetime.utcnow)
    expires_at       = Column(DateTime,      nullable=False)
    claimed_at       = Column(DateTime,      nullable=True)
    released_at      = Column(DateTime,      nullable=True)
    # Accumulated fill totals (updated on each fill event)
    filled_quantity  = Column(Numeric(20, 8), nullable=True)
    filled_notional  = Column(Numeric(20, 8), nullable=True)
    actual_fee_usd   = Column(Numeric(20, 8), nullable=True)
    broker_order_id  = Column(String(128),   nullable=True)
    # F21-active: worst-case cost stored at reservation time so active-reservation
    # accumulation uses consistent worst-case figures across sessions.
    worst_case_total_usd     = Column(Numeric(20, 8), nullable=True)  # notional×1.05 + fee_on_worst
    worst_case_notional_usd  = Column(Numeric(20, 8), nullable=True)  # notional×1.05 (no fee; for exposure checks)
    # F22-persist: step-aligned completeness threshold persisted to DB so
    # settle_reservation can load it in a fresh session.
    min_filled_qty   = Column(Numeric(20, 8), nullable=True)

    fill_events = relationship('ReservationFillEvent', back_populates='reservation',
                               cascade='all, delete-orphan')

    # ── convenience properties ──────────────────────────────────────────────
    @property
    def quantity_d(self) -> Decimal:
        return Decimal(str(self.quantity)) if self.quantity is not None else Decimal('0')

    @property
    def notional_d(self) -> Decimal:
        return Decimal(str(self.notional_usd)) if self.notional_usd is not None else Decimal('0')

    @property
    def remaining_quantity_d(self) -> Decimal:
        filled = Decimal(str(self.filled_quantity)) if self.filled_quantity is not None else Decimal('0')
        return max(Decimal('0'), self.quantity_d - filled)


class ReservationFillEvent(Base):
    """Append-only log of fill events.

    UNIQUE(reservation_id, fill_id) prevents double-counting the same fill.
    Surviving fills on a cancelled order record what was actually executed.
    """

    __tablename__ = 'reservation_fill_events'
    __table_args__ = (
        UniqueConstraint('reservation_id', 'fill_id', name='uq_fill_event'),
    )

    id             = Column(Integer,       primary_key=True, autoincrement=True)
    reservation_id = Column(Integer,       ForeignKey('execution_reservations.id',
                                                      name='fk_rfe_reservation'),
                            nullable=False)
    fill_id        = Column(String(128),   nullable=False)
    filled_quantity = Column(Numeric(20, 8), nullable=False)
    filled_notional = Column(Numeric(20, 8), nullable=False)
    actual_fee_usd  = Column(Numeric(20, 8), nullable=False)
    recorded_at    = Column(DateTime,      nullable=False, default=datetime.utcnow)

    reservation = relationship('ExecutionReservation', back_populates='fill_events')
