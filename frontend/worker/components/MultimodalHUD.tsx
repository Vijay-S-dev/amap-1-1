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

export type MicLifecycleState =
  | 'MIC_IDLE'
  | 'MIC_REQUESTING_PERMISSION'
  | 'MIC_READY'
  | 'LISTENING'
  | 'MIC_ERROR'
  | 'MIC_STOPPED';

interface MultimodalHUDProps {
  onActionTriggered: (actionName: string, sourceModality: string) => void;
  dwellTimeMs?: number;
}

export function MultimodalHUD({ onActionTriggered, dwellTimeMs = 500 }: MultimodalHUDProps) {
  const { language, modality, setModality, announce, playAudioCue } = useAccessibility();

  // Active Modalities
  const isGestureActive = modality === 'gesture' || modality === 'multimodal';
  const isVoiceActive = modality === 'voice' || modality === 'multimodal';

  // Hardware State Machines (FR-01)
  const [cameraState, setCameraState] = useState<CameraLifecycleState>(
    isGestureActive ? 'CAMERA_REQUESTING_PERMISSION' : 'CAMERA_STOPPED'
  );
  const [micState, setMicState] = useState<MicLifecycleState>(
    isVoiceActive ? 'MIC_REQUESTING_PERMISSION' : 'MIC_STOPPED'
  );
  const [micErrorMessage, setMicErrorMessage] = useState<string>('');
  const [micRetryTrigger, setMicRetryTrigger] = useState<number>(0);

  // Recognition States
  const [activeGesture, setActiveGesture] = useState<string | null>(null);
  const [activeVoiceCommand, setActiveVoiceCommand] = useState<string>('standby');
  const [hasHandInView, setHasHandInView] = useState<boolean>(false);
  const [conflictWarning, setConflictWarning] = useState<string>('');
  const [lastExecutedAction, setLastExecutedAction] = useState<string | null>(null);

  // References for Speech Recognition
  const recognitionRef = useRef<any>(null);

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

  // One-Shot Confirmed Gesture Execution (Enforces Release Latch)
  const handleGestureConfirmed = async (gesture: string) => {
    if (!isGestureActive) return;

    // 1. Cross-Modal Conflict Check (§ 33: Voice=Stop vs Gesture=Thumbs Up)
    if (gesture === 'THUMBS_UP' && activeVoiceCommand === 'stop') {
      const conflictMsg =
        '⚠️ Cross-Modal Conflict Detected! Modalities disagreed (Voice: Stop vs Gesture: Thumbs Up). Action suspended for safety.';
      setConflictWarning(conflictMsg);
      announce(conflictMsg);
      playAudioCue('alert');
      return;
    }

    setConflictWarning('');

    const targetAction =
      gesture === 'THUMBS_UP'
        ? 'confirm_action'
        : gesture === 'POINTING'
        ? 'next_step'
        : gesture === 'OPEN_PALM'
        ? 'pause_session'
        : gesture === 'FIST'
        ? 'emergency_stop'
        : null;

    if (targetAction) {
      setLastExecutedAction(targetAction);
      onActionTriggered(targetAction, 'gesture');
      announce(`Physical Gesture Confirmed: ${gesture}`);
      playAudioCue('confirm');
    }
  };

  // Web Speech API Listener with Hardware Isolation & Bounded Factory Vocabulary
  useEffect(() => {
    // Hardware Isolation: If Voice is inactive, stop and teardown SpeechRecognition
    if (!isVoiceActive) {
      setMicState('MIC_STOPPED');
      setMicErrorMessage('');
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
        recognitionRef.current = null;
      }
      return;
    }

    let isMounted = true;
    let recognitionInstance: any = null;
    let lastVoiceTime = 0;

    try {
      setMicState('MIC_REQUESTING_PERMISSION');
      setMicErrorMessage('');

      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

      if (!SpeechRecognition) {
        setMicState('MIC_ERROR');
        setMicErrorMessage(t('mic_unavailable', language));
        return;
      }

      recognitionInstance = new SpeechRecognition();
      recognitionRef.current = recognitionInstance;
      recognitionInstance.continuous = true;
      recognitionInstance.interimResults = false;

      // Set language for Web Speech API
      const speechLangMap: Record<string, string> = {
        en: 'en-US',
        es: 'es-ES',
        ta: 'ta-IN',
        hi: 'hi-IN',
        de: 'de-DE',
      };
      recognitionInstance.lang = speechLangMap[language] || 'en-US';

      recognitionInstance.onstart = () => {
        if (!isMounted) return;
        setMicState('LISTENING');
        announce(t('mic_sr_ready', language));
      };

      recognitionInstance.onerror = (event: any) => {
        if (!isMounted) return;
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          setMicState('MIC_ERROR');
          setMicErrorMessage(t('mic_access_denied', language));
        } else if (event.error === 'no-speech') {
          // Normal boundary silence, keep state as LISTENING
          setMicState('LISTENING');
        } else {
          setMicState('MIC_ERROR');
          setMicErrorMessage(t('mic_unavailable', language));
        }
      };

      recognitionInstance.onend = () => {
        if (!isMounted) return;
        // Auto restart if voice mode remains active
        if (isVoiceActive) {
          try {
            recognitionInstance.start();
          } catch {
            setMicState('MIC_READY');
          }
        } else {
          setMicState('MIC_STOPPED');
        }
      };

      recognitionInstance.onresult = async (event: any) => {
        if (!isMounted) return;
        const now = Date.now();
        if (now - lastVoiceTime < 500) return;
        lastVoiceTime = now;

        const rawTranscript = event.results[event.results.length - 1][0].transcript.trim();
        if (!rawTranscript) return;

        try {
          const res = await api.processVoiceCommand({ raw_transcript: rawTranscript });
          if (res.validation_status === 'valid' && res.action_mapping) {
            const action = res.action_mapping;
            setActiveVoiceCommand(res.matched_command || action);

            // Cross-Modal Conflict Check (§ 33: Voice=Stop vs Gesture=Thumbs Up)
            if (action === 'emergency_stop' || action === 'pause_session') {
              if (activeGesture === 'THUMBS_UP') {
                setConflictWarning('⚠️ Conflict: Voice said "Stop" but hand is Thumbs Up (Confirm). Action suspended.');
                playAudioCue('alert');
                return;
              }
            } else if (action === 'confirm_action') {
              if (activeGesture === 'OPEN_PALM') {
                setConflictWarning('⚠️ Conflict: Voice said "Confirm" but hand is Open Palm (Pause). Action suspended.');
                playAudioCue('alert');
                return;
              }
            }

            setConflictWarning('');
            onActionTriggered(action, 'voice');
            announce(`Voice Command Confirmed: ${res.matched_command || action}`);
            playAudioCue(action === 'emergency_stop' ? 'alert' : 'confirm');
          }
        } catch (err) {
          console.error('Voice processing error in HUD:', err);
        }
      };

      recognitionInstance.start();
      setMicState('MIC_READY');
    } catch (err) {
      console.error('Speech recognition initialization error:', err);
      setMicState('MIC_ERROR');
      setMicErrorMessage(t('mic_unavailable', language));
    }

    return () => {
      isMounted = false;
      if (recognitionInstance) {
        try {
          recognitionInstance.stop();
        } catch {}
      }
    };
  }, [isVoiceActive, micRetryTrigger, language, activeGesture, announce, onActionTriggered, playAudioCue]);

  const handleRetryMic = () => {
    setMicErrorMessage('');
    setMicRetryTrigger((prev) => prev + 1);
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
                        ? `✓ ${activeGesture}`
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
                    ) : (
                      <span className="badge badge-rose">❌ {t('mic_status_error', language)}</span>
                    )
                  ) : (
                    <span className="badge badge-muted">⏹️ {t('mic_status_idle', language)}</span>
                  )}
                </div>
              </div>

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

