"""XBRL data extractor for SEC financial filings."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FinancialFact:
    """Single XBRL financial fact."""

    concept: str
    label: str
    value: float | str
    unit: str
    period_start: str
    period_end: str
    instant: str | None = None
    decimals: int | None = None
    context_id: str = ""


@dataclass
class FinancialData:
    """Extracted XBRL financial data."""

    ticker: str
    cik: str
    company_name: str
    filing_type: str
    period_end: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None

    # Key metrics
    revenue: float | None = None
    net_income: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    stockholders_equity: float | None = None
    cash_and_equivalents: float | None = None
    operating_cash_flow: float | None = None

    # All extracted facts
    facts: list[FinancialFact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class XBRLExtractor:
    """Extractor for XBRL financial data from SEC filings."""

    # Common XBRL namespaces
    NAMESPACES = {
        "xbrli": "http://www.xbrl.org/2003/instance",
        "xbrldi": "http://xbrl.org/2006/xbrldi",
        "dei": "http://xbrl.sec.gov/dei/2023",
        "us-gaap": "http://fasb.org/us-gaap/2023",
        "srt": "http://fasb.org/srt/2023",
    }

    # Key financial concepts (US-GAAP taxonomy)
    KEY_CONCEPTS = {
        # Income Statement
        "Revenues": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        "NetIncomeLoss": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
        "EarningsPerShareBasic": ["EarningsPerShareBasic"],
        "EarningsPerShareDiluted": ["EarningsPerShareDiluted"],
        "GrossProfit": ["GrossProfit"],
        "OperatingIncomeLoss": ["OperatingIncomeLoss"],

        # Balance Sheet
        "Assets": ["Assets"],
        "Liabilities": ["Liabilities"],
        "StockholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "CashAndCashEquivalentsAtCarryingValue": ["CashAndCashEquivalentsAtCarryingValue", "Cash"],

        # Cash Flow
        "NetCashProvidedByUsedInOperatingActivities": ["NetCashProvidedByUsedInOperatingActivities"],
        "NetCashProvidedByUsedInInvestingActivities": ["NetCashProvidedByUsedInInvestingActivities"],
        "NetCashProvidedByUsedInFinancingActivities": ["NetCashProvidedByUsedInFinancingActivities"],
    }

    def extract(self, content: str, metadata: dict[str, Any] | None = None) -> FinancialData:
        """Extract financial data from XBRL content.

        Args:
            content: Raw XBRL content (XML)
            metadata: Additional metadata

        Returns:
            FinancialData object with extracted metrics
        """
        metadata = metadata or {}

        financial = FinancialData(
            ticker=metadata.get("ticker", ""),
            cik=metadata.get("cik", ""),
            company_name=metadata.get("company_name", ""),
            filing_type=metadata.get("filing_type", ""),
            period_end=metadata.get("period_end", ""),
            metadata=metadata,
        )

        try:
            # Parse XML
            root = self._parse_xml(content)
            if root is None:
                return financial

            # Extract contexts (periods)
            contexts = self._extract_contexts(root)

            # Extract units
            units = self._extract_units(root)

            # Extract all facts
            facts = self._extract_facts(root, contexts, units)
            financial.facts = facts

            # Map to key metrics
            self._map_key_metrics(financial, facts)

            # Extract document info
            self._extract_document_info(financial, facts)

        except Exception as e:
            logger.error("Failed to extract XBRL data", error=str(e))

        return financial

    def _parse_xml(self, content: str) -> ET.Element | None:
        """Parse XBRL XML content."""
        try:
            # Clean up content
            content = content.strip()

            # Handle different encodings
            if content.startswith("<?xml"):
                # Already has XML declaration
                pass
            else:
                content = '<?xml version="1.0"?>' + content

            return ET.fromstring(content.encode("utf-8"))

        except ET.ParseError as e:
            logger.warning("Failed to parse XBRL XML", error=str(e))
            return None

    def _extract_contexts(self, root: ET.Element) -> dict[str, dict[str, str]]:
        """Extract context definitions (reporting periods)."""
        contexts = {}

        for context in root.findall(".//{http://www.xbrl.org/2003/instance}context"):
            ctx_id = context.get("id", "")

            period = context.find("{http://www.xbrl.org/2003/instance}period")
            if period is None:
                continue

            ctx_data = {"id": ctx_id}

            # Instant period
            instant = period.find("{http://www.xbrl.org/2003/instance}instant")
            if instant is not None and instant.text:
                ctx_data["instant"] = instant.text

            # Duration period
            start = period.find("{http://www.xbrl.org/2003/instance}startDate")
            end = period.find("{http://www.xbrl.org/2003/instance}endDate")

            if start is not None and start.text:
                ctx_data["start"] = start.text
            if end is not None and end.text:
                ctx_data["end"] = end.text

            contexts[ctx_id] = ctx_data

        return contexts

    def _extract_units(self, root: ET.Element) -> dict[str, str]:
        """Extract unit definitions."""
        units = {}

        for unit in root.findall(".//{http://www.xbrl.org/2003/instance}unit"):
            unit_id = unit.get("id", "")

            measure = unit.find("{http://www.xbrl.org/2003/instance}measure")
            if measure is not None and measure.text:
                # Clean up measure (e.g., "iso4217:USD" -> "USD")
                measure_text = measure.text.split(":")[-1]
                units[unit_id] = measure_text

        return units

    def _extract_facts(
        self,
        root: ET.Element,
        contexts: dict[str, dict[str, str]],
        units: dict[str, str],
    ) -> list[FinancialFact]:
        """Extract all XBRL facts."""
        facts = []

        # Find all elements with contextRef attribute (these are facts)
        for elem in root.iter():
            context_ref = elem.get("contextRef")
            if not context_ref or context_ref not in contexts:
                continue

            # Get fact value
            if elem.text is None:
                continue

            value_text = elem.text.strip()
            if not value_text:
                continue

            # Get concept name (local part of tag)
            concept = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            # Get context info
            ctx = contexts.get(context_ref, {})

            # Get unit
            unit_ref = elem.get("unitRef", "")
            unit = units.get(unit_ref, "")

            # Get decimals
            decimals_str = elem.get("decimals", "")
            decimals = int(decimals_str) if decimals_str.lstrip("-").isdigit() else None

            # Parse value
            try:
                value: float | str = float(value_text.replace(",", ""))
            except ValueError:
                value = value_text

            fact = FinancialFact(
                concept=concept,
                label=self._concept_to_label(concept),
                value=value,
                unit=unit,
                period_start=ctx.get("start", ""),
                period_end=ctx.get("end", ctx.get("instant", "")),
                instant=ctx.get("instant"),
                decimals=decimals,
                context_id=context_ref,
            )

            facts.append(fact)

        return facts

    def _concept_to_label(self, concept: str) -> str:
        """Convert camelCase concept name to readable label."""
        # Add spaces before capitals
        label = re.sub(r"([A-Z])", r" \1", concept)
        return label.strip()

    def _map_key_metrics(self, financial: FinancialData, facts: list[FinancialFact]) -> None:
        """Map extracted facts to key financial metrics."""
        # Group facts by concept
        facts_by_concept: dict[str, list[FinancialFact]] = {}
        for fact in facts:
            if fact.concept not in facts_by_concept:
                facts_by_concept[fact.concept] = []
            facts_by_concept[fact.concept].append(fact)

        # Map each key metric
        for metric_name, concept_names in self.KEY_CONCEPTS.items():
            for concept in concept_names:
                if concept in facts_by_concept:
                    # Get most recent fact (by period end date)
                    metric_facts = facts_by_concept[concept]
                    metric_facts.sort(key=lambda f: f.period_end or "", reverse=True)

                    if metric_facts:
                        value = metric_facts[0].value
                        if isinstance(value, (int, float)):
                            self._set_metric(financial, metric_name, value)
                            break

    def _set_metric(self, financial: FinancialData, metric_name: str, value: float) -> None:
        """Set a metric value on the FinancialData object."""
        mapping = {
            "Revenues": "revenue",
            "NetIncomeLoss": "net_income",
            "EarningsPerShareBasic": "eps_basic",
            "EarningsPerShareDiluted": "eps_diluted",
            "Assets": "total_assets",
            "Liabilities": "total_liabilities",
            "StockholdersEquity": "stockholders_equity",
            "CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
            "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
        }

        attr_name = mapping.get(metric_name)
        if attr_name:
            setattr(financial, attr_name, value)

    def _extract_document_info(self, financial: FinancialData, facts: list[FinancialFact]) -> None:
        """Extract document-level information."""
        # Look for DEI (Document and Entity Information) facts
        for fact in facts:
            if fact.concept == "DocumentFiscalYearFocus":
                try:
                    financial.fiscal_year = int(fact.value)
                except (ValueError, TypeError):
                    pass
            elif fact.concept == "DocumentFiscalPeriodFocus":
                period = str(fact.value)
                if period == "Q1":
                    financial.fiscal_quarter = 1
                elif period == "Q2":
                    financial.fiscal_quarter = 2
                elif period == "Q3":
                    financial.fiscal_quarter = 3
                elif period in ("Q4", "FY"):
                    financial.fiscal_quarter = 4
            elif fact.concept == "DocumentPeriodEndDate":
                financial.period_end = str(fact.value)


def extract_xbrl(content: str, metadata: dict[str, Any] | None = None) -> FinancialData:
    """Convenience function to extract XBRL data.

    Args:
        content: Raw XBRL content
        metadata: Additional metadata

    Returns:
        FinancialData object
    """
    extractor = XBRLExtractor()
    return extractor.extract(content, metadata)
