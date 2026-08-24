'use client';

/**
 * Organization & Supervisor Operations Portal (/organization)
 * Live fleet monitoring, active worker stations, task dispatcher, and supervisor assistance queue.
 */

import React from 'react';
import { LiveSessionMonitor } from '@/organization/components/LiveSessionMonitor';
import { AssistanceTicketQueue } from '@/organization/components/AssistanceTicketQueue';

export default function OrganizationPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Organization Header & Fleet Status */}
      <div className="glass-panel" style={{ padding: '2rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--org-emerald)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Supervisor & Fleet Operations
            </span>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem' }}>
              Acme Motors — Assembly Plant 1
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Department: Powertrain & Gearbox Integration • 12 Assigned Workers • 8 Active Workstations
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" className="btn btn-secondary">
              📊 Export Shift Telemetry
            </button>
            <button type="button" className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}>
              + Dispatch Task Assignment
            </button>
          </div>
        </div>

        {/* Fleet KPI Quick Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
          <div className="glass-card" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ON-TIME STEP COMPLETION</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--org-emerald)', marginTop: '0.25rem' }}>98.4%</div>
          </div>
          <div className="glass-card" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>AVG. MULTIMODAL CONFIDENCE</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--worker-cyan)', marginTop: '0.25rem' }}>94.2%</div>
          </div>
          <div className="glass-card" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ASSISTANCE RESOLUTION TIME</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '0.25rem' }}>1.4 min</div>
          </div>
          <div className="glass-card" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ERGONOMIC SAFETY SCORE</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--admin-purple)', marginTop: '0.25rem' }}>9.8 / 10</div>
          </div>
        </div>
      </div>

      {/* Main Monitoring & Assistance Queue Grid */}
      <AssistanceTicketQueue />
      <LiveSessionMonitor />
    </div>
  );
}
