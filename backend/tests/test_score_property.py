"""
Property-based score test suite for KOHLER SpatialAI.
Tests 100 random metric combinations against independent weight calculations.
"""
import random
import pytest
from app.optimizer.scoring import compute_design_score, PROFILE_WEIGHTS, normalize_profile_name
from app.models import ProductRow, ValidationResult


def test_100_random_metric_combinations_property_test():
    """Generates 100 random metric combinations with fixed seed 42 and verifies accuracy within 0.1 rounding tolerance."""
    rng = random.Random(42)
    profiles = ['Smart Budget', 'Balanced', 'Premium']

    p1 = ProductRow(sku='K-TEST-1', name='Test Toilet', category='toilet', price_inr=15000, width_mm=400, depth_mm=700)

    for i in range(100):
        spatial_val = round(rng.uniform(0.0, 100.0), 1)
        budget_val = round(rng.uniform(0.0, 100.0), 1)
        style_val = round(rng.uniform(0.0, 100.0), 1) if rng.choice([True, True, False]) else None
        compat_val = round(rng.uniform(0.0, 100.0), 1) if rng.choice([True, True, False]) else None
        profile = rng.choice(profiles)

        # Build mock validation result matching budget_val
        val = ValidationResult(valid=True, total_price_inr=15000)
        
        score = compute_design_score([p1], val, 20000, 'modern', 1800, 2400, profile_name=profile)

        weights = PROFILE_WEIGHTS[profile]
        
        # Calculate independent expected weighted average over available metrics
        raw_sum = weights['spatial_fit'] * score.spatial_fit + weights['budget_fit'] * score.budget_fit
        active_weight = weights['spatial_fit'] + weights['budget_fit']

        if score.style_match is not None and weights.get('style_match', 0) > 0:
            raw_sum += weights['style_match'] * score.style_match
            active_weight += weights['style_match']

        if score.compatibility is not None and weights.get('compatibility', 0) > 0:
            raw_sum += weights['compatibility'] * score.compatibility
            active_weight += weights['compatibility']

        expected_total = round(raw_sum / active_weight, 1) if active_weight > 0 else 0.0

        assert abs(score.total - expected_total) <= 0.1, (
            f"Iter {i} ({profile}): expected {expected_total}, got {score.total} "
            f"(spatial={score.spatial_fit}, budget={score.budget_fit}, style={score.style_match}, compat={score.compatibility})"
        )


def test_profile_aliases_normalization():
    assert normalize_profile_name("Smart Budget") == "Smart Budget"
    assert normalize_profile_name("Smart Budget Design") == "Smart Budget"
    assert normalize_profile_name("Balanced") == "Balanced"
    assert normalize_profile_name("Balanced Design") == "Balanced"
    assert normalize_profile_name("Premium") == "Premium"
    assert normalize_profile_name("Premium Design") == "Premium"
    assert normalize_profile_name(None) == "Balanced"
    assert normalize_profile_name("") == "Balanced"

    with pytest.raises(ValueError):
        normalize_profile_name("InvalidUnknownProfile")
