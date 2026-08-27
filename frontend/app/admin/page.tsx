'use client';

/**
 * AMAP Enterprise Organization & System Administration Portal (/admin)
 * Multi-tenant organization dashboard, department management, supervisor/worker rosters,
 * workflow definitions, interaction presets, evidence adaptation review, and immutable audit trails.
 */

import React, { useState } from 'react';
import {
  AdaptationReviewPanel,
  AuditLogTimeline,
  DepartmentManagementPanel,
  EnterpriseWorkflowManager,
  InteractionPresetEditor,
  OrganizationOverviewPanel,
  RolePermissionsMatrix,
  SupervisorManagementPanel,
  WorkerManagementPanel,
} from '@/admin/components';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'departments' | 'supervisors' | 'workers' | 'workflows' | 'presets' | 'permissions' | 'adaptations' | 'audit'
  >('overview');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Enterprise Organization Studio Header */}
      <div className="glass-panel" style={{ padding: '2rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--admin-purple)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Enterprise Governance & Multi-Tenant Operations
            </span>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem' }}>
              Enterprise Organization Studio
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Manage organizational hierarchy, departments, supervisors, workers, approved workflow templates, and audit logs.
            </p>
          </div>

          {/* Navigation Tab Pills */}
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`btn ${activeTab === 'overview' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'overview' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('overview')}
            >
              🏢 Overview
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'departments' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'departments' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('departments')}
            >
              🏬 Departments
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'supervisors' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'supervisors' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('supervisors')}
            >
              👥 Supervisors
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'workers' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'workers' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('workers')}
            >
              👷 Workers
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'workflows' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'workflows' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('workflows')}
            >
              🛠️ Workflows
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'presets' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'presets' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('presets')}
            >
              ⚙️ Presets
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'permissions' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'permissions' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('permissions')}
            >
              🛡️ Permissions
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'adaptations' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'adaptations' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('adaptations')}
            >
              📊 Adaptations
            </button>
            <button
              type="button"
              className={`btn ${activeTab === 'audit' ? 'btn-primary' : 'btn-secondary'}`}
              style={activeTab === 'audit' ? { background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' } : {}}
              onClick={() => setActiveTab('audit')}
            >
              🔒 Audit Trail
            </button>
          </div>
        </div>
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && <OrganizationOverviewPanel />}
      {activeTab === 'departments' && <DepartmentManagementPanel />}
      {activeTab === 'supervisors' && <SupervisorManagementPanel />}
      {activeTab === 'workers' && <WorkerManagementPanel />}
      {activeTab === 'workflows' && <EnterpriseWorkflowManager />}
      {activeTab === 'presets' && <InteractionPresetEditor />}
      {activeTab === 'permissions' && <RolePermissionsMatrix />}
      {activeTab === 'adaptations' && <AdaptationReviewPanel />}
      {activeTab === 'audit' && <AuditLogTimeline />}
    </div>
  );
}
