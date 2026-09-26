'use client';

/**
 * Admin Adaptation Review Panel
 * Loads real pending adaptation recommendations from PostgreSQL
 * (GET /api/v1/personalization/recommendations) and records approve/dismiss
 * decisions through the review API. No hardcoded demo adaptation rows.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '@/shared/api/client';
import { AdaptationReviewItem } from '@/shared/types';

function valueLabel(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function AdaptationReviewPanel() {
  const [items, setItems] = useState<AdaptationReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setItems(await api.getAdaptationRecommendations('pending'));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to load adaptation recommendations.'
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAction = async (id: string, approved: boolean) => {
    setBusyId(id);
    setError(null);
    try {
      await api.reviewAdaptationRecommendation(id, approved ? 'approve' : 'dismiss');
      setMessage(
        approved
          ? '✓ Recommendation approved and applied to worker personalization.'
          : '✗ Recommendation dismissed.'
      );
      setTimeout(() => setMessage(null), 3000);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Review action failed.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '1.25rem',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '1.2rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span style={{ color: 'var(--worker-cyan)' }}>🧠</span> Evidence-Based Adaptation Review
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Pending recommendations persisted in PostgreSQL, generated from repeated interaction evidence
          </span>
        </div>
        {message && (
          <span className="badge badge-emerald" role="status">
            {message}
          </span>
        )}
        {error && (
          <span role="alert" style={{ color: 'var(--accent-rose)', fontWeight: 600 }}>
            {error}
          </span>
        )}
      </div>

      {isLoading ? (
        <div
          role="status"
          aria-live="polite"
          style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}
        >
          Loading pending recommendations…
        </div>
      ) : error && items.length === 0 ? (
        <div role="alert" style={{ padding: '2rem', textAlign: 'center' }}>
          <p style={{ color: 'var(--accent-rose)', marginBottom: '0.75rem' }}>{error}</p>
          <button type="button" className="btn btn-secondary" onClick={load}>
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div
          role="status"
          style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}
        >
          ✅ No pending worker adaptation recommendations.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {items.map((item) => (
            <div key={item.id} className="glass-card" style={{ borderLeft: '4px solid var(--worker-cyan)' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: '0.5rem',
                }}
              >
                <div>
                  <strong style={{ fontSize: '1.05rem', color: 'white' }}>
                    {item.worker_name || item.worker_profile_id}
                  </strong>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                    ({item.recommendation_type}) • Evidence: {item.evidence_count} recurring events
                  </span>
                </div>
                <span className="badge badge-cyan">
                  {Math.round(item.confidence * 100)}% CONFIDENCE
                </span>
              </div>

              <p
                style={{
                  fontSize: '0.9rem',
                  color: 'var(--text-primary)',
                  marginBottom: '0.75rem',
                  lineHeight: '1.5',
                }}
              >
                {item.reason}
              </p>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                  Current: <strong style={{ color: 'white' }}>{valueLabel(item.current_value)}</strong> ➔
                  Suggested: <strong style={{ color: 'var(--org-emerald)' }}>{valueLabel(item.suggested_value)}</strong>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => handleAction(item.id, false)}
                    disabled={busyId === item.id}
                    className="btn btn-secondary"
                    style={{ minHeight: '36px', fontSize: '0.8rem' }}
                  >
                    {busyId === item.id ? 'Saving…' : 'Dismiss'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction(item.id, true)}
                    disabled={busyId === item.id}
                    className="btn btn-primary"
                    style={{ minHeight: '36px', fontSize: '0.8rem' }}
                  >
                    {busyId === item.id ? 'Saving…' : 'Approve & Apply'}
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
