'use client';

/**
 * Worker Deep-Dive Detail View Component (§ 4, § 5, § 13, § 14, § 21).
 * Displays full worker session details, active workflow steps breakdown,
 * accessibility interaction health, and historical assistance requests.
 */

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';

interface WorkerDetailPanelProps {
  workerId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export function WorkerDetailPanel({ workerId, isOpen, onClose }: WorkerDetailPanelProps) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !workerId) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    api
      .getSupervisorWorkerDetail(workerId)
      .then((data) => {
        if (mounted) setDetail(data);
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Failed to load worker detail');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [workerId, isOpen]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="worker-detail-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(11, 15, 25, 0.85)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '750px',
          maxHeight: '90vh',
          overflowY: 'auto',
          borderRadius: '24px',
          padding: '2rem',
          border: '1px solid var(--surface-glass-border)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem',
        }}
      >
        {/* Modal Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--org-emerald)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Worker Operations Telemetry
            </span>
            <h2 id="worker-detail-title" style={{ fontSize: '1.5rem', fontWeight: 800, color: 'white', marginTop: '0.2rem' }}>
              {detail?.full_name || 'Worker Inspection'}
            </h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{detail?.email}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            aria-label="Close worker details"
            style={{ minHeight: '40px', minWidth: '40px', padding: '0.4rem', borderRadius: '50%' }}
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading telemetry from live database...
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--accent-rose)' }}>
            ⚠️ {error}
          </div>
        ) : detail ? (
          <>
            {/* Top Cards: Status & Health */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              <div className="glass-card">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OPERATIONAL STATE</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.25rem', color: 'var(--text-primary)' }}>
                  {detail.status}
                </div>
              </div>
              <div className="glass-card">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>INTERACTION MODE</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.25rem', color: 'var(--worker-cyan)', textTransform: 'capitalize' }}>
                  {detail.interaction_mode}
                </div>
              </div>
              <div className="glass-card">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SESSION DURATION</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.25rem', color: 'var(--org-emerald)' }}>
                  {Math.floor(detail.session_duration_seconds / 60)} mins
                </div>
              </div>
            </div>

            {/* Live Task & Step Tree (§ 5) */}
            <div className="glass-card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>📋</span> Active Assembly Workflow
              </h3>
              <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'white', marginBottom: '0.75rem' }}>
                {detail.current_task_name || 'No task in execution'}
              </div>

              {detail.step_details && detail.step_details.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {detail.step_details.map((step: any) => (
                    <div
                      key={step.step_number}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.6rem 0.9rem',
                        borderRadius: '8px',
                        background: step.is_current
                          ? 'rgba(6, 182, 212, 0.15)'
                          : step.status === 'completed'
                          ? 'rgba(16, 185, 129, 0.08)'
                          : 'rgba(255, 255, 255, 0.02)',
                        borderLeft: step.is_current
                          ? '3px solid var(--worker-cyan)'
                          : step.status === 'completed'
                          ? '3px solid var(--org-emerald)'
                          : '3px solid transparent',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <span style={{ fontSize: '1rem' }}>
                          {step.status === 'completed' ? '✓' : step.is_current ? '⚡' : '○'}
                        </span>
                        <div>
                          <strong style={{ fontSize: '0.9rem', color: step.is_current ? 'white' : 'var(--text-primary)' }}>
                            Step {step.step_number}: {step.title}
                          </strong>
                          {step.description && (
                            <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {step.description}
                            </p>
                          )}
                        </div>
                      </div>
                      <span
                        className={`badge ${
                          step.status === 'completed'
                            ? 'badge-emerald'
                            : step.is_current
                            ? 'badge-cyan'
                            : 'badge-muted'
                        }`}
                        style={{ fontSize: '0.7rem' }}
                      >
                        {step.status.toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No active workflow steps tracked for current station assignment.
                </div>
              )}
            </div>

            {/* Recent Assistance History (§ 14) */}
            <div className="glass-card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>🆘</span> Recent Assistance Requests
              </h3>
              {detail.recent_assistance_requests && detail.recent_assistance_requests.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {detail.recent_assistance_requests.map((req: any) => (
                    <div
                      key={req.id}
                      style={{
                        padding: '0.5rem 0.75rem',
                        borderRadius: '6px',
                        background: 'rgba(255, 255, 255, 0.02)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div>
                        <span>{req.reason || 'Assistance requested'}</span>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{req.requested_at}</div>
                      </div>
                      <span className={req.status === 'resolved' ? 'badge badge-emerald' : 'badge badge-amber'}>
                        {req.status.toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  No recent assistance tickets on record for this worker.
                </div>
              )}
            </div>
          </>
        ) : null}

        {/* Footer Close */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
          <button type="button" onClick={onClose} className="btn btn-secondary" style={{ minHeight: '48px', padding: '0.6rem 1.5rem' }}>
            Close Inspection
          </button>
        </div>
      </div>
    </div>
  );
}
