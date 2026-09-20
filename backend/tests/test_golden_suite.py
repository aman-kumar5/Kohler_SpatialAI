import pytest
from app.models import RequirementSpec, RoomSpec, GenerateRequest, LayoutRequest, FixturePlacement, ProductRow, Design
from app.ai import parse_requirements, extract_category_price_constraints, normalize_amount
from app.repository import search
from app.spatial.validation import validate_layout
from app.spatial.clearance import door_swing
from app.optimizer.service import generate, _shower_wall_candidates
from app.optimizer.scoring import compute_spatial_fit_score, compute_design_score
from app.pdf_export import build_design_pdf


def test_normalize_amount():
    assert normalize_amount("20k") == 20000
    assert normalize_amount("20 thousand") == 20000
    assert normalize_amount("1 lakh") == 100000
    assert normalize_amount("₹20,000") == 20000
    assert normalize_amount("50000") == 50000


def test_category_price_constraint_parsing():
    text = "Keep my toilet below ₹20,000 and shower under 50k. Total budget is 300000."
    parsed = parse_requirements(text)
    assert "toilet" in parsed.category_constraints
    assert parsed.category_constraints["toilet"]["max_price_inr"] == 20000
    assert "shower" in parsed.category_constraints
    assert parsed.category_constraints["shower"]["max_price_inr"] == 50000
    assert parsed.budget_inr == 300000
    # Additive categories
    assert "toilet" in parsed.requirements
    assert "shower" in parsed.requirements


def test_category_constraint_does_not_set_global_budget():
    text = "I need a toilet below 20000 and a modern vanity."
    parsed = parse_requirements(text)
    assert parsed.budget_inr is None  # Does not set global budget to 20000
    assert parsed.category_constraints.get("toilet", {}).get("max_price_inr") == 20000


def test_premium_mode_respects_category_max_price():
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=RoomSpec(width_mm=1800, depth_mm=2400, door_wall="south", door_offset_mm=1000, door_width_mm=700),
            budget_inr=300000,
            style="modern",
            requirements=["toilet", "vanity", "shower"],
            category_constraints={"toilet": {"max_price_inr": 20000}},
        ),
        categories=["toilet", "vanity", "shower"],
    )
    designs = generate(req)
    assert len(designs) > 0
    for d in designs:
        toilet_p = next(p for p in d.products if p.category == "toilet")
        assert toilet_p.price_inr <= 20000, f"Profile {d.name} selected toilet costing ₹{toilet_p.price_inr} exceeding ₹20,000 constraint!"


def test_shower_four_walls():
    cands = _shower_wall_candidates(1800, 2400, 900, 900)
    walls = set()
    for x, y, rot in cands:
        if y == 0:
            walls.add("south")
        elif y == 2400 - 900:
            walls.add("north")
        if x == 0:
            walls.add("west")
        elif x == 1800 - 900:
            walls.add("east")
    assert {"north", "south", "east", "west"}.issubset(walls), "Shower candidates must search all four walls!"


def test_door_swing_outside_room_rejected():
    # Door offset 1500 + width 700 = 2200 > room width 1800 (extends outside room)
    invalid_room = RoomSpec(width_mm=1800, depth_mm=2400, door_wall="south", door_offset_mm=1500, door_width_mm=700)
    res = validate_layout(LayoutRequest(room=invalid_room, fixtures=[]))
    assert not res.valid
    assert any(i.code == 'door_outside_room' for i in res.issues)


def test_pdf_canonical_state_matching():
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=RoomSpec(width_mm=1800, depth_mm=2400, door_wall="south", door_offset_mm=1000, door_width_mm=700),
            budget_inr=300000,
            style="modern",
            requirements=["toilet", "vanity", "shower"],
        ),
        categories=["toilet", "vanity", "shower"],
    )
    designs = generate(req)
    d = designs[0]
    pdf_bytes = build_design_pdf(d)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert d.room is not None
    assert d.room.width_mm == 1800
    assert d.room.depth_mm == 2400
