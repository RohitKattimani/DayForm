from __future__ import annotations

import logging
from urllib.parse import unquote, urlsplit

from opensearchpy import OpenSearch
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Product

logger = logging.getLogger(__name__)


def get_opensearch_client() -> OpenSearch | None:
    if not settings.opensearch_configured:
        return None
    parsed = urlsplit(settings.opensearch_url)
    if not parsed.hostname:
        raise ValueError("OPENSEARCH_URL must be a full https:// URI from the Aiven OpenSearch Overview page")
    auth = None
    if parsed.username is not None:
        auth = (unquote(parsed.username), unquote(parsed.password or ""))
    return OpenSearch(
        hosts=[{"host": parsed.hostname, "port": parsed.port or 443, "scheme": parsed.scheme or "https"}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        ssl_assert_hostname=True,
        ssl_show_warn=True,
        timeout=6,
        max_retries=2,
        retry_on_timeout=True,
    )


INDEX_BODY = {
    "settings": {
        "index": {"number_of_shards": 1, "number_of_replicas": 0},
        "analysis": {
            "normalizer": {"folding_normalizer": {"type": "custom", "filter": ["lowercase", "asciifolding"]}},
        },
    },
    "mappings": {
        "properties": {
            "id": {"type": "integer"},
            "sku": {"type": "keyword"},
            "slug": {"type": "keyword"},
            "name": {"type": "text", "fields": {"raw": {"type": "keyword", "normalizer": "folding_normalizer"}}},
            "description": {"type": "text"},
            "category": {"type": "keyword"},
            "brand": {"type": "text", "fields": {"raw": {"type": "keyword", "normalizer": "folding_normalizer"}}},
            "price_paise": {"type": "integer"},
            "mrp_paise": {"type": "integer"},
            "stock_on_hand": {"type": "integer"},
            "reserved_stock": {"type": "integer"},
            "available_stock": {"type": "integer"},
            "in_stock": {"type": "boolean"},
            "city": {"type": "keyword"},
            "image_url": {"type": "keyword", "index": False},
            "badge": {"type": "keyword"},
            "rating": {"type": "float"},
            "review_count": {"type": "integer"},
            "tags": {"type": "text"},
            "featured_rank": {"type": "integer"},
        }
    },
}


def product_document(product: Product) -> dict:
    available = product.available_stock
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
        "available_stock": available,
        "in_stock": available > 0,
        "city": product.city,
        "image_url": product.image_url,
        "badge": product.badge,
        "rating": product.rating,
        "review_count": product.review_count,
        "tags": product.tags or [],
        "featured_rank": product.featured_rank,
    }


def ensure_index(client: OpenSearch | None = None) -> None:
    client = client or get_opensearch_client()
    if client is None:
        return
    if not client.indices.exists(index=settings.opensearch_index):
        client.indices.create(index=settings.opensearch_index, body=INDEX_BODY)
        logger.info("Created OpenSearch index %s", settings.opensearch_index)


def index_product(product: Product, client: OpenSearch | None = None, refresh: bool = False) -> None:
    client = client or get_opensearch_client()
    if client is None:
        raise RuntimeError("OpenSearch is not configured. Set OPENSEARCH_URL in .env.")
    ensure_index(client)
    client.index(
        index=settings.opensearch_index,
        id=str(product.id),
        body=product_document(product),
        refresh="wait_for" if refresh else False,
    )


def reindex_all(db: Session) -> int:
    client = get_opensearch_client()
    if client is None:
        raise RuntimeError("OpenSearch is not configured. Set OPENSEARCH_URL in .env.")
    ensure_index(client)
    products = db.scalars(select(Product).where(Product.active.is_(True))).all()
    for product in products:
        index_product(product, client=client)
    client.indices.refresh(index=settings.opensearch_index)
    return len(products)


def sync_product_ids(db: Session, product_ids: list[int]) -> None:
    client = get_opensearch_client()
    if client is None:
        raise RuntimeError("OpenSearch is not configured. Set OPENSEARCH_URL in .env.")
    ensure_index(client)
    if not product_ids:
        return
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    for product in products:
        index_product(product, client=client)
    client.indices.refresh(index=settings.opensearch_index)


def search_products(
    q: str = "",
    category: str | None = None,
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    in_stock: bool = False,
    sort: str = "featured",
    size: int = 48,
) -> dict:
    client = get_opensearch_client()
    if client is None:
        raise RuntimeError("OpenSearch is not configured. Set OPENSEARCH_URL in .env.")
    ensure_index(client)

    filters: list[dict] = []
    if category and category.lower() != "all":
        filters.append({"term": {"category": category}})
    if city and city.lower() != "all":
        filters.append({"term": {"city": city}})
    price_bounds: dict[str, int] = {}
    if min_price is not None:
        price_bounds["gte"] = min_price * 100
    if max_price is not None:
        price_bounds["lte"] = max_price * 100
    if price_bounds:
        filters.append({"range": {"price_paise": price_bounds}})
    if in_stock:
        filters.append({"term": {"in_stock": True}})

    if q.strip():
        text_query: dict = {
            "multi_match": {
                "query": q.strip(),
                "fields": ["name^5", "brand^3", "tags^2", "category^2", "description"],
                "type": "best_fields",
                "fuzziness": "AUTO",
                "prefix_length": 1,
                "operator": "or",
            }
        }
    else:
        text_query = {"match_all": {}}

    body: dict = {
        "size": min(max(size, 1), 100),
        "query": {"bool": {"must": [text_query], "filter": filters}},
        "track_total_hits": True,
    }
    sort_map = {
        "featured": [{"featured_rank": {"order": "asc"}}, {"_score": {"order": "desc"}}],
        "price_asc": [{"price_paise": {"order": "asc"}}],
        "price_desc": [{"price_paise": {"order": "desc"}}],
        "rating": [{"rating": {"order": "desc"}}],
    }
    body["sort"] = sort_map.get(sort, sort_map["featured"])
    result = client.search(index=settings.opensearch_index, body=body)
    hits = result.get("hits", {})
    return {
        "items": [hit.get("_source", {}) for hit in hits.get("hits", [])],
        "total": hits.get("total", {}).get("value", 0),
        "source": "Aiven OpenSearch",
        "took_ms": result.get("took", 0),
    }
