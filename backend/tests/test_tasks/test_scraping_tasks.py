"""Tests for scraping Celery tasks."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.workers.tasks.scraping_tasks import (
    run_async,
    process_filing,
    process_article,
    process_social_mention,
    process_event,
    backfill_data,
)


class TestRunAsync:
    """Tests for the run_async helper function."""

    def test_run_async_simple_coroutine(self):
        """Test running a simple async coroutine."""
        async def simple_coro():
            return "result"

        result = run_async(simple_coro())
        assert result == "result"

    def test_run_async_with_exception(self):
        """Test run_async propagates exceptions."""
        async def failing_coro():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            run_async(failing_coro())


class TestProcessFiling:
    """Tests for process_filing task."""

    def test_process_filing_creates_chain(self):
        """Test process_filing creates correct task chain."""
        filing_data = {
            "ticker": "AAPL",
            "filing_type": "4",
            "source": "sec_edgar",
            "headline": "Form 4 Filing",
        }

        with patch("backend.workers.tasks.scraping_tasks.extract_entities_task") as mock_extract, \
             patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task") as mock_sentiment, \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task") as mock_alpha, \
             patch("backend.workers.tasks.scraping_tasks.store_event_task") as mock_store, \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task") as mock_alerts:

            # Setup chain mocking
            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-123")
            mock_extract.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_filing(filing_data)

            assert result["status"] == "processing"
            assert result["source"] == "sec_edgar"
            assert result["ticker"] == "AAPL"
            assert "task_id" in result

    def test_process_filing_default_source(self):
        """Test process_filing uses default source."""
        filing_data = {"headline": "Filing"}

        with patch("backend.workers.tasks.scraping_tasks.extract_entities_task") as mock_extract, \
             patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task"), \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task"), \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-123")
            mock_extract.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_filing(filing_data)

            assert result["source"] == "sec_edgar"


class TestProcessArticle:
    """Tests for process_article task."""

    def test_process_article_creates_chain(self):
        """Test process_article creates correct task chain."""
        article_data = {
            "ticker": "MSFT",
            "source": "prnewswire",
            "headline": "Press Release",
        }

        with patch("backend.workers.tasks.scraping_tasks.extract_entities_task") as mock_extract, \
             patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task"), \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task"), \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-456")
            mock_extract.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_article(article_data)

            assert result["status"] == "processing"
            assert result["source"] == "prnewswire"
            assert result["ticker"] == "MSFT"

    def test_process_article_default_source(self):
        """Test process_article uses default source."""
        article_data = {"headline": "News"}

        with patch("backend.workers.tasks.scraping_tasks.extract_entities_task") as mock_extract, \
             patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task"), \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task"), \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-456")
            mock_extract.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_article(article_data)

            assert result["source"] == "news"


class TestProcessSocialMention:
    """Tests for process_social_mention task."""

    def test_process_social_mention_creates_chain(self):
        """Test process_social_mention creates correct task chain."""
        mention_data = {
            "ticker": "AAPL",
            "source": "reddit",
            "title": "AAPL Discussion",
        }

        with patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task") as mock_sentiment, \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task"), \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-789")
            mock_sentiment.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_social_mention(mention_data)

            assert result["status"] == "processing"
            assert result["source"] == "reddit"
            assert result["ticker"] == "AAPL"

    def test_process_social_mention_default_source(self):
        """Test process_social_mention uses default source."""
        mention_data = {"title": "Stock mention"}

        with patch("backend.workers.tasks.scraping_tasks.analyze_sentiment_task") as mock_sentiment, \
             patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task"), \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-789")
            mock_sentiment.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_social_mention(mention_data)

            assert result["source"] == "social"


class TestProcessEvent:
    """Tests for process_event task."""

    def test_process_event_creates_chain(self):
        """Test process_event creates correct task chain."""
        event_data = {
            "ticker": "GOOG",
            "source": "tier_change",
            "headline": "OTC Tier Upgrade",
        }

        with patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task") as mock_alpha, \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-abc")
            mock_alpha.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_event(event_data)

            assert result["status"] == "processing"
            assert result["source"] == "tier_change"
            assert result["ticker"] == "GOOG"

    def test_process_event_default_source(self):
        """Test process_event uses default source."""
        event_data = {"headline": "Event"}

        with patch("backend.workers.tasks.scraping_tasks.calculate_alpha_task") as mock_alpha, \
             patch("backend.workers.tasks.scraping_tasks.store_event_task"), \
             patch("backend.workers.tasks.scraping_tasks.check_alerts_task"):

            mock_chain = MagicMock()
            mock_chain.apply_async.return_value = MagicMock(id="task-abc")
            mock_alpha.s.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = process_event(event_data)

            assert result["source"] == "event"


class TestBackfillData:
    """Tests for backfill_data task."""

    def test_backfill_data_success(self):
        """Test successful data backfill."""
        mock_filings = [
            {"ticker": "AAPL", "filing_type": "4", "headline": "Filing 1"},
            {"ticker": "AAPL", "filing_type": "8-K", "headline": "Filing 2"},
        ]

        with patch("backend.workers.tasks.scraping_tasks.process_filing") as mock_process:
            mock_process.delay = MagicMock()

            async def mock_get_filings(**kwargs):
                return mock_filings

            # Mock the SECPollingClient
            with patch("backend.ingestion.sec_edgar.SECPollingClient") as MockClient:
                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client.get_company_filings = AsyncMock(return_value=mock_filings)
                MockClient.return_value = mock_client

                result = backfill_data("AAPL", days=30)

        assert result["count"] == 2
        assert result["filings"] == mock_filings
        assert result["error"] is None

    def test_backfill_data_error_handling(self):
        """Test backfill handles errors gracefully."""
        with patch("backend.ingestion.sec_edgar.SECPollingClient") as MockClient:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_company_filings = AsyncMock(
                side_effect=Exception("API Error")
            )
            MockClient.return_value = mock_client

            result = backfill_data("TEST", days=30)

        assert result["error"] == "API Error"
        assert result["filings"] == []
