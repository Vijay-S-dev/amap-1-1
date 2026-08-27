'use client';

/**
 * AMAP Organization Department & Line Governance Panel
 * Allows supervisors to monitor departments, active workstations, and assign shift workflows.
 */

import React, { useState } from 'react';

interface DepartmentInfo {
  id: string;
  name: string;
  activeStations: number;
  totalWorkers: number;
  activeWorkflow: string;
  status: 'optimal' | 'attention' | 'maintenance';
}

const INITIAL_DEPARTMENTS: DepartmentInfo[] = [
  {
    id: 'dept_1',
    name: 'Powertrain & Gearbox Integration',
    activeStations: 8,
    totalWorkers: 12,
    activeWorkflow: 'Inverter Sub-Assembly Alpha (v1)',
    status: 'optimal',
  },
  {
    id: 'dept_2',
    name: 'Chassis & Structural Welding',
    activeStations: 6,
    totalWorkers: 8,
    activeWorkflow: 'Robotic Jig Calibration (v2)',
    status: 'optimal',
  },
  {
    id: 'dept_3',
    name: 'Quality Control & Diagnostics',
    activeStations: 4,
    totalWorkers: 6,
    activeWorkflow: 'End-of-Line Dielectric Stress (v1)',
    status: 'attention',
  },
];

export function DepartmentGovernancePanel() {
  const [departments, setDepartments] = useState<DepartmentInfo[]>(INITIAL_DEPARTMENTS);

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>🏭</span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>Department & Line Governance</h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Multi-department operational overview, active line assignments, and capacity allocation.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          style={{ fontSize: '0.85rem' }}
        >
          + Add Department
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        {departments.map((dept) => (
          <div
            key={dept.id}
            className="glass-card"
            style={{
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderTop:
                dept.status === 'optimal'
                  ? '3px solid var(--org-emerald)'
                  : '3px solid var(--accent-amber)',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {dept.name}
                </h4>
                <span
                  style={{
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    background:
                      dept.status === 'optimal'
                        ? 'rgba(16, 185, 129, 0.15)'
                        : 'rgba(245, 158, 11, 0.15)',
                    color:
                      dept.status === 'optimal'
                        ? 'var(--org-emerald)'
                        : 'var(--accent-amber)',
                  }}
                >
                  {dept.status}
                </span>
              </div>

              <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                  <span>Active Stations:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{dept.activeStations} Online</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                  <span>Shift Workers:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{dept.totalWorkers} Assigned</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                  <span>Active Workflow:</span>
                  <span style={{ color: 'var(--worker-cyan)', fontSize: '0.8rem', textAlign: 'right' }}>
                    {dept.activeWorkflow}
                  </span>
                </div>
              </div>
            </div>

            <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ flex: 1, padding: '0.4rem 0.6rem', fontSize: '0.75rem' }}
              >
                Line Settings
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ flex: 1, padding: '0.4rem 0.6rem', fontSize: '0.75rem', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
              >
                Inspect Telemetry
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
