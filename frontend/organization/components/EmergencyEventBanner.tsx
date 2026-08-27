'use client';

/**
 * High-Priority Emergency Event Alert Banner for Supervisor Module (§ 8, § 29).
 * Displays immediately at the top of the supervisor screen when a line halt or emergency stop is triggered.
 */

import React from 'react';

interface EmergencyEventBannerProps {
  emergencyEvents: Array<{
    id: string;
    worker_name: string;
    task_name: string;
    reason: string;
    requested_at?: string;
    status: string;
  }>;
  onAcknowledge: (id: string) => void;
}

export function EmergencyEventBanner({ emergencyEvents, onAcknowledge }: EmergencyEventBannerProps) {
  if (!emergencyEvents || emergencyEvents.length === 0) {
    return null;
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.95) 0%, rgba(185, 28, 28, 0.95) 100%)',
        border: '2px solid #fecaca',
        borderRadius: '16px',
        padding: '1.25rem 1.75rem',
        color: 'white',
        boxShadow: '0 10px 25px -5px rgba(239, 68, 68, 0.5)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <span style={{ fontSize: '2rem' }}>🛑</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <strong style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                CRITICAL SAFETY HALT — EMERGENCY STOP ACTIVATED
              </strong>
              <span className="badge" style={{ background: 'white', color: '#b91c1c', fontWeight: 800 }}>
                {emergencyEvents.length} ACTIVE
              </span>
            </div>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.9rem', opacity: 0.95 }}>
              Assembly operations suspended at the station. Supervisor safety clearance required before resumption.
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {emergencyEvents.map((evt) => (
          <div
            key={evt.id}
            style={{
              background: 'rgba(0, 0, 0, 0.25)',
              borderRadius: '10px',
              padding: '0.85rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div>
              <strong style={{ fontSize: '1rem' }}>{evt.worker_name}</strong>
              <span style={{ opacity: 0.8, fontSize: '0.85rem', marginLeft: '0.5rem' }}>
                • Station Task: {evt.task_name}
              </span>
              <div style={{ fontSize: '0.85rem', marginTop: '0.2rem', fontStyle: 'italic' }}>
                Reason: &ldquo;{evt.reason}&rdquo;
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {evt.status === 'open' && (
                <button
                  type="button"
                  onClick={() => onAcknowledge(evt.id)}
                  style={{
                    background: 'white',
                    color: '#991b1b',
                    fontWeight: 800,
                    border: 'none',
                    borderRadius: '8px',
                    padding: '0.6rem 1.2rem',
                    cursor: 'pointer',
                    minHeight: '48px',
                    fontSize: '0.9rem',
                  }}
                >
                  ✓ Acknowledge Emergency
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
