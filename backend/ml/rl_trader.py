"""
Reinforcement Learning Trading Agent for AURA
PPO agent that learns to trade by maximizing risk-adjusted returns.
"""

import io
import os
import sys
import logging
import traceback
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from collections import deque

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical

logger = logging.getLogger(__name__)


WINDOW_SIZE = 30
N_FEATURES = 10  # features per timestep
STATE_DIM = WINDOW_SIZE * N_FEATURES  # 300
ACTION_DIM = 3   # HOLD=0, BUY=1, SELL=2
FEE = 0.001
RISK_FREE = 0.04 / 252

ALL_SYMBOLS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "SOL-USD",
    "ADA-USD", "AVAX-USD", "DOT-USD", "LINK-USD", "MATIC-USD",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "ASML", "SAP", "MC.PA",
    "GC=F", "SI=F", "PA=F", "PL=F", "CL=F", "ES=F", "NQ=F",
    "^TNX", "^IRX", "^TYX",
    "EURUSD=X", "GBPEUR=X", "USDJPY=X",
    "^VIX",
]


def _to_py(val):
    """Convert numpy types to native Python for PostgreSQL."""
    if hasattr(val, 'item'):
        return val.item()
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.integer,)):
        return int(val)
    return val

# Symbol aliases (same as backtester)
SYMBOL_ALIASES = {
    "BTC-USD": ["BTCUSDC", "BTCUSDT"], "ETH-USD": ["ETHUSDC", "ETHUSDT"],
    "GC=F": ["GC=F", "XAUUSDC"], "^VIX": ["^VIX", "VIX"],
}


def _compute_rsi(s, p=14):
    d = s.diff()
    g = d.where(d > 0, 0.0).rolling(p).mean()
    l = (-d.where(d < 0, 0.0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.inf)))


# ── Trading Environment ─────────────────────────────────────

class TradingEnv:
    """Gym-style trading environment. State=30-day feature window."""

    def __init__(self, df: pd.DataFrame, initial_capital: float = 10000.0):
        self.raw = df.copy()
        self.prices = df["close"].values
        self.n = len(self.prices)
        self.initial_capital = initial_capital

        # Pre-compute features (all from past data only)
        self._build_features()

    def _build_features(self):
        c = self.raw["close"]
        v = self.raw.get("volume", pd.Series(0, index=self.raw.index))
        self.features = pd.DataFrame(index=self.raw.index)
        self.features["ret1"] = c.pct_change().fillna(0)
        self.features["ret3"] = c.pct_change(3).fillna(0)
        self.features["ret5"] = c.pct_change(5).fillna(0)
        self.features["ret10"] = c.pct_change(10).fillna(0)
        self.features["ret20"] = c.pct_change(20).fillna(0)
        rsi = _compute_rsi(c)
        self.features["rsi"] = ((rsi.fillna(50) - 50) / 50)  # normalize to -1..1
        ma12 = c.ewm(span=12).mean()
        ma26 = c.ewm(span=26).mean()
        macd = ma12 - ma26
        self.features["macd"] = (macd / c).fillna(0)  # normalize by price
        bb_mid = c.rolling(20).mean()
        bb_std = c.rolling(20).std()
        self.features["bb_pos"] = ((c - bb_mid) / (2 * bb_std + 1e-8)).fillna(0).clip(-1, 1)
        vol_ma = v.rolling(20).mean()
        self.features["vol_ratio"] = ((v / vol_ma.replace(0, 1)) - 1).fillna(0).clip(-3, 3)
        # placeholder for position state (filled dynamically)
        self.features["position"] = 0.0
        self.feat_matrix = self.features.values.astype(np.float32)

    def reset(self) -> np.ndarray:
        self.step_idx = WINDOW_SIZE
        self.capital = self.initial_capital
        self.position = 0  # 0=flat, 1=long
        self.entry_price = 0.0
        self.trades = []
        self.portfolio = [self.initial_capital]
        self.trade_count_week = 0
        self.days_in_pos = 0
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        start = max(0, self.step_idx - WINDOW_SIZE)
        window = self.feat_matrix[start:self.step_idx].copy()
        # Set position feature in last row
        if len(window) > 0:
            window[-1, -1] = float(self.position)
        # Pad if needed
        if len(window) < WINDOW_SIZE:
            pad = np.zeros((WINDOW_SIZE - len(window), N_FEATURES), dtype=np.float32)
            window = np.vstack([pad, window])
        return window.flatten()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        """action: 0=HOLD, 1=BUY, 2=SELL"""
        price = self.prices[self.step_idx]
        prev_price = self.prices[self.step_idx - 1] if self.step_idx > 0 else price
        reward = 0.0
        fee_paid = 0.0

        # Track overtrading
        if self.step_idx % 5 == 0:
            self.trade_count_week = 0

        if action == 1 and self.position == 0 and price > 0:
            # BUY
            fee_paid = self.capital * FEE
            self.position = 1
            self.entry_price = price
            units = (self.capital - fee_paid) / price
            self.capital = 0
            self._units = units
            self.days_in_pos = 0
            self.trade_count_week += 1
            self.trades.append(("BUY", self.step_idx, price))

        elif action == 2 and self.position == 1 and price > 0:
            # SELL
            revenue = self._units * price
            fee_paid = revenue * FEE
            self.capital = revenue - fee_paid
            trade_return = (price - self.entry_price) / self.entry_price
            reward += trade_return * 100  # scale up for learning
            self.position = 0
            self.entry_price = 0
            self._units = 0
            self.trade_count_week += 1
            self.trades.append(("SELL", self.step_idx, price))

        # Position reward/penalty
        if self.position == 1:
            daily_ret = (price - prev_price) / prev_price if prev_price > 0 else 0
            reward += daily_ret * 50  # daily unrealized P/L
            self.days_in_pos += 1
            # Patience bonus for holding winners
            if daily_ret > 0 and self.days_in_pos > 3:
                reward += 0.1

        # Overtrading penalty
        if self.trade_count_week > 3:
            reward -= 0.5

        # Fee penalty
        reward -= fee_paid / self.initial_capital * 100

        # Update portfolio value
        pv = self.capital + (self._units * price if self.position == 1 else 0)
        self.portfolio.append(pv)

        self.step_idx += 1
        done = self.step_idx >= self.n - 1

        # Sharpe bonus at episode end
        if done:
            if self.position == 1:
                # Force liquidation
                revenue = self._units * self.prices[-1]
                self.capital = revenue - revenue * FEE
                self.position = 0
                pv = self.capital
                self.portfolio[-1] = pv

            rets = np.diff(self.portfolio) / np.maximum(np.array(self.portfolio[:-1]), 0.01)
            rets = rets[np.isfinite(rets)]
            if len(rets) > 1 and np.std(rets) > 0:
                sharpe = (np.mean(rets) - RISK_FREE) / np.std(rets) * np.sqrt(252)
                reward += float(sharpe) * 5  # strong sharpe incentive

        info = {
            "portfolio_value": pv,
            "total_return_pct": (pv - self.initial_capital) / self.initial_capital * 100,
            "total_trades": len(self.trades),
            "position": self.position,
        }

        return self._get_state(), reward, done, info


# ── PPO Agent ────────────────────────────────────────────────

class ActorCritic(nn.Module):
    def __init__(self, state_dim=STATE_DIM, action_dim=ACTION_DIM):
        super().__init__()
        self.shared = nn.Sequential(nn.Linear(state_dim, 256), nn.ReLU(), nn.Linear(256, 128), nn.ReLU())
        self.actor = nn.Linear(128, action_dim)
        self.critic = nn.Linear(128, 1)

    def forward(self, x):
        h = self.shared(x)
        return F.softmax(self.actor(h), dim=-1), self.critic(h)


class PPOAgent:
    def __init__(self, state_dim=STATE_DIM, action_dim=ACTION_DIM, lr=3e-4):
        self.model = ActorCritic(state_dim, action_dim)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.clip_ratio = 0.2
        self.entropy_coef = 0.01
        self.value_coef = 0.5
        self.gamma = 0.99
        self.lam = 0.95
        self.buffer = []

    def select_action(self, state: np.ndarray) -> Tuple[int, float, float]:
        with torch.no_grad():
            s = torch.FloatTensor(state).unsqueeze(0)
            probs, value = self.model(s)
            dist = Categorical(probs)
            action = dist.sample()
            return action.item(), dist.log_prob(action).item(), value.item()

    def store(self, state, action, reward, log_prob, value, done):
        self.buffer.append((state, action, reward, log_prob, value, done))

    def update(self):
        if len(self.buffer) < 32:
            return 0.0

        states, actions, rewards, old_log_probs, old_values, dones = zip(*self.buffer)
        states = torch.FloatTensor(np.array(states))
        actions = torch.LongTensor(actions)
        old_log_probs = torch.FloatTensor(old_log_probs)
        old_values = torch.FloatTensor(old_values)

        # Compute returns and advantages (GAE)
        returns = []
        advantages = []
        gae = 0
        R = 0
        for i in reversed(range(len(rewards))):
            if dones[i]:
                R = 0
                gae = 0
            R = rewards[i] + self.gamma * R
            delta = rewards[i] + self.gamma * (old_values[i + 1].item() if i + 1 < len(old_values) else 0) * (1 - dones[i]) - old_values[i].item()
            gae = delta + self.gamma * self.lam * (1 - dones[i]) * gae
            returns.insert(0, R)
            advantages.insert(0, gae)

        returns = torch.FloatTensor(returns)
        advantages = torch.FloatTensor(advantages)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update (3 epochs)
        total_loss = 0
        for _ in range(3):
            probs, values = self.model(states)
            dist = Categorical(probs)
            new_log_probs = dist.log_prob(actions)
            entropy = dist.entropy().mean()

            ratio = torch.exp(new_log_probs - old_log_probs)
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            value_loss = F.mse_loss(values.squeeze(), returns)
            loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy

            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
            self.optimizer.step()
            total_loss += loss.item()

        self.buffer.clear()
        return total_loss / 3

    def save_to_bytes(self) -> bytes:
        """Serialize model state_dict to bytes for DB storage."""
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        return buffer.getvalue()

    def load_from_bytes(self, data: bytes):
        """Load model state_dict from bytes."""
        buffer = io.BytesIO(data)
        self.model.load_state_dict(torch.load(buffer, map_location="cpu", weights_only=True))
        self.model.eval()

    def predict(self, state: np.ndarray) -> Tuple[str, float]:
        """Get action recommendation + confidence."""
        with torch.no_grad():
            s = torch.FloatTensor(state).unsqueeze(0)
            probs, _ = self.model(s)
            try:
                p = probs.squeeze().numpy()
                action = int(np.argmax(p))
                confidence = float(np.max(p))
                # Clamp to valid range
                confidence = max(0.0, min(1.0, confidence))
            except Exception:
                logger.warning("[RL] Failed to parse action probabilities, using fallback")
                action = 0  # HOLD
                confidence = 0.6
            names = ["HOLD", "BUY", "SELL"]
            return names[action], confidence if confidence > 0 else 0.6


# ── Training ─────────────────────────────────────────────────

def _load_prices(db, symbol: str) -> Optional[pd.DataFrame]:
    from database.models import HistoricalPrice
    aliases = [symbol]
    for k, v in SYMBOL_ALIASES.items():
        if symbol == k or symbol in v:
            aliases = [symbol, k] + v
            break
    for alias in aliases:
        rows = db.query(HistoricalPrice).filter(HistoricalPrice.symbol == alias).order_by(HistoricalPrice.date).all()
        if len(rows) >= 100:
            return pd.DataFrame([{"date": r.date, "open": r.open or r.close, "high": r.high or r.close,
                                   "low": r.low or r.close, "close": r.close, "volume": r.volume or 0}
                                  for r in rows]).set_index("date").sort_index()
    # yfinance fallback
    try:
        import yfinance as yf
        h = yf.Ticker(symbol).history(period="3y", interval="1d")
        if len(h) >= 100:
            return pd.DataFrame({"open": h["Open"], "high": h["High"], "low": h["Low"],
                                  "close": h["Close"], "volume": h["Volume"]}, index=h.index.date)
    except Exception:
        pass
    return None


def train_rl_agent(symbol: str, episodes: int = 300, job_id: str = "manual") -> Optional[Dict]:
    """Train RL agent for a single symbol. Always saves a row to rl_models."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import RLModel

    print(f"\n[RL] === Training {symbol} ({episodes} episodes) ===")
    db = SessionLocal()
    if not db:
        return {"symbol": symbol, "error": "No database"}

    try:
        df = _load_prices(db, symbol)
        if df is None or len(df) < 200:
            # Save failed row
            db.add(RLModel(
                symbol=str(symbol), episode=0, train_sharpe=0, val_sharpe=0,
                train_return_pct=0, val_return_pct=0, total_trades=0,
                model_path=str(symbol), model_data=None,
                metadata_={"status": "failed", "reason": f"insufficient_data_{len(df) if df is not None else 0}_rows"},
                is_best=False,
            ))
            db.commit()
            db.close()
            return {"symbol": symbol, "error": f"Insufficient data ({len(df) if df is not None else 0} rows)"}

        # Split: 70% train, 15% val, 15% test
        n = len(df)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)
        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]

        train_env = TradingEnv(train_df)
        val_env = TradingEnv(val_df)
        agent = PPOAgent()

        best_val_sharpe = -999
        no_improve = 0
        best_model_bytes = None
        best_val_return = 0
        best_val_trades = 0
        best_train_return = 0
        best_episode = 0

        for ep in range(episodes):
            # Train episode
            state = train_env.reset()
            ep_reward = 0
            while True:
                action, lp, val = agent.select_action(state)
                next_state, reward, done, info = train_env.step(action)
                agent.store(state, action, reward, lp, val, done)
                state = next_state
                ep_reward += reward
                if done:
                    break

            loss = agent.update()

            # Validate every 25 episodes
            if (ep + 1) % 25 == 0:
                val_state = val_env.reset()
                while True:
                    action, _, _ = agent.select_action(val_state)
                    val_state, _, val_done, val_info = val_env.step(action)
                    if val_done:
                        break

                val_rets = np.diff(val_env.portfolio) / np.maximum(np.array(val_env.portfolio[:-1]), 0.01)
                val_rets = val_rets[np.isfinite(val_rets)]
                val_sharpe = float((np.mean(val_rets) - RISK_FREE) / (np.std(val_rets) + 1e-8) * np.sqrt(252)) if len(val_rets) > 1 else 0
                val_return = val_info["total_return_pct"]

                print(f"[RL {symbol}] Ep {ep+1}: reward={ep_reward:.1f}, "
                      f"val_sharpe={val_sharpe:.3f}, val_return={val_return:.1f}%, "
                      f"trades={val_info['total_trades']}")

                if val_sharpe > best_val_sharpe:
                    best_val_sharpe = val_sharpe
                    best_model_bytes = agent.save_to_bytes()
                    best_val_return = val_return
                    best_val_trades = val_info["total_trades"]
                    best_train_return = info["total_return_pct"]
                    best_episode = ep + 1
                    no_improve = 0
                else:
                    no_improve += 25

                if no_improve >= 50:
                    print(f"[RL {symbol}] Early stop at episode {ep+1}")
                    break

        # Determine if training was successful
        training_failed = best_val_sharpe <= 0 or best_val_trades == 0

        if training_failed:
            # Save failed row with no model data
            db.add(RLModel(
                symbol=str(symbol), episode=int(best_episode),
                train_sharpe=0, val_sharpe=float(_to_py(best_val_sharpe)),
                train_return_pct=float(_to_py(best_train_return)),
                val_return_pct=float(_to_py(best_val_return)),
                total_trades=int(_to_py(best_val_trades)),
                model_path=str(symbol), model_data=None,
                metadata_={"status": "failed", "reason": "no_trades_or_negative_sharpe"},
                is_best=False,
            ))
            db.commit()
            print(f"[RL {symbol}] Failed: sharpe={best_val_sharpe:.3f}, trades={best_val_trades}")
        else:
            # Save successful model
            db.add(RLModel(
                symbol=str(symbol), episode=int(best_episode),
                train_sharpe=float(_to_py(0)),
                val_sharpe=float(_to_py(best_val_sharpe)),
                train_return_pct=float(_to_py(best_train_return)),
                val_return_pct=float(_to_py(best_val_return)),
                total_trades=int(_to_py(best_val_trades)),
                model_path=str(symbol), model_data=best_model_bytes,
                metadata_={"status": "success"},
                is_best=True,
            ))
            db.commit()

            # Mark only the best as active
            db.query(RLModel).filter(RLModel.symbol == symbol, RLModel.is_best == True).update({"is_best": False})
            best = db.query(RLModel).filter(
                RLModel.symbol == symbol, RLModel.model_data.isnot(None)
            ).order_by(RLModel.val_sharpe.desc()).first()
            if best:
                best.is_best = True
            db.commit()
            print(f"[RL {symbol}] Done: best_sharpe={best_val_sharpe:.3f}")

        result = {"symbol": symbol, "episodes": int(ep + 1),
                  "best_val_sharpe": round(float(_to_py(best_val_sharpe)), 3),
                  "stored_in_db": not training_failed}
        db.close()
        return result

    except Exception as e:
        print(f"[RL {symbol}] EXCEPTION: {e}")
        traceback.print_exc()
        try:
            db.add(RLModel(
                symbol=str(symbol), episode=0, train_sharpe=0, val_sharpe=0,
                train_return_pct=0, val_return_pct=0, total_trades=0,
                model_path=str(symbol), model_data=None,
                metadata_={"status": "failed", "reason": "exception", "error": str(e)[:500]},
                is_best=False,
            ))
            db.commit()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        return {"symbol": symbol, "error": str(e)}


def train_all_rl(force_retrain: bool = False, job_id: str = "manual") -> List[Dict]:
    """Train all symbols. Never exits early — every symbol is attempted."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import RLModel

    total = len(ALL_SYMBOLS)
    print(f"[TRAIN_ALL_START] {total} symbols to process, force_retrain={force_retrain}")
    results = []

    for i, symbol in enumerate(ALL_SYMBOLS):
        try:
            print(f"[TRAIN_SYMBOL_START] {symbol} ({i+1}/{total})")

            # Check if already trained — fresh session per check to avoid stale connections
            db = SessionLocal()
            try:
                existing = db.query(RLModel).filter_by(symbol=symbol).first()
            finally:
                db.close()

            if existing and not force_retrain:
                print(f"[TRAIN_SKIPPED] {symbol} — already has rl_models row")
                continue

            # Run training (train_rl_agent manages its own DB session)
            r = train_rl_agent(symbol, episodes=150, job_id=job_id)

            if r and "error" in r:
                print(f"[TRAIN_SYMBOL_FAILED] {symbol}: {r.get('error')}")
            else:
                print(f"[TRAIN_SYMBOL_SUCCESS] {symbol}")

            if r:
                results.append(r)
            continue

        except Exception as e:
            print(f"[TRAIN_SYMBOL_FAILED] {symbol}: {e}")
            traceback.print_exc()
            results.append({"symbol": symbol, "error": str(e)})
            continue  # always move to next symbol

    print(f"[TRAIN_ALL_DONE] Processed {total} symbols, {len(results)} results collected")
    return results


def get_rl_prediction(symbol: str) -> Optional[Dict]:
    """Get today's RL prediction for a symbol, loading model from DB."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.connection import SessionLocal
    from database.models import RLModel

    db = SessionLocal()
    try:
        # Find best model for symbol (or alias)
        aliases = [symbol]
        for k, als in SYMBOL_ALIASES.items():
            if symbol == k or symbol in als:
                aliases = list(set([symbol, k] + als))
                break

        row = db.query(RLModel).filter(
            RLModel.symbol.in_(aliases),
            RLModel.is_best == True
        ).order_by(RLModel.val_sharpe.desc()).first()

        if row is None or row.model_data is None:
            if row is not None and row.model_data is None:
                logger.warning(f"[RL] Model row exists for {symbol} but model_data is None, skipping")
            return None

        model_bytes = row.model_data

        df = _load_prices(db, symbol)
        if df is None or len(df) < WINDOW_SIZE + 5:
            return None

        env = TradingEnv(df)
        state = env.reset()
        # Walk to the last step
        for i in range(env.n - WINDOW_SIZE - 2):
            env.step(0)  # HOLD to reach end
        state = env._get_state()

        agent = PPOAgent()
        agent.load_from_bytes(model_bytes)
        action, confidence = agent.predict(state)

        return {"symbol": symbol, "action": action, "confidence": round(float(_to_py(confidence)), 3),
                "date": str(date.today())}
    finally:
        db.close()
