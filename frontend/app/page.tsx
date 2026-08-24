'use client';

/**
 * AMAP Main Landing & Launchpad Hub (/)
 * Portal entrance with live architectural invariant status, system telemetry, and quick launchers.
 */

import React from 'react';
import Link from 'next/link';

export default function HomePage() {
  const portals = [
    {
      title: 'Worker Assembly Station',
      href: '/worker',
      badge: 'Multimodal HUD',
      color: 'var(--worker-cyan)',
      icon: '🖐️',
      description:
        'Live step-by-step guidance workstation with optical hand gesture tracking, acoustic voice commands, and spatial target binding.',
      actionText: 'Launch Workstation →',
    },
    {
      title: 'Supervisor & Organization Fleet',
      href: '/organization',
      badge: 'Live Telemetry',
      color: 'var(--org-emerald)',
      icon: '🏢',
      description:
        'Real-time fleet monitoring across active workstations, pending assistance request queue, and departmental metrics.',
      actionText: 'Open Fleet Monitor →',
    },
    {
      title: 'Admin & Interaction Studio',
      href: '/admin',
      badge: 'System Governance',
      color: 'var(--admin-purple)',
      icon: '⚙️',
      description:
        'Interaction presets studio, multi-signal evidence adaptation approvals, capability profiles, and immutable audit logs.',
      actionText: 'Enter Admin Studio →',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Hero Welcome Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '3rem 2.5rem',
          borderRadius: '24px',
          background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.85) 0%, rgba(11, 15, 25, 0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: '800px' }}>
          <span className="badge badge-cyan" style={{ marginBottom: '1rem' }}>
            Adaptive Multimodal Assembly Platform (AMAP)
          </span>
          <h1 style={{ fontSize: '2.75rem', fontWeight: 800, lineHeight: '1.2', letterSpacing: '-0.03em', color: 'white' }}>
            Accessible Real-Time Industrial Assembly Guidance
          </h1>
          <p style={{ fontSize: '1.15rem', color: 'var(--text-secondary)', marginTop: '1rem', lineHeight: '1.6' }}>
            Empowering factory workers with adaptive gesture and voice intent recognition, evidence-based difficulty tuning,
            and safety-critical deterministic execution.
          </p>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '1.75rem', flexWrap: 'wrap' }}>
            <Link href="/worker" className="btn btn-primary" style={{ padding: '0.85rem 1.75rem' }}>
              Launch Worker Workstation
            </Link>
            <Link href="/organization" className="btn btn-secondary" style={{ padding: '0.85rem 1.75rem' }}>
              View Fleet Operations
            </Link>
          </div>
        </div>
      </div>

      {/* Safety Invariant Core Callout */}
      <div className="invariant-banner" style={{ padding: '1.25rem 2rem', borderRadius: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '1.5rem' }}>🛡️</span>
          <div>
            <strong style={{ color: 'white', display: 'block', fontSize: '0.95rem' }}>
              Core Deterministic Safety Invariant
            </strong>
            <code style={{ color: 'var(--worker-cyan)', fontSize: '0.95rem' }}>
              Recognition ≠ Intent ≠ Authorization ≠ Execution
            </code>
          </div>
        </div>
        <span className="badge badge-emerald">Enforced by Backend Services</span>
      </div>

      {/* Product Portal Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {portals.map((portal) => (
          <div
            key={portal.href}
            className="glass-panel"
            style={{
              padding: '2rem',
              borderRadius: '20px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'transform 0.2s ease, border-color 0.2s ease',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <span style={{ fontSize: '2.5rem' }}>{portal.icon}</span>
                <span
                  className="badge"
                  style={{
                    color: portal.color,
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: `1px solid ${portal.color}`,
                  }}
                >
                  {portal.badge}
                </span>
              </div>

              <h2 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: '0.5rem', color: 'white' }}>
                {portal.title}
              </h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '1.5rem' }}>
                {portal.description}
              </p>
            </div>

            <Link
              href={portal.href}
              className="btn btn-secondary"
              style={{
                width: '100%',
                justifyContent: 'center',
                borderColor: 'rgba(255, 255, 255, 0.15)',
                color: portal.color,
                fontWeight: 700,
              }}
            >
              {portal.actionText}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
