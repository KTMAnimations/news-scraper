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
    # Extracted sections (signature, risk_factors, forward_looking_statements, etc.)
    extracted_sections: dict[str, str] = field(default_factory=dict)


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

    # S-1 IPO-related keywords
    IPO_KEYWORDS = {
        "initial public offering",
        "ipo",
        "proposed maximum aggregate offering price",
        "shares being offered",
        "underwriters",
        "underwriting agreement",
        "prospectus",
        "registration statement",
    }

    # Key S-1 sections to extract
    S1_SECTIONS = {
        "prospectus_summary": ["prospectus summary", "summary"],
        "risk_factors": ["risk factors"],
        "use_of_proceeds": ["use of proceeds"],
        "dividend_policy": ["dividend policy"],
        "capitalization": ["capitalization"],
        "dilution": ["dilution"],
        "business": ["business", "description of business"],
        "management": ["management", "directors and executive officers"],
        "underwriting": ["underwriting", "underwriters"],
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
        elif filing_type == "S-1" or filing_type.startswith("S-1"):
            self._parse_s1(content, filing)
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

        # Extract key sections (signature, exhibits, risk factors)
        filing.extracted_sections = self.extract_sections(content)

        # Extract exhibits list and add to filing
        if "exhibits" in filing.extracted_sections:
            exhibits_list = filing.extracted_sections.pop("exhibits")
            if isinstance(exhibits_list, list):
                filing.exhibits = exhibits_list

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

    def _parse_s1(self, content: str, filing: FilingData) -> None:
        """Parse Form S-1 (IPO registration) content.

        Extracts key IPO information including:
        - Offering amount
        - Share price range
        - Shares being offered
        - Underwriters
        - Use of proceeds
        - Risk factors summary
        """
        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        filing.full_text = text[:100000]

        # Extract IPO-specific data
        ipo_data = {
            "is_ipo": True,
            "offering_amount": None,
            "price_range": None,
            "shares_offered": None,
            "underwriters": [],
            "use_of_proceeds": "",
            "risk_factors_summary": "",
            "sections_found": [],
        }

        # Extract proposed offering amount
        offering_patterns = [
            r"proposed maximum aggregate offering price[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
            r"aggregate offering price[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
            r"total offering[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
            r"raise[s]?\s+(?:up to\s+)?\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
        ]

        for pattern in offering_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    # Check for multiplier in the original match
                    full_match = match.group(0).lower()
                    if "billion" in full_match:
                        amount *= 1_000_000_000
                    elif "million" in full_match:
                        amount *= 1_000_000
                    ipo_data["offering_amount"] = amount
                    break
                except ValueError:
                    pass

        # Extract price range (e.g., "$15.00 to $17.00 per share")
        price_range_patterns = [
            r"\$([\d.]+)\s*(?:to|-)\s*\$([\d.]+)\s*per\s*share",
            r"price range of \$([\d.]+)\s*(?:to|-)\s*\$([\d.]+)",
            r"initial public offering price.*?\$([\d.]+)\s*(?:to|-)\s*\$([\d.]+)",
        ]

        for pattern in price_range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    low_price = float(match.group(1))
                    high_price = float(match.group(2))
                    ipo_data["price_range"] = {
                        "low": low_price,
                        "high": high_price,
                        "midpoint": (low_price + high_price) / 2,
                    }
                    break
                except ValueError:
                    pass

        # Extract number of shares being offered
        shares_patterns = [
            r"offering\s+([\d,]+)\s*shares",
            r"([\d,]+)\s*shares\s*(?:of\s+)?(?:common\s+stock\s+)?(?:are\s+)?being\s+offered",
            r"sell\s+([\d,]+)\s*shares",
            r"([\d,]+)\s*shares\s*at",
        ]

        for pattern in shares_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    shares = int(match.group(1).replace(",", ""))
                    ipo_data["shares_offered"] = shares
                    break
                except ValueError:
                    pass

        # Extract underwriters
        underwriter_patterns = [
            r"(?:lead\s+)?(?:book-running\s+)?(?:managing\s+)?underwriter[s]?[:\s]+([A-Z][A-Za-z\s&,]+?)(?:\.|,\s*(?:Inc|LLC|LP)|$)",
            r"(Goldman Sachs|Morgan Stanley|JPMorgan|J\.P\. Morgan|BofA Securities|Citigroup|Credit Suisse|Deutsche Bank|UBS|Barclays|Wells Fargo)",
        ]

        underwriters = set()
        for pattern in underwriter_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                underwriter = match.strip()
                if underwriter and len(underwriter) > 2 and len(underwriter) < 100:
                    underwriters.add(underwriter)

        ipo_data["underwriters"] = list(underwriters)[:10]

        # Find and extract key sections
        for section_name, keywords in self.S1_SECTIONS.items():
            for keyword in keywords:
                # Look for section header
                section_pattern = rf"(?:^|\n)\s*{re.escape(keyword)}[:\s]*\n"
                match = re.search(section_pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    ipo_data["sections_found"].append(section_name)

                    # Extract section content (up to next section or 2000 chars)
                    start_idx = match.end()
                    section_text = text[start_idx:start_idx + 3000]

                    if section_name == "risk_factors":
                        # Get first 500 chars of risk factors as summary
                        ipo_data["risk_factors_summary"] = section_text[:500].strip()
                    elif section_name == "use_of_proceeds":
                        ipo_data["use_of_proceeds"] = section_text[:1000].strip()

                    break

        # Generate headline
        company_name = filing.company_name or "Company"
        if ipo_data["offering_amount"]:
            amount_str = self._format_money(ipo_data["offering_amount"])
            filing.headline = f"S-1 IPO Registration: {company_name} - {amount_str} Offering"
        else:
            filing.headline = f"S-1 IPO Registration: {company_name}"

        # Generate summary
        summary_parts = [f"{company_name} filed an S-1 registration statement."]

        if ipo_data["shares_offered"]:
            summary_parts.append(f"Offering {ipo_data['shares_offered']:,} shares.")

        if ipo_data["price_range"]:
            summary_parts.append(
                f"Price range: ${ipo_data['price_range']['low']:.2f} - ${ipo_data['price_range']['high']:.2f} per share."
            )

        if ipo_data["offering_amount"]:
            summary_parts.append(f"Total offering: {self._format_money(ipo_data['offering_amount'])}.")

        if ipo_data["underwriters"]:
            summary_parts.append(f"Lead underwriter(s): {', '.join(ipo_data['underwriters'][:3])}.")

        filing.summary = " ".join(summary_parts)

        # Store IPO data in metadata
        filing.metadata["ipo_data"] = ipo_data
        filing.metadata["is_ipo"] = True

    def _format_money(self, amount: float) -> str:
        """Format a monetary amount for display.

        Args:
            amount: Dollar amount

        Returns:
            Formatted string (e.g., "$150M", "$1.5B")
        """
        if amount >= 1_000_000_000:
            return f"${amount / 1_000_000_000:.1f}B"
        elif amount >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.1f}K"
        else:
            return f"${amount:,.2f}"

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

    def extract_sections(self, content: str) -> dict[str, str]:
        """Extract key sections from filing content.

        Extracts:
        - Signature block
        - Exhibits list
        - Risk factors
        - Forward-looking statements

        Args:
            content: Raw filing content (HTML or plain text)

        Returns:
            Dictionary of section_name -> section_content
        """
        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(separator="\n", strip=True)

        sections = {}

        # Extract signature block
        signature = self._extract_signature_block(text)
        if signature:
            sections["signature"] = signature

        # Extract exhibits
        exhibits = self._extract_exhibits(text, soup)
        if exhibits:
            sections["exhibits"] = exhibits

        # Extract risk factors
        risk_factors = self._extract_risk_factors(text)
        if risk_factors:
            sections["risk_factors"] = risk_factors

        # Extract forward-looking statements
        forward_looking = self._extract_forward_looking(text)
        if forward_looking:
            sections["forward_looking_statements"] = forward_looking

        return sections

    def _extract_signature_block(self, text: str) -> str | None:
        """Extract the signature block from a filing.

        Args:
            text: Plain text content

        Returns:
            Signature block text or None
        """
        # Common signature patterns
        signature_patterns = [
            r"(?:SIGNATURE[S]?)\s*(?:\n|$)([\s\S]{100,2000}?)(?:EXHIBIT|$)",
            r"Pursuant to the requirements[^.]*signed[^.]*\.([\s\S]{100,2000}?)(?:EXHIBIT|$)",
            r"IN WITNESS WHEREOF([\s\S]{100,2000}?)(?:EXHIBIT|$)",
            r"(?:By:|/s/)\s*([A-Za-z\s,\.]+)(?:\n|$)",
        ]

        for pattern in signature_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                signature_text = match.group(1).strip()
                # Clean up excessive whitespace
                signature_text = re.sub(r'\n{3,}', '\n\n', signature_text)
                if len(signature_text) > 20:
                    return signature_text[:2000]

        return None

    def _extract_exhibits(self, text: str, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract list of exhibits from filing.

        Args:
            text: Plain text content
            soup: BeautifulSoup parsed HTML

        Returns:
            List of exhibit dictionaries with number, description, and optional link
        """
        exhibits = []

        # Pattern for exhibit entries (e.g., "Exhibit 10.1 - Employment Agreement")
        exhibit_patterns = [
            r"Exhibit\s+(\d+(?:\.\d+)?)\s*[-–]\s*([^\n]{5,200})",
            r"Ex(?:h)?\.?\s*(\d+(?:\.\d+)?)\s*[-–]?\s*([^\n]{5,200})",
            r"(\d+\.\d+)\s+([A-Z][^\n]{5,200})",  # Table format
        ]

        seen_exhibits = set()

        for pattern in exhibit_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                exhibit_num = match[0].strip()
                description = match[1].strip()

                # Skip if already seen or description looks invalid
                if exhibit_num in seen_exhibits:
                    continue
                if len(description) < 5 or description.isdigit():
                    continue

                seen_exhibits.add(exhibit_num)
                exhibits.append({
                    "number": exhibit_num,
                    "description": description[:200],
                })

                if len(exhibits) >= 50:  # Limit to prevent noise
                    break

            if len(exhibits) >= 50:
                break

        # Also look for exhibit links in HTML
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            link_text = link.get_text(strip=True)

            if "exhibit" in href.lower() or "ex" in href.lower():
                # Try to extract exhibit number from link
                num_match = re.search(r"ex(?:hibit)?[\s_-]*(\d+(?:\.\d+)?)", href, re.IGNORECASE)
                if num_match:
                    exhibit_num = num_match.group(1)
                    if exhibit_num not in seen_exhibits:
                        seen_exhibits.add(exhibit_num)
                        exhibits.append({
                            "number": exhibit_num,
                            "description": link_text[:200] if link_text else "Exhibit Document",
                            "link": href,
                        })

        return exhibits

    def _extract_risk_factors(self, text: str) -> str | None:
        """Extract risk factors section from filing.

        Args:
            text: Plain text content

        Returns:
            Risk factors text or None
        """
        # Find the risk factors section
        risk_patterns = [
            r"(?:ITEM\s+1A[.:]?\s*)?RISK\s+FACTORS\s*\n([\s\S]{500,}?)(?:ITEM\s+\d|UNRESOLVED\s+STAFF|PROPERTIES|$)",
            r"RISK\s+FACTORS\s*\n([\s\S]{500,}?)(?:\n\s*[A-Z]{4,}|\n\s*ITEM\s+\d|$)",
        ]

        for pattern in risk_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                risk_text = match.group(1).strip()
                # Clean up formatting
                risk_text = re.sub(r'\n{3,}', '\n\n', risk_text)
                # Return first 10000 chars (risk factors can be very long)
                return risk_text[:10000]

        return None

    def _extract_forward_looking(self, text: str) -> str | None:
        """Extract forward-looking statements disclaimer.

        Args:
            text: Plain text content

        Returns:
            Forward-looking statements text or None
        """
        patterns = [
            r"(?:FORWARD-LOOKING\s+STATEMENTS?|SAFE\s+HARBOR)\s*\n?([\s\S]{100,3000}?)(?:\n\s*[A-Z]{4,}|\n\s*ITEM|$)",
            r"(?:This\s+)?(?:press\s+release|document|report)\s+contains\s+forward-looking\s+statements?([\s\S]{100,2000}?)(?:\n\s*[A-Z]{4,}|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fls_text = match.group(1).strip()
                if len(fls_text) > 50:
                    return fls_text[:3000]

        return None

    def extract_key_content(self, content: str, filing_type: str) -> dict[str, Any]:
        """Extract key content based on filing type.

        This is a unified method that extracts the most relevant content
        for each filing type.

        Args:
            content: Raw filing content
            filing_type: Type of filing

        Returns:
            Dictionary with extracted key content
        """
        result = {
            "sections": self.extract_sections(content),
            "filing_type": filing_type,
        }

        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(separator=" ", strip=True)

        # Add filing-type specific extractions
        if filing_type == "8-K":
            # Extract 8-K items
            items_found = []
            for item_code in self.FORM_8K_ITEMS:
                pattern = rf"Item\s*{re.escape(item_code)}"
                if re.search(pattern, text, re.IGNORECASE):
                    items_found.append({
                        "code": item_code,
                        "description": self.FORM_8K_ITEMS[item_code],
                    })
            result["items"] = items_found
            result["is_high_signal"] = any(i["code"] in self.HIGH_SIGNAL_ITEMS for i in items_found)

        elif filing_type == "S-1" or filing_type.startswith("S-1"):
            # Extract IPO-specific content
            result["ipo_keywords_found"] = [
                kw for kw in self.IPO_KEYWORDS
                if kw.lower() in text.lower()
            ]

        # Extract any tables (useful for financial data)
        tables = self._extract_tables(soup)
        if tables:
            result["tables"] = tables[:5]  # Limit to first 5 tables

        return result

    def _extract_tables(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract tables from HTML content.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of table dictionaries with headers and rows
        """
        tables = []

        for table in soup.find_all("table")[:10]:  # Limit to first 10 tables
            rows = table.find_all("tr")
            if not rows:
                continue

            table_data = {
                "headers": [],
                "rows": [],
            }

            # Extract headers from first row or th elements
            header_row = rows[0]
            headers = header_row.find_all(["th", "td"])
            table_data["headers"] = [h.get_text(strip=True)[:100] for h in headers]

            # Extract data rows
            for row in rows[1:20]:  # Limit rows
                cells = row.find_all(["td", "th"])
                row_data = [c.get_text(strip=True)[:100] for c in cells]
                if any(row_data):  # Skip empty rows
                    table_data["rows"].append(row_data)

            if table_data["rows"]:
                tables.append(table_data)

        return tables


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
