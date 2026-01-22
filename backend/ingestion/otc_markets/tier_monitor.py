"""OTC Markets tier change monitor."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


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


class TierMonitor:
    """Monitor for OTC Markets tier changes."""

    # OTC Markets tier list endpoint
    TIER_LIST_URL = "https://backend.otcmarkets.com/otcapi/market-data/tier-changes"

    def __init__(self, rate_limit: float = 5.0):
        """Initialize tier monitor.

        Args:
            rate_limit: Seconds between requests
        """
        self.rate_limit = rate_limit
        self._client: httpx.AsyncClient | None = None
        self._symbol_tiers: dict[str, OTCTier] = {}

    async def __aenter__(self) -> "TierMonitor":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_tier_changes(
        self,
        days: int = 7,
    ) -> list[TierChange]:
        """Get recent tier changes from OTC Markets.

        Args:
            days: Number of days to look back

        Returns:
            List of tier changes
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        changes = []

        try:
            response = await self._client.get(
                self.TIER_LIST_URL,
                params={"days": days},
            )
            response.raise_for_status()

            data = response.json()
            records = data.get("records", [])

            for record in records:
                old_tier_code = record.get("previousTier", "")
                new_tier_code = record.get("currentTier", "")

                old_tier = OTCTier.from_code(old_tier_code)
                new_tier = OTCTier.from_code(new_tier_code)

                is_upgrade = new_tier.rank > old_tier.rank
                is_downgrade = new_tier.rank < old_tier.rank

                # Calculate signal strength
                tier_diff = abs(new_tier.rank - old_tier.rank)
                signal_strength = min(1.0, tier_diff * 0.25)

                # Major tier changes have higher signal
                if new_tier == OTCTier.OTCQX or old_tier == OTCTier.OTCQX:
                    signal_strength = min(1.0, signal_strength * 1.5)

                changes.append(TierChange(
                    symbol=record.get("symbol", ""),
                    company_name=record.get("companyName", ""),
                    old_tier=old_tier,
                    new_tier=new_tier,
                    change_date=record.get("effectiveDate", ""),
                    is_upgrade=is_upgrade,
                    is_downgrade=is_downgrade,
                    signal_strength=signal_strength,
                    reason=record.get("reason", ""),
                ))

        except httpx.HTTPStatusError as e:
            logger.error("Failed to fetch tier changes", status=e.response.status_code)
        except Exception as e:
            logger.error("Error fetching tier changes", error=str(e))

        return changes

    async def get_symbol_tier(self, symbol: str) -> OTCTier | None:
        """Get current tier for a symbol.

        Args:
            symbol: OTC stock symbol

        Returns:
            Current tier or None
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        # Check cache first
        if symbol in self._symbol_tiers:
            return self._symbol_tiers[symbol]

        try:
            url = f"https://backend.otcmarkets.com/otcapi/company/{symbol}/profile"
            response = await self._client.get(url)
            response.raise_for_status()

            data = response.json()
            tier_code = data.get("tierCode", "")
            tier = OTCTier.from_code(tier_code)

            self._symbol_tiers[symbol] = tier
            return tier

        except Exception as e:
            logger.warning("Failed to get tier", symbol=symbol, error=str(e))
            return None

    async def check_symbol_tier_change(
        self,
        symbol: str,
    ) -> TierChange | None:
        """Check if a symbol's tier has changed.

        Args:
            symbol: OTC stock symbol

        Returns:
            TierChange if changed, None otherwise
        """
        current_tier = await self.get_symbol_tier(symbol)

        if current_tier is None:
            return None

        # Get cached tier
        old_tier = self._symbol_tiers.get(symbol)

        if old_tier is None:
            # First time seeing this symbol
            self._symbol_tiers[symbol] = current_tier
            return None

        if old_tier != current_tier:
            # Tier changed
            is_upgrade = current_tier.rank > old_tier.rank
            is_downgrade = current_tier.rank < old_tier.rank
            tier_diff = abs(current_tier.rank - old_tier.rank)

            change = TierChange(
                symbol=symbol,
                company_name="",
                old_tier=old_tier,
                new_tier=current_tier,
                change_date=datetime.now(timezone.utc).isoformat(),
                is_upgrade=is_upgrade,
                is_downgrade=is_downgrade,
                signal_strength=min(1.0, tier_diff * 0.25),
            )

            # Update cache
            self._symbol_tiers[symbol] = current_tier

            return change

        return None

    async def monitor_tiers(
        self,
        poll_interval: float = 3600.0,
    ) -> AsyncIterator[TierChange]:
        """Monitor for tier changes.

        Args:
            poll_interval: Seconds between checks

        Yields:
            Tier change events
        """
        seen_changes: set[str] = set()

        while True:
            try:
                changes = await self.get_tier_changes(days=1)

                for change in changes:
                    change_id = f"{change.symbol}:{change.old_tier}:{change.new_tier}:{change.change_date}"

                    if change_id not in seen_changes:
                        seen_changes.add(change_id)

                        logger.info(
                            "Tier change detected",
                            symbol=change.symbol,
                            old_tier=change.old_tier.value,
                            new_tier=change.new_tier.value,
                            signal=change.signal,
                        )

                        yield change

            except Exception as e:
                logger.error("Monitor error", error=str(e))

            # Limit seen set size
            if len(seen_changes) > 5000:
                seen_changes = set(list(seen_changes)[-2500:])

            await asyncio.sleep(poll_interval)

    def tier_change_to_event(self, change: TierChange) -> dict[str, Any]:
        """Convert tier change to event dictionary.

        Args:
            change: TierChange object

        Returns:
            Event dictionary
        """
        direction = "upgrade" if change.is_upgrade else "downgrade" if change.is_downgrade else "lateral"

        return {
            "ticker": change.symbol,
            "event_type": "TIER_CHANGE",
            "event_category": f"TIER_{direction.upper()}",
            "headline": f"{change.symbol} tier {direction}: {change.old_tier.value} → {change.new_tier.value}",
            "summary": f"{change.company_name or change.symbol} has been moved from {change.old_tier.value} to {change.new_tier.value} on OTC Markets.",
            "source_name": "OTC Markets",
            "sentiment_label": "positive" if change.is_upgrade else "negative" if change.is_downgrade else "neutral",
            "alpha_score": change.signal_strength if change.is_upgrade else -change.signal_strength if change.is_downgrade else 0,
            "direction": change.signal,
            "metadata": {
                "old_tier": change.old_tier.value,
                "new_tier": change.new_tier.value,
                "change_date": change.change_date,
                "reason": change.reason,
            },
            "event_time": change.change_date or datetime.now(timezone.utc).isoformat(),
            "source": "otc_markets",
        }


async def main():
    """Example usage of tier monitor."""
    async with TierMonitor() as monitor:
        changes = await monitor.get_tier_changes(days=7)
        print(f"Found {len(changes)} tier changes in last 7 days")

        for change in changes[:5]:
            print(f"{change.symbol}: {change.old_tier.value} → {change.new_tier.value} ({change.signal})")


if __name__ == "__main__":
    asyncio.run(main())
