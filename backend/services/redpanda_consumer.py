"""Redpanda consumer that reads events and broadcasts to WebSocket.

This module provides a standalone consumer service that:
1. Consumes events from Redpanda topics
2. Broadcasts events to WebSocket connections via Redis pub/sub

Run as a standalone service:
    python -m backend.services.redpanda_consumer
"""

import asyncio
import json
from typing import Any

import structlog
import redis.asyncio as redis

from backend.config import settings
from backend.services.streaming import (
    RedpandaConsumer,
    TOPIC_ALL_EVENTS,
    TOPIC_HIGH_ALPHA,
)

logger = structlog.get_logger(__name__)


class RedpandaToWebSocketBridge:
    """Bridges Redpanda events to WebSocket connections via Redis pub/sub.

    This consumer reads from Redpanda topics and publishes to Redis channels
    that the WebSocket server listens to.
    """

    # Redis channels (must match WebSocket streamer)
    REDIS_CHANNEL_ALL = "events:all"
    REDIS_CHANNEL_HIGH_ALPHA = "events:high_alpha"
    REDIS_CHANNEL_TICKER_PREFIX = "events:ticker:"

    def __init__(
        self,
        group_id: str = "news-scraper-ws-bridge",
    ):
        """Initialize the bridge.

        Args:
            group_id: Kafka consumer group ID
        """
        self._group_id = group_id
        self._consumer: RedpandaConsumer | None = None
        self._redis: redis.Redis | None = None
        self._running = False
        self._stats = {
            "messages_processed": 0,
            "messages_published": 0,
            "errors": 0,
        }

    async def start(self) -> bool:
        """Start the bridge.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        try:
            # Initialize Redis connection
            self._redis = redis.from_url(str(settings.redis_url))
            await self._redis.ping()
            logger.info("Connected to Redis", url=str(settings.redis_url))

            # Initialize Kafka consumer
            self._consumer = RedpandaConsumer(
                topics=[TOPIC_ALL_EVENTS, TOPIC_HIGH_ALPHA],
                group_id=self._group_id,
                auto_offset_reset="latest",  # Only process new messages
            )

            if not await self._consumer.start():
                logger.error("Failed to start Redpanda consumer")
                return False

            self._running = True
            logger.info(
                "Redpanda to WebSocket bridge started",
                topics=[TOPIC_ALL_EVENTS, TOPIC_HIGH_ALPHA],
                group_id=self._group_id,
            )
            return True

        except Exception as e:
            logger.error("Failed to start bridge", error=str(e))
            return False

    async def stop(self) -> None:
        """Stop the bridge."""
        self._running = False

        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        logger.info(
            "Bridge stopped",
            stats=self._stats,
        )

    async def run(self) -> None:
        """Run the bridge, consuming messages and publishing to Redis."""
        if not self._running:
            if not await self.start():
                return

        try:
            async for message in self._consumer.consume():
                if not self._running:
                    break

                await self._process_message(message)

        except asyncio.CancelledError:
            logger.info("Bridge cancelled")
        except Exception as e:
            logger.error("Error in bridge run loop", error=str(e))
        finally:
            await self.stop()

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a Kafka message and publish to Redis.

        Args:
            message: Kafka message with topic, value, etc.
        """
        try:
            self._stats["messages_processed"] += 1

            topic = message["topic"]
            event = message["value"]

            if not isinstance(event, dict):
                logger.warning("Invalid message value", topic=topic)
                return

            # Serialize event for Redis
            event_json = json.dumps(event)
            ticker = event.get("ticker", "UNKNOWN")

            # Determine which Redis channels to publish to
            channels_published = []

            if topic == TOPIC_ALL_EVENTS:
                # Publish to all events channel
                await self._redis.publish(self.REDIS_CHANNEL_ALL, event_json)
                channels_published.append(self.REDIS_CHANNEL_ALL)

                # Also publish to ticker-specific channel
                if ticker and ticker != "UNKNOWN":
                    ticker_channel = f"{self.REDIS_CHANNEL_TICKER_PREFIX}{ticker.upper()}"
                    await self._redis.publish(ticker_channel, event_json)
                    channels_published.append(ticker_channel)

            elif topic == TOPIC_HIGH_ALPHA:
                # Publish to high-alpha channel
                await self._redis.publish(self.REDIS_CHANNEL_HIGH_ALPHA, event_json)
                channels_published.append(self.REDIS_CHANNEL_HIGH_ALPHA)

            self._stats["messages_published"] += len(channels_published)

            logger.debug(
                "Event bridged to Redis",
                topic=topic,
                ticker=ticker,
                channels=channels_published,
            )

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Error processing message",
                error=str(e),
                topic=message.get("topic"),
            )

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics.

        Returns:
            Dictionary with processing statistics
        """
        return {
            **self._stats,
            "running": self._running,
            "consumer_connected": self._consumer.is_connected if self._consumer else False,
        }


async def main():
    """Run the Redpanda to WebSocket bridge as a standalone service."""
    import signal

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    bridge = RedpandaToWebSocketBridge()

    # Handle shutdown signals
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start bridge
    if not await bridge.start():
        logger.error("Failed to start bridge, exiting")
        return

    # Run until shutdown
    try:
        # Create task for bridge
        bridge_task = asyncio.create_task(bridge.run())

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Cancel bridge task
        bridge_task.cancel()
        try:
            await bridge_task
        except asyncio.CancelledError:
            pass

    finally:
        await bridge.stop()
        logger.info("Bridge shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
