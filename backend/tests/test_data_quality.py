import pandas as pd
import pytest
from app.repository import products, product_by_sku, CSV_PATH
from app.models import Design, FixturePlacement, ValidationResult, DesignScore, RoomSpec
from app.pdf_export import build_design_pdf

def test_all_spatial_ready_products_data_quality():
    """Verify that every product in the CSV has valid non-zero prices, dimensions, and unique SKUs."""
    df = pd.read_csv(CSV_PATH)
    assert len(df) > 0, "Product dataset must not be empty"

    skus = df['sku'].dropna().tolist()
    assert len(skus) == len(df), "All products must have a SKU"
    assert len(skus) == len(set(skus)), "SKUs must be unique"

    for idx, row in df.iterrows():
        sku = row['sku']
        name = str(row['product_name'])
        category = str(row['category'])
        price = row['price_inr']
        w = row['width_mm']
        d = row['depth_mm']

        assert isinstance(sku, str) and len(sku) > 0, f"Row {idx} missing valid SKU"
        assert name and name != 'nan', f"SKU {sku} missing product_name"
        assert category and category != 'nan', f"SKU {sku} missing category"
        assert pd.notna(price) and float(price) > 0, f"SKU {sku} ({name}) has invalid/missing price {price}"
        assert pd.notna(w) and int(w) > 0, f"SKU {sku} missing valid width_mm"
        assert pd.notna(d) and int(d) > 0, f"SKU {sku} missing valid depth_mm"

        acc = row.get('accessibility_rating')
        sust = row.get('sustainability_rating')
        prov = row.get('rating_provenance')

        assert pd.notna(acc) and 0 <= float(acc) <= 100, f"SKU {sku} accessibility_rating invalid"
        assert pd.notna(sust) and 0 <= float(sust) <= 100, f"SKU {sku} sustainability_rating invalid"
        assert pd.notna(prov) and len(str(prov)) > 0, f"SKU {sku} rating_provenance missing"

def test_luxe_vanity_price_regression():
    """Specific regression test for K-30460IN-MWF (Luxe Vanity) to prevent ₹0 price regression."""
    target_sku = 'K-30460IN-MWF'
    p = product_by_sku(target_sku)

    assert p is not None, f"Product {target_sku} must exist in repository"
    assert p.price_inr > 0, f"Product {target_sku} price must be positive, got {p.price_inr}"
    assert p.price_inr == 115849, f"Product {target_sku} price expected 115849, got {p.price_inr}"

    df = pd.read_csv(CSV_PATH)
    csv_row = df[df['sku'] == target_sku].iloc[0]
    assert p.price_inr == int(csv_row['price_inr'])

def test_luxe_vanity_pdf_export_price():
    """Verify PDF export builds valid PDF output for K-30460IN-MWF with non-zero total price."""
    target_sku = 'K-30460IN-MWF'
    p = product_by_sku(target_sku)
    assert p is not None
    assert p.price_inr == 115849

    design = Design(
        name='Luxe Test Design',
        fixtures=[FixturePlacement(sku=target_sku, x_mm=100, y_mm=100)],
        products=[p],
        validation=ValidationResult(valid=True, issues=[], total_price_inr=p.price_inr),
        room=RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=1000, door_width_mm=700),
        score=DesignScore(
            spatial_fit=90, budget_fit=85, style_match=100, compatibility=100,
            accessibility=0, sustainability=None, total=92.5
        )
    )

    pdf_bytes = build_design_pdf(design)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b'%PDF')
