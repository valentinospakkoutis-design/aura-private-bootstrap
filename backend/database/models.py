"""
SQLAlchemy models for AURA database
"""

import os
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date, UniqueConstraint, ARRAY, LargeBinary
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


class BrokerCredential(Base):
    """Persistent broker API credentials (encrypted)"""
    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True, index=True)
    broker_name = Column(String(50), unique=True, nullable=False, index=True)
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

