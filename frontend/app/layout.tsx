import type { Metadata } from 'next';
import './globals.css';
import { NavBar } from '@/shared/components/NavBar';

export const metadata: Metadata = {
  title: 'AMAP — Adaptive Multimodal Assembly Platform',
  description:
    'Real-time accessible assembly guidance platform with gesture, voice, and multimodal intent fusion for workers and supervisors.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <main id="main-content" style={{ padding: '0 1.5rem 3rem 1.5rem', maxWidth: '1600px', margin: '0 auto' }}>
          {children}
        </main>
      </body>
    </html>
  );
}
