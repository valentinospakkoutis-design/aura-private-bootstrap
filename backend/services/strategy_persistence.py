"""
Strategy Platform Persistence Service for AURA.

Three tables:
  - persistent_strategy_registry  (mutable — the strategy catalog)
  - strategy_health_snapshots     (append-only — performance over time)
  - strategy_allocations          (append-only — capital allocation decisions)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Registry CRUD ─────────────────────────────────────────────

def upsert_strategy(
    strategy_key: str,
    display_name: str,
    description: Optional[str] = None,
    asset_scope: Optional[str] = None,
    holding_style: Optional[str] = None,
    risk_class: Optional[str] = None,
    is_active: bool = True,
    version: str = "1.0",
    config_schema: Optional[dict] = None,
) -> Optional[int]:
    """Create or update a strategy in the registry. Returns the strategy ID."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentStrategyRegistry

        db = SessionLocal()
        existing = db.query(PersistentStrategyRegistry).filter(
            PersistentStrategyRegistry.strategy_key == strategy_key
        ).first()

        if existing:
            existing.display_name = display_name
            existing.description = description
            existing.asset_scope = asset_scope
            existing.holding_style = holding_style
            existing.risk_class = risk_class
            existing.is_active = is_active
            existing.version = version
            if config_schema is not None:
                existing.config_schema_json = config_schema
            strat_id = existing.id
        else:
            row = PersistentStrategyRegistry(
                strategy_key=strategy_key,
                display_name=display_name,
                description=description,
                asset_scope=asset_scope,
                holding_style=holding_style,
                risk_class=risk_class,
                is_active=is_active,
                version=version,
                config_schema_json=config_schema or {},
            )
            db.add(row)
            db.flush()
            strat_id = row.id

        db.commit()
        db.close()

        try:
            from services.audit_trail import emit_audit
            emit_audit(
                domain="strategy",
                event_name="STRATEGY_UPSERTED",
                summary=f"Strategy '{strategy_key}' v{version} ({'active' if is_active else 'inactive'})",
                entity_type="persistent_strategy_registry",
                entity_id=strat_id,
                severity="info",
                payload={"strategy_key": strategy_key, "version": version,
                         "is_active": is_active, "risk_class": risk_class},
            )
        except Exception:
            pass

        return strat_id

    except Exception as e:
        logger.error(f"[strategy_persist] Failed to upsert strategy: {e}")
        return None


def get_all_strategies(active_only: bool = False) -> List[Dict]:
    """Get all registered strategies."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentStrategyRegistry

        db = SessionLocal()
        query = db.query(PersistentStrategyRegistry)
        if active_only:
            query = query.filter(PersistentStrategyRegistry.is_active.is_(True))
        rows = query.order_by(PersistentStrategyRegistry.strategy_key).all()
        db.close()

        return [
            {
                "id": r.id,
                "strategy_key": r.strategy_key,
                "display_name": r.display_name,
                "description": r.description,
                "asset_scope": r.asset_scope,
                "holding_style": r.holding_style,
                "risk_class": r.risk_class,
                "is_active": r.is_active,
                "version": r.version,
                "config_schema": r.config_schema_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[strategy_persist] Failed to load strategies: {e}")
        return []


def get_strategy_by_key(strategy_key: str) -> Optional[Dict]:
    """Get a single strategy by key."""
    try:
        from database.connection import SessionLocal
        from database.models import PersistentStrategyRegistry

        db = SessionLocal()
        r = db.query(PersistentStrategyRegistry).filter(
            PersistentStrategyRegistry.strategy_key == strategy_key
        ).first()
        db.close()

        if not r:
            return None
        return {
            "id": r.id,
            "strategy_key": r.strategy_key,
            "display_name": r.display_name,
            "description": r.description,
            "asset_scope": r.asset_scope,
            "holding_style": r.holding_style,
            "risk_class": r.risk_class,
            "is_active": r.is_active,
            "version": r.version,
            "config_schema": r.config_schema_json or {},
        }

    except Exception as e:
        logger.warning(f"[strategy_persist] Failed to load strategy: {e}")
        return None


# ── Health snapshots ──────────────────────────────────────────

def save_health_snapshot(
    strategy_id: int,
    health_score: float,
    recent_return_pct: Optional[float] = None,
    recent_drawdown_pct: Optional[float] = None,
    win_rate_pct: Optional[float] = None,
    volatility_score: Optional[float] = None,
    stability_score: Optional[float] = None,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Append a health snapshot for a strategy."""
    try:
        from database.connection import SessionLocal
        from database.models import StrategyHealthSnapshot

        db = SessionLocal()
        row = StrategyHealthSnapshot(
            strategy_id=strategy_id,
            snapshot_timestamp=datetime.utcnow(),
            health_score=health_score,
            recent_return_pct=recent_return_pct,
            recent_drawdown_pct=recent_drawdown_pct,
            win_rate_pct=win_rate_pct,
            volatility_score=volatility_score,
            stability_score=stability_score,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.commit()
        row_id = row.id
        db.close()
        return row_id

    except Exception as e:
        logger.error(f"[strategy_persist] Failed to save health snapshot: {e}")
        return None


def get_health_history(strategy_id: int, limit: int = 30) -> List[Dict]:
    """Get recent health snapshots for a strategy."""
    try:
        from database.connection import SessionLocal
        from database.models import StrategyHealthSnapshot

        db = SessionLocal()
        rows = (
            db.query(StrategyHealthSnapshot)
            .filter(StrategyHealthSnapshot.strategy_id == strategy_id)
            .order_by(StrategyHealthSnapshot.snapshot_timestamp.desc())
            .limit(min(limit, 200))
            .all()
        )
        db.close()

        return [
            {
                "id": r.id,
                "snapshot_timestamp": r.snapshot_timestamp.isoformat() if r.snapshot_timestamp else None,
                "health_score": r.health_score,
                "recent_return_pct": r.recent_return_pct,
                "recent_drawdown_pct": r.recent_drawdown_pct,
                "win_rate_pct": r.win_rate_pct,
                "volatility_score": r.volatility_score,
                "stability_score": r.stability_score,
                "metadata": r.metadata_json or {},
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[strategy_persist] Failed to load health history: {e}")
        return []


# ── Allocations ───────────────────────────────────────────────

def save_allocation(
    strategy_id: int,
    target_allocation_pct: float,
    user_id: Optional[int] = None,
    actual_allocation_pct: Optional[float] = None,
    reason_summary: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Append an allocation record for a strategy."""
    try:
        from database.connection import SessionLocal
        from database.models import StrategyAllocation

        db = SessionLocal()
        row = StrategyAllocation(
            strategy_id=strategy_id,
            user_id=user_id,
            allocation_timestamp=datetime.utcnow(),
            target_allocation_pct=target_allocation_pct,
            actual_allocation_pct=actual_allocation_pct,
            reason_summary=reason_summary,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.commit()
        row_id = row.id
        db.close()
        return row_id

    except Exception as e:
        logger.error(f"[strategy_persist] Failed to save allocation: {e}")
        return None


def get_allocation_history(
    strategy_id: Optional[int] = None,
    user_id: Optional[int] = None,
    limit: int = 30,
) -> List[Dict]:
    """Get recent allocation history, optionally filtered by strategy or user."""
    try:
        from database.connection import SessionLocal
        from database.models import StrategyAllocation

        db = SessionLocal()
        query = db.query(StrategyAllocation)
        if strategy_id is not None:
            query = query.filter(StrategyAllocation.strategy_id == strategy_id)
        if user_id is not None:
            query = query.filter(StrategyAllocation.user_id == user_id)

        rows = (
            query
            .order_by(StrategyAllocation.allocation_timestamp.desc())
            .limit(min(limit, 200))
            .all()
        )
        db.close()

        return [
            {
                "id": r.id,
                "strategy_id": r.strategy_id,
                "user_id": r.user_id,
                "allocation_timestamp": r.allocation_timestamp.isoformat() if r.allocation_timestamp else None,
                "target_allocation_pct": r.target_allocation_pct,
                "actual_allocation_pct": r.actual_allocation_pct,
                "reason_summary": r.reason_summary,
                "metadata": r.metadata_json or {},
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"[strategy_persist] Failed to load allocation history: {e}")
        return []
