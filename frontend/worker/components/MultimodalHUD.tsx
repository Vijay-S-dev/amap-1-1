'use client';

/**
 * Worker Multimodal HUD Component
 * Displays live gesture recognition simulator, voice speech recognition waveform,
 * cross-modal intent fusion status, and dwell countdown.
 */

import React, { useState, useEffect } from 'react';
import { InteractionMode, MultimodalFusionResult } from '@/shared/types';
import { api } from '@/shared/api/client';

interface MultimodalHUDProps {
  onActionTriggered: (actionName: string, sourceModality: string) => void;
  dwellTimeMs?: number;
}

export function MultimodalHUD({ onActionTriggered, dwellTimeMs = 450 }: MultimodalHUDProps) {
  const [activeGesture, setActiveGesture] = useState<string>('thumbs_up');
  const [activeVoiceCommand, setActiveVoiceCommand] = useState<string>('confirm step');
  const [dwellProgress, setDwellProgress] = useState<number>(0);
  const [isDwelling, setIsDwelling] = useState<boolean>(false);
  const [fusionResult, setFusionResult] = useState<MultimodalFusionResult | null>(null);

  // Simulates multi-modal intent evaluation when buttons are pressed or voice is spoken
  const triggerMultimodalSimulation = async (gesture: string, voice: string) => {
    setActiveGesture(gesture);
    setActiveVoiceCommand(voice);
    setIsDwelling(true);
    setDwellProgress(0);

    const result = await api.fuseMultimodal([
      { mode: 'gesture', rawIntent: gesture, confidence: 0.92, timestampMs: Date.now() },
      { mode: 'voice', rawIntent: voice, confidence: 0.94, timestampMs: Date.now() + 100 },
    ]);

    setFusionResult(result);

    // Simulate dwell timer accumulation
    const interval = setInterval(() => {
      setDwellProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsDwelling(false);
          if (result.fusedAction) {
            onActionTriggered(result.fusedAction, result.fusionStrategy);
          }
          return 100;
        }
        return prev + 25;
      });
    }, dwellTimeMs / 4);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: 'var(--worker-cyan)' }}>✦</span> Multimodal Intent HUD
        </h2>
        <span className="badge badge-cyan">Adaptive Threshold: {dwellTimeMs}ms</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        {/* Gesture Recognition Stream */}
        <div className="glass-card" style={{ borderLeft: '4px solid var(--worker-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)' }}>🖐️ OPTICAL GESTURE FEED</span>
            <span className="badge badge-cyan">92% CONF</span>
          </div>

          <div
            style={{
              height: '110px',
              borderRadius: '8px',
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px dashed var(--worker-cyan)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ fontSize: '2rem', marginBottom: '0.25rem' }}>
              {activeGesture === 'thumbs_up' && '👍'}
              {activeGesture === 'pointing' && '👉'}
              {activeGesture === 'open_palm' && '✋'}
              {activeGesture === 'pinch' && '🤏'}
              {activeGesture === 'thumbs_down' && '👎'}
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--worker-cyan)' }}>
              gesture: {activeGesture}
            </span>
          </div>

          {/* Gesture Sim Controls */}
          <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
            {['thumbs_up', 'pointing', 'open_palm', 'thumbs_down'].map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => triggerMultimodalSimulation(g, 'confirm')}
                className="btn btn-secondary"
                style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', minHeight: '32px' }}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        {/* Voice Recognition Stream */}
        <div className="glass-card" style={{ borderLeft: '4px solid var(--accent-blue)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)' }}>🎙️ ACOUSTIC VOICE FEED</span>
            <span className="badge badge-cyan">94% CONF</span>
          </div>

          <div
            style={{
              height: '110px',
              borderRadius: '8px',
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px dashed var(--accent-blue)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', gap: '3px', alignItems: 'center', height: '24px', marginBottom: '0.5rem' }}>
              {[12, 20, 8, 24, 16, 22, 10, 18, 14].map((h, i) => (
                <div
                  key={i}
                  style={{
                    width: '4px',
                    height: `${isDwelling ? h : 6}px`,
                    background: 'var(--accent-blue)',
                    borderRadius: '2px',
                    transition: 'height 0.15s ease',
                  }}
                />
              ))}
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
              &ldquo;{activeVoiceCommand}&rdquo;
            </span>
          </div>

          {/* Voice Sim Controls */}
          <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
            {['confirm step', 'next step', 'pause session', 'emergency stop'].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => triggerMultimodalSimulation('thumbs_up', v)}
                className="btn btn-secondary"
                style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', minHeight: '32px' }}
              >
                &ldquo;{v}&rdquo;
              </button>
            ))}
          </div>
        </div>

        {/* Fusion Arbitration & Dwell Meter */}
        <div className="glass-card" style={{ borderLeft: '4px solid var(--org-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)' }}>⚡ CROSS-MODAL FUSION</span>
            <span className="badge badge-emerald">
              {fusionResult ? `${Math.round(fusionResult.fusedConfidence * 100)}% BOOSTED` : 'READY'}
            </span>
          </div>

          <div
            style={{
              height: '110px',
              borderRadius: '8px',
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid var(--surface-glass-border)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              padding: '0.75rem',
            }}
          >
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Strategy: <strong style={{ color: 'var(--worker-cyan)' }}>{fusionResult?.fusionStrategy || 'Reinforcing Agreement'}</strong>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Candidate: <strong style={{ color: 'white' }}>{fusionResult?.fusedAction || 'confirm_action'}</strong>
            </div>

            {/* Dwell Progress Bar */}
            <div style={{ height: '8px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${dwellProgress}%`,
                  background: 'linear-gradient(90deg, var(--worker-cyan), var(--org-emerald))',
                  transition: 'width 0.1s linear',
                }}
              />
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.35rem', textAlign: 'right' }}>
              Dwell Hold: {dwellProgress}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
