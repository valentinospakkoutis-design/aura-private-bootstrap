from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import desc

from database.connection import SessionLocal
from database.models import DrawdownEvent, PnLSnapshot, RiskShutdownEvent
from ops.kill_switch import kill_switch_manager
from ops.observability import runtime_monitor


@dataclass
class RiskGovernorConfig:
    caution_drawdown_pct: float = float(os.getenv("RISK_CAUTION_DRAWDOWN_PCT", "3.0"))
    defense_drawdown_pct: float = float(os.getenv("RISK_DEFENSE_DRAWDOWN_PCT", "5.0"))
    preservation_drawdown_pct: float = float(os.getenv("RISK_PRESERVATION_DRAWDOWN_PCT", "8.0"))
    hard_shutdown_drawdown_pct: float = float(os.getenv("RISK_HARD_SHUTDOWN_DRAWDOWN_PCT", "10.0"))
    daily_loss_limit_pct: float = float(os.getenv("RISK_DAILY_LOSS_LIMIT_PCT", "4.0"))
    session_loss_limit_pct: float = float(os.getenv("RISK_SESSION_LOSS_LIMIT_PCT", "6.0"))
    auto_shutdown_activates_kill_switch: bool = os.getenv("RISK_AUTO_SHUTDOWN_ENABLE", "true").strip().lower() in {"1", "true", "yes", "on"}
    auto_shutdown_cancel_open_orders: bool = os.getenv("RISK_AUTO_SHUTDOWN_CANCEL_OPEN_ORDERS", "false").strip().lower() in {"1", "true", "yes", "on"}
    preservation_blocks_new_trades: bool = os.getenv("RISK_PRESERVATION_BLOCK_NEW_TRADES", "true").strip().lower() in {"1", "true", "yes", "on"}
    session_bucket_hours: int = int(os.getenv("RISK_SESSION_BUCKET_HOURS", "8"))


class RiskGovernorService:
    STATES = ["NORMAL", "CAUTION", "DEFENSE", "PRESERVATION", "SHUTDOWN"]

    def __init__(self, session_factory=SessionLocal, config: Optional[RiskGovernorConfig] = None):
        self._session_factory = session_factory
        self.config = config or RiskGovernorConfig()

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    def _session_bucket(self, now: datetime) -> str:
        bucket = int(now.hour / max(self.config.session_bucket_hours, 1))
        return f"{now.date().isoformat()}-B{bucket}"

    def _latest_snapshot(self, db: Any, mode: str) -> Optional[PnLSnapshot]:
        return (
            db.query(PnLSnapshot)
            .filter(PnLSnapshot.mode == mode)
            .order_by(desc(PnLSnapshot.timestamp), desc(PnLSnapshot.id))
            .first()
        )

    @staticmethod
    def _daily_pct(daily_pnl: float, day_start_equity: float) -> float:
        if day_start_equity <= 0:
            return 0.0
        return abs(min(daily_pnl, 0.0)) / day_start_equity * 100.0

    @staticmethod
    def _session_pct(session_pnl: float, session_start_equity: float) -> float:
        if session_start_equity <= 0:
            return 0.0
        return abs(min(session_pnl, 0.0)) / session_start_equity * 100.0

    def _determine_state(self, *, drawdown_pct: float, daily_loss_pct: float, session_loss_pct: float) -> Tuple[str, str]:
        if (
            drawdown_pct >= self.config.hard_shutdown_drawdown_pct
            or daily_loss_pct >= self.config.daily_loss_limit_pct
            or session_loss_pct >= self.config.session_loss_limit_pct
        ):
            if drawdown_pct >= self.config.hard_shutdown_drawdown_pct:
                return "SHUTDOWN", "hard_drawdown_threshold"
            if daily_loss_pct >= self.config.daily_loss_limit_pct:
                return "SHUTDOWN", "daily_loss_limit"
            return "SHUTDOWN", "session_loss_limit"

        if drawdown_pct >= self.config.preservation_drawdown_pct:
            return "PRESERVATION", "preservation_drawdown_threshold"
        if drawdown_pct >= self.config.defense_drawdown_pct:
            return "DEFENSE", "defense_drawdown_threshold"
        if drawdown_pct >= self.config.caution_drawdown_pct:
            return "CAUTION", "caution_drawdown_threshold"
        return "NORMAL", "within_limits"

    def restore_enforcement(self) -> None:
        try:
            status = self.get_status(mode="live")
            if status.get("shutdown_active") and self.config.auto_shutdown_activates_kill_switch:
                kill_switch_manager.activate(
                    actor="risk_governor",
                    scope="global",
                    reason="restored_shutdown_state",
                    emergency=True,
                    cancel_open_orders=self.config.auto_shutdown_cancel_open_orders,
                )
        except Exception:
            runtime_monitor.log_event(event="risk_governor_restore_failed", level="error")

    def can_execute(self, *, mode: str, symbol: Optional[str] = None, strategy: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        blocked, reason = kill_switch_manager.is_blocked(symbol=symbol or "GLOBAL", strategy=strategy)
        if blocked:
            return False, reason

        try:
            status = self.get_status(mode=mode)
        except Exception:
            runtime_monitor.log_event(event="risk_governor_status_unavailable", level="error", mode=mode)
            return True, None

        state = status.get("risk_state", "NORMAL")
        if state == "SHUTDOWN":
            return False, "RISK_SHUTDOWN_ACTIVE"
        if state == "PRESERVATION" and self.config.preservation_blocks_new_trades:
            return False, "RISK_PRESERVATION_ACTIVE"
        return True, None

    def update_pnl(
        self,
        *,
        mode: str,
        equity: float,
        realized_delta: float = 0.0,
        unrealized_pnl: float = 0.0,
        source: str,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        trading_day = now.date().isoformat()
        session_id = self._session_bucket(now)

        db = self._session_factory()
        try:
            last = self._latest_snapshot(db, mode)

            realized_pnl = (float(last.realized_pnl) if last else 0.0) + float(realized_delta)
            peak_equity = max(float(last.peak_equity) if last else float(equity), float(equity))
            drawdown_pct = ((peak_equity - float(equity)) / peak_equity * 100.0) if peak_equity > 0 else 0.0
            max_drawdown_pct = max(float(last.max_drawdown_pct) if last else 0.0, drawdown_pct)

            day_start_snapshot = (
                db.query(PnLSnapshot)
                .filter(PnLSnapshot.mode == mode, PnLSnapshot.trading_day == trading_day)
                .order_by(PnLSnapshot.timestamp.asc(), PnLSnapshot.id.asc())
                .first()
            )
            session_start_snapshot = (
                db.query(PnLSnapshot)
                .filter(PnLSnapshot.mode == mode, PnLSnapshot.session_id == session_id)
                .order_by(PnLSnapshot.timestamp.asc(), PnLSnapshot.id.asc())
                .first()
            )

            day_start_equity = float(day_start_snapshot.equity) if day_start_snapshot else float(last.equity) if last else float(equity)
            session_start_equity = float(session_start_snapshot.equity) if session_start_snapshot else float(last.equity) if last else float(equity)

            daily_pnl = float(equity) - day_start_equity
            session_pnl = float(equity) - session_start_equity

            rolling_cutoff = now - timedelta(days=7)
            rolling_base = (
                db.query(PnLSnapshot)
                .filter(PnLSnapshot.mode == mode, PnLSnapshot.timestamp >= rolling_cutoff)
                .order_by(PnLSnapshot.timestamp.asc(), PnLSnapshot.id.asc())
                .first()
            )
            rolling_7d_pnl = float(equity) - (float(rolling_base.equity) if rolling_base else float(equity))

            if realized_delta > 0:
                win_streak = (int(last.win_streak) if last else 0) + 1
                loss_streak = 0
            elif realized_delta < 0:
                loss_streak = (int(last.loss_streak) if last else 0) + 1
                win_streak = 0
            else:
                win_streak = int(last.win_streak) if last else 0
                loss_streak = int(last.loss_streak) if last else 0

            daily_loss_pct = self._daily_pct(daily_pnl=daily_pnl, day_start_equity=day_start_equity)
            session_loss_pct = self._session_pct(session_pnl=session_pnl, session_start_equity=session_start_equity)
            new_state, trigger_reason = self._determine_state(
                drawdown_pct=drawdown_pct,
                daily_loss_pct=daily_loss_pct,
                session_loss_pct=session_loss_pct,
            )
            previous_state = str(last.risk_state) if last else "NORMAL"
            shutdown_active = new_state == "SHUTDOWN"

            kill_switch_activated = False
            if shutdown_active and self.config.auto_shutdown_activates_kill_switch:
                kill_switch_manager.activate(
                    actor="risk_governor",
                    scope="global",
                    reason=trigger_reason,
                    emergency=True,
                    cancel_open_orders=self.config.auto_shutdown_cancel_open_orders,
                )
                kill_switch_activated = True

            snapshot = PnLSnapshot(
                timestamp=now,
                mode=mode,
                equity=float(equity),
                realized_pnl=realized_pnl,
                unrealized_pnl=float(unrealized_pnl),
                daily_pnl=daily_pnl,
                session_pnl=session_pnl,
                rolling_7d_pnl=rolling_7d_pnl,
                peak_equity=peak_equity,
                drawdown_pct=drawdown_pct,
                max_drawdown_pct=max_drawdown_pct,
                risk_state=new_state,
                shutdown_active=shutdown_active,
                win_streak=win_streak,
                loss_streak=loss_streak,
                source=source,
                trading_day=trading_day,
                session_id=session_id,
            )
            db.add(snapshot)

            if previous_state != new_state:
                db.add(
                    DrawdownEvent(
                        timestamp=now,
                        mode=mode,
                        previous_state=previous_state,
                        new_state=new_state,
                        drawdown_pct=drawdown_pct,
                        trigger_reason=trigger_reason,
                        daily_pnl=daily_pnl,
                        session_pnl=session_pnl,
                    )
                )
                runtime_monitor.record_drawdown_state_change(mode=mode, previous_state=previous_state, new_state=new_state, drawdown_pct=drawdown_pct)

            if new_state in {"PRESERVATION", "SHUTDOWN"}:
                db.add(
                    RiskShutdownEvent(
                        timestamp=now,
                        mode=mode,
                        state=new_state,
                        trigger_reason=trigger_reason,
                        drawdown_pct=drawdown_pct,
                        daily_pnl=daily_pnl,
                        session_pnl=session_pnl,
                        symbol=symbol,
                        strategy=strategy,
                        kill_switch_activated=kill_switch_activated,
                        cancel_open_orders=bool(self.config.auto_shutdown_cancel_open_orders),
                    )
                )
                runtime_monitor.record_shutdown_trigger(mode=mode, state=new_state, reason=trigger_reason, drawdown_pct=drawdown_pct)

            if new_state == "DEFENSE":
                runtime_monitor.record_defense_mode(mode=mode, drawdown_pct=drawdown_pct)
            if loss_streak >= 3:
                runtime_monitor.record_losing_streak_warning(mode=mode, loss_streak=loss_streak)
            if daily_loss_pct >= max(0.7 * self.config.daily_loss_limit_pct, 1.0):
                runtime_monitor.record_rapid_pnl_deterioration(mode=mode, daily_loss_pct=daily_loss_pct)

            db.commit()

            return {
                "mode": mode,
                "equity": float(equity),
                "realized_pnl": realized_pnl,
                "unrealized_pnl": float(unrealized_pnl),
                "daily_pnl": daily_pnl,
                "session_pnl": session_pnl,
                "rolling_7d_pnl": rolling_7d_pnl,
                "drawdown_pct": drawdown_pct,
                "max_drawdown_pct": max_drawdown_pct,
                "risk_state": new_state,
                "shutdown_active": shutdown_active,
                "trigger_reason": trigger_reason,
                "kill_switch_activated": kill_switch_activated,
                "timestamp": now.isoformat(),
            }
        finally:
            db.close()

    def get_status(self, *, mode: str) -> Dict[str, Any]:
        db = self._session_factory()
        try:
            latest = self._latest_snapshot(db, mode)
            if latest is None:
                return {
                    "mode": mode,
                    "current_equity": 0.0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "daily_pnl": 0.0,
                    "session_pnl": 0.0,
                    "rolling_7d_pnl": 0.0,
                    "drawdown_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                    "risk_state": "NORMAL",
                    "shutdown_active": False,
                    "kill_switch_status": kill_switch_manager.status(),
                    "trigger_history": [],
                    "timestamp": self._now().isoformat(),
                }

            triggers = (
                db.query(RiskShutdownEvent)
                .filter(RiskShutdownEvent.mode == mode)
                .order_by(RiskShutdownEvent.timestamp.desc(), RiskShutdownEvent.id.desc())
                .limit(20)
                .all()
            )

            return {
                "mode": mode,
                "current_equity": float(latest.equity),
                "realized_pnl": float(latest.realized_pnl),
                "unrealized_pnl": float(latest.unrealized_pnl),
                "daily_pnl": float(latest.daily_pnl),
                "session_pnl": float(latest.session_pnl),
                "rolling_7d_pnl": float(latest.rolling_7d_pnl),
                "peak_equity": float(latest.peak_equity),
                "drawdown_pct": float(latest.drawdown_pct),
                "max_drawdown_pct": float(latest.max_drawdown_pct),
                "risk_state": str(latest.risk_state),
                "shutdown_active": bool(latest.shutdown_active),
                "win_streak": int(latest.win_streak),
                "loss_streak": int(latest.loss_streak),
                "kill_switch_status": kill_switch_manager.status(),
                "trigger_history": [
                    {
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                        "state": event.state,
                        "trigger_reason": event.trigger_reason,
                        "drawdown_pct": float(event.drawdown_pct),
                        "daily_pnl": float(event.daily_pnl),
                        "session_pnl": float(event.session_pnl),
                        "kill_switch_activated": bool(event.kill_switch_activated),
                    }
                    for event in triggers
                ],
                "timestamp": self._now().isoformat(),
            }
        finally:
            db.close()


risk_governor_service = RiskGovernorService()
