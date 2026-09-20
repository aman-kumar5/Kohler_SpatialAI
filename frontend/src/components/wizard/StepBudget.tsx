import React from 'react';
import { useDesignStore } from '../../store';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

const PRESETS = [
  { label: '₹1,00,000', value: 100000 },
  { label: '₹2,00,000', value: 200000 },
  { label: '₹3,00,000', value: 300000 },
  { label: '₹5,00,000', value: 500000 },
  { label: '₹10,00,000', value: 1000000 },
];

export default function StepBudget({ onNext, onBack }: Props) {
  const { wizardData, setWizardData } = useDesignStore();
  const { budget_inr } = wizardData;

  const fmt = (v: number) =>
    '₹' + v.toLocaleString('en-IN');

  const handleNumChange = (valStr: string) => {
    const parsed = valStr === '' ? 0 : parseInt(valStr, 10);
    setWizardData({ budget_inr: isNaN(parsed) ? 0 : parsed });
  };

  return (
    <div className="step-card budget-step-card">
      <p className="eyebrow">Step 3 of 4</p>
      <h2>Set your total budget</h2>
      <p className="step-desc">
        This is a hard constraint — the optimizer will only select products whose combined price stays within this limit.
      </p>

      {/* Hero Budget Card */}
      <div className="budget-hero-box">
        <span className="budget-hero-eyebrow">TOTAL BUDGET</span>
        <h3 className="budget-hero-value">{fmt(budget_inr)}</h3>
      </div>

      {/* Range Slider */}
      <div className="budget-slider-wrap">
        <input
          type="range"
          min={50000}
          max={2000000}
          step={10000}
          value={budget_inr || 50000}
          onChange={e => setWizardData({ budget_inr: +e.target.value })}
          className="budget-slider"
        />
        <div className="budget-bounds">
          <span>₹50,000</span>
          <span>₹20,00,000</span>
        </div>
      </div>

      {/* Preset Chips */}
      <div className="preset-chips">
        {PRESETS.map(p => (
          <button
            key={p.value}
            className={`chip ${budget_inr === p.value ? 'selected' : ''}`}
            onClick={() => setWizardData({ budget_inr: p.value })}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Manual Input */}
      <label className="manual-budget">
        Or enter exact amount (INR)
        <input
          type="number"
          min={50000}
          max={2000000}
          step={1000}
          value={budget_inr === 0 ? '' : budget_inr}
          onChange={e => handleNumChange(e.target.value)}
        />
      </label>

      {/* Info Box */}
      <div className="space-info-box">
        <span className="info-icon">ⓘ</span>
        <p>Your budget helps us recommend the best possible products within your range.</p>
      </div>

      {/* Actions */}
      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn-primary" onClick={onNext} disabled={budget_inr <= 0}>Next: Requirements →</button>
      </div>
    </div>
  );
}
