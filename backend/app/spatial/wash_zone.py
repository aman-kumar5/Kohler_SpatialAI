"""Deterministic wash-zone planning geometry derived only from catalog dimensions."""
from ..models import FixturePlacement, ProductRow, RoomSpec, WashZone

WASH_CATEGORIES = {'vanity', 'basin', 'faucet'}


def _dimensions(fixture: FixturePlacement, product: ProductRow) -> tuple[int, int]:
    width, depth = product.width_mm or 0, product.depth_mm or 0
    return (depth, width) if fixture.rotation_deg in (90, 270) else (width, depth)


def derive_wash_zone(fixtures: list[FixturePlacement], products: list[ProductRow], room: RoomSpec) -> WashZone | None:
    """Build a wall-aware planning envelope for the selected wash-zone members.

    The zone is an envelope only: it never replaces physical product geometry.
    """
    by_sku = {product.sku: product for product in products}
    members = [fixture for fixture in fixtures if by_sku.get(fixture.sku) and by_sku[fixture.sku].category in WASH_CATEGORIES]
    if not members:
        return None

    # Prefer vanity as the physical wall reference, then basin, then faucet.
    priority = {'vanity': 0, 'basin': 1, 'faucet': 2}
    anchor = min(members, key=lambda fixture: priority[by_sku[fixture.sku].category])
    anchor_w, anchor_d = _dimensions(anchor, by_sku[anchor.sku])
    distances = {
        'west': anchor.x_mm,
        'east': room.width_mm - (anchor.x_mm + anchor_w),
        'south': anchor.y_mm,
        'north': room.depth_mm - (anchor.y_mm + anchor_d),
    }
    wall = min(distances, key=distances.get)
    member_dims = [_dimensions(fixture, by_sku[fixture.sku]) for fixture in members]
    width = max(900, 600, *(dimension[0] for dimension in member_dims))
    depth = max(600, 550, *(dimension[1] for dimension in member_dims))
    x = min(max(anchor.x_mm, 0), max(0, room.width_mm - width))
    y = min(max(anchor.y_mm, 0), max(0, room.depth_mm - depth))
    if wall == 'west': x = 0
    elif wall == 'east': x = room.width_mm - width
    elif wall == 'south': y = 0
    else: y = room.depth_mm - depth
    return WashZone(x_mm=x, y_mm=y, width_mm=width, depth_mm=depth, wall=wall, members=[fixture.sku for fixture in members])
