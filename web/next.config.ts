import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Forward the backend URL at build time for SSR fetches
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
