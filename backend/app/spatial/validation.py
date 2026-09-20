from dataclasses import dataclass
from shapely.geometry import box

from ..models import LayoutRequest, ValidationIssue, ValidationResult, RoomSpec
from ..repository import product_by_sku
from .geometry import fixture_polygon, fixture_envelope_polygon, room_polygon
from .collision import overlaps
from .clearance import door_swing
from .wash_zone import derive_wash_zone

def check_inside_room(poly, room):
    return room.contains(poly) or room.covers(poly)

def check_overlap(a, b):
    return overlaps(a, b)

def check_clearance(poly, others, required_mm=0):
    return all(poly.buffer(required_mm).intersection(o).area == 0 for o in others)

def check_door_collision(poly, door_polygon):
    return overlaps(poly, door_polygon)

def check_wall_constraints(poly, room):
    return check_inside_room(poly, room)

def check_shower_wall_anchor(poly, room, tolerance_mm=50):
    """Shower assemblies must touch a room wall rather than float in open space."""
    return poly.distance(room.boundary) <= tolerance_mm

@dataclass(frozen=True)
class ValidationContext:
    """Per-request static geometry reused while exploring candidate layouts."""
    room_polygon: object
    door_polygon: object


def make_validation_context(room: RoomSpec) -> ValidationContext:
    return ValidationContext(room_polygon=room_polygon(room), door_polygon=door_swing(room))


def validate_layout(request: LayoutRequest, context: ValidationContext | None = None) -> ValidationResult:
    issues = []
    total = 0
    context = context or make_validation_context(request.room)
    room = context.room_polygon
    resolved = []
    valid_fixtures = []
    valid_products = []
    
    # Check door swing boundary
    d_swing = context.door_polygon
    if not check_inside_room(d_swing, room):
        issues.append(ValidationIssue(
            code='door_outside_room',
            message='Door clearance envelope extends outside the room boundary.',
            fixture_skus=[]
        ))

    cat_constraints = request.category_constraints or {}
    
    for f in request.fixtures:
        p = product_by_sku(f.sku)
        if not p:
            issues.append(ValidationIssue(
                code='unknown_sku',
                message=f'Product {f.sku} is not in the CSV.',
                fixture_skus=[f.sku]
            ))
            continue
        
        total += p.price_inr

        # Check category price constraints
        if p.category in cat_constraints:
            max_p = cat_constraints[p.category].get("max_price_inr")
            if max_p is not None and p.price_inr > max_p:
                issues.append(ValidationIssue(
                    code='category_price_exceeded',
                    message=f'{p.category.title()} {p.sku} price (₹{p.price_inr:,}) exceeds category max limit of ₹{max_p:,}.',
                    fixture_skus=[f.sku]
                ))

        poly = fixture_polygon(f, p)
        env_poly = fixture_envelope_polygon(f, p, request.room)
        
        # Always validate the real catalog fixture independently from its
        # directional shower installation zone.
        if not check_inside_room(poly, room):
            issues.append(ValidationIssue(
                code='outside_room',
                message=f'Fixture {f.sku} extends outside the room.',
                fixture_skus=[f.sku]
            ))
        elif not check_inside_room(env_poly, room):
            issues.append(ValidationIssue(
                code='outside_room',
                message=f'Fixture {f.sku} installation envelope extends outside the room.',
                fixture_skus=[f.sku]
            ))
        
        if check_door_collision(poly, d_swing) or check_door_collision(env_poly, d_swing):
            all_associated = [f.sku]
            if p.category in ('vanity', 'basin', 'faucet'):
                all_associated = list({fix.sku for fix in request.fixtures if product_by_sku(fix.sku) and product_by_sku(fix.sku).category in ('vanity', 'basin', 'faucet')})
            issues.append(ValidationIssue(
                code='door_collision',
                message=f'{p.category.title()} ({f.sku}) overlaps the door swing/clearance zone (yellow dashed doorway area). Move fixture away from doorway.',
                fixture_skus=all_associated
            ))


        if p.category in ('shower', 'rainhead') and not check_shower_wall_anchor(poly, room):
            issues.append(ValidationIssue(
                code='shower_not_wall_anchored',
                message='Shower must be anchored to a bathroom wall inside its wet zone.',
                fixture_skus=[f.sku]
            ))
            
        for sku, other_env, other_product in resolved:
            # Basin/faucet entries can be catalog members of the same physical
            # vanity wash station. They share the vanity anchor by design and
            # must still be checked against every *other* installation zone.
            wash_station_pair = {p.category, other_product.category}.issubset({'vanity', 'basin', 'faucet'})
            if check_overlap(env_poly, other_env) and not wash_station_pair:
                issues.append(ValidationIssue(
                    code='overlap',
                    message=f'Installation envelopes overlap between fixtures ({sku} and {f.sku}).',
                    fixture_skus=[sku, f.sku]
                ))
                
        resolved.append((f.sku, env_poly, p))
        valid_fixtures.append(f)
        valid_products.append(p)

    # The vanity/basin/faucet WashStation is one physical installation, wider
    # than any single member's own rectangle (see wash_zone.derive_wash_zone,
    # the same function that drives the 2D/3D/PDF WashStation visual). A
    # fixture-by-fixture check above only ever sees each member's own raw
    # footprint, so a narrow vanity SKU can pass while the real wash-station
    # footprint it belongs to still reaches into the door swing. This is the
    # single place that complete envelope is checked against the door and
    # room boundary as a hard constraint, so 2D drag, the optimizer search,
    # and this endpoint can never disagree about whether it is feasible.
    wash_zone = derive_wash_zone(valid_fixtures, valid_products, request.room)
    if wash_zone is not None:
        wash_zone_poly = box(
            wash_zone.x_mm, wash_zone.y_mm,
            wash_zone.x_mm + wash_zone.width_mm, wash_zone.y_mm + wash_zone.depth_mm,
        )
        if check_door_collision(wash_zone_poly, d_swing):
            issues.append(ValidationIssue(
                code='door_collision',
                message='Vanity overlaps the door clearance zone.',
                fixture_skus=list(wash_zone.members),
            ))
        elif not check_inside_room(wash_zone_poly, room):
            issues.append(ValidationIssue(
                code='outside_room',
                message='Vanity installation envelope extends outside the room.',
                fixture_skus=list(wash_zone.members),
            ))
        
        for sku, other_env, other_product in resolved:
            if other_product.category not in ('vanity', 'basin', 'faucet'):
                if check_overlap(wash_zone_poly, other_env):
                    issues.append(ValidationIssue(
                        code='overlap',
                        message=f'Wash station envelope overlaps fixture {sku}.',
                        fixture_skus=list(wash_zone.members) + [sku],
                    ))

    if request.budget_inr is not None and total > request.budget_inr:
        issues.append(ValidationIssue(
            code='over_budget',
            message='Product total exceeds the stated budget.',
            fixture_skus=[]
        ))
        
    return ValidationResult(valid=not issues, issues=issues, total_price_inr=total)
