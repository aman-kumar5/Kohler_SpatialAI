"""Regression tests for the door-clearance depth change: the door now opens
OUTWARD (away from the bathroom), so validate_layout() only reserves a
200mm interior "keep clear" strip at the doorway instead of the old 700mm
inward swing zone. These tests lock in the new depth and prove the freed-up
floor space (200mm-700mm from the door wall) is now usable.
"""
from app.models import FixturePlacement, LayoutRequest, RoomSpec
from app.spatial.clearance import door_swing
from app.spatial.validation import validate_layout

ROOM = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=500, door_width_mm=700)


def test_door_clearance_depth_is_200mm():
    zone = door_swing(ROOM)
    minx, miny, maxx, maxy = zone.bounds
    assert (maxy - miny) == 200, f"Expected a 200mm-deep clearance zone, got {maxy - miny}mm"


def test_fixture_just_past_200mm_no_longer_blocked_by_door():
    """A small fixture placed 250mm off the door wall — inside the OLD
    700mm swing zone but outside the NEW 200mm clearance strip — must now
    be feasible. This is exactly the freed-up floor space requested."""
    fixture = FixturePlacement(sku='K-3983IN-S-0', x_mm=500, y_mm=250)  # toilet, 366x724mm
    result = validate_layout(LayoutRequest(room=ROOM, fixtures=[fixture]))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' not in codes, f"Expected no door collision, got: {codes}"


def test_fixture_inside_200mm_is_still_blocked():
    """A fixture that genuinely sits in the doorway itself must still be
    rejected — the reduced depth must not disable the hard constraint."""
    fixture = FixturePlacement(sku='K-3983IN-S-0', x_mm=500, y_mm=0)  # touches the south wall
    result = validate_layout(LayoutRequest(room=ROOM, fixtures=[fixture]))
    codes = [issue.code for issue in result.issues]
    assert 'door_collision' in codes, f"Expected door_collision, got: {codes}"


def test_door_clearance_depth_consistent_on_all_four_walls():
    for wall in ('south', 'north', 'east', 'west'):
        room = RoomSpec(width_mm=2400, depth_mm=3000, door_wall=wall, door_offset_mm=500, door_width_mm=800)
        zone = door_swing(room)
        minx, miny, maxx, maxy = zone.bounds
        depth = (maxy - miny) if wall in ('south', 'north') else (maxx - minx)
        assert depth == 200, f"{wall} wall: expected 200mm clearance depth, got {depth}mm"
