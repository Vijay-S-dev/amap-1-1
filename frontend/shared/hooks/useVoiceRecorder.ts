'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/shared/api/client';

export type VoiceRecorderState =
  | 'IDLE'
  | 'REQUESTING_MIC'
  | 'READY'
  | 'RECORDING'
  | 'PROCESSING'
  | 'ERROR';

export interface TranscriptionResult {
  transcript: string;
  detected_language: string;
  confidence: number;
  processing_time_ms: number;
  success: boolean;
}

interface UseVoiceRecorderOptions {
  enabled?: boolean;
  autoRequestMic?: boolean;
  continuous?: boolean;
  language?: string;
  maxDurationMs?: number;
  silenceThresholdMs?: number;
  silenceLevel?: number;
  onTranscript: (result: TranscriptionResult) => void;
  onError: (error: string) => void;
  onStateChange?: (state: VoiceRecorderState) => void;
}

const getAudioContext = () => {
  if (typeof window === 'undefined') return null;
  const AudioContextClass = window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  return AudioContextClass ? new AudioContextClass() : null;
};

export function useVoiceRecorder({
  enabled = true,
  autoRequestMic = true,
  continuous = true,
  language = 'en',
  maxDurationMs = 4000,
  silenceThresholdMs = 600,
  silenceLevel = 8,
  onTranscript,
  onError,
  onStateChange,
}: UseVoiceRecorderOptions) {
  const [state, setState] = useState<VoiceRecorderState>('IDLE');
  const [volumeLevel, setVolumeLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const silenceStartedRef = useRef<number | null>(null);
  const speechDetectedRef = useRef(false);
  const mountedRef = useRef(true);
  const continuousRef = useRef(continuous);
  const callbacksRef = useRef({ onTranscript, onError, onStateChange });
  const languageRef = useRef(language);

  useEffect(() => {
    callbacksRef.current = { onTranscript, onError, onStateChange };
    languageRef.current = language;
    continuousRef.current = continuous;
  }, [continuous, language, onError, onStateChange, onTranscript]);

  const updateState = useCallback((next: VoiceRecorderState) => {
    if (mountedRef.current) {
      setState(next);
      callbacksRef.current.onStateChange?.(next);
    }
  }, []);

  const stopMonitoring = useCallback(() => {
    if (animationFrameRef.current !== null) cancelAnimationFrame(animationFrameRef.current);
    animationFrameRef.current = null;
    analyserRef.current = null;
    if (audioContextRef.current) {
      void audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
  }, []);

  const ensureMicrophone = useCallback(async () => {
    if (streamRef.current?.active) return streamRef.current;
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access is unavailable in this browser.');
    updateState('REQUESTING_MIC');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    updateState('READY');
    return stream;
  }, [updateState]);

  // Reference to startRecording for use in continuous restart
  const startRecordingRef = useRef<() => Promise<void>>();

  const transcribe = useCallback(async (blob: Blob) => {
    updateState('PROCESSING');
    try {
      const result = await Promise.race([
        api.transcribeAudio(blob, languageRef.current),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('Transcription timed out.')), 10000)),
      ]);
      if (!result.success && !result.transcript.trim()) throw new Error('No speech was detected.');
      callbacksRef.current.onTranscript(result);
      updateState('READY');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Audio transcription failed.';
      updateState('ERROR');
      callbacksRef.current.onError(message);
    }
    // Continuous mode: auto-restart recording after transcription completes
    if (continuousRef.current && mountedRef.current) {
      setTimeout(() => {
        if (mountedRef.current && continuousRef.current) {
          startRecordingRef.current?.();
        }
      }, 50);
    }
  }, [updateState]);

  const stopRecording = useCallback(() => {
    if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
    maxTimerRef.current = null;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  }, []);

  const startRecording = useCallback(async () => {
    if (recorderRef.current?.state === 'recording' || state === 'PROCESSING') return;
    try {
      const stream = await ensureMicrophone();
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorderRef.current = recorder;
      speechDetectedRef.current = false;
      silenceStartedRef.current = null;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        recorderRef.current = null;
        stopMonitoring();
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        if (blob.size === 0) {
          updateState('ERROR');
          callbacksRef.current.onError('No audio was recorded.');
          return;
        }
        void transcribe(blob);
      };
      recorder.onerror = () => {
        recorderRef.current = null;
        stopMonitoring();
        updateState('ERROR');
        callbacksRef.current.onError('The microphone recording failed.');
      };
      recorder.start(100);
      updateState('RECORDING');
      maxTimerRef.current = setTimeout(stopRecording, maxDurationMs);

      const context = getAudioContext();
      if (context) {
        audioContextRef.current = context;
        const source = context.createMediaStreamSource(stream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyserRef.current = analyser;
        const data = new Uint8Array(analyser.fftSize);
        const monitor = () => {
          if (!analyserRef.current) return;
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (let index = 0; index < data.length; index += 1) {
            const normalized = (data[index] - 128) / 128;
            sum += normalized * normalized;
          }
          const level = Math.min(100, Math.round(Math.sqrt(sum / data.length) * 180));
          setVolumeLevel(level);
          if (level > silenceLevel) {
            speechDetectedRef.current = true;
            silenceStartedRef.current = null;
          } else if (speechDetectedRef.current) {
            silenceStartedRef.current ??= Date.now();
            if (Date.now() - silenceStartedRef.current >= silenceThresholdMs) {
              stopRecording();
              return;
            }
          }
          animationFrameRef.current = requestAnimationFrame(monitor);
        };
        animationFrameRef.current = requestAnimationFrame(monitor);
      }
    } catch (error) {
      updateState('ERROR');
      callbacksRef.current.onError(error instanceof Error ? error.message : 'Microphone access failed.');
    }
  }, [ensureMicrophone, maxDurationMs, silenceLevel, silenceThresholdMs, state, stopMonitoring, stopRecording, transcribe, updateState]);

  // Keep startRecordingRef in sync
  useEffect(() => {
    startRecordingRef.current = startRecording;
  }, [startRecording]);

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) {
      stopRecording();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      stopMonitoring();
      updateState('IDLE');
      return () => undefined;
    }
    if (autoRequestMic) {
      void ensureMicrophone().then(() => {
        // In continuous mode, auto-start recording once mic is acquired
        if (continuousRef.current && mountedRef.current) {
          startRecordingRef.current?.();
        }
      }).catch((error) => {
        updateState('ERROR');
        callbacksRef.current.onError(error instanceof Error ? error.message : 'Microphone access failed.');
      });
    }
    return () => {
      mountedRef.current = false;
      stopRecording();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      stopMonitoring();
    };
  }, [autoRequestMic, enabled, ensureMicrophone, stopMonitoring, stopRecording, updateState]);

  return { startRecording, stopRecording, requestMicrophone: ensureMicrophone, state, volumeLevel };
}
