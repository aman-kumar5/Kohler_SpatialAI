import pytest
from app.models import RequirementSpec, RoomSpec, GenerateRequest
from app.optimizer.service import generate

def test_no_feasible_design_room_too_small():
    # 500x500mm room cannot fit toilet + vanity + shower envelopes
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=RoomSpec(width_mm=500, depth_mm=500),
            budget_inr=300000,
        ),
        categories=['toilet', 'vanity', 'shower'],
    )
    with pytest.raises(ValueError) as exc:
        generate(req)
    err_text = str(exc.value)
    assert "NO FEASIBLE DESIGN FOUND" in err_text
    assert "exceed available room space" in err_text or "conflicts" in err_text
    assert "Suggested Actions:" in err_text

def test_no_feasible_design_budget_too_small():
    # Budget of ₹10 cannot buy any Kohler product set
    req = GenerateRequest(
        requirements=RequirementSpec(
            room=RoomSpec(width_mm=1800, depth_mm=2400),
            budget_inr=10,
        ),
        categories=['toilet', 'vanity', 'shower'],
    )
    with pytest.raises(ValueError) as exc:
        generate(req)
    err_text = str(exc.value)
    assert "NO FEASIBLE DESIGN FOUND" in err_text
    assert "exceeds stated budget" in err_text
    assert "Suggested Actions:" in err_text
