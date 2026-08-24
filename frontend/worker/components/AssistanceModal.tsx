'use client';

/**
 * Worker Assistance Modal Component
 * Allows workers to submit priority-tagged help requests and report assembly difficulties.
 */

import React, { useState } from 'react';
import { AssistancePriority } from '@/shared/types';
import { api } from '@/shared/api/client';

interface AssistanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  workSessionId: string;
}

export function AssistanceModal({ isOpen, onClose, workSessionId }: AssistanceModalProps) {
  const [priority, setPriority] = useState<AssistancePriority>('high');
  const [category, setCategory] = useState<string>('part_misalignment');
  const [description, setDescription] = useState<string>('');
  const [submitted, setSubmitted] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.requestAssistance({
      workSessionId,
      priority,
      category,
      description: description || 'Assistance requested at station.',
    });
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      onClose();
    }, 1500);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="assistance-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
    >
      <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '2rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h2 id="assistance-modal-title" style={{ fontSize: '1.3rem', fontWeight: 800 }}>
            🙋 Request Supervisor Assistance
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="btn btn-secondary"
            style={{ minHeight: '36px', padding: '0.25rem 0.65rem' }}
          >
            ✕
          </button>
        </div>

        {submitted ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
            <h3 style={{ color: 'var(--org-emerald)', marginBottom: '0.25rem' }}>Assistance Dispatched</h3>
            <p style={{ color: 'var(--text-secondary)' }}>Supervisor on duty has been notified with high priority.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Priority Selector */}
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Urgency Priority
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                {(['low', 'medium', 'high', 'critical'] as AssistancePriority[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPriority(p)}
                    className="btn btn-secondary"
                    style={{
                      minHeight: '40px',
                      textTransform: 'capitalize',
                      borderColor: priority === p ? 'var(--worker-cyan)' : 'transparent',
                      background: priority === p ? 'rgba(0, 242, 254, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                      color: priority === p ? 'var(--worker-cyan)' : 'var(--text-primary)',
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* Category Selector */}
            <div>
              <label htmlFor="assistance-category" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Difficulty Category
              </label>
              <select
                id="assistance-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'var(--surface-card)',
                  color: 'white',
                  border: '1px solid var(--surface-glass-border)',
                  fontFamily: 'var(--font-main)',
                  fontSize: '0.95rem',
                }}
              >
                <option value="part_misalignment">Part Tolerance / Alignment Issue</option>
                <option value="tool_malfunction">Tool / Sensor Calibration Error</option>
                <option value="physical_fatigue">Ergonomic / Physical Fatigue</option>
                <option value="guidance_clarification">Step Instruction Clarification</option>
              </select>
            </div>

            {/* Description Textarea */}
            <div>
              <label htmlFor="assistance-desc" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Details for Supervisor (Optional)
              </label>
              <textarea
                id="assistance-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Describe specific friction or assistance needed..."
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'var(--surface-card)',
                  color: 'white',
                  border: '1px solid var(--surface-glass-border)',
                  fontFamily: 'var(--font-main)',
                  fontSize: '0.95rem',
                  resize: 'none',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary" style={{ flex: 1 }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 2 }}>
                Dispatch Request
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
