from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("aura.execution")


class MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)


@dataclass
class AlertEvent:
    level: str
    kind: str
    message: str
    details: Dict[str, Any]


class AlertManager:
    def __init__(self) -> None:
        self.mode = os.getenv("ALERT_CHANNEL", "console").strip().lower()
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        self.timeout_seconds = int(os.getenv("ALERT_WEBHOOK_TIMEOUT_SECONDS", "5"))

    def send(self, event: AlertEvent) -> None:
        payload = {
            "timestamp": int(time.time()),
            "level": event.level,
            "kind": event.kind,
            "message": event.message,
            "details": event.details,
        }

        if self.mode in {"webhook", "both"} and self.webhook_url:
            try:
                requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
            except requests.RequestException:
                logger.error("Failed to deliver webhook alert")

        if self.mode in {"console", "both", "webhook"}:
            logger.warning("ALERT %s", json.dumps(payload, sort_keys=True))


class RuntimeMonitor:
    def __init__(self) -> None:
        self.metrics = MetricsStore()
        self.alerts = AlertManager()
        self._validation_failures: deque[float] = deque(maxlen=500)
        self._validation_spike_window = int(os.getenv("VALIDATION_FAILURE_WINDOW_SECONDS", "60"))
        self._validation_spike_threshold = int(os.getenv("VALIDATION_FAILURE_SPIKE_THRESHOLD", "10"))

    def log_event(self, *, event: str, level: str = "info", **kwargs: Any) -> None:
        payload = {"event": event, "ts": int(time.time()), **kwargs}
        line = json.dumps(payload, sort_keys=True)
        if level == "error":
            logger.error(line)
        elif level == "warning":
            logger.warning(line)
        else:
            logger.info(line)

    def record_order_submitted(self, *, order_id: str, symbol: str, latency_ms: float) -> None:
        self.metrics.inc("orders_submitted")
        self.log_event(event="order_submitted", order_id=order_id, symbol=symbol, status="SUBMITTED", latency_ms=latency_ms)

    def record_order_failed(self, *, symbol: str, error_type: str, latency_ms: float) -> None:
        self.metrics.inc("orders_failed")
        self.log_event(event="order_failed", level="error", symbol=symbol, status="FAILED", latency_ms=latency_ms, error_type=error_type)

    def record_broker_error(self, *, error_type: str, retryable: bool) -> None:
        self.metrics.inc("broker_errors")
        self.log_event(event="broker_error", level="error", error_type=error_type, retryable=retryable)
        if not retryable:
            self.alerts.send(
                AlertEvent(
                    level="critical",
                    kind="broker_unreachable",
                    message="Non-retryable broker error",
                    details={"error_type": error_type},
                )
            )

    def record_idempotency_replay(self) -> None:
        self.metrics.inc("idempotency_replays")

    def record_kill_switch_activation(self, *, scope: str, value: str) -> None:
        self.metrics.inc("kill_switch_activations")
        self.alerts.send(
            AlertEvent(
                level="critical",
                kind="kill_switch_activated",
                message="Kill switch activated",
                details={"scope": scope, "value": value},
            )
        )

    def record_circuit_breaker_trigger(self, *, provider: str) -> None:
        self.metrics.inc("circuit_breaker_triggers")
        self.alerts.send(
            AlertEvent(
                level="critical",
                kind="circuit_breaker_opened",
                message="Execution circuit breaker opened",
                details={"provider": provider},
            )
        )

    def record_reconciliation_mismatch(self, *, count: int) -> None:
        if count <= 0:
            return
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="reconciliation_mismatch",
                message="Reconciliation detected mismatches",
                details={"count": count},
            )
        )

    def record_high_latency(self, *, operation: str, latency_ms: float) -> None:
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="high_latency",
                message="Broker operation latency is high",
                details={"operation": operation, "latency_ms": latency_ms},
            )
        )

    def record_retry_spike(self, *, operation: str, retries: int) -> None:
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="retry_spike",
                message="Broker retries exceeded normal threshold",
                details={"operation": operation, "retries": retries},
            )
        )

    def record_validation_failure(self, *, symbol: str) -> None:
        now = time.time()
        self._validation_failures.append(now)
        while self._validation_failures and (now - self._validation_failures[0]) > self._validation_spike_window:
            self._validation_failures.popleft()

        if len(self._validation_failures) >= self._validation_spike_threshold:
            self.alerts.send(
                AlertEvent(
                    level="critical",
                    kind="validation_failures_spike",
                    message="Validation failures spike detected",
                    details={"symbol": symbol, "count": len(self._validation_failures)},
                )
            )

    def record_drawdown_state_change(self, *, mode: str, previous_state: str, new_state: str, drawdown_pct: float) -> None:
        self.log_event(
            event="drawdown_state_change",
            mode=mode,
            previous_state=previous_state,
            new_state=new_state,
            drawdown_pct=drawdown_pct,
        )
        if new_state in {"PRESERVATION", "SHUTDOWN"}:
            self.alerts.send(
                AlertEvent(
                    level="critical",
                    kind="drawdown_threshold_breached",
                    message="Drawdown threshold breached",
                    details={
                        "mode": mode,
                        "previous_state": previous_state,
                        "new_state": new_state,
                        "drawdown_pct": drawdown_pct,
                    },
                )
            )

    def record_shutdown_trigger(self, *, mode: str, state: str, reason: str, drawdown_pct: float) -> None:
        self.alerts.send(
            AlertEvent(
                level="critical",
                kind="risk_shutdown_triggered",
                message="Risk governor triggered shutdown protection",
                details={"mode": mode, "state": state, "reason": reason, "drawdown_pct": drawdown_pct},
            )
        )

    def record_defense_mode(self, *, mode: str, drawdown_pct: float) -> None:
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="defense_mode_entered",
                message="Risk governor entered defense mode",
                details={"mode": mode, "drawdown_pct": drawdown_pct},
            )
        )

    def record_rapid_pnl_deterioration(self, *, mode: str, daily_loss_pct: float) -> None:
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="rapid_pnl_deterioration",
                message="Rapid PnL deterioration detected",
                details={"mode": mode, "daily_loss_pct": daily_loss_pct},
            )
        )

    def record_losing_streak_warning(self, *, mode: str, loss_streak: int) -> None:
        self.alerts.send(
            AlertEvent(
                level="warning",
                kind="losing_streak",
                message="Repeated losing streak detected",
                details={"mode": mode, "loss_streak": loss_streak},
            )
        )

    def record_equity_mismatch(self, *, mode: str, expected_equity: float, observed_equity: float) -> None:
        self.alerts.send(
            AlertEvent(
                level="critical",
                kind="equity_reconciliation_anomaly",
                message="Equity mismatch detected during reconciliation",
                details={
                    "mode": mode,
                    "expected_equity": expected_equity,
                    "observed_equity": observed_equity,
                },
            )
        )


runtime_monitor = RuntimeMonitor()
