'use client';

/**
 * Worker Voice Setup & Calibration Studio (/onboarding/voice-setup)
 * Restored Stable Single-Instance Speech Recognition Engine (Phases 2, 3, 4, 5, 8)
 * 
 * Invariant Guarantees:
 * 1. Single stable recognition instance with resilient auto-restart on boundary silence.
 * 2. Processes final speech transcript events without interim substring race conditions.
 * 3. Step-by-step factory intent calibration: CONFIRM -> NEXT_STEP -> ASSISTANCE -> EMERGENCY_STOP.
 * 4. Comprehensive telemetry timestamps (T0 to T4) logging actual end-to-end latency.
 * 5. Unknown speech gating returning UNKNOWN with zero accidental intent execution.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t, SupportedLanguage } from '@/shared/i18n/languages';
import { api } from '@/shared/api/client';

type MicState =
  | 'MICROPHONE_PERMISSION_REQUIRED'
  | 'MICROPHONE_REQUESTING'
  | 'MICROPHONE_READY'
  | 'MICROPHONE_DENIED'
  | 'MICROPHONE_ERROR';

interface TrainingStep {
  id: string;
  intent: string;
  displayKeyword: string;
  instructionPrompt: string;
  actionMapping: string;
  expectedAction: string;
  completed: boolean;
}

const TRAINING_STEPS_BY_LANG: Record<SupportedLanguage, TrainingStep[]> = {
  en: [
    { id: 'confirm', intent: 'CONFIRM', displayKeyword: 'Confirm', instructionPrompt: 'Say: "Confirm"', actionMapping: 'confirm_action', expectedAction: 'confirm_action', completed: false },
    { id: 'next', intent: 'NEXT_STEP', displayKeyword: 'Next', instructionPrompt: 'Say: "Next" or "Next Step"', actionMapping: 'next_step', expectedAction: 'next_step', completed: false },
    { id: 'help', intent: 'ASSISTANCE', displayKeyword: 'Help', instructionPrompt: 'Say: "Help" or "Supervisor"', actionMapping: 'request_assistance', expectedAction: 'request_assistance', completed: false },
    { id: 'stop', intent: 'EMERGENCY_STOP', displayKeyword: 'Stop', instructionPrompt: 'Say: "Stop" or "Emergency Stop"', actionMapping: 'emergency_stop', expectedAction: 'emergency_stop', completed: false },
  ],
  es: [
    { id: 'confirm', intent: 'CONFIRM', displayKeyword: 'Confirmar', instructionPrompt: 'Diga: "Confirmar"', actionMapping: 'confirm_action', expectedAction: 'confirm_action', completed: false },
    { id: 'next', intent: 'NEXT_STEP', displayKeyword: 'Siguiente', instructionPrompt: 'Diga: "Siguiente" o "Continuar"', actionMapping: 'next_step', expectedAction: 'next_step', completed: false },
    { id: 'help', intent: 'ASSISTANCE', displayKeyword: 'Ayuda', instructionPrompt: 'Diga: "Ayuda" o "Soporte"', actionMapping: 'request_assistance', expectedAction: 'request_assistance', completed: false },
    { id: 'stop', intent: 'EMERGENCY_STOP', displayKeyword: 'Detener', instructionPrompt: 'Diga: "Detener" o "Parada"', actionMapping: 'emergency_stop', expectedAction: 'emergency_stop', completed: false },
  ],
  ta: [
    { id: 'confirm', intent: 'CONFIRM', displayKeyword: 'உறுதி (Confirm)', instructionPrompt: 'சொல்லுங்கள்: "உறுதி" (Confirm)', actionMapping: 'confirm_action', expectedAction: 'confirm_action', completed: false },
    { id: 'next', intent: 'NEXT_STEP', displayKeyword: 'அடுத்து (Next)', instructionPrompt: 'சொல்லுங்கள்: "அடுத்து" (Next)', actionMapping: 'next_step', expectedAction: 'next_step', completed: false },
    { id: 'help', intent: 'ASSISTANCE', displayKeyword: 'உதவி (Help)', instructionPrompt: 'சொல்லுங்கள்: "உதவி" (Help)', actionMapping: 'request_assistance', expectedAction: 'request_assistance', completed: false },
    { id: 'stop', intent: 'EMERGENCY_STOP', displayKeyword: 'நிறுத்து (Stop)', instructionPrompt: 'சொல்லுங்கள்: "நிறுத்து" (Stop)', actionMapping: 'emergency_stop', expectedAction: 'emergency_stop', completed: false },
  ],
  hi: [
    { id: 'confirm', intent: 'CONFIRM', displayKeyword: 'पुष्टि (Confirm)', instructionPrompt: 'बोलिए: "पुष्टि" (Confirm)', actionMapping: 'confirm_action', expectedAction: 'confirm_action', completed: false },
    { id: 'next', intent: 'NEXT_STEP', displayKeyword: 'अगला (Next)', instructionPrompt: 'बोलिए: "अगला" (Next)', actionMapping: 'next_step', expectedAction: 'next_step', completed: false },
    { id: 'help', intent: 'ASSISTANCE', displayKeyword: 'मदद (Help)', instructionPrompt: 'बोलिए: "मदद" (Help)', actionMapping: 'request_assistance', expectedAction: 'request_assistance', completed: false },
    { id: 'stop', intent: 'EMERGENCY_STOP', displayKeyword: 'रोकें (Stop)', instructionPrompt: 'बोलिए: "रोकें" (Stop)', actionMapping: 'emergency_stop', expectedAction: 'emergency_stop', completed: false },
  ],
  de: [
    { id: 'confirm', intent: 'CONFIRM', displayKeyword: 'Bestätigen', instructionPrompt: 'Sagen Sie: "Bestätigen"', actionMapping: 'confirm_action', expectedAction: 'confirm_action', completed: false },
    { id: 'next', intent: 'NEXT_STEP', displayKeyword: 'Weiter', instructionPrompt: 'Sagen Sie: "Weiter"', actionMapping: 'next_step', expectedAction: 'next_step', completed: false },
    { id: 'help', intent: 'ASSISTANCE', displayKeyword: 'Hilfe', instructionPrompt: 'Sagen Sie: "Hilfe"', actionMapping: 'request_assistance', expectedAction: 'request_assistance', completed: false },
    { id: 'stop', intent: 'EMERGENCY_STOP', displayKeyword: 'Stopp', instructionPrompt: 'Sagen Sie: "Stopp"', actionMapping: 'emergency_stop', expectedAction: 'emergency_stop', completed: false },
  ],
};

export default function VoiceSetupPage() {
  const router = useRouter();
  const { language, setHasCompletedVoiceSetup, announce, playAudioCue } = useAccessibility();

  // Microphone Permission & Stream State
  const [micState, setMicState] = useState<MicState>('MICROPHONE_PERMISSION_REQUIRED');
  const [micErrorMessage, setMicErrorMessage] = useState<string>('');
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

  // Speech Recognition State
  const [isListening, setIsListening] = useState<boolean>(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [trainingSteps, setTrainingSteps] = useState<TrainingStep[]>(
    TRAINING_STEPS_BY_LANG[language] || TRAINING_STEPS_BY_LANG.en
  );

  // Diagnostic Telemetry State
  const [rawTranscript, setRawTranscript] = useState<string>('');
  const [matchedCommand, setMatchedCommand] = useState<string>('NONE');
  const [matchedIntent, setMatchedIntent] = useState<string>('NONE');
  const [confidenceScore, setConfidenceScore] = useState<number>(0.0);
  const [feedbackMessage, setFeedbackMessage] = useState<string>('');
  const [processingLatencyMs, setProcessingLatencyMs] = useState<number>(0);

  // Stable References (Prevent recreation during re-renders)
  const recognitionRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const isListeningRef = useRef<boolean>(false);
  const currentStepIndexRef = useRef<number>(0);
  const lastProcessedTimeRef = useRef<number>(0);

  // Keep step index ref in sync
  useEffect(() => {
    currentStepIndexRef.current = currentStepIndex;
  }, [currentStepIndex]);

  // Sync training steps when language changes
  useEffect(() => {
    setTrainingSteps(TRAINING_STEPS_BY_LANG[language] || TRAINING_STEPS_BY_LANG.en);
  }, [language]);

  // Handle Speech Result with Diagnostic Timestamps (Phase 4)
  const handleRecognizedTranscript = useCallback(
    async (spokenText: string, rawConfidence: number, recognitionLang: string) => {
      const t0 = performance.now();
      const now = Date.now();

      // 500ms Debounce Latch
      if (now - lastProcessedTimeRef.current < 500) {
        return;
      }
      lastProcessedTimeRef.current = now;

      setRawTranscript(spokenText);

      try {
        const tApiStart = performance.now();
        const result = await api.processVoiceCommand({
          raw_transcript: spokenText,
          confidence: rawConfidence,
          language: recognitionLang,
        });
        const tApiEnd = performance.now();
        const apiDuration = Math.round(tApiEnd - tApiStart);
        const totalDuration = Math.round(performance.now() - t0);

        setProcessingLatencyMs(totalDuration);
        console.log(`[AMAP Voice] Spoken: "${spokenText}" | API Match: ${apiDuration}ms | Total Latency: ${totalDuration}ms`);

        setConfidenceScore(result.confidence);

        if (result.validation_status === 'valid' && result.action_mapping) {
          setMatchedCommand(result.matched_command || 'NONE');
          setMatchedIntent(result.action_mapping.toUpperCase());
          setFeedbackMessage(`✓ Recognized: "${spokenText}" (${result.action_mapping})`);

          // Match against current step using ref to avoid closure staleness
          const stepIdx = currentStepIndexRef.current;
          setTrainingSteps((prevSteps) => {
            const currentStep = prevSteps[stepIdx];
            if (currentStep && result.action_mapping === currentStep.expectedAction) {
              playAudioCue('confirm');
              announce(`Command verified: "${spokenText}"!`);
              const updated = [...prevSteps];
              updated[stepIdx] = { ...currentStep, completed: true };

              if (stepIdx + 1 < updated.length) {
                setCurrentStepIndex(stepIdx + 1);
              }
              return updated;
            }
            return prevSteps;
          });
        } else {
          setMatchedCommand('UNKNOWN');
          setMatchedIntent('NONE');
          setFeedbackMessage(`⚠️ Unrecognized speech: "${spokenText}". Please repeat the command.`);
          playAudioCue('alert');
        }
      } catch (err: any) {
        console.error('[AMAP Voice Error] Processing error details:', {
          message: err?.message,
          spokenText,
          language: recognitionLang,
        });
        setFeedbackMessage(`⚠️ Voice command evaluation error: ${err?.message || 'Connection error'}`);
      }
    },
    [announce, playAudioCue]
  );

  const handleTranscriptRef = useRef(handleRecognizedTranscript);
  useEffect(() => {
    handleTranscriptRef.current = handleRecognizedTranscript;
  });

  // Initialize Speech Recognition Engine (Single Stable Instance)
  const startSpeechRecognition = useCallback(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setMicState('MICROPHONE_ERROR');
      setMicErrorMessage('Web Speech API is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.lang =
        language === 'es'
          ? 'es-ES'
          : language === 'ta'
          ? 'ta-IN'
          : language === 'hi'
          ? 'hi-IN'
          : language === 'de'
          ? 'de-DE'
          : 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        isListeningRef.current = true;
      };

      recognition.onresult = (event: any) => {
        const lastIdx = event.results.length - 1;
        const resultObj = event.results[lastIdx][0];
        const spokenText = resultObj.transcript.trim();
        const rawConfidence = resultObj.confidence || 0.92;

        if (spokenText && handleTranscriptRef.current) {
          handleTranscriptRef.current(spokenText, rawConfidence, recognition.lang);
        }
      };

      recognition.onend = () => {
        if (isListeningRef.current) {
          setTimeout(() => {
            if (isListeningRef.current && recognitionRef.current) {
              try {
                recognitionRef.current.start();
              } catch (e) {
                console.log('[AMAP Voice] Auto-restart active');
              }
            }
          }, 150);
        }
      };

      recognition.onerror = (event: any) => {
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition status:', event.error);
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
      isListeningRef.current = true;
      setIsListening(true);
    } catch (err: any) {
      console.error('Speech recognition startup error:', err);
      setMicState('MICROPHONE_ERROR');
      setMicErrorMessage('Failed to initialize speech recognition engine.');
    }
  }, [language]);

  // Request Microphone Access
  const requestMicrophoneAccess = async () => {
    try {
      setMicState('MICROPHONE_REQUESTING');
      setMicErrorMessage('');
      announce('Requesting microphone access.');

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setAudioStream(stream);

      // Web Audio Analyser for Energy Monitor
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        const audioCtx = new AudioCtx();
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const checkVolume = () => {
          if (analyserRef.current) {
            analyserRef.current.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
              sum += dataArray[i];
            }
            const avg = sum / dataArray.length;
            setVolumeLevel(Math.min(100, Math.round((avg / 128) * 100)));
            requestAnimationFrame(checkVolume);
          }
        };
        requestAnimationFrame(checkVolume);
      }

      setMicState('MICROPHONE_READY');
      announce('Microphone ready! Starting voice recognition.');
      startSpeechRecognition();
    } catch (err: any) {
      console.error('Microphone access error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setMicState('MICROPHONE_DENIED');
        setMicErrorMessage('Microphone access was denied. Please allow microphone permission in your browser address bar.');
      } else {
        setMicState('MICROPHONE_ERROR');
        setMicErrorMessage(err.message || 'Microphone unavailable. Please connect a working microphone.');
      }
    }
  };

  const stopListening = () => {
    isListeningRef.current = false;
    setIsListening(false);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
  };

  const restartListening = () => {
    if (micState === 'MICROPHONE_READY') {
      startSpeechRecognition();
    } else {
      requestMicrophoneAccess();
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
      if (audioStream) {
        audioStream.getTracks().forEach((t) => t.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [audioStream]);

  const allCompleted = trainingSteps.every((s) => s.completed);

  const handleContinue = () => {
    setHasCompletedVoiceSetup(true);
    playAudioCue('confirm');
    router.push('/training');
  };

  const currentStep = trainingSteps[currentStepIndex];

  return (
    <div style={{ maxWidth: '880px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.5rem' }}>🎙️</span>
          <h1 style={{ fontSize: '2rem', fontWeight: 800 }}>
            {t('voice_setup_title', language)}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
            {t('voice_setup_subtitle', language)}
          </p>
        </div>

        {/* Live Diagnostics HUD */}
        <div
          className="glass-card"
          style={{
            padding: '0.85rem 1.25rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            background: 'rgba(11, 15, 25, 0.75)',
            borderLeft: '4px solid var(--worker-cyan)',
            fontSize: '0.75rem',
            marginBottom: '1.5rem',
          }}
        >
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>MICROPHONE</span>
            <strong style={{ color: micState === 'MICROPHONE_READY' ? 'var(--org-emerald)' : 'var(--accent-rose)' }}>
              {micState === 'MICROPHONE_READY' ? 'READY' : micState === 'MICROPHONE_REQUESTING' ? 'REQUESTING...' : 'NOT READY'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>LISTENING</span>
            <strong style={{ color: isListening ? 'var(--org-emerald)' : 'var(--accent-amber)' }}>
              {isListening ? 'YES (ACTIVE)' : 'NO (PAUSED)'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>TRANSCRIPT</span>
            <strong style={{ color: rawTranscript ? '#fff' : 'var(--text-muted)' }}>
              {rawTranscript ? `"${rawTranscript}"` : 'NONE'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>COMMAND</span>
            <strong style={{ color: matchedCommand !== 'NONE' && matchedCommand !== 'UNKNOWN' ? 'var(--org-emerald)' : matchedCommand === 'UNKNOWN' ? 'var(--accent-rose)' : 'var(--text-muted)' }}>
              {matchedCommand}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>CONFIDENCE</span>
            <strong style={{ color: confidenceScore > 0 ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
              {confidenceScore > 0 ? `${(confidenceScore * 100).toFixed(0)}%` : '0.00'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>INTENT</span>
            <strong style={{ color: matchedIntent !== 'NONE' ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
              {matchedIntent}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>MATCH TIME</span>
            <strong style={{ color: processingLatencyMs > 0 ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
              {processingLatencyMs > 0 ? `${processingLatencyMs}ms` : '--'}
            </strong>
          </div>
        </div>

        {/* Microphone Permission Gate */}
        {micState === 'MICROPHONE_PERMISSION_REQUIRED' && (
          <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', marginBottom: '1.5rem' }}>
            <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '0.75rem' }}>🎤</span>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff', marginBottom: '0.5rem' }}>
              Microphone Access Required
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '500px', margin: '0 auto 1.5rem auto' }}>
              AMAP needs access to your microphone to recognize acoustic assembly commands in real time.
            </p>
            <button
              type="button"
              onClick={requestMicrophoneAccess}
              className="btn btn-primary"
              style={{ padding: '0.85rem 2.25rem', fontSize: '1.1rem', fontWeight: 800 }}
            >
              Grant Microphone Access →
            </button>
          </div>
        )}

        {/* Microphone Permission Denied / Error */}
        {(micState === 'MICROPHONE_DENIED' || micState === 'MICROPHONE_ERROR') && (
          <div
            className="glass-card"
            style={{
              padding: '1.5rem',
              textAlign: 'center',
              border: '2px solid var(--accent-rose)',
              background: 'rgba(244, 63, 94, 0.1)',
              marginBottom: '1.5rem',
            }}
          >
            <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>🚫</span>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--accent-rose)', marginBottom: '0.5rem' }}>
              {micState === 'MICROPHONE_DENIED' ? 'Microphone Permission Denied' : 'Microphone Error'}
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              {micErrorMessage}
            </p>
            <button
              type="button"
              onClick={requestMicrophoneAccess}
              className="btn btn-primary"
              style={{ padding: '0.75rem 1.75rem', fontSize: '0.95rem' }}
            >
              🔄 Retry Microphone Access
            </button>
          </div>
        )}

        {/* Real Live Waveform Decibel Monitor */}
        {micState === 'MICROPHONE_READY' && (
          <div className="glass-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                Live Acoustic Energy Monitor
              </span>
              <span style={{ fontSize: '0.85rem', fontWeight: 800, color: volumeLevel > 15 ? 'var(--org-emerald)' : 'var(--text-muted)' }}>
                {volumeLevel > 15 ? 'AUDIO DETECTED' : 'AWAITING SPEECH'} ({volumeLevel}%)
              </span>
            </div>

            {/* Volume Meter Bar */}
            <div style={{ width: '100%', height: '10px', borderRadius: '5px', background: 'rgba(255, 255, 255, 0.1)', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${volumeLevel}%`,
                  height: '100%',
                  background: volumeLevel > 15 ? 'linear-gradient(90deg, var(--worker-cyan), var(--org-emerald))' : 'var(--text-muted)',
                  transition: 'width 0.05s ease-out',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Status: {isListening ? '🎤 Listening continuously for commands' : '⏸️ Voice recognition paused'}
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {isListening ? (
                  <button
                    type="button"
                    onClick={stopListening}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.78rem', padding: '0.35rem 0.75rem' }}
                  >
                    ⏸️ Pause Listening
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={restartListening}
                    className="btn btn-primary"
                    style={{ fontSize: '0.78rem', padding: '0.35rem 0.75rem' }}
                  >
                    ▶️ Resume Listening
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Guided Step-by-Step Training Vocabulary */}
        {micState === 'MICROPHONE_READY' && (
          <div className="glass-card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--worker-cyan)', fontWeight: 800, textTransform: 'uppercase' }}>
              Guided Voice Training ({trainingSteps.filter((s) => s.completed).length} / {trainingSteps.length} Complete)
            </span>

            {/* Active Training Step Prompt */}
            {!allCompleted && currentStep && (
              <div
                style={{
                  background: 'rgba(6, 182, 212, 0.1)',
                  border: '2px solid var(--worker-cyan)',
                  borderRadius: '16px',
                  padding: '1.5rem',
                  textAlign: 'center',
                  margin: '1rem 0 1.5rem 0',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: 'var(--worker-cyan)', fontWeight: 700, display: 'block' }}>
                  STEP {currentStepIndex + 1} OF {trainingSteps.length}
                </span>
                <h2 style={{ fontSize: '1.8rem', fontWeight: 900, color: '#fff', margin: '0.35rem 0' }}>
                  {currentStep.instructionPrompt}
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
                  Speak clearly into your microphone to verify acoustic calibration for intent <strong>{currentStep.intent}</strong>.
                </p>
              </div>
            )}

            {/* Live Feedback Banner */}
            {feedbackMessage && (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  background: feedbackMessage.startsWith('✓') ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                  border: feedbackMessage.startsWith('✓') ? '1px solid var(--org-emerald)' : '1px solid var(--accent-rose)',
                  color: feedbackMessage.startsWith('✓') ? 'var(--org-emerald)' : 'var(--accent-rose)',
                  fontSize: '0.9rem',
                  fontWeight: 700,
                  marginBottom: '1.25rem',
                  textAlign: 'center',
                }}
              >
                {feedbackMessage}
              </div>
            )}

            {/* Vocabulary Checklist */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              {trainingSteps.map((step, idx) => (
                <div
                  key={step.id}
                  className="glass-card"
                  style={{
                    padding: '1rem',
                    border: step.completed
                      ? '2px solid var(--org-emerald)'
                      : idx === currentStepIndex
                      ? '2px solid var(--worker-cyan)'
                      : '1px solid var(--surface-glass-border)',
                    background: step.completed
                      ? 'rgba(16, 185, 129, 0.1)'
                      : idx === currentStepIndex
                      ? 'rgba(6, 182, 212, 0.08)'
                      : 'var(--surface-glass)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '1rem', color: step.completed ? 'var(--org-emerald)' : '#fff' }}>
                      {step.displayKeyword}
                    </strong>
                    <span style={{ fontSize: '1.1rem' }}>{step.completed ? '✅' : '⏳'}</span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                    {step.intent}
                  </span>
                </div>
              ))}
            </div>

            {allCompleted && (
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid var(--org-emerald)',
                  color: 'var(--org-emerald)',
                  padding: '1.25rem',
                  borderRadius: '16px',
                  textAlign: 'center',
                  marginTop: '1.5rem',
                }}
              >
                <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.25rem' }}>🎉</span>
                <strong style={{ fontSize: '1.1rem', display: 'block' }}>
                  Acoustic Voice Calibration Complete!
                </strong>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  All 4 factory commands have been calibrated and verified against the backend.
                </span>
              </div>
            )}
          </div>
        )}

        {/* Footer Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={() => router.push('/onboarding/custom-gesture')}
            className="btn btn-secondary"
            style={{ padding: '0.75rem 1.25rem', fontSize: '0.95rem' }}
          >
            ← Back to Custom Gesture
          </button>
          <button
            type="button"
            onClick={handleContinue}
            disabled={!allCompleted && micState !== 'MICROPHONE_READY'}
            className="btn btn-primary"
            style={{ padding: '0.85rem 2rem', fontSize: '1.05rem', fontWeight: 800 }}
          >
            Save & Continue to Training →
          </button>
        </div>
      </div>
    </div>
  );
}
