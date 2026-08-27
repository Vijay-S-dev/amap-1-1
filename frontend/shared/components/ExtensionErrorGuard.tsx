'use client';

import { useEffect } from 'react';

/**
 * Extension Error Guard
 * Suppresses unhandled promise rejections and errors originating from third-party
 * browser extensions (e.g. MetaMask, wallet injectors, ad-blockers) that interfere
 * with Next.js development error overlays.
 */
export function ExtensionErrorGuard() {
  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const reasonStr = typeof reason === 'string' ? reason : reason?.message || String(reason || '');

      // Suppress MetaMask and browser extension injected script errors
      if (
        reasonStr.includes('MetaMask') ||
        reasonStr.includes('chrome-extension://') ||
        reasonStr.includes('Failed to connect to MetaMask') ||
        reasonStr.includes('ethereum')
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };

    const handleError = (event: ErrorEvent) => {
      const filename = event.filename || '';
      const message = event.message || '';

      if (
        filename.includes('chrome-extension://') ||
        filename.includes('moz-extension://') ||
        message.includes('MetaMask') ||
        message.includes('Failed to connect to MetaMask')
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, []);

  return null;
}
