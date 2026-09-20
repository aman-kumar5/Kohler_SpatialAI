import React, { useState, useEffect } from 'react';
import { useDesignStore } from '../../store';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api';
import type { GenerateRequest, Room } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const CATEGORY_OPTIONS = [
  { id: 'toilet', label: 'Toilet' },
  { id: 'smart_toilet', label: 'Smart Toilet' },
  { id: 'vanity', label: 'Vanity Cabinet' },
  { id: 'basin', label: 'Basin / Sink' },
  { id: 'faucet', label: 'Faucet / Tap' },
  { id: 'shower', label: 'Shower' },
];

const STYLE_OPTIONS = [
  { id: 'modern', label: 'Modern / Contemporary' },
  { id: 'classical', label: 'Classical / Traditional' },
  { id: 'industrial', label: 'Industrial' },
  { id: 'scandinavian', label: 'Scandinavian' },
];

export default function EditRequirementsModal({ isOpen, onClose }: Props) {
  const { wizardData, setWizardData, setDesigns, setGenerating, setGenerationError } = useDesignStore();

  const [room, setRoom] = useState<Room>(wizardData.room);
  const [style, setStyle] = useState<string>(wizardData.style);
  const [budget, setBudget] = useState<number>(wizardData.budget_inr);
  const [categories, setCategories] = useState<string[]>(wizardData.categories);
  const [nlText, setNlText] = useState<string>(wizardData.nlText);

  useEffect(() => {
    if (isOpen) {
      setRoom(wizardData.room);
      setStyle(wizardData.style);
      setBudget(wizardData.budget_inr);
      setCategories(wizardData.categories);
      setNlText(wizardData.nlText);
    }
  }, [isOpen, wizardData]);

  const generateMutation = useMutation({
    mutationFn: async (updatedWizard: typeof wizardData) => {
      let parsedCatConstraints = updatedWizard.category_constraints || {};
      if (updatedWizard.nlText && updatedWizard.nlText.trim()) {
        try {
          const parsed = await api.parseRequirements(updatedWizard.nlText);
          if (parsed.category_constraints) {
            parsedCatConstraints = { ...parsedCatConstraints, ...parsed.category_constraints };
          }
        } catch {
          // Fallback to existing
        }
      }
      const req: GenerateRequest = {
        requirements: {
          room: updatedWizard.room,
          budget_inr: updatedWizard.budget_inr,
          style: updatedWizard.style,
          priority: 'balanced',
          requirements: updatedWizard.categories,
          category_constraints: parsedCatConstraints,
        },
        categories: updatedWizard.categories,
        accessibility: updatedWizard.accessibility,
        eco: updatedWizard.eco,
      };
      return api.generate(req);
    },
    onSuccess: (data) => {
      setDesigns(data);
      setGenerating(false);
      setGenerationError(null);
      onClose();
    },
    onError: (err: Error) => {
      setGenerating(false);
      setGenerationError(err.message);
      onClose();
    },
  });

  if (!isOpen) return null;

  const toggleCategory = (catId: string) => {
    setCategories(prev =>
      prev.includes(catId) ? prev.filter(c => c !== catId) : [...prev, catId]
    );
  };

  const handleApply = () => {
    const updated = {
      ...wizardData,
      room,
      style,
      budget_inr: budget,
      categories,
      nlText,
    };
    setWizardData(updated);
    setGenerating(true);
    generateMutation.mutate(updated);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card edit-req-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>EDIT DESIGN REQUIREMENTS</h3>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body edit-req-body">
          {/* Space & Room section */}
          <section className="edit-req-section">
            <h4>SPACE & ROOM DIMENSIONS</h4>
            <div className="field-grid">
              <label>
                Room Width (mm)
                <input
                  type="number"
                  min={800}
                  max={5000}
                  step={50}
                  value={room.width_mm}
                  onChange={e => setRoom({ ...room, width_mm: parseInt(e.target.value, 10) || 0 })}
                />
              </label>
              <label>
                Room Depth (mm)
                <input
                  type="number"
                  min={800}
                  max={5000}
                  step={50}
                  value={room.depth_mm}
                  onChange={e => setRoom({ ...room, depth_mm: parseInt(e.target.value, 10) || 0 })}
                />
              </label>
            </div>
          </section>

          {/* Door Specs */}
          <section className="edit-req-section">
            <h4>DOOR POSITION & SWING</h4>
            <div className="field-grid">
              <label>
                Door Wall
                <select
                  value={room.door_wall}
                  onChange={e => setRoom({ ...room, door_wall: e.target.value as Room['door_wall'] })}
                >
                  <option value="south">South Wall (Bottom)</option>
                  <option value="north">North Wall (Top)</option>
                  <option value="west">West Wall (Left)</option>
                  <option value="east">East Wall (Right)</option>
                </select>
              </label>
              <label>
                Door Offset (mm)
                <input
                  type="number"
                  min={0}
                  max={2000}
                  step={50}
                  value={room.door_offset_mm}
                  onChange={e => setRoom({ ...room, door_offset_mm: parseInt(e.target.value, 10) || 0 })}
                />
              </label>
              <label>
                Door Width (mm)
                <input
                  type="number"
                  min={600}
                  max={1200}
                  step={50}
                  value={room.door_width_mm}
                  onChange={e => setRoom({ ...room, door_width_mm: parseInt(e.target.value, 10) || 0 })}
                />
              </label>
            </div>
          </section>

          {/* Style & Budget */}
          <section className="edit-req-section">
            <h4>STYLE & BUDGET</h4>
            <div className="field-grid">
              <label>
                Design Style
                <select value={style} onChange={e => setStyle(e.target.value)}>
                  {STYLE_OPTIONS.map(s => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              </label>
              <label>
                Total Budget (INR ₹)
                <input
                  type="number"
                  min={50000}
                  step={10000}
                  value={budget}
                  onChange={e => setBudget(parseInt(e.target.value, 10) || 0)}
                />
              </label>
            </div>
          </section>

          {/* Requirements / Categories */}
          <section className="edit-req-section">
            <h4>FIXTURE CATEGORIES</h4>
            <div className="cat-checkbox-grid">
              {CATEGORY_OPTIONS.map(c => (
                <label key={c.id} className="cat-chk-label">
                  <input
                    type="checkbox"
                    checked={categories.includes(c.id)}
                    onChange={() => toggleCategory(c.id)}
                  />
                  {c.label}
                </label>
              ))}
            </div>
          </section>

          {/* Natural Language Request */}
          <section className="edit-req-section">
            <h4>NATURAL LANGUAGE DESCRIPTION</h4>
            <textarea
              rows={2}
              value={nlText}
              placeholder="Describe your bathroom requirements or preferences..."
              onChange={e => setNlText(e.target.value)}
            />
          </section>
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={handleApply}
            disabled={generateMutation.isPending || categories.length === 0}
          >
            {generateMutation.isPending ? 'Recalculating…' : '✦ Apply & Recalculate'}
          </button>
        </div>
      </div>
    </div>
  );
}
