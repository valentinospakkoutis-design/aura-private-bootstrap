from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class BrokerOrderRequest:
    symbol: str
    side: str
    quantity: float
    order_type: str
    price: Optional[float]
    client_order_id: str


@dataclass(frozen=True)
class BrokerOrderResponse:
    broker_order_id: str
    status: ExecutionStatus
    symbol: str
    side: str
    quantity: float
    filled_quantity: float
    avg_fill_price: Optional[float]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class ExecutionRequest:
    broker: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    price: float
    stop_loss_price: Optional[float]
    idempotency_key: str
    user_email: str


@dataclass(frozen=True)
class ValidationContext:
    user_roles: List[str]
    allowed_symbols: List[str]
    portfolio_value: float
    max_position_size_percent: float
    max_daily_loss_percent: float
    current_daily_loss: float
    stop_loss_required: bool
    trading_mode: str
    env_trading_mode: str
    allow_live_trading: bool
    kill_switch_active: bool
    idempotency_reserved: bool
