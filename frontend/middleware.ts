import { NextResponse, type NextRequest } from 'next/server';

/**
 * AMAP Edge Route Protection Middleware (§ 7, § 50)
 * Intercepts requests to protected worker, supervisor, and admin pages.
 * Redirects unauthenticated sessions directly to /login.
 */

const PROTECTED_PREFIXES = [
  '/worker',
  '/organization',
  '/organisation',
  '/admin',
  '/onboarding',
  '/training',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check if target route is within protected prefixes
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (isProtected) {
    // Check for bearer token or auth cookie
    const token = request.cookies.get('amap_token')?.value || request.headers.get('authorization');
    
    // In Next.js client environment, also check cookie header
    if (!token && !request.headers.get('x-amap-authenticated')) {
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
