from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional, Tuple

from ops.observability import runtime_monitor


@dataclass
class KillSwitchAuditEvent:
    action: str
    scope: str
    value: Optional[str]
    actor: str
    reason: Optional[str]
    emergency: bool
    cancel_open_orders: bool
    timestamp: str


class KillSwitchManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self.global_active = False
        self.emergency_mode = False
        self.cancel_open_orders = False
        self.blocked_symbols: set[str] = set()
        self.blocked_strategies: set[str] = set()
        self.audit_events: List[KillSwitchAuditEvent] = []

    def _audit(self, event: KillSwitchAuditEvent) -> None:
        self.audit_events.append(event)
        runtime_monitor.record_kill_switch_activation(scope=event.scope, value=event.value or "global")

    def activate(
        self,
        *,
        actor: str,
        scope: str,
        value: Optional[str] = None,
        reason: Optional[str] = None,
        emergency: bool = False,
        cancel_open_orders: bool = False,
    ) -> Dict:
        normalized_scope = scope.strip().lower()
        normalized_value = value.strip().upper() if value else None
        with self._lock:
            if normalized_scope == "global":
                self.global_active = True
                self.emergency_mode = emergency
                self.cancel_open_orders = cancel_open_orders
            elif normalized_scope == "symbol":
                if not normalized_value:
                    raise ValueError("symbol value is required")
                self.blocked_symbols.add(normalized_value)
            elif normalized_scope == "strategy":
                if not normalized_value:
                    raise ValueError("strategy value is required")
                self.blocked_strategies.add(normalized_value)
            else:
                raise ValueError("scope must be global, symbol, or strategy")

            event = KillSwitchAuditEvent(
                action="activate",
                scope=normalized_scope,
                value=normalized_value,
                actor=actor,
                reason=reason,
                emergency=bool(emergency),
                cancel_open_orders=bool(cancel_open_orders),
                timestamp=datetime.utcnow().isoformat(),
            )
            self._audit(event)
            return self.status()

    def deactivate(self, *, actor: str, scope: str, value: Optional[str] = None, reason: Optional[str] = None) -> Dict:
        normalized_scope = scope.strip().lower()
        normalized_value = value.strip().upper() if value else None
        with self._lock:
            if normalized_scope == "global":
                self.global_active = False
                self.emergency_mode = False
                self.cancel_open_orders = False
            elif normalized_scope == "symbol":
                if not normalized_value:
                    raise ValueError("symbol value is required")
                self.blocked_symbols.discard(normalized_value)
            elif normalized_scope == "strategy":
                if not normalized_value:
                    raise ValueError("strategy value is required")
                self.blocked_strategies.discard(normalized_value)
            else:
                raise ValueError("scope must be global, symbol, or strategy")

            self.audit_events.append(
                KillSwitchAuditEvent(
                    action="deactivate",
                    scope=normalized_scope,
                    value=normalized_value,
                    actor=actor,
                    reason=reason,
                    emergency=False,
                    cancel_open_orders=False,
                    timestamp=datetime.utcnow().isoformat(),
                )
            )
            return self.status()

    def status(self) -> Dict:
        with self._lock:
            return {
                "global_active": self.global_active,
                "emergency_mode": self.emergency_mode,
                "cancel_open_orders": self.cancel_open_orders,
                "blocked_symbols": sorted(self.blocked_symbols),
                "blocked_strategies": sorted(self.blocked_strategies),
                "audit_events": [event.__dict__ for event in self.audit_events[-50:]],
                "timestamp": datetime.utcnow().isoformat(),
            }

    def is_blocked(self, *, symbol: str, strategy: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        normalized_symbol = symbol.strip().upper()
        normalized_strategy = strategy.strip().upper() if strategy else None
        with self._lock:
            if self.global_active:
                return True, "GLOBAL_KILL_SWITCH_ACTIVE"
            if normalized_symbol in self.blocked_symbols:
                return True, "SYMBOL_KILL_SWITCH_ACTIVE"
            if normalized_strategy and normalized_strategy in self.blocked_strategies:
                return True, "STRATEGY_KILL_SWITCH_ACTIVE"
            return False, None


kill_switch_manager = KillSwitchManager()
