"""
SQLAlchemy models for AURA database
"""

import os
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    portfolio_positions = relationship("PortfolioPosition", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """User session model (for JWT tokens)"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String(512), unique=True, index=True, nullable=False)
    refresh_token = Column(String(512), unique=True, index=True, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class PortfolioPosition(Base):
    """Portfolio position model"""
    __tablename__ = "portfolio_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    asset_id = Column(String(50), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_buy_price = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=True)
    total_value = Column(Float, nullable=False, default=0.0)
    pnl = Column(Float, nullable=False, default=0.0)
    pnl_percent = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="portfolio_positions")


class Transaction(Base):
    """Transaction model"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    asset_id = Column(String(50), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # BUY, SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)  # For SELL transactions
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="transactions")


class PriceData(Base):
    """Historical price data model"""
    __tablename__ = "price_data"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {"postgresql_partition_by": "RANGE (timestamp)"} if os.getenv("USE_PARTITIONING") == "true" else {},
    )


class Prediction(Base):
    """AI prediction model"""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), nullable=False, index=True)
    predicted_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    model_version = Column(String(50), nullable=True)
    prediction_date = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelTraining(Base):
    """ML model training history"""
    __tablename__ = "model_trainings"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), nullable=False, index=True)
    model_type = Column(String(50), nullable=False)
    model_path = Column(String(255), nullable=False)
    metrics = Column(JSON, nullable=True)  # Store MAE, RMSE, R², etc.
    training_samples = Column(Integer, nullable=False)
    test_samples = Column(Integer, nullable=False)
    trained_at = Column(DateTime, default=datetime.utcnow, index=True)


class OrderSubmissionLedger(Base):
    """Durable idempotency ledger for order submissions"""
    __tablename__ = "order_submission_ledger"

    id = Column(Integer, primary_key=True, index=True)
    principal_id = Column(String(255), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_fingerprint = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    result_order_id = Column(String(128), nullable=True)
    result_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("principal_id", "idempotency_key", name="uq_order_submission_principal_key"),
    )


class ExecutionOrder(Base):
    """Durable live execution order ledger."""

    __tablename__ = "execution_orders"

    id = Column(Integer, primary_key=True, index=True)
    internal_order_id = Column(String(64), unique=True, index=True, nullable=False)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    request_fingerprint = Column(String(128), nullable=False)
    broker = Column(String(64), nullable=False, index=True)
    broker_order_id = Column(String(128), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=False, default=0.0)
    avg_fill_price = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, index=True)
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)


class ExecutionOrderAudit(Base):
    """Full audit events for execution lifecycle."""

    __tablename__ = "execution_order_audit"

    id = Column(Integer, primary_key=True, index=True)
    internal_order_id = Column(String(64), ForeignKey("execution_orders.internal_order_id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PnLSnapshot(Base):
    """Persistent PnL and equity snapshots for risk governor."""

    __tablename__ = "pnl_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)  # paper/live
    equity = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    daily_pnl = Column(Float, nullable=False, default=0.0)
    session_pnl = Column(Float, nullable=False, default=0.0)
    rolling_7d_pnl = Column(Float, nullable=False, default=0.0)
    peak_equity = Column(Float, nullable=False)
    drawdown_pct = Column(Float, nullable=False, default=0.0)
    max_drawdown_pct = Column(Float, nullable=False, default=0.0)
    risk_state = Column(String(32), nullable=False, index=True)
    shutdown_active = Column(Boolean, nullable=False, default=False)
    win_streak = Column(Integer, nullable=False, default=0)
    loss_streak = Column(Integer, nullable=False, default=0)
    source = Column(String(64), nullable=False, default="unknown")
    trading_day = Column(String(10), nullable=False, index=True)
    session_id = Column(String(32), nullable=False, index=True)


class DrawdownEvent(Base):
    """Auditable risk state transitions driven by drawdown/loss limits."""

    __tablename__ = "drawdown_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    previous_state = Column(String(32), nullable=False)
    new_state = Column(String(32), nullable=False, index=True)
    drawdown_pct = Column(Float, nullable=False, default=0.0)
    trigger_reason = Column(String(128), nullable=False)
    daily_pnl = Column(Float, nullable=False, default=0.0)
    session_pnl = Column(Float, nullable=False, default=0.0)


class RiskShutdownEvent(Base):
    """Hard preservation/shutdown trigger history with enforcement details."""

    __tablename__ = "risk_shutdown_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    state = Column(String(32), nullable=False, index=True)
    trigger_reason = Column(String(128), nullable=False)
    drawdown_pct = Column(Float, nullable=False, default=0.0)
    daily_pnl = Column(Float, nullable=False, default=0.0)
    session_pnl = Column(Float, nullable=False, default=0.0)
    symbol = Column(String(32), nullable=True)
    strategy = Column(String(64), nullable=True)
    kill_switch_activated = Column(Boolean, nullable=False, default=False)
    cancel_open_orders = Column(Boolean, nullable=False, default=False)

