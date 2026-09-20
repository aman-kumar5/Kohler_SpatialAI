"""
Deterministic Product Compatibility Engine for KOHLER SpatialAI.

Evaluates structural and installation compatibility rules based on product metadata:
1. Basin + Vanity dimensional mounting constraints (Basin width & depth <= Vanity width & depth).
2. Category pairing rules.
3. Explicit distinction between KNOWN COMPATIBLE, KNOWN INCOMPATIBLE, and UNKNOWN (Limited data available).
"""
from __future__ import annotations
from typing import Sequence
from ..models import ProductRow

class CompatibilityCheckResult:
    def __init__(
        self,
        compatible: bool,
        score: float | None,
        status: str,
        message: str,
    ):
        self.compatible = compatible
        self.score = score
        self.status = status
        self.message = message

def _extract_finish(p: ProductRow) -> str:
    finish_val = getattr(p, 'finish_color', getattr(p, 'finish', '')) or ''
    text = f"{p.name} {finish_val} {p.features or ''} {p.keywords or ''}".lower()
    if 'brass' in text or 'gold' in text or 'bronze' in text: return 'gold/brass'
    if 'black' in text or 'dark' in text: return 'matte_black'
    if 'nickel' in text or 'brushed' in text: return 'brushed_nickel'
    if 'chrome' in text or 'polished' in text: return 'chrome'
    return 'neutral'

def evaluate_compatibility(products: Sequence[ProductRow]) -> CompatibilityCheckResult:
    """Evaluates deterministic compatibility rules across selected products."""
    if not products:
        return CompatibilityCheckResult(True, 100.0, "Measured", "No products selected")

    checks: list[float] = []
    messages: list[str] = []
    has_known_relationship = False

    basins = [p for p in products if p.category == 'basin']
    vanities = [p for p in products if p.category == 'vanity']
    faucets = [p for p in products if p.category == 'faucet']
    showers = [p for p in products if p.category in ('shower', 'rainhead')]

    # 1. Basin + Vanity Mounting & Dimensional Compatibility
    if basins and vanities:
        has_known_relationship = True
        for basin in basins:
            for vanity in vanities:
                bw, bd = basin.width_mm, basin.depth_mm
                vw, vd = vanity.width_mm, vanity.depth_mm

                if bw is None or bd is None or vw is None or vd is None:
                    continue

                if bw > vw:
                    checks.append(0.0)
                    messages.append(f"Incompatible: Basin width ({bw}mm) exceeds vanity counter width ({vw}mm).")
                elif bd > vd:
                    checks.append(0.0)
                    messages.append(f"Incompatible: Basin depth ({bd}mm) exceeds vanity counter depth ({vd}mm).")
                else:
                    ratio = bw / vw
                    if 0.55 <= ratio <= 0.85:
                        checks.append(100.0)
                        messages.append(f"Optimal Fit: Basin ({bw}mm) fits vanity ({vw}mm) with ideal deck clearance.")
                    else:
                        checks.append(85.0)
                        messages.append(f"Compatible: Basin ({bw}mm) fits vanity counter ({vw}mm).")

    # 2. Faucet + Basin Spout & Rim Clearance Compatibility
    if faucets and basins:
        has_known_relationship = True
        for faucet in faucets:
            for basin in basins:
                faucet_text = f"{faucet.name} {faucet.features or ''}".lower()
                basin_text = f"{basin.name} {basin.features or ''} {basin.installation_type or ''}".lower()
                basin_height = basin.height_mm or 0

                is_vessel = 'vessel' in basin_text or basin_height >= 140
                is_tall_faucet = 'tall' in faucet_text or (faucet.height_mm or 0) >= 240 or 'wall-mount' in faucet_text or 'wall' in faucet_text

                if is_vessel:
                    if is_tall_faucet:
                        checks.append(100.0)
                        messages.append(f"Compatible: Tall/wall faucet serves vessel sink.")
                    else:
                        checks.append(40.0)
                        messages.append(f"Partial compatibility: Standard height faucet with vessel sink.")
                else:
                    if is_tall_faucet:
                        checks.append(80.0)
                        messages.append(f"Mostly compatible: Tall faucet with recessed basin.")
                    else:
                        checks.append(95.0)
                        messages.append(f"Compatible: Faucet serves basin.")

    # 3. Finish & Material Harmony
    trim_products = [p for p in products if p.category in ('faucet', 'shower', 'rainhead', 'drain')]
    if len(trim_products) >= 2:
        has_known_relationship = True
        finishes = set(_extract_finish(p) for p in trim_products if _extract_finish(p) != 'neutral')
        if len(finishes) <= 1:
            checks.append(100.0)
            messages.append("Harmonious: Matching trim metal finishes across fixtures.")
        else:
            checks.append(75.0)
            messages.append(f"Finish variation: Mixed trim finishes ({', '.join(finishes)}).")

    # 4. Collection / Design Line Cohesion
    collections = set(p.collection.lower() for p in products if p.collection and p.collection.strip())
    if collections:
        has_known_relationship = True
        if len(collections) == 1:
            checks.append(100.0)
            messages.append(f"Unified Series: All products belong to the KOHLER {next(iter(collections)).title()} collection.")
        else:
            checks.append(88.0)
            messages.append(f"Curated Blend: Products selected from {len(collections)} complementary KOHLER collections.")

    if not checks:
        if has_known_relationship:
            return CompatibilityCheckResult(True, None, "Limited data available", "Compatibility data unavailable (missing product dimensions)")
        return CompatibilityCheckResult(True, 90.0, "Measured", "Valid independent fixtures")

    final_score = round(sum(checks) / len(checks), 1)
    status = "Known incompatible" if final_score < 40 else ("Partially compatible" if final_score < 70 else "Measured")
    msg_str = " | ".join(messages) if messages else "Valid independent fixtures"
    return CompatibilityCheckResult(final_score >= 40, final_score, status, msg_str)
