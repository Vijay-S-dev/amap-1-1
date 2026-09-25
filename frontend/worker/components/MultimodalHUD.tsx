'use client';

/**
 * Worker Multimodal HUD Component (§ 16, § 17, § 28, FR-01)
 * Enforces the strict Two-Layer recognition invariant:
 * - Layer 1: Hand Presence Gate (No hand = No gesture = No intent)
 * - Layer 2: Geometric Gesture Classification + Release Latch (One-shot execution)
 * - Cross-Modal Intent Fusion & Conflict Arbitration (Voice vs Gesture)
 * - FR-01 Input Capture: Microphone & Camera Lifecycles, Hardware Isolation, Accessible Status
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MediaPipeHandTracker, CameraLifecycleState } from '@/worker/components/MediaPipeHandTracker';
import { useAccessibility, InteractionModality } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { api } from '@/shared/api/client';
import { useVoiceRecorder, VoiceRecorderState, TranscriptionResult } from '@/shared/hooks/useVoiceRecorder';
import { MultimodalFusionResult, MultimodalInputItem } from '@/shared/types';

export type MicLifecycleState =
  | 'MIC_IDLE'
  | 'MIC_REQUESTING_PERMISSION'
  | 'MIC_READY'
  | 'LISTENING'
  | 'PROCESSING'
  | 'MIC_ERROR'
  | 'MIC_STOPPED';

interface MultimodalHUDProps {
  onActionTriggered: (
    actionName: string,
    sourceModality: string,
    options?: { requiresConfirmation?: boolean; displayCommand?: string }
  ) => void;
  dwellTimeMs?: number;
  isEmergencyStopped?: boolean;
}

export function MultimodalHUD({
  onActionTriggered,
  dwellTimeMs = 500,
  isEmergencyStopped = false,
}: MultimodalHUDProps) {
  const { language, modality, setModality, announce, playAudioCue } = useAccessibility();

  // Active Modalities
  const isGestureActive = modality === 'gesture' || modality === 'multimodal';
  const isVoiceActive = modality === 'voice' || modality === 'multimodal';
  const sttLanguage = language === 'hi' ? 'hi' : 'en';

  // Hardware State Machines (FR-01)
  const [cameraState, setCameraState] = useState<CameraLifecycleState>(
    isGestureActive ? 'CAMERA_REQUESTING_PERMISSION' : 'CAMERA_STOPPED'
  );
  const [micState, setMicState] = useState<MicLifecycleState>(
    isVoiceActive ? 'MIC_REQUESTING_PERMISSION' : 'MIC_STOPPED'
  );
  const [micErrorMessage, setMicErrorMessage] = useState<string>('');

  // Recognition States
  const [activeGesture, setActiveGesture] = useState<string | null>(null);
  const [gestureConfidence, setGestureConfidence] = useState<number>(0);
  const [activeVoiceCommand, setActiveVoiceCommand] = useState<string>('standby');
  const [hasHandInView, setHasHandInView] = useState<boolean>(false);
  const [conflictWarning, setConflictWarning] = useState<string>('');
  const [lastExecutedAction, setLastExecutedAction] = useState<string | null>(null);
  const [lastTranscript, setLastTranscript] = useState<string>('');
  const [voiceLatencyMs, setVoiceLatencyMs] = useState<number>(0);
  const recordingStartedAtRef = useRef<number>(0);
  const lastVoiceProcessedTimeRef = useRef<number>(0);
  const isVoiceProcessingRef = useRef<boolean>(false);
  const lastPerceivedGestureRef = useRef<{ gesture: string; confidence: number; timestamp: number } | null>(null);
  const lastPerceivedVoiceRef = useRef<{ action: string; command: string; confidence: number; timestamp: number } | null>(null);
  const lastDispatchedExecutionRef = useRef<{ action: string; timestamp: number } | null>(null);

  // Sync Camera Lifecycle Callback from MediaPipeHandTracker
  const handleCameraStateChange = useCallback(
    (state: CameraLifecycleState) => {
      setCameraState(state);
      if (state === 'CAMERA_ACTIVE') {
        announce(t('camera_sr_ready', language));
      }
    },
    [announce, language]
  );

  // Unified Multimodal Action Candidate Dispatcher
  // Enforces:
  // - Emergency Stop Priority (immediate lockout, requires_confirmation = false)
  // - De-duplication latch: Exactly ONE execution request and ONE database event for agreeing modalities
  // - Safe conflict suspension (no automatic unsafe execution)
  const processFusedMultimodalCandidate = useCallback(
    async (
      fusedResult: MultimodalFusionResult,
      fallbackDisplay?: string
    ) => {
      const now = Date.now();

      // 1. Ambiguous Conflict Check
      if (fusedResult.validation_status === 'ambiguous') {
        const conflictMsg =
          fusedResult.message ||
          '⚠️ Cross-Modal Conflict Detected! Modalities disagreed. Action suspended for safety.';
        setConflictWarning(conflictMsg);
        announce(conflictMsg);
        playAudioCue('alert');
        return;
      }

      // 2. Rejection Check (stale, low confidence, unknown)
      if (fusedResult.validation_status === 'rejected') {
        if (fusedResult.message) {
          setConflictWarning(`⚠️ ${fusedResult.message}`);
          announce(fusedResult.message);
          playAudioCue('alert');
        }
        return;
      }

      const action = fusedResult.fused_action;
      if (!action) return;

      // 3. De-duplication Latch: If this exact action was already dispatched within 1200ms, skip duplicate
      if (
        lastDispatchedExecutionRef.current &&
        lastDispatchedExecutionRef.current.action === action &&
        now - lastDispatchedExecutionRef.current.timestamp < 1200
      ) {
        return;
      }

      setConflictWarning('');

      // 4. Emergency Stop: Immediate fail-safe execution without confirmation
      if (action === 'emergency_stop') {
        lastDispatchedExecutionRef.current = { action: 'emergency_stop', timestamp: now };
        setLastExecutedAction('emergency_stop');
        onActionTriggered('emergency_stop', 'multimodal', { requiresConfirmation: false });
        announce('Emergency Stop Confirmed Across Modalities!');
        playAudioCue('alert');
        return;
      }

      // 5. Staged confirmation gating
      if (fusedResult.requires_confirmation) {
        lastDispatchedExecutionRef.current = { action, timestamp: now };
        onActionTriggered(action, 'multimodal', {
          requiresConfirmation: true,
          displayCommand: fallbackDisplay || action,
        });
        announce(`Command '${fallbackDisplay || action}' requires confirmation.`);
        playAudioCue('alert');
        return;
      }

      // 6. Normal execution
      lastDispatchedExecutionRef.current = { action, timestamp: now };
      setLastExecutedAction(action);
      onActionTriggered(action, 'multimodal', {
        requiresConfirmation: false,
        displayCommand: fallbackDisplay || action,
      });
      announce(`Command Confirmed: ${fallbackDisplay || action}`);
      playAudioCue('confirm');
    },
    [announce, onActionTriggered, playAudioCue]
  );

  // One-Shot Confirmed Gesture Execution (Enforces Multimodal Fusion & Release Latch)
  const handleGestureConfirmed = async (gesture: string) => {
    if (!isGestureActive) return;
    const now = Date.now();
    const rawConf = gestureConfidence > 0 ? gestureConfidence : 90;
    const conf = rawConf > 1 ? Number((rawConf / 100).toFixed(2)) : rawConf;
    lastPerceivedGestureRef.current = { gesture, confidence: conf, timestamp: now };

    const inputs: MultimodalInputItem[] = [
      {
        mode: 'gesture',
        raw_intent: gesture.toLowerCase(),
        confidence: conf,
        timestamp_ms: now,
      },
    ];

    // Check for concurrent voice command in the 1500ms temporal window
    if (
      lastPerceivedVoiceRef.current &&
      now - lastPerceivedVoiceRef.current.timestamp <= 1500
    ) {
      inputs.push({
        mode: 'voice',
        raw_intent: lastPerceivedVoiceRef.current.action,
        confidence: lastPerceivedVoiceRef.current.confidence,
        timestamp_ms: lastPerceivedVoiceRef.current.timestamp,
      });
    }

    try {
      const fusedResult = await api.processMultimodalIntent({
        inputs,
        temporal_window_ms: 1500,
      });
      await processFusedMultimodalCandidate(fusedResult, gesture);
    } catch (err: any) {
      setConflictWarning(`Multimodal arbitration unavailable: ${err?.message || 'Server error'}`);
    }
  };

  const handleVoiceTranscript = useCallback(async (result: TranscriptionResult) => {
    // Emergency Stop Voice Lockout
    if (isEmergencyStopped) {
      return;
    }

    const now = Date.now();
    // Debounce latch (~500ms) and in-flight processing guard
    if (now - lastVoiceProcessedTimeRef.current < 500 || isVoiceProcessingRef.current) {
      return;
    }
    lastVoiceProcessedTimeRef.current = now;
    isVoiceProcessingRef.current = true;

    const transcript = result.transcript.trim();
    setLastTranscript(transcript);
    const startedAt = recordingStartedAtRef.current || performance.now();
    try {
      const command = await api.processVoiceCommand({
        raw_transcript: transcript,
        confidence: result.confidence,
        language: result.detected_language,
      });
      setVoiceLatencyMs(Math.round(performance.now() - startedAt));

      // Unmatched commands: give feedback to worker, do not proceed
      if (!command.action_mapping) {
        setActiveVoiceCommand(null);
        setMicErrorMessage(command.message || 'Command not recognized. Please try again.');
        announce(command.message || 'Voice command not recognized.');
        return;
      }

      const action = command.action_mapping;
      const displayCmd = command.matched_command || action;
      setActiveVoiceCommand(displayCmd);
      lastPerceivedVoiceRef.current = {
        action,
        command: displayCmd,
        confidence: result.confidence,
        timestamp: now,
      };

      const inputs: MultimodalInputItem[] = [
        {
          mode: 'voice',
          raw_intent: action,
          confidence: result.confidence,
          timestamp_ms: now,
        },
      ];

      // Check for concurrent gesture in the 1500ms temporal window
      if (
        lastPerceivedGestureRef.current &&
        now - lastPerceivedGestureRef.current.timestamp <= 1500
      ) {
        const rawGConf = lastPerceivedGestureRef.current.confidence;
        const gConf = rawGConf > 1 ? Number((rawGConf / 100).toFixed(2)) : rawGConf;
        inputs.push({
          mode: 'gesture',
          raw_intent: lastPerceivedGestureRef.current.gesture.toLowerCase(),
          confidence: gConf,
          timestamp_ms: lastPerceivedGestureRef.current.timestamp,
        });
      }

      const fusedResult = await api.processMultimodalIntent({
        inputs,
        temporal_window_ms: 1500,
      });

      // Combine confirmation requirements: fusion, voice service, and low_confidence
      const needsConfirmation = fusedResult.requires_confirmation ||
        command.requires_confirmation ||
        command.validation_status === 'low_confidence';
      if (needsConfirmation) {
        fusedResult.requires_confirmation = true;
        fusedResult.requiresConfirmation = true;
      }

      await processFusedMultimodalCandidate(fusedResult, displayCmd);
    } catch (err) {
      setMicErrorMessage(err instanceof Error ? err.message : t('mic_unavailable', language));
    } finally {
      isVoiceProcessingRef.current = false;
    }
  }, [isEmergencyStopped, language, processFusedMultimodalCandidate]);

  const handleRecorderError = useCallback((message: string) => {
    setMicErrorMessage(message);
  }, []);

  const handleRecorderState = useCallback((next: VoiceRecorderState) => {
    const stateMap: Record<VoiceRecorderState, MicLifecycleState> = {
      IDLE: 'MIC_STOPPED',
      REQUESTING_MIC: 'MIC_REQUESTING_PERMISSION',
      READY: 'MIC_READY',
      RECORDING: 'LISTENING',
      PROCESSING: 'PROCESSING',
      ERROR: 'MIC_ERROR',
    };
    setMicState(stateMap[next]);
    if (next === 'READY') setMicErrorMessage('');
  }, []);

  const recorder = useVoiceRecorder({
    enabled: isVoiceActive && !isEmergencyStopped,
    language: sttLanguage,
    onTranscript: handleVoiceTranscript,
    onError: handleRecorderError,
    onStateChange: handleRecorderState,
  });

  const handleRetryMic = () => {
    setMicErrorMessage('');
    recorder.startRecording();
  };

  const handleModeSelect = (newModality: InteractionModality) => {
    setModality(newModality);
    playAudioCue('step');
    announce(`Switched interaction mode to: ${newModality}`);
  };

  return (
    <div
      className="glass-panel"
      style={{
        padding: '1.5rem',
        borderRadius: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}
    >
      {/* Top Header with Modality Selector (FR-01 Section 9 & 10) */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.5rem' }}>👁️🎙️</span>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Multimodal Input Capture Engine (FR-01)
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Active Modality: <strong style={{ color: 'var(--worker-cyan)' }}>{modality.toUpperCase()}</strong> • Strict Hardware Isolation
            </span>
          </div>
        </div>

        {/* 48px Touch Target Mode Switcher */}
        <div
          role="group"
          aria-label="Select Input Modality"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(255, 255, 255, 0.05)',
            padding: '0.35rem',
            borderRadius: '14px',
            border: '1px solid var(--surface-glass-border)',
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            onClick={() => handleModeSelect('gesture')}
            aria-pressed={modality === 'gesture'}
            className={`btn ${modality === 'gesture' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              minHeight: '48px',
              padding: '0.5rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            🖐️ {t('input_mode_gesture', language)}
          </button>

          <button
            type="button"
            onClick={() => handleModeSelect('voice')}
            aria-pressed={modality === 'voice'}
            className={`btn ${modality === 'voice' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              minHeight: '48px',
              padding: '0.5rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            🎙️ {t('input_mode_voice', language)}
          </button>

          <button
            type="button"
            onClick={() => handleModeSelect('multimodal')}
            aria-pressed={modality === 'multimodal'}
            className={`btn ${modality === 'multimodal' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              minHeight: '48px',
              padding: '0.5rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            ⚡ {t('input_mode_both', language)}
          </button>
        </div>
      </div>

      {/* Cross-Modal Conflict Warning (§ 33) */}
      {conflictWarning && (
        <div
          role="alert"
          style={{
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid var(--accent-rose)',
            color: 'var(--accent-rose)',
            padding: '0.75rem 1.25rem',
            borderRadius: '12px',
            fontSize: '0.88rem',
            fontWeight: 700,
          }}
        >
          {conflictWarning}
        </div>
      )}

      {/* Main HUD Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* Real MediaPipe Hand Tracker with enabled hardware isolation */}
        <div>
          <MediaPipeHandTracker
            height="240px"
            showLabels={false}
            requiredDwellMs={dwellTimeMs}
            enabled={isGestureActive}
            onCameraStateChange={handleCameraStateChange}
            onHandPresenceChange={(present) => {
              setHasHandInView(present);
              if (!present) setActiveGesture(null);
            }}
            onGestureDetected={(g, conf) => {
              setActiveGesture(g !== 'NONE' && g !== 'UNKNOWN' ? g : null);
              setGestureConfidence(Math.round(conf * 100));
            }}
            onGestureConfirmed={handleGestureConfirmed}
          />
        </div>

        {/* Live Input Channels & Telemetry Status Cards (Section 11: Text + Icons) */}
        <div
          className="glass-card"
          style={{
            padding: '1.25rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 800,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              INPUT CAPTURE STATUS (FR-01)
            </span>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.75rem' }}>
              {/* Camera Channel Status Card */}
              <div
                role="status"
                aria-label={`Camera status: ${cameraState}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--surface-glass-border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.1rem' }}>📷</span>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {t('camera_label', language)}:
                  </span>
                </div>
                <div>
                  {isGestureActive ? (
                    cameraState === 'CAMERA_ACTIVE' ? (
                      <span className="badge badge-emerald">● {t('camera_status_ready', language)}</span>
                    ) : cameraState === 'CAMERA_REQUESTING_PERMISSION' ? (
                      <span className="badge badge-amber">⏳ {t('camera_status_requesting', language)}</span>
                    ) : (
                      <span className="badge badge-rose">❌ {t('camera_status_error', language)}</span>
                    )
                  ) : (
                    <span className="badge badge-muted">⏹️ {t('camera_status_idle', language)}</span>
                  )}
                </div>
              </div>

              {/* Hand Detection Layer */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.03)',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {t('hand_input_label', language)}:
                </span>
                <span className={hasHandInView ? 'badge badge-emerald' : 'badge badge-rose'}>
                  {isGestureActive
                    ? hasHandInView
                      ? activeGesture
                        ? `✓ ${activeGesture} (CONF: ${gestureConfidence}%)`
                        : '● Hand In View'
                      : '○ Waiting'
                    : '— Inactive'}
                </span>
              </div>

              {/* Microphone Channel Status Card */}
              <div
                role="status"
                aria-label={`Microphone status: ${micState}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--surface-glass-border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.1rem' }}>🎙️</span>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {t('microphone_label', language)}:
                  </span>
                </div>
                <div>
                  {isVoiceActive ? (
                    micState === 'LISTENING' || micState === 'MIC_READY' ? (
                      <span className="badge badge-emerald">● {t('mic_status_ready', language)}</span>
                    ) : micState === 'MIC_REQUESTING_PERMISSION' ? (
                      <span className="badge badge-amber">⏳ {t('mic_status_requesting', language)}</span>
                    ) : micState === 'PROCESSING' ? (
                      <span className="badge badge-cyan">⏳ Processing</span>
                    ) : (
                      <span className="badge badge-rose">❌ {t('mic_status_error', language)}</span>
                    )
                  ) : (
                    <span className="badge badge-muted">⏹️ {t('mic_status_idle', language)}</span>
                  )}
                </div>
              </div>

              {isVoiceActive && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => {
                      if (recorder.state === 'RECORDING') {
                        recorder.stopRecording();
                      } else {
                        recordingStartedAtRef.current = performance.now();
                        recorder.startRecording();
                      }
                    }}
                    disabled={isEmergencyStopped || recorder.state === 'PROCESSING' || micState === 'MIC_REQUESTING_PERMISSION'}
                    className={`btn ${recorder.state === 'RECORDING' ? 'btn-danger' : 'btn-primary'}`}
                    style={{ minHeight: '52px', fontWeight: 800, fontSize: '1rem' }}
                  >
                    {isEmergencyStopped
                      ? '🛑 Mic Locked'
                      : recorder.state === 'RECORDING'
                      ? '⏹️ Stop Recording'
                      : recorder.state === 'PROCESSING'
                      ? '⏳ Transcribing…'
                      : '🎙️ Speak'}
                  </button>
                  <span style={{ fontSize: '0.75rem', color: isEmergencyStopped ? 'var(--accent-rose)' : 'var(--text-muted)', textAlign: 'center', fontWeight: isEmergencyStopped ? 700 : 400 }}>
                    {isEmergencyStopped
                      ? 'Microphone locked during emergency stop. Clear lockout to resume.'
                      : recorder.state === 'RECORDING'
                      ? 'Click to stop immediately, or pause speech for 1.5s'
                      : 'Push to talk — click to speak, click again to stop'}
                  </span>
                  {lastTranscript && (
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      Last transcript: <strong style={{ color: '#fff' }}>“{lastTranscript}”</strong> · {voiceLatencyMs}ms
                    </span>
                  )}
                </div>
              )}

              {/* Listening State */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '10px',
                  background: 'rgba(255, 255, 255, 0.03)',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {t('listening_label', language)}:
                </span>
                <span className={isVoiceActive ? 'badge badge-emerald' : 'badge badge-muted'}>
                  {isVoiceActive ? `🎙️ "${activeVoiceCommand}"` : '— Inactive'}
                </span>
              </div>
            </div>

            {/* Mic Error Prompt & Retry (FR-01 Section 8) */}
            {isVoiceActive && micErrorMessage && (
              <div
                role="alert"
                style={{
                  marginTop: '0.75rem',
                  padding: '0.75rem',
                  borderRadius: '10px',
                  background: 'rgba(244, 63, 94, 0.15)',
                  border: '1px solid var(--accent-rose)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                }}
              >
                <span style={{ fontSize: '0.82rem', color: 'var(--accent-rose)', fontWeight: 600 }}>
                  ⚠️ {micErrorMessage}
                </span>
                <button
                  type="button"
                  onClick={handleRetryMic}
                  className="btn btn-secondary"
                  style={{
                    minHeight: '48px',
                    padding: '0.4rem 0.8rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                  }}
                >
                  🔄 {t('try_again_btn', language)}
                </button>
              </div>
            )}
          </div>

          {/* Last Executed Action Display (Latch invariant) */}
          <div
            style={{
              padding: '0.65rem 0.85rem',
              background: 'rgba(255, 255, 255, 0.04)',
              borderRadius: '10px',
            }}
          >
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              LAST EXECUTED INTENT (ONE-SHOT LATCH)
            </span>
            <strong style={{ fontSize: '0.9rem', color: 'var(--worker-cyan)' }}>
              {lastExecutedAction ? `✓ ${lastExecutedAction}` : 'Awaiting Input'}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MultimodalHUD;
