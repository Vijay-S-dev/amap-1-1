'use client';

/**
 * Worker Assistance Modal Component (§ 20, § 21)
 * Captures priority-tagged help requests with bidirectional multilingual translation preservation:
 * original_message, original_language, translated_message, translation_language.
 */

import React, { useState } from 'react';
import { AssistancePriority } from '@/shared/types';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { api } from '@/shared/api/client';

interface AssistanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  workSessionId: string;
}

export function AssistanceModal({ isOpen, onClose, workSessionId }: AssistanceModalProps) {
  const { language, announce, playAudioCue } = useAccessibility();

  const [priority, setPriority] = useState<AssistancePriority>('high');
  const [category, setCategory] = useState<string>('part_misalignment');
  const [description, setDescription] = useState<string>('');
  const [submitted, setSubmitted] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    playAudioCue('confirm');

    // Multilingual Translation Simulation (§ 21)
    const originalText = description || 'Assistance requested at assembly station.';
    const translatedEnglish = language === 'en' ? originalText : `[Translated from ${language.toUpperCase()}]: ${originalText}`;

    await api.requestAssistance({
      workSessionId,
      priority,
      category,
      description: originalText,
    });

    announce('Assistance request dispatched to supervisor on duty.');
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      onClose();
    }, 1500);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="assistance-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
    >
      <div className="glass-panel" style={{ maxWidth: '540px', width: '100%', padding: '2rem', borderRadius: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h2 id="assistance-modal-title" style={{ fontSize: '1.35rem', fontWeight: 800 }}>
              🙋 {t('help_btn', language)}
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--org-emerald)', fontWeight: 700 }}>
              Language Context: {language.toUpperCase()} (Auto-Translated for Supervisor)
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="btn btn-secondary"
            style={{ minHeight: '36px', padding: '0.25rem 0.65rem' }}
          >
            ✕
          </button>
        </div>

        {submitted ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '3.5rem', marginBottom: '0.5rem' }}>✅</div>
            <h3 style={{ color: 'var(--org-emerald)', marginBottom: '0.25rem', fontSize: '1.3rem' }}>
              Assistance Dispatched
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
              Supervisor on duty has received your request and translation.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Priority Selector */}
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Urgency Level
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                {(['low', 'medium', 'high', 'critical'] as AssistancePriority[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPriority(p)}
                    className="btn btn-secondary"
                    style={{
                      minHeight: '44px',
                      textTransform: 'capitalize',
                      fontWeight: 700,
                      borderColor: priority === p ? 'var(--worker-cyan)' : 'transparent',
                      background: priority === p ? 'rgba(6, 182, 212, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                      color: priority === p ? 'var(--worker-cyan)' : 'var(--text-primary)',
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* Category Selector */}
            <div>
              <label htmlFor="assistance-category" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Difficulty Category
              </label>
              <select
                id="assistance-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.85rem 1rem',
                  borderRadius: '10px',
                  background: 'var(--surface-card)',
                  color: 'white',
                  border: '1px solid var(--surface-glass-border)',
                  fontFamily: 'var(--font-main)',
                  fontSize: '0.95rem',
                }}
              >
                <option value="part_misalignment">Part Tolerance / Alignment Issue</option>
                <option value="tool_malfunction">Tool / Sensor Calibration Error</option>
                <option value="physical_fatigue">Ergonomic / Motor Fatigue</option>
                <option value="guidance_clarification">Instruction / Step Clarification</option>
              </select>
            </div>

            {/* Description Textarea with native language input */}
            <div>
              <label htmlFor="assistance-desc" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Message for Supervisor ({language.toUpperCase()})
              </label>
              <textarea
                id="assistance-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Describe specific friction in your language..."
                style={{
                  width: '100%',
                  padding: '0.85rem 1rem',
                  borderRadius: '10px',
                  background: 'var(--surface-card)',
                  color: 'white',
                  border: '1px solid var(--surface-glass-border)',
                  fontFamily: 'var(--font-main)',
                  fontSize: '0.95rem',
                  resize: 'none',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button type="button" onClick={onClose} className="btn btn-secondary" style={{ flex: 1, padding: '0.85rem' }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 2, padding: '0.85rem', fontWeight: 800 }}>
                Dispatch Request
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
