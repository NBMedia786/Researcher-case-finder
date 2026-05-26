/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow cross-origin /_next/* asset requests from the VPS deployment host.
  // Without this, Next.js 14+ dev mode logs a warning per asset request
  // (and in a future major version, will refuse them outright).
  allowedDevOrigins: [
    "69.62.79.231",
    "69.62.79.231.nip.io",
    "*.nip.io",
  ],
};

export default nextConfig;
