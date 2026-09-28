'use client';

/**
 * Assembly Drag Bench (frontend/worker/components/AssemblyDragBench.tsx)
 *
 * A REAL drag-and-drop task interaction surface: each workflow step exposes a
 * component that the worker drags into the assembly zone using the virtual
 * gesture pointer (pinch-drag), voice-initiated drag, or an actual mouse.
 *
 * Drops dispatch through the same real event pipeline:
 *   gesture pinch-drag  -> uiActionExecutor.dragStart/Move/End -> amapdrop
 *   voice "move this"   -> engine.beginExternalDrag + pinch/drop   -> amapdrop
 *   mouse               -> native HTML5 drag events               -> onDrop
 * All paths converge on `onPartInstalled`, which the workstation records in
 * the step's execution data (persisted via the workflow step execution API).
 */

import React, { useEffect, useRef, useState } from 'react';

interface AssemblyDragBenchProps {
  /** Unique part identifier for the current step (e.g. spatialTargetId). */
  partId: string;
  partLabel: string;
  zoneLabel?: string;
  installed: boolean;
  onPartInstalled: (partId: string, via: string) => void;
}

export function AssemblyDragBench({
  partId,
  partLabel,
  zoneLabel = 'Assembly Zone',
  installed,
  onPartInstalled,
}: AssemblyDragBenchProps) {
  const zoneRef = useRef<HTMLDivElement | null>(null);
  const [dropHover, setDropHover] = useState(false);

  // Consume gesture-driven drops (custom 'amapdrop' event from the executor)
  useEffect(() => {
    const zone = zoneRef.current;
    if (!zone) return;
    const handleAmapDrop = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      onPartInstalled(partId, detail.source === 'voice' ? 'voice-drag' : 'gesture-drag');
    };
    const handleHover = () => setDropHover(true);
    const handleHoverEnd = () => setDropHover(false);
    zone.addEventListener('amapdrop', handleAmapDrop as EventListener);
    zone.addEventListener('amapdrophover', handleHover as EventListener);
    zone.addEventListener('amapdropleave', handleHoverEnd as EventListener);
    return () => {
      zone.removeEventListener('amapdrop', handleAmapDrop as EventListener);
      zone.removeEventListener('amapdrophover', handleHover as EventListener);
      zone.removeEventListener('amapdropleave', handleHoverEnd as EventListener);
    };
  }, [partId, onPartInstalled]);

  // Native mouse drag support (HTML5) so the same surface works with a mouse
  const [mouseHover, setMouseHover] = useState(false);

  return (
    <div
      style={{
        display: 'flex',
        gap: '1rem',
        alignItems: 'stretch',
        flexWrap: 'wrap',
        marginTop: '1rem',
      }}
      data-amap-bench="true"
    >
      {/* Draggable component chip */}
      <div
        data-amap-draggable="true"
        data-amap-action-id={`part-${partId}`}
        draggable={installed ? false : true}
        onDragStart={(e) => {
          e.dataTransfer.setData('text/amap-part', partId);
          e.dataTransfer.effectAllowed = 'move';
        }}
        aria-label={`Assembly component: ${partLabel}. Pinch and move to drag into the assembly zone.`}
        role="button"
        tabIndex={0}
        style={{
          flex: '1 1 200px',
          minHeight: '84px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.3rem',
          borderRadius: '12px',
          border: `2px dashed ${installed ? 'var(--org-emerald)' : 'var(--worker-cyan)'}`,
          background: installed ? 'rgba(16, 185, 129, 0.12)' : 'rgba(0, 242, 254, 0.07)',
          padding: '0.75rem',
          cursor: installed ? 'default' : 'grab',
          opacity: installed ? 0.75 : 1,
          transition: 'background 0.2s ease, border-color 0.2s ease',
        }}
      >
        <span style={{ fontSize: '1.6rem' }}>{installed ? '✅' : '🔧'}</span>
        <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{partLabel}</strong>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {installed ? 'Installed' : 'Pinch-drag or say "move this"'}
        </span>
      </div>

      {/* Drop zone */}
      <div
        ref={zoneRef}
        data-amap-drop-zone="true"
        data-amap-zone-id={`zone-${partId}`}
        onDragOver={(e) => {
          if (installed) return;
          e.preventDefault();
          setMouseHover(true);
        }}
        onDragLeave={() => setMouseHover(false)}
        onDrop={(e) => {
          e.preventDefault();
          setMouseHover(false);
          const id = e.dataTransfer.getData('text/amap-part');
          if (id && !installed) onPartInstalled(id, 'mouse-drag');
        }}
        aria-label={`${zoneLabel}: drop ${partLabel} here`}
        style={{
          flex: '1.4 1 240px',
          minHeight: '84px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.3rem',
          borderRadius: '12px',
          border: `2px solid ${dropHover || mouseHover ? 'var(--org-emerald)' : 'var(--surface-glass-border)'}`,
          background: dropHover || mouseHover ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255,255,255,0.03)',
          padding: '0.75rem',
          transition: 'background 0.15s ease, border-color 0.15s ease',
        }}
      >
        <span style={{ fontSize: '1.6rem' }}>{dropHover || mouseHover ? '📥' : '⬜'}</span>
        <strong style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{zoneLabel}</strong>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {installed ? `✓ ${partLabel} mounted` : 'Drop the component here'}
        </span>
      </div>
    </div>
  );
}

export default AssemblyDragBench;
