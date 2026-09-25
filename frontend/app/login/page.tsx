'use client';

/**
 * Accessible Worker Login Page (/login) (§ 6, § 7, § 12, § 38)
 * Dynamically checks whether worker is a Fresher or Existing Employee:
 * - Fresher (New Hire): Enforces mandatory Onboarding & Training flow.
 * - Existing (Certified Worker): Restores preferences & routes directly to /worker.
 */

import React, { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { api } from '@/shared/api/client';

function LoginForm() {
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get('redirect');

  const {
    language,
    announce,
    playAudioCue,
    setLanguage,
    setModality,
    setHasCompletedLanguage,
    setHasCompletedAccessibility,
    setHasCompletedGestureCalibration,
    setHasCompletedVoiceSetup,
    setHasCompletedTraining,
  } = useAccessibility();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organizationId, setOrganizationId] = useState('9a61e05d-7a32-4112-9c17-1833d7b42f65');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // 1. Fresher Demo (New hire requiring onboarding)
  const fillDemoFresher = () => {
    setEmail('maria.newhire@amap.com');
    setPassword('SecurePassword123!');
    setOrganizationId('9a61e05d-7a32-4112-9c17-1833d7b42f65');
    announce('Demo Fresher credentials filled for Maria Rodriguez (New Hire).');
  };

  // 2. Existing Worker Demo (Certified returning worker)
  const fillDemoExistingWorker = () => {
    setEmail('alex.worker@amap.com');
    setPassword('SecurePassword123!');
    setOrganizationId('9a61e05d-7a32-4112-9c17-1833d7b42f65');
    announce('Demo Existing Worker credentials filled for Alex Morgan (Certified).');
  };

  // 3. Supervisor Demo
  const fillDemoSupervisor = () => {
    setEmail('supervisor@amap.com');
    setPassword('SecurePassword123!');
    setOrganizationId('9a61e05d-7a32-4112-9c17-1833d7b42f65');
    announce('Demo supervisor credentials filled.');
  };

  // 4. Admin Demo
  const fillDemoAdmin = () => {
    setEmail('admin@amap.com');
    setPassword('SecurePassword123!');
    setOrganizationId('9a61e05d-7a32-4112-9c17-1833d7b42f65');
    announce('Demo administrator credentials filled.');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please provide both email and password.');
      announce('Error: Please provide both email and password.');
      playAudioCue('alert');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');

    try {
      // 1. Authenticate with backend API (real authentication, no localhost hardcoding, no fake token)
      const authResult = await api.login({
        organization_id: organizationId,
        email: email.trim(),
        password,
      });

      const accessToken = authResult.access_token;

      // 2. Set auth cookie for edge middleware route gating
      if (typeof document !== 'undefined') {
        document.cookie = `amap_token=${accessToken}; path=/; max-age=86400; SameSite=Lax`;
      }

      playAudioCue('confirm');

      // 3. Obtain authoritative user context from backend /auth/me
      const me = await api.getMe();
      const roles = me.roles || [];

      // 4. Role Dispatch based on authoritative backend roles
      // Use window.location.href to bypass stale Next.js Router Cache prefetch redirects
      if (roles.includes('admin') || roles.includes('organization_admin')) {
        announce('Welcome Administrator. Entering Configuration Studio.');
        const target = (redirectTarget && redirectTarget.startsWith('/admin')) ? redirectTarget : '/admin';
        window.location.href = target;
        return;
      }

      if (roles.includes('supervisor')) {
        announce('Welcome Supervisor. Entering Fleet Operations.');
        const target = (redirectTarget && (redirectTarget.startsWith('/organization') || redirectTarget.startsWith('/organisation'))) ? redirectTarget : '/organization';
        window.location.href = target;
        return;
      }

      // 5. Worker Lifecycle: Fresher vs. Existing Employee based on real worker profile
      const workerProfileId = me.workerProfileId;

      if (workerProfileId) {
        try {
          const readiness = await api.getWorkerReadiness(workerProfileId);

          if (readiness.is_fresher || !readiness.onboarding_completed) {
            // Fresher Flow (§ 12)
            setHasCompletedLanguage(false);
            setHasCompletedAccessibility(false);
            setHasCompletedGestureCalibration(false);
            setHasCompletedVoiceSetup(false);
            setHasCompletedTraining(false);

            announce('Welcome to AMAP! Starting first-time worker onboarding.');
            window.location.href = '/onboarding/language';
            return;
          } else {
            // Existing Employee Flow (§ 38)
            setHasCompletedLanguage(true);
            setHasCompletedAccessibility(true);
            setHasCompletedGestureCalibration(true);
            setHasCompletedVoiceSetup(true);
            setHasCompletedTraining(true);

            if (readiness.active_preferences) {
              if (readiness.active_preferences.language) {
                setLanguage(readiness.active_preferences.language);
              }
              if (readiness.active_preferences.modality) {
                setModality(readiness.active_preferences.modality);
              }
            }

            announce(`Welcome back ${me.fullName || 'Worker'}! Restoring active workstation.`);
            const target = (redirectTarget && (redirectTarget.startsWith('/worker') || redirectTarget.startsWith('/training'))) ? redirectTarget : '/worker';
            window.location.href = target;
            return;
          }
        } catch {
          // If readiness check fails, route to worker safely
        }
      }

      // Default worker routing
      announce('Entering production workstation.');
      const defaultTarget = (redirectTarget && (redirectTarget.startsWith('/worker') || redirectTarget.startsWith('/training'))) ? redirectTarget : '/worker';
      window.location.href = defaultTarget;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed. Please verify credentials.';
      setErrorMessage(msg);
      announce(`Login error: ${msg}`);
      playAudioCue('alert');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '660px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header card */}
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px', textAlign: 'center' }}>
        <span style={{ fontSize: '3.5rem', display: 'block', marginBottom: '0.5rem' }}>🛡️</span>
        <h1 style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          {t('login_title', language)}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
          {t('login_subtitle', language)}
        </p>

        {/* Quick Demo Fill Buttons with Fresher vs Existing (§ 12, § 38) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(135px, 1fr))', gap: '0.5rem', marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={fillDemoFresher}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', padding: '0.6rem 0.5rem', borderRadius: '12px', border: '1px solid var(--worker-cyan)' }}
          >
            🆕 <strong>Fresher</strong> (Maria)
          </button>
          <button
            type="button"
            onClick={fillDemoExistingWorker}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', padding: '0.6rem 0.5rem', borderRadius: '12px', border: '1px solid var(--org-emerald)' }}
          >
            👷 <strong>Existing</strong> (Alex)
          </button>
          <button
            type="button"
            onClick={fillDemoSupervisor}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', padding: '0.6rem 0.5rem', borderRadius: '12px' }}
          >
            🏢 Supervisor
          </button>
          <button
            type="button"
            onClick={fillDemoAdmin}
            className="btn btn-secondary"
            style={{ fontSize: '0.8rem', padding: '0.6rem 0.5rem', borderRadius: '12px' }}
          >
            ⚙️ Admin
          </button>
        </div>

        {/* Login Form */}
        <form onSubmit={handleLogin} style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', textAlign: 'left' }}>
          {errorMessage && (
            <div
              role="alert"
              style={{
                background: 'rgba(244, 63, 94, 0.2)',
                border: '1px solid var(--accent-rose)',
                color: 'var(--accent-rose)',
                padding: '0.85rem 1.25rem',
                borderRadius: '12px',
                fontSize: '0.9rem',
                fontWeight: 600,
              }}
            >
              ⚠️ {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="email-input"
              style={{ display: 'block', fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-primary)' }}
            >
              {t('email_label', language)}
            </label>
            <input
              id="email-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="alex.worker@amap.com or maria.newhire@amap.com"
              style={{
                width: '100%',
                padding: '1rem 1.25rem',
                fontSize: '1.1rem',
                borderRadius: '12px',
                background: 'var(--surface-card)',
                color: '#fff',
                border: '2px solid var(--surface-glass-border)',
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password-input"
              style={{ display: 'block', fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-primary)' }}
            >
              {t('password_label', language)}
            </label>
            <input
              id="password-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••••••"
              style={{
                width: '100%',
                padding: '1rem 1.25rem',
                fontSize: '1.1rem',
                borderRadius: '12px',
                background: 'var(--surface-card)',
                color: '#fff',
                border: '2px solid var(--surface-glass-border)',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn btn-primary"
            style={{
              width: '100%',
              padding: '1.15rem',
              fontSize: '1.15rem',
              fontWeight: 800,
              borderRadius: '14px',
              marginTop: '0.5rem',
              minHeight: '56px',
            }}
          >
            {isLoading ? 'Authenticating & Verifying Profile...' : t('login_button', language)} →
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ padding: '4rem', textAlign: 'center', color: '#fff' }}>Loading AMAP Login...</div>}>
      <LoginForm />
    </Suspense>
  );
}
