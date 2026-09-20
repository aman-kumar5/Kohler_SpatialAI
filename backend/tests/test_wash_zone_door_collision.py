"""Regression tests for Bug #2: a vanity's raw rectangle could clear the
door swing while the real WashStation installation envelope (vanity +
basin/faucet clearance, expanded to the same minimum plan size shown in
2D/3D/PDF via wash_zone.derive_wash_zone) still reached into it, yet the
design was reported as feasible.

validate_layout() now checks the derived wash_zone against the door swing
as an explicit hard constraint (see spatial/validation.py), in addition to
the existing per-fixture check. These tests construct cases where the two
checks would disagree, to prove the wash_zone check is the one actually
catching the collision, and cover both required room sizes.
"""
from app.models import FixturePlacement, LayoutRequest, RoomSpec
from app.repository import products
from app.spatial.validation import validate_layout
from app.spatial.geometry import fixture_envelope_polygon
from app.spatial.clearance import door_swing
from app.spatial.wash_zone import derive_wash_zone
from app.spatial.collision import overlaps

# K-31601IN-E64: 900 x 520mm vanity. Its own raw footprint already meets the
# 900mm minimum wash-zone width, but not the 600mm minimum wash-zone depth —
# exactly the gap this bug hid.
VANITY = next(p for p in products() if p.sku == 'K-31601IN-E64')

SMALL_ROOM = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='west', door_offset_mm=650, door_width_mm=700)
LARGE_ROOM = RoomSpec(width_mm=4000, depth_mm=5000, door_wall='west', door_offset_mm=560, door_width_mm=900)


def test_vanity_raw_rectangle_alone_clears_the_door_small_room():
    """Sanity check: the vanity's own 900x520 rectangle does NOT reach the
    door on its own — proving any failure below comes from the wash-zone
    check, not from the simpler per-fixture check."""
    fixture = FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=100)
    env_poly = fixture_envelope_polygon(fixture, VANITY, SMALL_ROOM)
    assert not overlaps(env_poly, door_swing(SMALL_ROOM))


def test_vanity_wash_zone_overlapping_door_is_infeasible_small_room():
    """The expanded 600mm-deep WashStation envelope reaches into the same
    door swing the raw rectangle cleared. This must be a hard failure."""
    fixtures = [FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=100)]
    zone = derive_wash_zone(fixtures, [VANITY], SMALL_ROOM)
    assert zone is not None and zone.wall == 'west'

    result = validate_layout(LayoutRequest(room=SMALL_ROOM, fixtures=fixtures, budget_inr=300000))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' in codes, f"Expected door_collision, got: {codes}"
    assert result.valid is False, "A design with a door collision must never report Design Feasible."
    assert any('door' in issue.message.lower() for issue in result.issues)


def test_vanity_moved_into_free_space_is_feasible_small_room():
    """Moving the same vanity away from the door clears both checks."""
    fixtures = [FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=1500)]
    result = validate_layout(LayoutRequest(room=SMALL_ROOM, fixtures=fixtures, budget_inr=300000))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' not in codes
    assert result.valid is True


def test_vanity_raw_rectangle_alone_clears_the_door_large_room():
    fixture = FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=10)
    env_poly = fixture_envelope_polygon(fixture, VANITY, LARGE_ROOM)
    assert not overlaps(env_poly, door_swing(LARGE_ROOM))


def test_vanity_wash_zone_overlapping_door_is_infeasible_large_room():
    fixtures = [FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=10)]
    zone = derive_wash_zone(fixtures, [VANITY], LARGE_ROOM)
    assert zone is not None and zone.wall == 'west'

    result = validate_layout(LayoutRequest(room=LARGE_ROOM, fixtures=fixtures, budget_inr=300000))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' in codes, f"Expected door_collision, got: {codes}"
    assert result.valid is False


def test_vanity_moved_into_free_space_is_feasible_large_room():
    fixtures = [FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=3000)]
    result = validate_layout(LayoutRequest(room=LARGE_ROOM, fixtures=fixtures, budget_inr=300000))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' not in codes
    assert result.valid is True


def test_full_washstation_still_moves_as_one_assembly_without_false_overlap():
    """Vanity + basin + faucet placed together (as the frontend drag handler
    and optimizer do — all three sharing one x/y) must not trip the
    same-station 'overlap' rule, and the wash_zone must list every member."""
    basin = next(p for p in products() if p.category == 'basin')
    faucet = next(p for p in products() if p.category == 'faucet')
    fixtures = [
        FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=1500),
        FixturePlacement(sku=basin.sku, x_mm=0, y_mm=1500),
        FixturePlacement(sku=faucet.sku, x_mm=0, y_mm=1500),
    ]
    result = validate_layout(LayoutRequest(room=SMALL_ROOM, fixtures=fixtures, budget_inr=300000))
    codes = [issue.code for issue in result.issues]
    assert 'overlap' not in codes
    assert 'door_collision' not in codes

    zone = derive_wash_zone(fixtures, [VANITY, basin, faucet], SMALL_ROOM)
    assert zone is not None
    assert set(zone.members) == {VANITY.sku, basin.sku, faucet.sku}
