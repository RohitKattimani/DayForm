from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, wait_for_database
from app.models import EventLog, OrderItem, OutboxEvent, ProcessedEvent, Product, StoreOrder
from app.search import sync_product_ids
from app.workers.kafka_common import create_consumer, ensure_topic

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dayform.consumer")


def _record_event(db, event_id: str, event_type: str, order_number: str | None, message: str) -> None:
    existing = db.scalar(select(EventLog.id).where(EventLog.event_id == event_id))
    if existing is None:
        db.add(EventLog(
            event_id=event_id,
            event_type=event_type,
            order_number=order_number,
            status="PROCESSED",
            message=message,
        ))


def process_order_placed(event: dict) -> list[int]:
    event_id = event["event_id"]
    order_id = int(event["order_id"])
    order_number = event.get("order_number")
    product_ids = [int(item["product_id"]) for item in event.get("items", [])]

    with SessionLocal.begin() as db:
        already_processed = db.get(ProcessedEvent, event_id)
        if already_processed is None:
            order = db.scalar(select(StoreOrder).where(StoreOrder.id == order_id).with_for_update())
            if order is None:
                raise RuntimeError(f"Order {order_id} referenced by event does not exist")
            if order.status != "CONFIRMED":
                items = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.product_id)).all()
                locked_products = db.scalars(
                    select(Product).where(Product.id.in_([item.product_id for item in items])).order_by(Product.id).with_for_update()
                ).all()
                product_map = {product.id: product for product in locked_products}
                for item in items:
                    product = product_map[item.product_id]
                    if product.stock_on_hand < item.quantity or product.reserved_stock < item.quantity:
                        raise RuntimeError(f"Inventory invariant failed for SKU {product.sku}; order is not acknowledged")
                    product.stock_on_hand -= item.quantity
                    product.reserved_stock -= item.quantity
                order.status = "CONFIRMED"
                order.confirmed_at = datetime.now(timezone.utc)

            db.add(ProcessedEvent(event_id=event_id, event_type="order.placed"))
            _record_event(db, event_id, "order.placed", order_number, f"Order {order_number} consumed from Kafka; inventory deducted in PostgreSQL.")

            inventory_event_id = str(uuid.uuid4())
            inventory_payload = {
                "event_id": inventory_event_id,
                "event_type": "inventory.updated",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "order_number": order_number,
                "product_ids": product_ids,
            }
            db.add(OutboxEvent(
                event_id=inventory_event_id,
                event_type="inventory.updated",
                aggregate_id=str(order_id),
                payload=inventory_payload,
            ))
            logger.info("Order %s confirmed; inventory reduced for %s SKU(s)", order_number, len(product_ids))

    return product_ids


def process_inventory_updated(event: dict) -> list[int]:
    event_id = event["event_id"]
    product_ids = [int(value) for value in event.get("product_ids", [])]
    order_number = event.get("order_number")
    with SessionLocal.begin() as db:
        if db.get(ProcessedEvent, event_id) is None:
            db.add(ProcessedEvent(event_id=event_id, event_type="inventory.updated"))
            _record_event(db, event_id, "inventory.updated", order_number, f"OpenSearch product availability refreshed after order {order_number}.")
    return product_ids


def consume_forever() -> None:
    wait_for_database()
    ensure_topic()
    consumer = create_consumer()
    consumer.subscribe([settings.kafka_topic])
    logger.info("Kafka consumer running ← topic=%s group=%s", settings.kafka_topic, settings.kafka_group_id)
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                logger.error("Kafka consumer error: %s", message.error())
                continue
            try:
                event = json.loads(message.value().decode("utf-8"))
                event_type = event.get("event_type")
                if event_type == "order.placed":
                    product_ids = process_order_placed(event)
                    # The DB transaction above is idempotent. If indexing fails, Kafka will redeliver.
                    with SessionLocal() as db:
                        sync_product_ids(db, product_ids)
                elif event_type == "inventory.updated":
                    product_ids = process_inventory_updated(event)
                    with SessionLocal() as db:
                        sync_product_ids(db, product_ids)
                else:
                    logger.info("Ignoring unhandled event type=%s", event_type)
                consumer.commit(message=message, asynchronous=False)
                logger.info("Committed Kafka offset=%s partition=%s event_type=%s", message.offset(), message.partition(), event_type)
            except Exception:
                logger.exception("Event processing failed; message will be retried")
                time.sleep(1)
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_forever()
