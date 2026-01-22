"""Link extracted entities to ticker symbols."""

import re
from dataclasses import dataclass
from typing import Any

import structlog

from .entity_extractor import ExtractedEntities
from .knowledge_base import TickerKnowledgeBase

logger = structlog.get_logger(__name__)


@dataclass
class LinkedEntity:
    """An entity linked to a ticker symbol."""

    ticker: str
    confidence: float  # 0-1 confidence score
    source_text: str
    link_type: str  # "explicit", "company_name", "fuzzy"
    cik: str | None = None
    company_name: str | None = None


class TickerLinker:
    """Link entities to ticker symbols using knowledge base."""

    def __init__(self, knowledge_base: TickerKnowledgeBase):
        """Initialize ticker linker.

        Args:
            knowledge_base: Ticker knowledge base
        """
        self.kb = knowledge_base

    async def link_entities(
        self,
        entities: ExtractedEntities,
        text: str | None = None,
    ) -> list[LinkedEntity]:
        """Link extracted entities to ticker symbols.

        Args:
            entities: Extracted entities
            text: Original text for context

        Returns:
            List of linked entities
        """
        linked = []

        # Link explicit tickers (highest confidence)
        for ticker in entities.tickers:
            if self.kb.is_valid_ticker(ticker):
                linked.append(LinkedEntity(
                    ticker=ticker,
                    confidence=1.0,
                    source_text=f"${ticker}",
                    link_type="explicit",
                    cik=self.kb.get_cik(ticker),
                    company_name=self.kb.get_company_name(ticker),
                ))
            else:
                # Ticker not in KB - could be OTC, foreign, or invalid
                linked.append(LinkedEntity(
                    ticker=ticker,
                    confidence=0.7,
                    source_text=f"${ticker}",
                    link_type="explicit_unverified",
                    cik=None,
                    company_name=None,
                ))

        # Link company names (medium confidence)
        for company in entities.companies:
            ticker = self.kb.resolve_company_name(company)
            if ticker and ticker not in [e.ticker for e in linked]:
                linked.append(LinkedEntity(
                    ticker=ticker,
                    confidence=0.85,
                    source_text=company,
                    link_type="company_name",
                    cik=self.kb.get_cik(ticker),
                    company_name=company,
                ))

        return linked

    def link_text(self, text: str) -> list[LinkedEntity]:
        """Link all ticker references in text.

        Args:
            text: Input text

        Returns:
            List of linked entities
        """
        from .entity_extractor import extract_entities

        entities = extract_entities(text, use_spacy=False)

        # Sync version - can't call async from here easily
        linked = []

        for ticker in entities.tickers:
            if self.kb.is_valid_ticker(ticker):
                linked.append(LinkedEntity(
                    ticker=ticker,
                    confidence=1.0,
                    source_text=f"${ticker}",
                    link_type="explicit",
                    cik=self.kb.get_cik(ticker),
                    company_name=self.kb.get_company_name(ticker),
                ))
            else:
                linked.append(LinkedEntity(
                    ticker=ticker,
                    confidence=0.7,
                    source_text=f"${ticker}",
                    link_type="explicit_unverified",
                ))

        return linked

    def resolve_single(self, text: str) -> str | None:
        """Resolve a single text string to a ticker.

        Args:
            text: Company name, ticker, or alias

        Returns:
            Ticker symbol or None
        """
        text = text.strip().upper()

        # Check if it's already a valid ticker
        if self.kb.is_valid_ticker(text):
            return text

        # Check if it's a ticker with $
        if text.startswith("$"):
            ticker = text[1:]
            if self.kb.is_valid_ticker(ticker):
                return ticker

        # Try resolving as company name
        ticker = self.kb.resolve_company_name(text)
        if ticker:
            return ticker

        return None

    def get_primary_ticker(
        self,
        linked_entities: list[LinkedEntity],
    ) -> str | None:
        """Get the primary/most relevant ticker from linked entities.

        Args:
            linked_entities: List of linked entities

        Returns:
            Primary ticker or None
        """
        if not linked_entities:
            return None

        # Sort by confidence
        sorted_entities = sorted(
            linked_entities,
            key=lambda e: e.confidence,
            reverse=True,
        )

        # Prefer explicit mentions over inferred
        for entity in sorted_entities:
            if entity.link_type == "explicit":
                return entity.ticker

        # Fall back to highest confidence
        return sorted_entities[0].ticker

    def validate_ticker(self, ticker: str) -> dict[str, Any]:
        """Validate a ticker and get its info.

        Args:
            ticker: Ticker symbol

        Returns:
            Validation result dict
        """
        ticker = ticker.upper()
        is_valid = self.kb.is_valid_ticker(ticker)

        return {
            "ticker": ticker,
            "is_valid": is_valid,
            "cik": self.kb.get_cik(ticker) if is_valid else None,
            "company_name": self.kb.get_company_name(ticker) if is_valid else None,
        }
