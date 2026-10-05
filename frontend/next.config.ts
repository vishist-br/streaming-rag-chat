import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Dockerfile sets NEXT_OUTPUT=standalone to emit a self-contained server
  // (no node_modules in the image). Locally, `npm run start` keeps working.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
};

export default nextConfig;
