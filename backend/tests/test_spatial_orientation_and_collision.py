import pytest
from app.models import FixturePlacement, LayoutRequest, RoomSpec
from app.repository import products
from app.spatial.validation import validate_layout
from app.spatial.geometry import fixture_envelope_polygon, fixture_polygon

ROOM_1800_2400 = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=1000, door_width_mm=700)
ROOM_4000_5000 = RoomSpec(width_mm=4000, depth_mm=5000, door_wall='south', door_offset_mm=1000, door_width_mm=700)

VANITY = next(p for p in products() if p.category == 'vanity')
SHOWER = next(p for p in products() if p.category == 'shower')
TOILET = next(p for p in products() if p.category == 'toilet')


def test_vanity_overlapping_door_swing_is_infeasible():
    # Door is on south wall at x=1000, width=700, swing depth=200 (x: 1000..1700, y: 0..200)
    # Placing vanity directly over door swing (x: 800..1700, y: 50..550)
    vanity_placement = FixturePlacement(sku=VANITY.sku, x_mm=800, y_mm=50)
    req = LayoutRequest(room=ROOM_1800_2400, fixtures=[vanity_placement], budget_inr=300000)
    res = validate_layout(req)
    
    assert res.valid is False
    codes = [i.code for i in res.issues]
    assert 'door_collision' in codes
    door_issue = next(i for i in res.issues if i.code == 'door_collision')
    assert 'Vanity' in door_issue.message or 'vanity' in door_issue.message.lower()



def test_vanity_in_valid_free_space_is_feasible():
    # Placed on north wall (y = 2400 - vanity_depth) far from south door swing
    v_depth = VANITY.depth_mm or 400
    vanity_placement = FixturePlacement(sku=VANITY.sku, x_mm=100, y_mm=ROOM_1800_2400.depth_mm - v_depth)
    req = LayoutRequest(room=ROOM_1800_2400, fixtures=[vanity_placement], budget_inr=300000)
    res = validate_layout(req)
    
    assert res.valid is True
    assert len(res.issues) == 0


@pytest.mark.parametrize('room', [ROOM_1800_2400, ROOM_4000_5000])
def test_shower_wet_zone_remains_inside_room_across_room_sizes(room):
    # Test all 4 walls
    walls = [
        ('south', 0, 0),
        ('north', 0, room.depth_mm - (SHOWER.depth_mm or 300)),
        ('west', 0, 1000),
        ('east', room.width_mm - (SHOWER.width_mm or 300), 1000),
    ]
    for wall_name, x, y in walls:
        fix = FixturePlacement(sku=SHOWER.sku, x_mm=x, y_mm=y)
        env = fixture_envelope_polygon(fix, SHOWER, room)
        assert env.bounds[0] >= 0 and env.bounds[1] >= 0
        assert env.bounds[2] <= room.width_mm and env.bounds[3] <= room.depth_mm
        
        res = validate_layout(LayoutRequest(room=room, fixtures=[fix], budget_inr=500000))
        assert res.valid is True


def test_vanity_overlapping_shower_wet_zone_is_infeasible():
    # Shower on West wall at y=1000
    shower_fix = FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=1000)
    # Vanity placed at x=0, y=700 (which intersects shower 900x900 wet zone centered around y=1000)
    vanity_fix = FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=700)
    
    req = LayoutRequest(room=ROOM_1800_2400, fixtures=[shower_fix, vanity_fix], budget_inr=500000)
    res = validate_layout(req)
    
    assert res.valid is False
    codes = [i.code for i in res.issues]
    assert 'overlap' in codes
