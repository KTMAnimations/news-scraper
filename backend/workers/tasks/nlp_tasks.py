"""NLP tasks for entity extraction and sentiment analysis."""

from typing import Any

import structlog

from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def extract_entities_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Extract entities from text content.

    Args:
        data: Event data with text content

    Returns:
        Data enriched with extracted entities
    """
    try:
        from backend.processing.ner import EntityExtractor

        # Get text content
        text = ""
        if "headline" in data:
            text = data["headline"]
        if "title" in data:
            text = data.get("title", "") + " " + text
        if "content" in data:
            text = text + " " + data.get("content", "")[:2000]
        if "summary" in data:
            text = text + " " + data.get("summary", "")

        text = text.strip()

        if not text:
            return data

        # Extract entities
        extractor = EntityExtractor(use_spacy=False)  # Use regex for speed
        entities = extractor.extract(text)

        # Enrich data
        data["extracted_tickers"] = entities.tickers
        data["extracted_companies"] = entities.companies
        data["extracted_people"] = entities.people
        data["extracted_amounts"] = entities.money

        # Set primary ticker if not already set
        if not data.get("ticker") and entities.tickers:
            data["ticker"] = entities.tickers[0]

        logger.debug(
            "Entities extracted",
            tickers=entities.tickers,
            companies=len(entities.companies),
        )

        return data

    except Exception as e:
        logger.error("Entity extraction failed", error=str(e))
        raise self.retry(exc=e, countdown=5)


@celery_app.task(bind=True, max_retries=2)
def analyze_sentiment_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Analyze sentiment of text content.

    Args:
        data: Event data with text content

    Returns:
        Data enriched with sentiment analysis
    """
    try:
        from backend.processing.sentiment import SimpleSentimentService

        # Get text for sentiment analysis
        text = data.get("headline", "") or data.get("title", "")
        if not text:
            text = data.get("summary", "") or data.get("content", "")[:500]

        if not text:
            data["sentiment_label"] = "neutral"
            data["sentiment_score"] = 0.0
            data["sentiment_confidence"] = 0.5
            return data

        # Use simple sentiment for worker tasks (FinBERT for batch/GPU)
        service = SimpleSentimentService()
        result = service.analyze(text)

        # Enrich data
        data["sentiment_label"] = result.label
        data["sentiment_score"] = result.score
        data["sentiment_confidence"] = result.confidence
        data["sentiment_probabilities"] = result.probabilities

        logger.debug(
            "Sentiment analyzed",
            label=result.label,
            score=result.score,
        )

        return data

    except Exception as e:
        logger.error("Sentiment analysis failed", error=str(e))
        raise self.retry(exc=e, countdown=5)


@celery_app.task
def batch_analyze_sentiment(texts: list[str]) -> list[dict[str, Any]]:
    """Batch sentiment analysis for multiple texts.

    Args:
        texts: List of texts to analyze

    Returns:
        List of sentiment results
    """
    try:
        from backend.processing.sentiment import get_sentiment_service

        service = get_sentiment_service(use_finbert=True)

        if hasattr(service, "analyze_batch"):
            results = service.analyze_batch(texts)
        else:
            results = [service.analyze(text) for text in texts]

        return [
            {
                "label": r.label,
                "score": r.score,
                "confidence": r.confidence,
                "probabilities": r.probabilities,
            }
            for r in results
        ]

    except Exception as e:
        logger.error("Batch sentiment failed", error=str(e))
        return [
            {"label": "neutral", "score": 0.0, "confidence": 0.5, "probabilities": {}}
            for _ in texts
        ]


@celery_app.task(bind=True, max_retries=2)
def classify_event_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Classify event type from content.

    Args:
        data: Event data

    Returns:
        Data enriched with classification
    """
    try:
        from backend.processing.classification import EventClassifier

        # Get text for classification
        text = data.get("headline", "") or data.get("title", "")
        text = text + " " + (data.get("summary", "") or data.get("content", "")[:1000])

        if not text.strip():
            return data

        # Classify
        classifier = EventClassifier()
        classification = classifier.classify(text, data.get("source"))

        # Enrich data
        data["event_type"] = classification.event_type.value
        data["event_confidence"] = classification.confidence
        data["is_material"] = classification.is_material
        data["base_signal_weight"] = classification.base_signal_weight

        logger.debug(
            "Event classified",
            event_type=classification.event_type.value,
            confidence=classification.confidence,
        )

        return data

    except Exception as e:
        logger.error("Event classification failed", error=str(e))
        raise self.retry(exc=e, countdown=5)


@celery_app.task
def link_tickers_task(data: dict[str, Any]) -> dict[str, Any]:
    """Link extracted entities to validated ticker symbols.

    Args:
        data: Event data with extracted entities

    Returns:
        Data with validated tickers
    """
    import asyncio

    async def _link():
        from backend.processing.ner import TickerKnowledgeBase, TickerLinker

        kb = TickerKnowledgeBase()
        await kb.load()

        linker = TickerLinker(kb)

        # Validate extracted tickers
        tickers = data.get("extracted_tickers", [])
        validated = []

        for ticker in tickers:
            info = linker.validate_ticker(ticker)
            if info["is_valid"]:
                validated.append({
                    "ticker": ticker,
                    "cik": info["cik"],
                    "company_name": info["company_name"],
                })
            else:
                # Keep unvalidated tickers but mark them
                validated.append({
                    "ticker": ticker,
                    "cik": None,
                    "company_name": None,
                    "unverified": True,
                })

        data["validated_tickers"] = validated

        return data

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_link())
    finally:
        loop.close()
