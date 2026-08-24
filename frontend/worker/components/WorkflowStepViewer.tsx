'use client';

/**
 * Worker Workflow Step Viewer Component
 * Renders assembly instructions, visual guidance, step timeline, and direct accessible execution controls.
 */

import React from 'react';
import { WorkflowStep } from '@/shared/types';

interface WorkflowStepViewerProps {
  currentStep: WorkflowStep;
  totalSteps: number;
  currentStepIndex: number;
  onNextStep: () => void;
  onPreviousStep: () => void;
  onRequestAssistance: () => void;
  onEmergencyStop: () => void;
}

export function WorkflowStepViewer({
  currentStep,
  totalSteps,
  currentStepIndex,
  onNextStep,
  onPreviousStep,
  onRequestAssistance,
  onEmergencyStop,
}: WorkflowStepViewerProps) {
  return (
    <div className="glass-panel" style={{ padding: '2rem', borderRadius: '20px' }}>
      {/* Step Header & Progress */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--worker-cyan)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Assembly Workflow
          </span>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.25rem' }}>
            Step {currentStep.stepNumber} of {totalSteps}: {currentStep.title}
          </h1>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span className="badge badge-cyan" style={{ fontSize: '0.85rem', padding: '0.35rem 0.85rem' }}>
            Target: {currentStep.spatialTargetId || 'Standard Workzone'}
          </span>
        </div>
      </div>

      {/* Main Instruction Display Card */}
      <div
        className="glass-card"
        style={{
          padding: '2rem',
          background: 'linear-gradient(135deg, rgba(31, 41, 55, 0.9) 0%, rgba(17, 24, 39, 0.9) 100%)',
          border: '1px solid rgba(0, 242, 254, 0.2)',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'rgba(0, 242, 254, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              color: 'var(--worker-cyan)',
              flexShrink: 0,
            }}
          >
            📋
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem', color: 'white' }}>
              Instruction Guidance
            </h2>
            <p style={{ fontSize: '1.1rem', lineHeight: '1.6', color: 'var(--text-primary)' }}>
              {currentStep.instructionText}
            </p>
          </div>
        </div>

        {/* Spatial Target Callout */}
        {currentStep.spatialTargetId && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.75rem 1rem',
              background: 'rgba(0, 242, 254, 0.08)',
              border: '1px solid rgba(0, 242, 254, 0.3)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              fontSize: '0.9rem',
            }}
          >
            <span>🎯</span>
            <span>
              Spatial Focus Area: <strong>{currentStep.spatialTargetId}</strong> — Align parts within optical target boundary.
            </span>
          </div>
        )}
      </div>

      {/* Accessible Action Control Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={onPreviousStep}
            disabled={currentStepIndex === 0}
            className="btn btn-secondary"
            style={{ opacity: currentStepIndex === 0 ? 0.5 : 1 }}
          >
            ← Previous Step
          </button>
          <button
            type="button"
            onClick={onNextStep}
            className="btn btn-primary"
          >
            Confirm & Next Step →
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={onRequestAssistance}
            className="btn btn-secondary"
            style={{ borderColor: 'rgba(245, 158, 11, 0.4)', color: 'var(--accent-amber)' }}
          >
            🙋 Request Assistance
          </button>
          <button
            type="button"
            onClick={onEmergencyStop}
            className="btn btn-danger"
          >
            🛑 Emergency Stop
          </button>
        </div>
      </div>
    </div>
  );
}
