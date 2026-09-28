'use client';

/**
 * Gesture Control Panel (frontend/worker/components/GestureControlPanel.tsx)
 *
 * Worker-personalized gesture mapping + calibration editor.
 * All changes are persisted to PostgreSQL through
 * PUT /personalization/me/gesture-mapping (worker_personalizations with audit
 * history) — never localStorage.
 */

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';
import { t } from '@/shared/i18n/languages';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';

interface GestureControlPanelProps {
  /** Effective mapping loaded by the workstation (worker -> preset -> default). */
  gestureActionMap: Record<string, string>;
  sources: Record<string, string>;
  calibration: Record<string, any>;
  onMappingChanged: (map: Record<string, string>, calibration: Record<string, any>) => void;
  enabledGesturesList: string[];
  actionChoices: string[];
}

const CALIBRATION_FIELDS: { key: string; label: string; min: number; max: number; step: number; unit?: string }[] = [
  { key: 'dwell_time_ms', label: 'Dwell time', min: 200, max: 1500, step: 50, unit: 'ms' },
  { key: 'click_debounce_ms', label: 'Click debounce', min: 250, max: 2000, step: 50, unit: 'ms' },
  { key: 'cursor_sensitivity', label: 'Pointer sensitivity', min: 0.8, max: 3, step: 0.1, unit: 'x' },
  { key: 'scroll_sensitivity', label: 'Scroll sensitivity', min: 60, max: 600, step: 20, unit: 'px' },
  { key: 'smoothing_alpha', label: 'Smoothing (lower = smoother)', min: 0.1, max: 1, step: 0.05 },
  { key: 'jitter_threshold', label: 'Jitter threshold', min: 0.004, max: 0.05, step: 0.002 },
];

export function GestureControlPanel({
  gestureActionMap,
  sources,
  calibration,
  onMappingChanged,
  enabledGesturesList,
  actionChoices,
}: GestureControlPanelProps) {
  const { language } = useAccessibility();
  const [isOpen, setIsOpen] = useState(false);
  const [draftMap, setDraftMap] = useState<Record<string, string>>(gestureActionMap);
  const [draftCalibration, setDraftCalibration] = useState<Record<string, any>>(calibration);
  const [enabledDraft, setEnabledDraft] = useState<Record<string, boolean>>(
    calibration?.enabled_gestures || {}
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState(false);

  useEffect(() => {
    setDraftMap(gestureActionMap);
    setDraftCalibration(calibration);
    setEnabledDraft(calibration?.enabled_gestures || {});
  }, [gestureActionMap, calibration]);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      const result = await api.updateGestureMapping({
        gesture_action_map: draftMap,
        calibration: { ...draftCalibration, enabled_gestures: enabledDraft },
        change_reason: 'Workstation gesture control panel update',
      });
      onMappingChanged(result.gesture_action_map, result.calibration);
      setSaveOk(true);
      window.setTimeout(() => setSaveOk(false), 2500);
    } catch (err: any) {
      setSaveError(err?.message || 'Failed to save gesture mapping.');
    } finally {
      setIsSaving(false);
    }
  };

  const sourceBadge = (gesture: string) => {
    const src = sources[gesture] || 'default';
    const labels: Record<string, string> = {
      worker_override: t('control_panel_your_setting', language),
      preset: t('control_panel_org_preset', language),
      default: t('control_panel_default', language),
    };
    const colors: Record<string, string> = {
      worker_override: 'var(--org-emerald)',
      preset: 'var(--worker-cyan)',
      default: 'var(--text-muted)',
    };
    return (
      <span
        style={{
          fontSize: '0.62rem',
          fontWeight: 800,
          letterSpacing: '0.08em',
          color: colors[src],
          border: `1px solid ${colors[src]}`,
          borderRadius: '6px',
          padding: '1px 5px',
        }}
      >
        {labels[src]}
      </span>
    );
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', borderRadius: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            🎛️ Gesture Control & Personalization
          </h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Map gestures to actions and tune interaction sensitivity — saved to your worker profile in PostgreSQL.
          </span>
        </div>
        <button
          type="button"
          className={`btn ${isOpen ? 'btn-secondary' : 'btn-primary'}`}
          style={{ minHeight: '44px' }}
          onClick={() => setIsOpen((v) => !v)}
          aria-expanded={isOpen}
        >
          {isOpen ? 'Close Settings ▲' : 'Customize Gestures ▼'}
        </button>
      </div>

      {isOpen && (
        <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Gesture -> Action mapping */}
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 800, marginBottom: '0.6rem', color: 'var(--worker-cyan)' }}>
              GESTURE → ACTION MAPPING
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0.6rem' }}>
              {enabledGesturesList.map((gesture) => (
                <div
                  key={gesture}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--surface-glass-border)',
                    borderRadius: '10px',
                    padding: '0.5rem 0.6rem',
                  }}
                >
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      minWidth: 130,
                      color: 'var(--text-primary)',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={enabledDraft[gesture] !== false}
                      onChange={(e) => setEnabledDraft((prev) => ({ ...prev, [gesture]: e.target.checked }))}
                      aria-label={`Enable gesture ${gesture}`}
                    />
                    {gesture}
                  </label>
                  <span style={{ color: 'var(--text-muted)' }}>→</span>
                  <select
                    value={draftMap[gesture] || ''}
                    onChange={(e) => setDraftMap((prev) => ({ ...prev, [gesture]: e.target.value }))}
                    aria-label={`Action for gesture ${gesture}`}
                    style={{
                      flex: 1,
                      minHeight: '38px',
                      background: 'rgba(9,13,22,0.9)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--surface-glass-border)',
                      borderRadius: '8px',
                      padding: '0.25rem 0.5rem',
                      fontSize: '0.82rem',
                    }}
                  >
                    {actionChoices.map((action) => (
                      <option key={action} value={action}>
                        {action}
                      </option>
                    ))}
                  </select>
                  {sourceBadge(gesture)}
                </div>
              ))}
            </div>
          </div>

          {/* Calibration sliders */}
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 800, marginBottom: '0.6rem', color: 'var(--worker-cyan)' }}>
              INTERACTION CALIBRATION
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.9rem' }}>
              {CALIBRATION_FIELDS.map((field) => (
                <label key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {field.label}:{' '}
                    <strong style={{ color: 'var(--text-primary)' }}>
                      {draftCalibration[field.key]}
                      {field.unit ? ` ${field.unit}` : ''}
                    </strong>
                  </span>
                  <input
                    type="range"
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    value={Number(draftCalibration[field.key] ?? 0)}
                    onChange={(e) =>
                      setDraftCalibration((prev) => ({ ...prev, [field.key]: Number(e.target.value) }))
                    }
                    aria-label={field.label}
                  />
                </label>
              ))}
            </div>
          </div>

          {/* Handedness */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.85rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Preferred hand:</span>
            {(['Either', 'Left', 'Right'] as const).map((hand) => (
              <button
                key={hand}
                type="button"
                className={`btn ${(draftCalibration.handedness || 'Either') === hand ? 'btn-primary' : 'btn-secondary'}`}
                style={{ minHeight: '40px', padding: '0.35rem 0.9rem', fontSize: '0.8rem' }}
                onClick={() => setDraftCalibration((prev) => ({ ...prev, handedness: hand }))}
                aria-pressed={(draftCalibration.handedness || 'Either') === hand}
              >
                {hand}
              </button>
            ))}
          </div>

          {/* Save */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-primary"
              style={{ minHeight: '48px', background: 'var(--org-emerald)', borderColor: 'var(--org-emerald)', fontWeight: 800 }}
              onClick={handleSave}
              disabled={isSaving}
              aria-busy={isSaving}
            >
              💾 {isSaving ? t('control_panel_saving', language) : t('control_panel_save', language)}
            </button>
            {saveOk && (
              <span role="status" style={{ color: 'var(--org-emerald)', fontWeight: 700, fontSize: '0.85rem' }}>
                ✓ {t('control_panel_saved', language)}
              </span>
            )}
            {saveError && (
              <span role="alert" style={{ color: 'var(--accent-rose)', fontWeight: 700, fontSize: '0.85rem' }}>
                ⚠️ {saveError}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default GestureControlPanel;
