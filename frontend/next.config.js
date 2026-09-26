/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required by deployment/docker/Dockerfile.frontend (standalone server bundle).
  output: 'standalone',
};

module.exports = nextConfig;
