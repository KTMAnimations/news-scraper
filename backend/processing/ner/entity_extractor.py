"""Entity extraction using spaCy NER."""

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedEntities:
    """Container for extracted entities."""

    tickers: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    money: list[dict[str, Any]] = field(default_factory=list)
    percentages: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tickers": self.tickers,
            "companies": self.companies,
            "people": self.people,
            "money": self.money,
            "percentages": self.percentages,
            "dates": self.dates,
            "locations": self.locations,
        }


class EntityExtractor:
    """Extract named entities from financial text using spaCy."""

    # Ticker pattern: $ followed by 1-5 uppercase letters
    TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")

    # Alternative ticker patterns (exchange prefixes)
    EXCHANGE_TICKER_PATTERN = re.compile(
        r"(?:NYSE|NASDAQ|OTC|OTCQB|OTCQX|TSX|AMEX)[:\s]*([A-Z]{1,5})\b",
        re.IGNORECASE,
    )

    # Money pattern
    MONEY_PATTERN = re.compile(
        r"\$[\d,]+(?:\.\d{1,2})?\s*(?:million|billion|thousand|M|B|K)?",
        re.IGNORECASE,
    )

    # Percentage pattern
    PERCENT_PATTERN = re.compile(r"[\d.]+%")

    # Words that look like tickers but aren't
    EXCLUDED_TICKERS = {
        "A", "I", "US", "UK", "EU", "CEO", "CFO", "CTO", "COO",
        "IPO", "ETF", "SEC", "FDA", "FTC", "NYSE", "NASDAQ", "OTC",
        "OTCQB", "OTCQX", "TSX", "AMEX", "DD", "IMO", "YOLO", "FOMO",
        "EPS", "ATH", "ATL", "ITM", "OTM", "PM", "AM", "EST", "PST",
        "USD", "CAD", "EUR", "GBP", "THE", "AND", "FOR", "NEW", "INC",
        "LLC", "CORP", "AI", "EV", "TV", "PC", "IT", "PR", "IR",
        "CEO", "CTO", "CFO", "COO", "CMO", "CIO", "CISO",
    }

    def __init__(self, use_spacy: bool = True, model_name: str = "en_core_web_sm"):
        """Initialize entity extractor.

        Args:
            use_spacy: Whether to use spaCy NER
            model_name: spaCy model to load
        """
        self.use_spacy = use_spacy
        self.model_name = model_name
        self._nlp = None

    def _get_nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None and self.use_spacy:
            try:
                import spacy

                self._nlp = spacy.load(self.model_name)
                logger.info("Loaded spaCy model", model=self.model_name)
            except OSError:
                logger.warning(
                    "spaCy model not found, falling back to regex",
                    model=self.model_name,
                )
                self.use_spacy = False
            except ImportError:
                logger.warning("spaCy not installed, falling back to regex")
                self.use_spacy = False

        return self._nlp

    def extract(self, text: str) -> ExtractedEntities:
        """Extract entities from text.

        Args:
            text: Input text

        Returns:
            ExtractedEntities object
        """
        entities = ExtractedEntities()

        # Extract tickers (always use regex for these)
        entities.tickers = self._extract_tickers(text)

        # Extract money amounts
        entities.money = self._extract_money(text)

        # Extract percentages
        entities.percentages = self._extract_percentages(text)

        # Use spaCy for other entities if available
        nlp = self._get_nlp()
        if nlp:
            doc = nlp(text[:100000])  # Limit text length

            for ent in doc.ents:
                if ent.label_ == "ORG":
                    entities.companies.append(ent.text)
                elif ent.label_ == "PERSON":
                    entities.people.append(ent.text)
                elif ent.label_ == "DATE":
                    entities.dates.append(ent.text)
                elif ent.label_ == "GPE" or ent.label_ == "LOC":
                    entities.locations.append(ent.text)
                elif ent.label_ == "MONEY" and ent.text not in [m["raw"] for m in entities.money]:
                    entities.money.append({"raw": ent.text, "value": None, "currency": "USD"})

        # Deduplicate
        entities.companies = list(dict.fromkeys(entities.companies))[:20]
        entities.people = list(dict.fromkeys(entities.people))[:20]
        entities.dates = list(dict.fromkeys(entities.dates))[:10]
        entities.locations = list(dict.fromkeys(entities.locations))[:10]

        return entities

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text.

        Args:
            text: Input text

        Returns:
            List of ticker symbols
        """
        tickers = set()

        # Extract $TICKER patterns
        cashtag_matches = self.TICKER_PATTERN.findall(text)
        for match in cashtag_matches:
            ticker = match.upper()
            if ticker not in self.EXCLUDED_TICKERS:
                tickers.add(ticker)

        # Extract EXCHANGE:TICKER patterns
        exchange_matches = self.EXCHANGE_TICKER_PATTERN.findall(text)
        for match in exchange_matches:
            ticker = match.upper()
            if ticker not in self.EXCLUDED_TICKERS:
                tickers.add(ticker)

        return list(tickers)[:20]

    def _extract_money(self, text: str) -> list[dict[str, Any]]:
        """Extract monetary amounts from text.

        Args:
            text: Input text

        Returns:
            List of money dictionaries
        """
        matches = self.MONEY_PATTERN.findall(text)
        results = []

        for match in matches[:20]:
            value = self._parse_money_value(match)
            results.append({
                "raw": match,
                "value": value,
                "currency": "USD",
            })

        return results

    def _parse_money_value(self, text: str) -> float | None:
        """Parse a money string to numeric value.

        Args:
            text: Money string like "$1.5 million"

        Returns:
            Numeric value or None
        """
        try:
            # Remove $ and commas
            cleaned = text.replace("$", "").replace(",", "").strip()

            # Determine multiplier
            multiplier = 1
            cleaned_lower = cleaned.lower()

            if "billion" in cleaned_lower or cleaned_lower.endswith("b"):
                multiplier = 1_000_000_000
                cleaned = re.sub(r"[bB]illion|[bB]$", "", cleaned).strip()
            elif "million" in cleaned_lower or cleaned_lower.endswith("m"):
                multiplier = 1_000_000
                cleaned = re.sub(r"[mM]illion|[mM]$", "", cleaned).strip()
            elif "thousand" in cleaned_lower or cleaned_lower.endswith("k"):
                multiplier = 1_000
                cleaned = re.sub(r"[tT]housand|[kK]$", "", cleaned).strip()

            # Extract numeric part
            numeric_match = re.search(r"[\d.]+", cleaned)
            if numeric_match:
                return float(numeric_match.group()) * multiplier

        except (ValueError, AttributeError) as e:
            logger.debug("Failed to parse money value", raw=money_str, error=str(e))

        return None

    def _extract_percentages(self, text: str) -> list[str]:
        """Extract percentage values from text.

        Args:
            text: Input text

        Returns:
            List of percentage strings
        """
        matches = self.PERCENT_PATTERN.findall(text)
        return list(dict.fromkeys(matches))[:20]

    def extract_with_context(
        self,
        text: str,
        window_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Extract entities with surrounding context.

        Args:
            text: Input text
            window_size: Characters of context on each side

        Returns:
            List of entities with context
        """
        results = []
        entities = self.extract(text)

        # Get context for tickers
        for ticker in entities.tickers:
            pattern = re.compile(rf"\${re.escape(ticker)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                start = max(0, match.start() - window_size)
                end = min(len(text), match.end() + window_size)
                context = text[start:end]

                results.append({
                    "entity": ticker,
                    "type": "TICKER",
                    "context": context,
                    "position": match.start(),
                })

        # Get context for money
        for money in entities.money:
            pattern = re.compile(re.escape(money["raw"]))
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - window_size)
                end = min(len(text), match.end() + window_size)
                context = text[start:end]

                results.append({
                    "entity": money["raw"],
                    "type": "MONEY",
                    "value": money["value"],
                    "context": context,
                    "position": match.start(),
                })

        return results


def extract_entities(text: str, use_spacy: bool = True) -> ExtractedEntities:
    """Convenience function to extract entities.

    Args:
        text: Input text
        use_spacy: Whether to use spaCy

    Returns:
        ExtractedEntities object
    """
    extractor = EntityExtractor(use_spacy=use_spacy)
    return extractor.extract(text)
