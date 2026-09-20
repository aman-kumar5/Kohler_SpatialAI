import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { useDesignStore } from '../../store';
import { api } from '../../api';
import FloorPlan2D from '../canvas/FloorPlan2D';
import Scene3D from '../canvas/Scene3D';
import AICopilot from './AICopilot';
import BudgetPanel from './BudgetPanel';
import EditorToolbar from './EditorToolbar';
import FixtureInspector from './FixtureInspector';
import ProductSelectorModal from './ProductSelectorModal';
import EditRequirementsModal from './EditRequirementsModal';
import type { GenerateRequest, Product } from '../../types';

const CHECKLIST = [
  { id: 'requirements', label: 'Requirements understood' },
  { id: 'catalog', label: 'Catalog filtered' },
  { id: 'layouts', label: 'Generating and validating feasible layouts' },
  { id: 'ranking', label: 'Ranking feasible designs' },
];

export default function Dashboard() {
  const {
    wizardData,
    designs,
    activeDesignIdx,
    isGenerating,
    generationError,
    isEditMode,
    setIsEditMode,
    saveVersion,
    setWizardData,
    setDesigns,
    setGenerating,
    setGenerationError,
    setActiveDesignIdx,
    resetWizard,
    changeProduct,
    addProduct,
    updateActiveDesign,
  } = useDesignStore();

  const [activeView, setActiveView] = useState<'2d' | '3d'>('2d');

  // Product Selector Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'change' | 'add'>('change');
  const [modalTargetSku, setModalTargetSku] = useState<string | undefined>(undefined);
  const [modalCategory, setModalCategory] = useState<string | undefined>(undefined);

  // Edit Requirements Modal state
  const [editReqOpen, setEditReqOpen] = useState(false);

  const generateMutation = useMutation({
    mutationFn: async () => {
      let parsedCatConstraints = wizardData.category_constraints || {};
      if (wizardData.nlText && wizardData.nlText.trim()) {
        try {
          const parsed = await api.parseRequirements(wizardData.nlText);
          if (parsed.category_constraints) {
            parsedCatConstraints = { ...parsedCatConstraints, ...parsed.category_constraints };
          }
        } catch {
          // Fallback to existing constraints
        }
      }
      const req: GenerateRequest = {
        requirements: {
          room: wizardData.room,
          budget_inr: wizardData.budget_inr,
          style: wizardData.style,
          priority: 'balanced',
          requirements: wizardData.categories,
          category_constraints: parsedCatConstraints,
        },
        categories: wizardData.categories,
        accessibility: wizardData.accessibility,
        eco: wizardData.eco,
      };
      return api.generate(req);
    },
    onSuccess: (data) => {
      setDesigns(data);
      setGenerating(false);
      setGenerationError(null);
    },
    onError: (e: Error) => {
      setGenerating(false);
      const msg = e.message || 'Unknown network error';
      setGenerationError(msg);
    },
  });

  // Auto-generate on initial mount if designs empty
  useEffect(() => {
    if (designs.length === 0 && !isGenerating) {
      setGenerating(true);
      setGenerationError(null);
      generateMutation.mutate();
    }
  }, []);

  const activeDesign = designs[activeDesignIdx];

  // Open modal to change product
  const handleOpenChangeModal = (sku: string, category: string) => {
    setModalMode('change');
    setModalTargetSku(sku);
    setModalCategory(category);
    setModalOpen(true);
  };

  // Open modal to add product
  const handleOpenAddModal = () => {
    setModalMode('add');
    setModalTargetSku(undefined);
    setModalCategory(undefined);
    setModalOpen(true);
  };

  // Product selection callback
  const handleSelectProduct = (newProduct: Product) => {
    if (modalMode === 'change' && modalTargetSku) {
      changeProduct(modalTargetSku, newProduct);
    } else if (modalMode === 'add') {
      addProduct(newProduct);
    }
  };

  // Editable room dimension handler
  const handleRoomDimensionChange = (field: 'width_mm' | 'depth_mm', valStr: string) => {
    const val = valStr === '' ? 0 : parseInt(valStr, 10);
    const updatedRoom = { ...wizardData.room, [field]: isNaN(val) ? 0 : val };
    setWizardData({ room: updatedRoom });

    if (activeDesign && updatedRoom.width_mm > 0 && updatedRoom.depth_mm > 0) {
      // Revalidate layout deterministically
      api.validate(updatedRoom, activeDesign.fixtures, wizardData.budget_inr).then((valRes) => {
        const updatedDesign = {
          ...activeDesign,
          validation: valRes,
        };
        updateActiveDesign(updatedDesign);
      });
    }
  };

  // ── Generating Screen ──────────────────────────────────────────────────────
  if (isGenerating || generateMutation.isPending) {
    return (
      <div className="generating-screen">
        <h2>Generating your designs…</h2>
        <div className="checklist">
          {CHECKLIST.map((item, i) => (
            <motion.div
              key={item.id}
              className={`checklist-item ${i < 2 ? 'done' : i === 2 ? 'active' : 'pending'}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.15 }}
            >
              <span className="check-icon">
                {i < 2 ? '✓' : i === 2 ? '⟳' : '○'}
              </span>
              {item.label}
            </motion.div>
          ))}
        </div>
      </div>
    );
  }

  // ── Error Screen ───────────────────────────────────────────────────────────
  if (generationError) {
    return (
      <div className="error-screen">
        <h2>Design generation failed</h2>
        <p className="error-details" style={{ whiteSpace: 'pre-line' }}>{generationError}</p>
        <p className="hint">
          Suggested fix: ensure the backend server is running and room dimensions/budget fit your selected categories.
        </p>
        <div className="error-actions">
          <button
            className="btn-primary"
            onClick={() => {
              setGenerating(true);
              generateMutation.mutate();
            }}
          >
            Try again
          </button>
          <button className="btn-ghost" onClick={resetWizard}>
            ← Change settings
          </button>
        </div>
      </div>
    );
  }

  if (!activeDesign) return null;

  // ── Main Dashboard ─────────────────────────────────────────────────────────
  return (
    <div className="dashboard-shell">
      {/* ── Top Bar ── */}
      <div className="dashboard-topbar">
        <div className="topbar-left">
          <div className="design-tabs">
            {designs.map((d, i) => (
              <button
                key={i}
                className={`design-tab ${i === activeDesignIdx ? 'active' : ''}`}
                onClick={() => setActiveDesignIdx(i)}
              >
                <span className="tab-name">{d.name}</span>
                <span className="tab-score">{d.score.total}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="topbar-right">
          <div className="view-toggle">
            <button
              className={activeView === '2d' ? 'active' : ''}
              onClick={() => setActiveView('2d')}
            >
              2D
            </button>
            <button
              className={activeView === '3d' ? 'active' : ''}
              onClick={() => setActiveView('3d')}
            >
              3D
            </button>
          </div>

          <button
            className="btn-ghost btn-sm"
            onClick={() => setEditReqOpen(true)}
          >
            ⚙ Edit Requirements
          </button>
          <button
            className={`btn-sm ${isEditMode ? 'btn-secondary' : 'btn-ghost'}`}
            onClick={() => setIsEditMode(!isEditMode)}
          >
            {isEditMode ? '✓ Exit Edit Mode' : '✏ Edit Layout'}
          </button>
          <button className="btn-ghost btn-sm" onClick={saveVersion}>
            💾 Save Version
          </button>
          <button
            className="btn-secondary btn-sm"
            onClick={() => api.exportPdf({ ...activeDesign, room: wizardData.room })}
          >
            📄 Export PDF
          </button>
        </div>
      </div>

      {/* ── Editor Toolbar (in Edit Mode) ── */}
      <EditorToolbar
        onAddProductClick={handleOpenAddModal}
        onChangeProductClick={handleOpenChangeModal}
      />

      {/* ── 3-Column Body ── */}
      <div className="dashboard-body">
        {/* Col 1: Left Panel — Budget & Products */}
        <aside className="col-controls">
          <BudgetPanel
            design={activeDesign}
            allDesigns={designs}
            onChangeProductClick={handleOpenChangeModal}
            onAddProductClick={handleOpenAddModal}
          />
        </aside>

        {/* Col 2: Center Panel — Canvas & Status */}
        <main className="col-canvas-wrap">
          {/* Status Header with Score Breakdown */}
          <div className="canvas-status-header">
            <div className="status-title-row">
              <span className={`status-badge ${activeDesign.validation.valid ? 'pass' : 'fail'}`}>
                {activeDesign.validation.valid ? '✓ DESIGN FEASIBLE' : '✕ VALIDATION WARNING'}
              </span>
              <span className="status-score">DESIGN SCORE: {activeDesign.score.total}/100</span>
            </div>
            <div className="score-breakdown-bars">
              {[
                { label: 'Spatial Fit', value: activeDesign.score.spatial_fit, status: 'Measured' },
                { label: 'Budget Fit', value: activeDesign.score.budget_fit, status: 'Measured' },
                { label: 'Style Match', value: activeDesign.score.style_match, status: activeDesign.score.style_match_status || 'Limited data available' },
                { label: 'Compatibility', value: activeDesign.score.compatibility, status: activeDesign.score.compatibility_status || 'Limited data available' },
                { label: 'Accessibility', value: activeDesign.score.accessibility, status: activeDesign.score.accessibility_status || 'Limited data available' },
                { label: 'Sustainability', value: activeDesign.score.sustainability, status: activeDesign.score.sustainability_status || 'Limited data available' },
              ].map(m => (
                <div key={m.label} className="score-bar-item">
                  <span className="score-bar-label">{m.label}</span>
                  <div className="score-bar-track">
                    <div
                      className="score-bar-fill"
                      style={{ width: m.value != null ? `${m.value}%` : '0%', opacity: m.value != null ? 1 : 0.2 }}
                    />
                  </div>
                  <span className="score-bar-value">
                    {m.value != null ? `${m.value}` : 'Limited'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Editable Room Dimensions Bar (in Edit Mode) */}
          {isEditMode && (
            <div className="editable-room-bar">
              <span className="bar-label">ROOM SIZE:</span>
              <label>
                W:
                <input
                  type="number"
                  min={800}
                  max={5000}
                  step={50}
                  value={wizardData.room.width_mm === 0 ? '' : wizardData.room.width_mm}
                  onChange={(e) => handleRoomDimensionChange('width_mm', e.target.value)}
                />
                mm
              </label>
              <label>
                D:
                <input
                  type="number"
                  min={800}
                  max={5000}
                  step={50}
                  value={wizardData.room.depth_mm === 0 ? '' : wizardData.room.depth_mm}
                  onChange={(e) => handleRoomDimensionChange('depth_mm', e.target.value)}
                />
                mm
              </label>
            </div>
          )}

          {/* Canvas Component */}
          <div className="canvas-container">
            <AnimatePresence mode="wait">
              {activeView === '2d' ? (
                <motion.div
                  key="2d"
                  style={{ width: '100%', height: '100%' }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <FloorPlan2D
                    design={activeDesign}
                    room={wizardData.room}
                    budget={wizardData.budget_inr}
                  />
                </motion.div>
              ) : (
                <motion.div
                  key="3d"
                  style={{ width: '100%', height: '100%' }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Scene3D design={activeDesign} room={wizardData.room} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Fixture Inspector */}
          <FixtureInspector
            design={activeDesign}
            onChangeProductClick={handleOpenChangeModal}
          />
        </main>

        {/* Col 3: Right Panel — AI Copilot */}
        <aside className="col-copilot">
          <AICopilot design={activeDesign} allDesigns={designs} />
        </aside>
      </div>

      {/* Product Selector Modal */}
      <ProductSelectorModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSelectProduct={handleSelectProduct}
        targetCategory={modalCategory}
        title={
          modalMode === 'change'
            ? `Change ${modalCategory ? modalCategory.replace('_', ' ') : 'Product'}`
            : 'Add Product to Design'
        }
      />

      {/* Edit Requirements Modal */}
      <EditRequirementsModal
        isOpen={editReqOpen}
        onClose={() => setEditReqOpen(false)}
      />
    </div>
  );
}
