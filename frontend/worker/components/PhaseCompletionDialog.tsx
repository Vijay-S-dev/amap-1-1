'use client';

/**
 * Phase Completion Dialog (frontend/worker/components/PhaseCompletionDialog.tsx)
 *
 * Interactive success dialog shown when the CURRENT assignment is genuinely
 * completed in the backend (task_results row recorded via
 * POST /tasks/assignments/{id}/complete) — never merely because the UI
 * reached the last displayed step.
 *
 * - Tied to one specific assignment id (completing one phase never marks
 *   other assignments complete).
 * - Shown again after refresh / re-login until the worker acknowledges it
 *   (the completed STATE itself lives in PostgreSQL; the acknowledgement is
 *   a UI preference only).
 * - Accessible: role=dialog + aria-modal, focus moves to Continue on open,
 *   Escape activates Continue.
 */

import React, { useEffect, useRef } from 'react';
import { t, tParams } from '@/shared/i18n/languages';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';

export interface PhaseCompletionInfo {
  assignmentId: string;
  taskName: string;
  completedSteps: number;
  totalSteps: number;
  outcome: string;
  durationSeconds?: number | null;
}

interface PhaseCompletionDialogProps {
  completion: PhaseCompletionInfo | null;
  onContinue: () => void;
}

export function PhaseCompletionDialog({ completion, onContinue }: PhaseCompletionDialogProps) {
  const { language, announce, playAudioCue } = useAccessibility();
  const continueRef = useRef<HTMLButtonElement>(null);

  const isOpen = Boolean(completion);

  useEffect(() => {
    if (isOpen && completion) {
      // Move focus to the primary action for keyboard / switch users.
      continueRef.current?.focus();
      announce(
        `${t('phase_complete_title', language)}. ${tParams('phase_complete_steps', language, {
          done: completion.completedSteps,
          total: completion.totalSteps,
        })}`
      );
      playAudioCue('confirm');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, completion?.assignmentId]);

  if (!isOpen || !completion) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(4, 8, 16, 0.72)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 120,
        padding: '1.5rem',
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          onContinue();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="phase-complete-title"
        className="glass-panel"
        style={{
          maxWidth: '520px',
          width: '100%',
          padding: '2.5rem 2.25rem',
          borderRadius: '24px',
          textAlign: 'center',
          border: '2px solid var(--org-emerald)',
          boxShadow: '0 24px 64px rgba(16, 185, 129, 0.18)',
        }}
      >
        {/* Success mark */}
        <div
          style={{
            width: '84px',
            height: '84px',
            margin: '0 auto 1.25rem auto',
            borderRadius: '50%',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '3px solid var(--org-emerald)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '2.6rem',
            color: 'var(--org-emerald)',
            animation: 'amap-pulse 1.6s ease-in-out infinite',
          }}
          aria-hidden="true"
        >
          ✓
        </div>

        <h2 id="phase-complete-title" style={{ fontSize: '1.9rem', fontWeight: 800, color: 'var(--org-emerald)' }}>
          {t('phase_complete_title', language)}
        </h2>

        <p style={{ color: 'var(--text-secondary)', fontSize: '1.02rem', margin: '0.75rem 0 0.35rem 0' }}>
          {t('phase_complete_body', language)}
        </p>
        <p style={{ color: 'var(--text-primary)', fontSize: '1.05rem', fontWeight: 700, margin: '0 0 1.25rem 0' }}>
          {completion.taskName}
        </p>

        {/* Real result facts from PostgreSQL */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            margin: '0 auto 1.75rem auto',
            maxWidth: '420px',
          }}
        >
          <div className="glass-panel" style={{ padding: '0.85rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>
              {t('workstation_completed', language)}
            </span>
            <strong style={{ fontSize: '1.15rem', color: 'var(--worker-cyan)' }}>
              {tParams('phase_complete_steps', language, {
                done: completion.completedSteps,
                total: completion.totalSteps,
              })}
            </strong>
          </div>
          <div className="glass-panel" style={{ padding: '0.85rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>Outcome</span>
            <strong
              style={{
                fontSize: '1.05rem',
                color: completion.outcome === 'completed' ? 'var(--org-emerald)' : 'var(--accent-amber)',
                textTransform: 'uppercase',
              }}
            >
              {completion.outcome}
            </strong>
          </div>
          {completion.durationSeconds != null && (
            <div className="glass-panel" style={{ padding: '0.85rem', borderRadius: '12px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>Duration</span>
              <strong style={{ fontSize: '1.15rem', color: 'var(--text-primary)' }}>
                {Math.round(completion.durationSeconds)}s
              </strong>
            </div>
          )}
        </div>

        <button
          ref={continueRef}
          type="button"
          onClick={onContinue}
          className="btn btn-primary"
          style={{ minHeight: '56px', padding: '0.9rem 3rem', fontSize: '1.05rem', fontWeight: 800 }}
        >
          {t('phase_complete_continue', language)} →
        </button>
      </div>
    </div>
  );
}

export default PhaseCompletionDialog;
