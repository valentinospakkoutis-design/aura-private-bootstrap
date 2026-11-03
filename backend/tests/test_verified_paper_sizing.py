"""Offline SQLite integration with real UserProfile, paper service and PaperBroker."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def module_overrides(mapping):
    # Restore only replaced keys. Restoring all sys.modules can unload modules
    # imported during the test and corrupt SQLAlchemy enum/cache identities.
    missing = object()
    saved = {key: sys.modules.get(key, missing) for key in mapping}
    sys.modules.update(mapping)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value



class VerifiedPaperTests(unittest.TestCase):
    def setUp(self):
        self.net = patch('socket.socket', side_effect=AssertionError('offline test')); self.net.start(); self.addCleanup(self.net.stop)
        self.engine = create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        self.sessions = sessionmaker(bind=self.engine)
        # Import actual project models without initializing production DB engines.
        spec = importlib.util.spec_from_file_location('offline_models', ROOT/'database/models.py')
        self.models = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.models)
        self.models.UserProfile.__table__.create(self.engine)
        migration_spec = importlib.util.spec_from_file_location('risk_migration', ROOT/'alembic/versions/20261021_023_auto_sizing_paper_risk.py')
        migration = importlib.util.module_from_spec(migration_spec); migration_spec.loader.exec_module(migration)
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        with self.engine.begin() as migration_conn:
            with Operations.context(MigrationContext.configure(migration_conn)):
                migration.upgrade()
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE dca_orders (user_id INTEGER, symbol TEXT, size_usd FLOAT, status TEXT)'))
        conn = types.ModuleType('database.connection'); conn.SessionLocal = self.sessions
        self.mods = module_overrides({'database': types.ModuleType('database'),
                'database.models': self.models, 'database.connection': conn})
        self.mods.__enter__(); self.addCleanup(self.mods.__exit__, None, None, None)
        from services import verified_sizing as risk
        self.risk = risk
        spec = importlib.util.spec_from_file_location('offline_paper_service', ROOT/'services/paper_trading.py')
        service_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(service_module)
        self.paper = service_module.paper_trading_service
        self.paper_mod = module_overrides({'services.paper_trading': service_module})
        self.paper_mod.__enter__(); self.addCleanup(self.paper_mod.__exit__, None, None, None)
        from brokers.paper_broker import PaperBroker
        self.broker = PaperBroker(user_id=7)
        self.price = 100.
        self.quote = patch.object(risk, 'verified_paper_price', side_effect=lambda symbol: self.price)
        self.quote_mock = self.quote.start(); self.addCleanup(self.quote.stop)
        self.paper._ensure_user_profile(7)  # Actual creation writes the risk epoch.

    def snapshot(self):
        return self.risk.paper_sizing_snapshot(7, self.broker, self.sessions)

    def row(self):
        with self.sessions() as db:
            return db.query(self.models.UserProfile).filter_by(user_id=7).one()

    def test_actual_paper_execution_and_restart_drawdown(self):
        before = self.snapshot()
        self.assertEqual(before.equity_usd, 10000)
        order = self.broker.place_live_order('BTCUSDC', 'BUY', 4)
        self.assertEqual(order['status'], 'FILLED')
        self.assertEqual(self.snapshot().exposure_by_symbol['BTCUSDC'], 400)
        self.price = 200
        self.assertEqual(self.snapshot().peak_equity_usd, 10400)
        self.paper._user_states.clear()  # Simulated service restart; real DB persists.
        self.price = 50
        after = self.snapshot()
        self.assertEqual(after.equity_usd, 9800)
        self.assertEqual(after.peak_equity_usd, 10400)
        self.assertGreater(1-after.equity_usd/after.peak_equity_usd, .05)

    def test_reservations_reduce_cash_and_symbol_capacity(self):
        with self.sessions.begin() as db:
            db.execute(text("INSERT INTO dca_orders VALUES (7, 'BTCUSDC', 450, 'pending')"))
            db.execute(text("INSERT INTO dca_orders VALUES (8, 'ETHUSDC', 9000, 'pending')"))
        state = self.snapshot()
        self.assertEqual(state.available_cash_usd, 9550)
        self.assertEqual(state.exposure_by_symbol, {'BTCUSDC': 450})
        self.assertEqual(state.equity_usd, 10000)  # Reservations are not extra equity.

    def test_missing_dca_table_blocks(self):
        with self.engine.begin() as db: db.execute(text('DROP TABLE dca_orders'))
        with self.assertRaises(Exception): self.snapshot()

    def test_legacy_profile_requires_explicit_reset(self):
        with self.sessions.begin() as db:
            db.query(self.models.AutoSizingPaperRisk).filter_by(user_id=7).delete()
        with self.assertRaisesRegex(ValueError, 'history_unavailable'): self.snapshot()
        self.paper.reset(user_id=7)
        self.assertEqual(self.snapshot().peak_equity_usd, 10000)

    def test_user_mode_and_live_adapter_rejected(self):
        from brokers.paper_broker import PaperBroker
        for broker in (PaperBroker(user_id=8), Mock()):
            with self.assertRaisesRegex(ValueError, 'live_risk_adapter'):
                self.risk.paper_sizing_snapshot(7, broker, self.sessions)

    def test_missing_quote_does_not_use_entry_price(self):
        self.broker.place_live_order('BTCUSDC', 'BUY', 1)
        self.quote_mock.side_effect = ValueError('quote unavailable')
        with self.assertRaises(ValueError): self.snapshot()
        self.assertIn('error', self.broker.place_live_order('BTCUSDC','BUY',1))

    def test_database_runtime_mismatch_blocks(self):
        self.broker.place_live_order('BTCUSDC', 'BUY', 1)
        with self.sessions.begin() as db:
            row = db.query(self.models.UserProfile).filter_by(user_id=7).one(); row.paper_balance = 8000
        with self.assertRaisesRegex(ValueError, 'mismatch'): self.snapshot()

    def test_bad_pending_amount_blocks(self):
        with self.sessions.begin() as db: db.execute(text("INSERT INTO dca_orders VALUES (7, 'BTCUSDC', -1, 'pending')"))
        with self.assertRaises(ValueError): self.snapshot()

    def test_portfolio_total_uses_user_cash(self):
        self.broker.place_live_order('BTCUSDC', 'BUY', 2)
        self.paper.cash = 123  # Another/legacy account must not affect this user.
        pf = self.paper.get_portfolio({'BTCUSDC':100}, user_id=7)
        self.assertEqual(pf['total_value'], 10000)

    def test_real_engine_size_to_real_paper_fill(self):
        dca = types.ModuleType('services.dca_engine')
        for name in ('calculate_dca_plan','execute_dca_plan','check_pending_dca_orders'):
            setattr(dca, name, Mock(side_effect=AssertionError('DCA must remain paused')))
        with module_overrides({'services.dca_engine': dca}):
            spec = importlib.util.spec_from_file_location('paper_integration_engine', ROOT/'services/auto_trading_engine.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        auto = module.AutoTradingEngine(lambda uid, broker: self.risk.paper_sizing_snapshot(uid,broker,self.sessions))
        auto.broker = self.broker
        auto.config["paper_mode"] = True
        auto._get_symbol_backtest_stats = Mock(return_value={'win_rate':.7,'avg_win':.03,'avg_loss':.01})
        auto._get_regime_position_multiplier = Mock(return_value=1.)
        qty = auto._calculate_position_size(100,.9,.2,'BTCUSDC',user_id=7)
        self.assertGreater(qty,0)
        self.assertLessEqual(qty*100,10)
        filled = self.broker.place_live_order('BTCUSDC','BUY',qty)
        self.assertEqual(filled['status'],'FILLED')
        state = self.snapshot()
        self.assertAlmostEqual(state.equity_usd,10000)
        self.assertAlmostEqual(state.exposure_by_symbol['BTCUSDC'],qty*100)
        self.assertAlmostEqual(self.row().paper_balance,10000-qty*100)
        auto.config.update(enabled=True,dca_enabled=True)
        self.assertIsNone(auto.place_auto_order({'symbol':'BTCUSDC'},user_id=7))
        dca.execute_dca_plan.assert_not_called()

    def test_failed_high_water_commit_rejects_and_rolls_back(self):
        self.broker.place_live_order('BTCUSDC','BUY',1)
        self.price = 200
        db = self.sessions()
        with patch.object(db,'commit',side_effect=RuntimeError('disk failure')):
            with self.assertRaisesRegex(RuntimeError,'disk failure'):
                self.risk.paper_sizing_snapshot(7,self.broker,lambda:db)
        with self.sessions() as db:
            self.assertEqual(db.query(self.models.AutoSizingPaperRisk).filter_by(user_id=7).one().peak_equity_usd,10000)

    def test_editable_profile_notes_cannot_override_peak(self):
        self.broker.place_live_order('BTCUSDC','BUY',1)
        self.price = 200
        self.snapshot()
        with self.sessions.begin() as db:
            row = db.query(self.models.UserProfile).filter_by(user_id=7).one()
            row.notes_json = {'auto_sizing_paper_v1': {'version':1,'peak_equity_usd':1}}
        self.price = 50
        self.assertEqual(self.snapshot().peak_equity_usd,10100)

    def test_strict_price_cache_timestamp(self):
        # Unpatch the price function for validation tests; no Redis/network used.
        self.quote.stop()
        cache = Mock()
        for payload in ({'price':100}, {'price':100,'ts_ms':(time.time()-70)*1000},
                        {'price':100,'ts_ms':(time.time()+70)*1000},
                        {'price':'NaN','ts_ms':time.time()*1000}):
            cache.get.return_value = json.dumps(payload)
            with self.assertRaises(ValueError): self.risk.verified_paper_price('BTCUSDC', cache)
        cache.get.return_value=json.dumps({'price':100,'ts_ms':time.time()*1000})
        self.assertEqual(self.risk.verified_paper_price('BTCUSDC',cache),100)


if __name__ == '__main__': unittest.main(verbosity=2)
