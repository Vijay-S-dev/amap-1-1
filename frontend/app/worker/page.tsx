'use client';

/**
 * Worker Interactive Assembly Workstation (/worker) (§ 15, § 18, § 24)
 * Primary AMAP screen designed for motor accessibility:
 * Answers: What am I doing? What step? What next? How to interact? How to get help? How to stop?
 */

import React, { useState, useEffect, useRef } from 'react';
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
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [workflowAssignmentId, setWorkflowAssignmentId] = useState<string | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isAssistanceOpen, setIsAssistanceOpen] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('Ready for assembly input.');
  const [isEmergencyStopped, setIsEmergencyStopped] = useState<boolean>(false);
  const [emergencyError, setEmergencyError] = useState<string | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [taskLoadingError, setTaskLoadingError] = useState<string | null>(null);
  const [isSessionEnded, setIsSessionEnded] = useState<boolean>(false);
  const [completedTaskResult, setCompletedTaskResult] = useState<any | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [pendingConfirmation, setPendingConfirmation] = useState<{
    actionName: string;
    displayCommand: string;
  } | null>(null);

  // Guard against duplicate triggers during in-flight operations
  const isExecutingRef = useRef<boolean>(false);
  // Remember if action authorization succeeded so persistence retry does not re-execute action
  const lastAuthorizedStepRef = useRef<string | null>(null);
  // Phase 6: Focus management for confirmation dialog
  const confirmActionBtnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (pendingConfirmation) {
      // Safely move focus to confirm action button without executing
      const timer = setTimeout(() => {
        confirmActionBtnRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [pendingConfirmation]);

  // Phase 6: Escape cancels pending confirmation safely without triggering actions
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && pendingConfirmation && !isAssistanceOpen) {
        e.preventDefault();
        setPendingConfirmation(null);
        setStatusMessage('Pending action canceled.');
        announce('Pending action canceled.');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [pendingConfirmation, isAssistanceOpen, announce]);

  useEffect(() => {
    loadWorkstationData();
  }, []);

  async function loadWorkstationData() {
    setTaskLoadingError(null);
    try {
      // 1. Fetch active session if available
      try {
        const activeSession = await api.getActiveSession();
        setSession(activeSession);
      } catch (sessErr) {
        console.warn('Active session query notice:', sessErr);
      }

      // 2. Fetch real assigned tasks from backend (read-only)
      const assigned = await api.getAssignedTasks();
      if (!assigned || assigned.length === 0) {
        setTaskLoadingError('No active assembly tasks assigned to your worker profile. Please contact your supervisor.');
        return;
      }

      // 3. Find active assignment or first assigned task
      const targetAssignment =
        assigned.find((a: any) => a.status === 'active' || a.status === 'in_progress') || assigned[0];
      setAssignmentId(targetAssignment.id);

      let currentWfAssignId = targetAssignment.workflow_assignment_id || null;

      // 4. Start assignment if still in 'assigned' status (legitimate write lifecycle)
      if (targetAssignment.status === 'assigned') {
        try {
          const started = await api.startTaskAssignment(targetAssignment.id);
          if (started?.workflow_assignment_id) {
            currentWfAssignId = started.workflow_assignment_id;
          }
        } catch (startErr) {
          console.warn('Assignment start lifecycle notice:', startErr);
        }
      }
      setWorkflowAssignmentId(currentWfAssignId);

      // 5. Fetch task details and workflow steps from backend
      const taskData = await api.getTaskDetails(targetAssignment.task_id);
      if (!taskData || !taskData.steps || taskData.steps.length === 0) {
        setTaskLoadingError('Assigned task has no workflow steps configured.');
        return;
      }

      setTask(taskData);
      setCurrentStepIndex(0);
      setStatusMessage(`Workstation ready: ${taskData.name}. Step 1 of ${taskData.steps.length}.`);
    } catch (err: any) {
      setTaskLoadingError(`Failed to load workstation assignment: ${err?.message || 'Backend connection error'}`);
    }
  }

  const handleNextStep = async () => {
    if (!task || isExecutingRef.current) return;
    const currentStep = task.steps[currentStepIndex];
    if (!currentStep) return;

    if (currentStepIndex >= task.steps.length - 1) {
      const finishMsg = '🎉 All assembly workflow steps completed! Click "End Work" to close task.';
      setStatusMessage(finishMsg);
      announce(finishMsg);
      playAudioCue('confirm');
      return;
    }

    const nextIdx = currentStepIndex + 1;
    isExecutingRef.current = true;
    setIsExecuting(true);
    setExecutionError(null);

    try {
      // Step 1: Canonical Action Execution Gate (if not already authorized for this step)
      if (lastAuthorizedStepRef.current !== currentStep.id) {
        setStatusMessage(`Authorizing 'next_step' with backend safety gateway...`);
        const actionRes = await api.executeAction({
          action_name: 'next_step',
          workflow_step_id: currentStep.id,
          task_id: task.id,
          work_session_id: session?.id || null,
          parameters: { from_step: currentStep.stepNumber, to_step: task.steps[nextIdx]?.stepNumber },
        });

        if (!actionRes?.success) {
          throw new Error(actionRes?.feedback_message || 'Action rejected by backend safety gate.');
        }
        lastAuthorizedStepRef.current = currentStep.id;
      }

      // Step 2: Persist Step Execution to Database
      if (workflowAssignmentId) {
        setStatusMessage(`Saving Step ${currentStep.stepNumber} completion to backend...`);
        await api.recordStepExecution(workflowAssignmentId, currentStep.id, {
          status: 'completed',
          execution_data: { step_number: currentStep.stepNumber, title: currentStep.title },
        });
      }

      // Step 3: UI Progression (ONLY after persistence succeeds)
      lastAuthorizedStepRef.current = null;
      setCurrentStepIndex(nextIdx);
      const msg = `Advanced to Step ${nextIdx + 1}: ${task.steps[nextIdx].title}`;
      setStatusMessage(msg);
      announce(msg);
      playAudioCue('step');
    } catch (err: any) {
      // Failure: preserve step position, display clear honest error
      const errMsg = `⚠️ Step advancement stopped: ${err?.message || 'Server rejected action or persistence failed'}. Step ${currentStep.stepNumber} retained.`;
      setExecutionError(errMsg);
      setStatusMessage(errMsg);
      announce(errMsg);
      playAudioCue('alert');
    } finally {
      isExecutingRef.current = false;
      setIsExecuting(false);
    }
  };

  const handlePreviousStep = async () => {
    if (!task || currentStepIndex === 0 || isExecutingRef.current) return;
    const currentStep = task.steps[currentStepIndex];
    const prevIdx = currentStepIndex - 1;
    isExecutingRef.current = true;
    setIsExecuting(true);
    setExecutionError(null);

    try {
      await api.executeAction({
        action_name: 'previous_step',
        workflow_step_id: currentStep.id,
        task_id: task.id,
        work_session_id: session?.id || null,
      });

      lastAuthorizedStepRef.current = null;
      setCurrentStepIndex(prevIdx);
      const msg = `Returned to Step ${prevIdx + 1}: ${task.steps[prevIdx].title}`;
      setStatusMessage(msg);
      announce(msg);
      playAudioCue('step');
    } catch (err: any) {
      const errMsg = `Navigation rejected: ${err?.message || 'Backend rejected action'}`;
      setExecutionError(errMsg);
      setStatusMessage(errMsg);
    } finally {
      isExecutingRef.current = false;
      setIsExecuting(false);
    }
  };

  const handleActionTriggered = async (
    actionName: string,
    sourceModality: string = 'unknown',
    options?: { requiresConfirmation?: boolean; displayCommand?: string }
  ) => {
    // Step 6: If action requires confirmation and is not emergency_stop, stage it
    if (options?.requiresConfirmation && actionName !== 'emergency_stop') {
      setPendingConfirmation({
        actionName,
        displayCommand: options.displayCommand || actionName,
      });
      const confirmPrompt = `⚠️ Voice command '${options.displayCommand || actionName}' requires confirmation. Say "Confirm" or click Confirm, or say "Cancel" to abort.`;
      setStatusMessage(confirmPrompt);
      announce(confirmPrompt);
      playAudioCue('alert');
      return;
    }

    // If there is an active pendingConfirmation staged:
    if (pendingConfirmation) {
      if (actionName === 'confirm_action') {
        const targetAction = pendingConfirmation.actionName;
        setPendingConfirmation(null);
        await executeResolvedAction(targetAction);
        return;
      } else if (actionName === 'cancel_action') {
        setPendingConfirmation(null);
        const cancelMsg = 'Pending action canceled.';
        setStatusMessage(cancelMsg);
        announce(cancelMsg);
        playAudioCue('step');
        return;
      }
    }

    await executeResolvedAction(actionName);
  };

  const executeResolvedAction = async (actionName: string) => {
    if (actionName === 'confirm_action' || actionName === 'next_step') {
      await handleNextStep();
    } else if (actionName === 'previous_step') {
      await handlePreviousStep();
    } else if (actionName === 'pause_session') {
      try {
        if (task) {
          await api.executeAction({
            action_name: 'pause_session',
            task_id: task.id,
            work_session_id: session?.id || null,
          });
        }
        setStatusMessage('⏸️ Work session paused safely.');
        announce('Work session paused.');
      } catch (err: any) {
        setStatusMessage(`Pause notice: ${err?.message || 'Pause request rejected'}`);
      }
    } else if (actionName === 'resume_session') {
      await handleResume();
    } else if (actionName === 'request_assistance') {
      setIsAssistanceOpen(true);
      const helpMsg = '🙋 Supervisor assistance request modal opened via voice command.';
      setStatusMessage(helpMsg);
      announce('Supervisor assistance request opened.');
      playAudioCue('alert');
    } else if (actionName === 'cancel_action') {
      setStatusMessage('No active operation to cancel.');
      announce('No active operation to cancel.');
    } else if (actionName === 'emergency_stop') {
      await handleEmergencyStop();
    }
  };

  const handleEmergencyStop = async () => {
    setEmergencyError(null);
    try {
      const res = await api.triggerSafetyStop(
        'Worker emergency stop triggered at assembly workstation',
        session?.id
      );
      if (res.success) {
        setIsEmergencyStopped(true);
        const msg = '🛑 SOFTWARE EMERGENCY STOP ACTIVATED. Work session locked. Supervisor alert dispatched.';
        setStatusMessage(msg);
        announce(msg);
        playAudioCue('stop');
      } else {
        throw new Error('Safety stop rejected by backend');
      }
    } catch (err: any) {
      setIsEmergencyStopped(false);
      const errMsg = `⚠️ EMERGENCY STOP FAILED: Backend unreachable or rejected (${err?.message || 'Connection failed'}). Software lockout not confirmed. Engage manual emergency hardware if applicable.`;
      setEmergencyError(errMsg);
      setStatusMessage(errMsg);
      announce(errMsg);
      playAudioCue('alert');
    }
  };

  const handleResume = async () => {
    try {
      if (task) {
        await api.executeAction({
          action_name: 'resume_session',
          task_id: task.id,
          work_session_id: session?.id || null,
        });
      }
    } catch (err) {
      console.warn('Resume action notice:', err);
    }
    setIsEmergencyStopped(false);
    setEmergencyError(null);
    setStatusMessage('Session resumed safely.');
    announce('Session resumed safely.');
    playAudioCue('confirm');
  };

  const handleEndWork = async () => {
    if (isExecutingRef.current) return;
    isExecutingRef.current = true;
    setIsExecuting(true);
    setExecutionError(null);

    try {
      if (assignmentId) {
        await api.completeTaskAssignment(assignmentId, {
          outcome: 'completed',
          result_data: { completed_steps: task?.steps?.length || 0 },
          notes: 'Assembly completed through accessible multimodal workstation',
        });

        // MUST FIX #6: Obtain real persisted result from backend
        try {
          const resData = await api.getTaskResult(assignmentId);
          setCompletedTaskResult(resData);
        } catch (fetchErr) {
          console.warn('Notice: Could not load task result details:', fetchErr);
        }
      }
      setIsSessionEnded(true);
      setStatusMessage('Work session and task assignment completed and persisted in immutable audit trail.');
      announce('Work session completed.');
      playAudioCue('confirm');
    } catch (err: any) {
      const errMsg = `⚠️ Task completion failed: ${err?.message || 'Server rejected completion'}. Task not marked complete.`;
      setExecutionError(errMsg);
      setStatusMessage(errMsg);
      announce(errMsg);
      playAudioCue('alert');
    } finally {
      isExecutingRef.current = false;
      setIsExecuting(false);
    }
  };

  if (taskLoadingError) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center' }}>
        <div className="glass-card" style={{ maxWidth: '600px', margin: '0 auto', padding: '2.5rem', border: '1px solid var(--accent-amber)' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '1rem' }}>📋</span>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--accent-amber)' }}>
            Workstation Notice
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>{taskLoadingError}</p>
          <button
            type="button"
            onClick={loadWorkstationData}
            className="btn btn-primary"
            style={{ padding: '0.65rem 1.5rem' }}
          >
            🔄 Retry Connecting
          </button>
        </div>
      </div>
    );
  }

  if (!task || !task.steps || task.steps.length === 0) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center' }}>
        <div role="status" aria-live="polite" className="animate-pulse-glow" style={{ fontSize: '2rem' }}>
          ⚡ Connecting to Workstation...
        </div>
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

      {/* Emergency Lockout Banner (§ 25) - Software Prototype Boundary Only */}
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
              <strong style={{ fontSize: '1.2rem', display: 'block' }}>Software Emergency Lockout Active</strong>
              <span>Assembly work session locked. Supervisor assistance alert dispatched. (Software prototype safety boundary).</span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleResume}
            className="btn btn-secondary"
            style={{ background: 'white', color: '#be123c', fontWeight: 700 }}
          >
            Clear Lockout & Resume
          </button>
        </div>
      )}

      {/* Persistent Emergency Stop Failure Warning */}
      {emergencyError && (
        <div
          role="alert"
          style={{
            background: 'rgba(239, 68, 68, 0.2)',
            border: '2px solid #ef4444',
            color: '#fca5a5',
            padding: '1.25rem 2rem',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>⚠️</span>
            <div>
              <strong style={{ fontSize: '1.1rem', color: '#fee2e2', display: 'block' }}>
                Emergency Stop Request Failed
              </strong>
              <span>{emergencyError}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleEmergencyStop}
            className="btn btn-primary"
            style={{ background: '#ef4444', borderColor: '#ef4444', whiteSpace: 'nowrap' }}
          >
            Retry Stop
          </button>
        </div>
      )}

      {/* Step Progression / Action Execution Failure Banner */}
      {executionError && (
        <div
          role="alert"
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '2px solid #ef4444',
            color: '#fca5a5',
            padding: '1.25rem 2rem',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>⚠️</span>
            <div>
              <strong style={{ fontSize: '1.1rem', color: '#fee2e2', display: 'block' }}>
                Action / Step Persistence Error
              </strong>
              <span>{executionError}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleNextStep}
            disabled={isExecuting}
            aria-busy={isExecuting}
            className="btn btn-primary"
            style={{ minHeight: '48px', background: '#f59e0b', borderColor: '#f59e0b', whiteSpace: 'nowrap' }}
          >
            🔄 Retry Step Progression
          </button>
        </div>
      )}

      {/* Action Confirmation Required Banner (Step 6) */}
      {pendingConfirmation && (
        <div
          role="alertdialog"
          aria-labelledby="confirm-heading"
          aria-describedby="confirm-desc"
          className="glass-card"
          style={{
            padding: '1.25rem 1.75rem',
            borderRadius: '16px',
            background: 'rgba(245, 158, 11, 0.15)',
            border: '2px solid var(--accent-amber)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>⚠️</span>
            <div>
              <strong id="confirm-heading" style={{ fontSize: '1.1rem', color: 'var(--accent-amber)', display: 'block' }}>
                Action Confirmation Required
              </strong>
              <span id="confirm-desc" style={{ color: 'var(--text-primary)', fontSize: '0.92rem' }}>
                Voice command <strong>“{pendingConfirmation.displayCommand}”</strong> requires confirmation before execution.
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              ref={confirmActionBtnRef}
              type="button"
              onClick={() => handleActionTriggered('confirm_action', 'ui')}
              className="btn btn-primary"
              style={{ minHeight: '48px', background: 'var(--org-emerald)', borderColor: 'var(--org-emerald)', padding: '0.65rem 1.5rem', fontWeight: 700 }}
            >
              ✓ Confirm Action
            </button>
            <button
              type="button"
              onClick={() => handleActionTriggered('cancel_action', 'ui')}
              className="btn btn-secondary"
              style={{ minHeight: '48px', padding: '0.65rem 1.25rem' }}
            >
              ✕ Cancel
            </button>
          </div>
        </div>
      )}

      {/* Live Status Toast */}
      <div
        role="status"
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
          style={{ minHeight: '48px', padding: '0.5rem 1.25rem', fontSize: '0.88rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center' }}
        >
          🏁 {t('end_work_btn', language)}
        </button>
      </div>

      {isSessionEnded ? (
        /* End Work Summary Card (MUST FIX #6 / FR-09) */
        <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', border: '2px solid var(--org-emerald)' }}>
          <span style={{ fontSize: '4rem', display: 'block', marginBottom: '1rem' }}>🏁</span>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--org-emerald)' }}>
            Work Session Successfully Closed
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0.75rem auto 1.5rem auto' }}>
            Authoritative workflow execution records and task completion outcome have been saved to PostgreSQL.
          </p>

          {/* Real Server Result Telemetry Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
              maxWidth: '700px',
              margin: '0 auto 2rem auto',
              textAlign: 'left',
            }}
          >
            <div className="glass-panel" style={{ padding: '1rem', borderRadius: '12px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block' }}>Outcome</span>
              <strong style={{ fontSize: '1.2rem', color: 'var(--org-emerald)', textTransform: 'uppercase' }}>
                {completedTaskResult?.outcome || 'completed'}
              </strong>
            </div>

            <div className="glass-panel" style={{ padding: '1rem', borderRadius: '12px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block' }}>Completed Steps</span>
              <strong style={{ fontSize: '1.2rem', color: 'var(--worker-cyan)' }}>
                {completedTaskResult?.result_data?.completed_steps ?? task.steps.length} /{' '}
                {completedTaskResult?.result_data?.total_steps ?? task.steps.length}
              </strong>
            </div>

            <div className="glass-panel" style={{ padding: '1rem', borderRadius: '12px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block' }}>Active Duration</span>
              <strong style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>
                {completedTaskResult?.result_data?.duration_seconds != null
                  ? `${completedTaskResult.result_data.duration_seconds}s`
                  : 'Recorded'}
              </strong>
            </div>

            <div className="glass-panel" style={{ padding: '1rem', borderRadius: '12px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block' }}>Recorded Time</span>
              <span style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                {completedTaskResult?.recorded_at
                  ? new Date(completedTaskResult.recorded_at).toLocaleTimeString()
                  : 'Just now'}
              </span>
            </div>
          </div>

          {completedTaskResult?.notes && (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '1.5rem' }}>
              Notes: {completedTaskResult.notes}
            </p>
          )}

          <button
            type="button"
            onClick={() => {
              setIsSessionEnded(false);
              setCompletedTaskResult(null);
            }}
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

          <MultimodalHUD
            onActionTriggered={handleActionTriggered}
            workSessionId={session?.id || null}
            dwellTimeMs={500}
            isEmergencyStopped={isEmergencyStopped}
          />
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
