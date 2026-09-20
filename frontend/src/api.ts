import type {
  Design, Validation, Fixture, Room, Product,
  GenerateRequest, RequirementSpec,
  DesignComparison,
} from './types';

const BASE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: body !== undefined ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => null);
    const detail = err?.detail ?? 'The server could not complete that request.';
    throw new Error(detail);
  }
  return r.json();
}

export const api = {
  products: () =>
    request<Product[]>('/products'),

  parseRequirements: (text: string) =>
    request<RequirementSpec>('/requirements/parse', { text }),

  searchProducts: (
    categories: string[],
    keywords: string[],
    style: string | null,
    budget_inr: number | null,
  ) =>
    request<Product[]>('/products/search', { categories, keywords, style, budget_inr }),

  generate: (body: GenerateRequest) =>
    request<Design[]>('/design/generate', body),

  validate: (room: Room, fixtures: Fixture[], budget: number) =>
    request<Validation>('/design/validate', { room, fixtures, budget_inr: budget }),

  evaluate: (room: Room, fixtures: Fixture[], budget: number | null, style: string | null, designName: string = 'User Edited') =>
    request<Design>('/design/evaluate', { room, fixtures, budget_inr: budget, style, design_name: designName }),

  improve: (metric: string, current_design: Design, budget_inr?: number | null, style?: string | null) =>
      request<{ improved_design: Design | null; no_improvement?: boolean; reason: string }>('/design/improve', { metric, current_design, budget_inr, style }),

  compare: (selected: Design, alternatives: Design[]) =>
    request<DesignComparison[]>('/design/compare', { selected, alternatives }),

  explain: (products: Product[], validation: Validation, score: Design['score'], budget_inr?: number, rejected?: Design[]) =>
    request<{ explanation: string }>('/design/explain', { products, validation, score, budget_inr, rejected }),

  simulate: (before: GenerateRequest, modified: GenerateRequest) =>
    request<{ before: Design[]; after: Design[]; trade_off: string }>(
      '/design/simulate',
      { before, modified },
    ),

  exportPdf: async (design: Design): Promise<void> => {
    const r = await fetch(BASE + '/design/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(design),
    });
    if (!r.ok) throw new Error('PDF export failed. Check the backend is running.');
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kohler-spatialai-design.pdf';
    a.click();
    URL.revokeObjectURL(url);
  },
};
