import React from 'react';
import { useDesignStore } from '../../store';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

const STYLES = [
  { value: 'modern', label: 'Modern', image: '/images/styles/modern.jpg', desc: 'Clean lines, minimal detail,\nneutral palette' },
  { value: 'classical', label: 'Classical', image: '/images/styles/classical.jpg', desc: 'Ornate fixtures, warm tones,\ntimeless elegance' },
  { value: 'industrial', label: 'Industrial', image: '/images/styles/industrial.jpg', desc: 'Matte finishes, exposed hardware,\nbold contrast' },
  { value: 'scandinavian', label: 'Scandinavian', image: '/images/styles/scandinavian.jpg', desc: 'Light woods, whites,\nfunctional simplicity' },
];

export default function StepStyle({ onNext, onBack }: Props) {
  const { wizardData, setWizardData } = useDesignStore();

  return (
    <div className="step-card style-step-card">
      <p className="eyebrow">Step 2 of 4</p>
      <h2>Choose your style</h2>
      <p className="step-desc">
        Style influences product selection and design recommendations. All products are from the KOHLER catalog.
      </p>

      <div className="style-grid">
        {STYLES.map(s => {
          const isSelected = wizardData.style === s.value;
          return (
            <button
              key={s.value}
              className={`style-card style-${s.value} ${isSelected ? 'selected' : ''}`}
              onClick={() => setWizardData({ style: s.value })}
              style={{ backgroundImage: `url(${s.image})` }}
            >
              {isSelected && (
                <div className="style-check-badge" aria-label="Selected">
                  ✓
                </div>
              )}
              <div className="style-card-content">
                <h3>{s.label}</h3>
                <p className="style-desc">{s.desc}</p>
              </div>
            </button>
          );
        })}
      </div>

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn-primary" onClick={onNext}>Next: Budget →</button>
      </div>
    </div>
  );
}
