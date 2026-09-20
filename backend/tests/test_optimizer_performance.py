"""Regression coverage for the optimizer's bounded, deterministic search."""
from app.models import GenerateRequest, RequirementSpec, RoomSpec
from app.optimizer.service import (
    _category_wall_candidates,
    generate,
    last_optimization_stats,
)
from app.spatial.rules import get_installation_envelope_dims


def _request(room: RoomSpec | None = None) -> GenerateRequest:
    return GenerateRequest(
        requirements=RequirementSpec(
            room=room or RoomSpec(width_mm=4000, depth_mm=5000, door_wall='south', door_offset_mm=1000),
            budget_inr=500000,
            style='modern',
        ),
        categories=['toilet', 'vanity', 'basin', 'faucet', 'shower'],
    )


def test_optimization_completes_without_excessive_recomputation():
    designs = generate(_request())
    stats = last_optimization_stats()
    assert designs
    # The product search remains meaningful (3^5 per profile), while layout
    # exploration is bounded instead of materializing 48^3 placements.
    assert stats['generated_candidates'] >= 200
    assert stats['placement_combinations'] < 1500
    # We now evaluate multiple candidates per profile to find the best layout,
    # so fully_scored >= len(designs) (one design per profile at most).
    assert stats['fully_scored'] >= len(designs)


def test_candidate_deduplication():
    candidates = _category_wall_candidates(1800, 2400, 300, 300, 'shower')
    assert candidates
    assert len(candidates) == len(set(candidates))


def test_hard_constraint_early_pruning():
    request = _request(RoomSpec(width_mm=1800, depth_mm=2400, door_wall='south', door_offset_mm=1000))
    request.requirements.budget_inr = 1
    try:
        generate(request)
    except ValueError:
        pass
    stats = last_optimization_stats()
    assert stats['hard_rejected'] > 0
    assert stats['fully_scored'] == 0


def test_cached_geometry_consistency():
    get_installation_envelope_dims.cache_clear()
    first = get_installation_envelope_dims('shower', 300, 300)
    second = get_installation_envelope_dims('shower', 300, 300)
    assert first == second
    assert get_installation_envelope_dims.cache_info().hits == 1


def test_two_stage_candidate_ranking():
    designs = generate(_request())
    stats = last_optimization_stats()
    assert designs
    assert stats['feasible_layouts'] >= stats['fully_scored']
    # fully_scored >= len(designs): multiple candidates are scored per profile
    # and the best one is selected, so the scoring count exceeds design count.
    assert stats['fully_scored'] >= len(designs)

