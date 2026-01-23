"""Tests for NLP tasks - entity extraction and sentiment analysis."""

from unittest.mock import MagicMock, patch

import pytest

from backend.processing.ner.entity_extractor import (
    EntityExtractor,
    ExtractedEntities,
    extract_entities,
)


class TestExtractedEntities:
    """Tests for ExtractedEntities dataclass."""

    def test_default_values(self):
        """Test that ExtractedEntities has correct default values."""
        entities = ExtractedEntities()
        assert entities.tickers == []
        assert entities.companies == []
        assert entities.people == []
        assert entities.money == []
        assert entities.percentages == []
        assert entities.dates == []
        assert entities.locations == []

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entities = ExtractedEntities(
            tickers=["AAPL", "MSFT"],
            companies=["Apple Inc.", "Microsoft"],
            people=["Tim Cook"],
            money=[{"raw": "$1 million", "value": 1000000, "currency": "USD"}],
            percentages=["5%", "10.5%"],
            dates=["2024-01-01"],
            locations=["Cupertino"],
        )
        result = entities.to_dict()

        assert result["tickers"] == ["AAPL", "MSFT"]
        assert result["companies"] == ["Apple Inc.", "Microsoft"]
        assert result["people"] == ["Tim Cook"]
        assert len(result["money"]) == 1
        assert result["percentages"] == ["5%", "10.5%"]


class TestEntityExtractorTickerExtraction:
    """Tests for ticker extraction functionality."""

    def test_extract_cashtag_ticker(self):
        """Test extraction of $TICKER format."""
        extractor = EntityExtractor(use_spacy=False)
        text = "I'm buying $AAPL today!"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers

    def test_extract_multiple_cashtag_tickers(self):
        """Test extraction of multiple $TICKER symbols."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Looking at $AAPL, $MSFT, and $GOOG for my portfolio"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers
        assert "MSFT" in entities.tickers
        assert "GOOG" in entities.tickers

    def test_extract_exchange_prefixed_ticker(self):
        """Test extraction of EXCHANGE:TICKER format."""
        extractor = EntityExtractor(use_spacy=False)
        text = "NYSE:AAPL is trading higher today"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers

    def test_extract_nasdaq_ticker(self):
        """Test extraction of NASDAQ prefixed ticker."""
        extractor = EntityExtractor(use_spacy=False)
        text = "NASDAQ:TSLA hit a new high"
        entities = extractor.extract(text)

        assert "TSLA" in entities.tickers

    def test_extract_otc_ticker(self):
        """Test extraction of OTC prefixed ticker."""
        extractor = EntityExtractor(use_spacy=False)
        text = "OTCQB: ABCD is showing strong momentum"
        entities = extractor.extract(text)

        assert "ABCD" in entities.tickers

    def test_excludes_common_abbreviations(self):
        """Test that common abbreviations are excluded from tickers."""
        extractor = EntityExtractor(use_spacy=False)
        text = "The CEO and CFO met with the SEC about the IPO"
        entities = extractor.extract(text)

        assert "CEO" not in entities.tickers
        assert "CFO" not in entities.tickers
        assert "SEC" not in entities.tickers
        assert "IPO" not in entities.tickers

    def test_excludes_single_letter_tickers(self):
        """Test that single letter common words are excluded."""
        extractor = EntityExtractor(use_spacy=False)
        text = "$A great $I idea"
        entities = extractor.extract(text)

        assert "A" not in entities.tickers
        assert "I" not in entities.tickers

    def test_limits_ticker_count(self):
        """Test that ticker count is limited."""
        extractor = EntityExtractor(use_spacy=False)
        # Create text with many tickers
        tickers = [f"${chr(65 + i//26)}{chr(65 + i%26)}XY" for i in range(30)]
        text = " ".join(tickers)
        entities = extractor.extract(text)

        # Should be limited to 20
        assert len(entities.tickers) <= 20


class TestEntityExtractorMoneyExtraction:
    """Tests for money amount extraction."""

    def test_extract_simple_dollar_amount(self):
        """Test extraction of simple dollar amounts."""
        extractor = EntityExtractor(use_spacy=False)
        text = "The deal was worth $5,000,000"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        assert any("5,000,000" in m["raw"] for m in entities.money)

    def test_extract_million_suffix(self):
        """Test extraction of amounts with million suffix."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Revenue reached $50 million last quarter"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        money_item = entities.money[0]
        assert money_item["value"] == 50_000_000

    def test_extract_billion_suffix(self):
        """Test extraction of amounts with billion suffix."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Market cap is $2.5 billion"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        money_item = entities.money[0]
        assert money_item["value"] == 2_500_000_000

    def test_extract_thousand_suffix(self):
        """Test extraction of amounts with thousand suffix."""
        extractor = EntityExtractor(use_spacy=False)
        text = "The fine was $500 thousand"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        money_item = entities.money[0]
        assert money_item["value"] == 500_000

    def test_extract_abbreviated_million(self):
        """Test extraction with M abbreviation."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Profit was $10M this year"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        money_item = entities.money[0]
        assert money_item["value"] == 10_000_000

    def test_extract_abbreviated_billion(self):
        """Test extraction with B abbreviation."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Total investment: $1.5B"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        money_item = entities.money[0]
        assert money_item["value"] == 1_500_000_000

    def test_money_has_currency(self):
        """Test that extracted money includes currency."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Cost: $100"
        entities = extractor.extract(text)

        assert len(entities.money) > 0
        assert entities.money[0]["currency"] == "USD"


class TestEntityExtractorPercentageExtraction:
    """Tests for percentage extraction."""

    def test_extract_simple_percentage(self):
        """Test extraction of simple percentage."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Stock rose 5% today"
        entities = extractor.extract(text)

        assert "5%" in entities.percentages

    def test_extract_decimal_percentage(self):
        """Test extraction of decimal percentage."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Interest rate is 3.75%"
        entities = extractor.extract(text)

        assert "3.75%" in entities.percentages

    def test_extract_multiple_percentages(self):
        """Test extraction of multiple percentages."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Grew 10% YoY and 2.5% QoQ"
        entities = extractor.extract(text)

        assert "10%" in entities.percentages
        assert "2.5%" in entities.percentages


class TestEntityExtractorWithContext:
    """Tests for extraction with surrounding context."""

    def test_extract_with_context_returns_context(self):
        """Test that context is returned around entities."""
        extractor = EntityExtractor(use_spacy=False)
        text = "The company announced that $AAPL is expanding operations significantly"
        results = extractor.extract_with_context(text, window_size=20)

        ticker_results = [r for r in results if r["type"] == "TICKER"]
        assert len(ticker_results) > 0
        assert "context" in ticker_results[0]
        assert "AAPL" in ticker_results[0]["context"]

    def test_extract_with_context_includes_position(self):
        """Test that position is included in context results."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Looking at $MSFT today"
        results = extractor.extract_with_context(text)

        ticker_results = [r for r in results if r["type"] == "TICKER"]
        assert len(ticker_results) > 0
        assert "position" in ticker_results[0]
        assert isinstance(ticker_results[0]["position"], int)


class TestConvenienceFunction:
    """Tests for the convenience extract_entities function."""

    def test_extract_entities_without_spacy(self):
        """Test convenience function without spaCy."""
        text = "$AAPL reported earnings of $50 million, up 10%"
        entities = extract_entities(text, use_spacy=False)

        assert isinstance(entities, ExtractedEntities)
        assert "AAPL" in entities.tickers
        assert len(entities.money) > 0
        assert "10%" in entities.percentages

    def test_extract_entities_returns_correct_type(self):
        """Test that convenience function returns ExtractedEntities."""
        entities = extract_entities("Some text", use_spacy=False)
        assert isinstance(entities, ExtractedEntities)


class TestEntityExtractionIntegration:
    """Integration tests for entity extraction in NLP tasks context."""

    def test_extract_from_sec_filing_text(self, sample_filing_data: dict):
        """Test entity extraction from SEC filing-like text."""
        extractor = EntityExtractor(use_spacy=False)
        text = f"{sample_filing_data['title']} - {sample_filing_data['company_name']}"
        entities = extractor.extract(text)

        # Should extract entities from filing text
        assert isinstance(entities.tickers, list)
        assert isinstance(entities.companies, list)

    def test_extract_from_social_post(self, sample_social_post_data: dict):
        """Test entity extraction from social media post."""
        extractor = EntityExtractor(use_spacy=False)
        text = f"{sample_social_post_data['title']} {sample_social_post_data['content']}"
        entities = extractor.extract(text)

        # Should find the $AAPL ticker
        assert "AAPL" in entities.tickers

    def test_extract_from_earnings_headline(self, sample_event_data: dict):
        """Test entity extraction from earnings headline."""
        extractor = EntityExtractor(use_spacy=False)
        # Modify headline to include cashtag
        text = f"${sample_event_data['ticker']} - {sample_event_data['headline']}"
        entities = extractor.extract(text)

        assert sample_event_data["ticker"] in entities.tickers


class TestEntityExtractorEdgeCases:
    """Tests for edge cases in entity extraction."""

    def test_empty_text(self):
        """Test extraction from empty text."""
        extractor = EntityExtractor(use_spacy=False)
        entities = extractor.extract("")

        assert entities.tickers == []
        assert entities.money == []
        assert entities.percentages == []

    def test_whitespace_only_text(self):
        """Test extraction from whitespace-only text."""
        extractor = EntityExtractor(use_spacy=False)
        entities = extractor.extract("   \n\t   ")

        assert entities.tickers == []

    def test_very_long_text(self):
        """Test extraction from very long text."""
        extractor = EntityExtractor(use_spacy=False)
        text = "$AAPL " * 1000 + "$MSFT " * 1000
        entities = extractor.extract(text)

        # Should still work and apply limits
        assert len(entities.tickers) <= 20
        assert "AAPL" in entities.tickers
        assert "MSFT" in entities.tickers

    def test_special_characters_in_text(self):
        """Test extraction from text with special characters."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Check out $AAPL!!! It's up 10%!!! Worth $1M+++ wow"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers
        assert "10%" in entities.percentages

    def test_case_sensitivity(self):
        """Test that ticker extraction handles case correctly."""
        extractor = EntityExtractor(use_spacy=False)
        text = "$aapl and $MSFT and $gOOg"
        entities = extractor.extract(text)

        # All should be uppercase in results
        for ticker in entities.tickers:
            assert ticker == ticker.upper()

    def test_unicode_text(self):
        """Test extraction from text with unicode characters."""
        extractor = EntityExtractor(use_spacy=False)
        text = "Apple $AAPL stock rose 5% to $150"
        entities = extractor.extract(text)

        assert "AAPL" in entities.tickers
        assert "5%" in entities.percentages


class TestCIKExtraction:
    """Tests for CIK extraction helper functions."""

    def test_extract_cik_from_direct_field(self):
        """Test CIK extraction from direct cik field."""
        from backend.workers.tasks.nlp_tasks import _extract_cik_from_data

        data = {"cik": "0001234567"}
        result = _extract_cik_from_data(data)

        assert result == "1234567"

    def test_extract_cik_from_url(self):
        """Test CIK extraction from filing URL."""
        from backend.workers.tasks.nlp_tasks import _extract_cik_from_data

        data = {
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456724000001"
        }
        result = _extract_cik_from_data(data)

        assert result == "1234567"

    def test_extract_cik_strips_leading_zeros(self):
        """Test that leading zeros are stripped from CIK."""
        from backend.workers.tasks.nlp_tasks import _extract_cik_from_data

        data = {"cik": "0000001234"}
        result = _extract_cik_from_data(data)

        assert result == "1234"

    def test_extract_cik_returns_none_when_missing(self):
        """Test that None is returned when CIK is not found."""
        from backend.workers.tasks.nlp_tasks import _extract_cik_from_data

        data = {"headline": "Some text without CIK"}
        result = _extract_cik_from_data(data)

        assert result is None
