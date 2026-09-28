'use client';

/**
 * Worker Interactive Assembly Workstation (/worker) (§ 15, § 18, § 24)
 * Primary AMAP screen designed for motor accessibility:
 * Answers: What am I doing? What step? What next? How to interact? How to get help? How to stop?
 *
 * Real-time interaction engine (Part 1-6):
 *   Camera -> MediaPipe landmarks -> gesture engine (pointer/click/drag/scroll
 *   state machine) -> worker gesture mapping (PostgreSQL) -> action resolver
 *   -> REAL UI/task action -> backend API -> PostgreSQL -> supervisor view.
 *
 * Voice and dwell gestures flow through the same action resolver via the
 * MultimodalHUD; the workstation owns the session lifecycle (start/heartbeat/
 * pause/resume/end) so the supervisor live monitor reflects reality.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { MultimodalHUD } from '@/worker/components/MultimodalHUD';
import { WorkflowStepViewer } from '@/worker/components/WorkflowStepViewer';
import { AssistanceModal } from '@/worker/components/AssistanceModal';
import { VirtualCursor } from '@/worker/components/VirtualCursor';
import { GestureContextMenu } from '@/worker/components/GestureContextMenu';
import { GestureControlPanel } from '@/worker/components/GestureControlPanel';
import { AssemblyDragBench } from '@/worker/components/AssemblyDragBench';
import {
  WorkerGestureEngine,
  EngineEvent,
  InteractionState,
  DEFAULT_ENGINE_CALIBRATION,
  engineCalibrationFromBackend,
  engineCalibrationToBackend,
} from '@/worker/lib/gestureEngine';
import * as executor from '@/worker/lib/uiActionExecutor';
import { poseToGestureKey } from '@/worker/lib/handPoses';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { TaskDetails, WorkSession } from '@/shared/types';
import { api } from '@/shared/api/client';

/** Actions offered in the gesture context menu (right click). */
const CONTEXT_MENU_ACTIONS = [
  { id: 'next', label: 'Next Step', icon: '➡️', action: 'next_step' },
  { id: 'prev', label: 'Previous Step', icon: '⬅️', action: 'previous_step' },
  { id: 'complete', label: 'Complete This Step', icon: '✅', action: 'complete_step' },
  { id: 'select', label: 'Select Item Under Pointer', icon: '🎯', action: 'select_item' },
  { id: 'help', label: 'Request Assistance', icon: '🙋', action: 'request_assistance' },
  { id: 'pause', label: 'Pause Session', icon: '⏸️', action: 'pause_session' },
  { id: 'resume', label: 'Resume Session', icon: '▶️', action: 'resume_session' },
  { id: 'endwork', label: 'Finish Assignment', icon: '🏁', action: 'finish_assignment' },
  { id: 'estop', label: 'EMERGENCY STOP', icon: '🛑', action: 'emergency_stop', danger: true },
];

const GESTURE_CHOICE_LIST = [
  'pinch',
  'pinch_hold',
  'two_finger',
  'two_finger_move',
  'swipe_up',
  'swipe_down',
  'swipe_left',
  'swipe_right',
  'thumbs_up',
  'thumbs_down',
  'open_palm',
  'fist',
];

const ACTION_CHOICES = [
  'left_click',
  'right_click',
  'double_click',
  'select_item',
  'scroll_up',
  'scroll_down',
  'scroll_left',
  'scroll_right',
  'next_step',
  'previous_step',
  'confirm_action',
  'cancel_action',
  'pause_session',
  'resume_session',
  'request_assistance',
  'emergency_stop',
  'start_assignment',
  'complete_step',
  'finish_assignment',
];

export default function WorkerPage() {
  const { language, announce, playAudioCue, isReady, modality } = useAccessibility();

  const [session, setSession] = useState<WorkSession | null>(null);
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [assignmentStatus, setAssignmentStatus] = useState<string | null>(null);
  const [workflowAssignmentId, setWorkflowAssignmentId] = useState<string | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [completedStepIds, setCompletedStepIds] = useState<Set<string>>(new Set());
  const [installedParts, setInstalledParts] = useState<Record<string, string>>({});
  const [isAssistanceOpen, setIsAssistanceOpen] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('Ready for assembly input.');
  const [isEmergencyStopped, setIsEmergencyStopped] = useState<boolean>(false);
  const [isInteractionPaused, setIsInteractionPaused] = useState<boolean>(false);
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

  // Gesture engine state
  const engineRef = useRef<WorkerGestureEngine | null>(null);
  const [cursorPosition, setCursorPosition] = useState<{ x: number; y: number } | null>(null);
  const [cursorState, setCursorState] = useState<InteractionState>('IDLE');
  const [gestureMap, setGestureMap] = useState<Record<string, string>>({});
  const [gestureMapSources, setGestureMapSources] = useState<Record<string, string>>({});
  const [calibration, setCalibration] = useState<Record<string, any>>(
    DEFAULT_ENGINE_CALIBRATION as unknown as Record<string, any>
  );
  const [contextMenu, setContextMenu] = useState<{ open: boolean; position: { x: number; y: number } | null }>({
    open: false,
    position: null,
  });

  /** Shared with the HUD voice pipeline for cross-modal fusion of engine gestures. */
  const engineGestureRef = useRef<{
    gesture: string;
    confidence: number;
    timestamp: number;
    position?: { x: number; y: number };
  } | null>(null);

  // Guard against duplicate triggers during in-flight operations
  const isExecutingRef = useRef<boolean>(false);
  // Remember if action authorization succeeded so persistence retry does not re-execute action
  const lastAuthorizedStepRef = useRef<string | null>(null);
  // Phase 6: Focus management for confirmation dialog
  const confirmActionBtnRef = useRef<HTMLButtonElement | null>(null);
  // Aggregated scroll audit (avoids flooding execution events)
  const scrollAuditRef = useRef<{ counts: Record<string, number>; lastFlush: number }>({
    counts: {},
    lastFlush: 0,
  });
  // Emergency stop de-dup (engine fires instantly; HUD dwell may repeat)
  const lastEmergencyRef = useRef<number>(0);

  useEffect(() => {
    if (pendingConfirmation) {
      const timer = setTimeout(() => {
        confirmActionBtnRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [pendingConfirmation]);

  // Escape cancels pending confirmation / context menu safely
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (pendingConfirmation && !isAssistanceOpen) {
          e.preventDefault();
          setPendingConfirmation(null);
          setStatusMessage('Pending action canceled.');
          announce('Pending action canceled.');
        }
        setContextMenu((cm) => (cm.open ? { open: false, position: null } : cm));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [pendingConfirmation, isAssistanceOpen, announce]);

  // -------------------------------------------------------------------------
  // Gesture engine construction + viewport tracking
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!engineRef.current) {
      engineRef.current = new WorkerGestureEngine(
        {},
        {},
        { width: window.innerWidth, height: window.innerHeight }
      );
    }
    const onResize = () => engineRef.current?.setViewport(window.innerWidth, window.innerHeight);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Right-click (context menu) event from the UI action executor
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      setContextMenu({ open: true, position: { x: detail.x ?? 0, y: detail.y ?? 0 } });
    };
    window.addEventListener('amapcontextmenu', handler);
    return () => window.removeEventListener('amapcontextmenu', handler);
  }, []);

  // Periodic scroll audit flush (batched, PostgreSQL execution events)
  useEffect(() => {
    const interval = window.setInterval(() => {
      flushScrollAudit();
    }, 2500);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, task]);

  useEffect(() => {
    loadWorkstationData();
  }, []);

  // Session heartbeat: keeps the supervisor live worker monitor accurate
  useEffect(() => {
    if (!session || isEmergencyStopped) return;
    const beat = () => {
      api
        .heartbeatWorkSession(session.id)
        .then((updated) => {
          if (updated) setSession(updated);
        })
        .catch(() => {
          /* transient heartbeat failure — retried on next interval */
        });
    };
    beat();
    const interval = window.setInterval(beat, 30000);
    return () => window.clearInterval(interval);
  }, [session?.id, isEmergencyStopped]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadWorkstationData() {
    setTaskLoadingError(null);
    try {
      // 1. Fetch or START the active work session (the supervisor live monitor
      //    derives online status from this session's heartbeat).
      let activeSession: WorkSession | null = null;
      try {
        activeSession = await api.getActiveSession();
      } catch {
        activeSession = null;
      }
      if (!activeSession) {
        try {
          activeSession = await api.startWorkSession();
        } catch {
          try {
            activeSession = await api.getActiveSession(); // 409: already active
          } catch {
            activeSession = null;
          }
        }
      }
      setSession(activeSession);

      // 2. Load the worker's effective gesture mapping + calibration (PostgreSQL)
      try {
        const mapping = await api.getGestureMapping();
        setGestureMap(mapping.gesture_action_map || {});
        setGestureMapSources(mapping.sources || {});
        if (mapping.calibration) {
          setCalibration(mapping.calibration);
          engineRef.current?.updateCalibration(engineCalibrationFromBackend(mapping.calibration));
          engineRef.current?.setGestureActionMap(mapping.gesture_action_map || {});
        }
      } catch (mapErr) {
        console.warn('Gesture mapping load notice (canonical defaults apply):', mapErr);
        engineRef.current?.setGestureActionMap({});
      }

      // 3. Fetch real assigned tasks from backend (read-only)
      const assigned = await api.getAssignedTasks();
      if (!assigned || assigned.length === 0) {
        setTaskLoadingError(
          'No active assembly tasks assigned to your worker profile. Please contact your supervisor.'
        );
        return;
      }

      // 4. Find active assignment or first assigned task
      const targetAssignment =
        assigned.find((a: any) => a.status === 'active' || a.status === 'in_progress') || assigned[0];
      setAssignmentId(targetAssignment.id);
      setAssignmentStatus(targetAssignment.status);

      let currentWfAssignId = targetAssignment.workflow_assignment_id || null;

      // 5. Start assignment if still in 'assigned' status (legitimate write lifecycle)
      if (targetAssignment.status === 'assigned') {
        try {
          const started = await api.startTaskAssignment(targetAssignment.id);
          if (started?.workflow_assignment_id) {
            currentWfAssignId = started.workflow_assignment_id;
          }
          setAssignmentStatus(started?.status || 'in_progress');
        } catch (startErr) {
          console.warn('Assignment start lifecycle notice:', startErr);
        }
      }
      setWorkflowAssignmentId(currentWfAssignId);

      // 6. Fetch task details and workflow steps from backend
      const taskData = await api.getTaskDetails(targetAssignment.task_id);
      if (!taskData || !taskData.steps || taskData.steps.length === 0) {
        setTaskLoadingError('Assigned task has no workflow steps configured.');
        return;
      }

      setTask(taskData);

      // 7. Restore persisted progress (survives refresh / re-login)
      let completedIds = new Set<string>();
      if (currentWfAssignId) {
        try {
          const executions = await api.getStepExecutions(currentWfAssignId);
          completedIds = new Set(
            executions.filter((e: any) => e.status === 'completed').map((e: any) => e.workflow_step_id)
          );
        } catch (execErr) {
          console.warn('Progress restore notice:', execErr);
        }
      }
      setCompletedStepIds(completedIds);

      const firstIncompleteIdx = taskData.steps.findIndex((s: any) => !completedIds.has(s.id));
      const restoredIdx = firstIncompleteIdx === -1 ? taskData.steps.length - 1 : firstIncompleteIdx;
      setCurrentStepIndex(restoredIdx);

      const doneCount = completedIds.size;
      setStatusMessage(
        `Workstation ready: ${taskData.name}. Step ${restoredIdx + 1} of ${taskData.steps.length}` +
          (doneCount > 0 ? ` (${doneCount} step${doneCount > 1 ? 's' : ''} already completed).` : '.')
      );
    } catch (err: any) {
      setTaskLoadingError(`Failed to load workstation assignment: ${err?.message || 'Backend connection error'}`);
    }
  }

  // -------------------------------------------------------------------------
  // Gesture engine frame + event handling
  // -------------------------------------------------------------------------

  const handleRawHandFrame = useCallback(
    (hands: { x: number; y: number; z?: number }[][], labels: string[]) => {
      const engine = engineRef.current;
      if (!engine) return;
      if (modality !== 'gesture' && modality !== 'multimodal') return;
      const events = engine.processFrame(hands, labels, Date.now());
      if (events.length) processEngineEvents(events);
    },
    [modality] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const processEngineEvents = useCallback((events: EngineEvent[]) => {
    for (const evt of events) {
      switch (evt.type) {
        case 'pointer':
          setCursorPosition(evt.position);
          setCursorState(evt.state);
          // Expose the current pointer pose for cross-modal voice fusion
          if (evt.pose && evt.pose !== 'NONE') {
            engineGestureRef.current = {
              gesture: poseToGestureKey(evt.pose),
              confidence: 0.9,
              timestamp: Date.now(),
              position: evt.position,
            };
          }
          break;
        case 'state':
          setCursorState(evt.state);
          break;
        case 'action':
          handleEngineAction(evt.action, evt.gesture, evt.confidence, evt.position, evt.context);
          break;
        case 'scroll':
          handleEngineScroll(evt.direction, evt.amountPx, evt.position, evt.source);
          break;
        case 'drag':
          handleEngineDrag(evt);
          break;
        case 'feedback':
          if (evt.level !== 'info') setStatusMessage(`⚠️ ${evt.message}`);
          break;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Gesture-dispatched action -> shared action resolver (same path as voice). */
  const handleEngineAction = (
    action: string,
    gesture: string,
    confidence: number,
    position: { x: number; y: number } | null,
    context?: Record<string, unknown>
  ) => {
    // Emergency stop must bypass everything, including pause locks.
    if (action === 'emergency_stop') {
      const now = Date.now();
      if (now - lastEmergencyRef.current < 2000) return;
      lastEmergencyRef.current = now;
      handleEmergencyStop();
      return;
    }

    if (isInteractionPaused) {
      // While paused only UI navigation (clicks/scroll/select) stays live so
      // the worker can still reach the Resume control; task actions wait.
      const uiOnly = ['left_click', 'right_click', 'double_click', 'select_item'].includes(action);
      if (!uiOnly) {
        setStatusMessage('⏸️ Interaction paused. Say "resume" or click Resume to continue task actions.');
        announce('Interaction is paused.');
        return;
      }
    }

    executeResolvedAction(action, 'gesture-engine', { position, context, displayCommand: gesture });
  };

  const handleEngineScroll = (
    direction: 'up' | 'down' | 'left' | 'right',
    amountPx: number,
    position: { x: number; y: number },
    source: string
  ) => {
    const result = executor.scrollView(direction, amountPx, position);
    if (result.ok) {
      scrollAuditRef.current.counts[direction] = (scrollAuditRef.current.counts[direction] || 0) + 1;
    }
    setCursorState('TRIGGERED');
    window.setTimeout(() => setCursorState((s) => (s === 'TRIGGERED' ? 'HOVER' : s)), 200);
    if (source === 'swipe') {
      setStatusMessage(`📜 Scrolled ${direction} (swipe gesture).`);
    }
  };

  const flushScrollAudit = () => {
    const audit = scrollAuditRef.current;
    const now = Date.now();
    const total = Object.values(audit.counts).reduce((a, b) => a + b, 0);
    if (total === 0 || now - audit.lastFlush < 2000) return;
    const counts = { ...audit.counts };
    audit.counts = {};
    audit.lastFlush = now;
    api
      .executeAction({
        action_name: 'scroll',
        work_session_id: session?.id || null,
        task_id: task?.id || null,
        parameters: { aggregated: true, scroll_events: counts, total, source: 'gesture-engine' },
      })
      .catch(() => {
        /* audit failure must not disrupt interaction; next flush retries */
      });
  };

  const handleEngineDrag = (evt: Extract<EngineEvent, { type: 'drag' }>) => {
    if (evt.phase === 'start') {
      const result = executor.dragStart(evt.position.x, evt.position.y);
      if (result.ok) {
        setStatusMessage(`🖐️ Dragging "${result.target.text || result.target.tag}" — move to the assembly zone and release.`);
        announce('Drag started.');
        auditUIAction('drag_start', evt.position, result.target, {
          source: evt.source,
        });
      } else {
        setStatusMessage('⚠️ Nothing draggable at the pointer position.');
        engineRef.current?.endExternalDrag();
      }
    } else if (evt.phase === 'move') {
      executor.dragMove(evt.position.x, evt.position.y);
    } else if (evt.phase === 'end') {
      const result = executor.dragEnd(evt.position.x, evt.position.y);
      if (result.ok) {
        setStatusMessage(
          result.detail?.includes('Dropped onto')
            ? `✅ ${result.detail}`
            : 'Drag released outside the assembly zone — nothing installed.'
        );
        announce('Drag ended.');
        auditUIAction('drag_end', evt.position, result.target, {
          source: evt.source,
          path_px: evt.pathLengthPx,
          duration_ms: evt.durationMs,
          dropped: Boolean(result.detail?.includes('Dropped onto')),
        });
      }
    }
  };

  /** Persist discrete UI interaction actions to the backend audit trail. */
  const auditUIAction = (
    actionName: string,
    position: { x: number; y: number } | null,
    target: executor.ActionTargetDescriptor,
    extra: Record<string, unknown> = {}
  ) => {
    api
      .executeAction({
        action_name: actionName,
        work_session_id: session?.id || null,
        task_id: task?.id || null,
        parameters: {
          pointer_x: position?.x ?? null,
          pointer_y: position?.y ?? null,
          target_tag: target.tag || null,
          target_role: target.role || null,
          target_text: target.text || null,
          ...extra,
        },
      })
      .catch((err) => {
        console.warn(`UI action audit notice (${actionName}):`, err?.message || err);
      });
  };

  // -------------------------------------------------------------------------
  // Step progression (persisted)
  // -------------------------------------------------------------------------

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
          execution_data: {
            step_number: currentStep.stepNumber,
            title: currentStep.title,
            parts_installed: installedParts[currentStep.id] ? [installedParts[currentStep.id]] : [],
          },
        });
      }

      // Step 3: UI Progression (ONLY after persistence succeeds)
      lastAuthorizedStepRef.current = null;
      setCompletedStepIds((prev) => new Set(prev).add(currentStep.id));
      setCurrentStepIndex(nextIdx);
      const msg = `Advanced to Step ${nextIdx + 1}: ${task.steps[nextIdx].title}`;
      setStatusMessage(msg);
      announce(msg);
      playAudioCue('step');
    } catch (err: any) {
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

  /** Complete the CURRENT step without advancing (persisted immediately). */
  const handleCompleteStep = async () => {
    if (!task || isExecutingRef.current) return;
    const currentStep = task.steps[currentStepIndex];
    if (!currentStep) return;

    if (completedStepIds.has(currentStep.id)) {
      setStatusMessage(`✓ Step ${currentStep.stepNumber} is already completed.`);
      return;
    }

    isExecutingRef.current = true;
    setIsExecuting(true);
    setExecutionError(null);
    try {
      // 1. Persist the step completion
      if (workflowAssignmentId) {
        await api.recordStepExecution(workflowAssignmentId, currentStep.id, {
          status: 'completed',
          execution_data: {
            step_number: currentStep.stepNumber,
            title: currentStep.title,
            parts_installed: installedParts[currentStep.id] ? [installedParts[currentStep.id]] : [],
            completed_via: 'complete_step',
          },
        });
      }
      // 2. Audit through the action gateway
      await api.executeAction({
        action_name: 'complete_step',
        workflow_step_id: currentStep.id,
        task_id: task.id,
        work_session_id: session?.id || null,
      });
      setCompletedStepIds((prev) => new Set(prev).add(currentStep.id));
      const msg = `✅ Step ${currentStep.stepNumber} marked completed and saved to PostgreSQL.`;
      setStatusMessage(msg);
      announce(msg);
      playAudioCue('confirm');
    } catch (err: any) {
      const errMsg = `⚠️ Step completion failed: ${err?.message || 'Server rejected completion'}.`;
      setExecutionError(errMsg);
      setStatusMessage(errMsg);
      announce(errMsg);
      playAudioCue('alert');
    } finally {
      isExecutingRef.current = false;
      setIsExecuting(false);
    }
  };

  // -------------------------------------------------------------------------
  // Unified action resolver (gesture + voice + multimodal + UI)
  // -------------------------------------------------------------------------

  const handleActionTriggered = async (
    actionName: string,
    sourceModality: string = 'unknown',
    options?: {
      requiresConfirmation?: boolean;
      displayCommand?: string;
      position?: { x: number; y: number } | null;
      context?: Record<string, unknown>;
    }
  ) => {
    // If there is an active pendingConfirmation staged:
    if (pendingConfirmation) {
      if (actionName === 'confirm_action') {
        const targetAction = pendingConfirmation.actionName;
        setPendingConfirmation(null);
        await executeResolvedAction(targetAction, sourceModality, options);
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

    // Stage actions that require confirmation (never emergency_stop)
    if (options?.requiresConfirmation && actionName !== 'emergency_stop') {
      setPendingConfirmation({
        actionName,
        displayCommand: options.displayCommand || actionName,
      });
      const confirmPrompt = `⚠️ Command '${options.displayCommand || actionName}' requires confirmation. Say "Confirm" or click Confirm, or say "Cancel" to abort.`;
      setStatusMessage(confirmPrompt);
      announce(confirmPrompt);
      playAudioCue('alert');
      return;
    }

    await executeResolvedAction(actionName, sourceModality, options);
  };

  const resolvePointerForAction = (options?: {
    position?: { x: number; y: number } | null;
    context?: Record<string, unknown>;
  }): { x: number; y: number } | null => {
    if (options?.position) return options.position;
    const ctx = options?.context as any;
    if (ctx && typeof ctx.spatial_x === 'number' && typeof ctx.spatial_y === 'number') {
      return { x: ctx.spatial_x, y: ctx.spatial_y };
    }
    return engineRef.current?.getPointer() || cursorPosition;
  };

  const executeResolvedAction = async (
    actionName: string,
    sourceModality: string = 'unknown',
    options?: {
      position?: { x: number; y: number } | null;
      context?: Record<string, unknown>;
      displayCommand?: string;
    }
  ) => {
    if (actionName === 'emergency_stop') {
      await handleEmergencyStop();
      return;
    }

    if (isEmergencyStopped && actionName !== 'resume_session') {
      setStatusMessage('🛑 Emergency lockout active. Clear the lockout to continue.');
      return;
    }

    // ---------- A. Computer / UI interaction actions ----------
    switch (actionName) {
      case 'left_click': {
        const pos = resolvePointerForAction(options);
        if (!pos) {
          setStatusMessage('⚠️ Left click requested but the virtual pointer has no position yet.');
          return;
        }
        const result = executor.leftClick(pos.x, pos.y);
        if (result.ok) {
          setStatusMessage(`🖱️ Clicked "${result.target.text || result.target.tag}" via ${sourceModality}.`);
          playAudioCue('step');
          auditUIAction('left_click', pos, result.target, { source: sourceModality });
        } else {
          setStatusMessage(`⚠️ ${result.detail || 'No clickable element under the pointer.'}`);
        }
        return;
      }
      case 'right_click': {
        const pos = resolvePointerForAction(options);
        if (!pos) {
          setStatusMessage('⚠️ Right click requested but the virtual pointer has no position yet.');
          return;
        }
        const result = executor.rightClick(pos.x, pos.y);
        setStatusMessage(`🖱️ Right click at pointer — context menu opened (${sourceModality}).`);
        playAudioCue('step');
        auditUIAction('right_click', pos, result.target, { source: sourceModality });
        return;
      }
      case 'double_click': {
        const pos = resolvePointerForAction(options);
        if (!pos) {
          setStatusMessage('⚠️ Double click requested but the virtual pointer has no position yet.');
          return;
        }
        const result = executor.doubleClick(pos.x, pos.y);
        if (result.ok) {
          setStatusMessage(`🖱️ Double clicked "${result.target.text || result.target.tag}".`);
          playAudioCue('step');
          auditUIAction('double_click', pos, result.target, { source: sourceModality });
        } else {
          setStatusMessage(`⚠️ ${result.detail || 'No element under the pointer.'}`);
        }
        return;
      }
      case 'select_item': {
        const pos = resolvePointerForAction(options);
        if (!pos) {
          setStatusMessage('⚠️ Select requested but the virtual pointer has no position yet.');
          return;
        }
        const result = executor.selectItem(pos.x, pos.y);
        if (result.ok) {
          setStatusMessage(`🎯 Selected "${result.target.text || result.target.tag}" (focused).`);
          announce('Item selected.');
          playAudioCue('step');
          auditUIAction('select_item', pos, result.target, { source: sourceModality });
        } else {
          setStatusMessage('⚠️ No element under the pointer to select.');
        }
        return;
      }
      case 'scroll_up':
      case 'scroll_down':
      case 'scroll_left':
      case 'scroll_right': {
        const direction = actionName.replace('scroll_', '') as 'up' | 'down' | 'left' | 'right';
        const pos = resolvePointerForAction(options);
        const amount = Number((options?.context as any)?.amount) || 300;
        const result = executor.scrollView(direction, amount, pos, 60);
        if (result.ok) {
          scrollAuditRef.current.counts[direction] =
            (scrollAuditRef.current.counts[direction] || 0) + 1;
          setStatusMessage(`📜 Scrolled ${direction} via ${sourceModality}.`);
        }
        return;
      }
      case 'scroll': {
        const ctx = (options?.context || {}) as any;
        const direction = (ctx.direction || 'down') as 'up' | 'down' | 'left' | 'right';
        const pos = resolvePointerForAction(options);
        const result = executor.scrollView(direction, Number(ctx.amount) || 300, pos, 60);
        if (result.ok) {
          scrollAuditRef.current.counts[direction] =
            (scrollAuditRef.current.counts[direction] || 0) + 1;
        }
        return;
      }
      case 'drag_start': {
        // Multimodal "pinch/point + move this": arm the engine so the pinch
        // grabs the element under the pointer; if no hand is tracked, start
        // an immediate external drag at the last pointer position.
        const engine = engineRef.current;
        if (engine && engine.getPointer()) {
          engine.armVoiceDrag();
          setStatusMessage('🖐️ Drag armed: pinch to grab the element under the pointer, then move and release.');
          announce('Drag armed. Pinch to grab.');
          playAudioCue('step');
        } else {
          const pos = cursorPosition;
          if (pos) {
            const events = engine?.beginExternalDrag('voice') || [];
            if (events.length) processEngineEvents(events);
            setStatusMessage('🖐️ Drag started at the pointer. Say "drop" to release.');
          } else {
            setStatusMessage('⚠️ Drag requested but no pointer position is available.');
          }
        }
        return;
      }
      case 'drag_end': {
        const engine = engineRef.current;
        if (engine) {
          const events = engine.endExternalDrag();
          if (events.length) processEngineEvents(events);
          else {
            // Voice "drop" while a pinch-drag is active is handled by the
            // engine release; nothing else to end here.
            setStatusMessage('No active drag to release.');
          }
        }
        return;
      }
      case 'pointer_move':
      case 'drag_move':
        // Continuous pointer motion is engine-internal; no discrete dispatch.
        return;
      default:
        break;
    }

    // ---------- B. AMAP task actions ----------
    switch (actionName) {
      case 'confirm_action':
      case 'next_step':
        await handleNextStep();
        return;
      case 'previous_step':
        await handlePreviousStep();
        return;
      case 'complete_step':
        await handleCompleteStep();
        return;
      case 'start_assignment': {
        if (assignmentId && assignmentStatus === 'assigned') {
          try {
            const started = await api.startTaskAssignment(assignmentId);
            setAssignmentStatus(started?.status || 'in_progress');
            if (started?.workflow_assignment_id) setWorkflowAssignmentId(started.workflow_assignment_id);
            setStatusMessage('▶️ Assignment started and persisted.');
            playAudioCue('confirm');
          } catch (err: any) {
            setStatusMessage(`⚠️ Could not start assignment: ${err?.message || 'server error'}`);
          }
        } else {
          setStatusMessage('Assignment already started or not assigned.');
        }
        return;
      }
      case 'pause_session':
        await handlePause();
        return;
      case 'resume_session':
        await handleResume();
        return;
      case 'request_assistance':
        setIsAssistanceOpen(true);
        setStatusMessage('🙋 Supervisor assistance request opened.');
        announce('Supervisor assistance request opened.');
        playAudioCue('alert');
        return;
      case 'cancel_action':
        if (pendingConfirmation) {
          setPendingConfirmation(null);
          setStatusMessage('Pending action canceled.');
        } else {
          executor.dragCancel();
          setStatusMessage('No pending action to cancel.');
          announce('Nothing to cancel.');
        }
        return;
      case 'finish_assignment':
        await handleEndWork();
        return;
      default:
        setStatusMessage(`⚠️ Unsupported action '${actionName}'.`);
        announce(`Unsupported action ${actionName}.`);
        playAudioCue('alert');
        return;
    }
  };

  // -------------------------------------------------------------------------
  // Safety: pause / resume / emergency stop
  // -------------------------------------------------------------------------

  const handlePause = async () => {
    try {
      if (task) {
        await api.executeAction({
          action_name: 'pause_session',
          task_id: task.id,
          work_session_id: session?.id || null,
        });
      }
      if (session) {
        const updated = await api.pauseWorkSession(session.id);
        setSession(updated);
      }
      engineRef.current?.setPaused(true);
      setIsInteractionPaused(true);
      setStatusMessage('⏸️ Work session paused safely. UI navigation stays live; task actions wait.');
      announce('Work session paused.');
    } catch (err: any) {
      setStatusMessage(`Pause notice: ${err?.message || 'Pause request rejected'}`);
      announce('Pause request issue.');
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
      if (session) {
        const updated = await api.resumeWorkSession(session.id);
        setSession(updated);
      }
    } catch (err) {
      console.warn('Resume action notice:', err);
    }
    engineRef.current?.setEmergencyStopped(false);
    engineRef.current?.setPaused(false);
    setIsEmergencyStopped(false);
    setIsInteractionPaused(false);
    setEmergencyError(null);
    setStatusMessage('Session resumed safely.');
    announce('Session resumed safely.');
    playAudioCue('confirm');
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
        engineRef.current?.setEmergencyStopped(true);
        executor.dragCancel();
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

        try {
          const resData = await api.getTaskResult(assignmentId);
          setCompletedTaskResult(resData);
        } catch (fetchErr) {
          console.warn('Notice: Could not load task result details:', fetchErr);
        }
      }
      // End the work session so the supervisor monitor reflects reality.
      if (session && session.status !== 'completed') {
        try {
          await api.endWorkSession(session.id);
        } catch (endErr) {
          console.warn('Session end notice:', endErr);
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

  // -------------------------------------------------------------------------
  // Assembly bench interaction (drag & drop of real parts)
  // -------------------------------------------------------------------------

  const handlePartInstalled = useCallback(
    (partId: string, via: string) => {
      setInstalledParts((prev) => {
        if (prev[partId]) return prev;
        return { ...prev, [partId]: via };
      });
      setStatusMessage(`🔧 Component installed via ${via}. Complete the step to persist it.`);
      announce('Component installed.');
      playAudioCue('confirm');
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const handleMappingChanged = useCallback(
    (map: Record<string, string>, cal: Record<string, any>) => {
      setGestureMap(map);
      setCalibration(cal);
      engineRef.current?.setGestureActionMap(map);
      engineRef.current?.updateCalibration(engineCalibrationFromBackend(cal));
      setStatusMessage('✅ Gesture mapping saved to your worker profile (PostgreSQL).');
      playAudioCue('confirm');
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

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
  const isGestureMode = modality === 'gesture' || modality === 'multimodal';
  const currentStepCompleted = completedStepIds.has(currentStep.id);
  const partId = currentStep.spatialTargetId || `step-${currentStep.stepNumber}-component`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Virtual gesture pointer (real-time) */}
      <VirtualCursor
        position={cursorPosition}
        state={cursorState}
        visible={isGestureMode && !isEmergencyStopped}
      />

      {/* Gesture context menu (real right-click affordance) */}
      <GestureContextMenu
        open={contextMenu.open && !isEmergencyStopped}
        position={contextMenu.position}
        actions={CONTEXT_MENU_ACTIONS.map((a) => ({
          ...a,
          disabled:
            (a.action === 'next_step' && currentStepIndex >= task.steps.length - 1) ||
            (a.action === 'previous_step' && currentStepIndex === 0) ||
            (a.action === 'resume_session' && !isInteractionPaused && !isEmergencyStopped),
        }))}
        onAction={(action, label) => handleActionTriggered(action, 'context-menu', { displayCommand: label })}
        onClose={() => setContextMenu({ open: false, position: null })}
      />

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
          Station: {session?.stationId || 'Assembly 4B'} • Language: {language.toUpperCase()} • Mode: {modality.toUpperCase()}
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
            Clear Lockout &amp; Resume
          </button>
        </div>
      )}

      {/* Paused banner */}
      {isInteractionPaused && !isEmergencyStopped && (
        <div
          role="status"
          style={{
            background: 'rgba(245, 158, 11, 0.18)',
            border: '2px solid var(--accent-amber)',
            color: 'var(--text-primary)',
            padding: '1rem 2rem',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.6rem' }}>⏸️</span>
            <div>
              <strong style={{ display: 'block' }}>Interaction Paused</strong>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Task actions suspended. Pointer and UI navigation stay live. Say &quot;resume&quot; to continue.
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleResume}
            className="btn btn-primary"
            style={{ minHeight: '48px', background: 'var(--org-emerald)', borderColor: 'var(--org-emerald)' }}
          >
            ▶️ Resume
          </button>
        </div>
      )}

      {/* Emergency Stop Failure Warning */}
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
                Command <strong>“{pendingConfirmation.displayCommand}”</strong> requires confirmation before execution.
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
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span>💡</span>
          <span>
            <strong>Status:</strong> {statusMessage}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={isInteractionPaused ? handleResume : handlePause}
            className="btn btn-secondary"
            style={{ minHeight: '48px', padding: '0.5rem 1.1rem', fontSize: '0.85rem', fontWeight: 600 }}
          >
            {isInteractionPaused ? '▶️ Resume' : '⏸️ Pause'}
          </button>
          <button
            type="button"
            onClick={handleEndWork}
            className="btn btn-secondary"
            style={{ minHeight: '48px', padding: '0.5rem 1.25rem', fontSize: '0.88rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center' }}
          >
            🏁 {t('end_work_btn', language)}
          </button>
        </div>
      </div>

      {isSessionEnded ? (
        /* End Work Summary Card */
        <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', border: '2px solid var(--org-emerald)' }}>
          <span style={{ fontSize: '4rem', display: 'block', marginBottom: '1rem' }}>🏁</span>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--org-emerald)' }}>
            Work Session Successfully Closed
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0.75rem auto 1.5rem auto' }}>
            Authoritative workflow execution records and task completion outcome have been saved to PostgreSQL.
          </p>

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
              loadWorkstationData();
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
            completedStepIds={completedStepIds}
            onNextStep={handleNextStep}
            onPreviousStep={handlePreviousStep}
            onCompleteStep={handleCompleteStep}
            onRequestAssistance={() => setIsAssistanceOpen(true)}
            onEmergencyStop={handleEmergencyStop}
          >
            {/* Real drag & drop assembly bench for the current step */}
            <AssemblyDragBench
              partId={currentStep.id}
              partLabel={currentStep.spatialTargetId || `Step ${currentStep.stepNumber} Component`}
              zoneLabel={`Assembly Zone — Step ${currentStep.stepNumber}`}
              installed={Boolean(installedParts[currentStep.id]) || currentStepCompleted}
              onPartInstalled={handlePartInstalled}
            />
          </WorkflowStepViewer>

          <MultimodalHUD
            onActionTriggered={handleActionTriggered}
            workSessionId={session?.id || null}
            dwellTimeMs={Number(calibration?.dwell_time_ms) || 500}
            isEmergencyStopped={isEmergencyStopped}
            onRawHandFrame={handleRawHandFrame}
            externalGestureRef={engineGestureRef}
          />

          {/* Worker-personalized gesture mapping + calibration (PostgreSQL) */}
          <GestureControlPanel
            gestureActionMap={gestureMap}
            sources={gestureMapSources}
            calibration={calibration}
            onMappingChanged={handleMappingChanged}
            enabledGesturesList={GESTURE_CHOICE_LIST}
            actionChoices={ACTION_CHOICES}
          />
        </div>
      )}

      {/* Multilingual Assistance Modal (§ 20, § 21) — only with a real
          PostgreSQL work session (no placeholder session ids) */}
      {session?.id ? (
        <AssistanceModal
          isOpen={isAssistanceOpen}
          onClose={() => setIsAssistanceOpen(false)}
          workSessionId={session.id}
        />
      ) : isAssistanceOpen ? (
        <div
          role="alert"
          className="glass-panel"
          style={{
            position: 'fixed',
            bottom: '1.5rem',
            right: '1.5rem',
            padding: '1rem 1.5rem',
            borderRadius: '12px',
            borderColor: 'rgba(245, 158, 11, 0.5)',
            zIndex: 95,
            maxWidth: '380px',
          }}
        >
          <strong style={{ color: 'var(--accent-amber)' }}>⚠ No active work session</strong>
          <p style={{ fontSize: '0.85rem', marginTop: '0.35rem' }}>
            Assistance requests are tied to a real work session. Please start your work session
            first, then request assistance.
          </p>
        </div>
      ) : null}
    </div>
  );
}
