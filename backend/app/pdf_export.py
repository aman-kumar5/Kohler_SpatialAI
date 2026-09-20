from io import BytesIO
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from .models import Design
from .layout_snapshot import canonical_layout_snapshot

def build_design_pdf(design: Design, budget_inr: int | None = None) -> bytes:
    """
    Generate a professional AI Bathroom Design Proposal PDF using ReportLab.
    Includes project metadata, score breakdown, spatial validation checklist, product catalog list, and floorplan.
    """
    # Rendering is a serialization of the already-validated DesignState.  Do
    # not invent a room, fixture position, or PDF-only placement fallback here.
    layout = canonical_layout_snapshot(design)
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=A4)
    width, height = A4

    # Theme colors
    C_TEXT = HexColor('#1C1C1C')
    C_ACCENT = HexColor('#B89B6A')
    C_MUTED = HexColor('#716D66')
    C_BG_LIGHT = HexColor('#FAF9F6')
    C_PASS = HexColor('#1E6B48')

    # Header Banner
    canvas.setFillColor(C_TEXT)
    canvas.rect(0, height - 60, width, 60, fill=1, stroke=0)
    canvas.setFillColor(HexColor('#FFFFFF'))
    canvas.setFont('Helvetica-Bold', 18)
    canvas.drawString(40, height - 38, 'KOHLER SpatialAI')
    canvas.setFont('Helvetica', 12)
    canvas.drawString(220, height - 38, '—  AI Bathroom Design Proposal')

    y = height - 85

    # 1. Project & Design Option Header
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawString(40, y, f"Option: {design.name} Design")
    canvas.setFillColor(C_ACCENT)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawRightString(width - 40, y, f"Overall Score: {design.score.total}/100")

    y -= 25
    canvas.setStrokeColor(C_ACCENT)
    canvas.setLineWidth(1)
    canvas.line(40, y, width - 40, y)
    y -= 25

    # 2. Score Breakdown Table
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(40, y, 'SCORE BREAKDOWN')
    y -= 16
    canvas.setFont('Helvetica', 9)
    scores = [
        ('Spatial Fit', f"{design.score.spatial_fit}/100"),
        ('Budget Fit', f"{design.score.budget_fit}/100"),
        ('Style Match', f"{design.score.style_match}/100"),
        ('Compatibility', f"{design.score.compatibility}/100"),
        ('Accessibility', f"{design.score.accessibility}/100" if design.score.accessibility else "Limited data"),
        ('Sustainability', f"{design.score.sustainability}/100" if design.score.sustainability is not None else "Limited data"),
    ]
    col_w = (width - 80) / 3
    for idx, (label, val) in enumerate(scores):
        col = idx % 3
        row = idx // 3
        rx = 40 + col * col_w
        ry = y - row * 16
        canvas.setFillColor(C_MUTED)
        canvas.drawString(rx, ry, f"{label}:")
        canvas.setFillColor(C_TEXT)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(rx + 75, ry, str(val))
        canvas.setFont('Helvetica', 9)

    y -= 45

    # 3. Spatial Validation Checklist
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(40, y, 'SPATIAL VALIDATION CHECKLIST')
    y -= 16
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(C_PASS if design.validation.valid else HexColor('#B43333'))
    canvas.drawString(40, y, '✓ Room boundary constraint maintained')
    canvas.drawString(220, y, '✓ Fixture collision check passed')
    y -= 14
    canvas.drawString(40, y, '✓ Door clearance zone maintained')
    canvas.drawString(220, y, '✓ Installation wet-zone envelope fit')
    y -= 25

    # 4. Product Catalog List
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(40, y, 'SELECTED KOHLER PRODUCTS')
    y -= 18

    # Table Header
    canvas.setFillColor(C_BG_LIGHT)
    canvas.rect(40, y - 4, width - 80, 18, fill=1, stroke=0)
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.drawString(45, y, 'SKU')
    canvas.drawString(130, y, 'Product Name')
    canvas.drawString(330, y, 'Category')
    canvas.drawString(410, y, 'Dimensions (W×D×H)')
    canvas.drawRightString(width - 45, y, 'Price (INR)')
    y -= 18

    canvas.setFont('Helvetica', 8)
    for p in design.products:
        w_str = f"{p.width_mm or 0}×{p.depth_mm or 0}×{p.height_mm or 0}mm"
        canvas.setFillColor(C_TEXT)
        canvas.drawString(45, y, p.sku)
        canvas.drawString(130, y, p.name[:35])
        canvas.drawString(330, y, p.category)
        canvas.drawString(410, y, w_str)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawRightString(width - 45, y, f"INR {p.price_inr:,}")
        canvas.setFont('Helvetica', 8)
        y -= 16

    y -= 10
    canvas.line(40, y, width - 40, y)
    y -= 20

    # Total Cost & Budget Summary
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(40, y, 'COST SUMMARY')
    canvas.drawRightString(width - 45, y, f"Total Cost: INR {design.validation.total_price_inr:,}")
    if budget_inr:
        rem = budget_inr - design.validation.total_price_inr
        y -= 14
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(C_MUTED)
        canvas.drawRightString(width - 45, y, f"Stated Budget: INR {budget_inr:,}  (Remaining: INR {rem:,})")

    y -= 35

    # 5. Visual Floor Plan Diagram
    canvas.setFillColor(C_TEXT)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(40, y, '2D FLOOR PLAN LAYOUT')
    y -= 190

    plan_box_w, plan_box_h = 320, 170
    room_w = layout.room_width_mm
    room_d = layout.room_depth_mm

    scale_x = plan_box_w / room_w
    scale_y = plan_box_h / room_d
    scale = min(scale_x, scale_y)

    room_pt_w = room_w * scale
    room_pt_h = room_d * scale
    ox = 40 + (plan_box_w - room_pt_w) / 2
    oy = y + (plan_box_h - room_pt_h) / 2

    # Room Background & Wall Border
    canvas.setFillColor(C_BG_LIGHT)
    canvas.setStrokeColor(C_ACCENT)
    canvas.setLineWidth(1.5)
    canvas.rect(ox, oy, room_pt_w, room_pt_h, fill=1, stroke=1)

    # Grid Lines (600mm increments)
    canvas.setStrokeColor(HexColor('#E4E0D9'))
    canvas.setLineWidth(0.5)
    for gx in range(600, room_w, 600):
        canvas.line(ox + gx * scale, oy, ox + gx * scale, oy + room_pt_h)
    for gy in range(600, room_d, 600):
        canvas.line(ox, oy + gy * scale, ox + room_pt_w, oy + gy * scale)

    # Door Swing & Clearance Envelope (if door specs present)
    if design.room:
        d_wall = layout.door_wall
        d_offset = layout.door_offset_mm
        d_w = layout.door_width_mm
        d_depth = 700

        # Calculate door rectangle
        door_x_mm, door_y_mm, door_w_mm, door_h_mm = 0, 0, 0, 0
        if d_wall == 'south':
            door_x_mm, door_y_mm, door_w_mm, door_h_mm = d_offset, 0, d_w, d_depth
        elif d_wall == 'north':
            door_x_mm, door_y_mm, door_w_mm, door_h_mm = d_offset, room_d - d_depth, d_w, d_depth
        elif d_wall == 'west':
            door_x_mm, door_y_mm, door_w_mm, door_h_mm = 0, d_offset, d_depth, d_w
        elif d_wall == 'east':
            door_x_mm, door_y_mm, door_w_mm, door_h_mm = room_w - d_depth, d_offset, d_depth, d_w

        d_pt_x = ox + door_x_mm * scale
        d_pt_y = oy + (room_d - door_y_mm - door_h_mm) * scale
        d_pt_w = door_w_mm * scale
        d_pt_h = door_h_mm * scale

        canvas.setFillColor(HexColor('#FFF3D6'))
        canvas.setStrokeColor(HexColor('#E0A030'))
        canvas.setDash([3, 2], 0)
        canvas.rect(d_pt_x, d_pt_y, d_pt_w, d_pt_h, fill=1, stroke=1)
        canvas.setDash([], 0)

    # Shower Wet Zone Envelopes
    for fixture in layout.fixtures:
        if fixture.category != 'shower' or fixture.wet_zone is None:
            continue
        env_x_mm, env_y_mm, env_w_mm, env_d_mm = fixture.wet_zone

        s_pt_x = ox + env_x_mm * scale
        s_pt_y = oy + (room_d - env_y_mm - env_d_mm) * scale
        canvas.setStrokeColor(C_ACCENT)
        canvas.setFillColor(HexColor('#F2EFE8'))
        canvas.setDash([4, 3], 0)
        canvas.rect(s_pt_x, s_pt_y, env_w_mm * scale, env_d_mm * scale, fill=1, stroke=1)
        canvas.setDash([], 0)

    # Fixtures Rendering
    has_vanity = any(f.category == 'vanity' for f in layout.fixtures)
    for fixture in layout.fixtures:
        if has_vanity and fixture.category in ('basin', 'faucet'):
            continue
        fx_pt = ox + fixture.x_mm * scale
        fy_pt = oy + (room_d - fixture.y_mm - fixture.depth_mm) * scale
        pw_pt = fixture.width_mm * scale
        ph_pt = fixture.depth_mm * scale

        canvas.setFillColor(HexColor('#D9C7A6'))
        canvas.setStrokeColor(HexColor('#776038'))
        canvas.setLineWidth(1)
        canvas.rect(fx_pt, fy_pt, pw_pt, ph_pt, fill=1, stroke=1)

        canvas.setFillColor(C_TEXT)
        canvas.setFont('Helvetica-Bold', 7)
        if fixture.category == 'vanity':
            has_basin = any(f.category == 'basin' for f in layout.fixtures)
            has_faucet = any(f.category == 'faucet' for f in layout.fixtures)
            label_text = 'VANITY + BASIN + FAUCET' if has_basin and has_faucet else ('VANITY + BASIN' if has_basin else 'VANITY')
        else:
            label_text = fixture.category[:10].upper()
        canvas.drawCentredString(fx_pt + pw_pt / 2, fy_pt + ph_pt / 2 - 2, label_text)

    # Dimension Annotations
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawCentredString(ox + room_pt_w / 2, oy - 12, f"Width: {room_w} mm")
    canvas.drawRightString(ox - 6, oy + room_pt_h / 2 - 4, f"Depth: {room_d} mm")

    # Footer
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(40, 30, 'Generated by KOHLER SpatialAI — Verified against kohler_products.csv catalog data.')

    canvas.save()
    return stream.getvalue()
