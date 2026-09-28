'use client';

/**
 * Gesture Context Menu (frontend/worker/components/GestureContextMenu.tsx)
 *
 * REAL application right-click affordance for the gesture-driven workstation:
 * opened by the right_click action (two-finger gesture or voice "right click")
 * at the pointer position. Every menu item dispatches the same action
 * resolver used by gestures and voice — no modal-only fakery.
 */

import React, { useEffect, useRef } from 'react';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon: string;
  action: string;
  danger?: boolean;
  disabled?: boolean;
}

interface GestureContextMenuProps {
  open: boolean;
  position: { x: number; y: number } | null;
  actions: ContextMenuAction[];
  onAction: (action: string, displayCommand: string) => void;
  onClose: () => void;
}

export function GestureContextMenu({ open, position, actions, onAction, onClose }: GestureContextMenuProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    // Auto-close when clicking anywhere else (real dismiss behavior)
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    };
    window.setTimeout(() => window.addEventListener('mousedown', handleClick), 0);
    return () => {
      window.removeEventListener('keydown', handleKey);
      window.removeEventListener('mousedown', handleClick);
    };
  }, [open, onClose]);

  if (!open || !position) return null;

  const menuWidth = 280;
  const menuHeight = actions.length * 48 + 16;
  const left = Math.min(Math.max(8, position.x), Math.max(8, window.innerWidth - menuWidth - 8));
  const top = Math.min(Math.max(8, position.y), Math.max(8, window.innerHeight - menuHeight - 8));

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Gesture context menu"
      style={{
        position: 'fixed',
        left,
        top,
        width: menuWidth,
        background: 'rgba(11, 15, 25, 0.97)',
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--surface-glass-border)',
        borderRadius: '14px',
        boxShadow: '0 18px 50px rgba(0,0,0,0.55)',
        padding: '0.5rem',
        zIndex: 100001,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem',
      }}
    >
      <div
        style={{
          fontSize: '0.7rem',
          fontWeight: 800,
          letterSpacing: '0.1em',
          color: 'var(--worker-cyan)',
          padding: '0.35rem 0.6rem 0.5rem',
          textTransform: 'uppercase',
        }}
      >
        ✋ Gesture Context Menu
      </div>
      {actions.map((item) => (
        <button
          key={item.id}
          type="button"
          role="menuitem"
          disabled={item.disabled}
          onClick={() => {
            onAction(item.action, item.label);
            onClose();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            minHeight: '48px',
            padding: '0.5rem 0.75rem',
            borderRadius: '10px',
            background: item.danger ? 'rgba(244, 63, 94, 0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${item.danger ? 'rgba(244,63,94,0.45)' : 'var(--surface-glass-border)'}`,
            color: item.danger ? '#fda4af' : 'var(--text-primary)',
            fontWeight: 700,
            fontSize: '0.9rem',
            cursor: item.disabled ? 'not-allowed' : 'pointer',
            opacity: item.disabled ? 0.45 : 1,
            textAlign: 'left',
            width: '100%',
          }}
        >
          <span style={{ fontSize: '1.1rem' }}>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
}

export default GestureContextMenu;
