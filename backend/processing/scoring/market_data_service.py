"""Market data service for fetching market cap and other financial data.

Uses free APIs (Yahoo Finance via yfinance) to fetch market data for
liquidity scoring and alpha calculation.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MarketData:
    """Market data for a ticker."""

    ticker: str
    market_cap: float | None  # Market cap in USD
    price: float | None  # Current price
    avg_volume: float | None  # Average daily volume
    volume: float | None  # Current day volume
    pe_ratio: float | None  # P/E ratio
    sector: str | None  # Yahoo Finance sector
    industry: str | None  # Yahoo Finance industry
    exchange: str | None  # Exchange (NYSE, NASDAQ, etc.)
    is_otc: bool
    fetched_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticker": self.ticker,
            "market_cap": self.market_cap,
            "price": self.price,
            "avg_volume": self.avg_volume,
            "volume": self.volume,
            "pe_ratio": self.pe_ratio,
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "is_otc": self.is_otc,
            "fetched_at": self.fetched_at.isoformat(),
        }


class MarketDataService:
    """Service for fetching market data from free APIs.

    Uses yfinance (Yahoo Finance) as the primary data source.
    Implements caching to minimize API calls.
    """

    # Cache TTL in seconds (1 hour for market data)
    CACHE_TTL = 3600

    # Rate limiting: max requests per second
    MAX_REQUESTS_PER_SECOND = 2

    def __init__(self, cache_ttl: int | None = None):
        """Initialize market data service.

        Args:
            cache_ttl: Cache time-to-live in seconds (default 1 hour)
        """
        self.cache_ttl = cache_ttl or self.CACHE_TTL
        self._cache: dict[str, tuple[MarketData, datetime]] = {}
        self._last_request_time: float = 0
        self._yfinance = None

    def _get_yfinance(self):
        """Lazy load yfinance."""
        if self._yfinance is None:
            try:
                import yfinance
                self._yfinance = yfinance
                logger.info("yfinance loaded successfully")
            except ImportError:
                logger.warning(
                    "yfinance not installed. Install with: pip install yfinance"
                )
                raise ImportError("yfinance is required for market data fetching")

        return self._yfinance

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.MAX_REQUESTS_PER_SECOND

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    def get_market_data(self, ticker: str, use_cache: bool = True) -> MarketData | None:
        """Fetch market data for a ticker.

        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data if available

        Returns:
            MarketData or None if fetch fails
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache and ticker in self._cache:
            data, cached_at = self._cache[ticker]
            if datetime.now(timezone.utc) - cached_at < timedelta(seconds=self.cache_ttl):
                logger.debug("Using cached market data", ticker=ticker)
                return data

        try:
            yf = self._get_yfinance()
            self._rate_limit()

            # Fetch ticker info
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or info.get("regularMarketPrice") is None:
                logger.warning("No market data found", ticker=ticker)
                return None

            # Determine if OTC
            exchange = info.get("exchange", "")
            is_otc = any(x in exchange.upper() for x in ["OTC", "PINK", "GREY"])

            # Create market data object
            data = MarketData(
                ticker=ticker,
                market_cap=info.get("marketCap"),
                price=info.get("regularMarketPrice") or info.get("currentPrice"),
                avg_volume=info.get("averageVolume"),
                volume=info.get("regularMarketVolume") or info.get("volume"),
                pe_ratio=info.get("trailingPE") or info.get("forwardPE"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                exchange=exchange,
                is_otc=is_otc,
                fetched_at=datetime.now(timezone.utc),
            )

            # Cache result
            self._cache[ticker] = (data, datetime.now(timezone.utc))

            logger.debug(
                "Fetched market data",
                ticker=ticker,
                market_cap=data.market_cap,
                price=data.price,
            )

            return data

        except ImportError:
            logger.error("yfinance not available")
            return None
        except Exception as e:
            logger.error("Failed to fetch market data", ticker=ticker, error=str(e))
            return None

    def get_market_cap(self, ticker: str, use_cache: bool = True) -> float | None:
        """Get market cap for a ticker.

        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data

        Returns:
            Market cap in USD or None
        """
        data = self.get_market_data(ticker, use_cache)
        return data.market_cap if data else None

    def get_batch_market_data(
        self,
        tickers: list[str],
        use_cache: bool = True,
    ) -> dict[str, MarketData]:
        """Fetch market data for multiple tickers.

        Args:
            tickers: List of ticker symbols
            use_cache: Whether to use cached data

        Returns:
            Dictionary mapping tickers to MarketData
        """
        results = {}

        # Check cache first
        tickers_to_fetch = []
        for ticker in tickers:
            ticker = ticker.upper()
            if use_cache and ticker in self._cache:
                data, cached_at = self._cache[ticker]
                if datetime.now(timezone.utc) - cached_at < timedelta(seconds=self.cache_ttl):
                    results[ticker] = data
                    continue
            tickers_to_fetch.append(ticker)

        if not tickers_to_fetch:
            return results

        try:
            yf = self._get_yfinance()
            self._rate_limit()

            # Batch download (yfinance supports this)
            # Use download for basic price data
            batch_data = yf.download(
                " ".join(tickers_to_fetch),
                period="1d",
                progress=False,
                threads=True,
            )

            # For full info, we need to fetch individually
            for ticker in tickers_to_fetch:
                data = self.get_market_data(ticker, use_cache=False)
                if data:
                    results[ticker] = data

        except Exception as e:
            logger.error("Batch market data fetch failed", error=str(e))
            # Fallback to individual fetches
            for ticker in tickers_to_fetch:
                data = self.get_market_data(ticker, use_cache=False)
                if data:
                    results[ticker] = data

        return results

    def clear_cache(self, ticker: str | None = None):
        """Clear cached data.

        Args:
            ticker: Specific ticker to clear, or None for all
        """
        if ticker:
            self._cache.pop(ticker.upper(), None)
        else:
            self._cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache stats dictionary
        """
        now = datetime.now(timezone.utc)
        valid_count = sum(
            1 for _, (_, cached_at) in self._cache.items()
            if now - cached_at < timedelta(seconds=self.cache_ttl)
        )

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "cache_ttl_seconds": self.cache_ttl,
        }


# Global market data service instance
_market_data_service: MarketDataService | None = None


def get_market_data_service() -> MarketDataService:
    """Get or create global market data service."""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service


def get_market_cap(ticker: str) -> float | None:
    """Convenience function to get market cap.

    Args:
        ticker: Stock ticker

    Returns:
        Market cap in USD or None
    """
    service = get_market_data_service()
    return service.get_market_cap(ticker)
