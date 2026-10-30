"use client";
import { useEffect } from "react";
import { api, apiMode } from "./api";
import { writeStore } from "./local-store";
export const KEYS = {
  listings: "trustrent-api-listings",
  myListings: "trustrent-api-my-listings",
  application: "trustrent-api-application",
  conversations: "trustrent-api-conversations",
  messages: "trustrent-api-messages",
  ready: "trustrent-api-ready",
} as const;
export function apiReady(): boolean {
  if (!apiMode) return true;
  try {
    return localStorage.getItem(KEYS.ready) === "true";
  } catch {
    return true;
  }
}
export async function refreshListings() {
  writeStore(KEYS.listings, await api<unknown[]>("/listings"));
  writeStore(KEYS.ready, true);
}
export async function refreshOwner() {
  const [mine, app] = await Promise.all([
    api<unknown[]>("/owner/listings"),
    api<{ application: unknown }>("/owner/application"),
  ]);
  writeStore(KEYS.myListings, mine);
  writeStore(KEYS.application, app.application);
}
let acceptedVisits: string | null = null;
export async function refreshInbox() {
  const box = await api<{ conversations: unknown[]; messages: { id: string; visit?: { status: string } }[] }>("/inbox");
  writeStore(KEYS.messages, box.messages);
  writeStore(KEYS.conversations, box.conversations);
  const accepted = box.messages.filter((m) => m.visit?.status === "accepted").map((m) => m.id).join(",");
  if (accepted !== acceptedVisits) {
    const first = acceptedVisits === null;
    acceptedVisits = accepted;
    if (!first) await refreshListings();
  }
}
export function clearApiCache() {
  if (!apiMode) return;
  try {
    Object.values(KEYS).forEach((k) => localStorage.removeItem(k));
    acceptedVisits = null;
  } catch {
  }
}
const quiet = (p: Promise<unknown>) => p.catch(() => {});
export function ApiSync({ userId }: { userId: string }) {
  useEffect(() => {
    if (!apiMode) return;
    quiet(refreshListings());
    quiet(refreshOwner());
    quiet(refreshInbox());
    const tick = (fn: () => Promise<unknown>, ms: number) =>
      window.setInterval(() => {
        if (document.visibilityState === "visible") quiet(fn());
      }, ms);
    const a = tick(refreshInbox, 4000);
    const b = tick(refreshListings, 30000);
    return () => {
      window.clearInterval(a);
      window.clearInterval(b);
    };
  }, [userId]);
  return null;
}
