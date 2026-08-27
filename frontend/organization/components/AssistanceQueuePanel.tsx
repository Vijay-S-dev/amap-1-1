'use client';

/**
 * Supervisor Assistance Queue & Triage Panel (§ 6, § 7, § 8, § 21).
 * Displays live worker assistance requests with Acknowledge, Guidance Response,
 * and Resolution workflows.
 */

import React, { useState } from 'react';
import { api } from '@/shared/api/client';

interface AssistanceItem {
  id: string;
  worker_name: string;
  worker_email?: string;
  task_name: string;
  status: string; // open | acknowledged | in_progress | resolved
  priority: string; // urgent | high | normal | low
  reason: string;
  is_emergency: boolean;
  requested_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  request_data?: any;
}

interface AssistanceQueuePanelProps {
  requests: AssistanceItem[];
  onRefresh: () => void;
}

export function AssistanceQueuePanel({ requests, onRefresh }: AssistanceQueuePanelProps) {
  const [respondingId, setRespondingId] = useState<string | null>(null);
  const [guidanceMessage, setGuidanceMessage] = useState<string>('');
  const [resolutionNotes, setResolutionNotes] = useState<string>('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleAcknowledge = async (requestId: string) => {
    try {
      setActionLoading(true);
      setActionError(null);
      await api.acknowledgeSupervisorAssistance(requestId);
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Failed to acknowledge request');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendGuidance = async (requestId: string) => {
    if (!guidanceMessage.trim()) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await api.respondSupervisorAssistance(requestId, guidanceMessage.trim());
      setRespondingId(null);
      setGuidanceMessage('');
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Failed to send guidance');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolve = async (requestId: string) => {
    try {
      setActionLoading(true);
      setActionError(null);
      await api.resolveSupervisorAssistance(requestId, resolutionNotes.trim() || undefined);
      setResolutionNotes('');
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Failed to resolve request');
    } finally {
      setActionLoading(false);
    }
  };

  const activeRequests = requests.filter((r) => r.status !== 'resolved');

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--accent-amber)' }}>⚠️</span> Supervisor Assistance Queue
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Real-time worker assistance tickets and operator guidance triage
          </span>
        </div>
        <span className={`badge ${activeRequests.length > 0 ? 'badge-rose' : 'badge-emerald'}`}>
          {activeRequests.length} Pending
        </span>
      </div>

      {actionError && (
        <div role="alert" style={{ background: 'rgba(244, 63, 94, 0.2)', border: '1px solid var(--accent-rose)', padding: '0.75rem', borderRadius: '8px', color: '#fca5a5', marginBottom: '1rem', fontSize: '0.85rem' }}>
          ⚠️ {actionError}
        </div>
      )}

      {/* Empty State */}
      {activeRequests.length === 0 ? (
        <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>✅</span>
          <strong>All worker assistance requests are currently resolved.</strong>
          <p style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Station assistance signals triggered by voice &ldquo;Help&rdquo; or assistance gestures will appear here live.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {activeRequests.map((req) => (
            <div
              key={req.id}
              className="glass-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                borderLeft: `4px solid ${
                  req.is_emergency
                    ? 'var(--accent-rose)'
                    : req.priority === 'high'
                    ? 'var(--accent-amber)'
                    : 'var(--worker-cyan)'
                }`,
              }}
            >
              {/* Row 1: Badges & Worker Info */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span
                    className={
                      req.is_emergency
                        ? 'badge badge-rose'
                        : req.priority === 'high'
                        ? 'badge badge-amber'
                        : 'badge badge-cyan'
                    }
                  >
                    {req.priority.toUpperCase()}
                  </span>
                  <strong style={{ color: 'white' }}>{req.worker_name}</strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    • Station: {req.task_name}
                  </span>
                </div>
                <span
                  className={`badge ${
                    req.status === 'in_progress'
                      ? 'badge-cyan'
                      : req.status === 'acknowledged'
                      ? 'badge-emerald'
                      : 'badge-amber'
                  }`}
                >
                  {req.status.toUpperCase()}
                </span>
              </div>

              {/* Row 2: Worker Message */}
              <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', background: 'rgba(0, 0, 0, 0.2)', padding: '0.75rem', borderRadius: '8px' }}>
                <strong>Issue Description:</strong> {req.reason}
              </div>

              {/* Row 3: Existing Guidance if in progress */}
              {req.request_data?.supervisor_guidance && (
                <div style={{ fontSize: '0.85rem', color: 'var(--org-emerald)', background: 'rgba(16, 185, 129, 0.1)', padding: '0.6rem 0.85rem', borderRadius: '8px' }}>
                  <strong>Transmitted Guidance:</strong> &ldquo;{req.request_data.supervisor_guidance}&rdquo;
                </div>
              )}

              {/* Row 4: Guidance Input Form (if responding) */}
              {respondingId === req.id && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.25rem' }}>
                  <textarea
                    value={guidanceMessage}
                    onChange={(e) => setGuidanceMessage(e.target.value)}
                    placeholder="Type guidance instructions for the worker..."
                    rows={2}
                    className="glass-card"
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '8px', color: 'white', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid var(--surface-glass-border)', fontSize: '0.85rem', resize: 'none' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                    <button
                      type="button"
                      onClick={() => setRespondingId(null)}
                      className="btn btn-secondary"
                      style={{ minHeight: '38px', padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={actionLoading || !guidanceMessage.trim()}
                      onClick={() => handleSendGuidance(req.id)}
                      className="btn btn-primary"
                      style={{ minHeight: '38px', padding: '0.4rem 1rem', fontSize: '0.8rem', background: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)' }}
                    >
                      Transmit Guidance →
                    </button>
                  </div>
                </div>
              )}

              {/* Row 5: Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', marginTop: '0.25rem' }}>
                {req.status === 'open' && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => handleAcknowledge(req.id)}
                    className="btn btn-secondary"
                    style={{ minHeight: '44px', padding: '0.4rem 1rem', fontSize: '0.85rem' }}
                  >
                    ✓ Acknowledge
                  </button>
                )}

                {respondingId !== req.id && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => {
                      setRespondingId(req.id);
                      setGuidanceMessage('');
                    }}
                    className="btn btn-secondary"
                    style={{ minHeight: '44px', padding: '0.4rem 1rem', fontSize: '0.85rem' }}
                  >
                    💬 Send Guidance
                  </button>
                )}

                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={() => handleResolve(req.id)}
                  className="btn btn-success"
                  style={{
                    minHeight: '44px',
                    padding: '0.4rem 1.2rem',
                    fontSize: '0.85rem',
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    color: 'white',
                  }}
                >
                  ✓ Resolve & Close Ticket
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
