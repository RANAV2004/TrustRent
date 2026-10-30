"use client";
import { api, API_URL, getToken } from "./api";
export interface Applicant { name: string; email: string; phone: string; username: string }
export interface OwnerRequest {
  userId: string; status: "submitted" | "approved" | "rejected"; relation: string;
  idDocType: string; idFileName: string; propertyDocType: string; propertyFileName: string;
  propertyAddress: string; submittedAt: string; reviewedAt: string | null; reviewNote: string | null;
  applicant: Applicant;
}
export interface IdRequest {
  id: string; userId: string; docType: string; fileName: string; status: "pending" | "approved" | "rejected";
  submittedAt: string; reviewedAt: string | null; reviewNote: string | null; applicant: Applicant;
}
export const getVerifications = () => api<{ owners: OwnerRequest[]; identities: IdRequest[] }>("/admin/verifications");
export const reviewOwner = (userId: string, approve: boolean, note?: string) =>
  api(`/owner/application/${userId}/review`, { json: { approve, note } });
export const reviewIdentity = (id: string, approve: boolean, note?: string) =>
  api(`/admin/identity/${id}/review`, { json: { approve, note } });
export async function openProtected(path: string, download?: string) {
  const res = await fetch(API_URL + path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("Couldn't open the file.");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  if (download) a.download = download;
  else a.target = "_blank";
  a.rel = "noopener";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
export interface AdminOverview {
  users: { total: number; seekers: number; owners: number; verified: number; banned: number; deleted: number; premium: number };
  listings: { live: number; paused: number; unlisted: number; removed: number };
  deposits: { count: number; held: number; open: number; disputed: number; refunded: number };
  conversations: number; messages: number; premiumRevenue: number; pendingVerifications: number;
}
export interface PremiumInfo { planId: string; plan: string; until: string; active: boolean }
export interface AdminUser {
  id: string; name: string; username: string; email: string; phone: string; accountType: "seeker" | "owner";
  role: string; provider: string; verified: boolean; isAdmin: boolean; isDemo: boolean; premium: PremiumInfo | null;
  createdAt: string; banned: { at: string; reason: string } | null; deletedAt: string | null; listings: number; deposits: number;
}
export interface AdminListing {
  id: string; title: string; area: string; rent: number; deposit: number; bhk: number;
  status: "live" | "paused" | "removed" | "blocked"; adminNote: string | null; listedAt: string; sample: boolean;
  conversations: number; owner: { id: string; name: string; email: string; banned: boolean };
}
export interface AdminConversation {
  id: string; listing: { id: string; title: string }; seeker: { id: string; name: string };
  owner: { id: string; name: string }; messages: number; updatedAt: string; last: string;
}
export interface AdminMessage {
  id: string; senderName: string; from: "seeker" | "owner"; kind: "text" | "visit"; text?: string; createdAt: string;
  visit?: { slots: string[]; status: string; acceptedSlot?: string };
}
export interface AdminPremium {
  plans: { id: string; label: string; days: number; price: number }[];
  members: (AdminUser & { paid: number })[];
  payments: { id: string; user: { id: string; name: string }; plan: string; amount: number; provider: string; paidAt: string }[];
}
export const getOverview = () => api<AdminOverview>("/admin/overview");
export const getUsers = () => api<AdminUser[]>("/admin/users");
export const banUser = (id: string, reason: string) => api<{ user: AdminUser }>(`/admin/users/${id}/ban`, { json: { reason } });
export const unbanUser = (id: string) => api<{ user: AdminUser }>(`/admin/users/${id}/unban`, { method: "POST" });
export const deleteUser = (id: string) => api<{ ok: boolean }>(`/admin/users/${id}`, { method: "DELETE" });
export const getAdminListings = () => api<AdminListing[]>("/admin/listings");
export const unlistListing = (id: string, reason: string) => api<AdminListing>(`/admin/listings/${id}/unlist`, { json: { reason } });
export const relistListing = (id: string) => api<AdminListing>(`/admin/listings/${id}/relist`, { method: "POST" });
export const getConversations = () => api<AdminConversation[]>("/admin/conversations");
export const getConversationMessages = (id: string) => api<AdminMessage[]>(`/admin/conversations/${id}/messages`);
export const getPremium = () => api<AdminPremium>("/admin/premium");
export const revokePremium = (id: string) => api<{ user: AdminUser }>(`/admin/premium/${id}/revoke`, { method: "POST" });
export interface LedgerBlock {
  seq: number; depositId: string; kind: "deposit" | "settlement"; amounts: Record<string, number>;
  dataHash: string; prevHash: string; hash: string; chainTx: string | null; at: string;
}
export const getLedger = () => api<{ intact: boolean; genesis: string; network: string; blocks: LedgerBlock[] }>("/admin/ledger");
