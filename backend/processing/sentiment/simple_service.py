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
    "beat", "exceed", "outperform", "upgrade", "buy", "accumulate",
    "surge", "surges", "surging", "surged",
    "rally", "rallies", "rallying", "breakout", "momentum", "recovery", "rebound", "expand",
    "soar", "soars", "soaring", "jump", "jumps", "jumping", "spike", "spikes",
    "rise", "rises", "rising", "climb", "climbs", "climbing", "increase", "increased",
    # Financial events
    "approval", "approved", "grant", "awarded", "win", "wins", "won",
    "dividend", "distribution", "buyback", "repurchase", "acquisition", "merger",
    "partnership", "contract", "deal", "agreement", "launch", "launches",
    "record", "records", "milestone", "milestone", "breakthrough", "innovation",
    "expansion", "expands", "growing", "accelerate", "accelerating",
    # Earnings/Financial
    "beats", "exceeds", "surpasses", "outperforms", "raises", "guidance",
    "raises guidance", "strong results", "record revenue", "record profit",
    "profitable", "profitability", "margin expansion", "cost savings",
    # SEC/Insider
    "purchase", "bought", "insider buy", "open market purchase",
    "form 4 purchase", "increased position", "new position",
    "insider buying", "directors purchase", "ceo buys", "cfo buys",
    # Regulatory
    "fda approval", "fda approves", "cleared", "clearance", "authorized",
    "patent", "patents", "patent granted",
}

NEGATIVE_WORDS = {
    # General negative
    "bearish", "downside", "loss", "losses", "negative", "weak", "weakness",
    "miss", "missed", "decline", "downgrade", "sell", "warning", "concern",
    "drop", "dropped", "drops", "fell", "fall", "falls", "crash", "plunge", "slump", "deteriorate",
    "sink", "sinks", "sinking", "tumble", "tumbles", "plummet", "plummets",
    "decrease", "decreases", "decreased", "lower", "lowers", "lowered",
    # Financial events
    "reject", "rejected", "deny", "denied", "lawsuit", "litigation",
    "investigation", "subpoena", "fraud", "default", "bankruptcy",
    "delisting", "dilution", "offering", "secondary", "shelf",
    "chapter 11", "chapter 7", "insolvent", "insolvency",
    # Legal/Class action
    "class action", "securities class action", "securities fraud",
    "shareholder lawsuit", "investor lawsuit", "plaintiffs",
    "allegations", "alleged", "alleges", "misleading", "misrepresented",
    "pomerantz", "rosen law", "levi & korsinsky", "bernstein liebhard",
    "schall law", "kessler topaz", "deadline", "important deadline",
    "encourages investors", "secure counsel", "investigates claims",
    # SEC/Insider
    "sale", "sold", "insider sell", "disposal", "decreased position",
    "terminated", "resigned", "departure", "layoff", "layoffs", "restructuring",
    "insider selling", "ceo sells", "cfo sells", "directors sell",
    "cuts", "cutting", "cut jobs", "workforce reduction", "headcount reduction",
    # Earnings/Financial
    "misses", "disappoints", "disappointing", "shortfall", "below expectations",
    "lowers guidance", "cuts guidance", "withdraws guidance", "suspends dividend",
    "cuts dividend", "losses widen", "margin compression", "cost overruns",
    # Regulatory
    "fda rejection", "fda rejects", "complete response letter", "crl",
    "warning letter", "consent decree", "enforcement action",
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
        positive_count = 0.0
        negative_count = 0.0
        matched_positive = []
        matched_negative = []

        # Check for multi-word phrases first (higher weight)
        for phrase in self.positive_words:
            if " " in phrase and phrase in text_lower:
                positive_count += 3.0  # Phrases get extra weight
                matched_positive.append(phrase)
        for phrase in self.negative_words:
            if " " in phrase and phrase in text_lower:
                negative_count += 3.0
                matched_negative.append(phrase)

        # Count individual words with modifier detection
        for i, word in enumerate(words):
            modifier = 1.0
            if i > 0 and words[i-1] in self.modifiers:
                modifier = self.modifiers[words[i-1]]

            if word in self.positive_words and word not in matched_positive:
                positive_count += modifier
                matched_positive.append(word)
            elif word in self.negative_words and word not in matched_negative:
                negative_count += modifier
                matched_negative.append(word)

        # Calculate score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.3
        else:
            # Use a formula that produces stronger directional scores
            raw_score = (positive_count - negative_count) / total
            # Amplify the score while keeping it bounded
            score = raw_score * min(1.0, 0.5 + total * 0.15)
            # Higher confidence with more matches
            confidence = min(0.95, 0.5 + (total * 0.08))

        # Clamp score
        score = max(-1.0, min(1.0, score))

        # Determine label with lower threshold
        if score > 0.05:
            label = "positive"
        elif score < -0.05:
            label = "negative"
        else:
            label = "neutral"

        # Calculate probabilities based on score
        if label == "positive":
            pos_prob = min(0.9, 0.5 + abs(score) * 0.4)
            probabilities = {
                "positive": pos_prob,
                "negative": (1 - pos_prob) * 0.3,
                "neutral": (1 - pos_prob) * 0.7,
            }
        elif label == "negative":
            neg_prob = min(0.9, 0.5 + abs(score) * 0.4)
            probabilities = {
                "positive": (1 - neg_prob) * 0.3,
                "negative": neg_prob,
                "neutral": (1 - neg_prob) * 0.7,
            }
        else:
            probabilities = {
                "positive": 0.3,
                "negative": 0.3,
                "neutral": 0.4,
            }

        logger.debug(
            "Sentiment analyzed",
            text_preview=text[:50],
            positive_matches=matched_positive[:5],
            negative_matches=matched_negative[:5],
            score=score,
            label=label,
        )

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
