# Dayform : The Everyday Edit

An online-store demo built around the three required Aiven services:

- **Aiven for PostgreSQL** : catalogue, customers, carts, order records, stock reservations and the transactional outbox.
- **Aiven for Apache Kafka** : durable `order.placed` and `inventory.updated` events, published by a background worker and processed by a separate consumer.
- **Aiven for OpenSearch** : product discovery with fuzzy matching, category/city/price/availability filters and sorting.

The storefront is React + Vite. The API and workers are Python + FastAPI. Docker Compose runs the entire application while the data services remain on Aiven.

> **Security:** credentials pasted into a chat or committed to a repository must be treated as exposed. Rotate the PostgreSQL and Kafka passwords in Aiven before running this project. Never commit `.env`; only `.env.example` belongs in Git.

## 1. Aiven setup

Create or select one Aiven project and provision all three services in that project. The Aiven Free Tier/trial availability and quotas can change, so use the limits currently shown in your console.

### PostgreSQL

1. Open your Aiven PostgreSQL service and copy the Service URI from **Overview → Connection information**.
2. Rotate the password first, then use the rotated credentials in `DATABASE_URL`.
3. Keep TLS enabled with `sslmode=require`.
4. The application creates its tables on first boot (`AUTO_CREATE_TABLES=true`) and seeds a small editorial product catalogue only when the `products` table is empty.

The `.env.example` already contains the non-secret host and port values shared for your PostgreSQL and Kafka services. Replace `CHANGE_ME` with the rotated passwords. If your PostgreSQL password contains URI-reserved characters, URL-encode it before placing it in the URI.

### Apache Kafka

1. Open the Aiven Kafka service and confirm SASL authentication is enabled for the service user.
2. Copy the SASL host and port into `KAFKA_BOOTSTRAP_SERVERS` and use the rotated credentials.
3. Use `KAFKA_SASL_MECHANISM=SCRAM-SHA-256` (Aiven's recommended username/password method) unless the Quick connect snippet for your service explicitly specifies another enabled mechanism.
4. Download the Kafka CA certificate in Aiven Quick connect and save it as `certs/ca.pem`. The Compose file mounts this folder read-only and `.env.example` points `KAFKA_CA_PATH` at `/certs/ca.pem`.
5. The publisher creates the `store.events` topic (3 partitions, replication factor 1) if it does not already exist. If your service policy does not allow topic creation, create that topic in Aiven Console and restart the workers.

### OpenSearch

1. Provision Aiven for OpenSearch.
2. Copy the full HTTPS Service URI from **Overview → Connection information**. It has the form `https://USER:PASSWORD@HOST:PORT`.
3. Put that complete value in `OPENSEARCH_URL`. Do not put it in frontend code.
4. The API creates the `dayform-products-v1` index and performs an initial PostgreSQL → OpenSearch sync at startup.

## 2. Configure the project

From the project root:

```bash
cp .env.example .env
```

Edit `.env` and replace the PostgreSQL and Kafka passwords with the **rotated** values. Add your OpenSearch service URI. Do not share or commit `.env`.

## 3. Run everything with Docker (recommended for the demo)

Requirements: Docker Desktop with Compose v2.

```bash
docker compose up --build
```

Open:

- Storefront: <http://localhost:8080>
- API health: <http://localhost:8080/api/health>
- Interactive API docs: <http://localhost:8080/docs>

Compose starts four containers:

| Container | Responsibility |
|---|---|
| `api` | FastAPI endpoints, PostgreSQL persistence and OpenSearch search API |
| `publisher` | Polls the PostgreSQL outbox and publishes events to Kafka |
| `consumer` | Consumes Kafka events, commits inventory changes in PostgreSQL and refreshes OpenSearch |
| `web` | Serves the production React build and proxies `/api` to FastAPI |

Check logs during the order demo:

```bash
docker compose logs -f publisher consumer api
```

## 4. Run locally without Docker

Use Python 3.11+ and Node.js 20+.

Terminal 1 : backend API:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Terminal 2 : outbox publisher:

```bash
cd backend
# activate the same virtual environment
python -m app.workers.publisher
```

Terminal 3 : Kafka consumer:

```bash
cd backend
# activate the same virtual environment
python -m app.workers.consumer
```

Terminal 4 : storefront:

```bash
cd frontend
npm install
npm run dev
```

Before starting the local workers, change `KAFKA_CA_PATH` in `.env` to the local certificate path (for example `../certs/ca.pem` when launching from `backend/`). Open <http://localhost:5173>. Vite proxies `/api` to `http://localhost:8000`.

## 5. The important order flow

```text
Browser checkout
   │
   ▼
FastAPI transaction ──► PostgreSQL
   │                      ├─ lock product rows (SELECT FOR UPDATE)
   │                      ├─ verify available stock
   │                      ├─ reserve units (stock cannot be double-sold)
   │                      ├─ save customer + order + order items
   │                      └─ write order.placed to transactional outbox
   │
   ▼
Outbox publisher ──────► Aiven Kafka: store.events
                              │
                              ▼
                       Inventory consumer
                              ├─ idempotency check by event_id
                              ├─ deduct stock_on_hand and reserved_stock in PostgreSQL
                              ├─ mark order CONFIRMED
                              └─ enqueue inventory.updated in outbox
                                      │
                                      ▼
                             Outbox publisher → Kafka
                                      │
                                      ▼
                             Inventory consumer
                                      └─ refresh changed product documents in OpenSearch

Search bar ─────────────► Aiven OpenSearch
                           ├─ fuzzy multi-field matching
                           ├─ category and city filters
                           ├─ price range and in-stock filters
                           └─ relevance / price / rating sorting
```

### Why reserve and then deduct?

Checkout reserves available units while holding PostgreSQL row locks. This prevents two buyers from both checking out the last unit. The Kafka consumer then finalizes the sale by decrementing physical stock and releasing the reservation. An outbox row is written in the same PostgreSQL transaction as the order, so the app does not lose the event if the API process exits after committing the order.

Kafka delivery is at-least-once. `processed_events` makes the consumer idempotent: if Kafka redelivers after a crash, stock is not deducted twice. The consumer commits its Kafka offset only after the database and OpenSearch steps complete.

## 6. Demo checklist

1. Open the storefront and scroll to **The engine room**. Confirm PostgreSQL, Kafka and OpenSearch all show **Connected**.
2. Search for `bluetoth`. The OpenSearch-backed search should still find Bluetooth products. The search context displays `Aiven OpenSearch` and the query latency.
3. Try category, city, in-stock and price sorting controls.
4. Add one item to the bag and place an order using a test email/address.
5. The order confirmation modal shows the sequence: order saved → Kafka event processed → search index refreshed.
6. Open **View live signals** in The engine room. The metrics and event stream should show the order and inventory events.
7. Search for the purchased product again. The available stock count should have dropped, with the updated value coming from OpenSearch.
8. For a stronger concurrency demo, put the last available item in two independent browser sessions and attempt checkout in both. PostgreSQL row locking and the reservation check allow only one checkout to reserve the final unit.

## 7. API surface

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Live PostgreSQL, Kafka and OpenSearch connectivity checks |
| GET | `/api/catalog` | Browse catalogue and load available categories/cities from PostgreSQL |
| GET | `/api/search` | Fuzzy product search and facets/filters from OpenSearch |
| GET | `/api/cart/{session_id}` | Read a persisted cart |
| POST | `/api/cart/{session_id}` | Add product quantity to cart |
| PATCH | `/api/cart/{session_id}/{item_id}` | Update cart quantity |
| DELETE | `/api/cart/{session_id}/{item_id}` | Remove cart item |
| POST | `/api/orders` | Reserve stock and persist order + outbox event |
| GET | `/api/orders/{order_number}` | Poll order processing status |
| GET | `/api/ops/overview` | Store metrics and recent consumed events |
| POST | `/api/ops/reindex` | Rebuild OpenSearch product index from PostgreSQL |

## 8. Submission notes

**What makes the demo more than a static storefront:** the three services are on the critical path. PostgreSQL is the transactional source of truth, Kafka carries order/inventory events asynchronously, and OpenSearch is the actual query backend used by the shopping search bar. The engine-room panel makes each service's health and the event stream visible to judges.

**Before submission:**

- Confirm all three Aiven endpoints are healthy from the machine/container running the app.
- Confirm `.env` is ignored by Git and no credentials appear in commit history, screenshots, logs or the pitch deck.
- Run at least one end-to-end order and capture the event stream + reduced inventory in the demo.
- Replace the seed catalogue imagery/copy with your own product choices if the event asks for a real retailer-specific catalogue.

## 9. Troubleshooting

- **PostgreSQL SSL/connection error:** confirm the full URI and `sslmode=require`; check that the service is running and the rotated password is correct.
- **Kafka authentication/TLS error:** check the SASL port, username/password, `KAFKA_SASL_MECHANISM` and `KAFKA_CA_PATH`. Download the CA certificate from Aiven Quick connect; SASL and client-certificate connections use different ports.
- **Topic authorization error:** create `store.events` in Aiven Console and make sure the service user has topic read/write permissions.
- **OpenSearch 401/403:** copy the complete HTTPS Service URI, check the user/password and confirm the URI is server-side in `.env` only.
- **Search shows connection warning:** catalogue browsing can still load from PostgreSQL, but fuzzy search requires a working OpenSearch URI and index. Use `POST /api/ops/reindex` after fixing credentials.
- **Order remains PROCESSING:** inspect `docker compose logs -f publisher consumer`. The publisher must publish to Kafka and the consumer must have topic read access. The UI polls order status for 30 seconds; refreshing the page or opening the order endpoint will show the latest persisted status.

## 10. Project structure

```text
backend/
  app/
    main.py                 # REST API and checkout transaction
    models.py               # PostgreSQL schema
    database.py             # SQLAlchemy engine/session + bootstrap
    search.py               # Aiven OpenSearch index and query DSL
    seed.py                 # Editorial demo catalogue
    workers/
      publisher.py          # PostgreSQL outbox → Kafka
      consumer.py           # Kafka → PostgreSQL + OpenSearch
      kafka_common.py       # Aiven SASL_SSL client configuration
frontend/
  src/App.jsx               # Responsive storefront and checkout UX
  src/styles.css            # Design system and responsive styling
  Dockerfile                # Production frontend image
  nginx.conf                # SPA serving + API reverse proxy
docker-compose.yml
.env.example
PITCH.md
```

**Payment note:** this hackathon build captures a demo order and delivery details but does not charge a card or integrate a payment gateway. That keeps the judging flow usable without collecting real payment data.


## 11. Run the lightweight tests

With the backend virtual environment active:

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. python -m pytest tests -q
```

The included tests cover the stock-availability calculation. The local API smoke test used during assembly also exercised catalogue seeding, cart persistence and order creation against SQLite; live Aiven/Kafka/OpenSearch behaviour still needs to be verified with your service credentials.
