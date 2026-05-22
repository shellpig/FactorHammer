import { readFileSync } from "fs";
import { resolve } from "path";

const pkg = JSON.parse(readFileSync(resolve(process.cwd(), "package.json"), "utf8")) as { version: string };

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_APP_VERSION: pkg.version,
  },
  devIndicators: {
    position: "top-right" as const,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
