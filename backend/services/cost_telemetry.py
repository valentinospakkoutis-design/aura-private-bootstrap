"""
cost_telemetry.py — στιγμιότυπο βιβλίου τη στιγμή της απόφασης.

Καμία εντολή. Μόνο μέτρηση.

Συλλέγει:
  - top-of-book bid/ask (ήδη υπάρχει στο trend_paper_spreads)
  - depth-5: συνολική ποσότητα στα 5 καλύτερα επίπεδα (για εκτίμηση slippage)
  - bid_qty / ask_qty στο top level

Γράφει σε JSONL: data/costs/book.jsonl (ένα record ανά σύμβολο/στιγμιότυπο)
Χρησιμοποιείται από cost_report.py για υπολογισμό πραγματοποιημένου κόστους.

Κλήση:
    from services.cost_telemetry import snapshot_all
    await snapshot_all(session, symbols, sleeve="USDC")  # aiohttp session
    # ή sync:
    from services.cost_telemetry import snapshot_all_sync
    snapshot_all_sync(symbols, sleeve="USDC")
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

OUT = Path("data/costs/book.jsonl")


def _ensure_dir() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)


def _parse_depth(book: dict) -> dict:
    """Εξάγει top-of-book και depth-5 από Binance /api/v3/depth response."""
    bids = book.get("bids", [])
    asks = book.get("asks", [])
    if not bids or not asks:
        return {}

    bid = float(bids[0][0])
    ask = float(asks[0][0])
    if bid <= 0 or ask <= 0 or ask < bid:
        return {}

    mid = (bid + ask) / 2.0
    return {
        "bid":        bid,
        "ask":        ask,
        "mid":        mid,
        "half_spread_bps": (ask - bid) / 2.0 / mid * 10_000.0,
        "bid_qty":    float(bids[0][1]),
        "ask_qty":    float(asks[0][1]),
        "bid_depth5": sum(float(x[1]) for x in bids),
        "ask_depth5": sum(float(x[1]) for x in asks),
        "levels_bid": len(bids),
        "levels_ask": len(asks),
    }


def _write(record: dict) -> None:
    _ensure_dir()
    with OUT.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


# ── Async (aiohttp) ─────────────────────────────────────────────────────────────

async def snapshot(session, symbol: str, sleeve: str = "USDC") -> Optional[dict]:
    """Ένα σύμβολο, async. Επιστρέφει το record ή None σε σφάλμα."""
    try:
        async with session.get(
            "https://api.binance.com/api/v3/depth",
            params={"symbol": symbol, "limit": 5},
            timeout=10,
        ) as r:
            book = await r.json()
        parsed = _parse_depth(book)
        if not parsed:
            return None
        rec = {"ts": time.time(), "symbol": symbol, "sleeve": sleeve, **parsed}
        _write(rec)
        return rec
    except Exception:
        return None


async def snapshot_all(session, symbols: List[str], sleeve: str = "USDC") -> List[dict]:
    """Όλα τα symbols ταυτόχρονα."""
    import asyncio
    tasks = [snapshot(session, s, sleeve) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


# ── Sync (httpx / requests) ──────────────────────────────────────────────────────

def _fetch_depth_sync(symbol: str) -> Optional[dict]:
    """Sync fallback — χρησιμοποιεί httpx αν υπάρχει, αλλιώς requests."""
    url = "https://api.binance.com/api/v3/depth"
    params = {"symbol": symbol, "limit": 5}
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except ImportError:
        pass
    try:
        import requests
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def snapshot_sync(symbol: str, sleeve: str = "USDC") -> Optional[dict]:
    book = _fetch_depth_sync(symbol)
    if book is None:
        return None
    parsed = _parse_depth(book)
    if not parsed:
        return None
    rec = {"ts": time.time(), "symbol": symbol, "sleeve": sleeve, **parsed}
    _write(rec)
    return rec


def snapshot_all_sync(symbols: List[str], sleeve: str = "USDC",
                      workers: int = 8) -> List[dict]:
    """Sync, παράλληλο με threads."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(snapshot_sync, s, sleeve): s for s in symbols}
        for fut in as_completed(futures):
            rec = fut.result()
            if rec is not None:
                results.append(rec)
    return results


# ── Slippage estimation ──────────────────────────────────────────────────────────

def estimate_taker_cost_bps(record: dict, notional_usd: float) -> float:
    """
    Εκτιμά το κόστος taker εντολής για δεδομένο notional.

    Λογική:
      - Αν notional <= top-of-book qty * mid: πληρώνεις μόνο half-spread
      - Αν notional > top-of-book qty * mid: η υπερβάλλουσα ποσότητα
        χτυπάει τα επόμενα levels (εδώ: uniform distribution στο depth-5)
      - Αποτέλεσμα: half-spread + slippage (σε bps)

    Χρησιμοποιείται για εκτίμηση μόνο — δεν αντικαθιστά πραγματοποιημένο.
    """
    mid = record.get("mid", 0)
    if mid <= 0:
        return float("nan")

    half_spread = record.get("half_spread_bps", 0)
    top_qty = record.get("ask_qty", 0)   # αγορά → χτυπάμε ask side
    depth5_qty = record.get("ask_depth5", top_qty)
    if depth5_qty <= 0:
        return half_spread

    # notional σε qty
    qty_needed = notional_usd / mid
    top_notional = top_qty * mid

    if notional_usd <= top_notional or depth5_qty <= top_qty:
        return half_spread

    # fraction πέρα από top level
    overflow = qty_needed - top_qty
    # uniform slippage assumption στα υπόλοιπα 4 levels
    remaining_depth = depth5_qty - top_qty
    if remaining_depth <= 0:
        return half_spread

    # Approximate: average price impact = overflow / remaining_depth * half_spread_per_level
    # Rough: each level adds ~half_spread more slippage (very conservative)
    fraction_overflow = min(overflow / remaining_depth, 1.0)
    slippage_bps = fraction_overflow * half_spread  # conservative: 1× additional half-spread

    return half_spread + slippage_bps


# ── Diagnostic summary ───────────────────────────────────────────────────────────

def load_book_jsonl(path: Path = OUT) -> "pd.DataFrame":
    """Φορτώνει το book.jsonl σε DataFrame."""
    import pandas as pd
    if not path.exists():
        return pd.DataFrame()
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df


def book_summary(path: Path = OUT) -> Dict:
    """Σύντομη περίληψη του book.jsonl για reporting."""
    import pandas as pd
    df = load_book_jsonl(path)
    if df.empty:
        return {"records": 0}

    out = {
        "records": len(df),
        "symbols": int(df["symbol"].nunique()),
        "snapshots": int(df["ts"].nunique()),
        "date_range": f"{str(df['dt'].min())[:10]} → {str(df['dt'].max())[:10]}",
    }

    if "half_spread_bps" in df.columns:
        # Per sleeve
        for sleeve, g in df.groupby("sleeve"):
            key = f"sleeve_{sleeve}"
            out[key] = {
                "median_half_spread_bps": round(float(g["half_spread_bps"].median()), 2),
                "p90_half_spread_bps":    round(float(g["half_spread_bps"].quantile(0.90)), 2),
                "symbols": int(g["symbol"].nunique()),
            }

    return out
