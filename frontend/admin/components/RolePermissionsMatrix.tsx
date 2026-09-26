'use client';

/**
 * AMAP Admin Role & Permissions Governance Matrix
 * Loads the organization-scoped permission matrix from PostgreSQL via
 * GET/PUT /api/v1/permissions/matrix. Every toggle is persisted server-side
 * immediately (no local-only unsaved state, no hardcoded permission table).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '@/shared/api/client';
import { PermissionMatrix } from '@/shared/types';

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  admin: { label: 'ADMIN', color: 'var(--admin-purple)' },
  organization_admin: { label: 'ORG ADMIN', color: 'var(--admin-purple)' },
  supervisor: { label: 'SUPERVISOR', color: 'var(--org-emerald)' },
  worker: { label: 'WORKER', color: 'var(--worker-cyan)' },
};

function categoryFor(name: string): string {
  if (name.startsWith('session:')) return 'Session';
  if (name.startsWith('multimodal:')) return 'Multimodal';
  if (name.startsWith('assistance:')) return 'Assistance';
  if (name.startsWith('admin:')) return 'Governance';
  return 'General';
}

export function RolePermissionsMatrix() {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setMatrix(await api.getPermissionsMatrix());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load permission matrix.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const togglePermission = async (permissionName: string, role: string) => {
    if (!matrix) return;
    const current = matrix.permissions.find((p) => p.permission.name === permissionName);
    if (!current) return;
    const granted = current.roles[role] ?? false;
    const key = `${permissionName}:${role}`;
    setBusyKey(key);
    setError(null);
    try {
      const updated = await api.setPermissionGrant({
        role_name: role,
        permission_name: permissionName,
        granted: !granted,
      });
      setMatrix(updated);
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.message : 'Failed to update permission.';
      setError(detail);
      // refetch to drop any optimistic illusion — server state is the truth
      await load();
    } finally {
      setBusyKey(null);
    }
  };

  if (isLoading) {
    return (
      <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
        <p role="status" aria-live="polite" style={{ color: 'var(--text-secondary)' }}>
          Loading permission matrix from server…
        </p>
      </div>
    );
  }

  if (error && !matrix) {
    return (
      <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
        <p role="alert" style={{ color: 'var(--accent-rose)' }}>
          ⚠️ {error}
        </p>
        <button type="button" className="btn btn-secondary" onClick={load}>
          Retry
        </button>
      </div>
    );
  }

  if (!matrix) return null;

  const roleColumns = matrix.roles.filter((r) => ROLE_LABELS[r]);

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>🛡️</span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>
              Role &amp; Permissions Governance Matrix
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Organization-scoped RBAC grants persisted in PostgreSQL. Changes apply
            to API enforcement immediately.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {error && (
            <span role="alert" style={{ color: 'var(--accent-rose)', fontWeight: 600 }}>
              {error}
            </span>
          )}
          <button type="button" className="btn btn-secondary" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      {matrix.permissions.length === 0 ? (
        <div
          role="status"
          style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}
        >
          No permissions defined in the catalog yet.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--surface-glass-border)',
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                }}
              >
                <th style={{ padding: '0.75rem 1rem' }}>PERMISSION</th>
                <th style={{ padding: '0.75rem 1rem' }}>CATEGORY</th>
                <th style={{ padding: '0.75rem 1rem' }}>DESCRIPTION</th>
                {roleColumns.map((role) => (
                  <th key={role} style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                    <span style={{ color: ROLE_LABELS[role].color, fontWeight: 700 }}>
                      {ROLE_LABELS[role].label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.permissions.map((entry) => {
                const permName = entry.permission.name;
                const category = categoryFor(permName);
                return (
                  <tr
                    key={entry.permission.id}
                    style={{
                      borderBottom: '1px solid var(--surface-glass-border)',
                      transition: 'background var(--transition-fast)',
                    }}
                  >
                    <td
                      style={{
                        padding: '1rem',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        color: 'var(--text-primary)',
                      }}
                    >
                      {permName}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <span
                        style={{
                          padding: '0.2rem 0.6rem',
                          borderRadius: '6px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          background:
                            category === 'Governance'
                              ? 'rgba(139, 92, 246, 0.2)'
                              : 'rgba(59, 130, 246, 0.2)',
                          color:
                            category === 'Governance'
                              ? 'var(--admin-purple)'
                              : 'var(--accent-blue)',
                        }}
                      >
                        {category}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      {entry.permission.description || '—'}
                    </td>
                    {roleColumns.map((role) => {
                      const locked = permName === 'admin:config' && role === 'admin';
                      const key = `${permName}:${role}`;
                      return (
                        <td key={role} style={{ padding: '1rem', textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={entry.roles[role] ?? false}
                            disabled={locked || busyKey === key}
                            onChange={() => togglePermission(permName, role)}
                            style={{ cursor: locked ? 'not-allowed' : 'pointer', transform: 'scale(1.2)' }}
                            aria-label={`Toggle ${permName} for ${role}${
                              locked ? ' (locked governance invariant)' : ''
                            }`}
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
