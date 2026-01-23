"""OTC Markets tier change monitor.

This module monitors OTC Markets for tier changes and generates events
for tier upgrades and downgrades. Tier changes are significant for OTC
stocks as they indicate changes in reporting standards, compliance, and
overall company health.

OTC Market Tiers (from best to worst):
- OTCQX: Best Market - highest standards, reporting requirements
- OTCQB: Venture Market - emerging growth companies
- Pink Current: Limited information publicly available
- Pink Limited: Minimal information
- Pink No Information: No information available
- Grey Market: Not quoted by market makers
- Expert Market: Restricted, only available to sophisticated investors
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator

import httpx
import redis
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings

logger = structlog.get_logger(__name__)

# Redis key prefix for tier storage
TIER_CACHE_PREFIX = "otc:tier:"
TIER_HISTORY_PREFIX = "otc:tier_history:"
SEEN_CHANGES_KEY = "otc:seen_tier_changes"


class OTCTier(str, Enum):
    """OTC Markets tier classifications."""

    OTCQX = "OTCQX"  # Best market - highest standards
    OTCQB = "OTCQB"  # Venture market
    PINK_CURRENT = "Pink Current"  # Limited information
    PINK_LIMITED = "Pink Limited"  # Minimal information
    PINK_NO_INFO = "Pink No Information"  # No information
    GREY_MARKET = "Grey Market"  # Not quoted
    EXPERT_MARKET = "Expert Market"  # Restricted

    @classmethod
    def from_code(cls, code: str) -> "OTCTier":
        """Get tier from OTC Markets tier code."""
        mapping = {
            "QX": cls.OTCQX,
            "QB": cls.OTCQB,
            "PC": cls.PINK_CURRENT,
            "PL": cls.PINK_LIMITED,
            "PN": cls.PINK_NO_INFO,
            "GM": cls.GREY_MARKET,
            "EM": cls.EXPERT_MARKET,
        }
        return mapping.get(code.upper(), cls.PINK_NO_INFO)

    @property
    def rank(self) -> int:
        """Get tier rank (higher is better)."""
        ranks = {
            self.OTCQX: 6,
            self.OTCQB: 5,
            self.PINK_CURRENT: 4,
            self.PINK_LIMITED: 3,
            self.PINK_NO_INFO: 2,
            self.GREY_MARKET: 1,
            self.EXPERT_MARKET: 0,
        }
        return ranks.get(self, 0)


@dataclass
class TierChange:
    """Represents a tier change event."""

    symbol: str
    company_name: str
    old_tier: OTCTier
    new_tier: OTCTier
    change_date: str
    is_upgrade: bool
    is_downgrade: bool
    signal_strength: float  # 0-1, higher for significant changes
    reason: str = ""

    @property
    def signal(self) -> str:
        """Get trading signal from tier change."""
        if self.is_upgrade:
            return "BULLISH"
        elif self.is_downgrade:
            return "BEARISH"
        return "NEUTRAL"


class TierChangeClassifier:
    """Classifies tier changes and determines their significance."""

    # Tier change significance weights
    TIER_WEIGHTS = {
        OTCTier.OTCQX: 100,
        OTCTier.OTCQB: 80,
        OTCTier.PINK_CURRENT: 60,
        OTCTier.PINK_LIMITED: 40,
        OTCTier.PINK_NO_INFO: 20,
        OTCTier.GREY_MARKET: 10,
        OTCTier.EXPERT_MARKET: 5,
    }

    @classmethod
    def classify_change(
        cls,
        old_tier: OTCTier,
        new_tier: OTCTier,
    ) -> tuple[str, float, str]:
        """Classify the tier change and determine its significance.

        Args:
            old_tier: Previous tier
            new_tier: New tier

        Returns:
            Tuple of (change_type, signal_strength, description)
        """
        old_weight = cls.TIER_WEIGHTS.get(old_tier, 0)
        new_weight = cls.TIER_WEIGHTS.get(new_tier, 0)
        weight_diff = new_weight - old_weight

        # Determine change type and base description
        if new_tier == OTCTier.OTCQX:
            if old_tier == OTCTier.OTCQB:
                return ("MAJOR_UPGRADE", 0.85, "Promoted to premium OTCQX tier")
            else:
                return ("MAJOR_UPGRADE", 0.95, "Significant upgrade to OTCQX")

        elif new_tier == OTCTier.OTCQB:
            if old_tier == OTCTier.OTCQX:
                return ("MINOR_DOWNGRADE", 0.4, "Downgraded from OTCQX to OTCQB")
            elif old_tier in (OTCTier.PINK_CURRENT, OTCTier.PINK_LIMITED):
                return ("UPGRADE", 0.7, "Upgraded to OTCQB venture market")
            else:
                return ("MAJOR_UPGRADE", 0.8, "Significant upgrade to OTCQB")

        elif new_tier == OTCTier.PINK_CURRENT:
            if old_tier in (OTCTier.OTCQX, OTCTier.OTCQB):
                return ("DOWNGRADE", 0.6, "Downgraded to Pink Current")
            elif old_tier in (OTCTier.PINK_LIMITED, OTCTier.PINK_NO_INFO):
                return ("UPGRADE", 0.5, "Upgraded to Pink Current")
            else:
                return ("MAJOR_UPGRADE", 0.65, "Upgraded from restricted tier")

        elif new_tier == OTCTier.EXPERT_MARKET:
            return ("MAJOR_DOWNGRADE", 0.9, "Moved to restricted Expert Market")

        elif new_tier == OTCTier.GREY_MARKET:
            return ("MAJOR_DOWNGRADE", 0.85, "Moved to Grey Market - no active quotes")

        elif new_tier == OTCTier.PINK_NO_INFO:
            if old_tier in (OTCTier.EXPERT_MARKET, OTCTier.GREY_MARKET):
                return ("MINOR_UPGRADE", 0.3, "Slight improvement from restricted tier")
            else:
                return ("DOWNGRADE", 0.65, "Downgraded to Pink No Information")

        elif new_tier == OTCTier.PINK_LIMITED:
            if old_tier in (OTCTier.PINK_NO_INFO, OTCTier.GREY_MARKET, OTCTier.EXPERT_MARKET):
                return ("MINOR_UPGRADE", 0.35, "Upgraded to Pink Limited")
            else:
                return ("DOWNGRADE", 0.5, "Downgraded to Pink Limited")

        # Default classification based on weight difference
        if weight_diff > 0:
            strength = min(0.8, abs(weight_diff) / 100)
            return ("UPGRADE", strength, f"Tier upgrade: {old_tier.value} to {new_tier.value}")
        elif weight_diff < 0:
            strength = min(0.8, abs(weight_diff) / 100)
            return ("DOWNGRADE", strength, f"Tier downgrade: {old_tier.value} to {new_tier.value}")
        else:
            return ("LATERAL", 0.1, "Lateral tier move")


class TierPersistence:
    """Redis-based persistence for tier tracking across task runs."""

    def __init__(self, redis_url: str | None = None):
        """Initialize tier persistence.

        Args:
            redis_url: Redis connection URL
        """
        self._redis_url = redis_url or str(settings.redis_url)
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url)
        return self._client

    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None

    def get_stored_tier(self, symbol: str) -> OTCTier | None:
        """Get stored tier for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Stored tier or None if not found
        """
        try:
            client = self._get_client()
            tier_value = client.get(f"{TIER_CACHE_PREFIX}{symbol.upper()}")
            if tier_value:
                return OTCTier(tier_value.decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to get stored tier", symbol=symbol, error=str(e))
        return None

    def store_tier(self, symbol: str, tier: OTCTier, ttl_days: int = 90) -> bool:
        """Store tier for a symbol.

        Args:
            symbol: Stock symbol
            tier: Current tier
            ttl_days: TTL in days for the cache entry

        Returns:
            True if stored successfully
        """
        try:
            client = self._get_client()
            key = f"{TIER_CACHE_PREFIX}{symbol.upper()}"
            ttl_seconds = ttl_days * 24 * 60 * 60
            client.setex(key, ttl_seconds, tier.value)
            return True
        except Exception as e:
            logger.warning("Failed to store tier", symbol=symbol, error=str(e))
            return False

    def store_tier_history(
        self,
        symbol: str,
        old_tier: OTCTier,
        new_tier: OTCTier,
        change_date: str,
    ) -> bool:
        """Store tier change history.

        Args:
            symbol: Stock symbol
            old_tier: Previous tier
            new_tier: New tier
            change_date: Date of change

        Returns:
            True if stored successfully
        """
        try:
            client = self._get_client()
            key = f"{TIER_HISTORY_PREFIX}{symbol.upper()}"
            history_entry = json.dumps({
                "old_tier": old_tier.value,
                "new_tier": new_tier.value,
                "change_date": change_date,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            })
            # Store in sorted set with timestamp as score for ordering
            score = datetime.now(timezone.utc).timestamp()
            client.zadd(key, {history_entry: score})
            # Keep only last 100 changes per symbol
            client.zremrangebyrank(key, 0, -101)
            return True
        except Exception as e:
            logger.warning("Failed to store tier history", symbol=symbol, error=str(e))
            return False

    def is_change_seen(self, change_id: str) -> bool:
        """Check if a tier change has been seen before.

        Args:
            change_id: Unique identifier for the change

        Returns:
            True if change was already seen
        """
        try:
            client = self._get_client()
            return client.sismember(SEEN_CHANGES_KEY, change_id)
        except Exception as e:
            logger.warning("Failed to check seen change", error=str(e))
            return False

    def mark_change_seen(self, change_id: str, ttl_days: int = 30) -> bool:
        """Mark a tier change as seen.

        Args:
            change_id: Unique identifier for the change
            ttl_days: TTL for the seen marker

        Returns:
            True if marked successfully
        """
        try:
            client = self._get_client()
            client.sadd(SEEN_CHANGES_KEY, change_id)
            # Trim set if it gets too large
            if client.scard(SEEN_CHANGES_KEY) > 10000:
                # Remove random members to keep set manageable
                members = client.srandmember(SEEN_CHANGES_KEY, 5000)
                if members:
                    client.srem(SEEN_CHANGES_KEY, *members)
            return True
        except Exception as e:
            logger.warning("Failed to mark change seen", error=str(e))
            return False

    def get_all_stored_tiers(self) -> dict[str, OTCTier]:
        """Get all stored tiers from Redis.

        Returns:
            Dictionary mapping symbols to their stored tiers
        """
        result = {}
        try:
            client = self._get_client()
            # Scan for all tier keys
            cursor = 0
            while True:
                cursor, keys = client.scan(
                    cursor=cursor,
                    match=f"{TIER_CACHE_PREFIX}*",
                    count=100,
                )
                for key in keys:
                    symbol = key.decode("utf-8").replace(TIER_CACHE_PREFIX, "")
                    tier_value = client.get(key)
                    if tier_value:
                        try:
                            result[symbol] = OTCTier(tier_value.decode("utf-8"))
                        except ValueError:
                            pass
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning("Failed to get all stored tiers", error=str(e))
        return result


class TierMonitor:
    """Monitor for OTC Markets tier changes.

    This monitor fetches tier information from OTC Markets, compares against
    previously known tiers (stored in Redis), and generates events for
    tier upgrades and downgrades.
    """

    # OTC Markets tier list endpoint
    TIER_LIST_URL = "https://backend.otcmarkets.com/otcapi/market-data/tier-changes"
    COMPANY_PROFILE_URL = "https://backend.otcmarkets.com/otcapi/company/{symbol}/profile"
    SCREENER_URL = "https://backend.otcmarkets.com/otcapi/market-data/screener"

    def __init__(self, rate_limit: float = 5.0, use_persistence: bool = True):
        """Initialize tier monitor.

        Args:
            rate_limit: Seconds between requests
            use_persistence: Whether to use Redis persistence for tier tracking
        """
        self.rate_limit = rate_limit
        self._client: httpx.AsyncClient | None = None
        self._symbol_tiers: dict[str, OTCTier] = {}
        self._use_persistence = use_persistence
        self._persistence: TierPersistence | None = None
        self._classifier = TierChangeClassifier()

    async def __aenter__(self) -> "TierMonitor":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        if self._use_persistence:
            self._persistence = TierPersistence()
            # Load stored tiers into memory cache
            self._symbol_tiers = self._persistence.get_all_stored_tiers()
            logger.info("Loaded stored tiers", count=len(self._symbol_tiers))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
        if self._persistence:
            self._persistence.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_tier_changes(
        self,
        days: int = 7,
    ) -> list[TierChange]:
        """Get recent tier changes from OTC Markets.

        This method fetches tier changes from the OTC Markets API and filters
        out any changes that have already been processed. New changes are
        persisted to Redis for future comparison.

        Args:
            days: Number of days to look back

        Returns:
            List of new tier changes (excluding previously seen changes)
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        changes = []
        new_changes = []

        try:
            response = await self._client.get(
                self.TIER_LIST_URL,
                params={"days": days},
            )
            response.raise_for_status()

            data = response.json()
            records = data.get("records", [])

            logger.info("Fetched tier change records", count=len(records), days=days)

            for record in records:
                symbol = record.get("symbol", "").upper()
                if not symbol:
                    continue

                old_tier_code = record.get("previousTier", "")
                new_tier_code = record.get("currentTier", "")
                change_date = record.get("effectiveDate", "")

                old_tier = OTCTier.from_code(old_tier_code)
                new_tier = OTCTier.from_code(new_tier_code)

                # Skip if tiers are the same
                if old_tier == new_tier:
                    continue

                # Create unique change ID for deduplication
                change_id = f"{symbol}:{old_tier.value}:{new_tier.value}:{change_date}"

                # Check if already seen (using persistence if available)
                if self._persistence and self._persistence.is_change_seen(change_id):
                    continue

                # Classify the tier change
                change_type, signal_strength, description = self._classifier.classify_change(
                    old_tier, new_tier
                )

                is_upgrade = new_tier.rank > old_tier.rank
                is_downgrade = new_tier.rank < old_tier.rank

                change = TierChange(
                    symbol=symbol,
                    company_name=record.get("companyName", ""),
                    old_tier=old_tier,
                    new_tier=new_tier,
                    change_date=change_date,
                    is_upgrade=is_upgrade,
                    is_downgrade=is_downgrade,
                    signal_strength=signal_strength,
                    reason=record.get("reason", "") or description,
                )

                changes.append(change)

                # Mark as seen and update stored tier
                if self._persistence:
                    self._persistence.mark_change_seen(change_id)
                    self._persistence.store_tier(symbol, new_tier)
                    self._persistence.store_tier_history(
                        symbol, old_tier, new_tier, change_date
                    )

                # Update in-memory cache
                self._symbol_tiers[symbol] = new_tier

                logger.info(
                    "Tier change detected",
                    symbol=symbol,
                    old_tier=old_tier.value,
                    new_tier=new_tier.value,
                    change_type=change_type,
                    signal_strength=signal_strength,
                )

                new_changes.append(change)

        except httpx.HTTPStatusError as e:
            logger.error("Failed to fetch tier changes", status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("Error fetching tier changes", error=str(e))
            raise

        logger.info(
            "Processed tier changes",
            total_records=len(records) if "records" in dir() else 0,
            new_changes=len(new_changes),
        )

        return new_changes

    async def get_symbol_tier(self, symbol: str, use_cache: bool = True) -> OTCTier | None:
        """Get current tier for a symbol.

        This method first checks the in-memory cache, then Redis persistence,
        and finally fetches from the OTC Markets API if not found.

        Args:
            symbol: OTC stock symbol
            use_cache: Whether to use cached value if available

        Returns:
            Current tier or None if not found
        """
        symbol = symbol.upper()

        # Check in-memory cache first
        if use_cache and symbol in self._symbol_tiers:
            return self._symbol_tiers[symbol]

        # Check Redis persistence
        if use_cache and self._persistence:
            stored_tier = self._persistence.get_stored_tier(symbol)
            if stored_tier:
                self._symbol_tiers[symbol] = stored_tier
                return stored_tier

        # Fetch from API
        current_tier = await self.fetch_current_tier(symbol)
        if current_tier:
            # Cache the result
            self._symbol_tiers[symbol] = current_tier
            if self._persistence:
                self._persistence.store_tier(symbol, current_tier)

        return current_tier

    async def check_symbol_tier_change(
        self,
        symbol: str,
    ) -> TierChange | None:
        """Check if a symbol's tier has changed from its stored value.

        This is an alias for detect_tier_change_for_symbol for backwards
        compatibility.

        Args:
            symbol: OTC stock symbol

        Returns:
            TierChange if changed, None otherwise
        """
        return await self.detect_tier_change_for_symbol(symbol)

    async def monitor_tiers(
        self,
        poll_interval: float = 3600.0,
    ) -> AsyncIterator[TierChange]:
        """Monitor for tier changes continuously.

        This is a long-running generator that continuously polls for tier
        changes at the specified interval. Changes are deduplicated using
        Redis persistence when available.

        Args:
            poll_interval: Seconds between checks (default: 1 hour)

        Yields:
            TierChange events as they are detected
        """
        logger.info("Starting tier monitor", poll_interval=poll_interval)

        while True:
            try:
                # get_tier_changes now handles deduplication internally
                changes = await self.get_tier_changes(days=1)

                for change in changes:
                    logger.info(
                        "Yielding tier change",
                        symbol=change.symbol,
                        old_tier=change.old_tier.value,
                        new_tier=change.new_tier.value,
                        signal=change.signal,
                        signal_strength=change.signal_strength,
                    )

                    yield change

                logger.debug("Tier monitor poll complete", changes_found=len(changes))

            except Exception as e:
                logger.error("Monitor error", error=str(e))
                # Continue monitoring despite errors

            await asyncio.sleep(poll_interval)

    async def get_tier_changes_batch(
        self,
        symbols: list[str],
        rate_limit_delay: float = 0.5,
    ) -> list[TierChange]:
        """Check multiple symbols for tier changes.

        This method is useful for checking a batch of symbols from a watchlist
        against their stored tiers.

        Args:
            symbols: List of symbols to check
            rate_limit_delay: Delay between API calls to avoid rate limiting

        Returns:
            List of detected tier changes
        """
        changes = []

        for symbol in symbols:
            try:
                change = await self.detect_tier_change_for_symbol(symbol)
                if change:
                    changes.append(change)

                # Rate limiting
                await asyncio.sleep(rate_limit_delay)

            except Exception as e:
                logger.warning("Error checking symbol", symbol=symbol, error=str(e))

        return changes

    def tier_change_to_event(self, change: TierChange) -> dict[str, Any]:
        """Convert tier change to event dictionary.

        This method creates a properly formatted event dictionary that can be
        processed by the standard NLP pipeline and stored in the database.

        Args:
            change: TierChange object

        Returns:
            Event dictionary compatible with the event processing pipeline
        """
        # Classify the change for better event categorization
        change_type, signal_strength, description = self._classifier.classify_change(
            change.old_tier, change.new_tier
        )

        # Determine event category and type
        if change.is_upgrade:
            direction = "upgrade"
            event_category = "TIER_UPGRADE"
            sentiment_label = "positive"
            sentiment_score = signal_strength
        elif change.is_downgrade:
            direction = "downgrade"
            event_category = "TIER_DOWNGRADE"
            sentiment_label = "negative"
            sentiment_score = -signal_strength
        else:
            direction = "lateral"
            event_category = "TIER_CHANGE"
            sentiment_label = "neutral"
            sentiment_score = 0.0

        # Create descriptive headline
        headline = f"{change.symbol} OTC tier {direction}: {change.old_tier.value} to {change.new_tier.value}"

        # Create detailed summary
        company = change.company_name or change.symbol
        summary_parts = [
            f"{company} has been moved from {change.old_tier.value} to {change.new_tier.value} on OTC Markets.",
        ]
        if change.reason:
            summary_parts.append(f"Reason: {change.reason}")
        if description and description != change.reason:
            summary_parts.append(description)

        summary = " ".join(summary_parts)

        # Calculate alpha score based on change significance
        alpha_score = signal_strength if change.is_upgrade else -signal_strength if change.is_downgrade else 0

        # Determine urgency level based on signal strength
        if signal_strength >= 0.8:
            urgency_level = "HIGH"
        elif signal_strength >= 0.5:
            urgency_level = "MEDIUM"
        else:
            urgency_level = "LOW"

        return {
            "ticker": change.symbol,
            "event_type": "TIER_CHANGE",
            "event_category": event_category,
            "headline": headline,
            "summary": summary,
            "content": f"{summary}\n\nPrevious Tier: {change.old_tier.value}\nNew Tier: {change.new_tier.value}\nChange Type: {change_type}",
            "source_name": "OTC Markets",
            "source_url": f"https://www.otcmarkets.com/stock/{change.symbol}/overview",
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
            "sentiment_confidence": 0.9,  # High confidence for tier changes
            "alpha_score": alpha_score,
            "direction": change.signal,
            "urgency_level": urgency_level,
            "extracted_tickers": [change.symbol],
            "extracted_companies": [change.company_name] if change.company_name else [],
            "metadata": {
                "old_tier": change.old_tier.value,
                "new_tier": change.new_tier.value,
                "old_tier_rank": change.old_tier.rank,
                "new_tier_rank": change.new_tier.rank,
                "change_date": change.change_date,
                "change_type": change_type,
                "reason": change.reason,
                "signal_strength": signal_strength,
            },
            "event_time": change.change_date or datetime.now(timezone.utc).isoformat(),
            "source": "otc_markets",
        }

    async def fetch_current_tier(self, symbol: str) -> OTCTier | None:
        """Fetch the current tier for a symbol from OTC Markets.

        Args:
            symbol: Stock symbol

        Returns:
            Current tier or None if not found
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            url = self.COMPANY_PROFILE_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)
            response.raise_for_status()

            data = response.json()
            tier_code = data.get("tierCode", "")
            if tier_code:
                return OTCTier.from_code(tier_code)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug("Symbol not found", symbol=symbol)
            else:
                logger.warning("Failed to fetch current tier", symbol=symbol, status=e.response.status_code)
        except Exception as e:
            logger.warning("Error fetching current tier", symbol=symbol, error=str(e))

        return None

    async def detect_tier_change_for_symbol(
        self,
        symbol: str,
    ) -> TierChange | None:
        """Detect tier change for a specific symbol by comparing to stored tier.

        This method is useful for checking individual symbols against their
        previously known tier.

        Args:
            symbol: Stock symbol to check

        Returns:
            TierChange if a change was detected, None otherwise
        """
        symbol = symbol.upper()

        # Get stored tier
        stored_tier = self._symbol_tiers.get(symbol)
        if self._persistence and not stored_tier:
            stored_tier = self._persistence.get_stored_tier(symbol)

        # Fetch current tier from OTC Markets
        current_tier = await self.fetch_current_tier(symbol)
        if not current_tier:
            return None

        # First time seeing this symbol - store and return
        if not stored_tier:
            self._symbol_tiers[symbol] = current_tier
            if self._persistence:
                self._persistence.store_tier(symbol, current_tier)
            logger.debug("New symbol tracked", symbol=symbol, tier=current_tier.value)
            return None

        # Check for change
        if stored_tier != current_tier:
            change_type, signal_strength, description = self._classifier.classify_change(
                stored_tier, current_tier
            )

            change = TierChange(
                symbol=symbol,
                company_name="",  # Would need additional API call
                old_tier=stored_tier,
                new_tier=current_tier,
                change_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                is_upgrade=current_tier.rank > stored_tier.rank,
                is_downgrade=current_tier.rank < stored_tier.rank,
                signal_strength=signal_strength,
                reason=description,
            )

            # Update stored tier
            self._symbol_tiers[symbol] = current_tier
            if self._persistence:
                self._persistence.store_tier(symbol, current_tier)
                self._persistence.store_tier_history(
                    symbol, stored_tier, current_tier, change.change_date
                )

            logger.info(
                "Tier change detected for symbol",
                symbol=symbol,
                old_tier=stored_tier.value,
                new_tier=current_tier.value,
                change_type=change_type,
            )

            return change

        return None


async def main():
    """Example usage of tier monitor."""
    print("OTC Markets Tier Monitor Demo")
    print("=" * 50)

    async with TierMonitor(use_persistence=True) as monitor:
        # Fetch recent tier changes
        print("\nFetching tier changes from last 7 days...")
        changes = await monitor.get_tier_changes(days=7)
        print(f"Found {len(changes)} new tier changes")

        if changes:
            print("\nRecent Tier Changes:")
            print("-" * 50)

            for change in changes[:10]:
                # Get classified change info
                change_type, signal_strength, description = TierChangeClassifier.classify_change(
                    change.old_tier, change.new_tier
                )

                print(f"\n{change.symbol}: {change.old_tier.value} -> {change.new_tier.value}")
                print(f"  Company: {change.company_name or 'N/A'}")
                print(f"  Type: {change_type}")
                print(f"  Signal: {change.signal} (strength: {signal_strength:.2f})")
                print(f"  Date: {change.change_date}")
                if change.reason:
                    print(f"  Reason: {change.reason}")

                # Convert to event
                event = monitor.tier_change_to_event(change)
                print(f"  Event Headline: {event['headline']}")
                print(f"  Alpha Score: {event['alpha_score']:.2f}")

        # Demo single symbol lookup
        print("\n" + "=" * 50)
        print("\nLooking up specific symbol tier...")
        test_symbols = ["ABML", "ALPP", "HCMC"]

        for symbol in test_symbols:
            tier = await monitor.get_symbol_tier(symbol)
            if tier:
                print(f"  {symbol}: {tier.value}")
            else:
                print(f"  {symbol}: Not found")


if __name__ == "__main__":
    asyncio.run(main())
