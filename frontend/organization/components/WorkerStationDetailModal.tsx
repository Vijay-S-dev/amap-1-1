'use client';

/**
 * AMAP Organization Worker Station Deep-Dive Telemetry Modal
 * Provides real-time modal telemetry view for active workstation cameras, dwell smoothing, and voice metrics.
 */

import React from 'react';

interface WorkerStationDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  workerName?: string;
  stationId?: string;
  badgeNumber?: string;
}

export function WorkerStationDetailModal({
  isOpen,
  onClose,
  workerName = 'Alex Morgan',
  stationId = 'STN-04',
  badgeNumber = 'WRK-1048',
}: WorkerStationDetailModalProps) {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '700px',
          padding: '2rem',
          borderRadius: '24px',
          border: '1px solid var(--surface-glass-border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--surface-glass-border)', paddingBottom: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--worker-cyan)', fontWeight: 700, textTransform: 'uppercase' }}>
              Station Telemetry Deep Dive
            </span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '0.2rem' }}>
              {workerName} — {stationId}
            </h3>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Badge: {badgeNumber} • Workflow: Inverter Sub-Assembly Alpha (Step 2/3)
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: '1.5rem',
              cursor: 'pointer',
            }}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Live Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', margin: '1.5rem 0' }}>
          <div className="glass-card">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OPTICAL GESTURE CONFIDENCE</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--worker-cyan)', marginTop: '0.2rem' }}>96.2%</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Active: Thumbs Up</span>
          </div>
          <div className="glass-card">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ACOUSTIC SNR / CLARITY</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--org-emerald)', marginTop: '0.2rem' }}>22.4 dB</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Voice Gate: 14.0 dB</span>
          </div>
          <div className="glass-card">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>DWELL HOLD TIME</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--admin-purple)', marginTop: '0.2rem' }}>650 ms</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Auto-Adapted (+150ms)</span>
          </div>
        </div>

        {/* Diagnostic Notes */}
        <div
          style={{
            background: 'var(--surface-card)',
            padding: '1rem',
            borderRadius: '12px',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            marginBottom: '1.5rem',
          }}
        >
          <strong style={{ color: 'var(--text-primary)' }}>Personalization Invariant Note:</strong>
          <p style={{ marginTop: '0.3rem' }}>
            Worker is utilizing adaptive Exponential Moving Average (EMA) low-pass filtering on optical pointer landmarks to dampen mild motor tremors. No safety interlock bypasses permitted.
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
            onClick={onClose}
          >
            Direct Audio Intercom
          </button>
        </div>
      </div>
    </div>
  );
}
