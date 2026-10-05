import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a self-contained server in .next/standalone so the Docker image
  // does not need node_modules.
  output: "standalone",
};

export default nextConfig;
