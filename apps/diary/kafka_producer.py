"""
Kafka producer for publishing domain events from the diary application.

Uses confluent-kafka with fire-and-forget semantics: delivery failures
are logged but never block the HTTP response.
"""

import json
import logging
from datetime import UTC, datetime

from django.conf import settings

from confluent_kafka import Producer

logger = logging.getLogger(__name__)

_producer: Producer | None = None


def _get_producer() -> Producer:
    """Return a module-level singleton Kafka producer."""
    global _producer
    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "client.id": "postways-django",
                "acks": 1,
                "queue.buffering.max.messages": 10000,
                "linger.ms": 100,
            }
        )
    return _producer


def _delivery_report(err, msg):
    """Callback invoked once per produced message to report delivery status."""
    if err is not None:
        logger.error(
            "Kafka delivery failed for topic %s [%s]: %s",
            msg.topic(),
            msg.key(),
            err,
        )
    else:
        logger.debug(
            "Kafka message delivered to %s [partition %d] at offset %d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def publish_post_liked_event(
    *,
    like_id,
    post_id,
    post_title,
    liker_id,
    liker_username,
    author_id,
    author_email,
    author_username,
):
    """
    Publish a post.liked event to Kafka.

    Fire-and-forget: failures are logged but never raised to the caller.
    """
    event = {
        "event_type": "post.liked",
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "like_id": like_id,
            "post_id": post_id,
            "post_title": post_title,
            "liker_id": liker_id,
            "liker_username": liker_username,
            "author_id": author_id,
            "author_email": author_email,
            "author_username": author_username,
        },
    }

    try:
        producer = _get_producer()
        producer.produce(
            topic=settings.KAFKA_TOPIC_POST_EVENTS,
            key=str(post_id),
            value=json.dumps(event),
            callback=_delivery_report,
        )
        # Trigger delivery callbacks without blocking
        producer.poll(0)
    except Exception:
        logger.exception("Failed to publish post.liked event for post %d", post_id)
