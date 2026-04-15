"""Real-time Binance websocket price feed with Redis caching."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional

import websockets

from cache.connection import get_redis

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
PRICE_TTL_SECONDS = 60

_feed_instance: Optional["BinanceWebSocketFeed"] = None
_feed_task: Optional[asyncio.Task] = None


class BinanceWebSocketFeed:
    """Consumes Binance ticker websocket streams and writes latest prices to Redis."""

    def __init__(self, symbols: List[str]):
        self.symbols = sorted({str(s or "").upper().strip() for s in (symbols or []) if str(s or "").strip()})
        self._connected = False
        self._stop = False
        self._last_update_ms: Dict[str, int] = {}
        self._redis = get_redis()

    @property
    def connected(self) -> bool:
        return self._connected

    def get_status(self) -> Dict:
        now_ms = int(time.time() * 1000)
        active_symbols = [
            {
                "symbol": sym,
                "last_update_ms": ts,
                "age_ms": max(0, now_ms - ts),
            }
            for sym, ts in sorted(self._last_update_ms.items(), key=lambda x: x[0])
        ]
        return {
            "connected": self._connected,
            "subscribed_symbols": list(self.symbols),
            "active_symbols": active_symbols,
            "active_count": len(active_symbols),
        }

    async def stop(self) -> None:
        self._stop = True

    async def _subscribe(self, ws) -> None:
        params = [f"{sym.lower()}@ticker" for sym in self.symbols]
        if not params:
            return
        payload = {
            "method": "SUBSCRIBE",
            "params": params,
            "id": 1,
        }
        await ws.send(json.dumps(payload))

    def _set_price_cache(self, symbol: str, price: float, ts_ms: int) -> None:
        if self._redis is None:
            return
        try:
            key = f"price:{symbol.upper()}"
            value = json.dumps({"price": float(price), "ts_ms": int(ts_ms)})
            self._redis.setex(key, PRICE_TTL_SECONDS, value)
        except Exception as e:
            logger.debug("[WS_FEED] Redis write failed for %s: %s", symbol, e)

    async def _handle_message(self, raw_msg: str) -> None:
        try:
            payload = json.loads(raw_msg)
        except Exception:
            return

        # SUBSCRIBE ack payload includes result/id and no ticker fields.
        data = payload.get("data", payload)
        symbol = str(data.get("s") or "").upper()
        last_price_raw = data.get("c")
        if not symbol or last_price_raw is None:
            return

        try:
            price = float(last_price_raw)
        except Exception:
            return

        ts_ms = int(time.time() * 1000)
        self._last_update_ms[symbol] = ts_ms
        self._set_price_cache(symbol=symbol, price=price, ts_ms=ts_ms)

    async def run(self) -> None:
        """Run websocket client loop with automatic reconnect."""
        backoff = 1
        while not self._stop:
            try:
                async with websockets.connect(
                    BINANCE_WS_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                ) as ws:
                    self._connected = True
                    backoff = 1
                    await self._subscribe(ws)

                    async for msg in ws:
                        if self._stop:
                            break
                        await self._handle_message(msg)
            except Exception as e:
                logger.warning("[WS_FEED] disconnected, reconnecting in %ss: %s", backoff, e)
            finally:
                self._connected = False

            if self._stop:
                break
            await asyncio.sleep(backoff)
            backoff = min(30, backoff * 2)


def _read_cached_price(symbol: str) -> Optional[Dict]:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(f"price:{symbol.upper()}")
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        payload = json.loads(raw)
        if "price" not in payload:
            return None
        return payload
    except Exception:
        return None


def get_realtime_price(symbol: str) -> dict:
    """Return latest live price from Redis, fallback to yfinance."""
    symbol_u = str(symbol or "").upper().strip()
    if not symbol_u:
        return {"symbol": symbol_u, "price": None, "source": "invalid_symbol", "age_ms": None}

    cached = _read_cached_price(symbol_u)
    if cached is not None:
        now_ms = int(time.time() * 1000)
        ts_ms = int(cached.get("ts_ms") or now_ms)
        age_ms = max(0, now_ms - ts_ms)
        return {
            "symbol": symbol_u,
            "price": float(cached.get("price")),
            "source": "websocket",
            "age_ms": age_ms,
        }

    try:
        from market_data.yfinance_client import get_price as yf_get_price

        info = yf_get_price(symbol_u)
        if info and info.get("price") is not None:
            return {
                "symbol": symbol_u,
                "price": float(info.get("price")),
                "source": "yfinance_fallback",
                "age_ms": None,
            }
    except Exception as e:
        logger.debug("[WS_FEED] yfinance fallback failed for %s: %s", symbol_u, e)

    return {
        "symbol": symbol_u,
        "price": None,
        "source": "unavailable",
        "age_ms": None,
    }


def start_websocket_feed(symbols: list):
    """Start Binance websocket feed as background asyncio task."""
    global _feed_instance, _feed_task

    target_symbols = [str(s or "").upper().strip() for s in (symbols or []) if str(s or "").strip()]
    if _feed_task is not None and not _feed_task.done() and _feed_instance is not None:
        existing = set(_feed_instance.symbols)
        merged = sorted(existing.union(target_symbols))
        if merged != _feed_instance.symbols:
            logger.warning("[WS_FEED] feed already running; symbol updates require restart")
        return _feed_instance.get_status()

    _feed_instance = BinanceWebSocketFeed(target_symbols)
    _feed_task = asyncio.create_task(_feed_instance.run())
    return _feed_instance.get_status()


def get_websocket_feed_status() -> dict:
    """Return feed status and active symbol freshness."""
    if _feed_instance is None:
        return {
            "running": False,
            "connected": False,
            "subscribed_symbols": [],
            "active_symbols": [],
            "active_count": 0,
        }

    status = _feed_instance.get_status()
    return {
        "running": bool(_feed_task is not None and not _feed_task.done()),
        **status,
    }
