"""Tests for processing modules."""

import pytest
from datetime import datetime, timezone


class TestEntityExtraction:
    """Test entity extraction."""

    def test_ticker_extraction(self):
        """Test extracting ticker symbols from text."""
        from backend.processing.ner import EntityExtractor

        extractor = EntityExtractor(use_spacy=False)

        text = "Check out $AAPL and $MSFT - they're both doing great!"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers
        assert "MSFT" in entities.tickers

    def test_ticker_extraction_without_cashtag(self):
        """Test extracting tickers without $ prefix."""
        from backend.processing.ner import EntityExtractor

        extractor = EntityExtractor(use_spacy=False)

        text = "Apple (AAPL) reported earnings today"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers

    def test_money_extraction(self):
        """Test extracting monetary amounts."""
        from backend.processing.ner import EntityExtractor

        extractor = EntityExtractor(use_spacy=False)

        text = "The company raised $5.2M in funding"
        entities = extractor.extract(text)

        assert len(entities.money) > 0

    def test_excludes_common_words(self):
        """Test that common words are not extracted as tickers."""
        from backend.processing.ner import EntityExtractor

        extractor = EntityExtractor(use_spacy=False)

        text = "The CEO said US markets are doing well"
        entities = extractor.extract(text)

        assert "CEO" not in entities.tickers
        assert "US" not in entities.tickers


class TestSentimentAnalysis:
    """Test sentiment analysis."""

    def test_simple_sentiment_positive(self):
        """Test positive sentiment detection."""
        from backend.processing.sentiment import SimpleSentimentService

        service = SimpleSentimentService()
        result = service.analyze("Great earnings beat! Stock is soaring!")

        assert result.label in ["positive", "neutral"]
        assert result.score >= 0

    def test_simple_sentiment_negative(self):
        """Test negative sentiment detection."""
        from backend.processing.sentiment import SimpleSentimentService

        service = SimpleSentimentService()
        result = service.analyze("Terrible loss, stock is crashing hard")

        assert result.label in ["negative", "neutral"]
        assert result.score <= 0

    def test_sentiment_confidence(self):
        """Test sentiment confidence is within range."""
        from backend.processing.sentiment import SimpleSentimentService

        service = SimpleSentimentService()
        result = service.analyze("This is a neutral statement about the market")

        assert 0 <= result.confidence <= 1


class TestEventClassification:
    """Test event classification."""

    def test_classify_earnings_beat(self):
        """Test classifying earnings beat events."""
        from backend.processing.classification import EventClassifier

        classifier = EventClassifier()
        text = "Apple beats earnings expectations by 20%"
        result = classifier.classify(text)

        assert result.event_type.value == "EARNINGS_BEAT"

    def test_classify_insider_buy(self):
        """Test classifying insider buying events."""
        from backend.processing.classification import EventClassifier

        classifier = EventClassifier()
        text = "CEO purchased 50,000 shares at $150"
        result = classifier.classify(text)

        assert result.event_type.value == "INSIDER_BUY"

    def test_classify_fda_approval(self):
        """Test classifying FDA approval events."""
        from backend.processing.classification import EventClassifier

        classifier = EventClassifier()
        text = "FDA approves new drug treatment for cancer"
        result = classifier.classify(text)

        assert result.event_type.value == "FDA_APPROVAL"

    def test_classification_confidence(self):
        """Test classification confidence is valid."""
        from backend.processing.classification import EventClassifier

        classifier = EventClassifier()
        text = "Some random text about a company"
        result = classifier.classify(text)

        assert 0 <= result.confidence <= 1


class TestAlphaCalculation:
    """Test alpha score calculation."""

    def test_alpha_calculation_high_signal(self):
        """Test alpha calculation for high-signal events."""
        from backend.processing.classification import EventClassification, EventType
        from backend.processing.sentiment.finbert_service import SentimentResult
        from backend.processing.scoring import AlphaCalculator

        calculator = AlphaCalculator()

        classification = EventClassification(
            event_type=EventType.INSIDER_BUY,
            confidence=0.95,
            matched_patterns=["insider purchase"],
            is_material=True,
            base_signal_weight=0.8,
        )

        sentiment = SentimentResult(
            label="positive",
            score=0.8,
            confidence=0.9,
            probabilities={"positive": 0.8, "negative": 0.1, "neutral": 0.1},
        )

        alpha = calculator.calculate(
            classification=classification,
            sentiment=sentiment,
            source="sec_edgar",
            event_time=datetime.now(timezone.utc),
            ticker="TEST",
        )

        assert abs(alpha.score) > 0.3  # Should be significant
        assert alpha.direction in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert alpha.urgency_level in ["critical", "high", "medium", "low"]

    def test_alpha_calculation_low_signal(self):
        """Test alpha calculation for low-signal events."""
        from backend.processing.classification import EventClassification, EventType
        from backend.processing.scoring import AlphaCalculator

        calculator = AlphaCalculator()

        classification = EventClassification(
            event_type=EventType.NEWS,
            confidence=0.5,
            matched_patterns=[],
            is_material=False,
            base_signal_weight=0.1,
        )

        alpha = calculator.calculate(
            classification=classification,
            sentiment=None,
            source="unknown",
            event_time=datetime.now(timezone.utc),
            ticker="TEST",
        )

        assert abs(alpha.score) < 0.5  # Should be lower


class TestUrgencyScoring:
    """Test urgency scoring."""

    def test_critical_urgency_for_insider_trade(self):
        """Test critical urgency for insider trades."""
        from backend.processing.classification import EventType, UrgencyScorer

        scorer = UrgencyScorer()
        urgency = scorer.score(
            event_type=EventType.INSIDER_BUY,
            source="sec_edgar",
            event_time=datetime.now(timezone.utc),
        )

        assert urgency.level in ["critical", "high"]

    def test_low_urgency_for_old_news(self):
        """Test low urgency for old events."""
        from datetime import timedelta
        from backend.processing.classification import EventType, UrgencyScorer

        scorer = UrgencyScorer()
        old_time = datetime.now(timezone.utc) - timedelta(days=7)

        urgency = scorer.score(
            event_type=EventType.NEWS,
            source="blog",
            event_time=old_time,
        )

        assert urgency.level in ["low", "medium"]
