from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = (ROOT / "app.py").read_text(encoding="utf-8")
LIBRARY = (ROOT / "frontend/app/library/page.tsx").read_text(encoding="utf-8")
DETAIL = (ROOT / "frontend/app/library/[slug]/page.tsx").read_text(encoding="utf-8")

def test_shared_catalog_inventory_and_entitlement_schema():
    for name in ("catalog_products", "manga_chapters", "subscription_entitlements"):
        assert f"CREATE TABLE IF NOT EXISTS {name}" in APP

def test_catalog_api_exposes_shared_availability():
    assert "@app.get('/api/catalog/products')" in APP
    assert "availability_status" in APP and "inventory_quantity" in APP

def test_cart_rejects_unavailable_inventory_and_formats():
    assert "Out of stock" in APP
    assert "digital_available" in APP

def test_chapter_api_and_subscription_entitlement_are_connected():
    assert "@app.get('/api/manga/<int:series_book_id>/chapters')" in APP
    assert "@app.get('/api/subscriptions/me')" in APP
    assert "early_access_at" in APP and "membership_required" in APP
    assert "chapterItems" in DETAIL and "chapterStatus" in DETAIL

def test_library_renders_backend_availability():
    assert "availability_status" in LIBRARY
    assert "availability-chip" in LIBRARY
