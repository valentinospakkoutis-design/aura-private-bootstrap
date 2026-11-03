"""Paper risk integration. Live adapters are deliberately unsupported/fail closed.

A paper risk epoch begins only at creation/reset, never by inventing history for
an existing account. Peak is the persisted high-water mark of observed MTM equity.
"""
import json
import math
import time
from datetime import datetime, timezone
from sqlalchemy import text
from services.sizing_snapshot import SizingSnapshot, validate_snapshot


def finite(value, positive=False):
    if isinstance(value, bool):
        raise ValueError('invalid_risk_number')
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        raise ValueError('invalid_risk_number')
    return result


def initialize_paper_epoch(db, user_id, cash):
    """Called only inside the creation/reset transaction; never from a read."""
    from database.models import AutoSizingPaperRisk
    cash = finite(cash, positive=True)
    risk = db.query(AutoSizingPaperRisk).filter_by(user_id=user_id).with_for_update().first()
    if risk is None:
        risk = AutoSizingPaperRisk(user_id=user_id)
        db.add(risk)
    risk.initial_equity_usd = cash
    risk.peak_equity_usd = cash
    risk.started_at = datetime.utcnow()
    risk.last_observed_at = None


def verified_paper_price(symbol, redis_client=None):
    """Read only timestamped websocket data, never yfinance/base-price fallbacks."""
    if redis_client is None:
        from cache.connection import get_redis
        redis_client = get_redis()
    if redis_client is None:
        raise ValueError('verified_price_cache_unavailable')
    raw = redis_client.get(f'price:{symbol}')
    quote = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
    if not isinstance(quote, dict) or 'ts_ms' not in quote:
        raise ValueError('verified_price_missing')
    ts = finite(quote['ts_ms'], positive=True)
    if not 0 <= time.time() * 1000 - ts <= 60000:
        raise ValueError('verified_price_stale_or_future')
    return finite(quote['price'], positive=True)


def paper_sizing_snapshot(user_id, broker, session_factory=None, price_reader=None):
    from brokers.paper_broker import PaperBroker
    from database.models import UserProfile, AutoSizingPaperRisk
    if type(broker) is not PaperBroker or broker.user_id != user_id:
        raise ValueError('verified_live_risk_adapter_unavailable')
    if session_factory is None:
        from database.connection import SessionLocal
        session_factory = SessionLocal
    if not session_factory:
        raise ValueError('risk_database_unavailable')
    price_reader = price_reader or verified_paper_price
    db = session_factory()
    try:
        row = db.query(UserProfile).filter(UserProfile.user_id == user_id).with_for_update().first()
        if row is None:
            raise ValueError('paper_profile_unavailable')
        epoch = db.query(AutoSizingPaperRisk).filter_by(user_id=user_id).with_for_update().first()
        if epoch is None:
            raise ValueError('paper_risk_history_unavailable_reset_required')
        peak = finite(epoch.peak_equity_usd, positive=True)
        cash = finite(row.paper_balance)
        if not isinstance(row.paper_positions, list):
            raise ValueError('paper_positions_unverified')
        exposures = {}
        for pos in row.paper_positions:
            symbol = pos['symbol']
            if not isinstance(symbol, str) or not symbol or symbol != symbol.upper():
                raise ValueError('invalid_paper_symbol')
            quantity = finite(pos['quantity'], positive=True)
            exposures[symbol] = exposures.get(symbol, 0.) + quantity * finite(price_reader(symbol), positive=True)
        equity = cash + sum(exposures.values())
        # DCA schema/query failures must propagate, never mean 'no pending orders'.
        pending = db.execute(text("SELECT symbol, size_usd FROM dca_orders WHERE user_id=:uid AND status='pending'"),
                             {'uid': user_id}).mappings().all()
        reserved = 0.
        for order in pending:
            symbol = order['symbol']
            if not isinstance(symbol, str) or not symbol or symbol != symbol.upper():
                raise ValueError('invalid_pending_symbol')
            amount = finite(order['size_usd'], positive=True)
            exposures[symbol] = exposures.get(symbol, 0.) + amount
            reserved += amount
        if reserved > cash:
            raise ValueError('paper_reservations_exceed_cash')
        # Reject stale service caches instead of sizing one state and executing another.
        from services.paper_trading import paper_trading_service
        cached = paper_trading_service._user_states.get(user_id)
        if cached is not None:
            persisted = {p['symbol']: {'quantity': p['quantity'], 'avg_price': p['avg_price'],
                                      'total_cost': p['total_cost']} for p in row.paper_positions}
            if cached['cash'] != cash or cached['portfolio'] != persisted:
                raise ValueError('paper_runtime_database_mismatch')
        peak = max(peak, equity)
        snapshot = SizingSnapshot(user_id, broker, True, datetime.now(timezone.utc),
                                  equity, peak, cash-reserved, exposures, True)
        snapshot = validate_snapshot(snapshot, user_id, broker, True)
        epoch.peak_equity_usd = peak
        epoch.last_observed_at = snapshot.observed_at.replace(tzinfo=None)
        db.commit()  # Failed persistence must reject the sizing attempt.
        return snapshot
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
