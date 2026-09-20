import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useDesignStore } from '../../store';
import { api } from '../../api';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

export default function StepNaturalLanguage({ onBack }: Props) {
  const { wizardData, setWizardData, completeWizard } = useDesignStore();
  const [parseError, setParseError] = useState('');
  const [parsed, setParsed] = useState(false);

  const parseMutation = useMutation({
    mutationFn: () => api.parseRequirements(wizardData.nlText),
    onSuccess: (spec) => {
      // Merge AI-parsed fields into wizard, but only concrete non-null ones
      const updates: Partial<typeof wizardData> = {};
      if (spec.room) updates.room = spec.room;
      if (spec.budget_inr) updates.budget_inr = spec.budget_inr;
      if (spec.style) updates.style = spec.style;
      if (spec.requirements?.length) updates.categories = spec.requirements;
      setWizardData(updates);
      setParsed(true);
      setParseError('');
    },
    onError: (e: Error) => {
      setParseError(`Could not parse the description: ${e.message}. You can still proceed with your manual selections.`);
    },
  });

  const handleGenerate = () => {
    completeWizard();
  };

  return (
    <div className="step-card">
      <p className="eyebrow">STEP 6 OF 6</p>
      <h2>Describe in your own words</h2>
      <p className="step-desc">
        Optionally describe your ideal bathroom. The AI extracts room size, budget, style and fixture types —
        it never invents products, prices or dimensions beyond what you state.
      </p>

      <textarea
        className="nl-textarea"
        rows={5}
        placeholder='e.g. "1800×2400mm modern bathroom with a smart toilet, compact vanity and shower, budget ₹3,00,000"'
        value={wizardData.nlText}
        onChange={e => { setWizardData({ nlText: e.target.value }); setParsed(false); }}
      />

      {wizardData.nlText.trim() && !parsed && (
        <button
          className="btn-secondary"
          onClick={() => parseMutation.mutate()}
          disabled={parseMutation.isPending}
        >
          {parseMutation.isPending ? 'Parsing…' : '✦ Parse with AI'}
        </button>
      )}

      {parsed && (
        <p className="success-text">
          ✓ AI updated your space ({wizardData.room.width_mm}×{wizardData.room.depth_mm}mm),
          budget (₹{wizardData.budget_inr.toLocaleString('en-IN')}),
          style ({wizardData.style}). Review the steps above to confirm.
        </p>
      )}

      {parseError && <p className="error-text">{parseError}</p>}

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn-primary btn-generate" onClick={handleGenerate}>
          Generate My Designs →
        </button>
      </div>
    </div>
  );
}
