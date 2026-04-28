import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to fastapi so client-side fetches stay same-origin (farm.local)
    // and don't require api.farm.local to be in the browser's DNS.
    const backendUrl =
      process.env.INTERNAL_API_URL ?? "http://fastapi:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
