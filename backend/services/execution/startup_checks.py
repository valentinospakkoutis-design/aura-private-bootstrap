from __future__ import annotations

import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from database.connection import check_db_connection, sync_engine
from ops.secret_loader import SecretConfigurationError, SecretRule, get_secret_loader


class StartupSafetyError(RuntimeError):
    """Raised when live startup safety gates fail."""


class ExecutionStartupChecker:
    @staticmethod
    def is_live_mode() -> bool:
        trading_mode = os.getenv("TRADING_MODE", "paper").strip().lower()
        allow_live = os.getenv("ALLOW_LIVE_TRADING", "false").strip().lower() in {"1", "true", "yes", "on"}
        return trading_mode == "live" or allow_live

    def validate_live_requirements(self, *, provider: str) -> None:
        if not self.is_live_mode():
            return

        if not check_db_connection():
            raise StartupSafetyError("Database must be reachable before live startup")

        if provider == "binance":
            loader = get_secret_loader()
            try:
                loader.validate_live_requirements(
                    [
                        SecretRule(name="BINANCE_API_KEY", min_length=16),
                        SecretRule(name="BINANCE_API_SECRET", min_length=24),
                    ]
                )
            except SecretConfigurationError as exc:
                raise StartupSafetyError("Live startup blocked: broker secrets invalid") from exc

        self._assert_migrations_up_to_date()

    @staticmethod
    def _assert_migrations_up_to_date() -> None:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        alembic_ini = os.path.join(backend_root, "alembic.ini")
        if not os.path.exists(alembic_ini):
            raise StartupSafetyError("Live startup blocked: Alembic config missing")

        config = Config(alembic_ini)
        script_dir = ScriptDirectory.from_config(config)
        head_revision = script_dir.get_current_head()
        if not head_revision:
            raise StartupSafetyError("Live startup blocked: migration head unavailable")

        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            current_revision = row[0] if row else None

        if current_revision != head_revision:
            raise StartupSafetyError("Live startup blocked: database migrations are not up-to-date")


startup_checker = ExecutionStartupChecker()
