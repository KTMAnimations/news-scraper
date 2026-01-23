"""Event classification module."""

from .direction_predictor import DirectionPredictor, DirectionPrediction
from .event_classifier import EventClassifier, EventClassification, EventType
from .industry_classifier import (
    IndustryClassifier,
    IndustryClassification,
    GICSSector,
    SECTOR_NAMES,
    classify_industry,
)
from .ml_classifier import (
    MLEventClassifier,
    MLClassificationResult,
    get_ml_classifier,
)
from .subcategory_classifier import (
    SubCategoryClassifier,
    SubCategoryResult,
    InsiderSubCategory,
    EarningsSubCategory,
    FDASubCategory,
    MAndASubCategory,
    OfferingSubCategory,
    ClinicalTrialSubCategory,
    classify_subcategory,
)
from .urgency_scorer import UrgencyScorer, UrgencyScore

__all__ = [
    # Core classifiers
    "EventClassifier",
    "EventClassification",
    "EventType",
    # ML classifier
    "MLEventClassifier",
    "MLClassificationResult",
    "get_ml_classifier",
    # Sub-category classification
    "SubCategoryClassifier",
    "SubCategoryResult",
    "InsiderSubCategory",
    "EarningsSubCategory",
    "FDASubCategory",
    "MAndASubCategory",
    "OfferingSubCategory",
    "ClinicalTrialSubCategory",
    "classify_subcategory",
    # Urgency and direction
    "UrgencyScorer",
    "UrgencyScore",
    "DirectionPredictor",
    "DirectionPrediction",
    # Industry classification
    "IndustryClassifier",
    "IndustryClassification",
    "GICSSector",
    "SECTOR_NAMES",
    "classify_industry",
]
