from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from confluent_kafka.admin import AdminClient
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.database import SessionLocal, engine, get_db, initialize_database
from app.models import (
    CartItem,
    Customer,
    EventLog,
    OrderItem,
    OutboxEvent,
    Product,
    StoreOrder,
    utcnow,
)
from app.schemas import CartAdd, CartUpdate, CheckoutRequest
from app.search import get_opensearch_client, reindex_all, search_products
from app.workers.kafka_common import kafka_config

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dayform Store API",
    description="Omnichannel retail demo powered by Aiven PostgreSQL, Kafka and OpenSearch.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    try:
        from app.search import ensure_index

        client = get_opensearch_client()
        if client:
            ensure_index(client)
            with SessionLocal() as db:
                reindex_all(db)
            logger.info("OpenSearch index is ready")
    except Exception as exc:  # Search credentials may be added after the first API boot.
        logger.warning("OpenSearch bootstrap skipped: %s", exc)


@app.get("/api/health")
def health() -> dict[str, Any]:
    services = {
        "postgresql": {"status": "not_configured", "label": "PostgreSQL", "detail": "DATABASE_URL is missing"},
        "kafka": {"status": "not_configured", "label": "Apache Kafka", "detail": "Kafka credentials are missing"},
        "opensearch": {"status": "not_configured", "label": "OpenSearch", "detail": "OPENSEARCH_URL is missing"},
    }

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        services["postgresql"] = {"status": "connected", "label": "PostgreSQL", "detail": "Persistent store is responding"}
    except Exception as exc:
        services["postgresql"] = {"status": "error", "label": "PostgreSQL", "detail": str(exc)[:180]}

    if settings.kafka_configured:
        try:
            kafka_health_config = kafka_config()
            kafka_health_config.update({"client.id": "dayform-health-check", "socket.timeout.ms": 3500})
            admin = AdminClient(kafka_health_config)
            metadata = admin.list_topics(timeout=4)
            services["kafka"] = {
                "status": "connected", "label": "Apache Kafka",
                "detail": f"Broker reachable · {len(metadata.topics)} topics visible",
            }
        except Exception as exc:
            services["kafka"] = {"status": "error", "label": "Apache Kafka", "detail": str(exc)[:180]}

    if settings.opensearch_configured:
        try:
            client = get_opensearch_client()
            info = client.info()
            services["opensearch"] = {
                "status": "connected", "label": "OpenSearch",
                "detail": f"Search cluster responding · {info.get('version', {}).get('number', 'online')}",
            }
        except Exception as exc:
            services["opensearch"] = {"status": "error", "label": "OpenSearch", "detail": str(exc)[:180]}

    return {"ok": all(item["status"] == "connected" for item in services.values()), "services": services}


def product_payload(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "sku": product.sku,
        "slug": product.slug,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "brand": product.brand,
        "price_paise": product.price_paise,
        "mrp_paise": product.mrp_paise,
        "stock_on_hand": product.stock_on_hand,
        "reserved_stock": product.reserved_stock,
        "available_stock": product.available_stock,
        "city": product.city,
        "image_url": product.image_url,
        "badge": product.badge,
        "rating": product.rating,
        "review_count": product.review_count,
        "tags": product.tags or [],
        "featured_rank": product.featured_rank,
    }


def cart_payload(db: Session, session_id: str) -> dict[str, Any]:
    rows = db.scalars(
        select(CartItem).options(joinedload(CartItem.product)).where(CartItem.session_id == session_id).order_by(CartItem.id)
    ).all()
    items = []
    for item in rows:
        product = item.product
        items.append({"id": item.id, "quantity": item.quantity, "product": product_payload(product)})
    subtotal = sum(item["product"]["price_paise"] * item["quantity"] for item in items)
    return {"session_id": session_id, "items": items, "item_count": sum(item["quantity"] for item in items), "subtotal_paise": subtotal}


@app.get("/api/catalog")
def catalog(db: Session = Depends(get_db)) -> dict[str, Any]:
    products = db.scalars(
        select(Product).where(Product.active.is_(True)).order_by(Product.featured_rank.asc(), Product.id.asc())
    ).all()
    categories = db.scalars(select(Product.category).where(Product.active.is_(True)).distinct().order_by(Product.category)).all()
    cities = db.scalars(select(Product.city).where(Product.active.is_(True)).distinct().order_by(Product.city)).all()
    return {
        "items": [product_payload(product) for product in products],
        "categories": categories,
        "cities": cities,
        "total": len(products),
        "source": "PostgreSQL",
    }


@app.get("/api/search")
def search(
    q: str = Query(default="", max_length=120),
    category: str | None = None,
    city: str | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    in_stock: bool = False,
    sort: str = "featured",
) -> dict[str, Any]:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="Minimum price cannot be greater than maximum price")
    try:
        result = search_products(q, category, city, min_price, max_price, in_stock, sort)
        return {**result, "filters": {"q": q, "category": category, "city": city, "min_price": min_price, "max_price": max_price, "in_stock": in_stock, "sort": sort}}
    except Exception as exc:
        logger.exception("OpenSearch query failed")
        raise HTTPException(status_code=503, detail=f"OpenSearch is unavailable: {str(exc)[:160]}") from exc


@app.get("/api/cart/{session_id}")
def get_cart(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return cart_payload(db, session_id)


@app.post("/api/cart/{session_id}")
def add_to_cart(session_id: str, payload: CartAdd, db: Session = Depends(get_db)) -> dict[str, Any]:
    product = db.scalar(select(Product).where(Product.id == payload.product_id, Product.active.is_(True)).with_for_update())
    if product is None:
        raise HTTPException(status_code=404, detail="That product is no longer available")
    existing = db.scalar(select(CartItem).where(CartItem.session_id == session_id, CartItem.product_id == product.id).with_for_update())
    current_quantity = existing.quantity if existing else 0
    requested = current_quantity + payload.quantity
    if requested > product.available_stock:
        raise HTTPException(status_code=409, detail=f"Only {product.available_stock} units are currently available")
    if existing:
        existing.quantity = requested
    else:
        db.add(CartItem(session_id=session_id, product_id=product.id, quantity=payload.quantity))
    db.commit()
    return cart_payload(db, session_id)


@app.patch("/api/cart/{session_id}/{item_id}")
def update_cart_item(session_id: str, item_id: int, payload: CartUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.session_id == session_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")
    product = db.scalar(select(Product).where(Product.id == item.product_id).with_for_update())
    if product is None or payload.quantity > product.available_stock:
        available = product.available_stock if product else 0
        raise HTTPException(status_code=409, detail=f"Only {available} units are currently available")
    item.quantity = payload.quantity
    db.commit()
    return cart_payload(db, session_id)


@app.delete("/api/cart/{session_id}/{item_id}")
def remove_cart_item(session_id: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.session_id == session_id))
    if item is not None:
        db.delete(item)
        db.commit()
    return cart_payload(db, session_id)


@app.post("/api/orders", status_code=201)
def place_order(payload: CheckoutRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    cart_rows = db.scalars(
        select(CartItem).where(CartItem.session_id == payload.session_id).order_by(CartItem.product_id).with_for_update()
    ).all()
    if not cart_rows:
        raise HTTPException(status_code=400, detail="Your bag is empty")

    product_ids = [row.product_id for row in cart_rows]
    products = db.scalars(select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()).all()
    product_map = {product.id: product for product in products}
    for row in cart_rows:
        product = product_map.get(row.product_id)
        if product is None or row.quantity > product.available_stock:
            available = product.available_stock if product else 0
            raise HTTPException(status_code=409, detail=f"Stock changed for an item in your bag. Only {available} remain. Please update your bag.")

    customer = db.scalar(select(Customer).where(Customer.email == payload.email.lower()).with_for_update())
    if customer is None:
        customer = Customer(
            name=payload.name.strip(), email=payload.email.lower(), phone=payload.phone.strip(),
            city=payload.city.strip(), address_line=payload.address.strip(),
        )
        db.add(customer)
        db.flush()
    else:
        customer.name = payload.name.strip()
        customer.phone = payload.phone.strip()
        customer.city = payload.city.strip()
        customer.address_line = payload.address.strip()

    subtotal = 0
    order_lines = []
    for row in cart_rows:
        product = product_map[row.product_id]
        product.reserved_stock += row.quantity
        subtotal += product.price_paise * row.quantity
        order_lines.append({
            "product_id": product.id,
            "sku": product.sku,
            "product_name": product.name,
            "image_url": product.image_url,
            "unit_price_paise": product.price_paise,
            "quantity": row.quantity,
        })

    delivery_fee = 0 if subtotal >= 99900 else 4900
    order_number = f"DF-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"
    order = StoreOrder(
        order_number=order_number,
        customer_id=customer.id,
        status="PROCESSING",
        subtotal_paise=subtotal,
        total_paise=subtotal + delivery_fee,
        delivery_address=payload.address.strip(),
        delivery_city=payload.city.strip(),
        items=[OrderItem(**line) for line in order_lines],
    )
    db.add(order)
    db.flush()

    event_id = str(uuid.uuid4())
    event_payload = {
        "event_id": event_id,
        "event_type": "order.placed",
        "occurred_at": utcnow().isoformat(),
        "order_id": order.id,
        "order_number": order.order_number,
        "customer": {"name": customer.name, "email": customer.email, "city": customer.city},
        "items": [
            {"product_id": line["product_id"], "sku": line["sku"], "quantity": line["quantity"], "unit_price_paise": line["unit_price_paise"]}
            for line in order_lines
        ],
        "total_paise": order.total_paise,
    }
    db.add(OutboxEvent(event_id=event_id, event_type="order.placed", aggregate_id=str(order.id), payload=event_payload))
    for row in cart_rows:
        db.delete(row)
    db.commit()

    return {
        "order_number": order.order_number,
        "status": order.status,
        "subtotal_paise": order.subtotal_paise,
        "delivery_fee_paise": delivery_fee,
        "total_paise": order.total_paise,
        "item_count": sum(line["quantity"] for line in order_lines),
        "event_id": event_id,
        "message": "Order saved. Waiting for the Kafka inventory consumer to confirm it.",
    }


@app.get("/api/orders/{order_number}")
def get_order(order_number: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    order = db.scalar(
        select(StoreOrder).options(selectinload(StoreOrder.items), joinedload(StoreOrder.customer)).where(StoreOrder.order_number == order_number)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_number": order.order_number,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
        "subtotal_paise": order.subtotal_paise,
        "total_paise": order.total_paise,
        "customer": {"name": order.customer.name, "email": order.customer.email, "city": order.customer.city},
        "items": [
            {"product_id": item.product_id, "product_name": item.product_name, "sku": item.sku, "quantity": item.quantity, "unit_price_paise": item.unit_price_paise, "image_url": item.image_url}
            for item in order.items
        ],
    }


@app.get("/api/ops/overview")
def ops_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    order_count = db.scalar(select(func.count(StoreOrder.id))) or 0
    product_count = db.scalar(select(func.count(Product.id)).where(Product.active.is_(True))) or 0
    event_count = db.scalar(select(func.count(EventLog.id))) or 0
    pending_count = db.scalar(select(func.count(OutboxEvent.event_id)).where(OutboxEvent.published_at.is_(None))) or 0
    stock_total = db.scalar(select(func.coalesce(func.sum(Product.stock_on_hand - Product.reserved_stock), 0))) or 0
    recent = db.scalars(select(EventLog).order_by(EventLog.created_at.desc()).limit(8)).all()
    return {
        "metrics": {"orders": order_count, "products": product_count, "processed_events": event_count, "pending_events": pending_count, "available_units": int(stock_total)},
        "events": [
            {"event_id": event.event_id, "event_type": event.event_type, "order_number": event.order_number, "status": event.status, "message": event.message, "created_at": event.created_at.isoformat()}
            for event in recent
        ],
    }


@app.post("/api/ops/reindex")
def rebuild_search_index(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        indexed = reindex_all(db)
        return {"indexed": indexed, "index": settings.opensearch_index, "source": "PostgreSQL → Aiven OpenSearch"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:200]) from exc
