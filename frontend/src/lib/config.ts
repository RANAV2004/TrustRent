"use client";
import { api, apiMode } from "./api";
export interface ServerConfig {
  demoMode: boolean; payments: "razorpay" | "demo" | "off"; razorpayKeyId: string | null;
  digilocker?: boolean; aadhaarEsign?: boolean; routePayouts?: boolean;
}
let cached: Promise<ServerConfig | null> | null = null;
export function serverConfig(): Promise<ServerConfig | null> {
  if (!apiMode) return Promise.resolve(null);
  cached ??= api<ServerConfig>("/config").catch(() => { cached = null; return null; });
  return cached;
}
