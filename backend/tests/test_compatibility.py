import pytest
from app.models import ProductRow
from app.spatial.compatibility import evaluate_compatibility

def test_compatible_basin_and_vanity():
    basin = ProductRow(sku='B1', name='Basin 500', category='basin', price_inr=5000, width_mm=500, depth_mm=400)
    vanity = ProductRow(sku='V1', name='Vanity 900', category='vanity', price_inr=40000, width_mm=900, depth_mm=520)
    res = evaluate_compatibility([basin, vanity])
    assert res.compatible
    assert res.score == 100.0
    assert res.status == "Measured"
    assert "Optimal Fit" in res.message or "Compatible" in res.message

def test_incompatible_basin_larger_than_vanity():
    basin = ProductRow(sku='B2', name='Big Basin', category='basin', price_inr=8000, width_mm=1000, depth_mm=600)
    vanity = ProductRow(sku='V2', name='Small Vanity', category='vanity', price_inr=30000, width_mm=750, depth_mm=500)
    res = evaluate_compatibility([basin, vanity])
    assert not res.compatible
    assert res.score == 0.0
    assert res.status == "Known incompatible"
    assert "exceeds vanity counter" in res.message

def test_unsupported_compatibility_data():
    basin = ProductRow(sku='B3', name='Basin No Dims', category='basin', price_inr=5000)
    vanity = ProductRow(sku='V3', name='Vanity', category='vanity', price_inr=40000, width_mm=900, depth_mm=520)
    res = evaluate_compatibility([basin, vanity])
    assert res.compatible
    assert res.score is None
    assert res.status == "Limited data available"
    assert "Compatibility data unavailable" in res.message

def test_valid_independent_fixtures():
    toilet = ProductRow(sku='T1', name='Toilet', category='toilet', price_inr=15000, width_mm=366, depth_mm=724)
    shower = ProductRow(sku='S1', name='Shower', category='shower', price_inr=5000, width_mm=117, depth_mm=205)
    res = evaluate_compatibility([toilet, shower])
    assert res.compatible
    assert res.score == 90.0
    assert res.status == "Measured"
    assert "Valid independent fixtures" in res.message

def test_faucet_and_trim_compatibility():
    faucet = ProductRow(sku='F1', name='Tall Brass Faucet', category='faucet', price_inr=12000, finish='Polished Brass')
    basin = ProductRow(sku='B1', name='Vessel Basin', category='basin', price_inr=8000, height_mm=150, width_mm=450, depth_mm=450)
    vanity = ProductRow(sku='V1', name='Vanity 900', category='vanity', price_inr=40000, width_mm=900, depth_mm=520)
    res = evaluate_compatibility([faucet, basin, vanity])
    assert res.compatible
    assert res.score > 0

