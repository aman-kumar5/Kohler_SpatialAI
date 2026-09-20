import pytest
from app.models import FixturePlacement, LayoutRequest, RoomSpec
from app.repository import products
from app.spatial.validation import validate_layout
from app.spatial.geometry import fixture_envelope_polygon, fixture_polygon

ROOM = RoomSpec(width_mm=2400, depth_mm=2400, door_wall='south', door_offset_mm=1200, door_width_mm=800)
SHOWER = next(product for product in products() if product.category == 'shower')
TOILET = next(product for product in products() if product.category == 'toilet')

def test_1_shower_is_inside_room():
    poly = fixture_polygon(FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=1200), SHOWER)
    assert poly.bounds[0] >= 0 and poly.bounds[1] >= 0
    assert poly.bounds[2] <= ROOM.width_mm and poly.bounds[3] <= ROOM.depth_mm

def test_2_wet_zone_is_exactly_900_by_900():
    env_poly = fixture_envelope_polygon(FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=1200), SHOWER)
    env_w = env_poly.bounds[2] - env_poly.bounds[0]
    env_h = env_poly.bounds[3] - env_poly.bounds[1]
    assert env_w == 900 and env_h == 900

def test_3_shower_remains_near_wall():
    res_valid = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=1200)], budget_inr=300000))
    assert 'shower_not_wall_anchored' not in [i.code for i in res_valid.issues]

    res_invalid = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=800, y_mm=800)], budget_inr=300000))
    assert 'shower_not_wall_anchored' in [i.code for i in res_invalid.issues]

def test_4_north_wall_anchoring():
    y = ROOM.depth_mm - (SHOWER.depth_mm or 300)
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=1000, y_mm=y)], budget_inr=300000))
    assert 'shower_not_wall_anchored' not in [i.code for i in res.issues]

def test_5_south_wall_anchoring():
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=0)], budget_inr=300000))
    assert 'shower_not_wall_anchored' not in [i.code for i in res.issues]

def test_6_east_wall_anchoring():
    x = ROOM.width_mm - (SHOWER.width_mm or 300)
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=x, y_mm=1000)], budget_inr=300000))
    assert 'shower_not_wall_anchored' not in [i.code for i in res.issues]

def test_7_west_wall_anchoring():
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=1000)], budget_inr=300000))
    assert 'shower_not_wall_anchored' not in [i.code for i in res.issues]

def test_8_shower_does_not_collide_with_door_clearance():
    # Placed directly inside door swing
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=1200, y_mm=0)], budget_inr=300000))
    assert 'door_collision' in [i.code for i in res.issues]

def test_9_shower_does_not_collide_with_fixtures():
    fixtures = [
        FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=0),
        FixturePlacement(sku=TOILET.sku, x_mm=200, y_mm=200) # overlaps with 900x900 envelope
    ]
    res = validate_layout(LayoutRequest(room=ROOM, fixtures=fixtures, budget_inr=300000))
    assert 'overlap' in [i.code for i in res.issues]

def test_10_wet_zone_remains_inside_room():
    env_poly = fixture_envelope_polygon(FixturePlacement(sku=SHOWER.sku, x_mm=0, y_mm=0), SHOWER)
    assert env_poly.bounds[0] >= 0 and env_poly.bounds[1] >= 0
    assert env_poly.bounds[2] <= ROOM.width_mm and env_poly.bounds[3] <= ROOM.depth_mm

@pytest.mark.parametrize('x,y,wall', [
    (0, 1000, 'west'),
    (ROOM.width_mm - (SHOWER.width_mm or 300), 1000, 'east'),
    (1000, 0, 'south'),
    (1000, ROOM.depth_mm - (SHOWER.depth_mm or 300), 'north'),
])
def test_11_shower_wet_zone_projects_inward_from_each_wall(x, y, wall):
    fixture = FixturePlacement(sku=SHOWER.sku, x_mm=x, y_mm=y)
    envelope = fixture_envelope_polygon(fixture, SHOWER, ROOM)
    bounds = envelope.bounds
    # Wet zone dimensions must be at least 900x900
    assert (bounds[2] - bounds[0]) >= 900
    assert (bounds[3] - bounds[1]) >= 900
    # Envelope must remain within room boundary
    assert bounds[0] >= 0 and bounds[1] >= 0
    assert bounds[2] <= ROOM.width_mm and bounds[3] <= ROOM.depth_mm
    # Shower head must be centered along the wall in the wet zone
    w = SHOWER.width_mm or 300
    d = SHOWER.depth_mm or 300
    if wall in ('west', 'east'):
        center_y = (bounds[1] + bounds[3]) / 2
        assert abs(center_y - (y + d / 2)) < 50
    else:
        center_x = (bounds[0] + bounds[2]) / 2
        assert abs(center_x - (x + w / 2)) < 50

@pytest.mark.parametrize('x,y', [
    (0, 1000),
    (ROOM.width_mm - (SHOWER.width_mm or 300), 1000),
    (1000, 0),
    (1000, ROOM.depth_mm - (SHOWER.depth_mm or 300)),
])
def test_12_each_wall_shower_does_not_report_outside_envelope(x, y):
    result = validate_layout(LayoutRequest(
        room=ROOM,
        fixtures=[FixturePlacement(sku=SHOWER.sku, x_mm=x, y_mm=y)],
        budget_inr=300000,
    ))
    assert 'outside_room' not in [issue.code for issue in result.issues]
