"""The engine's books must match what the broker actually holds."""

import pytest

from services.auto_trading_engine import AutoTradingEngine


class FakeBroker:
    """Long-only broker that tracks holdings like the paper portfolio does."""
    supports_short = False

    def __init__(self, holdings=None, prices=None, fail=False):
        self.connected = True
        self.holdings = dict(holdings or {})      # symbol -> {"quantity", "avg_price"}
        self.prices = dict(prices or {})
        self.orders = []
        self.fail = fail

    def get_symbol_price(self, symbol):
        return self.prices.get(symbol, 0.0)

    def get_positions(self):
        return [{"symbol": s, **h} for s, h in self.holdings.items() if h["quantity"] > 0]

    def place_live_order(self, symbol, side, quantity, order_type="MARKET", client_order_id=None):
        if self.fail:
            return {"error": "exchange unavailable", "status": "failed"}
        held = self.holdings.get(symbol, {"quantity": 0.0, "avg_price": 0.0})
        if side == "SELL":
            if quantity > held["quantity"] + 1e-9:
                return {"error": "Insufficient quantity", "status": "failed"}
            held["quantity"] = round(held["quantity"] - quantity, 8)
        else:
            held["quantity"] = round(held["quantity"] + quantity, 8)
        self.holdings[symbol] = held
        self.orders.append((symbol, side, quantity))
        return {"order_id": f"T{len(self.orders)}", "price": self.prices[symbol], "status": "FILLED"}


def _engine(broker, positions=None):
    engine = AutoTradingEngine()
    engine.broker = broker
    engine.open_positions = dict(positions or {})
    engine._notify_user = lambda *a, **k: None
    return engine


def _long(symbol, qty, entry, target):
    return {"symbol": symbol, "side": "BUY", "quantity": qty, "entry_price": entry,
            "target_price": target, "stop_loss": entry * 0.97, "trailing_stop": entry * 0.98,
            "confidence": 0.9, "status": "open"}


# ── partial take-profit ────────────────────────────────────────────────────────

def test_partial_take_profit_really_sells_and_books_the_trade():
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0})
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})

    engine._check_partial_tp(user_id=1)

    assert broker.orders == [("AAA", "SELL", 4.0)]                 # a real order went out
    assert broker.holdings["AAA"]["quantity"] == 6.0
    assert engine.open_positions["AAA"]["quantity"] == 6.0         # books match the broker
    assert engine.open_positions["AAA"]["tp1_taken"] is True
    trade = engine.closed_trades[-1]
    assert trade["partial"] is True and trade["quantity"] == 4.0
    assert trade["pnl"] == pytest.approx((106.0 - 100.0) * 4.0)


def test_second_step_sells_forty_percent_of_the_original_size():
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0})
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._check_partial_tp(user_id=1)                            # TP1 at +5%
    broker.prices["AAA"] = 108.0                                   # TP2 at +7.5%
    engine._check_partial_tp(user_id=1)

    assert broker.orders == [("AAA", "SELL", 4.0), ("AAA", "SELL", 4.0)]
    assert engine.open_positions["AAA"]["quantity"] == 2.0         # 20% left to trail
    assert broker.holdings["AAA"]["quantity"] == 2.0
    assert engine.open_positions["AAA"]["tp2_taken"] is True


def test_failed_partial_sale_changes_nothing_and_is_retried():
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0}, fail=True)
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._check_partial_tp(user_id=1)

    assert engine.open_positions["AAA"]["quantity"] == 10.0
    assert not engine.open_positions["AAA"].get("tp1_taken")
    assert engine.closed_trades == []

    broker.fail = False                                            # next scan succeeds
    engine._check_partial_tp(user_id=1)
    assert engine.open_positions["AAA"]["quantity"] == 6.0


def test_full_close_after_partials_leaves_nothing_behind():
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0})
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._check_partial_tp(user_id=1)
    engine._close_position("AAA", current_price=106.0, user_id=1, reason="trailing_stop")

    assert "AAA" not in engine.open_positions
    assert broker.holdings["AAA"]["quantity"] == 0.0               # the old bug left 40% here


# ── reconciliation after a restart ─────────────────────────────────────────────

def test_untracked_holdings_are_adopted_with_a_stop():
    broker = FakeBroker({"AAA": {"quantity": 3.0, "avg_price": 50.0}}, {"AAA": 50.0})
    engine = _engine(broker)                                       # fresh process: knows nothing

    engine._reconcile_positions(user_id=1)

    pos = engine.open_positions["AAA"]
    assert pos["adopted"] is True and pos["side"] == "BUY"
    assert pos["quantity"] == 3.0 and pos["entry_price"] == 50.0
    assert 0 < pos["trailing_stop"] < 50.0                         # it is managed again
    engine._reconcile_positions(user_id=1)                         # idempotent
    assert len(engine.open_positions) == 1


def test_adopted_position_is_closed_by_its_stop():
    broker = FakeBroker({"AAA": {"quantity": 3.0, "avg_price": 50.0}}, {"AAA": 45.0})
    engine = _engine(broker)
    engine._reconcile_positions(user_id=1)
    engine._update_trailing_stops(user_id=1)

    assert "AAA" not in engine.open_positions
    assert broker.holdings["AAA"]["quantity"] == 0.0
    assert engine.closed_trades[-1]["reason"] == "trailing_stop"


def test_quantity_mismatch_is_corrected_to_the_broker():
    broker = FakeBroker({"AAA": {"quantity": 4.0, "avg_price": 100.0}}, {"AAA": 100.0})
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._reconcile_positions(user_id=1)
    assert engine.open_positions["AAA"]["quantity"] == 4.0


def test_position_the_broker_no_longer_holds_is_dropped():
    broker = FakeBroker({}, {"AAA": 100.0})
    engine = _engine(broker, {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._reconcile_positions(user_id=1)
    assert engine.open_positions == {}


def test_brokers_that_cannot_list_holdings_are_left_alone():
    class Opaque:
        connected = True
    engine = _engine(Opaque(), {"AAA": _long("AAA", 10.0, 100.0, 105.0)})
    engine._reconcile_positions(user_id=1)
    assert engine.open_positions["AAA"]["quantity"] == 10.0


def test_full_close_is_written_to_the_log(caplog):
    import logging
    broker = FakeBroker({"AAA": {"quantity": 3.0, "avg_price": 50.0}}, {"AAA": 45.0})
    engine = _engine(broker, {"AAA": _long("AAA", 3.0, 50.0, 52.5)})
    with caplog.at_level(logging.INFO, logger="services.auto_trading_engine"):
        engine._close_position("AAA", current_price=45.0, user_id=1, reason="trailing_stop")
    assert any("Position closed: AAA" in r.getMessage() and "trailing_stop" in r.getMessage()
               for r in caplog.records)


# ── positions survive a restart ────────────────────────────────────────────────

class MemoryStore:
    """Stands in for the database table behind services.position_store."""
    def __init__(self):
        self.rows = {}
        self.saves = 0

    def load(self, user_id):
        import json
        return json.loads(json.dumps(self.rows.get(user_id, {})))

    def save(self, user_id, positions):
        import json
        self.rows[user_id] = json.loads(json.dumps(positions, default=str))
        self.saves += 1
        return True


@pytest.fixture
def store(monkeypatch):
    import services.position_store as ps
    memory = MemoryStore()
    monkeypatch.setattr(ps, "position_store", memory)
    return memory


def test_restart_keeps_what_the_engine_knew_about_a_position(store):
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0})
    first = _engine(broker)
    first._load_user_context(1)
    first.open_positions = {"AAA": dict(_long("AAA", 10.0, 100.0, 105.0), smart_score=81, opened_at="2026-11-20T10:00:00")}
    first._check_partial_tp(user_id=1)                # sells the first 40% and flags it
    first._save_user_context(1)
    flags_before = {k: v for k, v in first.open_positions["AAA"].items() if "tp" in k.lower() or "partial" in k.lower()}

    second = _engine(broker)                          # a fresh process
    second.open_positions = {}
    second._load_user_context(1)
    second._reconcile_positions(1)
    restored = second.open_positions["AAA"]

    assert restored["quantity"] == pytest.approx(6.0)
    assert restored["smart_score"] == 81
    assert restored["opened_at"] == "2026-11-20T10:00:00"
    assert not restored.get("adopted")                # remembered, not re-adopted blind
    for key, value in flags_before.items():
        assert restored[key] == value
    orders_before = len(broker.orders)
    second._check_partial_tp(user_id=1)               # same price: the first step must not repeat
    assert len(broker.orders) == orders_before


def test_saved_position_the_broker_no_longer_holds_is_dropped(store):
    store.rows[1] = {"GONE": _long("GONE", 5.0, 10.0, 11.0)}
    engine = _engine(FakeBroker({}, {"GONE": 10.0}))
    engine.open_positions = {}
    engine._load_user_context(1)
    assert "GONE" in engine.open_positions
    engine._reconcile_positions(1)
    assert engine.open_positions == {}
    engine._save_user_context(1)
    assert store.rows[1] == {}


def test_partial_sale_is_saved_immediately(store):
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 106.0})
    engine = _engine(broker)
    engine._load_user_context(1)
    engine.open_positions = {"AAA": _long("AAA", 10.0, 100.0, 105.0)}
    engine._check_partial_tp(user_id=1)
    assert store.rows[1]["AAA"]["quantity"] == pytest.approx(6.0)   # before any end-of-scan save


def test_storage_failure_does_not_stop_the_engine(monkeypatch):
    import services.position_store as ps

    class Broken:
        def load(self, user_id): raise RuntimeError("db down")
        def save(self, user_id, positions): raise RuntimeError("db down")

    monkeypatch.setattr(ps, "position_store", Broken())
    broker = FakeBroker({"AAA": {"quantity": 10.0, "avg_price": 100.0}}, {"AAA": 100.0})
    engine = _engine(broker)
    engine.open_positions = {}
    engine._load_user_context(1)
    engine._reconcile_positions(1)
    engine._save_user_context(1)
    assert engine.open_positions["AAA"]["adopted"] is True
