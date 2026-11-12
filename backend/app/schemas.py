from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CartAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


class CartUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=30)
    address: str = Field(min_length=8, max_length=500)
    city: str = Field(min_length=2, max_length=80)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    slug: str
    name: str
    description: str
    category: str
    brand: str
    price_paise: int
    mrp_paise: int
    stock_on_hand: int
    reserved_stock: int
    city: str
    image_url: str
    badge: str | None
    rating: float
    review_count: int
    tags: list[str]
    featured_rank: int
    active: bool
    available_stock: int

