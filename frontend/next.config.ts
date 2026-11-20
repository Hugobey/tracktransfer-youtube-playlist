import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    const backend = process.env.TRACKTRANSFER_API_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
