"use client";
import { API_URL, apiMode } from "./api";

const sent = new Set<string>();
const MAX_PER_PAGE = 10;

export function reportError(error: unknown, digest?: string) {
  try {
    if (!apiMode || sent.size >= MAX_PER_PAGE) return;
    const err = error instanceof Error ? error : new Error(String(error));
    const message = `${err.name}: ${err.message}`.slice(0, 500);
    if (sent.has(message)) return;
    sent.add(message);
    const body = JSON.stringify({
      message, digest, url: window.location.origin + window.location.pathname, stack: (err.stack ?? "").slice(0, 4000),
    });
    fetch(`${API_URL}/client-errors`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true })
      .catch(() => {});
  } catch {
  }
}
