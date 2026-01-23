"""Simple sentiment analysis service using keyword-based approach.

A lightweight fallback that doesn't require transformers/GPU.
"""

import re
from dataclasses import dataclass
from typing import Any

import structlog

from .finbert_service import SentimentResult

logger = structlog.get_logger(__name__)

# Financial sentiment word lists
POSITIVE_WORDS = {
    # General positive
    "bullish", "upside", "growth", "profit", "gain", "positive", "strong",
    "beat", "exceed", "outperform", "upgrade", "buy", "accumulate", "surge",
    "rally", "breakout", "momentum", "recovery", "rebound", "expand",
    # Financial events
    "approval", "approved", "grant", "awarded", "win", "wins", "won",
    "dividend", "buyback", "repurchase", "acquisition", "merger",
    "partnership", "contract", "deal", "agreement", "launch",
    # SEC/Insider
    "purchase", "bought", "insider buy", "open market purchase",
    "form 4 purchase", "increased position", "new position",
}

NEGATIVE_WORDS = {
    # General negative
    "bearish", "downside", "loss", "losses", "negative", "weak", "weakness",
    "miss", "missed", "decline", "downgrade", "sell", "warning", "concern",
    "drop", "fell", "fall", "crash", "plunge", "slump", "deteriorate",
    # Financial events
    "reject", "rejected", "deny", "denied", "lawsuit", "litigation",
    "investigation", "subpoena", "fraud", "default", "bankruptcy",
    "delisting", "dilution", "offering", "secondary", "shelf",
    # SEC/Insider
    "sale", "sold", "insider sell", "disposal", "decreased position",
    "terminated", "resigned", "departure", "layoff", "restructuring",
}

INTENSITY_MODIFIERS = {
    "very": 1.5,
    "extremely": 2.0,
    "significantly": 1.5,
    "slightly": 0.5,
    "somewhat": 0.7,
    "materially": 1.5,
    "substantially": 1.5,
}


class SimpleSentimentService:
    """Simple keyword-based sentiment analyzer.

    Fast, CPU-only sentiment analysis using financial keyword lists.
    Use FinBERTService for more accurate analysis.
    """

    def __init__(self):
        """Initialize simple sentiment service."""
        self.positive_words = POSITIVE_WORDS
        self.negative_words = NEGATIVE_WORDS
        self.modifiers = INTENSITY_MODIFIERS

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            SentimentResult with label, score, confidence
        """
        if not text or not text.strip():
            return SentimentResult(
                label="neutral",
                score=0.0,
                confidence=0.5,
                probabilities={"positive": 0.33, "negative": 0.33, "neutral": 0.34},
            )

        # Normalize text
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        # Count sentiment words
        positive_count = 0
        negative_count = 0

        # Check for multi-word phrases first
        for phrase in self.positive_words:
            if " " in phrase and phrase in text_lower:
                positive_count += 2  # Phrases get extra weight
        for phrase in self.negative_words:
            if " " in phrase and phrase in text_lower:
                negative_count += 2

        # Count individual words with modifier detection
        for i, word in enumerate(words):
            modifier = 1.0
            if i > 0 and words[i-1] in self.modifiers:
                modifier = self.modifiers[words[i-1]]

            if word in self.positive_words:
                positive_count += modifier
            elif word in self.negative_words:
                negative_count += modifier

        # Calculate score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.3
        else:
            score = (positive_count - negative_count) / (total + 2)  # Smoothing
            confidence = min(0.9, 0.4 + (total * 0.1))  # More matches = higher confidence

        # Clamp score
        score = max(-1.0, min(1.0, score))

        # Determine label
        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        # Calculate probabilities
        if label == "positive":
            probabilities = {
                "positive": 0.4 + abs(score) * 0.4,
                "negative": 0.1,
                "neutral": 0.5 - abs(score) * 0.4,
            }
        elif label == "negative":
            probabilities = {
                "positive": 0.1,
                "negative": 0.4 + abs(score) * 0.4,
                "neutral": 0.5 - abs(score) * 0.4,
            }
        else:
            probabilities = {
                "positive": 0.3,
                "negative": 0.3,
                "neutral": 0.4,
            }

        return SentimentResult(
            label=label,
            score=score,
            confidence=confidence,
            probabilities=probabilities,
        )

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze sentiment for multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of SentimentResults
        """
        return [self.analyze(text) for text in texts]
