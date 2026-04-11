"""Circuit breaker service for auto-trading safety rules."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal


DAILY_LOSS_PCT = 5.0
WEEKLY_LOSS_PCT = 10.0
CONSECUTIVE_LOSSES_LIMIT = 3


class CircuitBreakerService:
    def _ensure_table(self):
        """Create table/indexes lazily to avoid runtime 500s on brownfield deploys."""
        db = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        rule_id VARCHAR NOT NULL,
                        reason VARCHAR NOT NULL,
                        tripped_at TIMESTAMP DEFAULT NOW(),
                        resume_at TIMESTAMP NOT NULL,
                        reset_manually BOOLEAN DEFAULT FALSE
                    )
                    """
                )
            )
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_user_id ON circuit_breaker_events (user_id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_circuit_breaker_events_tripped_at ON circuit_breaker_events (tripped_at DESC)"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _parse_ts(self, value) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        try:
            raw = str(value).strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return datetime.fromisoformat(raw).replace(tzinfo=None)
        except Exception:
            return None

    def _get_active_event(self, user_id: int) -> Optional[Dict]:
        self._ensure_table()
        db = SessionLocal()
        try:
            row = db.execute(
                text(
                    """
                    SELECT id, rule_id, reason, tripped_at, resume_at
                    FROM circuit_breaker_events
                    WHERE user_id = :user_id
                      AND reset_manually = FALSE
                      AND resume_at > NOW()
                    ORDER BY tripped_at DESC
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).mappings().first()
            return dict(row) if row else None
        except Exception:
            return None
        finally:
            db.close()

    def _insert_event(self, user_id: int, rule_id: str, reason: str, pause_minutes: int) -> Dict:
        self._ensure_table()
        db = SessionLocal()
        try:
            row = db.execute(
                text(
                    """
                    INSERT INTO circuit_breaker_events (user_id, rule_id, reason, resume_at)
                    VALUES (:user_id, :rule_id, :reason, NOW() + (:pause_minutes || ' minutes')::interval)
                    RETURNING id, rule_id, reason, tripped_at, resume_at
                    """
                ),
                {
                    "user_id": user_id,
                    "rule_id": rule_id,
                    "reason": reason,
                    "pause_minutes": int(max(1, pause_minutes)),
                },
            ).mappings().first()
            db.commit()
            return dict(row)
        except Exception:
            db.rollback()
            return {
                "id": None,
                "rule_id": rule_id,
                "reason": reason,
                "tripped_at": datetime.utcnow().isoformat(),
                "resume_at": (datetime.utcnow() + timedelta(minutes=int(max(1, pause_minutes)))).isoformat(),
            }
        finally:
            db.close()

    def get_state(self, user_id: int) -> Dict:
        event = self._get_active_event(user_id)
        if not event:
            return {
                "state": "active",
                "reason": None,
                "resume_at": None,
                "minutes_remaining": 0,
            }

        resume_at = self._parse_ts(event.get("resume_at"))
        minutes_remaining = 0
        if resume_at:
            minutes_remaining = max(0, int((resume_at - datetime.utcnow()).total_seconds() // 60))

        return {
            "state": "paused",
            "reason": event.get("reason"),
            "rule_id": event.get("rule_id"),
            "resume_at": event.get("resume_at"),
            "minutes_remaining": minutes_remaining,
        }

    def reset(self, user_id: int) -> bool:
        self._ensure_table()
        db = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    UPDATE circuit_breaker_events
                    SET reset_manually = TRUE,
                        resume_at = NOW()
                    WHERE user_id = :user_id
                      AND reset_manually = FALSE
                      AND resume_at > NOW()
                    """
                ),
                {"user_id": user_id},
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            return True
        finally:
            db.close()

    def evaluate_and_trip(self, user_id: int, closed_trades: List[dict], equity_reference: float) -> Dict:
        state = self.get_state(user_id)
        if state.get("state") == "paused":
            return {"tripped": False, "state": state, "already_paused": True}

        now = datetime.utcnow()
        day_start = now - timedelta(hours=24)
        week_start = now - timedelta(days=7)
        hour_start = now - timedelta(hours=1)

        normalized = []
        for tr in closed_trades or []:
            closed_at = self._parse_ts(tr.get("closed_at"))
            pnl = float(tr.get("pnl") or 0.0)
            if not closed_at:
                continue
            normalized.append({"closed_at": closed_at, "pnl": pnl})

        base = max(float(equity_reference or 0.0), 1.0)
        daily_loss_abs = abs(sum(min(t["pnl"], 0.0) for t in normalized if t["closed_at"] >= day_start))
        weekly_loss_abs = abs(sum(min(t["pnl"], 0.0) for t in normalized if t["closed_at"] >= week_start))

        daily_loss_pct = (daily_loss_abs / base) * 100.0
        weekly_loss_pct = (weekly_loss_abs / base) * 100.0

        in_last_hour = [t for t in normalized if t["closed_at"] >= hour_start]
        in_last_hour.sort(key=lambda x: x["closed_at"], reverse=True)
        consecutive_losses = 0
        for t in in_last_hour:
            if t["pnl"] < 0:
                consecutive_losses += 1
            else:
                break

        if daily_loss_pct > DAILY_LOSS_PCT:
            reason = f"Daily loss exceeded {DAILY_LOSS_PCT:.1f}% in 24h ({daily_loss_pct:.2f}%)"
            event = self._insert_event(user_id, "daily_loss_24h", reason, pause_minutes=24 * 60)
            return {"tripped": True, "event": event, "reason": reason}

        if weekly_loss_pct > WEEKLY_LOSS_PCT:
            reason = f"Weekly loss exceeded {WEEKLY_LOSS_PCT:.1f}% in 7d ({weekly_loss_pct:.2f}%)"
            event = self._insert_event(user_id, "weekly_loss_7d", reason, pause_minutes=7 * 24 * 60)
            return {"tripped": True, "event": event, "reason": reason}

        if consecutive_losses >= CONSECUTIVE_LOSSES_LIMIT:
            reason = f"{consecutive_losses} consecutive losses within the last hour"
            event = self._insert_event(user_id, "consecutive_losses_1h", reason, pause_minutes=60)
            return {"tripped": True, "event": event, "reason": reason}

        return {"tripped": False, "state": self.get_state(user_id)}


circuit_breaker_service = CircuitBreakerService()
