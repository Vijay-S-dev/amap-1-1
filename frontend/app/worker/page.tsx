'use client';

/**
 * Worker Interactive Assembly Workstation (/worker)
 * Live execution page with step progression, multimodal intent simulator,
 * deterministic execution gate, and emergency assistance controls.
 */

import React, { useState, useEffect } from 'react';
import { MultimodalHUD } from '@/worker/components/MultimodalHUD';
import { WorkflowStepViewer } from '@/worker/components/WorkflowStepViewer';
import { AssistanceModal } from '@/worker/components/AssistanceModal';
import { TaskDetails, WorkSession } from '@/shared/types';
import { api } from '@/shared/api/client';

export default function WorkerPage() {
  const [session, setSession] = useState<WorkSession | null>(null);
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(1);
  const [isAssistanceOpen, setIsAssistanceOpen] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('Ready for assembly input.');
  const [isEmergencyStopped, setIsEmergencyStopped] = useState<boolean>(false);

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
      setCurrentStepIndex((prev) => prev + 1);
      setStatusMessage(`Advanced to Step ${currentStepIndex + 2}: ${task.steps[currentStepIndex + 1].title}`);
    } else {
      setStatusMessage('🎉 All workflow steps completed successfully!');
    }
  };

  const handlePreviousStep = () => {
    if (!task || currentStepIndex === 0) return;
    setCurrentStepIndex((prev) => prev - 1);
    setStatusMessage(`Returned to Step ${currentStepIndex}: ${task.steps[currentStepIndex - 1].title}`);
  };

  const handleActionTriggered = (actionName: string, strategy: string) => {
    if (actionName === 'confirm_action' || actionName === 'next_step') {
      handleNextStep();
    } else if (actionName === 'previous_step') {
      handlePreviousStep();
    } else if (actionName === 'pause_session') {
      setStatusMessage('⏸️ Work session paused via multimodal gesture.');
    } else if (actionName === 'emergency_stop') {
      handleEmergencyStop();
    }
  };

  const handleEmergencyStop = () => {
    setIsEmergencyStopped(true);
    setStatusMessage('🛑 EMERGENCY STOP ACTIVATED. Machinery locked. Supervisor dispatched.');
  };

  const handleResume = () => {
    setIsEmergencyStopped(false);
    setStatusMessage('Session resumed safely.');
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
      {/* Architectural Invariant Header Banner */}
      <div className="invariant-banner">
        <span>
          🛡️ <strong>Execution Safety Invariant:</strong>{' '}
          <code>Recognition ≠ Intent ≠ Authorization ≠ Execution</code>
        </span>
        <span style={{ color: 'var(--worker-cyan)' }}>Active Station: {session?.stationId || 'Assembly 4B'}</span>
      </div>

      {/* Emergency Stop Alert Bar if triggered */}
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
              <span>Assembly line paused. Safety interlocks engaged.</span>
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
          alignItems: 'center',
          gap: '0.75rem',
          fontSize: '0.9rem',
          borderLeft: '4px solid var(--worker-cyan)',
        }}
      >
        <span>💡</span>
        <span>
          <strong>Live Status:</strong> {statusMessage}
        </span>
      </div>

      {/* Main Assembly Workstation Grid */}
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

        <MultimodalHUD onActionTriggered={handleActionTriggered} dwellTimeMs={450} />
      </div>

      <AssistanceModal
        isOpen={isAssistanceOpen}
        onClose={() => setIsAssistanceOpen(false)}
        workSessionId={session?.id || 'ws-001'}
      />
    </div>
  );
}
