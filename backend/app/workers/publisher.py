from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, wait_for_database
from app.models import OutboxEvent
from app.workers.kafka_common import create_producer, ensure_topic

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dayform.publisher")


def publish_forever() -> None:
    wait_for_database()
    ensure_topic()
    producer = create_producer()
    logger.info("Outbox publisher running → topic=%s", settings.kafka_topic)
    while True:
        published_any = False
        with SessionLocal.begin() as db:
            event = db.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if event is not None:
                try:
                    producer.produce(
                        settings.kafka_topic,
                        key=event.aggregate_id,
                        value=json.dumps(event.payload, separators=(",", ":")),
                        headers={"event_type": event.event_type, "event_id": event.event_id},
                    )
                    remaining = producer.flush(12)
                    if remaining:
                        raise TimeoutError(f"Kafka still has {remaining} message(s) in flight")
                    event.published_at = datetime.now(timezone.utc)
                    event.attempts += 1
                    event.last_error = None
                    published_any = True
                    logger.info("Published %s event_id=%s aggregate=%s", event.event_type, event.event_id, event.aggregate_id)
                except Exception as exc:
                    event.attempts += 1
                    event.last_error = str(exc)[:1000]
                    logger.exception("Could not publish event %s", event.event_id)
        if not published_any:
            time.sleep(1.25)


if __name__ == "__main__":
    publish_forever()
