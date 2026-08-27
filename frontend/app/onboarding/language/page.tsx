'use client';

/**
 * Worker Language Selection Onboarding Step (/onboarding/language) (§ 7)
 * Persists preferred language for UI, voice synthesis, and supervisor translation.
 */

import React from 'react';
import { useRouter } from 'next/navigation';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { SUPPORTED_LANGUAGES, SupportedLanguage, t } from '@/shared/i18n/languages';

export default function LanguageOnboardingPage() {
  const router = useRouter();
  const { language, setLanguage, setHasCompletedLanguage, announce, playAudioCue } = useAccessibility();

  const handleSelectLanguage = (lang: SupportedLanguage) => {
    setLanguage(lang);
    setHasCompletedLanguage(true);
    playAudioCue('confirm');
    announce(`Language selected: ${lang}.`);
  };

  const handleContinue = () => {
    setHasCompletedLanguage(true);
    router.push('/onboarding/accessibility');
  };

  return (
    <div style={{ maxWidth: '720px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px', textAlign: 'center' }}>
        <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.5rem' }}>🌐</span>
        <h1 style={{ fontSize: '2rem', fontWeight: 800 }}>
          {t('language_select_title', language)}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
          {t('language_select_subtitle', language)}
        </p>

        {/* Language Selection Grid (§ 7) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '2rem' }}>
          {SUPPORTED_LANGUAGES.map((l) => {
            const isSelected = language === l.code;
            return (
              <button
                key={l.code}
                type="button"
                onClick={() => handleSelectLanguage(l.code)}
                className="glass-card"
                style={{
                  padding: '1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: 'pointer',
                  border: isSelected ? '3px solid var(--worker-cyan)' : '1px solid var(--surface-glass-border)',
                  background: isSelected ? 'rgba(6, 182, 212, 0.15)' : 'var(--surface-card)',
                  transform: isSelected ? 'scale(1.03)' : 'scale(1)',
                  transition: 'all 0.15s ease',
                  borderRadius: '16px',
                }}
              >
                <span style={{ fontSize: '2.5rem' }}>{l.flag}</span>
                <strong style={{ fontSize: '1.2rem', color: '#fff' }}>{l.nativeName}</strong>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{l.name}</span>
                {isSelected && (
                  <span
                    style={{
                      marginTop: '0.25rem',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '999px',
                      background: 'var(--worker-cyan)',
                      color: '#000',
                      fontWeight: 800,
                      fontSize: '0.75rem',
                    }}
                  >
                    ✓ Active
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2.5rem' }}>
          <button
            type="button"
            onClick={() => router.push('/onboarding')}
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
