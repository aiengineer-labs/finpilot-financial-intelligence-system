import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    // An advisor run makes up to four sequential Mesh calls, each capped at 60 s by the API;
    // the 30 s default dropped slower runs that the API still completed and persisted.
    proxyTimeout: 240_000
  },
  async rewrites() {
    const api = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
    return [
      { source: "/api/v1/:path*", destination: `${api}/api/v1/:path*` },
      { source: "/api-health", destination: `${api}/health` }
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" }
        ]
      }
    ];
  }
};

export default nextConfig;
