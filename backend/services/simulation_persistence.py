"""
Simulation Persistence Service for AURA.
Stores simulation/backtest runs with full config (reproducibility),
summary results, and optional equity curve timeseries.

All tables are append-only.

Storage volume notes:
  - persistent_simulation_runs: 1 row per run. Config JSON is typically <2KB.
  - simulation_results: 1 row per run. Lightweight summary.
  - simulation_result_timeseries: N rows per run (1 per trade/day). A 30-day
    sim with 33 symbols produces ~33 points. A 365-day sim could produce
    ~365 points. At 100 runs/user/month, this is ~3K-36K rows/month.
    Consider pruning timeseries older than 6 months for inactive runs.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_RUN_TYPES = {"backtest", "paper_simulation", "what_if"}
VALID_STATUSES = {"queued", "running", "completed", "failed"}


def save_simulation_run(
    user_id: int,
    strategy_id: str,
    run_type: str,
    symbols: List[str],
    initial_capital: float,
    config: dict,
    disclaimer: str,
    result: dict,
    timeframe_days: int = 30,
    assumptions: Optional[dict] = None,
) -> Optional[int]:
    """
    Save a completed simulation run with results.
    Returns the run ID or None on failure.

    Args:
        user_id: user who ran the simulation
        strategy_id: strategy name (ai_follow, conservative_ai, etc.)
        run_type: backtest / paper_simulation / what_if
        symbols: list of symbols used
        initial_capital: starting capital
        config: full input params for reproducibility
        disclaimer: mandatory disclaimer text
        result: output from run_simulation() — contains PnL, trades, metrics
        timeframe_days: simulation timeframe
        assumptions: optional slippage/fee assumptions
    """
    if run_type not in VALID_RUN_TYPES:
        run_type = "backtest"

    try:
        from database.connection import SessionLocal
        from database.models import (
            PersistentSimulationRun, SimulationResult, SimulationResultTimeseries,
        )

        db = SessionLocal()
        now = datetime.utcnow()

        # ── 1. Insert run ──
        run = PersistentSimulationRun(
            user_id=user_id,
            strategy_id=strategy_id,
            run_type=run_type,
            symbol_universe_json=symbols,
            timeframe_start=now - timedelta(days=timeframe_days),
            timeframe_end=now,
            initial_capital=initial_capital,
            config_json=config,
            assumptions_json=assumptions or {},
            disclaimer_text=disclaimer,
            status="completed",
            started_at=now,
            completed_at=now,
        )
        db.add(run)
        db.flush()

        # ── 2. Insert result summary ──
        executed_trades = [t for t in result.get("trades", []) if t.get("side") not in ("SKIP", "HOLD")]
        avg_trade_return = 0
        if executed_trades:
            avg_trade_return = sum(t.get("pnl_pct", 0) for t in executed_trades) / len(executed_trades)

        # Build summary text
        summary = (
            f"{result.get('strategy_label', strategy_id)}: "
            f"{'profit' if result.get('pnl', 0) >= 0 else 'loss'} of "
            f"${abs(result.get('pnl', 0)):.2f} ({result.get('pnl_pct', 0):+.1f}%) "
            f"over {timeframe_days}d with {result.get('total_trades', 0)} trades. "
            f"Sharpe: {result.get('sharpe_ratio', 0):.2f}, "
            f"Max DD: {result.get('max_drawdown_pct', 0):.1f}%, "
            f"Win rate: {result.get('win_rate_pct', 0):.0f}%."
        )

        db.add(SimulationResult(
            simulation_run_id=run.id,
            total_return_pct=result.get("pnl_pct"),
            annualized_return_pct=(
                result.get("pnl_pct", 0) * (365 / max(timeframe_days, 1))
                if result.get("pnl_pct") is not None else None
            ),
            max_drawdown_pct=result.get("max_drawdown_pct"),
            sharpe_ratio=result.get("sharpe_ratio"),
            win_rate_pct=result.get("win_rate_pct"),
            total_trades=result.get("total_trades"),
            avg_trade_return_pct=round(avg_trade_return, 3),
            pnl_value=result.get("pnl"),
            risk_metrics_json={
                "profit_factor": result.get("profit_factor"),
                "avg_win": result.get("avg_win"),
                "avg_loss": result.get("avg_loss"),
                "winning_trades": result.get("winning_trades"),
                "losing_trades": result.get("losing_trades"),
                "skipped_trades": result.get("skipped_trades"),
            },
            summary_text=summary,
        ))

        # ── 3. Insert equity timeseries from trades ──
        equity = initial_capital
        for i, trade in enumerate(result.get("trades", [])):
            if trade.get("side") in ("SKIP", "HOLD"):
                continue
            equity += trade.get("pnl", 0)
            peak = max(initial_capital, equity)
            dd = ((peak - equity) / peak * 100) if peak > 0 else 0
            db.add(SimulationResultTimeseries(
                simulation_run_id=run.id,
                point_timestamp=now - timedelta(days=timeframe_days) + timedelta(
                    days=(i + 1) * timeframe_days / max(len(result.get("trades", [])), 1)
                ),
                equity_value=round(equity, 2),
                drawdown_pct=round(dd, 2),
            ))

        db.commit()
        run_id = run.id
        db.close()

        logger.info(
            f"[sim_persist] Saved run #{run_id}: {strategy_id} | "
            f"PnL={result.get('pnl', 0):+.2f} | trades={result.get('total_trades', 0)}"
        )

        try:
            from services.audit_trail import emit_audit
            pnl = result.get("pnl", 0)
            emit_audit(
                domain="simulation",
                event_name="SIMULATION_COMPLETED",
                summary=f"{strategy_id} simulation: PnL={pnl:+.2f} | {result.get('total_trades', 0)} trades",
                user_id=user_id,
                entity_type="persistent_simulation_run",
                entity_id=run_id,
                severity="info",
                payload={"strategy": strategy_id, "pnl": pnl,
                         "symbols": symbols[:5], "run_type": run_type},
            )
        except Exception:
            pass

        return run_id

    except Exception as e:
        logger.error(f"[sim_persist] Failed to save run: {e}")
        return None


def get_simulation_history(
    user_id: int,
    run_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """Get simulation run history for a user with summary results."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentSimulationRun, SimulationResult

        db = SessionLocal()
        query = db.query(PersistentSimulationRun).filter(
            PersistentSimulationRun.user_id == user_id
        )
        if run_type:
            query = query.filter(PersistentSimulationRun.run_type == run_type)

        runs = (
            query
            .order_by(PersistentSimulationRun.created_at.desc())
            .limit(min(limit, 100))
            .all()
        )

        run_ids = [r.id for r in runs]
        results_map = {}
        if run_ids:
            results = (
                db.query(SimulationResult)
                .filter(SimulationResult.simulation_run_id.in_(run_ids))
                .all()
            )
            for res in results:
                results_map[res.simulation_run_id] = res

        db.close()

        return [
            {
                "id": r.id,
                "strategy_id": r.strategy_id,
                "run_type": r.run_type,
                "symbols": r.symbol_universe_json or [],
                "initial_capital": float(r.initial_capital) if r.initial_capital is not None else None,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "result": _format_result(results_map.get(r.id)) if r.id in results_map else None,
            }
            for r in runs
        ]

    except Exception as e:
        logger.warning(f"[sim_persist] Failed to load history: {e}")
        return []


def get_simulation_detail(run_id: int) -> Optional[Dict]:
    """Get full simulation detail including config, results, and timeseries."""
    try:
        from database.connection import SessionLocal
        from database.models import (
            PersistentSimulationRun, SimulationResult, SimulationResultTimeseries,
        )

        db = SessionLocal()
        run = db.query(PersistentSimulationRun).filter(
            PersistentSimulationRun.id == run_id
        ).first()
        if not run:
            db.close()
            return None

        result = (
            db.query(SimulationResult)
            .filter(SimulationResult.simulation_run_id == run_id)
            .first()
        )

        ts_points = (
            db.query(SimulationResultTimeseries)
            .filter(SimulationResultTimeseries.simulation_run_id == run_id)
            .order_by(SimulationResultTimeseries.point_timestamp)
            .all()
        )
        db.close()

        return {
            "id": run.id,
            "user_id": run.user_id,
            "strategy_id": run.strategy_id,
            "run_type": run.run_type,
            "symbols": run.symbol_universe_json or [],
            "timeframe_start": run.timeframe_start.isoformat() if run.timeframe_start else None,
            "timeframe_end": run.timeframe_end.isoformat() if run.timeframe_end else None,
            "initial_capital": float(run.initial_capital) if run.initial_capital is not None else None,
            "config": run.config_json or {},
            "assumptions": run.assumptions_json or {},
            "disclaimer": run.disclaimer_text,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "result": _format_result(result) if result else None,
            "equity_curve": [
                {
                    "timestamp": p.point_timestamp.isoformat() if p.point_timestamp else None,
                    "equity": float(p.equity_value) if p.equity_value is not None else None,
                    "drawdown_pct": p.drawdown_pct,
                    "exposure_pct": p.exposure_pct,
                }
                for p in ts_points
            ],
        }

    except Exception as e:
        logger.warning(f"[sim_persist] Failed to load detail: {e}")
        return None


def _format_result(res) -> Optional[Dict]:
    """Format a SimulationResult row into a dict."""
    if not res:
        return None
    return {
        "total_return_pct": res.total_return_pct,
        "annualized_return_pct": res.annualized_return_pct,
        "max_drawdown_pct": res.max_drawdown_pct,
        "sharpe_ratio": res.sharpe_ratio,
        "win_rate_pct": res.win_rate_pct,
        "total_trades": res.total_trades,
        "avg_trade_return_pct": res.avg_trade_return_pct,
        "pnl_value": float(res.pnl_value) if res.pnl_value is not None else None,
        "risk_metrics": res.risk_metrics_json or {},
        "summary": res.summary_text,
    }
