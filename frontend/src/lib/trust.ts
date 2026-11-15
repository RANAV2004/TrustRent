"use client";
import { api, API_URL, ApiError, getToken } from "./api";
import type { User } from "./auth";
import type { AgreementView } from "./deposits";

// Opens an authenticated HTML/PDF document from the API in a new tab.
export async function openDocument(path: string) {
  const token = getToken();
  const tab = window.open("", "_blank");
  const res = await fetch(API_URL + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    tab?.close();
    throw new ApiError(res.status === 404 ? "That document isn't available yet." : "Couldn't open the document.", res.status);
  }
  const url = URL.createObjectURL(await res.blob());
  if (tab) tab.location.href = url;
  else window.location.href = url;
}

// rent
export interface RentInvoice {
  id: string; period: string; amount: number; dueDate: string; status: "due" | "overdue" | "paid" | "cancelled";
  method: "online" | "offline" | null; paidAt: string | null; receiptNo: string | null; payout: string | null; payable: boolean;
}
export interface RentSchedule { invoices: RentInvoice[]; role: "tenant" | "owner" | "admin"; paidTotal: number; financialYears: number[] }
export const rentSchedule = (depositId: string) => api<RentSchedule>(`/deposits/${depositId}/rent`);
export const markRentPaid = (id: string, method: string, reference: string) => api<RentInvoice>(`/rent/${id}/mark-paid`, { json: { method, reference } });

// reviews
export interface ReviewItem { id: string; rating: number; text: string | null; createdAt: string; author: string; depositId: string; direction: string }
export interface ReviewState { canReview: boolean; reviewBy: string | null; about: string; mine: ReviewItem | null; theirs: ReviewItem | null; theirsWaiting: boolean }
export const reviewState = (depositId: string) => api<ReviewState>(`/deposits/${depositId}/review`);
export const leaveReview = (depositId: string, rating: number, text: string) => api<ReviewState>(`/deposits/${depositId}/review`, { json: { rating, text } });
export const userReviews = (userId: string) => api<{ summary: { avg: number | null; count: number }; reviews: ReviewItem[] }>(`/users/${userId}/reviews`);

// checklist
export interface Checklist {
  rooms: { name: string; tip: string }[];
  side: "tenant" | "owner" | null;
  open: Record<"move_in" | "move_out", boolean>;
  stages: Record<"move_in" | "move_out", Record<"tenant" | "owner", { done?: string[]; missing?: string[]; completedAt: string | null; rooms?: number }>>;
}
export const getChecklist = (depositId: string) => api<Checklist>(`/deposits/${depositId}/checklist`);
export const completeChecklist = (depositId: string, stage: string) => api<Checklist>(`/deposits/${depositId}/checklist/${stage}/complete`, { method: "POST" });

// payouts
export interface PayoutAccount { holderName: string; ifsc: string; accountLast4: string; panLast4: string; status: "submitted" | "active" | "rejected"; note: string | null; linked: boolean; linkedAccountId?: string | null }
export const myPayout = () => api<{ account: PayoutAccount | null; routeEnabled: boolean }>("/owner/payout-account");
export const savePayout = (body: { holderName: string; ifsc: string; accountNumber: string; pan: string }) =>
  api<{ account: PayoutAccount; routeEnabled: boolean }>("/owner/payout-account", { method: "PUT", json: body });
export interface PayoutDue { kind: "deposit" | "rent"; id: string; amount: number; depositId: string; period?: string; owner: { id: string; name: string; account: PayoutAccount | null } }
export const adminPayouts = () => api<{ routeEnabled: boolean; due: PayoutDue[]; accounts: (PayoutAccount & { user: { id: string; name: string } })[] }>("/admin/payouts");
export const reviewPayout = (userId: string, approve: boolean, linkedAccountId: string, note: string) =>
  api<PayoutAccount>(`/admin/payout-accounts/${userId}`, { json: { approve, linkedAccountId, note } });
export const revealPayout = (userId: string) => api<{ accountNumber: string; ifsc: string; holderName: string; pan: string }>(`/admin/payout-accounts/${userId}/reveal`);
export const rentPayoutPaid = (id: string) => api(`/admin/rent/${id}/payout-paid`, { method: "POST" });

// reports
export const REPORT_REASONS: Record<string, string> = {
  fake: "Fake or not real", scam: "Asks for money outside TrustRent", wrong_details: "Wrong price, photos or details",
  already_rented: "Already rented", offensive: "Offensive or discriminatory", other: "Something else",
};
export const reportListing = (listingId: string, reason: string, details: string) =>
  api<{ ok: boolean; message: string }>(`/listings/${listingId}/report`, { json: { reason, details } });
export interface AdminReport {
  id: string; reason: string; reasonLabel: string; details: string | null; status: string; createdAt: string; resolution: string | null;
  reporter: { id: string; name: string }; listing: { id: string; title: string; status: string; openReports: number };
}
export const adminReports = (state = "open") => api<AdminReport[]>(`/admin/reports?state=${state}`);
export const resolveReport = (id: string, action: "dismiss" | "unlist", note: string) => api(`/admin/reports/${id}/resolve`, { json: { action, note } });
export interface AdminReview extends ReviewItem { about: string; hidden: boolean; hiddenReason: string | null }
export const adminReviews = () => api<AdminReview[]>("/admin/reviews");
export const hideReview = (id: string, reason: string) => api(`/admin/reviews/${id}/hide`, { json: { reason } });

// audit
export interface AuditRow { id: number; at: string; actor: string; action: string; targetType: string | null; targetId: string | null; details: Record<string, unknown>; ip: string | null }
export const auditLog = (q: { action?: string; actor?: string; target?: string; page?: number }) => {
  const p = new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
  return api<{ total: number; page: number; actions: string[]; rows: AuditRow[] }>(`/admin/audit?${p}`);
};

// DigiLocker
export const digilockerStart = () => api<{ url: string }>("/identity/digilocker/start");
export const digilockerComplete = (code: string, state: string) =>
  api<{ user: User; matched: boolean; pendingReview: boolean; message: string }>("/identity/digilocker/complete", { json: { code, state } });

// Aadhaar eSign and e-stamp
export const startEsign = (depositId: string) => api<AgreementView>(`/deposits/${depositId}/agreement/esign`, { method: "POST" });
export const refreshEsign = (depositId: string) => api<AgreementView>(`/deposits/${depositId}/agreement/esign/refresh`, { method: "POST" });
export function attachEstamp(depositId: string, state: string, certificateNumber: string, amount: number, file: File) {
  const form = new FormData();
  form.append("state", state);
  form.append("certificateNumber", certificateNumber);
  form.append("amount", String(amount));
  form.append("file", file);
  return api<AgreementView>(`/deposits/${depositId}/agreement/estamp`, { form });
}
export const ESTAMP_STATES = ["Andhra Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana",
  "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Puducherry",
  "Punjab", "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Other"];
