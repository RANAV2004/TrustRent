"use client";
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const apiMode = API_URL !== "";
const TOKEN_KEY = "trustrent-token";
export class ApiError extends Error {
  constructor(message: string, public status: number, public field?: string) {
    super(message);
  }
}
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
  }
}
function errorFrom(data: unknown, status: number): ApiError {
  const detail = (data as { detail?: unknown })?.detail;
  if (typeof detail === "string") return new ApiError(detail, status);
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; field?: string | null };
    return new ApiError(d.message, status, d.field ?? undefined);
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    const loc = detail[0].loc as string[] | undefined;
    return new ApiError(String(detail[0].msg), status, loc?.at(-1));
  }
  if (status === 401 || status === 403) return new ApiError("Please sign in again.", status);
  return new ApiError("Something went wrong. Try again.", status);
}
interface CallOptions {
  method?: string;
  json?: unknown;
  form?: FormData;
}
export async function api<T>(path: string, { method, json, form }: CallOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(API_URL + path, {
      method: method ?? (json !== undefined || form ? "POST" : "GET"),
      headers,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
    });
  } catch {
    throw new ApiError(`Can't reach the TrustRent server at ${API_URL}. Is the backend running?`, 0);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw errorFrom(data, res.status);
  return data as T;
}
export function dataUrlToBlob(dataUrl: string): Blob {
  const [head, b64] = dataUrl.split(",");
  const mime = head.match(/data:([^;]+)/)?.[1] ?? "image/jpeg";
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}
