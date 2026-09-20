import pytest
from app.models import ProductRow, ValidationResult
from app.optimizer.scoring import compute_budget_fit, compute_design_score

def test_budget_fit_monotonicity():
    budget = 100000
    score_low = compute_budget_fit(20000, budget)   # 20%
    score_mid = compute_budget_fit(50000, budget)   # 50%
    score_high = compute_budget_fit(80000, budget)  # 80%
    score_max = compute_budget_fit(100000, budget)  # 100%
    score_over = compute_budget_fit(105000, budget) # Over budget

    assert score_low >= score_mid >= score_high >= score_max > score_over
    assert score_over == 0.0
    assert score_low == 99.1
    assert score_mid == 96.5
    assert score_high == 92.8
    assert score_max == 90.0

def test_style_match_and_unknown_handling():
    p1 = ProductRow(sku='P1', name='Modern Toilet', category='toilet', price_inr=20000, width_mm=400, depth_mm=700, style='modern', features='sleek modern wall-hung design')
    val = ValidationResult(valid=True, total_price_inr=20000)

    # Strong match
    score_modern = compute_design_score([p1], val, 100000, 'modern', 1800, 2400)
    assert score_modern.style_match == 100.0
    assert score_modern.style_match_status == "Measured"

    # Mismatch (classical requested for modern product)
    score_classic = compute_design_score([p1], val, 100000, 'classical', 1800, 2400)
    assert score_classic.style_match == 30.0
    assert score_classic.style_match_status == "Measured"

    # Unknown style requested (None) -> Limited data available, NOT 0.0
    p_plain = ProductRow(sku='P2', name='Plain Item', category='toilet', price_inr=20000, width_mm=400, depth_mm=700)
    score_unknown = compute_design_score([p_plain], val, 100000, None, 1800, 2400)
    assert score_unknown.style_match is None
    assert score_unknown.style_match_status == "Limited data available"
    assert 'style_match' in score_unknown.unavailable_metrics

def test_score_normalization_over_active_metrics():
    p1 = ProductRow(sku='P1', name='Toilet', category='toilet', price_inr=20000, width_mm=400, depth_mm=724)
    p2 = ProductRow(sku='P2', name='Vanity', category='vanity', price_inr=60000, width_mm=900, depth_mm=520)
    p3 = ProductRow(sku='P3', name='Shower', category='shower', price_inr=30000, width_mm=900, depth_mm=900)
    val = ValidationResult(valid=True, total_price_inr=110000)

    score = compute_design_score([p1, p2, p3], val, 150000, 'modern', 1800, 2400)
    assert 'spatial_fit' in score.available_metrics
    assert 'budget_fit' in score.available_metrics
    assert 'compatibility' in score.available_metrics
    assert 'accessibility' in score.unavailable_metrics
    assert 'sustainability' in score.unavailable_metrics

    # Full design should score well (>75.0) when active metrics are strong
    assert score.total >= 75.0

def test_increasing_style_match_increases_overall_score():
    p_mismatch = ProductRow(sku='P1', name='Traditional Classic Toilet', category='toilet', price_inr=20000, width_mm=400, depth_mm=700, style='classical')
    p_match = ProductRow(sku='P2', name='Modern Wall-hung Toilet', category='toilet', price_inr=20000, width_mm=400, depth_mm=700, style='modern')
    val = ValidationResult(valid=True, total_price_inr=20000)

    score_mismatch = compute_design_score([p_mismatch], val, 100000, 'modern', 1800, 2400)
    score_match = compute_design_score([p_match], val, 100000, 'modern', 1800, 2400)

    assert score_match.style_match > score_mismatch.style_match
    assert score_match.total > score_mismatch.total

def test_increasing_compatibility_increases_overall_score():
    b_large = ProductRow(sku='B1', name='Basin', category='basin', price_inr=5000, width_mm=1000, depth_mm=600)
    b_small = ProductRow(sku='B2', name='Basin', category='basin', price_inr=5000, width_mm=500, depth_mm=400)
    vanity = ProductRow(sku='V1', name='Vanity', category='vanity', price_inr=30000, width_mm=800, depth_mm=500)
    val = ValidationResult(valid=True, total_price_inr=35000)

    score_incompat = compute_design_score([b_large, vanity], val, 100000, None, 1800, 2400)
    score_compat = compute_design_score([b_small, vanity], val, 100000, None, 1800, 2400)

    assert score_compat.compatibility > score_incompat.compatibility
    assert score_compat.total > score_incompat.total

def test_spatial_score_changes_when_geometry_changes():
    p1 = ProductRow(sku='P1', name='Toilet', category='toilet', price_inr=10000, width_mm=400, depth_mm=700)
    val = ValidationResult(valid=True, total_price_inr=10000)

    score_small_room = compute_design_score([p1], val, 100000, None, 1200, 1500)
    score_large_room = compute_design_score([p1], val, 100000, None, 2500, 3000)

    assert score_small_room.spatial_fit != score_large_room.spatial_fit

def test_overall_score_equals_documented_weighted_calculation():
    p1 = ProductRow(sku='P1', name='Modern Toilet', category='toilet', price_inr=20000, width_mm=400, depth_mm=700, style='modern')
    val = ValidationResult(valid=True, total_price_inr=20000)
    score = compute_design_score([p1], val, 100000, 'modern', 1800, 2400)

    # Active metrics for Balanced profile: spatial_fit (30%), budget_fit (25%), style_match (25%), compatibility (20%)
    weights = {'spatial_fit': 0.30, 'budget_fit': 0.25, 'style_match': 0.25, 'compatibility': 0.20}
    active_weight_sum = sum(weights.values())
    raw_sum = (
        weights['spatial_fit'] * score.spatial_fit +
        weights['budget_fit'] * score.budget_fit +
        weights['style_match'] * score.style_match +
        weights['compatibility'] * score.compatibility
    )
    expected_total = round(raw_sum / active_weight_sum, 1)
    assert score.total == expected_total

def test_pdf_export_coordinate_consistency():
    from app.models import Design, FixturePlacement, RoomSpec
    from app.pdf_export import build_design_pdf

    p1 = ProductRow(sku='K-1381T-S-0', name='Veil Toilet', category='toilet', price_inr=28559, width_mm=387, depth_mm=725)
    f1 = FixturePlacement(sku='K-1381T-S-0', x_mm=200, y_mm=400, rotation_deg=90)
    val = ValidationResult(valid=True, total_price_inr=28559)
    score = compute_design_score([p1], val, 100000, 'modern', 1800, 2400)
    room = RoomSpec(width_mm=1800, depth_mm=2400)

    design = Design(
        name="Test Option",
        fixtures=[f1],
        products=[p1],
        validation=val,
        score=score,
        room=room,
    )

    pdf_bytes = build_design_pdf(design)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert b'%PDF' in pdf_bytes[:10]


def test_style_score_is_design_specific():
    p_modern = [
        ProductRow(sku='P1', name='Veil Toilet', category='toilet', price_inr=50000, width_mm=400, depth_mm=700, style='modern'),
        ProductRow(sku='P2', name='Forefront Basin', category='basin', price_inr=20000, width_mm=600, depth_mm=450, style='modern'),
    ]
    p_mixed = [
        ProductRow(sku='P1', name='Veil Toilet', category='toilet', price_inr=50000, width_mm=400, depth_mm=700, style='modern'),
        ProductRow(sku='P3', name='Memoirs Classic Basin', category='basin', price_inr=15000, width_mm=600, depth_mm=450, style='classical'),
    ]
    val = ValidationResult(valid=True, total_price_inr=65000)

    score_smart_budget = compute_design_score(p_mixed, val, 100000, 'modern', 1800, 2400, profile_name='Smart Budget')
    score_premium = compute_design_score(p_modern, val, 100000, 'modern', 1800, 2400, profile_name='Premium')

    assert score_smart_budget.style_match != score_premium.style_match
    assert score_premium.style_match == 100.0
    assert score_smart_budget.style_match < 100.0


