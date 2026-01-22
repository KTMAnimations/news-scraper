"""SEC filing content parser for extracting structured data."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


@dataclass
class FilingData:
    """Structured filing data extracted from SEC document."""

    filing_type: str
    company_name: str
    cik: str
    filing_date: str
    accession_number: str
    headline: str = ""
    summary: str = ""
    full_text: str = ""
    items: list[str] = field(default_factory=list)
    exhibits: list[dict[str, str]] = field(default_factory=list)
    monetary_values: list[dict[str, Any]] = field(default_factory=list)
    mentioned_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class FilingParser:
    """Parser for SEC EDGAR filing documents."""

    # 8-K item codes and descriptions
    FORM_8K_ITEMS = {
        "1.01": "Entry into a Material Definitive Agreement",
        "1.02": "Termination of a Material Definitive Agreement",
        "1.03": "Bankruptcy or Receivership",
        "1.04": "Mine Safety",
        "2.01": "Completion of Acquisition or Disposition of Assets",
        "2.02": "Results of Operations and Financial Condition",
        "2.03": "Creation of a Direct Financial Obligation",
        "2.04": "Triggering Events That Accelerate Obligation",
        "2.05": "Costs Associated with Exit or Disposal Activities",
        "2.06": "Material Impairments",
        "3.01": "Notice of Delisting",
        "3.02": "Unregistered Sales of Equity Securities",
        "3.03": "Material Modification to Rights of Security Holders",
        "4.01": "Changes in Registrant's Certifying Accountant",
        "4.02": "Non-Reliance on Previously Issued Financial Statements",
        "5.01": "Changes in Control of Registrant",
        "5.02": "Departure of Directors or Certain Officers",
        "5.03": "Amendments to Articles of Incorporation or Bylaws",
        "5.04": "Temporary Suspension of Trading Under Registrant's Plans",
        "5.05": "Amendment to Registrant's Code of Ethics",
        "5.06": "Change in Shell Company Status",
        "5.07": "Submission of Matters to a Vote of Security Holders",
        "5.08": "Shareholder Nominations",
        "6.01": "ABS Informational and Computational Material",
        "6.02": "Change of Servicer or Trustee",
        "6.03": "Change in Credit Enhancement",
        "6.04": "Failure to Make a Required Distribution",
        "6.05": "Securities Act Updating Disclosure",
        "7.01": "Regulation FD Disclosure",
        "8.01": "Other Events",
        "9.01": "Financial Statements and Exhibits",
    }

    # High-signal 8-K items for trading
    HIGH_SIGNAL_ITEMS = {
        "1.01",  # Material agreements
        "1.03",  # Bankruptcy
        "2.01",  # Acquisitions
        "2.02",  # Results of operations
        "3.01",  # Delisting
        "5.01",  # Change in control
        "5.02",  # Officer departures
    }

    def __init__(self):
        """Initialize filing parser."""
        self._money_pattern = re.compile(
            r"\$[\d,]+(?:\.\d{2})?\s*(?:million|billion|thousand)?",
            re.IGNORECASE,
        )
        self._percentage_pattern = re.compile(r"[\d.]+%")

    def parse(self, content: str, filing_type: str, metadata: dict[str, Any] | None = None) -> FilingData:
        """Parse SEC filing content.

        Args:
            content: Raw filing content (HTML or plain text)
            filing_type: Type of filing (8-K, 10-Q, etc.)
            metadata: Additional metadata about the filing

        Returns:
            FilingData object with extracted information
        """
        metadata = metadata or {}

        # Initialize filing data
        filing = FilingData(
            filing_type=filing_type,
            company_name=metadata.get("company_name", ""),
            cik=metadata.get("cik", ""),
            filing_date=metadata.get("filing_date", ""),
            accession_number=metadata.get("accession_number", ""),
            metadata=metadata,
        )

        # Parse based on filing type
        if filing_type == "8-K":
            self._parse_8k(content, filing)
        elif filing_type in ("10-Q", "10-K"):
            self._parse_periodic_report(content, filing)
        elif filing_type == "4":
            # Form 4 has specialized parser for insider trading
            from .form4_parser import Form4Parser
            form4_parser = Form4Parser()
            form4_data = form4_parser.parse(content, metadata)
            if form4_data:
                filing.metadata["form4_data"] = {
                    "issuer_ticker": form4_data.issuer_ticker,
                    "insider_name": form4_data.insider_name,
                    "insider_title": form4_data.insider_title,
                    "relationship": form4_data.relationship,
                    "net_shares": form4_data.net_shares,
                    "total_buy_value": form4_data.total_buy_value,
                    "total_sell_value": form4_data.total_sell_value,
                    "signal": form4_data.signal,
                    "signal_strength": form4_data.signal_strength,
                    "is_c_suite": form4_data.is_c_suite,
                    "transactions": [
                        {
                            "type": t.transaction_type,
                            "shares": t.shares,
                            "price": t.price_per_share,
                            "value": t.total_value,
                        }
                        for t in form4_data.transactions
                    ],
                }
                # Generate headline from Form 4 data
                if form4_data.signal == "BULLISH":
                    filing.headline = f"Insider Buy: {form4_data.insider_name} ({form4_data.insider_title})"
                elif form4_data.signal == "BEARISH":
                    filing.headline = f"Insider Sell: {form4_data.insider_name} ({form4_data.insider_title})"
                else:
                    filing.headline = f"Form 4: {form4_data.insider_name} filing"
                filing.summary = f"{form4_data.insider_name} ({', '.join(form4_data.relationship)}) reported {len(form4_data.transactions)} transaction(s). Net shares: {form4_data.net_shares:,.0f}"
            else:
                # Fall back to generic parsing if Form 4 parser fails
                self._parse_generic(content, filing)
        else:
            self._parse_generic(content, filing)

        # Extract common elements
        self._extract_monetary_values(content, filing)
        self._extract_entities(content, filing)

        return filing

    def _parse_8k(self, content: str, filing: FilingData) -> None:
        """Parse Form 8-K content."""
        soup = BeautifulSoup(content, "lxml")

        # Extract text content
        text = soup.get_text(separator=" ", strip=True)
        filing.full_text = text[:50000]  # Limit size

        # Find reported items
        items_found = []
        for item_code in self.FORM_8K_ITEMS:
            pattern = rf"Item\s*{re.escape(item_code)}"
            if re.search(pattern, text, re.IGNORECASE):
                items_found.append(item_code)

        filing.items = items_found

        # Generate headline based on items
        if items_found:
            primary_item = items_found[0]
            item_desc = self.FORM_8K_ITEMS.get(primary_item, "")
            filing.headline = f"8-K: {item_desc}"
        else:
            filing.headline = "8-K Filing"

        # Check for high-signal items
        high_signal = [i for i in items_found if i in self.HIGH_SIGNAL_ITEMS]
        if high_signal:
            filing.metadata["high_signal"] = True
            filing.metadata["high_signal_items"] = high_signal

        # Extract summary (first few paragraphs)
        paragraphs = soup.find_all("p")
        summary_parts = []
        for p in paragraphs[:5]:
            p_text = p.get_text(strip=True)
            if len(p_text) > 50:
                summary_parts.append(p_text)

        filing.summary = " ".join(summary_parts)[:2000]

    def _parse_periodic_report(self, content: str, filing: FilingData) -> None:
        """Parse 10-Q/10-K periodic reports."""
        soup = BeautifulSoup(content, "lxml")

        text = soup.get_text(separator=" ", strip=True)
        filing.full_text = text[:100000]

        # Generate headline
        filing.headline = f"{filing.filing_type} Quarterly/Annual Report"

        # Look for key sections
        sections = []
        section_patterns = [
            r"Management.s Discussion and Analysis",
            r"Risk Factors",
            r"Financial Statements",
            r"Legal Proceedings",
        ]

        for pattern in section_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                sections.append(pattern)

        filing.metadata["sections_found"] = sections

    def _parse_generic(self, content: str, filing: FilingData) -> None:
        """Parse generic filing content."""
        soup = BeautifulSoup(content, "lxml")

        text = soup.get_text(separator=" ", strip=True)
        filing.full_text = text[:50000]

        # Basic headline
        filing.headline = f"{filing.filing_type} Filing"

        # Extract first paragraph as summary
        paragraphs = soup.find_all("p")
        for p in paragraphs[:3]:
            p_text = p.get_text(strip=True)
            if len(p_text) > 100:
                filing.summary = p_text[:1000]
                break

    def _extract_monetary_values(self, content: str, filing: FilingData) -> None:
        """Extract monetary values from content."""
        matches = self._money_pattern.findall(content)

        for match in matches[:20]:  # Limit to prevent noise
            # Parse the value
            cleaned = match.replace("$", "").replace(",", "").strip()

            multiplier = 1
            if "billion" in match.lower():
                multiplier = 1_000_000_000
            elif "million" in match.lower():
                multiplier = 1_000_000
            elif "thousand" in match.lower():
                multiplier = 1_000

            try:
                # Extract numeric part
                numeric = re.search(r"[\d.]+", cleaned)
                if numeric:
                    value = float(numeric.group()) * multiplier
                    filing.monetary_values.append({
                        "raw": match,
                        "value": value,
                        "currency": "USD",
                    })
            except ValueError as e:
                logger.debug("Failed to parse monetary value", raw=match, error=str(e))

    def _extract_entities(self, content: str, filing: FilingData) -> None:
        """Extract mentioned company/entity names."""
        # This is a simplified extraction
        # Full implementation would use spaCy NER

        # Common patterns for company mentions
        company_patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc|Corp|Ltd|LLC|Co)\.?))",
        ]

        entities = set()
        for pattern in company_patterns:
            matches = re.findall(pattern, content[:10000])
            for match in matches[:50]:
                if len(match) > 3 and len(match) < 100:
                    entities.add(match)

        filing.mentioned_entities = list(entities)[:20]


def parse_filing(content: str, filing_type: str, metadata: dict[str, Any] | None = None) -> FilingData:
    """Convenience function to parse a filing.

    Args:
        content: Raw filing content
        filing_type: Type of filing
        metadata: Additional metadata

    Returns:
        FilingData object
    """
    parser = FilingParser()
    return parser.parse(content, filing_type, metadata)
