import React, { useState } from 'react';
import { useDesignStore } from '../../store';
import { api } from '../../api';
import type { Design } from '../../types';

interface Props {
  design: Design;
  allDesigns: Design[];
  onChangeProductClick?: (sku: string, category: string) => void;
  onAddProductClick?: () => void;
}

function getClassification(score: number): { label: string; cls: string } {
  if (score >= 90) return { label: 'EXCELLENT', cls: 'score-excellent' };
  if (score >= 80) return { label: 'STRONG', cls: 'score-strong' };
  if (score >= 70) return { label: 'GOOD', cls: 'score-good' };
  if (score >= 60) return { label: 'FAIR', cls: 'score-fair' };
  return { label: 'NEEDS IMPROVEMENT', cls: 'score-needs-imp' };
}

function ProductThumbnailSvg({ category }: { category: string }) {
  if (category === 'toilet') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6D665B" strokeWidth="1.5">
        <rect x="6" y="3" width="12" height="7" rx="1.5" fill="#FAF9F6" />
        <path d="M7 10c0 4.4 2.2 8 5 8s5-3.6 5-8" fill="#FAF9F6" />
      </svg>
    );
  }
  if (category === 'vanity') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6D665B" strokeWidth="1.5">
        <rect x="3" y="6" width="18" height="12" rx="1" fill="#FAF9F6" />
        <path d="M3 10h18" />
        <circle cx="12" cy="8" r="1.5" />
      </svg>
    );
  }
  if (category === 'shower') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4F807A" strokeWidth="1.5">
        <rect x="4" y="3" width="16" height="18" rx="1" fill="#F4F8F8" />
        <path d="M12 3v10M9 13l3 3 3-3" />
      </svg>
    );
  }
  if (category === 'basin') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6D665B" strokeWidth="1.5">
        <ellipse cx="12" cy="12" rx="8" ry="5" fill="#FAF9F6" />
        <circle cx="12" cy="12" r="1.5" />
      </svg>
    );
  }
  if (category === 'faucet') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#B08D57" strokeWidth="1.5">
        <path d="M8 20v-8c0-3.3 2.7-6 6-6h2" />
        <path d="M16 6v3" />
      </svg>
    );
  }
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6D665B" strokeWidth="1.5">
      <rect x="5" y="5" width="14" height="14" rx="2" />
    </svg>
  );
}

export default function BudgetPanel({
  design,
  allDesigns,
  onChangeProductClick,
  onAddProductClick,
}: Props) {
  const { wizardData, isEditMode, deleteProduct } = useDesignStore();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const total = design.validation.total_price_inr;
  const remBudget = wizardData.budget_inr - total;
  const budgetUsedPct = wizardData.budget_inr > 0 ? Math.min(100, (total / wizardData.budget_inr) * 100) : 0;

  const roomW = ((design.room?.width_mm ?? wizardData.room.width_mm) / 1000).toFixed(1);
  const roomD = ((design.room?.depth_mm ?? wizardData.room.depth_mm) / 1000).toFixed(1);
  const styleName = wizardData.style ? (wizardData.style.charAt(0).toUpperCase() + wizardData.style.slice(1)) : 'Modern';

  const classification = getClassification(design.score.total);

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      await api.exportPdf({ ...design, room: design.room || wizardData.room });
    } catch (e: any) {
      setExportError(
        'PDF export failed. Make sure the backend is running. ' + (e?.message ?? ''),
      );
    } finally {
      setExporting(false);
    }
  };

  const scorePct = Math.min(100, Math.max(0, design.score.total));
  const strokeDashoffset = 283 - (283 * scorePct) / 100;

  return (
    <div className="budget-panel-shell">
      {/* 1. DESIGN OVERVIEW */}
      <div className="overview-card">
        <span className="overview-eyebrow">DESIGN OVERVIEW</span>
        <h3 className="overview-title">{styleName} Bathroom</h3>
        <p className="overview-dims">{roomW} m × {roomD} m</p>
      </div>

      {/* 2. TOTAL INVESTMENT */}
      <div className="investment-card">
        <span className="section-eyebrow">TOTAL INVESTMENT</span>
        <div className="total-price-hero">₹{total.toLocaleString('en-IN')}</div>
        <div className="stat-split-row">
          <div>
            <span className="stat-lbl">Budget</span>
            <strong className="stat-val">₹{wizardData.budget_inr.toLocaleString('en-IN')}</strong>
          </div>
          <div>
            <span className="stat-lbl">Remaining</span>
            <strong className={`stat-val ${remBudget < 0 ? 'text-danger' : 'text-success'}`}>
              ₹{remBudget.toLocaleString('en-IN')}
            </strong>
          </div>
        </div>
      </div>

      {/* 3. BUDGET UTILIZATION */}
      <div className="utilization-card">
        <span className="section-eyebrow">BUDGET UTILIZATION</span>
        <div className="pct-hero">{budgetUsedPct.toFixed(1)}%</div>
        <div className="bar-track">
          <div className="bar-fill-gold" style={{ width: `${budgetUsedPct}%` }} />
        </div>
      </div>

      {/* 4. DESIGN SCORE */}
      <div className="score-hero-card">
        <span className="section-eyebrow">DESIGN SCORE</span>
        <div className="score-ring-container">
          <svg className="score-ring-svg" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" className="score-ring-bg" />
            <circle
              cx="50"
              cy="50"
              r="45"
              className="score-ring-val"
              style={{ strokeDashoffset }}
            />
          </svg>
          <div className="score-ring-center">
            <span className="score-big">{design.score.total}</span>
            <span className="score-denom">/ 100</span>
          </div>
        </div>
        <div className="score-badge-wrap">
          <span className={`score-badge ${classification.cls}`}>{classification.label}</span>
        </div>
      </div>

      {/* 5. PRODUCT MIX */}
      <div className="mix-card">
        <div className="mix-head">
          <span className="section-eyebrow">PRODUCT MIX ({design.products.length} products)</span>
        </div>
        <div className="mix-thumbnails" aria-label="Selected product categories">
          {design.products.map((product) => {
            const imgUrl = (product as any).image_url;
            return (
              <div className={`mix-thumbnail mix-${product.category}`} key={product.sku} title={`${product.category}: ${product.name}`}>
                {imgUrl ? (
                  <img src={imgUrl} alt={product.name} className="mix-img" />
                ) : (
                  <ProductThumbnailSvg category={product.category} />
                )}
                <small>{product.category}</small>
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. SELECTED PRODUCTS */}
      <div className="products-section">
        <div className="products-head">
          <h4>SELECTED PRODUCTS</h4>
          {onAddProductClick && (
            <button className="btn-ghost btn-xs" onClick={onAddProductClick}>
              + Add
            </button>
          )}
        </div>

        <div className="product-cards-stack">
          {design.products.map((p) => (
            <div key={p.sku} className="product-card-redesign">
              <div className="card-top-row">
                <span className="card-cat-badge">{p.category.replace('_', ' ').toUpperCase()}</span>
                <span className="card-price-text">₹{p.price_inr.toLocaleString('en-IN')}</span>
              </div>
              <h5 className="card-title-text">{p.name}</h5>
              <div className="card-bottom-row">
                <span className="card-sku-muted">{p.sku}</span>
                <div className="card-actions-group">
                  {onChangeProductClick && (
                    <button
                      className="btn-ghost btn-xs"
                      onClick={() => onChangeProductClick(p.sku, p.category)}
                    >
                      Change
                    </button>
                  )}
                  {isEditMode && (
                    <button
                      className="btn-ghost btn-xs text-danger"
                      onClick={() => deleteProduct(p.sku)}
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 7. DEDICATED EXPORT PDF CTA */}
      <div className="pdf-export-card">
        <span className="pdf-eyebrow">READY TO SHARE?</span>
        <p className="pdf-desc">Create a professional bathroom proposal with products, pricing and floor plan.</p>
        <button className="btn-gold-cta" onClick={handleExport} disabled={exporting}>
          {exporting ? 'Generating Report…' : '↓ Export PDF Report'}
        </button>
        {exportError && <p className="error-text">{exportError}</p>}
      </div>
    </div>
  );
}
