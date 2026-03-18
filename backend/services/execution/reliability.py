from __future__ import annotations

import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable, Deque

from ops.observability import runtime_monitor
from services.execution.broker_client import BrokerClientError


@dataclass
class GuardConfig:
    max_retries: int = int(os.getenv("BROKER_MAX_RETRIES", "3"))
    backoff_base_seconds: float = float(os.getenv("BROKER_BACKOFF_BASE_SECONDS", "0.25"))
    call_timeout_seconds: float = float(os.getenv("BROKER_CALL_TIMEOUT_SECONDS", "12"))
    circuit_failure_threshold: int = int(os.getenv("BROKER_CIRCUIT_FAILURE_THRESHOLD", "5"))
    circuit_window_seconds: int = int(os.getenv("BROKER_CIRCUIT_WINDOW_SECONDS", "60"))
    circuit_open_seconds: int = int(os.getenv("BROKER_CIRCUIT_OPEN_SECONDS", "30"))
    high_latency_ms: float = float(os.getenv("BROKER_HIGH_LATENCY_MS", "1000"))


class BrokerExecutionGuard:
    def __init__(self, provider: str, config: GuardConfig | None = None) -> None:
        self.provider = provider
        self.config = config or GuardConfig()
        self._failures: Deque[float] = deque()
        self._circuit_open_until = 0.0

    def _cleanup_failures(self) -> None:
        now = time.time()
        while self._failures and (now - self._failures[0]) > self.config.circuit_window_seconds:
            self._failures.popleft()

    def _record_failure(self) -> None:
        now = time.time()
        self._failures.append(now)
        self._cleanup_failures()
        if len(self._failures) >= self.config.circuit_failure_threshold:
            self._circuit_open_until = now + self.config.circuit_open_seconds
            runtime_monitor.record_circuit_breaker_trigger(provider=self.provider)

    def _retryable_error(self, error: Exception) -> bool:
        text = str(error).lower()
        non_retryable_markers = [
            "insufficient",
            "invalid",
            "min",
            "lot size",
            "quantity",
            "precision",
            "forbidden",
            "unauthorized",
            "rejected",
        ]
        if any(marker in text for marker in non_retryable_markers):
            return False

        retryable_markers = [
            "timeout",
            "network",
            "connection",
            "temporarily",
            "unreachable",
            "429",
            "-1003",
            "too many requests",
        ]
        return any(marker in text for marker in retryable_markers)

    def _run_with_timeout(self, fn: Callable[[], Any]) -> Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            try:
                return future.result(timeout=self.config.call_timeout_seconds)
            except FutureTimeout as exc:
                future.cancel()
                raise BrokerClientError("BROKER_TIMEOUT") from exc

    def execute(self, *, operation: str, symbol: str, fn: Callable[[], Any]) -> Any:
        now = time.time()
        self._cleanup_failures()
        if now < self._circuit_open_until:
            raise BrokerClientError("BROKER_CIRCUIT_OPEN")

        attempt = 0
        retry_count = 0
        while True:
            attempt += 1
            started = time.perf_counter()
            try:
                result = self._run_with_timeout(fn)
                latency_ms = (time.perf_counter() - started) * 1000.0
                if latency_ms > self.config.high_latency_ms:
                    runtime_monitor.record_high_latency(operation=operation, latency_ms=latency_ms)
                runtime_monitor.log_event(
                    event="broker_call",
                    provider=self.provider,
                    operation=operation,
                    symbol=symbol,
                    status="ok",
                    attempt=attempt,
                    latency_ms=latency_ms,
                )
                return result
            except Exception as exc:
                retryable = self._retryable_error(exc)
                runtime_monitor.record_broker_error(error_type=type(exc).__name__, retryable=retryable)
                self._record_failure()

                if not retryable or attempt > self.config.max_retries:
                    runtime_monitor.log_event(
                        event="broker_call",
                        level="error",
                        provider=self.provider,
                        operation=operation,
                        symbol=symbol,
                        status="failed",
                        attempt=attempt,
                        error_type=type(exc).__name__,
                    )
                    raise BrokerClientError(str(exc)) from exc

                retry_count += 1
                delay = self.config.backoff_base_seconds * (2 ** (attempt - 1))
                if "429" in str(exc) or "-1003" in str(exc):
                    delay = max(delay, 1.0)
                time.sleep(delay)

                if retry_count >= 2:
                    runtime_monitor.record_retry_spike(operation=operation, retries=retry_count)
