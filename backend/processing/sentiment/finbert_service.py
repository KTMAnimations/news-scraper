"""FinBERT sentiment analysis service."""

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    label: str  # "positive", "negative", "neutral"
    score: float  # -1 to 1 scale
    confidence: float  # 0 to 1 confidence
    probabilities: dict[str, float]  # All class probabilities

    @property
    def direction(self) -> str:
        """Get trading direction."""
        if self.score > 0.3:
            return "BULLISH"
        elif self.score < -0.3:
            return "BEARISH"
        return "NEUTRAL"


class FinBERTService:
    """FinBERT sentiment analysis service.

    Uses ProsusAI/finbert model for financial text sentiment.
    """

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        max_length: int = 512,
    ):
        """Initialize FinBERT service.

        Args:
            model_name: HuggingFace model name
            device: Device to run on ("cuda", "cpu", or None for auto)
            max_length: Maximum sequence length
        """
        self.model_name = model_name or self.MODEL_NAME
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
        self._device = device

    def _load_model(self):
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch

            logger.info("Loading FinBERT model", model=self.model_name)

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

            # Determine device
            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            self._model = self._model.to(self._device)
            self._model.eval()

            logger.info("FinBERT model loaded", device=self._device)

        except ImportError:
            logger.error("transformers or torch not installed")
            raise
        except Exception as e:
            logger.error("Failed to load FinBERT model", error=str(e))
            raise

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of a single text.

        Args:
            text: Text to analyze

        Returns:
            SentimentResult
        """
        self._load_model()

        import torch

        # Tokenize
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )

        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        # Inference
        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)

        # FinBERT labels: positive, negative, neutral
        labels = ["positive", "negative", "neutral"]
        probs_dict = {label: float(probs[0][i]) for i, label in enumerate(labels)}

        # Get predicted label
        pred_idx = torch.argmax(probs, dim=1).item()
        pred_label = labels[pred_idx]
        confidence = float(probs[0][pred_idx])

        # Calculate score (-1 to 1 scale)
        # positive = +1, negative = -1, neutral = 0
        score = probs_dict["positive"] - probs_dict["negative"]

        return SentimentResult(
            label=pred_label,
            score=score,
            confidence=confidence,
            probabilities=probs_dict,
        )

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze sentiment of multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of SentimentResults
        """
        if not texts:
            return []

        self._load_model()

        import torch

        # Tokenize batch
        inputs = self._tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )

        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        # Inference
        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)

        # Convert to results
        labels = ["positive", "negative", "neutral"]
        results = []

        for i in range(len(texts)):
            probs_dict = {label: float(probs[i][j]) for j, label in enumerate(labels)}
            pred_idx = torch.argmax(probs[i]).item()
            pred_label = labels[pred_idx]
            confidence = float(probs[i][pred_idx])
            score = probs_dict["positive"] - probs_dict["negative"]

            results.append(SentimentResult(
                label=pred_label,
                score=score,
                confidence=confidence,
                probabilities=probs_dict,
            ))

        return results

    def analyze_headline(self, headline: str) -> SentimentResult:
        """Analyze sentiment of a headline.

        Optimized for short financial headlines.

        Args:
            headline: Headline text

        Returns:
            SentimentResult
        """
        # Headlines don't need truncation usually
        return self.analyze(headline)


class SimpleSentimentService:
    """Simple rule-based sentiment for when FinBERT is not available."""

    # Positive financial terms
    POSITIVE_TERMS = {
        "beat", "beats", "exceeds", "exceeded", "surpasses", "surpassed",
        "growth", "grew", "grows", "increase", "increased", "increases",
        "profit", "profits", "profitable", "gain", "gains", "gained",
        "bullish", "buy", "upgrade", "upgraded", "outperform",
        "strong", "stronger", "strength", "record", "high", "higher",
        "approval", "approved", "approves", "success", "successful",
        "partnership", "acquisition", "acquires", "acquired",
        "positive", "upbeat", "optimistic", "soar", "soars", "soared",
        "surge", "surges", "surged", "rally", "rallies", "rallied",
    }

    # Negative financial terms
    NEGATIVE_TERMS = {
        "miss", "misses", "missed", "below", "decline", "declined", "declines",
        "loss", "losses", "lost", "decrease", "decreased", "decreases",
        "bearish", "sell", "downgrade", "downgraded", "underperform",
        "weak", "weaker", "weakness", "low", "lower", "lowest",
        "rejection", "rejected", "rejects", "failure", "failed", "fails",
        "lawsuit", "sued", "sues", "investigation", "investigated",
        "negative", "warning", "warns", "warned", "concern", "concerns",
        "fall", "falls", "fell", "drop", "drops", "dropped",
        "plunge", "plunges", "plunged", "crash", "crashes", "crashed",
        "bankruptcy", "bankrupt", "default", "defaults", "defaulted",
        "recall", "recalls", "recalled", "layoff", "layoffs",
    }

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using rules.

        Args:
            text: Text to analyze

        Returns:
            SentimentResult
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        positive_count = len(words & self.POSITIVE_TERMS)
        negative_count = len(words & self.NEGATIVE_TERMS)

        total = positive_count + negative_count

        if total == 0:
            return SentimentResult(
                label="neutral",
                score=0.0,
                confidence=0.5,
                probabilities={"positive": 0.33, "negative": 0.33, "neutral": 0.34},
            )

        positive_ratio = positive_count / total
        negative_ratio = negative_count / total

        score = positive_ratio - negative_ratio
        confidence = max(positive_ratio, negative_ratio)

        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"

        return SentimentResult(
            label=label,
            score=score,
            confidence=confidence,
            probabilities={
                "positive": positive_ratio,
                "negative": negative_ratio,
                "neutral": 1 - max(positive_ratio, negative_ratio),
            },
        )


def get_sentiment_service(use_finbert: bool = True) -> FinBERTService | SimpleSentimentService:
    """Get sentiment service instance.

    Args:
        use_finbert: Whether to use FinBERT (requires transformers/torch)

    Returns:
        Sentiment service instance
    """
    if use_finbert:
        try:
            import torch
            import transformers
            return FinBERTService()
        except ImportError:
            logger.warning("FinBERT dependencies not available, using simple sentiment")
            return SimpleSentimentService()

    return SimpleSentimentService()
