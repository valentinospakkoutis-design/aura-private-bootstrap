"""
Portfolio Persistence Service for AURA.
Stores portfolio state snapshots with relational symbol and cluster exposures.

All tables are append-only — each snapshot is a point-in-time record.

Retention note:
  At 1 snapshot per decision (roughly per symbol check), a user checking
  33 symbols once a day produces ~33 rows/day + ~33*N child rows.
  At scale, consider partitioning by snapshot_timestamp or periodic
  aggregation (daily rollups) with raw row pruning after 90 days.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def save_portfolio_snapshot(
    user_id: int,
    total_equity: float,
    available_cash: float,
    positions: List[Dict],
    correlated_exposure: Dict[str, float],
    risk_score: float = 0.0,
    concentration_score: Optional[float] = None,
    diversification_score: Optional[float] = None,
    drawdown_pct: Optional[float] = None,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """
    Save a portfolio snapshot with relational symbol and cluster exposures.
    Returns the snapshot ID or None on failure.

    positions: list of dicts with at minimum:
        {symbol, quantity, market_value, exposure_pct}
        optional: {asset_class, direction, unrealized_pnl}

    correlated_exposure: dict of {cluster_name: gross_exposure_usd}
    """
    try:
        from database.connection import SessionLocal
        from database.models import (
            PortfolioStateSnapshot, PortfolioSymbolExposure, PortfolioClusterExposure,
        )

        db = SessionLocal()

        # Compute aggregates
        total_exposure = sum(p.get("market_value", 0) for p in positions)
        long_exposure = sum(
            p.get("market_value", 0)
            for p in positions
            if p.get("direction", "long") == "long"
        )
        short_exposure = sum(
            p.get("market_value", 0)
            for p in positions
            if p.get("direction", "long") == "short"
        )
        gross_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure

        # ── 1. Insert snapshot ──
        snapshot = PortfolioStateSnapshot(
            user_id=user_id,
            snapshot_timestamp=datetime.utcnow(),
            total_equity=total_equity,
            available_cash=available_cash,
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            gross_exposure=gross_exposure,
            drawdown_pct=drawdown_pct,
            concentration_score=concentration_score,
            diversification_score=diversification_score,
            risk_score=risk_score,
            metadata_json=metadata or {},
        )
        db.add(snapshot)
        db.flush()  # get snapshot.id

        # ── 2. Insert symbol exposures ──
        for p in positions:
            db.add(PortfolioSymbolExposure(
                portfolio_snapshot_id=snapshot.id,
                symbol=p.get("symbol", ""),
                asset_class=p.get("asset_class"),
                direction=p.get("direction", "long"),
                quantity=p.get("quantity", 0),
                market_value=p.get("market_value", 0),
                exposure_pct=p.get("exposure_pct", 0),
                unrealized_pnl=p.get("unrealized_pnl"),
                metadata_json=p.get("metadata") or {},
            ))

        # ── 3. Insert cluster exposures ──
        for cluster_name, gross_val in correlated_exposure.items():
            cluster_pct = (gross_val / total_equity * 100) if total_equity > 0 else 0
            db.add(PortfolioClusterExposure(
                portfolio_snapshot_id=snapshot.id,
                cluster_name=cluster_name,
                gross_exposure=gross_val,
                net_exposure=gross_val,  # clusters are typically all-long
                exposure_pct=round(cluster_pct, 2),
                risk_weight=None,
            ))

        db.commit()
        snap_id = snapshot.id
        db.close()

        logger.info(
            f"[portfolio_persist] Saved snapshot #{snap_id}: "
            f"user={user_id} equity=${total_equity:.0f} "
            f"positions={len(positions)} clusters={len(correlated_exposure)}"
        )
        return snap_id

    except Exception as e:
        logger.error(f"[portfolio_persist] Failed to save snapshot: {e}")
        return None


def get_snapshot_history(
    user_id: int,
    limit: int = 30,
) -> List[Dict]:
    """
    Get recent portfolio snapshots for a user (summary level).
    Use get_snapshot_detail() for full symbol/cluster breakdown.
    """
    try:
        from database.connection import SessionLocal
        from database.models import PortfolioStateSnapshot

        db = SessionLocal()
        rows = (
            db.query(PortfolioStateSnapshot)
            .filter(PortfolioStateSnapshot.user_id == user_id)
            .order_by(PortfolioStateSnapshot.snapshot_timestamp.desc())
            .limit(min(limit, 200))
            .all()
        )
        db.close()

        return [
            {
                "id": r.id,
                "snapshot_timestamp": r.snapshot_timestamp.isoformat() if r.snapshot_timestamp else None,
                "total_equity": float(r.total_equity) if r.total_equity is not None else None,
                "available_cash": float(r.available_cash) if r.available_cash is not None else None,
                "total_exposure": float(r.total_exposure) if r.total_exposure is not None else None,
                "net_exposure": float(r.net_exposure) if r.net_exposure is not None else None,
                "gross_exposure": float(r.gross_exposure) if r.gross_exposure is not None else None,
                "drawdown_pct": r.drawdown_pct,
                "concentration_score": r.concentration_score,
                "diversification_score": r.diversification_score,
                "risk_score": r.risk_score,
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[portfolio_persist] Failed to load history: {e}")
        return []


def get_snapshot_detail(snapshot_id: int) -> Optional[Dict]:
    """
    Get a single snapshot with full symbol and cluster exposure breakdown.
    """
    try:
        from database.connection import SessionLocal
        from database.models import (
            PortfolioStateSnapshot, PortfolioSymbolExposure, PortfolioClusterExposure,
        )

        db = SessionLocal()
        snap = db.query(PortfolioStateSnapshot).filter(
            PortfolioStateSnapshot.id == snapshot_id
        ).first()

        if not snap:
            db.close()
            return None

        symbols = (
            db.query(PortfolioSymbolExposure)
            .filter(PortfolioSymbolExposure.portfolio_snapshot_id == snapshot_id)
            .all()
        )
        clusters = (
            db.query(PortfolioClusterExposure)
            .filter(PortfolioClusterExposure.portfolio_snapshot_id == snapshot_id)
            .all()
        )
        db.close()

        return {
            "id": snap.id,
            "user_id": snap.user_id,
            "snapshot_timestamp": snap.snapshot_timestamp.isoformat() if snap.snapshot_timestamp else None,
            "total_equity": float(snap.total_equity) if snap.total_equity is not None else None,
            "available_cash": float(snap.available_cash) if snap.available_cash is not None else None,
            "total_exposure": float(snap.total_exposure) if snap.total_exposure is not None else None,
            "net_exposure": float(snap.net_exposure) if snap.net_exposure is not None else None,
            "gross_exposure": float(snap.gross_exposure) if snap.gross_exposure is not None else None,
            "drawdown_pct": snap.drawdown_pct,
            "concentration_score": snap.concentration_score,
            "diversification_score": snap.diversification_score,
            "risk_score": snap.risk_score,
            "metadata": snap.metadata_json or {},
            "symbol_exposures": [
                {
                    "symbol": s.symbol,
                    "asset_class": s.asset_class,
                    "direction": s.direction,
                    "quantity": float(s.quantity) if s.quantity is not None else 0,
                    "market_value": float(s.market_value) if s.market_value is not None else 0,
                    "exposure_pct": s.exposure_pct,
                    "unrealized_pnl": float(s.unrealized_pnl) if s.unrealized_pnl is not None else None,
                }
                for s in symbols
            ],
            "cluster_exposures": [
                {
                    "cluster_name": c.cluster_name,
                    "gross_exposure": float(c.gross_exposure) if c.gross_exposure is not None else 0,
                    "net_exposure": float(c.net_exposure) if c.net_exposure is not None else 0,
                    "exposure_pct": c.exposure_pct,
                    "risk_weight": c.risk_weight,
                }
                for c in clusters
            ],
        }

    except Exception as e:
        logger.warning(f"[portfolio_persist] Failed to load detail: {e}")
        return None


def get_equity_timeseries(user_id: int, limit: int = 90) -> List[Dict]:
    """
    Get equity over time for charting.
    Returns (timestamp, total_equity, risk_score) tuples.
    """
    try:
        from database.connection import SessionLocal
        from database.models import PortfolioStateSnapshot

        db = SessionLocal()
        rows = (
            db.query(
                PortfolioStateSnapshot.snapshot_timestamp,
                PortfolioStateSnapshot.total_equity,
                PortfolioStateSnapshot.risk_score,
                PortfolioStateSnapshot.total_exposure,
            )
            .filter(PortfolioStateSnapshot.user_id == user_id)
            .order_by(PortfolioStateSnapshot.snapshot_timestamp.desc())
            .limit(min(limit, 365))
            .all()
        )
        db.close()

        return [
            {
                "timestamp": r.snapshot_timestamp.isoformat() if r.snapshot_timestamp else None,
                "total_equity": float(r.total_equity) if r.total_equity is not None else None,
                "risk_score": r.risk_score,
                "total_exposure": float(r.total_exposure) if r.total_exposure is not None else None,
            }
            for r in reversed(rows)  # chronological order for charts
        ]

    except Exception as e:
        logger.warning(f"[portfolio_persist] Failed to load timeseries: {e}")
        return []
