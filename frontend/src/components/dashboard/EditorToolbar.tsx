import React, { useEffect } from 'react';
import { useDesignStore } from '../../store';

interface Props {
  onAddProductClick: () => void;
  onChangeProductClick: (sku: string, category: string) => void;
}

export default function EditorToolbar({
  onAddProductClick,
  onChangeProductClick,
}: Props) {
  const {
    isEditMode,
    setIsEditMode,
    undo,
    redo,
    historyIdx,
    history,
    selectedFixtureSku,
    rotateFixture,
    deleteProduct,
    saveVersion,
    designs,
    activeDesignIdx,
  } = useDesignStore();

  const activeDesign = designs[activeDesignIdx];
  const selectedProduct = activeDesign?.products.find(
    (p) => p.sku === selectedFixtureSku
  );

  // Keyboard shortcut listener
  useEffect(() => {
    if (!isEditMode) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept typing in input or textarea
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        undo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        redo();
      } else if (e.key.toLowerCase() === 'r' && selectedFixtureSku) {
        e.preventDefault();
        rotateFixture(selectedFixtureSku);
      } else if (
        (e.key === 'Delete' || e.key === 'Backspace') &&
        selectedFixtureSku
      ) {
        e.preventDefault();
        deleteProduct(selectedFixtureSku);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isEditMode, selectedFixtureSku, undo, redo, rotateFixture, deleteProduct]);

  if (!isEditMode) return null;

  const canUndo = historyIdx > 0;
  const canRedo = historyIdx < history.length - 1;

  return (
    <div className="editor-toolbar-bar">
      <div className="toolbar-left">
        <span className="toolbar-badge">✏ EDIT MODE</span>
        <button
          className="btn-ghost btn-sm"
          onClick={undo}
          disabled={!canUndo}
          title="Undo (Ctrl+Z)"
        >
          ↩ Undo
        </button>
        <button
          className="btn-ghost btn-sm"
          onClick={redo}
          disabled={!canRedo}
          title="Redo (Ctrl+Y)"
        >
          ↪ Redo
        </button>
        <div className="toolbar-divider" />
        <button className="btn-primary btn-sm" onClick={onAddProductClick}>
          + Add Product
        </button>
        {selectedProduct && (
          <>
            <button
              className="btn-secondary btn-sm"
              onClick={() =>
                onChangeProductClick(selectedProduct.sku, selectedProduct.category)
              }
            >
              Change Product
            </button>
            <button
              className="btn-ghost btn-sm"
              onClick={() => rotateFixture(selectedProduct.sku)}
              title="Rotate (Key: R)"
            >
              Rotate 90°
            </button>
            <button
              className="btn-ghost btn-sm btn-danger"
              onClick={() => deleteProduct(selectedProduct.sku)}
              title="Delete (Key: Del)"
            >
              Delete
            </button>
          </>
        )}
      </div>

      <div className="toolbar-right">
        <button
          className="btn-ghost btn-sm"
          onClick={saveVersion}
          title="Save current state as new version"
        >
          💾 Save as Version
        </button>
        <button
          className="btn-secondary btn-sm"
          onClick={() => setIsEditMode(false)}
        >
          ✓ Done Editing
        </button>
      </div>
    </div>
  );
}
