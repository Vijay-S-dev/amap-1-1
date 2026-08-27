'use client';

/**
 * Supervisor Summary KPI Cards (§ 2, § 20).
 * Displays real-time operational capacity, active worker states, and throughput metrics.
 * 100% Real Database Derived (No Mock Statistics).
 */

import React from 'react';

interface SupervisorSummaryKPIsProps {
  summary: {
    active_workers_count: number;
    available_workers_count: number;
    workers_in_task_count: number;
    workers_requesting_assistance_count: number;
    completed_tasks_count: number;
    in_progress_tasks_count: number;
    failed_tasks_count: number;
    current_workload_percent: number;
    emergency_stops_active: number;
  };
}

export function SupervisorSummaryKPIs({ summary }: SupervisorSummaryKPIsProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '1rem',
      }}
    >
      {/* 1. Active Workers */}
      <div className="glass-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Active Workers
        </span>
        <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--org-emerald)', marginTop: '0.25rem' }}>
          {summary.active_workers_count}
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {summary.available_workers_count} Available for dispatch
        </span>
      </div>

      {/* 2. In-Task Workers */}
      <div className="glass-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Executing Tasks
        </span>
        <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--worker-cyan)', marginTop: '0.25rem' }}>
          {summary.workers_in_task_count}
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {summary.in_progress_tasks_count} Active workflow lines
        </span>
      </div>

      {/* 3. Assistance Queue */}
      <div
        className="glass-card"
        style={{
          padding: '1.25rem',
          textAlign: 'center',
          borderLeft: summary.workers_requesting_assistance_count > 0 ? '4px solid var(--accent-amber)' : undefined,
        }}
      >
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Assistance Requests
        </span>
        <div
          style={{
            fontSize: '2rem',
            fontWeight: 800,
            color: summary.workers_requesting_assistance_count > 0 ? 'var(--accent-amber)' : 'var(--text-secondary)',
            marginTop: '0.25rem',
          }}
        >
          {summary.workers_requesting_assistance_count}
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {summary.emergency_stops_active > 0 ? `⚠️ ${summary.emergency_stops_active} Emergency Halts` : 'All stations clear'}
        </span>
      </div>

      {/* 4. Completed Tasks */}
      <div className="glass-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Completed Tasks
        </span>
        <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--admin-purple)', marginTop: '0.25rem' }}>
          {summary.completed_tasks_count}
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {summary.failed_tasks_count} Failed / blocked
        </span>
      </div>

      {/* 5. Station Workload */}
      <div className="glass-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Line Capacity Workload
        </span>
        <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
          {summary.current_workload_percent}%
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Active plant utilization
        </span>
      </div>
    </div>
  );
}
