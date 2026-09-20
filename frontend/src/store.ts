import { create } from 'zustand';
import type { Design, Room, Fixture, Product, PendingImprovement, ImprovementMetric } from './types';
import { api } from './api';

export interface WizardData {
  room: Room;
  style: string;
  budget_inr: number;
  categories: string[];
  nlText: string;
  imageUrl: string | null;
  accessibility: boolean;
  eco: boolean;
  category_constraints?: Record<string, { max_price_inr: number }>;
}

export interface DesignState {
  // Wizard
  wizardStep: number;
  wizardDone: boolean;
  wizardData: WizardData;

  // Generated & edited designs
  designs: Design[];
  activeDesignIdx: number;
  isGenerating: boolean;
  generationError: string | null;

  // Edit Mode & History
  isEditMode: boolean;
  history: Design[];
  historyIdx: number;
  versions: Design[];
  pendingImprovement: PendingImprovement | null;

  // Selected fixture (for 2D/3D & Inspector)
  selectedFixtureSku: string | null;

  // Actions
  setWizardStep: (step: number) => void;
  setWizardData: (data: Partial<WizardData>) => void;
  completeWizard: () => void;
  resetWizard: () => void;
  setDesigns: (designs: Design[]) => void;
  setActiveDesignIdx: (idx: number) => void;
  setGenerating: (v: boolean) => void;
  setGenerationError: (msg: string | null) => void;
  setSelectedFixture: (sku: string | null) => void;
  setIsEditMode: (v: boolean) => void;

  // Editor Actions
  evaluateAndUpdateDesign: (fixtures: Fixture[], extraProducts?: Product[]) => Promise<void>;
  updateFixturePlacement: (sku: string, x_mm: number, y_mm: number, rotation_deg?: 0 | 90 | 180 | 270) => void;
  rotateFixture: (sku: string) => void;
  changeProduct: (oldSku: string, newProduct: Product) => void;
  addProduct: (product: Product) => void;
  deleteProduct: (sku: string) => void;
  updateActiveDesign: (d: Design) => void;
  saveVersion: () => void;
  undo: () => void;
  redo: () => void;
  setPendingImprovement: (proposal: Design | null, metric?: ImprovementMetric, reason?: string) => void;
  acceptPendingImprovement: () => Promise<void>;
  rejectPendingImprovement: () => void;
}

const DEFAULT_WIZARD: WizardData = {
  room: {
    width_mm: 1800,
    depth_mm: 2400,
    door_wall: 'south',
    door_offset_mm: 1000,
    door_width_mm: 700,
  },
  style: 'modern',
  budget_inr: 300000,
  categories: ['toilet', 'vanity', 'shower'],
  nlText: '',
  imageUrl: null,
  accessibility: false,
  eco: false,
  category_constraints: {},
};

export const useDesignStore = create<DesignState>((set, get) => ({
  wizardStep: 0,
  wizardDone: false,
  wizardData: { ...DEFAULT_WIZARD },
  designs: [],
  activeDesignIdx: 0,
  isGenerating: false,
  generationError: null,
  selectedFixtureSku: null,

  isEditMode: false,
  history: [],
  historyIdx: -1,
  versions: [],
  pendingImprovement: null,

  setWizardStep: (step) => set({ wizardStep: step }),

  setWizardData: (data) =>
    set((s) => ({ wizardData: { ...s.wizardData, ...data } })),

  completeWizard: () => set({ wizardDone: true }),

  resetWizard: () =>
    set({
      wizardStep: 0,
      wizardDone: false,
      wizardData: { ...DEFAULT_WIZARD },
      designs: [],
      activeDesignIdx: 0,
      isGenerating: false,
      generationError: null,
      isEditMode: false,
      history: [],
      historyIdx: -1,
      selectedFixtureSku: null,
      versions: [],
      pendingImprovement: null,
    }),

  setDesigns: (designs) => {
    const first = designs[0];
    set({
      designs,
      activeDesignIdx: 0,
      history: first ? [first] : [],
      historyIdx: first ? 0 : -1,
      versions: first ? [first] : [],
      pendingImprovement: null,
    });
  },

  setActiveDesignIdx: (idx) => {
    const target = get().designs[idx];
    set({
      activeDesignIdx: idx,
      history: target ? [target] : [],
      historyIdx: target ? 0 : -1,
      selectedFixtureSku: null,
    });
  },

  setGenerating: (v) => set({ isGenerating: v }),

  setGenerationError: (msg) => set({ generationError: msg }),

  setSelectedFixture: (sku) => set({ selectedFixtureSku: sku }),

  setIsEditMode: (v) => set({ isEditMode: v }),

  updateActiveDesign: (newDesign: Design) => {
    const state = get();
    const currentHist = state.history.slice(0, state.historyIdx + 1);
    const updatedHist = [...currentHist, newDesign];

    set({
      history: updatedHist,
      historyIdx: updatedHist.length - 1,
      designs: state.designs.map((d, i) =>
        i === state.activeDesignIdx ? newDesign : d
      ),
    });
  },

  evaluateAndUpdateDesign: async (fixtures: Fixture[], extraProducts?: Product[]) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;
    const room = active.room || state.wizardData.room;
    const budget = state.wizardData.budget_inr;
    const style = state.wizardData.style;

    try {
      const evaluated = await api.evaluate(room, fixtures, budget, style, active.name);
      const fullDesign: Design = {
        ...evaluated,
        room: room,
      };
      get().updateActiveDesign(fullDesign);
    } catch {
      const updatedProducts = extraProducts || active.products;
      const newTotal = updatedProducts.reduce((sum, p) => sum + p.price_inr, 0);
      const updatedDesign: Design = {
        ...active,
        fixtures,
        products: updatedProducts,
        validation: {
          ...active.validation,
          total_price_inr: newTotal,
        },
      };
      get().updateActiveDesign(updatedDesign);
    }
  },

  updateFixturePlacement: (sku, x_mm, y_mm, rotation_deg) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    const targetProd = active.products.find((p) => p.sku === sku);
    const isWashStation = targetProd && ['vanity', 'basin', 'faucet'].includes(targetProd.category);

    const washStationSkus = isWashStation
      ? active.products.filter((p) => ['vanity', 'basin', 'faucet'].includes(p.category)).map((p) => p.sku)
      : [sku];

    const updatedFixtures = active.fixtures.map((f) =>
      washStationSkus.includes(f.sku)
        ? { ...f, x_mm, y_mm, rotation_deg: rotation_deg !== undefined ? (rotation_deg as 0 | 90 | 180 | 270) : f.rotation_deg }
        : f
    );

    get().evaluateAndUpdateDesign(updatedFixtures);
  },


  rotateFixture: (sku) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    const updatedFixtures = active.fixtures.map((f) => {
      if (f.sku !== sku) return f;
      const nextRot = ((f.rotation_deg + 90) % 360) as 0 | 90 | 180 | 270;
      return { ...f, rotation_deg: nextRot };
    });

    get().evaluateAndUpdateDesign(updatedFixtures);
  },

  changeProduct: (oldSku, newProduct) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    const updatedProducts = active.products.map((p) =>
      p.sku === oldSku ? newProduct : p
    );

    const updatedFixtures = active.fixtures.map((f) =>
      f.sku === oldSku ? { ...f, sku: newProduct.sku } : f
    );

    get().evaluateAndUpdateDesign(updatedFixtures, updatedProducts);
    set({ selectedFixtureSku: newProduct.sku });
  },

  addProduct: (product) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    if (active.products.some((p) => p.sku === product.sku)) return;

    const updatedProducts = [...active.products, product];
    const newFixture: Fixture = {
      sku: product.sku,
      x_mm: 100,
      y_mm: 100,
      rotation_deg: 0,
    };

    const updatedFixtures = [...active.fixtures, newFixture];
    get().evaluateAndUpdateDesign(updatedFixtures, updatedProducts);
    set({ selectedFixtureSku: product.sku });
  },

  deleteProduct: (sku) => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    const updatedProducts = active.products.filter((p) => p.sku !== sku);
    const updatedFixtures = active.fixtures.filter((f) => f.sku !== sku);

    get().evaluateAndUpdateDesign(updatedFixtures, updatedProducts);
    set({ selectedFixtureSku: null });
  },

  saveVersion: () => {
    const state = get();
    const active = state.designs[state.activeDesignIdx];
    if (!active) return;

    // Version labels are metadata; optimizer mode names must never be rewritten.
    set({ versions: [...state.versions, active] });
  },

  undo: () => {
    const state = get();
    if (state.historyIdx <= 0) return;
    const prevIdx = state.historyIdx - 1;
    const prevDesign = state.history[prevIdx];
    set({
      historyIdx: prevIdx,
      designs: state.designs.map((d, i) =>
        i === state.activeDesignIdx ? prevDesign : d
      ),
    });
  },

  redo: () => {
    const state = get();
    if (state.historyIdx >= state.history.length - 1) return;
    const nextIdx = state.historyIdx + 1;
    const nextDesign = state.history[nextIdx];
    set({
      historyIdx: nextIdx,
      designs: state.designs.map((d, i) =>
        i === state.activeDesignIdx ? nextDesign : d
      ),
    });
  },

  setPendingImprovement: (proposal, metric, reason) =>
    set({ pendingImprovement: proposal && metric ? { proposal, metric, reason: reason || '' } : null }),

  acceptPendingImprovement: async () => {
    const state = get();
    const pending = state.pendingImprovement;
    const current = state.designs[state.activeDesignIdx];
    if (!pending || !current) return;
    const room = current.room || state.wizardData.room;
    // Re-evaluate at commit time. A failed or over-budget proposal can never replace current design.
    const verified = await api.evaluate(room, pending.proposal.fixtures, state.wizardData.budget_inr, state.wizardData.style, current.name);
    if (!verified.validation.valid || verified.validation.total_price_inr > state.wizardData.budget_inr) {
      throw new Error('The proposal no longer meets spatial or budget constraints and was not applied.');
    }
    get().updateActiveDesign({ ...verified, name: current.name, aiOptimized: true, room });
    set((s) => ({ versions: [...s.versions, { ...verified, name: current.name, aiOptimized: true, room }], pendingImprovement: null }));
  },

  rejectPendingImprovement: () => set({ pendingImprovement: null }),
}));
