import React from 'react';
import { useDesignStore } from '../../store';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

// Only categories present in the CSV
const CATEGORIES = [
  { value: 'toilet', label: '🚽 Toilet', desc: 'Standard toilet' },
  { value: 'smart_toilet', label: '🤖 Smart Toilet', desc: 'Integrated cleansing system' },
  { value: 'vanity', label: '🪞 Vanity', desc: 'Washbasin unit with counter' },
  { value: 'basin', label: '🫙 Basin', desc: 'Wall-mount or pedestal basin' },
  { value: 'shower', label: '🚿 Shower', desc: 'Shower head / system' },
  { value: 'faucet', label: '🚰 Faucet', desc: 'Tap / faucet' },
];

export default function StepRequirements({ onNext, onBack }: Props) {
  const { wizardData, setWizardData, completeWizard } = useDesignStore();
  const { categories, nlText } = wizardData;

  const toggleCategory = (val: string) => {
    const next = categories.includes(val)
      ? categories.filter(c => c !== val)
      : [...categories, val];
    setWizardData({ categories: next });
  };

  const handleFinish = () => {
    completeWizard();
    onNext();
  };

  return (
    <div className="step-card">
      <p className="eyebrow">Step 4 of 4</p>
      <h2>What do you need?</h2>
      <p className="step-desc">Select the fixture categories to include from the KOHLER product catalog.</p>

      <div className="category-grid">
        {CATEGORIES.map(c => (
          <button
            key={c.value}
            className={`category-card ${categories.includes(c.value) ? 'selected' : ''}`}
            onClick={() => toggleCategory(c.value)}
          >
            <span className="cat-emoji">{c.label.split(' ')[0]}</span>
            <strong>{c.label.split(' ').slice(1).join(' ')}</strong>
            <span className="cat-desc">{c.desc}</span>
          </button>
        ))}
      </div>

      {categories.length === 0 && (
        <p className="warn-text">⚠ Select at least one category to generate a design.</p>
      )}

      {/* Describe Your Requirements Section */}
      <div className="describe-requirements-section" style={{ marginTop: '24px' }}>
        <label style={{ display: 'block', fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>
          Describe your requirements
        </label>
        <textarea
          className="nl-textarea"
          rows={4}
          style={{ width: '100%', padding: '12px', borderRadius: '4px', border: '1px solid #D8D2C8', fontSize: '13px', fontFamily: 'Inter, sans-serif' }}
          placeholder="Example: Keep the toilet below ₹20,000. I want a modern bathroom with a wall-hung vanity and shower. Prefer compact products and keep the center circulation open."
          value={nlText}
          onChange={e => setWizardData({ nlText: e.target.value })}
        />
        <p style={{ fontSize: '11px', color: '#68635B', marginTop: '6px', lineHeight: '1.4' }}>
          ⓘ Your description is interpreted as additional constraints and preferences. It does not remove selected categories unless you explicitly ask.
        </p>
      </div>

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button
          className="btn-primary"
          onClick={handleFinish}
          disabled={categories.length === 0}
        >
          Generate Design ✨
        </button>
      </div>
    </div>
  );
}
