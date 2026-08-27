'use client';

/**
 * Supervisor Audit Event Timeline (§ 17, § 18, § 21).
 * Displays an immutable chronological audit trail of all supervisor dispatches,
 * assistance ticket lifecycle events, and emergency safety interventions.
 */

import React from 'react';

interface AuditItem {
  id: string;
  event_type: string;
  actor_name: string;
  resource_type: string;
  resource_id?: string;
  occurred_at: string;
  event_data?: any;
}

interface SupervisorAuditTimelineProps {
  events: AuditItem[];
}

export function SupervisorAuditTimeline({ events }: SupervisorAuditTimelineProps) {
  const formatEventName = (eventType: string) => {
    return eventType
      .replace(/_/g, ' ')
      .replace(/\./g, ' — ')
      .toUpperCase();
  };

  const getEventBadgeClass = (eventType: string) => {
    if (eventType.includes('emergency') || eventType.includes('stop')) return 'badge-rose';
    if (eventType.includes('assigned') || eventType.includes('created')) return 'badge-emerald';
    if (eventType.includes('resolved') || eventType.includes('acknowledged')) return 'badge-cyan';
    return 'badge-muted';
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ marginBottom: '1.25rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: 'var(--worker-cyan)' }}>📜</span> Operations Audit Timeline
        </h2>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Immutable cryptographic log of supervisor dispatches and station safety events
        </span>
      </div>

      {events.length === 0 ? (
        <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>📝</span>
          <strong>No audit events recorded for this organization yet.</strong>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {events.map((evt) => (
            <div
              key={evt.id}
              className="glass-card"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '0.75rem',
                padding: '0.85rem 1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                <span className={`badge ${getEventBadgeClass(evt.event_type)}`} style={{ fontSize: '0.75rem' }}>
                  {formatEventName(evt.event_type)}
                </span>
                <div>
                  <strong style={{ fontSize: '0.9rem', color: 'white' }}>{evt.actor_name}</strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                    Target: {evt.resource_type}
                  </span>
                </div>
              </div>

              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {new Date(evt.occurred_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
