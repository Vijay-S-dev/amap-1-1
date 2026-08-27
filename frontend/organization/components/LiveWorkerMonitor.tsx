'use client';

/**
 * Live Worker Monitor Component (§ 3, § 11, § 13, § 21).
 * Displays real-time operational status, active task progress, interaction health,
 * and session telemetry for all workers in the supervisor's organization.
 */

import React, { useState } from 'react';

interface WorkerItem {
  worker_profile_id: string;
  user_id: string;
  full_name: string;
  email: string;
  status: string; // AVAILABLE | WORKING | PAUSED | ASSISTANCE_REQUESTED | COMPLETED | OFFLINE
  current_task_id?: string;
  current_task_name?: string;
  current_assignment_id?: string;
  progress_percent: number;
  current_step_title?: string;
  current_step_number?: number;
  total_steps?: number;
  interaction_mode: string;
  interaction_health: {
    gesture_ready: boolean;
    voice_ready: boolean;
    multimodal_ready: boolean;
  };
  active_session_id?: string;
  session_duration_seconds: number;
  has_open_assistance: boolean;
  is_emergency_stop: boolean;
}

interface LiveWorkerMonitorProps {
  workers: WorkerItem[];
  onSelectWorker: (workerId: string) => void;
  onDispatchTask: (workerId: string) => void;
}

export function LiveWorkerMonitor({ workers, onSelectWorker, onDispatchTask }: LiveWorkerMonitorProps) {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  const filteredWorkers = workers.filter((w) => {
    if (filterStatus === 'ALL') return true;
    return w.status === filterStatus;
  });

  const getStatusBadge = (status: string, isEmergency: boolean) => {
    if (isEmergency) {
      return (
        <span className="badge badge-rose" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          🛑 EMERGENCY STOP
        </span>
      );
    }
    switch (status) {
      case 'AVAILABLE':
        return (
          <span className="badge badge-emerald" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            🟢 AVAILABLE
          </span>
        );
      case 'WORKING':
        return (
          <span className="badge badge-cyan" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            ⚡ WORKING
          </span>
        );
      case 'PAUSED':
        return (
          <span className="badge badge-amber" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            ⏸️ PAUSED
          </span>
        );
      case 'ASSISTANCE_REQUESTED':
        return (
          <span className="badge badge-rose" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            ⚠️ ASSISTANCE
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="badge badge-purple" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            ✓ COMPLETED
          </span>
        );
      default:
        return (
          <span className="badge badge-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            ⚪ OFFLINE
          </span>
        );
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds <= 0) return '—';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hrs > 0) return `${hrs}h ${mins}m`;
    return `${mins}m`;
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      {/* Header & Filter Controls */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--org-emerald)' }}>●</span> Live Worker Fleet Telemetry
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Real-time station monitoring, task progress, and accessibility interaction health
          </span>
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {['ALL', 'AVAILABLE', 'WORKING', 'ASSISTANCE_REQUESTED', 'OFFLINE'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setFilterStatus(st)}
              className={`btn ${filterStatus === st ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                fontSize: '0.75rem',
                padding: '0.4rem 0.8rem',
                minHeight: '38px',
                borderRadius: '8px',
              }}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Zero State */}
      {filteredWorkers.length === 0 ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>👥</span>
          <strong>No workers found matching the selected filter.</strong>
          <p style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Workers assigned to your organization will appear here automatically upon activation.
          </p>
        </div>
      ) : (
        /* Worker Grid / Table */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: '1rem' }}>
          {filteredWorkers.map((worker) => (
            <div
              key={worker.worker_profile_id}
              className="glass-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '1.25rem',
                borderRadius: '14px',
                borderLeft: `4px solid ${
                  worker.is_emergency_stop
                    ? 'var(--accent-rose)'
                    : worker.status === 'WORKING'
                    ? 'var(--worker-cyan)'
                    : worker.status === 'AVAILABLE'
                    ? 'var(--org-emerald)'
                    : 'var(--surface-glass-border)'
                }`,
              }}
            >
              {/* Top Row: Worker Name & Status */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
                  <div>
                    <strong style={{ fontSize: '1.1rem', color: 'white', display: 'block' }}>
                      {worker.full_name}
                    </strong>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{worker.email}</span>
                  </div>
                  {getStatusBadge(worker.status, worker.is_emergency_stop)}
                </div>

                {/* Active Task Info */}
                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.75rem', borderRadius: '8px', marginBottom: '0.75rem' }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                    Current Task:
                  </div>
                  <strong style={{ fontSize: '0.95rem', color: worker.current_task_name ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                    {worker.current_task_name || 'No active task assigned'}
                  </strong>

                  {worker.current_task_name && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                        <span>Progress: {worker.current_step_title || 'In progress'}</span>
                        <strong style={{ color: 'var(--worker-cyan)' }}>{worker.progress_percent}%</strong>
                      </div>
                      <div
                        style={{
                          height: '6px',
                          background: 'rgba(255, 255, 255, 0.1)',
                          borderRadius: '3px',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${Math.min(100, Math.max(5, worker.progress_percent))}%`,
                            background: 'linear-gradient(90deg, #06b6d4, #10b981)',
                            borderRadius: '3px',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Telemetry Row: Mode & Session */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                  <span>
                    Mode: <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{worker.interaction_mode}</strong>
                  </span>
                  <span>
                    Session: <strong style={{ color: 'var(--text-primary)' }}>{formatDuration(worker.session_duration_seconds)}</strong>
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => onSelectWorker(worker.worker_profile_id)}
                  className="btn btn-secondary"
                  style={{ flex: 1, minHeight: '44px', fontSize: '0.85rem', padding: '0.5rem' }}
                >
                  🔍 Inspect Details
                </button>
                {worker.status === 'AVAILABLE' && (
                  <button
                    type="button"
                    onClick={() => onDispatchTask(worker.worker_profile_id)}
                    className="btn btn-primary"
                    style={{
                      flex: 1,
                      minHeight: '44px',
                      fontSize: '0.85rem',
                      padding: '0.5rem',
                      background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    }}
                  >
                    + Assign Task
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
