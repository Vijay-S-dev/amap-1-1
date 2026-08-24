'use client';

/**
 * Admin Adaptation Review Panel Component
 * Displays evidence-based personalization adaptation recommendations
 * and allows supervisors/admins to approve or reject suggestions.
 */

import React, { useState } from 'react';
import { AdaptationRecommendation } from '@/shared/types';

interface PendingWorkerAdaptation {
  id: string;
  workerName: string;
  stationName: string;
  evidenceCount: number;
  recommendation: AdaptationRecommendation;
}

const DEMO_ADAPTATIONS: PendingWorkerAdaptation[] = [
  {
    id: 'adapt-1',
    workerName: 'Alex Morgan',
    stationName: 'Station 4B',
    evidenceCount: 4,
    recommendation: {
      recommendationType: 'dwell_time_adjustment',
      currentValue: 450,
      suggestedValue: 600,
      confidence: 0.88,
      reason: 'Observed 4 repeated low-confidence gesture tremor events. Recommend increasing dwell time from 450ms to 600ms.',
      autoApplicable: true,
    },
  },
  {
    id: 'adapt-2',
    workerName: 'Jordan Lee',
    stationName: 'Station 2A',
    evidenceCount: 5,
    recommendation: {
      recommendationType: 'modality_switch_recommendation',
      currentValue: 'Voice primary',
      suggestedValue: 'Gesture / UI primary',
      confidence: 0.85,
      reason: 'Observed 5 repeated acoustic noise floor dropouts in stamping zone. Recommend switching primary mode to Gesture.',
      autoApplicable: false,
    },
  },
];

export function AdaptationReviewPanel() {
  const [adaptations, setAdaptations] = useState<PendingWorkerAdaptation[]>(DEMO_ADAPTATIONS);
  const [message, setMessage] = useState<string | null>(null);

  const handleAction = (id: string, approved: boolean) => {
    setAdaptations((prev) => prev.filter((a) => a.id !== id));
    setMessage(approved ? '✓ Adaptation approved and applied to worker profile.' : '✗ Adaptation suggestion dismissed.');
    setTimeout(() => setMessage(null), 3000);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--worker-cyan)' }}>🧠</span> Evidence-Based Adaptation Review
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Evaluates multi-signal repeated difficulty patterns per AMAP adaptation rules
          </span>
        </div>
        {message && <span className="badge badge-emerald">{message}</span>}
      </div>

      {adaptations.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          ✅ All pending worker adaptation recommendations have been reviewed.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {adaptations.map((item) => (
            <div key={item.id} className="glass-card" style={{ borderLeft: '4px solid var(--worker-cyan)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <div>
                  <strong style={{ fontSize: '1.05rem', color: 'white' }}>{item.workerName}</strong>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                    ({item.stationName}) • Evidence: {item.evidenceCount} recurring events
                  </span>
                </div>
                <span className="badge badge-cyan">{Math.round(item.recommendation.confidence * 100)}% CONFIDENCE</span>
              </div>

              <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '0.75rem', lineHeight: '1.5' }}>
                {item.recommendation.reason}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Current: <strong style={{ color: 'white' }}>{String(item.recommendation.currentValue)}</strong> ➔ Suggested:{' '}
                  <strong style={{ color: 'var(--org-emerald)' }}>{String(item.recommendation.suggestedValue)}</strong>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => handleAction(item.id, false)}
                    className="btn btn-secondary"
                    style={{ minHeight: '36px', fontSize: '0.8rem' }}
                  >
                    Dismiss
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction(item.id, true)}
                    className="btn btn-primary"
                    style={{ minHeight: '36px', fontSize: '0.8rem' }}
                  >
                    Approve & Apply
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
