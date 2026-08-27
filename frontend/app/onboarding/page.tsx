'use client';

/**
 * Worker Onboarding Hub (/onboarding) (§ 4, § 13)
 * Orchestrates the complete pre-production onboarding journey and readiness evaluation.
 */

import React from 'react';
import Link from 'next/link';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';

export default function OnboardingHubPage() {
  const {
    language,
    modality,
    hasCompletedLanguage,
    hasCompletedAccessibility,
    hasCompletedGestureCalibration,
    hasCompletedVoiceSetup,
    hasCompletedTraining,
    isReady,
  } = useAccessibility();

  const allPossibleSteps = [
    {
      id: 'language',
      title: t('language_select_title', language),
      href: '/onboarding/language',
      completed: hasCompletedLanguage,
      icon: '🌐',
      desc: 'Select preferred language for all factory instructions and speech guidance.',
      requiredFor: ['gesture', 'voice', 'multimodal', 'ui'],
    },
    {
      id: 'accessibility',
      title: t('accessibility_title', language),
      href: '/onboarding/accessibility',
      completed: hasCompletedAccessibility,
      icon: '🎛️',
      desc: 'Choose primary interaction modality (Gesture, Voice, Both, UI) and contrast.',
      requiredFor: ['gesture', 'voice', 'multimodal', 'ui'],
    },
    {
      id: 'gesture',
      title: t('gesture_calibration_title', language),
      href: '/onboarding/gesture-calibration',
      completed: hasCompletedGestureCalibration,
      icon: '🖐️',
      desc: 'Calibrate optical camera tracking, stability metrics, and dwell time.',
      requiredFor: ['gesture', 'multimodal', 'ui'],
    },
    {
      id: 'voice',
      title: t('voice_setup_title', language),
      href: '/onboarding/voice-setup',
      completed: hasCompletedVoiceSetup,
      icon: '🎙️',
      desc: 'Test microphone levels, noise floor, and practice bounded factory commands.',
      requiredFor: ['voice', 'multimodal', 'ui'],
    },
    {
      id: 'training',
      title: t('training_title', language),
      href: '/training',
      completed: hasCompletedTraining,
      icon: '🛠️',
      desc: 'Complete simulated Order #1042 training assembly safely before production.',
      requiredFor: ['gesture', 'voice', 'multimodal', 'ui'],
    },
  ];

  const steps = allPossibleSteps
    .filter((s) => s.requiredFor.includes(modality))
    .map((s, idx) => ({ ...s, num: idx + 1 }));

  return (
    <div style={{ maxWidth: '800px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--worker-cyan)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Worker Onboarding & Readiness Gate (§ 13)
            </span>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem' }}>
              Pre-Production Setup
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Complete the required calibration and simulated training milestones before beginning live assembly work.
            </p>
          </div>

          <span
            style={{
              padding: '0.45rem 1rem',
              borderRadius: '999px',
              fontWeight: 800,
              fontSize: '0.85rem',
              background: isReady ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
              color: isReady ? 'var(--org-emerald)' : 'var(--accent-amber)',
              border: `1px solid ${isReady ? 'var(--org-emerald)' : 'var(--accent-amber)'}`,
            }}
          >
            {isReady ? `✓ ${t('readiness_ready', language)}` : `⏳ ${t('readiness_not_ready', language)}`}
          </span>
        </div>
      </div>

      {/* Step Cards Sequence */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {steps.map((s) => (
          <Link
            key={s.num}
            href={s.href}
            style={{ textDecoration: 'none' }}
          >
            <div
              className="glass-card"
              style={{
                padding: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderLeft: s.completed ? '5px solid var(--org-emerald)' : '5px solid rgba(255, 255, 255, 0.2)',
                transition: 'transform 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <span
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '50%',
                    background: s.completed ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                    color: s.completed ? 'var(--org-emerald)' : '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 800,
                    fontSize: '1.1rem',
                  }}
                >
                  {s.completed ? '✓' : s.num}
                </span>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.25rem' }}>{s.icon}</span>
                    <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {s.title}
                    </h3>
                  </div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
                    {s.desc}
                  </p>
                </div>
              </div>

              <span
                className="btn btn-secondary"
                style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
              >
                {s.completed ? 'Re-calibrate →' : 'Start →'}
              </span>
            </div>
          </Link>
        ))}
      </div>

      {/* Production Entry Button */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <Link
          href="/worker"
          className="btn btn-primary"
          style={{
            padding: '1.15rem 2.5rem',
            fontSize: '1.15rem',
            fontWeight: 800,
            borderRadius: '16px',
            opacity: isReady ? 1 : 0.65,
            pointerEvents: isReady ? 'auto' : 'none',
          }}
        >
          {t('start_work_btn', language)} →
        </Link>
      </div>
    </div>
  );
}
