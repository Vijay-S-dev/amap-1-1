'use client';

/**
 * Shared Global Top Navigation
 * Includes product domain routes, organization context, high contrast switch, and live connection status.
 */

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function NavBar() {
  const pathname = usePathname();
  const [highContrast, setHighContrast] = useState(false);

  useEffect(() => {
    if (highContrast) {
      document.body.classList.add('high-contrast');
    } else {
      document.body.classList.remove('high-contrast');
    }
  }, [highContrast]);

  const navLinks = [
    { href: '/', label: 'Overview', badge: 'Hub' },
    { href: '/worker', label: 'Worker Station', badge: 'Multimodal HUD', color: 'var(--worker-cyan)' },
    { href: '/organization', label: 'Organization & Supervisor', badge: 'Fleet', color: 'var(--org-emerald)' },
    { href: '/admin', label: 'Admin & Configs', badge: 'Presets', color: 'var(--admin-purple)' },
  ];

  return (
    <header className="glass-panel" style={{ margin: '1rem 1.5rem', padding: '0.85rem 1.5rem', borderRadius: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        {/* Brand Logo & Invariant Tag */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', textDecoration: 'none' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #00f2fe 0%, #8b5cf6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                color: '#0b0f19',
                fontSize: '1.1rem',
              }}
            >
              A
            </div>
            <div>
              <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'white' }}>AMAP</span>
              <span style={{ display: 'block', fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Adaptive Multimodal Assembly
              </span>
            </div>
          </Link>
          <div className="badge badge-cyan" style={{ marginLeft: '0.5rem', display: 'none', md: 'inline-flex' }}>
            ● System Active (12ms)
          </div>
        </div>

        {/* Product Side Navigation Tabs */}
        <nav aria-label="Main Navigation" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className="btn btn-secondary"
                aria-current={isActive ? 'page' : undefined}
                style={{
                  fontSize: '0.88rem',
                  padding: '0.5rem 1rem',
                  minHeight: '40px',
                  background: isActive ? 'rgba(255, 255, 255, 0.12)' : 'transparent',
                  borderColor: isActive ? 'rgba(255, 255, 255, 0.25)' : 'transparent',
                  color: isActive ? link.color || 'var(--text-primary)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 700 : 500,
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Accessibility & Tenant Tools */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={() => setHighContrast(!highContrast)}
            className="btn btn-secondary"
            aria-pressed={highContrast}
            aria-label="Toggle High Contrast Mode"
            style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', minHeight: '36px' }}
          >
            {highContrast ? '👁️ Standard Contrast' : '🔲 High Contrast'}
          </button>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.35rem 0.75rem',
              background: 'rgba(255, 255, 255, 0.04)',
              borderRadius: '8px',
              fontSize: '0.8rem',
              border: '1px solid var(--surface-glass-border)',
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>Tenant:</span>
            <strong style={{ color: 'var(--text-primary)' }}>Acme Motors Assembly</strong>
          </div>
        </div>
      </div>
    </header>
  );
}
