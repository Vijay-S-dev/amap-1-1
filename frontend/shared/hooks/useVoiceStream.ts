'use client';

/**
 * Streaming voice input hook (Vosk over WebSocket).
 *
 * Replaces the previous batch MediaRecorder + upload workflow. The worker
 * experience is now:
 *
 *   activate() -> LISTENING -> (worker speaks) -> SPEAKING (live partials)
 *   -> automatic end-of-speech (server-side Vosk endpointer)
 *   -> FINALIZING -> EXECUTING (existing AMAP command pipeline)
 *   -> READY -> LISTENING (mic stays open for the next utterance)
 *
 * There is NO stop-recording button, NO audio upload, and NO recording cap.
 * Partial results are display-only feedback and NEVER reach the command
 * pipeline; only server-finalized utterances invoke `onFinal`.
 *
 * Robustness:
 * - microphone permission denied / unavailable  -> ERROR (message from browser)
 * - WebSocket disconnect / backend unavailable  -> auto-reconnect w/ backoff
 *   (the microphone stream is kept so no re-permission is needed)
 * - Vosk model unavailable / auth failure        -> fatal ERROR (no reconnect;
 *   no command can ever execute from a failed stream)
 * - malformed audio                             -> impossible from this hook
 *   (worklet always emits well-formed 16-bit PCM)
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/shared/api/client';

export type VoiceStreamState =
  | 'IDLE'
  | 'REQUESTING_MIC'
  | 'CONNECTING'
  | 'LISTENING'
  | 'SPEAKING'
  | 'FINALIZING'
  | 'EXECUTING'
  | 'READY'
  | 'ERROR';

export interface VoiceStreamCommand {
  matched_command: string | null;
  action_mapping: string | null;
  confidence: number;
  fuzzy_score: number;
  requires_confirmation: boolean;
  validation_status: string;
  message: string | null;
}

export interface VoiceFinalEvent {
  transcript: string;
  detected_language: string;
  confidence: number;
  processing_time_ms?: number;
  command: VoiceStreamCommand | null;
}

interface UseVoiceStreamOptions {
  enabled?: boolean;
  language?: string;
  onFinal: (event: VoiceFinalEvent) => void | Promise<void>;
  onError: (error: string) => void;
  onStateChange?: (state: VoiceStreamState) => void;
}

const TARGET_SAMPLE_RATE = 16000;
const FRAME_SAMPLES = 512; // 32 ms PCM frames at 16 kHz
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;

/**
 * AudioWorklet processor: mono downmix, linear resample to 16 kHz, convert to
 * 16-bit PCM, and post 512-sample frames to the main thread. Injected as a
 * Blob URL so no extra static asset or build step is needed.
 */
const PCM_WORKLET_SRC = `
class AmapPcmSender extends AudioWorkletProcessor {
  constructor() {
    super();
    this.sourceRate = sampleRate;
    this.targetRate = ${TARGET_SAMPLE_RATE};
    this.buf = new Float32Array(${FRAME_SAMPLES});
    this.idx = 0;
  }
  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];
    let samples = ch;
    const ratio = this.sourceRate / this.targetRate;
    if (Math.abs(ratio - 1) > 0.001) {
      const outLen = Math.max(1, Math.floor(ch.length / ratio));
      const out = new Float32Array(outLen);
      for (let i = 0; i < outLen; i++) {
        const srcPos = i * ratio;
        const i0 = Math.floor(srcPos);
        const frac = srcPos - i0;
        const s0 = ch[i0] || 0;
        const s1 = i0 + 1 < ch.length ? ch[i0 + 1] : s0;
        out[i] = s0 + (s1 - s0) * frac;
      }
      samples = out;
    }
    for (let i = 0; i < samples.length; i++) {
      this.buf[this.idx++] = samples[i];
      if (this.idx === this.buf.length) {
        const pcm16 = new Int16Array(this.buf.length);
        for (let j = 0; j < this.buf.length; j++) {
          const s = Math.max(-1, Math.min(1, this.buf[j]));
          pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
        this.idx = 0;
      }
    }
    return true;
  }
}
registerProcessor('amap-pcm-sender', AmapPcmSender);
`;

export function useVoiceStream({
  enabled = true,
  language = 'en',
  onFinal,
  onError,
  onStateChange,
}: UseVoiceStreamOptions) {
  const [state, setState] = useState<VoiceStreamState>('IDLE');
  const [partialText, setPartialText] = useState('');
  const [volumeLevel, setVolumeLevel] = useState(0);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const activeRef = useRef(false); // worker wants the mic on
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const mountedRef = useRef(true);
  const callbacksRef = useRef({ onFinal, onError, onStateChange });
  const languageRef = useRef(language);
  const executingRef = useRef(false);

  useEffect(() => {
    callbacksRef.current = { onFinal, onError, onStateChange };
    languageRef.current = language;
  }, [language, onFinal, onError, onStateChange]);

  const updateState = useCallback((next: VoiceStreamState) => {
    if (!mountedRef.current) return;
    setState(next);
    callbacksRef.current.onStateChange?.(next);
  }, []);

  /** Fatal stream errors: never reconnect, never execute anything. */
  const isFatalClose = (code: number) =>
    code === 4401 || code === 4403 || code === 4503;

  const clearReconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const teardownSocket = useCallback(() => {
    clearReconnect();
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      ws.onclose = null;
      ws.onmessage = null;
      ws.onerror = null;
      try {
        ws.close(1000, 'client-deactivate');
      } catch {
        /* already closing */
      }
    }
  }, [clearReconnect]);

  const teardownAudio = useCallback(() => {
    if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
    animFrameRef.current = null;
    analyserRef.current = null;
    if (workletRef.current) {
      try {
        workletRef.current.port.onmessage = null;
        workletRef.current.disconnect();
      } catch {
        /* node already detached */
      }
      workletRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const connectSocket = useCallback(() => {
    if (!mountedRef.current || !activeRef.current) return;
    const token = api.getToken();
    if (!token) {
      updateState('ERROR');
      callbacksRef.current.onError('Not signed in — voice input unavailable.');
      return;
    }
    updateState('CONNECTING');

    let socket: WebSocket;
    try {
      const url = api.getVoiceStreamUrl(languageRef.current, token);
      socket = new WebSocket(url);
      socket.binaryType = 'arraybuffer';
    } catch (err) {
      updateState('ERROR');
      callbacksRef.current.onError(
        err instanceof Error ? err.message : 'Unable to open the voice stream.'
      );
      return;
    }
    wsRef.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current || !activeRef.current) {
        socket.close(1000, 'client-deactivate');
        return;
      }
      reconnectAttemptsRef.current = 0;
      setPartialText('');
      updateState('LISTENING');
    };

    socket.onmessage = (event) => {
      if (!mountedRef.current || wsRef.current !== socket) return;
      if (typeof event.data !== 'string') return;
      let payload: any;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (payload.type === 'partial') {
        // Display-only feedback. Partials never reach the command pipeline.
        setPartialText(String(payload.text || ''));
        updateState('SPEAKING');
        return;
      }
      if (payload.type === 'final') {
        setPartialText('');
        updateState('FINALIZING');
        const finalEvent: VoiceFinalEvent = {
          transcript: String(payload.transcript || ''),
          detected_language: String(payload.detected_language || languageRef.current),
          confidence: typeof payload.confidence === 'number' ? payload.confidence : 0,
          processing_time_ms: payload.processing_time_ms,
          command: payload.command ?? null,
        };
        executingRef.current = true;
        Promise.resolve(callbacksRef.current.onFinal(finalEvent))
          .catch(() => undefined)
          .finally(() => {
            executingRef.current = false;
            if (mountedRef.current && wsRef.current === socket) {
              updateState('READY');
              setTimeout(() => {
                if (
                  mountedRef.current &&
                  wsRef.current === socket &&
                  !executingRef.current
                ) {
                  updateState('LISTENING');
                }
              }, 300);
            }
          });
        return;
      }
      if (payload.type === 'error') {
        const code = String(payload.code || 'unknown');
        const message = String(payload.message || 'Voice stream error.');
        updateState('ERROR');
        callbacksRef.current.onError(message);
        if (code === 'model_unavailable' || code === 'unauthenticated' || code === 'forbidden') {
          // Fatal: stop streaming; a failed stream must never execute commands.
          activeRef.current = false;
          teardownSocket();
        }
      }
    };

    socket.onerror = () => {
      // onclose follows; handled there.
    };

    socket.onclose = (event) => {
      if (!mountedRef.current || wsRef.current !== socket) return;
      wsRef.current = null;
      if (!activeRef.current) return;
      if (isFatalClose(event.code)) {
        activeRef.current = false;
        updateState('ERROR');
        callbacksRef.current.onError(
          event.code === 4503
            ? 'Voice recognition model unavailable on the server. Please contact your supervisor.'
            : 'Voice stream authentication failed. Please sign in again.'
        );
        return;
      }
      // Unexpected loss (backend restart, network drop): reconnect with backoff.
      updateState('ERROR');
      callbacksRef.current.onError('Voice stream connection lost. Reconnecting…');
      const attempt = reconnectAttemptsRef.current + 1;
      reconnectAttemptsRef.current = attempt;
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** (attempt - 1), RECONNECT_MAX_MS);
      clearReconnect();
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && activeRef.current) connectSocket();
      }, delay);
    };
  }, [teardownSocket, updateState]);

  const activate = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    reconnectAttemptsRef.current = 0;
    try {
      updateState('REQUESTING_MIC');
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access is unavailable in this browser.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!mountedRef.current || !activeRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;

      const AudioContextClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      const context = new AudioContextClass({ sampleRate: TARGET_SAMPLE_RATE });
      audioContextRef.current = context;

      const blobUrl = URL.createObjectURL(new Blob([PCM_WORKLET_SRC], { type: 'text/javascript' }));
      let worklet: AudioWorkletNode;
      try {
        await context.audioWorklet.addModule(blobUrl);
        worklet = new AudioWorkletNode(context, 'amap-pcm-sender');
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
      workletRef.current = worklet;

      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      source.connect(worklet);
      analyserRef.current = analyser;

      // Volume meter for the UI (same visual as before).
      const data = new Uint8Array(analyser.fftSize);
      const monitor = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
          const normalized = (data[i] - 128) / 128;
          sum += normalized * normalized;
        }
        const level = Math.min(100, Math.round(Math.sqrt(sum / data.length) * 180));
        setVolumeLevel(level);
        animFrameRef.current = requestAnimationFrame(monitor);
      };
      animFrameRef.current = requestAnimationFrame(monitor);

      worklet.port.onmessage = (event) => {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN && event.data instanceof ArrayBuffer) {
          ws.send(event.data);
        }
      };

      connectSocket();
    } catch (err) {
      activeRef.current = false;
      teardownAudio();
      updateState('ERROR');
      const message =
        err instanceof Error && err.name === 'NotAllowedError'
          ? 'Microphone permission was denied. Enable it in your browser settings.'
          : err instanceof Error && (err.name === 'NotFoundError' || err.name === 'NotReadableError')
          ? 'Microphone is unavailable or in use by another application.'
          : err instanceof Error
          ? err.message
          : 'Microphone activation failed.';
      callbacksRef.current.onError(message);
    }
  }, [connectSocket, teardownAudio, updateState]);

  const deactivate = useCallback(() => {
    activeRef.current = false;
    clearReconnect();
    teardownSocket();
    teardownAudio();
    setPartialText('');
    setVolumeLevel(0);
    if (mountedRef.current) {
      setState('IDLE');
      callbacksRef.current.onStateChange?.('IDLE');
    }
  }, [clearReconnect, teardownAudio, teardownSocket]);

  // Modality disabled -> shut the whole voice session down.
  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) {
      deactivate();
      return () => undefined;
    }
    return () => {
      mountedRef.current = false;
      activeRef.current = false;
      clearReconnect();
      teardownSocket();
      teardownAudio();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return { activate, deactivate, state, partialText, volumeLevel };
}
