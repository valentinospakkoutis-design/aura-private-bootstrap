"""
AI Feed Persistence Service for AURA.
Stores user-facing product insights to the persistent_feed_events table.

Supports:
  - prioritized, typed feed events
  - deduplication via MD5 key (day + source + type + symbol + title)
  - expiration (expires_at for time-limited insights)
  - per-user read/unread state via feed_event_reads
  - source cross-referencing (link to decision event, risk event, etc.)
"""

import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Valid enums ──────────────────────────────────────────────────
VALID_SOURCE_TYPES = {
    "decision_engine", "risk_engine", "portfolio_engine",
    "simulation_engine", "system",
}

VALID_EVENT_TYPES = {
    "market_insight", "trade_opportunity", "risk_alert",
    "exposure_warning", "no_trade_explanation", "autopilot_update",
    "portfolio_health", "personalization_insight",
}

VALID_PRIORITIES = {"low", "medium", "high", "critical"}

# Default expiry durations per event type (hours)
DEFAULT_EXPIRY_HOURS = {
    "trade_opportunity": 24,
    "market_insight": 48,
    "risk_alert": 12,
    "exposure_warning": 24,
    "no_trade_explanation": 24,
    "autopilot_update": 72,
    "portfolio_health": 48,
    "personalization_insight": 168,  # 7 days
}


def _build_dedupe_key(
    source_type: str, event_type: str, symbol: str, title: str,
) -> str:
    """Generate a dedup key scoped to today + source + type + symbol + title."""
    today = date.today().isoformat()
    raw = f"{today}:{source_type}:{event_type}:{symbol}:{title}"
    return hashlib.md5(raw.encode()).hexdigest()


def emit_feed_event(
    source_type: str,
    event_type: str,
    title: str,
    short_summary: str,
    user_id: Optional[int] = None,
    full_explanation: Optional[str] = None,
    priority: str = "medium",
    related_symbol: Optional[str] = None,
    confidence_score: Optional[float] = None,
    risk_level: Optional[str] = None,
    action_suggestion: Optional[str] = None,
    source_reference_type: Optional[str] = None,
    source_reference_id: Optional[int] = None,
    expires_in_hours: Optional[int] = None,
    dedupe: bool = True,
) -> Optional[int]:
    """
    Emit a feed event. Deduplicated per day by default.
    Returns the row ID or None on duplicate/error.
    """
    if source_type not in VALID_SOURCE_TYPES:
        logger.warning(f"[feed_persist] Unknown source_type: {source_type}")
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(f"[feed_persist] Unknown event_type: {event_type}")
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    sym = related_symbol.upper() if related_symbol else ""
    dedupe_key = _build_dedupe_key(source_type, event_type, sym, title) if dedupe else None

    # Compute expiry
    expires_at = None
    if expires_in_hours is not None:
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    elif event_type in DEFAULT_EXPIRY_HOURS:
        expires_at = datetime.utcnow() + timedelta(hours=DEFAULT_EXPIRY_HOURS[event_type])

    try:
        from database.connection import SessionLocal
        from database.models import PersistentFeedEvent

        db = SessionLocal()

        # Check dedup before insert
        if dedupe_key:
            existing = (
                db.query(PersistentFeedEvent.id)
                .filter(PersistentFeedEvent.dedupe_key == dedupe_key)
                .first()
            )
            if existing:
                db.close()
                logger.debug(f"[feed_persist] Deduplicated: {event_type} | {sym} | {title}")
                return None

        row = PersistentFeedEvent(
            user_id=user_id,
            source_type=source_type,
            event_type=event_type,
            priority=priority,
            title=title,
            short_summary=short_summary,
            full_explanation=full_explanation,
            related_symbol=sym or None,
            confidence_score=confidence_score,
            risk_level=risk_level,
            action_suggestion=action_suggestion,
            source_reference_type=source_reference_type,
            source_reference_id=source_reference_id,
            dedupe_key=dedupe_key,
            expires_at=expires_at,
        )
        db.add(row)
        db.commit()
        row_id = row.id
        db.close()

        logger.debug(f"[feed_persist] Emitted #{row_id}: {event_type} | {sym} | {title}")
        return row_id

    except Exception as e:
        logger.error(f"[feed_persist] Failed to emit: {e}")
        return None


def get_user_feed(
    user_id: int,
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    symbol: Optional[str] = None,
    include_expired: bool = False,
    limit: int = 50,
) -> List[Dict]:
    """
    Get feed events for a user, newest first.
    Excludes expired events by default.
    Includes read/unread status per event.
    """
    try:
        from database.connection import SessionLocal
        from database.models import PersistentFeedEvent, FeedEventRead
        from sqlalchemy import and_

        db = SessionLocal()
        query = db.query(PersistentFeedEvent).filter(
            PersistentFeedEvent.user_id == user_id
        )

        if event_type:
            query = query.filter(PersistentFeedEvent.event_type == event_type)
        if priority:
            query = query.filter(PersistentFeedEvent.priority == priority)
        if symbol:
            query = query.filter(PersistentFeedEvent.related_symbol == symbol.upper())
        if not include_expired:
            now = datetime.utcnow()
            query = query.filter(
                (PersistentFeedEvent.expires_at.is_(None)) |
                (PersistentFeedEvent.expires_at > now)
            )

        events = (
            query
            .order_by(PersistentFeedEvent.created_at.desc())
            .limit(min(limit, 200))
            .all()
        )

        # Batch-fetch read state for this user
        event_ids = [e.id for e in events]
        read_ids = set()
        if event_ids:
            read_rows = (
                db.query(FeedEventRead.feed_event_id)
                .filter(
                    and_(
                        FeedEventRead.user_id == user_id,
                        FeedEventRead.feed_event_id.in_(event_ids),
                    )
                )
                .all()
            )
            read_ids = {r.feed_event_id for r in read_rows}

        db.close()

        return [
            {
                "id": e.id,
                "source_type": e.source_type,
                "event_type": e.event_type,
                "priority": e.priority,
                "title": e.title,
                "short_summary": e.short_summary,
                "full_explanation": e.full_explanation,
                "related_symbol": e.related_symbol,
                "confidence_score": e.confidence_score,
                "risk_level": e.risk_level,
                "action_suggestion": e.action_suggestion,
                "source_reference_type": e.source_reference_type,
                "source_reference_id": e.source_reference_id,
                "is_read": e.id in read_ids,
                "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]

    except Exception as e:
        logger.warning(f"[feed_persist] Failed to get feed: {e}")
        return []


def get_unread_count(user_id: int) -> int:
    """Count unread, non-expired feed events for a user."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentFeedEvent, FeedEventRead
        from sqlalchemy import func, and_

        db = SessionLocal()
        now = datetime.utcnow()

        total = (
            db.query(func.count(PersistentFeedEvent.id))
            .filter(
                PersistentFeedEvent.user_id == user_id,
                (PersistentFeedEvent.expires_at.is_(None)) |
                (PersistentFeedEvent.expires_at > now),
            )
            .scalar()
        ) or 0

        read_count = (
            db.query(func.count(FeedEventRead.id))
            .join(PersistentFeedEvent, FeedEventRead.feed_event_id == PersistentFeedEvent.id)
            .filter(
                FeedEventRead.user_id == user_id,
                PersistentFeedEvent.user_id == user_id,
                (PersistentFeedEvent.expires_at.is_(None)) |
                (PersistentFeedEvent.expires_at > now),
            )
            .scalar()
        ) or 0

        db.close()
        return max(0, total - read_count)

    except Exception as e:
        logger.warning(f"[feed_persist] Failed to get unread count: {e}")
        return 0


def mark_read(user_id: int, feed_event_ids: List[int]) -> int:
    """
    Mark feed events as read for a user.
    Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
    Returns number of newly marked events.
    """
    if not feed_event_ids:
        return 0

    try:
        from database.connection import SessionLocal
        from database.models import FeedEventRead

        db = SessionLocal()
        marked = 0
        for eid in feed_event_ids:
            existing = (
                db.query(FeedEventRead.id)
                .filter(
                    FeedEventRead.feed_event_id == eid,
                    FeedEventRead.user_id == user_id,
                )
                .first()
            )
            if not existing:
                db.add(FeedEventRead(
                    feed_event_id=eid,
                    user_id=user_id,
                ))
                marked += 1

        db.commit()
        db.close()
        return marked

    except Exception as e:
        logger.error(f"[feed_persist] Failed to mark read: {e}")
        return 0


def mark_all_read(user_id: int) -> int:
    """Mark all unread feed events as read for a user."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentFeedEvent, FeedEventRead
        from sqlalchemy import and_

        db = SessionLocal()
        now = datetime.utcnow()

        # Find all unread event IDs for this user
        all_ids = (
            db.query(PersistentFeedEvent.id)
            .filter(
                PersistentFeedEvent.user_id == user_id,
                (PersistentFeedEvent.expires_at.is_(None)) |
                (PersistentFeedEvent.expires_at > now),
            )
            .all()
        )
        all_event_ids = {r.id for r in all_ids}

        already_read = (
            db.query(FeedEventRead.feed_event_id)
            .filter(
                FeedEventRead.user_id == user_id,
                FeedEventRead.feed_event_id.in_(all_event_ids) if all_event_ids else False,
            )
            .all()
        )
        already_read_ids = {r.feed_event_id for r in already_read}

        unread_ids = all_event_ids - already_read_ids
        for eid in unread_ids:
            db.add(FeedEventRead(feed_event_id=eid, user_id=user_id))

        db.commit()
        db.close()
        return len(unread_ids)

    except Exception as e:
        logger.error(f"[feed_persist] Failed to mark all read: {e}")
        return 0
