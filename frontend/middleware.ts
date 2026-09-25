import { NextResponse, type NextRequest } from 'next/server';

/**
 * AMAP Edge Route Protection Middleware (§ 7, § 50)
 *
 * Provides client-side route gating via structural JWT checks and expiration validation.
 * IMPORTANT SECURITY BOUNDARY NOTE:
 * This edge middleware performs structural and expiry gating only to prevent unauthenticated
 * UI rendering. It does NOT perform cryptographic HMAC signature verification (to avoid
 * exposing secrets to the edge/frontend runtime).
 * The FastAPI backend remains the authoritative cryptographic security boundary enforcing
 * signature verification, active user status, and RBAC authorization on every API request.
 */

const PROTECTED_PREFIXES = [
  '/worker',
  '/organization',
  '/organisation',
  '/admin',
  '/onboarding',
  '/training',
];

function isTokenStructurallyValidAndUnexpired(token: string): boolean {
  if (!token || typeof token !== 'string') return false;

  // Reject fake demo tokens
  if (token.startsWith('demo_token_') || token.startsWith('demo_token')) return false;

  // JWT must contain exactly 3 dot-separated base64url segments (header.payload.signature)
  const parts = token.split('.');
  if (parts.length !== 3) return false;

  try {
    // Decode payload segment (base64url → base64 with proper padding)
    let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) base64 += '=';
    const jsonPayload = atob(base64);
    const payload = JSON.parse(jsonPayload);

    // Check expiration claim (exp in seconds)
    if (payload.exp && typeof payload.exp === 'number') {
      const currentTimeSeconds = Math.floor(Date.now() / 1000);
      if (currentTimeSeconds >= payload.exp) {
        return false; // Token expired
      }
    }

    return true;
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (isProtected) {
    let rawToken = request.cookies.get('amap_token')?.value;

    // Strip enclosing quotes that some cookie parsers may include
    if (rawToken && rawToken.startsWith('"') && rawToken.endsWith('"')) {
      rawToken = rawToken.slice(1, -1);
    }

    if (!rawToken) {
      const authHeader = request.headers.get('authorization');
      if (authHeader && authHeader.startsWith('Bearer ')) {
        rawToken = authHeader.substring(7).trim();
      }
    }

    // Reject missing, fake, expired, or malformed tokens (no x-amap-authenticated bypass)
    if (!rawToken || !isTokenStructurallyValidAndUnexpired(rawToken)) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/worker/:path*',
    '/organization/:path*',
    '/organisation/:path*',
    '/admin/:path*',
    '/onboarding/:path*',
    '/training/:path*',
  ],
};
