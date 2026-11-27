"use client";
import { useEffect } from "react";
import { ApiError } from "@/lib/api";
import { AuthError } from "@/lib/auth";
import { reportError } from "@/lib/report-error";

export function ErrorReporter() {
  useEffect(() => {
    const onError = (e: ErrorEvent) => reportError(e.error ?? e.message);
    const onRejection = (e: PromiseRejectionEvent) => {
      const r = e.reason;
      if (r instanceof ApiError || r instanceof AuthError || (r as { name?: string })?.name === "AbortError") return;
      reportError(e.reason);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);
  return null;
}
