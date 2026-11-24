"""
Durable copy of the trading engine's open positions.

The engine keeps open positions in memory. After a restart it can recover WHAT
is held from the broker, but not what it knew about each holding: the stop it
had trailed up, which take-profit steps were already done, when and why the
position was opened. This store keeps that, one row per (user, symbol).

The broker stays the source of truth for what is actually held: the engine
restores from here and then reconciles against the broker, so a stale row can
never create a position that does not exist.

Storage failures are logged and swallowed — losing the copy must never stop
the engine from managing positions.
"""

import json
import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

_CREATE = """
CREATE TABLE IF NOT EXISTS engine_positions (
    user_id    INTEGER     NOT NULL,
    symbol     TEXT        NOT NULL,
    data       TEXT        NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
)
"""


def _default_session_factory():
    from database.connection import SessionLocal
    return SessionLocal


class PositionStore:
    def __init__(self, session_factory: Optional[Callable] = None):
        self._session_factory = session_factory
        self._table_ready = False
        self._last_saved: Dict[int, str] = {}   # user_id -> serialized positions

    def _session(self):
        factory = self._session_factory or _default_session_factory()
        return factory() if factory else None

    def _ensure_table(self, db) -> None:
        if self._table_ready:
            return
        from sqlalchemy import text
        db.execute(text(_CREATE))
        db.commit()
        self._table_ready = True

    @staticmethod
    def _serialize(positions: Dict[str, dict]) -> Dict[str, str]:
        return {str(symbol): json.dumps(data, sort_keys=True, default=str)
                for symbol, data in positions.items()}

    def load(self, user_id: int) -> Dict[str, dict]:
        """Positions saved for this user; empty if none or if storage is unavailable."""
        try:
            db = self._session()
            if db is None:
                return {}
            try:
                from sqlalchemy import text
                self._ensure_table(db)
                rows = db.execute(text("SELECT symbol, data FROM engine_positions WHERE user_id = :u"),
                                  {"u": int(user_id)}).fetchall()
            finally:
                db.close()
            positions = {}
            for symbol, data in rows:
                try:
                    positions[symbol] = json.loads(data)
                except Exception:
                    logger.warning(f"[position-store] user={user_id} {symbol}: unreadable row ignored")
            self._last_saved[int(user_id)] = json.dumps(self._serialize(positions), sort_keys=True)
            return positions
        except Exception as e:
            logger.warning(f"[position-store] load failed for user={user_id}: {type(e).__name__}: {e}")
            return {}

    def save(self, user_id: int, positions: Dict[str, dict]) -> bool:
        """Make the stored rows equal to `positions`. Returns True if anything was written."""
        try:
            rows = self._serialize(positions)
            fingerprint = json.dumps(rows, sort_keys=True)
            if self._last_saved.get(int(user_id)) == fingerprint:
                return False
            db = self._session()
            if db is None:
                return False
            try:
                from sqlalchemy import text
                self._ensure_table(db)
                existing = {r[0] for r in db.execute(
                    text("SELECT symbol FROM engine_positions WHERE user_id = :u"),
                    {"u": int(user_id)}).fetchall()}
                for symbol in existing - set(rows):
                    db.execute(text("DELETE FROM engine_positions WHERE user_id = :u AND symbol = :s"),
                               {"u": int(user_id), "s": symbol})
                for symbol, data in rows.items():
                    db.execute(text(
                        "INSERT INTO engine_positions (user_id, symbol, data, updated_at) "
                        "VALUES (:u, :s, :d, NOW()) "
                        "ON CONFLICT (user_id, symbol) DO UPDATE SET data = :d, updated_at = NOW()"),
                        {"u": int(user_id), "s": symbol, "d": data})
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            self._last_saved[int(user_id)] = fingerprint
            return True
        except Exception as e:
            logger.warning(f"[position-store] save failed for user={user_id}: {type(e).__name__}: {e}")
            return False


position_store = PositionStore()
