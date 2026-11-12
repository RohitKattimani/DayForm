from sqlalchemy import select

from app.database import SessionLocal
from app.models import Product

PRODUCTS = [
    {
        "sku": "DF-AUD-001", "slug": "sonic-wireless-headphones", "name": "Sonic Wireless Headphones",
        "description": "Immersive, balanced sound with soft memory-foam cups and 42-hour battery life.",
        "category": "Audio & Tech", "brand": "Dayform Studio", "price_paise": 649900, "mrp_paise": 799900,
        "stock_on_hand": 31, "city": "Bengaluru", "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1000&q=85",
        "badge": "BESTSELLER", "rating": 4.8, "review_count": 284, "tags": ["bluetooth", "headphones", "wireless", "audio", "music"], "featured_rank": 1,
    },
    {
        "sku": "DF-HOM-002", "slug": "arc-table-lamp", "name": "Arc Table Lamp",
        "description": "A warm, sculptural glow for slow mornings and late-night reading.",
        "category": "Home & Living", "brand": "Form & Field", "price_paise": 329900, "mrp_paise": 399900,
        "stock_on_hand": 18, "city": "Mumbai", "image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=1000&q=85",
        "badge": "DESIGN PICK", "rating": 4.7, "review_count": 126, "tags": ["lamp", "lighting", "home", "decor", "table"], "featured_rank": 2,
    },
    {
        "sku": "DF-LIF-003", "slug": "cloud-knit-throw", "name": "Cloud Knit Throw",
        "description": "A soft, breathable layer woven for the art of doing absolutely nothing.",
        "category": "Home & Living", "brand": "Form & Field", "price_paise": 249900, "mrp_paise": 299900,
        "stock_on_hand": 42, "city": "Pune", "image_url": "https://images.unsplash.com/photo-1600369671236-e74521d4b6ad?auto=format&fit=crop&w=1000&q=85",
        "badge": "SOFT FAVOURITE", "rating": 4.9, "review_count": 91, "tags": ["blanket", "throw", "knit", "home", "textile"], "featured_rank": 3,
    },
    {
        "sku": "DF-WEA-004", "slug": "everyday-canvas-tote", "name": "Everyday Canvas Tote",
        "description": "Room for the essentials, made from durable, heavyweight cotton canvas.",
        "category": "Carry & Wear", "brand": "Dayform Studio", "price_paise": 119900, "mrp_paise": 149900,
        "stock_on_hand": 57, "city": "Bengaluru", "image_url": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?auto=format&fit=crop&w=1000&q=85",
        "badge": None, "rating": 4.6, "review_count": 203, "tags": ["bag", "tote", "canvas", "cotton", "carry"], "featured_rank": 4,
    },
    {
        "sku": "DF-TEC-005", "slug": "orbit-bluetooth-speaker", "name": "Orbit Bluetooth Speaker",
        "description": "Pocket-sized, room-filling sound with a water-resistant, travel-ready build.",
        "category": "Audio & Tech", "brand": "Dayform Studio", "price_paise": 289900, "mrp_paise": 349900,
        "stock_on_hand": 24, "city": "Delhi", "image_url": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=1000&q=85",
        "badge": "NEW ARRIVAL", "rating": 4.7, "review_count": 74, "tags": ["speaker", "bluetooth", "wireless", "audio", "portable"], "featured_rank": 5,
    },
    {
        "sku": "DF-ACC-006", "slug": "studio-analog-watch", "name": "Studio Analog Watch",
        "description": "A clean dial, considered proportions and a strap made for everyday wear.",
        "category": "Carry & Wear", "brand": "Northline", "price_paise": 429900, "mrp_paise": 499900,
        "stock_on_hand": 13, "city": "Mumbai", "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1000&q=85",
        "badge": "LOW STOCK", "rating": 4.8, "review_count": 158, "tags": ["watch", "analog", "accessory", "fashion", "timepiece"], "featured_rank": 6,
    },
    {
        "sku": "DF-HOM-007", "slug": "stoneware-coffee-set", "name": "Stoneware Coffee Set",
        "description": "Two tactile ceramic cups that make the first sip feel like a ritual.",
        "category": "Home & Living", "brand": "Form & Field", "price_paise": 179900, "mrp_paise": 219900,
        "stock_on_hand": 36, "city": "Chennai", "image_url": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=1000&q=85",
        "badge": None, "rating": 4.9, "review_count": 112, "tags": ["coffee", "mug", "cup", "ceramic", "kitchen"], "featured_rank": 7,
    },
    {
        "sku": "DF-TEC-008", "slug": "pulse-smartwatch-band", "name": "Pulse Sport Watch",
        "description": "A lightweight everyday tracker with a crisp display and seven-day battery.",
        "category": "Audio & Tech", "brand": "Dayform Studio", "price_paise": 559900, "mrp_paise": 649900,
        "stock_on_hand": 16, "city": "Hyderabad", "image_url": "https://images.unsplash.com/photo-1544117519-31a4b719223d?auto=format&fit=crop&w=1000&q=85",
        "badge": None, "rating": 4.5, "review_count": 88, "tags": ["smartwatch", "fitness", "wearable", "watch", "tech"], "featured_rank": 8,
    },
    {
        "sku": "DF-BEA-009", "slug": "botanical-hand-care", "name": "Botanical Hand Care Set",
        "description": "A gentle, plant-inspired hand wash and nourishing lotion duo.",
        "category": "Care & Wellness", "brand": "Kindred Rituals", "price_paise": 149900, "mrp_paise": 189900,
        "stock_on_hand": 29, "city": "Bengaluru", "image_url": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=1000&q=85",
        "badge": "GIFT READY", "rating": 4.8, "review_count": 67, "tags": ["skincare", "handwash", "lotion", "care", "wellness", "gift"], "featured_rank": 9,
    },
    {
        "sku": "DF-WEA-010", "slug": "weekend-sneaker", "name": "Weekend Everyday Sneaker",
        "description": "An easy-wearing low-top with a cushioned footbed and versatile neutral finish.",
        "category": "Carry & Wear", "brand": "Northline", "price_paise": 389900, "mrp_paise": 449900,
        "stock_on_hand": 22, "city": "Pune", "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1000&q=85",
        "badge": "COMMUNITY PICK", "rating": 4.7, "review_count": 176, "tags": ["sneaker", "shoes", "footwear", "fashion", "casual"], "featured_rank": 10,
    },
    {
        "sku": "DF-HOM-011", "slug": "minimal-desk-chair", "name": "Minimal Desk Chair",
        "description": "Thoughtful support and a timeless silhouette for your corner of focus.",
        "category": "Home & Living", "brand": "Form & Field", "price_paise": 899900, "mrp_paise": 1049900,
        "stock_on_hand": 8, "city": "Delhi", "image_url": "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=1000&q=85",
        "badge": "ONLY 8 LEFT", "rating": 4.6, "review_count": 48, "tags": ["chair", "desk", "office", "furniture", "home"], "featured_rank": 11,
    },
    {
        "sku": "DF-TEC-012", "slug": "instant-film-camera", "name": "Instant Film Camera",
        "description": "Make the little moments tangible with a playful, point-and-shoot instant camera.",
        "category": "Audio & Tech", "brand": "Dayform Studio", "price_paise": 749900, "mrp_paise": 849900,
        "stock_on_hand": 11, "city": "Mumbai", "image_url": "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1000&q=85",
        "badge": "THE FUN ONE", "rating": 4.8, "review_count": 139, "tags": ["camera", "film", "instant", "photography", "tech"], "featured_rank": 12,
    },
]


def seed_products() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Product.id).limit(1))
        if existing is not None:
            return
        db.add_all([Product(**item) for item in PRODUCTS])
        db.commit()
