/** @type {import('next').NextConfig} */

// Backend origin for the same-origin API proxy below. In Docker/production the
// frontend typically sets NEXT_PUBLIC_API_BASE_URL to the backend directly and
// this rewrite is simply unused; for local dev and hosted previews it lets the
// browser call a relative /api/v1/* (no CORS, no localhost-from-browser issue).
const backendOrigin = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000';

const nextConfig = {
  reactStrictMode: true,
  // Required by deployment/docker/Dockerfile.frontend (standalone server bundle).
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
