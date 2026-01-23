"""Redpanda (Kafka-compatible) event streaming service.

This module provides:
- RedpandaProducer: Async producer for publishing events to Redpanda topics
- RedpandaConsumer: Async consumer for reading events from Redpanda topics
- StreamingService: High-level service for managing streaming operations
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

import structlog
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError, KafkaError

from backend.config import settings

logger = structlog.get_logger(__name__)

# Topic names
TOPIC_ALL_EVENTS = "events.all"
TOPIC_HIGH_ALPHA = "events.high-alpha"
TOPIC_TICKER_PREFIX = "events.ticker."


def get_ticker_topic(ticker: str) -> str:
    """Get the topic name for a specific ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Topic name for the ticker
    """
    return f"{TOPIC_TICKER_PREFIX}{ticker.upper()}"


class RedpandaProducer:
    """Async Kafka producer for publishing events to Redpanda.

    Usage:
        producer = RedpandaProducer()
        await producer.start()
        await producer.publish_event(event_data)
        await producer.stop()
    """

    def __init__(
        self,
        bootstrap_servers: str | list[str] | None = None,
        client_id: str = "news-scraper-producer",
    ):
        """Initialize the Redpanda producer.

        Args:
            bootstrap_servers: Kafka broker addresses (defaults to settings)
            client_id: Client identifier for Kafka
        """
        if bootstrap_servers is None:
            bootstrap_servers = settings.kafka_brokers_list
        elif isinstance(bootstrap_servers, str):
            bootstrap_servers = bootstrap_servers.split(",")

        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._producer: AIOKafkaProducer | None = None
        self._started = False

    async def start(self) -> bool:
        """Start the Kafka producer.

        Returns:
            True if started successfully
        """
        if self._started:
            return True

        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                client_id=self._client_id,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",  # Wait for all replicas
                enable_idempotence=True,  # Exactly-once semantics
                compression_type="gzip",
                max_batch_size=16384,
                linger_ms=10,  # Small batching delay for better throughput
            )
            await self._producer.start()
            self._started = True

            logger.info(
                "Redpanda producer started",
                bootstrap_servers=self._bootstrap_servers,
                client_id=self._client_id,
            )
            return True

        except KafkaConnectionError as e:
            logger.error(
                "Failed to connect to Redpanda",
                error=str(e),
                bootstrap_servers=self._bootstrap_servers,
            )
            return False

        except Exception as e:
            logger.error("Failed to start Redpanda producer", error=str(e))
            return False

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self._producer and self._started:
            try:
                await self._producer.stop()
                logger.info("Redpanda producer stopped")
            except Exception as e:
                logger.error("Error stopping Redpanda producer", error=str(e))
            finally:
                self._producer = None
                self._started = False

    async def publish(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """Publish a message to a Kafka topic.

        Args:
            topic: Topic name
            value: Message value (will be JSON serialized)
            key: Optional message key for partitioning

        Returns:
            True if published successfully
        """
        if not self._started or not self._producer:
            logger.warning("Producer not started, attempting to start")
            if not await self.start():
                return False

        try:
            await self._producer.send_and_wait(topic, value=value, key=key)
            logger.debug(
                "Message published",
                topic=topic,
                key=key,
            )
            return True

        except KafkaError as e:
            logger.error(
                "Failed to publish message",
                topic=topic,
                error=str(e),
            )
            return False

    async def publish_event(self, event: dict[str, Any]) -> dict[str, bool]:
        """Publish an event to appropriate topics based on its properties.

        Events are published to:
        - events.all: All events
        - events.high-alpha: High alpha events (|alpha_score| >= 0.7)
        - events.ticker.{TICKER}: Per-ticker topic

        Args:
            event: Event data dictionary

        Returns:
            Dictionary with topic names and success status
        """
        results = {}

        # Ensure event has timestamp
        if "published_at" not in event:
            event["published_at"] = datetime.now(timezone.utc).isoformat()

        # Use ticker as partition key for ordering
        ticker = event.get("ticker", "UNKNOWN")
        key = ticker.upper()

        # Publish to all events topic
        results[TOPIC_ALL_EVENTS] = await self.publish(
            TOPIC_ALL_EVENTS,
            event,
            key=key,
        )

        # Publish to ticker-specific topic
        if ticker and ticker != "UNKNOWN":
            ticker_topic = get_ticker_topic(ticker)
            results[ticker_topic] = await self.publish(
                ticker_topic,
                event,
                key=key,
            )

        # Publish to high-alpha topic if applicable
        alpha_score = event.get("alpha_score")
        if alpha_score is not None:
            try:
                alpha_value = float(alpha_score)
                if abs(alpha_value) >= 0.7:
                    results[TOPIC_HIGH_ALPHA] = await self.publish(
                        TOPIC_HIGH_ALPHA,
                        event,
                        key=key,
                    )
            except (ValueError, TypeError):
                pass

        return results

    @property
    def is_connected(self) -> bool:
        """Check if producer is connected."""
        return self._started and self._producer is not None


class RedpandaConsumer:
    """Async Kafka consumer for reading events from Redpanda.

    Usage:
        consumer = RedpandaConsumer(topics=["events.all"])
        await consumer.start()

        async for message in consumer.consume():
            process_message(message)

        await consumer.stop()
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str = "news-scraper-consumer",
        bootstrap_servers: str | list[str] | None = None,
        client_id: str = "news-scraper-consumer",
        auto_offset_reset: str = "latest",
    ):
        """Initialize the Redpanda consumer.

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID for offset management
            bootstrap_servers: Kafka broker addresses (defaults to settings)
            client_id: Client identifier for Kafka
            auto_offset_reset: Where to start if no offset ("earliest" or "latest")
        """
        if bootstrap_servers is None:
            bootstrap_servers = settings.kafka_brokers_list
        elif isinstance(bootstrap_servers, str):
            bootstrap_servers = bootstrap_servers.split(",")

        self._bootstrap_servers = bootstrap_servers
        self._topics = topics
        self._group_id = group_id
        self._client_id = client_id
        self._auto_offset_reset = auto_offset_reset
        self._consumer: AIOKafkaConsumer | None = None
        self._started = False
        self._stop_event = asyncio.Event()

    async def start(self) -> bool:
        """Start the Kafka consumer.

        Returns:
            True if started successfully
        """
        if self._started:
            return True

        try:
            self._consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=self._bootstrap_servers,
                client_id=self._client_id,
                group_id=self._group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset=self._auto_offset_reset,
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
            )
            await self._consumer.start()
            self._started = True
            self._stop_event.clear()

            logger.info(
                "Redpanda consumer started",
                topics=self._topics,
                group_id=self._group_id,
                bootstrap_servers=self._bootstrap_servers,
            )
            return True

        except KafkaConnectionError as e:
            logger.error(
                "Failed to connect to Redpanda",
                error=str(e),
                bootstrap_servers=self._bootstrap_servers,
            )
            return False

        except Exception as e:
            logger.error("Failed to start Redpanda consumer", error=str(e))
            return False

    async def stop(self) -> None:
        """Stop the Kafka consumer."""
        self._stop_event.set()

        if self._consumer and self._started:
            try:
                await self._consumer.stop()
                logger.info("Redpanda consumer stopped")
            except Exception as e:
                logger.error("Error stopping Redpanda consumer", error=str(e))
            finally:
                self._consumer = None
                self._started = False

    async def consume(self):
        """Async generator that yields messages from subscribed topics.

        Yields:
            Dictionary with message data including:
            - topic: Topic name
            - partition: Partition number
            - offset: Message offset
            - key: Message key
            - value: Message value (deserialized JSON)
            - timestamp: Message timestamp
        """
        if not self._started or not self._consumer:
            logger.warning("Consumer not started, attempting to start")
            if not await self.start():
                return

        try:
            async for message in self._consumer:
                if self._stop_event.is_set():
                    break

                yield {
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                    "key": message.key,
                    "value": message.value,
                    "timestamp": message.timestamp,
                }

        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        except Exception as e:
            logger.error("Error consuming messages", error=str(e))

    async def consume_with_handler(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Consume messages and process with a handler function.

        Args:
            handler: Async function to handle each message
        """
        async for message in self.consume():
            try:
                await handler(message)
            except Exception as e:
                logger.error(
                    "Error in message handler",
                    error=str(e),
                    topic=message.get("topic"),
                    offset=message.get("offset"),
                )

    @property
    def is_connected(self) -> bool:
        """Check if consumer is connected."""
        return self._started and self._consumer is not None


class StreamingService:
    """High-level service for managing Redpanda streaming operations.

    This service provides a simplified interface for:
    - Publishing events to Redpanda
    - Consuming events from Redpanda
    - Managing producer/consumer lifecycle

    Usage:
        service = StreamingService()
        await service.start()

        # Publish event
        await service.publish_event(event_data)

        # Start consumer with handler
        await service.start_consumer(my_handler)

        await service.stop()
    """

    def __init__(
        self,
        bootstrap_servers: str | list[str] | None = None,
    ):
        """Initialize the streaming service.

        Args:
            bootstrap_servers: Kafka broker addresses (defaults to settings)
        """
        self._bootstrap_servers = bootstrap_servers
        self._producer: RedpandaProducer | None = None
        self._consumers: list[RedpandaConsumer] = []
        self._consumer_tasks: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> bool:
        """Start the streaming service (producer only).

        Returns:
            True if started successfully
        """
        if self._started:
            return True

        self._producer = RedpandaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id="news-scraper-service-producer",
        )

        if await self._producer.start():
            self._started = True
            logger.info("Streaming service started")
            return True

        return False

    async def stop(self) -> None:
        """Stop the streaming service."""
        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop all consumers
        for consumer in self._consumers:
            await consumer.stop()

        # Stop producer
        if self._producer:
            await self._producer.stop()

        self._consumer_tasks = []
        self._consumers = []
        self._producer = None
        self._started = False

        logger.info("Streaming service stopped")

    async def publish_event(self, event: dict[str, Any]) -> dict[str, bool]:
        """Publish an event to appropriate Redpanda topics.

        Args:
            event: Event data dictionary

        Returns:
            Dictionary with topic names and success status
        """
        if not self._started or not self._producer:
            logger.warning("Service not started, attempting to start")
            if not await self.start():
                return {}

        return await self._producer.publish_event(event)

    async def publish_to_topic(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """Publish a message to a specific topic.

        Args:
            topic: Topic name
            value: Message value
            key: Optional partition key

        Returns:
            True if published successfully
        """
        if not self._started or not self._producer:
            logger.warning("Service not started, attempting to start")
            if not await self.start():
                return False

        return await self._producer.publish(topic, value, key)

    async def start_consumer(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        topics: list[str] | None = None,
        group_id: str = "news-scraper-ws-consumer",
    ) -> RedpandaConsumer | None:
        """Start a consumer with a message handler.

        Args:
            handler: Async function to handle each message
            topics: Topics to subscribe to (defaults to all events)
            group_id: Consumer group ID

        Returns:
            Consumer instance or None if failed to start
        """
        if topics is None:
            topics = [TOPIC_ALL_EVENTS, TOPIC_HIGH_ALPHA]

        consumer = RedpandaConsumer(
            topics=topics,
            group_id=group_id,
            bootstrap_servers=self._bootstrap_servers,
        )

        if not await consumer.start():
            return None

        self._consumers.append(consumer)

        # Create task for consuming
        task = asyncio.create_task(consumer.consume_with_handler(handler))
        self._consumer_tasks.append(task)

        logger.info(
            "Started consumer with handler",
            topics=topics,
            group_id=group_id,
        )

        return consumer

    def create_consumer(
        self,
        topics: list[str],
        group_id: str = "news-scraper-consumer",
    ) -> RedpandaConsumer:
        """Create a consumer without starting it.

        Args:
            topics: Topics to subscribe to
            group_id: Consumer group ID

        Returns:
            Consumer instance
        """
        consumer = RedpandaConsumer(
            topics=topics,
            group_id=group_id,
            bootstrap_servers=self._bootstrap_servers,
        )
        self._consumers.append(consumer)
        return consumer

    @property
    def is_connected(self) -> bool:
        """Check if the service is connected."""
        return self._started and self._producer is not None and self._producer.is_connected


# Global streaming service instance
streaming_service = StreamingService()


# Synchronous producer for use in Celery tasks
class SyncRedpandaProducer:
    """Synchronous Kafka producer for use in Celery tasks.

    This class wraps the async producer for use in synchronous contexts
    like Celery workers.
    """

    def __init__(
        self,
        bootstrap_servers: str | list[str] | None = None,
    ):
        """Initialize the sync producer.

        Args:
            bootstrap_servers: Kafka broker addresses
        """
        if bootstrap_servers is None:
            bootstrap_servers = settings.kafka_brokers_list
        elif isinstance(bootstrap_servers, str):
            bootstrap_servers = bootstrap_servers.split(",")

        self._bootstrap_servers = bootstrap_servers
        self._producer = None

    def _get_producer(self):
        """Get or create the Kafka producer."""
        if self._producer is None:
            from kafka import KafkaProducer

            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    acks="all",
                    compression_type="gzip",
                )
                logger.info(
                    "Sync Kafka producer created",
                    bootstrap_servers=self._bootstrap_servers,
                )
            except Exception as e:
                logger.error("Failed to create sync Kafka producer", error=str(e))
                raise

        return self._producer

    def publish(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """Publish a message synchronously.

        Args:
            topic: Topic name
            value: Message value
            key: Optional partition key

        Returns:
            True if published successfully
        """
        try:
            producer = self._get_producer()
            future = producer.send(topic, value=value, key=key)
            future.get(timeout=10)  # Wait for send to complete
            return True
        except Exception as e:
            logger.error(
                "Failed to publish message (sync)",
                topic=topic,
                error=str(e),
            )
            return False

    def publish_event(self, event: dict[str, Any]) -> dict[str, bool]:
        """Publish an event to appropriate topics.

        Args:
            event: Event data

        Returns:
            Dictionary with topic names and success status
        """
        results = {}

        if "published_at" not in event:
            event["published_at"] = datetime.now(timezone.utc).isoformat()

        ticker = event.get("ticker", "UNKNOWN")
        key = ticker.upper()

        # All events topic
        results[TOPIC_ALL_EVENTS] = self.publish(TOPIC_ALL_EVENTS, event, key=key)

        # Ticker topic
        if ticker and ticker != "UNKNOWN":
            ticker_topic = get_ticker_topic(ticker)
            results[ticker_topic] = self.publish(ticker_topic, event, key=key)

        # High alpha topic
        alpha_score = event.get("alpha_score")
        if alpha_score is not None:
            try:
                if abs(float(alpha_score)) >= 0.7:
                    results[TOPIC_HIGH_ALPHA] = self.publish(TOPIC_HIGH_ALPHA, event, key=key)
            except (ValueError, TypeError):
                pass

        return results

    def close(self) -> None:
        """Close the producer."""
        if self._producer:
            try:
                self._producer.close(timeout=5)
                logger.info("Sync Kafka producer closed")
            except Exception as e:
                logger.error("Error closing sync Kafka producer", error=str(e))
            finally:
                self._producer = None


def publish_event_to_redpanda(event: dict[str, Any]) -> dict[str, bool]:
    """Convenience function to publish an event to Redpanda synchronously.

    This is designed for use in Celery tasks.

    Args:
        event: Event data

    Returns:
        Dictionary with topic names and success status
    """
    producer = SyncRedpandaProducer()
    try:
        return producer.publish_event(event)
    finally:
        producer.close()
