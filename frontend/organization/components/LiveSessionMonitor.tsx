'use client';

/**
 * Organization Live Session Monitor Component
 * Real-time station telemetry, worker active tasks, modality usage, and productivity metrics.
 */

import React from 'react';

interface StationTelemetry {
  stationId: string;
  stationName: string;
  workerName: string;
  currentTask: string;
  stepProgress: string;
  activeModality: string;
  dwellTimeMs: number;
  status: 'optimal' | 'warning' | 'paused';
}

const DEMO_STATIONS: StationTelemetry[] = [
  {
    stationId: 'st-4b',
    stationName: 'Station 4B (Robotic Feeder)',
    workerName: 'Alex Morgan',
    currentTask: 'High-Precision Gearbox Assembly',
    stepProgress: 'Step 2 / 4',
    activeModality: 'Gesture (thumbs_up)',
    dwellTimeMs: 450,
    status: 'optimal',
  },
  {
    stationId: 'st-2a',
    stationName: 'Station 2A (Sub-assembly)',
    workerName: 'Jordan Lee',
    currentTask: 'Planetary Housing Torque Check',
    stepProgress: 'Step 3 / 5',
    activeModality: 'Voice (torque check)',
    dwellTimeMs: 600,
    status: 'warning',
  },
  {
    stationId: 'st-1c',
    stationName: 'Station 1C (Electronics QA)',
    workerName: 'Samira Chen',
    currentTask: 'Circuit Board Continuity Inspection',
    stepProgress: 'Step 4 / 4',
    activeModality: 'Touch / UI',
    dwellTimeMs: 300,
    status: 'optimal',
  },
];

export function LiveSessionMonitor() {
  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--org-emerald)' }}>●</span> Real-Time Station Telemetry
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Monitoring 3 active workstations across Assembly Line 1
          </span>
        </div>
        <span className="badge badge-emerald">3 Active Sessions</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
        {DEMO_STATIONS.map((station) => (
          <div
            key={station.stationId}
            className="glass-card"
            style={{
              borderLeft: `4px solid ${
                station.status === 'optimal' ? 'var(--org-emerald)' : 'var(--accent-amber)'
              }`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
              <div>
                <strong style={{ fontSize: '1.05rem', color: 'white', display: 'block' }}>{station.stationName}</strong>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Worker: {station.workerName}</span>
              </div>
              <span
                className={`badge ${station.status === 'optimal' ? 'badge-emerald' : 'badge-rose'}`}
                style={{ fontSize: '0.7rem' }}
              >
                {station.status === 'optimal' ? 'OPTIMAL' : 'ATTENTION'}
              </span>
            </div>

            <div style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Task: </span>
              <strong>{station.currentTask}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
              <span>Progress: <strong style={{ color: 'var(--worker-cyan)' }}>{station.stepProgress}</strong></span>
              <span>Modality: <strong>{station.activeModality}</strong></span>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn btn-secondary" style={{ flex: 1, minHeight: '36px', fontSize: '0.8rem' }}>
                View Stream
              </button>
              <button type="button" className="btn btn-secondary" style={{ flex: 1, minHeight: '36px', fontSize: '0.8rem', borderColor: 'var(--org-emerald)' }}>
                Adapt Settings
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
