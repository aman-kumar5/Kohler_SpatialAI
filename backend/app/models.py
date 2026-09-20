from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Any


class ProductRow(BaseModel):
    """Maps directly to columns in kohler_products.csv."""
    sku: str
    name: str  # mapped from product_name
    category: str
    price_inr: int
    width_mm: int | None = None
    depth_mm: int | None = None
    height_mm: int | None = None
    installation_type: str | None = None
    finish: str | None = None
    collection: str | None = None  # mapped from collection
    features: str | None = None    # mapped from features
    style: str | None = None       # extracted from collection & text evidence
    keywords: str | None = None    # extracted features & tags
    accessibility_rating: float | None = None
    sustainability_rating: float | None = None
    accessibility_basis: str | None = None
    sustainability_basis: str | None = None
    rating_provenance: str | None = None

    @classmethod
    def from_csv_row(cls, row: dict) -> "ProductRow":
        """Create a ProductRow from a raw CSV dict, preserving all catalog fields."""
        price_raw = row.get("price_inr")
        try:
            price = int(float(price_raw)) if price_raw is not None else 0
        except (ValueError, TypeError):
            price = 0

        def _int_or_none(v: Any) -> int | None:
            try:
                return int(float(v)) if v is not None and str(v).strip() not in ("", "nan") else None
            except (ValueError, TypeError):
                return None

        def _float_or_none(v: Any) -> float | None:
            try:
                return float(v) if v is not None and str(v).strip() not in ("", "nan", "None") else None
            except (ValueError, TypeError):
                return None

        def _str_or_none(v: Any) -> str | None:
            if v is None or str(v).strip() in ("", "nan", "None"):
                return None
            return str(v).strip()

        name = str(row.get("product_name", row.get("name", "")))
        collection = _str_or_none(row.get("collection"))
        features = _str_or_none(row.get("features"))
        install_type = _str_or_none(row.get("installation_type"))
        finish = _str_or_none(row.get("finish"))

        # Extract text evidence for style matching
        combined_text = f"{name} {collection or ''} {features or ''}".lower()
        style_tags = []
        if any(w in combined_text for w in ['modern', 'contemporary', 'sleek', 'minimalist', 'clean', 'wall-hung', 'smart']):
            style_tags.append('modern')
        if any(w in combined_text for w in ['classic', 'classical', 'traditional', 'vintage', 'ornate']):
            style_tags.append('classical')
        if any(w in combined_text for w in ['industrial', 'matte', 'exposed', 'raw']):
            style_tags.append('industrial')
        if any(w in combined_text for w in ['scandinavian', 'nordic', 'simple', 'light']):
            style_tags.append('scandinavian')

        primary_style = style_tags[0] if style_tags else (collection.lower() if collection else None)

        acc_rating = _float_or_none(row.get("accessibility_rating"))
        eco_rating = _float_or_none(row.get("sustainability_rating"))
        acc_basis = _str_or_none(row.get("accessibility_basis")) or "Estimated planning score based on installation type, dimensions and spatial planning characteristics."
        eco_basis = _str_or_none(row.get("sustainability_basis")) or "Estimated planning score based on available catalog features such as water-use information, product type and installation characteristics."
        provenance = _str_or_none(row.get("rating_provenance")) or "estimated_from_catalog"

        return cls(
            sku=str(row["sku"]),
            name=name,
            category=str(row.get("category", "")),
            price_inr=price,
            width_mm=_int_or_none(row.get("width_mm")),
            depth_mm=_int_or_none(row.get("depth_mm")),
            height_mm=_int_or_none(row.get("height_mm")),
            installation_type=install_type,
            finish=finish,
            collection=collection,
            features=features,
            style=primary_style,
            keywords=features or collection,
            accessibility_rating=acc_rating,
            sustainability_rating=eco_rating,
            accessibility_basis=acc_basis,
            sustainability_basis=eco_basis,
            rating_provenance=provenance,
        )


class RoomSpec(BaseModel):
    width_mm: int = Field(gt=0)
    depth_mm: int = Field(gt=0)
    door_wall: Literal['north', 'south', 'east', 'west'] = 'south'
    door_offset_mm: int = Field(default=0, ge=0)
    door_width_mm: int = Field(default=700, gt=0)


class RequirementSpec(BaseModel):
    room: RoomSpec | None = None
    budget_inr: int | None = Field(default=None, ge=0)
    style: str | None = None
    priority: str | None = None
    requirements: list[str] = []
    category_constraints: dict[str, dict[str, int]] = Field(default_factory=dict)


class ProductSearchRequest(BaseModel):
    categories: list[str] = []
    keywords: list[str] = []
    style: str | None = None
    budget_inr: int | None = None


class FixturePlacement(BaseModel):
    sku: str
    x_mm: int
    y_mm: int
    rotation_deg: Literal[0, 90, 180, 270] = 0


class LayoutRequest(BaseModel):
    room: RoomSpec
    fixtures: list[FixturePlacement]
    budget_inr: int | None = None
    category_constraints: dict[str, dict[str, int]] = Field(default_factory=dict)


class LayoutEvaluateRequest(BaseModel):
    room: RoomSpec
    fixtures: list[FixturePlacement]
    budget_inr: int | None = None
    category_constraints: dict[str, dict[str, int]] = Field(default_factory=dict)
    style: str | None = None
    design_name: str = "User Edited"


class ValidationIssue(BaseModel):
    code: str
    message: str
    fixture_skus: list[str] = []


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = []
    total_price_inr: int = 0


class WashZone(BaseModel):
    """Logical planning zone; member product dimensions remain catalog-backed."""
    id: str = 'wash-zone'
    x_mm: int
    y_mm: int
    width_mm: int
    depth_mm: int
    wall: Literal['north', 'south', 'east', 'west']
    members: list[str] = []


class RequirementSatisfaction(BaseModel):
    requested: str
    satisfied: bool
    selected_category: str | None = None
    product_name: str | None = None
    sku: str | None = None


class StyleEvidenceItem(BaseModel):
    sku: str
    score: float | None = None
    reason: str


class SpatialBreakdownItem(BaseModel):
    component: str
    score: float
    weight: float
    status: str = "pass"  # 'pass' | 'warning' | 'overlap'
    # 'overlap' = physical fixture envelopes actually intersect (triggers red in UI)
    # 'warning' = score is degraded but no physical collision
    # 'pass'    = component is healthy
    detail: str


class DesignScore(BaseModel):
    spatial_fit: float
    spatial_breakdown: list[SpatialBreakdownItem] = []
    budget_fit: float
    style_match: float | None = None
    style_match_status: str = "Measured"
    style_evidence: list[StyleEvidenceItem] = []
    compatibility: float | None = None
    compatibility_status: str = "Measured"
    accessibility: float | None = None
    accessibility_status: str = "Limited data available"
    sustainability: float | None = None
    sustainability_status: str = "Limited data available"
    total: float
    available_metrics: list[str] = []
    unavailable_metrics: list[str] = []
    score_method: str = "Active weight normalization"
    weights: dict[str, float] = {}
    normalized_weight_sum: float = 0.0
    weighted_contributions: dict[str, float] = {}


class Design(BaseModel):
    name: str
    fixtures: list[FixturePlacement]
    products: list[ProductRow]
    validation: ValidationResult
    score: DesignScore
    requirements_satisfaction: list[RequirementSatisfaction] = []
    room: RoomSpec | None = None
    wash_zone: WashZone | None = None


class GenerateRequest(BaseModel):
    requirements: RequirementSpec
    categories: list[str] = ['toilet', 'vanity', 'shower']
    accessibility: bool = False
    eco: bool = False


class ImproveRequest(BaseModel):
    metric: str
    current_design: Design
    budget_inr: int | None = 300000
    style: str | None = 'modern'


class ExplainRequest(BaseModel):
    products: list[ProductRow]
    validation: ValidationResult
    score: DesignScore
    budget_inr: int | None = None
    rejected: list[Design] = []


class SimulationRequest(BaseModel):
    before: GenerateRequest
    modified: GenerateRequest

class DesignComparison(BaseModel):
    design: str
    primary_reason: str
    headline: str
    details: list[str]

class CompareDesignsRequest(BaseModel):
    selected: Design
    alternatives: list[Design]
