import React from 'react';
import { useDesignStore } from '../../store';
import type { Product, Design } from '../../types';

interface Props {
  design: Design;
  onChangeProductClick: (sku: string, category: string) => void;
}

export default function FixtureInspector({ design, onChangeProductClick }: Props) {
  const {
    selectedFixtureSku,
    setSelectedFixture,
    rotateFixture,
    deleteProduct,
    isEditMode,
  } = useDesignStore();

  if (!selectedFixtureSku) return null;

  const fixture = design.fixtures.find((f) => f.sku === selectedFixtureSku);
  const product = design.products.find((p) => p.sku === selectedFixtureSku);

  if (!product || !fixture) return null;

  const issue = design.validation.issues.find((i) =>
    i.fixture_skus.includes(selectedFixtureSku)
  );

  const isRequiredElement = ['toilet', 'smart_toilet', 'vanity', 'shower'].includes(product.category);

  const handleDelete = () => {
    if (isRequiredElement) {
      const confirmDelete = window.confirm(
        `Warning: Removing this ${product.category} satisfies a required bathroom element. Remove product anyway?`
      );
      if (!confirmDelete) return;
    }
    deleteProduct(selectedFixtureSku);
  };

  return (
    <div className="fixture-inspector-card">
      <div className="inspector-top">
        <span className="inspector-eyebrow">SELECTED FIXTURE</span>
        <button className="btn-ghost btn-sm" onClick={() => setSelectedFixture(null)}>✕</button>
      </div>

      <h4 className="inspector-title">{product.name}</h4>
      <p className="inspector-sku">SKU: {product.sku}</p>

      <div className="inspector-grid">
        <div className="insp-item">
          <span className="insp-label">Price</span>
          <span className="insp-val price-val">₹{product.price_inr.toLocaleString('en-IN')}</span>
        </div>
        <div className="insp-item">
          <span className="insp-label">Category</span>
          <span className="insp-val">{product.category}</span>
        </div>
        <div className="insp-item">
          <span className="insp-label">Dimensions</span>
          <span className="insp-val">
            {product.width_mm || '—'} × {product.depth_mm || '—'} × {product.height_mm || '—'} mm
          </span>
        </div>
        <div className="insp-item">
          <span className="insp-label">Position</span>
          <span className="insp-val">X: {fixture.x_mm}mm · Y: {fixture.y_mm}mm</span>
        </div>
        <div className="insp-item">
          <span className="insp-label">Rotation</span>
          <span className="insp-val">{fixture.rotation_deg}°</span>
        </div>
        <div className="insp-item">
          <span className="insp-label">Validation</span>
          <span className={`insp-val ${issue ? 'val-fail' : 'val-pass'}`}>
            {issue ? `✕ ${issue.code}` : '✓ Valid'}
          </span>
        </div>
      </div>

      {isEditMode && (
        <div className="inspector-actions">
          <button
            className="btn-secondary btn-sm"
            onClick={() => onChangeProductClick(product.sku, product.category)}
          >
            Change Product
          </button>
          <button
            className="btn-ghost btn-sm"
            onClick={() => rotateFixture(product.sku)}
          >
            Rotate (90°)
          </button>
          <button
            className="btn-ghost btn-sm btn-danger"
            onClick={handleDelete}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
