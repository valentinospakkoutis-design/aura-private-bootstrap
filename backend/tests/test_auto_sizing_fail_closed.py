"""Offline regression tests; broker, DB and optional integrations are fakes.
Run: python -m unittest discover -s backend/tests -p test_auto_sizing_fail_closed.py -v
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch
from dataclasses import replace
from datetime import datetime, timezone, timedelta

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

# Loading the real engine must not initialize DCA/database/broker integrations.
dca = types.ModuleType('services.dca_engine')
for name in ('calculate_dca_plan', 'execute_dca_plan', 'check_pending_dca_orders'):
    setattr(dca, name, Mock(side_effect=AssertionError('DCA must not execute')))
with module_overrides({'services.dca_engine': dca}):
    spec = importlib.util.spec_from_file_location('offline_auto_engine', ROOT / 'services/auto_trading_engine.py')
    engine_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine_module)
from services.sizing_snapshot import SizingSnapshot, validate_snapshot
from services.position_sizing import SizingInput, calculate_position_size


class SizingTests(unittest.TestCase):
    def setUp(self):
        # Any accidental network use fails the offline regression run.
        network = patch('socket.socket', side_effect=AssertionError('network disabled in tests'))
        network.start(); self.addCleanup(network.stop)
        self.broker = Mock(connected=True)
        self.state = SizingSnapshot(7, self.broker, False, datetime.now(timezone.utc),
                                   10000., 10000., 10000., {}, True)
        self.provider = Mock(side_effect=lambda *args: self.state)
        self.engine = engine_module.AutoTradingEngine(self.provider)
        self.engine.broker = self.broker
        self.engine._estimate_equity_reference = Mock(return_value=10000.)
        self.engine.config.update(enabled=True, fixed_order_value_usd=1000, max_order_value_usd=1000)
        self.engine._get_symbol_backtest_stats = Mock(return_value={'win_rate': .7, 'avg_win': .03, 'avg_loss': .01})
        self.engine._get_regime_position_multiplier = Mock(return_value=1.)
        self.row = types.SimpleNamespace(risk_profile='moderate')
        self.db = Mock()
        self.db.query.return_value.filter.return_value.first.side_effect = lambda: self.row
        conn = types.ModuleType('database.connection'); conn.SessionLocal = Mock(return_value=self.db)
        models = types.ModuleType('database.models'); models.UserProfile = types.SimpleNamespace(user_id=7)
        self.modules = module_overrides({'database': types.ModuleType('database'),
                                               'database.connection': conn, 'database.models': models})
        self.modules.__enter__(); self.addCleanup(self.modules.__exit__, None, None, None)

    def size(self, **kw):
        return self.engine._calculate_position_size(100, confidence=.9, volatility=.2,
                                                    symbol='BTCUSDC', user_id=7, **kw)

    def test_sizing_exception_never_fixed_fallback(self):
        with patch('services.position_sizing.calculate_position_size', side_effect=RuntimeError('risk failed')):
            self.assertEqual(self.size(), 0)
        self.assertEqual(self.engine.trade_log[-1]['type'], 'SIZING_REJECTED')
        self.assertIn('risk failed', self.engine.trade_log[-1]['message'])
        self.broker.place_live_order.assert_not_called()

    def test_missing_provider_blocks(self):
        self.engine.risk_snapshot_provider = None
        self.assertEqual(self.size(), 0)

    def test_snapshot_failures_block(self):
        for changes in ({'user_id': 8}, {'broker': Mock()}, {'paper_mode': True}, {'complete': False},
                        {'observed_at': datetime.now(timezone.utc)-timedelta(minutes=2)},
                        {'observed_at': datetime.now(timezone.utc)+timedelta(minutes=2)},
                        {'equity_usd': float('nan')}, {'peak_equity_usd': 0},
                        {'available_cash_usd': float('inf')}, {'exposure_by_symbol': {'BTCUSDC': -1}}):
            with self.subTest(changes=changes):
                self.state = replace(self.state, **changes)
                self.assertEqual(self.size(), 0)
                self.state = SizingSnapshot(7, self.broker, False, datetime.now(timezone.utc),10000.,10000.,10000.,{},True)

    def test_db_error_blocks_and_closes(self):
        self.db.query.side_effect = RuntimeError('db unavailable')
        self.assertEqual(self.size(), 0)
        self.db.close.assert_called_once()

    def test_missing_and_unknown_profiles_block(self):
        for row in (None, types.SimpleNamespace(risk_profile='unknown')):
            self.row = row
            self.assertEqual(self.size(), 0)

    def test_profiles_change_actual_size(self):
        sizes = []
        for profile in ('conservative', 'moderate', 'aggressive'):
            self.row.risk_profile = profile
            sizes.append(self.size())
        self.assertTrue(0 < sizes[0] < sizes[1] < sizes[2], sizes)

    def test_real_drawdown_reductions(self):
        sizes = []
        for dd in (0, .06, .11, .16):
            self.state = replace(self.state, peak_equity_usd=10000/(1-dd))
            sizes.append(self.size())
        self.assertTrue(sizes[0] > sizes[1] > sizes[2] > sizes[3] > 0, sizes)

    def test_symbol_exposure_forwarded_and_capped(self):
        self.state = replace(self.state, exposure_by_symbol={'BTCUSDC': 499.23})
        self.assertEqual(self.size(), 0)  # Remaining capacity below $1 minimum.
        self.state = replace(self.state, exposure_by_symbol={'BTCUSDC': 498.77})
        self.assertLessEqual(self.size()*100, 1.23)

    def test_portfolio_exposure_blocks(self):
        self.state = replace(self.state, exposure_by_symbol={'ETHUSDC': 2500})
        self.assertEqual(self.size(), 0)

    def test_cash_and_config_caps(self):
        self.state = replace(self.state, available_cash_usd=5.1234567)
        self.assertLessEqual(self.size()*100, 5.1234567)
        self.engine.config['fixed_order_value_usd'] = 2
        self.assertLessEqual(self.size()*100, 2)
        self.engine.config['max_order_value_usd'] = float('nan')
        self.assertEqual(self.size(), 0)

    def test_block_and_malformed_engine_results(self):
        for decision, value in (('block', 50), ('unknown', 50), ('execute', float('nan')), ('execute', -1)):
            with self.subTest(decision=decision, value=value), patch('services.position_sizing.calculate_position_size',
                    return_value=types.SimpleNamespace(decision=decision, recommended_notional=value, reasoning='denied')):
                self.assertEqual(self.size(), 0)

    def test_invalid_input_rejected_by_real_sizer(self):
        defaults = dict(account_balance=10000, signal_confidence=.9, volatility=.2,
                        current_drawdown=0, current_portfolio_exposure=0, price=100)
        for name in defaults:
            for value in (float('nan'), float('inf'), -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    calculate_position_size(SizingInput(**{**defaults, name: value}))

    def test_circuit_breaker_failure_prevents_execution(self):
        cb = types.ModuleType('services.circuit_breaker')
        cb.check_circuit_breaker = Mock(side_effect=RuntimeError('unavailable'))
        with module_overrides({'services.circuit_breaker': cb}):
            self.assertIsNone(self.engine.place_auto_order(dict(symbol='BTCUSDC', action='buy', price=100, confidence=.99), 7))
        self.broker.place_live_order.assert_not_called()
        dca.execute_dca_plan.assert_not_called()

    def test_order_path_sizing_rejection_and_kill_switch(self):
        # Exercise actual place_auto_order, with external decision services faked.
        mods = {}
        def module(name, **attrs):
            mod = types.ModuleType(name)
            for key, value in attrs.items(): setattr(mod, key, value)
            mods[name] = mod
        module('services.circuit_breaker', check_circuit_breaker=lambda *a: {'tripped': False})
        module('services.market_hours', is_tradeable_now=lambda *a: True)
        module('services.smart_score', smart_score_calculator=types.SimpleNamespace(
            calculate_smart_score=lambda *a: {'smart_score': 99, 'signals': {}}))
        module('ml', __path__=[])
        module('ml.correlation_engine', check_correlation_risk=lambda **kw: {'allowed': True, 'max_allowed_usd': 1000})
        prediction = dict(symbol='BTCUSDC', action='buy', price=100, confidence=.99,
                          ensemble_vote={'strong_consensus': True, 'final_signal': 'BUY'})
        with module_overrides(mods), patch.dict('os.environ', {'ALLOW_LIVE_TRADING': 'false'}):
            self.provider.side_effect = RuntimeError('snapshot unavailable')
            self.assertIsNone(self.engine.place_auto_order(prediction, 7))
            self.assertTrue(any(e['type']=='SIZING_REJECTED' for e in self.engine.trade_log))
            self.provider.side_effect = lambda *a: self.state
            self.engine.trade_log.clear()
            self.assertIsNone(self.engine.place_auto_order(prediction, 7))
            self.assertTrue(any('ALLOW_LIVE_TRADING' in e['message'] for e in self.engine.trade_log))
            self.broker.place_live_order.assert_not_called()
            # Positive control proves the fake order path is reachable.
            with patch.dict('os.environ', {'ALLOW_LIVE_TRADING': 'true'}):
                self.broker.place_live_order.return_value = {'price': 100, 'order_id': 'offline-only'}
                self.assertIsNotNone(self.engine.place_auto_order(prediction, 7))
                self.broker.place_live_order.assert_called_once()
            self.broker.place_live_order.reset_mock()
            self.engine.open_positions.clear()
            for verdict in ({}, {'allowed': True, 'max_allowed_usd': float('nan')}):
                mods['ml.correlation_engine'].check_correlation_risk = lambda **kw: verdict
                self.assertIsNone(self.engine.place_auto_order(prediction, 7))
                self.broker.place_live_order.assert_not_called()
            def unavailable(**kw): raise RuntimeError('exposure unavailable')
            mods['ml.correlation_engine'].check_correlation_risk = unavailable
            self.assertIsNone(self.engine.place_auto_order(prediction, 7))
        self.broker.place_live_order.assert_not_called()
        dca.execute_dca_plan.assert_not_called()

    def test_original_sizing_regressions(self):
        spec = importlib.util.spec_from_file_location('existing_sizing_tests', ROOT/'tests/test_position_sizing.py')
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        for name in sorted(vars(original)):
            if name.startswith('test_'):
                with self.subTest(original_test=name): getattr(original, name)()


if __name__ == '__main__': unittest.main(verbosity=2)
