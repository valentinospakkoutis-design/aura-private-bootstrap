"""Paper A/B strategy recorder: periodic equity/P&L snapshots per paper user."""
from database.connection import SessionLocal
from database.models import PaperStrategySnapshot, UserAutopilotSettings
from services.paper_trading import PaperTradingService


def _paper_users():
    db = SessionLocal()
    try:
        rows = db.query(UserAutopilotSettings).filter(
            UserAutopilotSettings.is_enabled == True
        ).all()
        out = []
        for r in rows:
            ov = r.config_overrides_json or {}
            if isinstance(ov, dict) and ov.get("paper_mode"):
                out.append((int(r.user_id), ov.get("paper_smart_score_threshold")))
        return out
    finally:
        db.close()


def _prices_for(symbols, user_id):
    prices = {}
    if not symbols:
        return prices
    try:
        from brokers.paper_broker import PaperBroker
        pb = PaperBroker(user_id=user_id)
        for s in symbols:
            try:
                p = pb.get_symbol_price(s)
                if p:
                    prices[s] = float(p)
            except Exception:
                pass
    except Exception:
        pass
    return prices


def record_snapshots():
    """Write one equity snapshot per active paper user. Returns count written."""
    users = _paper_users()
    if not users:
        return 0
    svc = PaperTradingService()
    db = SessionLocal()
    n = 0
    try:
        for uid, threshold in users:
            try:
                state = svc._get_state(uid)
                history = state.get("trade_history") or []
                open_syms = list((state.get("portfolio") or {}).keys())
                prices = _prices_for(open_syms, uid)
                pf = svc.get_portfolio(prices, user_id=uid)
                closed = [t for t in history if t.get("pnl") is not None]
                wins = sum(1 for t in closed if float(t.get("pnl", 0) or 0) > 0)
                losses = sum(1 for t in closed if float(t.get("pnl", 0) or 0) < 0)
                # Unrealized P&L = sum of open-position P&L; realized = total - floating.
                floating = sum(float(p.get("pnl", 0) or 0) for p in pf.get("positions", []))
                total_pnl = float(pf["total_pnl"])
                db.add(PaperStrategySnapshot(
                    user_id=uid,
                    threshold=float(threshold) if threshold is not None else None,
                    equity=float(pf["total_value"]),
                    cash=float(pf["cash"]),
                    floating_pnl=floating,
                    realized_pnl=total_pnl - floating,
                    total_pnl=total_pnl,
                    n_open=len(pf.get("positions", [])),
                    n_closed=len(closed),
                    wins=wins,
                    losses=losses,
                ))
                n += 1
            except Exception as e:
                print("[recorder] user %s failed: %s" % (uid, e))
        db.commit()
    except Exception as e:
        db.rollback()
        print("[recorder] commit failed: %s" % e)
    finally:
        db.close()
    return n
