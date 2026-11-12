"""Small pure-logic regression tests for the inventory availability contract."""

from app.models import Product


def test_available_stock_subtracts_reserved_units():
    product = Product(
        sku="TEST-1", slug="test-1", name="Test", description="Test item",
        category="Test", brand="Test", price_paise=100, mrp_paise=100,
        stock_on_hand=8, reserved_stock=3, city="Bengaluru", image_url="https://example.com/item.jpg",
    )
    assert product.available_stock == 5


def test_available_stock_never_goes_below_zero():
    product = Product(
        sku="TEST-2", slug="test-2", name="Test", description="Test item",
        category="Test", brand="Test", price_paise=100, mrp_paise=100,
        stock_on_hand=2, reserved_stock=4, city="Bengaluru", image_url="https://example.com/item.jpg",
    )
    assert product.available_stock == 0
