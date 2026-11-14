import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const api = (() => {
  try {
    return process.env.NEXT_PUBLIC_API_URL ? new URL(process.env.NEXT_PUBLIC_API_URL).origin : "";
  } catch {
    return "";
  }
})();

// Only Google sign-in and Razorpay checkout may load outside code. Photos can come from the API or a public bucket.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://accounts.google.com https://checkout.razorpay.com`,
  "style-src 'self' 'unsafe-inline' https://accounts.google.com",
  `img-src 'self' blob: data: https: ${api}` + (isDev ? " http:" : ""),
  "font-src 'self' data:",
  `connect-src 'self' ${api} https://accounts.google.com https://api.razorpay.com https://lumberjack.razorpay.com${isDev ? " http://localhost:* ws://localhost:*" : ""}`,
  "frame-src https://accounts.google.com https://api.razorpay.com https://checkout.razorpay.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(!isDev && api.startsWith("https://") ? ["upgrade-insecure-requests"] : []),
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(self)" },
          ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
        ],
      },
    ];
  },
};

export default nextConfig;
