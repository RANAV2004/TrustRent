"use client";
import { useEffect, useState } from "react";
const EVENT = "trustrent-store";
export function readStore<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const value = JSON.parse(raw);
    if (Array.isArray(fallback) && !Array.isArray(value)) return fallback;
    return value as T;
  } catch {
    return fallback;
  }
}
export class StorageFullError extends Error {}
export function writeStore<T>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    if (e instanceof DOMException && e.name === "QuotaExceededError") {
      throw new StorageFullError("Browser storage is full. Remove some photos or old listings and try again.");
    }
    throw e;
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }));
}
export function useStore<T>(read: () => T, deps: unknown[] = []): T {
  const [value, setValue] = useState<T>(read);
  useEffect(() => {
    const refresh = () => setValue(read());
    refresh();
    window.addEventListener(EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return value;
}
export function uid(prefix: string) {
  return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}
