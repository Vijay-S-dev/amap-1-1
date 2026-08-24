'use client';

/**
 * Admin Interaction Preset Editor Component
 * Configures station-level and organization-wide interaction parameters:
 * Dwell Time, Gesture Confidence Sensitivity, Acoustic Noise Floor, and Modality Fallbacks.
 */

import React, { useState } from 'react';
import { InteractionPreset } from '@/shared/types';

export function InteractionPresetEditor() {
  const [presets, setPresets] = useState<InteractionPreset[]>([
    {
      id: 'preset-1',
      name: 'Default Factory Floor Preset',
      description: 'Standard optical tracking with moderate noise tolerance.',
      status: 'active',
      dwellTimeMs: 450,
      gestureSensitivity: 0.85,
      acousticFloor: 0.60,
    },
    {
      id: 'preset-2',
      name: 'High Noise Stamping Area',
      description: 'Elevated acoustic threshold with mandatory gesture confirmation.',
      status: 'active',
      dwellTimeMs: 600,
      gestureSensitivity: 0.90,
      acousticFloor: 0.75,
    },
  ]);

  const [activePresetIndex, setActivePresetIndex] = useState<number>(0);
  const [savedToast, setSavedToast] = useState<boolean>(false);

  const active = presets[activePresetIndex];

  const updateActiveField = (field: keyof InteractionPreset, val: any) => {
    setPresets((prev) => {
      const copy = [...prev];
      copy[activePresetIndex] = { ...copy[activePresetIndex], [field]: val };
      return copy;
    });
  };

  const handleSave = () => {
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 2000);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--admin-purple)' }}>⚙️</span> Interaction Configuration Presets
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Configure temporal dwell times, acoustic floor gates, and gesture sensitivity
          </span>
        </div>
        {savedToast && <span className="badge badge-emerald">✓ Saved & Synced to Edge Stations</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        {/* Preset Selector List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Config Presets</label>
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
                background: idx === activePresetIndex ? 'rgba(139, 92, 246, 0.12)' : 'var(--surface-card)',
              }}
            >
              <strong style={{ color: 'white', display: 'block', fontSize: '0.95rem' }}>{p.name}</strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.description}</span>
            </button>
          ))}
        </div>

        {/* Preset Parameter Form */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Dwell Time Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Temporal Dwell Time Threshold
              </label>
              <strong style={{ color: 'var(--worker-cyan)' }}>{active.dwellTimeMs} ms</strong>
            </div>
            <input
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

          {/* Gesture Confidence Sensitivity */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Gesture Confidence Floor
              </label>
              <strong style={{ color: 'var(--org-emerald)' }}>{Math.round(active.gestureSensitivity * 100)}%</strong>
            </div>
            <input
              type="range"
              min={0.5}
              max={0.99}
              step={0.01}
              value={active.gestureSensitivity}
              onChange={(e) => updateActiveField('gestureSensitivity', Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--org-emerald)' }}
            />
          </div>

          {/* Acoustic Floor */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Acoustic Noise Floor Gate
              </label>
              <strong style={{ color: 'var(--accent-amber)' }}>{Math.round(active.acousticFloor * 100)}%</strong>
            </div>
            <input
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
            className="btn btn-primary"
            style={{ marginTop: '0.5rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
          >
            Save Preset Changes
          </button>
        </div>
      </div>
    </div>
  );
}
