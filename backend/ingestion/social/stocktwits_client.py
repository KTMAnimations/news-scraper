"""StockTwits API client for sentiment streaming."""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class StockTwitsClient:
    """Client for StockTwits API."""

    BASE_URL = "https://api.stocktwits.com/api/2"

    def __init__(
        self,
        access_token: str | None = None,
        rate_limit: float = 1.0,
    ):
        """Initialize StockTwits client.

        Args:
            access_token: Optional access token for authenticated requests
            rate_limit: Seconds between requests
        """
        self.access_token = access_token or settings.stocktwits_access_token
        self.rate_limit = rate_limit
        self._client: httpx.AsyncClient | None = None
        self._last_request: float = 0
        self._seen_ids: set[int] = set()

    async def __aenter__(self) -> "StockTwitsClient":
        """Async context manager entry."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _rate_limit_wait(self) -> None:
        """Wait for rate limit."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def get_symbol_stream(
        self,
        symbol: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get message stream for a symbol.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit_wait()

        try:
            url = f"{self.BASE_URL}/streams/symbol/{symbol.upper()}.json"
            params = {"limit": min(limit, 30)}

            if self.access_token:
                params["access_token"] = self.access_token

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            messages = []

            for msg in data.get("messages", []):
                parsed = self._parse_message(msg, symbol)
                if parsed:
                    messages.append(parsed)

            return messages

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Symbol not found on StockTwits", symbol=symbol)
            else:
                logger.error("StockTwits API error", status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Failed to fetch symbol stream", symbol=symbol, error=str(e))
            return []

    async def get_trending(self) -> list[dict[str, Any]]:
        """Get trending symbols on StockTwits.

        Returns:
            List of trending symbols with metadata
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit_wait()

        try:
            url = f"{self.BASE_URL}/trending/symbols.json"
            response = await self._client.get(url)
            response.raise_for_status()

            data = response.json()
            symbols = []

            for sym in data.get("symbols", []):
                symbols.append({
                    "symbol": sym.get("symbol", ""),
                    "title": sym.get("title", ""),
                    "watchlist_count": sym.get("watchlist_count", 0),
                    "is_following": sym.get("is_following", False),
                })

            return symbols

        except Exception as e:
            logger.error("Failed to fetch trending", error=str(e))
            return []

    async def get_symbol_sentiment(self, symbol: str) -> dict[str, Any]:
        """Get aggregated sentiment for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Sentiment data
        """
        messages = await self.get_symbol_stream(symbol, limit=30)

        if not messages:
            return {
                "symbol": symbol.upper(),
                "message_count": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "sentiment_ratio": 0.5,
                "sentiment_label": "neutral",
            }

        bullish = sum(1 for m in messages if m.get("sentiment") == "Bullish")
        bearish = sum(1 for m in messages if m.get("sentiment") == "Bearish")
        total_sentiment = bullish + bearish

        if total_sentiment > 0:
            ratio = bullish / total_sentiment
        else:
            ratio = 0.5

        if ratio > 0.6:
            label = "bullish"
        elif ratio < 0.4:
            label = "bearish"
        else:
            label = "neutral"

        return {
            "symbol": symbol.upper(),
            "message_count": len(messages),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "sentiment_ratio": ratio,
            "sentiment_label": label,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_message(self, msg: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """Parse StockTwits message.

        Args:
            msg: Raw message data
            symbol: Symbol context

        Returns:
            Parsed message dict or None
        """
        try:
            msg_id = msg.get("id")
            body = msg.get("body", "")
            created_at = msg.get("created_at", "")

            if not body:
                return None

            # Get sentiment
            entities = msg.get("entities", {})
            sentiment_data = entities.get("sentiment")
            sentiment = None

            if sentiment_data:
                sentiment = sentiment_data.get("basic", "")

            # Get user info
            user = msg.get("user", {})
            username = user.get("username", "")
            followers = user.get("followers", 0)
            ideas = user.get("ideas", 0)

            # Calculate influence score
            influence_score = min(1.0, (followers + ideas * 10) / 10000)

            # Extract other mentioned symbols
            mentioned_symbols = []
            for sym in entities.get("symbols", []):
                mentioned_symbols.append(sym.get("symbol", ""))

            return {
                "message_id": msg_id,
                "body": body,
                "symbol": symbol.upper(),
                "mentioned_symbols": mentioned_symbols,
                "sentiment": sentiment,
                "username": username,
                "user_followers": followers,
                "user_ideas": ideas,
                "influence_score": influence_score,
                "likes_count": msg.get("likes", {}).get("total", 0),
                "created_at": created_at,
                "source": "stocktwits",
                "event_type": "SOCIAL_MENTION",
                "event_category": "STOCKTWITS",
            }

        except Exception as e:
            logger.warning("Failed to parse message", error=str(e))
            return None

    async def monitor_symbols(
        self,
        symbols: list[str],
        poll_interval: float = 60.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Monitor multiple symbols for new messages.

        Args:
            symbols: List of symbols to monitor
            poll_interval: Seconds between poll cycles

        Yields:
            New messages
        """
        while True:
            for symbol in symbols:
                try:
                    messages = await self.get_symbol_stream(symbol, limit=20)

                    for msg in messages:
                        msg_id = msg.get("message_id")
                        if msg_id and msg_id not in self._seen_ids:
                            self._seen_ids.add(msg_id)
                            yield msg

                except Exception as e:
                    logger.error("Monitor error", symbol=symbol, error=str(e))

            # Limit seen IDs cache
            if len(self._seen_ids) > 10000:
                self._seen_ids = set(list(self._seen_ids)[-5000:])

            await asyncio.sleep(poll_interval)

    async def get_user_stream(self, username: str, limit: int = 30) -> list[dict[str, Any]]:
        """Get message stream from a specific user.

        Args:
            username: StockTwits username
            limit: Maximum messages

        Returns:
            List of messages
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit_wait()

        try:
            url = f"{self.BASE_URL}/streams/user/{username}.json"
            params = {"limit": min(limit, 30)}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            messages = []

            for msg in data.get("messages", []):
                # Get primary symbol from entities
                symbols = msg.get("entities", {}).get("symbols", [])
                primary_symbol = symbols[0].get("symbol", "") if symbols else ""

                parsed = self._parse_message(msg, primary_symbol)
                if parsed:
                    messages.append(parsed)

            return messages

        except Exception as e:
            logger.error("Failed to fetch user stream", username=username, error=str(e))
            return []


async def main():
    """Example usage of StockTwits client."""
    async with StockTwitsClient() as client:
        # Get trending symbols
        trending = await client.get_trending()
        print(f"Top trending symbols: {[s['symbol'] for s in trending[:5]]}")

        # Get sentiment for a symbol
        sentiment = await client.get_symbol_sentiment("AAPL")
        print(f"AAPL sentiment: {sentiment['sentiment_label']} (ratio: {sentiment['sentiment_ratio']:.2f})")

        # Get recent messages
        messages = await client.get_symbol_stream("AAPL", limit=5)
        for msg in messages:
            print(f"@{msg['username']}: {msg['body'][:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
