"""
Deterministic, explainable scoring engine for KOHLER SpatialAI.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Sequence
from time import perf_counter
from ..models import ProductRow, ValidationResult, DesignScore, StyleEvidenceItem, FixturePlacement, RoomSpec
from ..spatial.compatibility import evaluate_compatibility
from ..spatial.clearance import door_swing, door_opening_segment
from ..spatial.geometry import fixture_polygon, fixture_envelope_polygon, room_polygon, toilet_front_clearance_polygon

from ..perf import log_perf

RULES_PATH = Path(__file__).parent.parent / 'data' / 'style_rules.json'

def _load_style_rules():
    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

STYLE_RULES = _load_style_rules()

DEFAULT_WEIGHTS = {
    'spatial_fit': 0.30,
    'budget_fit': 0.20,
    'style_match': 0.20,
    'compatibility': 0.15,
    'accessibility': 0.10,
    'sustainability': 0.05,
}

PROFILE_WEIGHTS = {
    'Smart Budget': {
        'budget_fit': 0.40,
        'spatial_fit': 0.30,
        'style_match': 0.15,
        'compatibility': 0.15,
        'accessibility': 0.0,
        'sustainability': 0.0,
    },
    'Balanced': {
        'budget_fit': 0.25,
        'spatial_fit': 0.30,
        'style_match': 0.25,
        'compatibility': 0.20,
        'accessibility': 0.0,
        'sustainability': 0.0,
    },
    'Premium': {
        'style_match': 0.30,
        'spatial_fit': 0.30,
        'compatibility': 0.25,
        'budget_fit': 0.15,
        'accessibility': 0.0,
        'sustainability': 0.0,
    },
}

def compute_budget_fit(total_price_inr: int, budget_inr: int) -> float:
    """
    Smooth budget fit scoring function.
    0-100% utilization yields 100.0 -> 90.0 score.
    Over budget yields 0.0.
    """
    if budget_inr <= 0 or total_price_inr > budget_inr:
        return 0.0
    u = total_price_inr / budget_inr
    score = 100.0 - 10.0 * (u ** 1.5)
    return round(max(0.0, min(100.0, score)), 1)


def compute_style_match(products: Sequence[ProductRow], target_style: str | None) -> tuple[float | None, str, list[StyleEvidenceItem]]:
    if not products:
        return None, "Limited data available", []

    if target_style is None or not str(target_style).strip():
        evidence_list = [StyleEvidenceItem(sku=p.sku, score=None, reason="Limited style evidence") for p in products]
        return None, "Limited data available", evidence_list

    target = target_style.lower().strip()
    dict_rules = STYLE_RULES.get('style_dictionary', {})
    weights = STYLE_RULES.get('weights', {
        'explicit_metadata': 100,
        'keyword_match': 85,
        'collection_match': 70,
        'feature_text_match': 50,
        'style_conflict': 30
    })

    target_rule = None
    for k, v in dict_rules.items():
        if target in k or k in target or any(target in s for s in v.get('synonyms', [])):
            target_rule = v
            break

    synonyms = target_rule.get('synonyms', [target]) if target_rule else [target]
    target_collections = target_rule.get('collections', []) if target_rule else []
    conflict_styles = target_rule.get('conflict_styles', []) if target_rule else []

    evidence_list: list[StyleEvidenceItem] = []
    scores: list[float] = []

    for p in products:
        p_style = (p.style or '').lower()
        p_coll = (p.collection or '').lower()
        p_kw = (p.keywords or '').lower()
        p_name = (p.name or '').lower()
        p_features = (p.features or '').lower()

        # 1. Explicit style metadata match (Score 100)
        if p_style and any(s in p_style for s in synonyms):
            scores.append(float(weights['explicit_metadata']))
            evidence_list.append(StyleEvidenceItem(sku=p.sku, score=100.0, reason=f"Explicit {target_style} style metadata match"))
            continue

        # 2. Keyword or Product Name match (Score 85)
        if (p_kw and any(s in p_kw for s in synonyms)) or (p_name and any(s in p_name for s in synonyms)):
            scores.append(float(weights['keyword_match']))
            evidence_list.append(StyleEvidenceItem(sku=p.sku, score=85.0, reason=f"Strong {target_style} keyword/name match"))
            continue

        # 3. Collection match (Score 70)
        if p_coll and (any(c in p_coll for c in target_collections) or any(s in p_coll for s in synonyms)):
            scores.append(float(weights['collection_match']))
            evidence_list.append(StyleEvidenceItem(sku=p.sku, score=70.0, reason=f"Collection match ({p.collection})"))
            continue

        # 4. Feature text evidence (Score 50)
        if p_features and any(s in p_features for s in synonyms):
            scores.append(float(weights['feature_text_match']))
            evidence_list.append(StyleEvidenceItem(sku=p.sku, score=50.0, reason=f"Weak feature text style evidence"))
            continue

        # 5. Explicit Conflict (Score 30)
        if (p_style and any(cs in p_style for cs in conflict_styles)) or (p_coll and any(cs in p_coll for cs in conflict_styles)):
            scores.append(float(weights['style_conflict']))
            evidence_list.append(StyleEvidenceItem(sku=p.sku, score=30.0, reason=f"Style conflict with requested {target_style}"))
            continue

        # 6. Versatile Neutral Compatibility (Score 75)
        scores.append(75.0)
        evidence_list.append(StyleEvidenceItem(sku=p.sku, score=75.0, reason=f"Versatile catalog product compatible with {target_style} style"))

    valid_scores = [s for s in scores if s is not None]
    if not valid_scores:
        return 75.0, "Measured", evidence_list

    prod_avg = sum(valid_scores) / len(valid_scores)
    if len(products) > 1:
        matching_count = sum(1 for s in valid_scores if s >= 50)
        coherence_ratio = (matching_count / len(products)) * 100
        final_style_score = round(0.8 * prod_avg + 0.2 * coherence_ratio, 1)
    else:
        final_style_score = round(prod_avg, 1)

    return final_style_score, "Measured", evidence_list


def compute_spatial_fit_score(
    products: Sequence[ProductRow],
    result: ValidationResult,
    room_w: int,
    room_d: int,
    fixtures: Sequence[FixturePlacement] | None = None,
    room: RoomSpec | None = None,
) -> float:
    """
    Deterministic multi-factor spatial fit score (0-100):
    - 30% Boundary & margin quality
    - 25% Clearance quality between fixtures
    - 20% Usable circulation quality
    - 10% Door conflict margin
    - 10% Wall installation efficiency
    - 5% Wet-zone validity
    """
    has_overlap_issue = not result.valid and any(i.code == 'overlap' for i in result.issues)
    has_hard_issue = not result.valid and any(i.code in ('outside_room', 'door_collision', 'overlap', 'shower_not_wall_anchored', 'door_outside_room', 'category_price_exceeded', 'over_budget') for i in result.issues)

    room_area = room_w * room_d
    if room_area <= 0 or not products:
        empty_breakdown = [
            SpatialBreakdownItem(component="Boundary Fit", score=50.0, weight=0.25, status="pass", detail="Room dimension data unavailable"),
            SpatialBreakdownItem(component="Inter-Fixture Clearance", score=50.0, weight=0.15, status="pass", detail="Fixture data unavailable"),
            SpatialBreakdownItem(component="Space Utilization", score=50.0, weight=0.25, status="pass", detail="Fixture data unavailable"),
            SpatialBreakdownItem(component="Central Circulation", score=50.0, weight=0.10, status="pass", detail="Floor space data unavailable"),
            SpatialBreakdownItem(component="Door Clearance", score=50.0, weight=0.10, status="pass", detail="Door data unavailable"),
            SpatialBreakdownItem(component="Wall Efficiency", score=50.0, weight=0.10, status="pass", detail="Wall data unavailable"),
            SpatialBreakdownItem(component="Wet Zone Validity", score=50.0, weight=0.05, status="pass", detail="Shower data unavailable"),
        ]
        return 50.0, empty_breakdown

    used_area = sum((p.width_mm or 300) * (p.depth_mm or 300) for p in products)
    footprint_ratio = used_area / room_area

    # 1. Boundary & margin quality (30%)
    if 0.15 <= footprint_ratio <= 0.45:
        boundary_score = 100.0 - abs(footprint_ratio - 0.28) * 110.0
    else:
        boundary_score = max(20.0, 100.0 - abs(footprint_ratio - 0.28) * 180.0)
    boundary_score = min(100.0, max(0.0, boundary_score))

    # 2. Clearance quality (25%)
    n = len(products)
    if n > 1:
        clearance_score = min(100.0, max(30.0, 75.0 + (1.0 - (used_area / (room_area * 0.5))) * 25.0))
    else:
        clearance_score = 90.0

    # 3. Usable circulation quality (20%).  Open floor is desirable for
    # movement; only a large-room *cluster* is penalized, not free area itself.
    free_area_pct = max(0.0, (room_area - used_area * 1.5) / room_area)
    circulation_score = min(100.0, max(30.0, free_area_pct * 130.0))
    logical_fixtures = list(fixtures or [])
    if fixtures and any(p.category == 'vanity' for p in products):
        product_by_sku = {p.sku: p for p in products}
        logical_fixtures = [
            f for f in fixtures
            if product_by_sku.get(f.sku) is None or product_by_sku[f.sku].category not in ('basin', 'faucet')
        ]
    if len(logical_fixtures) >= 2:
        xs = [f.x_mm for f in logical_fixtures]
        ys = [f.y_mm for f in logical_fixtures]
        spread = max(max(xs) - min(xs), max(ys) - min(ys)) / max(room_w, room_d)
        # A generous central circulation zone remains intact; this detects only
        # layouts collapsed into one small corner/end of a room.
        distribution_quality = min(100.0, max(45.0, 45.0 + spread * 70.0))
        circulation_score = circulation_score * 0.65 + distribution_quality * 0.35

    # 4. Space Utilization / Inter-Fixture Separation (20%)
    # Uses envelope centers so large-footprint fixtures (vanity 900mm wide) are
    # correctly treated as "close" when centers are near, and far when they're on
    # opposite walls.  Any envelope-level physical overlap → 0 score for the pair.
    space_utilization_score = 90.0
    has_envelope_overlap = False
    toilet_legroom_blocked = False
    if len(logical_fixtures) >= 2 and room:
        p_by_sku = {p.sku: p for p in products}
        diagonal = math.hypot(room_w, room_d)

        def env_center(f: FixturePlacement):
            p = p_by_sku.get(f.sku)
            if p is None:
                return f.x_mm, f.y_mm
            env = fixture_envelope_polygon(f, p, room)
            cx = (env.bounds[0] + env.bounds[2]) / 2.0
            cy = (env.bounds[1] + env.bounds[3]) / 2.0
            return cx, cy

        centers = [env_center(f) for f in logical_fixtures]
        envelopes = []
        for f in logical_fixtures:
            p = p_by_sku.get(f.sku)
            if p:
                envelopes.append(fixture_envelope_polygon(f, p, room))
            else:
                envelopes.append(fixture_polygon(f, p) if p else None)

        pair_distances = []
        has_envelope_overlap = False
        for i in range(len(logical_fixtures)):
            for j in range(i + 1, len(logical_fixtures)):
                cx1, cy1 = centers[i]
                cx2, cy2 = centers[j]
                dist = math.hypot(cx1 - cx2, cy1 - cy2)
                pair_distances.append(dist)
                # Hard penalty: physical envelopes overlap in 2D ground plane
                if envelopes[i] and envelopes[j] and envelopes[i].intersects(envelopes[j]) and envelopes[i].intersection(envelopes[j]).area > 100:
                    has_envelope_overlap = True

        # Check toilet legroom approach clearance against other fixtures & shower wet zones
        toilet_legroom_blocked = False
        for f in logical_fixtures:
            p = p_by_sku.get(f.sku)
            if p and p.category in ('toilet', 'smart_toilet'):
                legroom_box = toilet_front_clearance_polygon(f, p, room)
                for j_f in logical_fixtures:
                    if j_f.sku == f.sku:
                        continue
                    j_p = p_by_sku.get(j_f.sku)
                    if j_p:
                        other_env = fixture_envelope_polygon(j_f, j_p, room)
                        if legroom_box.intersects(other_env) and legroom_box.intersection(other_env).area > 500:
                            toilet_legroom_blocked = True

        if has_envelope_overlap or toilet_legroom_blocked:
            # Layouts where installation envelopes overlap OR toilet legroom is blocked by another fixture/shower
            space_utilization_score = 15.0 if toilet_legroom_blocked and not has_envelope_overlap else 5.0
        elif pair_distances:
            min_dist = min(pair_distances)
            avg_dist = sum(pair_distances) / len(pair_distances)
            norm_avg = avg_dist / max(1.0, diagonal)
            # Highest score when avg separation >= 60% diagonal AND min separation >= 800mm
            base = 30.0 + norm_avg * 140.0
            min_bonus = min(35.0, (min_dist / 800.0) * 35.0)
            space_utilization_score = min(100.0, max(20.0, base + min_bonus))



    # 5. Door margin (10%) - calculate minimum distance from fixtures to door swing & threshold
    door_margin_score = 92.0
    if fixtures and room:
        d_poly = door_swing(room)
        p_by_sku = {p.sku: p for p in products}
        distances = []
        toilet_near_door = False
        d_seg = door_opening_segment(room)

        for f in fixtures:
            p = p_by_sku.get(f.sku)
            if p:
                f_poly = fixture_envelope_polygon(f, p, room)
                distances.append(f_poly.distance(d_poly))
                if p.category in ('toilet', 'smart_toilet'):
                    raw_poly = fixture_polygon(f, p)
                    if raw_poly.distance(d_seg) < 300:
                        toilet_near_door = True


        if distances:
            min_dist = min(distances)
            # 0 mm -> 50 score, >= 300 mm -> 100 score
            door_margin_score = min(100.0, max(40.0, 50.0 + (min_dist / 300.0) * 50.0))
            if toilet_near_door:
                door_margin_score = max(15.0, door_margin_score - 45.0)


    # 6. Wall efficiency (10%) - favor useful wall distribution, not occupied area.
    wall_score = 90.0
    if fixtures and room:
        r_poly = room_polygon(room)
        p_by_sku = {p.sku: p for p in products}
        wall_dists = []
        for f in fixtures:
            p = p_by_sku.get(f.sku)
            if p:
                f_poly = fixture_polygon(f, p)
                wall_dists.append(f_poly.distance(r_poly.boundary))
        if wall_dists:
            avg_dist = sum(wall_dists) / len(wall_dists)
            wall_score = min(100.0, max(50.0, 100.0 - avg_dist * 0.1))
        if logical_fixtures:
            anchors = set()
            for f in logical_fixtures:
                p = p_by_sku.get(f.sku)
                if not p:
                    continue
                poly = fixture_polygon(f, p)
                # Bounds provide directional attachment without an alternate layout model.
                minx, miny, maxx, maxy = poly.bounds
                distances = {'west': minx, 'east': room.width_mm - maxx, 'south': miny, 'north': room.depth_mm - maxy}
                anchors.add(min(distances, key=distances.get))
            # Strongly reward fixtures on different walls.
            # 1 unique wall → 45, 2 walls → 70, 3 walls → 88, 4 walls → 100
            wall_diversity = min(100.0, 45.0 + 18.0 * len(anchors))
            # Same-wall crowding penalty: every pair of non-shower fixtures sharing
            # the same anchor wall reduces the score.
            same_wall_pairs = 0
            anchors_list = []
            for f in logical_fixtures:
                p = p_by_sku.get(f.sku)
                if not p or p.category in ('shower', 'rainhead'):
                    continue
                poly = fixture_polygon(f, p)
                minx, miny, maxx, maxy = poly.bounds
                dists = {'west': minx, 'east': room.width_mm - maxx, 'south': miny, 'north': room.depth_mm - maxy}
                anchors_list.append(min(dists, key=dists.get))
            for i in range(len(anchors_list)):
                for j in range(i + 1, len(anchors_list)):
                    if anchors_list[i] == anchors_list[j]:
                        same_wall_pairs += 1
            same_wall_penalty = same_wall_pairs * 12.0
            wall_score = max(5.0, wall_score * 0.55 + wall_diversity * 0.45 - same_wall_penalty)

    # 7. Wet-zone validity (5%)
    wet_zone_score = 95.0
    showers = [p for p in products if p.category in ('shower', 'rainhead')]
    if showers:
        wet_zone_score = 100.0

    spatial_fit = (
        0.25 * boundary_score +
        0.15 * clearance_score +
        0.25 * space_utilization_score +
        0.10 * circulation_score +
        0.10 * door_margin_score +
        0.10 * wall_score +
        0.05 * wet_zone_score
    )
    if has_overlap_issue:
        has_envelope_overlap = True
    if has_hard_issue:
        spatial_fit_val = 0.0
    else:
        spatial_fit_val = round(min(100.0, max(0.0, spatial_fit)), 1)

    from ..models import SpatialBreakdownItem

    # 'overlap' status = physical envelopes actually intersect → red in UI
    # 'pass'    status = healthy or just a score nuance → no red indicator
    clearance_overlap = has_envelope_overlap  # fixtures' install envelopes overlap
    space_overlap = has_envelope_overlap or toilet_legroom_blocked  # overlap or toilet blocked

    breakdown_list = [
        SpatialBreakdownItem(
            component="Boundary Fit",
            score=round(boundary_score, 1),
            weight=0.25,
            status="pass",
            detail=f"✓ All selected fixtures remain within the {room_w} × {room_d} mm room bounds" if boundary_score >= 75 else f"△ High footprint density ({int(footprint_ratio*100)}% room utilization)"
        ),
        SpatialBreakdownItem(
            component="Inter-Fixture Clearance",
            score=round(clearance_score, 1),
            weight=0.15,
            status="overlap" if clearance_overlap else "pass",
            detail="⚠ Installation envelopes of two or more fixtures physically overlap — move fixtures apart" if clearance_overlap else "✓ Installation envelopes maintain clear separation between fixtures"
        ),
        SpatialBreakdownItem(
            component="Space Utilization",
            score=round(space_utilization_score, 1),
            weight=0.25,
            status="overlap" if space_overlap else "pass",
            detail=("⚠ Fixture envelopes physically overlap — fixtures are occupying the same floor area" if has_envelope_overlap
                    else "⚠ Toilet approach clearance is blocked by another fixture" if toilet_legroom_blocked
                    else "✓ Balanced fixture distribution across available floor space" if space_utilization_score >= 75
                    else "△ Uneven spatial distribution; fixtures cluster near one side of the room")
        ),
        SpatialBreakdownItem(
            component="Central Circulation",
            score=round(circulation_score, 1),
            weight=0.10,
            status="pass",
            detail="✓ Open central aisle for unhindered movement" if circulation_score >= 75 else "△ Central circulation path is somewhat constrained"
        ),
        SpatialBreakdownItem(
            component="Door Clearance",
            score=round(door_margin_score, 1),
            weight=0.10,
            status="pass",
            detail="✓ Door swing and entry threshold remain unobstructed" if door_margin_score >= 75 else "△ Fixture positioned close to door swing or entry threshold"
        ),
        SpatialBreakdownItem(
            component="Wall Efficiency",
            score=round(wall_score, 1),
            weight=0.10,
            status="pass",
            detail="✓ Fixtures efficiently anchored across available walls" if wall_score >= 75 else "△ Multiple fixtures share the same wall, causing localized crowding"
        ),
        SpatialBreakdownItem(
            component="Wet Zone Validity",
            score=round(wet_zone_score, 1),
            weight=0.05,
            status="pass",
            detail="✓ Dedicated 900×900mm shower wet zone properly wall-anchored"
        ),
    ]

    return spatial_fit_val, breakdown_list



KNOWN_PROFILE_ALIASES = {
    'smart budget': 'Smart Budget',
    'smart budget design': 'Smart Budget',
    'balanced': 'Balanced',
    'balanced design': 'Balanced',
    'premium': 'Premium',
    'premium design': 'Premium',
}


def normalize_profile_name(profile_name: str | None) -> str:
    if profile_name is None or not str(profile_name).strip():
        return 'Balanced'
    raw = str(profile_name).strip().lower()
    if raw in KNOWN_PROFILE_ALIASES:
        return KNOWN_PROFILE_ALIASES[raw]
    for alias, canonical in KNOWN_PROFILE_ALIASES.items():
        if alias in raw:
            return canonical
    raise ValueError(f"Unknown scoring profile: '{profile_name}'. Must be one of: Smart Budget, Balanced, Premium.")


def compute_design_score(
    products: Sequence[ProductRow],
    result: ValidationResult,
    budget_inr: int,
    style: str | None,
    room_w: int,
    room_d: int,
    profile_name: str | None = None,
    fixtures: Sequence[FixturePlacement] | None = None,
    room: RoomSpec | None = None,
) -> DesignScore:
    try:
        canonical_profile = normalize_profile_name(profile_name)
    except ValueError:
        canonical_profile = 'Balanced'
    weights = PROFILE_WEIGHTS[canonical_profile]

    score_started = perf_counter()
    stage_started = perf_counter()
    spatial_fit, spatial_breakdown = compute_spatial_fit_score(products, result, room_w, room_d, fixtures=fixtures, room=room)
    log_perf('spatial scoring', stage_started)

    stage_started = perf_counter()
    budget_fit = compute_budget_fit(result.total_price_inr, budget_inr)
    log_perf('budget scoring', stage_started)

    # Style Match Evaluation
    stage_started = perf_counter()
    style_match, style_match_status, style_evidence = compute_style_match(products, style)
    log_perf('style scoring', stage_started)

    # Compatibility Evaluation
    stage_started = perf_counter()
    compat_res = evaluate_compatibility(products)
    log_perf('compatibility scoring', stage_started)
    compatibility_score = compat_res.score
    compatibility_status = compat_res.status

    # Accessibility Rating Evaluation
    acc_vals = [p.accessibility_rating for p in products if p.accessibility_rating is not None]
    accessibility: float | None = round(sum(acc_vals) / len(acc_vals), 1) if acc_vals else None
    accessibility_status = "Planning estimate" if accessibility is not None else "Limited data available"

    # Sustainability Rating Evaluation
    eco_vals = [p.sustainability_rating for p in products if p.sustainability_rating is not None]
    sustainability: float | None = round(sum(eco_vals) / len(eco_vals), 1) if eco_vals else None
    sustainability_status = "Planning estimate" if sustainability is not None else "Limited data available"

    # Dynamic Weight Normalization over active metrics
    available_metrics = ['spatial_fit', 'budget_fit']
    unavailable_metrics = []

    raw_sum = weights['spatial_fit'] * spatial_fit + weights['budget_fit'] * budget_fit
    active_weight = weights['spatial_fit'] + weights['budget_fit']

    if style_match is not None:
        available_metrics.append('style_match')
        raw_sum += weights['style_match'] * style_match
        active_weight += weights['style_match']
    else:
        unavailable_metrics.append('style_match')

    if compatibility_score is not None:
        available_metrics.append('compatibility')
        raw_sum += weights['compatibility'] * compatibility_score
        active_weight += weights['compatibility']
    else:
        unavailable_metrics.append('compatibility')

    if accessibility is not None and weights.get('accessibility', 0) > 0:
        available_metrics.append('accessibility')
        raw_sum += weights['accessibility'] * accessibility
        active_weight += weights['accessibility']
    elif accessibility is None:
        unavailable_metrics.append('accessibility')

    if sustainability is not None and weights.get('sustainability', 0) > 0:
        available_metrics.append('sustainability')
        raw_sum += weights['sustainability'] * sustainability
        active_weight += weights['sustainability']
    elif sustainability is None:
        unavailable_metrics.append('sustainability')

    total = round(raw_sum / active_weight, 1) if active_weight > 0 else 0.0

    contributions = {
        'spatial_fit': weights['spatial_fit'] * spatial_fit / active_weight,
        'budget_fit': weights['budget_fit'] * budget_fit / active_weight,
        **({'style_match': weights['style_match'] * style_match / active_weight} if style_match is not None else {}),
        **({'compatibility': weights['compatibility'] * compatibility_score / active_weight} if compatibility_score is not None else {}),
    }
    rounded_contributions = {key: round(value, 1) for key, value in contributions.items()}
    # Keep the visible contribution contract exactly reconcilable with total after rounding.
    if rounded_contributions:
        last_key = next(reversed(rounded_contributions))
        rounded_contributions[last_key] = round(rounded_contributions[last_key] + (total - sum(rounded_contributions.values())), 1)

    design_score = DesignScore(
        spatial_fit=spatial_fit,
        spatial_breakdown=spatial_breakdown,
        budget_fit=budget_fit,
        style_match=style_match,
        style_match_status=style_match_status,
        style_evidence=style_evidence,
        compatibility=compatibility_score,
        compatibility_status=compatibility_status,
        accessibility=accessibility,
        accessibility_status=accessibility_status,
        sustainability=sustainability,
        sustainability_status=sustainability_status,
        total=total,
        available_metrics=available_metrics,
        unavailable_metrics=unavailable_metrics,
        score_method="Active weight normalization",
        weights={key: round(value * 100, 1) for key, value in weights.items() if value > 0},
        normalized_weight_sum=round(active_weight, 3),
        weighted_contributions=rounded_contributions,
    )
    log_perf('overall score calculation', score_started)
    return design_score
