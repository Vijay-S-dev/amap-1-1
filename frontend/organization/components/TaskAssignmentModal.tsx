'use client';

/**
 * Task Dispatcher & Assignment Modal (§ 9, § 10, § 25).
 * Allows supervisors to assign available assembly tasks to eligible workers.
 * Enforces organization isolation and validates availability server-side.
 */

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';

interface TaskAssignmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  workers: Array<{ worker_profile_id: string; full_name: string; status: string }>;
  preselectedWorkerId?: string | null;
  onTaskAssigned: () => void;
}

export function TaskAssignmentModal({
  isOpen,
  onClose,
  workers,
  preselectedWorkerId,
  onTaskAssigned,
}: TaskAssignmentModalProps) {
  const [tasks, setTasks] = useState<any[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>(preselectedWorkerId || '');
  const [notes, setNotes] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (preselectedWorkerId) {
      setSelectedWorkerId(preselectedWorkerId);
    } else if (workers.length > 0 && !selectedWorkerId) {
      setSelectedWorkerId(workers[0].worker_profile_id);
    }
  }, [preselectedWorkerId, workers, selectedWorkerId]);

  useEffect(() => {
    if (!isOpen) return;

    api
      .getSupervisorTasks()
      .then((data) => {
        setTasks(data);
        if (data.length > 0) setSelectedTaskId(data[0].id);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load assignable tasks');
      });
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTaskId || !selectedWorkerId) {
      setError('Please select both a worker and an assembly task.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const res = await api.assignSupervisorTask({
        task_id: selectedTaskId,
        worker_profile_id: selectedWorkerId,
        notes: notes.trim() || undefined,
      });

      setSuccessMessage(res.message || 'Task dispatched successfully!');
      setTimeout(() => {
        setSuccessMessage(null);
        onTaskAssigned();
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.message || 'Failed to assign task');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="task-assignment-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(11, 15, 25, 0.85)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '560px',
          borderRadius: '24px',
          padding: '2rem',
          border: '1px solid var(--surface-glass-border)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--org-emerald)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Dispatch Center
            </span>
            <h2 id="task-assignment-title" style={{ fontSize: '1.4rem', fontWeight: 800, color: 'white', marginTop: '0.2rem' }}>
              Assign Assembly Task
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            aria-label="Close task assignment"
            style={{ minHeight: '40px', minWidth: '40px', padding: '0.4rem', borderRadius: '50%' }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div role="alert" style={{ background: 'rgba(244, 63, 94, 0.2)', border: '1px solid var(--accent-rose)', padding: '0.75rem', borderRadius: '8px', color: '#fca5a5', marginBottom: '1rem', fontSize: '0.85rem' }}>
            ⚠️ {error}
          </div>
        )}

        {successMessage && (
          <div role="status" style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid var(--org-emerald)', padding: '0.75rem', borderRadius: '8px', color: '#6ee7b7', marginBottom: '1rem', fontSize: '0.85rem' }}>
            ✓ {successMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Worker Select */}
          <div>
            <label htmlFor="worker-select" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.4rem' }}>
              Select Worker Profile:
            </label>
            <select
              id="worker-select"
              value={selectedWorkerId}
              onChange={(e) => setSelectedWorkerId(e.target.value)}
              className="glass-card"
              style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', color: 'white', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--surface-glass-border)', fontSize: '0.9rem' }}
            >
              {workers.map((w) => (
                <option key={w.worker_profile_id} value={w.worker_profile_id}>
                  {w.full_name} ({w.status})
                </option>
              ))}
            </select>
          </div>

          {/* Task Select */}
          <div>
            <label htmlFor="task-select" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.4rem' }}>
              Select Assembly Task:
            </label>
            {tasks.length === 0 ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', padding: '0.5rem 0' }}>
                No active tasks found in organization catalog.
              </div>
            ) : (
              <select
                id="task-select"
                value={selectedTaskId}
                onChange={(e) => setSelectedTaskId(e.target.value)}
                className="glass-card"
                style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', color: 'white', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--surface-glass-border)', fontSize: '0.9rem' }}
              >
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Supervisor Notes */}
          <div>
            <label htmlFor="task-notes" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.4rem' }}>
              Special Supervisor Instructions (Optional):
            </label>
            <textarea
              id="task-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Prioritize high-precision torque alignment on Step 2..."
              rows={3}
              className="glass-card"
              style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', color: 'white', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--surface-glass-border)', fontSize: '0.85rem', resize: 'none' }}
            />
          </div>

          {/* Modal Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              style={{ minHeight: '48px', padding: '0.6rem 1.5rem' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || tasks.length === 0}
              className="btn btn-primary"
              style={{
                minHeight: '48px',
                padding: '0.6rem 1.5rem',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              }}
            >
              {loading ? 'Dispatching...' : 'Dispatch Task Assignment →'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
