"""Seed script to populate the database with sample events for testing."""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb"

# Sample data
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "CRM",
    "PLTR", "SOFI", "NIO", "RIVN", "LCID", "MARA", "RIOT", "COIN", "HOOD", "AFRM",
    "ABCD", "EFGH", "IJKL", "MNOP", "QRST", "UVWX", "YZAB", "CDEF", "GHIJ", "KLMN"
]

EVENT_TYPES = [
    ("INSIDER_BUY", "SEC_FILING", "positive"),
    ("INSIDER_SELL", "SEC_FILING", "negative"),
    ("EARNINGS_BEAT", "EARNINGS", "positive"),
    ("EARNINGS_MISS", "EARNINGS", "negative"),
    ("FDA_APPROVAL", "REGULATORY", "positive"),
    ("FDA_REJECTION", "REGULATORY", "negative"),
    ("ACQUISITION", "CORPORATE", "positive"),
    ("ACTIVIST_STAKE", "SEC_FILING", "positive"),
    ("OFFERING", "CAPITAL_MARKETS", "negative"),
    ("MANAGEMENT_CHANGE", "CORPORATE", "neutral"),
    ("CONTRACT_WIN", "BUSINESS", "positive"),
    ("REGULATORY_ACTION", "REGULATORY", "negative"),
    ("PARTNERSHIP", "BUSINESS", "positive"),
    ("PRODUCT_LAUNCH", "BUSINESS", "positive"),
]

HEADLINES = {
    "INSIDER_BUY": [
        "CEO purchases {amount} shares at ${price} in open market transaction",
        "Director acquires {amount} shares, signaling confidence",
        "Multiple insiders buy shares worth ${value}M total",
        "CFO increases stake with {amount} share purchase",
    ],
    "INSIDER_SELL": [
        "CEO sells {amount} shares in planned divestiture",
        "Insider reduces position by {percent}%",
        "Executive sells shares worth ${value}M",
    ],
    "EARNINGS_BEAT": [
        "Q{quarter} earnings beat expectations, EPS ${eps} vs ${expected} expected",
        "Revenue surges {percent}% YoY, beating analyst estimates",
        "Strong quarterly results drive shares higher",
        "Company reports record revenue of ${value}B",
    ],
    "EARNINGS_MISS": [
        "Q{quarter} earnings miss expectations, revenue down {percent}% YoY",
        "Disappointing results as EPS misses by ${miss}",
        "Weak guidance sends shares lower",
        "Company reports wider than expected loss",
    ],
    "FDA_APPROVAL": [
        "FDA grants breakthrough therapy designation for lead drug candidate",
        "Company receives FDA approval for {drug} treatment",
        "Positive Phase 3 results pave way for FDA submission",
        "FDA clears new indication for flagship product",
    ],
    "FDA_REJECTION": [
        "FDA issues complete response letter for drug application",
        "Regulatory setback as FDA requests additional data",
        "Phase 3 trial fails to meet primary endpoint",
    ],
    "ACQUISITION": [
        "Company to acquire {target} for ${value}B in cash and stock",
        "Strategic acquisition expands market presence",
        "Merger agreement reached at ${premium}% premium",
    ],
    "ACTIVIST_STAKE": [
        "Activist fund discloses {percent}% stake, plans strategic review",
        "Hedge fund builds position, pushes for changes",
        "Activist investor nominates board candidates",
    ],
    "OFFERING": [
        "Company announces ${value}M registered direct offering at ${price}",
        "Secondary offering prices below market",
        "Dilutive financing raises concerns",
    ],
    "MANAGEMENT_CHANGE": [
        "CEO announces retirement, successor named",
        "CFO resigns unexpectedly, interim appointed",
        "New CTO hired from {company}",
        "Board appoints new independent directors",
    ],
    "CONTRACT_WIN": [
        "Company wins ${value}M government contract",
        "Major partnership deal worth ${value}M annually",
        "New enterprise customer signs multi-year agreement",
    ],
    "REGULATORY_ACTION": [
        "SEC opens investigation into accounting practices",
        "Company receives DOJ subpoena",
        "Regulatory fine of ${value}M announced",
    ],
    "PARTNERSHIP": [
        "Strategic partnership announced with {partner}",
        "Joint venture to develop new technology",
        "Collaboration agreement with major industry player",
    ],
    "PRODUCT_LAUNCH": [
        "Company unveils next-generation product line",
        "New platform launch exceeds expectations",
        "Revolutionary product enters beta testing",
    ],
}

SOURCES = [
    ("SEC EDGAR", "https://sec.gov"),
    ("PR Newswire", "https://prnewswire.com"),
    ("Business Wire", "https://businesswire.com"),
    ("GlobeNewswire", "https://globenewswire.com"),
    ("Reuters", "https://reuters.com"),
    ("Bloomberg", "https://bloomberg.com"),
    ("CNBC", "https://cnbc.com"),
    ("MarketWatch", "https://marketwatch.com"),
]


def generate_headline(event_type: str) -> str:
    """Generate a random headline for the event type."""
    templates = HEADLINES.get(event_type, ["Breaking news for {ticker}"])
    template = random.choice(templates)

    return template.format(
        amount=random.randint(10, 500) * 1000,
        price=round(random.uniform(1, 200), 2),
        value=round(random.uniform(1, 100), 1),
        percent=random.randint(5, 50),
        quarter=random.randint(1, 4),
        eps=round(random.uniform(0.5, 5), 2),
        expected=round(random.uniform(0.4, 4.5), 2),
        miss=round(random.uniform(0.05, 0.5), 2),
        drug="ABC-123",
        target="Target Corp",
        premium=random.randint(15, 45),
        company="Tech Giant",
        partner="Industry Leader",
        ticker="TICK",
    )


def generate_summary(headline: str, sentiment: str) -> str:
    """Generate a summary based on headline and sentiment."""
    if sentiment == "positive":
        return f"{headline}. This development is viewed positively by analysts and could signal strong future performance."
    elif sentiment == "negative":
        return f"{headline}. Market participants are concerned about the implications for the company's outlook."
    else:
        return f"{headline}. Analysts are monitoring the situation for further developments."


async def seed_database():
    """Seed the database with sample events."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if events table exists and has data
        result = await session.execute(text("SELECT COUNT(*) FROM events"))
        count = result.scalar()

        if count > 0:
            print(f"Database already has {count} events. Skipping seed.")
            return

        print("Seeding database with sample events...")

        now = datetime.now(timezone.utc)
        events_to_insert = []

        # Generate events for the past 7 days
        for days_ago in range(7):
            # Generate 30-50 events per day
            num_events = random.randint(30, 50)

            for _ in range(num_events):
                ticker = random.choice(TICKERS)
                event_type, category, base_sentiment = random.choice(EVENT_TYPES)
                source_name, source_url = random.choice(SOURCES)

                # Random time within the day
                hours_offset = random.uniform(0, 24)
                event_time = now - timedelta(days=days_ago, hours=hours_offset)

                headline = generate_headline(event_type)
                summary = generate_summary(headline, base_sentiment)

                # Generate sentiment score based on base sentiment
                if base_sentiment == "positive":
                    sentiment_score = random.uniform(0.3, 0.95)
                    sentiment_label = "positive"
                    direction = "BULLISH"
                elif base_sentiment == "negative":
                    sentiment_score = random.uniform(-0.95, -0.3)
                    sentiment_label = "negative"
                    direction = "BEARISH"
                else:
                    sentiment_score = random.uniform(-0.2, 0.2)
                    sentiment_label = "neutral"
                    direction = "NEUTRAL"

                # Alpha score - higher for more significant events
                alpha_base = abs(sentiment_score) * 0.5
                alpha_noise = random.uniform(-0.2, 0.3)
                alpha_score = max(0, min(1, alpha_base + alpha_noise))

                # Urgency based on alpha and event type
                if alpha_score > 0.7 or event_type in ["FDA_APPROVAL", "FDA_REJECTION", "ACQUISITION"]:
                    urgency = "CRITICAL" if alpha_score > 0.8 else "HIGH"
                elif alpha_score > 0.4:
                    urgency = "MEDIUM"
                else:
                    urgency = "LOW"

                event_id = uuid4()

                events_to_insert.append({
                    "id": event_id,
                    "ticker": ticker,
                    "event_time": event_time,
                    "ingest_time": event_time + timedelta(seconds=random.randint(1, 60)),
                    "event_type": event_type,
                    "event_category": category,
                    "headline": headline,
                    "summary": summary,
                    "source_url": f"{source_url}/news/{event_id}",
                    "source_name": source_name,
                    "sentiment_score": round(sentiment_score, 4),
                    "sentiment_label": sentiment_label,
                    "sentiment_confidence": round(random.uniform(0.7, 0.98), 4),
                    "alpha_score": round(alpha_score, 4),
                    "direction": direction,
                    "urgency_level": urgency,
                    "extracted_tickers": [ticker],
                })

        # Insert events in batches
        batch_size = 50
        for i in range(0, len(events_to_insert), batch_size):
            batch = events_to_insert[i:i + batch_size]

            for event in batch:
                await session.execute(
                    text("""
                        INSERT INTO events (
                            id, ticker, event_time, ingest_time, event_type, event_category,
                            headline, summary, source_url, source_name,
                            sentiment_score, sentiment_label, sentiment_confidence,
                            alpha_score, direction, urgency_level, extracted_tickers
                        ) VALUES (
                            :id, :ticker, :event_time, :ingest_time, :event_type, :event_category,
                            :headline, :summary, :source_url, :source_name,
                            :sentiment_score, :sentiment_label, :sentiment_confidence,
                            :alpha_score, :direction, :urgency_level, :extracted_tickers
                        )
                    """),
                    event
                )

            await session.commit()
            print(f"Inserted {min(i + batch_size, len(events_to_insert))}/{len(events_to_insert)} events...")

        print(f"\nSuccessfully seeded {len(events_to_insert)} events!")

        # Print summary stats
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE direction = 'BULLISH') as bullish,
                COUNT(*) FILTER (WHERE direction = 'BEARISH') as bearish,
                COUNT(*) FILTER (WHERE alpha_score >= 0.7) as high_alpha
            FROM events
        """))
        stats = result.fetchone()
        print(f"\nDatabase stats:")
        print(f"  Total events: {stats[0]}")
        print(f"  Bullish: {stats[1]}")
        print(f"  Bearish: {stats[2]}")
        print(f"  High Alpha (≥70): {stats[3]}")


if __name__ == "__main__":
    asyncio.run(seed_database())
