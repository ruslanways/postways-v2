"""Kafka consumer for processing post events."""

import json
import logging

from confluent_kafka import Consumer, KafkaError

from .config import settings
from .email import send_like_notification_email

logger = logging.getLogger(__name__)


def create_consumer():
    """Create and configure a Kafka consumer."""
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_consumer_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
        }
    )


def process_message(msg_value):
    """
    Process a single Kafka message.

    Handles post.liked events by sending email notifications,
    skipping self-likes.
    """
    try:
        event = json.loads(msg_value)
    except json.JSONDecodeError:
        logger.error("Failed to decode message: %s", msg_value)
        return

    event_type = event.get("event_type")

    if event_type == "post.liked":
        data = event["data"]

        # Skip self-likes
        if data["liker_id"] == data["author_id"]:
            logger.debug(
                "Skipping self-like notification: user %d on post %d",
                data["liker_id"],
                data["post_id"],
            )
            return

        send_like_notification_email(
            author_email=data["author_email"],
            author_username=data["author_username"],
            liker_username=data["liker_username"],
            post_title=data["post_title"],
            post_id=data["post_id"],
        )
    else:
        logger.debug("Ignoring unknown event type: %s", event_type)


def run_consumer():
    """Run the Kafka consumer loop (blocking)."""
    consumer = create_consumer()
    consumer.subscribe([settings.kafka_topic])
    logger.info(
        "Subscribed to topic '%s', waiting for messages...",
        settings.kafka_topic,
    )

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug("Reached end of partition")
                else:
                    logger.error("Consumer error: %s", msg.error())
                continue

            logger.info(
                "Received message from %s [%d] at offset %d",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )
            process_message(msg.value())
    except KeyboardInterrupt:
        logger.info("Consumer interrupted, shutting down...")
    finally:
        consumer.close()
