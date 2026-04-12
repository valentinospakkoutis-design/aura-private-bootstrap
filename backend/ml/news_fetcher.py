"""
CryptoPanic integration helpers for ML sentiment pipeline.
"""

import asyncio
from typing import Dict, List

import httpx

CRYPTOPANIC_SYMBOLS: Dict[str, str] = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "BNB-USD": "BNB",
    "SOL-USD": "SOL",
    "ADA-USD": "ADA",
    "AVAX-USD": "AVAX",
    "DOT-USD": "DOT",
    "MATIC-USD": "MATIC",
    "LINK-USD": "LINK",
    "UNI-USD": "UNI",
    "BTCUSDC": "BTC",
    "ETHUSDC": "ETH",
    "BNBUSDC": "BNB",
    "SOLUSDC": "SOL",
    "ADAUSDC": "ADA",
    "AVAXUSDC": "AVAX",
    "DOTUSDC": "DOT",
    "POLUSDC": "MATIC",
    "LINKUSDC": "LINK",
    "UNIUSDC": "UNI",
}


async def fetch_cryptopanic_news(symbol: str) -> List[dict]:
    """Fetch crypto news from CryptoPanic free API with basic rate limiting."""
    cp_symbol = CRYPTOPANIC_SYMBOLS.get(symbol)
    if not cp_symbol:
        return []

    try:
        # Anonymous endpoint has strict limits; keep a small delay between symbol calls.
        await asyncio.sleep(0.5)
        url = (
            "https://cryptopanic.com/api/free/v1/posts/"
            f"?auth_token=anonymous&currencies={cp_symbol}&kind=news&public=true"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
            data = r.json()

        results: List[dict] = []
        for item in data.get("results", [])[:10]:
            title = item.get("title", "")
            votes = item.get("votes", {})
            bullish_votes = int(votes.get("positive", 0) or 0)
            bearish_votes = int(votes.get("negative", 0) or 0)
            results.append(
                {
                    "title": title,
                    "summary": item.get("slug", ""),
                    "source": "cryptopanic",
                    "bullish_votes": bullish_votes,
                    "bearish_votes": bearish_votes,
                    "published_at": item.get("published_at", ""),
                    "url": item.get("url", ""),
                }
            )
        return results
    except Exception as e:
        print(f"[CryptoPanic] Error for {symbol}: {e}")
        return []
