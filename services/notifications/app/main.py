"""
FastAPI application with Kafka consumer lifecycle management.

The consumer runs in a background thread, started when the app starts
and stopped on shutdown.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consumer import run_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_consumer_thread = None


def _consumer_worker():
    """Worker function that runs in a background thread."""
    try:
        run_consumer()
    except Exception:
        logger.exception("Consumer crashed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Kafka consumer lifecycle."""
    global _consumer_thread
    logger.info("Starting Kafka consumer thread...")
    _consumer_thread = threading.Thread(
        target=_consumer_worker,
        daemon=True,
        name="kafka-consumer",
    )
    _consumer_thread.start()
    yield
    logger.info("Shutting down Kafka consumer...")


app = FastAPI(
    title="Postways Notification Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "consumer_alive": _consumer_thread is not None and _consumer_thread.is_alive(),
    }
