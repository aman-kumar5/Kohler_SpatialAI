import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { useDesignStore } from '../../store';
import { api } from '../../api';
import type { Design, DesignComparison, ImprovementMetric } from '../../types';

interface Props { design: Design; allDesigns: Design[]; }

const labels: Record<ImprovementMetric, string> = {
  style: 'Style improvement',
  budget: 'Lower-cost proposal',
  spatial_fit: 'Spatial-fit improvement',
  compatibility: 'Compatibility improvement'
};

const coreScores = (d: Design): [string, number | null][] => [
  ['Spatial fit', d.score.spatial_fit],
  ['Budget fit', d.score.budget_fit],
  ['Style match', d.score.style_match],
  ['Compatibility', d.score.compatibility]
];

export default function AICopilot({ design, allDesigns }: Props) {
  const { wizardData, pendingImprovement, setPendingImprovement, acceptPendingImprovement, rejectPendingImprovement } = useDesignStore();
  const [error, setError] = useState<string | null>(null);
  const [comparisons, setComparisons] = useState<DesignComparison[]>([]);
  const [expandedAlternative, setExpandedAlternative] = useState<string | null>(null);

  const alternatives = allDesigns.filter(item => item.name !== design.name);

  useEffect(() => {
    if (!alternatives.length) { setComparisons([]); return; }
    api.compare(design, alternatives).then(setComparisons).catch(() => setComparisons([]));
  }, [design, allDesigns]);

  const improve = useMutation({
    mutationFn: (metric: ImprovementMetric) => api.improve(metric, design, wizardData.budget_inr, wizardData.style),
    onSuccess: (data, metric) => {
      if (data.no_improvement || !data.improved_design) {
        setError(data.reason || 'No verified improvement was found under current constraints.');
      } else {
        setError(null);
        setPendingImprovement({ ...data.improved_design, name: design.name, room: design.room || wizardData.room }, metric, data.reason);
      }
    },
    onError: (e: Error) => setError(e.message)
  });

  const accept = useMutation({
    mutationFn: acceptPendingImprovement,
    onError: (e: Error) => setError(e.message)
  });

  if (pendingImprovement) {
    const proposed = pendingImprovement.proposal;
    const costDelta = proposed.validation.total_price_inr - design.validation.total_price_inr;
    return (
      <motion.section className="proposal-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        <p className="eyebrow">AI OPTIMIZER PROPOSAL</p>
        <h3>{labels[pendingImprovement.metric]}</h3>
        <div className="proposal-score">
          <div><small>Current</small><strong>{design.score.total}/100</strong></div>
          <span>→</span>
          <div><small>Proposed</small><strong>{proposed.score.total}/100</strong></div>
        </div>
        <p className="proposal-delta">
          {(proposed.score.total - design.score.total) >= 0 ? '+' : ''}{(proposed.score.total - design.score.total).toFixed(1)} points · ₹{Math.abs(costDelta).toLocaleString('en-IN')} {costDelta > 0 ? 'more' : costDelta < 0 ? 'saved' : 'unchanged'}
        </p>
        <h4>Metric Impact</h4>
        {coreScores(design).map(([name, value], i) => (
          <div className="proposal-metric" key={name}>
            <span>{name}</span>
            <span>{value ?? 'Limited'} → {coreScores(proposed)[i][1] ?? 'Limited'}</span>
          </div>
        ))}
        <p className="proposal-reason">{pendingImprovement.reason}</p>
        {error && <p className="error-text">{error}</p>}
        <div className="proposal-actions">
          <button className="btn-primary" onClick={() => accept.mutate()} disabled={accept.isPending}>
            {accept.isPending ? 'Verifying…' : '✓ ACCEPT IMPROVEMENT'}
          </button>
          <button className="btn-ghost" onClick={rejectPendingImprovement}>← BACK / DISCARD</button>
        </div>
      </motion.section>
    );
  }

  const radar = [
    ['Spatial', design.score.spatial_fit],
    ['Budget', design.score.budget_fit],
    ['Style', design.score.style_match],
    ['Compat.', design.score.compatibility],
    ['Access.', design.score.accessibility],
    ['Sustain.', design.score.sustainability]
  ].map(([subject, value]) => ({ subject, value: value ?? 0 }));

  const used = design.validation.total_price_inr;
  const roomW = design.room?.width_mm ?? wizardData.room.width_mm ?? 1800;
  const roomD = design.room?.depth_mm ?? wizardData.room.depth_mm ?? 2400;

  // Derive dynamic design insight
  const scorePairs = [
    ['spatial fit', design.score.spatial_fit ?? 0],
    ['budget fit', design.score.budget_fit ?? 0],
    ['style match', design.score.style_match ?? 0],
    ['compatibility', design.score.compatibility ?? 0],
  ].sort((a, b) => (b[1] as number) - (a[1] as number));
  const strongest = scorePairs[0][0];
  const weakest = scorePairs[scorePairs.length - 1][0];
  const insightText = `Your design is strongest on ${strongest}. The main opportunity is ${weakest}.`;

  return (
    <div className="copilot-panel">
      <p className="eyebrow">AI OPTIMIZER</p>
      <div className="copilot-header">
        <h2>AI Optimizer</h2>
      </div>
      <p className="copilot-summary">Optimize your bathroom with evidence-based suggestions.</p>

      {/* Improve Score Actions Grid */}
      <div className="copilot-score-actions-section">
        <span className="section-subtitle-sm">Improve score actions</span>
        <div className="improve-action-buttons-grid">
          <button onClick={() => improve.mutate('style')} disabled={improve.isPending}>
            <span>✨ Improve Style</span>
          </button>
          <button onClick={() => improve.mutate('budget')} disabled={improve.isPending}>
            <span>₹ Lower Cost</span>
          </button>
          <button onClick={() => improve.mutate('spatial_fit')} disabled={improve.isPending}>
            <span>📐 Improve Fit</span>
          </button>
          <button onClick={() => improve.mutate('compatibility')} disabled={improve.isPending}>
            <span>🔗 Improve Compatibility</span>
          </button>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {/* Design Insight Card */}
      <div className="design-insight-card">
        <span className="insight-eyebrow">DESIGN INSIGHT</span>
        <p className="insight-text">{insightText}</p>
      </div>

      {/* Radar Chart Visualizer */}
      <div className="radar-wrap">
        <ResponsiveContainer width="100%" height={180}>
          <RadarChart data={radar}>
            <PolarGrid stroke="#E4E0D6" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9, fill: '#5B5852' }} />
            <Tooltip formatter={(value: number) => [`${value}/100`, 'Score']} />
            <Radar dataKey="value" stroke="#B08D57" fill="#B08D57" fillOpacity={0.22} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Why this design? Section */}
      <div className="copilot-section">
        <h3>Why this design?</h3>
        <p className="why-subtext">Best overall balance for your room, budget and preferences.</p>

        <div className="why-breakdown-list">
          <div className="why-item">
            <div className="why-item-head">
              <strong>ROOM FIT</strong>
              <span className="why-score-val">{design.score.spatial_fit}</span>
            </div>
            {design.score.spatial_breakdown && design.score.spatial_breakdown.length > 0 ? (
              <div className="why-item-details" style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                {design.score.spatial_breakdown.map((item, idx) => (
                  <p key={idx} className="why-item-desc" style={{ color: item.status === 'overlap' ? '#B43333' : 'inherit', fontSize: '0.82rem', margin: 0 }}>
                    {item.detail}
                  </p>
                ))}
              </div>
            ) : (
              <p className="why-item-desc">
                ✓ All selected fixtures remain within the {roomW} × {roomD} mm room bounds.
              </p>
            )}
          </div>

          <div className="why-item">
            <div className="why-item-head">
              <strong>DOOR CLEARANCE</strong>
              <span className="why-score-val">Pass</span>
            </div>
            <p className="why-item-desc">
              ✓ The required door clearance swing zone remains unobstructed.
            </p>
          </div>

          <div className="why-item">
            <div className="why-item-head">
              <strong>BUDGET FIT</strong>
              <span className="why-score-val">{design.score.budget_fit}</span>
            </div>
            <p className="why-item-desc">
              ✓ ₹{used.toLocaleString('en-IN')} used of ₹{wizardData.budget_inr.toLocaleString('en-IN')} budget.
            </p>
          </div>

          {design.score.style_match !== null && (
            <div className="why-item">
              <div className="why-item-head">
                <strong>STYLE MATCH</strong>
                <span className="why-score-val">{design.score.style_match}</span>
              </div>
              <p className="why-item-desc">
                ✓ Catalog style matching score: {design.score.style_match}/100.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Why not the others? Section */}
      <div className="copilot-section">
        <h3>Why not the others?</h3>
        <div className="why-others-stack">
          {alternatives.map((alt) => {
            const isExpanded = expandedAlternative === alt.name;
            const comp = comparisons.find(c => c.design === alt.name);
            const scoreDiff = alt.score.total - design.score.total;
            const priceDiff = alt.validation.total_price_inr - design.validation.total_price_inr;

            return (
              <div className="why-other-card" key={alt.name}>
                <button
                  className="btn-other-toggle-ref"
                  onClick={() => setExpandedAlternative(isExpanded ? null : alt.name)}
                >
                  <span className="alt-title">{alt.name}</span>
                  <span className="caret">{isExpanded ? '▲' : '▼'}</span>
                </button>
                {isExpanded && (
                  <div className="other-details-body-ref">
                    <p className="other-summary-text">
                      Different profile prioritizes {alt.name.toLowerCase()} alignment.
                    </p>
                    <p className="other-bullet">
                      • Cost {priceDiff >= 0 ? `+₹${priceDiff.toLocaleString('en-IN')}` : `-₹${Math.abs(priceDiff).toLocaleString('en-IN')}`} versus selected design
                    </p>
                    {alt.score.style_match !== null && design.score.style_match !== null && (
                      <p className="other-bullet">
                        • Style Alignment {alt.score.style_match >= design.score.style_match ? '+' : ''}{(alt.score.style_match - design.score.style_match).toFixed(1)} points
                      </p>
                    )}
                    <p className="other-bullet">
                      • Overall score {alt.score.total}/100 versus {design.score.total}/100
                    </p>
                    {comp?.details && comp.details.map(d => (
                      <p key={d} className="other-bullet">• {d}</p>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
