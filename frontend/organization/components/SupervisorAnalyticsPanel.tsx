'use client';

/**
 * Supervisor Operational Analytics & Throughput Panel (§ 15, § 16, § 20).
 * Displays real-time operational efficiency, assistance resolution speed,
 * and plant assembly throughput metrics.
 */

import React from 'react';

interface SupervisorAnalyticsPanelProps {
  analytics: {
    tasks_assigned_count: number;
    tasks_completed_count: number;
    tasks_in_progress_count: number;
    average_task_duration_minutes: number;
    workflow_completion_rate: number;
    total_assistance_requests: number;
    resolved_assistance_requests: number;
    average_resolution_time_minutes: number;
    emergency_stops_count: number;
  };
}

export function SupervisorAnalyticsPanel({ analytics }: SupervisorAnalyticsPanelProps) {
  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: 'var(--admin-purple)' }}>📊</span> Plant Operational Analytics & Throughput
        </h2>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Aggregated performance indicators derived from immutable factory work sessions
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
        {/* Completion Rate */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Workflow Completion Rate
          </span>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--org-emerald)', marginTop: '0.25rem' }}>
            {analytics.workflow_completion_rate}%
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {analytics.tasks_completed_count} of {analytics.tasks_assigned_count} dispatched tasks finished
          </span>
        </div>

        {/* Avg Task Duration */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Avg Assembly Cycle Duration
          </span>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--worker-cyan)', marginTop: '0.25rem' }}>
            {analytics.average_task_duration_minutes} <span style={{ fontSize: '1.2rem', fontWeight: 500 }}>mins</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Mean cycle time across all active stations
          </span>
        </div>

        {/* Assistance Resolution Time */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Assistance Resolution Speed
          </span>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '0.25rem' }}>
            {analytics.average_resolution_time_minutes} <span style={{ fontSize: '1.2rem', fontWeight: 500 }}>mins</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {analytics.resolved_assistance_requests} of {analytics.total_assistance_requests} requests closed
          </span>
        </div>

        {/* Safety & Emergency Stoppages */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Emergency Line Halts
          </span>
          <div
            style={{
              fontSize: '2.2rem',
              fontWeight: 800,
              color: analytics.emergency_stops_count > 0 ? 'var(--accent-rose)' : 'var(--text-primary)',
              marginTop: '0.25rem',
            }}
          >
            {analytics.emergency_stops_count}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Total safety interlock halts on record
          </span>
        </div>
      </div>
    </div>
  );
}
