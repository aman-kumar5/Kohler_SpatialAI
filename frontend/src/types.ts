// ── Product ──────────────────────────────────────────────────────────────────
export interface Product {
  sku: string;
  name: string;
  category: string;
  price_inr: number;
  width_mm: number | null;
  depth_mm: number | null;
  height_mm: number | null;
  installation_type?: string | null;
  finish?: string | null;
  collection?: string | null;
  features?: string | null;
  style: string | null;
  keywords: string | null;
  accessibility_rating: number | null;
  sustainability_rating: number | null;
}

// ── Room ─────────────────────────────────────────────────────────────────────
export interface Room {
  width_mm: number;
  depth_mm: number;
  door_wall: 'north' | 'south' | 'east' | 'west';
  door_offset_mm: number;
  door_width_mm: number;
}

// ── Fixture ──────────────────────────────────────────────────────────────────
export interface Fixture {
  sku: string;
  x_mm: number;
  y_mm: number;
  rotation_deg: 0 | 90 | 180 | 270;
}

// ── Validation ───────────────────────────────────────────────────────────────
export interface ValidationIssue {
  code: string;
  message: string;
  fixture_skus: string[];
}

export interface Validation {
  valid: boolean;
  issues: ValidationIssue[];
  total_price_inr: number;
}

export interface WashZone {
  id: string; x_mm: number; y_mm: number; width_mm: number; depth_mm: number;
  wall: 'north' | 'south' | 'east' | 'west'; members: string[];
}

// ── Requirement Satisfaction ──────────────────────────────────────────────────
export interface RequirementSatisfaction {
  requested: string;
  satisfied: boolean;
  selected_category: string | null;
  product_name: string | null;
  sku: string | null;
}

export interface SpatialBreakdownItem {
  component: string;
  score: number;
  weight: number;
  status: 'pass' | 'warning' | 'overlap';
  detail: string;
}

// ── Score ─────────────────────────────────────────────────────────────────────
export interface DesignScore {
  spatial_fit: number;
  spatial_breakdown?: SpatialBreakdownItem[];
  budget_fit: number;
  style_match: number | null;
  style_match_status?: string;
  compatibility: number | null;
  compatibility_status?: string;
  accessibility: number | null;
  accessibility_status?: string;
  sustainability: number | null;
  sustainability_status?: string;
  total: number;
  available_metrics?: string[];
  unavailable_metrics?: string[];
  score_method?: string;
  weights?: Record<string, number>;
  normalized_weight_sum?: number;
  weighted_contributions?: Record<string, number>;
}

// ── Design ───────────────────────────────────────────────────────────────────
export interface Design {
  name: string;
  fixtures: Fixture[];
  products: Product[];
  validation: Validation;
  score: DesignScore;
  requirements_satisfaction?: RequirementSatisfaction[];
  room?: Room | null;
  wash_zone?: WashZone | null;
  /** UI-only marker: never part of the permanent optimizer mode name. */
  aiOptimized?: boolean;
}

export type ImprovementMetric = 'style' | 'budget' | 'spatial_fit' | 'compatibility';
export interface PendingImprovement {
  proposal: Design;
  metric: ImprovementMetric;
  reason: string;
}

// ── API request shapes ────────────────────────────────────────────────────────
export interface RequirementSpec {
  room: Room | null;
  budget_inr: number | null;
  style: string | null;
  priority: string | null;
  requirements: string[];
  category_constraints?: Record<string, { max_price_inr: number }>;
}

export interface GenerateRequest {
  requirements: RequirementSpec;
  categories: string[];
  accessibility: boolean;
  eco: boolean;
}

export interface DesignComparison { design: string; primary_reason: string; headline: string; details: string[]; }
