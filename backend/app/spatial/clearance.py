from shapely.geometry import box, LineString
from ..models import RoomSpec

def door_opening_segment(room: RoomSpec):
    w = min(room.door_width_mm, room.width_mm)
    offset = max(0, min(room.door_offset_mm, room.width_mm - w)) if room.door_wall in ('south', 'north') else max(0, min(room.door_offset_mm, room.depth_mm - w))
    if room.door_wall == 'south':
        return LineString([(offset, 0), (offset + w, 0)])
    if room.door_wall == 'north':
        return LineString([(offset, room.depth_mm), (offset + w, room.depth_mm)])
    if room.door_wall == 'west':
        return LineString([(0, offset), (0, offset + w)])
    return LineString([(room.width_mm, offset), (room.width_mm, offset + w)])

def door_swing(room: RoomSpec):
    """
    Returns the interior door-clearance zone: a hard "keep clear" strip just
    inside the doorway. The door itself is modelled as opening OUTWARD (away
    from the bathroom), so no fixture-blocking swing arc is needed inside the
    room — only a shallow strip for the door leaf/frame and stepping through
    the threshold. This is deliberately the single source of the door
    clearance depth (200mm); the 2D plan (FloorPlan2D.tsx) and the PDF export
    (pdf_export.py) each draw the same rectangle and must be kept at the same
    depth if it ever changes again.
    """
    w = min(room.door_width_mm, room.width_mm)
    offset = room.door_offset_mm
    depth = 200  # mm of interior clearance for an outward-opening door

    if room.door_wall == 'south':
        return box(offset, 0, offset + w, depth)
    if room.door_wall == 'north':
        return box(offset, max(0, room.depth_mm - depth), offset + w, room.depth_mm)
    if room.door_wall == 'west':
        return box(0, offset, depth, offset + w)
    # east
    return box(max(0, room.width_mm - depth), offset, room.width_mm, offset + w)
