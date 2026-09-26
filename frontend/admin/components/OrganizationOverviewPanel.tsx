'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';

export function OrganizationOverviewPanel() {
  const { announce, playAudioCue } = useAccessibility();
  const [dashboard, setDashboard] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');
  const [location, setLocation] = useState('');
  const [dwellTime, setDwellTime] = useState(500);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const [dashData, profData] = await Promise.all([
      api.getOrgDashboard(),
      api.getOrgProfile(),
    ]);
    setDashboard(dashData);
    setProfile(profData);
    if (profData) {
      setName(profData.name || '');
      setIndustry(profData.industry || '');
      setLocation(profData.location || '');
      setDwellTime(profData.accessibility_defaults?.default_dwell_time_ms || 500);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveStatus('saving');
    try {
      await api.updateOrgProfile({
        name,
        industry,
        location,
        accessibility_defaults: {
          ...profile?.accessibility_defaults,
          default_dwell_time_ms: dwellTime,
        },
      });
      setSaveStatus('saved');
      announce('Organization profile and accessibility settings successfully updated.');
      playAudioCue('confirm');
      setIsEditing(false);
      loadData();
    } catch {
      setSaveStatus('idle');
      announce('Failed to update organization profile.');
      playAudioCue('alert');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Organization Header & Overview */}
      <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '2rem' }}>🏭</span>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>{profile?.name || 'Acme Motors — Assembly Plant 1'}</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.15rem' }}>
                  {profile?.industry || 'Automotive & Electric Powertrain'} • {profile?.location || 'Sector 4 Facility'}
                </p>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setIsEditing(!isEditing)}
            style={{ minHeight: '48px', padding: '0 1.25rem' }}
          >
            {isEditing ? '✕ Cancel Edit' : '✏️ Edit Profile & Settings'}
          </button>
        </div>

        {/* Edit Form */}
        {isEditing && (
          <form onSubmit={handleSave} style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Organization Name
              </label>
              <input
                type="text"
                className="input-field"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={{ width: '100%', minHeight: '48px' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Industry Sector
              </label>
              <input
                type="text"
                className="input-field"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                style={{ width: '100%', minHeight: '48px' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Facility Location
              </label>
              <input
                type="text"
                className="input-field"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                style={{ width: '100%', minHeight: '48px' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Default Optical Dwell Time (ms)
              </label>
              <input
                type="number"
                min="200"
                max="2000"
                step="50"
                className="input-field"
                value={dwellTime}
                onChange={(e) => setDwellTime(Number(e.target.value))}
                style={{ width: '100%', minHeight: '48px' }}
              />
            </div>

            <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saveStatus === 'saving'}
                style={{ minHeight: '48px', padding: '0 1.5rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
              >
                {saveStatus === 'saving' ? 'Saving...' : '💾 Save Settings'}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Summary Operational KPIs Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div className="glass-panel" style={{ padding: '1.25rem', borderRadius: '16px', borderLeft: '4px solid #3b82f6' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
            Total Workforce
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: '#3b82f6' }}>
            {dashboard?.total_workers_count ?? '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            {dashboard?.active_workers_count ?? '—'} active on line
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderRadius: '16px', borderLeft: '4px solid #10b981' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
            Line Utilization
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: '#10b981' }}>
            {dashboard?.current_line_utilization_percent ?? '—'}%
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            {dashboard?.active_tasks_count ?? '—'} active assembly stations
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderRadius: '16px', borderLeft: '4px solid #8b5cf6' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
            Departments
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: '#8b5cf6' }}>
            {dashboard?.departments_count ?? '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            {dashboard?.supervisors_count ?? '—'} floor supervisors
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderRadius: '16px', borderLeft: '4px solid #f59e0b' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
            Completed Cycles
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: '#f59e0b' }}>
            {dashboard?.completed_tasks_count ?? '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            94.5% first-pass yield
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderRadius: '16px', borderLeft: '4px solid #ef4444' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
            Assistance Tickets
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: '#ef4444' }}>
            {dashboard?.open_assistance_requests_count ?? '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Avg response: 1.5 mins
          </div>
        </div>
      </div>
    </div>
  );
}
