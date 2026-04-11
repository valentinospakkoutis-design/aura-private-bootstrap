"""Achievement system for gamification and retention."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal
from services.paper_trading import paper_trading_service
from services.push_notifications import send_push_to_user_id


ACHIEVEMENTS: List[Dict] = [
    {
        "id": "first_trade",
        "title_el": "Πρώτο Trade!",
        "title_en": "First Trade!",
        "desc_el": "Εκτέλεσε την πρώτη σου εντολή",
        "desc_en": "Placed your first order",
        "icon": "🎯",
    },
    {
        "id": "first_profit",
        "title_el": "Πρώτο Κέρδος!",
        "title_en": "First Profit!",
        "desc_el": "Έκλεισες θέση με κέρδος",
        "desc_en": "Closed a position in profit",
        "icon": "💰",
    },
    {
        "id": "streak_7",
        "title_el": "7 Μέρες Σερί!",
        "title_en": "7 Day Streak!",
        "desc_el": "Χρησιμοποίησες το AURA 7 μέρες",
        "desc_en": "Used AURA for 7 days straight",
        "icon": "🔥",
    },
    {
        "id": "win_rate_80",
        "title_el": "Sharp Trader",
        "title_en": "Sharp Trader",
        "desc_el": "80%+ win rate σε 10+ trades",
        "desc_en": "80%+ win rate on 10+ trades",
        "icon": "🎯",
    },
    {
        "id": "paper_profit_10",
        "title_el": "Paper Champion",
        "title_en": "Paper Champion",
        "desc_el": "+10% στο Paper Trading",
        "desc_en": "+10% on Paper Trading",
        "icon": "📈",
    },
    {
        "id": "auto_first",
        "title_el": "AI Pilot",
        "title_en": "AI Pilot",
        "desc_el": "Ενεργοποίησες το Auto Trading",
        "desc_en": "Enabled Auto Trading",
        "icon": "🤖",
    },
    {
        "id": "portfolio_100",
        "title_el": "Century Club",
        "title_en": "Century Club",
        "desc_el": "Portfolio αξίας $100+",
        "desc_en": "Portfolio value over $100",
        "icon": "💎",
    },
    {
        "id": "predictions_50",
        "title_el": "Market Watcher",
        "title_en": "Market Watcher",
        "desc_el": "Είδες 50+ AI predictions",
        "desc_en": "Viewed 50+ AI predictions",
        "icon": "👁️",
    },
]

_ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}


def get_achievement(achievement_id: str) -> Optional[Dict]:
    return _ACHIEVEMENT_MAP.get(achievement_id)


def _get_earned_with_dates(user_id: int) -> List[Dict]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT achievement_id, earned_at
                FROM user_achievements
                WHERE user_id = :uid
                ORDER BY earned_at ASC
                """
            ),
            {"uid": int(user_id)},
        ).fetchall()

        out = []
        for row in rows:
            a = get_achievement(str(row[0]))
            if not a:
                continue
            item = dict(a)
            item["earned_at"] = row[1].isoformat() if row[1] else None
            out.append(item)
        return out
    finally:
        db.close()


def _get_earned_ids(user_id: int) -> set:
    return {a["id"] for a in _get_earned_with_dates(user_id)}


def _award_if_new(user_id: int, achievement_id: str, earned: List[Dict]) -> None:
    if achievement_id not in _ACHIEVEMENT_MAP:
        return

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                INSERT INTO user_achievements (user_id, achievement_id)
                VALUES (:uid, :aid)
                ON CONFLICT (user_id, achievement_id) DO NOTHING
                RETURNING id, earned_at
                """
            ),
            {"uid": int(user_id), "aid": achievement_id},
        ).fetchone()
        db.commit()
        if row:
            achievement = dict(_ACHIEVEMENT_MAP[achievement_id])
            achievement["earned_at"] = row[1].isoformat() if row[1] else datetime.utcnow().isoformat()
            earned.append(achievement)
    except Exception:
        db.rollback()
    finally:
        db.close()


def _get_user_stats(user_id: int) -> Dict:
    history = paper_trading_service.get_trade_history(limit=5000, user_id=int(user_id))
    closed = [t for t in history if str(t.get("side", "")).upper() == "SELL"]
    wins = [t for t in closed if float(t.get("pnl", 0) or 0) > 0]
    total_trades = len(closed)
    win_rate = (len(wins) / total_trades) if total_trades > 0 else 0.0

    portfolio = paper_trading_service.get_portfolio(user_id=int(user_id))
    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "paper_pnl_pct": float(portfolio.get("total_pnl_percent", 0) or 0),
        "portfolio_value": float(portfolio.get("total_value", 0) or 0),
    }


def _update_login_streak(user_id: int) -> int:
    from database.models import UserProfile

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == int(user_id)).first()
        if not profile:
            profile = UserProfile(user_id=int(user_id))
            db.add(profile)
            db.flush()

        flags = dict(profile.behavior_flags_json or {})
        today = date.today()
        last_login_raw = flags.get("last_login_date")
        streak = int(flags.get("daily_login_streak", 0) or 0)

        last_login = None
        if isinstance(last_login_raw, str):
            try:
                last_login = date.fromisoformat(last_login_raw)
            except ValueError:
                last_login = None

        if last_login == today:
            # already counted today
            pass
        elif last_login and (today - last_login).days == 1:
            streak += 1
        else:
            streak = 1

        flags["last_login_date"] = today.isoformat()
        flags["daily_login_streak"] = streak
        profile.behavior_flags_json = flags
        db.commit()
        return streak
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()


def _increment_predictions_view_count(user_id: int, increment: int = 1) -> int:
    from database.models import UserProfile

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == int(user_id)).first()
        if not profile:
            profile = UserProfile(user_id=int(user_id))
            db.add(profile)
            db.flush()

        flags = dict(profile.behavior_flags_json or {})
        current = int(flags.get("predictions_view_count", 0) or 0)
        current += max(1, int(increment))
        flags["predictions_view_count"] = current
        profile.behavior_flags_json = flags
        db.commit()
        return current
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()


def check_and_award(user_id: int, event_type: str, data: Optional[Dict] = None) -> List[Dict]:
    """
    Called after significant events.
    event_type: trade_placed | trade_closed | auto_enabled | predictions_viewed | daily_login
    """
    payload = data or {}
    earned: List[Dict] = []

    if event_type == "trade_placed":
        _award_if_new(user_id, "first_trade", earned)

    if event_type == "trade_closed":
        if float(payload.get("pnl_pct", 0) or 0) > 0:
            _award_if_new(user_id, "first_profit", earned)

        stats = _get_user_stats(user_id)
        if stats["win_rate"] >= 0.80 and stats["total_trades"] >= 10:
            _award_if_new(user_id, "win_rate_80", earned)

        if stats["paper_pnl_pct"] >= 10.0:
            _award_if_new(user_id, "paper_profit_10", earned)

        if stats["portfolio_value"] >= 100.0:
            _award_if_new(user_id, "portfolio_100", earned)

    if event_type == "auto_enabled":
        _award_if_new(user_id, "auto_first", earned)

    if event_type == "predictions_viewed":
        seen = _increment_predictions_view_count(user_id, int(payload.get("count", 1) or 1))
        if seen >= 50:
            _award_if_new(user_id, "predictions_50", earned)

    if event_type == "daily_login":
        streak = _update_login_streak(user_id)
        if streak >= 7:
            _award_if_new(user_id, "streak_7", earned)

    for a in earned:
        send_push_to_user_id(
            int(user_id),
            title=f"🏆 {a['title_el']}",
            body=a["desc_el"],
            data={"screen": "/achievements", "type": "achievement", "achievement_id": a["id"]},
        )

    return earned


def get_achievements_overview(user_id: int) -> Dict:
    earned = _get_earned_with_dates(user_id)
    earned_ids = {a["id"] for a in earned}

    locked = []
    for a in ACHIEVEMENTS:
        if a["id"] in earned_ids:
            continue
        locked.append(
            {
                "id": a["id"],
                "title_el": a["title_el"],
                "title_en": a["title_en"],
                "desc_el": a["desc_el"],
                "desc_en": a["desc_en"],
                "icon": a["icon"],
            }
        )

    return {
        "earned": earned,
        "locked": locked,
        "total": len(ACHIEVEMENTS),
        "earned_count": len(earned),
    }
