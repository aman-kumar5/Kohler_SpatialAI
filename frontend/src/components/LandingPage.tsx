import React from 'react';
import { motion } from 'framer-motion';
import { useDesignStore } from '../store';

export default function LandingPage({ onEnter }: { onEnter: () => void }) {
  const { completeWizard, setWizardData } = useDesignStore();
  const start = () => onEnter();
  const demo = () => {
    setWizardData({
      room: { width_mm: 1800, depth_mm: 2400, door_wall: 'south', door_offset_mm: 1000, door_width_mm: 700 },
      budget_inr: 300000,
      style: 'modern',
      categories: ['toilet', 'vanity', 'shower'],
    });
    completeWizard();
    onEnter();
  };

  return (
    <div className="landing-shell">
      {/* Hero Section */}
      <section className="landing-hero" aria-label="Architectural bathroom design studio">
        <nav className="landing-nav" aria-label="Main navigation">
          <div className="landing-brand">
            <strong>KOHLER</strong>
            <span>SpatialAI</span>
          </div>
          <div className="landing-nav-links">
            <a href="#design">Design</a>
            <a href="#inspiration">Inspiration</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
          </div>
          <button className="landing-nav-cta" onClick={start}>
            Start Designing <span aria-hidden="true">→</span>
          </button>
        </nav>

        <img
          className="landing-hero-image"
          src="/images/hero.jpg"
          alt="Contemporary luxury bathroom with freestanding bath and gold fixtures"
        />
        <div className="landing-image-wash" aria-hidden="true" />

        <motion.div
          id="design"
          className="landing-copy"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <p className="eyebrow">THE ART OF A BETTER HOME</p>
          <h1>
            Design your<br />
            bathroom.<br />
            Intelligently.
          </h1>
          <p>
            From dimensions to design — AI that understands your space, your style, and your budget.
          </p>
          <div className="landing-actions">
            <button className="btn-primary btn-hero-cta" onClick={start}>
              Start Designing <span aria-hidden="true">→</span>
            </button>
            <button className="landing-text-action" onClick={demo}>
              View Demo
            </button>
          </div>
        </motion.div>
      </section>

      {/* Trust Ribbon (5 Equal Columns) */}
      <section className="landing-proof">
        <div className="proof-col">
          <svg className="proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 2L15 9L22 12L15 15L12 22L9 15L2 12L9 9L12 2Z" />
          </svg>
          <div className="proof-text">
            <strong>AI Proposes</strong>
            <span>Understands your needs</span>
          </div>
        </div>

        <div className="proof-col">
          <svg className="proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M8 9h8M8 13h6M8 17h4" />
          </svg>
          <div className="proof-text">
            <strong>Catalog verifies</strong>
            <span>Uses real KOHLER products</span>
          </div>
        </div>

        <div className="proof-col">
          <svg className="proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          </svg>
          <div className="proof-text">
            <strong>Geometry validates</strong>
            <span>Checks every dimension</span>
          </div>
        </div>

        <div className="proof-col">
          <svg className="proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <div className="proof-text">
            <strong>Optimization decides</strong>
            <span>Finds the best design</span>
          </div>
        </div>

        <div className="proof-col">
          <svg className="proof-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v8M8 12h8" />
          </svg>
          <div className="proof-text">
            <strong>You remain in control</strong>
            <span>Approve, edit, and explore</span>
          </div>
        </div>
      </section>
    </div>
  );
}
