import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { useDesignStore } from '../../store';
import type { Product } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSelectProduct: (product: Product) => void;
  targetCategory?: string;
  title?: string;
}

export default function ProductSelectorModal({
  isOpen,
  onClose,
  onSelectProduct,
  targetCategory,
  title = 'Select KOHLER Product',
}: Props) {
  const { wizardData } = useDesignStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCat, setSelectedCat] = useState<string>(targetCategory || 'all');
  const [priceMax, setPriceMax] = useState<number>(600000);

  useEffect(() => {
    if (targetCategory) {
      setSelectedCat(targetCategory);
    } else {
      setSelectedCat('all');
    }
  }, [targetCategory, isOpen]);

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: api.products,
    enabled: isOpen,
  });

  const categories = useMemo(() => {
    const set = new Set(products.map((p) => p.category));
    return Array.from(set).sort();
  }, [products]);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      // Category filter
      if (selectedCat !== 'all' && p.category !== selectedCat) return false;
      // Price filter
      if (p.price_inr > priceMax) return false;
      // Search text query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = p.name.toLowerCase().includes(q);
        const matchSku = p.sku.toLowerCase().includes(q);
        const matchCat = p.category.toLowerCase().includes(q);
        const matchColl = (p.collection || '').toLowerCase().includes(q);
        const matchFeat = (p.features || '').toLowerCase().includes(q);
        if (!matchName && !matchSku && !matchCat && !matchColl && !matchFeat) return false;
      }
      return true;
    });
  }, [products, selectedCat, searchQuery, priceMax]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="modal-backdrop" onClick={onClose}>
        <motion.div
          className="modal-card"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
        >
          <div className="modal-header">
            <h3>{title}</h3>
            <button className="btn-ghost btn-sm" onClick={onClose}>✕</button>
          </div>

          {/* Filter Bar */}
          <div className="modal-filters">
            <input
              type="text"
              placeholder="Search KOHLER catalog by SKU, name, collection..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
              autoFocus
            />

            <div className="filter-row">
              <label className="filter-label">
                Category:
                <select
                  value={selectedCat}
                  onChange={(e) => setSelectedCat(e.target.value)}
                >
                  <option value="all">All Categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c.charAt(0).toUpperCase() + c.slice(1).replace('_', ' ')}
                    </option>
                  ))}
                </select>
              </label>

              <label className="filter-label">
                Max Price: ₹{priceMax.toLocaleString('en-IN')}
                <input
                  type="range"
                  min={5000}
                  max={600000}
                  step={10000}
                  value={priceMax}
                  onChange={(e) => setPriceMax(Number(e.target.value))}
                />
              </label>
            </div>
          </div>

          {/* Product List Grid */}
          <div className="modal-product-grid">
            {isLoading ? (
              <p className="modal-loading">Loading KOHLER product catalog…</p>
            ) : filteredProducts.length === 0 ? (
              <div className="modal-empty">
                <p>No products found matching your filters.</p>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => {
                    setSearchQuery('');
                    setSelectedCat('all');
                    setPriceMax(600000);
                  }}
                >
                  Reset Filters
                </button>
              </div>
            ) : (
              filteredProducts.map((p) => {
                const catMax = wizardData.category_constraints?.[p.category]?.max_price_inr;
                const isExceeded = catMax !== undefined && p.price_inr > catMax;
                return (
                  <div key={p.sku} className={`modal-product-card ${isExceeded ? 'disabled-card' : ''}`}>
                    <div className="card-top">
                      <span className="card-cat">{p.category.replace('_', ' ')}</span>
                      <span className="card-price">₹{p.price_inr.toLocaleString('en-IN')}</span>
                    </div>
                    <h4 className="card-name">{p.name}</h4>
                    <span className="card-sku">SKU: {p.sku}</span>
                    <div className="card-dims">
                      <span>
                        {p.width_mm || '—'} × {p.depth_mm || '—'} × {p.height_mm || '—'} mm
                      </span>
                      {p.installation_type && (
                        <span className="card-tag">{p.installation_type}</span>
                      )}
                    </div>
                    {p.collection && (
                      <p className="card-collection">Collection: {p.collection}</p>
                    )}
                    {isExceeded ? (
                      <div className="exceeded-badge" style={{ marginTop: '8px', fontSize: '11px', color: '#A5453A', fontWeight: 600 }}>
                        ✕ Exceeds {p.category} price limit of ₹{catMax?.toLocaleString('en-IN')}
                      </div>
                    ) : (
                      <button
                        className="btn-primary btn-sm btn-select-prod"
                        onClick={() => {
                          onSelectProduct(p);
                          onClose();
                        }}
                      >
                        Select Product →
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
