'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';

export function DepartmentManagementPanel() {
  const { announce, playAudioCue } = useAccessibility();
  const [departments, setDepartments] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDeptName, setNewDeptName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadDepartments();
  }, []);

  const loadDepartments = async () => {
    setIsLoading(true);
    const data = await api.getOrgDepartments();
    setDepartments(data);
    setIsLoading(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDeptName.trim()) return;

    setIsSubmitting(true);
    try {
      await api.createOrgDepartment({ name: newDeptName.trim(), status: 'active' });
      announce(`Department ${newDeptName} created successfully.`);
      playAudioCue('confirm');
      setNewDeptName('');
      setShowCreateModal(false);
      loadDepartments();
    } catch {
      announce('Failed to create department.');
      playAudioCue('alert');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async (dept: any) => {
    if (!confirm(`Are you sure you want to deactivate department "${dept.name}"?`)) return;

    try {
      await api.deactivateOrgDepartment(dept.id);
      announce(`Department ${dept.name} deactivated.`);
      playAudioCue('confirm');
      loadDepartments();
    } catch {
      announce('Failed to deactivate department.');
      playAudioCue('alert');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header with Create Action */}
      <div className="glass-panel" style={{ padding: '1.5rem', borderRadius: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800 }}>🏢 Operational Departments</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.2rem' }}>
            Manage isolated operational departments, supervisor assignments, and assembly station lines.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
          style={{ minHeight: '48px', padding: '0 1.25rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
        >
          ➕ Add Department
        </button>
      </div>

      {/* Departments Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {departments.map((dept) => (
          <div key={dept.id} className="glass-panel" style={{ padding: '1.5rem', borderRadius: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1.25rem' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{dept.name}</h3>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.6rem',
                    borderRadius: '20px',
                    backgroundColor: dept.status === 'active' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: dept.status === 'active' ? '#10b981' : '#ef4444',
                  }}
                >
                  {dept.status.toUpperCase()}
                </span>
              </div>

              {/* Department Statistics */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginTop: '1.25rem' }}>
                <div style={{ padding: '0.75rem', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Supervisors</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '0.15rem' }}>{dept.supervisor_count ?? 1}</div>
                </div>

                <div style={{ padding: '0.75rem', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Workers</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '0.15rem' }}>{dept.worker_count ?? 2}</div>
                </div>

                <div style={{ padding: '0.75rem', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Active Tasks</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700, marginTop: '0.15rem' }}>{dept.active_tasks_count ?? 1}</div>
                </div>
              </div>
            </div>

            {/* Department Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleDeactivate(dept)}
                style={{ minHeight: '44px', fontSize: '0.85rem', color: '#ef4444' }}
              >
                Deactivate
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Create Department Modal Dialog */}
      {showCreateModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="dept-modal-title"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div className="glass-panel" style={{ width: '100%', maxWidth: '480px', padding: '2rem', borderRadius: '24px' }}>
            <h3 id="dept-modal-title" style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '0.5rem' }}>
              ➕ Create Department
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              Define a new organizational department entity scoped to this enterprise.
            </p>

            <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Department Name
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Battery Module Assembly"
                  value={newDeptName}
                  onChange={(e) => setNewDeptName(e.target.value)}
                  required
                  style={{ width: '100%', minHeight: '48px' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  style={{ minHeight: '48px', padding: '0 1.25rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                  style={{ minHeight: '48px', padding: '0 1.5rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
                >
                  {isSubmitting ? 'Creating...' : 'Create Department'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
