"""Reddit monitoring client for penny stock subreddits."""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


# Target subreddits for penny stock discussion
TARGET_SUBREDDITS = [
    "pennystocks",
    "smallstreetbets",
    "RobinHoodPennyStocks",
    "OTCstocks",
    "MicroCapStocks",
    "Shortsqueeze",
    "spacs",
    "wallstreetbets",
    "stocks",
    "investing",
]


class RedditMonitor:
    """Monitor Reddit for stock mentions using PRAW or direct API."""

    # OAuth endpoint
    AUTH_URL = "https://www.reddit.com/api/v1/access_token"
    BASE_URL = "https://oauth.reddit.com"

    # Ticker patterns
    TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")
    TICKER_MENTION_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")

    # Words to exclude from ticker matching
    EXCLUDED_WORDS = {
        "A", "I", "US", "UK", "EU", "CEO", "CFO", "IPO", "ETF", "SEC",
        "FDA", "FTC", "NYSE", "NASDAQ", "OTC", "DD", "IMO", "YOLO", "FOMO",
        "EPS", "ATH", "ATL", "ITM", "OTM", "PM", "AM", "EST", "PST",
        "USD", "CAD", "EUR", "GBP", "THE", "AND", "FOR", "NEW", "INC",
        "LLC", "CORP", "AI", "EV", "TV", "PC", "CEO", "CTO", "CFO",
        "WSB", "GME", "AMC", "BB", "NOK", "PLTR", "HODL", "MOON",
    }

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        subreddits: list[str] | None = None,
    ):
        """Initialize Reddit monitor.

        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string
            subreddits: List of subreddits to monitor
        """
        self.client_id = client_id or settings.reddit_client_id
        self.client_secret = client_secret or settings.reddit_client_secret
        self.user_agent = user_agent or settings.reddit_user_agent
        self.subreddits = subreddits or TARGET_SUBREDDITS
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._seen_ids: set[str] = set()

    async def __aenter__(self) -> "RedditMonitor":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=30.0,
        )
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _authenticate(self) -> bool:
        """Authenticate with Reddit OAuth.

        Returns:
            True if authentication successful
        """
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit credentials not configured")
            return False

        try:
            response = await self._client.post(
                self.AUTH_URL,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + timedelta(seconds=expires_in - 60)

            logger.info("Reddit authentication successful")
            return True

        except Exception as e:
            logger.error("Reddit authentication failed", error=str(e))
            return False

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if not self._access_token or (
            self._token_expires and datetime.now(timezone.utc) > self._token_expires
        ):
            await self._authenticate()

    async def get_subreddit_posts(
        self,
        subreddit: str,
        limit: int = 25,
        sort: str = "new",
    ) -> list[dict[str, Any]]:
        """Get posts from a subreddit.

        Args:
            subreddit: Subreddit name
            limit: Number of posts to fetch
            sort: Sort method (new, hot, top)

        Returns:
            List of post data
        """
        await self._ensure_authenticated()

        if not self._access_token:
            return []

        try:
            url = f"{self.BASE_URL}/r/{subreddit}/{sort}"
            response = await self._client.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params={"limit": limit},
            )
            response.raise_for_status()

            data = response.json()
            posts = []

            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                post = self._parse_post(post_data, subreddit)
                if post:
                    posts.append(post)

            return posts

        except Exception as e:
            logger.error("Failed to fetch subreddit", subreddit=subreddit, error=str(e))
            return []

    def _parse_post(self, data: dict[str, Any], subreddit: str) -> dict[str, Any] | None:
        """Parse Reddit post data.

        Args:
            data: Raw post data
            subreddit: Source subreddit

        Returns:
            Parsed post dict or None
        """
        try:
            post_id = data.get("id", "")
            title = data.get("title", "")
            selftext = data.get("selftext", "")

            if not title:
                return None

            # Extract tickers from title and content
            full_text = f"{title} {selftext}"
            tickers = self._extract_tickers(full_text)

            # Get metrics
            score = data.get("score", 0)
            upvote_ratio = data.get("upvote_ratio", 0.5)
            num_comments = data.get("num_comments", 0)

            # Calculate engagement score
            engagement = min(1.0, (score + num_comments * 2) / 1000)

            # Parse timestamp
            created_utc = data.get("created_utc", 0)
            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

            # Determine flair/category
            flair = data.get("link_flair_text", "")

            return {
                "post_id": post_id,
                "title": title,
                "content": selftext[:5000],
                "author": data.get("author", "[deleted]"),
                "subreddit": subreddit,
                "url": f"https://reddit.com{data.get('permalink', '')}",
                "score": score,
                "upvote_ratio": upvote_ratio,
                "num_comments": num_comments,
                "flair": flair,
                "tickers": tickers,
                "ticker": tickers[0] if tickers else "",
                "engagement_score": engagement,
                "created_at": created_at,
                "source": "reddit",
                "event_type": "SOCIAL_MENTION",
                "event_category": f"REDDIT_{subreddit.upper()}",
            }

        except Exception as e:
            logger.warning("Failed to parse post", error=str(e))
            return None

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text.

        Args:
            text: Text to search

        Returns:
            List of extracted tickers
        """
        tickers = []

        # First, find explicit cashtags ($AAPL)
        cashtags = self.TICKER_PATTERN.findall(text)
        for tag in cashtags:
            if tag.upper() not in self.EXCLUDED_WORDS:
                tickers.append(tag.upper())

        # Then find potential ticker mentions (2-5 uppercase letters)
        mentions = self.TICKER_MENTION_PATTERN.findall(text)
        for mention in mentions:
            if mention.upper() not in self.EXCLUDED_WORDS and mention.upper() not in tickers:
                # Only add if it looks like a ticker (not a common word)
                if len(mention) >= 2 and mention.upper() == mention:
                    tickers.append(mention)

        return list(dict.fromkeys(tickers))[:10]

    async def monitor_subreddits(
        self,
        poll_interval: float = 60.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Monitor all configured subreddits for new posts.

        Args:
            poll_interval: Seconds between poll cycles

        Yields:
            New posts
        """
        while True:
            for subreddit in self.subreddits:
                try:
                    posts = await self.get_subreddit_posts(subreddit, limit=25, sort="new")

                    for post in posts:
                        post_id = post.get("post_id", "")

                        if post_id and post_id not in self._seen_ids:
                            self._seen_ids.add(post_id)
                            yield post

                except Exception as e:
                    logger.error("Monitor error", subreddit=subreddit, error=str(e))

                # Rate limit between subreddits
                await asyncio.sleep(2)

            # Limit seen IDs cache
            if len(self._seen_ids) > 10000:
                self._seen_ids = set(list(self._seen_ids)[-5000:])

            await asyncio.sleep(poll_interval)

    async def search_ticker(
        self,
        ticker: str,
        subreddits: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for posts mentioning a specific ticker.

        Args:
            ticker: Stock ticker symbol
            subreddits: Subreddits to search (defaults to all configured)
            limit: Maximum results per subreddit

        Returns:
            List of matching posts
        """
        await self._ensure_authenticated()

        if not self._access_token:
            return []

        subreddits = subreddits or self.subreddits
        all_posts = []

        for subreddit in subreddits:
            try:
                url = f"{self.BASE_URL}/r/{subreddit}/search"
                response = await self._client.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params={
                        "q": f"${ticker} OR {ticker}",
                        "restrict_sr": "true",
                        "sort": "new",
                        "limit": min(limit, 25),
                    },
                )
                response.raise_for_status()

                data = response.json()
                for child in data.get("data", {}).get("children", []):
                    post = self._parse_post(child.get("data", {}), subreddit)
                    if post:
                        all_posts.append(post)

            except Exception as e:
                logger.error("Search error", subreddit=subreddit, error=str(e))

            await asyncio.sleep(1)  # Rate limit

        return all_posts[:limit]


async def main():
    """Example usage of Reddit monitor."""
    async with RedditMonitor() as monitor:
        # Get recent posts from pennystocks
        posts = await monitor.get_subreddit_posts("pennystocks", limit=10)
        print(f"Found {len(posts)} posts from r/pennystocks")

        for post in posts[:5]:
            tickers = post.get("tickers", [])
            ticker_str = ", ".join(tickers) if tickers else "N/A"
            print(f"[{ticker_str}] {post['title'][:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
