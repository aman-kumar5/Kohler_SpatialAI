import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDesignStore } from '../../store';
import StepSpace from './StepSpace';
import StepStyle from './StepStyle';
import StepBudget from './StepBudget';
import StepRequirements from './StepRequirements';

const STEPS = [
  { num: '1', label: 'Space & Image', component: StepSpace },
  { num: '2', label: 'Style', component: StepStyle },
  { num: '3', label: 'Budget', component: StepBudget },
  { num: '4', label: 'Requirements', component: StepRequirements },
];

export default function OnboardingWizard() {
  const { wizardStep, setWizardStep } = useDesignStore();
  const CurrentStep = STEPS[wizardStep].component;

  const goNext = () => {
    if (wizardStep < STEPS.length - 1) setWizardStep(wizardStep + 1);
  };
  const goBack = () => {
    if (wizardStep > 0) setWizardStep(wizardStep - 1);
  };

  return (
    <div className="wizard-shell">
      {/* Progress bar */}
      <div className="wizard-progress">
        {STEPS.map((s, i) => (
          <div key={s.label} className="wizard-step-dot-wrap">
            <button
              className={`wizard-step-dot ${i === wizardStep ? 'active' : ''} ${i < wizardStep ? 'done' : ''}`}
              onClick={() => i < wizardStep && setWizardStep(i)}
              aria-label={`Go to step ${s.num}. ${s.label}`}
            >
              {i < wizardStep ? '✓' : s.num}
            </button>
            <span className={`wizard-step-label ${i === wizardStep ? 'active' : ''}`}>
              {s.label}
            </span>
          </div>
        ))}
      </div>

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={wizardStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className="wizard-content"
        >
          <CurrentStep onNext={goNext} onBack={goBack} isFirst={wizardStep === 0} isLast={wizardStep === STEPS.length - 1} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
