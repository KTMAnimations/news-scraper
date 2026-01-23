"""Industry/Sector classification using GICS (Global Industry Classification Standard).

GICS is a four-tiered hierarchical classification system:
1. Sector (11 sectors)
2. Industry Group (25 groups)
3. Industry (74 industries)
4. Sub-Industry (163 sub-industries)

This module provides classification based on ticker lookup and keyword matching.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GICSSector(str, Enum):
    """GICS Sector codes (top level)."""

    ENERGY = "10"
    MATERIALS = "15"
    INDUSTRIALS = "20"
    CONSUMER_DISCRETIONARY = "25"
    CONSUMER_STAPLES = "30"
    HEALTH_CARE = "35"
    FINANCIALS = "40"
    INFORMATION_TECHNOLOGY = "45"
    COMMUNICATION_SERVICES = "50"
    UTILITIES = "55"
    REAL_ESTATE = "60"


# Sector names for display
SECTOR_NAMES = {
    GICSSector.ENERGY: "Energy",
    GICSSector.MATERIALS: "Materials",
    GICSSector.INDUSTRIALS: "Industrials",
    GICSSector.CONSUMER_DISCRETIONARY: "Consumer Discretionary",
    GICSSector.CONSUMER_STAPLES: "Consumer Staples",
    GICSSector.HEALTH_CARE: "Health Care",
    GICSSector.FINANCIALS: "Financials",
    GICSSector.INFORMATION_TECHNOLOGY: "Information Technology",
    GICSSector.COMMUNICATION_SERVICES: "Communication Services",
    GICSSector.UTILITIES: "Utilities",
    GICSSector.REAL_ESTATE: "Real Estate",
}


# GICS Industry Group codes (second level)
INDUSTRY_GROUPS = {
    # Energy
    "1010": {"name": "Energy", "sector": GICSSector.ENERGY},

    # Materials
    "1510": {"name": "Materials", "sector": GICSSector.MATERIALS},

    # Industrials
    "2010": {"name": "Capital Goods", "sector": GICSSector.INDUSTRIALS},
    "2020": {"name": "Commercial & Professional Services", "sector": GICSSector.INDUSTRIALS},
    "2030": {"name": "Transportation", "sector": GICSSector.INDUSTRIALS},

    # Consumer Discretionary
    "2510": {"name": "Automobiles & Components", "sector": GICSSector.CONSUMER_DISCRETIONARY},
    "2520": {"name": "Consumer Durables & Apparel", "sector": GICSSector.CONSUMER_DISCRETIONARY},
    "2530": {"name": "Consumer Services", "sector": GICSSector.CONSUMER_DISCRETIONARY},
    "2550": {"name": "Consumer Discretionary Distribution & Retail", "sector": GICSSector.CONSUMER_DISCRETIONARY},

    # Consumer Staples
    "3010": {"name": "Consumer Staples Distribution & Retail", "sector": GICSSector.CONSUMER_STAPLES},
    "3020": {"name": "Food, Beverage & Tobacco", "sector": GICSSector.CONSUMER_STAPLES},
    "3030": {"name": "Household & Personal Products", "sector": GICSSector.CONSUMER_STAPLES},

    # Health Care
    "3510": {"name": "Health Care Equipment & Services", "sector": GICSSector.HEALTH_CARE},
    "3520": {"name": "Pharmaceuticals, Biotechnology & Life Sciences", "sector": GICSSector.HEALTH_CARE},

    # Financials
    "4010": {"name": "Banks", "sector": GICSSector.FINANCIALS},
    "4020": {"name": "Financial Services", "sector": GICSSector.FINANCIALS},
    "4030": {"name": "Insurance", "sector": GICSSector.FINANCIALS},

    # Information Technology
    "4510": {"name": "Software & Services", "sector": GICSSector.INFORMATION_TECHNOLOGY},
    "4520": {"name": "Technology Hardware & Equipment", "sector": GICSSector.INFORMATION_TECHNOLOGY},
    "4530": {"name": "Semiconductors & Semiconductor Equipment", "sector": GICSSector.INFORMATION_TECHNOLOGY},

    # Communication Services
    "5010": {"name": "Telecommunication Services", "sector": GICSSector.COMMUNICATION_SERVICES},
    "5020": {"name": "Media & Entertainment", "sector": GICSSector.COMMUNICATION_SERVICES},

    # Utilities
    "5510": {"name": "Utilities", "sector": GICSSector.UTILITIES},

    # Real Estate
    "6010": {"name": "Equity Real Estate Investment Trusts (REITs)", "sector": GICSSector.REAL_ESTATE},
    "6020": {"name": "Real Estate Management & Development", "sector": GICSSector.REAL_ESTATE},
}


@dataclass
class IndustryClassification:
    """Industry classification result."""

    sector: GICSSector
    sector_name: str
    industry_group: str | None
    industry_group_name: str | None
    confidence: float
    classification_method: str  # "ticker_lookup", "keyword_match", "default"
    keywords_matched: list[str] | None = None


class IndustryClassifier:
    """Classify events/companies by industry using GICS codes."""

    # Major ticker -> sector mappings for well-known companies
    TICKER_SECTOR_MAP = {
        # Energy
        "XOM": GICSSector.ENERGY, "CVX": GICSSector.ENERGY, "COP": GICSSector.ENERGY,
        "SLB": GICSSector.ENERGY, "OXY": GICSSector.ENERGY, "MPC": GICSSector.ENERGY,
        "VLO": GICSSector.ENERGY, "PSX": GICSSector.ENERGY, "EOG": GICSSector.ENERGY,
        "PXD": GICSSector.ENERGY, "HAL": GICSSector.ENERGY, "BKR": GICSSector.ENERGY,

        # Materials
        "LIN": GICSSector.MATERIALS, "APD": GICSSector.MATERIALS, "SHW": GICSSector.MATERIALS,
        "ECL": GICSSector.MATERIALS, "NEM": GICSSector.MATERIALS, "FCX": GICSSector.MATERIALS,
        "NUE": GICSSector.MATERIALS, "DOW": GICSSector.MATERIALS, "DD": GICSSector.MATERIALS,

        # Industrials
        "HON": GICSSector.INDUSTRIALS, "UNP": GICSSector.INDUSTRIALS, "UPS": GICSSector.INDUSTRIALS,
        "CAT": GICSSector.INDUSTRIALS, "BA": GICSSector.INDUSTRIALS, "RTX": GICSSector.INDUSTRIALS,
        "DE": GICSSector.INDUSTRIALS, "GE": GICSSector.INDUSTRIALS, "LMT": GICSSector.INDUSTRIALS,
        "MMM": GICSSector.INDUSTRIALS, "FDX": GICSSector.INDUSTRIALS, "DAL": GICSSector.INDUSTRIALS,
        "UAL": GICSSector.INDUSTRIALS, "AAL": GICSSector.INDUSTRIALS, "CSX": GICSSector.INDUSTRIALS,

        # Consumer Discretionary
        "AMZN": GICSSector.CONSUMER_DISCRETIONARY, "TSLA": GICSSector.CONSUMER_DISCRETIONARY,
        "HD": GICSSector.CONSUMER_DISCRETIONARY, "MCD": GICSSector.CONSUMER_DISCRETIONARY,
        "NKE": GICSSector.CONSUMER_DISCRETIONARY, "LOW": GICSSector.CONSUMER_DISCRETIONARY,
        "SBUX": GICSSector.CONSUMER_DISCRETIONARY, "TGT": GICSSector.CONSUMER_DISCRETIONARY,
        "TJX": GICSSector.CONSUMER_DISCRETIONARY, "F": GICSSector.CONSUMER_DISCRETIONARY,
        "GM": GICSSector.CONSUMER_DISCRETIONARY, "ROST": GICSSector.CONSUMER_DISCRETIONARY,
        "MAR": GICSSector.CONSUMER_DISCRETIONARY, "HLT": GICSSector.CONSUMER_DISCRETIONARY,

        # Consumer Staples
        "PG": GICSSector.CONSUMER_STAPLES, "KO": GICSSector.CONSUMER_STAPLES,
        "PEP": GICSSector.CONSUMER_STAPLES, "COST": GICSSector.CONSUMER_STAPLES,
        "WMT": GICSSector.CONSUMER_STAPLES, "PM": GICSSector.CONSUMER_STAPLES,
        "MO": GICSSector.CONSUMER_STAPLES, "CL": GICSSector.CONSUMER_STAPLES,
        "MDLZ": GICSSector.CONSUMER_STAPLES, "KHC": GICSSector.CONSUMER_STAPLES,
        "GIS": GICSSector.CONSUMER_STAPLES, "K": GICSSector.CONSUMER_STAPLES,
        "KR": GICSSector.CONSUMER_STAPLES, "SYY": GICSSector.CONSUMER_STAPLES,

        # Health Care
        "UNH": GICSSector.HEALTH_CARE, "JNJ": GICSSector.HEALTH_CARE, "LLY": GICSSector.HEALTH_CARE,
        "PFE": GICSSector.HEALTH_CARE, "ABBV": GICSSector.HEALTH_CARE, "MRK": GICSSector.HEALTH_CARE,
        "TMO": GICSSector.HEALTH_CARE, "ABT": GICSSector.HEALTH_CARE, "DHR": GICSSector.HEALTH_CARE,
        "BMY": GICSSector.HEALTH_CARE, "AMGN": GICSSector.HEALTH_CARE, "GILD": GICSSector.HEALTH_CARE,
        "CVS": GICSSector.HEALTH_CARE, "MDT": GICSSector.HEALTH_CARE, "ISRG": GICSSector.HEALTH_CARE,
        "VRTX": GICSSector.HEALTH_CARE, "REGN": GICSSector.HEALTH_CARE, "MRNA": GICSSector.HEALTH_CARE,
        "BIIB": GICSSector.HEALTH_CARE, "CI": GICSSector.HEALTH_CARE, "HUM": GICSSector.HEALTH_CARE,

        # Financials
        "JPM": GICSSector.FINANCIALS, "BAC": GICSSector.FINANCIALS, "WFC": GICSSector.FINANCIALS,
        "GS": GICSSector.FINANCIALS, "MS": GICSSector.FINANCIALS, "C": GICSSector.FINANCIALS,
        "BLK": GICSSector.FINANCIALS, "SCHW": GICSSector.FINANCIALS, "AXP": GICSSector.FINANCIALS,
        "USB": GICSSector.FINANCIALS, "PNC": GICSSector.FINANCIALS, "TFC": GICSSector.FINANCIALS,
        "BK": GICSSector.FINANCIALS, "COF": GICSSector.FINANCIALS, "CME": GICSSector.FINANCIALS,
        "ICE": GICSSector.FINANCIALS, "CB": GICSSector.FINANCIALS, "MMC": GICSSector.FINANCIALS,
        "AON": GICSSector.FINANCIALS, "MET": GICSSector.FINANCIALS, "PRU": GICSSector.FINANCIALS,
        "AFL": GICSSector.FINANCIALS, "AIG": GICSSector.FINANCIALS, "V": GICSSector.FINANCIALS,
        "MA": GICSSector.FINANCIALS, "PYPL": GICSSector.FINANCIALS, "DFS": GICSSector.FINANCIALS,

        # Information Technology
        "AAPL": GICSSector.INFORMATION_TECHNOLOGY, "MSFT": GICSSector.INFORMATION_TECHNOLOGY,
        "NVDA": GICSSector.INFORMATION_TECHNOLOGY, "AVGO": GICSSector.INFORMATION_TECHNOLOGY,
        "ORCL": GICSSector.INFORMATION_TECHNOLOGY, "CSCO": GICSSector.INFORMATION_TECHNOLOGY,
        "ACN": GICSSector.INFORMATION_TECHNOLOGY, "ADBE": GICSSector.INFORMATION_TECHNOLOGY,
        "CRM": GICSSector.INFORMATION_TECHNOLOGY, "AMD": GICSSector.INFORMATION_TECHNOLOGY,
        "INTC": GICSSector.INFORMATION_TECHNOLOGY, "TXN": GICSSector.INFORMATION_TECHNOLOGY,
        "QCOM": GICSSector.INFORMATION_TECHNOLOGY, "IBM": GICSSector.INFORMATION_TECHNOLOGY,
        "INTU": GICSSector.INFORMATION_TECHNOLOGY, "NOW": GICSSector.INFORMATION_TECHNOLOGY,
        "AMAT": GICSSector.INFORMATION_TECHNOLOGY, "MU": GICSSector.INFORMATION_TECHNOLOGY,
        "LRCX": GICSSector.INFORMATION_TECHNOLOGY, "KLAC": GICSSector.INFORMATION_TECHNOLOGY,
        "SNPS": GICSSector.INFORMATION_TECHNOLOGY, "CDNS": GICSSector.INFORMATION_TECHNOLOGY,
        "MRVL": GICSSector.INFORMATION_TECHNOLOGY, "PANW": GICSSector.INFORMATION_TECHNOLOGY,
        "FTNT": GICSSector.INFORMATION_TECHNOLOGY, "CRWD": GICSSector.INFORMATION_TECHNOLOGY,

        # Communication Services
        "GOOGL": GICSSector.COMMUNICATION_SERVICES, "GOOG": GICSSector.COMMUNICATION_SERVICES,
        "META": GICSSector.COMMUNICATION_SERVICES, "NFLX": GICSSector.COMMUNICATION_SERVICES,
        "DIS": GICSSector.COMMUNICATION_SERVICES, "CMCSA": GICSSector.COMMUNICATION_SERVICES,
        "T": GICSSector.COMMUNICATION_SERVICES, "VZ": GICSSector.COMMUNICATION_SERVICES,
        "TMUS": GICSSector.COMMUNICATION_SERVICES, "CHTR": GICSSector.COMMUNICATION_SERVICES,
        "WBD": GICSSector.COMMUNICATION_SERVICES, "EA": GICSSector.COMMUNICATION_SERVICES,
        "TTWO": GICSSector.COMMUNICATION_SERVICES, "ATVI": GICSSector.COMMUNICATION_SERVICES,
        "SPOT": GICSSector.COMMUNICATION_SERVICES, "RBLX": GICSSector.COMMUNICATION_SERVICES,

        # Utilities
        "NEE": GICSSector.UTILITIES, "DUK": GICSSector.UTILITIES, "SO": GICSSector.UTILITIES,
        "D": GICSSector.UTILITIES, "AEP": GICSSector.UTILITIES, "EXC": GICSSector.UTILITIES,
        "XEL": GICSSector.UTILITIES, "SRE": GICSSector.UTILITIES, "PEG": GICSSector.UTILITIES,
        "WEC": GICSSector.UTILITIES, "ED": GICSSector.UTILITIES, "AWK": GICSSector.UTILITIES,

        # Real Estate
        "PLD": GICSSector.REAL_ESTATE, "AMT": GICSSector.REAL_ESTATE, "EQIX": GICSSector.REAL_ESTATE,
        "CCI": GICSSector.REAL_ESTATE, "PSA": GICSSector.REAL_ESTATE, "O": GICSSector.REAL_ESTATE,
        "WELL": GICSSector.REAL_ESTATE, "SPG": GICSSector.REAL_ESTATE, "DLR": GICSSector.REAL_ESTATE,
        "AVB": GICSSector.REAL_ESTATE, "EQR": GICSSector.REAL_ESTATE, "VTR": GICSSector.REAL_ESTATE,
        "SBAC": GICSSector.REAL_ESTATE, "ARE": GICSSector.REAL_ESTATE, "MAA": GICSSector.REAL_ESTATE,
    }

    # Keyword patterns for sector classification
    SECTOR_KEYWORDS = {
        GICSSector.ENERGY: [
            r"\b(oil|gas|petroleum|crude|drilling|refinery|pipeline|lng|fracking)\b",
            r"\b(energy\s+company|oil\s+producer|upstream|downstream|midstream)\b",
            r"\b(opec|barrel|brent|wti)\b",
        ],
        GICSSector.MATERIALS: [
            r"\b(mining|metals|steel|aluminum|copper|gold|silver|chemicals)\b",
            r"\b(fertilizer|packaging|paper|lumber|timber|cement)\b",
        ],
        GICSSector.INDUSTRIALS: [
            r"\b(aerospace|defense|airline|railroad|trucking|logistics)\b",
            r"\b(machinery|equipment|construction|engineering|manufacturing)\b",
            r"\b(industrial|conglomerate|contractor)\b",
        ],
        GICSSector.CONSUMER_DISCRETIONARY: [
            r"\b(retail|restaurant|hotel|casino|cruise|automotive|car\s+maker)\b",
            r"\b(apparel|footwear|luxury|homebuilder|furniture)\b",
            r"\b(e-?commerce|online\s+retail)\b",
        ],
        GICSSector.CONSUMER_STAPLES: [
            r"\b(grocery|supermarket|food\s+(company|producer)|beverage)\b",
            r"\b(tobacco|cigarette|household\s+products|personal\s+care)\b",
            r"\b(consumer\s+goods|packaged\s+food)\b",
        ],
        GICSSector.HEALTH_CARE: [
            r"\b(pharma|pharmaceutical|biotech|biotechnology|drug\s+maker)\b",
            r"\b(hospital|healthcare|medical\s+device|diagnostic)\b",
            r"\b(fda|clinical\s+trial|drug\s+approval|vaccine|therapy)\b",
            r"\b(health\s+insurance|managed\s+care|pharmacy)\b",
        ],
        GICSSector.FINANCIALS: [
            r"\b(bank|banking|financial\s+services|investment\s+bank)\b",
            r"\b(insurance|asset\s+management|credit\s+card|payment)\b",
            r"\b(hedge\s+fund|private\s+equity|mortgage|lending)\b",
            r"\b(broker|exchange|clearing|custody)\b",
        ],
        GICSSector.INFORMATION_TECHNOLOGY: [
            r"\b(software|saas|cloud|cybersecurity|tech\s+company)\b",
            r"\b(semiconductor|chip|processor|computing|hardware)\b",
            r"\b(it\s+services|data\s+center|artificial\s+intelligence|ai)\b",
            r"\b(enterprise\s+software|developer|platform)\b",
        ],
        GICSSector.COMMUNICATION_SERVICES: [
            r"\b(telecom|wireless|5g|mobile|carrier|broadband)\b",
            r"\b(social\s+media|streaming|entertainment|gaming|media)\b",
            r"\b(advertising|search\s+engine|video\s+game)\b",
        ],
        GICSSector.UTILITIES: [
            r"\b(utility|electric\s+(company|utility)|power\s+company)\b",
            r"\b(natural\s+gas\s+utility|water\s+utility|renewable)\b",
            r"\b(grid|transmission|distribution|generation)\b",
        ],
        GICSSector.REAL_ESTATE: [
            r"\b(reit|real\s+estate|property|commercial\s+real\s+estate)\b",
            r"\b(office\s+building|apartment|industrial\s+property)\b",
            r"\b(data\s+center\s+reit|cell\s+tower|warehouse)\b",
        ],
    }

    def __init__(self):
        """Initialize industry classifier."""
        # Compile keyword patterns
        self._compiled_keywords = {
            sector: [re.compile(p, re.IGNORECASE) for p in patterns]
            for sector, patterns in self.SECTOR_KEYWORDS.items()
        }

    def classify_by_ticker(self, ticker: str) -> IndustryClassification | None:
        """Classify industry by ticker symbol.

        Args:
            ticker: Stock ticker symbol

        Returns:
            IndustryClassification or None if ticker not in map
        """
        ticker = ticker.upper()

        if ticker in self.TICKER_SECTOR_MAP:
            sector = self.TICKER_SECTOR_MAP[ticker]
            return IndustryClassification(
                sector=sector,
                sector_name=SECTOR_NAMES[sector],
                industry_group=None,
                industry_group_name=None,
                confidence=0.95,
                classification_method="ticker_lookup",
            )

        return None

    def classify_by_text(self, text: str) -> IndustryClassification | None:
        """Classify industry from text content using keyword matching.

        Args:
            text: Text to analyze

        Returns:
            IndustryClassification or None if no strong match
        """
        text_lower = text.lower()

        # Count keyword matches per sector
        sector_scores: dict[GICSSector, tuple[int, list[str]]] = {}

        for sector, patterns in self._compiled_keywords.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(text_lower)
                matches.extend(found)

            if matches:
                sector_scores[sector] = (len(matches), matches[:5])

        if not sector_scores:
            return None

        # Get sector with most matches
        best_sector = max(sector_scores, key=lambda s: sector_scores[s][0])
        match_count, keywords = sector_scores[best_sector]

        # Calculate confidence based on match count
        confidence = min(0.9, 0.5 + (match_count * 0.1))

        return IndustryClassification(
            sector=best_sector,
            sector_name=SECTOR_NAMES[best_sector],
            industry_group=None,
            industry_group_name=None,
            confidence=confidence,
            classification_method="keyword_match",
            keywords_matched=keywords,
        )

    def classify(
        self,
        ticker: str | None = None,
        text: str | None = None,
    ) -> IndustryClassification:
        """Classify industry using ticker and/or text.

        Args:
            ticker: Optional ticker symbol
            text: Optional text content

        Returns:
            IndustryClassification (defaults to INDUSTRIALS if no match)
        """
        # Try ticker first (most reliable)
        if ticker:
            result = self.classify_by_ticker(ticker)
            if result:
                return result

        # Try text-based classification
        if text:
            result = self.classify_by_text(text)
            if result:
                return result

        # Default classification
        return IndustryClassification(
            sector=GICSSector.INDUSTRIALS,
            sector_name=SECTOR_NAMES[GICSSector.INDUSTRIALS],
            industry_group=None,
            industry_group_name=None,
            confidence=0.3,
            classification_method="default",
        )

    def get_sector_info(self, sector: GICSSector) -> dict[str, Any]:
        """Get information about a sector.

        Args:
            sector: GICS sector

        Returns:
            Sector information dictionary
        """
        return {
            "code": sector.value,
            "name": SECTOR_NAMES[sector],
            "industry_groups": [
                {"code": code, **info}
                for code, info in INDUSTRY_GROUPS.items()
                if info["sector"] == sector
            ],
        }


def classify_industry(
    ticker: str | None = None,
    text: str | None = None,
) -> IndustryClassification:
    """Convenience function to classify industry.

    Args:
        ticker: Optional ticker symbol
        text: Optional text content

    Returns:
        IndustryClassification
    """
    classifier = IndustryClassifier()
    return classifier.classify(ticker, text)
