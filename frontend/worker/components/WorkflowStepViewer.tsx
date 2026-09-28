'use client';

/**
 * Worker Workflow Step Viewer Component
 * Renders assembly instructions, visual guidance, step timeline, and direct accessible execution controls.
 * Includes real-time completion state (persisted via the workflow step execution API).
 */

import React from 'react';
import { WorkflowStep } from '@/shared/types';

interface WorkflowStepViewerProps {
  currentStep: WorkflowStep;
  totalSteps: number;
  currentStepIndex: number;
  completedStepIds?: Set<string>;
  onNextStep: () => void;
  onPreviousStep: () => void;
  onCompleteStep?: () => void;
  onRequestAssistance: () => void;
  onEmergencyStop: () => void;
  children?: React.ReactNode;
}

export function WorkflowStepViewer({
  currentStep,
  totalSteps,
  currentStepIndex,
  completedStepIds = new Set(),
  onNextStep,
  onPreviousStep,
  onCompleteStep,
  onRequestAssistance,
  onEmergencyStop,
  children,
}: WorkflowStepViewerProps) {
  const isCurrentStepCompleted = completedStepIds.has(currentStep.id);

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
            {isCurrentStepCompleted && (
              <span className="badge badge-emerald" style={{ marginLeft: '0.75rem', fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}>
                ✓ Completed
              </span>
            )}
          </h1>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span className="badge badge-cyan" style={{ fontSize: '0.85rem', padding: '0.35rem 0.85rem' }}>
            Target: {currentStep.spatialTargetId || 'Standard Workzone'}
          </span>
        </div>
      </div>

      {/* Step Timeline (real persisted completion state) */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.25rem', flexWrap: 'wrap' }} aria-hidden="true">
        {Array.from({ length: totalSteps }).map((_, idx) => {
          const done = idx < currentStepIndex;
          const isCurrent = idx === currentStepIndex;
          return (
            <div
              key={idx}
              style={{
                flex: '1 1 40px',
                height: '8px',
                borderRadius: '4px',
                background: done
                  ? 'var(--org-emerald)'
                  : isCurrent
                  ? 'linear-gradient(90deg, var(--worker-cyan), var(--org-emerald))'
                  : 'rgba(255,255,255,0.1)',
                opacity: done || isCurrent ? 1 : 0.6,
              }}
            />
          );
        })}
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

        {/* Gesture Interaction Hint */}
        <div
          style={{
            marginTop: '1rem',
            padding: '0.65rem 1rem',
            background: 'rgba(0, 242, 254, 0.06)',
            border: '1px solid rgba(0, 242, 254, 0.25)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            fontSize: '0.9rem',
            color: 'var(--text-primary)',
            flexWrap: 'wrap',
          }}
        >
          <span>💡</span>
          <span>
            <strong>Input Hint:</strong> Point 👉 to move the pointer • Pinch 🤏 to click • Two fingers ✌️ for
            right-click/scroll • Swipe right ➡️ for next step • Say &quot;Next&quot; / &quot;Confirm&quot;.
          </span>
        </div>

        {/* Real drag & drop assembly bench (passed by the workstation) */}
        {children}
      </div>

      {/* Accessible Action Control Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={onPreviousStep}
            disabled={currentStepIndex === 0}
            className="btn btn-secondary"
            style={{ minHeight: '48px', opacity: currentStepIndex === 0 ? 0.5 : 1 }}
          >
            ← Previous Step
          </button>
          {onCompleteStep && (
            <button
              type="button"
              onClick={onCompleteStep}
              disabled={isCurrentStepCompleted}
              className="btn btn-secondary"
              style={{ minHeight: '48px', opacity: isCurrentStepCompleted ? 0.5 : 1, borderColor: 'rgba(16, 185, 129, 0.5)', color: 'var(--org-emerald)' }}
              data-amap-action-id="complete-step"
            >
              ✓ Complete Step
            </button>
          )}
          <button
            type="button"
            onClick={onNextStep}
            className="btn btn-primary"
            style={{ minHeight: '48px', fontWeight: 700 }}
            data-amap-action-id="next-step"
          >
            Confirm &amp; Next Step →
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={onRequestAssistance}
            className="btn btn-secondary"
            style={{ minHeight: '48px', borderColor: 'rgba(245, 158, 11, 0.4)', color: 'var(--accent-amber)' }}
            data-amap-action-id="request-assistance"
          >
            🙋 Request Assistance
          </button>
          <button
            type="button"
            onClick={onEmergencyStop}
            className="btn btn-danger"
            style={{ minHeight: '48px', minWidth: '160px', fontWeight: 800 }}
            data-amap-action-id="emergency-stop"
          >
            🛑 Emergency Stop
          </button>
        </div>
      </div>
    </div>
  );
}

export default WorkflowStepViewer;
