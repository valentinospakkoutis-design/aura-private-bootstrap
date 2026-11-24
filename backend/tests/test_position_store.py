"""The position store against a real SQL engine (SQLite stands in for Postgres)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.position_store as ps


def test_round_trip_update_and_delete(monkeypatch):
    from sqlalchemy import event
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _add_now(conn, _):
        conn.create_function("NOW", 0, lambda: "2026-11-24 00:00:00")

    monkeypatch.setattr(ps, "_CREATE", ps._CREATE.replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP"))
    store = ps.PositionStore(session_factory=sessionmaker(bind=engine))

    assert store.load(1) == {}
    a = {"symbol": "AAA", "quantity": 1.5, "tp1_done": True, "signals": {"rsi": 31}}
    assert store.save(1, {"AAA": a, "BBB": {"symbol": "BBB", "quantity": 2}}) is True
    assert store.save(1, {"AAA": a, "BBB": {"symbol": "BBB", "quantity": 2}}) is False   # unchanged: no write
    assert store.save(2, {"CCC": {"symbol": "CCC", "quantity": 9}}) is True

    fresh = ps.PositionStore(session_factory=sessionmaker(bind=engine))
    assert fresh.load(1) == {"AAA": a, "BBB": {"symbol": "BBB", "quantity": 2}}
    assert set(fresh.load(2)) == {"CCC"}                                               # users are separate

    assert fresh.save(1, {"AAA": dict(a, quantity=0.9)}) is True                       # update one, delete one
    assert ps.PositionStore(session_factory=sessionmaker(bind=engine)).load(1) == {"AAA": dict(a, quantity=0.9)}


def test_no_database_is_a_quiet_no_op():
    store = ps.PositionStore(session_factory=lambda: None)
    assert store.load(1) == {}
    assert store.save(1, {"AAA": {"quantity": 1}}) is False
