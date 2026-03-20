from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from database.connection import check_db_connection, sync_engine
from ops.kill_switch import kill_switch_manager
from ops.observability import runtime_monitor
from ops.secret_loader import SecretConfigurationError, SecretRule, get_secret_loader
from services.execution.broker_client import ExecutionConfigurationError, execution_profile, validate_execution_provider_or_raise
from services.execution.startup_checks import StartupSafetyError, startup_checker
from services.live_trading import LiveTradingService
from services.risk_governor import risk_governor_service


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

GO = "GO"
LIMITED_GO = "LIMITED GO"
NO_GO = "NO-GO"


@dataclass
class ReadinessCheck:
    name: str
    status: str
    details: str
    next_action: Optional[str] = None
    critical: bool = True


@dataclass
class LiveReadinessReport:
    verdict: str
    checks: List[ReadinessCheck]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "generated_at": self.generated_at,
            "checks": [asdict(check) for check in self.checks],
        }


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class LiveReadinessChecker:
    def __init__(self, backend_root: Optional[Path] = None):
        self.backend_root = backend_root or Path(__file__).resolve().parents[1]

    @staticmethod
    def _env(name: str, default: str = "") -> str:
        return os.getenv(name, default).strip()

    def _is_live_intended(self) -> bool:
        trading_mode = self._env("TRADING_MODE", "paper").lower()
        allow_live = _truthy(self._env("ALLOW_LIVE_TRADING", "false"))
        profile = execution_profile()
        return trading_mode == "live" or allow_live or profile in {"prod", "production", "staging", "live"}

    def run(self) -> LiveReadinessReport:
        checks = [
            self.check_test_status(),
            self.check_execution_provider_safety(),
            self.check_broker_credentials(),
            self.check_binance_static_ip_auth_gate(),
            self.check_database_readiness(),
            self.check_kill_switch_status(),
            self.check_risk_governor_readiness(),
            self.check_startup_live_guards(),
            self.check_observability_alerting(),
            self.check_operator_limits(),
        ]
        verdict = self._compute_verdict(checks)
        return LiveReadinessReport(
            verdict=verdict,
            checks=checks,
            generated_at=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def _compute_verdict(checks: Sequence[ReadinessCheck]) -> str:
        for check in checks:
            if check.critical and check.status == FAIL:
                return NO_GO

        if any(check.status in {WARNING, UNKNOWN} for check in checks):
            return LIMITED_GO

        return GO

    def check_test_status(self) -> ReadinessCheck:
        pytest_ini = self.backend_root / "pytest.ini"
        if not pytest_ini.exists():
            return ReadinessCheck(
                name="test_status",
                status=WARNING,
                details="pytest.ini is missing; hardened baseline config cannot be confirmed.",
                next_action="Restore pytest.ini baseline config before live deployment.",
                critical=False,
            )

        lastfailed_path = self.backend_root / ".pytest_cache" / "v" / "cache" / "lastfailed"
        if not lastfailed_path.exists():
            return ReadinessCheck(
                name="test_status",
                status=WARNING,
                details="No pytest lastfailed metadata found; last known deterministic test outcome is unknown.",
                next_action="Run backend baseline tests and keep pytest cache artifact.",
                critical=False,
            )

        try:
            payload = json.loads(lastfailed_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and len(payload) > 0:
                return ReadinessCheck(
                    name="test_status",
                    status=WARNING,
                    details=f"pytest cache reports {len(payload)} last failed test entries.",
                    next_action="Re-run baseline tests and resolve failures before first live capital.",
                    critical=False,
                )
        except Exception:
            return ReadinessCheck(
                name="test_status",
                status=UNKNOWN,
                details="Could not parse pytest failure metadata.",
                next_action="Re-run baseline tests to regenerate test metadata.",
                critical=False,
            )

        return ReadinessCheck(
            name="test_status",
            status=PASS,
            details="Baseline test configuration present and pytest cache shows no last failed tests.",
            critical=False,
        )

    def check_execution_provider_safety(self) -> ReadinessCheck:
        provider = self._env("EXECUTION_PROVIDER", "stub").lower()
        trading_mode = self._env("TRADING_MODE", "paper").lower()
        allow_live = _truthy(self._env("ALLOW_LIVE_TRADING", "false"))
        live_intended = self._is_live_intended()

        try:
            validate_execution_provider_or_raise(
                provider=provider,
                trading_mode=trading_mode,
                allow_live_trading=allow_live,
            )
        except ExecutionConfigurationError as exc:
            return ReadinessCheck(
                name="execution_provider",
                status=FAIL,
                details=str(exc),
                next_action="Set EXECUTION_PROVIDER to a real provider and keep stub disabled in live context.",
            )

        if live_intended and trading_mode != "live":
            return ReadinessCheck(
                name="execution_provider",
                status=FAIL,
                details="Live intent detected but TRADING_MODE is not 'live'.",
                next_action="Set TRADING_MODE=live for launch context.",
            )

        if live_intended and not allow_live:
            return ReadinessCheck(
                name="execution_provider",
                status=FAIL,
                details="Live intent detected but ALLOW_LIVE_TRADING is not enabled.",
                next_action="Set ALLOW_LIVE_TRADING=true only after readiness is fully green.",
            )

        details = f"Provider={provider}, TRADING_MODE={trading_mode}, ALLOW_LIVE_TRADING={str(allow_live).lower()}"
        if not live_intended:
            return ReadinessCheck(
                name="execution_provider",
                status=WARNING,
                details=f"{details}. Live intent not fully enabled yet.",
                next_action="Enable live intent vars only when ready to launch.",
                critical=False,
            )

        return ReadinessCheck(name="execution_provider", status=PASS, details=details)

    def check_broker_credentials(self) -> ReadinessCheck:
        provider = self._env("EXECUTION_PROVIDER", "stub").lower()

        if provider != "binance":
            return ReadinessCheck(
                name="broker_credentials",
                status=WARNING,
                details=f"Credential rules for provider '{provider}' are not explicitly defined in this check.",
                next_action="Add provider-specific secret rules before production use.",
                critical=False,
            )

        rules = [
            SecretRule(name="BINANCE_API_KEY", min_length=16),
            SecretRule(name="BINANCE_API_SECRET", min_length=24),
        ]
        loader = get_secret_loader()
        try:
            loader.validate_live_requirements(rules)
        except SecretConfigurationError as exc:
            return ReadinessCheck(
                name="broker_credentials",
                status=FAIL,
                details=f"Broker credential validation failed: {exc}",
                next_action="Set strong broker credentials in secret backend; do not use defaults/placeholders.",
            )

        return ReadinessCheck(
            name="broker_credentials",
            status=PASS,
            details="Required broker secrets are present and pass minimum strength rules.",
        )

    def check_binance_static_ip_auth_gate(self) -> ReadinessCheck:
        provider = self._env("EXECUTION_PROVIDER", "stub").lower()
        trading_mode = self._env("TRADING_MODE", "paper").lower()
        allow_live = _truthy(self._env("ALLOW_LIVE_TRADING", "false"))
        live_intended = self._is_live_intended() or trading_mode == "live" or allow_live

        if provider != "binance" and not live_intended:
            return ReadinessCheck(
                name="binance_static_ip_auth",
                status=WARNING,
                details="Binance static-IP auth gate is not active because execution provider is not binance in current context.",
                next_action="Enable provider=binance in launch context when ready for live activation.",
                critical=False,
            )

        manual_verified = _truthy(self._env("AURA_STATIC_IP_AUTH_VERIFIED", "false"))
        verified_ip = self._env("AURA_EXECUTION_STATIC_PUBLIC_IP", "")
        verified_by = self._env("AURA_STATIC_IP_AUTH_VERIFIED_BY", "")
        verified_at = self._env("AURA_STATIC_IP_AUTH_VERIFIED_AT", "")
        evidence = self._env("AURA_STATIC_IP_AUTH_EVIDENCE", "")

        if manual_verified:
            details = (
                "Manual operator verification accepted for Binance signed auth from static-IP execution host "
                f"(ip={verified_ip or 'unset'}, verified_by={verified_by or 'unset'}, verified_at={verified_at or 'unset'})."
            )
            if evidence:
                details = f"{details} Evidence={evidence}."
            return ReadinessCheck(
                name="binance_static_ip_auth",
                status=PASS,
                details=details,
                critical=True,
            )

        return ReadinessCheck(
            name="binance_static_ip_auth",
            status=FAIL,
            details="Binance static-IP authenticated account access is not verified for live context.",
            next_action=(
                "Run signed /api/v3/account auth test from execution host static IP and set "
                "AURA_STATIC_IP_AUTH_VERIFIED=true with operator evidence."
            ),
            critical=True,
        )

    def _migration_state(self) -> tuple[bool, str]:
        alembic_ini = self.backend_root / "alembic.ini"
        if not alembic_ini.exists():
            return False, "Alembic config missing"

        config = Config(str(alembic_ini))
        config.set_main_option("script_location", str(self.backend_root / "alembic"))
        config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")))
        script_dir = ScriptDirectory.from_config(config)
        head_revision = script_dir.get_current_head()
        if not head_revision:
            return False, "Migration head revision unavailable"

        with sync_engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()

        current_revision = row[0] if row else None
        if current_revision != head_revision:
            return False, f"Migrations not current (db={current_revision}, head={head_revision})"

        return True, f"Current revision is at head ({head_revision})"

    def check_database_readiness(self) -> ReadinessCheck:
        if not check_db_connection():
            return ReadinessCheck(
                name="database_readiness",
                status=FAIL,
                details="Database is not reachable.",
                next_action="Restore DB connectivity and credentials before live deployment.",
            )

        required_tables = {
            "execution_orders",
            "execution_order_audit",
            "order_submission_ledger",
            "pnl_snapshots",
            "drawdown_events",
            "risk_shutdown_events",
            "alembic_version",
        }

        try:
            with sync_engine.connect() as conn:
                inspector = inspect(conn)
                present_tables = set(inspector.get_table_names())
        except SQLAlchemyError as exc:
            return ReadinessCheck(
                name="database_readiness",
                status=FAIL,
                details=f"Database schema inspection failed: {exc}",
                next_action="Verify DB permissions and schema visibility for readiness user.",
            )

        missing = sorted(required_tables - present_tables)
        if missing:
            return ReadinessCheck(
                name="database_readiness",
                status=FAIL,
                details=f"Missing required tables: {', '.join(missing)}",
                next_action="Run migrations/init so execution, idempotency, audit, and risk tables exist.",
            )

        migrations_ok, migration_details = self._migration_state()
        if not migrations_ok:
            return ReadinessCheck(
                name="database_readiness",
                status=FAIL,
                details=migration_details,
                next_action="Apply pending Alembic migrations before live launch.",
            )

        return ReadinessCheck(
            name="database_readiness",
            status=PASS,
            details=f"DB reachable; required execution/idempotency/audit/risk tables present; {migration_details}.",
        )

    def check_kill_switch_status(self) -> ReadinessCheck:
        status = kill_switch_manager.status()
        global_active = bool(status.get("global_active"))
        symbols = status.get("blocked_symbols") or []
        strategies = status.get("blocked_strategies") or []

        if global_active:
            return ReadinessCheck(
                name="kill_switch",
                status=WARNING,
                details="Global kill switch is currently active.",
                next_action="If launch is intended, deactivate global kill switch with approved runbook.",
                critical=False,
            )

        if symbols or strategies:
            return ReadinessCheck(
                name="kill_switch",
                status=WARNING,
                details=f"Scoped blocks active (symbols={len(symbols)}, strategies={len(strategies)}).",
                next_action="Confirm scoped blocks are intentional for first-live rollout.",
                critical=False,
            )

        return ReadinessCheck(name="kill_switch", status=PASS, details="No active global or scoped kill-switch blocks.", critical=False)

    def check_risk_governor_readiness(self) -> ReadinessCheck:
        required_thresholds = {
            "caution_drawdown_pct": risk_governor_service.config.caution_drawdown_pct,
            "defense_drawdown_pct": risk_governor_service.config.defense_drawdown_pct,
            "preservation_drawdown_pct": risk_governor_service.config.preservation_drawdown_pct,
            "hard_shutdown_drawdown_pct": risk_governor_service.config.hard_shutdown_drawdown_pct,
            "daily_loss_limit_pct": risk_governor_service.config.daily_loss_limit_pct,
            "session_loss_limit_pct": risk_governor_service.config.session_loss_limit_pct,
        }
        invalid = [name for name, value in required_thresholds.items() if value is None or float(value) <= 0]
        if invalid:
            return ReadinessCheck(
                name="risk_governor",
                status=FAIL,
                details=f"Invalid risk governor thresholds: {', '.join(invalid)}",
                next_action="Set all risk thresholds to positive values.",
            )

        try:
            status = risk_governor_service.get_status(mode="live")
        except Exception as exc:
            return ReadinessCheck(
                name="risk_governor",
                status=FAIL,
                details=f"Risk governor status unavailable: {exc}",
                next_action="Fix risk governor datastore access before live launch.",
            )

        state = str(status.get("risk_state", "UNKNOWN")).upper()
        if state == "SHUTDOWN":
            return ReadinessCheck(
                name="risk_governor",
                status=FAIL,
                details="Risk governor is in SHUTDOWN state; new live execution must remain blocked.",
                next_action="Investigate losses/drawdown and clear shutdown only via approved incident procedure.",
            )

        if state == "PRESERVATION":
            return ReadinessCheck(
                name="risk_governor",
                status=FAIL,
                details="Risk governor is in PRESERVATION state; live launch is unsafe.",
                next_action="Stabilize equity and return governor to DEFENSE/CAUTION/NORMAL before launch.",
            )

        if state in {"DEFENSE", "CAUTION"}:
            return ReadinessCheck(
                name="risk_governor",
                status=WARNING,
                details=f"Risk governor is in {state} state.",
                next_action="Limit rollout size and monitor drawdown closely.",
                critical=False,
            )

        return ReadinessCheck(
            name="risk_governor",
            status=PASS,
            details="PnL and drawdown governor is readable with valid thresholds and non-blocking state.",
        )

    def _jwt_secret_is_strong(self) -> tuple[bool, str]:
        secret = self._env("JWT_SECRET_KEY")
        if not secret:
            return False, "JWT_SECRET_KEY missing"
        weak_values = {
            "aura-secret-key-change-in-production-2025",
            "changeme",
            "secret",
            "password",
        }
        if len(secret) < 32 or secret.lower() in weak_values:
            return False, "JWT_SECRET_KEY is weak"
        return True, "JWT secret strength OK"

    def check_startup_live_guards(self) -> ReadinessCheck:
        provider = self._env("EXECUTION_PROVIDER", "stub").lower()
        trading_mode = self._env("TRADING_MODE", "paper").lower()
        allow_live = _truthy(self._env("ALLOW_LIVE_TRADING", "false"))

        if _truthy(self._env("REAL_BROKER_STUB_MODE", "false")):
            return ReadinessCheck(
                name="startup_live_guards",
                status=FAIL,
                details="REAL_BROKER_STUB_MODE is enabled in launch context.",
                next_action="Disable REAL_BROKER_STUB_MODE before first live capital deployment.",
            )

        try:
            validate_execution_provider_or_raise(
                provider=provider,
                trading_mode=trading_mode,
                allow_live_trading=allow_live,
            )
        except ExecutionConfigurationError as exc:
            return ReadinessCheck(
                name="startup_live_guards",
                status=FAIL,
                details=str(exc),
                next_action="Fix provider/live-mode safety alignment before startup.",
            )

        if self._is_live_intended():
            try:
                startup_checker.validate_live_requirements(provider=provider)
            except StartupSafetyError as exc:
                return ReadinessCheck(
                    name="startup_live_guards",
                    status=FAIL,
                    details=f"Startup live guard failed: {exc}",
                    next_action="Resolve startup safety guard failure before launch.",
                )

        jwt_ok, jwt_details = self._jwt_secret_is_strong()
        if not jwt_ok:
            return ReadinessCheck(
                name="startup_live_guards",
                status=FAIL,
                details=jwt_details,
                next_action="Set a strong JWT secret (>=32 chars, high entropy).",
            )

        return ReadinessCheck(name="startup_live_guards", status=PASS, details=f"Startup checks and JWT guard passed ({jwt_details}).")

    def check_observability_alerting(self) -> ReadinessCheck:
        mode = str(getattr(runtime_monitor.alerts, "mode", "console")).lower()
        webhook_url = str(getattr(runtime_monitor.alerts, "webhook_url", "") or "").strip()
        live_intended = self._is_live_intended()

        if not hasattr(runtime_monitor, "metrics") or not hasattr(runtime_monitor, "alerts"):
            return ReadinessCheck(
                name="observability_alerts",
                status=FAIL,
                details="Runtime monitor hooks are unavailable.",
                next_action="Restore runtime monitor wiring before live rollout.",
            )

        if live_intended and mode in {"console", ""}:
            return ReadinessCheck(
                name="observability_alerts",
                status=WARNING,
                details="Alerting is console-only in live context.",
                next_action="Configure webhook alert path for live incident visibility.",
                critical=False,
            )

        if live_intended and mode in {"webhook", "both"} and not webhook_url:
            return ReadinessCheck(
                name="observability_alerts",
                status=WARNING,
                details="Webhook alert mode selected but ALERT_WEBHOOK_URL is not configured.",
                next_action="Set ALERT_WEBHOOK_URL or switch mode intentionally with operator sign-off.",
                critical=False,
            )

        return ReadinessCheck(name="observability_alerts", status=PASS, details=f"Alerting configured in mode '{mode}'.", critical=False)

    def check_operator_limits(self) -> ReadinessCheck:
        service = LiveTradingService()
        risk = service.risk_settings

        max_pos = float(risk.get("max_position_size_percent", 0.0) or 0.0)
        max_daily = float(risk.get("max_daily_loss_percent", 0.0) or 0.0)
        allowed_symbol = self._env("AURA_FIRST_LIVE_ALLOWED_SYMBOL", "BTCUSDT").upper()

        if max_pos <= 0 or max_daily <= 0:
            return ReadinessCheck(
                name="first_live_guardrails",
                status=FAIL,
                details="Operator risk caps are not configured with positive values.",
                next_action="Set positive max position size and daily loss limits before launch.",
                critical=True,
            )

        first_live_profile = _truthy(self._env("AURA_FIRST_LIVE_PROFILE", "false"))

        if not first_live_profile:
            return ReadinessCheck(
                name="first_live_guardrails",
                status=WARNING,
                details=(
                    f"Risk caps present (max_position_size_percent={max_pos}, max_daily_loss_percent={max_daily}) "
                    "but explicit first-live profile flag is not enabled."
                ),
                next_action="Set AURA_FIRST_LIVE_PROFILE=true when small-capital first-live controls are approved.",
                critical=False,
            )

        if max_pos > 0.25 or max_daily > 0.50:
            return ReadinessCheck(
                name="first_live_guardrails",
                status=WARNING,
                details=f"First-live profile enabled but tiny-cap guardrails are too loose (position={max_pos}%, daily_loss={max_daily}%).",
                next_action="Tighten first-live guardrails to <=0.25% position and <=0.50% daily loss.",
                critical=False,
            )

        if allowed_symbol != "BTCUSDT":
            return ReadinessCheck(
                name="first_live_guardrails",
                status=WARNING,
                details=f"First-live symbol is set to {allowed_symbol} (expected safest default BTCUSDT).",
                next_action="Use BTCUSDT as single-symbol first-live scope unless operator explicitly approves another symbol.",
                critical=False,
            )

        return ReadinessCheck(
            name="first_live_guardrails",
            status=PASS,
            details=(
                "First-live profile enabled with tiny-cap guardrails "
                f"(position={max_pos}%, daily_loss={max_daily}%, symbol={allowed_symbol})."
            ),
            critical=False,
        )


def render_text_report(report: LiveReadinessReport) -> str:
    display_names = {
        "test_status": "Test Status / Baseline",
        "execution_provider": "Execution Provider",
        "broker_credentials": "Broker Credentials",
        "binance_static_ip_auth": "Binance Static-IP Auth",
        "database_readiness": "Database Readiness",
        "kill_switch": "Kill Switch Status",
        "risk_governor": "Risk Governor",
        "startup_live_guards": "Startup / Live Guards",
        "observability_alerts": "Observability / Alerts",
        "first_live_guardrails": "First-Live Guardrails",
    }

    lines = ["AURA LIVE READINESS REPORT", "--------------------------"]
    for check in report.checks:
        label = display_names.get(check.name, check.name)
        lines.append(f"{label}: {check.status}")
        lines.append(f"  - {check.details}")
        if check.next_action:
            lines.append(f"  - Next action: {check.next_action}")

    lines.append("")
    lines.append(f"FINAL VERDICT: {report.verdict}")
    return "\n".join(lines)


def exit_code_for_verdict(verdict: str) -> int:
    if verdict == GO:
        return 0
    if verdict == LIMITED_GO:
        return 1
    return 2
