/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // SSE passes through the /api/v1 proxy route (app/api/v1/[...path]/route.ts); gzip would buffer it.
  compress: false,
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
