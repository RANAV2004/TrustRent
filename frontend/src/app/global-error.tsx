"use client";
import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => { reportError(error, error.digest); }, [error]);
  return (
    <html lang="en-IN">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#f4f6f5", color: "#1b1b1b", margin: 0 }}>
        <main style={{ maxWidth: 420, margin: "20vh auto", padding: "0 16px" }}>
          <h1 style={{ fontSize: 24 }}>Something went wrong</h1>
          <p style={{ color: "#5b6461" }}>TrustRent hit a problem. We&apos;ve been told about it. Your data is safe.</p>
          <button type="button" onClick={() => retry()}
            style={{ background: "#0d5b4c", color: "white", border: 0, borderRadius: 8, padding: "10px 16px", fontSize: 14, cursor: "pointer" }}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
