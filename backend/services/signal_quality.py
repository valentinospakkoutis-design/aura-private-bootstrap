"""
Signal Quality Filter — ranks assets by historical profitability.

Computes a composite score per asset from prediction_outcomes:
    composite = win_rate_factor × avg_pnl_factor × sample_confidence

Only assets above the threshold are allowed for auto-trading.
Self-adapting: recomputes as more outcome data accumulates.
"""

import logging
from typing import Dict, Optional, Set
from datetime import datetime

from sqlalchemy import text
from database.connection import SessionLocal

logger = logging.getLogger(__name__)

# Cache to avoid hitting DB on every trade decision
_CACHE: Dict[str, Dict] = {}
_CACHE_TS: Optional[datetime] = None
_CACHE_TTL_SECONDS = 3600  # refresh hourly


class SignalQualityService:
    # Minimum samples before we trust an asset's stats
    MIN_SAMPLES = 20
    # Composite score threshold for allowing trades
    SCORE_THRESHOLD = 0.30
    # Minimum win rate floor (never trade assets below this)
    MIN_WIN_RATE = 55.0

    def _compute_scores(self) -> Dict[str, Dict]:
        """Compute composite score per asset from clean 7d outcomes."""
        if not callable(SessionLocal):
            return {}
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT symbol,
                       COUNT(*) as trades,
                       AVG(pnl_7d_pct) as avg_pnl,
                       (SUM(CASE WHEN was_correct_7d THEN 1 ELSE 0 END)::float
                        / NULLIF(COUNT(*), 0) * 100) as win_rate
                FROM prediction_outcomes
                WHERE pnl_7d_pct IS NOT NULL
                  AND was_correct_7d IS NOT NULL
                  AND confidence >= 0.70
                GROUP BY symbol
                HAVING COUNT(*) >= :min_samples
            """), {"min_samples": self.MIN_SAMPLES}).mappings().all()

            scores = {}
            for r in rows:
                sym = str(r["symbol"])
                trades = int(r["trades"])
                avg_pnl = float(r["avg_pnl"] or 0.0)
                win_rate = float(r["win_rate"] or 0.0)

                # Win rate factor: 0 at 50%, 1.0 at 100% (linear above coin-flip)
                win_factor = max(0.0, (win_rate - 50.0) / 50.0)

                # PnL factor: normalized, capped at 5% avg per trade = 1.0
                pnl_factor = max(0.0, min(1.0, avg_pnl / 5.0))

                # Sample confidence: more trades = more trust, plateau at 60
                sample_factor = min(1.0, trades / 60.0)

                composite = win_factor * (0.5 + 0.5 * pnl_factor) * (0.7 + 0.3 * sample_factor)

                scores[sym] = {
                    "symbol": sym,
                    "trades": trades,
                    "avg_pnl": round(avg_pnl, 3),
                    "win_rate": round(win_rate, 1),
                    "composite_score": round(composite, 3),
                    "allowed": composite >= self.SCORE_THRESHOLD and win_rate >= self.MIN_WIN_RATE,
                }
            return scores
        except Exception as e:
            logger.warning(f"[signal_quality] compute failed: {e}")
            return {}
        finally:
            db.close()

    def _get_scores(self, force: bool = False) -> Dict[str, Dict]:
        global _CACHE, _CACHE_TS
        now = datetime.utcnow()
        if (not force and _CACHE_TS is not None
                and (now - _CACHE_TS).total_seconds() < _CACHE_TTL_SECONDS):
            return _CACHE
        _CACHE = self._compute_scores()
        _CACHE_TS = now
        logger.info(f"[signal_quality] recomputed scores for {len(_CACHE)} assets")
        return _CACHE

    def is_allowed(self, symbol: str) -> bool:
        """Return True if asset has proven profitable enough to trade."""
        scores = self._get_scores()
        # If we have no data yet for this asset, allow (cold start) — be permissive
        if symbol not in scores:
            return True
        return bool(scores[symbol]["allowed"])

    def get_score(self, symbol: str) -> Optional[Dict]:
        return self._get_scores().get(symbol)

    def get_all_scores(self) -> Dict[str, Dict]:
        return self._get_scores()

    def get_allowed_assets(self) -> Set[str]:
        return {s for s, v in self._get_scores().items() if v["allowed"]}


signal_quality_service = SignalQualityService()
