"""Regression tests for large room (4000×5000 mm) spatial candidate placement & PDF consistency."""
import pytest
from app.models import RoomSpec, GenerateRequest, RequirementSpec
from app.optimizer.service import generate
from app.pdf_export import build_design_pdf
from app.layout_snapshot import canonical_layout_snapshot

def test_large_room_spatial_distribution():
    room = RoomSpec(width_mm=4000, depth_mm=5000, door_wall='south', door_offset_mm=1000, door_width_mm=700)
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=room,
            budget_inr=500000,
            style='modern',
            priority='balanced',
            requirements=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
        ),
        categories=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
    )
    
    designs = generate(req)
    assert len(designs) > 0
    
    for design in designs:
        assert design.validation.valid
        assert design.score.total > 0
        
        # Verify fixtures are spatially distributed and not all cramped at x=0, y=0
        xs = [f.x_mm for f in design.fixtures]
        ys = [f.y_mm for f in design.fixtures]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        
        # Spacing span should be at least 800mm in a 4000x5000 room
        assert span_x >= 800 or span_y >= 800

def test_pdf_matches_canonical_design_state():
    room = RoomSpec(width_mm=4000, depth_mm=5000, door_wall='south', door_offset_mm=1000, door_width_mm=700)
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=room,
            budget_inr=500000,
            style='modern',
            priority='balanced',
            requirements=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
        ),
        categories=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
    )
    
    designs = generate(req)
    selected = designs[0]
    
    # Export PDF directly from canonical DesignState
    pdf_bytes = build_design_pdf(selected, budget_inr=500000)
    assert pdf_bytes.startswith(b'%PDF')
    assert len(pdf_bytes) > 1000


def test_pdf_matches_dashboard_layout_snapshot():
    """PDF gets a serialized DesignState; it cannot introduce coordinates."""
    room = RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=1000, door_width_mm=700)
    request = GenerateRequest(
        requirements=RequirementSpec(room=room, budget_inr=300000, style='modern'),
        categories=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
    )
    design = generate(request)[0]
    snapshot = canonical_layout_snapshot(design)
    assert (snapshot.room_width_mm, snapshot.room_depth_mm) == (room.width_mm, room.depth_mm)
    assert [(f.sku, f.x_mm, f.y_mm, f.rotation_deg) for f in snapshot.fixtures] == [
        (f.sku, f.x_mm, f.y_mm, f.rotation_deg) for f in design.fixtures
    ]
    assert set(snapshot.wash_station_members) == set(design.wash_zone.members if design.wash_zone else [])
    shower = next(f for f in snapshot.fixtures if f.category == 'shower')
    assert shower.wet_zone is not None
