"""Spatial engine tests using real SKUs from kohler_products.csv."""
import pytest
from app.models import RoomSpec, FixturePlacement, LayoutRequest
from app.spatial.validation import validate_layout

# Room: 1800mm wide, 2400mm deep, door on south wall offset 1000mm
R = RoomSpec(width_mm=1800, depth_mm=2400, door_offset_mm=1000, door_wall='south', door_width_mm=700)

# Real SKUs from CSV:
# K-3983IN-S-0  toilet      366×724mm   ₹13,769
# K-5401IN-0    smart_toilet 670×438mm  ₹577,999
# K-31601IN-E64 vanity      900×520mm   ₹102,739
# K-29777IN-0   smart_toilet 429×411mm  ₹379,999
# K-72425IN-CP  shower      117×205mm   ₹4,749 (functional envelope 900×900mm)


def v(fixtures, budget=None):
    return validate_layout(LayoutRequest(room=R, fixtures=fixtures, budget_inr=budget))


# ── Test 1: Valid single fixture well inside room ──────────────────────────────
def test_valid_room():
    # Toilet at (100, 1500) — 366×724mm, fully inside 1800×2400 room
    result = v([FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500)])
    assert result.valid, f"Expected valid, got issues: {result.issues}"


# ── Test 2: Fixture placed outside room boundary ──────────────────────────────
def test_outside():
    # Toilet at x=1600: 1600+366=1966 > 1800 → outside
    result = v([FixturePlacement(sku='K-3983IN-S-0', x_mm=1600, y_mm=800)])
    codes = [i.code for i in result.issues]
    assert 'outside_room' in codes, f"Expected outside_room, got: {codes}"


# ── Test 3: Two fixtures overlapping ─────────────────────────────────────────
def test_overlap():
    # Both placed at same position
    result = v([
        FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=800),
        FixturePlacement(sku='K-31601IN-E64', x_mm=100, y_mm=800),
    ])
    codes = [i.code for i in result.issues]
    assert 'overlap' in codes, f"Expected overlap, got: {codes}"


# ── Test 4: Fixture blocking door clearance zone ──────────────────────────────
def test_door():
    # Door on south wall (y=0), offset 1000mm, width 700mm → zone x=1000..1700, y=0..700
    # Place vanity 900×520mm at (1000, 0) → overlaps door swing
    result = v([FixturePlacement(sku='K-31601IN-E64', x_mm=1000, y_mm=0)])
    codes = [i.code for i in result.issues]
    assert 'door_collision' in codes, f"Expected door_collision, got: {codes}"


# ── Test 5: Budget exceeded ────────────────────────────────────────────────────
def test_budget():
    # Toilet ₹13,769 — budget only ₹1
    result = v([FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500)], budget=1)
    codes = [i.code for i in result.issues]
    assert 'over_budget' in codes, f"Expected over_budget, got: {codes}"


# ── Test 6: Unknown SKU ────────────────────────────────────────────────────────
def test_unknown():
    result = v([FixturePlacement(sku='FAKE-SKU-000', x_mm=100, y_mm=800)])
    codes = [i.code for i in result.issues]
    assert 'unknown_sku' in codes, f"Expected unknown_sku, got: {codes}"


# ── Test 7: Valid compact room with real product ───────────────────────────────
def test_compact_valid():
    # Vanity 900×520mm at (100, 1000) — well inside 1800×2400
    result = v([FixturePlacement(sku='K-31601IN-E64', x_mm=100, y_mm=1000)])
    assert result.valid, f"Expected valid, got issues: {result.issues}"


# ── Test 8: Two fixtures touching (edge-to-edge) but NOT overlapping ──────────
def test_touch_not_overlap():
    # Toilet at x=100, envelope width=650 → right edge at x=750
    # Vanity wash station envelope starts at x=750 → exact touch, no overlap
    result = v([
        FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500),
        FixturePlacement(sku='K-31601IN-E64', x_mm=950, y_mm=1500),
    ])
    codes = [i.code for i in result.issues]
    assert 'overlap' not in codes, f"Expected no overlap for touching fixtures, got: {codes}"



# ── Test 9: Rotated fixture (90 degrees) still inside room ────────────────────
def test_rotation():
    # Toilet 366×724mm rotated 90° (envelope 724×650mm)
    # At position (100, 1700): 100+724=824 < 1800, 1700+650=2350 < 2400 → valid
    result = v([FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1700, rotation_deg=90)])
    assert result.valid, f"Expected valid rotated fixture, got: {result.issues}"



# ── Test 10: Price accumulation is correct ────────────────────────────────────
def test_multiple_prices():
    # Toilet ₹13,769
    result = v([FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500)], budget=200000)
    assert result.total_price_inr == 13769, f"Expected 13769, got {result.total_price_inr}"


# ── Test 11: Valid design with toilet + vanity (no overlap, both inside) ──────
def test_toilet_plus_vanity():
    result = v([
        FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500),   # toilet 366×724
        FixturePlacement(sku='K-31601IN-E64', x_mm=100, y_mm=800),   # vanity 900×520
    ])
    assert result.valid, f"Expected valid layout, got: {result.issues}"


# ── Test 12: Both fixtures over budget together ────────────────────────────────
def test_combined_over_budget():
    # Toilet ₹13,769 + Vanity ₹102,739 = ₹116,508 > ₹50,000
    result = v([
        FixturePlacement(sku='K-3983IN-S-0', x_mm=100, y_mm=1500),
        FixturePlacement(sku='K-31601IN-E64', x_mm=100, y_mm=800),
    ], budget=50000)
    codes = [i.code for i in result.issues]
    assert 'over_budget' in codes


# ── Test 13: North wall door collision ────────────────────────────────────────
def test_north_door_collision():
    room = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='north', door_offset_mm=500, door_width_mm=700)
    # Place fixture at north wall top: y = 2400-520 = 1880, x=500 → blocks north door
    result = validate_layout(LayoutRequest(
        room=room,
        fixtures=[FixturePlacement(sku='K-31601IN-E64', x_mm=500, y_mm=1900)],
    ))
    codes = [i.code for i in result.issues]
    assert 'door_collision' in codes


# ── Test 14: Shower functional wet-zone envelope (Phase A) ────────────────────
def test_unanchored_shower_installation_envelope_is_rejected():
    # Shower rainhead K-72425IN-CP physical size is 117x205mm.
    # Its functional shower wet-zone envelope is 900x900mm.
    # An open-room placement must be rejected for missing wall anchoring.
    # East/north/west/south anchored installations project the zone inward.
    result = v([FixturePlacement(sku='K-72425IN-CP', x_mm=1000, y_mm=1200)])
    codes = [i.code for i in result.issues]
    assert 'shower_not_wall_anchored' in codes, f"Expected wall-anchor warning, got {codes}"
    assert 'outside_room' not in codes, f"Directional wet zone must not be left-wall-only, got {codes}"
