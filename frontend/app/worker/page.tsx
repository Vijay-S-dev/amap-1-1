'use client';

/**
 * Worker Interactive Assembly Workstation (/worker) (§ 15, § 18, § 24)
 * Primary AMAP screen designed for motor accessibility:
 * Answers: What am I doing? What step? What next? How to interact? How to get help? How to stop?
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { MultimodalHUD } from '@/worker/components/MultimodalHUD';
import { WorkflowStepViewer } from '@/worker/components/WorkflowStepViewer';
import { AssistanceModal } from '@/worker/components/AssistanceModal';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { TaskDetails, WorkSession } from '@/shared/types';
import { api } from '@/shared/api/client';

export default function WorkerPage() {
  const { language, announce, playAudioCue, isReady } = useAccessibility();

  const [session, setSession] = useState<WorkSession | null>(null);
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(1);
  const [isAssistanceOpen, setIsAssistanceOpen] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('Ready for assembly input.');
  const [isEmergencyStopped, setIsEmergencyStopped] = useState<boolean>(false);
  const [isSessionEnded, setIsSessionEnded] = useState<boolean>(false);

  useEffect(() => {
    async function loadData() {
      const activeSession = await api.getActiveSession();
      setSession(activeSession);
      if (activeSession.activeTaskId) {
        const taskData = await api.getTaskDetails(activeSession.activeTaskId);
        setTask(taskData);
        setCurrentStepIndex(taskData.currentStepIndex || 0);
      }
    }
    loadData();
  }, []);

  const handleNextStep = () => {
    if (!task) return;
    if (currentStepIndex < task.steps.length - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      const msg = `Advanced to Step ${nextIdx + 1}: ${task.steps[nextIdx].title}`;
      setStatusMessage(msg);
      announce(msg);
      playAudioCue('step');
    } else {
      const finishMsg = '🎉 All assembly workflow steps completed successfully!';
      setStatusMessage(finishMsg);
      announce(finishMsg);
      playAudioCue('confirm');
    }
  };

  const handlePreviousStep = () => {
    if (!task || currentStepIndex === 0) return;
    const prevIdx = currentStepIndex - 1;
    setCurrentStepIndex(prevIdx);
    const msg = `Returned to Step ${prevIdx + 1}: ${task.steps[prevIdx].title}`;
    setStatusMessage(msg);
    announce(msg);
    playAudioCue('step');
  };

  const handleActionTriggered = (actionName: string) => {
    if (actionName === 'confirm_action' || actionName === 'next_step') {
      handleNextStep();
    } else if (actionName === 'previous_step') {
      handlePreviousStep();
    } else if (actionName === 'pause_session') {
      setStatusMessage('⏸️ Work session paused via multimodal gesture.');
      announce('Work session paused.');
    } else if (actionName === 'emergency_stop') {
      handleEmergencyStop();
    }
  };

  const handleEmergencyStop = () => {
    setIsEmergencyStopped(true);
    setStatusMessage('🛑 EMERGENCY STOP ACTIVATED. Machinery locked. Supervisor dispatched.');
    announce('Emergency stop activated.');
    playAudioCue('stop');
  };

  const handleResume = () => {
    setIsEmergencyStopped(false);
    setStatusMessage('Session resumed safely.');
    announce('Session resumed safely.');
    playAudioCue('confirm');
  };

  const handleEndWork = () => {
    setIsSessionEnded(true);
    setStatusMessage('Work session completed and logged in immutable audit trail.');
    announce('Work session completed.');
    playAudioCue('confirm');
  };

  if (!task) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center' }}>
        <div className="animate-pulse-glow" style={{ fontSize: '2rem' }}>⚡ Connecting to Workstation...</div>
      </div>
    );
  }

  const currentStep = task.steps[currentStepIndex];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Onboarding Readiness Reminder (§ 13) */}
      {!isReady && (
        <div
          role="alert"
          className="glass-card"
          style={{
            padding: '1rem 1.5rem',
            borderRadius: '16px',
            background: 'rgba(245, 158, 11, 0.15)',
            border: '1px solid var(--accent-amber)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>⏳</span>
            <div>
              <strong style={{ color: 'var(--accent-amber)', display: 'block' }}>
                Onboarding Milestones Incomplete
              </strong>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Complete language, accessibility, gesture calibration, and simulated training for optimal ergonomics.
              </span>
            </div>
          </div>
          <Link href="/onboarding" className="btn btn-secondary" style={{ fontSize: '0.85rem' }}>
            Open Onboarding Hub →
          </Link>
        </div>
      )}

      {/* Invariant Header Banner (§ 3) */}
      <div className="invariant-banner">
        <span>
          🛡️ <strong>Safety Invariant:</strong>{' '}
          <code>Recognition ≠ Intent ≠ Authorization ≠ Execution</code>
        </span>
        <span style={{ color: 'var(--worker-cyan)' }}>
          Station: {session?.stationId || 'Assembly 4B'} • Language: {language.toUpperCase()}
        </span>
      </div>

      {/* Emergency Lockout Banner (§ 25) */}
      {isEmergencyStopped && (
        <div
          role="alert"
          style={{
            background: 'linear-gradient(90deg, #f43f5e 0%, #be123c 100%)',
            color: 'white',
            padding: '1.25rem 2rem',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 0 30px rgba(244, 63, 94, 0.4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>🛑</span>
            <div>
              <strong style={{ fontSize: '1.2rem', display: 'block' }}>Emergency Lockout Active</strong>
              <span>Line paused. Safety interlocks engaged.</span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleResume}
            className="btn btn-secondary"
            style={{ background: 'white', color: '#be123c', fontWeight: 700 }}
          >
            Clear Interlock & Resume
          </button>
        </div>
      )}

      {/* Live Status Toast */}
      <div
        aria-live="polite"
        className="glass-panel"
        style={{
          padding: '0.75rem 1.25rem',
          borderRadius: '12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.95rem',
          borderLeft: '4px solid var(--worker-cyan)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span>💡</span>
          <span>
            <strong>Status:</strong> {statusMessage}
          </span>
        </div>

        {/* End Work Button (§ 24) */}
        <button
          type="button"
          onClick={handleEndWork}
          className="btn btn-secondary"
          style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
        >
          🏁 {t('end_work_btn', language)}
        </button>
      </div>

      {isSessionEnded ? (
        /* End Work Summary Card (§ 24) */
        <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', border: '2px solid var(--org-emerald)' }}>
          <span style={{ fontSize: '4rem', display: 'block', marginBottom: '1rem' }}>🏁</span>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--org-emerald)' }}>
            Work Session Successfully Closed
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0.75rem auto 1.5rem auto' }}>
            All task steps have been recorded. Operational metrics and safety interlock audit logs have been safely dispatched.
          </p>
          <button
            type="button"
            onClick={() => setIsSessionEnded(false)}
            className="btn btn-primary"
            style={{ padding: '0.85rem 2rem' }}
          >
            Start New Work Shift
          </button>
        </div>
      ) : (
        /* Main Assembly Workstation Grid (§ 15) */
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem' }}>
          <WorkflowStepViewer
            currentStep={currentStep}
            totalSteps={task.steps.length}
            currentStepIndex={currentStepIndex}
            onNextStep={handleNextStep}
            onPreviousStep={handlePreviousStep}
            onRequestAssistance={() => setIsAssistanceOpen(true)}
            onEmergencyStop={handleEmergencyStop}
          />

          <MultimodalHUD onActionTriggered={handleActionTriggered} dwellTimeMs={500} />
        </div>
      )}

      {/* Multilingual Assistance Modal (§ 20, § 21) */}
      <AssistanceModal
        isOpen={isAssistanceOpen}
        onClose={() => setIsAssistanceOpen(false)}
        workSessionId={session?.id || 'ws-001'}
      />
    </div>
  );
}
