'use client';

/**
 * AMAP Admin Workflow Builder
 * Visual assembly step editor with multimodal gesture and voice interaction bindings.
 */

import React, { useState } from 'react';

interface StepDraft {
  id: string;
  stepOrder: number;
  title: string;
  instruction: string;
  suggestedGesture: string;
  suggestedVoice: string;
  isSafetyCritical: boolean;
}

const INITIAL_STEPS: StepDraft[] = [
  {
    id: 's_1',
    stepOrder: 1,
    title: 'Optical Component Inspection',
    instruction: 'Verify thermal paste application and capacitor polarity on PCB bed.',
    suggestedGesture: 'thumbs_up',
    suggestedVoice: 'confirm',
    isSafetyCritical: false,
  },
  {
    id: 's_2',
    stepOrder: 2,
    title: 'Primary Busbar Torquing',
    instruction: 'Align copper busbar and torque M6 fasteners to 9.2 Nm in star pattern.',
    suggestedGesture: 'thumbs_up',
    suggestedVoice: 'next step',
    isSafetyCritical: false,
  },
  {
    id: 's_3',
    stepOrder: 3,
    title: 'High Voltage Isolation Check',
    instruction: 'Connect dielectric probe to safety terminal and engage automated 500V test.',
    suggestedGesture: 'pointing',
    suggestedVoice: 'confirm action',
    isSafetyCritical: true,
  },
];

export function WorkflowBuilder() {
  const [steps, setSteps] = useState<StepDraft[]>(INITIAL_STEPS);
  const [newTitle, setNewTitle] = useState('');
  const [newInstruction, setNewInstruction] = useState('');
  const [newGesture, setNewGesture] = useState('thumbs_up');
  const [newVoice, setNewVoice] = useState('confirm');
  const [isCritical, setIsCritical] = useState(false);

  const addStep = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    const newStep: StepDraft = {
      id: `s_${Date.now()}`,
      stepOrder: steps.length + 1,
      title: newTitle.trim(),
      instruction: newInstruction.trim() || `Perform ${newTitle.trim()} step.`,
      suggestedGesture: newGesture,
      suggestedVoice: newVoice,
      isSafetyCritical: isCritical,
    };

    setSteps([...steps, newStep]);
    setNewTitle('');
    setNewInstruction('');
    setIsCritical(false);
  };

  const removeStep = (id: string) => {
    setSteps(steps.filter((s) => s.id !== id).map((s, idx) => ({ ...s, stepOrder: idx + 1 })));
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>🛠️</span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>Workflow & Task Step Builder</h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Design sequential factory assembly tasks and bind multimodal input shortcuts.
          </p>
        </div>

        <span
          style={{
            padding: '0.35rem 0.85rem',
            borderRadius: '999px',
            fontSize: '0.8rem',
            fontWeight: 700,
            background: 'rgba(139, 92, 246, 0.15)',
            color: 'var(--admin-purple)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
          }}
        >
          {steps.length} Steps Defined
        </span>
      </div>

      {/* Step Sequence List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
        {steps.map((step) => (
          <div
            key={step.id}
            className="glass-card"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '1rem 1.25rem',
              borderLeft: step.isSafetyCritical ? '4px solid var(--accent-rose)' : '4px solid var(--worker-cyan)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
              <span
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--surface-card)',
                  fontWeight: 800,
                  fontSize: '0.9rem',
                  color: 'var(--text-primary)',
                }}
              >
                {step.stepOrder}
              </span>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{step.title}</h4>
                  {step.isSafetyCritical && (
                    <span
                      style={{
                        padding: '0.15rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        background: 'rgba(244, 63, 94, 0.2)',
                        color: 'var(--accent-rose)',
                      }}
                    >
                      CRITICAL INTERLOCK
                    </span>
                  )}
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
                  {step.instruction}
                </p>
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem', fontSize: '0.75rem' }}>
                  <span style={{ color: 'var(--worker-cyan)' }}>👋 Gesture: {step.suggestedGesture}</span>
                  <span style={{ color: 'var(--text-muted)' }}>•</span>
                  <span style={{ color: 'var(--org-emerald)' }}>🎙️ Voice: &ldquo;{step.suggestedVoice}&rdquo;</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => removeStep(step.id)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '1.1rem',
                padding: '0.5rem',
              }}
              aria-label="Remove step"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Add Step Form */}
      <form
        onSubmit={addStep}
        style={{
          background: 'var(--surface-card)',
          padding: '1.25rem',
          borderRadius: '12px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          alignItems: 'end',
        }}
      >
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
            STEP TITLE
          </label>
          <input
            type="text"
            className="input-text"
            placeholder="e.g. Fasten Ground Strap"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            required
            style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'var(--bg-secondary)', color: '#fff', border: '1px solid var(--surface-glass-border)' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
            INSTRUCTION
          </label>
          <input
            type="text"
            className="input-text"
            placeholder="e.g. Attach ground wire with 5Nm torque"
            value={newInstruction}
            onChange={(e) => setNewInstruction(e.target.value)}
            style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'var(--bg-secondary)', color: '#fff', border: '1px solid var(--surface-glass-border)' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
            BINDING GESTURE
          </label>
          <select
            value={newGesture}
            onChange={(e) => setNewGesture(e.target.value)}
            style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'var(--bg-secondary)', color: '#fff', border: '1px solid var(--surface-glass-border)' }}
          >
            <option value="thumbs_up">Thumbs Up (Confirm)</option>
            <option value="pointing">Pointing (Focus Target)</option>
            <option value="pinch">Pinch (Select Item)</option>
            <option value="open_palm">Open Palm (Pause)</option>
          </select>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--accent-rose)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={isCritical}
              onChange={(e) => setIsCritical(e.target.checked)}
            />
            Safety Critical?
          </label>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)', flex: 1 }}
          >
            + Add Step
          </button>
        </div>
      </form>
    </div>
  );
}
