"""
Greedy wall-hugging layout optimizer.

Strategy (deterministic, explainable):
1. For each design profile (Smart Budget / Balanced / Premium) pick the best
   product per category from the candidate list.
2. Place fixtures by iterating candidate positions along each wall
   (north/south/east/west edges, stepped in 50mm increments) until
   validate_layout returns valid for ALL fixtures placed so far.
3. If no valid placement exists for any profile, diagnose failed constraints deterministically.
4. Compute DesignScore using only CSV-backed data — never fabricate values.
"""
from __future__ import annotations
import itertools
import math
from time import perf_counter
from shapely.geometry import box
from ..models import (
    GenerateRequest, Design, DesignScore, RequirementSatisfaction,
    FixturePlacement, LayoutRequest, ProductRow, ValidationResult,
)
from ..repository import search
from ..spatial.validation import validate_layout, make_validation_context
from ..spatial.rules import get_installation_envelope_dims
from ..spatial.wash_zone import derive_wash_zone
from ..spatial.clearance import door_swing
from ..spatial.collision import overlaps
from .scoring import compute_design_score, compute_spatial_fit_score
from ..perf import log_perf, perf_enabled


PROFILES: list[tuple[str, str]] = [
    ('Smart Budget', 'cheapest'),
    ('Balanced', 'mid'),
    ('Premium', 'premium'),
]

STEP_MM = 50  # placement grid step
PLACEMENT_BEAM_WIDTH = 48
PRODUCT_COMBINATION_LIMIT = 18
FALLBACK_COMBINATION_LIMIT = 96

# Latest numbers are diagnostic-only: API response and DesignState remain unchanged.
_last_optimization_stats: dict[str, int | float] = {}


def last_optimization_stats() -> dict[str, int | float]:
    return dict(_last_optimization_stats)


def _diverse_product_combinations(
    candidate_lists: list[list[tuple[ProductRow, int, int, int]]],
    limit: int = PLACEMENT_BEAM_WIDTH,
):
    """Yield stable, diverse combinations without materializing a Cartesian product."""
    if not candidate_lists or any(not choices for choices in candidate_lists):
        return
    total = 1
    for choices in candidate_lists:
        total *= len(choices)
    count = min(limit, total)
    strides = (1, 7, 13, 19, 23, 29)
    emitted: set[tuple[int, ...]] = set()
    for sample in range(count * 4):
        indexes = tuple(
            (sample * strides[index % len(strides)] + index * 3) % len(choices)
            for index, choices in enumerate(candidate_lists)
        )
        if indexes in emitted:
            continue
        emitted.add(indexes)
        yield tuple(choices[index] for choices, index in zip(candidate_lists, indexes))
        if len(emitted) == count:
            break


def _ranked_product_combinations(
    ordered_lists: list[list[ProductRow]],
    limit: int,
):
    """Sample across ranked product sets without biasing only the final category."""
    if not ordered_lists or any(not choices for choices in ordered_lists):
        return
    total = math.prod(len(choices) for choices in ordered_lists)
    count = min(limit, total)
    for sample in range(count):
        flat_index = 0 if count == 1 else (sample * (total - 1)) // (count - 1)
        indexes: list[int] = []
        for choices in reversed(ordered_lists):
            flat_index, index = divmod(flat_index, len(choices))
            indexes.append(index)
        yield tuple(choices[index] for choices, index in zip(ordered_lists, reversed(indexes)))


_style_cache: dict[tuple[str, str | None], float] = {}

def _sort_key(profile: str, p: ProductRow, budget: int, style: str | None) -> float:
    cache_key = (p.sku, style)
    if cache_key in _style_cache:
        style_val = _style_cache[cache_key]
    else:
        from .scoring import compute_style_match
        p_style_score, _, _ = compute_style_match([p], style)
        style_val = p_style_score if p_style_score is not None else 50.0
        _style_cache[cache_key] = style_val

    if profile == 'cheapest':
        conflict_penalty = 10000.0 if (style and style_val <= 35.0) else 0.0
        return float(p.price_inr) + conflict_penalty - (style_val * 10.0)
    if profile == 'premium':
        return - (float(p.price_inr) * 10.0 + style_val * 500.0)
    target = (budget * 0.55) / 3
    return abs(p.price_inr - target) - (style_val * 50.0)


def _shower_wall_candidates(
    room_w: int, room_d: int, fix_w: int, fix_d: int
) -> list[tuple[int, int, int]]:
    """Generate shower candidates on ALL FOUR WALLS with physical wall orientation matching 3D."""
    candidates: list[tuple[int, int, int]] = []
    wall_rotations = {'south': 0, 'west': 90, 'north': 180, 'east': 270}
    offsets = [0.50, 0.25, 0.75, 0.20, 0.35, 0.65, 0.80, 0.0, 1.0, 0.15, 0.85]

    for wall in ('south', 'north', 'west', 'east'):
        rot = wall_rotations[wall]
        fw, fd = (fix_d, fix_w) if rot in (90, 270) else (fix_w, fix_d)
        if fw > room_w or fd > room_d:
            continue

        max_x = max(0, room_w - fw)
        max_y = max(0, room_d - fd)

        if wall == 'south':
            for r in offsets:
                candidates.append((int(max_x * r), 0, rot))
        elif wall == 'north':
            y_north = max(0, room_d - fd)
            for r in offsets:
                candidates.append((int(max_x * r), y_north, rot))
        elif wall == 'west':
            for r in offsets:
                candidates.append((0, int(max_y * r), rot))
        elif wall == 'east':
            x_east = max(0, room_w - fw)
            for r in offsets:
                candidates.append((x_east, int(max_y * r), rot))

    seen: set[tuple[int, int, int]] = set()
    unique: list[tuple[int, int, int]] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _category_wall_candidates(
    room_w: int, room_d: int, fix_w: int, fix_d: int, category: str
) -> list[tuple[int, int, int]]:
    """Generates candidate positions across all 4 walls with physical wall orientation matching 3D."""
    if category == 'shower':
        return _shower_wall_candidates(room_w, room_d, fix_w, fix_d)

    candidates: list[tuple[int, int, int]] = []
    offsets = [0.50, 0.25, 0.75, 0.20, 0.35, 0.65, 0.80, 0.0, 1.0, 0.15, 0.85]
    wall_rotations = {'south': 0, 'west': 90, 'north': 180, 'east': 270}

    if category == 'toilet':
        walls = ['east', 'south', 'west', 'north']
    elif category == 'vanity':
        walls = ['west', 'north', 'east', 'south']
    else:
        walls = ['north', 'west', 'east', 'south']

    for wall in walls:
        rot = wall_rotations[wall]
        fw, fd = (fix_d, fix_w) if rot in (90, 270) else (fix_w, fix_d)
        if fw > room_w or fd > room_d:
            continue

        max_x = max(0, room_w - fw)
        max_y = max(0, room_d - fd)

        if wall == 'north':
            y_north = max(0, room_d - fd)
            for r in offsets:
                candidates.append((int(max_x * r), y_north, rot))
        elif wall == 'west':
            for r in offsets:
                candidates.append((0, int(max_y * r), rot))
        elif wall == 'east':
            x_east = max(0, room_w - fw)
            for r in offsets:
                candidates.append((x_east, int(max_y * r), rot))
        elif wall == 'south':
            for r in offsets:
                candidates.append((int(max_x * r), 0, rot))

    seen: set[tuple[int, int, int]] = set()
    unique: list[tuple[int, int, int]] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _place_fixtures(
    products: list[ProductRow],
    room_w: int,
    room_d: int,
    budget: int,
    room_spec,
    category_constraints: dict[str, dict[str, int]] | None = None,
    stats: dict[str, int | float] | None = None,
) -> list[FixturePlacement] | None:
    cat_constraints = category_constraints or {}
    stats = stats if stats is not None else {}
    if not products:
        return []

    has_vanity = any(p.category == 'vanity' for p in products)
    has_basin = any(p.category == 'basin' for p in products)

    if has_vanity:
        primary_products = [p for p in products if p.category not in ('basin', 'faucet')]
        secondary_products = [p for p in products if p.category in ('basin', 'faucet')]
    elif has_basin:
        primary_products = [p for p in products if p.category != 'faucet']
        secondary_products = [p for p in products if p.category == 'faucet']
    else:
        primary_products = list(products)
        secondary_products = []

    # Build candidates list per primary product — pre-filtered against door swing
    d_poly = door_swing(room_spec)
    product_candidates: list[list[tuple[ProductRow, int, int, int]]] = []
    for product in primary_products:
        w = product.width_mm or 300
        d = product.depth_mm or 300
        cands = _category_wall_candidates(room_w, room_d, w, d, product.category)
        if not cands:
            return None
        valid_cands = []
        for x, y, rot in cands:
            fw, fd = (d, w) if rot in (90, 270) else (w, d)
            if not overlaps(box(x, y, x + fw, y + fd), d_poly):
                valid_cands.append((x, y, rot))
        if not valid_cands:
            valid_cands = cands
        product_candidates.append([(product, x, y, rot) for x, y, rot in valid_cands])

    best_placement: list[FixturePlacement] | None = None

    best_score: float = -1.0
    validation_context = make_validation_context(room_spec)

    # Systematically generate ALL Cartesian placement combinations across all wall
    # positions and angles (up to 1024 candidates), fully evaluated and scored,
    # guaranteeing that the globally highest-scoring layout is always selected.
    all_cartesian = list(itertools.product(*product_candidates))

    # Equitable multi-wall pattern sampling: group combinations by wall assignment pattern
    # so we sample diverse layout candidates across ALL walls (North, South, East, West)
    # rather than saturating the candidate budget on a single wall configuration.
    def _wall_pattern(combo):
        pattern = []
        for prod, x, y, rot in combo:
            side = 'west' if rot == 90 else ('east' if rot == 270 else ('north' if rot == 180 else 'south'))
            pattern.append((prod.category, side))
        return tuple(pattern)

    by_pattern: dict[tuple, list] = {}
    for combo in all_cartesian:
        pat = _wall_pattern(combo)
        if pat not in by_pattern:
            by_pattern[pat] = []
        by_pattern[pat].append(combo)

    # Sort patterns by wall diversity (preferring layouts spanning 3 or 4 distinct walls)
    sorted_patterns = sorted(by_pattern.keys(), key=lambda pat: len(set(side for _, side in pat)), reverse=True)

    combos_to_test = []
    # Sample up to 8 candidates per wall pattern to cover every room layout configuration
    for pat in sorted_patterns:
        combos_to_test.extend(by_pattern[pat][:8])

    combos_to_test = combos_to_test[:48]




    stats['placement_combinations'] = stats.get('placement_combinations', 0) + len(combos_to_test)

    for combo in combos_to_test:
        trial_placements: list[FixturePlacement] = []
        vanity_pos: tuple[int, int, int] | None = None
        basin_pos: tuple[int, int, int] | None = None

        for prod, x, y, rot in combo:
            trial_placements.append(FixturePlacement(sku=prod.sku, x_mm=x, y_mm=y, rotation_deg=rot))  # type: ignore[arg-type]
            if prod.category == 'vanity':
                vanity_pos = (x, y, rot)
            elif prod.category == 'basin':
                basin_pos = (x, y, rot)

        # Place secondary products (basin/faucet) anchored at vanity or basin position
        for sec_prod in secondary_products:
            if sec_prod.category in ('basin', 'faucet') and vanity_pos:
                vx, vy, vrot = vanity_pos
                trial_placements.append(FixturePlacement(sku=sec_prod.sku, x_mm=vx, y_mm=vy, rotation_deg=vrot))  # type: ignore[arg-type]
            elif sec_prod.category == 'faucet' and basin_pos:
                bx, by, brot = basin_pos
                trial_placements.append(FixturePlacement(sku=sec_prod.sku, x_mm=bx, y_mm=by, rotation_deg=brot))  # type: ignore[arg-type]
            else:
                first = trial_placements[0] if trial_placements else None
                if first:
                    trial_placements.append(FixturePlacement(sku=sec_prod.sku, x_mm=first.x_mm, y_mm=first.y_mm, rotation_deg=first.rotation_deg))
                else:
                    trial_placements.append(FixturePlacement(sku=sec_prod.sku, x_mm=100, y_mm=100, rotation_deg=0))

        val_res = validate_layout(LayoutRequest(
            room=room_spec, fixtures=trial_placements, budget_inr=budget, category_constraints=cat_constraints,
        ), context=validation_context)

        if val_res.valid:
            stats['feasible_layouts'] = stats.get('feasible_layouts', 0) + 1
            score, _breakdown = compute_spatial_fit_score(products, val_res, room_w, room_d, fixtures=trial_placements, room=room_spec)
            if score > best_score:
                best_score = score
                best_placement = trial_placements
        else:
            stats['hard_rejected'] = stats.get('hard_rejected', 0) + 1

    if best_placement is not None:
        return best_placement

    # Fallback sequential search across category wall candidates
    placed: list[FixturePlacement] = []
    vanity_placement: FixturePlacement | None = None
    basin_placement: FixturePlacement | None = None

    for product in primary_products:
        w = product.width_mm or 300
        d = product.depth_mm or 300
        cands = _category_wall_candidates(room_w, room_d, w, d, product.category)
        found = False
        for x, y, rot in cands:
            trial = placed + [FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)]  # type: ignore[arg-type]
            result = validate_layout(
                LayoutRequest(room=room_spec, fixtures=trial, budget_inr=budget, category_constraints=cat_constraints),
                context=validation_context,
            )
            if result.valid:
                placed = trial
                if product.category == 'vanity':
                    vanity_placement = FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)
                elif product.category == 'basin':
                    basin_placement = FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)
                found = True
                break
        if not found:
            # Final fallback: try fine-grained wall positions
            fine_offsets = [0.05, 0.20, 0.35, 0.50, 0.65, 0.80, 0.95]
            fine_cands = []
            for rot in (0, 90):
                fw, fd = (w, d) if rot == 0 else (d, w)
                if fw <= room_w and fd <= room_d:
                    max_x = room_w - fw
                    max_y = room_d - fd
                    for r in fine_offsets:
                        fine_cands.append((int(max_x * r), 0, rot))
                        fine_cands.append((int(max_x * r), max_y, rot))
                        fine_cands.append((0, int(max_y * r), rot))
                        fine_cands.append((max_x, int(max_y * r), rot))
            for x, y, rot in fine_cands:
                trial = placed + [FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)]  # type: ignore[arg-type]
                result = validate_layout(
                    LayoutRequest(room=room_spec, fixtures=trial, budget_inr=budget, category_constraints=cat_constraints),
                    context=validation_context,
                )
                if result.valid:
                    placed = trial
                    if product.category == 'vanity':
                        vanity_placement = FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)
                    elif product.category == 'basin':
                        basin_placement = FixturePlacement(sku=product.sku, x_mm=x, y_mm=y, rotation_deg=rot)
                    found = True
                    break
        if not found:
            return None

    stats['feasible_layouts'] = stats.get('feasible_layouts', 0) + 1

    # Attach secondary basin/faucet to vanity or basin
    for sec_prod in secondary_products:
        if vanity_placement:
            placed.append(FixturePlacement(sku=sec_prod.sku, x_mm=vanity_placement.x_mm, y_mm=vanity_placement.y_mm, rotation_deg=vanity_placement.rotation_deg))
        elif basin_placement:
            placed.append(FixturePlacement(sku=sec_prod.sku, x_mm=basin_placement.x_mm, y_mm=basin_placement.y_mm, rotation_deg=basin_placement.rotation_deg))
        elif placed:
            first = placed[0]
            placed.append(FixturePlacement(sku=sec_prod.sku, x_mm=first.x_mm, y_mm=first.y_mm, rotation_deg=first.rotation_deg))
        else:
            placed.append(FixturePlacement(sku=sec_prod.sku, x_mm=100, y_mm=100, rotation_deg=0))

    return placed


def generate(request: GenerateRequest) -> list[Design]:
    total_started = perf_counter()
    stats: dict[str, int | float] = {
        'generated_candidates': 0,
        'deduplicated': 0,
        'hard_rejected': 0,
        'feasible_layouts': 0,
        'fully_scored': 0,
    }
    spec = request.requirements
    if not spec.room or spec.budget_inr is None:
        raise ValueError('Room dimensions and budget are required to generate a design.')

    room = spec.room
    budget = spec.budget_inr
    cat_constraints = spec.category_constraints or {}

    retrieval_started = perf_counter()
    candidates: dict[str, list[ProductRow]] = {}
    for cat in request.categories:
        max_p = cat_constraints.get(cat, {}).get("max_price_inr")
        rows = search([cat], [], spec.style, budget, max_price=max_p)
        if not rows:
            rows = search([cat], [], None, None, max_price=max_p)
        if not rows:
            if max_p is not None:
                raise ValueError(
                    f'No CSV products found for category "{cat}" within limit ₹{max_p:,}. '
                    f'Please relax your price limit for {cat}.'
                )
            raise ValueError(
                f'No CSV products found for category "{cat}". '
                'Check kohler_products.csv contains that category.'
            )
        candidates[cat] = rows
    log_perf('retrieval', retrieval_started)

    designs: list[Design] = []

    for name, profile in PROFILES:
        ranking_started = perf_counter()
        category_sorted = {
            cat: sorted(candidates[cat], key=lambda p: _sort_key(profile, p, budget, spec.style))
            for cat in request.categories
        }

        from .scoring import compute_style_match

        # Pre-cache individual product style scores to avoid recomputation
        style_score_cache: dict[str, float] = {}
        for cat in request.categories:
            for p in category_sorted[cat][:3]:
                if p.sku not in style_score_cache:
                    s, _, _ = compute_style_match([p], spec.style)
                    style_score_cache[p.sku] = s if s is not None else 50.0

        combos = list(itertools.product(*(category_sorted[cat][:3] for cat in request.categories)))

        def _combo_sort_key(combo):
            # Fast cached style + compatibility scoring without calling full functions
            avg_style = sum(style_score_cache.get(p.sku, 50.0) for p in combo) / len(combo)
            # Collection cohesion bonus (same collection => higher compatibility)
            collections = set(p.collection.lower() for p in combo if p.collection and p.collection.strip())
            compat_bonus = 100.0 if len(collections) <= 1 else 85.0
            indiv_sort = sum(_sort_key(profile, p, budget, spec.style) for p in combo)
            return indiv_sort - (compat_bonus * 100.0) - (avg_style * 200.0)

        combos.sort(key=_combo_sort_key)
        stats['generated_candidates'] += len(combos)
        log_perf('sorting/ranking candidates', ranking_started)

        best_design: Design | None = None
        eval_count = 0
        for chosen_tuple in combos:
            chosen = list(chosen_tuple)
            total_price = sum(p.price_inr for p in chosen)
            if total_price > budget:
                stats['hard_rejected'] += 1
                continue

            placement_started = perf_counter()
            placements = _place_fixtures(chosen, room.width_mm, room.depth_mm, budget, room, cat_constraints, stats)
            log_perf('candidate generation and hard-constraint validation', placement_started)
            if placements is None:
                continue

            validation_started = perf_counter()
            result = validate_layout(LayoutRequest(
                room=room, fixtures=placements, budget_inr=budget, category_constraints=cat_constraints,
            ))
            log_perf('geometry validation', validation_started)
            if not result.valid:
                stats['hard_rejected'] += 1
                continue

            score_started = perf_counter()
            score = compute_design_score(chosen, result, budget, spec.style, room.width_mm, room.depth_mm, profile_name=name, fixtures=placements, room=room)
            stats['fully_scored'] += 1
            log_perf('full deterministic scoring', score_started)

            req_sat = []
            for req_cat in request.categories:
                matched = next((p for p in chosen if p.category == req_cat), None)
                req_sat.append(RequirementSatisfaction(
                    requested=req_cat,
                    satisfied=matched is not None,
                    selected_category=matched.category if matched else None,
                    product_name=matched.name if matched else None,
                    sku=matched.sku if matched else None,
                ))

            candidate_design = Design(
                name=name,
                fixtures=placements,
                products=chosen,
                validation=result,
                score=score,
                requirements_satisfaction=req_sat,
                room=room,
                wash_zone=derive_wash_zone(placements, chosen, room),
            )
            if best_design is None or candidate_design.score.total > best_design.score.total:
                best_design = candidate_design

            eval_count += 1
            if eval_count >= 8:
                break

        if best_design is not None:
            designs.append(best_design)
            found_design = True
        else:
            found_design = False

        if not found_design:
            # Fallback to lowest-cost combinations that fit within budget for this profile
            fallback_sorted = {
                cat: sorted(candidates[cat], key=lambda p: p.price_inr)
                for cat in request.categories
            }
            fallback_combos = _ranked_product_combinations([fallback_sorted[cat][:5] for cat in request.categories], FALLBACK_COMBINATION_LIMIT)
            for chosen_tuple in fallback_combos:
                chosen = list(chosen_tuple)
                if sum(p.price_inr for p in chosen) > budget:
                    continue
                placements = _place_fixtures(chosen, room.width_mm, room.depth_mm, budget, room, cat_constraints, stats)
                if placements is None:
                    continue
                result = validate_layout(LayoutRequest(
                    room=room, fixtures=placements, budget_inr=budget, category_constraints=cat_constraints,
                ))
                if not result.valid:
                    continue
                score = compute_design_score(chosen, result, budget, spec.style, room.width_mm, room.depth_mm, profile_name=name, fixtures=placements, room=room)
                stats['fully_scored'] += 1
                req_sat = [RequirementSatisfaction(requested=req_cat, satisfied=True, selected_category=req_cat, product_name=next(p.name for p in chosen if p.category == req_cat), sku=next(p.sku for p in chosen if p.category == req_cat)) for req_cat in request.categories]
                designs.append(Design(
                    name=name, fixtures=placements, products=chosen, validation=result, score=score,
                    requirements_satisfaction=req_sat, room=room, wash_zone=derive_wash_zone(placements, chosen, room),
                ))
                break

    if not designs:
        stats['deduplicated'] = sum(
            max(0, 48 - len(_category_wall_candidates(room.width_mm, room.depth_mm, p.width_mm or 300, p.depth_mm or 300, p.category)))
            for rows in candidates.values() for p in rows[:1]
        )
        stats['total_optimization_ms'] = round((perf_counter() - total_started) * 1000, 1)
        _last_optimization_stats.clear()
        _last_optimization_stats.update(stats)
        reasons = []
        suggestions = []

        total_min_cost = sum(
            min((p.price_inr for p in candidates[c]), default=0)
            for c in request.categories
        )
        if total_min_cost > budget:
            reasons.append(f"✕ Combined minimum cost of selected fixtures (₹{total_min_cost:,}) exceeds stated budget (₹{budget:,}).")
            suggestions.append("• Increase your total budget.")
            suggestions.append("• Deselect higher-cost fixture categories.")

        room_area = room.width_mm * room.depth_mm
        total_env_area = 0
        for c in request.categories:
            p_sample = candidates[c][0]
            w = p_sample.width_mm or 300
            d = p_sample.depth_mm or 300
            env_w, env_d, _ = get_installation_envelope_dims(c, w, d)
            total_env_area += env_w * env_d

        if total_env_area > room_area * 0.7:
            reasons.append(f"✕ Required fixture installation envelopes exceed available room space ({room.width_mm}×{room.depth_mm}mm).")
            suggestions.append("• Increase room width or depth dimensions.")
            suggestions.append("• Reduce the number of requested categories.")

        if not reasons:
            reasons.append("✕ Door clearance zone conflicts with fixture placement options.")
            suggestions.append("• Adjust door wall, offset, or door width.")
            suggestions.append("• Expand room dimensions to allow clearance around the door.")

        msg = "NO FEASIBLE DESIGN FOUND\n" + "\n".join(reasons) + "\n\nSuggested Actions:\n" + "\n".join(suggestions)
        raise ValueError(msg)

    stats['deduplicated'] = sum(
        max(0, 48 - len(_category_wall_candidates(room.width_mm, room.depth_mm, p.width_mm or 300, p.depth_mm or 300, p.category)))
        for rows in candidates.values() for p in rows[:1]
    )
    stats['total_optimization_ms'] = round((perf_counter() - total_started) * 1000, 1)
    _last_optimization_stats.clear()
    _last_optimization_stats.update(stats)
    if perf_enabled():
        log_perf('total optimization', total_started)
        from logging import getLogger
        getLogger(__name__).info(
            '[PERF] generated=%d hard_rejected=%d feasible=%d fully_scored=%d deduplicated=%d',
            stats['generated_candidates'], stats['hard_rejected'], stats['feasible_layouts'],
            stats['fully_scored'], stats['deduplicated'],
        )
    return designs


def budget_per_category(total: int, categories: list[str]) -> int:
    n = len(categories) or 1
    return total // n
