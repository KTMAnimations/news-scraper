"""Liquidity scoring for alpha adjustment."""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class LiquidityScorer:
    """Score liquidity and adjust alpha potential accordingly.

    Illiquid stocks (micro-caps, penny stocks, OTC) have higher
    alpha potential because:
    1. Less analyst coverage = more information asymmetry
    2. Lower volume = news moves prices more
    3. Wider spreads = larger price moves
    """

    # Market cap thresholds (USD)
    MARKET_CAP_TIERS = {
        "mega": 200_000_000_000,    # $200B+
        "large": 10_000_000_000,    # $10B+
        "mid": 2_000_000_000,       # $2B+
        "small": 300_000_000,       # $300M+
        "micro": 50_000_000,        # $50M+
        "nano": 0,                   # < $50M
    }

    # Average daily volume thresholds
    VOLUME_TIERS = {
        "very_high": 10_000_000,    # 10M+ shares/day
        "high": 1_000_000,          # 1M+ shares/day
        "moderate": 100_000,        # 100K+ shares/day
        "low": 10_000,              # 10K+ shares/day
        "very_low": 0,              # < 10K shares/day
    }

    # Alpha multipliers by liquidity category
    # Higher multiplier = more alpha potential
    ALPHA_MULTIPLIERS = {
        "mega_cap": 0.8,      # Very efficient market
        "large_cap": 0.85,    # Efficient
        "mid_cap": 0.95,      # Some inefficiency
        "small_cap": 1.1,     # Meaningful inefficiency
        "micro_cap": 1.25,    # High inefficiency
        "penny": 1.35,        # Very high inefficiency
        "otc": 1.4,           # Maximum inefficiency
    }

    def __init__(self, use_market_data_service: bool = True):
        """Initialize liquidity scorer.

        Args:
            use_market_data_service: Whether to fetch live market data
        """
        # Cache for ticker liquidity data
        self._cache: dict[str, dict[str, Any]] = {}
        self._use_market_data = use_market_data_service
        self._market_data_service = None

    def _get_market_data_service(self):
        """Lazy load market data service."""
        if self._market_data_service is None and self._use_market_data:
            try:
                from .market_data_service import get_market_data_service
                self._market_data_service = get_market_data_service()
            except ImportError:
                logger.warning("Market data service not available")
                self._use_market_data = False
        return self._market_data_service

    def score(
        self,
        ticker: str | None = None,
        market_cap: float | None = None,
        avg_volume: float | None = None,
        is_otc: bool = False,
        price: float | None = None,
        fetch_market_data: bool = True,
    ) -> dict[str, Any]:
        """Score liquidity and return alpha multiplier.

        Args:
            ticker: Stock ticker (for cache lookup and market data fetch)
            market_cap: Market capitalization in USD (optional, will be fetched if ticker provided)
            avg_volume: Average daily volume in shares (optional, will be fetched if ticker provided)
            is_otc: Whether stock trades OTC
            price: Current stock price (optional, will be fetched if ticker provided)
            fetch_market_data: Whether to fetch market data if not provided

        Returns:
            Liquidity scoring information
        """
        # Check cache
        if ticker and ticker.upper() in self._cache:
            return self._cache[ticker.upper()]

        # Fetch market data if ticker provided and data not supplied
        fetched_data = None
        if ticker and fetch_market_data and (market_cap is None or avg_volume is None):
            service = self._get_market_data_service()
            if service:
                try:
                    fetched_data = service.get_market_data(ticker)
                    if fetched_data:
                        market_cap = market_cap or fetched_data.market_cap
                        avg_volume = avg_volume or fetched_data.avg_volume
                        price = price or fetched_data.price
                        is_otc = is_otc or fetched_data.is_otc
                        logger.debug(
                            "Fetched market data for liquidity scoring",
                            ticker=ticker,
                            market_cap=market_cap,
                            avg_volume=avg_volume,
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to fetch market data",
                        ticker=ticker,
                        error=str(e),
                    )

        # Determine category
        category = self._categorize(
            market_cap=market_cap,
            avg_volume=avg_volume,
            is_otc=is_otc,
            price=price,
        )

        # Get multiplier
        multiplier = self.ALPHA_MULTIPLIERS.get(category, 1.0)

        # Calculate confidence based on data availability
        confidence = 0.5  # Base confidence

        if market_cap is not None:
            confidence += 0.25
        if avg_volume is not None:
            confidence += 0.15
        if is_otc:
            confidence += 0.1

        result = {
            "category": category,
            "alpha_multiplier": multiplier,
            "market_cap": market_cap,
            "avg_volume": avg_volume,
            "is_otc": is_otc,
            "price": price,
            "confidence": min(1.0, confidence),
            "data_source": "fetched" if fetched_data else "provided",
        }

        # Cache result
        if ticker:
            self._cache[ticker.upper()] = result

        return result

    def score_with_market_data(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """Score liquidity with automatic market data lookup.

        Convenience method that always fetches market data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Liquidity scoring information
        """
        return self.score(ticker=ticker, fetch_market_data=True)

    def _categorize(
        self,
        market_cap: float | None,
        avg_volume: float | None,
        is_otc: bool,
        price: float | None,
    ) -> str:
        """Categorize stock by liquidity.

        Args:
            market_cap: Market cap in USD
            avg_volume: Average daily volume
            is_otc: Whether OTC traded
            price: Stock price

        Returns:
            Liquidity category string
        """
        # OTC stocks get special category
        if is_otc:
            return "otc"

        # Penny stock check (price < $5 or market cap < $50M)
        if price is not None and price < 5.0:
            return "penny"

        if market_cap is not None:
            if market_cap < 50_000_000:
                return "penny"

        # Categorize by market cap
        if market_cap is not None:
            if market_cap >= self.MARKET_CAP_TIERS["mega"]:
                return "mega_cap"
            elif market_cap >= self.MARKET_CAP_TIERS["large"]:
                return "large_cap"
            elif market_cap >= self.MARKET_CAP_TIERS["mid"]:
                return "mid_cap"
            elif market_cap >= self.MARKET_CAP_TIERS["small"]:
                return "small_cap"
            elif market_cap >= self.MARKET_CAP_TIERS["micro"]:
                return "micro_cap"
            else:
                return "penny"

        # Fall back to volume if no market cap
        if avg_volume is not None:
            if avg_volume >= self.VOLUME_TIERS["very_high"]:
                return "large_cap"
            elif avg_volume >= self.VOLUME_TIERS["high"]:
                return "mid_cap"
            elif avg_volume >= self.VOLUME_TIERS["moderate"]:
                return "small_cap"
            elif avg_volume >= self.VOLUME_TIERS["low"]:
                return "micro_cap"
            else:
                return "penny"

        # Default for unknown
        return "small_cap"

    def update_cache(
        self,
        ticker: str,
        market_cap: float | None = None,
        avg_volume: float | None = None,
        is_otc: bool = False,
    ) -> None:
        """Update cached data for a ticker.

        Args:
            ticker: Stock ticker
            market_cap: Market capitalization
            avg_volume: Average volume
            is_otc: Whether OTC traded
        """
        self._cache[ticker.upper()] = self.score(
            ticker=ticker.upper(),
            market_cap=market_cap,
            avg_volume=avg_volume,
            is_otc=is_otc,
        )

    def clear_cache(self, ticker: str | None = None) -> None:
        """Clear cached data.

        Args:
            ticker: Specific ticker to clear, or None for all
        """
        if ticker:
            self._cache.pop(ticker.upper(), None)
        else:
            self._cache.clear()

    def get_category_description(self, category: str) -> str:
        """Get human-readable description of a category.

        Args:
            category: Liquidity category

        Returns:
            Description string
        """
        descriptions = {
            "mega_cap": "Mega-cap stock ($200B+) - Highly efficient market, limited alpha opportunity",
            "large_cap": "Large-cap stock ($10B+) - Efficient market, modest alpha opportunity",
            "mid_cap": "Mid-cap stock ($2B-$10B) - Some inefficiency, moderate alpha opportunity",
            "small_cap": "Small-cap stock ($300M-$2B) - Meaningful inefficiency, good alpha opportunity",
            "micro_cap": "Micro-cap stock ($50M-$300M) - High inefficiency, strong alpha opportunity",
            "penny": "Penny stock (<$5 or <$50M) - Very high inefficiency, highest alpha opportunity",
            "otc": "OTC-traded stock - Maximum inefficiency, extreme alpha opportunity (higher risk)",
        }
        return descriptions.get(category, "Unknown category")
