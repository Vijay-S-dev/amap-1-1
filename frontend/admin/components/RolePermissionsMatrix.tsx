'use client';

/**
 * AMAP Admin Role & Permissions Governance Matrix
 * Interactive role-based access control (RBAC) governance panel with immutable boundary guardrails.
 */

import React, { useState } from 'react';

interface PermissionEntry {
  id: string;
  name: string;
  category: 'Session' | 'Multimodal' | 'Assistance' | 'Governance' | 'Safety';
  description: string;
  roles: {
    admin: boolean;
    supervisor: boolean;
    worker: boolean;
  };
}

const INITIAL_PERMISSIONS: PermissionEntry[] = [
  {
    id: 'perm_1',
    name: 'session:read',
    category: 'Session',
    description: 'Read active workstation telemetry and step state',
    roles: { admin: true, supervisor: true, worker: true },
  },
  {
    id: 'perm_2',
    name: 'session:write',
    category: 'Session',
    description: 'Start, pause, advance, and conclude assembly sessions',
    roles: { admin: true, supervisor: true, worker: true },
  },
  {
    id: 'perm_3',
    name: 'multimodal:input',
    category: 'Multimodal',
    description: 'Stream optical 3D landmarks and acoustic voice commands',
    roles: { admin: false, supervisor: false, worker: true },
  },
  {
    id: 'perm_4',
    name: 'assistance:request',
    category: 'Assistance',
    description: 'Trigger supervisor call button on active workstation',
    roles: { admin: false, supervisor: false, worker: true },
  },
  {
    id: 'perm_5',
    name: 'assistance:resolve',
    category: 'Assistance',
    description: 'Claim, assign, and resolve open floor assistance tickets',
    roles: { admin: true, supervisor: true, worker: false },
  },
  {
    id: 'perm_6',
    name: 'admin:config:write',
    category: 'Governance',
    description: 'Modify interaction presets, dwell thresholds, and hitbox factors',
    roles: { admin: true, supervisor: false, worker: false },
  },
  {
    id: 'perm_7',
    name: 'safety:interlock:override',
    category: 'Safety',
    description: 'Secondary confirmation authorization for high-consequence machinery',
    roles: { admin: true, supervisor: true, worker: false },
  },
];

export function RolePermissionsMatrix() {
  const [permissions, setPermissions] = useState<PermissionEntry[]>(INITIAL_PERMISSIONS);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const togglePermission = (id: string, role: 'admin' | 'supervisor' | 'worker') => {
    // Admin cannot lose governance permission (invariant protection)
    if (id === 'perm_6' && role === 'admin') return;

    setPermissions((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, roles: { ...item.roles, [role]: !item.roles[role] } }
          : item
      )
    );
    setHasUnsavedChanges(true);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>🛡️</span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>Role & Permissions Governance Matrix</h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Enforces strict Role-Based Access Control (RBAC) and tenant boundary isolation across the platform.
          </p>
        </div>

        {hasUnsavedChanges && (
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--accent-amber)', fontWeight: 600 }}>
              ⚠️ Unsaved Policy Changes
            </span>
            <button
              type="button"
              className="btn btn-primary"
              style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
              onClick={() => setHasUnsavedChanges(false)}
            >
              Save Policy Matrix
            </button>
          </div>
        )}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--surface-glass-border)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <th style={{ padding: '0.75rem 1rem' }}>PERMISSION</th>
              <th style={{ padding: '0.75rem 1rem' }}>CATEGORY</th>
              <th style={{ padding: '0.75rem 1rem' }}>DESCRIPTION</th>
              <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                <span style={{ color: 'var(--admin-purple)', fontWeight: 700 }}>ADMIN</span>
              </th>
              <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                <span style={{ color: 'var(--org-emerald)', fontWeight: 700 }}>SUPERVISOR</span>
              </th>
              <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                <span style={{ color: 'var(--worker-cyan)', fontWeight: 700 }}>WORKER</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {permissions.map((perm) => (
              <tr
                key={perm.id}
                style={{
                  borderBottom: '1px solid var(--surface-glass-border)',
                  transition: 'background var(--transition-fast)',
                }}
              >
                <td style={{ padding: '1rem', fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  {perm.name}
                </td>
                <td style={{ padding: '1rem' }}>
                  <span
                    style={{
                      padding: '0.2rem 0.6rem',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      background:
                        perm.category === 'Safety'
                          ? 'rgba(244, 63, 94, 0.2)'
                          : perm.category === 'Governance'
                          ? 'rgba(139, 92, 246, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)',
                      color:
                        perm.category === 'Safety'
                          ? 'var(--accent-rose)'
                          : perm.category === 'Governance'
                          ? 'var(--admin-purple)'
                          : 'var(--accent-blue)',
                    }}
                  >
                    {perm.category}
                  </span>
                </td>
                <td style={{ padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  {perm.description}
                </td>
                <td style={{ padding: '1rem', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={perm.roles.admin}
                    onChange={() => togglePermission(perm.id, 'admin')}
                    style={{ cursor: 'pointer', transform: 'scale(1.2)' }}
                    aria-label={`Toggle ${perm.name} for admin`}
                  />
                </td>
                <td style={{ padding: '1rem', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={perm.roles.supervisor}
                    onChange={() => togglePermission(perm.id, 'supervisor')}
                    style={{ cursor: 'pointer', transform: 'scale(1.2)' }}
                    aria-label={`Toggle ${perm.name} for supervisor`}
                  />
                </td>
                <td style={{ padding: '1rem', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={perm.roles.worker}
                    onChange={() => togglePermission(perm.id, 'worker')}
                    style={{ cursor: 'pointer', transform: 'scale(1.2)' }}
                    aria-label={`Toggle ${perm.name} for worker`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
