import type { Metadata } from 'next';
import './globals.css';
import { NavBar } from '@/shared/components/NavBar';
import { AccessibilityProvider } from '@/shared/theme/AccessibilityContext';
import { ExtensionErrorGuard } from '@/shared/components/ExtensionErrorGuard';

export const metadata: Metadata = {
  title: 'AMAP — Adaptive Multimodal Assembly Platform',
  description:
    'Real-time accessible assembly guidance platform with gesture, voice, and multimodal intent fusion for workers and supervisors.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <html lang="en">
      <body>
        <ExtensionErrorGuard />
        <AccessibilityProvider>
          <NavBar />
          <main id="main-content" style={{ padding: '0 1.5rem 3rem 1.5rem', maxWidth: '1600px', margin: '0 auto' }}>
            {children}
          </main>
        </AccessibilityProvider>
      </body>
    </html>
  );
}
