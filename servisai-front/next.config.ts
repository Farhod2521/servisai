import type { NextConfig } from "next";

// Brauzer /api/* so‘rovlarini Next.js server orqali FastAPI backendga yo‘naltiramiz (CORS kerak bo‘lmaydi).
// Docker’da build vaqtida BACKEND_URL=http://backend:8000 beriladi.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
