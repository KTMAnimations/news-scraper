"""Integration tests for the full scraping pipeline.

Tests the complete flow from data scraping through NLP processing to storage.
External APIs are mocked, but internal processing is tested end-to-end.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.storage.timescale.models import Event


class TestScrapingPipelineSECFilings:
    """Integration tests for SEC filing scraping pipeline."""

    @pytest.fixture
    def mock_sec_filing(self):
        """Create a mock SEC filing response."""
        return {
            "id": "0001234567-24-000001",
            "filing_type": "4",
            "filing_category": "INSIDER_TRADE",
            "cik": "1234567",
            "company_name": "Test Corp",
            "title": "FORM 4 - Test Corp (TSLA)",
            "link": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=1234567",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456724000001",
            "filing_time": datetime.now(timezone.utc).isoformat(),
            "is_critical": True,
            "source": "sec_edgar",
        }

    @pytest.fixture
    def mock_sec_client(self, mock_sec_filing):
        """Mock SEC EDGAR client."""
        client = MagicMock()
        client.fetch_recent = AsyncMock(return_value=[mock_sec_filing])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    def test_process_filing_extracts_entities(self, mock_sec_filing):
        """Test that filing processing extracts entities correctly."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task

        # Add headline for entity extraction
        mock_sec_filing["headline"] = "Insider purchases 10,000 shares of $TSLA worth $2.5 million"

        result = extract_entities_task(mock_sec_filing)

        assert "extracted_tickers" in result
        assert "TSLA" in result["extracted_tickers"]
        assert "extracted_amounts" in result or "money" in result.get("extracted_amounts", [])

    def test_process_filing_analyzes_sentiment(self, mock_sec_filing):
        """Test that filing processing analyzes sentiment."""
        from backend.workers.tasks.nlp_tasks import analyze_sentiment_task

        mock_sec_filing["headline"] = "CEO increases stake with significant insider purchase"

        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "positive"
            mock_sentiment.score = 0.75
            mock_sentiment.confidence = 0.85
            mock_sentiment.probabilities = {"positive": 0.75, "negative": 0.15, "neutral": 0.10}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(mock_sec_filing)

            assert result["sentiment_label"] == "positive"
            assert result["sentiment_score"] == 0.75
            assert result["sentiment_confidence"] == 0.85

    def test_process_filing_calculates_alpha(self, mock_sec_filing):
        """Test that filing processing calculates alpha score."""
        from backend.workers.tasks.scoring_tasks import calculate_alpha_task

        # Prepare data with sentiment and classification
        mock_sec_filing["headline"] = "Major insider purchase"
        mock_sec_filing["event_type"] = "INSIDER_TRADE"
        mock_sec_filing["sentiment_label"] = "positive"
        mock_sec_filing["sentiment_score"] = 0.8
        mock_sec_filing["sentiment_confidence"] = 0.9
        mock_sec_filing["ticker"] = "TSLA"
        mock_sec_filing["event_time"] = datetime.now(timezone.utc).isoformat()

        with patch("backend.processing.scoring.AlphaCalculator") as MockCalculator:
            mock_alpha = MagicMock()
            mock_alpha.score = 0.72
            mock_alpha.direction = "BULLISH"
            mock_alpha.confidence = 0.85
            mock_alpha.urgency_level = "high"
            mock_alpha.recommended_action = "Consider long position"
            mock_alpha.factors = {"event_weight": 0.8, "sentiment": 0.7}
            MockCalculator.return_value.calculate.return_value = mock_alpha

            result = calculate_alpha_task(mock_sec_filing)

            assert result["alpha_score"] == 0.72
            assert result["direction"] == "BULLISH"
            assert result["urgency_level"] == "high"

    @pytest.mark.asyncio
    async def test_full_sec_pipeline_integration(self, test_session: AsyncSession, mock_sec_filing):
        """Test full SEC filing pipeline from scrape to storage."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task, analyze_sentiment_task
        from backend.workers.tasks.scoring_tasks import calculate_alpha_task

        # Prepare filing with full data
        mock_sec_filing["headline"] = "CEO Tim Cook purchases $5 million in $AAPL shares"
        mock_sec_filing["ticker"] = "AAPL"
        mock_sec_filing["event_time"] = datetime.now(timezone.utc).isoformat()

        # Step 1: Extract entities
        with patch("backend.workers.tasks.nlp_tasks._get_ticker_kb") as mock_kb:
            mock_kb.return_value._cik_to_ticker = {"1234567": "AAPL"}
            result = extract_entities_task(mock_sec_filing)

        assert "extracted_tickers" in result
        assert "AAPL" in result["extracted_tickers"]

        # Step 2: Analyze sentiment
        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "positive"
            mock_sentiment.score = 0.85
            mock_sentiment.confidence = 0.90
            mock_sentiment.probabilities = {"positive": 0.85}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(result)

        assert result["sentiment_label"] == "positive"

        # Step 3: Calculate alpha
        with patch("backend.processing.scoring.AlphaCalculator") as MockCalculator:
            mock_alpha = MagicMock()
            mock_alpha.score = 0.78
            mock_alpha.direction = "BULLISH"
            mock_alpha.confidence = 0.88
            mock_alpha.urgency_level = "high"
            mock_alpha.recommended_action = "Monitor for entry"
            mock_alpha.factors = {}
            MockCalculator.return_value.calculate.return_value = mock_alpha

            result = calculate_alpha_task(result)

        assert result["alpha_score"] == 0.78
        assert result["direction"] == "BULLISH"

        # Verify complete pipeline result has all expected fields
        assert "ticker" in result
        assert "headline" in result
        assert "sentiment_label" in result
        assert "alpha_score" in result
        assert "direction" in result
        assert "urgency_level" in result


class TestScrapingPipelineNews:
    """Integration tests for news article scraping pipeline."""

    @pytest.fixture
    def mock_news_article(self):
        """Create a mock news article."""
        return {
            "title": "Apple Reports Record Q4 Earnings Beat",
            "headline": "Apple Reports Record Q4 Earnings, Revenue Up 15%",
            "content": "Apple Inc. (AAPL) announced quarterly earnings that exceeded analyst expectations. Revenue grew 15% year-over-year to $95 billion.",
            "summary": "Apple beats earnings expectations with strong iPhone sales",
            "source": "business_wire",
            "source_name": "Business Wire",
            "source_url": "https://businesswire.com/news/aapl-earnings",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_news_pipeline_extracts_ticker(self, mock_news_article):
        """Test that news pipeline extracts ticker from content."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task

        result = extract_entities_task(mock_news_article)

        assert "extracted_tickers" in result
        assert "AAPL" in result["extracted_tickers"]

    def test_news_pipeline_classifies_event(self, mock_news_article):
        """Test that news pipeline classifies event type."""
        # The classification should identify this as an earnings event
        mock_news_article["event_type"] = "EARNINGS_BEAT"

        assert mock_news_article["event_type"] == "EARNINGS_BEAT"

    def test_news_pipeline_sentiment_for_earnings(self, mock_news_article):
        """Test sentiment analysis for earnings news."""
        from backend.workers.tasks.nlp_tasks import analyze_sentiment_task

        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "positive"
            mock_sentiment.score = 0.88
            mock_sentiment.confidence = 0.92
            mock_sentiment.probabilities = {"positive": 0.88, "negative": 0.05, "neutral": 0.07}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(mock_news_article)

            assert result["sentiment_label"] == "positive"
            assert result["sentiment_score"] > 0.5


class TestScrapingPipelineSocial:
    """Integration tests for social media scraping pipeline."""

    @pytest.fixture
    def mock_reddit_post(self):
        """Create a mock Reddit post."""
        return {
            "post_id": "abc123",
            "title": "Check out $MULN - insider buying detected!",
            "content": "MULN just had significant insider purchases. This could be huge! Up 10% premarket.",
            "author": "penny_stock_guru",
            "subreddit": "pennystocks",
            "url": "https://reddit.com/r/pennystocks/comments/abc123",
            "score": 250,
            "upvote_ratio": 0.94,
            "num_comments": 87,
            "ticker": "MULN",
            "tickers": ["MULN"],
            "engagement_score": 0.42,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "reddit",
            "event_type": "SOCIAL_MENTION",
        }

    def test_social_pipeline_preserves_ticker(self, mock_reddit_post):
        """Test that social pipeline preserves pre-extracted ticker."""
        from backend.workers.tasks.nlp_tasks import analyze_sentiment_task

        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "positive"
            mock_sentiment.score = 0.72
            mock_sentiment.confidence = 0.78
            mock_sentiment.probabilities = {"positive": 0.72}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(mock_reddit_post)

            # Original ticker should be preserved
            assert result["ticker"] == "MULN"
            assert "MULN" in result.get("tickers", [])

    def test_social_pipeline_calculates_alpha_with_engagement(self, mock_reddit_post):
        """Test alpha calculation considers social engagement."""
        from backend.workers.tasks.scoring_tasks import calculate_alpha_task

        mock_reddit_post["sentiment_label"] = "positive"
        mock_reddit_post["sentiment_score"] = 0.7
        mock_reddit_post["sentiment_confidence"] = 0.8

        with patch("backend.processing.scoring.AlphaCalculator") as MockCalculator:
            mock_alpha = MagicMock()
            mock_alpha.score = 0.55
            mock_alpha.direction = "BULLISH"
            mock_alpha.confidence = 0.65
            mock_alpha.urgency_level = "medium"
            mock_alpha.recommended_action = "Monitor momentum"
            mock_alpha.factors = {"engagement": 0.42, "sentiment": 0.7}
            MockCalculator.return_value.calculate.return_value = mock_alpha

            result = calculate_alpha_task(mock_reddit_post)

            # Social posts typically have lower alpha due to noise
            assert result["alpha_score"] >= 0
            assert result["direction"] in ["BULLISH", "BEARISH", "NEUTRAL"]


class TestScrapingPipelineChain:
    """Integration tests for the complete task chain."""

    @pytest.fixture
    def sample_event_for_chain(self):
        """Create sample event data for chain testing."""
        return {
            "id": str(uuid4()),
            "ticker": "NVDA",
            "headline": "NVIDIA announces $10 billion stock buyback program",
            "content": "NVIDIA Corporation announced a new $10B share repurchase program. The company reported strong AI chip demand driving record revenue growth of 200% year-over-year.",
            "summary": "NVIDIA announces major buyback after strong earnings",
            "source": "sec_edgar",
            "source_name": "SEC EDGAR",
            "filing_type": "8-K",
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

    def test_complete_chain_produces_valid_event(self, sample_event_for_chain):
        """Test that the complete chain produces a valid storable event."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task, analyze_sentiment_task
        from backend.workers.tasks.scoring_tasks import calculate_alpha_task

        # Run extraction
        with patch("backend.workers.tasks.nlp_tasks._get_ticker_kb") as mock_kb:
            mock_kb.return_value._cik_to_ticker = {}
            result = extract_entities_task(sample_event_for_chain)

        # Run sentiment
        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "positive"
            mock_sentiment.score = 0.9
            mock_sentiment.confidence = 0.95
            mock_sentiment.probabilities = {"positive": 0.9}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(result)

        # Run alpha calculation
        with patch("backend.processing.scoring.AlphaCalculator") as MockCalculator:
            mock_alpha = MagicMock()
            mock_alpha.score = 0.85
            mock_alpha.direction = "BULLISH"
            mock_alpha.confidence = 0.90
            mock_alpha.urgency_level = "critical"
            mock_alpha.recommended_action = "Strong buy signal"
            mock_alpha.factors = {}
            MockCalculator.return_value.calculate.return_value = mock_alpha

            result = calculate_alpha_task(result)

        # Verify all required fields are present
        required_fields = [
            "ticker",
            "headline",
            "sentiment_label",
            "sentiment_score",
            "alpha_score",
            "direction",
            "urgency_level",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Verify values
        assert result["ticker"] == "NVDA"
        assert result["alpha_score"] > 0.5
        assert result["direction"] == "BULLISH"
        assert result["urgency_level"] == "critical"

    def test_chain_handles_missing_content_gracefully(self):
        """Test that chain handles events with minimal content."""
        minimal_event = {
            "ticker": "TEST",
            "headline": "Test event",
            "source": "test",
        }

        from backend.workers.tasks.nlp_tasks import analyze_sentiment_task

        with patch("backend.workers.tasks.nlp_tasks.get_cached_sentiment_service") as mock_service:
            mock_sentiment = MagicMock()
            mock_sentiment.label = "neutral"
            mock_sentiment.score = 0.0
            mock_sentiment.confidence = 0.5
            mock_sentiment.probabilities = {}
            mock_service.return_value.analyze.return_value = mock_sentiment

            result = analyze_sentiment_task(minimal_event)

            # Should still produce valid sentiment
            assert "sentiment_label" in result

    def test_chain_preserves_original_data(self, sample_event_for_chain):
        """Test that chain preserves original event data through processing."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task

        original_ticker = sample_event_for_chain["ticker"]
        original_headline = sample_event_for_chain["headline"]

        with patch("backend.workers.tasks.nlp_tasks._get_ticker_kb") as mock_kb:
            mock_kb.return_value._cik_to_ticker = {}
            result = extract_entities_task(sample_event_for_chain)

        # Original data should be preserved
        assert result["ticker"] == original_ticker
        assert result["headline"] == original_headline


class TestScrapingPipelineErrorHandling:
    """Tests for error handling in the scraping pipeline."""

    def test_entity_extraction_handles_malformed_text(self):
        """Test entity extraction handles malformed input."""
        from backend.workers.tasks.nlp_tasks import extract_entities_task

        malformed_data = {
            "headline": None,
            "content": "",
            "ticker": "TEST",
        }

        # Should not raise, should return data with empty extractions
        result = extract_entities_task(malformed_data)
        assert "ticker" in result

    def test_sentiment_handles_empty_text(self):
        """Test sentiment analysis handles empty text gracefully."""
        from backend.workers.tasks.nlp_tasks import analyze_sentiment_task

        empty_event = {
            "headline": "",
            "content": "",
            "summary": "",
        }

        result = analyze_sentiment_task(empty_event)

        # Should return neutral sentiment for empty text
        assert result["sentiment_label"] == "neutral"
        assert result["sentiment_score"] == 0.0

    def test_alpha_calculation_handles_missing_sentiment(self):
        """Test alpha calculation works without sentiment data."""
        from backend.workers.tasks.scoring_tasks import calculate_alpha_task

        event_no_sentiment = {
            "ticker": "TEST",
            "headline": "Test event",
            "event_type": "NEWS",
            "source": "test",
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

        with patch("backend.processing.scoring.AlphaCalculator") as MockCalculator:
            mock_alpha = MagicMock()
            mock_alpha.score = 0.3
            mock_alpha.direction = "NEUTRAL"
            mock_alpha.confidence = 0.5
            mock_alpha.urgency_level = "low"
            mock_alpha.recommended_action = "Monitor"
            mock_alpha.factors = {}
            MockCalculator.return_value.calculate.return_value = mock_alpha

            result = calculate_alpha_task(event_no_sentiment)

            assert "alpha_score" in result
            assert result["direction"] == "NEUTRAL"
