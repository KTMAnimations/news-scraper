"""Knowledge base for ticker/company mapping."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


# SEC company tickers endpoint
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_EXCHANGE_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


class TickerKnowledgeBase:
    """Knowledge base for ticker symbols, CIKs, and company names.

    Supports companies with multiple share classes (e.g., GOOGL/GOOG, BRK.A/BRK.B).
    """

    def __init__(self, cache_path: Path | None = None):
        """Initialize knowledge base.

        Args:
            cache_path: Path to cache file
        """
        self.cache_path = cache_path or Path("data/ticker_kb.json")
        self._ticker_to_cik: dict[str, str] = {}
        self._cik_to_ticker: dict[str, str] = {}  # Primary ticker (first one seen)
        self._cik_to_tickers: dict[str, list[str]] = {}  # All tickers for a CIK
        self._ticker_to_name: dict[str, str] = {}
        self._name_to_ticker: dict[str, str] = {}
        self._aliases: dict[str, str] = {}  # Alias -> canonical ticker
        self._loaded = False

    async def load(self, force_refresh: bool = False) -> None:
        """Load ticker data from SEC and cache.

        Args:
            force_refresh: Force refresh from SEC
        """
        if self._loaded and not force_refresh:
            return

        # Try loading from cache first
        if not force_refresh and self._load_cache():
            self._loaded = True
            logger.info("Loaded ticker KB from cache", tickers=len(self._ticker_to_cik))
            return

        # Fetch from SEC
        await self._fetch_from_sec()

        # Add common aliases
        self._add_common_aliases()

        # Save to cache
        self._save_cache()

        self._loaded = True
        logger.info("Loaded ticker KB from SEC", tickers=len(self._ticker_to_cik))

    def _load_cache(self) -> bool:
        """Load from cache file.

        Returns:
            True if cache loaded successfully
        """
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path) as f:
                data = json.load(f)

            self._ticker_to_cik = data.get("ticker_to_cik", {})
            self._cik_to_ticker = data.get("cik_to_ticker", {})
            self._cik_to_tickers = data.get("cik_to_tickers", {})
            self._ticker_to_name = data.get("ticker_to_name", {})
            self._name_to_ticker = data.get("name_to_ticker", {})
            self._aliases = data.get("aliases", {})

            # Rebuild cik_to_tickers if missing (backward compatibility)
            if not self._cik_to_tickers and self._ticker_to_cik:
                self._rebuild_cik_to_tickers()

            return bool(self._ticker_to_cik)

        except Exception as e:
            logger.warning("Failed to load cache", error=str(e))
            return False

    def _rebuild_cik_to_tickers(self) -> None:
        """Rebuild cik_to_tickers mapping from ticker_to_cik."""
        self._cik_to_tickers = {}
        for ticker, cik in self._ticker_to_cik.items():
            if cik not in self._cik_to_tickers:
                self._cik_to_tickers[cik] = []
            if ticker not in self._cik_to_tickers[cik]:
                self._cik_to_tickers[cik].append(ticker)

    def _save_cache(self) -> None:
        """Save to cache file."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "ticker_to_cik": self._ticker_to_cik,
                "cik_to_ticker": self._cik_to_ticker,
                "cik_to_tickers": self._cik_to_tickers,
                "ticker_to_name": self._ticker_to_name,
                "name_to_ticker": self._name_to_ticker,
                "aliases": self._aliases,
            }

            with open(self.cache_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info("Saved ticker KB to cache", path=str(self.cache_path))

        except Exception as e:
            logger.warning("Failed to save cache", error=str(e))

    async def _fetch_from_sec(self) -> None:
        """Fetch ticker data from SEC.

        Handles companies with multiple share classes (e.g., GOOGL/GOOG for Alphabet).
        """
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.sec_user_agent},
            timeout=60.0,
        ) as client:
            try:
                response = await client.get(SEC_TICKERS_URL)
                response.raise_for_status()
                data = response.json()

                for entry in data.values():
                    ticker = str(entry.get("ticker", "")).upper()
                    cik = str(entry.get("cik_str", ""))
                    name = str(entry.get("title", ""))

                    if ticker and cik:
                        self._ticker_to_cik[ticker] = cik

                        # Build list of all tickers for this CIK
                        if cik not in self._cik_to_tickers:
                            self._cik_to_tickers[cik] = []
                            # Set first ticker as primary
                            self._cik_to_ticker[cik] = ticker

                        if ticker not in self._cik_to_tickers[cik]:
                            self._cik_to_tickers[cik].append(ticker)

                        if name:
                            self._ticker_to_name[ticker] = name
                            # Normalize company name for lookup
                            name_normalized = self._normalize_name(name)
                            self._name_to_ticker[name_normalized] = ticker

                # Log companies with multiple tickers
                multi_ticker_count = sum(1 for tickers in self._cik_to_tickers.values() if len(tickers) > 1)
                logger.info(
                    "Loaded ticker data from SEC",
                    total_tickers=len(self._ticker_to_cik),
                    multi_ticker_companies=multi_ticker_count,
                )

            except Exception as e:
                logger.error("Failed to fetch from SEC", error=str(e))

    def _normalize_name(self, name: str) -> str:
        """Normalize company name for matching.

        Args:
            name: Company name

        Returns:
            Normalized name
        """
        import re

        name = name.upper()
        # Remove common suffixes
        suffixes = [
            r"\s+INC\.?$",
            r"\s+CORP\.?$",
            r"\s+CO\.?$",
            r"\s+LTD\.?$",
            r"\s+LLC\.?$",
            r"\s+LP\.?$",
            r"\s+PLC\.?$",
            r"\s+LIMITED$",
            r"\s+CORPORATION$",
            r"\s+INCORPORATED$",
            r"\s+COMPANY$",
        ]

        for suffix in suffixes:
            name = re.sub(suffix, "", name)

        # Remove extra whitespace
        name = " ".join(name.split())

        return name

    def _add_common_aliases(self) -> None:
        """Add common company name aliases."""
        aliases = {
            # Tech giants
            "APPLE": "AAPL",
            "APPLE COMPUTER": "AAPL",
            "MICROSOFT": "MSFT",
            "GOOGLE": "GOOGL",
            "ALPHABET": "GOOGL",
            "AMAZON": "AMZN",
            "FACEBOOK": "META",
            "META": "META",
            "META PLATFORMS": "META",
            "TESLA": "TSLA",
            "NVIDIA": "NVDA",
            "NETFLIX": "NFLX",

            # Financial
            "JPMORGAN": "JPM",
            "JP MORGAN": "JPM",
            "BANK OF AMERICA": "BAC",
            "GOLDMAN": "GS",
            "GOLDMAN SACHS": "GS",
            "MORGAN STANLEY": "MS",
            "CITIGROUP": "C",
            "CITI": "C",
            "WELLS FARGO": "WFC",

            # Healthcare
            "PFIZER": "PFE",
            "JOHNSON AND JOHNSON": "JNJ",
            "J&J": "JNJ",
            "MERCK": "MRK",
            "ABBVIE": "ABBV",

            # Consumer
            "WALMART": "WMT",
            "COSTCO": "COST",
            "COCA COLA": "KO",
            "COKE": "KO",
            "PEPSI": "PEP",
            "PEPSICO": "PEP",
            "MCDONALD'S": "MCD",
            "MCDONALDS": "MCD",

            # Energy
            "EXXON": "XOM",
            "EXXON MOBIL": "XOM",
            "CHEVRON": "CVX",
        }

        for alias, ticker in aliases.items():
            self._aliases[alias.upper()] = ticker.upper()

        # Add known multi-class share mappings
        # These help when one class is referenced but we know about another
        self._add_share_class_mappings()

    def _add_share_class_mappings(self) -> None:
        """Add mappings for well-known companies with multiple share classes.

        This ensures both classes are properly linked to the same company.
        """
        # Well-known companies with multiple share classes
        multi_class_companies = {
            # Alphabet (Google) - GOOGL (Class A), GOOG (Class C)
            "GOOGL": ["GOOG"],
            "GOOG": ["GOOGL"],

            # Berkshire Hathaway - BRK.A (Class A), BRK.B (Class B)
            "BRK.A": ["BRK.B", "BRK-A", "BRK-B"],
            "BRK.B": ["BRK.A", "BRK-A", "BRK-B"],
            "BRK-A": ["BRK.A", "BRK.B", "BRK-B"],
            "BRK-B": ["BRK.A", "BRK.B", "BRK-A"],

            # News Corp - NWSA (Class A), NWS (Class B)
            "NWSA": ["NWS"],
            "NWS": ["NWSA"],

            # Fox Corporation - FOXA (Class A), FOX (Class B)
            "FOXA": ["FOX"],
            "FOX": ["FOXA"],

            # Discovery - DISCA (Class A), DISCB (Class B), DISCK (Class C)
            "DISCA": ["DISCB", "DISCK"],
            "DISCB": ["DISCA", "DISCK"],
            "DISCK": ["DISCA", "DISCB"],

            # Under Armour - UAA (Class A), UA (Class C)
            "UAA": ["UA"],
            "UA": ["UAA"],

            # Zillow - ZG (Class A), Z (Class C)
            "ZG": ["Z"],
            "Z": ["ZG"],
        }

        # Store these for reference (useful for resolving related tickers)
        self._share_class_mappings = multi_class_companies

    def get_cik(self, ticker: str) -> str | None:
        """Get CIK for a ticker.

        Args:
            ticker: Stock ticker

        Returns:
            CIK string or None
        """
        ticker = ticker.upper()

        # Check aliases first
        if ticker in self._aliases:
            ticker = self._aliases[ticker]

        return self._ticker_to_cik.get(ticker)

    def get_ticker(self, cik: str) -> str | None:
        """Get primary ticker for a CIK.

        For companies with multiple share classes, returns the first/primary ticker.
        Use get_all_tickers_for_cik() to get all tickers.

        Args:
            cik: SEC CIK

        Returns:
            Primary ticker string or None
        """
        # Normalize CIK (remove leading zeros)
        cik = str(int(cik))
        return self._cik_to_ticker.get(cik)

    def get_all_tickers_for_cik(self, cik: str) -> list[str]:
        """Get all tickers associated with a CIK.

        Companies may have multiple share classes (e.g., GOOGL/GOOG for Alphabet,
        BRK.A/BRK.B for Berkshire Hathaway).

        Args:
            cik: SEC CIK

        Returns:
            List of ticker symbols, or empty list if CIK not found
        """
        # Normalize CIK (remove leading zeros)
        cik = str(int(cik))
        return self._cik_to_tickers.get(cik, [])

    def has_multiple_tickers(self, cik: str) -> bool:
        """Check if a CIK has multiple associated tickers.

        Args:
            cik: SEC CIK

        Returns:
            True if company has multiple share classes/tickers
        """
        cik = str(int(cik))
        tickers = self._cik_to_tickers.get(cik, [])
        return len(tickers) > 1

    def get_related_tickers(self, ticker: str) -> list[str]:
        """Get all tickers related to a given ticker (same company).

        Useful for finding other share classes of the same company.
        Combines data from SEC filings and known share class mappings.

        Args:
            ticker: Stock ticker

        Returns:
            List of related tickers (excluding the input ticker),
            or empty list if no related tickers found
        """
        ticker = ticker.upper()
        related = set()

        # First, check CIK-based relationships
        cik = self._ticker_to_cik.get(ticker)
        if cik:
            all_tickers = self._cik_to_tickers.get(cik, [])
            related.update(t for t in all_tickers if t != ticker)

        # Also check known share class mappings
        if hasattr(self, "_share_class_mappings"):
            mapped = self._share_class_mappings.get(ticker, [])
            related.update(mapped)

        return list(related)

    def get_company_name(self, ticker: str) -> str | None:
        """Get company name for a ticker.

        Args:
            ticker: Stock ticker

        Returns:
            Company name or None
        """
        return self._ticker_to_name.get(ticker.upper())

    def resolve_company_name(self, name: str) -> str | None:
        """Resolve a company name to ticker.

        Args:
            name: Company name or alias

        Returns:
            Ticker string or None
        """
        name_upper = name.upper()

        # Check aliases first
        if name_upper in self._aliases:
            return self._aliases[name_upper]

        # Check normalized names
        name_normalized = self._normalize_name(name)
        if name_normalized in self._name_to_ticker:
            return self._name_to_ticker[name_normalized]

        return None

    def add_alias(self, alias: str, ticker: str) -> None:
        """Add a company alias.

        Args:
            alias: Alias name
            ticker: Ticker symbol
        """
        self._aliases[alias.upper()] = ticker.upper()

    def is_valid_ticker(self, ticker: str) -> bool:
        """Check if a ticker is valid.

        Args:
            ticker: Ticker to check

        Returns:
            True if valid ticker
        """
        return ticker.upper() in self._ticker_to_cik

    def search_tickers(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        """Search for tickers by name or symbol.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching ticker info
        """
        query = query.upper()
        results = []

        # Search by ticker prefix
        for ticker in self._ticker_to_cik:
            if ticker.startswith(query):
                results.append({
                    "ticker": ticker,
                    "name": self._ticker_to_name.get(ticker, ""),
                    "cik": self._ticker_to_cik[ticker],
                })

                if len(results) >= limit:
                    return results

        # Search by company name
        for ticker, name in self._ticker_to_name.items():
            if query in name.upper() and ticker not in [r["ticker"] for r in results]:
                results.append({
                    "ticker": ticker,
                    "name": name,
                    "cik": self._ticker_to_cik[ticker],
                })

                if len(results) >= limit:
                    return results

        return results

    def get_all_tickers(self) -> set[str]:
        """Get all known tickers.

        Returns:
            Set of all ticker symbols
        """
        return set(self._ticker_to_cik.keys())


# Global knowledge base instance
_kb: TickerKnowledgeBase | None = None


async def get_knowledge_base() -> TickerKnowledgeBase:
    """Get or create global knowledge base."""
    global _kb
    if _kb is None:
        _kb = TickerKnowledgeBase()
        await _kb.load()
    return _kb
