"""
api/web/image_worker.py — Dedicated Background Worker for Image Generation.

Run this as a separate background process:

    python -m api.web.image_worker

Consumes tasks exclusively from the "trendforge-images" queue so heavy image
generation jobs never block text generation or prompt orchestration.
"""

import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from redis import Redis
from rq import Queue

from api.web.image_deps import IMAGE_QUEUE_NAME
from api.web.db import init_db
from memory.redis_session_store import REDIS_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("trendforge.image_worker")

if __name__ == "__main__":
    try:
        init_db()
        logger.info("Database initialized and visual profiles verified.")
    except Exception as e:
        logger.warning("Could not initialize DB on worker startup: %s", e)

    logger.info("Connecting to Redis at %s...", REDIS_URL)
    conn = Redis.from_url(REDIS_URL)
    queue = Queue(IMAGE_QUEUE_NAME, connection=conn)

    logger.info("Starting TrendForge Image Worker on queue: '%s'", IMAGE_QUEUE_NAME)

    if os.name == "nt":
        # SimpleWorker for Windows development
        from rq import SimpleWorker
        worker = SimpleWorker([queue], connection=conn)
    else:
        # Process-isolated Worker for Linux deployment
        from rq import Worker
        worker = Worker([queue], connection=conn)

    worker.work()
