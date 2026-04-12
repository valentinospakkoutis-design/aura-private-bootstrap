"""Social features service: leaderboard snapshots and referrals."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal
from services.paper_trading import paper_trading_service
from services.push_notifications import send_push_to_user_id

LEADERBOARD_PERIODS = ("weekly", "monthly", "alltime")


class SocialService:
    def get_display_name(self, user_id: int) -> str:
        """Anonymized deterministic username for leaderboard rows."""
        adjectives = ["Swift", "Bold", "Sharp", "Smart", "Quick", "Wise"]
        nouns = ["Trader", "Hawk", "Eagle", "Wolf", "Bull", "Bear"]

        uid = int(user_id or 0)
        adj = adjectives[uid % len(adjectives)]
        noun = nouns[(uid // len(adjectives)) % len(nouns)]
        return f"{adj}{noun}{uid % 100:02d}"

    def _db_available(self) -> bool:
        return callable(SessionLocal)

    def _ensure_schema(self) -> None:
        if not self._db_available():
            return
        db = SessionLocal()
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    display_name VARCHAR NOT NULL,
                    paper_pnl_pct FLOAT DEFAULT 0,
                    paper_trades INTEGER DEFAULT 0,
                    win_rate FLOAT DEFAULT 0,
                    period VARCHAR NOT NULL,
                    snapshot_date DATE DEFAULT CURRENT_DATE,
                    UNIQUE(user_id, period, snapshot_date)
                )
            """))
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id INTEGER REFERENCES users(id),
                    referred_id INTEGER REFERENCES users(id),
                    referral_code VARCHAR UNIQUE NOT NULL,
                    reward_given BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR UNIQUE"))
            db.execute(text("""
                UPDATE users
                SET referral_code = UPPER(SUBSTRING(MD5(id::text), 1, 8))
                WHERE referral_code IS NULL
            """))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _get_active_users(self) -> List[int]:
        if not self._db_available():
            return []
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT id
                FROM users
                WHERE COALESCE(is_active, true) = true
                ORDER BY id ASC
            """)).fetchall()
            return [int(r[0]) for r in rows if r and r[0] is not None]
        except Exception:
            return []
        finally:
            db.close()

    def _paper_stats(self, user_id: int) -> Dict:
        try:
            stats = paper_trading_service.get_statistics(user_id=user_id)
            return {
                "pnl_pct": float(stats.get("total_pnl_percent", 0.0) or 0.0),
                "total_trades": int(stats.get("total_trades", 0) or 0),
                "win_rate": float(stats.get("win_rate", 0.0) or 0.0),
            }
        except Exception:
            return {"pnl_pct": 0.0, "total_trades": 0, "win_rate": 0.0}

    def _upsert_leaderboard_row(
        self,
        user_id: int,
        display_name: str,
        pnl_pct: float,
        trades: int,
        win_rate: float,
        period: str,
        snapshot_date: Optional[date] = None,
    ) -> None:
        if not self._db_available():
            return

        snap_date = snapshot_date or date.today()
        db = SessionLocal()
        try:
            db.execute(
                text("""
                    INSERT INTO leaderboard_snapshots (
                        user_id, display_name, paper_pnl_pct, paper_trades, win_rate, period, snapshot_date
                    )
                    VALUES (
                        :user_id, :display_name, :paper_pnl_pct, :paper_trades, :win_rate, :period, :snapshot_date
                    )
                    ON CONFLICT (user_id, period, snapshot_date)
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        paper_pnl_pct = EXCLUDED.paper_pnl_pct,
                        paper_trades = EXCLUDED.paper_trades,
                        win_rate = EXCLUDED.win_rate
                """),
                {
                    "user_id": int(user_id),
                    "display_name": str(display_name),
                    "paper_pnl_pct": float(pnl_pct or 0.0),
                    "paper_trades": int(trades or 0),
                    "win_rate": float(win_rate or 0.0),
                    "period": str(period),
                    "snapshot_date": snap_date,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def update_leaderboard(self) -> Dict:
        """Scheduled job: build daily snapshots for weekly/monthly/alltime views."""
        self._ensure_schema()

        users = self._get_active_users()
        updated = 0

        for user_id in users:
            stats = self._paper_stats(user_id)
            display_name = self.get_display_name(user_id)

            for period in LEADERBOARD_PERIODS:
                self._upsert_leaderboard_row(
                    user_id=user_id,
                    display_name=display_name,
                    pnl_pct=stats["pnl_pct"],
                    trades=stats["total_trades"],
                    win_rate=stats["win_rate"],
                    period=period,
                )
                updated += 1

        return {
            "updated_rows": updated,
            "active_users": len(users),
            "snapshot_date": date.today().isoformat(),
        }

    def get_leaderboard(self, user_id: int, period: str = "weekly", limit: int = 50) -> Dict:
        self._ensure_schema()

        p = str(period or "weekly").lower()
        if p not in LEADERBOARD_PERIODS:
            p = "weekly"

        lim = max(1, min(int(limit or 50), 200))
        rankings: List[Dict] = []

        if not self._db_available():
            return {
                "rankings": rankings,
                "my_rank": None,
                "my_display_name": self.get_display_name(user_id),
                "period": p,
                "snapshot_date": date.today().isoformat(),
                "database_available": False,
            }

        db = SessionLocal()
        try:
            # Populate snapshot on demand if today's rowset is empty.
            exists = db.execute(
                text("""
                    SELECT COUNT(1)
                    FROM leaderboard_snapshots
                    WHERE period = :period AND snapshot_date = CURRENT_DATE
                """),
                {"period": p},
            ).scalar() or 0
            if int(exists) == 0:
                db.close()
                self.update_leaderboard()
                db = SessionLocal()

            rows = db.execute(
                text("""
                    SELECT display_name, paper_pnl_pct, paper_trades, win_rate, rank
                    FROM (
                        SELECT
                            user_id,
                            display_name,
                            paper_pnl_pct,
                            paper_trades,
                            win_rate,
                            RANK() OVER (ORDER BY paper_pnl_pct DESC, win_rate DESC, paper_trades DESC) AS rank
                        FROM leaderboard_snapshots
                        WHERE period = :period
                          AND snapshot_date = CURRENT_DATE
                    ) ranked
                    ORDER BY rank ASC
                    LIMIT :limit
                """),
                {"period": p, "limit": lim},
            ).mappings().all()

            rankings = [
                {
                    "display_name": str(r["display_name"]),
                    "paper_pnl_pct": float(r["paper_pnl_pct"] or 0.0),
                    "paper_trades": int(r["paper_trades"] or 0),
                    "win_rate": float(r["win_rate"] or 0.0),
                    "rank": int(r["rank"] or 0),
                }
                for r in rows
            ]

            my_rank_row = db.execute(
                text("""
                    SELECT rank
                    FROM (
                        SELECT
                            user_id,
                            RANK() OVER (ORDER BY paper_pnl_pct DESC, win_rate DESC, paper_trades DESC) AS rank
                        FROM leaderboard_snapshots
                        WHERE period = :period
                          AND snapshot_date = CURRENT_DATE
                    ) ranked
                    WHERE user_id = :user_id
                """),
                {"period": p, "user_id": int(user_id)},
            ).first()

            return {
                "rankings": rankings,
                "my_rank": int(my_rank_row[0]) if my_rank_row else None,
                "my_display_name": self.get_display_name(user_id),
                "period": p,
                "snapshot_date": date.today().isoformat(),
            }
        finally:
            db.close()

    def _ensure_user_referral_code(self, user_id: int) -> str:
        if not self._db_available():
            uid = int(user_id)
            digest = hashlib.md5(str(uid).encode("utf-8")).hexdigest().upper()
            return digest[:8]

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT referral_code FROM users WHERE id = :user_id"),
                {"user_id": int(user_id)},
            ).first()
            if not row:
                return ""

            existing = (row[0] or "").strip().upper()
            if existing:
                return existing

            generated = hashlib.md5(str(int(user_id)).encode("utf-8")).hexdigest().upper()[:8]
            db.execute(
                text("UPDATE users SET referral_code = :code WHERE id = :user_id"),
                {"code": generated, "user_id": int(user_id)},
            )
            db.commit()
            return generated
        except Exception:
            db.rollback()
            return ""
        finally:
            db.close()

    def get_referral_stats(self, user_id: int) -> Dict:
        self._ensure_schema()
        code = self._ensure_user_referral_code(user_id)

        if not self._db_available():
            return {
                "code": code,
                "total_referrals": 0,
                "rewards_earned": 0,
                "share_url": f"https://aura-app.com/join/{code}" if code else "https://aura-app.com/join",
                "database_available": False,
            }

        db = SessionLocal()
        try:
            total = db.execute(
                text("SELECT COUNT(1) FROM referrals WHERE referrer_id = :uid"),
                {"uid": int(user_id)},
            ).scalar() or 0
            rewards = db.execute(
                text("SELECT COUNT(1) FROM referrals WHERE referrer_id = :uid AND reward_given = true"),
                {"uid": int(user_id)},
            ).scalar() or 0
            return {
                "code": code,
                "total_referrals": int(total),
                "rewards_earned": int(rewards),
                "share_url": f"https://aura-app.com/join/{code}" if code else "https://aura-app.com/join",
            }
        finally:
            db.close()

    def _extend_subscription(self, user_id: int, days: int = 30) -> None:
        if not self._db_available():
            return

        db = SessionLocal()
        try:
            row = db.execute(
                text("""
                    SELECT id, tier, expires_at
                    FROM subscriptions
                    WHERE user_id = :uid
                    LIMIT 1
                """),
                {"uid": int(user_id)},
            ).first()

            now = datetime.utcnow()
            base = now
            if row and row[2] and row[2] > now:
                base = row[2]
            new_expiry = base + timedelta(days=int(days))

            if row:
                db.execute(
                    text("""
                        UPDATE subscriptions
                        SET
                            tier = CASE WHEN tier = 'elite' THEN 'elite' ELSE 'pro' END,
                            is_active = true,
                            expires_at = :expires_at,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": int(row[0]), "expires_at": new_expiry},
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO subscriptions (user_id, tier, is_active, started_at, expires_at, payment_provider, created_at, updated_at)
                        VALUES (:uid, 'pro', true, NOW(), :expires_at, 'referral_reward', NOW(), NOW())
                    """),
                    {"uid": int(user_id), "expires_at": new_expiry},
                )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def apply_referral(self, referral_code: str, new_user_id: int) -> Dict:
        self._ensure_schema()
        code = str(referral_code or "").strip().upper()
        if not code:
            return {"success": False, "message": "Referral code is required."}

        if not self._db_available():
            return {"success": False, "message": "Referral service unavailable."}

        db = SessionLocal()
        try:
            referrer = db.execute(
                text("SELECT id, referral_code FROM users WHERE referral_code = :code LIMIT 1"),
                {"code": code},
            ).first()
            if not referrer:
                return {"success": False, "message": "Invalid referral code."}

            referrer_id = int(referrer[0])
            if referrer_id == int(new_user_id):
                return {"success": False, "message": "Cannot use your own referral code."}

            existing = db.execute(
                text("SELECT id FROM referrals WHERE referred_id = :rid LIMIT 1"),
                {"rid": int(new_user_id)},
            ).first()
            if existing:
                return {"success": False, "message": "Referral already applied for this account."}

            # Keep one row per referred user while satisfying DB unique(referral_code).
            referral_token = f"{code}-{int(new_user_id)}"
            db.execute(
                text("""
                    INSERT INTO referrals (referrer_id, referred_id, referral_code, reward_given, created_at)
                    VALUES (:referrer_id, :referred_id, :referral_code, true, NOW())
                """),
                {
                    "referrer_id": referrer_id,
                    "referred_id": int(new_user_id),
                    "referral_code": referral_token,
                },
            )
            db.commit()

            self._extend_subscription(referrer_id, days=30)
            send_push_to_user_id(
                referrer_id,
                title="🎉 Νέος φίλος στο AURA!",
                body="Κέρδισες 1 μήνα PRO δωρεάν!",
                data={"screen": "/referral", "type": "referral_reward"},
            )

            return {"success": True, "message": "Referral applied successfully. Reward granted."}
        except Exception:
            db.rollback()
            return {"success": False, "message": "Failed to apply referral code."}
        finally:
            db.close()


social_service = SocialService()
