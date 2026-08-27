'use client';

/**
 * Worker Accessibility & Interaction Preferences Onboarding Step (/onboarding/accessibility) (§ 8)
 * Configures interaction modalities, sensory preferences, font scaling, and high contrast.
 */

import React from 'react';
import { useRouter } from 'next/navigation';
import { InteractionModality, useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';

export default function AccessibilityOnboardingPage() {
  const router = useRouter();
  const {
    language,
    modality,
    setModality,
    highContrast,
    setHighContrast,
    textScale,
    setTextScale,
    reducedMotion,
    setReducedMotion,
    audioFeedback,
    setAudioFeedback,
    setHasCompletedAccessibility,
    announce,
    playAudioCue,
  } = useAccessibility();

  const modalities: { id: InteractionModality; titleKey: string; icon: string; desc: string }[] = [
    {
      id: 'multimodal',
      titleKey: 'modality_both',
      icon: '⚡',
      desc: 'Seamlessly combine optical hand gestures and voice speech confirmation for maximum accuracy.',
    },
    {
      id: 'gesture',
      titleKey: 'modality_gesture',
      icon: '🖐️',
      desc: 'Operate assembly workstation solely using camera-tracked optical hand gestures and dwell timers.',
    },
    {
      id: 'voice',
      titleKey: 'modality_voice',
      icon: '🎙️',
      desc: 'Operate workstation solely using spoken acoustic commands with noise-filtering.',
    },
    {
      id: 'ui',
      titleKey: 'modality_ui',
      icon: '📱',
      desc: 'Operate using large-target, high-contrast accessible screen controls and assistive devices.',
    },
  ];

  const handleSelectModality = (m: InteractionModality) => {
    setModality(m);
    playAudioCue('step');
    announce(`Interaction modality set to ${m}.`);
  };

  const handleContinue = () => {
    setHasCompletedAccessibility(true);
    playAudioCue('confirm');
    if (modality === 'voice') {
      router.push('/onboarding/voice-setup');
    } else {
      router.push('/onboarding/gesture-calibration');
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.5rem' }}>🎛️</span>
          <h1 style={{ fontSize: '2rem', fontWeight: 800 }}>
            {t('accessibility_title', language)}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
            {t('accessibility_subtitle', language)}
          </p>
        </div>

        {/* Modality Selection Cards (§ 8) */}
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--worker-cyan)' }}>
          {t('preferred_modality', language)}
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          {modalities.map((m) => {
            const isSelected = modality === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => handleSelectModality(m.id)}
                className="glass-card"
                style={{
                  padding: '1.25rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  textAlign: 'left',
                  cursor: 'pointer',
                  border: isSelected ? '3px solid var(--worker-cyan)' : '1px solid var(--surface-glass-border)',
                  background: isSelected ? 'rgba(6, 182, 212, 0.15)' : 'var(--surface-card)',
                  borderRadius: '16px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '1.75rem' }}>{m.icon}</span>
                  {isSelected && (
                    <span style={{ padding: '0.2rem 0.5rem', borderRadius: '999px', background: 'var(--worker-cyan)', color: '#000', fontWeight: 800, fontSize: '0.7rem' }}>
                      Active
                    </span>
                  )}
                </div>
                <strong style={{ fontSize: '1.05rem', color: '#fff', marginBottom: '0.25rem' }}>
                  {t(m.titleKey, language)}
                </strong>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                  {m.desc}
                </p>
              </button>
            );
          })}
        </div>

        {/* Sensory & Ergonomic Preferences */}
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--org-emerald)' }}>
          Visual & Sensory Settings
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          {/* High Contrast */}
          <label className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', cursor: 'pointer' }}>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{t('high_contrast', language)}</span>
            <input
              type="checkbox"
              checked={highContrast}
              onChange={(e) => setHighContrast(e.target.checked)}
              style={{ width: '22px', height: '22px', accentColor: 'var(--worker-cyan)' }}
            />
          </label>

          {/* Reduced Motion */}
          <label className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', cursor: 'pointer' }}>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{t('reduced_motion', language)}</span>
            <input
              type="checkbox"
              checked={reducedMotion}
              onChange={(e) => setReducedMotion(e.target.checked)}
              style={{ width: '22px', height: '22px', accentColor: 'var(--worker-cyan)' }}
            />
          </label>

          {/* Audio Feedback */}
          <label className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', cursor: 'pointer' }}>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{t('audio_feedback', language)}</span>
            <input
              type="checkbox"
              checked={audioFeedback}
              onChange={(e) => setAudioFeedback(e.target.checked)}
              style={{ width: '22px', height: '22px', accentColor: 'var(--worker-cyan)' }}
            />
          </label>
        </div>

        {/* Text Scaling Slider */}
        <div className="glass-card" style={{ padding: '1.25rem', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <label htmlFor="text-scale-slider" style={{ fontWeight: 600, fontSize: '0.95rem' }}>
              {t('text_size', language)}: {Math.round(textScale * 100)}%
            </label>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Standard (100%) to Large (150%)</span>
          </div>
          <input
            id="text-scale-slider"
            type="range"
            min="1.0"
            max="1.5"
            step="0.05"
            value={textScale}
            onChange={(e) => setTextScale(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--worker-cyan)', cursor: 'pointer' }}
          />
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => router.push('/onboarding/language')}
            className="btn btn-secondary"
            style={{ padding: '0.85rem 1.5rem', fontSize: '1rem' }}
          >
            ← {t('back_btn', language)}
          </button>
          <button
            type="button"
            onClick={handleContinue}
            className="btn btn-primary"
            style={{ padding: '0.85rem 2rem', fontSize: '1.1rem', fontWeight: 800 }}
          >
            {t('continue_btn', language)} →
          </button>
        </div>
      </div>
    </div>
  );
}
