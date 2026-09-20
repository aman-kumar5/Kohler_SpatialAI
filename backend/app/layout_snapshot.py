"""Canonical, render-neutral layout snapshot derived only from ``Design``.

The API sends the DesignState to the dashboard and passes that very same object
to PDF export.  This module makes the PDF side explicit: it may serialize the
state, but it must never place or re-place a fixture.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Design, FixturePlacement, ProductRow
from .spatial.geometry import fixture_envelope_polygon


@dataclass(frozen=True)
class LayoutFixture:
    sku: str
    category: str
    x_mm: int
    y_mm: int
    width_mm: int
    depth_mm: int
    rotation_deg: int
    grouped_in_wash_station: bool
    wet_zone: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class LayoutSnapshot:
    room_width_mm: int
    room_depth_mm: int
    door_wall: str
    door_offset_mm: int
    door_width_mm: int
    fixtures: tuple[LayoutFixture, ...]
    wash_station_members: tuple[str, ...]


def canonical_layout_snapshot(design: Design) -> LayoutSnapshot:
    """Serialize canonical DesignState without coordinate fallbacks or placement."""
    if design.room is None:
        raise ValueError("A canonical DesignState must include room geometry for rendering.")
    products = {product.sku: product for product in design.products}
    members = tuple(design.wash_zone.members) if design.wash_zone else ()
    fixtures: list[LayoutFixture] = []
    for fixture in design.fixtures:
        product: ProductRow | None = products.get(fixture.sku)
        if product is None:
            continue
        width, depth = product.width_mm or 300, product.depth_mm or 300
        if fixture.rotation_deg in (90, 270):
            width, depth = depth, width
        wet_zone = None
        if product.category == 'shower':
            bounds = fixture_envelope_polygon(fixture, product, design.room).bounds
            wet_zone = tuple(int(value) for value in (bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1]))
        fixtures.append(LayoutFixture(
            sku=fixture.sku,
            category=product.category,
            x_mm=fixture.x_mm,
            y_mm=fixture.y_mm,
            width_mm=width,
            depth_mm=depth,
            rotation_deg=fixture.rotation_deg,
            grouped_in_wash_station=fixture.sku in members,
            wet_zone=wet_zone,
        ))
    return LayoutSnapshot(
        room_width_mm=design.room.width_mm,
        room_depth_mm=design.room.depth_mm,
        door_wall=design.room.door_wall,
        door_offset_mm=design.room.door_offset_mm,
        door_width_mm=design.room.door_width_mm,
        fixtures=tuple(fixtures),
        wash_station_members=members,
    )
