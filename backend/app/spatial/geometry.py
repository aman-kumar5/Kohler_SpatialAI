from shapely.geometry import box
from ..models import FixturePlacement, ProductRow, RoomSpec
from .rules import get_installation_envelope_dims

def fixture_polygon(f: FixturePlacement, p: ProductRow):
    w, d = p.width_mm or 0, p.depth_mm or 0
    if f.rotation_deg in (90, 270):
        w, d = d, w
    return box(f.x_mm, f.y_mm, f.x_mm + w, f.y_mm + d)


def shower_wall_attachment(f: FixturePlacement, p: ProductRow, room: RoomSpec) -> str:
    """Return the closest physical wall for a wall-mounted shower fixture."""
    w, d = p.width_mm or 0, p.depth_mm or 0
    if f.rotation_deg in (90, 270):
        w, d = d, w
    distances = {
        'west': f.x_mm,
        'east': room.width_mm - (f.x_mm + w),
        'south': f.y_mm,
        'north': room.depth_mm - (f.y_mm + d),
    }
    return min(distances, key=distances.get)

def fixture_envelope_polygon(f: FixturePlacement, p: ProductRow, room: RoomSpec = None):
    w, d = p.width_mm or 0, p.depth_mm or 0
    env_w, env_d, _ = get_installation_envelope_dims(p.category, w, d)
    if f.rotation_deg in (90, 270):
        env_w, env_d = env_d, env_w
        
    if p.category == 'shower' and room is not None:
        side = shower_wall_attachment(f, p, room)
        if side == 'west':
            x = 0
            y = min(max(f.y_mm - (env_d - d) // 2, 0), max(0, room.depth_mm - env_d))
        elif side == 'east':
            x = max(0, room.width_mm - env_w)
            y = min(max(f.y_mm - (env_d - d) // 2, 0), max(0, room.depth_mm - env_d))
        elif side == 'south':
            x = min(max(f.x_mm - (env_w - w) // 2, 0), max(0, room.width_mm - env_w))
            y = 0
        else:  # north
            x = min(max(f.x_mm - (env_w - w) // 2, 0), max(0, room.width_mm - env_w))
            y = max(0, room.depth_mm - env_d)
        return box(x, y, x + env_w, y + env_d)

    if p.category in ('toilet', 'smart_toilet'):
        env_w = max(w, 650)
        env_d = max(d, 700)
        rot = f.rotation_deg % 360
        if room is not None:
            side = shower_wall_attachment(f, p, room)
            if rot == 0:
                rot = {'south': 0, 'west': 90, 'north': 180, 'east': 270}[side]
            if rot in (90, 270):
                env_w, env_d = env_d, env_w

            x = min(max(f.x_mm, 0), max(0, room.width_mm - env_w))
            y = min(max(f.y_mm, 0), max(0, room.depth_mm - env_d))
            return box(x, y, x + env_w, y + env_d)

        if rot in (90, 270):
            env_w, env_d = env_d, env_w
        return box(f.x_mm, f.y_mm, f.x_mm + env_w, f.y_mm + env_d)




    return box(f.x_mm, f.y_mm, f.x_mm + env_w, f.y_mm + env_d)


def toilet_front_clearance_polygon(f: FixturePlacement, p: ProductRow, room: RoomSpec = None):
    """Returns the 450mm front approach legroom box directly in front of the toilet bowl."""
    w, d = p.width_mm or 0, p.depth_mm or 0
    clearance_depth = 450
    env_min_w = max(w, 650)
    rot = f.rotation_deg % 360
    if rot == 0 and room is not None:
        side = shower_wall_attachment(f, p, room)
        rot = {'south': 0, 'west': 90, 'north': 180, 'east': 270}[side]
    
    if rot == 90:  # facing East (+X)
        cy = f.y_mm + w / 2.0
        return box(f.x_mm + d, cy - env_min_w / 2.0, f.x_mm + d + clearance_depth, cy + env_min_w / 2.0)
    elif rot == 180:  # facing South (-Y)
        cx = f.x_mm + w / 2.0
        return box(cx - env_min_w / 2.0, max(0, f.y_mm - clearance_depth), cx + env_min_w / 2.0, f.y_mm)
    elif rot == 270:  # facing West (-X)
        cy = f.y_mm + w / 2.0
        return box(max(0, f.x_mm - clearance_depth), cy - env_min_w / 2.0, f.x_mm, cy + env_min_w / 2.0)
    else:  # facing North (+Y)
        cx = f.x_mm + w / 2.0
        return box(cx - env_min_w / 2.0, f.y_mm + d, cx + env_min_w / 2.0, f.y_mm + d + clearance_depth)



    return box(f.x_mm, f.y_mm, f.x_mm + env_w, f.y_mm + env_d)


def room_polygon(room: RoomSpec):
    return box(0, 0, room.width_mm, room.depth_mm)
