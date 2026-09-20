from app.models import FixturePlacement, RoomSpec
from app.repository import products
from app.spatial.wash_zone import derive_wash_zone


ROOM = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=1000, door_width_mm=700)
VANITY = next(product for product in products() if product.category == 'vanity')


def test_vanity_creates_wall_aware_wash_zone():
    zone = derive_wash_zone([FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=1000)], [VANITY], ROOM)
    assert zone is not None
    assert zone.wall == 'west'
    assert zone.width_mm >= 900 and zone.depth_mm >= 600
    assert zone.members == [VANITY.sku]


def test_wash_zone_adapts_to_large_vanity_dimension():
    zone = derive_wash_zone([FixturePlacement(sku=VANITY.sku, x_mm=0, y_mm=1000)], [VANITY], ROOM)
    assert zone is not None
    assert zone.width_mm >= (VANITY.width_mm or 0)
