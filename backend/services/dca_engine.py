"""DCA strategy engine for opt-in staged entries in auto trading."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal


def calculate_dca_plan(symbol, total_amount, current_price, num_entries=3):
    total = float(total_amount or 0.0)
    px = float(current_price or 0.0)
    if total <= 0 or px <= 0:
        return []

    return [
        {
            "entry": 1,
            "price": px,
            "size": round(total * 0.40, 6),
            "type": "market",
            "execute": "now",
        },
        {
            "entry": 2,
            "price": round(px * 0.98, 8),
            "size": round(total * 0.35, 6),
            "type": "limit",
            "execute": "when_price_drops_2pct",
        },
        {
            "entry": 3,
            "price": round(px * 0.96, 8),
            "size": round(total * 0.25, 6),
            "type": "limit",
            "execute": "when_price_drops_4pct",
        },
    ][: max(1, int(num_entries or 3))]


def _ensure_table() -> None:
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS dca_orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                symbol VARCHAR NOT NULL,
                target_price FLOAT NOT NULL,
                size_usd FLOAT NOT NULL,
                status VARCHAR DEFAULT 'pending',
                executed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_dca_orders_user_status ON dca_orders (user_id, status, created_at DESC)"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _size_to_quantity(broker, symbol: str, size_usd: float, price: float) -> float:
    if price <= 0:
        return 0.0
    qty = float(size_usd) / float(price)
    try:
        lot = broker.get_lot_size(symbol)
        qty = broker.round_to_step_size(qty, lot["step_size"])
        if qty < lot["min_qty"]:
            return 0.0
    except Exception:
        pass
    return float(qty)


def save_pending_dca_order(user_id: int, symbol: str, target_price: float, size_usd: float) -> Optional[int]:
    _ensure_table()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                INSERT INTO dca_orders (user_id, symbol, target_price, size_usd, status)
                VALUES (:user_id, :symbol, :target_price, :size_usd, 'pending')
                RETURNING id
                """
            ),
            {
                "user_id": int(user_id),
                "symbol": str(symbol).upper(),
                "target_price": float(target_price),
                "size_usd": float(size_usd),
            },
        ).fetchone()
        db.commit()
        return int(row[0]) if row else None
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def execute_dca_plan(symbol, plan, broker, user_id: Optional[int] = None):
    if not plan:
        return {"success": False, "error": "empty_plan"}

    sym = str(symbol).upper()
    first = plan[0]
    market_price = float(first.get("price") or 0.0)
    qty = _size_to_quantity(broker, sym, float(first.get("size") or 0.0), market_price)
    if qty <= 0:
        return {"success": False, "error": "invalid_first_quantity"}

    first_result = broker.place_live_order(
        symbol=sym,
        side="BUY",
        quantity=qty,
        order_type="MARKET",
    )
    if "error" in first_result:
        return {"success": False, "error": first_result.get("error", "market_entry_failed")}

    pending_ids: List[int] = []
    if user_id is not None:
        for entry in plan[1:]:
            oid = save_pending_dca_order(
                user_id=int(user_id),
                symbol=sym,
                target_price=float(entry.get("price") or 0.0),
                size_usd=float(entry.get("size") or 0.0),
            )
            if oid is not None:
                pending_ids.append(oid)

    return {
        "success": True,
        "symbol": sym,
        "first_entry": {
            "price": float(first_result.get("price") or market_price),
            "quantity": qty,
            "order_id": first_result.get("order_id"),
            "size_usd": float(first.get("size") or 0.0),
        },
        "pending_order_ids": pending_ids,
        "plan": plan,
    }


def get_user_dca_orders(user_id: int) -> Dict:
    _ensure_table()
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT id, symbol, target_price, size_usd, status, executed_at, created_at
                FROM dca_orders
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 200
                """
            ),
            {"user_id": int(user_id)},
        ).mappings().all()

        pending = []
        executed = []
        cancelled = []
        for r in rows:
            item = {
                "id": int(r["id"]),
                "symbol": str(r["symbol"]),
                "target_price": float(r["target_price"]),
                "size_usd": float(r["size_usd"]),
                "status": str(r["status"]),
                "executed_at": r["executed_at"].isoformat() if r["executed_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            status = item["status"]
            if status == "pending":
                pending.append(item)
            elif status == "executed":
                executed.append(item)
            else:
                cancelled.append(item)

        return {"pending": pending, "executed": executed, "cancelled": cancelled}
    except Exception:
        return {"pending": [], "executed": [], "cancelled": []}
    finally:
        db.close()


def cancel_dca_order(user_id: int, order_id: int) -> bool:
    _ensure_table()
    db = SessionLocal()
    try:
        res = db.execute(
            text(
                """
                UPDATE dca_orders
                SET status = 'cancelled'
                WHERE id = :order_id
                  AND user_id = :user_id
                  AND status = 'pending'
                """
            ),
            {"order_id": int(order_id), "user_id": int(user_id)},
        )
        db.commit()
        return bool(getattr(res, "rowcount", 0) > 0)
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def check_pending_dca_orders(user_id: int, broker):
    _ensure_table()
    executed: List[Dict] = []
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT id, symbol, target_price, size_usd
                FROM dca_orders
                WHERE user_id = :user_id
                  AND status = 'pending'
                ORDER BY created_at ASC
                """
            ),
            {"user_id": int(user_id)},
        ).mappings().all()

        for row in rows:
            symbol = str(row["symbol"])
            target = float(row["target_price"])
            size_usd = float(row["size_usd"])
            current = float(broker.get_symbol_price(symbol) or 0.0)
            if current <= 0:
                continue
            if current > target:
                continue

            qty = _size_to_quantity(broker, symbol, size_usd, current)
            if qty <= 0:
                continue

            result = broker.place_live_order(
                symbol=symbol,
                side="BUY",
                quantity=qty,
                order_type="MARKET",
            )
            if "error" in result:
                continue

            db.execute(
                text(
                    """
                    UPDATE dca_orders
                    SET status = 'executed', executed_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": int(row["id"])}
            )

            executed.append(
                {
                    "id": int(row["id"]),
                    "symbol": symbol,
                    "target_price": target,
                    "size_usd": size_usd,
                    "executed_price": float(result.get("price") or current),
                    "quantity": qty,
                }
            )

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    if executed:
        try:
            from services.push_notifications import send_push_to_user_id

            for item in executed:
                send_push_to_user_id(
                    int(user_id),
                    title=f"DCA Entry: {item['symbol']}",
                    body=f"Entry @ ${item['executed_price']:.4f}",
                    data={"screen": "/auto-trading", "type": "dca_entry", "symbol": item["symbol"]},
                )
        except Exception:
            pass

    return executed
