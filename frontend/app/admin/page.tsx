'use client';

/**
 * Admin & System Configuration Studio (/admin)
 * Interaction configurations, evidence adaptation approval, and immutable audit logs.
 */

import React from 'react';
import { InteractionPresetEditor } from '@/admin/components/InteractionPresetEditor';
import { AdaptationReviewPanel } from '@/admin/components/AdaptationReviewPanel';
import { AuditLogTimeline } from '@/admin/components/AuditLogTimeline';

export default function AdminPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Admin Studio Header */}
      <div className="glass-panel" style={{ padding: '2rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--admin-purple)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              System Governance & Tuning
            </span>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem' }}>
              Configuration & Interaction Studio
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Manage station interaction presets, review worker personalization evidence, and query immutable tenant audit trails.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" className="btn btn-secondary">
              🔒 View Role Permissions Matrix
            </button>
            <button
              type="button"
              className="btn btn-primary"
              style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
            >
              + Create Interaction Preset
            </button>
          </div>
        </div>
      </div>

      {/* Admin Components Grid */}
      <InteractionPresetEditor />
      <AdaptationReviewPanel />
      <AuditLogTimeline />
    </div>
  );
}
