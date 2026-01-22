"""Specialized parser for SEC Form 4 insider trading filings."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


@dataclass
class InsiderTransaction:
    """Single insider transaction from Form 4."""

    security_title: str
    transaction_date: str
    transaction_code: str
    transaction_type: str  # "BUY", "SELL", "GRANT", "EXERCISE"
    shares: float
    price_per_share: float | None
    total_value: float | None
    shares_owned_after: float
    ownership_type: str  # "D" for direct, "I" for indirect
    is_10b5_1: bool = False


@dataclass
class Form4Data:
    """Parsed Form 4 insider trading data."""

    issuer_cik: str
    issuer_name: str
    issuer_ticker: str
    insider_cik: str
    insider_name: str
    insider_title: str
    relationship: list[str]  # Director, Officer, 10% Owner
    filing_date: str
    transactions: list[InsiderTransaction] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)

    # Computed fields
    net_shares: float = 0.0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    signal: str = "NEUTRAL"  # "BULLISH", "BEARISH", "NEUTRAL"
    signal_strength: float = 0.0

    @property
    def is_buy(self) -> bool:
        """Check if net transaction is a buy."""
        return self.net_shares > 0

    @property
    def is_sell(self) -> bool:
        """Check if net transaction is a sell."""
        return self.net_shares < 0

    @property
    def is_c_suite(self) -> bool:
        """Check if insider is C-suite executive."""
        c_suite_titles = ["CEO", "CFO", "COO", "CTO", "President", "Chief"]
        return any(t in self.insider_title.upper() for t in c_suite_titles)


class Form4Parser:
    """Parser for SEC Form 4 insider trading filings."""

    # Transaction codes
    TRANSACTION_CODES = {
        "P": ("BUY", "Open market purchase"),
        "S": ("SELL", "Open market sale"),
        "A": ("GRANT", "Award or grant"),
        "D": ("DISPOSITION", "Disposition to issuer"),
        "F": ("TAX", "Payment of exercise price or tax"),
        "M": ("EXERCISE", "Exercise or conversion"),
        "C": ("CONVERSION", "Conversion of derivative"),
        "G": ("GIFT", "Gift"),
        "J": ("OTHER", "Other acquisition or disposition"),
        "K": ("EQUITY_SWAP", "Equity swap"),
        "U": ("TENDER", "Tender of shares"),
        "X": ("EXERCISE_OOM", "Exercise of out-of-money derivative"),
    }

    # High-signal transaction codes (actual market activity)
    HIGH_SIGNAL_CODES = {"P", "S"}

    def parse(self, content: str, metadata: dict[str, Any] | None = None) -> Form4Data | None:
        """Parse Form 4 content.

        Args:
            content: Raw Form 4 content (XML or HTML)
            metadata: Additional metadata

        Returns:
            Form4Data object or None if parsing fails
        """
        metadata = metadata or {}

        # Try XML parsing first (modern filings)
        if "<ownershipDocument" in content or "<?xml" in content:
            return self._parse_xml(content, metadata)

        # Fall back to HTML parsing (older filings)
        return self._parse_html(content, metadata)

    def _parse_xml(self, content: str, metadata: dict[str, Any]) -> Form4Data | None:
        """Parse XML-formatted Form 4."""
        try:
            # Clean XML content
            content = re.sub(r"<\?xml[^?]*\?>", "", content)
            content = re.sub(r"xmlns[^\"]*\"[^\"]*\"", "", content)

            root = ET.fromstring(content)

            # Extract issuer info
            issuer = root.find(".//issuer")
            issuer_cik = self._get_text(issuer, "issuerCik", "")
            issuer_name = self._get_text(issuer, "issuerName", "")
            issuer_ticker = self._get_text(issuer, "issuerTradingSymbol", "")

            # Extract reporting owner (insider) info
            owner = root.find(".//reportingOwner")
            owner_id = owner.find(".//reportingOwnerId") if owner else None
            owner_rel = owner.find(".//reportingOwnerRelationship") if owner else None

            insider_cik = self._get_text(owner_id, "rptOwnerCik", "")
            insider_name = self._get_text(owner_id, "rptOwnerName", "")

            # Extract relationship
            relationship = []
            insider_title = ""
            if owner_rel is not None:
                if self._get_text(owner_rel, "isDirector", "") == "1":
                    relationship.append("Director")
                if self._get_text(owner_rel, "isOfficer", "") == "1":
                    relationship.append("Officer")
                    insider_title = self._get_text(owner_rel, "officerTitle", "")
                if self._get_text(owner_rel, "isTenPercentOwner", "") == "1":
                    relationship.append("10% Owner")

            # Extract transactions
            transactions = []

            # Non-derivative transactions
            for trans in root.findall(".//nonDerivativeTransaction"):
                txn = self._parse_transaction(trans)
                if txn:
                    transactions.append(txn)

            # Derivative transactions (options, etc.)
            for trans in root.findall(".//derivativeTransaction"):
                txn = self._parse_derivative_transaction(trans)
                if txn:
                    transactions.append(txn)

            # Extract footnotes
            footnotes = []
            for fn in root.findall(".//footnote"):
                fn_text = fn.text or ""
                if fn_text:
                    footnotes.append(fn_text.strip())

            # Create Form4Data
            form4 = Form4Data(
                issuer_cik=issuer_cik,
                issuer_name=issuer_name,
                issuer_ticker=issuer_ticker.upper(),
                insider_cik=insider_cik,
                insider_name=insider_name,
                insider_title=insider_title,
                relationship=relationship,
                filing_date=metadata.get("filing_date", ""),
                transactions=transactions,
                footnotes=footnotes,
            )

            # Calculate signals
            self._calculate_signals(form4)

            return form4

        except ET.ParseError as e:
            logger.warning("Failed to parse Form 4 XML", error=str(e))
            return None

    def _parse_transaction(self, trans: ET.Element) -> InsiderTransaction | None:
        """Parse a non-derivative transaction element."""
        try:
            security_title = self._get_text(trans, ".//securityTitle/value", "")
            transaction_date = self._get_text(trans, ".//transactionDate/value", "")
            transaction_code = self._get_text(trans, ".//transactionCoding/transactionCode", "")

            # Get transaction amounts
            amounts = trans.find(".//transactionAmounts")
            shares_str = self._get_text(amounts, ".//transactionShares/value", "0")
            price_str = self._get_text(amounts, ".//transactionPricePerShare/value", "")
            acq_disp = self._get_text(amounts, ".//transactionAcquiredDisposedCode/value", "A")

            # Parse numeric values
            shares = float(shares_str) if shares_str else 0.0
            price = float(price_str) if price_str else None

            # Adjust sign based on acquisition/disposition
            if acq_disp == "D":
                shares = -abs(shares)

            # Get shares owned after
            post_amounts = trans.find(".//postTransactionAmounts")
            shares_after_str = self._get_text(
                post_amounts, ".//sharesOwnedFollowingTransaction/value", "0"
            )
            shares_after = float(shares_after_str) if shares_after_str else 0.0

            # Ownership type
            ownership = trans.find(".//ownershipNature")
            ownership_type = self._get_text(ownership, ".//directOrIndirectOwnership/value", "D")

            # Determine transaction type
            txn_type, _ = self.TRANSACTION_CODES.get(transaction_code, ("OTHER", ""))
            if acq_disp == "D" and transaction_code == "P":
                txn_type = "SELL"

            # Calculate total value
            total_value = abs(shares) * price if price else None

            return InsiderTransaction(
                security_title=security_title,
                transaction_date=transaction_date,
                transaction_code=transaction_code,
                transaction_type=txn_type,
                shares=shares,
                price_per_share=price,
                total_value=total_value,
                shares_owned_after=shares_after,
                ownership_type=ownership_type,
            )

        except Exception as e:
            logger.warning("Failed to parse transaction", error=str(e))
            return None

    def _parse_derivative_transaction(self, trans: ET.Element) -> InsiderTransaction | None:
        """Parse a derivative transaction element (options, etc.)."""
        try:
            security_title = self._get_text(trans, ".//securityTitle/value", "")
            transaction_date = self._get_text(trans, ".//transactionDate/value", "")
            transaction_code = self._get_text(trans, ".//transactionCoding/transactionCode", "")

            # Get amounts
            amounts = trans.find(".//transactionAmounts")
            shares_str = self._get_text(amounts, ".//transactionShares/value", "0")
            price_str = self._get_text(amounts, ".//transactionPricePerShare/value", "")
            acq_disp = self._get_text(amounts, ".//transactionAcquiredDisposedCode/value", "A")

            shares = float(shares_str) if shares_str else 0.0
            price = float(price_str) if price_str else None

            if acq_disp == "D":
                shares = -abs(shares)

            txn_type, _ = self.TRANSACTION_CODES.get(transaction_code, ("OTHER", ""))

            return InsiderTransaction(
                security_title=security_title,
                transaction_date=transaction_date,
                transaction_code=transaction_code,
                transaction_type=txn_type,
                shares=shares,
                price_per_share=price,
                total_value=abs(shares) * price if price else None,
                shares_owned_after=0.0,
                ownership_type="D",
            )

        except Exception as e:
            logger.warning("Failed to parse derivative transaction", error=str(e))
            return None

    def _parse_html(self, content: str, metadata: dict[str, Any]) -> Form4Data | None:
        """Parse HTML-formatted Form 4 (legacy format)."""
        # Simplified HTML parsing for older filings
        soup = BeautifulSoup(content, "lxml")

        # Extract basic info from page
        text = soup.get_text()

        # Try to extract key fields using regex
        ticker_match = re.search(r"Trading Symbol[:\s]+([A-Z]+)", text)
        issuer_ticker = ticker_match.group(1) if ticker_match else ""

        name_match = re.search(r"Name of Issuer[:\s]+(.+?)(?:\n|$)", text)
        issuer_name = name_match.group(1).strip() if name_match else ""

        return Form4Data(
            issuer_cik=metadata.get("cik", ""),
            issuer_name=issuer_name,
            issuer_ticker=issuer_ticker,
            insider_cik="",
            insider_name="",
            insider_title="",
            relationship=[],
            filing_date=metadata.get("filing_date", ""),
            transactions=[],
            footnotes=[],
        )

    def _get_text(self, element: ET.Element | None, path: str, default: str = "") -> str:
        """Get text content from XML element."""
        if element is None:
            return default

        if path.startswith(".//"):
            found = element.find(path)
        else:
            found = element.find(path)

        if found is not None and found.text:
            return found.text.strip()

        return default

    def _calculate_signals(self, form4: Form4Data) -> None:
        """Calculate trading signals from Form 4 data."""
        # Sum up transactions
        net_shares = 0.0
        total_buy = 0.0
        total_sell = 0.0

        for txn in form4.transactions:
            # Only count high-signal transactions (actual market activity)
            if txn.transaction_code in self.HIGH_SIGNAL_CODES:
                net_shares += txn.shares

                if txn.total_value:
                    if txn.shares > 0:
                        total_buy += txn.total_value
                    else:
                        total_sell += txn.total_value

        form4.net_shares = net_shares
        form4.total_buy_value = total_buy
        form4.total_sell_value = total_sell

        # Determine signal
        if net_shares > 0:
            form4.signal = "BULLISH"
            # Stronger signal for C-suite and larger amounts
            strength = min(1.0, total_buy / 1_000_000) if total_buy > 0 else 0.5
            if form4.is_c_suite:
                strength = min(1.0, strength * 1.5)
            form4.signal_strength = strength
        elif net_shares < 0:
            form4.signal = "BEARISH"
            # Weaker signal for sales (often routine)
            strength = min(0.7, total_sell / 2_000_000) if total_sell > 0 else 0.3
            form4.signal_strength = strength
        else:
            form4.signal = "NEUTRAL"
            form4.signal_strength = 0.0


def parse_form4(content: str, metadata: dict[str, Any] | None = None) -> Form4Data | None:
    """Convenience function to parse Form 4.

    Args:
        content: Raw Form 4 content
        metadata: Additional metadata

    Returns:
        Form4Data object or None
    """
    parser = Form4Parser()
    return parser.parse(content, metadata)
