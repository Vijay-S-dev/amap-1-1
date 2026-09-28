'use client';

/**
 * Virtual Pointer Cursor (frontend/worker/components/VirtualCursor.tsx)
 *
 * Renders the gesture-driven application pointer with a state ring so the
 * worker always sees where the pointer is and what the interaction engine is
 * about to do (hover / armed / dragging / paused / emergency-locked).
 */

import React from 'react';
import { InteractionState } from '@/worker/lib/gestureEngine';

interface VirtualCursorProps {
  position: { x: number; y: number } | null;
  state: InteractionState;
  visible: boolean;
}

const STATE_COLORS: Record<InteractionState, string> = {
  IDLE: 'rgba(148, 163, 184, 0.85)',
  HOVER: '#00f2fe',
  ARMED: '#f59e0b',
  TRIGGERED: '#10b981',
  HELD: '#f59e0b',
  DRAGGING: '#a855f7',
  RELEASED: '#10b981',
  PAUSED: '#f59e0b',
  EMERGENCY_STOPPED: '#f43f5e',
};

const STATE_LABELS: Record<InteractionState, string> = {
  IDLE: 'IDLE',
  HOVER: 'POINTER',
  ARMED: 'ARMED',
  TRIGGERED: 'ACTION',
  HELD: 'HELD',
  DRAGGING: 'DRAGGING',
  RELEASED: 'RELEASED',
  PAUSED: 'PAUSED',
  EMERGENCY_STOPPED: 'E-STOP',
};

export function VirtualCursor({ position, state, visible }: VirtualCursorProps) {
  if (!visible || !position) return null;

  const color = STATE_COLORS[state] || STATE_COLORS.HOVER;
  const isStop = state === 'EMERGENCY_STOPPED';

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        width: 0,
        height: 0,
        zIndex: 100000,
        pointerEvents: 'none',
        transform: 'translate(-2px, -2px)',
      }}
    >
      {/* Pointer arrow */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: 0,
          height: 0,
          borderLeft: `14px solid ${color}`,
          borderBottom: '14px solid transparent',
          filter: `drop-shadow(0 0 6px ${color})`,
          transform: isStop ? 'scale(1.35)' : 'scale(1)',
        }}
      />
      {/* State ring */}
      <div
        style={{
          position: 'absolute',
          left: -18,
          top: -18,
          width: 36,
          height: 36,
          borderRadius: '50%',
          border: `2px solid ${color}`,
          boxShadow: `0 0 12px ${color}`,
          opacity: state === 'HOVER' ? 0.35 : 0.9,
          animation: state === 'DRAGGING' ? 'amap-pulse 1s infinite' : undefined,
        }}
      />
      {/* State label */}
      <span
        style={{
          position: 'absolute',
          left: 18,
          top: 12,
          background: 'rgba(9, 13, 22, 0.9)',
          color,
          fontFamily: 'monospace',
          fontSize: '10px',
          fontWeight: 700,
          padding: '2px 6px',
          borderRadius: '6px',
          border: `1px solid ${color}`,
          whiteSpace: 'nowrap',
        }}
      >
        {STATE_LABELS[state] || state}
      </span>
    </div>
  );
}

export default VirtualCursor;
