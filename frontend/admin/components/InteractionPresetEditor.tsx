'use client';

/**
 * Admin Interaction Preset Editor
 * Loads presets from GET /api/v1/admin/configs (config_data persisted in
 * PostgreSQL) and saves through PUT — the previous version edited local demo
 * arrays and showed a fake "Saved" toast with no API call at all.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '@/shared/api/client';
import { InteractionPreset } from '@/shared/types';

export function InteractionPresetEditor() {
  const [presets, setPresets] = useState<InteractionPreset[]>([]);
  const [activePresetIndex, setActivePresetIndex] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedToast, setSavedToast] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getInteractionPresets();
      setPresets(data);
      setActivePresetIndex(0);
      setDirty(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load presets.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = presets[activePresetIndex];

  const updateActiveField = (field: keyof InteractionPreset, val: unknown) => {
    setPresets((prev) => {
      const copy = [...prev];
      copy[activePresetIndex] = { ...copy[activePresetIndex], [field]: val } as InteractionPreset;
      return copy;
    });
    setDirty(true);
  };

  const handleSave = async () => {
    if (!active) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.updateInteractionPreset(active.id, {
        config_data: {
          dwell_time_ms: active.dwellTimeMs,
          gesture_sensitivity: active.gestureSensitivity,
          acoustic_floor: active.acousticFloor,
        },
      });
      setPresets((prev) =>
        prev.map((p, idx) => (idx === activePresetIndex ? updated : p))
      );
      setDirty(false);
      setSavedToast(true);
      setTimeout(() => setSavedToast(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save preset.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreate = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const created = await api.createInteractionPreset({
        name: `New Preset ${presets.length + 1}`,
        description: 'Created from admin preset editor.',
        config_data: { dwell_time_ms: 450, gesture_sensitivity: 0.85, acoustic_floor: 0.6 },
      });
      setPresets((prev) => [...prev, created]);
      setActivePresetIndex(presets.length);
      setDirty(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create preset.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
        <p role="status" aria-live="polite" style={{ color: 'var(--text-secondary)' }}>
          Loading interaction presets…
        </p>
      </div>
    );
  }

  if (error && presets.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
        <p role="alert" style={{ color: 'var(--accent-rose)' }}>
          ⚠️ {error}
        </p>
        <button type="button" className="btn btn-secondary" onClick={load}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '1.25rem',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '1.2rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span style={{ color: 'var(--admin-purple)' }}>⚙️</span> Interaction Configuration Presets
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Persisted to PostgreSQL (config_data) — refresh and re-login keep your changes
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {error && (
            <span role="alert" style={{ color: 'var(--accent-rose)', fontWeight: 600 }}>
              {error}
            </span>
          )}
          {savedToast && (
            <span className="badge badge-emerald" role="status">
              ✓ Saved to database
            </span>
          )}
        </div>
      </div>

      {presets.length === 0 ? (
        <div
          role="status"
          style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}
        >
          No interaction presets defined yet for this organization.
          <div style={{ marginTop: '1rem' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={isSaving}
            >
              {isSaving ? 'Creating…' : 'Create first preset'}
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Config Presets
            </label>
            {presets.map((p, idx) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setActivePresetIndex(idx)}
                className="glass-card"
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  borderColor: idx === activePresetIndex ? 'var(--admin-purple)' : 'transparent',
                  background:
                    idx === activePresetIndex ? 'rgba(139, 92, 246, 0.12)' : 'var(--surface-card)',
                }}
              >
                <strong style={{ color: 'white', display: 'block', fontSize: '0.95rem' }}>{p.name}</strong>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.description}</span>
              </button>
            ))}
            <button
              type="button"
              onClick={handleCreate}
              disabled={isSaving}
              className="btn btn-secondary"
              style={{ minHeight: '36px', fontSize: '0.8rem' }}
            >
              {isSaving ? 'Creating…' : '+ New preset'}
            </button>
          </div>

          {active && (
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <label htmlFor="preset-dwell" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Temporal Dwell Time Threshold
                  </label>
                  <strong style={{ color: 'var(--worker-cyan)' }}>{active.dwellTimeMs} ms</strong>
                </div>
                <input
                  id="preset-dwell"
                  type="range"
                  min={250}
                  max={1200}
                  step={25}
                  value={active.dwellTimeMs}
                  onChange={(e) => updateActiveField('dwellTimeMs', Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--admin-purple)' }}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Controls continuous gesture hold duration required before firing intent recognition.
                </span>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <label htmlFor="preset-sensitivity" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Gesture Confidence Floor
                  </label>
                  <strong style={{ color: 'var(--org-emerald)' }}>
                    {Math.round(active.gestureSensitivity * 100)}%
                  </strong>
                </div>
                <input
                  id="preset-sensitivity"
                  type="range"
                  min={0.5}
                  max={0.99}
                  step={0.01}
                  value={active.gestureSensitivity}
                  onChange={(e) => updateActiveField('gestureSensitivity', Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--org-emerald)' }}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <label htmlFor="preset-floor" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Acoustic Noise Floor Gate
                  </label>
                  <strong style={{ color: 'var(--accent-amber)' }}>
                    {Math.round(active.acousticFloor * 100)}%
                  </strong>
                </div>
                <input
                  id="preset-floor"
                  type="range"
                  min={0.4}
                  max={0.95}
                  step={0.01}
                  value={active.acousticFloor}
                  onChange={(e) => updateActiveField('acousticFloor', Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent-amber)' }}
                />
              </div>

              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving || !dirty}
                className="btn btn-primary"
                style={{ marginTop: '0.5rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
              >
                {isSaving
                  ? 'Saving…'
                  : dirty
                  ? 'Save Preset Changes'
                  : 'No unsaved changes'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
