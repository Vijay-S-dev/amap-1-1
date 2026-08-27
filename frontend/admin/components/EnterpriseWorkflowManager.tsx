'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';

export function EnterpriseWorkflowManager() {
  const { announce, playAudioCue } = useAccessibility();
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<any>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // New Workflow State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [duration, setDuration] = useState(15.0);
  const [steps, setSteps] = useState<any[]>([
    { title: 'Optical Component Check', instruction: 'Inspect component orientation on fixture bed.', is_safety_critical: false },
    { title: 'Fastener Torquing', instruction: 'Torque M6 bolts to specification in star sequence.', is_safety_critical: false },
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const [wfData, deptsData] = await Promise.all([
      api.getOrgWorkflows(),
      api.getOrgDepartments(),
    ]);
    setWorkflows(wfData || []);
    setDepartments(deptsData || []);
    if (wfData?.length > 0 && !selectedWorkflow) {
      setSelectedWorkflow(wfData[0]);
    }
    if (deptsData?.length > 0 && !departmentId) {
      setDepartmentId(deptsData[0].id);
    }
  };

  const handleAddStep = () => {
    setSteps([
      ...steps,
      {
        title: `Step ${steps.length + 1}`,
        instruction: 'Enter operator guidance instruction.',
        is_safety_critical: false,
      },
    ]);
  };

  const handleRemoveStep = (index: number) => {
    if (steps.length <= 1) return;
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    try {
      await api.createOrgWorkflow({
        name: name.trim(),
        description: description.trim(),
        department_id: departmentId || undefined,
        estimated_duration_minutes: duration,
        steps,
      });
      announce(`Workflow ${name} successfully configured and published.`);
      playAudioCue('confirm');
      setName('');
      setDescription('');
      setShowCreateModal(false);
      loadData();
    } catch {
      announce('Failed to create workflow template.');
      playAudioCue('alert');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header with Create Action */}
      <div className="glass-panel" style={{ padding: '1.5rem', borderRadius: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800 }}>🛠️ Approved Workflow & Task Templates</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.2rem' }}>
            Define standard operating procedures, safety-critical interlocking checkpoints, and step sequences.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
          style={{ minHeight: '48px', padding: '0 1.25rem', background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)' }}
        >
          ➕ Define Workflow
        </button>
      </div>

      {/* Main Workflow View: List & Step Tree */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {/* Workflow Catalog List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {workflows.map((wf) => (
            <div
              key={wf.id}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedWorkflow(wf)}
              onKeyDown={(e) => e.key === 'Enter' && setSelectedWorkflow(wf)}
              className="glass-panel"
              style={{
                padding: '1.25rem',
                borderRadius: '16px',
                cursor: 'pointer',
                border: selectedWorkflow?.id === wf.id ? '2px solid #8b5cf6' : '1px solid var(--border-color)',
                transition: 'border 0.2s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>{wf.name}</h3>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.5rem',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    color: '#a78bfa',
                  }}
                >
                  v{wf.version || 1}
                </span>
              </div>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.35rem', lineHeight: '1.4' }}>
                {wf.description || 'Standard industrial assembly procedure.'}
              </p>

              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                <span>📋 {wf.step_count || wf.steps?.length || 0} Steps</span>
                <span>⏱️ ~{wf.estimated_duration_minutes || 15} mins</span>
              </div>
            </div>
          ))}
        </div>

        {/* Selected Workflow Detailed Steps Inspection */}
        {selectedWorkflow && (
          <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#a78bfa', fontWeight: 700 }}>
                {selectedWorkflow.department_name || 'Assembly Line'}
              </span>
              <h3 style={{ fontSize: '1.4rem', fontWeight: 800, marginTop: '0.2rem' }}>{selectedWorkflow.name}</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                {selectedWorkflow.description}
              </p>
            </div>

            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem' }}>Assembly Step Checklist</h4>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {selectedWorkflow.steps?.map((s: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      padding: '1rem',
                      borderRadius: '12px',
                      backgroundColor: 'rgba(255, 255, 255, 0.03)',
                      borderLeft: s.is_safety_critical ? '4px solid #ef4444' : '4px solid #8b5cf6',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                        Step {s.step_number || idx + 1}: {s.title}
                      </div>
                      {s.is_safety_critical && (
                        <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '10px', backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}>
                          ⚠️ SAFETY CRITICAL
                        </span>
                      )}
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.35rem' }}>
                      {s.instruction}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Define Workflow Modal Dialog */}
      {showCreateModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="wf-modal-title"
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
          <div className="glass-panel" style={{ width: '100%', maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto', padding: '2rem', borderRadius: '24px' }}>
            <h3 id="wf-modal-title" style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '0.5rem' }}>
              ➕ Define Workflow Template
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              Configure a standard industrial procedure with multimodal operator guidance.
            </p>

            <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Workflow Name
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Inverter Sub-Assembly Beta"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  style={{ width: '100%', minHeight: '48px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Description
                </label>
                <textarea
                  className="input-field"
                  placeholder="Describe the assembly sequence and safety requirements..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  style={{ width: '100%', padding: '0.75rem' }}
                />
              </div>

              {/* Dynamic Step Builder */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <label style={{ fontSize: '0.9rem', fontWeight: 700 }}>Step Sequence</label>
                  <button
                    type="button"
                    onClick={handleAddStep}
                    className="btn btn-secondary"
                    style={{ minHeight: '36px', fontSize: '0.8rem', padding: '0 0.75rem' }}
                  >
                    ➕ Add Step
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {steps.map((step, idx) => (
                    <div key={idx} style={{ padding: '0.75rem', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.04)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <input
                          type="text"
                          className="input-field"
                          placeholder={`Step ${idx + 1} Title`}
                          value={step.title}
                          onChange={(e) => {
                            const updated = [...steps];
                            updated[idx].title = e.target.value;
                            setSteps(updated);
                          }}
                          required
                          style={{ flex: 1, minHeight: '40px' }}
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveStep(idx)}
                          disabled={steps.length <= 1}
                          style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '0 0.5rem' }}
                        >
                          ✕
                        </button>
                      </div>

                      <input
                        type="text"
                        className="input-field"
                        placeholder="Operator Instruction Text"
                        value={step.instruction}
                        onChange={(e) => {
                          const updated = [...steps];
                          updated[idx].instruction = e.target.value;
                          setSteps(updated);
                        }}
                        required
                        style={{ width: '100%', minHeight: '40px' }}
                      />

                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={step.is_safety_critical}
                          onChange={(e) => {
                            const updated = [...steps];
                            updated[idx].is_safety_critical = e.target.checked;
                            setSteps(updated);
                          }}
                        />
                        Mark as Safety Critical (Mandatory Confirmation)
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.75rem' }}>
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
                  {isSubmitting ? 'Publishing...' : 'Publish Workflow'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
