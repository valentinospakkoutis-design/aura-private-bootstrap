"""
SQLAlchemy models for AURA database
"""

import os
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date, UniqueConstraint, ARRAY, LargeBinary, Numeric, Index
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
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
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


class BrokerCredential(Base):
    """Persistent broker API credentials (encrypted)"""
    __tablename__ = "broker_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", name="uq_broker_credentials_user_broker"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    broker_name = Column(String(50), nullable=False, index=True)
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)
    testnet = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class HistoricalPrice(Base):
    """Historical OHLCV price data for training"""
    __tablename__ = "historical_prices"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_hist_price_symbol_date"),)

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_type = Column(String(20), nullable=False)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class FinancialNews(Base):
    """Financial news headlines for sentiment analysis"""
    __tablename__ = "financial_news"

    id = Column(Integer, primary_key=True, index=True)
    headline = Column(Text, nullable=False)
    summary = Column(Text)
    source = Column(String(100))
    url = Column(Text)
    published_at = Column(DateTime, nullable=False, index=True)
    symbols = Column(Text)  # comma-separated related symbols
    sentiment_score = Column(Float)
    sentiment_label = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingFeature(Base):
    """Engineered features for ML training"""
    __tablename__ = "training_features"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_train_feat_symbol_date"),)

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    features = Column(JSON, nullable=False)
    target_return = Column(Float)
    target_direction = Column(String(5))
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelRegistry(Base):
    """Model registry with performance metrics"""
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float)
    training_samples = Column(Integer)
    features_used = Column(Text)  # comma-separated
    trained_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class TrainingLog(Base):
    """Training pipeline execution logs"""
    __tablename__ = "training_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), nullable=False, index=True)
    phase = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # running, completed, failed
    message = Column(Text)
    progress = Column(Float, default=0)  # 0-100
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class BacktestResult(Base):
    """Backtest simulation results"""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    backtest_date = Column(DateTime, default=datetime.utcnow)
    start_date = Column(Date)
    end_date = Column(Date)
    initial_capital = Column(Float, default=10000)
    final_capital = Column(Float)
    total_return_pct = Column(Float)
    annual_return_pct = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown_pct = Column(Float)
    win_rate_pct = Column(Float)
    profit_factor = Column(Float)
    total_trades = Column(Integer)
    total_fees_paid = Column(Float)
    calmar_ratio = Column(Float)
    metrics_json = Column(JSON)


class RLModel(Base):
    """RL agent training history"""
    __tablename__ = "rl_models"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    episode = Column(Integer)
    train_sharpe = Column(Float)
    val_sharpe = Column(Float)
    train_return_pct = Column(Float)
    val_return_pct = Column(Float)
    total_trades = Column(Integer)
    model_path = Column(Text)
    model_data = Column(LargeBinary, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    is_best = Column(Boolean, default=False)
    trained_at = Column(DateTime, default=datetime.utcnow)


class RLPrediction(Base):
    """RL agent daily predictions"""
    __tablename__ = "rl_predictions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    action = Column(String(10))
    confidence = Column(Float)
    predicted_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    """
    Per-user personalization — risk, objectives, mode, overrides.
    Mutable state (one active profile per user).
    """
    __tablename__ = "user_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    risk_profile = Column(String(20), nullable=False, default="moderate")  # conservative/moderate/aggressive
    investment_objective = Column(String(30), default="balanced_growth")  # capital_preservation/balanced_growth/aggressive_growth
    preferred_mode = Column(String(20), default="manual_assist")  # manual_assist/guided/autopilot
    confidence_threshold_override = Column(Float, nullable=True)
    max_portfolio_exposure_override = Column(Float, nullable=True)
    max_position_size_override = Column(Float, nullable=True)
    paper_balance = Column(Float, nullable=False, default=10000.0)
    paper_positions = Column(JSON, default=[])
    behavior_flags_json = Column(JSON, default={})
    notes_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  NEXT-GEN SCHEMA — Trust, Explainability, Intelligence
# ═══════════════════════════════════════════════════════════════

class DecisionAudit(Base):
    """Append-only log of every AI decision with full explainability."""
    __tablename__ = "decision_audit"
    __table_args__ = (
        Index("ix_decision_audit_symbol_ts", "symbol", "created_at"),
        Index("ix_decision_audit_user", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # BUY/SELL/HOLD/NO-TRADE/BLOCKED
    confidence_score = Column(Float)
    confidence_band = Column(String(10))  # low/medium/high
    market_regime = Column(String(20))  # bullish/bearish/sideways/volatile
    reason_codes = Column(ARRAY(Text), default=[])
    blocked_by = Column(ARRAY(Text), default=[])
    sizing_adjustments = Column(ARRAY(Text), default=[])
    improvement_triggers = Column(ARRAY(Text), default=[])
    narrative_summary = Column(Text)
    machine_summary = Column(Text)
    smart_score = Column(Float)
    trend_score = Column(Float)
    price_change_pct = Column(Float)
    signal_agreement = Column(Float)
    using_ml_model = Column(Boolean)
    risk_profile = Column(String(20))
    sizing_decision = Column(String(10))  # execute/reduce/block
    sizing_notional = Column(Numeric)
    portfolio_risk_score = Column(Float)
    source = Column(String(30), default="decision_engine")
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AutopilotConfig(Base):
    """Mutable user autopilot mode configuration."""
    __tablename__ = "autopilot_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    mode = Column(String(20), nullable=False, default="balanced")  # safe/balanced/aggressive
    confidence_threshold = Column(Float, default=0.90)
    smart_score_threshold = Column(Integer, default=75)
    max_positions = Column(Integer, default=3)
    stop_loss_pct = Column(Float, default=0.03)
    take_profit_pct = Column(Float, default=0.05)
    fixed_order_value = Column(Float, default=10.0)
    check_interval_seconds = Column(Integer, default=60)
    is_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserAutopilotSettings(Base):
    """
    Mutable per-user autopilot state — current mode, enabled flag, overrides.
    One row per user (upsert pattern).
    """
    __tablename__ = "user_autopilot_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    current_mode = Column(String(20), nullable=False, default="balanced")  # safe/balanced/aggressive
    is_enabled = Column(Boolean, nullable=False, default=False)
    config_overrides_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutopilotModeChangeLog(Base):
    """
    Append-only audit trail of every autopilot mode change.
    Tracks who changed it, why, and what the previous mode was.
    """
    __tablename__ = "autopilot_mode_change_log"
    __table_args__ = (
        Index("ix_autopilot_change_user_ts", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    previous_mode = Column(String(20))
    new_mode = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(20), nullable=False, default="user")  # user/system/admin
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CircuitBreakerEvent(Base):
    """Append-only circuit breaker trip/reset window events."""
    __tablename__ = "circuit_breaker_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    rule_id = Column(String(100), nullable=False)
    reason = Column(String(500), nullable=False)
    tripped_at = Column(DateTime, default=datetime.utcnow)
    resume_at = Column(DateTime, nullable=False)
    reset_manually = Column(Boolean, default=False)


class PredictionOutcome(Base):
    """Prediction lifecycle tracking and delayed outcome evaluation."""
    __tablename__ = "prediction_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    price_at_prediction = Column(Float, nullable=False)
    price_7d_later = Column(Float, nullable=True)
    price_30d_later = Column(Float, nullable=True)
    was_correct_7d = Column(Boolean, nullable=True)
    was_correct_30d = Column(Boolean, nullable=True)
    pnl_7d_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    evaluated_at = Column(DateTime, nullable=True)


class AIDecisionEvent(Base):
    """
    Append-only log of every AI trading decision with full context.
    Central fact table — reason codes and counterfactuals link here via FK.
    """
    __tablename__ = "ai_decision_events"
    __table_args__ = (
        Index("ix_ai_decision_user_ts", "user_id", "created_at"),
        Index("ix_ai_decision_symbol_ts", "symbol", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # BUY/SELL/HOLD/NO-TRADE/BLOCKED/REDUCED
    confidence_score = Column(Float)
    confidence_band = Column(String(10))  # low/medium/high
    market_regime = Column(String(20))  # bullish/bearish/sideways/volatile
    narrative_summary = Column(Text)
    machine_summary = Column(Text)
    stop_loss_logic = Column(Text)
    take_profit_logic = Column(Text)
    expected_holding_profile = Column(Text)
    raw_signal_payload_json = Column(JSON, default={})
    audit_metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships to child tables
    reason_codes_rel = relationship("AIDecisionReasonCode", back_populates="decision_event", cascade="all, delete-orphan")
    counterfactuals_rel = relationship("AIDecisionCounterfactual", back_populates="decision_event", cascade="all, delete-orphan")


class AIDecisionReasonCode(Base):
    """
    Append-only relational reason codes for each decision.
    Queryable by code, category — not collapsed into a JSON blob.
    """
    __tablename__ = "ai_decision_reason_codes"
    __table_args__ = (
        Index("ix_ai_reason_code", "code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    decision_event_id = Column(Integer, ForeignKey("ai_decision_events.id"), nullable=False, index=True)
    code = Column(String(60), nullable=False)  # e.g. ML_POSITIVE_FORECAST, RISK_BLOCK
    category = Column(String(20), nullable=False)  # positive/risk/rejection/sizing/context
    detail_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    decision_event = relationship("AIDecisionEvent", back_populates="reason_codes_rel")


class AIDecisionCounterfactual(Base):
    """
    Append-only counterfactuals explaining what would change the decision.
    Types: why_not_opposite, why_not_wait, invalidation_condition, improvement_trigger.
    """
    __tablename__ = "ai_decision_counterfactuals"

    id = Column(Integer, primary_key=True, index=True)
    decision_event_id = Column(Integer, ForeignKey("ai_decision_events.id"), nullable=False, index=True)
    counterfactual_type = Column(String(30), nullable=False)  # why_not_opposite/why_not_wait/invalidation_condition/improvement_trigger
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    decision_event = relationship("AIDecisionEvent", back_populates="counterfactuals_rel")


class PortfolioSnapshot(Base):
    """Append-only periodic snapshot of portfolio state for analytics."""
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        Index("ix_portfolio_snap_user_ts", "user_id", "snapshot_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    total_value_usd = Column(Numeric, nullable=False)
    cash_usd = Column(Numeric)
    positions_value_usd = Column(Numeric)
    position_count = Column(Integer)
    exposure_by_class = Column(JSON)  # {"crypto": 70, "stock": 20, ...}
    exposure_by_symbol = Column(JSON)  # {"BTC": 2000, "ETH": 1500, ...}
    portfolio_risk_score = Column(Float)
    concentration_warnings = Column(ARRAY(Text), default=[])
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)


class SimulationRun(Base):
    """Append-only record of each simulation execution."""
    __tablename__ = "simulation_runs"
    __table_args__ = (
        Index("ix_sim_run_user_ts", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    strategy = Column(String(30), nullable=False)
    symbols = Column(ARRAY(Text))
    timeframe_days = Column(Integer)
    initial_capital = Column(Numeric, nullable=False)
    final_capital = Column(Numeric)
    pnl = Column(Numeric)
    pnl_pct = Column(Float)
    max_drawdown_pct = Column(Float)
    sharpe_ratio = Column(Float)
    win_rate_pct = Column(Float)
    total_trades = Column(Integer)
    profit_factor = Column(Float)
    config_json = Column(JSON)  # Full input params for reproducibility
    trades_json = Column(JSON)  # All trades for replay
    disclaimer_accepted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StrategyHealth(Base):
    """Append-only health/performance tracking per strategy."""
    __tablename__ = "strategy_health"
    __table_args__ = (
        Index("ix_strat_health_name_ts", "strategy_name", "recorded_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(30), nullable=False, index=True)
    symbol = Column(String(20), nullable=True)
    score = Column(Float)
    signal_action = Column(String(10))
    signal_confidence = Column(Float)
    consensus_action = Column(String(10))
    consensus_agreement = Column(Float)
    explanation = Column(Text)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)


class RiskEvent(Base):
    """Append-only log of risk events — blocks, reductions, alerts."""
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_event_symbol_ts", "symbol", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    symbol = Column(String(20), index=True)
    event_type = Column(String(30), nullable=False)  # block/reduce/alert/skip
    reason_codes = Column(ARRAY(Text), default=[])
    explanation = Column(Text)
    source = Column(String(30))  # auto_trader/position_sizing/portfolio_state
    severity = Column(String(10), default="warning")
    sizing_before = Column(Numeric)
    sizing_after = Column(Numeric)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PersistentRiskEvent(Base):
    """
    Append-only log of all meaningful risk interventions.
    Tracks blocked trades, size reductions, exposure caps, volatility/drawdown throttles,
    and portfolio concentration warnings with full numeric context.
    Optionally links to the AI decision that triggered the intervention.
    """
    __tablename__ = "persistent_risk_events"
    __table_args__ = (
        Index("ix_prisk_user_ts", "user_id", "created_at"),
        Index("ix_prisk_symbol_ts", "symbol", "created_at"),
        Index("ix_prisk_event_type", "event_type"),
        Index("ix_prisk_decision_event", "related_decision_event_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    symbol = Column(String(20), nullable=True, index=True)
    related_decision_event_id = Column(
        Integer,
        ForeignKey("ai_decision_events.id"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(30), nullable=False)
    # blocked_trade / size_reduced / exposure_warning / drawdown_throttle / volatility_throttle / risk_pause
    severity = Column(String(10), nullable=False, default="warning")  # info / warning / critical
    reason_code = Column(String(60), nullable=False)
    summary = Column(Text, nullable=False)
    details_json = Column(JSON, default={})
    original_requested_notional = Column(Numeric, nullable=True)
    adjusted_notional = Column(Numeric, nullable=True)
    original_requested_quantity = Column(Numeric, nullable=True)
    adjusted_quantity = Column(Numeric, nullable=True)
    portfolio_risk_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship back to the decision that triggered this
    decision_event = relationship("AIDecisionEvent", foreign_keys=[related_decision_event_id])


class PersistentFeedEvent(Base):
    """
    Append-only user-facing AI feed / timeline.
    Supports prioritization, deduplication, expiration, and per-user read state.
    """
    __tablename__ = "persistent_feed_events"
    __table_args__ = (
        Index("ix_pfeed_user_ts", "user_id", "created_at"),
        Index("ix_pfeed_user_type_ts", "user_id", "event_type", "created_at"),
        Index("ix_pfeed_dedupe", "dedupe_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    source_type = Column(String(30), nullable=False)
    # decision_engine / risk_engine / portfolio_engine / simulation_engine / system
    event_type = Column(String(30), nullable=False, index=True)
    # market_insight / trade_opportunity / risk_alert / exposure_warning /
    # no_trade_explanation / autopilot_update / portfolio_health / personalization_insight
    priority = Column(String(10), nullable=False, default="medium")  # low / medium / high / critical
    title = Column(Text, nullable=False)
    short_summary = Column(Text, nullable=False)
    full_explanation = Column(Text, nullable=True)
    related_symbol = Column(String(20), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)
    risk_level = Column(String(10), nullable=True)  # low / medium / high
    action_suggestion = Column(Text, nullable=True)
    source_reference_type = Column(String(30), nullable=True)
    # ai_decision_event / persistent_risk_event / simulation_run / etc.
    source_reference_id = Column(Integer, nullable=True)
    dedupe_key = Column(String(64), nullable=True, unique=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    reads = relationship("FeedEventRead", back_populates="feed_event", cascade="all, delete-orphan")


class FeedEventRead(Base):
    """
    Append-only read receipts for feed events.
    One row per user per event — unique constraint prevents duplicate reads.
    """
    __tablename__ = "feed_event_reads"
    __table_args__ = (
        UniqueConstraint("feed_event_id", "user_id", name="uq_feed_read_event_user"),
        Index("ix_feed_read_user_ts", "user_id", "read_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    feed_event_id = Column(Integer, ForeignKey("persistent_feed_events.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow)

    feed_event = relationship("PersistentFeedEvent", back_populates="reads")


# ═══════════════════════════════════════════════════════════════
#  Portfolio State & Exposure History
# ═══════════════════════════════════════════════════════════════

class PortfolioStateSnapshot(Base):
    """
    Append-only periodic snapshot of portfolio state.
    Parent table — symbol and cluster exposures link here via FK.
    """
    __tablename__ = "portfolio_state_snapshots"
    __table_args__ = (
        Index("ix_pstate_user_ts", "user_id", "snapshot_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    snapshot_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_equity = Column(Numeric, nullable=False)
    available_cash = Column(Numeric, nullable=False)
    total_exposure = Column(Numeric, nullable=False)
    net_exposure = Column(Numeric, nullable=False)
    gross_exposure = Column(Numeric, nullable=False)
    drawdown_pct = Column(Float, nullable=True)
    concentration_score = Column(Float, nullable=True)
    diversification_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships to child tables
    symbol_exposures = relationship("PortfolioSymbolExposure", back_populates="snapshot", cascade="all, delete-orphan")
    cluster_exposures = relationship("PortfolioClusterExposure", back_populates="snapshot", cascade="all, delete-orphan")


class PortfolioSymbolExposure(Base):
    """
    Append-only per-symbol exposure within a portfolio snapshot.
    One row per symbol per snapshot — relational, not JSON.
    """
    __tablename__ = "portfolio_symbol_exposures"
    __table_args__ = (
        Index("ix_psymexp_snapshot", "portfolio_snapshot_id"),
        Index("ix_psymexp_symbol", "symbol"),
    )

    id = Column(Integer, primary_key=True, index=True)
    portfolio_snapshot_id = Column(Integer, ForeignKey("portfolio_state_snapshots.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(30), nullable=True)
    direction = Column(String(10), nullable=False, default="long")  # long / short / flat
    quantity = Column(Numeric, nullable=False)
    market_value = Column(Numeric, nullable=False)
    exposure_pct = Column(Float, nullable=False)
    unrealized_pnl = Column(Numeric, nullable=True)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    snapshot = relationship("PortfolioStateSnapshot", back_populates="symbol_exposures")


class PortfolioClusterExposure(Base):
    """
    Append-only per-cluster/group exposure within a portfolio snapshot.
    Tracks correlated asset groups (large_cap_crypto, tech_stocks, etc.).
    """
    __tablename__ = "portfolio_cluster_exposures"
    __table_args__ = (
        Index("ix_pclusexp_snapshot", "portfolio_snapshot_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    portfolio_snapshot_id = Column(Integer, ForeignKey("portfolio_state_snapshots.id"), nullable=False, index=True)
    cluster_name = Column(String(40), nullable=False)
    gross_exposure = Column(Numeric, nullable=False)
    net_exposure = Column(Numeric, nullable=False)
    exposure_pct = Column(Float, nullable=False)
    risk_weight = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    snapshot = relationship("PortfolioStateSnapshot", back_populates="cluster_exposures")


# ═══════════════════════════════════════════════════════════════
#  Simulation & Backtesting Persistence
# ═══════════════════════════════════════════════════════════════

class PersistentSimulationRun(Base):
    """
    Append-only record of each simulation/backtest execution.
    Stores full config for reproducibility — results and timeseries link via FK.
    """
    __tablename__ = "persistent_simulation_runs"
    __table_args__ = (
        Index("ix_psim_user_ts", "user_id", "created_at"),
        Index("ix_psim_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    strategy_id = Column(String(30), nullable=True)  # ai_follow / conservative_ai / buy_and_hold / custom
    run_type = Column(String(20), nullable=False, default="backtest")  # backtest / paper_simulation / what_if
    symbol_universe_json = Column(JSON, nullable=False)  # ["BTCUSDC", "ETHUSDC", ...]
    timeframe_start = Column(DateTime, nullable=True)
    timeframe_end = Column(DateTime, nullable=True)
    initial_capital = Column(Numeric, nullable=False)
    config_json = Column(JSON, nullable=False)  # Full input params for exact reproducibility
    assumptions_json = Column(JSON, default={})  # Slippage model, fee model, fill assumptions
    disclaimer_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued / running / completed / failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    results = relationship("SimulationResult", back_populates="simulation_run", cascade="all, delete-orphan")
    timeseries = relationship("SimulationResultTimeseries", back_populates="simulation_run", cascade="all, delete-orphan")


class SimulationResult(Base):
    """
    Append-only summary metrics for a completed simulation run.
    One row per run — the distilled output.
    """
    __tablename__ = "simulation_results"
    __table_args__ = (
        Index("ix_simresult_run", "simulation_run_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    simulation_run_id = Column(Integer, ForeignKey("persistent_simulation_runs.id"), nullable=False, index=True)
    total_return_pct = Column(Float, nullable=True)
    annualized_return_pct = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    win_rate_pct = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    avg_trade_return_pct = Column(Float, nullable=True)
    pnl_value = Column(Numeric, nullable=True)
    risk_metrics_json = Column(JSON, default={})
    summary_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    simulation_run = relationship("PersistentSimulationRun", back_populates="results")


class SimulationResultTimeseries(Base):
    """
    Append-only equity curve points for a simulation run.
    Enables charting equity over the simulation timeframe.
    """
    __tablename__ = "simulation_result_timeseries"
    __table_args__ = (
        Index("ix_simts_run_ts", "simulation_run_id", "point_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    simulation_run_id = Column(Integer, ForeignKey("persistent_simulation_runs.id"), nullable=False, index=True)
    point_timestamp = Column(DateTime, nullable=False)
    equity_value = Column(Numeric, nullable=False)
    drawdown_pct = Column(Float, nullable=True)
    exposure_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    simulation_run = relationship("PersistentSimulationRun", back_populates="timeseries")


# ═══════════════════════════════════════════════════════════════
#  Strategy Platform
# ═══════════════════════════════════════════════════════════════

class PersistentStrategyRegistry(Base):
    """
    Mutable registry of all trading strategies.
    Each row defines a strategy's identity, scope, and config schema.
    Updated when strategies are versioned, enabled/disabled, or reconfigured.
    """
    __tablename__ = "persistent_strategy_registry"

    id = Column(Integer, primary_key=True, index=True)
    strategy_key = Column(String(40), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    asset_scope = Column(String(30), nullable=True)  # crypto / stock / multi / all
    holding_style = Column(String(30), nullable=True)  # intraday / swing / position / mixed
    risk_class = Column(String(20), nullable=True)  # conservative / moderate / aggressive
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(String(20), nullable=True, default="1.0")
    config_schema_json = Column(JSON, default={})  # JSON Schema for strategy params
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    health_snapshots = relationship("StrategyHealthSnapshot", back_populates="strategy", cascade="all, delete-orphan")
    allocations = relationship("StrategyAllocation", back_populates="strategy", cascade="all, delete-orphan")


class StrategyHealthSnapshot(Base):
    """
    Append-only periodic health/performance snapshot per strategy.
    Tracks how well each strategy is performing over time.
    """
    __tablename__ = "strategy_health_snapshots"
    __table_args__ = (
        Index("ix_strathsnap_strat_ts", "strategy_id", "snapshot_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("persistent_strategy_registry.id"), nullable=False, index=True)
    snapshot_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    health_score = Column(Float, nullable=False)  # 0-100
    recent_return_pct = Column(Float, nullable=True)
    recent_drawdown_pct = Column(Float, nullable=True)
    win_rate_pct = Column(Float, nullable=True)
    volatility_score = Column(Float, nullable=True)
    stability_score = Column(Float, nullable=True)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("PersistentStrategyRegistry", back_populates="health_snapshots")


class StrategyAllocation(Base):
    """
    Append-only record of strategy allocation decisions.
    Tracks what percentage of capital is allocated to each strategy over time.
    user_id is nullable for global/system-level allocation state.
    """
    __tablename__ = "strategy_allocations"
    __table_args__ = (
        Index("ix_stratalloc_strat_ts", "strategy_id", "allocation_timestamp"),
        Index("ix_stratalloc_user_ts", "user_id", "allocation_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("persistent_strategy_registry.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    allocation_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    target_allocation_pct = Column(Float, nullable=False)
    actual_allocation_pct = Column(Float, nullable=True)
    reason_summary = Column(Text, nullable=True)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("PersistentStrategyRegistry", back_populates="allocations")


# ═══════════════════════════════════════════════════════════════
#  Unified Audit Trail
# ═══════════════════════════════════════════════════════════════

class AuditEvent(Base):
    """
    Append-only unified audit trail across all AURA domains.
    Provides a single cross-domain view of operational events.

    Does NOT replace domain-specific tables (auth_audit_logs, live_order_audit_logs,
    ai_decision_events, persistent_risk_events, etc.) — those retain full
    domain-specific detail. This table captures a normalized summary of
    every significant event for operational visibility and compliance.
    """
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_user_ts", "user_id", "created_at"),
        Index("ix_audit_domain_ts", "event_domain", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_severity_ts", "severity", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    event_domain = Column(String(20), nullable=False, index=True)
    # decision / risk / autopilot / simulation / strategy / profile / execution / system
    event_name = Column(String(60), nullable=False)
    entity_type = Column(String(40), nullable=True)
    # ai_decision_event / persistent_risk_event / simulation_run / strategy / user_profile / order / etc.
    entity_id = Column(Integer, nullable=True)
    severity = Column(String(10), nullable=False, default="info")  # info / warning / critical
    summary = Column(Text, nullable=False)
    payload_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

