'use client';

/**
 * Supervisor & Operations Management Portal (/organization) (§ 2, § 3, § 9, § 11, § 21, § 29).
 * Real-time plant fleet telemetry, task dispatching, assistance queue triage,
 * emergency safety halt handling, operational analytics, and immutable audit timeline.
 * 100% Real Backend Data-Connected.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  AssistanceQueuePanel,
  EmergencyEventBanner,
  LiveWorkerMonitor,
  SupervisorAnalyticsPanel,
  SupervisorAuditTimeline,
  SupervisorSummaryKPIs,
  TaskAssignmentModal,
  WorkerDetailPanel,
} from '@/organization/components';
import { api } from '@/shared/api/client';

export default function OrganizationPage() {
  const [activeTab, setActiveTab] = useState<'FLEET' | 'ASSISTANCE' | 'ANALYTICS' | 'AUDIT'>('FLEET');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Live Data States
  const [summary, setSummary] = useState({
    active_workers_count: 0,
    available_workers_count: 0,
    workers_in_task_count: 0,
    workers_requesting_assistance_count: 0,
    completed_tasks_count: 0,
    in_progress_tasks_count: 0,
    failed_tasks_count: 0,
    current_workload_percent: 0.0,
    emergency_stops_active: 0,
  });

  const [workers, setWorkers] = useState<any[]>([]);
  const [assistanceRequests, setAssistanceRequests] = useState<any[]>([]);
  const [emergencyEvents, setEmergencyEvents] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState({
    tasks_assigned_count: 0,
    tasks_completed_count: 0,
    tasks_in_progress_count: 0,
    average_task_duration_minutes: 0.0,
    workflow_completion_rate: 0.0,
    total_assistance_requests: 0,
    resolved_assistance_requests: 0,
    average_resolution_time_minutes: 0.0,
    emergency_stops_count: 0,
  });
  const [auditEvents, setAuditEvents] = useState<any[]>([]);

  // Modal States
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [preselectedWorkerForAssign, setPreselectedWorkerForAssign] = useState<string | null>(null);

  // Fetch all real supervisor data from backend
  const fetchSupervisorData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [sumRes, wrkRes, astRes, emgRes, anaRes, audRes] = await Promise.allSettled([
        api.getSupervisorDashboard(),
        api.getSupervisorWorkers(),
        api.getSupervisorAssistance(),
        api.getSupervisorEmergencyEvents(),
        api.getSupervisorAnalytics(),
        api.getSupervisorAudit(30),
      ]);

      if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
      if (wrkRes.status === 'fulfilled') setWorkers(wrkRes.value);
      if (astRes.status === 'fulfilled') setAssistanceRequests(astRes.value);
      if (emgRes.status === 'fulfilled') setEmergencyEvents(emgRes.value);
      if (anaRes.status === 'fulfilled') setAnalytics(anaRes.value);
      if (audRes.status === 'fulfilled') setAuditEvents(audRes.value);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial load + lightweight 8-second live polling
  useEffect(() => {
    fetchSupervisorData();
    const interval = setInterval(fetchSupervisorData, 8000);
    return () => clearInterval(interval);
  }, [fetchSupervisorData]);

  // Handlers
  const handleInspectWorker = (workerId: string) => {
    setSelectedWorkerId(workerId);
    setIsDetailModalOpen(true);
  };

  const handleOpenAssignModal = (workerId?: string) => {
    setPreselectedWorkerForAssign(workerId || null);
    setIsAssignModalOpen(true);
  };

  const handleEmergencyAcknowledge = async (eventId: string) => {
    await api.acknowledgeSupervisorAssistance(eventId).catch(console.error);
    fetchSupervisorData();
  };

  return (
    <main
      role="main"
      aria-label="Supervisor Operations Portal"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem', paddingBottom: '3rem' }}
    >
      {/* 1. Emergency Safety Halt Alert Banner (§ 8, § 29) */}
      <EmergencyEventBanner
        emergencyEvents={emergencyEvents}
        onAcknowledge={handleEmergencyAcknowledge}
      />

      {/* 2. Top Header & Dispatch Actions */}
      <div className="glass-panel" style={{ padding: '2rem', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--org-emerald)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Supervisor Operations Portal
              </span>
              {refreshing && (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  (Refreshing telemetry...)
                </span>
              )}
            </div>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.25rem', color: 'white' }}>
              Plant Operations & Fleet Management
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', fontSize: '0.95rem' }}>
              Accessible Multimodal Assembly Operations • Real-time Task Dispatch & Operator Triage
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => fetchSupervisorData()}
              className="btn btn-secondary"
              style={{ minHeight: '48px', padding: '0.6rem 1.25rem' }}
            >
              🔄 Refresh
            </button>
            <button
              type="button"
              onClick={() => handleOpenAssignModal()}
              className="btn btn-primary"
              style={{
                minHeight: '48px',
                padding: '0.6rem 1.5rem',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              }}
            >
              + Dispatch Task Assignment
            </button>
          </div>
        </div>

        {/* Real KPI Cards */}
        <div style={{ marginTop: '1.75rem' }}>
          <SupervisorSummaryKPIs summary={summary} />
        </div>
      </div>

      {/* 3. Navigation Tabs */}
      <div
        role="tablist"
        aria-label="Supervisor Views"
        style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid var(--surface-glass-border)', paddingBottom: '0.5rem', flexWrap: 'wrap' }}
      >
        <button
          role="tab"
          aria-selected={activeTab === 'FLEET'}
          type="button"
          onClick={() => setActiveTab('FLEET')}
          className={`btn ${activeTab === 'FLEET' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ minHeight: '44px', padding: '0.5rem 1.25rem' }}
        >
          👥 Worker Fleet ({workers.length})
        </button>

        <button
          role="tab"
          aria-selected={activeTab === 'ASSISTANCE'}
          type="button"
          onClick={() => setActiveTab('ASSISTANCE')}
          className={`btn ${activeTab === 'ASSISTANCE' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ minHeight: '44px', padding: '0.5rem 1.25rem' }}
        >
          ⚠️ Assistance Queue ({assistanceRequests.filter((r) => r.status !== 'resolved').length})
        </button>

        <button
          role="tab"
          aria-selected={activeTab === 'ANALYTICS'}
          type="button"
          onClick={() => setActiveTab('ANALYTICS')}
          className={`btn ${activeTab === 'ANALYTICS' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ minHeight: '44px', padding: '0.5rem 1.25rem' }}
        >
          📊 Operational Analytics
        </button>

        <button
          role="tab"
          aria-selected={activeTab === 'AUDIT'}
          type="button"
          onClick={() => setActiveTab('AUDIT')}
          className={`btn ${activeTab === 'AUDIT' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ minHeight: '44px', padding: '0.5rem 1.25rem' }}
        >
          📜 Audit Timeline ({auditEvents.length})
        </button>
      </div>

      {/* 4. Tab Views */}
      {activeTab === 'FLEET' && (
        <LiveWorkerMonitor
          workers={workers}
          onSelectWorker={handleInspectWorker}
          onDispatchTask={handleOpenAssignModal}
        />
      )}

      {activeTab === 'ASSISTANCE' && (
        <AssistanceQueuePanel
          requests={assistanceRequests}
          onRefresh={fetchSupervisorData}
        />
      )}

      {activeTab === 'ANALYTICS' && (
        <SupervisorAnalyticsPanel analytics={analytics} />
      )}

      {activeTab === 'AUDIT' && (
        <SupervisorAuditTimeline events={auditEvents} />
      )}

      {/* 5. Inspection Modal */}
      <WorkerDetailPanel
        workerId={selectedWorkerId}
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
      />

      {/* 6. Task Assignment Modal */}
      <TaskAssignmentModal
        isOpen={isAssignModalOpen}
        onClose={() => setIsAssignModalOpen(false)}
        workers={workers}
        preselectedWorkerId={preselectedWorkerForAssign}
        onTaskAssigned={fetchSupervisorData}
      />
    </main>
  );
}
