import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

function checkApiUrl(phase: string) {
  if (phase !== PHASE_PRODUCTION_BUILD || process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_ALLOW_DEMO === "true") return;
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set, so this build would run in browser-only demo mode. " +
      "Set it to https://<your-backend>/api/v1, or set NEXT_PUBLIC_ALLOW_DEMO=true for a demo-only build.",
  );
}

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default function config(phase: string): NextConfig {
  checkApiUrl(phase);
  return nextConfig;
}
