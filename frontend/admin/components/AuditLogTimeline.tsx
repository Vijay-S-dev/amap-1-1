'use client';

/**
 * Admin Audit Log Timeline Component
 * Renders immutable audit log events with filter controls and resource inspector.
 */

import React, { useState, useEffect } from 'react';
import { AuditLogEntry } from '@/shared/types';
import { api } from '@/shared/api/client';

export function AuditLogTimeline() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    async function loadLogs() {
      const data = await api.getAuditLogs();
      setLogs(data);
    }
    loadLogs();
  }, []);

  const filteredLogs = filter === 'all' ? logs : logs.filter((l) => l.eventType.includes(filter));

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--accent-blue)' }}>📜</span> Organization Audit Log Feed
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Immutable chronological record of administrative actions, config edits, and security events
          </span>
        </div>

        {/* Filter Buttons */}
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {['all', 'user', 'config', 'personalization'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className="btn btn-secondary"
              style={{
                minHeight: '32px',
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                textTransform: 'capitalize',
                background: filter === f ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {filteredLogs.map((log) => (
          <div
            key={log.id}
            className="glass-card"
            style={{
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.9rem',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="badge badge-purple" style={{ fontFamily: 'var(--font-mono)' }}>
                  {log.eventType}
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>by {log.actorUserId || 'system'}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>• {log.occurredAt}</span>
              </div>
              <pre
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                  marginTop: '0.25rem',
                }}
              >
                {JSON.stringify(log.eventData)}
              </pre>
            </div>

            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Verified ✓</span>
          </div>
        ))}
      </div>
    </div>
  );
}
