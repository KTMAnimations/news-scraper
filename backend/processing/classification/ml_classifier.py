"""Machine learning-based event classifier for financial news."""

import json
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from .event_classifier import EventClassification, EventClassifier, EventType

logger = structlog.get_logger(__name__)

# Training data for financial news classification
# Categories mapped to event types with example texts
TRAINING_DATA = [
    # Insider activity - Buy
    ("Insider purchases 50,000 shares at $10.50", EventType.INSIDER_BUY),
    ("Form 4 shows director acquired 10,000 shares", EventType.INSIDER_BUY),
    ("CEO buys $500,000 worth of company stock", EventType.INSIDER_BUY),
    ("Executive open market purchase of common stock", EventType.INSIDER_BUY),
    ("Board member increases stake with stock purchase", EventType.INSIDER_BUY),
    ("CFO purchases shares showing confidence in company", EventType.INSIDER_BUY),
    ("Insider buying activity signals management confidence", EventType.INSIDER_BUY),
    ("Multiple insiders acquire shares in open market", EventType.INSIDER_BUY),
    ("Director purchases $1 million in stock", EventType.INSIDER_BUY),
    ("Form 4 filing reveals insider stock accumulation", EventType.INSIDER_BUY),

    # Insider activity - Sell
    ("Insider sells 100,000 shares at $25.00", EventType.INSIDER_SELL),
    ("Form 4 shows CEO disposed of shares", EventType.INSIDER_SELL),
    ("Executive sells stock after vesting", EventType.INSIDER_SELL),
    ("Director reduces stake by selling shares", EventType.INSIDER_SELL),
    ("Planned insider selling under 10b5-1 plan", EventType.INSIDER_SELL),
    ("CFO sells shares following option exercise", EventType.INSIDER_SELL),
    ("Insider liquidates position in company stock", EventType.INSIDER_SELL),
    ("Form 4 filing shows executive stock sale", EventType.INSIDER_SELL),
    ("Director disposes of shares in block trade", EventType.INSIDER_SELL),
    ("VP sells shares for personal financial planning", EventType.INSIDER_SELL),

    # Earnings - Beat
    ("Company beats Q3 earnings estimates by 15%", EventType.EARNINGS_BEAT),
    ("Quarterly results exceed analyst expectations", EventType.EARNINGS_BEAT),
    ("EPS surpasses consensus by $0.10", EventType.EARNINGS_BEAT),
    ("Revenue beats Wall Street forecasts", EventType.EARNINGS_BEAT),
    ("Strong earnings surprise delights investors", EventType.EARNINGS_BEAT),
    ("Better than expected quarterly performance", EventType.EARNINGS_BEAT),
    ("Company reports earnings beat on strong sales", EventType.EARNINGS_BEAT),
    ("Quarterly profit tops analyst projections", EventType.EARNINGS_BEAT),
    ("Results came in above street estimates", EventType.EARNINGS_BEAT),
    ("Earnings topped expectations with margin expansion", EventType.EARNINGS_BEAT),

    # Earnings - Miss
    ("Company misses Q2 earnings expectations", EventType.EARNINGS_MISS),
    ("Quarterly results fall short of estimates", EventType.EARNINGS_MISS),
    ("EPS disappoints below analyst forecasts", EventType.EARNINGS_MISS),
    ("Revenue misses Wall Street projections", EventType.EARNINGS_MISS),
    ("Earnings disappointment sends stock lower", EventType.EARNINGS_MISS),
    ("Worse than expected quarterly performance", EventType.EARNINGS_MISS),
    ("Company reports earnings miss on weak demand", EventType.EARNINGS_MISS),
    ("Quarterly profit falls below analyst targets", EventType.EARNINGS_MISS),
    ("Results came in below street consensus", EventType.EARNINGS_MISS),
    ("Earnings missed with margin compression", EventType.EARNINGS_MISS),

    # Earnings - Announce (neutral)
    ("Company announces Q4 earnings date", EventType.EARNINGS_ANNOUNCE),
    ("Quarterly results scheduled for release", EventType.EARNINGS_ANNOUNCE),
    ("Company to report annual results next week", EventType.EARNINGS_ANNOUNCE),
    ("Earnings call scheduled for Tuesday", EventType.EARNINGS_ANNOUNCE),
    ("Company reports Q1 2024 financial results", EventType.EARNINGS_ANNOUNCE),
    ("Annual report filing with SEC", EventType.EARNINGS_ANNOUNCE),

    # FDA - Approval
    ("FDA approves new drug application", EventType.FDA_APPROVAL),
    ("Company receives FDA clearance for device", EventType.FDA_APPROVAL),
    ("Drug approved for expanded indication", EventType.FDA_APPROVAL),
    ("FDA grants breakthrough therapy designation", EventType.FDA_APPROVAL),
    ("Regulatory approval received for treatment", EventType.FDA_APPROVAL),
    ("FDA clears medical device for market", EventType.FDA_APPROVAL),
    ("BLA approval granted by FDA", EventType.FDA_APPROVAL),
    ("Company announces FDA approval of cancer drug", EventType.FDA_APPROVAL),
    ("NDA approved with priority review", EventType.FDA_APPROVAL),
    ("EMA and FDA approve new medication", EventType.FDA_APPROVAL),

    # FDA - Rejection
    ("FDA issues complete response letter", EventType.FDA_REJECTION),
    ("Drug application rejected by FDA", EventType.FDA_REJECTION),
    ("Regulatory setback as FDA declines approval", EventType.FDA_REJECTION),
    ("FDA refuses to file application", EventType.FDA_REJECTION),
    ("Company receives CRL from FDA", EventType.FDA_REJECTION),
    ("FDA rejects new drug application citing safety concerns", EventType.FDA_REJECTION),
    ("Approval denial from regulatory agency", EventType.FDA_REJECTION),
    ("FDA requests additional clinical data", EventType.FDA_REJECTION),
    ("PDUFA date delay after FDA rejection", EventType.FDA_REJECTION),
    ("FDA declines accelerated approval request", EventType.FDA_REJECTION),

    # Clinical trials
    ("Phase 3 trial meets primary endpoint", EventType.CLINICAL_TRIAL),
    ("Positive clinical trial results announced", EventType.CLINICAL_TRIAL),
    ("Drug shows efficacy in pivotal study", EventType.CLINICAL_TRIAL),
    ("Phase 2 data demonstrates safety profile", EventType.CLINICAL_TRIAL),
    ("Clinical trial fails to meet endpoints", EventType.CLINICAL_TRIAL),
    ("Interim data shows promising results", EventType.CLINICAL_TRIAL),
    ("Phase 1 study initiated for new compound", EventType.CLINICAL_TRIAL),
    ("Clinical program advances to Phase 3", EventType.CLINICAL_TRIAL),

    # Acquisition
    ("Company to acquire competitor for $2 billion", EventType.ACQUISITION),
    ("Acquisition agreement announced", EventType.ACQUISITION),
    ("Company acquires startup in strategic deal", EventType.ACQUISITION),
    ("Takeover offer made at premium", EventType.ACQUISITION),
    ("Company buys rival in cash transaction", EventType.ACQUISITION),
    ("Acquisition completed for technology assets", EventType.ACQUISITION),
    ("Company to be acquired by private equity firm", EventType.ACQUISITION),
    ("Strategic acquisition expands market reach", EventType.ACQUISITION),

    # Merger
    ("Merger agreement reached between companies", EventType.MERGER),
    ("Companies announce merger of equals", EventType.MERGER),
    ("Proposed merger to create industry leader", EventType.MERGER),
    ("Merger talks confirmed by both parties", EventType.MERGER),
    ("Stock-for-stock merger announced", EventType.MERGER),
    ("Merger expected to close by year end", EventType.MERGER),

    # Spinoff
    ("Company announces spinoff of division", EventType.SPINOFF),
    ("Business unit to be spun off as separate company", EventType.SPINOFF),
    ("Spin-off expected to unlock shareholder value", EventType.SPINOFF),
    ("Company completes spinoff transaction", EventType.SPINOFF),

    # Offering
    ("Company announces secondary stock offering", EventType.OFFERING),
    ("Public offering priced at discount", EventType.OFFERING),
    ("Private placement of common stock", EventType.OFFERING),
    ("Company raises capital through equity offering", EventType.OFFERING),
    ("Stock dilution from new share issuance", EventType.OFFERING),
    ("ATM offering announced", EventType.OFFERING),
    ("PIPE transaction completed", EventType.OFFERING),

    # Buyback
    ("Company announces $1 billion stock buyback", EventType.BUYBACK),
    ("Share repurchase program authorized", EventType.BUYBACK),
    ("Board approves stock buyback plan", EventType.BUYBACK),
    ("Company to repurchase shares in open market", EventType.BUYBACK),
    ("Buyback program expanded by $500 million", EventType.BUYBACK),

    # Dividend
    ("Company raises quarterly dividend", EventType.DIVIDEND),
    ("Dividend increase announced", EventType.DIVIDEND),
    ("Special dividend declared", EventType.DIVIDEND),
    ("Dividend suspended due to cash constraints", EventType.DIVIDEND),
    ("Company cuts dividend by 50%", EventType.DIVIDEND),
    ("Dividend payment date announced", EventType.DIVIDEND),

    # Activist stake
    ("Activist investor acquires 5% stake", EventType.ACTIVIST_STAKE),
    ("13D filing reveals activist position", EventType.ACTIVIST_STAKE),
    ("Hedge fund takes significant stake", EventType.ACTIVIST_STAKE),
    ("Activist launches proxy fight", EventType.ACTIVIST_STAKE),
    ("Investor pushes for board changes", EventType.ACTIVIST_STAKE),
    ("13D amendment shows increased position", EventType.ACTIVIST_STAKE),

    # Regulatory action
    ("SEC launches investigation into company", EventType.REGULATORY_ACTION),
    ("Company receives SEC subpoena", EventType.REGULATORY_ACTION),
    ("Regulatory inquiry into accounting practices", EventType.REGULATORY_ACTION),
    ("SEC charges company with fraud", EventType.REGULATORY_ACTION),
    ("Company settles with SEC for $10 million", EventType.REGULATORY_ACTION),
    ("DOJ investigation announced", EventType.REGULATORY_ACTION),

    # Lawsuit
    ("Class action lawsuit filed against company", EventType.LAWSUIT),
    ("Company sued by shareholders", EventType.LAWSUIT),
    ("Patent infringement lawsuit filed", EventType.LAWSUIT),
    ("Securities litigation pending", EventType.LAWSUIT),
    ("Company faces legal action from competitor", EventType.LAWSUIT),

    # Settlement
    ("Company settles lawsuit for $50 million", EventType.SETTLEMENT),
    ("Settlement agreement reached", EventType.SETTLEMENT),
    ("Legal dispute resolved through settlement", EventType.SETTLEMENT),
    ("Company agrees to pay settlement", EventType.SETTLEMENT),

    # CEO change
    ("CEO resigns effective immediately", EventType.CEO_CHANGE),
    ("Company names new chief executive", EventType.CEO_CHANGE),
    ("CEO departure announced", EventType.CEO_CHANGE),
    ("Board appoints new CEO", EventType.CEO_CHANGE),
    ("CEO to step down after transition", EventType.CEO_CHANGE),
    ("New chief executive starts next month", EventType.CEO_CHANGE),

    # Executive departure
    ("CFO leaving company", EventType.EXECUTIVE_DEPARTURE),
    ("COO resignation announced", EventType.EXECUTIVE_DEPARTURE),
    ("CTO departing for new opportunity", EventType.EXECUTIVE_DEPARTURE),
    ("Executive team changes announced", EventType.EXECUTIVE_DEPARTURE),

    # Bankruptcy
    ("Company files for Chapter 11 bankruptcy", EventType.BANKRUPTCY),
    ("Bankruptcy protection sought", EventType.BANKRUPTCY),
    ("Company enters insolvency proceedings", EventType.BANKRUPTCY),
    ("Chapter 7 liquidation filed", EventType.BANKRUPTCY),
    ("Restructuring under bankruptcy court", EventType.BANKRUPTCY),

    # Delisting
    ("Stock to be delisted from exchange", EventType.DELISTING),
    ("Company receives delisting notice", EventType.DELISTING),
    ("NYSE delisting warning issued", EventType.DELISTING),
    ("Compliance issue may lead to delisting", EventType.DELISTING),

    # Tier change
    ("Stock upgraded to NASDAQ", EventType.TIER_CHANGE),
    ("Company uplisted to NYSE", EventType.TIER_CHANGE),
    ("Downgraded to OTC Pink Sheets", EventType.TIER_CHANGE),
    ("Stock moved to Grey Market", EventType.TIER_CHANGE),

    # Partnership
    ("Strategic partnership announced", EventType.PARTNERSHIP),
    ("Companies form joint venture", EventType.PARTNERSHIP),
    ("Partnership agreement signed", EventType.PARTNERSHIP),
    ("Collaboration deal with major company", EventType.PARTNERSHIP),
    ("Alliance formed for product development", EventType.PARTNERSHIP),

    # Contract
    ("Company wins $100 million contract", EventType.CONTRACT),
    ("Government contract awarded", EventType.CONTRACT),
    ("Major supply agreement signed", EventType.CONTRACT),
    ("Multi-year deal announced", EventType.CONTRACT),
    ("Company secures new customer contract", EventType.CONTRACT),

    # Product launch
    ("Company launches new product line", EventType.PRODUCT_LAUNCH),
    ("New product unveiled at trade show", EventType.PRODUCT_LAUNCH),
    ("Product release date announced", EventType.PRODUCT_LAUNCH),
    ("Company introduces next generation product", EventType.PRODUCT_LAUNCH),

    # General news
    ("Company updates full year guidance", EventType.NEWS),
    ("Management provides business update", EventType.NEWS),
    ("Company to present at investor conference", EventType.NEWS),
    ("Press release issued by company", EventType.NEWS),
    ("Market commentary on stock performance", EventType.NEWS),

    # Social mentions
    ("Stock trending on Reddit", EventType.SOCIAL_MENTION),
    ("Twitter buzz around ticker", EventType.SOCIAL_MENTION),
    ("StockTwits sentiment turning positive", EventType.SOCIAL_MENTION),
    ("Social media mentions spiking", EventType.SOCIAL_MENTION),
]


@dataclass
class MLClassificationResult:
    """Result from ML classification."""

    event_type: EventType
    confidence: float
    probabilities: dict[str, float]
    used_ml: bool  # True if ML model was used, False if fell back to rules


class MLEventClassifier:
    """ML-based event classifier with rule-based fallback."""

    MODEL_DIR = Path(__file__).parent / "models"
    MODEL_FILE = "event_classifier.pkl"
    VECTORIZER_FILE = "vectorizer.pkl"

    def __init__(self, use_ml: bool = True):
        """Initialize the ML classifier.

        Args:
            use_ml: Whether to attempt to use ML model
        """
        self.use_ml = use_ml
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.rule_classifier = EventClassifier()

        if use_ml:
            self._load_or_train_model()

    def _load_or_train_model(self) -> None:
        """Load existing model or train a new one."""
        model_path = self.MODEL_DIR / self.MODEL_FILE
        vectorizer_path = self.MODEL_DIR / self.VECTORIZER_FILE

        if model_path.exists() and vectorizer_path.exists():
            try:
                self._load_model()
                logger.info("Loaded ML classifier model")
                return
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

        # Train new model
        self._train_model()

    def _load_model(self) -> None:
        """Load the trained model from disk."""
        model_path = self.MODEL_DIR / self.MODEL_FILE
        vectorizer_path = self.MODEL_DIR / self.VECTORIZER_FILE

        with open(model_path, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.label_encoder = data["label_encoder"]

        with open(vectorizer_path, "rb") as f:
            self.vectorizer = pickle.load(f)

    def _train_model(self) -> None:
        """Train the ML model on the training data."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import LabelEncoder

            # Prepare training data
            texts = [text for text, _ in TRAINING_DATA]
            labels = [event_type.value for _, event_type in TRAINING_DATA]

            # Encode labels
            self.label_encoder = LabelEncoder()
            encoded_labels = self.label_encoder.fit_transform(labels)

            # Create TF-IDF features
            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words="english",
                lowercase=True,
            )
            X = self.vectorizer.fit_transform(texts)

            # Train logistic regression model
            self.model = LogisticRegression(
                max_iter=1000,
                multi_class="multinomial",
                solver="lbfgs",
                class_weight="balanced",
            )
            self.model.fit(X, encoded_labels)

            # Save model
            self._save_model()

            logger.info(
                "Trained ML classifier",
                num_samples=len(texts),
                num_classes=len(set(labels)),
            )

        except ImportError as e:
            logger.warning(f"scikit-learn not available, using rule-based only: {e}")
            self.model = None
        except Exception as e:
            logger.warning(f"Failed to train model: {e}")
            self.model = None

    def _save_model(self) -> None:
        """Save the trained model to disk."""
        # Create model directory
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)

        model_path = self.MODEL_DIR / self.MODEL_FILE
        vectorizer_path = self.MODEL_DIR / self.VECTORIZER_FILE

        with open(model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "label_encoder": self.label_encoder,
            }, f)

        with open(vectorizer_path, "wb") as f:
            pickle.dump(self.vectorizer, f)

        logger.info("Saved ML classifier model")

    def classify(
        self,
        text: str,
        source_type: str | None = None,
        min_confidence: float = 0.5,
    ) -> MLClassificationResult:
        """Classify text using ML model with rule-based fallback.

        Args:
            text: Text to classify
            source_type: Optional source type hint
            min_confidence: Minimum confidence to use ML result

        Returns:
            MLClassificationResult
        """
        ml_result = None

        # Try ML classification first
        if self.model is not None and self.vectorizer is not None:
            try:
                ml_result = self._ml_classify(text)
            except Exception as e:
                logger.warning(f"ML classification failed: {e}")

        # Use ML result if confident enough
        if ml_result and ml_result.confidence >= min_confidence:
            return ml_result

        # Fall back to rule-based classification
        rule_result = self.rule_classifier.classify(text, source_type)

        # Combine results if we have both
        if ml_result:
            # If rule-based found a match and ML is less confident, prefer rules
            if rule_result.event_type != EventType.NEWS:
                return MLClassificationResult(
                    event_type=rule_result.event_type,
                    confidence=rule_result.confidence,
                    probabilities={rule_result.event_type.value: rule_result.confidence},
                    used_ml=False,
                )
            else:
                # Use ML result even with lower confidence if rules found nothing
                return ml_result

        # Return rule-based result
        return MLClassificationResult(
            event_type=rule_result.event_type,
            confidence=rule_result.confidence,
            probabilities={rule_result.event_type.value: rule_result.confidence},
            used_ml=False,
        )

    def _ml_classify(self, text: str) -> MLClassificationResult:
        """Perform ML classification.

        Args:
            text: Text to classify

        Returns:
            MLClassificationResult
        """
        # Transform text to features
        X = self.vectorizer.transform([text])

        # Get predicted probabilities
        proba = self.model.predict_proba(X)[0]

        # Get predicted class
        predicted_idx = proba.argmax()
        predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]
        confidence = float(proba[predicted_idx])

        # Build probabilities dict
        probabilities = {}
        for idx, prob in enumerate(proba):
            label = self.label_encoder.inverse_transform([idx])[0]
            probabilities[label] = float(prob)

        # Convert to EventType
        try:
            event_type = EventType(predicted_label)
        except ValueError:
            event_type = EventType.NEWS

        return MLClassificationResult(
            event_type=event_type,
            confidence=confidence,
            probabilities=probabilities,
            used_ml=True,
        )

    def batch_classify(
        self,
        texts: list[str],
        min_confidence: float = 0.5,
    ) -> list[MLClassificationResult]:
        """Classify multiple texts efficiently.

        Args:
            texts: List of texts to classify
            min_confidence: Minimum confidence to use ML result

        Returns:
            List of MLClassificationResult
        """
        if not self.model or not self.vectorizer:
            # Fall back to individual rule-based classification
            return [
                self.classify(text, min_confidence=min_confidence)
                for text in texts
            ]

        try:
            # Batch ML classification
            X = self.vectorizer.transform(texts)
            proba_all = self.model.predict_proba(X)

            results = []
            for i, (text, proba) in enumerate(zip(texts, proba_all)):
                predicted_idx = proba.argmax()
                predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]
                confidence = float(proba[predicted_idx])

                probabilities = {}
                for idx, prob in enumerate(proba):
                    label = self.label_encoder.inverse_transform([idx])[0]
                    probabilities[label] = float(prob)

                try:
                    event_type = EventType(predicted_label)
                except ValueError:
                    event_type = EventType.NEWS

                ml_result = MLClassificationResult(
                    event_type=event_type,
                    confidence=confidence,
                    probabilities=probabilities,
                    used_ml=True,
                )

                # Check if we should use rule-based instead
                if confidence < min_confidence:
                    rule_result = self.rule_classifier.classify(text)
                    if rule_result.event_type != EventType.NEWS:
                        ml_result = MLClassificationResult(
                            event_type=rule_result.event_type,
                            confidence=rule_result.confidence,
                            probabilities={rule_result.event_type.value: rule_result.confidence},
                            used_ml=False,
                        )

                results.append(ml_result)

            return results

        except Exception as e:
            logger.warning(f"Batch ML classification failed: {e}")
            return [
                self.classify(text, min_confidence=min_confidence)
                for text in texts
            ]

    def retrain(self, additional_data: list[tuple[str, EventType]] | None = None) -> bool:
        """Retrain the model with additional data.

        Args:
            additional_data: Optional additional training examples

        Returns:
            True if training succeeded
        """
        global TRAINING_DATA

        if additional_data:
            # Add new data to training set
            all_data = list(TRAINING_DATA) + list(additional_data)
        else:
            all_data = TRAINING_DATA

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import LabelEncoder

            texts = [text for text, _ in all_data]
            labels = [event_type.value for _, event_type in all_data]

            self.label_encoder = LabelEncoder()
            encoded_labels = self.label_encoder.fit_transform(labels)

            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words="english",
                lowercase=True,
            )
            X = self.vectorizer.fit_transform(texts)

            self.model = LogisticRegression(
                max_iter=1000,
                multi_class="multinomial",
                solver="lbfgs",
                class_weight="balanced",
            )
            self.model.fit(X, encoded_labels)

            self._save_model()

            logger.info(
                "Retrained ML classifier",
                num_samples=len(texts),
                num_classes=len(set(labels)),
            )
            return True

        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            return False


# Singleton instance
_ml_classifier: MLEventClassifier | None = None


def get_ml_classifier(use_ml: bool = True) -> MLEventClassifier:
    """Get or create the ML classifier singleton.

    Args:
        use_ml: Whether to use ML model

    Returns:
        MLEventClassifier instance
    """
    global _ml_classifier

    if _ml_classifier is None:
        _ml_classifier = MLEventClassifier(use_ml=use_ml)

    return _ml_classifier
